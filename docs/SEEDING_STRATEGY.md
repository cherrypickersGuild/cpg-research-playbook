# Seeding Strategy — growing the corpus and the topic list over time

This document is the operating plan for keeping the pipeline's inputs (seed topics, sources, news)
and its output (the case corpus) growing and current, without re-crawling everything or drowning in
noise. It extends the existing Stage 1 sub-pipeline (`agents/stage1/00_discovery_overview.md`); read
that first if you haven't.

## 0. The gap this closes

Today the pipeline has three persistent stores in `state/` — the Search Strategy DB, the Visited-URL
Ledger, the Source/Community Registries — but **no persistent case database**. Every run's cases land
in `runs/<timestamp>/outputs/01_case_db.json` and stop there; `SETUP.md`'s troubleshooting section
literally says to *manually concatenate* `cases[]` arrays across batches. That's fine for a one-shot
deck build, but it means there is no real answer to "where do newly discovered cases accumulate,"
which is what this doc is about.

It also has no mechanism for two things you specifically asked about:
- **New categories.** `SEED_TOPICS` (`agent, mcp, prompt, skills, AX cases`) is a fixed list set once
  in `pipeline.config.sh`. Nothing proposes topic #6.
- **News.** Every source is crawled on the same 90-day `REFRESH_DAYS` cycle (`1D_refresh_scheduler.md`).
  That cycle is right for evergreen pages (awesome-lists, guides) but wrong for fast-moving news — by
  the time a 90-day-stale query re-runs, a news item is long buried.

