"""Metric computation — turns traces into the MyriadBench metric suite.

Implements the definitions in docs/metrics.md:
  IC (interference coefficient), SC (switch cost), RF (resume fidelity),
  SWC (state-web consistency), LTR (long-tail robustness), BE (budget efficiency),
  SV (survivability, needs multi-length runs — reported as N/A otherwise).

Usage (library):
    from harness.metrics import evaluate
    report = evaluate(session, trace, isolated_traces={unit_id: trace})
"""

from __future__ import annotations

import json
import math

from .envs import World, stable_hash
from .verifiers import verify

EPS = 1e-6


# --------------------------------------------------------------------------
# trace / world reconstruction
# --------------------------------------------------------------------------

def world_from_trace(trace: dict) -> World:
    env_meta = trace.get("env_meta", {})
    env_final = trace.get("env_final", {})
    spec = {}
    for env_id, state in env_final.items():
        spec[env_id] = {"kind": env_meta.get(env_id, "fs"), "state": state}
    w = World(spec)
    w._reads = list(trace.get("reads", []))
    return w


def key_value(env_final: dict, key: str):
    env_id, _, rel = key.partition("/")
    snap = env_final.get(env_id)
    if not snap:
        return None
    if env_id == "fs" or "files" in snap:
        return snap.get("files", {}).get(rel)
    if env_id == "calendar":
        return snap.get("events")
    if env_id == "email":
        return snap.get("sent")
    if env_id == "code":
        return snap.get("files", {}).get(rel)
    return snap.get(rel)


def per_unit_scores(session: dict, trace: dict, artifacts: dict | None = None) -> dict:
    """{unit_id: score in [0,1]} — verifies against the trace's final world state."""
    world = world_from_trace(trace)
    out = {}
    for unit in session["units"]:
        art = artifacts if artifacts is not None else trace.get("artifacts", {})
        ctx = {"artifacts": art, "final_reply": trace.get("unit_reply", {}).get(unit["id"], "")}
        res = verify(world, unit, trace, ctx)
        out[unit["id"]] = {"score": res["score"], "checks": res["checks"],
                           "family": unit.get("family"), "rarity": unit.get("rarity", 1)}
    return out


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

def interference(retention: dict) -> dict:
    rs = list(retention.values())
    if not rs:
        return {"IC": None, "retention": retention}
    R = math.exp(sum(math.log(max(r, EPS)) for r in rs) / len(rs))
    return {"IC": round(1 - R, 4), "retention": {k: round(v, 4) for k, v in retention.items()}}


def retention_map(mixed: dict, isolated: dict) -> dict:
    out = {}
    for uid, row in mixed.items():
        iso = isolated.get(uid, {}).get("score")
        if iso is None:
            iso = 0.0
        out[uid] = min(row["score"] / max(iso, EPS), 1.0)
    return out


def switch_cost(session: dict, trace: dict, tau: int = 3) -> dict:
    """Checkpoint-probe success in the warm window vs the steady window after a switch.

    Windows are counted in *assistant turns within the segment* (tool turns and
    replies alike); the probe reads the env snapshot after the last turn of each
    window.
    """
    units = {u["id"]: u for u in session["units"]}
    turn_envs = {te["i"]: te["snapshot"] for te in trace.get("turn_envs", [])}
    assistant_idx = [t["i"] for t in trace["turns"] if t["role"] == "assistant"]
    segments = []  # (unit_id, [assistant turn indices])
    cur, seg = None, []
    for i, t in zip(assistant_idx, [t for t in trace["turns"] if t["role"] == "assistant"]):
        if t["unit"] != cur:
            if cur is not None:
                segments.append((cur, seg))
            cur, seg = t["unit"], []
        seg.append(i)
    if cur is not None:
        segments.append((cur, seg))

    probes = []
    skipped = 0
    for idx, (uid, turns_in_seg) in enumerate(segments):
        unit = units.get(uid)
        if unit is None or not unit.get("checkpoints") or len(turns_in_seg) < 2 * tau:
            skipped += 1
            continue
        prev_family = units.get(segments[idx - 1][0], {}).get("family") if idx > 0 else None
        warm_end = turns_in_seg[min(tau - 1, len(turns_in_seg) - 1)]
        steady_end = turns_in_seg[min(2 * tau - 1, len(turns_in_seg) - 1)]
        if steady_end <= warm_end:
            skipped += 1
            continue
        warm_world = World(turn_envs.get(warm_end, {}) or {})
        steady_world = World(turn_envs.get(steady_end, {}) or {})
        from .verifiers import checkpoint_probe
        warm = checkpoint_probe(warm_world, unit, trace)
        steady = checkpoint_probe(steady_world, unit, trace)
        if warm is None or steady is None:
            skipped += 1
            continue
        probes.append({"unit": uid, "family": unit.get("family"),
                       "same_family_switch": prev_family == unit.get("family"),
                       "warm": warm, "steady": steady,
                       "cost": round(steady - warm, 4)})
    if not probes:
        return {"SC": None, "SC_first": None, "SC_same": None, "probes": [], "skipped": skipped}
    costs = [p["cost"] for p in probes]
    first = [p["cost"] for p in probes if not p["same_family_switch"]]
    same = [p["cost"] for p in probes if p["same_family_switch"]]
    return {
        "SC": round(sum(costs) / len(costs), 4),
        "SC_first": round(sum(first) / len(first), 4) if first else None,
        "SC_same": round(sum(same) / len(same), 4) if same else None,
        "probes": probes, "skipped": skipped,
    }


