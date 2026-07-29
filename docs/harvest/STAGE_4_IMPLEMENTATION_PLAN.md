# Stage 4 — extract, classify, verify, dedupe: implementation plan

```text
Status: PROPOSED — PENDING DEVIATION APPROVAL
```

**No code may be written under this document.** It is the design authority for Stage 4 and authorizes
nothing. `DV-11` is open; checkpoint **S4-1 is not authorized by the commit that adds this file**.
Each of S4-1 … S4-5 requires its own separate approval.

**Date:** 2026-07-29 · **Branch:** `main`

```text
stage_3_closing_commit:      68b6c2628aca36187aab37a4b8c08e401820d261
stage_3_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34
push_state:                  local only — nothing pushed to origin/main
assertions_at_plan_time:     567 across 17 suites, all green
```

Predecessors, still valid: `IMPLEMENTATION_PLAN.md` (§2 URL contract, §3 sources and vocabulary, §4
cross-topic phase, §6 budgets and enrichment, §13 allowed and prohibited paths) ·
`STAGE_3_IMPLEMENTATION_PLAN.md` (§13 Stage 4 opening condition). Where an older document conflicts
with shipped code, the **code** is authority; such conflicts are recorded in §10.

---

## 1 · Scope

**Stage 4 is metadata-only and entirely in-memory.**

It turns `AdapterResult` objects — already produced deterministically by Stage 3 — into
schema-validated records held in memory. It reads no body, issues no request, and **writes no file**.

**In scope**

| Component | Module | Authority |
|---|---|---|
| same-topic deduplication over canonical identity | `dedupe.py` | `IMPLEMENTATION_PLAN.md` §4.2 — one record per `identity_url` per topic, mandatory and not configurable |
| metadata normalization | `extract.py` | `TODO.md` Stage 4; `STAGE_3_IMPLEMENTATION_PLAN.md` §3 non-goals |
| deterministic classification | `classify.py` | `config/harvest/precedence.v1.json` — 10 ordered rules, 14 signals |
| scoring and verification | `verify.py` | `config/harvest/policy.v1.json` — "the accept/reject decision is made by verify.py against the thresholds below" |
| facet assignment | `facetassign.py` | `record.v1.json` requires `case_facets` for `cases__domain-applications`; `STAGE_2_5_IMPLEMENTATION_PLAN.md` §3 defers "classification implementation against live content" to Stage 4 |
| record construction | via `records.py` | `STAGE_3_IMPLEMENTATION_PLAN.md` §17 — "`records.py` — `make_full_record`/`make_cross_reference` — Stage 4's entry point" |

**Deferred to Stage 6 (enrichment / linkcheck)**

- target-page fetching and any target-fetch coordinator;
- target-page fixtures and the robots fixtures their hosts would need;
- setting `designated_target_fetch_owner_lane_id` or `designated_extraction_owner_lane_id`;
- body parsing, `content_hash`, and anchor-evidence fragment stripping;
- alias adjudication — 301/308 alias creation, `rel=canonical` trust tiers, and alias-conflict
  records — because every one of them requires fetch evidence Stage 4 does not have.

**Deferred to Stage 5 (orchestration)**

Cell workers · `CandidatePool` mutation of any kind · run manifests, cell artifacts, ledgers and
rejection logs · topic merging · cross-topic ownership execution (`build_content_index.py`,
`resolve_cross_topic.py`).

**Deferred further:** promotion and refresh (Stage 6) · migration (Stage 7) · `validate_task.sh`
wiring (Stage 8) · live smoke and `model_search` (Stage 9).

### 1.1 What Stage 4 does not modify

`src/harvest/pool.py` and `tests/harvest/test_pool.py` · every file under `schemas/harvest/` · every
file under `config/harvest/` · `src/harvest/adapters/**` · `src/harvest/sourcecache.py` ·
`src/harvest/httpclient.py`, `domainlease.py`, `budget.py` · `urlkey.py`, `slug.py`,
`request_key.py`, `records.py`, `facets.py`, `coverage.py`, `scheduler.py`, `schema.py`,
`fixtures.py` · `scripts/harvest/**` · `tests/fixtures/**` · **any existing test file** ·
`.gitignore` · the 18 protected files · the 508 pre-existing untracked paths · `state/**` ·
`data/**` · `scripts/validate_task.sh`.