Three additions close these gaps: a **master case database**, a **category registry + discovery
stage (1E)**, and a **news tier + monitor stage (1F)**. All three reuse the existing patterns
(status lifecycles, ledgers, pause-don't-delete, human review gates) rather than inventing new ones.

## 1. Three discovery layers

| Layer | Question it answers | Cadence | Existing mechanism | Gap / addition |
|---|---|---|---|---|
| **Topics/categories** | *What subjects should we even be searching for?* | Slow (monthly/quarterly) | none | **new: 1E Category Discovery + `state/category_registry.json`** |
| **Sources** (communities, awesome-lists, follow-lists) | *Which pages/accounts reliably cover a topic?* | Medium (90-day refresh; new-source discovery slower) | `1A_community_strategy_builder.md` MODE B, `source_registry.json` | none — already spec'd; this doc just schedules it |
| **News/hits** (individual articles/posts) | *What just happened, right now, on a topic we already track?* | Fast (daily / every 6-12h) | `1B_crawl_executor.md` (but on the same 90-day cycle as sources) | **new: 1F News Monitor, a `tier: "news"` fast lane** |

The case-extraction and validation machinery (1C, Stage 2-4) is unchanged — every layer still
funnels through the same "named company, concrete workflow, measurable KPI" bar. These additions
only change *what gets searched and how often*, not the inclusion bar for a case.

## 2. New/extended persistent stores

### 2.1 `state/ax_case_db.json` — the master case database (new)

The actual fix for "how do newly discovered cases get into the database." Every discovery run (initial,
1D refresh, or 1F news) still emits its own per-run case batch exactly as today — but that batch is now
**merged** into this cumulative file instead of being left as an orphaned snapshot.

```json
{
  "_about": "Cumulative case corpus. Every discovery run merges its new/updated cases in here by case_key. This is the one file Stage 2 (Validator) should be pointed at for a full-corpus pass, not a single run's 01_case_db.json.",
  "schema_version": 1,
  "last_merged_at": "2026-07-06",
  "cases": [
    {
      "case_id": "case-0001",
      "case_key": "acme-corp|agentic-support-triage|2026-q1",
      "...": "...full existing case schema (company, industry, function, workflows, kpi[], ax_pattern, etc.) unchanged...",
      "source": [ { "url": "...", "...": "..." } ],
      "discovery": {
        "first_seen_at": "2026-06-28",
        "last_corroborated_at": "2026-07-06",
        "corroboration_count": 2,
        "found_via": [
          { "hit_id": "hit-2026-0031", "run": "20260628T...Z" },
          { "hit_id": "hit-2026-0190", "run": "1F-news-20260706" }
        ]
      }
    }
  ]
}
```

**`case_key`** = normalized `company | ax_pattern (or one-line workflow) | transformation_period` — the
same identity 1C's existing rule ("one case per company × workflow × period; merge multiple `news_url`s
... raise `corroboration_count`") already defines. This just makes that rule apply *across runs*, not
only within one.

**Merge rule** (runs after every 1C invocation, whether from the initial pass, 1D, or 1F):
1. Compute `case_key` for each new case.
2. No match in `ax_case_db.json` → append as new, `corroboration_count: 1`.
3. Match found → append the new `source[]` entries, `corroboration_count += 1`, `last_corroborated_at = today`, keep the **higher** `confidence`, and **never silently overwrite** a KPI/date/fact that conflicts — if the new hit disagrees with the stored one (different KPI number, different date), add a `conflicting_evidence` note on the case instead of picking a winner. A human resolves conflicts; the pipeline never guesses.
4. Never delete a case here — corpus pruning (if ever needed) is a Stage 2/3 concern, not a merge-time one.

Mechanically this is the same shape as the ledger merge `run_stage1.sh` already does with `jq` (lines
36-39: fold `ledger_updates` into `visited_url_ledger.json`, `unique_by(.url)`) — this is the same
technique, keyed by `case_key` instead of `url`, with the added conflict check.

### 2.2 `state/category_registry.json` — topic lifecycle (new)

```json
{
  "_about": "Lifecycle for seed topics themselves — separate from cherry_category (content-type tags in source_registry_template.json) and from per-topic source lists (community_strategy_db.json). Read/written by 1E. On promotion to active, the category_id is appended to SEED_TOPICS and 1A/1A-community pick it up on their next run.",
  "categories": [
    {
      "category_id": "agent-memory",
      "label": "Agent memory / long-context systems",
      "status": "candidate",
      "first_observed_at": "2026-07-06",
      "promoted_at": null,
      "evidence": [
        { "type": "recurring_term", "source": "search_hits.json", "count": 14, "sample_hit_ids": ["hit-2026-0210", "hit-2026-0233"] },
        { "type": "discovery_candidate", "source": "niche_strategy_db.json#discovery_candidates" }
      ],
      "reviewer_notes": "",
      "rejected_reason": null
    }
  ]
}
```

`status`: `candidate` (1E proposed it, unreviewed) → `active` (human approved; now a real seed topic) →
`paused` (was active, yield dried up) → `rejected` (reviewed and declined — kept, never deleted, so 1E
doesn't re-propose it every cycle).

### 2.3 Extend `source_registry.json` targets[] and the Community Registry with a `tier` field

Add two fields to every row (both the JSON `targets[]` schema in `config/source_registry_template.json`
and the markdown Community Registry table in `1A_community_strategy_builder.md`):

- `tier`: `"evergreen"` (default — awesome-lists, guides, wikis; unchanged 90-day cycle) or `"news"`
  (RSS feeds, HN/new, product-launch trackers, company blogs' latest-posts pages; picked up by 1F
  instead of waiting for a 1D refresh).
- `check_frequency_days`: overrides `REFRESH_DAYS` per-source when `tier: "news"` (typically `1`).

This is additive — existing rows without `tier` default to `evergreen`, so nothing already committed
needs to change to keep working.

### 2.4 `state/entity_registry.json` — structured records for agent/mcp/prompt/skill things (new)

The same "no persistent database" gap from §0 existed for a second kind of output: 1C only ever
extracts **AX cases**. A hit describing, say, a specific MCP server or a specific Claude Skill never
became a structured record anywhere — at best it sat in `search_hits_<topic>.json` as an unprocessed
snippet. `state/entity_registry.json` is 1C's sibling store, populated by Stage 1G (below) and
`merge_entity_registry.sh`, deduped by `entity_key` (`topic|lowercase(name)`) the same way cases dedup
by `case_key`.

```json
{
  "schema_version": 1,
  "last_merged_at": "2026-07-06",
  "entities": [
    {
      "entity_id": "ent-2026-0001",
      "topic": "mcp",
      "entity_type": "server",
      "name": "example-mcp-server",
      "url": "https://github.com/example/example-mcp-server",
      "description": "Verified from the repo README: an MCP server exposing X to Y via Z.",
      "description_source": "verified",
      "maintainer_or_vendor": "Example Org",
      "freshness_signal": "last commit 2026-06-30",
      "related_topics": ["agent"],
      "corroboration_count": 2,
      "conflicting_evidence_log": [],
      "discovery": { "first_seen_at": "2026-06-28", "last_corroborated_at": "2026-07-06", "found_via": [] }
    }
  ]
}
```

Merge behavior mirrors `merge_case_db.sh`: a repeat match raises `corroboration_count`, upgrades
`description_source` from `snippet-only` to `verified` (never the reverse), backfills
`maintainer_or_vendor`/`freshness_signal` when the existing record had `"unknown"`, unions
`related_topics`, and — same discipline as the case DB — logs a conflicting `entity_type` to
`conflicting_evidence_log` instead of silently picking one.

## 3. New stages

### 1E — Category Discovery (`agents/stage1/1E_category_discovery.md`, new file)
Mines `search_hits.json`, the `discovery_candidates[]` already produced by MODE B, and a small batch of
broad "what's emerging in AI agents/tooling" searches, for terms that (a) recur across multiple
independent hits, (b) aren't covered by any `active` category, and (c) look durable rather than a
one-off product name. Writes candidates to `category_registry.json` with `status: "candidate"`. A human
reviews and flips approved ones to `"active"` — at that point they're appended to `SEED_TOPICS` in
`pipeline.config.sh` and 1A/1A-community treat them as first-class topics on their next run, exactly
like `agent`/`mcp`/`prompt`/`skill`/`ax-cases` today.

### 1F — News Monitor (`agents/stage1/1F_news_monitor.md`, new file)
Runs far more often than 1D's 90-day cycle. Crawls only `tier: "news"` sources across every `active`
topic/category, restricted to a short freshness window (default: published in the last 7 days — older
items are somebody else's job, either 1B's normal crawl or simply not worth a fast lane). Emits hits in
the same `Hit` schema 1B already uses (so 1C needs no changes), and separately surfaces any
non-topic-covered recurring term it notices into 1E's evidence pool (news is often the earliest signal
of an emerging category).

### 1G — Entity Extractor (`agents/stage1/1G_entity_extractor.md`, new file)
Runs on the **same hits** 1C reads, independently — the Hit schema carries no `topic` field, so like
1C, this stage decides purely from a page's own content, not from which query surfaced it. Where 1C asks
"is this an AX transformation case?", 1G asks "does this describe one specific, nameable agent
framework / MCP server / prompt technique-or-library / skill?" A single hit can produce a case, an
entity, both, or neither. Tracks its own `entity_extracted`/`entity_ids` ledger fields, separate from
1C's `extracted`/`case_ids` on the same row, so the two passes never interfere with each other.

All three specs are written in full (see `agents/stage1/1E_category_discovery.md`,
`1F_news_monitor.md`, `1G_entity_extractor.md`) in the same Mission/Inputs/Procedure/Output/Rules shape
as 1A-1D, run via the same `claude -p --append-system-prompt` pattern `run_stage1.sh` already uses.

## 4. End-to-end workflow

```
                         ┌─────────────────────────────────────────────┐
                         │            1E · Category Discovery           │  slow cadence
                         │  mines hits + candidates → category_registry │  (monthly/quarterly)
                         │  candidate ──human review──> active          │
                         └───────────────────┬───────────────────────────┘
                                             │ promotes → SEED_TOPICS
                                             ▼
   ┌───────────── 1A · Strategy Builder ─────────────┐   ┌── 1A-community (niche) ──┐
   │ query expansion → Search Strategy DB             │   │ community registry        │
   └───────────────────────┬──────────────────────────┘   └──────────────┬────────────┘
                           ▼                                              ▼
                     ┌─────────────────────── 1B · Crawl Executor ───────────────────────┐
                     │ evergreen sources: 90-day cycle (existing)                         │
                     │ tier:"news" sources: routed to 1F instead ───────┐                 │
                     └───────────────────────┬───────────────────────────┼─────────────────┘
                                             │                          ▼
                                             │              ┌── 1F · News Monitor ──┐   fast cadence
                                             │              │ short freshness window │   (daily / 6-12h)
                                             │              └───────────┬────────────┘
                                             ▼                          ▼
                     ┌────────────────────── same hits, two independent passes ─────────────────────┐
                     │  1C · Case Extractor              │  1G · Entity Extractor                   │
                     │  hits → AX cases (KPI schema)      │  hits → agent/mcp/prompt/skill records    │
                     └──────────────┬─────────────────────┴──────────────┬────────────────────────────┘
                                    ▼                                    ▼
                     ┌── MERGE into state/ax_case_db.json ──┐ ┌── MERGE into state/entity_registry.json ──┐
                     │ dedup by case_key · corroboration_count│ │ dedup by entity_key · corroboration_count │
                     │ conflicts flagged, never overwritten   │ │ conflicts flagged, never overwritten      │
                     └──────────────┬───────────────────────┘ └──────────────┬─────────────────────────────┘
                                    ▼
                     Stage 2 Validator → Stage 3 Selector → Stage 4 Slide Builder
                     (run on demand against the current state of ax_case_db.json,
                      not tied to any single discovery run; entity_registry.json is
                      a separate catalog, not part of the Samsung deck pipeline)
```

`1D Refresh Scheduler` is unchanged and keeps doing its job for evergreen sources/queries; it now also
triggers a 1E pass if `next_category_review_due` has elapsed (see schedule below).

## 5. Schedule

All cadences are "safe to run on a shorter check-cycle than the actual work cycle" — same principle as
today's `refresh.sh` ("safe to schedule ... often; it does nothing until stale"). Run the *check* daily
via cron/Task Scheduler; each stage internally no-ops until its own due date passes.

| Tier | What runs | Actual cadence | Cron (check daily, acts when due) | Notes |
|---|---|---|---|---|
| 1 — News | 1F News Monitor | every 6-24h | `0 */12 * * * bash scripts/discover.sh --news-only` | Cheap, narrow (news-tier sources only, 7-day window). Feeds both `ax_case_db.json` (via 1C) and `entity_registry.json` (via 1G). |
| 2 — Evergreen refresh | 1D → 1A/1B/1C for stale strategies | REFRESH_DAYS=90, checked often | `0 3 * * * bash scripts/refresh.sh` (already the recommended pattern) | Unchanged from today. |
| 3 — Source/community discovery (MODE B) | 1A-community MODE B | quarterly | `0 4 1 */3 * bash scripts/run_stage1.sh --community-discovery` | Finds wholly new communities/awesome-lists; candidates need review before `status: active`. |
| 4 — Category discovery | 1E | monthly, or triggered early if 1F repeatedly surfaces the same uncovered term ≥3× | `0 5 1 * * bash scripts/discover.sh --category-only` | Human review gate before any candidate becomes a seed topic. |
| 5 — Full corpus recalibration | `calibrate.sh` against `state/ax_case_db.json` | before each lecture engagement, or monthly | manual | Existing tool; now has a growing corpus to calibrate against instead of one run's snapshot. |
| 6 — Deck rebuild (Stages 2-4) | `run_pipeline.sh` with `FROM_STAGE=2`, `EXISTING_CASE_DB=state/ax_case_db.json` | on demand, per engagement | manual | Point it at the master DB, not a single run's case file. |

On Windows, the equivalent is Task Scheduler triggers calling `bash scripts/refresh.sh` / `bash scripts/discover.sh`
through Git Bash or WSL at the same cadences — cron syntax above is the portable spec either maps to.

## 6. Governance / review gates (unchanged principle, extended to two new places)

Every lifecycle in this system already promotes `candidate → active` only after human review
(`1A_community_strategy_builder.md` rule 5). This extends the same gate to:
- **Category promotion** (1E): a proposed topic never becomes a live seed topic — never starts spending
  crawl budget — until a human flips its `category_registry.json` status to `active`.
- **Conflicting evidence at merge time** (§2.1): the merge step never picks a winner between
  contradicting facts about the same case; it flags and waits.

Nothing here should ever auto-run with `--dangerously-skip-permissions` outside an isolated sandbox —
same caution `SETUP.md` §8 already states, and it applies doubly to anything on a cron trigger with no
one watching.

## 7. Metrics worth tracking as this runs (future `calibrate.sh` extension, not built yet)

- Yield per source/category over time (already tracked per-strategy via `yield_count`; worth rolling up
  by category to spot which topics have gone dry).
- Corroboration growth on existing cases (`corroboration_count` trend — a case corroborated by 4
  independent sources is stronger evidence than one with 1).
- Category candidate → active → paused funnel (how many proposals survive review; helps tune 1E's
  precision over time).
- News-tier yield vs. evergreen-tier yield (is the fast lane actually finding things the 90-day cycle
  would've missed, or is it redundant).

Not implemented in this pass — flagging so `calibrate.sh` has a clear next-extension point.

## 8. What's built

Everything described above is now implemented, not just designed:

- **`agents/stage1/1E_category_discovery.md`**, **`1F_news_monitor.md`**, and **`1G_entity_extractor.md`**
  — the three new stage specs.
- **`merge_case_db.sh`** — the case_key dedup/merge step. Tested directly (new case, corroborating
  match with source merge + confidence bump, and a genuine conflicting-date case that gets logged to
  `conflicting_evidence_log` rather than overwritten — all three behave as designed).
- **`merge_entity_registry.sh`** — 1G's sibling merge step for `entity_key`. Tested directly (new
  entity, corroborating match that upgrades `description_source` from snippet-only to verified *and*
  backfills `maintainer_or_vendor`/`freshness_signal`, and a genuine `entity_type` conflict that gets
  logged rather than overwritten).
- **`discover.sh`** — orchestrates 1F (news hits -> 1C + 1G -> `merge_case_db.sh` +
  `merge_entity_registry.sh`) and 1E (category proposals), with `--news-only` / `--category-only` /
  default-both modes. Mirrors `refresh.sh`'s structure and reuses its ledger-merge technique.
- **`run_stage1.sh`** now calls 1G and `merge_entity_registry.sh` right after 1C/`merge_case_db.sh`, so
  the initial discovery pass and every 1D refresh feed both master stores, not just the news lane.
- **`tier` / `check_frequency_days`** wired into `config/source_registry_template.json`,
  `state/source_registry.json`, and all 24 live rows of `state/community_strategy_db.json` (Reddit `/new/`
  and HackerNews search tagged `news`; Substack/GitHub/YouTube/LinkedIn stay `evergreen`). `1B_crawl_executor.md`
  now explicitly skips `tier:"news"` rows so 1B and 1F never double-crawl the same source.
- **`state/ax_case_db.json`**, **`state/category_registry.json`**, and **`state/entity_registry.json`**
  — created as empty, tracked skeletons (all scripts also auto-create them if missing, matching
  `run_stage1.sh`'s existing pattern).
- **`schedule/crontab.txt`** (Linux/macOS/WSL) and **`schedule/register_windows_tasks.ps1`** (Windows
  Task Scheduler, parse-verified) — install either to run the six-tier schedule from §5.
- **`calibrate_seeding.sh`** — the §7 metrics, reading `state/` directly rather than a single run
  folder: yield by seed topic, corroboration distribution across the master DB, the category discovery
  funnel, news-vs-evergreen yield, and a staleness snapshot. Verified against this project's real state.

One correctness note from testing: an early version of `calibrate_seeding.sh` counted "total cases" via
`.cases[]?.corroboration_count // 1`, which is wrong on an empty `cases[]` array — jq's `//` substitutes
its right-hand side for an *entire empty stream*, not per-missing-element, so it reported 1 case when
there were 0. Fixed by computing the count from `.cases | length` directly and only using `map(.field //
default)` (which is per-element-safe) for the derived values. Worth remembering if you extend these
scripts further: `stream // default` is an all-or-nothing fallback, not a null-coalesce over each item.
