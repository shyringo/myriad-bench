"""IC vs K curves + SC zoom — paper figures.

Optional matplotlib (pip install into your D:\\SoftwaresSetup conda env).
Without matplotlib: prints a text table; still useful.

Usage:
    python scripts/plot_curves.py <root> [--out figures/]
Reads <root>/<model>/metrics-*.json (same layout as make_tables.py).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="figures")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.root, "*", "metrics-*.json")))
    if not files:
        print(f"no metrics under {args.root}", file=sys.stderr)
        return 1
    runs = [load(f) for f in files]

    # session -> (K, D): parse from metrics session_id if available in meta? fallback from filename
    def kd_of(m):
        sid = m.get("session_id", "")
        k = d = None
        for tok in sid.split("-"):
            if tok.startswith("k"):
                k = int(tok[1:])
            if tok.startswith("d"):
                d = float(tok[1:])
        return k, d

    print("model | K | D | IC")
    series = {}
    for m in runs:
        k, d = kd_of(m)
        model = m.get("model")
        print(f"{model} | {k} | {d} | {m.get('IC')}")
        series.setdefault((model, d), []).append((k, m.get("IC")))

    if not HAVE_MPL:
        print("\n[matplotlib not installed; text table above. pip install matplotlib for figures]")
        return 0

    os.makedirs(args.out, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))
    for (model, d), pts in sorted(series.items()):
        pts = sorted(pts)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker="o", label=f"{model} D={d}")
    ax.set_xlabel("K (tasks per session)")
    ax.set_ylabel("IC (interference coefficient)")
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("MyriadBench: the multitasking tax grows with mixture size")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "fig1_ic_vs_k.png"), dpi=200)
    print(f"saved {os.path.join(args.out, 'fig1_ic_vs_k.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())