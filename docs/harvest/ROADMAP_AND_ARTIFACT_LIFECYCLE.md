# Taxonomy harvest — roadmap and artifact lifecycle

A **durable operational map**, not a session handoff. It answers four questions the stage handoffs
deliberately do not: *what exists in code right now*, *what JSON any of it actually produces*, *what
still has no implementation at all*, and *how far the project is from a published dataset*.

**Authority.** Committed code and executable tests outrank `IMPLEMENTATION_PLAN.md` wherever they
differ. **Every capability claim below was re-checked at Stage 9 closeout against the closing
executable baseline `ec9bedc5f209927ffd2899126ff20c2b31af0245`** (the S9-C documentation commit
contains no executable change); where the master plan describes something with no executable owner,
that is recorded as a gap rather than as a feature. Inference is labelled inference.

**Current authorities:** `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` and
`docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md`.
`docs/harvest/IMPLEMENTATION_PLAN.md` remains **design input only** — committed code and
current-stage records supersede it.

**This document opens nothing.** It is not a Stage 9 plan, it does not approve a checkpoint, and it
does not authorize a network request, a migration apply, or a promotion.

---

## 0 · The eight layers, and why "done" is never enough on its own

Every status word in this file is qualified by exactly one of these. They are ordered by increasing
distance from a real product artifact, and **nothing has ever reached layer 5, 6, 7 or 8.**
Stage 9 reached **layer 3** — but externally, and as *evidence*, not as a candidate.

| # | Layer | Meaning | Reached? |
|---|---|---|---|
| 1 | **Fixture run** | The pipeline driven over `tests/fixtures/harvest/**`, synthetic hand-authored inputs, no socket | **Yes**, routinely |
| 2 | **Temporary-root run** | Real writer code writing a real tree, into an injected `tmp` root that is deleted afterwards | **Yes**, routinely |
| 3 | **Retained runtime run** | Artifacts left on disk for a human to read | **YES — externally.** Three runs in the retained Stage 9 root (two smokes + one linkcheck). The repository path `state/taxonomy_harvest/` deliberately still does not exist |
| 4 | **Migration bundle** | The AX corpus converted to `record.v1.json` rows and published as one 3-file bundle | Temp-root only (layer 2) |
| 5 | **Candidate output** | A retained run's records, staged and awaiting human review | **No.** Retained runs now exist, but a smoke and a linkcheck can never be candidates — `derive_publication_eligibility` refuses every non-`harvest` mode, and no production `harvest` command exists |
| 6 | **Publication-eligible candidate** | A reviewed candidate set that `promote` would accept | **No** |
| 7 | **Promoted publication** | JSON committed under `data/harvested/**` | **No** — directory absent, no promotion code |
| 8 | **Website-consumed dataset** | `cherryinthehaystack.com` reading that JSON | **No** — no consumer, no owner, no interface |

A **retained runtime run** (3) is the first layer whose output survives the process that made it.
**Stage 9 delivered it** — three runs, externally retained and validated. The next unreached layer is
**5**, and its blocking dependency is no longer a driver: it is that **no production `harvest`
command exists** and no human-review process is defined.

---

## 1 · Executive status

```text
closing executable       ec9bedc5f209927ffd2899126ff20c2b31af0245
baseline                 test(harvest): repair authoritative full-gate findings
                         The S9-C documentation commit is the commit containing these
                         closeout records; its SHA is intentionally not self-recorded
                         and its publication is a separate checkpoint.
completed stage          Stage 9 — CLOSED
next stage               Stage 10 — NOT OPENED
repository runtime paths ABSENT: state/taxonomy_harvest/, data/harvested/, runs/, LATEST_RUN_ID
external retained state  PRESENT — three runs in the retained Stage 9 root (§7.1a)
publication output state NONE. data/harvested/ ABSENT; no promotion code exists anywhere
migration state          Implemented and offline-proven; ZERO operational applies. No bundle retained
live-network state       FOUR separately approved executions, each run exactly once:
                           S9-L1 source preflight · S9-L2 smoke · S9-L3 smoke · S9-L4 linkcheck
milestones               M2 ACHIEVED · M3 ACHIEVED · M4 ACHIEVED · M5 UNOPENED
```

**Stage 9 completion is not production readiness.** It delivered a retained, validated,
**unpublished** evidence corpus. Publication, promotion and website consumption remain **zero**.

*Loopback traffic bound by a test suite on `127.0.0.1` is **not** live external traffic and is never
counted here; only the four checkpoints above contacted real hosts.*

**Core pipeline implementation and offline verification.** The discovery → extraction →
classification → verification → faceting → record → artifact chain is implemented end to end in
`src/harvest/**` and verified offline: `bash scripts/validate_task.sh --all` now exercises **63
wrappers (19 legacy + 44 taxonomy), each exactly once, zero skips, exit 0** — the authoritative gate,
green at `ec9bedc` with 43 unittest suites and 2,386 tests (§5a).

**Has a real live taxonomy harvest occurred?** **No — and the reason has changed.** The old blocker
is gone: `run_cells.run()` takes an injected `Transport`, `cli.py` owns the single live-opener
decision, and real requests have been made. The blocker now is that **no CLI command performs a
production `harvest`**: `cli.COMMANDS` holds `preflight-sources`, `smoke`, `validate`,
`compare-runs`, `diff` and `linkcheck` — there is no `"harvest"` key. `mode: "harvest"` exists in the
driver and is the **only** mode `derive_publication_eligibility` accepts, but **it has never run
live**. Every live run so far was a `smoke` or a `linkcheck`, and neither can ever be a production
candidate.

**Has an operational AX migration apply occurred?** No. `migrate.sh ax-cases --apply --state-root
PATH` works and is proven, but every apply in the repository's history went to an injected temporary
root that was then deleted. `state/taxonomy_harvest/` does not exist.

**Has any real `data/harvested/` publication occurred?** No — and no code could perform one.
`promotion_receipt`, `promotion_journal`, `publication_manifest`, `promote_staging`,
`promote_rollback` and `--publication-root` have **zero occurrences** in `src/`, `scripts/`,
`schemas/`, `config/` or `tests/`. Promotion exists only as design prose in
`IMPLEMENTATION_PLAN.md` §7.

**Next observable data-producing milestone.** **M5 — a reviewed production candidate.** Its blocking
dependencies are that no production `harvest` command exists and that human review has no artifact,
no acceptance criteria and no owner. M5 is **unopened**.

### 1.1 Four percentages, four different denominators

Percentages here are counts, not judgement. Each names its denominator explicitly; they are **not**
comparable to one another and must never be averaged.

| Dimension | Denominator | Value | Basis |
|---|---|---|---|
| **Named stage completion** | The **12** named stage labels: 0, 1, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10 | **11 of 12 closed = 92 %** | Stages 0, 1, 2, 2.5, 3, 4, 5, 6, 7, 8, 9 closed; **Stage 10 not opened** |
| **Implementation capability** | The **same 13** subsystems the master plan names as commands or producers (harvest driver, migrate, preflight-sources, smoke, smoke-model, compare-runs, linkcheck, refresh, promote, diff, publication manifest, promotion journal, `harvest.sh` dispatcher) | **8 of 13 = 62 %** | Implemented: run driver · `migrate` · `preflight-sources` · `smoke` · `compare-runs` · `linkcheck` · `diff` · the `harvest.sh` dispatcher. **Still absent: `smoke-model`, `refresh`, `promote`, the publication-manifest producer, the promotion journal** |
| **Live operational validation** | Any single live request | **1 of 1 = 100 %** | Real external requests occurred through four separately approved executions (S9-L1, S9-L2, S9-L3, S9-L4) |
| **Production publication** | 16 expected stable published JSON files (§6.3) | **0 of 16 = 0 %** | `data/harvested/` absent; no promotion code |

**The denominator of row 2 is deliberately unchanged at 13.** `validate` is a Stage 9 command that
the master plan's 13-subsystem list never named; adding it would silently redefine the denominator
and invalidate every earlier percentage in this file's history. It is recorded in the command matrix
(§8) instead.

The gap between 92 % and 62 % is still the most important fact here — and a second gap has replaced
the old one. **Stage completion measures approved-and-verified checkpoints, not operable commands;
and operable commands are not the same as a publishable product.** Stage 9 turned the library into a
program a human can run against real hosts. It did **not** produce anything publishable: the last
five subsystems are exactly the ones between evidence and a dataset.

---

## 2 · Stage progress map

Legend for the two evidence columns: **Temp-root only** = every write went to an injected root;
**Retained** = output left in the repository tree.

### Stage 0 — scaffold, baselines, ignore rules

| Field | Value |
|---|---|
| Purpose | Establish the runtime namespace, the immutable-file guarantees, and the ignore rule |
| Status | **CLOSED** |
| Principal capability | `protected_baseline.py` + wrappers (18 protected paths, working-tree bytes vs `git cat-file --filters` of anchor `8865c54e`); `untracked_baseline.txt` (508 files); one `.gitignore` line `/state/taxonomy_harvest/` |
| Wrote only to temp roots? | n/a — committed files only |
| Contacted network? | No |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `TODO.md` Stage 0 section |
| Remaining dependency | None |

### Stage 1 — dependencies, config, schemas, identity

| Field | Value |
|---|---|
| Purpose | The versioned taxonomy, the policy/precedence/canonicalization configs, all v1 schemas, URL identity |
| Status | **CLOSED** — 95 assertions / 3 suites |
| Principal capability | 12 cells · 25 sources in `config/harvest/topics/*.v1.json`; `record.v1.json` discriminated union; `schema.py` with a local `referencing` registry so validation never touches the network; `urlkey.py`, `slug.py`, `records.py` |
| Wrote only to temp roots? | n/a |
| Contacted network? | No |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `TODO.md` Stage 1 section |
| Remaining dependency | CF-9 — `policy.v1.json` defines four source-tier weights but no source declares a tier, and `taxonomy.v1.json`'s source object is `additionalProperties: false` |

### Stage 2 — HTTP baseline, domain coordination, budgets

| Field | Value |
|---|---|
| Purpose | A polite, budgeted, RFC 9309-correct HTTP client and cross-process domain pacing |
| Status | **CLOSED** — 199 cumulative assertions / 7 suites |
| Principal capability | `httpclient.py` with its **own** RFC 9309 longest-match robots matcher (stdlib `urllib.robotparser` implements the 1996 draft and errs *unsafely*); `domainlease.py` with a Windows-correct liveness probe; `budget.py` |
| Wrote only to temp roots? | Yes (lease trees under `tempfile.mkdtemp`) |
| Contacted network? | **No** — `test_taxonomy_domain_throttle.sh` uses real subprocesses against a **local** recording server |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `TODO.md` Stage 2 section |
| Remaining dependency | Domain-throttle intermittent signatures remain **unresolved diagnostics** (three distinct signatures; S6-T found no reproducible production defect, S6-TD added instrumentation only). Never to be accepted as a permanent flake |

### Stage 2.5 — case facets and shared discovery

