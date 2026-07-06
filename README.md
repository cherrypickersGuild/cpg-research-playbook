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
- `agents/stage1/1E_category_discovery.md` / `1F_news_monitor.md` / `1G_entity_extractor.md` — slow-cadence new-topic discovery, fast-cadence news crawling, and 1C's sibling extractor for agent/mcp/prompt/skill entities; see `SEEDING_STRATEGY.md` for the full plan.
- `run_stage1.sh` — runs the discovery sub-pipeline.

### Seeding strategy
- `SEEDING_STRATEGY.md` — the strategy, schedule, and workflow for growing seed topics/categories, sources, and news coverage over time, and for merging newly discovered cases into a persistent `state/ax_case_db.json` instead of leaving them as disconnected per-run snapshots.
- `discover.sh` — runs 1F News Monitor and/or 1E Category Discovery (`--news-only` / `--category-only` / default both); mirrors `refresh.sh`.
- `merge_case_db.sh` — folds a batch of extracted cases into `state/ax_case_db.json`, deduped by `case_key`, raising `corroboration_count` on repeat matches and logging (never silently resolving) conflicting facts.
- `merge_entity_registry.sh` — same pattern for `state/entity_registry.json`: structured agent/mcp/prompt/skill records extracted by 1G, deduped by `entity_key`, upgrading `description_source` on corroboration rather than downgrading it.
- `calibrate_seeding.sh` — seeding-health metrics read from `state/` directly: yield by topic, corroboration distribution, category discovery funnel, news-vs-evergreen yield, staleness.
- `schedule/crontab.txt` / `schedule/register_windows_tasks.ps1` — install the six-tier schedule from `SEEDING_STRATEGY.md` §5 on Linux/macOS/WSL or Windows Task Scheduler.

### State (persists across runs)
- `state/search_strategy_db.json` — every query, last run, next refresh due, yield. **Read this to see what's being searched.**
- `state/search_hits.json` — Stage 1B output: URL + title + snippet for every search hit (510 as of 2026-06-28). Pages are NOT crawled at this stage — anti-crawl discipline.
- `state/search_hits_{agent,mcp,prompt,skills,ax}.json` — per-topic shards of `search_hits.json` (intermediate artifacts from the 5 parallel search subagents).
- `state/source_registry.json` — curated per-platform follow-lists (LinkedIn / X / Substack / Reddit / Medium / etc.).
- `state/visited_url_ledger.json` — every URL ever fetched; enforces fetch-once on `news_url`s.

### Interactive subagents (`.claude/agents/`)
- `.claude/agents/awesome-list-crawler.md` — on-demand subagent (invoke directly, not via the bash pipeline) that, given one seed topic (`mcp`, `agent`, `prompt`, `skill`, `ax-cases`), resolves that topic's GitHub "awesome-`<topic>`" list(s), fetches every linked entry's own subpage to verify and describe it, and writes a report to `reports/awesome-lists/`.

### Reports
- `reports/` — one markdown file per pipeline iteration. Read these to understand what each run did, what issues hit, and what changed. Start with `reports/2026-06-28_stage1B_search_iteration_001.md` for the most recent run.
- `reports/awesome-lists/awesome_<topic>.md` — one per seed topic, produced by the `awesome-list-crawler` subagent; each catalogs and verifies the entries in that topic's GitHub awesome-list(s) rather than just relisting the source blurb.

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

- **2026-07-06** — Added Stage 1G Entity Extractor (`agents/stage1/1G_entity_extractor.md`) — 1C's sibling: same hits, independently extracts structured records for specific agent/mcp/prompt/skill things (not AX cases) into the new `state/entity_registry.json`, deduped by `entity_key` via `merge_entity_registry.sh`. Wired into both `run_stage1.sh` (after 1C) and `discover.sh`'s news path, and added an entity-registry section to `calibrate_seeding.sh`. This closes the gap where a hit about, say, a specific MCP server or Claude Skill had no path to becoming a structured record — previously only `state/search_hits_skills.json`-style raw snippets existed, explicitly marked "use as input for deeper crawl/extraction" but never actually consumed.
- **2026-07-06** — Built out the full seeding strategy from `SEEDING_STRATEGY.md`: `discover.sh` (1F news + 1E category orchestration), `merge_case_db.sh` (case_key dedup/corroboration merge into the new persistent `state/ax_case_db.json`), `calibrate_seeding.sh` (seeding-health metrics), and `schedule/` (cron + Windows Task Scheduler wiring). Wired `tier`/`check_frequency_days` into the live source/community registries and made 1B skip `tier:"news"` rows so 1B and 1F never double-crawl. All scripts syntax-checked, the merge logic tested end-to-end (including a genuine conflict case), and the Windows script parse-verified after fixing an em-dash encoding issue.
- **2026-07-06** — Added `SEEDING_STRATEGY.md` (strategy/schedule/workflow for growing seed topics, sources, and news coverage, and for merging discovered cases into a persistent master database) plus two new stage specs: `agents/stage1/1E_category_discovery.md` and `agents/stage1/1F_news_monitor.md`.
- **2026-07-03** — Added `mdskills.ai` (a non-GitHub AI-agent-skills marketplace) to `reports/awesome-lists/awesome_skill.md`, deep-verified across its own `/skills` listing and `/docs/*` subpages. Registered it as a `skill`-topic source in both the `awesome-list-crawler` seed table and the Community Registry (new "Marketplaces" category, since it isn't a GitHub repo).
- **2026-07-03** — Added the `awesome-list-crawler` subagent and ran it for all five seed topics, producing `reports/awesome-lists/awesome_{agent,mcp,prompt,skill,ax-cases}.md`. Updated the Community Registry's GitHub rows in `agents/stage1/1A_community_strategy_builder.md`: added seeds for `skill` (previously unregistered), and swapped the `prompt`/`AX cases` seeds for lists that are actually curated link-out lists (the prior seeds turned out to be prompt/tutorial content, not link lists).
- **2026-06-28** — Stage 1B search-only run: 64 queries → 510 hits. See `reports/2026-06-28_stage1B_search_iteration_001.md`.
- **2026-06-26** — Stage 1A iteration 001: populated `search_strategy_db.json` from empty seed. See `reports/2026-06-26_stage1A_iteration_001.md`.
