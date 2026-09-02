"""MyriadBench visualization suite — the shareable figures (AA-style: clean, dark,
big numbers, one message per figure). All figures read data/pilot/<model>/metrics-*.json
plus traces, so re-running after a pilot regenerates everything.

Usage:
    python scripts/visuals.py [--root data/pilot] [--out data/pilot/figures]

Figures:
    hero.png             README/social banner: name + tagline + the hook numbers
    leaderboard.png      MI horizontal bars, sorted, with perfect-agent reference line
    decomposition.png    MI stacked into R/S/T/E per model
    ic_vs_k.png          IC vs K, two D curves (the paper's main figure)
    family_heatmap.png   per-family IC, models x families
    timeline.png         one session's turn stream: unit lanes, interrupts marked
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

C = {"bg": "#0d1117", "fg": "#e6edf3", "muted": "#8b949e",
     "purple": "#a371f7", "pink": "#f778ba", "cyan": "#39c5cf",
     "green": "#3fb950", "orange": "#d29922", "red": "#f85149",
     "blue": "#58a6ff"}


def load_metrics(root: str) -> list[dict]:
    files = sorted(glob.glob(os.path.join(root, "*", "metrics-*.json")))
    return [json.load(open(f, encoding="utf-8")) for f in files]


def _dark(ax):
    ax.set_facecolor(C["bg"])
    for spine in ax.spines.values():
        spine.set_color("#21262d")
    ax.tick_params(colors=C["fg"])
    ax.xaxis.label.set_color(C["fg"])
    ax.yaxis.label.set_color(C["fg"])
    ax.title.set_color(C["fg"])


# ---------------------------------------------------------------------------
# hero banner
# ---------------------------------------------------------------------------

def fig_hero(out: str):
    fig = plt.figure(figsize=(16, 4), facecolor=C["bg"])
    fig.text(0.5, 0.74, "MyriadBench", ha="center", va="center",
             color=C["fg"], fontsize=72, weight="bold")
    fig.text(0.5, 0.47, "One model. One session. All tasks.",
             ha="center", va="center", color=C["fg"], fontsize=24)
    fig.text(0.5, 0.22, "THE BENCHMARK FOR THE DAY IN THE LIFE OF ONE AI",
             ha="center", va="center", color=C["muted"], fontsize=13)
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# leaderboard
# ---------------------------------------------------------------------------

def fig_leaderboard(ms: list[dict], out: str):
    rows = [(m.get("model") or m.get("agent"), m.get("MI")) for m in ms if m.get("MI") is not None]
    rows = sorted(rows, key=lambda r: r[1])
    if not rows:
        print("leaderboard: no MI data"); return
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(10, max(3, 0.55 * len(rows))), facecolor=C["bg"])
    _dark(ax)
    colors = [C["purple"] if v < 60 else C["green"] for v in vals]
    ax.barh(labels, vals, color=colors, height=0.62)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Myriad Index (MI)")
    ax.set_title("MyriadBench leaderboard", loc="left", fontsize=16)
    for i, v in enumerate(vals):
        ax.text(v + 0.5, i, f"{v:.1f}", va="center", color=C["fg"], fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# MI decomposition
# ---------------------------------------------------------------------------

def fig_decomposition(ms: list[dict], out: str):
    rows = [(m.get("model") or m.get("agent"), (m.get("MI_components") or {}).get("components"))
            for m in ms if m.get("MI") is not None]
    if not rows:
        print("decomposition: no data"); return
    names = [r[0] for r in rows]
    comps = [r[1] for r in rows]
    parts = ["R", "S", "T", "E"]
    colors = [C["purple"], C["cyan"], C["green"], C["orange"]]
    fig, ax = plt.subplots(figsize=(9, 0.7 * len(names) + 2), facecolor=C["bg"])
    _dark(ax)
    bottom = [0.0] * len(names)
    for part, col in zip(parts, colors):
        vals = [c.get(part, 0) or 0 for c in comps]
        ax.barh(names, vals, left=bottom, color=col, height=0.6, label=part)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xlim(0, 100)
    ax.set_xlabel("weighted contribution to MI (%)")
    ax.set_title("What the MI is made of", loc="left", fontsize=16)
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=C["fg"])
    fig.tight_layout()
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# IC vs K
# ---------------------------------------------------------------------------

def fig_ic_vs_k(ms: list[dict], out: str):
    series = {}
    for m in ms:
        mix = m.get("mixture") or {}
        k, d, ic = mix.get("K"), mix.get("D"), m.get("IC")
        if k is None or d is None or ic is None:
            continue
        model = m.get("model") or m.get("agent")
        series.setdefault((model, d), []).append((k, ic))
    if not series:
        print("ic_vs_k: no data"); return
    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=C["bg"])
    _dark(ax)
    for (model, d), pts in sorted(series.items()):
        pts = sorted(pts)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o",
                color=C["purple"] if d == 0 else C["pink"],
                label=f"{model}  D={d}")
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("K (tasks in the session)")
    ax.set_ylabel("IC (interference coefficient)")
    ax.set_title("The multitasking tax grows with the day", loc="left", fontsize=14)
    ax.legend(frameon=False, fontsize=9, labelcolor=C["fg"])
    ax.grid(axis="y", color="#21262d", lw=0.6)
    fig.tight_layout()
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# family heatmap
# ---------------------------------------------------------------------------

def fig_family_heatmap(ms: list[dict], out: str):
    fams = sorted({f for m in ms for f in (m.get("IC_family") or {})})
    if not fams:
        print("family_heatmap: no data"); return
    models = [(m.get("model") or m.get("agent"), m.get("IC_family") or {}) for m in ms]
    data = [[m[1].get(f, 0.0) for f in fams] for m in models if m[1]]
    models = [m for m in models if m[1]]
    if not data:
        print("family_heatmap: empty"); return
    fig, ax = plt.subplots(figsize=(max(6, 0.8 * len(fams) + 2), 0.6 * len(models) + 1.5),
                           facecolor=C["bg"])
    _dark(ax)
    im = ax.imshow(data, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(fams)), fams, rotation=30, ha="right", color=C["fg"], fontsize=9)
    ax.set_yticks(range(len(models)), [m[0] for m in models], color=C["fg"], fontsize=9)
    ax.set_title("Who pays the multitasking tax", loc="left", fontsize=14)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.03)
    cbar.ax.tick_params(colors=C["fg"])
    cbar.set_label("family IC (1 = total collapse)", color=C["fg"], fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# session timeline (turn stream with interrupts)
# ---------------------------------------------------------------------------

def fig_timeline(trace_path: str, out: str):
    trace = json.load(open(trace_path, encoding="utf-8"))
    turns = trace.get("turns", [])
    if not turns:
        print("timeline: empty trace"); return
    units = {}
    for t in turns:
        if t.get("unit"):
            units.setdefault(t["unit"], len(units))
    if not units:
        print("timeline: no units"); return
    n_units = len(units)
    fig, ax = plt.subplots(figsize=(12, 0.6 * n_units + 1.6), facecolor=C["bg"])
    _dark(ax)
    for t in turns:
        u = t.get("unit")
        if not u:
            continue
        y = units[u]
        i, role = t["i"], t["role"]
        if role == "user":
            ax.scatter(i, y, marker="v", s=40, color=C["blue"], zorder=3)
        elif role == "tool":
            ax.scatter(i, y, marker="s", s=26, color=C["muted"], zorder=2)
        elif role == "assistant":
            ax.scatter(i, y, marker="o", s=30, color=C["green"] if not t.get("tool") else C["cyan"], zorder=3)
    for t in turns:
        if t["role"] == "system" and "[interrupt]" in t.get("content", ""):
            ax.axvline(t["i"], color=C["red"], lw=1.6, alpha=0.9)
            ax.text(t["i"], -0.55, "break", color=C["red"], fontsize=8, ha="center")
        if t["role"] == "system" and "[resume]" in t.get("content", ""):
            ax.axvline(t["i"], color=C["green"], lw=1.2, alpha=0.7)
    ax.set_yticks(range(n_units), list(units.keys()), color=C["fg"], fontsize=8)
    ax.set_xlabel("turn", color=C["fg"])
    ax.set_title(f"One session, many tasks — {trace.get('session_id')}", loc="left", fontsize=13)
    ax.grid(axis="x", color="#21262d", lw=0.5)
    fig.tight_layout()
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# how-it-works diagram (non-data asset)
# ---------------------------------------------------------------------------

def fig_how(out: str):
    fig, ax = plt.subplots(figsize=(13, 5), facecolor=C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 5); ax.axis("off")

    def box(x, y, w, h, title, lines, color):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                             facecolor="#161b22", edgecolor=color, lw=1.6))
        ax.text(x + w / 2, y + h - 0.42, title, ha="center", va="center",
                color=color, fontsize=14, weight="bold")
        for i, ln in enumerate(lines):
            ax.text(x + w / 2, y + h - 0.95 - i * 0.5, ln, ha="center", va="center",
                    color=C["muted"], fontsize=10)

    box(0.4, 1.4, 3.6, 2.6, "ONE AGENT",
        ["one model", "one context", "one endless session"], C["purple"])
    ax.annotate("", xy=(4.4, 2.7), xytext=(4.05, 2.7),
                arrowprops=dict(arrowstyle="-|>", color=C["fg"], lw=2))
    box(4.8, 1.4, 3.6, 2.6, "EVENT STREAM",
        ["assign  ·  interrupt ·  resume", "inject  ·  env change  ·  tick"], C["cyan"])
    ax.annotate("", xy=(8.8, 2.7), xytext=(8.45, 2.7),
                arrowprops=dict(arrowstyle="-|>", color=C["fg"], lw=2))
    box(9.2, 1.4, 3.4, 2.6, "THE MYRIAD INDEX",
        ["0–100, one ranking number", "vs. own isolated baselines", "no memorizing, no gaming"], C["green"])

    ax.text(6.5, 4.55, "countless interleaved tasks, one shared world state",
            ha="center", color=C["fg"], fontsize=11)
    ax.text(6.5, 0.55, "files · calendar · email · data · code",
            ha="center", color=C["muted"], fontsize=10)
    fig.savefig(out, dpi=180, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


# ---------------------------------------------------------------------------
# social cards: one 1200x630 shareable image per model (X/Twitter-ready)
# ---------------------------------------------------------------------------

def fig_card(m: dict, out: str):
    model = m.get("model") or m.get("agent")
    mi = m.get("MI")
    comps = (m.get("MI_components") or {}).get("components") or {}
    mix = m.get("mixture") or {}
    fig = plt.figure(figsize=(12, 6.3), facecolor=C["bg"])
    fig.text(0.5, 0.86, model, ha="center", color=C["fg"], fontsize=34, weight="bold")
    if mi is not None:
        fig.text(0.5, 0.55, f"{mi:.1f}", ha="center", color=C["purple"],
                 fontsize=120, weight="bold")
        fig.text(0.5, 0.38, "MYRIAD INDEX", ha="center", color=C["muted"], fontsize=16)
        # mini R/S/T/E bars
        parts = [("R", comps.get("R")), ("S", comps.get("S")),
                 ("T", comps.get("T")), ("E", comps.get("E"))]
        cols = [C["purple"], C["cyan"], C["green"], C["orange"]]
        n = len(parts)
        for i, ((name, v), col) in enumerate(zip(parts, cols)):
            x0 = 0.08 + i * 0.24
            fig.patches.append(mpatches.FancyBboxPatch((x0, 0.16), 0.2, 0.05,
                                                       boxstyle="round,pad=0.004",
                                                       facecolor="#161b22", edgecolor=col))
            if v:
                fig.patches.append(mpatches.FancyBboxPatch((x0, 0.16), 0.2 * min(v, 1.0), 0.05,
                                                           boxstyle="round,pad=0.004",
                                                           facecolor=col, edgecolor=col))
            fig.text(x0 + 0.1, 0.23, f"{name} {v:.2f}" if v is not None else name,
                     ha="center", color=C["muted"], fontsize=9)
        fig.text(0.5, 0.06, f"K={mix.get('K', '?')}  D={mix.get('D', '?')}  ·  one session, all tasks",
                 ha="center", color=C["muted"], fontsize=11)
    else:
        fig.text(0.5, 0.5, "pilot in progress", ha="center", color=C["muted"], fontsize=24)
    fig.savefig(out, dpi=160, facecolor=C["bg"])
    plt.close(fig)
    print("saved", out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/pilot")
    ap.add_argument("--out", default="data/pilot/figures")
    ap.add_argument("--assets-out", default="assets")
    ap.add_argument("--trace", default=None, help="trace json for the timeline figure")
    args = ap.parse_args()
    os.makedirs(args.assets_out, exist_ok=True)
    fig_hero(os.path.join(args.assets_out, "hero.png"))
    fig_how(os.path.join(args.assets_out, "how.png"))
    os.makedirs(args.out, exist_ok=True)
    ms = load_metrics(args.root)
    if not ms:
        print(f"no metrics under {args.root}; run scripts/run_pilot.py first")
        return 0
    fig_leaderboard(ms, os.path.join(args.out, "leaderboard.png"))
    cards_dir = os.path.join(args.out, "cards")
    os.makedirs(cards_dir, exist_ok=True)
    for m in ms:
        if m.get("MI") is not None:
            fig_card(m, os.path.join(cards_dir, (m.get("model") or "model").replace("/", "_") + ".png"))
    fig_decomposition(ms, os.path.join(args.out, "decomposition.png"))
    fig_ic_vs_k(ms, os.path.join(args.out, "ic_vs_k.png"))
    fig_family_heatmap(ms, os.path.join(args.out, "family_heatmap.png"))
    if args.trace:
        fig_timeline(args.trace, os.path.join(args.out, "timeline.png"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())