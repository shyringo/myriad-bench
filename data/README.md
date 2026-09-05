# Seeds & data

- `seeds/` — three hand-authored sessions, the reference experiences of the protocol:
  - `seed-a-consultant-morning.json` (tier S): lightly interleaved morning; 5 tasks, interrupts, filler chatter.
  - `seed-b-dependency-web.json` (tier M): 6 tasks wired through state-web obligations (cleaned CSV → email attach → memo → itinerary → brief).
  - `seed-c-long-haul.json` (tier M): 7 tasks, environment drift, two mid-session *injected* long-tail tasks (legal clause, quiz).
- Generated content lives in `generated/` (via `harness.cli generate`), results in `results/` (via `harness.cli run/report`). Both are gitignored and fully reproducible from seeds.

License: CC BY 4.0 (see LICENSE).
Provenance: all content synthetic/hand-authored; no external data is embedded.