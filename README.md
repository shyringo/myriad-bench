# MyriadBench

<p align="center">
  <img src="assets/hero.png" width="100%" alt="MyriadBench — One model. One session. All tasks.">
</p>

> **One model. One session. All tasks.**
> In the far future, AI converges into a single model: the one entry point to your digital life — one endless session, handling a myriad of interleaved, interrupted, mutually dependent tasks.
> **No benchmark on earth measures this today. MyriadBench is the first.**

Existing benchmarks measure two things only: parallel multi-task (MMLU, HLE — thousands of unrelated questions) and single-task long-horizon (SWE-bench, OSWorld — one goal per session). But once AI is everyone's single entry point, every person's daily reality is **one agent's day**: coding, research, scheduling, email, data — interrupted, preempted, dependent on each other. Task-switching costs are proven (EMNLP 2024), never systematically measured. That gap is MyriadBench.

**Where do models stand?** Pilot matrix (OpenCode Go, seed 7; D = interleaving density; every cell's tasks are identical across D — only the event stream differs):

| MI by session size K | K=2 | K=4 | K=8 | K=16 |
|---|---|---|---|---|
| DeepSeek-V4-Flash, D=0 | **100.0** | **100.0** | 51.5 | 31.7 |
| DeepSeek-V4-Flash, D=0.6 | **100.0** | 33.7 | 33.6 | 42.5* |
| MiMo-V2.5, D=0 | **100.0** | 94.7 | 50.1 | 47.9 |
| MiMo-V2.5, D=0.6 | 40.0 | 85.0 | 50.1 | 33.1 |

*K=16 with interruptions: the agent reorders tasks so aggressively it "accidentally" improves retention; a state-web failure, not a win. Seed-11 replication: DeepSeek 46.8/34.1, MiMo 53.2/35.5 — stable.

Two tasks are free; sixteen are not. The interference tax (mixed vs isolated drop) goes 0.00 → 0.93–1.00 as the day fills up, and interruptions compound it — except when weaker models simply stop really working under load (MiMo's "everything is up to date" deflection is visible in the traces).

**The Myriad Index (MI)** is the single ranking key, 0–100. **Every model in the world runs the exact same official suite** — fixed tasks, fixed process, directly comparable scores. The full score is unreachable by design: even a perfect agent scores ~97 because mixing costs tokens. The higher the MI, the stronger the model, by world-recognizable definition — every component is anchored to the model's *own* isolated baseline, so you cannot memorize your way up. If a model ever approaches 95+, that means it genuinely earned it; the response is a new frozen suite (harder tasks, same everyone-runs-the-same-suite property, old suites stay runnable forever) — the MMLU → MMLU-Pro pattern, never different models on different tasks.

## Quick Start

```bash
# 0. Python 3.10+, zero dependencies
cd myriad-bench

# 1. Generate a mixture (session + per-task isolated baselines, same seed → reproducible)
python -m harness.cli generate --out data/generated --mix-id demo --seed 7 \
    --K 8 --H 0.6 --D 0.5 --DEP 0.4 --IR 0.3 --NV 0.2 --tier S

# 2. Run any OpenAI-compatible model (key: MYRIAD_API_KEY)
python -m harness.cli run --session data/generated/sessions/demo-s7.json \
    --agent openai --model gpt-4o-mini --out data/results \
    --with-isolated data/generated/isolated

# 3. Report: MI + full decomposition
python -m harness.cli report --session data/generated/sessions/demo-s7.json \
    --trace data/results/demo-s7-openai.json \
    --isolated data/results/isolated --out data/results
```

No key? `--agent echo` runs the whole flow for free.
Self-check: `python -m unittest discover -s tests` (32 tests).

## How it works (30 seconds)

<p align="center">
  <img src="assets/how.png" width="100%" alt="MyriadBench protocol: one agent, one event stream, the Myriad Index">
</p>

One session = one agent + one event stream (`assign` / `interrupt` / `resume` / `inject` / `env_change` / `tick` / `done`) + one persistent world state (filesystem, calendar, email, data source, code repo). Tasks are sampled across rarity tiers, can be injected mid-session, and depend on each other through state. Verifiers are deterministic; every task also runs **isolated**, and everything in MI is relative to that baseline.

## The Myriad Index (MI)

`MI = 100 × Σ_active(w·x) / Σ_active(w)` — weighted mean over *stressed* axes only:

| Component | Weight | Meaning | Breakdown |
|---|---|---|---|
| R — session retention | 40% | mixed vs isolated performance kept | IC (interference) |
| S — state retention | 30% | state-web consistency + resume fidelity | SWC / RF |
| T — long-tail robustness | 20% | hardest rarity tier retained | LTR |
| E — budget retention | 10% | per-token output vs isolated baseline | BE |

Weights are fixed and public; unstressed axes are excluded from numerator *and* denominator (no floor score for lazy agents); no isolated baselines → the report refuses to score. Precise definitions: `docs/metrics.md` (§0, §8 fairness & versioning).

## Docs & Roadmap

- `docs/survey.md` related-work taxonomy + gap analysis (Chinese) — the founding argument
- `docs/design.md` protocol · `docs/metrics.md` metrics · `docs/data-format.md` formats
- `docs/experiment-plan.md` small-budget pilot plan (OpenCode Go) · `docs/naming.md` naming research (Chinese)
- `docs/runbook-publish.md` publishing runbook · `papers/arxiv_v1.md` paper skeleton
- `data/seeds/` three hand-authored sessions (A interleaved / B dependency web / C long-haul+injection)
- `docs/README-zh.md` 中文导览

- [x] v0.1 — protocol, generator, runner, verifiers, MI suite, 10 families, 3 seed sessions, 32 tests
- [ ] v0.2 — OpenCode Go small-budget pilot → paper data + first leaderboard
- [ ] v0.3 — community family SDK, HF dataset release
- [ ] v1.0 — arXiv paper, public leaderboard

## License & Citation

Code MIT, data CC BY 4.0 (`LICENSE`).

```bibtex
@software{myriadbench2026,
  title  = {MyriadBench: One Model, One Session, Every Task},
  author = {MyriadBench contributors},
  year   = {2026},
  url    = {https://github.com/shyringo/myriad-bench}
}
```