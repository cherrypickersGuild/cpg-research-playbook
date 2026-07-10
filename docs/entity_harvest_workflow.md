# Running the entity harvest

Design/rationale: [`entity_harvest_plan.md`](entity_harvest_plan.md). This is just the how-to.

## Usage

```
bash scripts/harvest_entities.sh <agent|mcp|prompt|skill> [target=250] [--check]
```

`target` is the **final total** of `description_source:"verified"` entities the topic should reach in
`state/entity_registry.json` (the canonical registry) — **not** a number to add. Existing verified
entities count toward it, so the loop only closes the gap (`target - current`). Default is **250**.

Runs candidate-sourcing → Stage 1G (fetch + verify) → `merge_entity_registry.sh` in a loop until the
topic has `target` verified entities, `NO_PROGRESS_THRESHOLD` consecutive loops add zero new verified
entities (sources exhausted), or `MAX_LOOPS` is hit. Each loop prints a diagnostics line
(`current`/`target`/`remaining`/`candidates`/`+new`/`dropped`/`no_progress`); the run always ends by
printing why it stopped. **A clean (exit 0) stop does not imply the target was met** — re-run with
`--check`, or use `scripts/harvest_all.sh`, to confirm.

`--check` prints one status line and exits 0 **without any `claude` call or side effects**:
```
[harvest][agent] check: current=115 target=250 remaining=135 status=incomplete
```
Use it to see remaining counts, or as the skip signal in orchestration. Needs only `jq`.

### Grow all four topics + AX cases (orchestrator)

```
bash scripts/harvest_all.sh                 # agent → mcp → prompt → skill → AX, sequentially
bash scripts/harvest_all.sh --entities-only # the four entity topics only
bash scripts/harvest_all.sh --ax-only       # AX cases only
```

`harvest_all.sh` runs each stage in order, first `--check`s it (skipping any topic already at target),
runs the harvest, then **re-checks**: a bounded child that stops below target is reported INCOMPLETE, and
the orchestrator exits non-zero if any requested stage is still below target (no false success).
Targets: `ENTITY_TARGET` (default 250, per topic) and `AX_TARGET` (default 250). Recommended manual order
matches the orchestrator's: `agent`, `mcp`, `prompt`, `skill`, then AX.

## What it touches

