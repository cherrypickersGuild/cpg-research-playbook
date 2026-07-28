# Handoff — Stage 2.5 complete, Stage 3 not started

**Date:** 2026-07-28 · **Repo:** `C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4` · **Branch:** `main`

```text
verified_code_checkpoint:    46ab67cde36acf4b2b403d17d4bc589eff3d5cb7   Stage 2.5 implementation
documentation_approval:      79389e1460a13492fcdc42ab8c96af5313ad9bca   approved plan
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  local only — nothing pushed to origin/main
stage_2_5:                   COMPLETE
stage_3:                     NOT STARTED — blocked, see §18
```

`verified_code_checkpoint` names the commit whose **code** was verified. Committing this handoff
advances `HEAD` without advancing the code checkpoint; the code checkpoint stays `46ab67c` until
Stage 3 code lands.

---

## 1 · State in one line

Stages 0–2 and Stage 2.5 are **implemented and tested — 387 assertions across 14 suites, all green**
(199 existing + 188 new). Stage 3 has **not started**. **No live source request, harvest, migration
application, refresh, link-check or promotion has been performed.** Nothing has been pushed.

| | |
|---|---|
| Total passing assertions | **387** (Stage 0–2: **199**, Stage 2.5: **188**) |
| Protected baseline | **passing** — 18 files byte-match Git's rendering of `8865c54e…` |
| Exact 12-cell taxonomy | **unchanged**; `APPROVED_CELLS` still 12; facets create no cells |
| Tracked modifications after `46ab67c` | **zero** |
| Untracked files | exactly the original **508**, all byte-unchanged |
| Pushed | **nothing** |

---

## 2 · Commit chain

| Commit | What it is |
|---|---|
| `8865c54e2cc8d879410576f247baac4aea149f34` | implementation-start anchor; the protected baseline is measured against **this** commit and never moves |
| `0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e` | Stage 0–2 implementation (199 assertions) |
| `3b85a8102fb89ae0585ef0fc080f518238e4c1bc` | approved facet **design** (`DOMAIN_FACETS_PROPOSAL.md` revision 4) |
| `79389e1460a13492fcdc42ab8c96af5313ad9bca` | approved implementation **plan**, D1–D10 corrections, DV-1…DV-6 |
| `46ab67cde36acf4b2b403d17d4bc589eff3d5cb7` | **Stage 2.5 implementation** — 36 files, 6650 insertions(+), 20 deletions(−) |

`DOMAIN_FACETS_PROPOSAL.md` and `STAGE_2_5_IMPLEMENTATION_PLAN.md` are **frozen design and approval
artifacts**. They were implemented by `46ab67c` with **no plan deviations**, except the separately
approved request-key correction described in §9. Do not rewrite their historical status.

---

## 3 · Files created and modified by `46ab67c`

**Created — 32**

| Purpose | Files |
|---|---|
| Vocabulary config (5) | `config/harvest/facets/{industries,business-functions,use-case-types}.v1.json` · `config/harvest/facets/legacy_industry_map.v1.json` · `config/harvest/coverage_targets.v1.json` |
| Schemas (5) | `schemas/harvest/{facet_vocabulary,facets.generated,candidate_pool,discovery_lane,coverage_report}.v1.json` |
| Runtime code (5) | `src/harvest/{facets,pool,coverage,scheduler,request_key}.py` |
| Tooling (2) | `scripts/harvest/{gen_facet_schema,check_facets}.py` |
| Test wrappers (7) | `tests/test_taxonomy_{facets,facet_ambiguity,facet_identity,facet_states,customer_interaction,pool,coverage}.sh` |
| Test suites (7) | `tests/harvest/test_{facets,facet_ambiguity,facet_identity,facet_states,customer_interaction,pool,coverage}.py` |
| Reference doc (1) | `docs/harvest/FACET_VOCABULARY.md` |

**Modified — 4**

| File | Change |
|---|---|
| `schemas/harvest/record.v1.json` | `case_facets` property, 5 new `$defs`, the applicability `allOf` **inside `$defs/full_record`**, 5 added `rejection_reason` values |
| `schemas/harvest/run_manifest.v1.json` | optional `rounds[]`, `coverage[]`, `lane_quality[]`, `request_accounting` — none added to `required` |
| `src/harvest/records.py` | one keyword-only `case_facets=None`, omitted when falsy |
| `docs/harvest/TODO.md` | Stage 2.5 marked complete |

