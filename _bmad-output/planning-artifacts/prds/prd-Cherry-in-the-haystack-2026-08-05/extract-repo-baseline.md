# Extract — existing baseline in `axCaseResearch4` (harvest engine)

Source: this repository, extracted 2026-08-05 for the Cherry harvest-engine PRD.
Method: subagent extraction over `CLAUDE.md`, `docs/**`, `docs/harvest/**`, `agents/**`,
`scripts/**`, `schemas/**`, `config/**`, `state/**`.

---

**Two distinct pipelines coexist in this repo.** They share a repository and a validation
gate, nothing else. Do not treat them as one system in the PRD.

- **Legacy entity harvest** (bash + `jq` + headless `claude -p`) — harvests *tools / agents /
  MCP servers / prompts / skills* into `state/BuildingBlocks_*.json`. This is the thing that
  actually contains 1,161 tool records today.
- **Taxonomy harvest** (Python, `src/harvest/**`, Stages 0–10) — a rigorously engineered
  *content/news* pipeline (cases, discourse, research-and-models) with schemas, scoring,
  facets, atomic artifacts, and a `publication_eligible` concept. It has produced 3 live runs
  and **zero published data**. Its `policy.v1.json` User-Agent is literally
  `cherry-harvest/1.0 (+https://cherryinthehaystack.com)` — it was built *for* this website,
  but it harvests articles, not tools.

## 1. What the system does today

**Legacy entity harvest** (`docs/entity_harvest_workflow.md`, `scripts/harvest_entities.sh`).
Per topic loop: seed from a curated `reports/awesome-lists/awesome_<topic>.md` +
`state/search_hits_<topic>.json` → **candidate batch** (`claude -p`, tools
`Read,WebSearch,WebFetch`, `BATCH_SIZE=40`) → **GitHub metadata prefetch**
(`scripts/github_meta.py`, deterministic, non-fatal, `harvest_entities.sh:536`) → **Stage 1G
extraction** (`claude -p --append-system-prompt agents/stage1/1G_entity_extractor.md`, tools
`Read,WebFetch` — it fetches and verifies each entity page) → topic guard →
`merge_entity_registry.sh` (dedup on `entity_key`) → progress accounting. Stops on `target`
reached (default 250 *verified* per topic), `NO_PROGRESS_THRESHOLD=3`, or `MAX_LOOPS=40`.
Four fixed topics: `agent`, `mcp`, `prompt`, `skill`; each owns a shard;
`state/entity_registry.json` is a derived union folded by `merge_building_blocks.sh`.

**Matrix mode** (`docs/matrix_harvest_workflow.md`, `scripts/run_matrix.sh`) generalises this
to arbitrary (category × topic) cells: per-cell query expansion (`expand_queries_cell.sh`,
augment-never-shrink) then the same harvest loop, `topic`/`category` stamped from
`state/matrix/manifest.json`, `MAX_PARALLEL=4`. **`state/matrix/` does not exist — matrix mode
has never been run in production.**

**Taxonomy harvest** (`scripts/harvest/harvest.sh` → `python -m src.harvest.cli`): preflight
sources → adapters (feed/sitemap/jsonapi/seed) → candidate pool + dedupe → precedence
classification into 12 cells → four-score verification → facet assignment → atomic artifact
writing → run manifest. Commands implemented: `preflight-sources`, `smoke`, `validate`,
`compare-runs`, `diff`, `linkcheck`. **8 of 13 planned commands exist**; `promote`, `refresh`,
`smoke-model` and the publication-manifest producer do not.

The AX→deck pipeline (`agents/01..04`, `run_pipeline.sh`) is a third, unrelated artifact —
case studies to slides.

## 2. Data model

**`state/BuildingBlocks_*.json` / `entity_registry.json`** — 16 fields, present on 100 % of
1,161 rows:

