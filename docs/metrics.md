# MyriadBench — Metric Definitions (v0.2)

Notation: for a session with units `U = {u_1..u_K}`, `s_i ∈ [0,1]` = per-unit
success in the mixed session (from verifier, possibly partial ∈ [0,1]),
`a_i ∈ [0,1]` = success in the isolated baseline run.

## 0. Myriad Index (MI) — the ONE headline number

**MI is the only ranking key of MyriadBench.** 0–100, higher is better.
It answers, in one number: *how much of a model's ability survives a mixed
day — relative to itself, alone.* Every other metric in this document is a
decomposition of it.

```
R = exp(mean_i ln(min(s_i / max(a_i, ε), 1)))        # session retention (= 1 − IC)
S = 0.5·SWC′ + 0.5·RF′     where X′ = X if defined else 1.0 (unstressed half)
T = mean retention of the hardest rarity tier present (max ρ)
E = min(1, (Σs_i / tokens_mixed) / mean_i(a_i / tokens_iso_i))   # budget retention

MI = 100 · Σ_active(w_k · x_k) / Σ_active(w_k)      # weighted mean over ACTIVE axes
```

- **Weights are fixed and public.** R is the direct measure of the
  multitasking tax; S of state continuity; T of long-tail robustness
  (the "uncountable" requirement); E of economy — re-doing every task from
  scratch may restore R but tanks E.
- **Active-axis policy**: an axis with no stress (no dependencies → SWC
  undefined; no interruptions → RF undefined) is *excluded from numerator and
  denominator* — never rewarded. A do-nothing agent scores ≈ 0, and the
  leaderboard mixes (DEP, IR > 0) stress all axes by construction.
- **Always relative to isolated baselines**: MI cannot be earned by running
  tasks alone. A report without isolated runs has `status: "no_isolated"` and
  no MI.
- Reported as `MI` + `MI_components` (R/S/T/E + weights + defined + tiers)
  in `metrics.json`.

## 1. Interference Coefficient (IC) — decomposition of R

- Per-unit retention: `r_i = min(s_i / max(a_i, ε), 1)` with `ε = 1e-6`.
- Session retention: `R = exp(mean_i ln r_i)` (geometric mean — any unit collapsing kills it).
- `IC = 1 − R`.
- Interpretation: IC ≈ 0 → multitasking is free; IC → 1 → session-level collapse.
- Report also per-family IC (`IC_fam`) to expose *which* families suffer.

## 2. Switch Cost (SC)

For each switch event at turn `t*` into unit `v`:

- `warm window` = first τ assistant turns of the segment (default τ = 3);
  `steady window` = the next τ turns.
- Subgoal probes: every unit's verifier exposes a *checkpoint sub-verifier*
  (a mid-task milestone, e.g. "locate the data file", "draft the outline").
- `SC = avg over switches of (probe success in steady window − probe success in warm window)`.
- Report also `SC_first` (switches into a *different family*) vs `SC_same`.

## 3. Resume Fidelity (RF)

For each interrupted unit:

- `touched(u)` = set of state keys the unit may modify (declared in the unit spec).
- Compare the final touched-state of the interrupted unit in the mixed run
  against its **uninterrupted reference run** (isolated trace):
  `RF_u = 1 − diff_fraction(hash(touched_mixed), hash(touched_isolated))`.
- `RF = mean over interrupted units`. Report bins by idle duration where data allows.

## 4. State-Web Consistency (SWC)

Dependency obligations: unit `v` declares `depends_on(u, artifact=a)`.
Obligation satisfied iff all three hold:

- the artifact's hash at the moment `u` finished (`certified`) exists,
- the current artifact hash equals `certified`,
- `v` actually read the artifact (consumption log).

`SWC = (# satisfied) / (# obligations)`; also `SWC_depth` = SWC restricted to
chains of length ≥ 3.

## 5. Long-Tail Robustness (LTR)

- `LTR(ρ) = mean r_i over units with rarity ρ` — report the monotonicity.
- MI's T component = `LTR(hardest tier present)`.

## 6. Budget Efficiency (BE)

- `BE = Σ s_i / tokens_used` (tokens per unit of passed weight).
- Token counting: agent-reported `usage` where available; fallback
  `len(text)/4` estimator flagged as estimated.
- MI's E component = BE_mixed / mean_i(BE_isolated_i), capped at 1.

## 7. Survivability (SV)

Same mixture at lengths `L ∈ {L0, 2L0, 4L0}` (units added, not stretched):
`SV(L) = R(L)`; report the curve and `L_collapse` (smallest L with
`R(L) < 0.5·R(L0)`). Requires tier-L protocol; reported as N/A otherwise.

## 8. Fairness & versioning(人人同跑:公平,永不测废)

**Core fairness principle: every model in the world runs the exact same benchmark —
同じ题、同じ流程、分数直接可比。** No model ever gets a different task set,
different process, or different difficulty to make scores look better.

1. **One official leaderboard suite, frozen.** The leaderboard runs a fixed set of
   mixtures (fixed seeds, fixed K/H/D/DEP/IR/NV, fixed event streams) and a fixed
   protocol (every task also isolated, same temperature 0). Anyone can reproduce
   any entry from the shipped reproducible block. Scores are directly comparable
   because the process is identical.
2. **The ceiling is not the goal.** The full score is unreachable by design:
   the E axis (token economy vs isolated baselines) is structurally un-gameable,
   so even a flawless agent pays a session tax and 100 does not exist.
   Saturation is thus structurally impossible inside a suite.
3. **Scoring high means being genuinely strong.** Every component is anchored to
   the model's *own* isolated baseline (R and E) or to structural invariants
   (SWC/RF/T). You cannot memorize your way up; you must genuinely lose nothing
   in the mixture. A MI of 95+ is therefore a world-recognizable claim, never
   a benchmark artifact.
4. **Versioning, not re-scoring.** If a future model ever approaches the
   practical ceiling, v2 releases a *new frozen suite* (harder families, deeper
   mixtures) — exactly the MMLU → MMLU-Pro / SWE-bench → Verified pattern.
   Old suites stay runnable forever (same seeds, same score meaning), so scores
   remain monotone evidence over time; cross-version calibration notes are
   published, and every version keeps the everyone-runs-the-same-suite property.

## 9. Reporting Contract

## 9. Reporting Contract

`metrics.json` contains: model_id, endpoint, session ids, MI (+components),
per-unit rows (family, rarity, isolated, mixed, retention), all metrics above
with config, cost summary (tokens, $ estimate if priced), and reproducibility
block (seeds, schema versions, verifier versions).

Leaderboard shows exactly one ranking key: **MI**. Everything else is a
breakdown column.