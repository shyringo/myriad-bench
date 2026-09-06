# MyriadBench — Technical Report v1.0

**One model. One session. All tasks.**

> A benchmark for measuring how much of an AI model's ability survives single-session, unbounded multi-task mixtures.
> Version 1.0 · Protocol `v3-usagefix` · Pilot: DeepSeek-V4-Flash & MiMo-V2.5 via OpenCode Go

**Status**: This is a self-published technical report hosted with the public repository and its release assets. It is not (yet) submitted to arXiv or a peer-reviewed venue; see §10 for the publication roadmap.

---

## 1. Abstract

As AI converges toward a single model being the sole entry point to a person's digital life, evaluation must shift from *how well a model performs a task* to *how well one agent survives a day of countless tasks*. MyriadBench is the first benchmark whose object of measurement is single-session extreme multitasking over an open task space: heterogeneous families — research, data munging, scheduling, email, code, planning, writing, long-tail rarities — interleaved, interrupted, resumed, and mutually dependent through persistent world state, with mid-session dynamic task injection.

Everything collapses into one ranking number, the **Myriad Index (MI, 0–100)**: a publicly weighted blend of session retention (R, 40%), state retention (S, 30%), long-tail robustness (T, 20%) and budget retention (E, 10%). Every component is anchored to the model's *own* isolated baselines; every model runs the same official suite; the full score is unreachable by design.

**Headline pilot result**: the interference tax is a scaling law. IC ≈ 0.00 at K=2 rises to 0.83–1.00 at K=8+ for both models; flawless small sessions score ~95, not 100 (the token tax is real); weaker models deflect work under load ("everything is up to date" replies, visible in traces).

## 2. Why: the evaluation gap

Popular benchmarks measure two extremes:

| Regime | Examples | What it misses |
|---|---|---|
| Parallel multi-task | MMLU, HLE, GAIA, GPQA | no session, no state, no cross-task interference |
| Single-task long-horizon | SWE-bench, WebArena, OSWorld, MLE-bench, τ-bench | one goal per session — long ≠ multi |
| Multi-domain dialogue | MultiWOZ, SGD | same ontology slot-filling, shallow state, no execution |
| Personal-assistant suites | PAUSE, π-Bench, ASTRA-bench | closed task spaces, small per-session task counts, no interference metrics |

The missing regime — one session, many heterogeneous tasks in a web of dependencies — is the daily reality of the far-future "single entry point" agent. Task-switch degradation is documented at toy scale (EMNLP-2024) but never systematically measured. **MyriadBench operationalizes the missing regime.**

## 3. Protocol (30 seconds)

- **Session** = one agent + one event stream (`assign / interrupt / resume / inject / env_change / tick / done`) + one persistent world state (filesystem, calendar, email, data source, code repo).
- **Task families** are pluggable (brief generator + env requirements + deterministic verifier + rarity tier ρ=1..4). The registry is open; mixtures are combinatorial; long-tail tasks can be *injected mid-session*. "Countless" is implemented, not claimed.
- **Clean ablations**: three independent random streams (task sampling / static structure / event interleaving) make interleaving density **D a single variable**: same (seed, K, DEP) with different D yields the *same task set*, only the event stream differs.
- **Isolated baselines**: every task also runs alone (same model, same seed). Everything in MI is relative to these baselines.

## 4. The Myriad Index

```
R = geometric mean of min(s_i / a_i, 1)                      # session retention = 1 − IC
S = 0.5·SWC′ + 0.5·RF′   (X′ = X if defined)                 # state retention
T = retention of the hardest rarity tier present             # long-tail robustness
E = min(1, (Σs/tokens_mix) / mean_i(a_i/tokens_iso_i))       # budget retention

MI = 100 · Σ_active(w·x) / Σ_active(w),   w = (0.40, 0.30, 0.20, 0.10)
```

- **Active-axis policy**: unstressed axes (no interruptions → RF undefined; no dependencies → SWC undefined) are excluded from numerator *and* denominator — never rewarded. A do-nothing agent scores ≈ 0.
- **No gaming**: R is relative to the same model's isolated run; SWC is structural (artifact checksums + consumption logs); E is economy (re-doing work restores R but tanks E).
- **Ceilings are session-shaped**: even a flawless agent pays a token tax in a mixed session, so small-session ceilings are ~95 — 100 is not a marketing number.

## 5. Pilot experiments

### Setup

- Models: **DeepSeek-V4-Flash**, **MiMo-V2.5** (OpenCode Go, temperature 0)
- Grid: K ∈ {2,4,8,16} × D ∈ {0.0, 0.6}, seed 7 · DEP=0.3 · NV=0.2 · H=0.6; plus seed-11 replication at K=8
- 20 cells total; each cell = 1 mixed session + K isolated runs; full traces stored
- Cost ≈ $5 (≈3.9M prompt + 1.2M completion tokens, DeepSeek off-peak pricing)

### Main results (MI, 0–100)