| Field | Value |
|---|---|
| Purpose | The three facet vocabularies, the five-state facet model, the candidate pool and coverage primitives |
| Status | **CLOSED** — 387 assertions / 14 suites, committed `46ab67c` |
| Principal capability | `facets.py`, `pool.py`, `coverage.py`, `scheduler.py`, `request_key.py`; `facets.generated.v1.json` (generated, drift-tested, pins the vocabulary SHA-256) |
| Wrote only to temp roots? | Yes |
| Contacted network? | No |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `TODO.md` Stage 2.5 section |
| Remaining dependency | CF-11 — `industry.secondary` deliberately left empty; filling it from runners-up would manufacture findings |

### Stage 3 — discovery adapters

| Field | Value |
|---|---|
| Purpose | The `feed` / `jsonapi` / `seed` adapters and one-logical-fetch-per-request-key caching |
| Status | **CLOSED** at `68b6c26` — 567 assertions / 17 suites |
| Principal capability | `adapters/{base,feed,jsonapi,seed}.py`; `sourcecache.py`; 25 synthetic source fixtures + 19 robots fixtures; `check_fixtures.py`. `sitemap` and `model_search` raise typed `AdapterNotImplemented` |
| Wrote only to temp roots? | Yes |
| Contacted network? | No — fixtures are **synthetic and hand-authored, never captured**, so no live harvest was needed to build them |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md` |
| Remaining dependency | `model_search` adapter unimplemented — blocks any `smoke-model` capability |

### Stage 4 — extract, classify, verify, dedupe

| Field | Value |
|---|---|
| Purpose | The judgement layer: identity grouping, metadata normalization, precedence classification, scoring, faceting |
| Status | **CLOSED** — 940 assertions / 23 suites |
| Principal capability | `dedupe.py`, `extract.py`, `classify.py` (10 rules read as data, token matching per S4-3A), `verify.py` (4 scores, all constants read from `policy.v1.json`), `facetassign.py` |
| Wrote only to temp roots? | **Entirely in-memory** — Stage 4 writes no file at all |
| Contacted network? | No |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` |
| Remaining dependency | **S4-4A calibration is explicitly provisional and deferred to a live corpus.** Measured on 109 fixture candidates: 4 accepted (3.7 %), 102 `off_topic`, 3 `min_relevance`. `min_audience_fit` is structurally non-binding; `accept_composite=0.40` is slack on this corpus; `SATURATION=3` and the `0.68/0.32` split are *provisionally* approved. Synthetic fixtures are stated to be **unsuitable for tuning editorial thresholds** |

### Stage 5 — artifact persistence

| Field | Value |
|---|---|
| Purpose | Turn the in-memory Stage 4 pipeline into a deterministic, atomic, idempotent artifact tree |
| Status | **CLOSED** at `bc920b5` |
| Principal capability | `artifacts.py` (one serializer, `write_atomic` via `.tmp_<uuid4hex>_` sibling + `os.replace`, schema-validate-before-write, `WriteJournal`, `publish_run` with pointer-last ordering); `ledger.py`; **`run_cells.run()` — the only thing in this repository that drives a whole run** |
| Wrote only to temp roots? | **Yes, always** |
| Contacted network? | No |
| Retained runtime output? | **No** |
| Published output? | No |
| Completion authority | `handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md` |
| Remaining dependency | **`run()` is a Python function with no CLI.** `src/harvest/run_cells.py` has no `__main__`, no `argparse`, and no shell script invokes it. CF-1 (unlocked pool paths) stays deferred and is guarded by a static concurrency scan |

### Stage 6 — target fetching and verification

