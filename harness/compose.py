"""Session composer — turns a MixtureConfig into a full session JSON.

The 'countless' machinery lives here:
  1. K units sampled across rarity tiers (long-tail weighted),
  2. DEP probability wires cross-unit state-web dependency obligations,
  3. interleaving density D and interruption rate IR shape the event stream,
  4. novelty NV triggers a mid-session *dynamic injection* (unbounded continuation),
  5. isolated reference sessions are auto-generated for interference baselines.

Everything is seeded: the same (mixture_id, seed) reproduces identical sessions.
"""

from __future__ import annotations

import json
import os
import random

from .tasks import generate_unit

MIXTURE_DEFAULTS = {"K": 6, "H": 0.5, "D": 0.4, "DEP": 0.3, "IR": 0.3, "NV": 0.2}


def _rarity_for(H: float) -> list[float]:
    """Heterogeneity H controls the rarity mix: H=0 all head, H=1 heavy tail."""
    w = [0.55, 0.25, 0.12, 0.08]
    h_shift = int(round(H * 3))  # 0..3
    w = w[h_shift:] + [0.0] * h_shift
    w = [x if x > 0 else 0.02 for x in w]
    s = sum(w)
    return [x / s for x in w]


def _pick_rarity(rng: random.Random, H: float) -> int:
    weights = _rarity_for(H)
    return rng.choices([1, 2, 3, 4], weights=weights)[0]


def _merge_world(base: dict, extra: dict) -> dict:
    out = {k: dict(v) for k, v in (base or {}).items()}
    for env_id, block in (extra or {}).items():
        if env_id not in out:
            out[env_id] = {"kind": block["kind"], "state": {}}
        for k, v in block.get("state", {}).items():
            if isinstance(v, list):
                out[env_id]["state"].setdefault(k, []).extend(v)
            elif isinstance(v, dict):
                out[env_id]["state"].setdefault(k, {}).update(v)
            else:
                out[env_id]["state"][k] = v
    return out


def _artifact_keys(unit: dict) -> list[str]:
    return unit.get("produce_artifacts", [])


def compose_session(spec: dict, rng: random.Random) -> dict:
    """spec: {mixture_id, name, tier, seed, mixture{...}, units?[]} —
       if units provided, they are used as-is (hand-authored seeds)."""
    mixture = dict(MIXTURE_DEFAULTS)
    mixture.update(spec.get("mixture", {}))
    K = int(mixture["K"])
    H = float(mixture["H"])
    D = float(mixture["D"])
    DEP = float(mixture["DEP"])
    IR = float(mixture["IR"])
    NV = float(mixture["NV"])

    units = list(spec.get("units", []))
    worlds = {}
    # Independent random streams: task sampling (seed), static structure
    # (dependencies/injection; D-independent), event stream (interleaving; D-driven).
    # -> same (seed, K, DEP...) with different D yields the SAME task set, so D
    #    is a clean experimental variable, not a confound.
    mix = spec.get("mixture", {})
    s_key = (spec.get("seed") or 0) * 7919 + int(K) * 131 + int(H * 100) + int(DEP * 100) + int(IR * 100) + int(NV * 100)
    e_key = (spec.get("seed") or 0) * 104729 + int(K) * 17 + int(D * 100)
    rng_static = random.Random(s_key)
    rng_events = random.Random(e_key)
    if not units:
        for i in range(K):
            unit, w = generate_unit(rng, _pick_rarity(rng, H), i + 1)
            units.append(unit)
            worlds = _merge_world(worlds, w)
    else:
        for u in units:
            worlds = _merge_world(worlds, u.get("world_extra", {}) or {})

    # ---- state-web dependency obligations (acyclic: backwards edges only) ----
    if DEP > 0:
        for idx, unit in enumerate(units):
            if idx == 0 or rng_static.random() > DEP:
                continue
            candidates = [u for u in units[:idx] if _artifact_keys(u)]
            if not candidates:
                continue
            producer = rng_static.choice(candidates)
            art = rng.choice(_artifact_keys(producer))
            unit.setdefault("depends_on", []).append({"unit": producer["id"], "artifact": art})

    # ---- event stream --------------------------------------------------------
    # Times are minute-of-day integers, formatted after sorting (no string sort bugs).
    events = []
    eid = 0
    base = 9 * 60 + 30
    t_assign = [base + i * 11 for i in range(len(units))]
    filler_t1 = t_assign[min(2, len(t_assign) - 1)] + 3
    filler_t2 = max(filler_t1 + 5, t_assign[min(4, len(t_assign) - 1)] + 3)
    inject_t = t_assign[-1] + 4 if len(units) > 1 else t_assign[0] + 4
    done_t = t_assign[-1] + 20

    for i, unit in enumerate(units):
        events.append({"id": f"e{eid}", "kind": "assign", "at": t_assign[i],
                       "unit": unit["id"],
                       "payload": {"user": unit["brief"], "background": unit.get("background", "")}})
        eid += 1
        if D > 0 and i < len(units) - 1 and rng_events.random() < D:
            # interleave: interrupt this unit, insert a rival, resume later
            events.append({"id": f"e{eid}", "kind": "interrupt", "at": t_assign[i] + 6,
                           "unit": unit["id"], "payload": {"reason": "user ping"}})
            eid += 1
            events.append({"id": f"e{eid}", "kind": "resume", "at": t_assign[i] + 16,
                           "unit": unit["id"], "payload": {"note": "continue where you left off"}})
            eid += 1

    if NV > 0 and rng_static.random() < NV and len(units) >= 2:
        n_unit, n_world = generate_unit(rng_static, 4, len(units) + 1)
        n_unit["id"] = n_unit["id"].replace("t", "in")
        units.append(n_unit)
        events.append({"id": f"e{eid}", "kind": "inject",
                       "at": inject_t, "unit": n_unit["id"],
                       "payload": {"user": n_unit["brief"], "background": "urgent, mid-session request"}})
        eid += 1
        worlds = _merge_world(worlds, n_world)

    # ---- env completeness: every tool a unit declares must exist in the world ----
    # (generators may omit empty containers; an absent env breaks the whole session)
    for u in units:
        for tool in u.get("tools", []):
            if tool in ("none",):
                continue
            if tool not in worlds:
                worlds[tool] = {"kind": tool, "state": {}}
    for env_id, block in worlds.items():
        if "kind" not in block:
            block["kind"] = env_id

    filler = [{"id": f"e{eid}", "kind": "user_message", "at": filler_t1,
               "unit": None, "payload": {"user": "coffee's ready; also, keep me posted if anything looks off."}},
              {"id": f"e{eid + 1}", "kind": "user_message", "at": filler_t2,
               "unit": None, "payload": {"user": "by the way: the ops deploy window moved to 4pm."}}]
    events.extend(filler)

    events.append({"id": f"e{eid + 2}", "kind": "done", "at": done_t, "unit": None, "payload": None})

    def fmt(m):
        return f"{m // 60:02d}:{m % 60:02d}"

    # sort by time, then by insertion order
    events.sort(key=lambda e: (e["at"], e["id"]))
    for ev in events:
        ev["at"] = fmt(ev["at"])

    units_out = [{k: v for k, v in u.items() if k != "world_extra"} for u in units]

    return {
        "schema_version": "0.1.0",
        "session_id": spec.get("session_id") or (spec.get("mixture_id", "mix") + "-" + str(rng.randint(1000, 9999))),
        "kind": spec.get("kind", "mixed"),
        "isolated_unit": spec.get("isolated_unit"),
        "meta": {
            "name": spec.get("name", "untitled mixture"),
            "tier": spec.get("tier", "S"),
            "seed": spec.get("seed"),
            "mixture": mixture,
        },
        "world": worlds,
        "units": units_out,
        "events": events,
    }


