# Harvest artifacts — run `20260713T063228Z-48898`

Diagnostic / reproducibility artifacts captured from a single successful MCP
entity-harvest loop. **These are NOT production pipeline inputs** — the pipeline's
persistent truth lives in `state/entity_registry.json` and
`state/visited_url_ledger.json` (already committed). Nothing here is read by any
harvest/pipeline script; the files are preserved purely as evidence of *how* the
run succeeded.

## Provenance

| | |
|---|---|
| Source run | `20260713T063228Z-48898` (timing log: `state/logs/harvest_20260713T063228Z-48898.jsonl`) |
| Final commit | `31a96e3` — "Harvest: +40 MCP entities (mcp verified 230->270) — target 250 reached" |
| Tally | **mcp 230 → 270** verified (loop 1 merged +40, 0 dropped; target 250 reached, exit 0) |
| Auth | unauthenticated GitHub access |

## Files

- **`_raw_awesome_mcp_readme.md`** — the raw `github.com/punkpeye/awesome-mcp-servers`
  README, fetched **once** via a single WebFetch. The sole upstream source for the
  batch below.
- **`_build_entity_batch.py`** — the offline script the 1G extractor wrote to parse
  that README into the entity batch. It carries the extracted rows inline
  (name, anchor, target_url, entity_type, description, maintainer, stars, pushed,
  related topics) and emits the `{entities, ledger_patch}` JSON — no live network
  calls.
- **`_entity_batch_mcp_out.json`** — the `{entities, ledger_patch}` output of that
  script: the exact batch that was merged into the registry (the +40 verified mcp
  entities of this run).

## Why this matters (the reproducibility point)

Three earlier resume attempts died at loop 2 because the 1G extractor made **one
live `api.github.com` call per repo** to fetch stargazer counts, exhausting the
unauthenticated GitHub rate limit (60 req/hr). This run instead used a
**"README-once, build-offline"** approach: fetch the awesome-list README a single
time, then assemble the whole batch from that text offline (the `_build_entity_batch.py`
above). That avoided per-repo API hammering entirely, so the run **never hit the
rate limit** and completed unauthenticated in one loop. These artifacts document
that path so it can be reproduced for the remaining topics (agent / prompt / skill).
