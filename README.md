# cpg-research-playbook

Archiving multiple strategies and memory systems used for searching in the Cherry seeding stage of the CPG (Cherry Pickers Guild) research pipeline.

## Pipeline overview

The playbook discovers credible AI-transformation cases via a 4-stage sub-pipeline (Stage 1), then validates, selects, and builds lecture-ready slide decks (Stages 2–4).

```
seed topics → 1A Strategy Builder → 1B Crawl Executor → 1C Case Extractor → ax_case_db.json
                     ↑                                                │
                     └────────── 1D Refresh Scheduler (closed cycle) ──┘
```

Persistent state lives in `state/`; per-run artifacts land in `runs/<timestamp>/`. Config in `pipeline.config.sh`; per-agent specs in `agents/stage*/`.

## Key files

### Config
- `pipeline.config.sh` — audience, date windows, model, stage entry point, seed topics.
- `config/source_registry_template.json` — per-platform follow-list schema (LinkedIn, X, Substack, Reddit, etc.).

### Stage 1 (Case Discovery)
- `agents/stage1/00_discovery_overview.md` — how 1A/1B/1C/1D cooperate.
- `agents/stage1/1A_strategy_builder.md` — query expansion spec + Search Strategy DB schema.
- `run_stage1.sh` — runs the discovery sub-pipeline.

### State (persists across runs)
- `state/search_strategy_db.json` — every query, last run, next refresh due, yield. **Read this to see what's being searched.**
- `state/search_hits.json` — Stage 1B output: URL + title + snippet for every search hit (510 as of 2026-06-28). Pages are NOT crawled at this stage — anti-crawl discipline.
- `state/search_hits_{agent,mcp,prompt,skills,ax}.json` — per-topic shards of `search_hits.json` (intermediate artifacts from the 5 parallel search subagents).
- `state/source_registry.json` — curated per-platform follow-lists (LinkedIn / X / Substack / Reddit / Medium / etc.).
- `state/visited_url_ledger.json` — every URL ever fetched; enforces fetch-once on `news_url`s.

### Reports
- `reports/` — one markdown file per pipeline iteration. Read these to understand what each run did, what issues hit, and what changed. Start with `reports/2026-06-28_stage1B_search_iteration_001.md` for the most recent run.

## Running the pipeline

```bash
# Edit pipeline.config.sh first (audience, model, dates), then:
bash run_stage1.sh     # one discovery pass: 1A → 1B → 1C
```

## Anti-crawl discipline

Two URL kinds matter (rule 5 of the discovery spec):
- **source_url** — broad page (blog index, subreddit, Substack home). Re-crawled on refresh to find new child articles.
- **news_url** — specific article. Fetched once, then never again — refetching is what trips anti-bot systems.

`state/visited_url_ledger.json` enforces this. Stage 1B must normalize URLs (lowercase host, strip `utm_*`/fragments/trailing slash) before the ledger check so trivially-different URLs aren't re-fetched.

## Recent activity

- **2026-06-28** — Stage 1B search-only run: 64 queries → 510 hits. See `reports/2026-06-28_stage1B_search_iteration_001.md`.
- **2026-06-26** — Stage 1A iteration 001: populated `search_strategy_db.json` from empty seed. See `reports/2026-06-26_stage1A_iteration_001.md`.
