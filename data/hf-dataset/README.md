---
license: cc-by-4.0
language:
  - en
tags:
  - llm-evaluation
  - agent-benchmark
  - multitasking
  - benchmark
task_categories:
  - text-generation
pretty_name: MyriadBench Pilot Grid
---

# MyriadBench Pilot Grid

**One model. One session. All tasks.** — the pilot dataset of [MyriadBench](https://github.com/shyringo/myriad-bench), a benchmark for single-session, unbounded multi-task survival of AI agents.

## What's inside

| file | content |
|---|---|
| `metrics.csv` | 20 cells × (MI, IC, R/S/T/E components, RF, SWC, turns) |
| `sessions.jsonl` | 20 mixed sessions (task units, event streams, world states) |
| `traces.jsonl` | 40 full agent transcripts + usage (mixed × 2 models) |

## Schema

- `sessions.jsonl`: one session per line — `schema_version, session_id, meta.mixture {K,H,D,DEP,IR,NV}, world, units[], events[]`
- `traces.jsonl`: `session_id, model, turns[], interrupts[], usage, unit_reply`

## Protocol version

`v3-usagefix` — per-run token accounting, D is a clean single variable (independent random streams), identical task sets across D within each K.

## Grid

- Models: DeepSeek-V4-Flash, MiMo-V2.5 (OpenCode Go, temperature 0)
- K ∈ {2, 4, 8, 16} × D ∈ {0.0, 0.6}, seed 7 + seed-11 replication at K=8

Headline: interference tax IC 0.00 (K=2) → 0.83–1.00 (K=8+); MI ceilings ~95 even for flawless small sessions (the token tax is real).

## How to load

```python
import pandas as pd
df = pd.read_csv("hf://datasets/shyringo/myriad-bench-pilot/metrics.csv")
```

## Reproduce

```bash
git clone https://github.com/shyringo/myriad-bench
python scripts/run_grid.py            # requires MYRIAD API key (OpenCode Go)
```

## License & provenance

CC BY 4.0. All content synthetic/procedurally generated; no external data embedded. Full provenance: [docs/provenance.md](https://github.com/shyringo/myriad-bench/blob/main/docs/provenance.md).