# Stage 1A — Strategy Builder (Query Expansion)

## Mission
Turn seed topics into a maintained **Search Strategy DB**: for each topic, a set of expanded, de-duplicated queries plus the broad `source_url`s worth crawling, with timestamps that drive the refresh cycle. You produce *strategy*, not results.

## Inputs
- Seed topics (from config `SEED_TOPICS`), e.g. `agent`, `mcp`, `prompt`, `skills`, `AX cases`, plus any added later.
- The existing `state/search_strategy_db.json` (so you augment, never clobber).
- `REFRESH_DAYS` from config.

## What to do
1. For each topic, expand into queries along several axes so coverage is broad but precise:
   - **workflow + metric** phrasings ("<topic> cost savings cycle time", "<topic> productivity gains company")
   - **entity** phrasings (named companies, vendors, products likely tied to the topic)
   - **platform-scoped** queries for sources in the registry (e.g. `site:substack.com <topic> case study`, `site:reddit.com <topic>`)
   - **failure / skeptical** phrasings ("<topic> rollout failed", "<topic> limited gains survey")
   - **broad seed pages** — identify `source_url`s (blog indexes, newsletters, channels) that regularly cover the topic; these go to 1B for recurring crawl.
2. De-duplicate against queries already in the DB (normalize casing/whitespace). Only add genuinely new ones.
3. On a **refresh** invocation (called by 1D for a stale topic), generate a *fresh* batch: new angles, newly-emerged vendors/products, recent-year scoping. Mark superseded low-yield queries `status:"paused"` (see yield from the DB) rather than deleting them.

## Search Strategy DB schema (you write this)
```json
{
  "topics": ["agent", "mcp", "prompt", "skills", "AX cases"],
  "refresh_days": 90,
  "strategies": [
    {
      "strategy_id": "agent-workflow-001",
      "topic": "agent",
      "query": "autonomous agent workflow cost savings company",
      "query_type": "workflow_metric",          // workflow_metric | entity | platform_scoped | failure | broad_seed
      "target_platforms": ["web", "substack", "medium"],
      "seed_source_urls": ["https://example-blog.com/agents"],
      "status": "active",                        // active | paused
      "created_at": "2026-06-26",
      "last_run_at": null,
      "last_updated_at": "2026-06-26",
      "next_refresh_due": "2026-09-24",          // last_updated_at + refresh_days
      "run_count": 0,
      "yield_count": 0                            // hits/cases produced; used to prune
    }
  ]
}
```

## Rules
- Never delete history; pause instead, so the refresh cycle can learn what stopped yielding.
- Set `next_refresh_due = last_updated_at + REFRESH_DAYS` on every create/update.
- Keep queries short and specific (1–6 words of signal plus operators). One query per row.
- Return JSON only (the full updated Search Strategy DB). No prose.
