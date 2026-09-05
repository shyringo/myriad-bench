"""MyriadBench CLI — generate mixtures, run agents, report metrics.

Examples:
    # generate a mixture (session + isolated baselines)
    python -m harness.cli generate --out data/generated --mix-id demo --seed 7 \
        --K 8 --H 0.6 --D 0.5 --DEP 0.4 --IR 0.3 --NV 0.2 --tier S

    # run any OpenAI-compatible model on a session
    python -m harness.cli run --session data/generated/sessions/demo-s7.json \
        --agent openai --model gpt-4o-mini --out data/results

    # offline report from saved traces
    python -m harness.cli report --session data/generated/sessions/demo-s7.json \
        --trace data/results/demo-s7-openai.json --isolated data/generated/isolated \
        --out data/results
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .agents import EchoAgent, OpenAICompatAgent, ReplayAgent
from .compose import generate_mixture, write_json
from .metrics import evaluate, evaluate_from_paths, format_markdown, load_json
from .runner import run_session


def _positive_float(x):
    return float(x)


def cmd_generate(args):
    path, isolated = generate_mixture(args.out, args.mix_id, args.seed, args.tier,
                                      K=args.K, H=args.H, D=args.D, DEP=args.DEP,
                                      IR=args.IR, NV=args.NV)
    print(f"session:  {path}")
    print(f"isolated: {len(isolated)} reference runs written to {os.path.dirname(isolated[0])}")
    session = load_json(path)
    print(f"units: {len(session['units'])} | events: {len(session['events'])} | worlds: {list(session['world'])}")
    for u in session["units"]:
        deps = ", ".join(d["unit"] for d in u.get("depends_on", [])) or "-"
        print(f"  {u['id']:24s} family={u['family']:16s} rarity={u['rarity']} deps=[{deps}]")


def cmd_run(args):
    session = load_json(args.session)
    if args.agent == "replay":
        actions = load_json(args.replay) if args.replay else [{"type": "reply", "text": "ok"}]
        agent = ReplayAgent(actions)
    elif args.agent == "echo":
        agent = EchoAgent()
    elif args.agent == "openai":
        agent = OpenAICompatAgent(args.model, base_url=args.base_url, api_key=args.api_key)
    else:
        sys.exit(f"unknown agent {args.agent!r} (replay|echo|openai)")
    trace = run_session(session, agent, out_dir=args.out,
                        max_turns_per_event=args.max_turns, max_total_turns=args.max_total)
    print(f"trace: {os.path.join(args.out, session['session_id'] + '-' + agent.name + '.json')}")
    print(f"turns: {len(trace['turns'])} | usage: {trace['usage']}")
    print(f"unit replies: {sorted(trace['unit_reply'])}")
    # optional: run the same agent on every isolated reference session
    if args.with_isolated:
        import glob
        iso_dir = os.path.join(args.out, "isolated")
        os.makedirs(iso_dir, exist_ok=True)
        n = 0
        for fp in sorted(glob.glob(os.path.join(args.with_isolated, "*.json"))):
            iso_session = load_json(fp)
            if iso_session.get("kind") != "isolated":
                continue
            run_session(iso_session, agent, out_dir=iso_dir,
                        max_turns_per_event=args.max_turns, max_total_turns=args.max_total)
            n += 1
        print(f"isolated traces: {n} written to {iso_dir}")


def cmd_report(args):
    import glob
    traces = args.trace
    if not traces and args.glob:
        traces = sorted(glob.glob(args.glob))
    if not traces:
        sys.exit("no traces given (--trace path or --glob pattern)")
    lines = []
    session = load_json(args.session)
    for tp in traces:
        trace = load_json(tp)
        report = evaluate_from_paths(args.session, tp, args.isolated)
        md = format_markdown(report)
        lines.append(md)
        out_json = os.path.join(args.out, f"metrics-{trace.get('session_id')}-{trace.get('agent')}.json")
        write_json(out_json, report)
        print(md)
        print(f"\n[JSON -> {out_json}]")
        if args.annotate:
            with open(os.path.join(args.out, "report_annotated.md"), "w", encoding="utf-8") as f:
                f.write("\n\n---\n\n".join(lines))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="myriad", description="MyriadBench harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate a mixture + isolated baselines")
    g.add_argument("--out", default="data/generated")
    g.add_argument("--mix-id", default="mix")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--tier", choices=["S", "M", "L"], default="S")
    g.add_argument("--K", type=int, default=None, help="number of tasks in the session")
    g.add_argument("--H", type=_positive_float, default=None, help="heterogeneity 0..1")
    g.add_argument("--D", type=_positive_float, default=None, help="interleaving density 0..1")
    g.add_argument("--DEP", type=_positive_float, default=None, help="dependency density 0..1")
    g.add_argument("--IR", type=_positive_float, default=None, help="interruption rate 0..1")
    g.add_argument("--NV", type=_positive_float, default=None, help="novelty / injection 0..1")
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("run", help="run an agent on a session")
    r.add_argument("--session", required=True)
    r.add_argument("--agent", default="echo", choices=["replay", "echo", "openai"])
    r.add_argument("--replay", help="JSON list of scripted actions (for --agent replay)")
    r.add_argument("--model", default="gpt-4o-mini")
    r.add_argument("--base-url", default=None)
    r.add_argument("--api-key", default=None, help="defaults to MYRIAD_API_KEY / OPENAI_API_KEY")
    r.add_argument("--out", default="data/results")
    r.add_argument("--max-turns", type=int, default=10)
    r.add_argument("--max-total", type=int, default=200)
    r.add_argument("--with-isolated", default=None,
                   help="dir with isolated reference SESSIONS; runs them with the same agent "
                        "and writes isolated TRACES under <out>/isolated")
    r.set_defaults(fn=cmd_run)

    rep = sub.add_parser("report", help="compute metrics from saved traces")
    rep.add_argument("--session", required=True)
    rep.add_argument("--trace", action="append", default=[])
    rep.add_argument("--glob", default=None)
    rep.add_argument("--isolated", default=None, help="dir with isolated reference traces")
    rep.add_argument("--out", default="data/results")
    rep.add_argument("--annotate", action="store_true")
    rep.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()