# Contributing to MyriadBench

## Ways to contribute

1. **New task families** — the heart of the open task space. A family is a generator in `harness/tasks.py` (+ optional world extras) with a deterministic verifier. Guidelines:
   - Every family ships with a *rarity tier* (1 = head, 4 = long tail).
   - Verifiers should be deterministic where possible; `llm_judge` only with a golden-set cross-check.
   - Add at least one checkpoint verifier for switch-cost probes where meaningful.
   - Keep the mock world small: a family that needs a new env kind must add it to `harness/envs.py` and the schema enum.
2. **Sessions / seed data** — hand-authored sessions are the most valuable data we have; they make the protocol legible. Follow `data/seeds/*.json` and validate with `harness/validate.py`.
3. **Metrics** — open an issue with the mechanism you want isolated before implementing; metrics must name a mechanism, not vibes.
4. **Harness** — clean, stdlib-only Python 3.10, tests for everything.

## Development flow

```bash
python -m unittest discover -s tests   # 29 tests, must stay green
python -m harness.cli generate --out data/generated --mix-id dev --seed 1 --K 4 --NV 0
python -m harness.cli run --session data/generated/sessions/dev-s1.json --agent echo --out data/results
```

## Standards

- No new dependencies (stdlib only) unless discussed in an issue first.
- Every data change keeps `spec/*.schema.json` and `harness/validate.py` in sync.
- Every public claim in the README must be reproducible from the commands in it.
- Provenance: if you adapt an idea/format from another benchmark, say so in `docs/provenance.md`.

## Reporting results

A result report must include: model + endpoint, seeds, schema/verifier versions, cost (tokens/$), and the raw `metrics-*.json`. The leaderboard policy (once live) will require tier-L runs + all isolated baselines.