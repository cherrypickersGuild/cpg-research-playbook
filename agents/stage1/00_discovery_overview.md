# Stage 1 — Case Discovery sub-pipeline (revised case finder)

The single case finder is replaced by **four cooperating agents**, **three persistent stores**, and a **closed refresh cycle**. Normal runs are linear (1A → 1B → 1C). Agent 1D closes the loop on a schedule: when a keyword goes stale it reopens 1A and re-runs only what's needed, so the corpus stays current without re-crawling everything.

```
        seed topics  (agent, mcp, prompt, skills, AX cases, ...)
                         │
   ┌──────────────── 1A · Strategy Builder ─────────────────┐
   │  query expansion → SEARCH STRATEGY DB                   │
   │  (topic, query, target platforms, seed source_urls,     │
   │   last_run, next_refresh_due)                           │
   └───────────────────────────┬────────────────────────────┘
                               ▼
   ┌──────────── 1B · Crawl Executor ───────────┐   reads ► SOURCE REGISTRY
   │  runs queries + pulls registry sources       │           (per-platform
   │  DEDUP via VISITED-URL LEDGER  (rule 2)       │            follow-lists)
   │  emits HITS {source_url, news_url, ...}       │
   └───────────────────────────┬─────────────────┘
                               ▼
   ┌──────────── 1C · Case Extractor ───────────┐
   │  new hits → AX cases (existing case schema)  │ ► ax_case_db.json → Stage 2
   │  marks no-case hits so they're never refetched│
   └──────────────────────────────────────────────┘

   1D · Refresh Scheduler   (closed cycle — conditional)
     for every strategy where age(last_updated) ≥ REFRESH_DAYS (default 90):
        reopen 1A (update queries) → 1B → 1C → stamp last_updated, set next_refresh_due
     otherwise: idle. This is the "closed cycle in some situation."
```

## Persistent stores (live in `state/`, survive across runs)
Unlike per-run outputs (which land in `runs/<ts>/outputs/`), these accumulate:

- **Search Strategy DB** (`state/search_strategy_db.json`) — every query, the topic it came from, when it last ran, when it's next due, and its yield (so low-yield queries can be pruned).
- **Visited-URL Ledger** (`state/visited_url_ledger.json`) — every URL ever fetched. This is what enforces rule 2: a `news_url` already in the ledger is **never fetched again**.
- **Source Registry** (`state/source_registry.json`) — the curated per-platform follow-lists (LinkedIn, X/Twitter, YouTube, Threads, Substack, email, Reddit, Medium, custom crawl).

## Two URL kinds (rule 5)
- **source_url** — a *broad* page: a blog index, a creator's channel/profile, a subreddit, a Substack home. **Re-crawled** on refresh to discover new articles.
- **news_url** — a *specific* article/post/video. **Fetched once, then never again** — its content is stable, and refetching is exactly what trips anti-bot systems.

The ledger therefore treats the two differently: `news_url` → fetch-once; `source_url` → may be revisited on the refresh cycle (and even then, only its *new* child `news_url`s are fetched).

## Anti-crawl discipline (rule 2, expanded)
1B must: normalize URLs before the ledger check (lowercase host, strip `utm_*`/fragments/trailing slash) so trivially-different URLs aren't re-fetched; respect per-domain rate limits and back off on 429/403; and route any registry entry marked `browser_use_only = true` (e.g. LinkedIn, X) to a browser-agent path rather than plain fetch, since those platforms block headless crawling.

## Where this sits in the whole pipeline
1C's output is the same `ax_case_db.json` the Validator (Stage 2) already consumes — so Stages 2–4 are unchanged. Discovered `news_url`s become each case's `source[].url`, which the Validator then re-checks for accessibility; `browser_use_only` flows through so the Validator knows to verify those via browser, not fetch.

## Run entry points
- `bash run_stage1.sh` — one discovery pass (1A if strategies missing/stale → 1B → 1C), writes this run's `01_case_db.json`.
- `bash refresh.sh` — the closed cycle (1D): refreshes only stale keywords. Schedule it (cron / Task Scheduler) every few days; it does nothing until something crosses `REFRESH_DAYS`.
