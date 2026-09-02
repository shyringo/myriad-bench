"""Session runner — drives one agent through a session event stream.

Produces a full trace (transcript + env snapshots + reads/writes + usage)
from which all metrics are computed. Deterministic and replayable.
"""

from __future__ import annotations

import json
import os

from .envs import World, stable_hash
from .verifiers import artifacts_from_trace


# --------------------------------------------------------------------------
# tools (applied by the runner; reads/writes logged against the current unit)
# --------------------------------------------------------------------------

def _tools_spec() -> list[dict]:
    return [
        {"name": "fs_read", "description": "read a file from the workspace",
         "parameters": {"path": {"type": "string", "description": "relative path", "required": True}}},
        {"name": "fs_write", "description": "create/overwrite a workspace file",
         "parameters": {"path": {"type": "string", "required": True},
                        "content": {"type": "string", "required": True}}},
        {"name": "fs_list", "description": "list workspace files",
         "parameters": {"prefix": {"type": "string", "required": False}}},
        {"name": "cal_list", "description": "list calendar events",
         "parameters": {}},
        {"name": "cal_add", "description": "add a calendar event",
         "parameters": {"start": {"type": "string", "required": True},
                        "end": {"type": "string", "required": True},
                        "title": {"type": "string", "required": True}}},
        {"name": "mail_list", "description": "list sent mail", "parameters": {}},
        {"name": "mail_send", "description": "send an email",
         "parameters": {"to": {"type": "string", "required": True},
                        "subject": {"type": "string", "required": True},
                        "body": {"type": "string", "required": True},
                        "cc": {"type": "string", "required": False},
                        "attach": {"type": "string", "required": False}}},
        {"name": "dsv_table", "description": "read a CSV-like table from the data source",
         "parameters": {"name": {"type": "string", "required": True}}},
        {"name": "dsv_doc", "description": "read a document from the data source",
         "parameters": {"name": {"type": "string", "required": True}}},
        {"name": "dsv_quote", "description": "read a current market quote",
         "parameters": {"ticker": {"type": "string", "required": True}}},
        {"name": "code_read", "description": "read a file from the code repo",
         "parameters": {"path": {"type": "string", "required": True}}},
        {"name": "code_write", "description": "write a file in the code repo",
         "parameters": {"path": {"type": "string", "required": True},
                        "content": {"type": "string", "required": True}}},
        {"name": "code_list", "description": "list code repo files", "parameters": {}},
    ]


def _tool_handlers(world: World, current_unit):
    def unit():
        return current_unit[0]

    handlers = {
        "fs_read": lambda a: (world.envs["fs"].read(a["path"], unit(), world), None),
        "fs_write": lambda a: world.envs["fs"].write(a["path"], a["content"], unit(), world),
        "fs_list": lambda a: (world.envs["fs"].list(a.get("prefix", "")), None),
        "cal_list": lambda a: (world.envs["calendar"].list_events(), None),
        "cal_add": lambda a: world.envs["calendar"].add(a["start"], a["end"], a["title"], unit(), world),
        "mail_list": lambda a: (world.envs["email"].unread() + [{"sent": m} for m in world.envs["email"].sent], None),
        "mail_send": lambda a: world.envs["email"].send(a["to"], a["subject"], a["body"],
                                                        a.get("cc", ""), a.get("attach", ""), unit(), world),
        "dsv_table": lambda a: (world.envs["dsv"].read_table(a["name"], unit(), world), None),
        "dsv_doc": lambda a: (world.envs["dsv"].read_doc(a["name"], unit(), world), None),
        "dsv_quote": lambda a: (world.envs["dsv"].quote(a["ticker"], unit(), world), None),
        "code_read": lambda a: (world.envs["code"].read(a["path"], unit(), world), None),
        "code_write": lambda a: world.envs["code"].write(a["path"], a["content"], unit(), world),
        "code_list": lambda a: (world.envs["code"].list(), None),
    }
    return handlers


def _fmt_result(r):
    if r is None:
        return "ok"
    if isinstance(r, str):
        return r
    try:
        return json.dumps(r, ensure_ascii=False, default=str)[:4000]
    except Exception:
        return str(r)[:4000]