Stage 4 is **purely additive apart from `docs/harvest/TODO.md`**: five new production modules, their
new test files and wrappers, and nothing else.

### 1.2 Honest field consequences

Because no target page is fetched, every Stage 4 record carries — and a test asserts it:

```text
access_status        "not_checked"       http_status      null
verification_status  "unverified"        content_hash     null
updated_at           null                last_checked_at  null
url_aliases          []                  canonical_url    == identity_url
```

This is exactly the field set `IMPLEMENTATION_PLAN.md` §6 predicts for a `--no-enrich` run. It is
honest, not degraded: `access_status: "not_checked"` is documented in `record.v1.json` as "NOT a
claim that the URL works."

### 1.3 Why `pool.py` is untouched

1. `pool.py:71` — "One per run. **Not thread-safe by design: the cell worker owns it.**" The cell
   worker is Stage 5.
2. `add_candidate`, `acquire_target_fetch` and `acquire_extraction` have **zero callers** in `src/`
   and `scripts/`. Stage 4 does not become the first.
3. Identity needs no pool: `request_key.candidate_key(target_url, …)` is a free function returning
   `(key, canonical)`, and `candidate_key == sha256(canonicalize_string(target_url))[:16]` while
   `identity_url == canonicalize_string(target_url)`. **One canonical group is exactly one
   `identity_url`, which is exactly one record per topic** — §4.2's mandatory rule, satisfied with no
   pool row.
4. Precedent: Stage 2.5 shipped `coverage.py` and `scheduler.py` as deterministic logic over injected
   inputs, owning no state. Stage 4 takes the same shape.
5. Stage 4 introduces no concurrency, so there is no race to correct. The candidate-side atomicity
   gap is real and is recorded as **CF-1** for the stage that introduces concurrent candidate
   processing.

---

## 2 · Extraction-owner semantics

The committed vocabulary is unambiguous and means **target-body extraction**:

- `pool.py:303` — "One extraction owner per accepted **response body** — no double parsing."
- `candidate_pool.v1.json` — "It is not evidence that this lane parsed the **body**. Null means
  extraction has not occurred. Exactly one extraction still happens per accepted **body**."

Stage 4 fetches no body. Therefore **`designated_target_fetch_owner_lane_id` and
`designated_extraction_owner_lane_id` both remain null**, and null keeps its committed meaning: the
operation has not occurred.

Normalizing a `RawCandidate` is **not** extraction in this vocabulary. `extract.py` is documented in
its own module docstring as *metadata normalization*, and a static test asserts it never references
`acquire_extraction`, `acquire_target_fetch`, `extraction_owner` or `target_fetch_owner`.

---

## 3 · Deviation ledger

Prior IDs are never recycled. Withdrawn entries are retained with their reasons so no number silently
changes meaning.