**Deliberately NOT modified:** `scripts/harvest/check_config.py` (byte-unchanged — DV-1) ·
`src/harvest/{urlkey,slug,schema,budget,domainlease,httpclient}.py` · every existing test ·
`config/harvest/topics/*` · `schemas/harvest/taxonomy.v1.json` · `.gitignore` (still exactly one
added line vs the anchor).

---

## 4 · The six approved deviations, as implemented

| ID | Decision | How it landed |
|---|---|---|
| **DV-1** | `check_config.py` stays byte-unchanged; facet validation lives in `check_facets.py` | It holds `APPROVED_CELLS` (the specification the config is checked *against*) and its suite asserts the literal `cells=12` / `sources=25`. Two independent specifications, two gates. Verified byte-unchanged in the committed tree |
| **DV-2** | `records.make_full_record` gains one keyword-only `case_facets=None` | Emitted only when truthy, matching the existing `legacy_ids`/`link_history`/`domain_fields` idiom. `make_full_record()` and `make_full_record(case_facets=None)` are byte-identical; `{}` omits the key |
| **DV-3** | A 5th schema, `facet_vocabulary.v1.json` | Otherwise the three vocabularies would be the only config in the repo with no schema |
| **DV-4** | Use-case tiers are **10 / 11 / 1 = 22** | The "10/10/1" in earlier drafts sums to 21 and cannot describe 22 approved values |
| **DV-5** | The applicability `allOf` sits **inside `$defs/full_record`** | At the document root it would bind `cross_reference_record` too, whose closed property set cannot carry `case_facets` — making every `cases__domain-applications` cross_reference row unsatisfiable. A regression test asserts such a row is still valid |
| **DV-6** | `vocabulary_versions` is **required** inside `case_facets` | The §11 runtime version-match guardrail is unenforceable when the key may be absent |

---

## 5 · D7 — the five reporting states

Mutually exclusive, exhaustive, derived from the **complete record** (`record_type`, `topic`,
`primary_category`, `case_facets`, and legacy provenance) — **not** from `case_facets` alone.

**Scope:** applicable = `record_type == "full"`. **`cross_reference` rows are excluded from all five**
and `reporting_state()` returns `None` for them.

**Precedence — first match wins:**

| # | State | Condition |
|---:|---|---|
| 1 | `unmapped_legacy_value` | any `unresolved[]` entry has that state |
| 2 | `not_enriched` | `case_facets` absent or `null` |
| 3 | `facet_complete` | `classification_state == "resolved"` |
| 4 | `facet_partial` | unresolved, ≥1 axis populated |
| 5 | `unresolved` | unresolved, nothing populated |

The order is total: after rule 0 removes non-`full` records, rule 1 fires or not; if not,
`case_facets` is absent/null (rule 2) or present, in which case the schema constrains
`classification_state` to `resolved` (rule 3) or `unresolved`, which rules 4 and 5 partition. The five
counts always sum to `applicable_full_records`.

`unmapped_legacy_value` ranks **first** — it outranks even `facet_partial`, so a record whose
functions were populated but whose industry came from an unmapped legacy string is still reported as
`unmapped_legacy_value`, because that is the fact a reviewer must act on. It never folds into
`unresolved`.

**Publication eligibility is derived, never persisted.** `facets.is_publication_eligible(record)`:
a `cases`/`domain-applications`/`full` record is eligible **only** in state `facet_complete`; the
other four are withheld. **Withheld is not rejected** — the record keeps its `record_id`, carries no
`rejection_reason`, and stays auditable. `record.v1.json` gained **no** eligibility property; a test
asserts `publication_eligible`, `publication_withheld`, `reporting_state` and `facet_state` are all
absent from `full_record.properties`. `coverage_report.v1.json` publishes the per-record state and
flag keyed by `record_id` for consumers that would rather not re-derive them.

---

## 6 · Vocabulary totals

```text
industries.v1.json          18 entries    7 priority ·  8 standard · 3 record_only
business-functions.v1.json  19 entries   10 priority ·  8 standard · 1 record_only
use-case-types.v1.json      22 entries   10 priority · 11 standard · 1 record_only
```

