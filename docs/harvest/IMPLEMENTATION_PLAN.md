<!-- Approved implementation plan, copied verbatim from the plan file that was
     reviewed and approved before implementation began. Companion documents:
       docs/harvest/INVENTORY_AND_REUSE_MAP.md  — what exists and what is reused
       docs/harvest/TODO.md                     — live task checklist
       docs/harvest/IMPLEMENTATION_REPORT.md    — written at Stage 10
-->

# Taxonomy harvest pipeline — Cherry in the Haystack

*Revision 4 (final). Implementation-start commit `8865c54e2cc8d879410576f247baac4aea149f34`.*

## Context

This repo harvests AI-ecosystem content through three families sharing one set of primitives: the
fixed-topic **entity** harvest, the **AX case** harvest (231 cases), and the **matrix** harvest
(`run_matrix.sh` → `state/matrix/`). Three things block reusing the matrix path for the publishing
taxonomy: the taxonomy is a hierarchy (3 cells, not 3×3) with positional matrix IDs being wrong for a
stable published taxonomy; there is **no local HTTP fetching anywhere in the repo** (so no robots
handling, no throttling, and `http_status_last`/`content_hash` are always `null`, making link-check
impossible); and there is **no URL canonicalization in the live dedup path**.

**Outcome:** a configuration-driven pipeline turning versioned taxonomy files into schema-valid,
traceable, deduplicated artifacts for review and publication on `cherryinthehaystack.com`, with
harvest / refresh / link-check modes — built alongside the existing paths, changing none of them.

---

## 1 · Namespace

All new mutable runtime state lives under `state/taxonomy_harvest/`, **including locks**
(`lockdir.sh` takes an arbitrary path, so no exception is warranted).

```
config/harvest/topics/{cases,research-and-models,discourse}.v1.json
config/harvest/policy.v1.json                      politeness, budgets, per-domain overrides
config/harvest/precedence.v1.json                  10 classification rules + cross_topic_policy
config/harvest/canonicalization.v1.json            tracking params, per-domain rules, migrations
config/harvest/watchlists/oss-milestones.v1.json
config/harvest/migration_overrides.v1.json         reviewed unmappable AX records
schemas/harvest/*.v1.json
src/harvest/ · scripts/harvest/ · tests/harvest/
requirements.txt · constraints.txt

# PUBLISHED OUTPUT — tracked; only ever written by `promote`
data/harvested/<topic_slug>/<topic_slug>__<category_slug>__harvest.json
data/harvested/<topic_slug>/<topic_slug>__all__harvest.json
data/harvested/publication_manifest.json
data/harvested/.promotion_journal.json             present ONLY mid-transaction

# MUTABLE RUNTIME STATE — gitignored, reconstructible
state/taxonomy_harvest/LATEST_RUN_ID               single line: "<run_id>\n"
state/taxonomy_harvest/runs/<run_id>/{manifest.json,logs/,tmp/<cell_id>/,candidate_output/,
                                      alias_conflicts.json,promote_staging/,promote_rollback/,
                                      promotion_receipt.json}
state/taxonomy_harvest/{registries,ledgers,rejections,cache,domains,migrations,locks}/
```

`run_id` format: `YYYYMMDDTHHMMSSZ-<pid>`. `LATEST_RUN_ID` is written atomically at the end of every
run-producing command (`smoke`, `harvest`, `refresh`, `linkcheck`).

---

## 2 · URL contract, identity, canonicalization, aliases

### 2.1 The four URL fields

| Field | Meaning | Mutability |
|---|---|---|
| `source_url` | The feed, API endpoint, index page, search result or citing page that **surfaced** the item | Set at discovery |
| `target_url` | The item's **own** page, verbatim as discovered, unnormalized | Immutable record of what was seen |
| `identity_url` | `canonicalize_string(target_url)` **fixed at first acceptance** | **Immutable, forever** |
| `canonical_url` | Latest *verified* preferred URL. Starts equal to `identity_url` | Mutable |

```python
content_id = sha256(identity_url).hexdigest()[:16]                     # global, cross-topic
record_id  = sha256(topic_slug + "|" + identity_url).hexdigest()[:16]  # per-topic primary key
```

Both derive from immutable `identity_url`, never `canonical_url`. A redirect or changed canonical tag
updates `canonical_url` and appends to `url_aliases[]`; it **cannot** mint a new identity.

### 2.2 String canonicalization — conservative, prefers false negatives

Only transformations RFC 3986 or an explicit versioned config rule guarantees are
equivalence-preserving:

1. Trim surrounding whitespace.
2. Lowercase **scheme and host only** (RFC 3986 §6.2.2.1). Path and query keep their case.
3. Remove the default port (`:80` http, `:443` https).
4. Normalize percent-encoding: uppercase hex digits, decode unreserved characters.
5. Resolve dot-segments (`/a/./b/../c` → `/a/c`).
6. Remove **only** parameters on the explicit tracking list. **Preserve the original order and
   multiplicity of every remaining parameter.**
7. Fragment: strip **ordinary document anchors only** (see below).

**Query ordering — corrected.** There is **no global query sort**. `?a=1&b=2` and `?b=2&a=1` remain
**distinct** by default, because parameter order is content-significant on some sites and repeated
keys (`?tag=x&tag=y`) are order-carrying. Sorting happens **only** when a domain carries an explicit
`"query_sort": true` rule in `canonicalization.v1.json`, whose safety justification is recorded in
the rule object and covered by a per-rule test.

**Fragments — conservative default.** Fragments are **preserved by default**. A fragment is stripped
**only** when one of these holds:

- a versioned per-domain rule in `canonicalization.v1.json` declares ordinary-anchor stripping safe
  for that domain (`"strip_ordinary_anchors": true`); **or**
- fetched-document evidence confirms the fragment names an ordinary in-document anchor — an element
  carrying that `id` or `name` exists in the fetched body — **and** the domain is not configured
  `"hash_routing": true`.

Resource equivalence is **never** inferred from fragment syntax alone. `#dashboard` is not treated as
an anchor merely because it lacks a leading `/` or `!`.

| Fragment | Default | With `strip_ordinary_anchors` rule | With fetched-anchor evidence |
|---|---|---|---|
| `#intro` | preserved | stripped | stripped iff `id="intro"` found in body |
| `#dashboard` | preserved | stripped | stripped iff `id="dashboard"` found in body |
| `#!/route` | preserved | preserved (hashbang never stripped) | preserved |
| `#?tab=results` | preserved | preserved (query-in-fragment never stripped) | preserved |
| `#/a/b` | preserved | preserved (router path never stripped) | preserved |
| any fragment, domain `"hash_routing": true` | preserved | preserved | preserved |