def _turn_snapshot(world: World, unit_id: str | None) -> dict:
    """Content-valued snapshot of the keys the current unit touched (for probes)."""
    snap = {}
    keys = sorted(world._touched.get(unit_id, set()))
    for env_id, key in keys:
        env = world.envs[env_id]
        kind = env.kind
        if kind == "fs":
            rel = key[3:]
            snap.setdefault(env_id, {"kind": kind, "state": {"files": {}}})
            if world.envs[env_id].files.get(rel) is not None:
                snap[env_id]["state"]["files"][rel] = env.files[rel]
        elif kind == "code":
            rel = key[5:]
            snap.setdefault(env_id, {"kind": kind, "state": {"files": {}}})
            if env.files.get(rel) is not None:
                snap[env_id]["state"]["files"][rel] = env.files[rel]
        elif kind == "calendar":
            snap.setdefault(env_id, {"kind": kind, "state": env.snapshot()})
        elif kind == "email":
            snap.setdefault(env_id, {"kind": kind, "state": env.snapshot()})
    return snap


SYSTEM_PROMPT = (
    "You are an autonomous assistant in a long working session. You receive tasks, "
    "questions and interruptions over time, all in this one conversation. "
    "Use the provided tools to inspect and modify your persistent workspace; "
    "when a task is done, reply to the user with a short confirmation. "
    "If a task is interrupted and later resumed, continue exactly where you left off. "
    "Keep track of everything you produce — later tasks may depend on earlier artifacts."
)