def resume_fidelity(session: dict, trace: dict, isolated_traces: dict) -> dict:
    """Continuity of an interrupted unit vs its uninterrupted reference run.

    Compares the unit's DELIVERED artifacts (produce_artifacts), falling back
    to touched keys when a unit declares none — extra reasonable work the agent
    did on the side is not counted as drift.
    """
    units = {u["id"]: u for u in session["units"]}
    mixed_final = trace.get("env_final", {})
    out = []
    for it in trace.get("interrupts", []):
        uid = it["unit"]
        iso = isolated_traces.get(uid)
        if iso is None:
            out.append({"unit": uid, "RF": None, "detail": "no isolated reference"})
            continue
        declared = units.get(uid, {}).get("produce_artifacts", [])
        touched = trace.get("writes", {}).get(uid, []) or []
        keys = declared if declared else touched
        keys = [k for k in keys if k in touched] or keys
        diffs = []
        for key in keys:
            v1 = key_value(mixed_final, key)
            v2 = key_value(iso.get("env_final", {}), key)
            if v1 is not None and v2 is not None:
                diffs.append(stable_hash(v1) == stable_hash(v2))
        if not diffs:
            out.append({"unit": uid, "RF": None, "detail": "no comparable state"})
            continue
        rf = sum(diffs) / len(diffs)
        out.append({"unit": uid, "RF": round(rf, 4), "keys": len(diffs)})
    rfs = [o["RF"] for o in out if o["RF"] is not None]
    return {"RF": round(sum(rfs) / len(rfs), 4) if rfs else None, "per_unit": out}


def state_web(session: dict, trace: dict) -> dict:
    obligations = []
    for unit in session["units"]:
        for dep in unit.get("depends_on", []):
            obligations.append({"consumer": unit["id"], **dep})
    if not obligations:
        return {"SWC": None, "obligations": []}
    env_final = trace.get("env_final", {})
    certified_map = trace.get("artifacts", {})
    reads = trace.get("reads", [])
    rows = []
    for ob in obligations:
        key = ob["artifact"]
        certified = certified_map.get(key)
        cur = stable_hash(key_value(env_final, key)) if key_value(env_final, key) is not None else None
        consumed = any(r.get("unit") == ob["consumer"] and r.get("key") == key for r in reads)
        ok = certified is not None and cur == certified and consumed
        rows.append({"consumer": ob["consumer"], "producer": ob["unit"], "artifact": key,
                     "certified": certified, "current": cur, "consumed": consumed, "ok": ok})
    swc = sum(r["ok"] for r in rows) / len(rows)
    return {"SWC": round(swc, 4), "obligations": rows}


def long_tail(mixed: dict, isolated: dict) -> dict:
    ret = retention_map(mixed, isolated)
    buckets = {}
    for uid, row in mixed.items():
        r = row.get("rarity", 1)
        buckets.setdefault(r, []).append(ret[uid])
    return {"LTR": {str(r): round(sum(v) / len(v), 4) for r, v in buckets.items() if v},
            "by_family": {}}


def budget_efficiency(session: dict, trace: dict, mixed: dict) -> dict:
    usage = trace.get("usage", {})
    tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    if not tokens:
        chars = sum(len(t.get("content", "")) for t in trace.get("turns", []))
        tokens = max(int(chars / 4), 1)
        estimated = True
    else:
        estimated = False
    passed = sum(row["score"] for row in mixed.values())
    return {"BE": round(passed / tokens, 6) if tokens else None,
            "tokens": tokens, "passed_weight": round(passed, 4), "estimated": estimated}


