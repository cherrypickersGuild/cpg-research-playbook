# Stage 6 completion handoff — target fetching and verification

**Date:** 2026-07-30 · **Branch:** `main` · **Closing implementation commit:**
`7aa1ccec439162d238ad87fd00c3b543ed3e8f55`

A durable milestone summary, not a session log. It records what Stage 6 delivered and the state the
repository was in when Stage 6 closed.

**It approves nothing.** It does not authorize a further implementation checkpoint, it does not open
Stage 7, it does not grant live network access, and it does not authorize a push. Stage 6's own live
smoke, S6-L, was never approved and was never run (§5). A completed stage and a green gate do not
together open the next one — the rule that governed every checkpoint below does not lapse at closure.

---

## 1 · Commit chain

```text
7aa1ccec439162d238ad87fd00c3b543ed3e8f55  test(harvest): prove target determinism and recovery   S6-7
1e0a0289074b46cdb0e91bcb88f09977f0d72329  fix(harvest): persist target evidence in ledgers       S6-6B
88d40cab3e916ab931bcbf382b6592d3285812e7  feat(harvest): report target request accounting        S6-6A
fa6301290de13006a361c8bc6fcc12b77b5866a2  feat(harvest): add alias conflict reporting            S6-6
461d79534e8c387a8b0b58fe4667c29c4811db3e  feat(harvest): add target evidence                     S6-5
7a86e60abbc4cfd7a57d3d61dc8f95e07d72228f  feat(harvest): add target fetch ownership              S6-4
d0a9ffedba1f133e842d957308155a5c8624f4e5  test(harvest): add lease timeout diagnostics           S6-TD
39b709b240d8179b9e9161f394442933e71ae6bf  feat(harvest): add alias adjudication                  S6-3
75a0bb6b2f82cb0e3ece3046047430d3ab555395  fix(harvest): align canonical domain policy            S6-2-C
e4a12b97c20dbd9f1964b3509ce41f3b7b6d6646  feat(harvest): add target fetch outcomes               S6-2
4df53801e4e25efc2e177805952004bde0d995b6  test(harvest): add target fixture corpus               S6-1
62fd40db36e6256ac3f2c5ffc1508268355ac2f6  docs(harvest): correct stage 6 fixture scope           S6-0-C
bc30419cb8399fa1862fc126e59c0137208c7c8b  docs(harvest): resolve stage 6 design decisions        S6-0
f2765def8df520d432f76bb0d3db443ecca24dbf  docs(harvest): plan stage 6                            S6-0
6bf7f51362863bdc12749a2cc86fb8a0668bc737  Stage 5 closeout baseline
8865c54e2cc8d879410576f247baac4aea149f34  implementation-start anchor (protected baseline measured here)
```

This documentation closeout commit sits on top of `7aa1cce` and changes exactly three documentation
paths; its hash is reported in the execution record rather than written into the files it commits.

Plan of record: `docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md`. Every checkpoint committed alone, each
separately approved **by name**, each gated by its narrowest suite before the next began. Two
checkpoints in the chain are **preflight corrections that stopped without editing a file** (S6-0-C,
S6-2-C), and two are corrections found by a read-only audit of the checkpoint that would have depended
on them (S6-6A, S6-6B) — §2.3.

## 2 · Delivered

**Production modules — three new, and three touched by explicit authorization.**

```text
NEW      src/harvest/targetfetch.py    one target page, fetched through the injected client
         src/harvest/aliases.py        redirect and rel=canonical adjudication
         (S6-1 extended src/harvest/fixtures.py; no new module)

TOUCHED  src/harvest/run_cells.py      the fetch phase, evidence routing, conflict routing,
                                       accounting, ledger observation
         src/harvest/records.py        one keyword-only url_aliases parameter (D6-A)
         src/harvest/artifacts.py      conflict artifact, target accounting, eligibility

UNTOUCHED, and asserted so: pool.py · httpclient.py · coverage.py · facets.py · verify.py ·
classify.py · extract.py · dedupe.py · facetassign.py · ledger.py · every Stage 1-4 schema
```

**Schemas — one added, one widened, both by a resolved decision.** `alias_conflict.v1.json` was
committed under D6-B; `run_manifest.v1.json` gained three optional integer keys under S6-6A. No other
schema changed, and no committed schema field was removed or narrowed.