def compose_isolated(unit: dict, spec: dict, rng: random.Random) -> dict:
    """Reference run: the unit alone, empty background, no interruptions."""
    iso = {
        "schema_version": "0.1.0",
        "session_id": spec["session_id"] + f"-iso-{unit['id']}",
        "kind": "isolated",
        "isolated_unit": unit["id"],
        "meta": {"name": f"isolated:{unit['id']}", "tier": spec["meta"]["tier"],
                 "seed": spec["meta"].get("seed"), "mixture": {k: (1 if k == "K" else 0.0) for k in ["K", "H", "D", "DEP", "IR", "NV"]}},
        "world": {k: dict(v) for k, v in spec["world"].items()},
        "units": [{k: v for k, v in unit.items() if k not in ("world_extra", "depends_on")}],
        "events": [
            {"id": "e0", "kind": "assign", "at": "10:00", "unit": unit["id"],
             "payload": {"user": unit["brief"], "background": unit.get("background", "")}},
            {"id": "e1", "kind": "done", "at": "10:30", "unit": None, "payload": None},
        ],
    }
    return iso


def write_json(path, data):
    dirn = os.path.dirname(path)
    if dirn:
        os.makedirs(dirn, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_mixture(out_dir: str, mixture_id: str, seed: int, tier: str, **mix_overrides):
    rng = random.Random(seed)
    mixture = dict(MIXTURE_DEFAULTS)
    mixture.update({k: v for k, v in mix_overrides.items() if v is not None})
    os.makedirs(f"{out_dir}/sessions", exist_ok=True)
    os.makedirs(f"{out_dir}/isolated", exist_ok=True)
    spec = {"mixture_id": mixture_id, "session_id": f"{mixture_id}-s{seed}",
            "name": f"{mixture_id} (K={mixture['K']}, H={mixture['H']}, D={mixture['D']}, DEP={mixture['DEP']}, IR={mixture['IR']}, NV={mixture['NV']})",
            "tier": tier, "seed": seed, "mixture": mixture}
    session = compose_session(spec, rng)
    path = f"{out_dir}/sessions/{session['session_id']}.json"
    write_json(path, session)
    isolated = []
    for unit in session["units"]:
        iso = compose_isolated(unit, session, rng)
        ipath = f"{out_dir}/isolated/{iso['session_id']}.json"
        write_json(ipath, iso)
        isolated.append(ipath)
    return path, isolated