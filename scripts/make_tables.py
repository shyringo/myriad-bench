"""Aggregate MyriadBench metric JSONs into paper tables (Table 1/2/3).

Usage:
    python scripts/make_tables.py data/results [--out tables.md]

Expects: data/results/<model>/metrics-<session>-openai.json per run
(produced by `harness.cli report`). Stdlib only.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HEAD = ["model", "session", "K", "D", "MI", "IC", "SC_first", "SC_same", "RF", "SWC",
        "LTR1", "LTR2", "LTR3", "LTR4", "BE", "tokens", "turns"]


def load_metrics(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def row_for(metrics: dict) -> list:
    sc = metrics.get("SC") or {}
    ltr = metrics.get("LTR", {}).get("LTR", {})
    be = metrics.get("BE") or {}
    mix = metrics.get("mixture") or {}
    return [
        metrics.get("model") or metrics.get("agent"),
        metrics.get("session_id"),
        mix.get("K"), mix.get("D"),
        metrics.get("MI"),
        metrics.get("IC"),
        sc.get("SC_first"), sc.get("SC_same"),
        metrics.get("RF", {}).get("RF"),
        metrics.get("SWC", {}).get("SWC"),
        ltr.get("1"), ltr.get("2"), ltr.get("3"), ltr.get("4"),
        be.get("BE"), be.get("tokens"),
        metrics.get("turns"),
    ]


def family_ic(metrics: dict) -> dict:
    return metrics.get("IC_family") or {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="dir containing <model>/metrics-*.json")
    ap.add_argument("--out", default="tables.md")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.root, "metrics-*.json"))
                + glob.glob(os.path.join(args.root, "*", "metrics-*.json")))
    if not files:
        print(f"no metrics found under {args.root}", file=sys.stderr)
        return 1

    rows = [row_for(load_metrics(f)) for f in files]
    lines = ["# MyriadBench pilot tables (auto-generated)\n",
             "| " + " | ".join(HEAD) + " |",
             "|" + "|".join(["---"] * len(HEAD)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join("" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)
                                       for v in r) + " |")

    # Table 2: family-level IC per run
    lines.append("\n## Table 2 — family-level IC (per run)")
    fam_runs = []
    for f in files:
        m = load_metrics(f)
        fi = family_ic(m)
        if fi:
            fam_runs.append((m.get("session_id"), m.get("model"), fi))
    if fam_runs:
        fams = sorted({k for _, _, fi in fam_runs for k in fi})
        lines.append("| run | model | " + " | ".join(fams) + " |")
        lines.append("|" + "|".join(["---"] * (len(fams) + 2)) + "|")
        for sid, model, fi in fam_runs:
            lines.append(f"| {sid} | {model} | " + " | ".join(f"{fi.get(f, 0.0):.4f}" for f in fams) + " |")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())