### 2.1 · What each checkpoint established

- **S6-1 — the fixture corpus, loader and checker.** 24 literal target fixtures and 2 robots fixtures
  under `tgt.harvest.test` / `tgt-robots-denied.harvest.test`; `fixtures.load_target_fixtures()` and
  `FixtureOpener(targets=…)` sharing **one** exact-URL index whose collision names both claimants;
  `check_fixtures.py` treating `TARGET_FIXTURE_IDS` as a declared set checked in both directions and
  refusing any transport-simulation key, importing that forbidden-key set from `fixtures.py` rather
  than re-listing it. `targets=None` means no targets, so every committed caller is byte-identically
  unaffected. **Discharges CF-3. 70 assertions.**
- **S6-2 — typed fetch outcomes and the exhaustive failure mapping.** `TargetFetchOutcome` ·
  `fetch_target()` · `ACCESS_STATUS_FOR_ERROR` · `TargetFetchError`. Exactly one logical client call;
  injected client, budget and clock; no system clock. Retries, robots, redirects, timeouts and the
  body cap are all left to the committed `HttpClient`, whose final response or final typed error is
  the only thing consumed. **All ten committed `HttpError` classes are mapped, enumerated from the
  AST and each one instantiated and exercised**; an unmapped subclass raises rather than receiving
  the nearest plausible status. **61 assertions.**
- **S6-3 — redirect and `rel=canonical` adjudication.** `aliases.py`: `adjudicate()` ·
  `extract_rel_canonical()` · `AliasConflict` · `CANONICAL_SCAN_BYTES` · `load_canonicalization()`.
  Both public functions pure relative to explicit inputs; the cached loader is the one impure
  function and sits outside them. **`urlkey.registrable_host` is the sole canonical-domain
  authority** — no second host comparison exists, and the helper itself is unchanged. Permanence is
  read from the S6-2 outcome's flag, never inferred from a hop count. `identity_url` is compared but
  never returned; `record_id` and `content_id` are unreachable from the module, proved with
  test-local sentinels across all eight row shapes. Robots arrives as an injected verdict, and
  `False` **and** unknown both decline. **81 assertions.**
- **S6-4 — ownership, deduplication and bounds.** `pool.add_candidate` → `pool.acquire_target_fetch`
  as the ownership gate; one `fetch_target()` per canonical identity with the **same outcome object**
  reused by every owner; a **run-scoped** pool and outcome map, so one identity is one fetch across
  cells *and* topics; per-owner `adjudicate()`; `MAX_TARGET_FETCHES_PER_CELL = 25` on top of the
  committed `cell:` budget, which discovery and fetching now share. Accepted candidates only, in
  committed `candidate_key` order. Budget-skipped targets are recorded as `not_checked` through the
  committed S6-2 dataclass **with no client call**. Sequential throughout — no thread, process, lock
  or async — so CF-1 stays untriggered with exactly one caller of the unlocked gate. **32
  assertions.**
- **S6-5 — target evidence and alias projection.** `records.make_full_record` gained **only** the
  resolved D6-A parameter, keyword-only `url_aliases=None`, plus `normalize_url_aliases()` and
  `RecordError`; it stays the **sole owner of the persistent record shape**, validating, projecting
  to the four schema-admitted keys, deduplicating and ordering by `(kind, url)`, and refusing before
  the record is assembled. Omission still yields `"url_aliases": []` byte-for-byte. **The difference
  set between a fetch and a no-fetch record is exactly six fields** — `access_status`, `http_status`,
  `verification_status`, `verification_evidence`, `content_hash`, `last_checked_at`. Every score, the
  classification, the facet payload, `record_id`, `content_id`, `identity_url`, `cell_id` and
  `target_url` are byte-identical: **a fetch supplies facts and re-judges nothing.** **47
  assertions.**
