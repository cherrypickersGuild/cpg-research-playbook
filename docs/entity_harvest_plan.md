# Entity Harvest Plan — growing entity_registry.json to ≥250 verified entities per topic

## Goal and current state

`state/entity_registry.json` began at 17 entities from a single 1G run over `state/news_hits.json` and
has since grown through the harvest harness (run `bash scripts/harvest_entities.sh <topic> --check` for
live per-topic counts). The target is **≥250 entities per topic
(`agent`/`mcp`/`prompt`/`skill`), all with `description_source: "verified"`**, where *verified* means
the description was pulled from the **entity's own primary page** (`target_url` — its repo, docs page,
model card, package page, paper page, or official product page), never from the citing page
(`source_url` — an awesome-list README, a search-hit page, a news article) and never from a search
snippet alone.

## Why volume, not machinery, is the gap

1G (`agents/stage1/1G_entity_extractor.md`) and `scripts/merge_entity_registry.sh` already do the
right thing: 1G WebFetches each candidate and emits an entity batch + `ledger_patch`; the merge script
dedups by `entity_key` (`topic|lowercase(name)`), upgrades `snippet-only → verified` on corroboration,
and never clobbers or downgrades an existing record. What's missing is **input volume** — the ledger
(`state/visited_url_ledger.json`) has only 16 URLs recorded as entity-processed. Two much larger pools
have never been run through 1G at all:

- `state/search_hits_<topic>.json` shards (~90–120 hits each, `search_hits_skills.json` for `skill`) —
  collected by 1B/1A but only ever fed to 1C (case extraction), never to 1G.
- `reports/awesome-lists/awesome_<topic>.md` — curated landscape reports (~40 rows each) that cite
  source awesome-list READMEs with **thousands** of further named entries. These reports and the
  awesome-list README URLs themselves are **seed material only** — they appear as a candidate's
  `source_url`, never as its `target_url`; the entity's own primary page must be resolved separately.

## Harness: `scripts/harvest_entities.sh` (built)

`bash scripts/harvest_entities.sh <topic> [target=250] [--check]`, `<topic> ∈ {agent,mcp,prompt,skill}`.
The how-to (final-target semantics, `--check`, tuning, the `scripts/harvest_all.sh` orchestrator, and
smoke-test guidance) lives in [`entity_harvest_workflow.md`](entity_harvest_workflow.md).
Structure mirrors `scripts/discover.sh` (source `pipeline.config.sh`, build `FLAGS`, reuse `clean()`,
reuse the ledger `jq -s` merge pattern), reusing the 1G invocation already in `run_stage1.sh:57-69` and
`merge_entity_registry.sh` unchanged — no changes needed to either.

### Per-loop steps

1. **Build candidate batch** — one `claude -p` call (`allowedTools: Read,WebFetch,WebSearch`) that:
   - Reads `reports/awesome-lists/awesome_<topic>.md` plus the source awesome-list raw READMEs it
     cites, and `state/search_hits_<mapped>.json`.
   - For every candidate, returns BOTH `source_url` (the original seed URL — the awesome-list row,
     search-hit page, or citing article where the entry was found) AND `target_url` (a best-effort
     resolved primary URL — repo / docs / model card / package page / paper / official product page).
     If `target_url` can't be confidently determined, the candidate-batch step emits the literal
     string `"unknown"` rather than guessing; 1G may still resolve it later via WebFetch.
   - **Excludes** any candidate whose `source_url` is already `entity_extracted:true` in the ledger
     or already present in the run's attempted-set (`state/harvest_<topic>_attempted.json`, step 5);
     also excludes any candidate whose `target_url` (when not `"unknown"`) is already a `target_url`
     in `state/entity_registry.json` (prevents re-cataloging the same entity via a different citing
     page).
   - Emits Hit-shaped JSON (`{hits:[{source_url,target_url,title,snippet,domain}]}`, capped at
     `BATCH_SIZE=25`) to transient `state/harvest_<topic>_hits.json`.
2. **Extract + verify** — run 1G over that hits file (`allowedTools: Read,WebFetch`) so every kept
   entity's `target_url` is actually fetched, giving `description_source:"verified"` (verified means
   the description came from `target_url` specifically — never from `source_url`, never from the
   snippet alone); write transient `state/harvest_<topic>_entity_batch.json`; fold its `ledger_patch`
   into `visited_url_ledger.json` using the same `jq -s` technique `run_stage1.sh` already uses.
3. **Merge** — `bash scripts/merge_entity_registry.sh state/harvest_<topic>_entity_batch.json state/entity_registry.json`.
4. **Tally** — count strictly `topic == <topic>` **and** `description_source == "verified"`:
   ```
   jq --arg t "$TOPIC" '[.entities[] | select(.topic==$t and .description_source=="verified")] | length' state/entity_registry.json
   ```
   Print `[harvest][<topic>] loop N: +K new verified → V/<target>`.
