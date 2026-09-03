# Data format (v0.1)

All data is JSON, validated by `spec/*.schema.json` and `harness/validate.py`.

## Session

```jsonc
{
  "schema_version": "0.1.0",
  "session_id": "mix-s7",
  "kind": "mixed | isolated",
  "isolated_unit": "t01_x" | null,
  "meta": { "name", "tier": "S|M|L", "seed", "mixture": {K, H, D, DEP, IR, NV} },
  "world": { "<env_id>": { "kind": "fs|calendar|email|dsv|code", "state": {...} } },
  "units": [ TaskUnit... ],
  "events": [ Event... ]
}
```

## TaskUnit

```jsonc
{
  "id": "t01_munging_inventory",
  "family": "data_munging",           // open registry
  "title": "...", "brief": "...", "background": "...",
  "tools": ["dsv", "fs"],
  "verifier": { "type": "...", "config": {...}, "weight": 1 },
  "priority": 1..5,
  "time_budget_min": 20,
  "rarity": 1..4,                      // long-tail tier
  "interruptible": true,
  "checkpoints": [ Verifier ],         // switch-cost probes
  "depends_on": [ { "unit": "t00_x", "artifact": "fs/out.csv" } ],
  "produce_artifacts": ["fs/out.csv"]  // state-web certification
}
```

## Event

```jsonc
{ "id": "e5", "kind": "assign|user_message|interrupt|resume|inject|env_change|tick|done",
  "at": "09:52", "unit": "t01_x" | null, "payload": {...} }
```

- `assign` / `inject` / `user_message` → user turn; the agent acts until it replies.
- `interrupt` → task paused (state snapshot before), `resume` → task continues (snapshot after).
- `env_change` / `tick` → system notes only (no agent turn required).

## World state containers

| kind | state | mutability |
|---|---|---|
| `fs` | `{"files": {relpath: content}}` | read / write / list / delete |
| `calendar` | `{"owner", "events": [{start, end, title}]}` | add / list (invariants checked) |
| `email` | `{"sent": [Mail], "inbox": [Mail]}` | send / list |
| `dsv` | `{"tables": {name: {cols, rows}}, "docs": {name: text}, "market": {ticker: {price, note}}}` | read-only |
| `code` | `{"readme", "files": {relpath: content}}` | read / write / list |

## Trace (runner output)

```jsonc
{
  "session_id", "kind", "isolated_unit", "agent", "model",
  "turns": [{ "i", "unit", "role", "content", "tool", "args", "at" }],
  "segments": { unit_id: [turn indices] },
  "unit_reply": { unit_id: last reply },
  "reads": [{ "env", "key", "unit", "ts" }],
  "writes": { unit_id: [artifact keys] },
  "interrupts": [{ "unit", "at", "touched_before", "touched_after" }],
  "artifacts": { artifact_key: content_hash },   // certified at producer segment end
  "env_at_unit_end": { unit_id: { "env:key": hash } },
  "turn_envs": [{ "i", "unit", "snapshot" }],    // probes for switch cost
  "env_meta": { env_id: kind },
  "env_final": { env_id: {...} },
  "usage": { "prompt_tokens", "completion_tokens" }
}
```

## MixtureConfig semantics

| knob | meaning |
|---|---|
| K | number of task units (before injection) |
| H | heterogeneity: rarity-tier mix (0 = all head, 1 = heavy tail) |
| D | interleaving density: probability a task gets interrupted mid-flight |
| DEP | dependency density: probability a later unit inherits an artifact obligation |
| IR | (reserved, folded into D in v0.1) interruption rate |
| NV | novelty: probability of a mid-session dynamic task injection (rare family) |