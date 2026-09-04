# LLM-judge verifiers (opt-in)

MyriadBench prefers deterministic verifiers: they are cheap, replayable, and
cannot drift. The `llm_judge` verifier type exists for tasks where automated
grading is genuinely hard (tone, creativity constraints, subjective rubric).

## Policy (v0.1)

1. **Opt-in**: a run that uses `llm_judge` must say so in the report;
   leaderboard entries must state the judge model + prompt version.
2. **Cross-checked**: every judge-rubric ships with a golden set of ≥ 20
   labeled examples (pass/fail); before each leaderboard run, the judge must
   score ≥ 90% agreement with the labels, or the run is invalidated.
3. **Secondary**: judge scores never replace deterministic verifier scores in
   the headline metrics; they may add a supplementary "quality" axis.
4. **Never on state**: state-web obligations, file existence, calendar
   invariants, numeric assertions, and code tests must always be deterministic.

## Implementation status

The verifier type is registered in `harness/verifiers.py` and returns
`skipped` until a provider adapter is wired (planned for v0.2, same
OpenAI-compatible endpoint as the agent harness).