`entity_id` · `topic` · `entity_type` · `name` · `description` · `description_source` ·
`maintainer_or_vendor` · `freshness_signal` · `related_topics` · `entity_key` ·
`corroboration_count` · `discovery{first_seen_at, last_corroborated_at, found_via[{hit_id,
platform}]}` · `conflicting_evidence_log[]` · `source_url` · `target_url` · `github_stars`

Mapping to PRD concerns: **quality** → nothing (only `corroboration_count` 1–5,
`conflicting_evidence_log`). **Verification** → `description_source ∈ {verified,
snippet-only}` — and the migration assessment states explicitly this "describes how the
DESCRIPTION was obtained, not whether the URL was fetched… it cannot supply
`verification_status`". **License / commercial usability** → **absent**. **Popularity** →
`github_stars` (int or null). **Source URL** → `source_url` (surfacing page) vs `target_url`
(the thing itself). **Topic/category** → `topic` (4 harvest lanes only); `entity_type` (16
values, no committed vocabulary); `category` exists only on matrix rows.

**`schemas/harvest/record.v1.json`** (taxonomy) is far richer: `record_id`, `content_id`,
`identity_url`, `canonical_url`, `url_aliases[]`, `curation_reason`, `access_status`,
`verification_status`, `verification_evidence`, `http_status`, `content_hash`,
`link_history[]`, `relevance_score`, `quality_score`, `audience_fit_score`, `freshness_score`,
`classification{rule_id, rationale, evidence}`, `provenance{source_id, source_adapter,
source_tier}`, `case_facets`, `domain_fields`, `legacy_ids[]`. **Still no license field.**

Ledger: `state/visited_url_ledger.json` = `{ledger:[{url, url_type, platform,
first_crawled_at, last_crawled_at, crawl_count, http_status_last, content_hash, extracted,
case_ids, entity_extracted, entity_ids}]}`. `state/github_meta_cache.json` =
`{repos:{"owner/repo":{status, stars, canonical_url, full_name, archived, pushed_at,
fetched_at}}}`.

## 3. Quality / validation machinery that exists

- **`gate_passed`** belongs to the *AX case* pipeline only (`agents/02_validator.md:39`), not
  to entities. Its checks: URL accessibility, source credibility on a manual A/B/C/D tier
  ladder (Tier D alone barred), KPI traceability, transformation vs publication date
  separation, vendor-claim labelling, and an active contradictory-evidence web search. There
  is no entity equivalent.
- **Dedup/exclusion**: `entity_key` (`topic|normalized(name)`) at merge; `source_url` via the
  visited-URL ledger; `target_url` exclusion at candidate-batch time; `attempted_urls[]`
  within a run.
- **Conflict, not scoring**: `merge_entity_registry.sh:62` ranks `verified(2) > snippet-only(1)
  > unknown(0)` purely to resolve which description wins; `entity_type`/`target_url`
  mismatches append to `conflicting_evidence_log`; `github_stars` is explicitly excluded from
  conflict handling (popularity, not identity).
- **GitHub enrichment**: `scripts/github_meta.py` extracts exactly `stargazers_count`,
  `html_url`, `full_name`, `archived`, `pushed_at`. Repo-roots only. Proper 429/403-ratelimit
  handling with exponential backoff; unauthenticated budget capped at 50.
- **Taxonomy scoring** (`src/harvest/verify.py` + `config/harvest/policy.v1.json`): four
  scores, weights relevance 0.40 / quality 0.25 / audience_fit 0.20 / freshness 0.15;
  thresholds `min_relevance 0.35`, `min_quality 0.30`, `min_audience_fit 0.20`,
  `accept_composite 0.40`; freshness half-life 90 days. Unknown dimensions are `null` and
  renormalised, never zero.
- **Facets** (`config/harvest/facets/*.v1.json`): three axes — industries (18),
  business-functions (19), use-case-types (22) — each entry with `slug`, `definition`,
  `positive_terms`, `synonyms`, `exclusions`, `disambiguation`, `coverage_policy ∈ {priority,
  standard, record_only}`. Applies to *cases*, not tools.