5. **Record attempts (no retry loops)** — union every `source_url` sent in this loop's batch
   (accepted *or* rejected by 1G) into `state/harvest_<topic>_attempted.json`. Combined with the
   ledger's `entity_extracted:true` (which 1G sets even for hits it decides aren't entities), this
   guarantees a `source_url` rejected or unverifiable in one loop is never re-selected in a later
   loop. The ledger (`state/visited_url_ledger.json`) also keys on `source_url` for the harvest
   path — see `scripts/harvest_entities.sh`'s inline note for why source_url was chosen over
   target_url as the ledger dedup key (short version: the ledger is "visited URL" semantics, so
   it tracks the fetched citing page; the "don't re-catalog same entity" guarantee is handled
   separately by registry `target_url` exclusion at candidate-batch time and by `entity_key` dedup
   at merge time).

### Stop / failure semantics

- **Exit 0 (normal stop):** `verified ≥ target`; a loop adds 0 new verified entities (sources
  exhausted for this topic); `MAX_LOOPS=12` reached. Each case prints the final tally so the caller
  knows which one happened.
- **Exit non-zero (real failure):** `claude` or `jq` missing from PATH; a `claude -p` call returns
  empty or fails `jq empty` (invalid JSON); `merge_entity_registry.sh` returns non-zero;
  `state/entity_registry.json` fails to parse before or after a merge. `set -euo pipefail` throughout;
  every produced file is validated before being consumed by the next step.

### Persistence and repo hygiene

- `state/entity_registry.json` remains the **only** persistent output, written solely by
  `merge_entity_registry.sh` — the harness never writes to it directly.
- All `state/harvest_<topic>_*.json` files (hits, entity batch, attempted-set) are transient,
  regenerated per run, and should be added to `.gitignore` alongside the existing
  `state/news_hits.json` / `state/news_entity_batch.json` entries when the script is built.
- Every entity also carries `github_stars` — a live number, populated by 1G only when `target_url`
  resolves to a GitHub repo root (fetched from the GitHub API, never scraped or inferred from a
  page that merely mentions a star count), `null` otherwise. `merge_entity_registry.sh` treats it
  as freshness data, not identity data: the latest non-null measurement always wins, no
  conflict-log entry needed (unlike a `target_url` mismatch).
- `state/entity_registry.json`'s top-level `metadata` block (topics, entity_types, counts) is
  fully recomputed by `merge_entity_registry.sh` on every merge.

## Verification

1. `bash -n scripts/harvest_entities.sh` — syntax check; confirm dependency guards match
   `discover.sh`'s `command -v claude`/`command -v jq` checks.
2. Offline suites (no live `claude`): `bash tests/test_harvest_targets.sh` (target/remaining/skip logic)
   and `bash tests/test_harvest_bounded.sh` (MAX_LOOPS / NO_PROGRESS termination via a mock `CLAUDE_BIN`,
   plus an assertion that real `state/` is byte-unchanged).
3. Controlled live smoke — use a `target` a few **above** the current verified count for a topic (see
   `--check`), e.g. `bash scripts/harvest_entities.sh agent 117` when agent is at 115. Confirm transient
   `state/harvest_agent_*` files appear, the tally increments loop over loop, every new `topic:"agent"`
   row has `description_source:"verified"` with a `target_url` distinct from `source_url` (and not an
   awesome-list README), and pre-existing entities are untouched. A `target` **below** the current count
   is a no-op — never use one as a smoke target against the real registry.
4. Idempotency — re-run the same command; it should add ~0 new verified entities and exit via the
   "0 new" stop path, proving the ledger + attempted-set + registry dedup actually prevents rework.
5. Failure paths — temporarily break `jq` on PATH or point at a corrupted registry file; confirm the
   script exits non-zero instead of silently continuing.
6. `git status --porcelain state/` shows no `harvest_*` files staged (they are gitignored).
7. Grow each topic to 250, in order, via the orchestrator: `bash scripts/harvest_all.sh --entities-only`
   (or one topic at a time, `bash scripts/harvest_entities.sh <topic> 250`) — the long, WebFetch-heavy
   phase. `harvest_all.sh` skips any topic already at target and exits non-zero if any stays below it.

## Recommended run order

`agent` → `mcp` → `prompt` → `skill` (then AX cases via `scripts/harvest_ax_cases.sh`) — the order
`scripts/harvest_all.sh` uses. `prompt` is the thinnest topic and therefore the longest to reach 250.
