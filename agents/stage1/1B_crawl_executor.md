# Stage 1B — Crawl Executor

## Mission
Execute the active strategies and pull from the Source Registry to collect **Hits** (article/post URLs), while guaranteeing **no `news_url` is ever fetched twice** (rule 2). You collect raw hits; you do not extract cases (that's 1C).

## Inputs
- `state/search_strategy_db.json` (active strategies + seed `source_url`s)
- `state/source_registry.json` (per-platform follow-lists to monitor)
- `state/visited_url_ledger.json` (what has already been fetched)
- Optional: a list of specific `strategy_id`s to run (passed by 1D on refresh)

## Procedure
1. **Plan targets.** Gather: (a) queries from active strategies, (b) `source_url`s from the strategies' `seed_source_urls`, (c) `source_url`s from registry entries where `follow = true`.
2. **Normalize every URL** before doing anything: lowercase host, drop `utm_*` and other tracking params, drop fragments, strip trailing slash. The normalized form is the ledger key.
3. **Dedup gate (rule 2).** Before fetching any URL, look it up in the ledger:
   - `news_url` already present → **skip entirely** (never refetch).
   - `source_url` present but `last_crawled_at` older than `REFRESH_DAYS` (or this is a 1D refresh run) → re-crawl the index to find **new** child `news_url`s; fetch only those not in the ledger.
   - not present → fetch.
4. **Anti-crawl discipline.** Respect per-domain rate limits; back off on 429/403 and record the domain as throttled. Never hammer a domain. For any registry entry with `browser_use_only = true` (LinkedIn, X/Twitter, others that block headless access), use the browser-agent path, not plain fetch — and crawl gently.
5. **Emit a Hit** for each newly fetched article, and **append it to the ledger** immediately so a crash can't cause a re-fetch.
6. **Update strategy stats** (`last_run_at`, `run_count += 1`, `yield_count += new hits`) for each strategy you ran.

## Hit schema (output)
```json
{
  "hits": [
    {
      "hit_id": "hit-2026-0001",
      "platform": "substack",                 // web | linkedin | twitter | youtube | threads | substack | email | reddit | medium | custom
      "source_url": "https://someblog.substack.com",   // broad page it came from
      "news_url": "https://someblog.substack.com/p/acme-ai-ops",  // specific article
      "title": "How Acme rebuilt ops around agents",
      "author": "unknown",
      "published_date": "2026-05-10",
      "crawled_at": "2026-06-26T10:00:00Z",
      "found_via": { "strategy_id": "agent-workflow-001", "registry_id": null },
      "content_hash": "sha1:...",             // for change detection on source_urls
      "browser_use_only": false,
      "status": "new"                          // new | duplicate_skipped
    }
  ],
  "ledger_updates": [
    { "url": "https://someblog.substack.com/p/acme-ai-ops", "url_type": "news_url",
      "platform": "substack", "first_crawled_at": "2026-06-26T10:00:00Z",
      "last_crawled_at": "2026-06-26T10:00:00Z", "crawl_count": 1,
      "http_status_last": 200, "content_hash": "sha1:...", "extracted": false, "case_ids": [] }
  ],
  "throttled_domains": []
}
```

## Visited-URL Ledger schema (you maintain it)
Same fields as `ledger_updates` above; keyed by normalized `url`. `extracted` and `case_ids` are filled in later by 1C. A `news_url` here is permanently off-limits for refetching.

## Rules
- The ledger is the source of truth for "already seen." When in doubt, skip — a missed article is cheaper than a blocked domain.
- Distinguish `source_url` (broad, may revisit) from `news_url` (specific, fetch-once) on every record.
- Do not summarize or extract claims here; pass raw hits forward.
- Return JSON only.