The default deliberately prefers duplicate retention over destructive false-positive merging.

**Never done in string canonicalization** — each is handled only by evidence-based aliasing:
`http:`→`https:` · stripping `www.` · stripping trailing slash. A **302/307** never rewrites identity;
only **301/308** or an authorized rule can.

**Tracking parameters stripped** (versioned in `canonicalization.v1.json`):
`utm_source, utm_medium, utm_campaign, utm_term, utm_content, utm_id, utm_source_platform,
utm_creative_format, utm_marketing_tactic, gclid, gclsrc, dclid, gbraid, wbraid, fbclid, msclkid,
twclid, igshid, ttclid, yclid, mc_cid, mc_eid, _hsenc, _hsmi, vero_id, vero_conv, oly_anon_id,
oly_enc_id, s_cid, ck_subscriber_id`

**Explicitly NOT stripped:** `ref`, `source`, `id`, `p`, `q`, `v`, `page`, `t`, `si` — each can be
content-significant.

### 2.3 Canonical-tag trust policy and alias conflicts

A `rel=canonical` tag is **not** trusted merely because it appeared in HTML.

| Tier | Condition | Result |
|---|---|---|
| Auto-accept | Canonical target is on the **same registrable domain**, is a syntactically valid absolute URL, passes robots, and is non-circular | alias `kind: canonical_tag` |
| Requires evidence | Canonical target is **cross-registrable-domain** | Accepted **only** with an allowlisted `domain_migration` rule in `canonicalization.v1.json` **or** independently observed 301/308 evidence to the same target. Otherwise → `alias_conflict` |
| Never | Malformed, circular (A→B→A), multiple conflicting `<link rel=canonical>` on one page, or contradicting an existing alias | `alias_conflict`, no alias created |

**Alias conflicts do not auto-merge.** When a proposed alias would join two records that already
exist **independently**:

- both records are **preserved unchanged** — no identity change, no deletion, no silent disappearance;
- an entry is written to `runs/<run_id>/alias_conflicts.json`:
  `{conflict_id, kind, record_ids[], proposed_alias, evidence, detected_at, resolution:"unresolved"}`;
- resolution requires an explicit `harvest.sh resolve-alias --conflict-id … --winner …` or a
  configured `domain_migration` rule;
- `promote` **refuses** while unresolved alias conflicts exist, unless `--allow-alias-conflicts`.

**Automatic merging is permitted in exactly two cases:** (a) the alias was already established when
the incoming candidate arrived, so the candidate resolves to an existing record at ingest and was
never an independent record; (b) an explicit `domain_migration` rule authorizes the merge. The
`discovered_at` tie-break from Revision 3 is removed.

### 2.4 Identity / canonicalization tests (`tests/test_taxonomy_identity.sh`)

| # | Scenario | Assertion |
|---|---|---|
| 1 | Same URL via two categories in one topic | one record, one `record_id` |
| 2 | Same URL under two topics | two `record_id`s, one `content_id`; §4 policy applied |
| 3 | Precedence flips `primary_category` | IDs byte-identical |
| 4 | Taxonomy config reordered | all IDs unchanged |
| 5 | Tracking params, default port, dot-segments | collapse to one `identity_url` |
| 6 | `ref=` / `source=` variants | remain **distinct** |
| 7 | `?a=1&a=2` (repeated, order-sensitive) | order and multiplicity preserved |
| 8 | `?a=1&b=2` vs `?b=2&a=1` | remain **distinct** (no global sort) |
| 9 | Domain with `query_sort:true` rule | those two collapse; rule-scoped only |
| 10 | `#intro` — default | **preserved** → distinct record |
| 11 | `#dashboard` — default | **preserved** (syntax alone proves nothing) |
| 12 | `#!/route` hashbang | preserved under every policy |
| 12b | `#?tab=results` query-in-fragment | preserved under every policy |
| 12c | Router fragment on a configured `hash_routing` SPA domain | preserved |
| 12d | `#intro` on a domain with `strip_ordinary_anchors: true` | stripped |
| 12e | `#dashboard` with fetched evidence of `id="dashboard"` | stripped |
| 12f | `#dashboard` with fetched body lacking that id | preserved |
| 13 | `http` → **301** → `https` | alias added, `canonical_url` updated, **IDs unchanged** |
| 14 | `http` and `https` serving different bodies | remain two distinct records |
| 15 | **302** temporary redirect | no alias, no rewrite, IDs unchanged |
| 16 | Same-domain `rel=canonical` | auto-accepted as alias |
| 17 | Cross-domain `rel=canonical`, no rule/evidence | `alias_conflict`, **no** alias |
| 18 | Circular / multiple conflicting canonical tags | `alias_conflict`, no alias |
| 19 | Alias would join two existing independent records | **both preserved**, conflict recorded, no identity change |
| 20 | Authorized `domain_migration` rule | merge performed, recorded in manifest |
| 21 | Repeated migration (×2) and repeated harvest | identical ID sets, no duplicates |

---

## 3 · The 12-category source table (machine-readable, no dittos)

Every configured source object independently carries all nine required fields. Documentation groups
values visually; **the config does not** — each object repeats every field.

```json
{
  "source_id": "aws-ml-blog",
  "topic_slug": "cases",
  "category_slug": "domain-applications",
  "adapter": "feed",
  "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
  "role": "discovery",
  "max_candidates": 6,
  "max_requests": 3,
  "fixture_id": "fx_aws_ml_blog"
}
```