def run_session(session: dict, agent, out_dir: str | None = None,
                max_turns_per_event: int = 10, max_total_turns: int = 200) -> dict:
    world = World(session.get("world", {}))
    units = {u["id"]: u for u in session["units"]}
    current_unit = [None]  # mutable holder for handlers
    handlers = _tool_handlers(world, current_unit)
    tools = _tools_spec()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    trace = {
        "session_id": session["session_id"],
        "kind": session.get("kind", "mixed"),
        "isolated_unit": session.get("isolated_unit"),
        "agent": agent.name,
        "model": getattr(agent, "model", None),
        "turns": [],
        "segments": {},          # unit_id -> list of turn indices
        "unit_reply": {},
        "reads": [],
        "writes": {},
        "interrupts": [],
        "artifacts": {},         # artifact key -> hash at producer's segment end
        "env_at_unit_end": {},
        "turn_envs": [],         # per-turn touched-key snapshots (probes)
        "env_meta": {eid: world.envs[eid].kind for eid in world.envs},
        "env_final": world.snapshot(),
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }

    total_turns = 0
    turn_i = 0

    def add_turn(role, content, unit, tool=None, args=None, at=None, tool_call_id=None):
        nonlocal turn_i
        entry = {"i": turn_i, "unit": unit, "role": role, "content": content,
                 "tool": tool, "args": args, "at": at,
                 "tool_call_id": tool_call_id or (f"tc{turn_i}" if role == "tool" else None)}
        trace["turns"].append(entry)
        if role == "assistant" and tool:
            messages.append({"role": "assistant", "content": content,
                             "tool_calls": [{"id": tool_call_id or f"tc{turn_i}",
                                               "type": "function",
                                               "function": {"name": tool,
                                                             "arguments": json.dumps(args or {})}}]})
        elif role == "tool":
            messages.append({"role": "tool",
                             "tool_call_id": tool_call_id or f"tc{turn_i}",
                             "content": content})
        else:
            messages.append({"role": role, "content": content})
        if unit:
            trace["segments"].setdefault(unit, []).append(turn_i)
        if role == "assistant":
            trace["turn_envs"].append({"i": turn_i, "unit": unit,
                                       "snapshot": _turn_snapshot(world, unit)})
        turn_i += 1
        return entry

    def agent_loop(ev):
        """Run agent turns until it replies (or budget exhausted)."""
        nonlocal total_turns
        guard = 0
        while guard < max_turns_per_event and total_turns < max_total_turns:
            guard += 1
            total_turns += 1
            action = agent.step(list(messages), tools, world)
            if action["type"] == "reply":
                add_turn("assistant", action["text"], current_unit[0], at=ev.get("at"))
                if current_unit[0]:
                    trace["unit_reply"][current_unit[0]] = action["text"]
                return "reply"
            if action["type"] == "error":
                add_turn("assistant", f"[error] {action['text']}", current_unit[0], at=ev.get("at"))
                return "error"
            if action["type"] == "tool":
                tool, args = action["tool"], action["args"]
                handler = handlers.get(tool)
                if handler is None:
                    add_turn("assistant", f"[unknown tool {tool}]", current_unit[0],
                             tool=tool, args=args, at=ev.get("at"))
                    continue
                try:
                    result = handler(args)
                    if result is None:
                        result, _ = "ok", None
                except Exception as e:
                    result = f"[tool error] {e}"
                txt = _fmt_result(result)
                entry = add_turn("assistant", f"[tool call {tool}]", current_unit[0], tool=tool, args=args, at=ev.get("at"))
                add_turn("tool", txt, current_unit[0], at=ev.get("at"),
                         tool_call_id=f"tc{entry['i']}")
                continue
            add_turn("assistant", "[noop]", current_unit[0], at=ev.get("at"))
            return "noop"
        return "budget"

    def seal_segment(unit_id):
        """Record produced-artifact hashes + touched snapshot at segment end."""
        unit = units.get(unit_id)
        if unit is None:
            return
        keys = set(world._touched.get(unit_id, set()))
        for art in unit.get("produce_artifacts", []):
            env_id, _, rel = art.partition("/")
            env = world.envs.get(env_id)
            val = env.peek(rel) if env else None
            if val is not None:
                keys.add((env_id, art))
                trace["artifacts"][art] = stable_hash(val)
        trace["env_at_unit_end"][unit_id] = world.snapshot_keys(sorted(set(keys)))

    for ev in session["events"]:
        kind = ev["kind"]
        payload = ev.get("payload")
        if kind in ("assign", "inject", "user_message"):
            unit_id = ev.get("unit")
            current_unit[0] = unit_id
            user = ""
            if payload:
                user = payload.get("user", "")
                if payload.get("background"):
                    messages.append({"role": "system",
                                     "content": f"[context] {payload['background']}"})
            add_turn("user", user, unit_id, at=ev.get("at"))
            agent_loop(ev)
            if unit_id:
                seal_segment(unit_id)
        elif kind == "interrupt":
            unit_id = ev.get("unit")
            if unit_id and unit_id in world._touched:
                trace["interrupts"].append({
                    "unit": unit_id, "at": ev.get("at"),
                    "touched_before": world.touched_snapshot(unit_id),
                    "touched_after": None,
                })
            current_unit[0] = None
            add_turn("system", f"[interrupt] {payload.get('reason', '')} — task paused.",
                     None, at=ev.get("at"))
        elif kind == "resume":
            unit_id = ev.get("unit")
            current_unit[0] = unit_id
            for it in reversed(trace["interrupts"]):
                if it["unit"] == unit_id and it["touched_after"] is None:
                    it["touched_after"] = world.touched_snapshot(unit_id)
                    break
            add_turn("system", f"[resume] {payload.get('note', '')}", unit_id, at=ev.get("at"))
            agent_loop(ev)
            if unit_id:
                seal_segment(unit_id)
        elif kind == "env_change":
            add_turn("system", f"[environment] {payload}", None, at=ev.get("at"))
        elif kind == "tick":
            add_turn("system", f"[time passes: {ev.get('at')}]", None, at=ev.get("at"))
        elif kind == "done":
            break

    trace["unit_reply"] = {u: r for u, r in trace["unit_reply"].items()}
    trace["usage"] = getattr(agent, "usage", {"prompt_tokens": 0, "completion_tokens": 0})
    trace["reads"] = world._reads
    trace["writes"] = {u: sorted(k for _, k in keys) for u, keys in world._touched.items()}
    trace["env_final"] = world.snapshot()

    for it in trace["interrupts"]:
        if it["touched_after"] is None:
            it["touched_after"] = {}
    _ = artifacts_from_trace(trace)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/{session['session_id']}-{agent.name}.json", "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2, default=str)
    return trace