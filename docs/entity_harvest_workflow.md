# Running the entity harvest

Design/rationale: [`entity_harvest_plan.md`](entity_harvest_plan.md). This is just the how-to.

## Usage

```
bash scripts/harvest_entities.sh <agent|mcp|prompt|skill> [target=100]
```

Runs candidate-sourcing → Stage 1G (fetch + verify) → `merge_entity_registry.sh` in a loop until the
topic has `target` entities with `description_source:"verified"` in `state/entity_registry.json`, a
loop adds zero new verified entities (sources exhausted), or `MAX_LOOPS` (default 12) is hit. Each
loop prints a tally line; the run always ends by printing why it stopped.

Recommended order, since `prompt` currently sits at 0: `agent`, `mcp`, `prompt`, `skill`.

## What it touches

- **Persistent (the only file this changes that matters across runs):** `state/entity_registry.json`
  — and only via `merge_entity_registry.sh`, never written directly. `state/visited_url_ledger.json`
  also persists (accumulates `entity_extracted`/`entity_ids`, same as every other stage-1 script).
- **Transient, gitignored (`state/harvest_*`):** `harvest_<topic>_hits.json` (this loop's candidates),
  `harvest_<topic>_entity_batch.json` (this loop's 1G output), `harvest_<topic>_attempted.json` (every
  URL sent this invocation, so a later loop doesn't re-select a candidate 1G already rejected),
  `harvest_<topic>.err` (stderr from the two `claude -p` calls), `harvest_<topic>_raw_candidates.json`
  / `harvest_<topic>_raw_1g.json` (each call's raw stdout, captured unconditionally before it's piped
  through `jq`/`clean` — this is what to check when a loop fails with a JSON-parse error, since the
  `.err` file only has stderr and won't show a malformed *stdout* response). All four `raw_*`/batch
  files are overwritten every loop, so they only ever reflect the most recent (often the failing) one.

## Re-running

Safe and idempotent: already-processed URLs are excluded via the ledger and the existing registry
contents, so re-running the same command mostly adds ~0 new entities once a topic is exhausted or at
target. The `attempted_urls` set itself resets each invocation — it only prevents re-picking a
rejected candidate *within* one run, not across separate runs.

## Exit codes

- **0** — target reached, sources exhausted (a loop added 0 new verified entities), or `MAX_LOOPS`
  reached. All three print the final tally before exiting.
- **non-zero** — a real failure: `claude`/`jq` missing, bad arguments, a `claude -p` call producing
  invalid/empty JSON, `merge_entity_registry.sh` failing, or the ledger/registry found or left
  corrupted. Check `state/harvest_<topic>.err` first, then the matching `raw_candidates`/`raw_1g`
  file above if the error mentions invalid JSON. Retrying is safe: the failed loop's candidates
  were already seeded into the ledger as `entity_extracted:false` (not `true`), so they aren't
  excluded and get picked up again.
- Both `claude -p` calls (candidate-batch and 1G extraction) retry themselves in-process —
  `CANDIDATE_ATTEMPTS` / `ONEG_ATTEMPTS` attempts respectively — before failing, since the model
  occasionally prefixes its JSON with a stray sentence despite the "no prose" instruction.
  Observed on both calls in live runs (not just the first one), often enough to be worth an
  automatic retry rather than a manual re-invocation every time. Only after all attempts are
  exhausted does the loop hard-fail with the non-zero exit above.

## Tuning

Override before invoking: `BATCH_SIZE` (candidates requested per loop, default 25), `MAX_LOOPS`
(default 12), `CANDIDATE_ATTEMPTS` / `ONEG_ATTEMPTS` (retries per loop for each of the two
`claude -p` calls, default 3 each). All env vars, e.g.
`BATCH_SIZE=40 bash scripts/harvest_entities.sh mcp 150`.
