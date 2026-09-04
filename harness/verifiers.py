"""MyriadBench verifiers — deterministic, config-driven task verification.

Every verifier receives (world, unit, trace, ctx) and returns
{"score": 0..1, "checks": [{"name": str, "pass": bool, "detail": str}]}.

ctx:
  artifacts : {artifact_key: stable_hash} captured when the producing unit finished
  checkpoint: optional verifier-id to evaluate a sub-verifier (switch-cost probes)
  final_reply: last assistant reply of the unit's segment

Canonical config fields per type (all under unit["verifier"]["config"]):
  file_created       {path}
  file_contains      {path, patterns:[str]}
  json_path_equals   {path, jpath: "a[0].b", expected: any}
  numeric_assert     {path or source:"reply", rows:[{col, op, value, tol}]}  # CSV cols
  csv_rows_match     {path, must_include_rows:[{col:value,...}], total_rows_expected}
  code_passes        {file, hidden_tests: str, marker: str, timeout_s}
  calendar_invariant {no_overlap: bool, requires_events:[{start,end,title_sub}]}
  email_checks       {requires:[{to, subject_sub, body_sub, cc_sub, attach_sub}]}
  constraint_solver  {path, must_include:[], order:[str], budget_cap}
  keyword_structure  {path or source:"reply", must_include:[], must_not_include:[],
                      min_words, structure_order:[str]}
  state_web          {obligation:{unit, artifact}}
  composite          {children:[verifier...]} — weighted mean by verifier["weight"]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

from .envs import stable_hash

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _fs(world, path):
    fs = world.envs["fs"]
    return fs.read(path)


def _file_content(world, path):
    if path == "reply":
        return None
    env_id, _, rel = path.partition("/")
    env = world.envs.get(env_id)
    if env is None or not hasattr(env, "read"):
        return None
    return env.read(rel)


def _check(name, ok, detail=""):
    return {"name": name, "pass": bool(ok), "detail": detail}


def _match_pattern(text, pat):
    try:
        return re.search(pat, text, re.IGNORECASE) is not None
    except re.error:
        return pat.lower() in text.lower()


# --------------------------------------------------------------------------
# individual verifiers
# --------------------------------------------------------------------------

def v_file_created(world, unit, trace, ctx, cfg):
    return {"score": 1.0 if _file_content(world, cfg["path"]) is not None else 0.0,
            "checks": [_check("file_created", _file_content(world, cfg["path"]) is not None, cfg["path"])]}


def v_file_contains(world, unit, trace, ctx, cfg):
    text = _file_content(world, cfg["path"]) or ""
    checks = [_check(f"contains {p[:40]}", _match_pattern(text, p)) for p in cfg["patterns"]]
    return {"score": sum(c["pass"] for c in checks) / len(checks), "checks": checks}


def v_json_path_equals(world, unit, trace, ctx, cfg):
    text = _file_content(world, cfg["path"]) or ""
    try:
        data = json.loads(text)
        cur = data
        for part in cfg["jpath"].replace("[", ".").replace("]", "").split("."):
            part = part.strip()
            if not part:
                continue
            if isinstance(cur, list):
                cur = cur[int(part)]
            else:
                cur = cur[part]
        ok = cur == cfg["expected"]
    except Exception:
        ok = False
    return {"score": 1.0 if ok else 0.0,
            "checks": [_check("json_path_equals", ok, f"{cfg['jpath']} == {cfg['expected']!r}")]}


def _csv_rows(path_content):
    if not path_content:
        return [], []
    lines = [l for l in path_content.strip().splitlines() if l.strip()]
    if not lines:
        return [], []
    cols = [c.strip() for c in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        vals = [v.strip() for v in line.split(",")]
        rows.append(dict(zip(cols, vals)))
    return cols, rows


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def v_numeric_assert(world, unit, trace, ctx, cfg):
    if cfg.get("source") == "reply":
        text = ctx.get("final_reply") or ""
        nums = [float(n) for n in NUM_RE.findall(text)]
        checks = []
        for i, (op, value, tol) in enumerate([(c["op"], c["value"], c.get("tol", 1e-6)) for c in cfg["rows"]]):
            got = nums[-1] if nums else None
            ok = _apply_op(got, op, value, tol)
            checks.append(_check(f"reply {op} {value}", ok, f"got {got}"))
        return {"score": sum(c["pass"] for c in checks) / len(checks), "checks": checks}
    path = cfg["path"]
    _, rows = _csv_rows(_file_content(world, path))
    checks = []
    for c in cfg["rows"]:
        col, op, value, tol = c["col"], c["op"], c["value"], c.get("tol", 1e-6)
        vals = [_num(r.get(col)) for r in rows if col in r]
        ok_rows = sum(1 for v in vals if v is not None and _apply_op(v, op, value, tol))
        ok = len(vals) > 0 and ok_rows == len(vals)
        checks.append(_check(f"{col} {op} {value}", ok, f"{ok_rows}/{len(vals)} rows"))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 0.0, "checks": checks}


def _apply_op(got, op, value, tol):
    if got is None:
        return False
    if op == "eq":
        return abs(got - value) <= tol
    if op == "approx":
        return abs(got - value) <= tol * max(1.0, abs(value))
    if op == "gt":
        return got > value
    if op == "gte":
        return got >= value
    if op == "lt":
        return got < value
    if op == "lte":
        return got <= value
    return False


def v_csv_rows_match(world, unit, trace, ctx, cfg):
    _, rows = _csv_rows(_file_content(world, cfg["path"]))
    checks = []
    for want in cfg["must_include_rows"]:
        ok = any(all(str(r.get(k)) == str(v) for k, v in want.items()) for r in rows)
        checks.append(_check(f"row {want}", ok))
    if "total_rows_expected" in cfg:
        ok = len(rows) == cfg["total_rows_expected"]
        checks.append(_check("row count", ok, f"{len(rows)} vs {cfg['total_rows_expected']}"))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 0.0, "checks": checks}


def v_code_passes(world, unit, trace, ctx, cfg):
    content = _file_content(world, cfg["file"])
    if content is None:
        return {"score": 0.0, "checks": [_check("code_passes", False, "file missing")]}
    if "PYTHONHASHSEED" not in os.environ:
        os.environ["PYTHONHASHSEED"] = "0"
    test_src = content + "\n\n" + cfg["hidden_tests"]
    try:
        with tempfile.TemporaryDirectory() as td:
            tf = os.path.join(td, "harness_test.py")
            with open(tf, "w", encoding="utf-8") as f:
                f.write(test_src)
            proc = subprocess.run([sys.executable, tf], capture_output=True, text=True,
                                  timeout=cfg.get("timeout_s", 15), cwd=td)
            ok = proc.returncode == 0 and cfg.get("marker", "ALL_TESTS_PASSED") in proc.stdout
            detail = ""
            if not ok:
                detail = (proc.stderr or proc.stdout or "")[-300:]
            return {"score": 1.0 if ok else 0.0,
                    "checks": [_check("code_passes", ok, detail)]}
    except subprocess.TimeoutExpired:
        return {"score": 0.0, "checks": [_check("code_passes", False, "timeout")]}
    except Exception as e:
        return {"score": 0.0, "checks": [_check("code_passes", False, str(e)[:200])]}


def v_calendar_invariant(world, unit, trace, ctx, cfg):
    cal = world.envs.get("calendar")
    if cal is None:
        return {"score": 0.0, "checks": [_check("calendar_invariant", False, "calendar env missing")]}
    checks = []
    if cfg.get("no_overlap"):
        bad = cal.overlaps()
        checks.append(_check("no overlap", not bad, f"{len(bad)} conflicts"))
    for want in cfg.get("requires_events", []):
        ok = any(e["start"] == want["start"] and e["end"] == want["end"]
                 and want.get("title_sub", "").lower() in e["title"].lower() for e in cal.events)
        checks.append(_check(f"event {want.get('title_sub')} {want['start']}", ok))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 1.0, "checks": checks}


def v_email_checks(world, unit, trace, ctx, cfg):
    sent = world.envs["email"].sent
    checks = []
    for want in cfg["requires"]:
        ok = any(
            m.get("to") == want["to"]
            and want.get("subject_sub", "").lower() in m.get("subject", "").lower()
            and want.get("body_sub", "").lower() in m.get("body", "").lower()
            and want.get("cc_sub", "") in (m.get("cc") or "")
            and want.get("attach_sub", "") in (m.get("attach") or "")
            for m in sent
        )
        checks.append(_check(f"mail to {want['to']}", ok))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 1.0, "checks": checks}


def v_constraint_solver(world, unit, trace, ctx, cfg):
    text = _file_content(world, cfg["path"]) or ""
    checks = [_check(f"must_include {p[:30]}", _match_pattern(text, p)) for p in cfg.get("must_include", [])]
    for seq in cfg.get("order", []):
        idx = [text.lower().find(s.lower()) for s in seq]
        ok = all(i >= 0 for i in idx) and idx == sorted(idx)
        checks.append(_check(f"order {seq[0][:20]}..{seq[-1][:20]}", ok))
    if cfg.get("budget_cap") is not None:
        spent = sum(float(n) for n in NUM_RE.findall(text))
        checks.append(_check(f"budget <= {cfg['budget_cap']}", spent <= cfg["budget_cap"], f"sum~{spent:.2f}"))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 1.0, "checks": checks}


def v_keyword_structure(world, unit, trace, ctx, cfg):
    if cfg.get("source") == "reply":
        text = ctx.get("final_reply") or ""
    else:
        text = _file_content(world, cfg["path"]) or ""
    checks = [_check(f"include {p[:30]}", _match_pattern(text, p)) for p in cfg.get("must_include", [])]
    for p in cfg.get("must_not_include", []):
        checks.append(_check(f"exclude {p[:30]}", not _match_pattern(text, p)))
    if cfg.get("min_words"):
        n = len(text.split())
        checks.append(_check("min_words", n >= cfg["min_words"], f"{n} words"))
    for seq in cfg.get("structure_order", []):
        idx = [text.lower().find(s.lower()) for s in seq]
        ok = all(i >= 0 for i in idx) and idx == sorted(idx)
        checks.append(_check(f"structure {seq[0][:20]}..{seq[-1][:20]}", ok))
    return {"score": sum(c["pass"] for c in checks) / len(checks) if checks else 1.0, "checks": checks}


def v_state_web(world, unit, trace, ctx, cfg):
    obl = cfg["obligation"]
    key = obl["artifact"]
    certified = (ctx.get("artifacts") or {}).get(key)
    env_id, _, rel = key.partition("/")
    env = world.envs.get(env_id)
    val = env.peek(rel) if env else None
    cur_hash = stable_hash(val) if val is not None else None
    consumed = world.artifact_consumed(unit["id"], key)
    ok = certified is not None and cur_hash == certified and consumed
    return {"score": 1.0 if ok else 0.0,
            "checks": [_check("state_web", ok, f"{key} certified={certified} cur={cur_hash} consumed={consumed}")]}


def v_composite(world, unit, trace, ctx, cfg):
    children = cfg["children"]
    results = [verify(world, unit, trace, ctx, child) for child in children]
    denom = sum(c.get("weight", 1) for c in children)
    score = sum(r["score"] * c.get("weight", 1) for r, c in zip(results, children)) / denom if denom else 0.0
    checks = [ch for r in results for ch in r["checks"]]
    return {"score": score, "checks": checks}


def v_llm_judge(world, unit, trace, ctx, cfg):
    return {"score": None, "checks": [{"name": "llm_judge", "pass": None,
                                        "detail": "skipped: needs provider; see docs/llm-judge.md"}]}


VERIFIERS = {
    "file_created": v_file_created,
    "file_contains": v_file_contains,
    "json_path_equals": v_json_path_equals,
    "numeric_assert": v_numeric_assert,
    "csv_rows_match": v_csv_rows_match,
    "code_passes": v_code_passes,
    "calendar_invariant": v_calendar_invariant,
    "email_checks": v_email_checks,
    "constraint_solver": v_constraint_solver,
    "keyword_structure": v_keyword_structure,
    "state_web": v_state_web,
    "composite": v_composite,
    "llm_judge": v_llm_judge,
}


def verify(world, unit: dict, trace: dict, ctx: dict, verifier: dict | None = None):
    """Run one verifier (default: unit's main verifier)."""
    v = verifier or unit.get("verifier")
    if v is None:
        return {"score": 0.0, "checks": [{"name": "no_verifier", "pass": False, "detail": ""}]}
    fn = VERIFIERS.get(v["type"])
    if fn is None:
        return {"score": None, "checks": [{"name": v["type"], "pass": None, "detail": "unknown type"}]}
    return fn(world, unit, trace, ctx, v.get("config", {}))


def checkpoint_probe(world, unit: dict, trace: dict):
    """Evaluate the first checkpoint sub-verifier of a unit (switch-cost probes)."""
    cps = unit.get("checkpoints") or []
    if not cps:
        return None
    return verify(world, unit, trace, {"artifacts": {}, "final_reply": ""}, cps[0])["score"]


def artifacts_from_trace(trace: dict) -> dict:
    """{artifact_key: hash} produced at unit-segment ends (state-web certification)."""
    return trace.get("artifacts", {})