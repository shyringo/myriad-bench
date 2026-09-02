"""Agent interfaces — pluggable, minimal.

Any Agent implements:
    step(messages: list[dict], tools: list[dict], world) -> action

action: {"type": "reply", "text": str}
     |  {"type": "tool", "tool": str, "args": dict}
     |  {"type": "error", "text": str}
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _system_proxy():
    """Discover an HTTP(S) proxy: env vars first, then Windows registry.
    The proxy is used only if its port is actually alive (a dead registry
    proxy silently breaks urllib otherwise)."""
    import socket
    candidates = []
    for env in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        v = os.environ.get(env)
        if v:
            candidates.append(v)
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        if winreg.QueryValueEx(k, "ProxyEnable")[0]:
            server = winreg.QueryValueEx(k, "ProxyServer")[0]
            if server:
                candidates.append("http://" + server)
    except Exception:
        pass
    for c in candidates:
        host_port = c.split("//")[-1].rstrip("/")
        host, _, port = host_port.partition(":")
        try:
            s = socket.create_connection((host, int(port or 80)), timeout=1.0)
            s.close()
            return c
        except Exception:
            continue
    return None


_PROXY = _system_proxy()

# Cloudflare (and similar edge layers) return 403/1010 to python's default
# urllib User-Agent; a plain browser UA is sufficient to pass.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class Agent:
    name = "base"

    def __init__(self):
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def step(self, messages, tools, world):
        raise NotImplementedError


class ReplayAgent(Agent):
    """Scripted agent for tests: returns actions from a list, in order."""
    name = "replay"

    def __init__(self, actions: list[dict]):
        super().__init__()
        self._actions = list(actions)
        self._i = 0

    def step(self, messages, tools, world):
        if self._i < len(self._actions):
            a = self._actions[self._i]
            self._i += 1
            return a
        return {"type": "reply", "text": "DONE"}


class EchoAgent(Agent):
    name = "echo"

    def step(self, messages, tools, world):
        return {"type": "reply", "text": "Received. Will do."}


class OpenAICompatAgent(Agent):
    """Stdlib-only client for any OpenAI-compatible /chat/completions endpoint.

    Env: MYRIAD_API_KEY or OPENAI_API_KEY; base URL default OpenAI.
    """

    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        super().__init__()
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("MYRIAD_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("no API key: set MYRIAD_API_KEY or OPENAI_API_KEY (or pass api_key=)")

    def _call(self, messages, tools):
        body = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            funcs = []
            for t in tools:
                props = {k: {kk: vv for kk, vv in v.items() if kk != "required"}
                         for k, v in t.get("parameters", {}).items()}
                req = [k for k, v in t.get("parameters", {}).items() if v.get("required")]
                funcs.append({"type": "function", "function": {
                    "name": t["name"], "description": t.get("description", ""),
                    "parameters": {"type": "object", "properties": props, "required": req}}})
            body["tools"] = funcs
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}",
                     "User-Agent": _UA},
        )
        opener = urllib.request.build_opener()
        if _PROXY:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": _PROXY, "https": _PROXY}))
        with opener.open(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        if "usage" in data:
            u = data["usage"]
            self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            self.usage["completion_tokens"] += u.get("completion_tokens", 0)
        return msg

    def step(self, messages, tools, world):
        try:
            msg = self._call(messages, tools)
        except urllib.error.HTTPError as e:
            return {"type": "error", "text": f"http {e.code}: {e.read()[:200]!r}"}
        except Exception as e:
            return {"type": "error", "text": str(e)[:300]}
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]["function"]
            try:
                args = json.loads(tc.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            return {"type": "tool", "tool": tc.get("name", ""), "args": args}
        return {"type": "reply", "text": msg.get("content") or ""}