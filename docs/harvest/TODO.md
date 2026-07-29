# Taxonomy harvest — task checklist

Updated as each item is completed **and tested**. An item is only ticked when its narrowest test
passes; "written" is not "done".

```text
verified_code_checkpoint:    68b6c2628aca36187aab37a4b8c08e401820d261   Stage 3 implementation
documentation_approval:      79389e1460a13492fcdc42ab8c96af5313ad9bca   approved plan
approved_facet_design:       3b85a8102fb89ae0585ef0fc080f518238e4c1bc
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e
stage_2_5_implementation:    46ab67cde36acf4b2b403d17d4bc589eff3d5cb7
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  local only — nothing pushed to origin/main
assertions:                  884 across 22 suites, all green
                             (567 prior + 55 S4-1 + 58 S4-2 + 78 S4-3/S4-3A
                              + 63 S4-4 + 63 S4-5A)
```

---

## Stage 0 — scaffold, baselines, ignore rules

- [x] `docs/harvest/INVENTORY_AND_REUSE_MAP.md` — repository inventory and reuse map
- [x] `docs/harvest/TODO.md` — this file
- [x] `docs/harvest/IMPLEMENTATION_PLAN.md` — approved design
- [x] `.gitignore` — **exactly one** appended line `/state/taxonomy_harvest/`, no comments
      (`git diff --stat` = `1 insertion(+)`). Verified necessary beforehand
      (`git check-ignore -v state/taxonomy_harvest/probe` → rc=1, no matching rule), effective
      afterwards, and narrow: `data/harvested/` and all pre-existing untracked noise still unignored
- [x] `scripts/harvest/hash_tree.py` — deterministic recursive SHA-256 manifest
- [x] `tests/fixtures/taxonomy/protected_paths.txt` — 18 protected paths
- [x] `scripts/harvest/protected_baseline.py` — generate/verify; primary check is exact working-tree
      bytes vs **Git's rendering of the implementation-start commit** (`git cat-file --filters`),
      with the observed `eol_form` pinned per file
- [x] `scripts/harvest/gen_protected_baseline.sh` — wrapper; refuses overwrite without `--replace-baseline`
- [x] `scripts/harvest/verify_protected_baseline.sh` — wrapper; 4 independent checks
- [x] `tests/fixtures/taxonomy/protected_sha256.txt` — generated once, 18 entries
      (filtered=8, blob=10 — the working tree is legitimately mixed; see INVENTORY §5.1)
- [x] `tests/test_taxonomy_protected_baseline.sh` — **24 assertions, all passing.** Proves: unchanged
      CRLF checkout passes · content modification fails · **LF-only rewrite fails even though
      `git diff` reports it clean** · tampered baseline fails · regeneration refused without
      `--replace-baseline` · drift matching neither rendering refused at generate
- [x] `tests/fixtures/taxonomy/untracked_baseline.txt` — 508 files, captured before the first edit,
      copied verbatim (sha256 match asserted)

## Stage 1 — dependencies, config, schemas, identity

- [x] `requirements.txt` (`jsonschema==4.26.0`, exact pin) + `constraints.txt`
      (resolved on CPython 3.13.9/win32; support limited to 3.13.x, stated in the file)
- [x] `config/harvest/topics/{cases,research-and-models,discourse}.v1.json`
      — verified: 12 unique cells, 25 unique sources, all 9 required fields present on every
      source object, no duplicate `source_id`/`fixture_id`, every slug round-trips through
      `slugify()`, all URLs absolute
- [x] `config/harvest/policy.v1.json` — 10 budgets, robots RFC 9309 policy, per-domain overrides
      (arxiv.org 15s, microsoft.com 10s), staged breaker/conditional flags, scoring weights
- [x] `config/harvest/precedence.v1.json` — 10 ordered rules, 14 signals, `cross_topic_policy`
- [x] `config/harvest/canonicalization.v1.json` — strip list, never-strip list with rationale,
      fragment policy (preserve by default), empty domain_rules/migrations
- [x] `config/harvest/watchlists/oss-milestones.v1.json` — 3 concrete repos, no placeholder
- [x] `config/harvest/migration_overrides.v1.json` — empty reviewed-unmappable list
- [x] `src/harvest/slug.py` — smoke-verified against all 15 taxonomy display names
- [x] `src/harvest/urlkey.py` — smoke-verified, 13/13 canonicalization cases correct
- [x] `schemas/harvest/record.v1.json` — `record_type` discriminated union (`oneOf` +
      `additionalProperties:false` on both branches)