| ID | Problem | Status | Paths | Checkpoint |
|---|---|---|---|---|
| **DV-11** | **RawCandidate payload retention.** `RawCandidate` carries `title / published_at / summary / publisher / adapter / position`; `candidate_pool.v1.json → $defs/candidate` is `additionalProperties: false` with no home for any of them. Stage 4 must decide, bindingly and forward, whether that schema is widened. **Proposal: it is not.** Payload lives in Stage 4's in-memory contracts and, for accepted items, in `provenance.raw`, which `record.v1.json` types as an unconstrained `["object","null"]`. Forward consequence a Stage 5 author must know: the candidate-pool artifact stays payload-free; titles are read from records, never from the pool | **OPEN — approval required before S4-1** | `src/harvest/dedupe.py` (new), `src/harvest/extract.py` (new). **No schema file touched** | S4-1 |
| **DV-16** | **Stage 3 completion documentation not committed.** `STAGE_3_IMPLEMENTATION_PLAN.md` §13 condition 9 requires a committed Stage 3 completion handoff; the handoff was written outside the repository by design, and `TODO.md` was stale for 4A / 4A′ / DV-9 / 4B | **ACCEPTED — discharged by S4-0** | `docs/harvest/handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md`, this file, `docs/harvest/TODO.md` | S4-0 |
| ~~DV-10~~ | pool candidate-side atomicity | **WITHDRAWN** — §1.3 proves Stage 4 does not touch `pool.py`; recorded as CF-1 | — | — |
| ~~DV-12~~ | facet assignment needs a fifth production module | **WITHDRAWN** — `IMPLEMENTATION_PLAN.md` §13 permits `src/harvest/**` wholesale; no committed plan restricts the file set. `TODO.md` summarized responsibilities, it did not constrain files | — | — |
| ~~DV-13~~ | `rejection.v1.json` omits the five `not_a_case_*` / `keyword_only_match` values | **WITHDRAWN** — §10 E8 shows the divergence is intentional and Stage 4 writes no artifact; recorded as CF-2 | — | — |
| ~~DV-14~~ | target-fetch coordinator | **WITHDRAWN** — target fetching deferred to Stage 6 | — | — |
| ~~DV-15~~ | target fixture corpus | **WITHDRAWN** — target fetching deferred to Stage 6; recorded as CF-3 | — | — |

### 3.1 Carried-forward findings — recorded, not investigated

| # | Finding | Belongs to |
|---|---|---|
| **CF-1** | `pool.add_candidate`, `acquire_target_fetch` and `acquire_extraction` are unlocked check-then-set / read-modify-write, while `record_established_source` holds `self._lock`. Harmless while all three have zero callers | the stage that first drives candidate rows concurrently — Stage 5 |
| **CF-2** | `rejection.v1.json` cannot store the five `not_a_case_*` / `keyword_only_match` values that `record.v1.json` admits. Different artifacts, different populations — but the per-cell rejection log will have to decide | Stage 5, when that log is first written |
| **CF-3** | No target-page fixtures exist. Measured from the shipped corpus: 109 capped candidates across 19 target hosts, one of which (`news.ycombinator.com`) has no robots fixture. `FixtureOpener` raises `FixtureMissing` for anything but the 25 configured source URLs | Stage 6 |
| **CF-4** | `scripts/validate_task.sh` contains zero taxonomy references, so CLAUDE.md's stated validation entry point exercises none of the 567 assertions | Stage 8 |

---

## 4 · DV-11 — the proposed ingest contract

**Proposed. Not approved. `dedupe.py` may not be written until DV-11 is approved.**

### 4.1 Constraints

1. **One distinct source item produces exactly one observation**, even when several lanes reuse the
   same source snapshot. Observation identity is `(source_id, position, target_url)` — properties of
   the item, never of the lane that happened to read it. Three lanes sharing one feed yield one
   observation per item, not three.
2. **Lane IDs and source request keys are provenance collections on the observation**: deduplicated
   and sorted lexically, exactly as `pool.to_document()` normalizes the same two field kinds under
   DV-7. They never influence ordering, selection or evidence.
3. **Observation ordering uses a complete immutable tie-breaker.** The sort key is
   `(source_id, position, target_url)` — a **total** order over immutable content, fixed before any
   concurrency could exist. It is not arrival order, thread order or lane order.
4. **Every metadata contribution and every conflict is retained.** Nothing is discarded to make a
   single value. `CandidateGroup.variants(field)` returns each distinct value with the sources that
   asserted it, ordered by first appearance in the total order.
5. **Primary selection uses committed source authority first, then a deterministic fallback.**
   Authority is the configured `role`: `taxonomy.v1.json` documents `validation_seed` as "an
   explicitly configured **authoritative** source", `discovery` as merely "expected to surface new
   items". So observations sort by `(role_rank, source_id, position, target_url)` with
   `validation_seed → 0`, `discovery → 1`. The fallback is the §4.1.3 total order, which is complete
   on its own — authority reorders, it never leaves a tie unresolved.
6. **All discovery topic/category contexts remain available to classification.** Each observation
   carries the `topic_slug` and `category_slug` of the source that produced it, and the full set
   reaches `classify.py`. This matters for rule R10 (`use_discovery_cell: true`) when one canonical
   candidate was surfaced by sources in two different cells; the competing contexts are recorded in
   `classification.competing_categories[]` rather than silently collapsed.
