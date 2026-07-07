# Known issue: `entity_id` is not globally unique across topics

**Status:** noted, not fixed. Discovered incidentally on 2026-07-07 while reviewing a
before/after diff during the `found_via` / `conflicting_evidence_log` schema-drift
fix (commit `b6ee7a7`). Out of scope for that commit — logged here for follow-up.

## The problem

Two unrelated entities in `state/entity_registry.json` currently share the same
`entity_id`:

- `entity_id: "ent-2026-0001"`, `entity_key: "agent|yolo-auto"` (topic `agent`)
- `entity_id: "ent-2026-0001"`, `entity_key: "mcp|modelcontextprotocol/servers"` (topic `mcp`)

`agents/stage1/1G_entity_extractor.md` shows `entity_id` in its output schema example
(`"entity_id": "ent-2026-0001"`) but never specifies how the ID should be generated in
a way that guarantees uniqueness across runs. In practice, each 1G invocation appears
to invent its own `ent-2026-NNNN` sequence starting fresh — and since `agent`, `mcp`,
`prompt`, and `skill` are extracted via **separate** `claude -p` calls (one per
`harvest_entities.sh` topic invocation, per loop, per attempt), nothing coordinates
numbering across them. Same-topic runs on different days are equally exposed, since
each run's 1G call has no visibility into IDs already used in the registry.

## `entity_key` is the actual dedup key

`scripts/merge_entity_registry.sh` never indexes or deduplicates by `entity_id` — its
`INDEX(...)` / `reduce` logic keys entirely on `entity_key` (`topic|normalized(name)`,
computed by the merge script itself, not trusted from the incoming batch beyond an
optional passthrough). This is why the collision above didn't cause data loss or a
merge conflict: the two entities are correctly treated as distinct records because
their `entity_key`s differ. `entity_id` is carried through as an inert display field,
not a lookup key.

## Downstream reader audit (2026-07-07)

Grepped every script, agent spec, and doc under `scripts/`, `agents/`, `docs/` for
`entity_id` usage:

| File | Uses `entity_id` for... |
|---|---|
| `scripts/merge_entity_registry.sh` | Nothing — dedup is entirely `entity_key`-based. |
| `scripts/harvest_entities.sh` | Nothing — `tally()` filters on `.topic`/`.description_source` only. |
| `scripts/calibrate_seeding.sh` | Nothing — only reads `conflicting_evidence_log`. |
| `scripts/discover.sh`, `scripts/run_stage1.sh` | Nothing — orchestration only, pass `entity_ids` (plural, ledger field) through verbatim. |
| `state/visited_url_ledger.json` (`entity_ids[]` per row) | Stores whichever `entity_id`(s) 1G reported for that URL — a per-URL list, never used as a cross-registry lookup key by any script. |

**Conclusion: nothing currently relies on `entity_id` being globally unique.** The
collision is latent, not actively causing incorrect behavior today. It would become a
real bug if any future feature tried to "look up an entity by `entity_id`" against the
full registry (e.g., a `jq` query keyed on `entity_id`, or a UI/report that treats it
as a primary key) — that lookup would silently return the wrong entity, or both,
depending on how it's written.

## Possible fixes (not evaluated in depth, not applied)

- Make `entity_id` topic-qualified at generation time (e.g., `ent-agent-2026-0001`),
  mirroring how `entity_key` already is.
- Have `merge_entity_registry.sh` assign `entity_id` itself at merge time (like it
  already does for `entity_key`), instead of trusting whatever 1G invented, using a
  counter seeded from the current max ID in the master registry.
- Leave `entity_id` as a non-unique display label and document it explicitly as such,
  if no future use case actually needs global uniqueness.

Any of these would need to reconcile with the **439 already-persisted** `entity_id`
values (a migration decision), and would touch at minimum
`agents/stage1/1G_entity_extractor.md` (schema/generation contract) and
`scripts/merge_entity_registry.sh` (merge logic) — same shape of change as the
`found_via`/`conflicting_evidence_log` fix, but not undertaken here.