| model | D | K=2 | K=4 | K=8 | K=16 | seed-11 (K=8) |
|---|---|---|---|---|---|---|
| DeepSeek-V4-Flash | 0.0 | 94.2 | 33.4 | 44.6 | 25.9 | 39.7 |
| DeepSeek-V4-Flash | 0.6 | 95.8 | 34.6 | 44.5 | 25.7 | 23.5 |
| MiMo-V2.5 | 0.0 | 92.7 | 80.2 | 27.7 | 38.6 | 47.5 |
| MiMo-V2.5 | 0.6 | 34.6 | 77.2 | 42.6 | 27.3 | 34.5 |

### Component view (seed 7)

| model / cell | R | S | T | E | IC | RF | SWC |
|---|---|---|---|---|---|---|---|
| DeepSeek k16d0s7 | 0.00 | 0.50 | 0.33 | 0.42 | 1.00 | — | 0.00 |
| MiMo k16d0s7 | 0.01 | 0.50 | 1.00 | 0.31 | 0.99 | — | 0.00 |
| DeepSeek k16d6s7 | 0.00 | 0.17 | 1.00 | 0.06 | 1.00 | 0.33 | 0.00 |
| MiMo k16d6s7 | 0.01 | 0.17 | 1.00 | 0.18 | 0.99 | 0.33 | 0.00 |
| DeepSeek k2d0s7 | 1.00 | — | 1.00 | 0.59 | 0.00 | — | — |
| MiMo k2d0s7 | 1.00 | — | 1.00 | 0.49 | 0.00 | — | — |
| DeepSeek k4d0s7 | 0.03 | 0.50 | 0.50 | 0.71 | 0.97 | — | 0.00 |
| MiMo k4d0s7 | 1.00 | 0.50 | 1.00 | 0.52 | 0.00 | — | 0.00 |
| DeepSeek k8d0s7 | 0.17 | 0.50 | 0.92 | 0.45 | 0.83 | — | 0.00 |
| MiMo k8d0s7 | 0.01 | 0.50 | 0.42 | 0.42 | 0.99 | — | 0.00 |

## 6. Findings

1. **The interference tax is a scaling law.** IC 0.00–0.07 at K=2–4 (D=0) → 0.83–0.99 at K=8 → 0.93–1.00 at K=16 for both models. The size of the day, not the task ceiling, is the bottleneck.
2. **Ceilings are session-shaped.** Flawless small sessions score ~94–96 — E is a real axis; 100 is unreachable by design.
3. **The interruption effect is task-dependent, not monotone** (DeepSeek: K=8 D≈D; seed-11 shows a large drop). Reported honestly with both seeds.
4. **Weaker models deflect work under load.** MiMo's "everything is up to date" / "no pending work" replies under interruption reveal avoidance — a measurable, visible-in-traces failure mode.
5. **Aggressive reordering is not a win.** DeepSeek K=16 D=0.6 preserves some retention by reordering tasks while breaking the state web (SWC=0).

## 7. Trace excerpts

**(a) Priority reordering (DeepSeek, K=8):** the agent fixes the code task before the data-munging task it was assigned first, explicitly citing priority. Retention is preserved per task, but the dependency obligation (consumer reading the cleaned CSV) is never satisfied in the assigned order — SWC evidence.

**(b) Deflection under load (MiMo, K=8, after interrupt):** the reply to a resumed task is a status report ("everything is up to date — no pending work") instead of execution; the file is never written in this segment. Isolation runs of the same task show real execution — the behavior is load-induced, not capability.

**(c) Session-confusion (DeepSeek, K=8):** two code-fix tasks in the same session; the agent answers the second with "the fix is already in place" — it believes it already did the work. Family-level IC for `code_fix` = 1.00.

## 8. Reproducibility & data

- Repository: <https://github.com/shyringo/myriad-bench>
- One command: `python scripts/run_grid.py` (requires an OpenCode Go / OpenAI-compatible key; zero dependencies)
- Full artifacts in release assets (v0.3.0): all 20 + 4 cell traces, metrics, tables, figures
- `docs/metrics.md` §8: fairness & versioning policy (everyone runs the same suite; versioned frozen suites, never per-model task sets)

## 9. Limitations

- Deterministic mock worlds: mechanism isolation over real-world messiness, deliberately.
- Two models, one provider catalog; generalization across providers is future work.
- D-effect varies across seeds — both seeds reported, no overclaim.
- Synthetic task families; LLM-judge axes are opt-in and cross-checked.
- Training-side continual learning and human-interface studies are out of scope.

## 10. Publication roadmap

1. **This report** — permanent, versioned with the repository (v1.0).
2. **arXiv** — under evaluation. Independent-researcher submission is permitted by arXiv policy; the current requirement is an *endorsement* for new submitters (since 2026-01-21, institutional email alone no longer qualifies). Path: existing arXiv account history if available, or endorsement from an established author in the field.
3. **Peer-reviewed venue** (Datasets & Benchmarks track) — under consideration once reviewer-critical mass (community replication) exists.

## 11. License & provenance

Code: MIT. Data (seeds, sessions, traces): CC BY 4.0. All task content is synthetic and procedurally generated — no external dataset is embedded. Provenance classification: [docs/provenance.md](docs/provenance.md).

---

*Cite this report as: MyriadBench project. "MyriadBench — Technical Report v1.0". 2026. https://github.com/shyringo/myriad-bench/blob/main/TECHNICAL_REPORT.md*