7. **Stage 4 performs canonical-equivalence grouping only.** Two candidates group iff
   `urlkey.canonicalize_string` maps them to the same string. No `http→https` merge, no `www.`
   stripping, no trailing-slash merge, no query sorting outside a configured per-domain rule — the
   conservative contract of `urlkey.py`, unchanged and unextended.
8. **Aliases and alias conflicts remain Stage 6 concerns.** Alias creation needs a 301/308 or a
   verified `rel=canonical`, both of which require a fetch. Stage 4 emits `url_aliases: []` and
   produces no alias-conflict record.

### 4.2 Proposed in-memory contracts

All frozen, all slotted, owned by `src/harvest/dedupe.py`. Nothing here is persisted by Stage 4.

```python
@dataclasses.dataclass(frozen=True, slots=True)
class CandidateObservation:
    """One source item's complete view of one candidate. Nothing is discarded."""
    source_id: str                 # stamped by Adapter.discover (adapters/base.py)
    adapter: str                   # ditto
    position: int                  # ditto — document order within that source
    role: str                      # "discovery" | "validation_seed", from the config
    topic_slug: str                # the discovery cell this observation came from
    category_slug: str
    target_url: str                # verbatim as THAT source published it
    title: str | None
    published_at: str | None       # verbatim; normalization belongs to extract.py
    summary: str | None
    publisher: str | None
    lane_ids: tuple                # deduplicated, sorted lexically  (constraint 2)
    source_request_keys: tuple     # deduplicated, sorted lexically  (constraint 2)

    @property
    def order_key(self):           # constraints 3 and 5
        return (0 if self.role == "validation_seed" else 1,
                self.source_id, self.position, self.target_url)


@dataclasses.dataclass(frozen=True, slots=True)
class CandidateGroup:
    """Every observation of one canonical candidate."""
    candidate_key: str             # request_key.candidate_key(...)[0]
    identity_url: str              # request_key.candidate_key(...)[1]
    observations: tuple            # sorted by order_key; NEVER truncated

    @property
    def primary(self): ...         # observations[0]
    def display(self, field): ...  # first non-null in the total order  (constraint 5)
    def variants(self, field): ... # ((value, (source_id, ...)), ...)   (constraint 4)
    def contexts(self): ...        # ordered distinct (topic_slug, category_slug)  (constraint 6)


@dataclasses.dataclass(frozen=True, slots=True)
class DedupeResult:
    groups: tuple                       # CandidateGroup, sorted by candidate_key
    observation_count: int
    duplicate_observation_count: int    # observations - groups
```

### 4.3 Duplicate representation

`CandidatePool` holds **one row per candidate key**, so there is no separately represented loser and
Stage 4 must not invent one.

- **The canonical row is untouched by Stage 4** — Stage 4 writes no pool row at all. `dropped_reason`
  is never set by Stage 4, and the surviving candidate is never marked dropped.
- **Duplicate observations are recorded in `CandidateGroup.observations`** (a group with
  `len(observations) > 1` was seen more than once) and reported in aggregate by
  `DedupeResult.duplicate_observation_count`.
- **The union of contributing sources, lanes and request keys** lives on the observations and is
  reproduced on the record as:

```json
"provenance": {
  "source_id":      "<primary.source_id>",
  "source_adapter": "<primary.adapter>",
  "raw": {
    "observations":   [ { "source_id": …, "adapter": …, "position": …, "role": …,
                          "topic_slug": …, "category_slug": …, "target_url": …,
                          "title": …, "published_at": …, "summary": …, "publisher": …,
                          "lane_ids": […], "source_request_keys": […] } ],
    "field_variants": { "title": [["A", ["src-a"]], ["B", ["src-b"]]] }
  }
}
```

`record.v1.json`'s `provenance` is `additionalProperties: false` with fixed keys, but `raw` is typed
`["object","null"]` with **no inner constraints**. Conflict retention therefore needs **no schema
change** — which is the concrete basis for DV-11's "do not widen" recommendation.
`provenance.source_id` and `source_adapter` are singular by schema and take the primary observation's
values; the complete set stays in `raw`.