| # | source_id | topic_slug | category_slug | adapter | exact URL | role | cand cap | req budget | fixture_id |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `aws-ml-blog` | `cases` | `domain-applications` | `feed` | `https://aws.amazon.com/blogs/machine-learning/feed/` | discovery | 6 | 3 | `fx_aws_ml_blog` |
| 2 | `nvidia-blog` | `cases` | `domain-applications` | `feed` | `https://blogs.nvidia.com/feed/` | discovery | 6 | 3 | `fx_nvidia_blog` |
| 3 | `openai-news` | `cases` | `case-studies` | `feed` | `https://openai.com/news/rss.xml` | discovery | 6 | 3 | `fx_openai_news` |
| 4 | `anthropic-customers` | `cases` | `case-studies` | `seed` | `https://www.anthropic.com/customers` | validation_seed | 6 | 3 | `fx_anthropic_customers` |
| 5 | `producthunt` | `cases` | `product-discovery` | `feed` | `https://www.producthunt.com/feed` | discovery | 12 | 4 | `fx_producthunt` |
| 6 | `hf-blog` | `research-and-models` | `model-updates` | `feed` | `https://huggingface.co/blog/feed.xml` | discovery | 6 | 3 | `fx_hf_blog` |
| 7 | `google-ai-blog` | `research-and-models` | `model-updates` | `feed` | `https://blog.google/technology/ai/rss/` | discovery | 6 | 3 | `fx_google_ai_blog` |
| 8 | `arxiv-cs-ai` | `research-and-models` | `papers` | `feed` | `https://rss.arxiv.org/rss/cs.AI` | discovery | 12 | 4 | `fx_arxiv_cs_ai` |
| 9 | `arxiv-cs-lg` | `research-and-models` | `benchmark-and-datasets` | `feed` | `https://rss.arxiv.org/rss/cs.LG` | discovery | 4 | 3 | `fx_arxiv_cs_lg` |
| 10 | `lm-eval-harness-releases` | `research-and-models` | `benchmark-and-datasets` | `feed` | `https://github.com/EleutherAI/lm-evaluation-harness/releases.atom` | validation_seed | 4 | 3 | `fx_lm_eval_harness` |
| 11 | `openai-evals-releases` | `research-and-models` | `benchmark-and-datasets` | `feed` | `https://github.com/openai/evals/releases.atom` | validation_seed | 4 | 3 | `fx_openai_evals` |
| 12 | `federal-register-ai` | `discourse` | `regulations-policy-compliance` | `jsonapi` | `https://www.federalregister.gov/api/v1/documents.json?conditions%5Bterm%5D=artificial+intelligence&per_page=20&order=newest` | discovery | 6 | 3 | `fx_federal_register_ai` |
| 13 | `nist-news` | `discourse` | `regulations-policy-compliance` | `feed` | `https://www.nist.gov/news-events/news/rss.xml` | discovery | 6 | 3 | `fx_nist_news` |
| 14 | `hn-algolia` | `discourse` | `community` | `jsonapi` | `https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI&hitsPerPage=20` | discovery | 3 | 2 | `fx_hn_algolia` |
| 15 | `oss-ollama-releases` | `discourse` | `community` | `feed` | `https://github.com/ollama/ollama/releases.atom` | validation_seed | 3 | 2 | `fx_oss_ollama` |
| 16 | `oss-mcp-servers-releases` | `discourse` | `community` | `feed` | `https://github.com/modelcontextprotocol/servers/releases.atom` | validation_seed | 3 | 2 | `fx_oss_mcp_servers` |
| 17 | `oss-langchain-releases` | `discourse` | `community` | `feed` | `https://github.com/langchain-ai/langchain/releases.atom` | validation_seed | 3 | 2 | `fx_oss_langchain` |
| 18 | `google-blog` | `discourse` | `big-tech-trends` | `feed` | `https://blog.google/rss/` | discovery | 6 | 3 | `fx_google_blog` |
| 19 | `microsoft-blogs` | `discourse` | `big-tech-trends` | `feed` | `https://blogs.microsoft.com/feed/` | discovery | 6 | 3 | `fx_microsoft_blogs` |
| 20 | `techcrunch-ai` | `discourse` | `market-and-investment` | `feed` | `https://techcrunch.com/category/artificial-intelligence/feed/` | discovery | 12 | 4 | `fx_techcrunch_ai` |
| 21 | `cloudflare-blog` | `discourse` | `technical-deep-dives` | `feed` | `https://blog.cloudflare.com/rss/` | discovery | 4 | 3 | `fx_cloudflare_blog` |
| 22 | `meta-engineering` | `discourse` | `technical-deep-dives` | `feed` | `https://engineering.fb.com/feed/` | discovery | 4 | 3 | `fx_meta_engineering` |
| 23 | `netflix-techblog` | `discourse` | `technical-deep-dives` | `feed` | `https://netflixtechblog.com/feed` | discovery | 4 | 3 | `fx_netflix_techblog` |
| 24 | `simonwillison` | `discourse` | `insights-and-opinions` | `feed` | `https://simonwillison.net/atom/everything/` | discovery | 6 | 3 | `fx_simonwillison` |
| 25 | `oneusefulthing` | `discourse` | `insights-and-opinions` | `feed` | `https://www.oneusefulthing.org/feed` | discovery | 6 | 3 | `fx_oneusefulthing` |

25 sources across **exactly 12 cells**. Sources 15–17 constitute
`config/harvest/watchlists/oss-milestones.v1.json`.

**`tests/test_taxonomy_config.sh`** fails when: any source object omits any of the nine fields; any
`source_id` or `fixture_id` is duplicated; any `url` is not absolute; any referenced fixture is
missing; the set of configured `(topic_slug, category_slug)` cells is **not exactly** the approved 12
categories (missing, extra or misspelled); or any `topic_slug`/`category_slug` fails to round-trip
through the slugifier from its display name.

**Robots constraints honoured pipeline-wide:** `export.arxiv.org` is `Disallow: /` (so the arXiv API
is unusable and `rss.arxiv.org` is used instead); `arxiv.org` requires `Crawl-delay: 15`;
`blogs.microsoft.com` requires `Crawl-delay: 10`.

**Source preflight.** Planning-time probes are informational only. `harvest.sh preflight-sources`
re-checks every configured source at the start of every live run — one bounded `GET` per source,
subject to `max_response_bytes`, with robots evaluated first — and records per source in the run
manifest: `{source_id, http_status, content_type, robots_allowed, crawl_delay, bytes, elapsed_ms,
result: "ok"|"adapter_error"|"infrastructure_error", reason}`. A failing source yields a recorded
`preflight_failed` for that source; it never silently drops the cell.

**Zero-result vs error taxonomy** (per source, per cell, in the run manifest — never conflated):
`zero_result`: `no_items_in_window` · `all_below_relevance_threshold` · `all_rejected_quality` ·
`all_duplicates_of_existing` · `category_exclusion_applied`.
`adapter_error`: `feed_parse_error` · `unexpected_content_type` · `empty_response` ·
`schema_mapping_failed` · `response_too_large` · `index_parse_failed`.
`infrastructure_error`: `robots_denied` · `http_timeout` · `http_5xx` · `dns_failure` ·
`lease_timeout` · `budget_exhausted` · `circuit_open` · `preflight_failed`.

Expected legitimate zero-results: **Case Studies** (measurable-KPI cases are rare in a 12-item
window) and **Product Discovery** (dev-tool exclusion). Relevance rules are never loosened.

### 3.1 The `seed` adapter — bounded index reader, not a crawler