- **S6-6 — the alias-conflict artifact, reporting and the eligibility proof.**
  `schemas/harvest/alias_conflict.v1.json` validates the **complete** document, envelope included, so
  a count disagreeing with its own rows cannot be written. `artifacts.py` gained
  `alias_conflicts_path()` · `conflict_id()` · `build_alias_conflicts()` · `write_alias_conflicts()` ·
  `alias_conflicts_count()`. The driver routes conflicts S6-3 already adjudicated, deduplicated
  run-wide by content. Written through the single S5-1 atomic writer **before** the manifest, which
  reads the count back from the validated document, so artifact and manifest cannot drift.
  `conflict_id` is a content hash, never positional. **An empty set still produces the artifact:**
  "found none" must be distinguishable from "nobody looked". §8 eligibility is proved in **both**
  directions, and no new predicate was added. **47 assertions.**
- **S6-6A — separated source and target request accounting.** `TargetFetchOutcome` gained one field,
  `accounting`, **copied** from the client's final `Response` or its typed error — never recomputed,
  never diffed from the shared `client.stats`. `artifacts.target_request_accounting()` sums the
  **run-scoped** outcome map once, at the manifest boundary, so a URL accepted in two cells or under
  two topics contributes once. Three optional keys — `target_http_attempts`, `target_retries`,
  `target_redirect_hops` — sit beside the owner counters; **`http_attempts`, `retries` and
  `redirect_hops` keep their source-only meaning, unchanged in value and in wording**, and there is
  no combined total. Omission and zero stay distinct via a `None` sentinel. `pool.py` and
  `httpclient.py` are byte-unchanged. **48 assertions.**
- **S6-6B — target evidence persisted into ledgers.** The run observation now carries
  `http_status`, `content_hash` and `last_checked_at`, **copied from the finished record** and joined
  by the `record_id` the observation already computes. Full records only — a `cross_reference` was
  never a page anyone fetched. No clock is read, and a field is written **only when the record
  carries a non-null value**, so a metadata-only record contributes none of the three, a
  budget-skipped target contributes no status and no hash, and a rejected candidate contributes
  nothing at all. `ledger.py` and every schema are byte-unchanged: all three fields have been
  storable since Stage 1, and only the wiring was missing. **11 assertions.**
- **S6-7 — determinism, ordering independence, composed scenarios, interruption and recovery.**
  Test and documentation only. Same-clock byte identity over the exact **43-path** tree, hashed and
  then compared file by file; cell, **source** and **candidate** ordering each shuffled
  non-vacuously at the boundary that can express it; four composed scenarios covering terminal
  failures, bodies and redirects, canonical adjudication and budget skipping; an interruption in the
  fetch phase publishing **nothing at all**, with the retry an ordinary fresh run producing a
  hash-identical tree; a finished `run_id` refused **before the first request and before the fixture
  corpus is loaded**. **88 assertions.**

### 2.2 · S6-7 — as shipped

A composed corpus is a **copy** of the committed fixture tree with target-fixture `status`, `headers`
and body substituted in the copy. `fixture_id`, the filename and the URL stay exactly as committed,
because the loader keys the corpus by filename and indexes it by URL, and because an accepted
record's identity must not move or the scenario stops being comparable to the clean run. **No
committed fixture, source fixture or topic configuration was edited**, and a test asserts
`tests/fixtures/harvest` is unmodified afterwards — a composer bug would otherwise silently edit the
corpus every other suite reads.

**The five clock-derived leaves are a property of the record-bearing artifacts over the committed
corpus, and S6-7 says so exactly** (erratum E19). Extended to the complete tree, three more families
carry instants of their own, each enumerated exactly and none excused:

```text
cells/ · topics/ · coverage.json · alias_conflicts.json   exactly harvest_run_id · generated_at ·
                                                          discovered_at · freshness_score ·
                                                          last_checked_at
runs/<id>/manifest.json      + started_at · finished_at   the run's own clock, in the document
                                                          that describes the run
rejections/<cell>.json       + rejected_at · freshness    `freshness` is the record's
                                                          `freshness_score` under the name
                                                          rejection.v1.json gives it
ledgers/<cell>.json          updated_at · first_seen_at · last_seen_at · last_checked_at
                                                          a CROSS-RUN store whose job is recording
                                                          when a URL was seen
```

A composed corpus that adopts an alias moves `observed_at`, and one that records a conflict moves
`detected_at`. Both are legitimate sixth and seventh clock-derived leaves, and **both are absent from
the committed corpus**. Those scenarios are therefore proved by **same-clock byte identity**, and the
five-leaf allowlist was never enlarged to admit leaves the committed corpus does not have.

