"""MyriadBench harness — deterministic in-memory environments.

World state is a dict of env containers; every mutation is logged so that
state-web consumption and resume fidelity can be verified.
All envs are JSON-serializable and replayable.
"""

from __future__ import annotations

import hashlib
import json


def stable_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


class World:
    """Persistent world state: a set of named env containers + read log."""

    def __init__(self, spec: dict):
        self.envs = {}
        self._reads = []  # (env_id, artifact_key, unit_id)
        self._touched = {}  # unit_id -> set of (env_id, key) it wrote
        for env_id, block in (spec or {}).items():
            kind = block.get("kind")
            state = block.get("state", {})
            self.envs[env_id] = make_env(kind, state)

    # -- logging ---------------------------------------------------------

    def log_read(self, env_id: str, key: str, unit_id: str | None):
        self._reads.append({"env": env_id, "key": key, "unit": unit_id, "ts": len(self._reads)})

    def log_write(self, env_id: str, key: str, unit_id: str | None):
        self._touched.setdefault(unit_id, set()).add((env_id, key))

    def reads_of(self, unit_id: str) -> list[dict]:
        return [r for r in self._reads if r["unit"] == unit_id]

    def artifact_consumed(self, unit_id: str, key: str) -> bool:
        return any(r["env"] == key.split("/", 1)[0] and r["key"] == key for r in self._reads if r["unit"] == unit_id)

    # -- snapshot / diff --------------------------------------------------

    def snapshot(self) -> dict:
        return {env_id: env.snapshot() for env_id, env in self.envs.items()}

    def snapshot_keys(self, keys: list[str]) -> dict:
        out = {}
        for env_id, key in keys:
            env = self.envs.get(env_id)
            if env is None:
                continue
            val = env.peek(key)
            if val is not None:
                out[f"{env_id}:{key}"] = stable_hash(val)
        return out

    def touched_snapshot(self, unit_id: str) -> dict:
        return self.snapshot_keys(sorted(self._touched.get(unit_id, set())))

    @staticmethod
    def diff_fraction(before: dict, after: dict) -> float:
        """Fraction of keys in `before` whose value changed in `after`."""
        if not before:
            return 0.0
        changed = sum(1 for k, v in before.items() if after.get(k) != v)
        return changed / len(before)


class FileSystem:
    kind = "fs"

    def __init__(self, state: dict):
        self.files = dict(state.get("files", {}))

    def snapshot(self):
        return {"files": dict(self.files)}

    def peek(self, key: str):
        if key.startswith("fs/"):
            return self.files.get(key[3:])
        return self.files.get(key)

    def read(self, path, unit=None, world=None):
        if world:
            world.log_read("fs", f"fs/{path}", unit)
        return self.files.get(path)

    def write(self, path, content, unit=None, world=None):
        src = self.files.get(path)
        self.files[path] = content
        if world:
            world.log_write("fs", f"fs/{path}", unit)
        return True, f"wrote {path} ({len(content)} chars)" if src is not None else f"created {path}"

    def list(self, prefix=""):
        return sorted(p for p in self.files if p.startswith(prefix))

    def delete(self, path, unit=None, world=None):
        if path in self.files:
            del self.files[path]
            if world:
                world.log_write("fs", f"fs/{path}", unit)
            return True, f"deleted {path}"
        return False, f"no such file {path}"


class Calendar:
    kind = "calendar"

    def __init__(self, state: dict):
        self.events = [dict(e) for e in state.get("events", [])]
        self.owner = state.get("owner", self.__class__.__name__)

    def snapshot(self):
        return {"events": list(self.events), "owner": self.owner}

    def peek(self, key: str):
        return self.events if key in ("events", "calendar/events") else None

    def add(self, start, end, title, unit=None, world=None):
        ev = {"start": start, "end": end, "title": title}
        self.events.append(ev)
        if world:
            world.log_write("calendar", "calendar/events", unit)
        return True, f"added event {title} {start}-{end}"

    def list_events(self):
        return sorted(self.events, key=lambda e: e["start"])

    def overlaps(self) -> list[tuple]:
        evs = sorted(self.events, key=lambda e: e["start"])
        bad = []
        for i in range(1, len(evs)):
            if evs[i]["start"] < evs[i - 1]["end"]:
                bad.append((evs[i - 1], evs[i]))
        return bad


class EmailBox:
    kind = "email"

    def __init__(self, state: dict):
        self.sent = [dict(m) for m in state.get("sent", [])]
        self.inbox = [dict(m) for m in state.get("inbox", [])]

    def snapshot(self):
        return {"sent": list(self.sent), "inbox": list(self.inbox)}

    def peek(self, key: str):
        if key in ("sent", "email/sent"):
            return self.sent
        if key in ("inbox", "email/inbox"):
            return self.inbox
        return None

    def send(self, to, subject, body, cc="", attach="", unit=None, world=None):
        self.sent.append({"to": to, "subject": subject, "body": body, "cc": cc, "attach": attach})
        if world:
            world.log_write("email", "email/sent", unit)
        return True, f"sent to {to}"

    def unread(self):
        return list(self.inbox)


class DSV:
    """Deterministic data source: tables (CSV-like), documents, market quotes."""

    kind = "dsv"

    def __init__(self, state: dict):
        self.tables = {k: {"cols": list(v["cols"]), "rows": [list(r) for r in v["rows"]]}
                       for k, v in state.get("tables", {}).items()}
        self.docs = dict(state.get("docs", {}))
        self.market = dict(state.get("market", {}))

    def snapshot(self):
        return {"tables": self.tables, "docs": self.docs, "market": self.market}

    def peek(self, key: str):
        if key.startswith("dsv/"):
            key = key[4:]
        if key in self.tables:
            return self.tables[key]
        if key in self.docs:
            return self.docs[key]
        if key in self.market:
            return self.market[key]
        return None

    def read_table(self, name, unit=None, world=None):
        if world:
            world.log_read("dsv", f"dsv/tables/{name}", unit)
        return self.tables.get(name)

    def read_doc(self, name, unit=None, world=None):
        if world:
            world.log_read("dsv", f"dsv/docs/{name}", unit)
        return self.docs.get(name)

    def quote(self, ticker, unit=None, world=None):
        if world:
            world.log_read("dsv", f"dsv/market/{ticker}", unit)
        return self.market.get(ticker)


class CodeRepo:
    kind = "code"

    def __init__(self, state: dict):
        self.files = dict(state.get("files", {}))
        self.readme = state.get("readme", "")

    def snapshot(self):
        return {"files": dict(self.files), "readme": self.readme}

    def peek(self, key: str):
        if key.startswith("code/"):
            return self.files.get(key[5:])
        return self.files.get(key)

    def read(self, path, unit=None, world=None):
        if world:
            world.log_read("code", f"code/{path}", unit)
        return self.files.get(path)

    def write(self, path, content, unit=None, world=None):
        self.files[path] = content
        if world:
            world.log_write("code", f"code/{path}", unit)
        return True, f"wrote {path} ({len(content)} chars)"

    def list(self):
        return sorted(self.files)


ENV_KINDS = {"fs": FileSystem, "calendar": Calendar, "email": EmailBox, "dsv": DSV, "code": CodeRepo}


def make_env(kind: str, state: dict):
    cls = ENV_KINDS.get(kind)
    if cls is None:
        raise ValueError(f"unknown env kind {kind!r}")
    return cls(state)