- [x] `schemas/harvest/{cell_artifact,topic_artifact,run_manifest,ledger,rejection,taxonomy}.v1.json`
- [x] `src/harvest/schema.py` — jsonschema required, no fallback; local `referencing` registry so
      validation never touches the network
- [x] `src/harvest/records.py` — builders with honest defaults (`access_status: not_checked`,
      `verification_status: unverified`), `"unknown"`→null, deterministic sort key,
      `HARVEST_CLOCK_UTC` clock pin for fixture determinism
- [x] `scripts/harvest/check_config.py` — config completeness + exact cell-set check
- [x] `tests/test_taxonomy_config.sh` — **18 assertions.** Real config passes; missing field,
      missing category, unapproved extra category, duplicate `source_id` and non-round-tripping slug
      each proved to be rejected
- [x] `tests/test_taxonomy_identity.sh` → `tests/harvest/test_identity.py` — **42 tests.**
      Safe ops, refusals, conservative non-operations, full fragment policy, identity stability
- [x] `tests/test_taxonomy_schema.sh` → `tests/harvest/test_schema.py` — **35 tests.**
      Every required field proved required; cross-reference cannot carry any full-record field;
      partial full record rejected under both branches; all artifact schemas

**Stage 1 status: complete.** 95 assertions across 3 suites, all green.

## Stage 2 — HTTP baseline, domain coordination, budgets

- [x] `src/harvest/budget.py` — nested scopes, charge-before-attempt, injectable clock
- [x] `src/harvest/domainlease.py` — cross-process `mkdir` slots, shared `next_allowed_at`,
      pipeline-wide `Retry-After` penalty, platform-correct stale-lease recovery
- [x] `src/harvest/httpclient.py` — **own RFC 9309 robots matcher** (see below), crawl-delay,
      backoff+jitter, `Retry-After`, bounded redirects with permanent/temporary classification,
      `max_response_bytes`, typed errors mapping onto the manifest enums, non-raising `preflight()`
- [x] `tests/test_taxonomy_http.sh` — **48 tests**
- [x] `tests/test_taxonomy_domain_throttle.sh` — **16 tests**, real subprocesses vs a recording server
- [x] `tests/test_taxonomy_budget.sh` — **16 tests**

**Stage 2 status: complete.** 199 assertions across 7 suites (stages 0–2), all green.

### Two defects found by these tests, both fixed

1. **`urllib.robotparser` does not implement RFC 9309.** The stdlib uses the 1996 draft's
   *first-match-in-file-order* rule; RFC 9309 §2.2.2 requires *longest-match-wins*. The difference
   errs unsafely: given `Allow: /` then `Disallow: /private`, first-match permits `/private/x`.
   Replaced with `httpclient.RobotsRules` (group selection, `*`/`$` wildcards, longest match,
   Allow wins ties, Crawl-delay). Pinned by 12 tests including the unsafe case.
2. **`os.kill(pid, 0)` is not a liveness probe on Windows.** Measured on CPython 3.13/win32: for a
   process that had definitively exited it returned normally, reporting the dead process ALIVE — so a
   crashed worker's lease could only be reclaimed by the 120 s age rule, the exact wedge the pid rule
   prevents. Replaced with `OpenProcess` + `GetExitCodeProcess` on Windows, `os.kill` on POSIX, with
   a regression test that starts and exits a real process. (An earlier hypothesis that the probe
   *terminated* live processes was tested and disproved.)

## Stage 2.5 — case facets and shared discovery

Design: `docs/harvest/DOMAIN_FACETS_PROPOSAL.md` (revision 4, plus its §16 Errata).
Plan: `docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md` — approved
(deviations DV-1 … DV-6 and design corrections D1–D10, including the D7 five-state model).
Reference: `docs/harvest/FACET_VOCABULARY.md`.

- [x] `config/harvest/facets/{industries,business-functions,use-case-types}.v1.json`
      — **18 / 19 / 22** entries, tiers 7-8-3 / 10-8-1 / **10-11-1**
- [x] `config/harvest/facets/legacy_industry_map.v1.json` — a reviewed **seed**: the 231 AX cases
      carry 173 distinct free-text values, so the long tail stays `unmapped_legacy_value`
- [x] `config/harvest/coverage_targets.v1.json` — 3/2/0 + overrides; a `record_only` override
      above 0 is refused