### 2.3 · Corrections and defects, each found and fixed inside its own checkpoint

- **S6-0-C — fixture-scope correction** (erratum E15). An S6-1 preflight **stopped without editing a
  file**: the plan's corpus wording determined no literal, implementable fixture set. Corrected in the
  plan, not by widening S6-1. Two cases relocated to S6-4 after measurement (109 candidates, 109
  distinct identities, 0 shared across sources or topics, so neither case was expressible without an
  unauthorized fixture or config edit); three transport cases removed from Stage 6 outright; the
  corpus replaced by two literal tables.
- **S6-2-C — canonical-domain correction** (erratum E16). An S6-3 preflight **stopped without editing
  a file**. A three-way contradiction: plan §4 said same-domain trust was "identical host", a
  fixture's `contract_intent` claimed a cross-domain conflict, and the committed
  `urlkey.registrable_host` mapped both hosts to `harvest.test` — so the two rules returned **opposite
  verdicts** on the one fixture built to prove that row. `registrable_host` became the single
  committed authority; the fixture's canonical target moved to a genuinely different registrable
  domain. No second host comparison, no public-suffix implementation, and `registrable_host` itself
  unchanged.
- **S6-2 — the MRO defect, found by its own test.** A uniform MRO walk let the `HttpError` base entry
  answer for every subclass, silently defeating the fail-loud contract. Fixed with `EXACT_MATCH_ONLY`.
- **S6-4 — the eligibility ordering defect.** Ownership alone flipped a run to
  `publication_eligible: true` while every record still said `not_checked`. **The missing-target-
  evidence guard was brought forward from S6-6 to S6-4** — and only that guard.
- **S6-6 — the `conflict_id` test defect, found by its own test.** The content-derivation test indexed
  a row by position after the rows are sorted, so it asserted the sort order rather than the id. The
  production hash was correct; the test now selects by `identity_url`.
- **S6-6A — accounting propagation** (erratum E17). The S6-6 preflight proved an exact target-attempt
  count unreachable inside S6-6's boundary and **reported none rather than estimating one**. A
  read-only ownership audit then found the cause: §5.0's "never observes an attempt" was a stronger
  claim than the design needed. The fence — one logical call, no retry, timeout, redirect or
  body-size logic, no branch on any counter — stands; the sentence now says so.
- **S6-6B — ledger propagation** (erratum E18). Found by the read-only S6-7 preflight, which
  **stopped without editing a file**. Plan §7.4 described the ledger carrying the target triple as a
  finished flow; the schema, `OBSERVATION_FIELDS` and `merge_ledger` all supported it, and only the
  driver's observation did not supply it. No test caught it because none existed to: the ledger
  assertions covered counts, outcomes, `seen_count`, `first_seen_at` and sort order — every property
  except the one §7.4 claimed.
- **S6-7 — clock-family clarifications** (errata E19, E20, E21) and one defect **in the new suite
  itself**: the interruption class re-read the artifact root per test while one of its own tests
  deliberately writes into it, so the emptiness assertion passed or failed on alphabetical method
  order. The post-interruption state is now captured once in `setUpClass`.

### 2.4 · Deviations and scope additions, each separately authorized

Every item below was approved before it shipped. None is unauthorized drift.

```text
D6-A       records.py gains one keyword-only url_aliases parameter      resolved in S6-0, used at S6-5
D6-B       schemas/harvest/alias_conflict.v1.json is committed          resolved in S6-0, used at S6-6
S6-6A      run_manifest.v1.json gains three optional integer keys       approved as S6-6A, scoped by a
           targetfetch.py / artifacts.py / run_cells.py touched         read-only ownership audit
S6-6B      run_cells.py observation carries the ledger triple           approved as S6-6B, scoped by
                                                                        the S6-7 preflight
S6-4       config.bounds and the eligibility guard brought forward      approved within S6-4
S6-5       config.enrich brought forward from S6-6                      approved within S6-5
S6-TD      throttle_worker.py emits failure-only diagnostics            approved as S6-TD
S6-3       committed under a one-time gate-failure exception            granted explicitly, once
```

