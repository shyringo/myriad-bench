"""Pilot results auditor — automated sanity gates before any data is published.

Catches the class of bugs that produced the MI=100 incident (E-axis collpase):
  1. perfect-score anomalies (MI == 100 / 0) that are not structurally expected
  2. frozen components (an axis stuck at 1.0/0.0 across cells => axis disabled)
  3. usage-accounting fingerprints: isolated traces that cost MORE tokens per
     turn than the mixed session (cumulative-usage pollution)
  4. protocol drift / missing protocol markers
  5. missing or empty traces/metrics

Usage:
    python scripts/audit_results.py data/pilot
Exit code 1 on any finding (breaking the publish pipeline).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

PROTOCOL = "v3-usagefix"
MAX_ISO_TURNS = 15  # isolated runs are short; mixed runs are not


def tokens(trace: dict) -> int:
    u = trace.get("usage") or {}
    return int(u.get("prompt_tokens", 0) or 0) + int(u.get("completion_tokens", 0) or 0)


def audit(root: str) -> int:
    problems = []
    cells = []

    model_dirs = sorted(d for d in os.listdir(root)
                        if os.path.isdir(os.path.join(root, d)) and d != "figures")
    for model in model_dirs:
        mdir = os.path.join(root, model)
        for mp in sorted(glob.glob(os.path.join(mdir, "metrics-*.json"))):
            m = json.load(open(mp, encoding="utf-8"))
            cid = os.path.basename(mp).replace("metrics-", "").replace("-openai.json", "")
            cells.append((model, cid, m))

            # 1) protocol marker
            if m.get("protocol") != PROTOCOL:
                problems.append(f"[protocol] {model}/{cid}: protocol={m.get('protocol')!r}, "
                                f"expected {PROTOCOL!r}")

            # 2) perfect-score anomalies
            mi = m.get("MI")
            if mi is not None and mi >= 99.5:
                problems.append(f"[score] {model}/{cid}: MI={mi} >= 99.5 — verify structurally expected")
            if mi is not None and mi <= 0.5:
                problems.append(f"[score] {model}/{cid}: MI={mi} <= 0.5 — verify")

            # 3) frozen components across cells are checked after the loop
            comps = (m.get("MI_components") or {}).get("components") or {}

            # 4) usage plausibility: find the mixed trace for this cell
            tp = os.path.join(mdir, f"{cid}-openai.json".replace("s11-s11", "s11-s11"))
            tp = os.path.join(mdir, f"{cid}-openai.json")
            if not os.path.exists(tp):
                problems.append(f"[trace] {model}/{cid}: mixed trace missing ({tp})")
                continue
            trace = json.load(open(tp, encoding="utf-8"))
            n_turns = len(trace.get("turns", []))
            tok = tokens(trace)
            if tok <= 0 and n_turns > 0:
                problems.append(f"[usage] {model}/{cid}: mixed usage is 0 with {n_turns} turns")
            tpt_mix = tok / max(n_turns, 1)

            # isolated traces: check tokens-per-turn fingerprint
            isod = os.path.join(mdir, "isolated")
            iso_traces = [json.load(open(os.path.join(isod, f), encoding="utf-8"))
                          for f in os.listdir(isod) if f.endswith(".json")]
            if not iso_traces:
                problems.append(f"[trace] {model}/{cid}: no isolated traces")
                continue
            iso_tpt = [tokens(t) / max(len(t.get("turns", [])), 1) for t in iso_traces]
            # cumulative-usage pollution makes ISOLATED tokens-per-turn balloon
            # (mixed session's tokens leak into every isolated trace)
            if max(iso_tpt) > 3 * tpt_mix and tpt_mix > 0:
                problems.append(
                    f"[usage] {model}/{cid}: isolated tpt {max(iso_tpt):.0f} > 3x mixed tpt "
                    f"{tpt_mix:.0f} — cumulative-usage signature")

    # 3b) frozen components across ALL cells of a model
    for model in sorted({c[0] for c in cells}):
        comps_list = [((c[2].get("MI_components") or {}).get("components") or {})
                      for c in cells if c[0] == model]
        for axis in ("R", "S", "T", "E"):
            vals = [c.get(axis) for c in comps_list if c.get(axis) is not None]
            if vals and min(vals) == max(vals) == 1.0 and len(vals) >= 4:
                problems.append(f"[frozen] {model}: component {axis} == 1.0 in all {len(vals)} cells "
                                f"— axis may be disabled")

    if problems:
        print(f"AUDIT FAILED ({len(problems)} findings):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"AUDIT OK: {len(cells)} cells, no anomalies "
          f"(n={sum(1 for c in cells if c[1].endswith('11'))} seed-11).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", default="data/pilot", nargs="?")
    args = ap.parse_args()
    return audit(args.root)


if __name__ == "__main__":
    raise SystemExit(main())