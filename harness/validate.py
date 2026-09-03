"""Lightweight schema validation (stdlib-only; no jsonschema dependency)."""

from __future__ import annotations

import json
import os

UNIT_REQUIRED = ["id", "family", "title", "brief", "tools", "verifier", "priority", "time_budget_min"]
SESSION_REQUIRED = ["schema_version", "session_id", "meta", "world", "units", "events"]
EVENT_KINDS = {"assign", "user_message", "interrupt", "resume", "inject", "env_change", "tick", "done"}
VERIFIER_TYPES = {
    "file_created", "file_contains", "json_path_equals", "numeric_assert", "csv_rows_match",
    "calendar_invariant", "email_checks", "code_passes", "constraint_solver",
    "keyword_structure", "state_web", "composite", "llm_judge",
}
ENV_KINDS = {"fs", "calendar", "email", "dsv", "code"}


def validate_session(session: dict) -> list[str]:
    errs = []
    if session.get("schema_version") != "0.1.0":
        errs.append("schema_version must be 0.1.0")
    if session.get("kind") not in ("mixed", "isolated"):
        errs.append("kind must be mixed|isolated")
    for k in SESSION_REQUIRED:
        if k not in session:
            errs.append(f"missing top-level key {k}")
    if "world" in session:
        for env_id, block in session["world"].items():
            if block.get("kind") not in ENV_KINDS:
                errs.append(f"world.{env_id}: bad kind")
    seen = set()
    for u in session.get("units", []):
        for k in UNIT_REQUIRED:
            if k not in u:
                errs.append(f"unit {u.get('id')}: missing {k}")
        if u.get("id") in seen:
            errs.append(f"duplicate unit id {u['id']}")
        seen.add(u.get("id"))
        vt = u.get("verifier", {}).get("type")
        if vt not in VERIFIER_TYPES:
            errs.append(f"unit {u.get('id')}: bad verifier type {vt}")
        for dep in u.get("depends_on", []):
            if dep.get("unit") not in seen and dep.get("unit") not in {x.get("id") for x in session.get("units", [])}:
                errs.append(f"unit {u.get('id')}: depends_on unknown unit {dep.get('unit')}")
    for ev in session.get("events", []):
        if ev.get("kind") not in EVENT_KINDS:
            errs.append(f"event {ev.get('id')}: bad kind {ev.get('kind')}")
        if ev.get("unit") and ev["unit"] not in seen:
            errs.append(f"event {ev.get('id')}: unknown unit {ev['unit']}")
    return errs


def load_and_validate(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data, validate_session(data)


def validate_dir(directory: str) -> dict:
    out = {}
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(directory, fn)
        data, errs = load_and_validate(path)
        out[fn] = errs
    return out