### 4.4 Stage 5 seam

When Stage 5 populates the pool it calls `pool.add_candidate` once per observation. The second call
finds the existing row, appends the lane and request key, and returns `is_new=False` — the union is
already shipped behaviour, no loser row is created, and no schema change is implied.

---

## 5 · Permanent checkpoint execution policy

This policy applies to every checkpoint in this plan and to any later plan that adopts it. It exists
so execution prompts do not have to restate contracts.

- **Solve only blockers for the current checkpoint.** A defect outside the checkpoint's allowed paths
  is recorded, not fixed.
- **Record future-stage concerns as carried-forward findings without investigating them.** A CF entry
  is one sentence and a target stage. Do not measure it, do not prototype it, do not price it.
- **Stop only for** material scope expansion · a contradiction between committed contracts · or a
  data-integrity risk. Nothing else justifies pausing mid-checkpoint.
- **Detailed contracts live in this plan and in the tests**, never in repeated execution prompts. If
  a contract is missing here, add it here first.
- **Docs-only checkpoints (L0) use diff and static validation only.** Inspect the diff, run
  `git diff --check`, confirm the exact allowed path set changed, run the 508-file baseline verifier
  once, confirm the absence of code paths the document says are absent. Do **not** run test suites or
  unrelated checkers.
- **Additive pure-function checkpoints (L1)** run their own focused suite repeatedly during work, and
  the full gate **once** before commit.
- **Shared-code changes (L2)** additionally receive regression or stress tests, and only where
  relevant to what changed. A concurrency stress run is required only when the change touches
  concurrency.
- **Do not rerun the full gate after commit** unless the commit content itself changed during
  staging.
- **Reports summarize results and deviations, not every command run.**

---

## 6 · Checkpoints

Every checkpoint requires **separate approval**. This document authorizes none of them.

### S4-1 · Same-topic dedupe and the ingest model

- **Goal.** Turn a sequence of `AdapterResult` objects into a deterministic `DedupeResult`: one
  `CandidateGroup` per canonical identity, every observation retained, every conflict retained.
- **Allowed paths.** `src/harvest/dedupe.py` (A) · `tests/harvest/test_dedupe.py` (A) ·
  `tests/test_taxonomy_dedupe.sh` (A) · `docs/harvest/TODO.md` (M).
- **API / data contract.** §4.2. Entry point
  `dedupe.group(results, *, sources, tracking_params=None, domain_rules=None) -> DedupeResult`, where
  `results` is an iterable of `AdapterResult` and `sources` maps `source_id` to its configured object
  (for `role`, `topic_slug`, `category_slug`).
- **Invariants.** Grouping is exactly canonical-string equality via `urlkey` · one observation per
  distinct source item regardless of lane count · `lane_ids` and `source_request_keys` deduplicated
  and lexically sorted · ordering is the total key of §4.1.5 · no truncation, no field discarded · no
  pool call, no file write, no network symbol · output byte-identical under shuffled input.
- **Focused tests.** Duplicates within one source · duplicates across two sources · three lanes on
  one source produce one observation · canonical-equivalent URLs group (tracking params, default
  port, dot-segments) · canonical-distinct URLs do not (`ref=`, `?a=1&b=2` vs `?b=2&a=1`, `#intro`) ·
  conflicting titles/publishers/dates all retained and reported by `variants()` · `validation_seed`
  outranks `discovery` for primary · fallback resolves a same-role tie · shuffled input yields
  identical output · injected 301/308 and `rel=canonical` evidence exercise the alias **rules**
  without producing an alias · static: no `pool`, `acquire_*`, `open(`, or network import.
- **Risk tier and validation.** L1. Focused suite during work; full gate once before commit.
- **Commit / stop boundary.** One commit. Stop if a dedupe rule cannot be expressed without a pool
  row or a schema widening.
- **Carried-forward findings.** CF-1 if concurrent grouping is ever wanted; CF-3 for alias evidence
  production.

### S4-2 · Metadata normalization (`extract.py`)