| Field | Value |
|---|---|
| Purpose | Fetch the item's own page, adjudicate aliases, attach target evidence, report conflicts |
| Status | **CLOSED** at `7aa1cce`, closeout `0d2da64` |
| Principal capability | `targetfetch.py` (exactly one logical client call, all ten `HttpError` classes mapped from the AST); `aliases.py`; run-scoped fetch ownership in `run_cells.py`; `alias_conflict.v1.json`; target request accounting kept in a **separate key space** from source accounting (no `total_http_attempts`) |
| Wrote only to temp roots? | Yes |
| Contacted network? | **No.** Every checkpoint S6-1 … S6-7 is fixture-backed with a no-socket assertion |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md` |
| Remaining dependency | **S6-L, the bounded live smoke, is UNEXECUTED and UNAUTHORIZED** — it required approval twice and received neither. The heading's `refresh` / `linkcheck` / `promote` / `diff` / `compare-runs` subcommands, the transaction journal and the promotion tests were **explicitly descoped** by plan §14 erratum E11 and remain untouched. CF-16: robots evidence stays unwired (`RobotsCache` has no cached-verdict API that cannot trigger a fetch) |

### Stage 7 — AX corpus migration

| Field | Value |
|---|---|
| Purpose | Convert the protected AX case registry into `record.v1.json` rows, offline and non-destructively; assess the entity registry read-only |
| Status | **CLOSED** at `c3d982c` |
| Principal capability | `migrate/{base,ax_cases,entity_assess}.py` + `scripts/harvest/migrate.sh`. Dry-run by default; `--apply --state-root PATH` publishes **one three-file bundle by a single directory rename** |
| Wrote only to temp roots? | **Yes — every apply, without exception.** An AST scan of the suite asserts no call site can pass `--apply` without an explicit `--state-root` |
| Contacted network? | No |
| Retained runtime output? | **No.** `state/taxonomy_harvest/` does not exist and that absence is the intended state |
| Published output? | No — migration is **not** promotion (§6.2) |
| Completion authority | `handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md` |
| Remaining dependency | An **operational default-root apply is separately unapproved**. 1,161 entities assessed, **0 migrated** — their destination taxonomy is an open product decision |

### Stage 8 — harness wiring and full offline regression

| Field | Value |
|---|---|
| Purpose | Wire the 39 taxonomy wrappers into `scripts/validate_task.sh` and prove one full offline regression |
| Status | **CLOSED and PUBLISHED** at `bf067303` |
| Principal capability | `ISOLATED[]` 19 → 58 entries (39 taxonomy wrappers individually, legacy 19 verbatim as a prefix); 50 additive case arms / 91 `add_test` calls; a harness-level `[ -e ]` check of all four runtime paths **before and after** the run that never deletes what it finds |
| Wrote only to temp roots? | Yes |
| Contacted network? | No |
| Retained runtime output? | No |
| Published output? | No |
| Completion authority | `handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md` |
| Remaining dependency | **CF-4 CLOSED — nothing else is.** CF-6 has *grown*: 33 of 39 wrappers now assert `config/` is unmodified, so no checkpoint editing `config/` can pass the gate before committing. S8-CF-1 … S8-CF-7 open (harness has no self-test; `CLAUDE.md` still calls `validate_task.sh` the single entry point without mentioning `--all`; `tests/harvest/*.py` unrouted in changed mode; `hash_tree.py` and `oss-milestones.v1.json` have zero consumers) |

### Stage 9 — bounded live validation

| Field | Value |
|---|---|
| Purpose | A live transport seam and CLI, source preflight, two bounded smoke runs, run validation and comparison, a live-corpus calibration decision, and bounded link-health checking |
| Status | **CLOSED.** Plan of record `STAGE_9_IMPLEMENTATION_PLAN.md`; closing executable baseline `ec9bedc` |
| Principal capability | A **six-command CLI surface** — `preflight-sources`, `smoke`, `validate`, `compare-runs`, `diff`, `linkcheck` — over the existing library, plus one atomic `Transport` seam that couples opener, pacing and lease root so a live opener can never be paired with disabled pacing |
| Wrote only to temp roots? | **No, by design.** Live runs wrote to an **explicitly supplied external retained root**; the four repository runtime paths remain **absent** |
| Contacted network? | **YES — four separately approved executions**, each run exactly once and never retried: S9-L1 preflight (rc 1, 19 ok / 6 robots-denied), S9-L2 smoke, S9-L3 smoke, S9-L4 linkcheck |
| Retained runtime output? | **YES — externally.** Three runs: two smokes and one linkcheck (§7.1a) |
| Published output? | **No.** Every retained run is `publication_eligible: false` **by derivation** — `smoke` and `linkcheck` are non-`harvest` modes |
| Completion authority | `docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md` |
| Milestones | **M2, M3 and M4 ACHIEVED** |
| Remaining dependency | **None for Stage 9.** What remains belongs to M5 and later: a production `harvest` command, human review, promotion, publication and website integration — all outside Stage 9's scope |

### Stage 10 — final report

| Field | Value |
|---|---|
| Purpose | `IMPLEMENTATION_REPORT.md` (every file created/changed, exact commands, results) and `CONVERGENCE_NOTE.md` (5 gates before matrix unification is reconsidered), plus unresolved issues and follow-ups |
| Status | **NOT OPENED.** Its prerequisite is now satisfied — Stage 9 is closed — but Stage 10 has not been approved, scoped or started |
| Principal capability | None delivered |
| Wrote only to temp roots? | n/a |
| Contacted network? | n/a |
| Retained runtime output? | **No — and it never would.** Stage 10 is two markdown documents |
| Published output? | **No.** Stage 10 does **not** create or publish production JSON. Nothing in the committed tree or in `TODO.md` gives it that scope |
| Completion authority | n/a |
| Remaining dependency | **Satisfied** (Stage 9 closed). Opening Stage 10 still needs its own approval by name |

---

## 3 · Product milestone map

Product milestones are defined by **observable artifacts**, independently of stage numbers. The
mapping between the two is deliberately not one-to-one: closing Stage 9 and Stage 10 as currently
described completes the *original task*, and leaves the product at M3/M4 at best.

### M1 — core engine and offline regression

- **Definition of done:** discovery → record → artifact runs end to end over the fixture corpus,
  deterministically, and the whole test suite passes offline in one invocation.
- **Status:** **COMPLETE.** `validate_task.sh --all`, exit 0, 58/58 wrappers, zero skips (S8-2).
- **Owner:** Stages 0–8.
- **Prerequisite:** none.
- **Visible artifact:** a 43-path tree in a temporary root, hash-identical across runs and shuffles;
  no repository artifact.
- **Approval required:** none remaining.
- **Scope:** part of the original task.

### M2 — first real staged taxonomy output · **COMPLETE**

- **Definition of done:** one **retained** run — 43 real paths a human can open — produced from live
  sources.
- **Status:** **ACHIEVED 2026-07-31 (S9-L2).** Run `20260731T113526Z-23992`, rc 0, one invocation.
  42 JSON + `LATEST_RUN_ID`; 10 `ok` cells / 2 `zero_result`; 32 records. Validated offline:
  `valid: true`, 42 documents / 43 paths.
- **Owner:** Stage 9. **Delivered.**
- **Visible artifact:** `runs/20260731T113526Z-23992/**` + shared `ledgers/` + `rejections/` +
  `LATEST_RUN_ID`, in the **external retained root** — deliberately *not* under
  `state/taxonomy_harvest/`, which remains absent.
- **Not a production candidate:** `publication_eligible: false` by derivation from `mode: "smoke"`.

### M3 — repeatability and calibration · **COMPLETE**

- **Definition of done:** two live smokes under a pinned bound, a comparison showing only enumerated
  clock-derived movement, and an explicit calibration decision against **live** data.
- **Status:** **ACHIEVED 2026-07-31 (S9-L3 + S9-5).** Second run `20260731T120702Z-20188`, rc 0,
  validated. `compare-runs`: 18 documents compared, 24 shared excluded, **197 permitted clock changes,
  23 content changes (all manifest `source_preflight[].elapsed_ms`), 0 invariant violations,
  `idempotent: true`**. Run 1 stayed byte-identical throughout.
- **Comparison output form:** **unpersisted stdout JSON** over the **18 selected-run documents only**.
  It writes no file. **There is no `--normalize`** (E9-14): differing paths are enumerated and
  classified into `permitted_changes` / `content_changes` / `invariant_violations`, and an
  unclassifiable field fails loudly rather than being normalized away.
- **Calibration decision:** **EDITORIAL THRESHOLDS STAY PROVISIONAL** — `quality` and `audience_fit`
  were saturated at 1.000 and rejected nothing; `relevance` was the only discriminating gate.
- **Owner:** Stage 9. **Delivered.**

### M4 — link-health validation · **COMPLETE**

- **Definition of done:** a bounded `linkcheck` over a retained run, producing a run in
  `mode: "linkcheck"`.
- **Status:** **ACHIEVED 2026-08-01 (S9-L4).** One live invocation, rc 0. Base
  `20260731T120702Z-20188` → run `20260801T085829Z-40852`; `--sample 20` over the 19 accepted full
  records available; **19 records checked, 19 logical identities**. Validated offline: `valid: true`,
  42 documents / 43 paths, pointer agreeing.
- **Link health:** 19 current-run `link_history` entries, 0 missing, 0 duplicate, **0 `not_checked`**;
  **14 `ok` / 5 `robots_denied`**; cells 7 `ok` / 5 `not_run`.
- **arXiv:** 8 of the 19 targets are `arxiv.org`, whose 15 s crawl-delay the plan treated as the point
  of the exercise. `locks/arxiv.org/` did not previously exist — the smokes only ever paced
  `rss.arxiv.org` — so this was the first target-page pacing on that host.
- **Owner:** Stage 9. **Delivered.**
- **Not a production candidate:** `publication_eligible: false` by derivation from the non-`harvest`
  mode.

### M5 — reviewed production candidate

- **Definition of done:** an **enrichment-complete** run (not `--no-enrich`), of publication quality,
  reviewed by a human against a defined acceptance record, with zero unresolved alias conflicts.
- **Status:** **UNOPENED and UNOWNED.** No stage in `TODO.md` owns a production-quality enriched
  run. `IMPLEMENTATION_PLAN.md` §7.1 explicitly disqualifies live *smoke* output from promotion and
  requires "a reviewed run ID · schema validity · zero unresolved conflicts · an explicit reason",
  rejecting `"initial deterministic smoke"` by name — but assigns that work to no stage.
- **Owner:** **None. This is a roadmap gap** (§9 item G4).
- **Prerequisite:** M3, M4, a calibration decision, and an enrichment budget: `policy.v1.json`
  `_enrich_why` records that enrichment is disabled by default because arXiv's mandated 15 s
  crawl-delay makes 12 candidates from that one source cost ≥180 s of pacing alone.
- **Visible artifact:** currently undefined. `runs/<run_id>/candidate_output/` appears in
  `IMPLEMENTATION_PLAN.md` §7.1 with **no producer** — today's runs write `runs/<run_id>/cells/`.
- **Approval required:** Yes — live, enriched, larger-budget execution.
- **Scope:** **additional production milestone**, beyond the original Stage 0–10 task.

### M6 — published JSON dataset

- **Definition of done:** 16 stable JSON files committed under `data/harvested/**` (§6.3) by a
  transaction-safe `promote`, with the promotion journal removed and a receipt written.
- **Status:** **NOT STARTED.** No promotion implementation exists in any form —
  `promotion_receipt`, `promotion_journal`, `publication_manifest`, `promote_staging`,
  `promote_rollback` and `--publication-root` are absent from the entire tree.
- **Owner:** **None.** `IMPLEMENTATION_PLAN.md` §7 designs it in detail (protocol, rollback, resume,
  crash-point recovery table, isolated test); `TODO.md` lists it under Stage 6, where plan §14
  erratum E11 **descoped it**. It has been unowned since.
- **Prerequisite:** M5.
- **Visible artifact:** `data/harvested/**` — tracked, committed, the first product output.
- **Approval required:** Yes — writing tracked publication paths.
- **Scope:** **additional production milestone.**

### M7 — website / consumer integration and recurring operation

- **Definition of done:** `cherryinthehaystack.com` (or another consumer) reads the published JSON,
  and a refresh cadence keeps it current.
- **Status:** **NOT STARTED, UNSCOPED, UNOWNED.** The website appears exactly once in the master
  plan, in the outcome sentence of the Context section. There is no interface contract, no consumer
  code, no schema-compatibility statement, and no scheduling design. `refresh` is a `mode` enum value
  with no producer. (`scripts/refresh.sh` in this repository belongs to the **legacy AX deck
  pipeline** and is unrelated — see §9 item G6.)
- **Owner:** none.
- **Prerequisite:** M6.
- **Visible artifact:** none defined.
- **Approval required:** Yes — external side effects.
- **Scope:** **additional production milestone.**

### 3.1 The five distinctions, stated plainly

| Claim | True today? | What actually holds |
|---|---|---|
| "Implementation task complete" | **Nearly** — 10 of 12 stages | The library is built and offline-verified. Stages 9 and 10 remain |
| "First live staged dataset exists" | **No** | Zero live requests ever; no run command; `run()` cannot reach the network |
| "Publication-eligible candidate exists" | **No** | No retained run, no review process, no candidate artifact producer |
| "JSON is promoted into `data/harvested/`" | **No** | Directory absent; zero lines of promotion code exist |
| "The website consumes it" | **No** | No consumer, no interface, no owner |

---

## 4 · Remaining-work forecast

Estimated in **checkpoint-sized work units** — one checkpoint being one separately approved, named,
exact-allowed-path unit of the size Stages 5–8 actually used. Calendar time is not estimated:
observed checkpoint duration in this project varies by more than an order of magnitude, and the
binding constraint is human approval latency, not machine time.

### 4.0 Current forecast, from Stage 9 closeout onward

**Stages 0–9 are closed. Everything in §§4.1–4.2 below is a RETROSPECTIVE record of what was
forecast before Stage 9 ran; it is retained for calibration and is NOT a current estimate.**

| To reach | Checkpoints (range) | Note |
|---|---|---|
| **Stage 10** — report + convergence note | **1 – 2** | Documentation only; creates no JSON |
| **M5** — reviewed production candidate | **7 – 10** | Unopened and undesigned; needs a production `harvest` command first |
| **M6** — published JSON | **+8 – 10** | `promote` does not exist in any form |
| **M7** — website integration / recurring refresh | **+6 – 10** | Outside this repository; unowned |
| **Remaining total, Stage 9 close → M7** | **22 – 32** | Low confidence beyond M5 |

**Actual Stage 9 outcome, against the pre-stage forecast of 13–18 checkpoints for "close the
described Stage 0–10 plan":** Stage 9 alone consumed **13 commits** plus **four live executions**,
**three authoritative gate invocations** (one of which failed and required the S9-6A repair) and
several read-only audits — and it did **not** include Stage 10. The forecast's shape held; its
scope did not. **The corrective-checkpoint precedent was correct**: S9-5C1, S9-5C2, the S9-5C3
deferral and S9-6A were all unplanned corrective units.

### 4.1 *(RETROSPECTIVE)* Close the currently described Stage 0–10 plan

| Field | Value |
|---|---|
| Minimum expected checkpoints | **10** — Stage 9 plan of record · run-command implementation · live-opener implementation · preflight-sources · smoke · second smoke · compare-runs · linkcheck · Stage 9 closeout · Stage 10 report+convergence note |
| Likely corrective checkpoints | **3–6.** Precedent is strong: Stage 6 needed S6-0-C, S6-2-C, S6-6A, S6-6B, S6-T, S6-TD — six unplanned units. First contact with real feeds will surface adapter, encoding, robots and pacing defects that 25 synthetic fixtures could not |
| Total range | **13–18 checkpoints** |
| Major uncertainty | Whether the live-run capability is one checkpoint or three. `run()` takes no opener parameter and no mode; adding a live path touches the driver, the budget wiring and the manifest `mode` field, all of which sit under 33 wrappers that assert `config/` is clean and several that assert byte-freezes |
| External dependency | 25 real source endpoints must still exist, still serve the expected shape, and still permit crawling under RFC 9309 |
| Live/network approval | **Yes** — for `preflight-sources`, both smokes, and `linkcheck`. Four separate outbound-request approvals minimum |

### 4.2 *(RETROSPECTIVE — M2 ACHIEVED 2026-07-31)* Generate the first real staged JSON set

| Field | Value |
|---|---|
| Minimum expected checkpoints | **4** — Stage 9 plan · run-command + live-opener implementation · live-source preflight · first bounded smoke |
| Likely corrective checkpoints | **1–3.** A preflight that finds three dead or reshaped feeds is a corrective checkpoint, not a failure |
| Total range | **5–7 checkpoints** |
| Major uncertainty | **The corpus may be nearly empty.** The committed relevance vocabularies accept **4 of 109** fixture candidates (3.7 %) in **1 of 12 cells**. If live acceptance lands near that rate, the first staged dataset is a handful of records across 12 cells, and calibration becomes urgent rather than optional. This is a stated S4-4A conclusion, not a new worry |
| External dependency | Network egress; per-domain crawl-delays (arXiv 15 s, microsoft.com 10 s); `smoke_budget_sec` = 1800 |
| Live/network approval | **Yes** — twice for the smoke (checkpoint, then immediately before the request) |

### 4.3 Obtain a reviewed production candidate (M5)

| Field | Value |
|---|---|
| Minimum expected checkpoints | **5** — define the candidate artifact and its producer · define the review artifact and acceptance process · calibration decision on live data · enrichment-budget design · the enriched production run |
| Likely corrective checkpoints | **2–5.** Calibration is the likeliest source: S4-4A concluded the thresholds are untuned and the fixture corpus unsuitable for tuning them |
| Total range | **7–10 checkpoints** |
| Major uncertainty | **Nothing here is designed.** `runs/<run_id>/candidate_output/` has no producer; human review has no artifact, no schema and no acceptance criteria beyond one prose sentence in plan §7.1. Every number in this row is inference from checkpoint sizing elsewhere in the project, not from a plan |
| External dependency | Enrichment cost — target-page fetching across 25 domains under mandated crawl-delays |
| Live/network approval | **Yes** |

### 4.4 Publish into `data/harvested/` (M6)

| Field | Value |
|---|---|
| Minimum expected checkpoints | **6** — promotion plan of record · path/manifest builders · the transaction (journal, before-images, commit walk) · rollback and resume · the fault-injected isolated test (`tests/test_taxonomy_promote_txn.sh`, 4 injection points + 3 modes) · the real promotion |
| Likely corrective checkpoints | **2–4.** The design is detailed but has never met code; plan §7.4's seven crash points each need a real implementation to be true |
| Total range | **8–10 checkpoints** |
| Major uncertainty | Whether the flat published layout in plan §1 survives contact with an actual consumer. Plan §7 already notes a versioned generations directory was rejected *because* it would change the published path contract — a contract no consumer has ever validated |
| External dependency | **A consumer that agrees to the schema.** Publishing a shape nobody reads is not the goal |
| Live/network approval | No network; **yes** to writing tracked publication paths, which is a separate and stricter approval |

### 4.5 Connect published JSON to the website / downstream consumer (M7)

| Field | Value |
|---|---|
| Minimum expected checkpoints | **4** — consumer interface contract · consumer-side integration · refresh/scheduling design · first recurring operation |
| Likely corrective checkpoints | **2–6**, entirely unbounded on the consumer side |
| Total range | **6–10 checkpoints**, low confidence |
| Major uncertainty | **This is outside the repository.** The website is a different system with different owners, a different deployment path and possibly a different schema. Nothing in this repository constrains it |
| External dependency | Total |
| Live/network approval | **Yes** — deployment and external side effects |

### 4.6 Roll-up *(the M2/M4 rows are now HISTORY, not forecast)*

| To reach | Checkpoints (range) | Status |
|---|---|---|
| M2 — first staged dataset | 5 – 7 | **ACHIEVED** |
| End of the described Stage 0–10 plan (≈ M4) | 13 – 18 | **M4 ACHIEVED**; Stage 10 not opened |
| M5 — reviewed production candidate | +7 – 10 | unopened |
| M6 — published JSON | +8 – 10 | not started |
| M7 — website integration | +6 – 10 | not started |
| **M1 → M7 total** | **34 – 48 checkpoints** | ~22–32 remain (§4.0) |

**Stage 10 does not create or publish production JSON.** It writes two markdown documents. Anyone
reading "only Stages 9 and 10 remain" as "publication is two stages away" is reading it wrong: the
described plan ends at M3/M4, and M5, M6 and M7 are roughly **21–30 further checkpoints** that are
currently unowned and mostly undesigned.

---

## 5 · JSON artifact catalog

Every JSON document or family the project defines, whether or not anything produces it.

### 5.1 General taxonomy-run artifacts

All are rooted at an **artifact root** passed to `run_cells.run(root, …)`. The operational root would
be `state/taxonomy_harvest/`; **every root ever used has been a temporary directory.**

#### `runs/<run_id>/cells/<cell_id>.json`

| Field | Value |
|---|---|
| Path template | `<root>/runs/<run_id>/cells/<cell_id>.json` |
| Example | `runs/20260730T120000Z-4812/cells/research-and-models__benchmark-and-datasets.json` |
| Producer | `artifacts.build_cell_artifact()` → `write_cell_artifact()`; path from `artifacts.cell_artifact_path()`; driven by `run_cells._run_one_cell` |
| Producer command | **None.** No CLI reaches `run_cells.run()` |
| Schema | `schemas/harvest/cell_artifact.v1.json` |
| Inputs | Accepted records for one cell, plus `metadata.sources` and optional `rejected` |
| Contents | `records[]` sorted by `records.sort_key`; derived counts (`full_records`, `by_category`, cross-references counted separately and excluded from `by_category`) |
| Granularity | **Per-cell, per-run** |
| First created | The cell's write phase, inside a `WriteJournal` |
| Update semantics | **Immutable.** A finished `run_id` is refused before the first byte is written |
| Retention | Never cleaned by this code. No retention policy is implemented |
| Exists in repo runtime? | **No** |
| Publication eligible | **No** — runtime-only |
| Status | **Implemented, fixture- and temp-root-proven, never operationally executed** |

**Counts are derived and a caller may not supply one** — a count can never disagree with the records
beside it.

#### `runs/<run_id>/topics/<topic_slug>.json`

| Field | Value |
|---|---|
| Path template | `<root>/runs/<run_id>/topics/<topic_slug>.json` |
| Example | `runs/20260730T120000Z-4812/topics/research-and-models.json` |
| Producer | `artifacts.build_topic_artifact()` → `write_topic_artifact()`; `topic_artifact_path()` |
| Producer command | **None** |
| Schema | `schemas/harvest/topic_artifact.v1.json` |
| Inputs | The topic's cell artifacts |
| Contents | Merged records, **sorted then deduplicated by `record_id`** — that order is load-bearing; deduplicating first made the survivor depend on cell order |
| Granularity | **Per-topic, per-run** |
| First created | After the topic's cells complete |
| Update semantics | **Immutable** |
| Retention | None implemented |
| Exists in repo runtime? | No |
| Publication eligible | No — the *published* topic aggregate is a different, unimplemented artifact (§5.4) |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

#### `runs/<run_id>/coverage.json`

| Field | Value |
|---|---|
| Path template | `<root>/runs/<run_id>/coverage.json` |
| Producer | `artifacts.build_coverage_report()` → `write_coverage_report()`; `coverage_report_path()` |
| Producer command | **None** |
| Schema | `schemas/harvest/coverage_report.v1.json` |
| Inputs | The run's records; `config/harvest/coverage_targets.v1.json`; `policy.v1.json` thresholds |
| Contents | Five facet states summing exactly to `applicable_full_records`; `thresholds_constant` **reported, never derived** — no S4-4 threshold is recalibrated here |
| Granularity | **Per-run** |
| First created | Run write phase |
| Update semantics | **Immutable** |
| Retention | None implemented |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

CF-11 is protected by six assertions: the word `secondary` appears nowhere in the serialized report.

#### `runs/<run_id>/alias_conflicts.json`

| Field | Value |
|---|---|
| Path template | `<root>/runs/<run_id>/alias_conflicts.json` |
| Producer | `artifacts.build_alias_conflicts()` → `write_alias_conflicts()`; `conflict_id()` is a **content hash, never positional** |
| Producer command | **None** |
| Schema | `schemas/harvest/alias_conflict.v1.json` — validates the **complete** document, envelope included |
| Inputs | Conflicts adjudicated by `aliases.adjudicate()`, deduplicated run-wide by content |
| Contents | Envelope + `conflicts[]`; the count is read back from the validated document by the manifest, so artifact and manifest cannot drift |
| Granularity | **Per-run** |
| First created | Written **before** the manifest |
| Update semantics | **Immutable.** An empty set still produces the file — "found none" must be distinguishable from "nobody looked" |
| Retention | None implemented |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

#### `runs/<run_id>/manifest.json`

| Field | Value |
|---|---|
| Path template | `<root>/runs/<run_id>/manifest.json` |
| Producer | `artifacts.build_run_manifest()` → `write_run_manifest()`, published by `publish_run()` |
| Producer command | **None** |
| Schema | `schemas/harvest/run_manifest.v1.json` |
| Inputs | Cell rows, `policy_thresholds()`, `environment_block()`, target-fetch outcomes, the alias-conflict count |
| Contents | **12 unique rows, one per configured cell, sorted by `cell_id`** — an unreached cell is `not_run`, one that found nothing is `zero_result` with a committed reason, so a silently skipped cell cannot hide. `mode` (enum: `harvest`, `smoke`, `smoke_model`, `refresh`, `linkcheck`, `migration` — **only `harvest` and `migration` have producers**); `config.enrich`; `config.bounds`; `request_accounting` with source and target key spaces kept **separate**; `publication_eligible` **derived, never a parameter** |
| Granularity | **Per-run** |
| First created | Last document of the run, immediately before the pointer |
| Update semantics | **Immutable.** Its existence *is* the "run finished" flag (`run_is_finished`) |
| Retention | None implemented |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

#### `ledgers/<cell_id>.json`

| Field | Value |
|---|---|
| Path template | `<root>/ledgers/<cell_id>.json` — deliberately **not** under `runs/` |
| Producer | `ledger.merge_ledger()` → `write_ledger()`; `artifacts.ledger_path()` |
| Producer command | **None** |
| Schema | `schemas/harvest/ledger.v1.json` |
| Inputs | Per-URL observations from the run, plus target evidence **copied from the finished record** (S6-6B) — never recomputed, so a second derivation cannot disagree with the record beside it |
| Contents | `identity_url`, `content_id`, `source_id`, `outcome`, `http_status`, `content_hash`, `last_checked_at`, plus merge-owned `first_seen_at` / `last_seen_at` / `seen_count` |
| Granularity | **Cross-run, cell-owned** — this is what one run knows that the next should not have to rediscover |
| First created | First run of that cell |
| Update semantics | **Merged.** `first_seen_at` is written once; a re-merge advances `last_seen_at`/`seen_count` and nothing else. **A terminal outcome is final** — a contradictory terminal→terminal change raises, and a later `pending` never un-decides a decided URL. A corrupt, invalid or foreign ledger **raises** rather than being treated as empty |
| Retention | **Permanent by design.** A `rejected` entry is retained on purpose, or every run re-fetches and re-rejects it |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

#### `rejections/<cell_id>.json`

| Field | Value |
|---|---|
| Path template | `<root>/rejections/<cell_id>.json` — cross-run location, per-run content |
| Producer | `ledger.build_rejection_log()` → `write_rejection_log()`; `artifacts.rejection_log_path()` |
| Producer command | **None** |
| Schema | `schemas/harvest/rejection.v1.json` — `additionalProperties: false`, one `harvest_run_id`, run-less entries |
| Inputs | `(extracted, verdict)` pairs from `verify.decide` |
| Contents | Per-candidate rejection reason (six reachable reasons, all six storable — CF-2 pinned by enumerating them from `verify.decide`'s AST) and `rejected_at` |
| Granularity | **Per-cell, replaced per run** |
| First created | The cell's write phase |
| Update semantics | **Replaced — and it structurally cannot merge**: a merged log could not name the run that produced its rows. The guarantee asserted instead is that **a run never clobbers a cell it did not run** |
| Retention | Superseded by the next run of that cell |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

#### `LATEST_RUN_ID` — a non-JSON pointer

| Field | Value |
|---|---|
| Path template | `<root>/LATEST_RUN_ID` |
| Producer | `artifacts.write_latest_run_id()`, called only from `publish_run()`; read by `read_latest_run_id()` / `verify_latest_run_id()` |
| Producer command | **None** |
| Schema | **None** — one line, one trailing newline, no CRLF, asserted |
| Contents | A single `run_id` |
| Granularity | **Cross-run, root-owned singleton** |
| First created | The very last write of the first finished run |
| Update semantics | **Pointer moved — last, or not at all.** An unfinished run, a mismatched `harvest_run_id`, and a re-publish of a finished run are each refused. An invalid manifest, a crashed write and a `KeyboardInterrupt` each left the *previous* pointer intact with no debris |
| Retention | Permanent; overwritten by the next finished run |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, fixture/temp-root-proven, never operationally executed |

### 5.2 Migration artifacts

Destination `<state-root>/migrations/<run_id>__ax_cases/`, derived by `migrate/base.py`, which
**creates nothing** — every path goes through `validate_run_id()` against an anchored
`^[0-9]{8}T[0-9]{6}Z-[0-9]+$`, so a separator or a `..` can never reach the filesystem.

#### Migration `manifest.json`

| Field | Value |
|---|---|
| Path template | `<state-root>/migrations/<run_id>__ax_cases/manifest.json` |
| Producer | `migrate/ax_cases.apply_migration()`; path from `base.manifest_path()` |
| Producer command | `bash scripts/harvest/migrate.sh ax-cases --apply --state-root PATH` |
| Schema | `schemas/harvest/run_manifest.v1.json` — the same schema, `mode: "migration"` |
| Inputs | The mapping result |
| Contents | **One migration cell row**, no request accounting, `publication_eligible: false` with a deterministic reason accounting for all 231 records remaining `not_checked` |
| Granularity | **Migration-only, per-bundle** |
| First created | Built and validated **before a staging directory exists** |
| Update semantics | **Transaction-only then immutable.** Published by **one `os.replace` of the directory**; a used run id is refused before the registry, overrides or facets are read |
| Retention | Permanent under the state root; nothing prunes it |
| Exists in repo runtime? | **No** |
| Publication eligible | **No — explicitly false** |
| Status | **Implemented, temp-root-proven, never operationally executed** |

#### Migration candidate output

| Field | Value |
|---|---|
| Path template | `<bundle>/candidate_output/cases__case-studies__harvest.json` |
| Producer | `apply_migration()`; `base.candidate_artifact_path()` |
| Producer command | `migrate.sh ax-cases --apply --state-root PATH` |
| Schema | `cell_artifact.v1.json` (via `artifacts.write_document`) |
| Inputs | `state/ax_case_harvest_registry.json` (**protected, read-only**), `config/harvest/migration_overrides.v1.json`, the facet vocabularies |
| Contents | **231 accepted records**, 231 distinct `record_id`/`content_id`/`identity_url` from **126 distinct legacy `case_id`s**; 231/231 `snippet_only`; 33 `"unknown"` dates → null with the originals intact in `provenance.raw`; **all four scores null**; facet states 112 `facet_partial` · 118 `unmapped_legacy_value` · 1 `unresolved` |
| Granularity | **Migration-only** |
| First created | Staging phase |
| Update semantics | **Immutable after the rename** |
| Retention | Permanent under the state root |
| Exists in repo runtime? | No |
| Publication eligible | **No.** Every record is `not_checked`, which the eligibility derivation refuses |
| Status | Implemented, temp-root-proven, never operationally executed |

> **`candidate_output` here is a *migration bundle* directory name.** It is **not** the
> `runs/<run_id>/candidate_output/` that `IMPLEMENTATION_PLAN.md` §7.1 describes for reviewed live
> output. The two share a name and nothing else, and the second has **no producer** (§9 item G5).

#### Migration rejection output

| Field | Value |
|---|---|
| Path template | `<bundle>/rejections/cases__case-studies__rejections.json` |
| Producer | `apply_migration()`; `base.rejection_artifact_path()` |
| Producer command | `migrate.sh ax-cases --apply --state-root PATH` |
| Schema | `rejection.v1.json` |
| Contents | **0 rejections** on the protected corpus — 0 of 231 `source_url` values trip the suspicious-URL guard under D7-H's structural predicates |
| Granularity | Migration-only |
| Update semantics | Immutable after the rename |
| Exists in repo runtime? | No |
| Publication eligible | No |
| Status | Implemented, temp-root-proven, never operationally executed |

#### Reports emitted only to stdout, never stored

| Report | Producer | Form | Stored? |
|---|---|---|---|
| `migrate.sh ax-cases` dry-run / apply report | `ax_cases.dry_run()` / `apply_migration()` | One deterministic **16-field** JSON document on **binary** stdout, rendered by the committed `artifacts.serialize` — no second serializer, no record dump, no path, no environment, no publication eligibility. `report_type: "ax_cases"` for both modes; `dry_run` is the sole discriminator | **No file** |
| `migrate.sh entity-assess` | `entity_assess` | Markdown on stdout, byte-identical to the committed `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md`; `--output PATH` writes exactly those bytes | Only to an explicit `--output` path |

### 5.3 Stage 9 / live-operation artifacts — audited, not assumed

**Every row below was searched for across `src/`, `scripts/`, `schemas/`, `config/` and `tests/`.**

| Artifact | Producer exists now? | Evidence | Status |
|---|---|---|---|
| Smoke output | **No** | `smoke` appears only as a `run_manifest.v1.json` `mode` enum value, in `policy.v1.json` `smoke_budget_sec`/`smoke` block, in comments, and in tests asserting the enum. **No script, no function, no `__main__`** | **Stage 9 work — planned, not implemented** |
| Second-smoke output | **No** | Same as above; the second run is the same producer run twice | Stage 9 work |
| `compare-runs` result | **No** | `compare-runs` / `compare_runs`: **zero occurrences in the entire tree.** Master plan §8 defines the *semantics* (`content_changes[]`) but names no output file | **Stage 9 work — not implemented, and its output form is undefined** |
| Linkcheck output | **No** | `linkcheck` appears only as a `mode` enum value and in prose/comments | Stage 9 work |
| Refresh output | **No** | `refresh` as a taxonomy mode: enum value only. (`scripts/refresh.sh` is the **legacy AX deck pipeline** — unrelated) | **Not implemented; also unowned by any stage** |
| Source-preflight result | **No** | `preflight-sources` / `preflight_sources`: **zero occurrences.** `httpclient.preflight()` exists as a non-raising per-request helper — a different thing, and no command drives it over the 25 configured sources | Stage 9 work |
| Model-search output | **No** | `smoke_model` is a `mode` enum value; the `model_search` adapter **raises typed `AdapterNotImplemented`** | **Not implemented, and its adapter is a deliberate stub.** Plan §14 command 24 marks it opt-in |

### 5.4 Publication artifacts — audited

**Production promotion does not exist.** Not partially, not behind a flag: `promotion_receipt`,
`promotion_journal`, `publication_manifest`, `promote_staging`, `promote_rollback` and
`--publication-root` return **zero matches** anywhere in the tree, and
`tests/fixtures/taxonomy/promote_candidate/` does not exist (that directory holds exactly three
files: `protected_paths.txt`, `protected_sha256.txt`, `untracked_baseline.txt`).

Everything below is **contractually specified by `IMPLEMENTATION_PLAN.md` §1 and §7 and has no
current producer.**

| Artifact | Path template | Update semantics (as designed) | Class | Producer |
|---|---|---|---|---|
| Category publication JSON | `data/harvested/<topic_slug>/<topic_slug>__<category_slug>__harvest.json` | Replaced per promotion generation | **Stable published** | **None — planned** |
| Topic aggregate publication JSON | `data/harvested/<topic_slug>/<topic_slug>__all__harvest.json` | Replaced per generation | **Stable published** | **None — planned** |
| Publication manifest | `data/harvested/publication_manifest.json` | Replaced; carries the generation and the promoted set | **Stable published** | **None — planned** |
| Promotion journal | `data/harvested/.promotion_journal.json` | **Transaction-only** — present *only* mid-transaction; states `prepared` → `committing` → `committed`; removed at finalize | **Transaction-only** | **None — planned** |
| Promotion receipt | `runs/<run_id>/promotion_receipt.json` | Written once at finalize | **Runtime-only** (lives under the run, not under `data/`) | **None — planned** |
| Promote staging | `runs/<run_id>/promote_staging/` | Transaction-only | **Transaction-only** | **None — planned** |
| Promote rollback (before-images) | `runs/<run_id>/promote_rollback/` | Transaction-only | **Transaction-only** | **None — planned** |

### 5.5 Artifact class summary

| Class | Members |
|---|---|
| **Stable published** | Category JSON, topic aggregate JSON, `publication_manifest.json` — **all planned, none implemented, none existing** |
| **Runtime-only** | cell · topic · coverage · alias_conflicts · manifest · rejections · ledgers · `LATEST_RUN_ID` — **all implemented, none retained**; plus the planned promotion receipt |
| **Transaction-only** | Migration staging `.tmp_migration_<run_id>_<unique>` (**implemented**); promotion journal, promote_staging, promote_rollback (**planned**) |
| **Migration bundle** | Migration manifest + candidate output + rejections — **implemented, temp-root-only** |
| **Planned with no current producer** | Everything in §5.3 and §5.4, plus `runs/<run_id>/{logs,tmp/<cell_id>,candidate_output}/` and `state/taxonomy_harvest/{registries,cache,domains,locks}/` from plan §1 |

---

## 6 · Exact expected file-set accounting

### 6.1 A full 12-cell taxonomy run

Verified against `tests/harvest/test_target_determinism.py:149-165` (`expected_paths`, and
`test_the_tree_is_exactly_the_43_expected_paths`, which asserts the length is **43**) and against
`artifacts.py`'s path builders. Asserted **exactly**, so an extra path fails as loudly as a missing
one.

| Family | Count | Location |
|---|---|---|
| Cell artifacts | **12** | under the run directory |
| Topic artifacts | **3** | under the run directory |
| Coverage report | **1** | under the run directory |
| Alias conflicts | **1** | under the run directory |
| Run manifest | **1** | under the run directory |
| Rejection logs | **12** | **cross-run state** (`rejections/`) |
| Ledgers | **12** | **cross-run state** (`ledgers/`) |
| `LATEST_RUN_ID` pointer | **1** | **cross-run state** (root) |

```text
JSON documents                     42
non-JSON pointer                  + 1
total filesystem paths             43

under runs/<run_id>/               18   (12 cells + 3 topics + coverage + alias_conflicts + manifest)
cross-run state                    25   (12 rejections + 12 ledgers + 1 pointer)
```

**Evidence class: fixture-proven and temp-root-proven. NOT live-proven.** The 43-path set has been
produced many times, always from the synthetic fixture corpus into an injected temporary root, and
every such tree has been deleted. Two equivalent runs under a pinned clock are byte-identical
file-by-file; cell, source and candidate order are each proved unable to reach the output.

**A caveat the count hides.** On the committed corpus this 43-path tree contains **four accepted
records, all in `research-and-models__benchmark-and-datasets`**; the other **11 cells are
zero-result**, every one reporting `all_below_relevance_threshold`. That is a real finding about the
corpus, not a harness failure — the bar was not lowered. A live run's *shape* will be these 43 paths;
its *content* is unknown.

### 6.1a The retained Stage 9 root — CURRENT STATE

```text
C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_stage9_retained
```

**This is where every live Stage 9 artifact lives.** The repository's four runtime paths
(`state/taxonomy_harvest/`, `data/harvested/`, `runs/`, `LATEST_RUN_ID`) remain **absent by design**,
and the validation harness asserts their absence before and after every run.

| Run ID | Mode | Checkpoint | Milestone |
|---|---|---|---|
| `20260731T113526Z-23992` | `smoke` | S9-L2 | M2 |
| `20260731T120702Z-20188` | `smoke` | S9-L3 | M3 — and the linkcheck base |
| `20260801T085829Z-40852` | `linkcheck` | S9-L4 | M4 |

```text
3 run directories x 18 selected-run JSON   = 54
12 ledgers                                 = 12
12 rejection logs                          = 12
1 LATEST_RUN_ID pointer                    =  1
20 next_allowed_at lock files              = 20
                                    total  = 99 regular files - 54 directories

LATEST_RUN_ID  20260801T085829Z-40852
aggregate      0a14269a00695fb2b259816b570c88a4df40a64f88e782d447f6a1abccab18e3
transient      0 slot_*.lease - 0 owner - 0 pace.lock - 0 .tmp_*
```

**Do not describe this root as "one 43-file run".** The 43-path contract is what **one run** is
validated against, and it is *not* the same as the root's file count:

- **18 selected-run JSON** live under `runs/<run_id>/` and are that run's own immutable output;
- **24 shared JSON** (12 ledgers + 12 rejection logs) are **cross-run documents updated in place** —
  a second run adds its own 18 and *updates the same 24* (E9-11), which is why three runs give
  54 + 24, not 3 x 42;
- **1 pointer** completes the 43 paths `validate --run-id` checks (42 JSON + `LATEST_RUN_ID`);
- **`locks/` is separate pacing infrastructure**, outside the 43-path contract entirely. It holds one
  `next_allowed_at` per host directory and must be **preserved, never cleaned** — it is operational
  evidence in its own right.

**Disposition: retain unchanged** through Stage 10 and until a separately approved disposition
checkpoint. All three runs are **evidence only** — none is a production candidate, none is
publication-eligible, none has been promoted, none is consumed by any website.

*Historical: before S9-L4 the root held two runs, 80 regular files, and aggregate
`1dcdfff3642e3abded6d8edd95810db4fa37dd497e9a1db9b27d3eea0fd58a94`. That value is the pre-S9-L4
baseline only.*

### 6.2 AX migration apply

```text
command      bash scripts/harvest/migrate.sh ax-cases --apply --state-root PATH
destination  <state-root>/migrations/<run_id>__ax_cases/
staging      <state-root>/migrations/.tmp_migration_<run_id>_<unique>/   (sibling; transaction-only)

JSON files                          3
directories created                 3   (migrations/, the bundle, and candidate_output/ + rejections/ within it)
total files                         3   — asserted exactly; an extra staged path fails the apply
```

| Path | Rows |
|---|---|
| `manifest.json` | 1 migration cell, `publication_eligible: false` |
| `candidate_output/cases__case-studies__harvest.json` | **231 accepted records** |
| `rejections/cases__case-studies__rejections.json` | **0 rejections** |

- **Source corpus:** `state/ax_case_harvest_registry.json` — one of the **18 protected paths**,
  opened read-only and asserted byte-identical before and after.
- **Accounting:** 231 source / **231 accepted / 0 rejected** / 0 unresolved, exit 0. Byte-identical
  across runs; unchanged by reordering source or review rows.
- **Explicitly absent from the bundle:** no topic artifact, no coverage, no alias-conflicts, no
  ledger, no pointer, no journal, no sidecar, no placeholder, nothing under `runs/`, no
  `LATEST_RUN_ID`.
- **Why this is not publication.** Four independent reasons: it writes under a **state root**, not
  under `data/harvested/`; its manifest derives `publication_eligible: false`; all 231 records are
  `not_checked` (`snippet_only`, no HTTP status, no content hash, no check time, all four scores
  null) because **no target page was ever fetched**; and promotion is a separate designed operation
  with its own journal and receipt that **does not exist in code**. A migration bundle is a
  *conversion of an existing corpus*, not a *harvest finding*, and not a *published dataset*.

### 6.3 The final published set, if production promotion were completed

Derived from the committed 3-topic / 12-category taxonomy and the path contract in
`IMPLEMENTATION_PLAN.md` §1.

```text
data/harvested/publication_manifest.json                                              1

data/harvested/cases/cases__all__harvest.json                                         1
data/harvested/cases/cases__domain-applications__harvest.json
data/harvested/cases/cases__case-studies__harvest.json
data/harvested/cases/cases__product-discovery__harvest.json                           3

data/harvested/discourse/discourse__all__harvest.json                                 1
data/harvested/discourse/discourse__regulations-policy-compliance__harvest.json
data/harvested/discourse/discourse__community__harvest.json
data/harvested/discourse/discourse__big-tech-trends__harvest.json
data/harvested/discourse/discourse__market-and-investment__harvest.json
data/harvested/discourse/discourse__technical-deep-dives__harvest.json
data/harvested/discourse/discourse__insights-and-opinions__harvest.json               6

data/harvested/research-and-models/research-and-models__all__harvest.json             1
data/harvested/research-and-models/research-and-models__model-updates__harvest.json
data/harvested/research-and-models/research-and-models__papers__harvest.json
data/harvested/research-and-models/research-and-models__benchmark-and-datasets__harvest.json   3

TOTAL expected stable published JSON                                                 16
  = 12 category files + 3 topic aggregates + 1 publication manifest
```

Plus, **mid-transaction only**, `data/harvested/.promotion_journal.json`.

**None of these files exist.** `data/harvested/` is absent from the repository, no code can create
any of them, and this accounting is derived from a design document, not from a producer.

---

## 7 · Source-to-output map

All 12 configured cells, grouped under their three topics. `cell_id` is derived as
`<topic_slug>__<category_slug>`; the published filenames are derived from the §6.3 contract and
**describe files that do not exist**.

### Topic `cases` → `runs/<run_id>/topics/cases.json`

| Category | Cell ID | Sources (adapter · role) | Intended content | Cell artifact | Published category file |
|---|---|---|---|---|---|
| Domain Applications | `cases__domain-applications` | `aws-ml-blog` (feed · discovery) · `nvidia-blog` (feed · discovery) | Vendor engineering posts describing deployed AI in a named industry | `cells/cases__domain-applications.json` | `cases__domain-applications__harvest.json` |
| Case Studies | `cases__case-studies` | `openai-news` (feed · discovery) · `anthropic-customers` (**seed** · validation_seed) | Named-customer transformation stories with an outcome | `cells/cases__case-studies.json` | `cases__case-studies__harvest.json` |
| Product Discovery | `cases__product-discovery` | `producthunt` (feed · discovery) | Newly launched AI products and tools | `cells/cases__product-discovery.json` | `cases__product-discovery__harvest.json` |

**Only `cases__*` cells carry `case_facets`** — `record.v1.json`'s conditionals **require** facets on
a `cases__domain-applications` full record and **refuse** them on `research-and-models` / `discourse`
full records. A `cases__*` **cross-reference** row stays satisfiable because the conditionals sit
inside the full-record branch.

### Topic `discourse` → `runs/<run_id>/topics/discourse.json`

| Category | Cell ID | Sources (adapter · role) | Intended content | Cell artifact | Published category file |
|---|---|---|---|---|---|
| Regulations · Policy · Compliance | `discourse__regulations-policy-compliance` | `federal-register-ai` (**jsonapi** · discovery) · `nist-news` (feed · discovery) | Rules, standards and official guidance on AI | `cells/discourse__regulations-policy-compliance.json` | `discourse__regulations-policy-compliance__harvest.json` |
| Community | `discourse__community` | `hn-algolia` (**jsonapi** · discovery) · `oss-ollama-releases` · `oss-mcp-servers-releases` · `oss-langchain-releases` (all feed · **validation_seed**) | Practitioner discussion and OSS milestone releases | `cells/discourse__community.json` | `discourse__community__harvest.json` |
| Big Tech Trends | `discourse__big-tech-trends` | `google-blog` · `microsoft-blogs` (feed · discovery) | Platform-vendor strategic announcements | `cells/discourse__big-tech-trends.json` | `discourse__big-tech-trends__harvest.json` |
| Market & Investment | `discourse__market-and-investment` | `techcrunch-ai` (feed · discovery) | Funding, M&A, market movement | `cells/discourse__market-and-investment.json` | `discourse__market-and-investment__harvest.json` |
| Technical Deep Dives | `discourse__technical-deep-dives` | `cloudflare-blog` · `meta-engineering` · `netflix-techblog` (feed · discovery) | Engineering write-ups of production systems | `cells/discourse__technical-deep-dives.json` | `discourse__technical-deep-dives__harvest.json` |
| Insights & Opinions | `discourse__insights-and-opinions` | `simonwillison` · `oneusefulthing` (feed · discovery) | Independent analysis and commentary | `cells/discourse__insights-and-opinions.json` | `discourse__insights-and-opinions__harvest.json` |

### Topic `research-and-models` → `runs/<run_id>/topics/research-and-models.json`

| Category | Cell ID | Sources (adapter · role) | Intended content | Cell artifact | Published category file |
|---|---|---|---|---|---|
| Model Updates | `research-and-models__model-updates` | `hf-blog` · `google-ai-blog` (feed · discovery) | New model releases and capability changes | `cells/research-and-models__model-updates.json` | `research-and-models__model-updates__harvest.json` |
| Papers | `research-and-models__papers` | `arxiv-cs-ai` (feed · discovery) | cs.AI preprints | `cells/research-and-models__papers.json` | `research-and-models__papers__harvest.json` |
| Benchmark & Datasets | `research-and-models__benchmark-and-datasets` | `arxiv-cs-lg` (feed · discovery) · `lm-eval-harness-releases` · `openai-evals-releases` (feed · **validation_seed**) | Evaluation harnesses, benchmarks, datasets | `cells/research-and-models__benchmark-and-datasets.json` | `research-and-models__benchmark-and-datasets__harvest.json` |

**25 unique sources across 12 cells.** Adapter mix: **22 feed · 2 jsonapi · 1 seed** — `seed` is a
bounded index reader with **depth hard-fixed at 1**, a fail-closed allowlist and no child-body fetch.
The `sitemap` and `model_search` adapters exist only as typed `AdapterNotImplemented` raisers.
Role mix: **19 discovery · 6 validation_seed**.

### 7.1 Routing

```text
source (feed / jsonapi / seed)
  → discovery candidate            adapters/*.py, one logical fetch per request key (sourcecache.py)
  → canonical identity             urlkey.py — conservative, prefers false negatives
  → dedupe                         dedupe.group(), same-topic, canonical-equivalence only
  → extraction / normalization     extract.normalize() — metadata only, no body
  → classification                 classify.classify() — 10 precedence rules read as data
  → scoring / verification         verify.score() + verify.decide() — 4 scores, accept/reject gate
  → optional facets                facetassign.assign() — cases__* only
  → optional target evidence       targetfetch.fetch_target() + aliases.adjudicate()
  → full record or cross-reference records.make_full_record / make_cross_reference
  → cell artifact                  runs/<run_id>/cells/<cell_id>.json
  → topic artifact                 runs/<run_id>/topics/<topic_slug>.json
  ──────────────────────────────── everything below this line has NO IMPLEMENTATION ───────────────
  → reviewed candidate             no producer, no artifact, no acceptance process
  → promotion                      no producer
  → published category / topic JSON  data/harvested/** — absent
```

**Where things leave the main path:**

| Departure | Leaves at | Destination | Rejoins? |
|---|---|---|---|
| **Rejected candidates** | `verify.decide()` returns a reject verdict | `rejections/<cell_id>.json`, with the exact rule and number in the detail | **No.** They never reach a record, an artifact, or a topic |
| **Alias conflicts** | `aliases.adjudicate()` during target fetch | `runs/<run_id>/alias_conflicts.json`, deduplicated run-wide by content hash | **No** — but the count enters the manifest, and plan §7 would have `promote` **refuse** while unresolved conflicts exist |
| **Coverage gaps** | `coverage.build_coverage_report()` after records are built | `runs/<run_id>/coverage.json` | **No.** Reported, never acted on — `thresholds_constant` is reported, never derived |
| **Ledger observations** | Written alongside every candidate outcome | `ledgers/<cell_id>.json`, cross-run | **Yes, into the next run** — this is the memory that stops a rejected URL being re-fetched and re-rejected forever |
| **Zero-result cells** | A cell whose candidates all fail relevance | A `zero_result` manifest row with a committed reason, plus a complete valid (empty) cell artifact | **No.** A silently skipped cell cannot hide — it is `not_run`, which is a different value |
| **Cross-topic classification** | `classify` may assign a topic other than the discovery cell's | `competing_categories` on the record; **recorded, not resolved** | Stays on the record |

---

## 8 · Command-to-artifact matrix

**Re-audited at Stage 9 closeout against `ec9bedc`.** Five words are kept distinct and must not be
collapsed: **implemented** (an executable owner exists) · **executed** (it has actually been run) ·
**networked** (it contacted a real external host) · **retained output** (its artifacts survive on
disk) · **publication capability** (it can write `data/harvested/**` — nothing has this).

### 8.1 The Stage 9 command surface — all six implemented

`src/harvest/cli.py` registers exactly six commands and `PLANNED_COMMANDS` is empty. **There is no
`harvest` key**, so no operator can perform a production harvest.

| Command | Implemented | Executed live | Retained output | Publication capability |
|---|---|---|---|---|
| `preflight-sources` | Yes | **Once** (S9-L1, rc 1 — 25 rows, 19 ok / 6 robots-denied). rc 1 means "a source failed", not a crash | None — writes nothing, owns one transient lease root it removes | No |
| `smoke` | Yes | **Twice** (S9-L2, S9-L3; rc 0 each) | **Yes** — two 43-path runs in the external retained root | **No** — `publication_eligible: false` by derivation |
| `validate` | Yes | **Three times against real data** (both smokes, then the linkcheck run; rc 0, `valid: true` each) | None — read-only, offline, writes nothing | No |
| `compare-runs` | Yes | **Once against two real runs** (rc 0, 0 invariant violations, `idempotent: true`) | None — **unpersisted stdout only**, over the 18 selected-run documents; the 24 shared ones are excluded by E9-15. **No `--normalize` exists** | No |
| `diff` | Yes | **Never against real publication data** — temp roots and an absent `data/harvested/` only | None — read-only; `data/harvested/` is looked at and never created | No |
| `linkcheck` | Yes | **Once** (S9-L4, rc 0) | **Yes** — a third run, `mode: "linkcheck"`, derived from the second smoke | **No** — non-`harvest` mode |

**`identities_fetched: 19` in the linkcheck's stdout is a count of logical outcome owners.** It is
**not** 19 downloaded pages: of those 19, **14 returned HTTP 200 and 5 were `robots_denied`**.

### 8.2 Absent commands and producers

| Surface | Status | What it blocks |
|---|---|---|
| a production `harvest` command | **Not implemented.** `mode: "harvest"` exists in the driver and is the only mode `derive_publication_eligibility` accepts, but no CLI command drives it live | M5 — the publication-eligible run itself |
| `promote` | **Not implemented** — zero occurrences of the promotion vocabulary in `src/`, `scripts/`, `schemas/`, `config/` or `tests/` | M6 |
| `refresh` | Not implemented as a taxonomy command | M7 |
| `smoke-model` | Not implemented; its `model_search` adapter raises `AdapterNotImplemented` | Optional |
| publication-manifest producer | Not implemented | M6 |
| promotion journal | Not implemented | M6 |

### 8.3 Migration commands *(unchanged by Stage 9)*

`migrate.sh entity-assess` and `migrate.sh ax-cases --dry-run` are implemented, offline, and have
run (1,161 entities assessed / 0 migrated; 231 of 231 accepted). `migrate.sh ax-cases --apply` works
**only under an injected `--state-root`**; an apply against the repository default root remains
**operationally unapproved and never executed**, and `state/taxonomy_harvest/` does not exist.

---

## 9 · Risks, contradictions, and roadmap gaps

Classified, not solved. Categories: **[R]** already resolved · **[S9]** Stage 9 planning decision ·
**[PM]** later production milestone · **[OOS]** explicit out-of-scope follow-up · **[C]**
contradiction requiring correction before implementation.

### 9.0 Disposition at Stage 9 closeout

**Nothing is deleted or renumbered.** Each item keeps its original text below; this table records
what Stage 9 actually did to it.

| Gap | Disposition |
|---|---|
| **G1** — no command runs the pipeline | **RESOLVED.** `harvest.sh` + `cli.py` exist; `smoke` and `linkcheck` have run live |
| **G2** — stage completion ≠ dataset creation | **RESOLVED IN FACT** — three retained runs now exist. The *lesson* stands permanently |
| **G3** — fixture success ≠ live success | **RESOLVED BY EVIDENCE.** Live contact happened four times; robots proved time-varying, and 5 of 19 linkcheck targets were denied |
| **G4** — production-quality enriched run has no owner | **OPEN.** No production `harvest` command; M5 unopened |
| **G5** — "candidate output" ambiguity | **OPEN** as a naming contradiction; no candidate producer exists |
| **G6** — `refresh` collides with the legacy pipeline | **OPEN.** `refresh` remains unimplemented |
| **G7** — promotion designed, not implemented | **OPEN.** Zero promotion code |
| **G8** — Stage 9 as sketched is too broad | **RESOLVED.** Decomposed into S9-0…S9-6, S9-6A, S9-L1…S9-L4 and S9-C |
| **G9** — human review has no artifact or process | **OPEN.** Blocks M5 |
| **G10** — website integration unowned | **OPEN** |
| **G11** — master plan runtime layout partly fictional | **PARTLY RESOLVED.** `harvest.sh` now exists; the repository runtime paths remain deliberately absent because Stage 9 state is external |
| **G12** — manifest advertises unimplemented modes | **PARTLY RESOLVED.** `smoke` and `linkcheck` now have producers; `smoke_model`, `refresh` and `migration` do not, and `runvalidate` **refuses** them |
| **G13** — domain-throttle instability | **OPEN.** It passed in every gate, but that is an observation, not a resolution; never accept it as a permanent flake |
| **G14** — CF-6 blocks any `config/` edit | **OPEN and confirmed in practice.** No Stage 9 checkpoint edited `config/` |
| **G15** — source tiers configured but unreachable | **OPEN** |
| **G16** — Stage 10 does not publish | **STANDS.** Stage 10 is two markdown documents |
| **G17** — 508 untracked scratch files | **OPEN, out of scope.** The baseline held at exactly 508 through every Stage 9 checkpoint and is used as an invariant |

**New at Stage 9 closeout — G18, carried forward, deliberately NOT fixed by S9-C:**

### G18 — `cli.py`'s pre-request refusal comment is wrong for `linkcheck` · **[C]**

`src/harvest/cli.py`'s `CliError` handler comments that *"Nothing has been probed at this point:
every such refusal happens before the first request."* That holds for the other five commands. It is
**false for `linkcheck`**, whose "no cell received a checked record" and manifest-validation refusals
fire **after fetching and after partial writes** — so a `CliError` exit 2 from `linkcheck` does
**not** guarantee that no artifact was written. **S9-C recorded this and did not fix it:** it is a
production-path edit and needs its own maintenance checkpoint with its own allowed-path set.

### G1 — There is no command that runs the pipeline · **[C]**

`run_cells.run(root, *, cells, clock, fixtures_dir, max_cells)` is the only whole-run driver, and it
is a **Python function**. `src/harvest/run_cells.py` has no `__main__` and no `argparse`; no shell
script imports or invokes it. Every run in the project's history was started by a test.

Worse for Stage 9 specifically: `run()` builds its opener as
`fixtures_mod.FixtureOpener(sources=…, robots=…, targets=…)` at `run_cells.py:794-806`,
**unconditionally**. There is no opener parameter, no mode switch, no live branch. `HttpClient` is
the real client and would work against a real opener — but the driver never gives it one.

**Consequence:** "Stage 9 is a live smoke" understates it. Before any request can be made, someone
must implement a run command *and* a live-source code path in the driver, and do it under 33 wrappers
that assert `config/` is unmodified and several that assert Stage 4/5 modules are byte-frozen.
**This is the single largest under-estimated item in the roadmap.** Correct it before Stage 9 is
scoped.

### G2 — Stage completion ≠ real dataset creation · **[C]**

`TODO.md` reads, correctly, that Stages 0–8 are closed with thousands of green assertions. A reader
reasonably infers a working system. What exists is a thoroughly tested **library** whose only
observable output has always been written to a temporary directory and deleted. **The distinction is
now stated in the `TODO.md` dashboard and in §0/§1 here.**

### G3 — Fixture success ≠ live success · **[S9]**

Every fixture is **synthetic and hand-authored, never captured** (Stage 3, by design, so no live
harvest was required to build them). Consequences: the 3.7 % acceptance rate is a property of
authored text, not of real feeds; S4-4A states explicitly that **synthetic parser fixtures are
unsuitable for tuning editorial acceptance thresholds**; and no adapter has ever met a real feed's
encoding, malformation, pagination or rate-limiting behaviour. Stage 9 should expect its preflight
and first smoke to be **discovery exercises**, not confirmations.

### G4 — A production-quality enriched run has no owner · **[PM]**

Stage 9 produces `--no-enrich` smokes, which plan §7.1 **explicitly disqualifies from promotion**
("`initial deterministic smoke`" is rejected by name as a promotion reason). Stage 10 writes two
markdown documents. **No stage owns the enriched, production-quality run that M5 requires.** Add it
as a named post-Stage-9 milestone; do not let it be absorbed into Stage 9.

### G5 — "Candidate output" means two different things · **[C]**

`candidate_output` currently exists as a **migration bundle** directory (`base.py:206`), holding 231
converted AX cases. `IMPLEMENTATION_PLAN.md` §7.1 uses the same name for `runs/<run_id>/candidate_output/`,
where reviewed live output would be staged — which **has no producer**; today's runs write
`runs/<run_id>/cells/`. Two artifacts, one name, one implemented and one not. Resolve the naming
before promotion is designed, or a reviewer will read a migration bundle as a publication candidate.

### G6 — `refresh` collides with the legacy pipeline · **[C]**

`scripts/refresh.sh`, `scripts/discover.sh` and `scripts/calibrate_seeding.sh` belong to the **legacy
AX deck pipeline** described in `CLAUDE.md`. The taxonomy harvest's `refresh` is an unimplemented
`mode` enum value. A future `harvest.sh refresh` would sit two directories away from an unrelated
`refresh.sh`. Name it distinctly, or scope it under `harvest.sh` only.

### G7 — Promotion is designed in detail and implemented not at all · **[PM]**

`IMPLEMENTATION_PLAN.md` §7 specifies the journal, before-images, the commit walk, rollback, resume,
a seven-row crash-point recovery table, `--publication-root`, and a fault-injected test. **Zero lines
exist.** `TODO.md` lists these items under Stage 6, where plan §14 **erratum E11 descoped them**;
they have had no owner since. Promotion is a full stage of work, not a checkpoint.

### G8 — Stage 9, as sketched, is far too broad · **[S9]**

`TODO.md`'s four Stage 9 bullets bundle: new script implementation · a live-network code path in the
driver · source preflight · two live executions · a comparison tool that does not exist · a link
checker that does not exist · and the threshold calibration deferred from S4-4A. That is at least
**seven separable concerns and four distinct outbound-request events** in one stage. Decompose it
(§10) — and keep code checkpoints strictly separate from network executions, so an approval to write
a smoke script is never mistaken for an approval to run it.

### G9 — Human review has no artifact and no acceptance process · **[PM]**

Plan §7.1 requires "a reviewed run ID · schema validity · zero unresolved alias conflicts · an
explicit reason describing the review". There is no reviewed-run artifact, no schema for one, no
place a reviewer records a decision, and no definition of what a reviewer is checking. M5 cannot be
scoped until this is designed.

### G10 — Website / consumer integration has no owner at all · **[OOS]**

The website appears once, in a single outcome sentence of the master plan's Context section. No
interface contract, no consumer code, no schema-compatibility statement, no cadence, no deployment
path. Track it as an explicit out-of-scope follow-up with a named owner, or M6 risks publishing a
shape nobody reads.

### G11 — The master plan's runtime layout is partly fictional · **[C]**

Plan §1 lists `runs/<run_id>/{logs/,tmp/<cell_id>/,candidate_output/,promote_staging/,promote_rollback/,promotion_receipt.json}`
and `state/taxonomy_harvest/{registries,cache,domains,locks}/`. **Current code produces none of
them.** A run directory holds `cells/`, `topics/`, `coverage.json`, `alias_conflicts.json`,
`manifest.json`; the state root additionally holds `ledgers/`, `rejections/`, `LATEST_RUN_ID` and
(via migrate) `migrations/`. The lease tree — plan §1's `locks/` — goes to
`tempfile.mkdtemp(prefix="harvest_leases_")`, deliberately outside the artifact root. Anyone sizing
Stage 9 from plan §1 will over-estimate what exists and under-estimate what is missing.

### G12 — `run_manifest.v1.json` advertises four unimplemented modes · **[S9]**

The `mode` enum admits `harvest`, `smoke`, `smoke_model`, `refresh`, `linkcheck`, `migration`. Only
**`harvest`** and **`migration`** have producers. The schema is not wrong — it was written forward —
but it makes an unimplemented capability look shipped. Stage 9 should close two of the four; the
other two stay open.

### G13 — Domain-throttle instability is unresolved · **[S9]**

Three distinct intermittent signatures, none explained. S6-T found no reproducible production defect;
S6-TD added diagnostics only. It passed in the S8-2 run — **one observation, not a resolution.** It
launches real subprocesses against a local recording server and measures timing, so it is the suite
most likely to fail under the load of a live run. **A failure is never to be accepted as a permanent
flake.**

### G14 — CF-6 has grown and now blocks any `config/` edit · **[S9]**

**33 of 39** taxonomy wrappers assert `config/` is unmodified (up from 14 at Stage 4). No checkpoint
that edits `config/` can pass the gate **before** committing. Any Stage 9 calibration change to
`policy.v1.json` hits this immediately. Fixing it means changing 33 files from "config is unmodified"
to "config is unchanged **by this test**".

### G15 — CF-9: source tiers are configured but unreachable · **[PM]**

`policy.v1.json` defines four source-tier weights; no configured source declares a tier, and
`taxonomy.v1.json`'s source object is `additionalProperties: false`. Quality scoring therefore uses
observable evidence completeness rather than authority. Wiring tiers needs a schema change and its
own deviation — relevant to calibration, so it will surface in Stage 9.

### G16 — Stage 10 does not publish · **[R]**

Resolved here by statement: Stage 10 is `IMPLEMENTATION_REPORT.md` + `CONVERGENCE_NOTE.md`. It
creates no JSON and publishes nothing. `TODO.md` and this document now say so; do not let "Stage 10 —
final" read as "final delivery".

### G17 — 508 untracked scratch files · **[OOS]**

Baseline-verified and byte-frozen at 508. Cleaning or gitignoring them is a separate decision,
already recorded as out of scope. Noted because their presence makes `git status` unreadable and
invites accidental scope widening.

---

## 10 · Recommended next checkpoint structure

**A recommendation only. Nothing here is approved, and this document creates no plan.**
`STAGE_9_IMPLEMENTATION_PLAN.md` is deliberately **not** created by this checkpoint.

The audit supports splitting Stage 9 into eight units. **Code checkpoints (odd numbering below) and
operational network executions (even) are deliberately alternated, and the rule holds without
exception: every live execution needs explicit approval immediately before the outbound request, in
addition to its checkpoint approval.**

| # | Proposed unit | Kind | Network | Rationale from the audit |
|---|---|---|---|---|
| **S9-0** | Stage 9 plan of record | Documentation | No | Must first resolve G1, G5, G8, G11, G12 and G14 — several of which change what Stage 9 *is* |
| **S9-1** | **Live command and orchestration implementation** | Code | **No** | G1: a run command and a live-opener path in `run_cells.run()` do not exist. Building them offline, with fixtures still the default, is a separate risk from using them |
| **S9-2** | Live-source preflight | **Execution** | **Yes** | 25 sources, bounded, informational. The cheapest possible first contact; expect it to find dead or reshaped feeds |
| **S9-3** | First bounded smoke | **Execution** | **Yes** | The M2 milestone: the first **retained** 43-path tree |
| **S9-4** | Second smoke + normalized comparison | **Code + execution** | **Yes** | `compare-runs` must be *written* (it does not exist) before the second run is worth making. Consider splitting into S9-4a (code) / S9-4b (execution) |
| **S9-5** | Calibration decision | Documentation + possibly `config/` | No | Discharges S4-4A. **Hits G14 head-on** — a `config/` edit cannot pass the gate before committing, so sequence it deliberately |
| **S9-6** | Linkcheck | **Code + execution** | **Yes** | Also does not exist. Same split recommendation as S9-4 |
| **S9-C** | Stage 9 closeout | Documentation | No | L0 validation only, matching S5-C / S6-C / S7-C / S8-C precedent |

`smoke-model` should stay **outside** this sequence and remain opt-in: its `model_search` adapter
raises `AdapterNotImplemented`, so it is an implementation project, not a run.

### Recommended post-Stage-9 milestones — separate, and each unopened

| Milestone | Why it must be separate |
|---|---|
| **M5 · Production enriched run** | Stage 9 produces `--no-enrich` smokes that plan §7.1 explicitly disqualifies from promotion. **G4: currently unowned.** Needs its own enrichment budget design |
| **M5b · Human review** | **G9: no artifact, no schema, no acceptance criteria exist.** Must be designed before it can be performed |
| **M6 · Production promotion** | **G7: zero lines of code exist** against a detailed §7 design. Journal, before-images, commit walk, rollback, resume and a fault-injected isolated test — a full stage, not a checkpoint |
| **M7a · Website integration** | **G10: no owner, no interface contract, outside this repository** |
| **M7b · Recurring scheduling / refresh** | **G6: name collision with the legacy `scripts/refresh.sh`**; cadence, budget and failure policy all undesigned |

---

## 11 · Evidence index

Read in this order; each outranks the one below it where they differ.

| # | Source | What it is authoritative for |
|---|---|---|
| 1 | Committed code under `src/harvest/**`, `scripts/harvest/**` | What actually exists and runs |
| 2 | `tests/**` (**63 wrappers**, 44 taxonomy) | What is proven, and at which layer |
| 3 | `schemas/harvest/*.v1.json`, `config/harvest/**` | The data contracts and the 12-cell taxonomy |
| 4 | `docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md` | **The current completion authority** — Stage 9 delivery record, commit chain, live evidence, retained-root disposition, carried-forward work |
| 5 | `docs/harvest/handoffs/HANDOFF_STAGE_<N>_COMPLETE_*.md` | Per-stage delivery record for earlier stages |
| 6 | `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` | **The Stage 9 plan of record** — every command contract, D9-A/D9-B, and errata E9-1 … E9-21 |
| 7 | `docs/harvest/STAGE_<N>_IMPLEMENTATION_PLAN.md` | The approved plan and errata for stages 2.5 – 8 |
| 8 | `docs/harvest/TODO.md` | The live checklist and current position |
| 9 | **This file** | Cross-stage roadmap, artifact lifecycle, gap register |
| 10 | `docs/harvest/IMPLEMENTATION_PLAN.md` | **Design input only.** Pre-Stage-3 in places, superseded by Stage 7 §11, and describes commands and paths that do not exist (G11) |

**Specific claims and where they were checked:**

- 43-path run set — `tests/harvest/test_target_determinism.py:149` (`expected_paths`) and `:397`
  (`test_the_tree_is_exactly_the_43_expected_paths`).
- *(Superseded by Stage 9)* Unconditional fixture opener — `src/harvest/run_cells.py:794-806`.
  `run()` now takes an injected `Transport`; `cli.py` owns the single live-opener decision.
- *(Superseded by Stage 9)* No run CLI. `scripts/harvest/harvest.sh` and `src/harvest/cli.py` exist,
  registering six commands. **There is still no `"harvest"` key in `cli.COMMANDS`.**
- 3-file migration bundle — `src/harvest/migrate/base.py:200-210` (`BUNDLE_RELATIVE_PATHS`).
- Migration source corpus — `ax_cases.py:517` `DEFAULT_REGISTRY = "state/ax_case_harvest_registry.json"`,
  one of the 18 paths in `tests/fixtures/taxonomy/protected_paths.txt`.
- Runtime-path guard — `scripts/validate_task.sh:250` (`RUNTIME_PATHS`), checked before and after.
- Absent producers, **re-checked at `ec9bedc`** — `promotion_receipt`, `promotion_journal`,
  `publication_manifest`, `promote_staging`, `promote_rollback`, `--publication-root`: **still zero
  matches** in `src/`, `scripts/`, `schemas/`, `config/`, `tests/`. *(`compare-runs` and
  `preflight-sources` were on this list before Stage 9 and are now implemented — see §8.1.)*
- 12 cells / 25 sources / 3 topics — `config/harvest/topics/*.v1.json` and
  `run_cells.configured_cells()`.
- Published-set derivation — `IMPLEMENTATION_PLAN.md` §1 path contract × the committed taxonomy.
  **Derived, not observed: none of those files exist.**