## 4. Concurrency, safety, operations

Per-topic sharding is the concurrency design: no two lanes touch a file. Locks are
`mkdir`-based advisory lockdirs (`scripts/lib/lockdir.sh` — `flock` absent on Git Bash), with
an owner file, 2 h staleness window, and release only by the owning PID. Atomic writes are
`mktemp` **in the destination dir** + `jq empty` validation + `mv` (never a fixed `.tmp`);
Python uses `mkstemp`+`fsync`+`os.replace`. `MAX_PARALLEL=4` exists **only in
`run_matrix.sh`**; `harvest_parallel.sh` launches all 5 lanes uncapped, mitigated only by
`STAGGER_SEC=20`. Retries are fixed-count (3) with **no backoff** and trigger on malformed
model output, not HTTP status — the Claude session 429 limit is not detected at all; a
rate-limited lane simply fails.

Safety wrappers: `.claude/hooks/guard_command.py` blocks exit-code-masking pipes, force push,
hard reset, destructive `rm`, and any write into production `state/`.
`scripts/validate_task.sh` is the single offline gate — mocks `CLAUDE_BIN` to `exit 97`,
redirects `STATE_DIR` to a temp dir, runs only a 57-entry audited allowlist, and hash-snapshots
production `state/` plus four runtime paths before and after (leaks fail, and are never
auto-cleaned). 63 wrapper tests; latest full green run is commit `ec9bedc` (43 suites, 2,386
tests, 0 failures). `safe_commit.sh` requires explicit file lists; `safe_push_main.sh
--execute` always requires a human.

## 5. Volume reality

| Measure | Value |
|---|---|
| Entities (union) | **1,161** — agent 293 · mcp 305 · prompt 204 · skill 359 |
| `description_source` | verified 975 · snippet-only 186 |
| Entity types | 16 values; server 230, skill 259, product 109, platform 95, framework 83 |
| GitHub `target_url` rows | 678 — **only 242 have stars**; 916 of 1,161 have `github_stars: null` |
| `target_url` usable | 1,024; **137 are the `"unknown"` sentinel**; 36 URLs shared by 77 rows |
| `entity_id` uniqueness | **721 distinct ids over 1,161 rows** (51 ids reused by 491 rows); only `entity_key` is unique |
| Visited-URL ledger | **1,132** rows |
| GitHub meta cache | 86 repos |
| AX cases | 231 in `ax_case_harvest_registry.json`; `ax_case_db.json` is empty |
| Harvest window | first_seen 2026-07-06 → 2026-07-15 (7 distinct dates); registry last merged 2026-07-22 |
| Taxonomy live runs | **3**, all in an external retained root, 99 files, **32 records / 19 accepted**; 4 outbound executions ever |
| Published harvest data | **0 of 16 files** · promotion code: zero · website consumption: zero |

## 6. Known gaps, limitations, open defects

- **Seed exhaustion** — agent, prompt, and ax-cases seeds are fully consumed; sourcing returns
  ~0 new. Skill is *not* exhausted: the raw VoltAgent README holds 400+ uncatalogued entries
  beyond the 40-row report cap.
- **GitHub stars ordering bug** — `github_meta.py prefetch` runs at `harvest_entities.sh:536`,
  **before** 1G resolves `target_url` at :550. Stars are fetched against candidate URLs, so 436
  of 678 GitHub entities have `null` stars. A token does not fix this; a backfill pass would.
- **`entity_id` collisions** — documented in `docs/entity_id_collision_note.md`, quantified in
  `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md` §3. Each 1G run invents its own
  `ent-YYYY-NNNN` sequence.
- **No entity → taxonomy path.** The assessment lists four blocking contract failures (137 rows
  with no URL; 77 rows sharing 36 URLs; no committed cell describes "an MCP server"; no scores,
  no fetch evidence) and four candidate destinations, **none approved**. 1,161 assessed, **0
  migrated**.
