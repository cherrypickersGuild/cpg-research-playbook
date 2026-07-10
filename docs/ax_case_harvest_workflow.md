# Running the AX case harvest

Design/rationale: [`ax_case_strategy.md`](ax_case_strategy.md). This is just the how-to. Sibling
document: [`entity_harvest_workflow.md`](entity_harvest_workflow.md) — same pattern, applied to
AX transformation case leads instead of agent/mcp/prompt/skill entities.

## Usage

```
bash scripts/harvest_ax_cases.sh [target=250] [--check]
```

`target` is the **final total** of `verification_status:"verified"` cases the **canonical registry**
`state/ax_case_harvest_registry.json` should reach — **not** a number to add. Existing verified cases
count toward it, so the loop only closes the gap (`target - current`). Default is **250**. There is no
topic argument — unlike the entity harvest's four topics, this is a single lane.

Runs candidate-sourcing → extraction → `merge_ax_case_harvest_registry.sh` in a loop until the
registry has `target` verified cases, `NO_PROGRESS_THRESHOLD` consecutive loops add zero new verified
cases (sources exhausted), or `MAX_LOOPS` is hit. Each loop prints a diagnostics line
(`current`/`target`/`remaining`/`candidates`/`+new`/`dropped`/`no_progress`); the run always ends by
printing why it stopped. **A clean (exit 0) stop does not imply the target was met** — re-run with
`--check` to confirm.

`--check` prints one status line and exits 0 **without any `claude` call or side effects**:
```
[harvest][ax_cases] check: current=0 target=250 remaining=250 status=incomplete
```
It is also how `scripts/harvest_all.sh` decides whether to skip or run this lane. Needs only `jq`.

Grow AX cases as part of the full sequence (`agent → mcp → prompt → skill → AX`), or on its own:
```
bash scripts/harvest_all.sh            # all stages; AX runs last
bash scripts/harvest_all.sh --ax-only  # AX only
```
`AX_TARGET` (default 250) overrides the AX target for the orchestrator.

## Isolation — read this before running

This path is deliberately walled off from the rest of Stage 1:

- **Never reads or writes `state/entity_registry.json`.** Case data and entity data are
  structurally separate outputs; nothing in this script even opens that file.
- **Never reads or writes `state/ax_case_db.json`** — the existing rich pipeline's output. This is
  a standalone, lighter-weight catalog, not a replacement or a feeder for it (see
  `ax_case_strategy.md` §5 for the manual promotion path if a harvested case is ever strong enough
  to graduate).
- **Never reads or writes `state/visited_url_ledger.json`.** There is no ledger seed/patch step in
  this script at all — dedup against re-selecting a candidate is handled entirely by this run's own
  `state/ax_case_harvest_attempted.json` plus the existing registry's `source_url` values. This is a
  deliberate design choice, not an oversight — see `ax_case_strategy.md` §2.

## What it touches

