# Schema migration: entity `url` split into `source_url` + `target_url`

**Status:** applied 2026-07-08. One-time `jq` migration over `state/entity_registry.json`,
coordinated with matching changes to `agents/stage1/1G_entity_extractor.md`,
`scripts/harvest_entities.sh`, and `scripts/merge_entity_registry.sh`.

## The problem

Every entity record historically carried a single `url` field. Its meaning was overloaded:
sometimes it pointed at the citing page that surfaced the entity (an awesome-list row, a
search-hit page, a news article), sometimes at the entity's own primary page (repo, docs,
model card, package page, paper, product page). The candidate-batch step in
`scripts/harvest_entities.sh` was instructed to "resolve each seed to the project's OWN
primary URL," so in practice the field drifted toward target-page semantics — but the
original seed/citing URL was discarded at candidate-batch time and never reached 1G at all.
That made the registry's `url` field ambiguous on a per-row basis and prevented either
interpretation from being reliably queryable.

## What was done

The single `url` field was replaced with two fields whose meanings never overlap:

- **`source_url`** — the URL that surfaced the entity (the citing/seed page: an awesome-list
  row, a search-hit page, a news article). Always present.
- **`target_url`** — the entity's own official/primary page (repo, docs page, model card,
  package page, paper, official product page). The literal string `"unknown"` if it cannot
  be confidently resolved — never defaulted to `source_url` to fill the field.

Schema/contract changes that ride along with the split:

- `agents/stage1/1G_entity_extractor.md` — output schema, procedure, and rules updated.
  `description_source:"verified"` now means the description was fetched from `target_url`
  specifically (not from `source_url`, not from the snippet alone). 1G is explicitly told to
  fetch `source_url` and `target_url` independently, and to echo `source_url` in its
  `ledger_patch[].url` so the merge step matches the seeded ledger row.
- `scripts/harvest_entities.sh` — candidate-batch prompt now returns BOTH URLs per
  candidate (Hit shape `{hits:[{source_url,target_url,title,snippet,domain}]}`). The
  attempted-set and the ledger seed key on `source_url` (see the inline note in the script
  for why `source_url` was chosen over `target_url` as the ledger dedup key — short version:
  the ledger has "visited URL" semantics and `source_url` is what was visited; the
  "don't re-catalog the same entity" guarantee is handled by `target_url` exclusion at
  candidate-batch time and by `entity_key` dedup at merge time).
- `scripts/merge_entity_registry.sh` — `entity_key` dedup unchanged (it never keyed on
  `.url`). `source_url` is pass-through on both branches (different citing pages for the
  same entity is corroboration, not a conflict). `target_url` gets two new behaviors: a
  real-vs-real mismatch is logged to `conflicting_evidence_log[]` (same shape as the
  existing `entity_type` conflict log); and an existing `"unknown"` is one-way backfilled
  from an incoming real value, so the registry cannot end up in the impossible state of
  `description_source:"verified"` paired with `target_url:"unknown"`.

## The migration itself

`state/entity_registry.json` had 439 entities, every one with a single `url` field. The
migration was a pure `jq` rename, applied in place after backing up:

1. `mkdir -p state/backups` (already in `.gitignore`).
2. `cp state/entity_registry.json state/backups/entity_registry.json.<UTC-timestamp>.bak`
   (file at `state/backups/entity_registry.json.20260708T093708Z.bak`).
3. `jq '.entities |= map(.source_url = .url | .target_url = "unknown" | del(.url))'`
   validated with `jq empty`, then swapped into place.

Result: every one of the 439 rows now has `source_url` (carrying today's `url` value
verbatim) and `target_url: "unknown"`.

## What was NOT done

- **No backfill of `target_url` from `url`.** Even where today's `url` value is obviously
  the entity's repo (e.g. `https://github.com/vaquarkhan/mcp-test-harness`), the migration
  does not promote it to `target_url`. Per this project's unknown-field rule (see
  `CLAUDE.md`), unknown fields are written as `"unknown"`, never invented — and the
  per-row intent of historical `url` values cannot be reconstructed mechanically. The
  next corroborating 1G run that re-extracts any of these entities will backfill
  `target_url` via the merge script's one-way `"unknown" → real` upgrade path.
- **No changes to `state/ax_case_db.json` or the case-side pipeline.** This is entity-
  registry only.
- **No live `harvest_entities.sh` run as part of this change.** Per the task's static-only
  validation bar: scripts pass `bash -n`, JSON outputs pass `jq empty`, and the merge
  script's three new behaviors (real-vs-real target_url conflict, `"unknown"` backfill,
  unchanged real-vs-real passthrough) were smoke-tested on throwaway files in `/tmp`.
