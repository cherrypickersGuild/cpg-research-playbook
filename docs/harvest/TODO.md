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
assertions:                  622 across 18 suites, all green (567 prior + 55 from S4-1)
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

## Stage 4 — extract, classify, verify, dedupe ⟵ **S4-1 COMPLETE. S4-2 NOT APPROVED.**

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
- [ ] **S4-2** `src/harvest/extract.py` — metadata normalization (not body extraction).
      **NOT APPROVED; not started**
- [ ] **S4-3** `src/harvest/classify.py` + `tests/test_taxonomy_classify.sh` — all 10 precedence rules
- [ ] **S4-4** `src/harvest/verify.py` — scoring and the accept/reject decision
- [ ] **S4-5** `src/harvest/facetassign.py` + in-memory record construction

**S4-1 gate:** 622 assertions across 18 suites, all green (567 prior, unchanged and unmodified, plus
55 new). `check_fixtures.py`, `verify_protected_baseline.sh`, `check_facets.py`,
`gen_facet_schema.py --check` and `check_config.py` all exit 0; `check_config.py` byte-unchanged; the
508 pre-existing untracked files byte-identical; `.gitignore` still exactly `1 insertion(+)` against
the anchor. No existing assertion was modified. `pool.py`, every schema and every config file remain
byte-unchanged.

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