Depth is **fixed at 1 and hard-coded, not configurable** — the property that stops it becoming a
crawler. `<a href>` anchors only via stdlib `html.parser`; no JS, no sitemap expansion.
`same_host_only: true` default; `path_prefix_allowlist: []` **fails closed** (empty list qualifies
nothing). `max_children` overflow dropped in document order. Robots evaluated for the index page and
independently for each child. Children resolved against the page base then canonicalized; in-page
duplicates collapse. Zero-result: `no_links_matched_allowlist`, `all_children_already_known`.
Errors: `index_fetch_failed`, `index_parse_failed`, `robots_denied_index`. Fixture asserts in-scope
links only, depth never exceeds 1 (a child that is itself an index is **not** expanded), and
deterministic overflow.

---

## 4 · Global cross-topic resolution phase

Per-cell workers cannot see other topics, so cross-topic policy is applied in an explicit
**single-writer phase after every topic artifact exists**.

```
1  plan_cells.py                    run manifest + cell list
2  harvest_cell.sh  × N   (parallel) per-cell registries        [isolated writer per cell]
3  merge_topic.sh   × 3   (parallel) per-topic artifacts        [one writer per topic]
   ───────────────────────── barrier: all topic artifacts present ─────────────────────────
4  build_content_index.py            global index keyed by content_id   [SINGLE writer]
5  resolve_cross_topic.py            applies cross_topic_policy         [SINGLE writer]
6  validate_candidate.py             schema-validate the complete set
7  stage → runs/<run_id>/candidate_output/
```

`resolve_cross_topic.py` sorts its input deterministically by `(content_id, topic_slug)` before
applying policy, so **output is independent of worker completion order and topic merge order**.

### 4.1 Record schema: discriminated union

`record_type: "full" | "cross_reference"`, enforced by JSON Schema `oneOf` with `if/then` on
`record_type` and `additionalProperties: false` on both branches:

- **`full`** — requires the complete field set (`title`, `summary`, `curation_reason`, scores,
  `verification_*`, …).
- **`cross_reference`** — requires **exactly** `{record_type, record_id, content_id, identity_url,
  topic, primary_category, duplicate_of, cross_reference_reason, harvest_run_id, discovered_at}` and
  **forbids** every full-record-only field.

A cross-reference is therefore structurally impossible to accept as a full record, and a partial
full record is structurally impossible to accept as a cross-reference.

### 4.2 Policies

Duplicate suppression **within** one topic is mandatory: one record per `identity_url` per topic.
Across topics, `config/harvest/precedence.v1.json → cross_topic_policy`:

| Policy | Behaviour |
|---|---|
| `cross_reference` **(default)** | Owning topic (highest precedence rank) emits a `full` record; each non-owning topic emits a `cross_reference` row |
| `multi_publish` | Every qualifying topic emits a `full` record carrying `multi_topic[]` and `multi_topic_reason` |
| `suppress` | Non-owning topics emit nothing; the manifest still records the suppression and reason |
| `link` | `full` records everywhere, joined only by `content_id`, no ownership designation |

The run manifest carries a `classification_decisions[]` entry for **every** content seen in more than
one topic: `content_id, topics[], owner_topic, policy_applied, reason, competing_categories[]`.
Nothing is suppressed without a manifest record explaining why.

`tests/test_taxonomy_cross_topic.sh` covers all four policies plus order-independence: shuffling cell
completion order and topic merge order must produce identical output.

---

## 5 · Protected baseline — immutable verification

The **commit is the authority**, not a regenerable file.

`scripts/harvest/verify_protected_baseline.sh` performs two independent checks:
1. each protected working-tree file's raw SHA-256 (`hashlib.sha256`) equals that of
   `git show 8865c54e2cc8d879410576f247baac4aea149f34:<path>`;
2. the committed `tests/fixtures/taxonomy/protected_sha256.txt` matches those same commit blobs.

Neither can be blessed by rerunning anything.

`scripts/harvest/gen_protected_baseline.sh` verifies the commit exists (`git cat-file -e`), verifies
every protected path matches it exactly, and **refuses to overwrite an existing baseline file unless
`--replace-baseline` is passed**. It runs **once, before implementation**, and its output is
committed. Acceptance command 0 is `verify_protected_baseline.sh` — verify, never regenerate.

Four separate checks for four separate purposes (`git hash-object` is *not* SHA-256 and is not used):

| Check | Proves |
|---|---|
| Raw SHA-256 vs commit blob | Byte-identical working-tree files |
| `git diff --exit-code -- <protected paths>` | Nothing tracked has changed |
| Recursive sorted `(relpath, sha256)` manifest over `state/matrix/**` | Directory contents *and* paths |
| `bash tests/test_matrix_harvest.sh` (64 assertions, unchanged) | Behavioural compatibility |

**Static matrix-reference check is scoped to production implementation files only** —
`src/harvest/**`, `config/harvest/**`, `schemas/harvest/**`, and `scripts/harvest/**` excluding the
boundary helpers (`verify_protected_baseline.sh`, `gen_protected_baseline.sh`). `tests/**` and
`docs/**` are excluded by construction, because the boundary test and the convergence note must name
the matrix path.

---

## 6 · Budgets, and enrichment in the smoke

| Budget | Default | Scope |
|---|---|---|
| `connect_timeout_sec` | 5 | DNS + TCP + TLS handshake |
| `read_timeout_sec` | 15 | Socket read of the response body |
| `request_timeout_sec` | 20 | Total wall clock for one request, connect + read inclusive |
| `max_response_bytes` | 8 MiB | Hard body cap → `adapter_error: response_too_large` |
| `adapter_max_requests` | 25 | One adapter in one cell, retries **and each redirect hop** included |
| `adapter_budget_sec` | 120 | One adapter in one cell, **including all pacing sleeps** |
| `cell_max_requests` | 60 | One cell across all its adapters |
| `cell_budget_sec` | 300 | One cell across all its adapters |
| `lease_wait_max_sec` | 60 | Max wait for a domain concurrency slot → `lease_timeout` |
| `smoke_budget_sec` | 1800 | Total wall clock for the 12-cell smoke |

A single `RequestBudget` object is threaded through the HTTP client; every attempt, retry and
redirect hop decrements the counters. Exceeding any budget raises a typed `budget_exhausted` error
and is recorded — never a silent truncation. Partial results are retained and labelled.

**Enrichment is disabled in the mandatory smoke** (`--no-enrich` is the default for `smoke`).
Candidate target pages are not fetched. Reason: arXiv mandates `Crawl-delay: 15`, so enriching 12
candidates from one arXiv source alone costs ≥180 s of mandatory pacing — infeasible under any honest
`adapter_budget_sec`. Fields that consequently remain unset, stated honestly in the artifact:
`content_hash: null` · `http_status: null` · `access_status: "not_checked"` ·
`verification_status: "unverified"` · `updated_at: null` · `author`/`language` null unless the feed
supplies them. `canonical_url` equals `identity_url` with no alias evidence. The adapter is still
fully validated, because the feed fetch exercises preflight → robots → lease → pacing → timeout →
byte cap → parse → canonicalize → classify → verify → dedupe → schema-validate → stage. Target-page
fetching is exercised deliberately by `linkcheck`, where arXiv's 15 s crawl-delay becomes a feature
of the global-limiter test.