- [x] `schemas/harvest/facet_vocabulary.v1.json` *(DV-3)*
- [x] `record.v1.json` — `case_facets`, 5 new `$defs`, the `allOf` **inside `$defs/full_record`**
      *(DV-5)*, `vocabulary_versions` required *(DV-6)*, 5 new rejection reasons
- [x] `run_manifest.v1.json` — optional `rounds[]` · `coverage[]` · `lane_quality[]` ·
      `request_accounting`; none added to `required`
- [x] `schemas/harvest/{candidate_pool,discovery_lane,coverage_report}.v1.json`
- [x] `facets.generated.v1.json` — generated, never hand-edited, drift-tested, malformed-file tested
- [x] `src/harvest/{facets,pool,coverage,scheduler,request_key}.py`
- [x] `src/harvest/records.py` — one keyword-only `case_facets=None`, omitted when falsy *(DV-2)*
- [x] `scripts/harvest/{gen_facet_schema,check_facets}.py` —
      `check_config.py` left **byte-unchanged** *(DV-1)*
- [x] `tests/test_taxonomy_{facets,facet_ambiguity,facet_identity,facet_states,customer_interaction,pool,coverage}.sh`
      — **188 new assertions**
- [x] **Rerun of the full 199-assertion Stage 0–2 baseline** — still green
- [x] `docs/harvest/FACET_VOCABULARY.md`

**Stage 2.5 status: complete**, committed as `46ab67c` (36 files, 6650 insertions).
**387 assertions across 14 suites** (199 existing + 188 new), all green; protected baseline verified;
`check_facets.py`, `gen_facet_schema.py --check` and `check_config.py` all exit 0. Zero tracked
modifications afterwards; the 508 pre-existing untracked files unchanged; nothing pushed. No live
source request, harvest, migration application, refresh, link-check or promotion was performed.

Implemented per `STAGE_2_5_IMPLEMENTATION_PLAN.md` with **no plan deviations**, except one separately
approved correction: **request-key query normalization is opt-in per request**
(`query_order_policy`, default `preserve`); adapter class never enables sorting, and repeated-key
value order and multiplicity stay significant under both policies.

### One defect found by these tests, fixed

**`source_request_key` double-counted the query.** The key material carried the full normalized URL
*and* a separately-computed `canonical_query`. `canonicalize_string` preserves parameter order, so the
un-normalized copy inside the URL leaked back in and the query policy had no effect at all. Fixed by
splitting the normalized URL and hashing the query exactly once, via `canonical_query`, which is now
the single authority on query normalization. Pinned by
`tests/harvest/test_pool.py::TestQueryOrderPolicy`.

The shipped contract, for the avoidance of doubt: query normalization is **opt-in per logical
request** (`query_order_policy`, keyword-only, default `preserve` for **every** adapter and every
source). Adapter class authorizes nothing — `ORDER_INSIGNIFICANT_ADAPTERS` does not exist, and
`test_pool.py:113` asserts its absence. Repeated-key value order and multiplicity stay significant
under both policies. Earlier drafts describing adapter-wide sorting for "order-insignificant
adapters" are superseded; see `STAGE_3_IMPLEMENTATION_PLAN.md` §2 erratum E1.

---

## Stage 3 — discovery adapters ⟵ **COMPLETE.**

Plan: **`docs/harvest/STAGE_3_IMPLEMENTATION_PLAN.md`** — standalone and authoritative. The Stage 2.5
entry conditions (§18 of `handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md`) were all satisfied: the
handoff was independently verified, `HEAD` and cleanliness confirmed, the 387 assertions and all four
gates rerun, and the scope reviewed against the actual Stage 2.5 interfaces.

Both deferred design questions are now resolved in that plan: the per-source `query_order_policy`
config field is **not added** (no configured source needs it, and adding it would edit a Stage 1
schema and invalidate cache keys), and the 25 fixtures are **synthetic and hand-authored**, never
captured — so no live harvest is required.

Three approved corrections preceded adapter code, each its own commit, in this order:

- [x] **C4** — `ClientError.reason = "http_4xx"`; a 4xx must not be reported as `http_5xx`.
      `httpclient.py` · `test_http.py` · `IMPLEMENTATION_PLAN.md` §3 — **`e271206`**
- [x] **DV-7** — `CandidatePool` byte-determinism and honest ownership vocabulary: type-aware
      set normalization at serialization, and deterministic **designation** fields that never claim to
      name the lane that actually performed the work. `pool.py` · `candidate_pool.v1.json` ·
      `test_pool.py` — **`0a03fdd`**
