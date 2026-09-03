"""Full pilot grid runner: deepseek-v4-flash + mimo-v2.5 over K x D x seed.

Cells:
    (model, K, D, seed) for K in {2,4,8,16}, D in {0.0,0.6}, seed 7
    plus (model, 8, D, seed 11) robustness cells.

Resumable: a cell whose metrics file exists with status ok is skipped.
Per-cell: fresh isolated dir (stale traces would pollute scoring).

Usage:
    python scripts/run_grid.py                 # all cells
    python scripts/run_grid.py --model mimo-v2.5 --K 8 --D 0.6 --seed 7    # one cell
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.agents import OpenAICompatAgent  # noqa: E402
from harness.compose import generate_mixture  # noqa: E402
from harness.metrics import evaluate_from_paths, load_json  # noqa: E402
from harness.runner import run_session  # noqa: E402
from scripts.run_pilot import BASE_URL, resolve_key  # noqa: E402

CELLS = [(m, K, D, sd) for m in ("deepseek-v4-flash", "mimo-v2.5")
         for K in (2, 4, 8, 16) for D in (0.0, 0.6) for sd in (7,)]
CELLS += [(m, 8, D, 11) for m in ("deepseek-v4-flash", "mimo-v2.5") for D in (0.0, 0.6)]

ROOT = "data/pilot"


def cell_id(m: str, K: int, D: float, sd: int) -> str:
    return f"k{K}d{int(D * 10)}s{sd}"


def run_cell(model: str, K: int, D: float, seed: int, api_key: str,
             max_total: int = 400) -> dict:
    mix_id = cell_id(model, K, D, seed)
    gen_dir = os.path.join(ROOT, "generated")
    res_dir = os.path.join(ROOT, model)
    os.makedirs(gen_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    sess_path, _ = generate_mixture(gen_dir, mix_id, seed, "S",
                                    K=K, H=0.6, D=D, DEP=0.3, IR=0.3, NV=0.2)
    session = load_json(sess_path)
    agent = OpenAICompatAgent(model, base_url=BASE_URL, api_key=api_key)

    t0 = time.time()
    trace = run_session(session, agent, out_dir=res_dir,
                        max_turns_per_event=10, max_total_turns=max_total)
    iso_dir = os.path.join(res_dir, "isolated")
    if os.path.isdir(iso_dir):
        shutil.rmtree(iso_dir)
    os.makedirs(iso_dir, exist_ok=True)
    for unit in session["units"]:
        iso = load_json(os.path.join(gen_dir, "isolated",
                                     f"{mix_id}-s{seed}-iso-{unit['id']}.json"))
        run_session(iso, agent, out_dir=iso_dir, max_turns_per_event=10,
                    max_total_turns=max_total)
    dt = time.time() - t0

    trace_path = os.path.join(res_dir, f"{session['session_id']}-openai.json")
    report = evaluate_from_paths(sess_path, trace_path, iso_dir)
    rep_path = os.path.join(res_dir, f"metrics-{session['session_id']}-openai.json")
    json.dump(report, open(rep_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return {"cell": mix_id, "model": model, "K": K, "D": D, "seed": seed,
            "seconds": round(dt), "MI": report.get("MI"), "IC": report.get("IC"),
            "RF": report.get("RF", {}).get("RF"), "SWC": report.get("SWC", {}).get("SWC"),
            "turns": report.get("turns"), "usage": trace.get("usage"),
            "status": report.get("status"), "protocol": "rng3-v1"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--K", type=int, default=None)
    ap.add_argument("--D", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()

    cells = CELLS
    if args.model:
        cells = [c for c in cells if c[0] == args.model]
    if args.K is not None:
        cells = [c for c in cells if c[1] == args.K]
    if args.D is not None:
        cells = [c for c in cells if abs(c[2] - args.D) < 1e-9]
    if args.seed is not None:
        cells = [c for c in cells if c[3] == args.seed]

    key = resolve_key(args.api_key)
    os.makedirs(ROOT, exist_ok=True)
    progress_path = os.path.join(ROOT, "grid-progress.json")
    progress = {}
    if os.path.exists(progress_path):
        progress = json.load(open(progress_path, encoding="utf-8"))

    for model, K, D, seed in cells:
        cid = cell_id(model, K, D, seed)
        rep = os.path.join(ROOT, model, f"metrics-{cid}-s{seed}-openai.json")
        if os.path.exists(rep):
            done = json.load(open(rep, encoding="utf-8"))
            if done.get("status") == "ok" and done.get("protocol") == "rng3-v1":
                print(f"[skip] {model} {cid} (MI={done.get('MI')})", flush=True)
                continue
        print(f"[run ] {model} {cid} K={K} D={D} seed={seed}", flush=True)
        try:
            r = run_cell(model, K, D, seed, key)
        except Exception as e:
            r = {"cell": cid, "model": model, "K": K, "D": D, "seed": seed,
                 "status": f"error: {e}"}
            print(f"[fail] {model} {cid}: {e}", flush=True)
        progress[cid] = r
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        print(f"[done] {model} {cid}: MI={r.get('MI')} IC={r.get('IC')} "
              f"({r.get('seconds')}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())