`tests/test_taxonomy_budget.sh` proves the caps cannot be exceeded via retries, redirect chains,
enrichment, multiple sources in one cell, or all four combined.

---

## 7 · Transaction-safe publication promotion

Per-file `os.replace` is atomic for one file only, so the whole-set promotion uses a recoverable
journal on the flat published layout. (A versioned generations directory would change the required
`<topic_slug>__<category_slug>__harvest.json` published path contract, so the journal is used
instead.)

### 7.1 Promotion modes and change classes

Every path in a promotion falls into exactly one class:

| Class | Condition | `complete_set` | `partial_cells` |
|---|---|---|---|
| `replaced` | in both current and next set, hashes differ | replace | replace (only if the path belongs to a listed cell) |
| `added` | in next set only | add | add (only if in a listed cell) |
| `unchanged` | in both, hashes equal | skip | skip |
| `removed` | in current published set only | **delete** | **never deleted — preserved** |

The journal records `mode: "complete_set" | "partial_cells"` and, when partial, the explicit
`cells[]` list.

- **`complete_set`** — the candidate set is authoritative; `removed` files are deleted.
- **`partial_cells`** (`--allow-partial`) — only files belonging to the listed cells are touched.
  **Failed or absent cells keep their currently published files.** No deletion is ever performed in
  this mode, and the run is recorded as non-authoritative so it can never be mistaken for a complete
  set.

### 7.2 Protocol

1. **Prepare** — materialize and schema-validate the complete next set into
   `runs/<run_id>/promote_staging/`; compute after-hashes; classify every path. Refuse on any
   validation error, unresolved alias conflict, or infrastructure error (overrides:
   `--allow-alias-conflicts`, `--allow-partial`).
2. **No-op check** — if `replaced`, `added` and `removed` are all empty: exit 0 `no_changes` and
   write **no** journal. This is what makes a repeated `promote` idempotent.
3. **Journal** — atomically write `<publication_root>/.promotion_journal.json`:
   `{journal_version, run_id, generation, mode, cells[], state:"prepared",
   files:[{path, action, before_sha256|null, after_sha256|null}], rollback_dir, committed:[]}`.
4. **Before-images** — copy every currently published file that will be **replaced or removed** into
   `runs/<run_id>/promote_rollback/`, verifying each copy by hash. Also copy the current
   `publication_manifest.json`. `added` paths have no before-image and are recorded with
   `before_sha256: null`.
5. **Commit** — set `state:"committing"`, then walk the file list in deterministic path order:
   - `replaced` / `added` → `os.replace(staging → published)`
   - `removed` → `os.remove(published)` *(never reached in `partial_cells`)*

   After **each** individual operation, atomically append `{path, action}` to `journal.committed[]`.
   This is what makes every crash point recoverable.
6. **Manifest** — atomically write `<publication_root>/publication_manifest.json`: generation, the
   complete resulting file list with per-file SHA-256, source `run_id`, and `mode`.
7. **Finalize** — set `state:"committed"`, write `runs/<run_id>/promotion_receipt.json` (source run,
   per-file before/after SHA-256 and action, generation, mode, operator reason, timestamp), then
   remove the journal.

### 7.3 Rollback and resume

**`--rollback`** (valid from `prepared` or `committing`) walks `journal.committed[]` in **reverse**:

| Committed action | Rollback action |
|---|---|
| `replaced` | restore the before-image, verify by hash |
| `added` | **delete the newly added file** |
| `removed` | **restore the deleted file** from its before-image, verify by hash |

then restores the previous `publication_manifest.json` from its before-image and removes the journal.
Rollback is itself idempotent and safely re-runnable.

**`--resume`** (valid from `committing`) replays only entries **not** already in
`journal.committed[]`, in the same deterministic order, then continues at step 6.

### 7.4 Crash-point recovery

| Crash after | Journal state | Recovery |
|---|---|---|
| step 1 or 2 | no journal | Nothing mutated |
| step 3 | `prepared` | Nothing mutated; discard or resume |
| step 4 | `prepared` | Before-images possibly partial; regenerated on resume |
| mid step 5 | `committing` | Plain promote **refused**; `--resume` completes, `--rollback` restores |
| end of step 5, before 6 | `committing`, all files in `committed[]` | `--resume` writes manifest + receipt |
| step 6, before 7 | `committing` | `--resume` finalizes idempotently |
| step 7a, before 7b | `committed`, journal present | Next invocation finalizes: writes receipt once, removes journal |
| after step 7 | no journal | Done |

No state is ever left as an undocumented mixture of publication generations — the journal always
names exactly which state it is in.

### 7.5 Isolated promotion test

`promote` accepts `--publication-root <dir>` (default `data/harvested/`). The transaction test runs
the **same** promotion implementation — same journal, before-images, commit walk, rollback, resume,
manifest and receipt code — against `--publication-root "$TMPROOT/data/harvested"`, so **no fixture
data is ever written into the real tracked publication path**.

`tests/test_taxonomy_promote_txn.sh` fault-injects termination at each point in §7.4 and additionally
covers: `added`-only promotion · `removed`-only promotion in `complete_set` · a `partial_cells` run
proving unaffected published artifacts survive untouched · rollback restoring a deleted file ·
rollback deleting an added file · repeated no-op promotion writing no journal · exactly-once receipt
emission.

### 7.1 Live smoke stays staged — promotion is **not** a completion requirement

The bounded smoke is an infrastructure and integration test, not a discovery- or publication-quality
benchmark: it runs with enrichment off and deliberately produces unverified fields.

- Acceptance commands 0–20 are mandatory. **Promoting live smoke output into `data/harvested/` is
  not required for task completion.**
- Live smoke candidate output remains staged in `runs/<run_id>/candidate_output/` for review, and the
  smoke run's manifest is marked `publication_eligible: false`, which `promote` checks and honours.
- Promotion is tested against a **fixture-backed, fully verified candidate run**
  (`tests/fixtures/taxonomy/promote_candidate/`) — deterministic, enrichment-complete, no unverified
  fields — and always with `--publication-root` pointed at a temporary directory (§7.5), never at the
  real `data/harvested/`.