- [x] **DV-8** — per-logical-fetch HTTP accounting: `FetchAccounting` frozen onto every `Response`
      and every typed failure, never diffed from the shared `client.stats`. `httpclient.py` ·
      `test_http.py` — **`2841578`**
- [x] Stage 3 proper:
      - [x] **4A** `src/harvest/sourcecache.py` — one logical fetch per request key for success
            **and** failure; `claim`/`wait`/`complete`/`fail` store protocol; the atomic
            `pool.record_established_source()` — **`3957fac`**
      - [x] **4A′** throttle-test measurement correction — pacing asserted at worker release, not
            server arrival. `throttle_worker.py` · `test_domain_throttle.py` — **`e3a8663`**
      - [x] **DV-9** pace lock fails closed; the caller translates it to a typed `lease_timeout`.
            `domainlease.py` · `httpclient.py` — **`bfde922`**
      - [x] **4B** `src/harvest/adapters/{base,feed,jsonapi,seed}.py` — three concrete adapters plus
            a contract layer; `sitemap` and `model_search` raise typed `AdapterNotImplemented`;
            synthetic fixtures (25 sources + 19 configured-host robots policy fixtures);
            `scripts/harvest/check_fixtures.py`;
            `tests/test_taxonomy_{adapters,source_cache,adapter_concurrency}.sh` — incl. seed depth
            hard-fixed at 1, fail-closed allowlist, and no child-body fetch — **`68b6c26`**

**Stage 3 status: complete**, closing at `68b6c26`. **567 assertions across 17 suites**, all green;
protected baseline 18/18; `check_fixtures.py` 25/25 sources · 19/19 hosts · 47 manifest entries;
`check_facets.py`, `gen_facet_schema.py --check` and `check_config.py` all exit 0. Zero tracked
modifications; the 508 pre-existing untracked files byte-identical; nothing pushed. No live request
of any kind was made. Completion handoff:
`docs/harvest/handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md`.

## Stage 4 — extract, classify, verify, dedupe ⟵ **S4-1…S4-5A COMPLETE. S4-5B NOT APPROVED.**

Plan: **`docs/harvest/STAGE_4_IMPLEMENTATION_PLAN.md`** — `Status: PROPOSED — PENDING DEVIATION
APPROVAL`. It is the design authority for Stage 4. Each of checkpoints S4-1 … S4-5 requires its own
separate approval, and approval of one grants nothing to the next.

Stage 4 is **metadata-only and entirely in-memory**: it reads no body, issues no request and writes
no file. **Target-page fetching, target fixtures, target-fetch and extraction ownership, body
parsing and alias adjudication are deferred to Stage 6.** Stage 4 modifies no schema, no config, no
adapter, `pool.py`, `sourcecache.py`, the HTTP code, or any existing test.

- [x] **DV-11 — approved.** `candidate_pool.v1.json` is **not** widened and stays payload-free.
      Candidate metadata lives in Stage 4's in-memory contracts and, later, under `provenance.raw`,
      which `record.v1.json` types as an unconstrained object. Forward consequence: the candidate-pool
      artifact carries no titles, dates, summaries or publishers — read records, never the pool
- [x] **S4-1** `src/harvest/dedupe.py` — same-topic dedupe over canonical identity plus the DV-11
      ingest model: `Delivery` · `CandidateObservation` · `CandidateGroup` · `DedupeResult` ·
      `group()`. One observation per distinct source item even when several lanes receive the same
      cached result; lane IDs and request keys merge into sorted, deduplicated provenance; ordering
      is the total content key `(role_rank, source_id, position, target_url)`; every metadata
      contribution and conflict retained; canonical-equivalence grouping only. **55 assertions**,
      `tests/test_taxonomy_dedupe.sh`
- [x] **S4-2** `src/harvest/extract.py` — metadata **normalization**, deliberately not body
      extraction: `ExtractedCandidate` · `ExtractionResult` · `NormalizationIssue` · `normalize()` ·
      `normalize_all()`. Display values follow S4-1's authority-then-content order; dates go through
      the committed `records.to_iso8601_utc` and an unparseable one becomes null **and is reported**;
      `identity_url` is consumed from S4-1, never recomputed; `canonical_url == identity_url`; no
      alias is produced; `access_status`, `http_status`, `content_hash`, `updated_at`,
      `last_checked_at` and `url_aliases` are structurally **absent**, because each needs a fetch.
      `designated_target_fetch_owner_lane_id` and `designated_extraction_owner_lane_id` stay null.
      **58 assertions**, `tests/test_taxonomy_extract.sh`