- **Persistent (the only file this changes that matters across runs):** `state/entity_registry.json`
  — and only via `merge_entity_registry.sh`, never written directly. Each entity record carries two
  URL fields: `source_url` (the URL that surfaced the entity — the awesome-list row, search-hit page,
  or citing article) and `target_url` (the entity's own primary page — repo, docs, model card,
  package page, paper, or official product page; `"unknown"` if it couldn't be confidently resolved).
  `state/visited_url_ledger.json` also persists (accumulates `entity_extracted`/`entity_ids`, same as
  every other stage-1 script); its row key for the harvest path is `source_url`. Each entity also
  carries `github_stars` — populated only when `target_url` is a confirmed GitHub repo root (a live
  count from the GitHub API), `null` for everything else; a later run's fresh measurement always
  overwrites the stored one, since this is popularity data, not identity data like `target_url`.
- **Transient, gitignored (`state/harvest_*`):** `harvest_<topic>_hits.json` (this loop's candidates,
  Hit shape `{hits:[{source_url,target_url,title,snippet,domain}]}`), `harvest_<topic>_entity_batch.json`
  (this loop's 1G output), `harvest_<topic>_attempted.json` (every `source_url` sent this invocation,
  so a later loop doesn't re-select a candidate 1G already rejected), `harvest_<topic>.err` (stderr
  from the two `claude -p` calls), `harvest_<topic>_raw_candidates.json` / `harvest_<topic>_raw_1g.json`
  (each call's raw stdout, captured unconditionally before it's piped through `jq`/`clean` — this is
  what to check when a loop fails with a JSON-parse error, since the `.err` file only has stderr and
  won't show a malformed *stdout* response). All four `raw_*`/batch files are overwritten every loop,
  so they only ever reflect the most recent (often the failing) one.

## Timing logs

Every invocation writes structured JSONL events to `state/logs/harvest_<run_id>.jsonl`, where
`run_id` is `<UTC timestamp>-<PID>` (e.g. `20260708T012345Z-12345`). **Local, transient, and
gitignored** — `state/logs/` is never committed; treat these as scratch diagnostics, not a durable
record.

**Event types**, one JSON object per line, always carrying `ts`/`run_id`/`event`:
`script_start`, `topic_start`, `loop_start`, `claude_call_start`, `claude_call_end`, `merge_start`,
`merge_end`, `topic_end`, `script_end`, `error`. `topic_end` and `script_end` are emitted by a
single exit trap, so exactly one of each is written no matter how the run ends (normal exit,
`set -e` failure, or a caught SIGINT/SIGTERM — SIGKILL can't be trapped by anything and leaves no
final event). `error` fires from that same trap but only when the exit code is non-zero — a clean
run (target reached, sources exhausted, `MAX_LOOPS` hit) never emits one.

**What you can reconstruct from a log:** total run duration (`script_end.duration_sec`), per-topic
duration (`topic_start`→`topic_end` timestamps), per-loop duration (deltas between consecutive
`loop_start` timestamps), Claude subprocess duration per attempt (`claude_call_end.duration_sec`,
labeled `candidate_batch` or `1g_extraction`), merge duration (`merge_start`→`merge_end`), verified-
count deltas per loop (`merge_end.verified_before`/`verified_after`), and — on a non-zero exit — the
specific failure category via `error.detail` (e.g. `candidate_batch_failed_after_retries`,
`merge_entity_registry_failed`) instead of needing to dig through the Claude Code session transcript.

Example inspection commands:

```bash
# find the most recent log
LATEST="$(ls -t state/logs/harvest_*.jsonl | head -1)"

# pretty-print every event
jq -c . "$LATEST"

# total run duration and how it ended
jq -r 'select(.event=="script_end") | "duration=\(.duration_sec)s exit_code=\(.exit_code)"' "$LATEST"

# per-claude-call durations, in order
jq -r 'select(.event=="claude_call_end") | "\(.command_label)\t\(.duration_sec)s\t\(.detail)"' "$LATEST"

# only the error event, if any
jq -r 'select(.event=="error")' "$LATEST"
```

## Re-running

Safe and idempotent: already-processed `source_url`s are excluded via the ledger (keyed on
`source_url` for the harvest path) and the existing registry contents (keyed on `target_url` at
candidate-batch exclusion time, on `entity_key` at merge time), so re-running the same command mostly
adds ~0 new entities once a topic is exhausted or at target. The `attempted_urls` set itself resets
each invocation — it only prevents re-picking a rejected candidate *within* one run, not across
separate runs.

## Exit codes

- **0** — target reached, sources exhausted (`NO_PROGRESS_THRESHOLD` consecutive loops added 0 new
  verified entities), or `MAX_LOOPS` reached. All three print the final tally before exiting. Exit 0
  is **not** proof the target was met — check the final line or re-run `--check`.
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

All env vars, overridable before invoking. Kept **distinct from `target`** (the final registry count):

| Var | Default | Meaning |
|---|---|---|
| final `target` (CLI arg) | `250` | final total of verified entities the topic should reach |
| `BATCH_SIZE` | `40` | candidate URLs requested per loop (bounded; never the whole remaining gap in one call) |
| `MAX_LOOPS` | `40` | hard upper bound on loops |
| `NO_PROGRESS_THRESHOLD` | `3` | consecutive no-progress loops (0 candidates **or** 0 new verified after merge) tolerated before stopping |
| `CANDIDATE_ATTEMPTS` / `ONEG_ATTEMPTS` | `3` each | in-process retries for each of the two `claude` calls (stray-prose formatting slips) |

Example: `BATCH_SIZE=60 MAX_LOOPS=60 bash scripts/harvest_entities.sh prompt 250`.

### Isolation / test overrides (default to production behavior)

- `STATE_DIR` — relocate **all** state/registry/log/batch paths to an alternate dir in one shot
  (default `<repo>/state`). Used by the offline tests to run against fixtures without touching real state.
- `CLAUDE_BIN` — the `claude` executable to invoke (default `claude`). Used by the offline boundedness
  test to drive the real loop with a deterministic mock.

## Smoke tests

- **Isolated fixture (no real registry):** point `STATE_DIR` at a scratch dir holding a small
  `entity_registry.json`, e.g. `STATE_DIR=/tmp/fix bash scripts/harvest_entities.sh agent 5`. A tiny
  `target` like 5 only makes sense here — on the real registry every topic is already well above 5, so
  it would harvest nothing.
- **Controlled live smoke (real registry):** use a `target` a few **above** the current verified count
  so a couple of records are actually harvested — e.g. if `--check` shows agent at 115,
  `bash scripts/harvest_entities.sh agent 117`. Never use a `target` below the current count (it is a
  no-op).
- **Offline test suites (no live `claude`):** `bash tests/test_harvest_targets.sh` and
  `bash tests/test_harvest_bounded.sh`.