**Spent progress guards retired, each with the checkpoint that made it false.** S6-4 retired
`test_no_target_fetching_was_introduced` and one `target_fetch_owners == 0` assertion; S6-5 retired
six more, including `records.py` leaving the Stage 4 byte-unchanged tuple under D6-A; S6-6A retired
three forbidden target key names while **keeping** the `total_http_attempts` prohibition, which is not
spent. Renaming a key or a method to dodge a token scan was rejected each time, on the S5-4 precedent.

## 3 · Validation at closure

**The figures below are the S6-7 closing gate's, run once before `7aa1cce`. They were not
re-measured for this documentation-only closeout** — per the checkpoint's own risk tier the focused
suites and the full gate are not rerun for a documentation change (§11, S6-C).

**38/38 suites green in one full-gate run.** The count basis is stated explicitly, because it changed
during Stage 6: the figures carried through S6-6A and S6-7 are **unittest-only**, whereas Stage 5's
1,324 included the two shell suites.

```text
1,773  Python unittest assertions across 36 unittest suites
   42  shell-style assertions across 2 shell suites   (config 18 · protected baseline 24)
1,815  total counted assertions across all 38 suites
```

```text
adapter_concurrency 10   adapters 66     aliases 81      artifacts 33    budget 16
cell_artifact 44         classify 78     coverage 27     coverage_report 43
customer_interaction 13  dedupe 55       domain_throttle 44   eligibility 48
extract 58               facet_ambiguity 28   facet_identity 16   facet_states 32
facetassign 68           facets 34       http 80         identity 42     ledger 46
manifest 52              pool 57         records 51      recovery 75     run_cells 99
schema 35                source_cache 34 target_accounting 48  target_determinism 88
target_evidence 47       target_fetch 61 target_fixtures 71    target_ownership 30
verify 63                                              + config 18 · protected_baseline 24
```

**Checkers — all five exit 0**

```text
python scripts/harvest/check_fixtures.py             exit 0   25/25 sources · 19/19 hosts ·
                                                              24/24 targets · 73 manifest entries
bash   scripts/harvest/verify_protected_baseline.sh  exit 0   18/18 byte-match 8865c54e...
python scripts/harvest/check_facets.py               exit 0
python scripts/harvest/gen_facet_schema.py --check    exit 0
python scripts/harvest/check_config.py               exit 0
git diff --exit-code -- scripts/harvest/check_config.py       byte-unchanged (DV-1 intact)
git diff --stat 8865c54e... HEAD -- .gitignore                still exactly 1 insertion(+)
```

**CF-6 was never triggered in Stage 6.** No checkpoint edited `config/`, so every checkpoint passed
the full gate before its own commit.

**The representative end-to-end run**, over the committed fixture corpus with a pinned clock:

```text
43 files        12 cell artifacts · 3 topic artifacts · 12 rejection logs · 12 ledgers ·
                coverage.json · alias_conflicts.json · manifest.json · LATEST_RUN_ID
                the file set is asserted exactly; all 43 validate
records         4 accepted, all four target pages fetched, four distinct content hashes
eligibility     publication_eligible: true — all four §8 clauses hold on observed evidence
source acct     source_fetch_owners 25 · http_attempts 25    (SOURCE-ONLY, unchanged meaning)
target acct     target_fetch_owners 4 · target_http_attempts 4 · target_retries 0 ·
                target_redirect_hops 0
conflicts       alias_conflicts_count 0 — the artifact is still written
determinism     two runs, a shuffled-cell run, and shuffled source and candidate orderings all
                agree; two runs at different instants differ only at the enumerated leaves
```

**No repository runtime artifact was created** — `state/taxonomy_harvest/`, `data/harvested/`,
`runs/` and `LATEST_RUN_ID` are all absent from the repository; every run wrote to an injected temp
root. **No live request was made at any point in Stage 6**, by any checkpoint.

### 3.1 · Domain throttle — unexplained, instrumented, not fixed

**The instability is not fixed and is not claimed to be.**