- A later *production* promotion requires: a reviewed run ID · schema validity · zero unresolved
  alias conflicts · zero infrastructure errors unless explicitly overridden · an operator reason
  describing the review. The reason `"initial deterministic smoke"` is explicitly rejected for
  production publication.

---

## 8 · Live-rerun comparison semantics

Two **live** runs must match on **identity and idempotency invariants only**:

`record_id` · `content_id` · `identity_url` · `discovered_at` (for records present in both) · `topic`
· `cell_id` · `source_id` · absence of duplicate insertion (no two records share a `record_id` within
a topic) · schema validity.

Everything else is a **reported content change**, emitted by `compare-runs` in a `content_changes[]`
section, and is **not** an idempotency failure — real feeds legitimately correct these between runs:
`title` · `author` · `published_at` · `summary` · `tags` · `primary_category` · `classification.*` ·
`curation_reason` · all scores · `canonical_url` · `url_aliases[]` · `verification_status` ·
`access_status` · `http_status` · `content_hash` · `last_checked_at` · `updated_at` ·
`harvest_run_id` · `link_history[]` · artifact `generated_at` / `last_merged_at`.

**Fixture tests continue to require complete byte-identical output** (recorded fixtures, fixed clock
via `HARVEST_CLOCK_UTC`, fixed `HARVEST_RUN_ID`, deterministic sort `(topic, primary_category,
record_id)`, stable key order) — no field is exempt there, because the fixture clock fixes them all.

---

## 9 · Python support — tested versions only

- **Supported and tested: CPython 3.13.x on win32.** This is the only interpreter the task is
  validated on. No 3.9–3.12 claim is made.
- The actual acceptance-run interpreter is recorded verbatim in the final report (currently
  `Python 3.13.9`; `python3` on this machine resolves to the Windows Store stub, so all commands use
  `python`).
- `requirements.txt`: `jsonschema==4.26.0` — exact pin. `constraints.txt`: the transitive set
  (`attrs`, `jsonschema-specifications`, `referencing`, `rpds-py`) pinned exactly, resolved on
  3.13.9 and labelled as such.
- `harvest.sh preflight` enforces `(3, 13) <= sys.version_info < (3, 14)` and
  `importlib.metadata.version("jsonschema") == "4.26.0"` exactly. Missing dependency → exit 2 with an
  actionable message. Version mismatch → exit 2, relaxable only via explicit `--allow-dep-drift` /
  `--allow-python-drift`, which warn and record `python_unverified: true` in the run manifest.
  Absence is never tolerated. There is no fallback validator.
- `docs/harvest/SETUP.md` states that other minor versions are unverified, and that supporting them
  requires adding a test-matrix run per version plus environment markers where transitive
  requirements differ.

---

## 10 · Runtime-namespace ignore, and the untracked baseline

### 10.1 Runtime ignore — one narrow authorized `.gitignore` line

Probed before deciding:

```
$ git check-ignore -v state/taxonomy_harvest/probe            -> rc=1, no matching rule
$ git check-ignore -v state/taxonomy_harvest/runs/x/manifest.json -> rc=1, no matching rule
# controls proving the probe works:
$ git check-ignore -v state/logs/x.jsonl   -> .gitignore:20:state/logs/
$ git check-ignore -v state/locks/y.lock   -> .gitignore:27:state/locks/
```

The existing rules do **not** cover the new namespace, so exactly **one** narrow existing-file
modification is authorized — appending a single line to `.gitignore`:

```gitignore
/state/taxonomy_harvest/
```

This is **ownership of the new pipeline's runtime namespace, not cleanup**. No rule is added for
`.scratch_ax/`, `state/_*`, the root log, or any other pre-existing noise.

`tests/test_taxonomy_staging_isolation.sh` asserts `git check-ignore -q state/taxonomy_harvest/probe`
**succeeds** after the change — the plan never claims the directory is ignored without proving it.

### 10.2 Untracked baseline — already captured, before any repository edit

Captured **at plan time, before the first edit**, at commit
`8865c54e2cc8d879410576f247baac4aea149f34`, using
`git ls-files --others --exclude-standard -z` so files inside untracked directories are enumerated
individually. **508 files** — the 62 `git status --short` entries expand to 508 because
`.scratch_ax/` alone holds 445. Format `<sha256>  <bytes>  <relpath>`, sorted deterministically,
with a provenance header (repo, commit, capture timestamp, enumeration command, file count).

The snapshot lives **outside the repository** in the session scratchpad. Once the task scaffold
exists it is **copied verbatim** to `tests/fixtures/taxonomy/untracked_baseline.txt` and committed.

`scripts/harvest/capture_untracked_baseline.sh` is written later and may **reproduce or verify** that
format (`--verify` mode); it **must not claim to be the session-start capture**, and it refuses to
overwrite an existing baseline without `--replace-baseline`.

`.gitignore` is otherwise untouched: the 508 pre-existing untracked files are out of scope.

- `tests/test_taxonomy_staging_isolation.sh` asserts, **scoped — not a clean-repo requirement**:
  1. tracked publication paths (`data/harvested/**`) unchanged by acceptance commands 1–20;
  2. protected files unchanged (raw SHA-256 vs commit `8865c54e…`);
  3. task-owned directories contain only expected paths;
  4. **no new untracked path appears outside the approved task-owned directories**;
  5. every pre-existing untracked path in the baseline is still present and byte-identical where the
     file is readable and stable (directories checked for existence; `.scratch_ax/` checked as a path
     set).
- The test explicitly does **not** require `git status` to be empty.
- Cleanup / gitignoring of the pre-existing scratch noise is recorded in `docs/harvest/TODO.md` as a
  **separate follow-up item, out of scope for this task**.

---

## 11 · AX migration mapping (confirmed against the live registry)