- [x] **S4-3** `src/harvest/classify.py` — the ten committed precedence rules over fourteen signals,
      evaluated as **data** read from `precedence.v1.json`: `Classification` · `Evidence` ·
      `CompetingCategory` · `classify()` · `classify_all()` · `signals_for()` · `load_precedence()`.
      First rule by committed `order` wins; every other firing rule is retained in
      `competing_categories`; R10 falls back to the discovery cell and records the remaining
      contexts. Evidence quotes the text that matched; the rationale is derived from the rule that
      fired. A lane ID, a request key and an ownership designation are none of them readable from
      the module. A rule may assign a topic other than the discovery topic — that is **recorded, not
      resolved**; cross-topic ownership stays Stage 5. **61 assertions**,
      `tests/test_taxonomy_classify.sh`
- [x] **S4-3A — corrective, completed before S4-4.** Precedence keyword matching made **explicit**:
      whole casefolded **tokens**, never an arbitrary substring, with `*` as the one declared
      token-prefix stem. `ide` matches `IDE` but not `guide`; `product` matches `product` but not
      `production`; `deprecat*` matches deprecate/deprecated/deprecation but not `undeprecated`;
      phrases respect token boundaries at both ends. The evaluator stays generic — a test asserts no
      configured term and no signal name appears as a string literal in `classify.py`.
      **Config changes: exactly two terms** — `deprecat` → `deprecat*` (the only configured term that
      is not a standalone word), and the lone Japanese term **removed** from
      `is_funding_or_ma_event`, where it had sat since `0edbf50`: token matching needs word
      separators, so a script without them cannot work absent segmentation this pipeline
      deliberately does not have, and keeping it would be an inert claim of multilingual coverage.
      Every other keyword unchanged. Semantics recorded in `STAGE_4_IMPLEMENTATION_PLAN.md` §4A and
      mirrored into the config's `_matching_about` / `_language_scope_about` keys.
      **+17 assertions** (61 → 78)
- [x] **S4-4** `src/harvest/verify.py` — the four committed scores and the accept/reject gate:
      `Scores` · `Verdict` · `ScoreEvidence` · `score()` · `decide()` · `verify()` · `verify_all()` ·
      `thresholds_for()`. Every weight, threshold and the 90-day half-life are read from
      `policy.v1.json` — a test asserts **no policy number appears as a numeric literal** in the
      module, checked on AST constants. Threshold selection is by the **classified** cell, honouring
      an optional `scoring.thresholds_by_cell` override if one is ever added. Relevance uses the
      classified category's own `require_any`/`boost`/`exclude` vocabulary through **classify's
      committed token matcher** (S4-3A) — no second matching semantics. An unknown publication date
      gives `freshness: null` and a composite **renormalized over the scored dimensions**, never 0.0,
      which would assert the item is old. Every verdict carries the honest no-enrichment values:
      `access_status "not_checked"`, `http_status null`, `verification_status "unverified"`,
      `content_hash null`, no invented timestamp. Rejections keep their scores and use only
      `record.v1.json`'s committed enum, with a detail naming the exact rule and number. Nothing is
      written to disk. **63 assertions**, `tests/test_taxonomy_verify.sh`
- [x] **S4-4A — scoring calibration conclusion (documentation only, no code).** Measured over the
      109 fixture-derived candidates: **4 accepted (3.7%)**, rejected by `off_topic` 102 and
      `min_relevance` 3, every other gate 0; minimum composite among candidates passing relevance and
      quality **0.7189**, i.e. `+0.3189` over the threshold. Conclusions, recorded in the plan §S4-4A:
      `min_audience_fit` is **structurally non-binding** under the current binary audience-fit and
      gate ordering · `accept_composite=0.40` is **slack on this corpus, not proven universally
      inert** · `min_quality` is **capable of binding** but was pre-empted by relevance on all 5
      candidates below it · **freshness still contributes** to the composite though it changed no
      fixture verdict · **synthetic parser fixtures are unsuitable for tuning editorial acceptance
      thresholds** (102 of 102 `off_topic` candidates would also have missed `require_any` in their
      *discovery* cell) · **calibration of audience fit, the composite threshold and acceptance rates
      is deferred to the Stage 9 bounded live corpus** · **`SATURATION=3` and the `0.68/0.32`
      required-versus-boost split are provisionally approved** until then. Corrective options were
      evaluated and rejected on evidence: dropping the early exclusion gate changes zero verdicts, and
      grading audience fit to 0.50 still leaves the minimum composite at 0.6189. **No S4-4 corrective
      code or config change was required.**
