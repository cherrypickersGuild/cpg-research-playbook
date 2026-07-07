# Entity Harvest Plan — growing entity_registry.json to ≥100 verified entities per topic

## Goal and current state

`state/entity_registry.json` currently holds 17 entities (9 `agent`, 7 `mcp`, 1 `skill`, 0 `prompt`) —
from a single 1G run over `state/news_hits.json`. The target is **≥100 entities per topic
(`agent`/`mcp`/`prompt`/`skill`), all with `description_source: "verified"`**, where *verified* means
the description was pulled from the **entity's own primary page** — its repo, docs page, model card,
package page, paper page, or official product page — never from an awesome-list README or a search
snippet.

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
  awesome-list README URLs themselves are **seed material only** — never emit an awesome-list URL as
  an entity's own `url`; the entity's own primary page must be resolved first.

## Proposed harness: `scripts/harvest_entities.sh` (design; not built yet)

`bash scripts/harvest_entities.sh <topic> [target=100]`, `<topic> ∈ {agent,mcp,prompt,skill}`.
Structure mirrors `scripts/discover.sh` (source `pipeline.config.sh`, build `FLAGS`, reuse `clean()`,
reuse the ledger `jq -s` merge pattern), reusing the 1G invocation already in `run_stage1.sh:57-69` and
`merge_entity_registry.sh` unchanged — no changes needed to either.

### Per-loop steps

1. **Build candidate batch** — one `claude -p` call (`allowedTools: Read,WebFetch,WebSearch`) that:
   - Reads `reports/awesome-lists/awesome_<topic>.md` plus the source awesome-list raw READMEs it
     cites, and `state/search_hits_<mapped>.json`.
   - **Resolves each seed entry to the project's own primary URL** (repo / docs / model card /
     package page / paper / official product page). Entries whose own source URL can't be determined
     are dropped rather than guessed.
   - **Excludes** any URL that is already `entity_extracted:true` in the ledger, already present in
     the run's attempted-set (`state/harvest_<topic>_attempted.json`, step 5), or already a `url` in
     `state/entity_registry.json`.
   - Emits Hit-shaped JSON (`{hits:[{url,title,snippet,domain}]}`, capped at `BATCH_SIZE=25`) to
     transient `state/harvest_<topic>_hits.json`.
2. **Extract + verify** — run 1G over that hits file (`allowedTools: Read,WebFetch`) so every kept
   entity is actually fetched from its own page, giving `description_source:"verified"`; write
   transient `state/harvest_<topic>_entity_batch.json`; fold its `ledger_patch` into
   `visited_url_ledger.json` using the same `jq -s` technique `run_stage1.sh` already uses.
3. **Merge** — `bash scripts/merge_entity_registry.sh state/harvest_<topic>_entity_batch.json state/entity_registry.json`.
4. **Tally** — count strictly `topic == <topic>` **and** `description_source == "verified"`:
   ```
   jq --arg t "$TOPIC" '[.entities[] | select(.topic==$t and .description_source=="verified")] | length' state/entity_registry.json
   ```
   Print `[harvest][<topic>] loop N: +K new verified → V/<target>`.
5. **Record attempts (no retry loops)** — union every URL sent in this loop's batch (accepted *or*
   rejected by 1G) into `state/harvest_<topic>_attempted.json`. Combined with the ledger's
   `entity_extracted:true` (which 1G sets even for hits it decides aren't entities), this guarantees a
   URL rejected or unverifiable in one loop is never re-selected in a later loop.

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
- No changes are needed to `agents/stage1/1G_entity_extractor.md` or `scripts/merge_entity_registry.sh`.

## Verification (once the script is implemented)

1. `bash -n scripts/harvest_entities.sh` — syntax check; confirm dependency guards match
   `discover.sh`'s `command -v claude`/`command -v jq` checks.
2. Small live loop, e.g. `bash scripts/harvest_entities.sh mcp 12` — confirm transient
   `state/harvest_mcp_*` files appear, the tally increments loop over loop, every new `topic:"mcp"`
   row has `description_source:"verified"` and a non-awesome-list own URL, and the original 17
   entities are untouched.
3. Idempotency — re-run the same command; it should add ~0 new verified entities and exit via the
   "0 new" stop path, proving the ledger + attempted-set + registry dedup actually prevents rework.
4. Failure paths — temporarily break `jq` on PATH or point at a corrupted registry file; confirm the
   script exits non-zero instead of silently continuing.
5. `git status --porcelain state/` shows no `harvest_*` files staged once `.gitignore` is updated.
6. Only after the above passes on a small target, run each topic at `target=100` in turn (`agent`,
   `mcp`, `prompt`, `skill`) — this is the long, WebFetch-heavy phase.

## Recommended run order

`agent` → `mcp` → `prompt` → `skill`. `prompt` currently sits at 0 and has an awesome-list report
(`awesome_prompt.md`) plus a `search_hits_prompt.json` shard already on disk, so it should clear the
bar as reliably as the other three once the harness exists.