Inspected: `state/ax_case_harvest_registry.json` has **exactly one URL field**, `source_url`, all 231
unique, and its values are the case's **own primary pages** (`https://www.uber.com/en-HR/blog/genie-
ubers-gen-ai-on-call-copilot/`, `https://github.blog/2023-09-06-how-to-build-an-enterprise-llm-
application-lessons-from-github-copilot/`). `discovery.found_via[]` holds `{hit_id, platform}` only —
**no URL**. Per `agents/stage1/ax_case_harvest_extractor.md` this field is the page the case was
extracted from, i.e. the item's own page.

| New field | ← Legacy | Note |
|---|---|---|
| `target_url` | `source_url` | **verbatim, unmodified** |
| `identity_url` | `canonicalize_string(target_url)` | immutable |
| `canonical_url` | = `identity_url` | no verification performed at migration time |
| `source_url` | **`null`** | the legacy schema has no separate feed, index, search or citing URL |
| `title` | `source_title` | |
| `publisher` | `source_domain` | |
| `topic` | const `Cases` | |
| `primary_category` | const `Case Studies` | |
| `record_type` | const `full` | |
| `published_at` | `publication_date` | `"unknown"` → `null` |
| `discovered_at` | `discovery.first_seen_at` | |
| `summary` | composed from `workflow_before` / `workflow_after` / `ai_system_or_tool` | |
| `curation_reason` | composed from `measurable_kpi` / `kpi_value` / `evidence_quote` | |
| `tags` | normalized `[industry, ai_system_or_tool]` | |
| `verification_status` | `verification_status` (`verified`→`fetched`, `snippet-only`→`snippet_only`) | renamed: the legacy value only means the fetch succeeded |
| `legacy_ids[]` | `[{system:"ax_case_harvest_registry", id:case_id, key:case_key}]` | |
| `provenance.raw` | **the complete original object, original field names intact** | including `source_url` under its original name |
| `provenance.discovered_via[]` | `discovery.found_via[]` | `{hit_id, platform}` — discovery metadata, **never treated as a URL** |
| `domain_fields` | `company`, `industry`, `workflow_before`, `workflow_after`, `ai_system_or_tool`, `measurable_kpi`, `kpi_value`, `evidence_quote`, `transformation_date`, `confidence`, `corroboration_count`, `conflicting_evidence_log` | surfaced **and** retained in `provenance.raw`; nothing dropped |

`"unknown"` → `null` everywhere, with the original retained in `provenance.raw`.

**Suspicious-URL guard.** `looks_like_index_or_search()` flags a sole legacy URL whose host is a
search engine (`google.`, `bing.`, `duckduckgo.`, `baidu.`, `yandex.`, `search.`), whose path/query
indicates search (`/search`, `?q=`, `?query=`, `?s=`), whose path is a feed (`/feed`, `/rss`,
`/atom`), or which is an index/list page (`raw.githubusercontent.com/**/README.md`, `/awesome-`,
`/tag/`, `/category/`, `/page/<n>`).

Behaviour — **never silently reinterpret or rewrite a URL**:
- the record is reported **unmappable** with `rejection_reason: ambiguous_legacy_url` plus the
  matched rule id; it is **not** migrated;
- the **complete rejected-record list** appears in the dry-run report;
- `tests/test_taxonomy_migration.sh` **fails** unless every rejected record is explicitly reviewed
  (listed in `config/harvest/migration_overrides.v1.json` with a reviewer note) or
  `--allow-unmappable` is supplied;
- a dedicated test fails if `identity_url` is ever derived from a feed, search, citing or index URL
  rather than the case's target page.

Expected against the current corpus: **0 rejections of 231** — but the count is asserted, not assumed.

`migrate.sh ax-cases` defaults to **dry-run**; `--apply` is explicit, expects exactly **231** source
records, and fails loudly on any other count unless `--expect-count N` is given. Apply writes only
under `state/taxonomy_harvest/migrations/<ts>__ax_cases/` and the run's `candidate_output/`;
promotion remains a separate explicit step (§7). It never opens the source registry for writing,
produces zero Agent/MCP/Prompt/Skill migration, and creates zero Product Discovery classifications
from entity records.

`migrate.sh entity-assess` is strictly read-only and produces
`docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md`: counts by topic and entity_type, schema
versions and key fields, candidate destination taxonomies, fields that cannot be mapped safely,
duplicate and `entity_id`-stability risks (per `docs/entity_id_collision_note.md`, `entity_id` is not
globally unique), and a recommended follow-up plan. The non-migration is recorded explicitly in the
migration manifest and the final report.

---

## 12 · Unchanged from Revision 3

Global cross-process per-domain rate limiting (`mkdir`-atomic slots, shared `next_allowed_at`,
pipeline-wide `Retry-After`, stale-lease policy with fail-safe liveness) · HTTP baseline vs staged
features · the `github_meta.py` reuse audit and per-primitive duplication ledger · the matrix
boundary proofs · failed-worker and stale-lock recovery tests · implementation stages 0–10.

---

## 13 · Files allowed and prohibited from changing

**Allowed — created:**
`config/harvest/**` · `schemas/harvest/**` · `src/harvest/**` · `scripts/harvest/**` ·
`tests/harvest/**` · `tests/test_taxonomy_*.sh` · `tests/fixtures/taxonomy/**` · `docs/harvest/**` ·
`requirements.txt` · `constraints.txt` · `data/harvested/**` *(only ever via `promote`)*

**Allowed — modified (exactly three existing files, each narrowly):**

| File | Permitted change |
|---|---|
| `scripts/validate_task.sh` | Add the new `test_taxonomy_*.sh` entries to the case table and `ISOLATED[]`. No other edit. |
| `CLAUDE.md` | Add one section pointing at the new pipeline. No other edit. |
| `.gitignore` | Append **exactly one line**: `/state/taxonomy_harvest/`. Justified by `git check-ignore` (§10.1). No other rule, and specifically no rule for `.scratch_ax/`, `state/_*` or the root log. |

**Runtime only, gitignored:** `state/taxonomy_harvest/**`

**Prohibited from changing:**

| Path | Reason |
|---|---|
| `scripts/run_matrix.sh`, `matrix_spec.py`, `merge_matrix.sh`, `expand_queries_cell.sh`, `harvest_matrix_cell.sh` | Protected matrix path |
| `tests/test_matrix_harvest.sh`, `tests/test_parallel_harvest.sh` | Mandatory regression gates, byte-identical |
| `scripts/lib/lockdir.sh`, `scripts/lib/clean_json.sh`, `scripts/github_meta.py`, `scripts/merge_entity_registry.sh` | Reused unmodified; audited on that basis |
| `state/matrix/**`, `state/entity_registry.json`, `state/BuildingBlocks_*.json`, `state/ax_case_harvest_registry.json`, `state/visited_url_ledger*.json` | Production data; read-only to this task |
| `.gitignore` — anything beyond the single `/state/taxonomy_harvest/` line | Pre-existing scratch noise is a separate follow-up |
| All other existing `scripts/**`, `agents/**`, `tests/**`, `config/*.json`, `pipeline.config.sh` | Not in scope |
| All 508 pre-existing untracked paths | Baseline-verified, must remain byte-identical |
| The real `data/harvested/` during acceptance commands 0–23 | Promotion tests use `--publication-root` in a temp dir |

---

## 14 · Acceptance commands

```bash
set -euo pipefail
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"

# recursive pre-image of the real publication path, for the isolation asserts
PUBHASH_BEFORE="$(mktemp)"; PUBHASH_AFTER="$(mktemp)"
python scripts/harvest/hash_tree.py data/harvested > "$PUBHASH_BEFORE"

# === 0. verify (never regenerate) the protected baseline ====================
bash scripts/harvest/verify_protected_baseline.sh
git check-ignore -q state/taxonomy_harvest/probe   # proves the runtime namespace is ignored
bash scripts/harvest/harvest.sh preflight
python -c "import sys, importlib.metadata as m; print(sys.version); print(m.version('jsonschema'))"

# === 1. configuration completeness and cell-set exactness ===================
bash tests/test_taxonomy_config.sh

# === 2. fixture determinism (byte-identical, fixed clock) ===================
bash tests/test_taxonomy_fixture_determinism.sh

# === 3. schema validation, including the record_type discriminated union ====
bash tests/test_taxonomy_schema.sh

# === 4. identity, canonicalization, alias trust and alias conflicts =========
bash tests/test_taxonomy_identity.sh

# === 5. HTTP baseline: robots, redirects, timeouts, retries =================
bash tests/test_taxonomy_http.sh

# === 6. global cross-process per-domain concurrency and spacing =============
bash tests/test_taxonomy_domain_throttle.sh

# === 7. request-count and wall-clock budget enforcement =====================
bash tests/test_taxonomy_budget.sh

# === 8. adapters, including the bounded seed adapter ========================
bash tests/test_taxonomy_adapters.sh

# === 9. classification precedence, dedupe, cross-topic resolution ===========
bash tests/test_taxonomy_classify.sh
bash tests/test_taxonomy_dedupe.sh
bash tests/test_taxonomy_cross_topic.sh

# === 10. cell worker, concurrency, failed-worker and stale-lock recovery ====
bash tests/test_taxonomy_cell.sh
bash tests/test_taxonomy_concurrency.sh
bash tests/test_taxonomy_recovery.sh

# === 11. transaction-safe promotion, fault-injected =========================
bash tests/test_taxonomy_promote_txn.sh

# === 12. matrix boundary ====================================================
bash tests/test_taxonomy_matrix_boundary.sh
git diff --exit-code -- \
  scripts/run_matrix.sh \
  scripts/matrix_spec.py \
  scripts/merge_matrix.sh \
  scripts/expand_queries_cell.sh \
  scripts/harvest_matrix_cell.sh \
  tests/test_matrix_harvest.sh \
  tests/test_parallel_harvest.sh

# === 13. the existing suites, unchanged (mandatory gate) ====================
bash tests/test_matrix_harvest.sh
bash tests/test_parallel_harvest.sh

# === 14. staging isolation and untracked-baseline scoping ===================
bash tests/test_taxonomy_staging_isolation.sh

# === 15. AX migration: dry-run, then apply twice (idempotency) ==============
bash scripts/harvest/migrate.sh ax-cases --dry-run
bash scripts/harvest/migrate.sh ax-cases --apply
bash scripts/harvest/migrate.sh ax-cases --apply
bash tests/test_taxonomy_migration.sh

# === 16. entity registry: read-only assessment, no mutation =================
bash scripts/harvest/migrate.sh entity-assess

# === 17. full offline suite (~25 min; includes 13 and every new test) =======
bash scripts/validate_task.sh --all

# === 18. live source preflight (bounded; re-checked every live run) =========
bash scripts/harvest/harvest.sh preflight-sources

# === 19. bounded deterministic live smoke, 12 categories, enrichment OFF ====
bash scripts/harvest/harvest.sh smoke --max-candidates 12 --max-accepted 5 --no-enrich
RUN_ID_1="$(cat state/taxonomy_harvest/LATEST_RUN_ID)"
bash scripts/harvest/harvest.sh validate --run-id "$RUN_ID_1"

# === 20. second live smoke + normalized rerun comparison ====================
bash scripts/harvest/harvest.sh smoke --max-candidates 12 --max-accepted 5 --no-enrich
RUN_ID_2="$(cat state/taxonomy_harvest/LATEST_RUN_ID)"
bash scripts/harvest/harvest.sh validate --run-id "$RUN_ID_2"
bash scripts/harvest/harvest.sh compare-runs \
  --baseline "$RUN_ID_1" \
  --candidate "$RUN_ID_2" \
  --normalize

# === 21. link-check (creates its own run; captured separately) ==============
bash scripts/harvest/harvest.sh linkcheck --run-id "$RUN_ID_2" --sample 20
RUN_ID_LINKCHECK="$(cat state/taxonomy_harvest/LATEST_RUN_ID)"
bash scripts/harvest/harvest.sh validate --run-id "$RUN_ID_LINKCHECK"

# === 22. prove tracked publication output is STILL unchanged ================
bash scripts/harvest/harvest.sh diff --run-id "$RUN_ID_2"
git diff --exit-code -- data/harvested/
test -z "$(git status --porcelain -- data/harvested/)"
python scripts/harvest/hash_tree.py data/harvested > "$PUBHASH_AFTER"
diff -u "$PUBHASH_BEFORE" "$PUBHASH_AFTER"

# === 23. promotion, on the VERIFIED FIXTURE, into an ISOLATED root ==========
#         (live smoke output stays staged; promoting it is NOT required)
PROMO_ROOT="$(mktemp -d)/data/harvested"
mkdir -p "$PROMO_ROOT"
bash scripts/harvest/harvest.sh promote \
  --run-id fixture-promote-candidate \
  --fixture tests/fixtures/taxonomy/promote_candidate \
  --publication-root "$PROMO_ROOT" \
  --reason "acceptance: transaction-safe promotion on verified fixture"
bash scripts/harvest/harvest.sh promote \
  --run-id fixture-promote-candidate \
  --fixture tests/fixtures/taxonomy/promote_candidate \
  --publication-root "$PROMO_ROOT" \
  --reason "acceptance: repeat promote must be a no-op"

# real publication path must STILL be untouched after promotion testing
test -z "$(git status --porcelain -- data/harvested/)"
python scripts/harvest/hash_tree.py data/harvested > "$PUBHASH_AFTER"
diff -u "$PUBHASH_BEFORE" "$PUBHASH_AFTER"

# === 24. opt-in model-search smoke, 1-2 cells, AFTER everything above =======
bash scripts/harvest/harvest.sh smoke-model \
  --cells cases__case-studies,discourse__insights-and-opinions \
  --max-candidates 6
RUN_ID_MODEL="$(cat state/taxonomy_harvest/LATEST_RUN_ID)"
```

**Completion requires** commands 0–22 green, plus 23. Command 24 is opt-in. Promoting *live smoke*
output into `data/harvested/` is **not** a completion requirement — the live candidate set stays
staged for review.
