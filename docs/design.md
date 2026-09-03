# MyriadBench — Design Specification (v0.1)

> **One model. One session. All tasks.**
> A benchmark protocol for measuring how frontier agents sustain performance on *unbounded, heterogeneous, interleaved task mixtures* within a single session.

## 1. Vision & Thesis

**Far-future thesis.** AI converges toward a single model being the one entry point to a person's entire digital life (everything except human-to-human relationships). One agent, one long-running session, handling *countless* tasks: coding, research, scheduling, communication, analysis, creative work, tool use — interleaved, interrupted, resumed, mutually dependent.

**Therefore the "multi" in multi-task is not N.** It is a *task continuum*: an open-ended space whose mixtures multiply combinatorially, with novel combinations appearing at test time. The capability that matters is not per-task ceiling skill but:

- **preservation** (how much mixed-session interference reduces per-task performance),
- **switching** (cost of context switches between heterogeneous tasks),
- **state continuity** (consistency of a web of cross-task dependencies over a long horizon),
- **long-tail robustness** (grace on novel/unseen mixtures),
- **resource economics** (context/token budget per unit of accomplished work).

**Existing benchmarks** measure either (a) parallel closed task sets (MMLU, HLE, GAIA: tasks are independent questions), or (b) single-task long-horizon agents (SWE-bench, WebArena, OSWorld, MLE-bench), or (c) shallow multi-domain dialogue (MultiWOZ: same ontology, slot-filling, no execution). The closest recent line — personal-assistant benchmarks (PAUSE, π-Bench, ASTRA-bench) — proves the paradigm but keeps the task space *service-closed* and per-session task counts small, and does not measure interference/switch cost at all. See `docs/survey.md`.

**MyriadBench is the first benchmark whose object of measurement is exactly the single-session, open-space, extreme-multi-task regime.**

## 2. Conceptual Model

```
              ┌─────────────────────────────────────────────┐
              │  ONE AGENT INSTANCE (one model, one context) │
              └──────────────▲──────────────────────────────┘
      acts / tool calls      │  event stream (assign, msg,
        modify world state   │  interrupt, resume, inject, tick)
              ┌──────────────┴──────────────┐
              │  SESSION                    │
              │   - event stream (replayable)│
              │   - persistent world state  │  FileSystem, Calendar,
              │     (a "life": workspace,   │  Email, DataSource,
              │      calendar, mailbox,     │  CodeRepo, ...
              │      data, code repo)       │
              │   - task units (open family │
              │     registry, verifiable)   │
              └─────────────────────────────┘
```

Three abstractions:

1. **TaskUnit** — the smallest verifiable unit of work. Belongs to a *family* (open registry). Has a user-facing brief, required tools, a verifier (deterministic or LLM-judge), dependencies on other units, priority, and a time budget.
2. **Session** — one agent + one event stream + one persistent world state. Tasks arrive, interleave, suspend, resume, get interrupted, and depend on each other through *world state* (not through conversation only).
3. **MixtureConfig** — the experimental treatment: (K) number of tasks, (H) heterogeneity, (D) interleaving density, (DEP) dependency density, (L) session length, (IR) interruption rate, (NV) novelty. A *mixture* is an instance of the treatment; the same mixture can be run on many agents.

## 3. Design Principles

| # | Principle | Consequence |
|---|---|---|
| P1 | **Open task space** — "countless" is a requirement, not a slogan | Task families are pluggable (schema + env + verifier). No closed list. Mixtures are algorithmically composed; new families only add value. |
| P2 | **Mixture is the unit of evaluation**, not task | Report per-family success *against isolated baselines*. Interference coefficient is the headline quantity. |
| P3 | **State is the medium of dependency** | Cross-task dependencies flow through the world state (files, calendar, email, data), enabling verifiable *state-web consistency* checks, not just conversational recall. |
| P4 | **Novelty is explicit** | Every task/mixture carries novelty tags. Held-out mixtures form the *long-tail split*. Contamination-resistant by construction (lives on generated mixtures, not memorized answers). |
| P5 | **Deterministic by default** | Mock environments, seeded RNG, replayable transcripts. LLM-judge verifiers are opt-in and cross-checked on a golden set. |
| P6 | **Everyone runs the same suite** | One official leaderboard suite (fixed seeds, fixed mixtures, fixed protocol) — every model in the world runs the identical benchmark and process; scores are directly comparable. Session length options S/M/L are research extensions, never part of official comparison. |
| P7 | **Mechanism, not vibes** | Every headline metric names the mechanism it isolates: interference, switch cost, resume fidelity, state consistency, long-tail robustness, budget efficiency. |

## 4. Task Family Registry (v0 shipped families)

A family = `(brief_generator, env_requirements, verifier, difficulty, novelty_axes)`.

| Family | What the agent must do | Verification |
|---|---|---|
| `research_memo` | Research a question against a mock data source (docs + market data), write a memo file with specific facts | Deterministic fact checks against source of truth |
| `data_munging` | Transform a CSV artifact (schema drift, missing values, units) into a target schema | Exact output file + numeric assertions |
| `scheduling` | Build a conflict-free schedule from constraints + existing calendar | Calendar state invariant checks |
| `comms` | Draft/update an email or message satisfying a checklist (tone, cc, attachments, policy) | Checklist assertions (regex/structured) |
| `code_fix` | Fix a bug in a provided Python file | Hidden tests executed in a subprocess (timeout, no network) |
| `math_word` | Solve word problems with units/rounding rules | Numeric tolerance + working-file check |
| `travel_plan` | Produce an itinerary artifact satisfying constraints (budget, order, preferences) | Constraint solver on the artifact |
| `creative_brief` | Write a brief/marketing copy containing required elements | Structural + keyword + style heuristics |
| *(future)* | multimodal, web, MCP tools, external APIs, human-in-loop | — |