```text
three signatures     remain UNEXPLAINED
S6-T                 attempted diagnosis; no reproducible production defect found; no file changed
S6-TD                added FAILURE-ONLY diagnostics to tests/harvest/throttle_worker.py
domainlease.py       byte-unchanged, as are httpclient.py and test_taxonomy_domain_throttle.sh
acceptance           no signature is accepted as a permanent flake
S6-3                 committed under a ONE-TIME approved gate-failure exception — one time, one
                     checkpoint, not a standing allowance
S6-7 closing gate    GREEN, with no throttle diagnostic emitted
```

Whichever checkpoint next sees a `LeaseTimeout` should read the `LEASE_TIMEOUT_DIAGNOSTIC` payload
rather than reason about the mechanism, and only then decide between a production defect and test
orchestration.

## 4 · Repository state at closure

State immediately **before** this documentation closeout commit:

```text
branch                  main (local)
implementation baseline 7aa1ccec439162d238ad87fd00c3b543ed3e8f55
anchor                  8865c54e2cc8d879410576f247baac4aea149f34
origin/main             6bf7f51362863bdc12749a2cc86fb8a0668bc737  (Stage 5 closeout)
position                0 behind · 14 ahead — NOT PUSHED
index                   empty
tracked modifications   zero
untracked baseline      508 files, byte-identical; drift 0, missing 0, extra 0
protected baseline      18/18 byte-match the implementation-start anchor
runtime artifacts       none
```

**Nothing has been pushed.** Pushing is a separate, explicitly approved action
(`safe_push_main.sh --check`, then `--execute`) and was never bundled into a checkpoint.

## 5 · What Stage 6 deliberately did not do

- **S6-L, the bounded live smoke, was NOT EXECUTED.** It was **optional to Stage 6 closure** (plan
  §11.1: a green offline Stage 6 is a complete stage). **Live network access was never approved** —
  S6-L requires approval twice, once as a checkpoint and once immediately before it runs, and neither
  was given. It is **not** represented here as passed, failed, waived, N/A or completed: it was
  simply never authorized and never run. **No Stage 6 live request was made.**
- **No promotion.** Nothing was promoted into `data/harvested/`, which remains absent. Publication
  eligibility is a **fact about a run**, not permission to publish.
- **No transport simulation.** Timeout sequencing, a `500 → 200` retry transition and over-cap body
  generation stay owned by the committed `HttpClient` and its own tests; no fixture in the corpus,
  and none in a composed temp corpus, carries a transport-simulation key.
- **No run-level `robots_denied` scenario** (erratum E20). All four accepted targets and the feed that
  surfaces them share `github.com`, so denying that host stops discovery and the scenario would prove
  nothing about a denied *record*. `RobotsDenied → robots_denied` keeps its owner in
  `test_target_fetch.py`, and fixture #20 exists so a test can prove the denial preceded the fetch by
  asserting the file was never opened.
- **No concurrency.** Cells, sources and target fetches all run sequentially; a static scan fails on
  any concurrency primitive in the driver, the artifact writer and the two new modules.
- **No re-judging.** No score, category, facet or identity is recomputed after a fetch. No Stage 4
  threshold was recalibrated; calibration remains Stage 9.
- **No refresh, linkcheck, promote, diff or compare-runs subcommand**, no transaction journal and no
  `--publication-root`: those sit under the older Stage 6 heading and remain unscheduled and
  unapproved (erratum E11).

## 6 · Carried-forward findings

```text
CF-1   DEFERRED and still GUARDED. Stage 6 runs sequentially, so the unlocked pool paths keep zero
       concurrent callers. A static scan fails on any concurrency primitive. Any later change that
       runs cells concurrently must fix CF-1 FIRST, in its own checkpoint.
CF-2   / CF-7 unchanged. No rejection vocabulary was widened.
CF-3   DISCHARGED by S6-1 — the target fixture corpus exists, is complete against a declared table
       and is checked in both directions.
CF-5   / CF-8 / CF-9 unchanged; relevance and tier tuning stay with their later stage.
CF-6   never triggered in Stage 6; the procedure stays documented for a later config-editing
       checkpoint.
CF-11  unchanged and protected. industry.secondary stays empty.
CF-12  CLOSED at S4-5A-C; the residual class stays with CF-5 and CF-8.
       (CF-14 does not exist — a deliberate numbering gap, retained.)
CF-13  CARRIED FORWARD. A post-acceptance inaccessible record has no rejection path, deliberately.
CF-15  CARRIED FORWARD, premise CORRECTED by E16. urlkey.registrable_host is the committed
       authority; its best-effort last-two-labels limitation is an inherited Stage 1 tradeoff,
       gated behind the syntax and robots checks — not a new Stage 6 redesign task.
CF-16  CARRIED FORWARD. ResponseTooLarge, UnexpectedContentType and EmptyResponse still collapse
       onto `unreachable`; the exact class survives verbatim in verification_evidence.
CF-17  CARRIED FORWARD. updated_at stays null even when Last-Modified is present: promoting a
       transport header to a content-update claim would contradict a freshness_score computed
       before the fetch.
```

