# Provenance & Originality

This document classifies every part of the repository into: **original work**,
**adaptations of published ideas/formats**, and **reused code/data** (none).

## A. Project-specific original work

- The **evaluation paradigm**: "mixture as the unit of evaluation" over an
  open task registry, with per-unit scores always anchored to isolated
  baselines, and an explicit long-tail/novelty split on the *mixture space*.
  To our knowledge no prior benchmark evaluates single-session, open-space,
  extreme multi-task mixtures.
- The **metric suite**: Interference Coefficient (geometric-mean retention),
  checkpoint-probe Switch Cost, Resume Fidelity via state-diff against
  uninterrupted references, State-Web Consistency via certified artifact
  hashes + consumption logs, Long-Tail Robustness by rarity tier, Budget
  Efficiency. These names/definitions are ours (see docs/metrics.md).
- The **session model**: one agent + one event stream + one persistent world
  state, with events assign/interrupt/resume/inject/env_change/tick/done and
  mid-session dynamic task injection (unbounded continuation).
- All **harness code** (compose/runner/verifiers/metrics/envs/agents): written
  from scratch for this project. No third-party code is vendored or wrapped.

## B. Adaptations of published ideas / formats (credited)

| Idea | Source | What we adapted |
|---|---|---|
| Event-stream session protocol | τ-bench (arXiv:2406.12045) | turn-based interaction with simulated users; we generalize to heterogeneous task streams with interrupts/resume/injection |
| Database-state verification | τ-bench | "compare final state" verification; we generalize to env snapshots + artifact certification hashes + consumption logs |
| Multi-domain in one session | MultiWOZ (arXiv:1810.00278) | the notion of spanning domains per session; we replace slot-filling with heterogeneous *tasks* with execution and state |
| Unified service environment + user state | PAUSE (arXiv:2607.27354), π-Bench, ASTRA-bench (arXiv:2603.01357) | persistent world state; we open the task space and add interference/switching metrics |
| Checklist-based completion | π-Bench | verifier checklists per task |
| Holistic taxonomy of scenarios | HELM (arXiv:2211.09110) | the idea of scenario/desiderata taxonomy; our taxonomy is task-family based and open |
| Task interference as a phenomenon | LLM Task Interference (arXiv:2402.18216, EMNLP 2024) | we scale the phenomenon from toy NLP prompts to full agentic sessions and make it a headline metric |
| Open-ended task generation philosophy | OMNI-EPIC (arXiv:2405.15568, ICLR 2025), GTA (ACL 2026) | procedural composition + programmatic injection |
| "Agent as OS" vocabulary | AIOS (arXiv:2403.16971) | scheduling/context-switch/memory vocabulary for the design narrative |

## C. Reused code/data

None. No external benchmark data is embedded; our data is generated
procedurally (seeded) or hand-authored for this project. Generated facts
(e.g., doc/market contents in `harness/tasks.py`) are synthetic.

## D. What we are NOT claiming

- Not a general AI benchmark (no AGI claim, no single-number IQ).
- Not a training-side continual-learning benchmark (supplementary, not
  covered — see docs/survey.md §H).
- Task prompts/verifiers are synthetic; they do not represent real
  workloads beyond the mock layer.

*All citations to be re-verified against the official versions before any
public release.*