- **Persistent (the only file this changes that matters across runs):**
  `state/ax_case_harvest_registry.json` — and only via `merge_ax_case_harvest_registry.sh`, never
  written directly. Every case carries `transformation_date` and `publication_date` as two separate
  fields (each independently `"unknown"` if the page doesn't state it) — the same shared rule the
  rich pipeline follows, without its date-window filtering.
- **Transient, gitignored (`state/ax_case_harvest_*`):** `ax_case_harvest_hits.json` (this loop's
  candidates), `ax_case_harvest_batch.json` (this loop's extractor output),
  `ax_case_harvest_attempted.json` (every URL sent this invocation, so a later loop doesn't
  re-select a candidate the extractor already rejected), `ax_case_harvest.err` (stderr from the two
  `claude -p` calls), `ax_case_harvest_raw_candidates.json` / `ax_case_harvest_raw_extract.json`
  (each call's raw stdout, captured unconditionally before it's piped through `jq`/`clean` — check
  these first when a loop fails with a JSON-parse error). All of these are overwritten every loop,
  so they only ever reflect the most recent (often the failing) one.

## Timing logs

Every invocation writes structured JSONL events to `state/logs/ax_case_harvest_<run_id>.jsonl`,
where `run_id` is `<UTC timestamp>-<PID>` (e.g. `20260708T012345Z-12345`). **Local, transient, and
gitignored** — `state/logs/` is never committed; treat these as scratch diagnostics, not a durable
record. Same event schema as `harvest_entities.sh`'s log (see `entity_harvest_workflow.md`'s
Timing logs section for the general shape) — `topic` is always the fixed string `"ax_cases"` in
this log, since there is only one lane here, which keeps the same reconstruction queries usable
against either log unchanged.

**Event types:** `script_start`, `topic_start`, `loop_start`, `claude_call_start`, `claude_call_end`
(`command_label` is `candidate_batch` or `case_extraction`), `merge_start`, `merge_end`,
`topic_end`, `script_end`, `error`. `topic_end` and `script_end` are emitted by a single exit trap,
so exactly one of each is written no matter how the run ends. `error` fires from that same trap but
only when the exit code is non-zero — a clean run never emits one.

**What you can reconstruct from a log:** total run duration (`script_end.duration_sec`), per-loop
duration (deltas between consecutive `loop_start` timestamps), Claude subprocess duration per
attempt (`claude_call_end.duration_sec`), merge duration (`merge_start`→`merge_end`), verified-count
deltas per loop (`merge_end.verified_before`/`verified_after`), and — on a non-zero exit — the
specific failure category via `error.detail`.

```bash
# find the most recent log
LATEST="$(ls -t state/logs/ax_case_harvest_*.jsonl | head -1)"

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

Safe and idempotent: already-processed URLs are excluded via the attempted-set (within one run) and
the existing registry's `source_url` values (across runs), so re-running the same command mostly
adds ~0 new cases once sources are exhausted or the target is met.

## Exit codes

- **0** — target reached, sources exhausted (`NO_PROGRESS_THRESHOLD` consecutive loops added 0 new
  verified cases), or `MAX_LOOPS` reached. All three print the final tally before exiting. Exit 0 is
  **not** proof the target was met — check the final line or re-run `--check`.
- **non-zero** — a real failure: `claude`/`jq` missing, a bad target argument, a `claude -p` call
  producing invalid/empty JSON after retries, `merge_ax_case_harvest_registry.sh` failing, or the
  registry found or left corrupted. Check `state/ax_case_harvest.err` first, then the matching
  `raw_candidates`/`raw_extract` file if the error mentions invalid JSON.
- Both `claude -p` calls (candidate-batch and case extraction) retry themselves in-process —
  `CANDIDATE_ATTEMPTS` / `EXTRACT_ATTEMPTS` attempts respectively — before failing, since the model
  occasionally prefixes its JSON with a stray sentence despite the "no prose" instruction (the same
  failure mode observed repeatedly in `harvest_entities.sh`'s live runs).

## Tuning

All env vars, overridable before invoking. Kept **distinct from `target`** (the final registry count):

| Var | Default | Meaning |
|---|---|---|
| final `target` (CLI arg) | `250` | final total of verified cases the registry should reach |
| `BATCH_SIZE` | `40` | candidate URLs requested per loop (bounded; never the whole remaining gap in one call) |
| `MAX_LOOPS` | `40` | hard upper bound on loops |
| `NO_PROGRESS_THRESHOLD` | `3` | consecutive no-progress loops (0 candidates **or** 0 new verified after merge) tolerated before stopping |
| `CANDIDATE_ATTEMPTS` / `EXTRACT_ATTEMPTS` | `3` each | in-process retries for each of the two `claude` calls |

Example: `BATCH_SIZE=60 MAX_LOOPS=60 bash scripts/harvest_ax_cases.sh 250`.

### Isolation / test overrides (default to production behavior)

- `STATE_DIR` — relocate all state/registry/log/batch paths in one shot (default `<repo>/state`).
- `CLAUDE_BIN` — the `claude` executable to invoke (default `claude`).

## Smoke tests

- **Real-registry live smoke:** `bash scripts/harvest_ax_cases.sh 3` is a valid tiny live smoke **only
  while the AX verified count is below 3** (currently 0). Once the registry has ≥ 3 verified cases,
  `target 3` is already satisfied and harvests nothing — bump the target above the current count instead.
- **Isolated fixture (no real registry):** `STATE_DIR=/tmp/fix bash scripts/harvest_ax_cases.sh 3`
  against a scratch `ax_case_harvest_registry.json`.
- **Offline test suites (no live `claude`):** `bash tests/test_harvest_targets.sh` and
  `bash tests/test_harvest_bounded.sh`.