# --------------------------------------------------------------------------
# Myriad Index — the single headline number (docs/metrics.md §0)
# --------------------------------------------------------------------------

MI_WEIGHTS = {"R": 0.40, "S": 0.30, "T": 0.20, "E": 0.10}


def retention_by_tier(ret: dict, mixed: dict) -> dict:
    tiers = {}
    for uid, r in ret.items():
        tiers.setdefault(mixed[uid].get("rarity", 1), []).append(r)
    return {t: sum(v) / len(v) for t, v in sorted(tiers.items())}


def _be_score(trace: dict, mixed: dict) -> float | None:
    be = budget_efficiency({"units": list(mixed.keys()) or [{"id": "_"}]}, trace, mixed)
    return be["BE"]


def myriad_index(ret: dict, mixed: dict, isolated: dict, isolated_traces: dict,
                swc: float | None, rf: float | None, tokens_mix: int) -> dict:
    """MI = 100*(0.4R + 0.3S + 0.2T + 0.1E); missing state components count
    as 'not stressed' (1.0) and are reported in `defined`."""
    R = math.exp(sum(math.log(max(r, EPS)) for r in ret.values()) / len(ret)) if ret else 0.0

    # S: state retention (SWC + RF halves); axis active iff at least one half is stressed
    defined = {"SWC": swc is not None, "RF": rf is not None}
    s_active = swc is not None or rf is not None
    S = 0.5 * (swc if swc is not None else 1.0) + 0.5 * (rf if rf is not None else 1.0)

    tiers = retention_by_tier(ret, mixed)
    hardest = max(tiers) if tiers else 1
    T = tiers.get(hardest, 0.0)
    defined["T_tier"] = hardest

    E = None
    be_ratios = []
    for uid, it in isolated_traces.items():
        if uid not in isolated:
            continue
        tokens = it.get("usage", {}).get("prompt_tokens", 0) + it.get("usage", {}).get("completion_tokens", 0)
        if not tokens:
            tokens = max(int(sum(len(t.get("content", "")) for t in it.get("turns", [])) / 4), 1)
        if tokens > 0:
            be_ratios.append(isolated[uid]["score"] / tokens)
    passed_mix = sum(row["score"] for row in mixed.values())
    if be_ratios and tokens_mix:
        E = min(1.0, (passed_mix / tokens_mix) / (sum(be_ratios) / len(be_ratios)))

    # MI = weighted mean over ACTIVE axes only (unstressed axes are excluded,
    # not rewarded) — an agent that does nothing scores ~0, never a free 30.
    comps = {"R": R, "S": S if s_active else None, "T": T, "E": E}
    active_w = sum(MI_WEIGHTS[k] for k, v in comps.items() if v is not None)
    if not active_w:
        wji = None
    else:
        wji = 100 * sum(MI_WEIGHTS[k] * comps[k] for k, v in comps.items() if v is not None) / active_w
    return {"MI": round(wji, 2) if wji is not None else None,
            "components": {k: (round(v, 4) if v is not None else None) for k, v in comps.items()},
            "weights": MI_WEIGHTS, "defined": defined,
            "tiers": {str(k): round(v, 4) for k, v in tiers.items()}}


# --------------------------------------------------------------------------
# top-level evaluation
# --------------------------------------------------------------------------