- **Goal.** `CandidateGroup → ExtractedCandidate`: the display values, normalized dates, derived
  `identity_url`, and the provenance payload of §4.3.
- **Allowed paths.** `src/harvest/extract.py` (A) · `tests/harvest/test_extract.py` (A) ·
  `tests/test_taxonomy_extract.sh` (A) · `docs/harvest/TODO.md` (M).
- **API / data contract.**
  `extract.normalize(group, *, tracking_params=None, domain_rules=None) -> ExtractedCandidate`
  carrying `target_url, identity_url, content_id, title, summary, published_at, publisher, author,
  language, content_type, provenance_raw`.
- **Invariants.** Dates go through `records.to_iso8601_utc`, which returns `None` rather than
  guessing · `identity_url` comes from `urlkey.canonicalize_string`, never recomputed locally ·
  `"unknown"` and empty strings become `None` via `records.null_if_unknown` · no body is read; no
  field derived from a body is set · sets neither ownership field (§2).
- **Focused tests.** RSS and Atom date forms · unparseable date ⇒ `None` · `"unknown"` ⇒ `None` ·
  `identity_url` equals `urlkey.canonicalize_string(target_url)` exactly · `content_id` matches
  `urlkey.content_id` · provenance payload contains every observation and every variant · shuffled
  input yields identical output · static: no `acquire_extraction` / `extraction_owner` reference.
- **Risk tier and validation.** L1.
- **Commit / stop boundary.** One commit. Stop if a schema-required field cannot be produced without
  a body.
- **Carried-forward findings.** None expected.

### S4-3 · Deterministic classification (`classify.py`)

- **Goal.** Apply `precedence.v1.json` — 10 ordered rules over 14 signals — to produce
  `(topic_slug, category_slug)` plus the `classification` payload `record.v1.json` requires.
- **Allowed paths.** `src/harvest/classify.py` (A) · `tests/harvest/test_classify.py` (A) ·
  `tests/test_taxonomy_classify.sh` (A) · `docs/harvest/TODO.md` (M).
- **API / data contract.**
  `classify.classify(extracted, *, contexts, precedence=None) -> Classification` with
  `topic_slug, category_slug, rule_id, rationale, evidence[{signal, matched}],
  competing_categories[{topic, category, rule_id}], ambiguous`.
- **Invariants.** Signals are computed from **title, summary, publisher, target_url and the source's
  own category** only, exactly as `precedence.v1.json` `_signal_about` states · first matching rule
  in `order` wins; every other matching rule is recorded in `competing_categories[]` · R10 falls back
  to the discovery cell and sets `record_ambiguity` · a `lane_id` is never an input and never becomes
  evidence · a classification assigning a topic other than the discovery topic is **recorded, not
  resolved** — cross-topic ownership is Stage 5.
- **Focused tests.** Each of R1–R10 fires on a designed input · ordering proven where it bites (R6
  beats R7 on an eval-bearing paper; R4 beats R9; R3 refuses a developer tool via `none_of`) · all 14
  signals · ambiguous input populates `competing_categories` while exactly one primary is chosen ·
  unmatched input reaches R10 · shuffled input yields identical output · static: `lane_id` is not a
  parameter of any entry point, and no cross-topic resolution symbol appears.
- **Risk tier and validation.** L1.
- **Commit / stop boundary.** One commit. Stop if a rule needs an input beyond the five committed
  signal sources.
- **Carried-forward findings.** Cross-topic resolution ordering for Stage 5.

### S4-4 · Scoring and verification (`verify.py`)

- **Goal.** The four scores from `policy.v1.json` weights and the category `relevance` blocks, the
  accept/reject decision against the committed thresholds, and honest status fields.
- **Allowed paths.** `src/harvest/verify.py` (A) · `tests/harvest/test_verify.py` (A) ·
  `tests/test_taxonomy_verify.sh` (A) · `docs/harvest/TODO.md` (M).
- **API / data contract.** `verify.score(extracted, classification, *, policy, category) -> Scores`
  and `verify.decide(extracted, scores, *, policy) -> Verdict` carrying
  `accepted, rejection_reason, access_status, http_status, verification_status,
  verification_evidence`.