Community extension is a first-class flow: `family_spec.json` + verifier plugin. That is how the space stays *countless*.

## 5. Session Composition (the "countless" machinery)

`compose.py` builds a session from a MixtureConfig:

1. **Sample K task units** from the registry distribution (long-tail-weighted: head families frequent but easy → tail families rare but unusual; *novelty tags* control how far into the tail we go).
2. **Dependency DAG**: with probability DEP, unit B consumes an artifact produced by unit A (file, computed number, calendar slot). Leaves *state-web obligations* that verifiers enforce.
3. **Event stream synthesis**: tasks arrive over time; with density D they interleave (task A paused mid-flight, task B assigned, A resumed); with rate IR a task is interrupted and resumed later; a *dynamic injection* event can add a brand-new task mid-session (unbounded continuation).
4. **Reference runs**: for every unit, an *isolated session* is auto-generated (same brief, empty background) — this is the baseline for interference metrics.

All randomness is seeded; the same `mixture_id` reproduces the identical session and baselines.

## 6. Evaluation Protocol

```
isolated runs:   unit_i alone            -> iso_score_i
mixed run:       full session            -> session_score_i (per unit)
metrics:         docs/metrics.md
```

Headline quantities (defined precisely in `docs/metrics.md`):

- **Interference Coefficient (IC)** — geometric-mean degradation of per-unit success in the mixed session vs isolated. IC=0: no interference; IC close to 1: multitasking collapse.
- **Switch Cost (SC)** — success drop within the first τ turns after a task switch vs the same unit's steady-state window. Measures "attention residue".
- **Resume Fidelity (RF)** — state continuity across interruption: final state of an interrupted unit vs its uninterrupted reference trajectory (state-diff over the unit's touchable state keys).
- **State-Web Consistency (SWC)** — fraction of dependency obligations satisfied: B's input artifact equals A's certified artifact (checksums / content equality / constraint satisfaction).
- **Long-Tail Robustness (LTR)** — success bucketed by novelty level, plus worst-decile-mixture success.
- **Budget Efficiency (BE)** — tokens (or simulation cost) per passed unit, and per unit of state-web progress.
- **Survivability (SV)** — score as a function of session length; the "context Kelvin scale": at which length does the curve collapse.

Grading: the official leaderboard runs the *single fixed suite* — every submitted
model executes the identical sessions and isolated baselines (same seeds, same
process), so entries are directly comparable. Session-length options (S/M/L) and
community mixtures are research extensions and never enter official comparison.

## 7. Data Format (see `spec/*.schema.json`)

- `session.schema.json` — session envelope: meta (mixture params), world (initial state), units[], events[].
- `task-unit.schema.json` — family, brief, tools, verifier config, dependencies, priority, time budget, novelty.
- `verifier.schema.json` — verifier type + typed config (file checks, numeric asserts, checklist, code tests, state-web, llm_judge stub).

Events: `task_assign`, `user_message`, `interrupt`, `resume`, `inject`, `env_change`, `tick`, `done`.

## 8. Harness (see `harness/`)

- `compose.py` — mixture/session generation (seeded).
- `envs.py` — deterministic in-memory environments: FileSystem, Calendar, EmailBox, DSV (data source), CodeRepo.
- `runner.py` — event-driven loop; drives any `Agent` with `act(transcript, tool_spec) -> action`; records full transcript + env snapshots.
- `agents.py` — `ReplayAgent` (tests), `EchoAgent`, `OpenAICompatAgent` (stdlib-only HTTP, any OpenAI-compatible endpoint).
- `verifiers.py` — verifier implementations + `run_checks`.
- `metrics.py` — all metric functions; produce `metrics.json` + human-readable report.
- `cli.py` — `generate`, `run`, `isolate`, `report` subcommands.
- `tests/` — unittest, stdlib only, `python -m unittest discover -s tests`.

## 9. Roadmap

- [x] v0.1: protocol spec, schemas, composer, runner, verifiers, metrics, 8 task families, 3 seed sessions, tests
- [ ] v0.2: pilot runs on frontier models (any OpenAI-compatible endpoint) → first interference curves; golden-set cross-check for LLM-judge verifiers
- [ ] v0.3: tier-L sessions (multi-day event streams), dynamic injection stress, community family SDK + docs
- [ ] v1.0: dataset release (HF), leaderboard, competition policy, arXiv paper v1

## 10. Threats & Honest Limits

- **Verifier leakage**: deterministic verifiers can be gamed; mitigations = hidden test variants, golden-set calibration, state-diff checks.
- **Simulation cheapness**: mock worlds understate real-world messiness (externalities, ambiguity); we deliberately trade realism for *mechanism isolation* — the point is measuring the multitasking bottleneck, not task SOTA.
- **LLM-judge variance**: opt-in, cross-checked, reported as secondary.
- **Single-session regime**: our claim is scoped to *session-level* multitasking; training-side continual learning (forgetting across tasks over time) is complementary, not covered (see survey §H).