Counts and tier splits are **derived from the files** by `facets.tier_counts()` and asserted against
the hard-coded specification in `check_facets.py` — deriving the expectation from the file being
checked would make the check vacuous.

Load-bearing vocabulary facts: no bare `operations` slug on any axis (both
`supply-chain-operations` and `production-operations` are priority) · `legal-risk-compliance`
(function) is separate from `information-security` (function, narrowed to SOC/threat ops,
vulnerability management, monitoring, incident response, identity) and from `risk-fraud-compliance`
(use case — the two co-occur by design and are not a duplicate) · `customer-interaction` is priority
and strictly external, `conversational-assistant` is standard and includes internal copilots ·
`technology-software`, `cross-industry` and `other-unclear` are `record_only` · `other-unclear` is
the **single** slug shared by all three axes and the only one exempt from cross-axis disjointness.

---

## 7 · Generated schema: source of truth and drift

`config/harvest/facets/*.v1.json` are the **single source of truth**.
`schemas/harvest/facets.generated.v1.json` is derived and **never hand-edited** — it carries the real
enums so a published artifact validates standalone for consumers with no repository access.

Seven guardrails: deterministic output (sorted keys, indent 2, LF, no timestamp) · a header naming
the generator and stating "DO NOT HAND-EDIT" · per-source `config_version`, `vocabulary_version` and
**SHA-256** · `--check` regenerates in memory and diffs · a test that regenerates into a **temp dir**
and byte-compares (never trusting the cached registry) · `mkstemp` + `os.replace` **inside** the
destination directory · `check_facets.py` compiles the file standalone as its first check.

**Why that last pair matters:** `src/harvest/schema.py::_build_registry()` loads **every** `*.json`
in `schemas/harvest/` into one module-global cached registry, keyed by both filename and `$id`. A
malformed or duplicate-`$id` file there breaks **all** suites, not just its own. Two tests pin this:
a truncated generated file is reported (naming the registry coupling), and a hand-edited one is
reported as DRIFT.

Regeneration workflow: edit the vocabulary → bump its `vocabulary_version` →
`python scripts/harvest/gen_facet_schema.py` → `python scripts/harvest/check_facets.py` →
run `test_taxonomy_facets.sh` and `test_taxonomy_facet_ambiguity.sh`.

---

## 8 · `case_facets` schema and identity independence

`full_record.properties.case_facets` — `["object","null"]`, `additionalProperties:false`, required
inner keys `facets_version`, `vocabulary_versions` (all three sub-keys required), `classification_state`,
`industry`, `business_functions` (≤4), `use_case_types` (≤4); optional `unresolved[]`. Five new
`$defs`: `facet_slug` (shape only), `facet_evidence`, `facet_axis_single` (≤2 secondary),
`facet_axis_multi`, `facet_unresolved`.

Applicability, via `allOf` **inside `$defs/full_record`**:

| Cell | `case_facets` |
|---|---|
| `cases`/`domain-applications` | **required**, and must be an object (explicit `null` refused) |
| `cases`/`case-studies` · `cases`/`product-discovery` | optional |
| `research-and-models`/* · `discourse`/* | must be **absent or null** |
| any `cross_reference` row | forbidden by the closed property set — and the row stays valid |

`case_facets` is **not** in `full_record.required`, so the Stage 1 assertion that every required
field is genuinely required is untouched.

**Identity independence is proved twice.** Structurally: add / change / remove / null `case_facets`
leaves `record_id`, `content_id`, `identity_url`, `canonical_url`, `cell_id`, the artifact filename
and the sort key byte-identical. Statically: `urlkey.py` and `slug.py` must not contain the strings
`facet`, `case_facets`, `industry`, `business_function` or `use_case`, and
`urlkey.record_id`/`content_id` must take only `(topic_slug, identity_url)` / `(identity_url)`.

---

## 9 · Request-key policies *(the one separately approved correction)*

`source_request_key(...)` hashes
`source_id | url-without-query | method | canonical_query | body_hash | significant_headers |
adapter_mode | canonicalization_version`, truncated to 16 hex.

**Query normalization is opt-in per logical request.**

```python
QUERY_ORDER_PRESERVE = "preserve"                                   # DEFAULT, every adapter
QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE = "sort-distinct-keys-stable" # explicit opt-in only
```

- **`preserve`** keeps the complete query-pair sequence, repeated-key multiplicity, repeated-key
  value order and blank values. **This is the default for every adapter and every source**, and it is
  what every real caller uses today.
- **`sort-distinct-keys-stable`** normalizes ordering **between distinct keys only**, via
  `sorted(pairs, key=lambda pair: pair[0])` — key-only and stable, so the relative order of repeated
  occurrences of the same key survives, as do multiplicity and blank values.
- **Adapter class never enables sorting.** `ORDER_INSIGNIFICANT_ADAPTERS` was deleted; `adapter` and
  `adapter_mode` select nothing about query handling. `jsonapi` behaves exactly like `feed`,
  `sitemap`, `seed` and `model_search`.
- The policy is **keyword-only**, so it cannot be passed by accident, and an unknown value raises
  `RequestKeyError` rather than silently defaulting.
- No generic `sort` or `order-insignificant` mode is exposed — a test asserts those names are absent,
  because either could later be read as licence to sort on `(key, value)` and merge ordered repeats.

**What this prevents:** `?filter=region&filter=date` and `?filter=date&filter=region` receive
different keys and therefore **two** logical owners. Reordering would have merged them into one owner
and one immutable snapshot, silently discarding one response.

*History, for the record:* the first implementation sorted on adapter class and on `(key, value)`.
That was caught by the pre-commit verification, reported before staging, and corrected under separate
approval. `canonicalization_version` is in the key material so a canonicalization config bump cannot
silently change keys. `candidate_key()` takes **no** policy parameter — it is a dedup key, never an
identity claim.

---

## 10 · Logical ownership versus HTTP attempts

**Asserted (logical):** one source-fetch owner per `source_request_key` per run · one target-fetch
owner per canonical candidate per run · one extraction owner per accepted response body · one record
per `(topic, identity_url)`.

**Observed (physical):** `http_attempts`, `retries`, `redirect_hops`, `conditional_revalidations` —
charged to the existing Stage 2 `RequestBudget`, which is unmodified.

Pinned by test: three lanes sharing a feed ⇒ **1 owner, 1 attempt**; a 301 hop plus one 503 retry on
that feed ⇒ **1 owner, 3 attempts, budget charged 3**. A page found by four lanes ⇒ one target-fetch
owner and one extraction owner, with all four `lane_id`s preserved on the survivor.

Early deduplication happens on `urlkey.canonicalize_string(target_url)` **before** extraction. Pool
output is byte-stable under shuffled lane ordering across 12 seeds.

---

## 11 · Immutable run-scoped snapshots

Per `source_request_key`: the first logical fetch may use `ETag`/`Last-Modified` carried over from a
**previous** run; a `200` **or** `304` establishes the snapshot; every later lane and every later
adaptive round reuses it; **no later round may revalidate or replace it.** A second
`establish_snapshot` for the same key raises `SnapshotExists`. A changed source requires a **new
run**, or an explicit `refresh`/`linkcheck`.

*Why:* mid-run revalidation would make output depend on when a round happened to execute, so two runs
over identical inputs could diverge — destroying the determinism the fixture suite asserts.

---

## 12 · Case Studies is report-only in v1

`cases`/`case-studies` and `cases`/`product-discovery` are schema-optional and **never gated**. Their
five state counts are computed and reported (`coverage[].gated == false`) but block neither migration
nor publication. Another existing gate — `rejection_reason`, the run-level `publication_eligible`
flag, a link-check outcome — may still withhold such a record; the facet predicate does not override
it. A test builds 231 `case-studies` records all in the worst facet state and asserts every one is
still eligible and still valid.

Coverage targets are **scheduler hints, never acceptance gates**. `min_relevance`, `min_quality` and
`accept_composite` are read once per run from `policy.v1.json`, recorded on every round, and never
written by the scheduler — asserted both by comparing every round's recorded thresholds and by a
static check that `scheduler.py` never assigns one. `cross-industry` and `other-unclear` never close
a concrete gap and never open a gap lane.

---

## 13 · AX unmapped-legacy handling

Measured against `state/ax_case_harvest_registry.json`: **231 cases carry 173 distinct free-text
`industry` values**. A complete one-to-one table is not achievable, so
`legacy_industry_map.v1.json` is a reviewed **seed** (80 entries), keyed on the original string after
a documented minimal normalization — NFKC, whitespace collapse, strip, casefold, and **nothing else**.
Hybrids, platforms, marketplaces and super-apps are deliberately left unmapped.

An unmapped non-empty value becomes reporting state `unmapped_legacy_value`: an `unresolved[]` entry
carrying the exact term, the exact original preserved in `provenance.raw`, **no slug guessed**, and
the value **never** presented as classification evidence (`check_facets.py` rejects any record that
cites it). A migrated record may **not** hide one by omitting `case_facets` — that would report as
`not_enriched`, so the consistency rule refuses it.

Migration is never blocked on facet quality: the 231 cases land in `case-studies`, count stays 231,
no ID changes. `migration_overrides.v1.json` keeps its separate job (the suspicious-URL guard) and is
not merged into the facet map.

---

## 14 · Test suites and assertion counts

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"
for t in protected_baseline config identity schema http domain_throttle budget \
         facets facet_ambiguity facet_identity facet_states customer_interaction pool coverage; do
  bash "tests/test_taxonomy_${t}.sh"
done
bash scripts/harvest/verify_protected_baseline.sh
python scripts/harvest/check_facets.py
python scripts/harvest/gen_facet_schema.py --check
python scripts/harvest/check_config.py
```

| Stage 0–2 (unmodified) | | Stage 2.5 (new) | |
|---|---:|---|---:|
| `protected_baseline` | 24 | `facets` | 34 |
| `config` | 18 | `facet_ambiguity` | 28 |
| `identity` | 42 | `facet_identity` | 16 |
| `schema` | 35 | `facet_states` | 32 |
| `http` | 48 | `customer_interaction` | 13 |
| `domain_throttle` | 16 | `pool` | 38 |
| `budget` | 16 | `coverage` | 27 |
| **subtotal** | **199** | **subtotal** | **188** |

**Total: 387, 0 failed.** All four gates exit 0.

### One defect found by these tests, fixed

**`source_request_key` double-counted the query.** The key material carried the full normalized URL
*and* a separately-computed `canonical_query`. `canonicalize_string` preserves parameter order, so the
un-normalized copy inside the URL leaked back in and the query policy had no effect. Fixed by
splitting the normalized URL so the query is hashed exactly once, via `canonical_query`, which is now
the single authority on query normalization. Pinned by `TestQueryOrderPolicy`.

---

## 15 · Operational traps

- **Line endings.** `core.autocrlf=true`, no `.gitattributes`. The working tree is legitimately
  **mixed**: 10 of 18 protected files are LF on disk, 8 are CRLF. The baseline compares against Git's
  own rendering and **pins the observed `eol_form` per file**, which is what catches an LF-only
  rewrite that `git diff` normalises away. Expect `LF will be replaced by CRLF` warnings on every
  `git add` — they are noise, not a problem.
- **Git Bash `/tmp` is invisible to native Windows Python.** `mktemp -d` returns an MSYS path that
  Bash resolves but `python` cannot open. Use `tempfile.mkdtemp()` **from Python**, or `cd` first and
  pass relative paths. `$TMPDIR` is unset.
- **Python prints CRLF**, so `$(...)` leaves interior `\r` and silently breaks multi-line comparison.
  Existing tests pipe through `tr -d '\r'`.
- **The guard hook blocks piping a protected command into `head`/`tail`/`grep`/`sed`/`awk`/`tee`** —
  it masks the exit code. Write to a temp file, then inspect the file. It also blocks broad/forced
  recursive `rm`.
- **`safe_commit.sh` fails closed on a non-empty index** and verifies the staged set exactly equals
  the requested set, rolling the index back on any mismatch. Name files explicitly — never `-A`, `.`,
  a glob, or a directory.
- **`python`, not `python3`** — the latter is a Store stub. CPython 3.13.9 win32, `jsonschema` 4.26.0
  pinned exactly.
- **`os.kill(pid, 0)` is not a liveness probe on Windows** — it reports exited processes as alive.
  Stage 2 uses `OpenProcess` + `GetExitCodeProcess`.
- **`urllib.robotparser` is not RFC 9309** — we ship `httpclient.RobotsRules`.

---

## 16 · Protected and prohibited paths

**18 protected files, byte-identical to `8865c54e…`** — verify with
`bash scripts/harvest/verify_protected_baseline.sh`:
`scripts/run_matrix.sh` · `scripts/matrix_spec.py` · `scripts/merge_matrix.sh` ·
`scripts/expand_queries_cell.sh` · `scripts/harvest_matrix_cell.sh` ·
`tests/test_matrix_harvest.sh` · `tests/test_parallel_harvest.sh` ·
`scripts/lib/lockdir.sh` · `scripts/lib/clean_json.sh` · `scripts/github_meta.py` ·
`scripts/merge_entity_registry.sh` · `state/ax_case_harvest_registry.json` ·
`state/entity_registry.json` · `state/BuildingBlocks_{Agent,MCP,Prompt,Skill}.json` ·
`state/visited_url_ledger.json`.

**Also do not modify:** `scripts/harvest/check_config.py` (DV-1) · `src/harvest/urlkey.py` ·
`src/harvest/slug.py` · any existing Stage 0–2 test · `.gitignore` beyond its single added line.

**Prohibited without explicit approval:** any live source request, harvest, migration application,
refresh, link-check or promotion · any write to production `state/` · pushing · anything needing
credentials.

**The 508 pre-existing untracked files** (`.scratch_ax/` 445, 56 `state/_*` scratch files, a 570 KB
root log, 4 uncommitted agent specs) must stay byte-identical and are out of scope. A clean
`git status` is **not** required and is never asserted; the wrapper scripts assert only that tracked
files under `state/` and `config/` were not modified.

---

## 17 · Stage 3 paths and runtime outputs — confirmed absent

Probed at `46ab67c` and again before this handoff was committed:

```text
absent  src/harvest/adapters/
absent  src/harvest/migrate/
absent  scripts/harvest/harvest.sh
absent  tests/fixtures/harvest/
absent  state/taxonomy_harvest/          (ignored namespace; no run exists)
absent  data/harvested/                  (nothing published)
```

A static scan confirms the five new Stage 2.5 modules contain no `urlopen`, `requests`, `httpx`,
`socket`, `http.client` or `aiohttp` call. `pool.py` and `scheduler.py` take **injected** results and
an **injected clock**; they have no adapter dependency and reach no network.

---

## 18 · Next task and Stage 3 entry conditions

**The exact next task:** produce and get approval for a **Stage 3 implementation plan** — discovery
adapters (`src/harvest/adapters/{base,feed,sitemap,jsonapi,seed,model_search}.py`), recorded fixtures
for all 25 configured sources, and `tests/test_taxonomy_adapters.sh` (including seed depth hard-fixed
at 1 and the fail-closed path allowlist).

**Stage 3 is NOT approved for implementation.** It remains blocked until a new session:

1. **reads and independently verifies this handoff** — treating its claims as assertions to check,
   not facts to inherit;
2. **verifies `HEAD` and repository cleanliness** — `git rev-parse HEAD`, `git log --oneline -5`,
   `git status --short --untracked-files=all`, and the unpushed-commit list;
3. **reruns or spot-verifies the trust-establishing checks** — the 387 assertions,
   `verify_protected_baseline.sh`, `check_facets.py`, `gen_facet_schema.py --check`,
   `check_config.py`, and the 508-file untracked baseline;
4. **reviews the committed Stage 3 scope against the actual Stage 2.5 interfaces** — in particular
   `pool.CandidatePool`, `request_key.source_request_key` and its `query_order_policy`, and the
   `candidate_pool` / `discovery_lane` schemas, which are the contracts adapters must satisfy;
5. **presents a Stage 3 implementation plan** for review, including any deviation it needs;
6. **receives explicit approval before editing any file.**

Two known Stage 3 design questions to raise in that plan, deliberately deferred here:

- the **per-source config field** for `query_order_policy`. `schemas/harvest/taxonomy.v1.json`'s
  `jsonapi` object is `additionalProperties:false`, so a config-level opt-in means editing a Stage 1
  schema — that needs its own deviation request. Until then every caller uses `preserve`.
- **recorded fixtures** for the 25 configured sources require deciding how they are captured without
  performing a live harvest.
