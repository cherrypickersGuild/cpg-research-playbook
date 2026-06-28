# Stage 1A — Strategy Builder iteration 001 (2026-06-26)

## Summary
Populated `state/search_strategy_db.json` from its empty seed (`{"topics":[],"refresh_days":90,"strategies":[]}`) into a working strategy DB with **64 query rows** spanning all five seed topics and all five expansion axes. This is the first 1A pass; nothing has been crawled yet.

## Inputs
- **Spec followed:** `agents/stage1/1A_strategy_builder.md` (no schema changes — used the schema exactly as written).
- **Seed topics:** `agent`, `mcp`, `prompt`, `skills`, `AX cases` (from `pipeline.config.sh:SEED_TOPICS`).
- **Refresh window:** `REFRESH_DAYS=90` → all rows stamped `next_refresh_due = 2026-09-24`.
- **Run date:** 2026-06-26.

## Output
- **File:** `state/search_strategy_db.json` (was 48 bytes empty seed → 64 populated rows).
- **No deletions:** nothing existed to clobber; every row is new.
- **All rows** carry the full schema: `strategy_id, topic, query, query_type, target_platforms, seed_source_urls, status, created_at, last_run_at, last_updated_at, next_refresh_due, run_count, yield_count`.
- `last_run_at = null`, `run_count = 0`, `yield_count = 0` on every row (no executions yet — that's 1B's job).
- `status = "active"` on every row.

## Coverage matrix (rows per topic × axis)

| topic        | workflow_metric | entity | platform_scoped | failure | broad_seed | total |
|--------------|----------------:|-------:|----------------:|--------:|-----------:|------:|
| agent        | 4               | 4      | 3               | 2       | 2          | 15    |
| mcp          | 3               | 3      | 2               | 2       | 2          | 12    |
| prompt       | 3               | 2      | 3               | 2       | 2          | 12    |
| skills       | 3               | 2      | 2               | 2       | 2          | 11    |
| AX cases     | 4               | 4      | 2               | 2       | 2          | 14    |
| **total**    | **17**          | **15** | **12**          | **10**  | **10**     | **64**|

## Platform coverage
- **web** (general search): every workflow_metric + entity row.
- **substack / reddit / medium**: scoped `site:` queries — one or two per relevant topic.
- **failure** rows: dual-targeted at `["web","reddit"]` since skeptical discussion concentrates on Reddit.
- **broad_seed** rows: each carries a concrete `seed_source_urls` URL (Anthropic news, LangChain blog, MCP spec site, Prompt Engineering Guide, OpenAI blog, Claude docs, HBR, McKinsey QuantumBlack).

## Notable choices
- **Klarna, JPMorgan LLM Suite, Microsoft/GitHub Copilot** seeded under `AX cases` as named entities — these are the highest-signal public enterprise AI rollouts to date.
- **Salesforce Agentforce, LangChain, CrewAI, AutoGen** seeded under `agent` — covers vendor-led and framework-led agentic stories.
- **Cursor, Replit** seeded under `mcp` — the IDEs that have shipped MCP integrations.
- `broad_seed` rows are deliberately *broad indexes*, not articles — 1B is expected to crawl them for new child `news_url`s.
- No query exceeded ~6 signal words (per spec).
- All queries are de-duplicated within the DB (64 unique `strategy_id`s, 64 unique query strings).

## Schema observations (deferred — not applied this iteration)
Per the pre-iteration analysis, the schema in `1A_strategy_builder.md` has known gaps. These were **not** applied because the instruction was to follow the spec as written. Flagged for a future iteration:
1. No `schema_version` / `_meta` block at the DB top level.
2. No `query_hash` for mechanical dedup (currently relies on the agent normalizing).
3. No `last_yield_at` / `consecutive_null_yield` for smarter pruning.
4. No per-platform `yield_by_platform` breakdown.
5. No `language` / `region` axis (Korean-language results are not specifically targeted).
6. Empty seed ships no exemplar rows for the next agent to mimic.
7. No JSON Schema file for validation in `run_stage1.sh`.

If you want any of these applied, say the word and I'll open a second iteration that updates `1A_strategy_builder.md` + `run_stage1.sh` + adds `config/search_strategy_db.schema.json`.

## Verification
- `jq -e` parses the file cleanly.
- All 64 `strategy_id`s unique.
- All `next_refresh_due` values = `2026-09-24`.
- All `status` values = `active`.

## Next stage
The DB is ready for **1B · Crawl Executor** (`run_stage1.sh` continues into 1B/1C on the next `bash run_stage1.sh`). 1B will:
- Read these 64 strategies + `state/source_registry.json`.
- Execute searches against `target_platforms`, dedup via `state/visited_url_ledger.json`.
- Emit `hits.json` with `{source_url, news_url, ...}` for 1C to extract AX cases from.

## Files changed this iteration
- `state/search_strategy_db.json` — populated (48 bytes → 64 rows).
- `reports/2026-06-26_stage1A_iteration_001.md` — this report (new).