- [x] **S4-5A** `src/harvest/facetassign.py` — deterministic `case_facets` assignment:
      `FacetAssignment` · `assign()` · `assign_all()` · `applicability()`. Values come only from the
      committed vocabularies, matched with **classify's committed token matcher** (S4-3A) — no second
      vocabulary or matching system. `INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS` keeps `publisher` out of
      industry evidence and `TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS` additionally keeps
      `target_url` out of `technology-software`; `LEXICAL_SUPPORT_REQUIRED` is gated through
      `facets.evidence_supports`; `classification_state` comes from
      `facets.decide_classification_state` and is never recomputed. A tie between two equally
      supported industries resolves to the committed `other-unclear` sentinel with both names
      recorded — never to a slug sort. Gated, report-only and forbidden cells are distinguished, and
      a forbidden topic returns an **explicit not-applicable** rather than an empty payload, which
      `reporting_state` would miscount as `unresolved` instead of `not_enriched`. Payloads validate
      against `facets.generated.v1.json`. **63 assertions**, `tests/test_taxonomy_facetassign.sh`
- [x] **S4-5A-C** *(corrective)* removed the standalone synonym `IT` from `it-infrastructure` in
      `config/harvest/facets/business-functions.v1.json` and regenerated
      `schemas/harvest/facets.generated.v1.json` with the committed generator. Facet matching is
      case-insensitive and token-based by design, so `IT` was indistinguishable from the English
      pronoun and assigned `it-infrastructure` to any document containing an ordinary "It …",
      quoting the pronoun as evidence. Corrected in the **vocabulary, not the matcher**: no
      case-sensitive exception, no `facetassign.py` change, no tokenization change, no invented
      replacement acronym, no other term touched. The specific committed terms — `infrastructure`,
      `IT operations`, `platform operations`, `ITSM`, `internal IT`, `cloud operations` and the rest
      — remain the supported evidence path. The vocabulary and its generated schema are one atomic
      contract (the schema pins the vocabulary's SHA-256), so both are in the same commit.
      **68 assertions** (was 63; the CF-12 pin is replaced by six regression tests),
      `tests/test_taxonomy_facetassign.sh`
- [ ] **S4-5B** in-memory record construction and schema validation.
      **NOT APPROVED; not started**

**S4-5A gate:** 884 assertions across 22 suites, all green (567 prior + 55 S4-1 + 58 S4-2 + 78
S4-3/S4-3A + 63 S4-4 + 63 S4-5A). All prior assertions unchanged and unmodified. All five checkers
exit 0; the 508 pre-existing untracked files byte-identical; `.gitignore` still exactly
`1 insertion(+)`. `config/`, `schemas/`, `verify.py`, `classify.py`, `extract.py`, `dedupe.py`,
`facets.py` and `records.py` all byte-unchanged.

**S4-5A-C gate:** 889 assertions across the same 22 suites, all green (884 − 1 removed CF-12 pin
+ 6 new regression tests). Only `tests/harvest/test_facetassign.py` changed among tests; no other
suite was touched and no prior assertion was weakened. Under **CF-6** the pre-commit run showed 16
suites failing on the dirty-config epilogue alone — 15 wrapper epilogues plus `test_taxonomy_config.sh`
section H — every one naming only `config/harvest/facets/business-functions.v1.json`, with all
behavioural assertions green; all 22 suites are green from the committed tree. (CF-6 recorded 14
suites when measured at S4-3A with 20 suites; the count grew with the two suites added since.) All
five checkers exit 0 including `gen_facet_schema.py --check` and `check_facets.py`; the 508
pre-existing untracked files byte-identical; `.gitignore` still exactly `1 insertion(+)`.
`facetassign.py`, `facets.py`, `records.py`, `verify.py`, `classify.py`, `extract.py`, `dedupe.py`
and `pool.py` all byte-unchanged — the correction is entirely in the vocabulary and its generated
schema.

**CF-11 (secondary industries, → the facet-quality stage).** `industry.secondary` is left empty. The
committed definition means **deployment context, never corporate portfolio** — a judgement lexical
evidence cannot make, so filling it with runners-up would manufacture findings.

**CF-12 (short vocabulary terms) — CLOSED by S4-5A-C.** `it-infrastructure` listed the term `IT`,
which matched the English pronoun "it" as a whole token. Token matching was behaving exactly as
S4-3A specifies; the sharp edge was in the committed facet list, and that is where it was fixed —
the term is gone and the generated schema regenerated. The residual class of finding, that other
terms may still be too weak to carry evidential weight, stays with **CF-5** and **CF-8**. A test now
pins the class: no term on any axis is a bare English pronoun.

**S4-4 gate:** 821 assertions across 21 suites, all green (567 prior + 55 S4-1 + 58 S4-2 + 78
S4-3/S4-3A + 63 S4-4). All prior assertions unchanged and unmodified. All five checkers exit 0; the
508 pre-existing untracked files byte-identical; `.gitignore` still exactly `1 insertion(+)`.
`config/`, `schemas/`, `classify.py`, `extract.py`, `dedupe.py` and `pool.py` all byte-unchanged.

**S4-4 design decisions, recorded because the committed config does not fix them.** `policy.v1.json`
supplies the weights, the four thresholds and the half-life, but **no formula shape** for any score.
The shapes are defined in `verify.py`, with every constant named, bounded and documented, and
deliberately chosen not to equal any policy number so the two can never be confused:

- **relevance** — the classified category's vocabulary: `exclude` match ⇒ 0.0; a non-empty
  `require_any` with no hit ⇒ 0.0; otherwise a saturating blend of required and boost hits.
- **quality** — observable evidence completeness (title, summary, publisher, date; a stub summary
  counts half) plus a capped corroboration bonus per additional independent source. `source_tiers`
  is **unused**: no configured source declares a tier, so `provenance.source_tier` stays null rather
  than being guessed from `role` — see **CF-9**.
- **audience_fit** — 1.0 unless the classified category's own `exclude` list fires, in which case
  0.0 and `developer_only_audience` when classify's `is_developer_tool` signal also fires.
- **freshness** — exponential decay over the committed 90-day half-life against an injected clock;
  null when no usable date exists.

**CF-7 (rejection vocabulary, → Stage 5).** `record.v1.json` has no `below_composite_threshold` and
no audience-fit-specific value, so a composite or audience_fit failure is reported as the closest
honest reason with the detail naming the actual rule and number. Sits with **CF-2**.

**CF-8 (unmatchable configured terms, → the relevance-tuning stage).** Two of the 214 category
relevance terms — `%` in `cases__case-studies` boost and `$` in `discourse__market-and-investment`
boost — contain no word character and so cannot participate in token matching. They are skipped
deterministically and **reported** on `Scores.unusable_terms` rather than dropped silently or
allowed to abort a batch. Both are already covered by regex patterns in `precedence.v1.json`, so
nothing is actually lost.

**CF-9 (source tiers, → the relevance-tuning stage).** `policy.v1.json` defines four tier weights,
but no configured source declares a tier and `taxonomy.v1.json`'s source object is
`additionalProperties: false`. Quality therefore uses observable evidence rather than authority.
Wiring tiers needs a schema change and its own deviation.

**S4-3A gate:** 758 assertions across 20 suites, all green (567 prior + 55 S4-1 + 58 S4-2 + 78
S4-3/S4-3A). All prior assertions unchanged and unmodified except the two in `test_classify.py` that
explicitly pinned the superseded substring interpretation. `check_fixtures.py`,
`verify_protected_baseline.sh`, `check_facets.py`, `gen_facet_schema.py --check` and
`check_config.py` all exit 0; the 508 pre-existing untracked files byte-identical; `.gitignore` still
exactly `1 insertion(+)` against the anchor. `pool.py`, `dedupe.py`, `extract.py` and every schema
remain byte-unchanged; `precedence.v1.json` is the only config file Stage 4 touches.

**Carried forward to Stage 8 (CF-6), recorded not acted on:** no checkpoint that edits `config/` can
pass the full gate **before** committing. 14 of the 20 taxonomy suites assert
`git status --porcelain --untracked-files=no -- state/ config/` is empty — 13 as a wrapper epilogue,
one as `test_taxonomy_config.sh` section H. The guard exists to catch a *test* mutating production
config and compares the working tree to HEAD, so it cannot distinguish that from an authorized
checkpoint edit. Measured in S4-3A: **755/756 behavioural assertions green pre-commit**, the single
failure being the guard itself, and **all 20 suites fully green immediately after the atomic
commit**. Fixing it means changing the guard from "config is unmodified" to "config is unchanged
**by this test**" across 14 existing test files, alongside the `validate_task.sh` wiring.

**Carried forward as CF-5, recorded not acted on:** keyword-list tuning under the new token
semantics. Plurals of single-token nouns no longer match (`benchmark` ≠ "benchmarks"); no `*` was
added to them, because the config hand-enumerates inflections elsewhere (`raises`/`raised`,
`acquires`/`acquired`) and blanket stemming would be destructive (`app*` would match "approach").
`abstract:` loses its trailing punctuation to tokenization and so also fires on a bare "abstract";
`ci/cd` is a two-token phrase and so also matches "ci cd".

## Stage 5 — cell worker, orchestration, cross-topic, staging

- [ ] `scripts/harvest/harvest.sh` (dispatcher) · `harvest_cell.sh` · `run_topics.sh` · `merge_topic.sh`
- [ ] `src/harvest/{plan_cells,build_content_index,resolve_cross_topic,validate_candidate}.py`
- [ ] `tests/test_taxonomy_cell.sh` · `test_taxonomy_concurrency.sh` · `test_taxonomy_recovery.sh`
- [ ] `tests/test_taxonomy_cross_topic.sh` — 4 policies + order-independence
- [ ] `tests/test_taxonomy_matrix_boundary.sh` — 5 proofs
- [ ] `tests/test_taxonomy_staging_isolation.sh`

## Stage 6 — refresh, link-check, diff, promote

**Target-page fetching lands here**, deferred from Stage 4: the target-fetch coordinator, target-page
fixtures and the robots fixtures their hosts need, `adapter_mode="record"`, per-child robots, body
parsing and `content_hash`, and alias adjudication (301/308 aliases, `rel=canonical` trust tiers,
alias conflicts). Until then `designated_target_fetch_owner_lane_id` and
`designated_extraction_owner_lane_id` stay null, which is their committed meaning.

- [ ] `scripts/harvest/{refresh,linkcheck,promote,diff,compare-runs}` subcommands
- [ ] Transaction journal, before-images, per-operation commit record, rollback, resume
- [ ] `--publication-root` for isolated testing
- [ ] `tests/test_taxonomy_linkcheck.sh`
- [ ] `tests/test_taxonomy_promote_txn.sh` — 4 fault-injection points + add/remove/partial modes

## Stage 7 — migration

- [ ] `src/harvest/migrate/{base,ax_cases,entity_assess}.py` + `scripts/harvest/migrate.sh`
- [ ] Suspicious-URL guard (`ambiguous_legacy_url`, never rewrites)
- [ ] `tests/test_taxonomy_migration.sh` — apply twice, 231 stable, protected data unchanged
- [ ] `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md` (read-only)

## Stage 8 — harness wiring and full offline regression

- [ ] `scripts/validate_task.sh` — new tests in the case table and `ISOLATED[]`
- [ ] `bash scripts/validate_task.sh --all` green, including the 64 unchanged matrix assertions

## Stage 9 — bounded deterministic live smoke

- [ ] `scripts/harvest/{smoke,smoke_model}.sh` + `preflight-sources`
- [ ] 12-category smoke, `--no-enrich`, twice, + `compare-runs --normalize`
- [ ] `linkcheck --sample 20`
- [ ] **Requires explicit user confirmation** — outbound requests and production runtime state

## Stage 10 — final report

- [ ] `docs/harvest/IMPLEMENTATION_REPORT.md` — every file created/changed, exact commands, results
- [ ] `docs/harvest/CONVERGENCE_NOTE.md` — 5 gates before matrix unification is reconsidered
- [ ] Unresolved issues, limitations, blocked sources, recommended follow-up

---

## Follow-ups explicitly OUT OF SCOPE for this task

1. **Pre-existing untracked scratch noise.** 508 untracked files at session start (`.scratch_ax/`
   445 files, 56 `state/_*` scratch files, a 570 KB root log, 4 uncommitted agent specs). They are
   baseline-verified and must remain byte-identical. Cleaning or gitignoring them is a separate
   decision — this task added exactly one ignore rule, for its own runtime namespace.
2. **Entity registry migration.** 1,161 entities are assessed (Stage 7) but not migrated; their
   destination taxonomy is an open product decision. No `Dev Tools` topic was invented.
3. **Matrix convergence.** Gated behind the 5 criteria in `CONVERGENCE_NOTE.md`. The matrix path is
   not deprecated.
4. **GitHub star backfill** (handoff item 3) and the **harvest→pipeline bridge** (handoff item 5)
   remain open in the legacy pipeline and are untouched here.