- **Invariants.** Thresholds are read once and never adjusted to admit anything ·
  `access_status` is `"not_checked"` and `verification_status` `"unverified"` on every Stage 4
  verdict (§1.2) · `rejection_reason` values come only from `record.v1.json`'s enum · a record
  withheld for weak facets is **not** rejected and carries no `rejection_reason` · nothing is written
  to disk, including any rejection log.
- **Focused tests.** Each weight and the composite · every threshold boundary, above and below ·
  `category_exclusion_applied` from a category `exclude` list · `developer_only_audience` ·
  insufficient evidence · inaccessible content is representable but never *claimed* by Stage 4 ·
  contradictory evidence recorded rather than resolved · freshness half-life · shuffled input yields
  identical output.
- **Risk tier and validation.** L1.
- **Commit / stop boundary.** One commit. Stop if a verdict requires fetch evidence.
- **Carried-forward findings.** CF-2 — the rejection-log vocabulary, when Stage 5 writes that log.

### S4-5 · Facet assignment and record construction

- **Goal.** Assign `case_facets` from the committed vocabularies, then build schema-valid `full` and
  `cross_reference` records in memory.
- **Allowed paths.** `src/harvest/facetassign.py` (A) · `tests/harvest/test_facetassign.py` (A) ·
  `tests/harvest/test_records_build.py` (A) · `tests/test_taxonomy_facetassign.sh` (A) ·
  `tests/test_taxonomy_records.sh` (A) · `docs/harvest/TODO.md` (M).
- **API / data contract.** `facetassign.assign(extracted, *, facets_dir=None) -> case_facets | None`;
  record construction calls the **unmodified** `records.make_full_record` / `make_cross_reference`.
- **Invariants.** Evidence is quoted from the document, per `facet_evidence{field, matched_term,
  quote, offset}` · `INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS` and
  `TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS` are enforced — a vendor-published customer case
  takes the customer's industry · `LEXICAL_SUPPORT_REQUIRED` values need lexical support ·
  `classification_state` comes from `facets.decide_classification_state`, never computed locally ·
  `vocabulary_versions` from `facets.vocabulary_versions()` · facets never touch `record_id`,
  `content_id`, `identity_url`, `cell_id` or any filename · the `cases__domain-applications`
  conditional is satisfied and the `research-and-models` / `discourse` null conditional is honoured ·
  facet terms never leak into `classification.evidence` · every record validates against
  `record.v1.json` in memory; **nothing is written**.
- **Focused tests.** Industry from a customer mention, refused from the publisher · the two forbidden
  evidence-field rules · `other-unclear` and the four unresolved states · resolved vs unresolved ·
  a `cases__domain-applications` record without facets is refused by the schema · a
  `research-and-models` record with facets is refused · `cross_reference` cannot carry a
  full-record field · deterministic sort by `(topic, primary_category, record_id)` · shuffled input
  yields identical output · static: `facetassign` and `classify` share no evidence constructor.
- **Risk tier and validation.** L1, with the full gate before commit — five suites are new by this
  point.
- **Commit / stop boundary.** One commit. Stop if a `cases__domain-applications` record cannot
  satisfy the `case_facets` conditional from committed vocabularies alone.
- **Carried-forward findings.** Coverage reporting wiring for Stage 5.

---

## 7 · Files

```text
S4-1  A  src/harvest/dedupe.py           A  tests/harvest/test_dedupe.py
      A  tests/test_taxonomy_dedupe.sh
S4-2  A  src/harvest/extract.py          A  tests/harvest/test_extract.py
      A  tests/test_taxonomy_extract.sh
S4-3  A  src/harvest/classify.py         A  tests/harvest/test_classify.py
      A  tests/test_taxonomy_classify.sh
S4-4  A  src/harvest/verify.py           A  tests/harvest/test_verify.py
      A  tests/test_taxonomy_verify.sh
S4-5  A  src/harvest/facetassign.py      A  tests/harvest/test_facetassign.py
      A  tests/harvest/test_records_build.py
      A  tests/test_taxonomy_facetassign.sh
      A  tests/test_taxonomy_records.sh
every M  docs/harvest/TODO.md
```