def evaluate(session: dict, trace: dict, isolated_traces: dict | None = None,
             tau: int = 3) -> dict:
    isolated_traces = isolated_traces or {}
    mixed = per_unit_scores(session, trace)
    unit_ids = {u["id"] for u in session["units"]}
    isolated = {uid: {"score": per_unit_scores(_iso_session(session, uid), it)[uid]["score"]}
                for uid, it in isolated_traces.items() if uid in unit_ids}
    ret = retention_map(mixed, isolated)
    ic = interference(ret)

    # family-level IC
    fam = {}
    for uid, r in ret.items():
        f = mixed[uid]["family"]
        fam.setdefault(f, []).append(r)
    ic_fam = {f: round(1 - math.exp(sum(math.log(max(x, EPS)) for x in v) / len(v)), 4)
              for f, v in fam.items()}

    # worst-decile note (single-session view)
    rows_dec = sorted(ret.values())
    worst = rows_dec[0] if rows_dec else None

    swc_res = state_web(session, trace)
    rf_res = resume_fidelity(session, trace, isolated_traces)
    be_res = budget_efficiency(session, trace, mixed)
    if isolated:
        wji = myriad_index(ret, mixed, isolated, isolated_traces,
                          swc_res["SWC"], rf_res["RF"], be_res["tokens"])
        status = "ok"
    else:
        wji = {"MI": None, "components": None, "weights": MI_WEIGHTS,
               "defined": {"SWC": False, "RF": False}, "tiers": {},
               "note": "MI requires isolated baselines"}
        status = "no_isolated"

    report = {
        "session_id": session["session_id"],
        "mixture": session.get("meta", {}).get("mixture"),
        "agent": trace.get("agent"),
        "model": trace.get("model"),
        "MI": wji["MI"],
        "MI_components": wji,
        "per_unit": {uid: {**r, "retention": round(ret[uid], 4)} for uid, r in mixed.items()},
        "IC": ic["IC"],
        "IC_family": ic_fam,
        "worst_unit_retention": round(worst, 4) if worst is not None else None,
        "SC": switch_cost(session, trace, tau),
        "RF": rf_res,
        "SWC": swc_res,
        "LTR": long_tail(mixed, isolated),
        "BE": be_res,
        "SV": {"note": "requires multi-length runs (tier L protocol) — N/A for this run"},
        "turns": len(trace.get("turns", [])),
        "status": status,
    }
    return report


def _iso_session(session: dict, unit_id: str) -> dict:
    """Minimal session view for isolated scoring."""
    return {"units": [u for u in session["units"] if u["id"] == unit_id],
            "events": [], "schema_version": session.get("schema_version", "0.1.0")}


def format_markdown(report: dict) -> str:
    L = []
    L.append(f"# MyriadBench report — {report['session_id']}")
    L.append(f"- agent: {report.get('agent')} ({report.get('model')})")
    L.append(f"- turns: {report.get('turns')}")
    L.append(f"\n## Headline")
    L.append(f"- **MI (Myriad Index): {report.get('MI')}** — the single ranking number")
    wc = report.get("MI_components", {}).get("components", {})
    if wc:
        L.append(f"  components: R={wc.get('R')} S={wc.get('S')} T={wc.get('T')} E={wc.get('E')}")
    L.append(f"- **IC (interference coefficient): {report.get('IC')}** (0 = free multitasking, 1 = collapse)")
    L.append(f"- worst unit retention: {report.get('worst_unit_retention')}")
    L.append(f"- SC: {report.get('SC', {}).get('SC')} (first-switch {report.get('SC', {}).get('SC_first')}, same-family {report.get('SC', {}).get('SC_same')})")
    rf = report.get("RF", {}).get("RF")
    L.append(f"- RF (resume fidelity): {rf}")
    swc = report.get("SWC", {}).get("SWC")
    L.append(f"- SWC (state-web consistency): {swc}")
    L.append(f"- BE (passed weight / tokens): {report.get('BE', {}).get('BE')} ({report.get('BE', {}).get('tokens')} tokens)")
    L.append(f"\n## Per unit")
    for uid, row in report.get("per_unit", {}).items():
        L.append(f"- {uid} [{row['family']} r{row['rarity']}] score={row['score']} retention={row['retention']}")
    sw = report.get("SWC", {})
    if sw.get("obligations"):
        L.append(f"\n## State web")
        for ob in sw["obligations"]:
            L.append(f"- {ob['consumer']} <- {ob['producer']} {ob['artifact']}: {'OK' if ob['ok'] else 'BROKEN'} (cert={ob['certified']}, cur={ob['current']}, consumed={ob['consumed']})")
    ltr = report.get("LTR", {}).get("LTR", {})
    if ltr:
        L.append(f"\n## Long tail")
        for r, v in ltr.items():
            L.append(f"- rarity {r}: mean retention {v}")
    return "\n".join(L)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_from_paths(session_path: str, trace_path: str, isolated_dir: str | None) -> dict:
    session = load_json(session_path)
    trace = load_json(trace_path)
    iso = {}
    if isolated_dir:
        import os
        for fn in os.listdir(isolated_dir):
            if not fn.endswith(".json"):
                continue
            it = load_json(os.path.join(isolated_dir, fn))
            if it.get("isolated_unit") and "env_final" in it and "turns" in it:
                iso[it["isolated_unit"]] = it
    report = evaluate(session, trace, iso)
    return report