"""One-command pilot runner (v0.2 minimal matrix on OpenCode Go).

Runs DeepSeek V4 Flash over the pilot matrix (docs/experiment-plan.md):
    g1: K=4, D=0.6 | g2: K=8, D=0.0 | g3: K=8, D=0.6   (seed=7, DEP=0.3, NV=0.2)

Usage:
    python scripts/run_pilot.py            # all three mixtures, deepseek-v4-flash
    python scripts/run_pilot.py --K 4 --D 0.6 --model deepseek-v4-flash

Key resolution (in order): --api-key, MYRIAD_API_KEY, ~/.pi/agent/auth.json
(pi's opencode-go credential, used with the OpenCode Go subscription),
OPENCODE_API_KEY. Base URL defaults to https://opencode.ai/zen/go/v1.

Output: data/pilot/<model>/... (sessions generated; traces, metrics, summary).
"""

from __future__ import annotations

import argparse
import glob
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

DEFAULT_MIXTURES = [(4, 0.6), (8, 0.0), (8, 0.6)]
DEFAULT_MODEL = "deepseek-v4-flash"
BASE_URL = "https://opencode.ai/zen/go/v1"


def resolve_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    for env in ("MYRIAD_API_KEY", "OPENCODE_API_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(env)
        if v:
            return v
    auth_path = os.path.expanduser("~/.pi/agent/auth.json")
    if os.path.exists(auth_path):
        auth = json.load(open(auth_path, encoding="utf-8"))
        go = auth.get("opencode-go") or {}
        if go.get("key"):
            return go["key"]
    raise SystemExit("no API key: pass --api-key or set MYRIAD_API_KEY / ~/.pi/agent/auth.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--K", type=int, default=None)
    ap.add_argument("--D", type=float, default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mix-id-prefix", default="g")
    ap.add_argument("--out", default="data/pilot")
    ap.add_argument("--max-turns", type=int, default=10)
    ap.add_argument("--max-total", type=int, default=220)
    args = ap.parse_args()

    key = resolve_key(args.api_key)
    agent = OpenAICompatAgent(args.model, base_url=args.base_url, api_key=key)

    if args.K is not None:
        mixtures = [(args.K, args.D if args.D is not None else 0.6)]
    else:
        mixtures = DEFAULT_MIXTURES
    if any(d is None for _, d in mixtures):
        mixtures = [(k, d if d is not None else 0.6) for k, d in mixtures]

    gen_dir = os.path.join(args.out, "generated")
    res_dir = os.path.join(args.out, args.model)
    os.makedirs(gen_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    rows = []
    for idx, (K, D) in enumerate(mixtures):
        mix_id = f"{args.mix_id_prefix}{idx + 1}"
        sess_path, _ = generate_mixture(gen_dir, mix_id, args.seed, "S",
                                        K=K, H=0.6, D=D, DEP=0.3, IR=0.3, NV=0.2)
        session = load_json(sess_path)
        print(f"\n=== {mix_id}: K={K} D={D} ({len(session['units'])} units, "
              f"{len(session['events'])} events) ===", flush=True)

        t0 = time.time()
        trace = run_session(session, agent, out_dir=res_dir,
                            max_turns_per_event=args.max_turns,
                            max_total_turns=args.max_total)
        iso_dir = os.path.join(res_dir, "isolated")
        if os.path.isdir(iso_dir):
            shutil.rmtree(iso_dir)  # traces from previous mixtures would pollute scoring
        os.makedirs(iso_dir, exist_ok=True)
        for unit in session["units"]:
            iso = load_json(os.path.join(gen_dir, "isolated",
                                         f"{mix_id}-s{args.seed}-iso-{unit['id']}.json"))
            run_session(iso, agent, out_dir=iso_dir,
                        max_turns_per_event=args.max_turns,
                        max_total_turns=args.max_total)
        dt = time.time() - t0
        print(f"ran in {dt:.0f}s | turns={len(trace['turns'])} | usage={trace['usage']}", flush=True)

        report = evaluate_from_paths(sess_path,
                                     os.path.join(res_dir, f"{session['session_id']}-{agent.name}.json"),
                                     iso_dir)
        rep_path = os.path.join(res_dir, f"metrics-{session['session_id']}-{agent.name}.json")
        json.dump(report, open(rep_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rows.append({"mixture": mix_id, "K": K, "D": D,
                     "MI": report.get("MI"), "IC": report.get("IC"),
                     "turns": report.get("turns"),
                     "usage": trace["usage"]})
        print(f"  -> MI={report.get('MI')} IC={report.get('IC')} "
              f"RF={report.get('RF', {}).get('RF')} SWC={report.get('SWC', {}).get('SWC')}", flush=True)

    summary = {"model": args.model, "base_url": args.base_url,
               "seed": args.seed, "rows": rows,
               "finish_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(args.out, "pilot-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nsummary -> {os.path.join(args.out, 'pilot-summary.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())