Nothing else. See §1.1 for the exhaustive not-modified list.

## 8 · Validation

Focused gate (during a checkpoint): that checkpoint's own wrapper. `test_taxonomy_schema.sh` is not
required at any point in Stage 4 — no schema is edited.

Full gate (once, before each commit from S4-1 onward): every `tests/test_taxonomy_*.sh` ·
`check_fixtures.py` · `verify_protected_baseline.sh` · `check_facets.py` ·
`gen_facet_schema.py --check` · `check_config.py` · `git diff --exit-code -- scripts/harvest/check_config.py` ·
`git status --porcelain --untracked-files=no` · the 508-file baseline verifier ·
`git diff --stat 8865c54e… HEAD -- .gitignore` still exactly `1 insertion(+)`.

`scripts/validate_task.sh` is **not** the Stage 4 gate — it has no taxonomy wiring (CF-4). Capture
output to a file rather than piping; the guard hook blocks piping a protected command into
`head`/`tail`/`grep`/`sed`/`awk`/`tee`.

## 9 · Rollback

S4-1 … S4-5 are purely additive apart from `TODO.md`: `rm` the checkpoint's new files, then
`git checkout -- docs/harvest/TODO.md`. **Triggers:** any of the 567 prior assertions turning red ·
any existing test needing an edit · protected-baseline failure · drift in the 508 pre-existing
untracked files · a `state/` or `data/` path appearing · discovering that a Stage 4 module cannot
meet a committed contract without changing `pool.py`, `records.py` or a schema — which returns for an
explicit deviation rather than being bent in code.

## 10 · Errata — stale statements in earlier documents

Earlier documents are not rewritten. This plan is the authority where they conflict.

**E7 — `STAGE_3_IMPLEMENTATION_PLAN.md` §4 overstates the seed adapter.** It says the seed adapter
"may … evaluate robots permission per child". The shipped `seed.py` does no such thing: it performs
pure string work, and robots is evaluated by `HttpClient` at fetch time. Per-child robots is
therefore a Stage 6 concern, arriving with target fetching. Authority: `src/harvest/adapters/seed.py`.

**E8 — the five extra `rejection_reason` values are `record.v1.json`-only, deliberately.**
`DOMAIN_FACETS_PROPOSAL.md` and `STAGE_2_5_IMPLEMENTATION_PLAN.md` both list the modified schemas as
`record.v1.json` **and** `run_manifest.v1.json`, and both omit `rejection.v1.json` from that same
list — an omission, not an oversight. The two artifacts also serve different populations:
`record.v1.json`'s `rejection_reason` sits on a **retained, auditable record** that keeps its
`record_id`, while `rejection.v1.json` logs **candidates that never became records**. No schema is
changed for vocabulary symmetry; the question is CF-2.

## 11 · Stage 5 opening condition

Stage 5 planning may begin only when all of the following hold **in one final run**:

1. `test_taxonomy_{dedupe,extract,classify,verify,facetassign,records}.sh` are green;
2. every prior assertion — the 567 — is green in that same run;
3. `verify_protected_baseline.sh`, `check_fixtures.py`, `check_facets.py`,
   `gen_facet_schema.py --check` and `check_config.py` all exit 0, and `check_config.py` is
   byte-unchanged;
4. the 508 pre-existing untracked files are byte-identical and `.gitignore` still shows exactly
   `1 insertion(+)` against the anchor;
5. a full `full` / `cross_reference` record set validates against `record.v1.json`, including both
   `case_facets` conditionals;
6. determinism is proved at every stage under shuffled source, candidate and lane orderings;
7. `state/taxonomy_harvest/`, `data/harvested/` and `runs/` are still **absent**; no artifact,
   manifest, ledger or rejection file was written; no live request was made;
8. `pool.py` and every schema and config file are byte-unchanged since `68b6c26`;
9. every deviation applied is recorded here with its approval, and a Stage 4 completion handoff is
   committed **in-repo**;
10. **explicit approval is given.** Green tests alone do not open Stage 5.
