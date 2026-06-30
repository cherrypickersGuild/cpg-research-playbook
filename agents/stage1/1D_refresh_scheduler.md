# Stage 1D — Refresh Scheduler (the closed cycle)

## Mission
Keep the corpus current by re-searching **only stale keywords**, on a cycle. This is the "closed cycle in some situation": the situation is staleness ≥ `REFRESH_DAYS`. Nothing happens until a strategy crosses that line.

## Inputs
- `state/search_strategy_db.json`
- `REFRESH_DAYS` (default 90, configurable)
- today's date

## Procedure
1. Compute `age = today − last_updated_at` for every `active` strategy.
2. **Select stale set:** strategies where `age ≥ REFRESH_DAYS` (or `next_refresh_due ≤ today`).
3. For the stale set, trigger the closed loop:
   - Call **1A in refresh mode** for the affected topics → new/updated queries, with low-yield ones paused.
   - Call **1B** restricted to those `strategy_id`s → fetches only new `news_url`s (ledger still blocks everything already seen).
   - Call **1C** on the new hits → new cases merged into the corpus.
4. **Stamp:** for every refreshed strategy set `last_updated_at = today`, `next_refresh_due = today + REFRESH_DAYS`.
5. **Prune:** any strategy with `run_count ≥ 3` and `yield_count = 0` → `status: "paused"` (stops wasting crawl budget; can be revived manually).

## Output
```json
{
  "refresh_run": { "ran_at": "datetime", "refresh_days": 90 },
  "refreshed_strategy_ids": ["agent-workflow-001"],
  "paused_strategy_ids": [],
  "skipped_fresh_count": 0,
  "new_cases": 0,
  "next_due": [ { "strategy_id": "agent-workflow-001", "next_refresh_due": "2026-09-24" } ]
}
```

## Rules
- Touch only the stale set — never re-crawl fresh keywords (that's the whole point: bounded, polite refresh).
- The Visited-URL Ledger is never reset; refresh discovers *new* URLs only.
- `REFRESH_DAYS` is read from config so it can be changed without editing this agent.
- Return JSON only.