**Canonical robots evidence remains unwired.** `RobotsCache.get`, `.allowed` and `.crawl_delay` all
fall through to `_fetch()` on a miss or expired TTL, so none can be called without risking a request,
and `self._cache` is private state that reading would duplicate the TTL logic. **There is no committed
cached-verdict API.** Consequently `canonical_robots_allowed=None` throughout, a same-domain canonical
records a `canonical_robots_not_verified` conflict instead of adopting an alias, and every
committed-corpus record carries `url_aliases: []` with `canonical_url == identity_url`. A test pins
that, so the day robots evidence is wired the change is visible rather than silent.

**Errata recorded during Stage 6, not renumbered:**

```text
E15  the S6-1 corpus wording was neither literal nor implementable         → S6-0-C
E16  same-domain canonical trust is registrable-domain, not identical host → S6-2-C
E17  §5.0's "never observes an attempt" was stronger than the design needed → S6-6A
E18  §7.4 described a ledger flow that was never implemented                → S6-6B
E19  the five clock-derived leaves are a record-bearing-artifact property   → S6-7
E20  a run-level robots_denied is not expressible on the committed corpus   → S6-7
E21  the S6-7 scenario corpus is four scenarios, not one run                → S6-7
```

## 7 · Successor

**Stage 7 is not open.** Nothing in this handoff, and nothing in a green gate, approves it. No Stage 7
planning document exists, and the migration work under that heading remains unscheduled.

**S6-L remains available but unapproved.** Running it needs two separate approvals — one as a
checkpoint, one immediately before execution — and it writes only to a temp root, is never committed,
and never becomes a fixture without a separate recording checkpoint.

**Exact starting point for the successor**

```text
start commit    this documentation closeout commit, on top of 7aa1ccec4391...
anchor          8865c54e2cc8d879410576f247baac4aea149f34  (protected baseline measured here)
assertions      1,815 across 38 suites (1,773 unittest + 42 shell), all green
push state      origin/main at 6bf7f51 (Stage 5 closeout); every Stage 6 commit unpushed
```

**Constraints the successor inherits.** The 18 protected files and the 508 pre-existing untracked
paths stay byte-identical; `.gitignore` stays at exactly `1 insertion(+)` against the anchor.
`pool.py`, `httpclient.py`, `ledger.py`, `coverage.py`, `facets.py`, `verify.py`, `classify.py`,
`extract.py`, `dedupe.py` and `facetassign.py` remain byte-unchanged unless a checkpoint explicitly
authorizes otherwise. A vocabulary file and `facets.generated.v1.json` are **one atomic contract**.
Any checkpoint that edits `config/` inherits the CF-6 procedure. Every artifact is serialized by the
single S5-1 function and written by the single S5-1 atomic writer. `LATEST_RUN_ID` is written last, or
not at all. **Source and target request accounting are two key spaces and are never summed.** A
boundary test asserts facts about the surface of the module under test — never which files exist yet,
and never how the working tree compares to HEAD for a module the same stage may edit.

**Three structural notes.** First, **there is no resume**: an interrupted run publishes nothing and
the retry is an ordinary fresh run, which is why determinism is what makes recovery safe. Second,
**one canonical identity is one fetch per run**, and every record owning it receives the same outcome
object — any future concurrency change must preserve that before it preserves anything else. Third,
**a plan section written in the present tense is a claim, and a claim with no test is a guess**: E18
cost a checkpoint because three sentences describing a finished flow read exactly like the sections
around them that were real.