- **Gap register G1–G18** (`docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §9): G4 no
  production harvest command · **G7 promotion designed, zero lines implemented** · **G9 human
  review has no artifact, schema, process, acceptance criteria or owner** · **G10 website
  integration unowned and outside this repo** · G14 33 of 39 wrappers assert `config/`
  unmodified, so *no checkpoint that edits `config/` can pass the gate* — this blocks adding
  new facet axes · G15 source tiers configured but unreachable.
- Editorial thresholds are **PROVISIONAL**; `docs/harvest/TODO.md:1216` is stale pre-Stage-9
  text.

## 7. The five decision-forcing questions

**a. License / commercial usability — NO.** Absent from all 16 entity fields; absent from
`schemas/harvest/record.v1.json`; `scripts/github_meta.py:179-186` extracts five keys and
`license`/`spdx_id` is not among them; no facet axis, no config, no doc mentions it. This is a
**greenfield requirement** — and given the PRD's "commercially usable" framing, it is the
single largest schema gap.

**b. Publishing to a website / CMS / API — NO.** `scripts/` contains no `curl`, webhook, HTTP
POST, Notion, CMS or deploy step; outputs are local JSON files. The taxonomy pipeline has
`derive_publication_eligibility()` and `publish_run()` (`src/harvest/artifacts.py:689, 831`)
but these write to a *local* run tree; `promote`, `promotion_journal`, `publication_manifest`,
`--publication-root` have **zero occurrences anywhere** in `src/`, `scripts/`, `schemas/`,
`config/`, `tests/`. `data/harvested/`, `runs/` and `LATEST_RUN_ID` do not exist. M7
("cherryinthehaystack.com reads the JSON") is NOT STARTED, UNSCOPED, UNOWNED.

**c. Non-developer audience — WEAKLY, and inverted.** There is `audience_fit_score` on the
taxonomy record and a `min_audience_fit: 0.20` threshold, but the implementation
(`src/harvest/verify.py:346-357`) is **binary 0.0/1.0**: it drops to 0.0 only when the
category's `exclude` list fires, and the rejection reason is `developer_only_audience` driven
by the `is_developer_tool` keyword signal (`config/harvest/precedence.v1.json:118` — "sdk",
"cli", "framework", "npm"…). In the only live corpus it was **saturated at 1.000 across all 19
records and rejected nothing**. There is **no skill-level, persona, or audience-type field**,
and no way to express "good for non-developers" positively — only "reject developer-only".

**d. How quality is decided.** For the 1,161 entities: **effectively nothing**. No score, no
rank, no threshold, no human review. The only gates are model-side verification during 1G
(`description_source: verified`), the `verified > snippet-only > unknown` ordinal used solely
to resolve merge conflicts (`scripts/merge_entity_registry.sh:62`), and progress-based stopping
(`NO_PROGRESS_THRESHOLD`, `MAX_LOOPS`, `TARGET`) — a *count*, not a quality bar. For the
taxonomy pipeline: model-free deterministic scoring in `src/harvest/verify.py` against
committed thresholds, where in practice only `relevance` discriminated (closest miss 0.3333 vs
0.35); quality and audience_fit rejected nothing. **Human review exists nowhere** — G9: "no
artifact, schema, process, acceptance criteria or owner", and it blocks milestone M5.

**e. Degree of automation — human-in-the-loop, session-driven.** Each lane is a `claude -p`
subprocess started by a human running a script in an interactive session; there is no
scheduler, no cron, no CI. `scripts/harvest_parallel.sh` overlaps 5 lanes but is still
hand-launched, and long/concurrent runs reliably hit the Claude session rate limit, failing all
lanes at once. Every orchestrator enforces the honesty rule that *a child's exit 0 does not
mean the target was met* — completion must be re-derived by re-running `--check`. Commits and
pushes are gated behind `safe_commit.sh` / `safe_push_main.sh` and always require explicit
human approval. `schedule/` exists but contains only logs.
