# Stage 1F — News Monitor

## Mission
Watch fast-moving news sources for **every active topic/category** on a much shorter cycle than 1D's
90-day evergreen refresh, and hand fresh hits straight to 1C. This is the fast lane for the `tier:
"news"` sources in the Source/Community Registries — RSS feeds, HN "new", product-launch trackers,
company-blog latest-posts pages — where a 90-day-stale check would miss the news entirely.

## Inputs
- `state/source_registry.json` and the Community Registry, filtered to rows where `tier == "news"`.
- `state/visited_url_ledger.json` (same dedup discipline as 1B — never refetch a `news_url` already in
  it).
- `SEED_TOPICS` + any `active` rows in `state/category_registry.json` (this stage covers *all* active
  topics/categories in one pass, not one topic at a time).
- `NEWS_FRESHNESS_WINDOW_DAYS` (default 7).

## Procedure
1. Gather targets: every registry row with `tier: "news"` and `follow: true` (or `status: active` for
   community rows), across every active topic/category.
2. Normalize URLs exactly as 1B does (lowercase host, strip `utm_*`/fragments/trailing slash) before
   the ledger check.
3. **Dedup gate**: skip any `news_url` already in the ledger — identical rule to 1B, no exceptions.
4. **Freshness gate**: only emit a hit if its published/posted date is within `NEWS_FRESHNESS_WINDOW_DAYS`
   of today. Older items on a news-tier source are not this stage's job — they either already came
   through on a prior run, or belong to the evergreen 1B/1D cycle if the source is misclassified as
   `news` when it's really a slow-moving index (flag that mismatch instead of silently skipping).
5. Emit hits in the **same Hit schema 1B uses** (see `1B_crawl_executor.md`) so 1C needs no changes;
   set `platform` accurately and `found_via.strategy_id: null` (news hits aren't tied to a query
   strategy, just a registry row) with `found_via.registry_id` set instead.
6. **Category-discovery side effect**: if you notice the same non-covered term recurring across ≥3 news
   hits during this pass, don't silently drop it — append it to a `category_signals[]` array in your
   output (not to `category_registry.json` directly; 1E owns that file and will pick these up).
7. Append every fetched URL to the ledger immediately, exactly as 1B does, so a crash mid-run can't
   cause a refetch on the next invocation.
8. Anti-crawl discipline is identical to 1B: respect per-domain rate limits, back off on 429/403, route
   `browser_use_only` registry rows to the browser-agent path.

## Output — same Hit schema as 1B, plus a category-signal side-channel
```json
{
  "hits": [
    { "hit_id": "hit-2026-0500", "platform": "custom", "source_url": "https://example.com/blog",
      "news_url": "https://example.com/blog/new-agent-framework-launch",
      "title": "...", "author": "unknown", "published_date": "2026-07-05",
      "crawled_at": "2026-07-06T08:00:00Z",
      "found_via": { "strategy_id": null, "registry_id": "custom-0007" },
      "content_hash": "sha1:...", "browser_use_only": false, "status": "new" }
  ],
  "ledger_updates": [ "...same shape 1B emits..." ],
  "category_signals": [
    { "term": "agent memory", "count": 3, "sample_hit_ids": ["hit-2026-0500", "hit-2026-0501", "hit-2026-0502"] }
  ],
  "freshness_window_days": 7,
  "throttled_domains": []
}
```

## Rules
- Never widen the freshness window on your own initiative — a stale-feeling news feed is a signal to
  flag (possible misclassified `tier`), not a reason to fetch further back.
- Do not extract cases here — that's still 1C's job; this stage only produces hits.
- Do not touch `category_registry.json` — only `category_signals[]` in your own output; 1E is the only
  stage that writes candidates.
- Return JSON only. No prose, no fences.
