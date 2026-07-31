# Taxonomy harvest — roadmap and artifact lifecycle

A **durable operational map**, not a session handoff. It answers four questions the stage handoffs
deliberately do not: *what exists in code right now*, *what JSON any of it actually produces*, *what
still has no implementation at all*, and *how far the project is from a published dataset*.

**Authority.** Committed code and executable tests outrank `IMPLEMENTATION_PLAN.md` wherever they
differ. Every capability claim below was checked against the tree at `bf067303`; where the master
plan describes something with no executable owner, that is recorded as a gap rather than as a
feature. Inference is labelled inference.

**This document opens nothing.** It is not a Stage 9 plan, it does not approve a checkpoint, and it
does not authorize a network request, a migration apply, or a promotion.

---

## 0 · The eight layers, and why "done" is never enough on its own

Every status word in this file is qualified by exactly one of these. They are ordered by increasing
distance from a real product artifact, and **nothing in this repository has ever reached layer 6, 7
or 8.**

| # | Layer | Meaning | Reached? |
|---|---|---|---|
| 1 | **Fixture run** | The pipeline driven over `tests/fixtures/harvest/**`, synthetic hand-authored inputs, no socket | **Yes**, routinely |
| 2 | **Temporary-root run** | Real writer code writing a real tree, into an injected `tmp` root that is deleted afterwards | **Yes**, routinely |
| 3 | **Retained runtime run** | Artifacts left on disk under `state/taxonomy_harvest/` for a human to read | **No** — the path does not exist |
| 4 | **Migration bundle** | The AX corpus converted to `record.v1.json` rows and published as one 3-file bundle | Temp-root only (layer 2) |
| 5 | **Candidate output** | A retained run's records, staged and awaiting human review | **No** — no producer, no retained run |
| 6 | **Publication-eligible candidate** | A reviewed candidate set that `promote` would accept | **No** |
| 7 | **Promoted publication** | JSON committed under `data/harvested/**` | **No** — directory absent, no promotion code |
| 8 | **Website-consumed dataset** | `cherryinthehaystack.com` reading that JSON | **No** — no consumer, no owner, no interface |

A **retained runtime run** (3) is the first layer whose output survives the process that made it. It
is the next observable data-producing milestone, and it has **no implemented command**.

---

## 1 · Executive status

```text
authoritative tip        bf067303a01fa80d1421f9eef7030cbadf805733
                         docs(harvest): record stage 8 completion
sync                     HEAD = local main = local origin/main, 0 behind / 0 ahead
completed stage          Stage 8 — CLOSED and PUBLISHED
next stage               Stage 9 — NOT OPEN, NOT APPROVED, no plan of record exists
runtime output state     NONE. state/taxonomy_harvest/, runs/, LATEST_RUN_ID all ABSENT
publication output state NONE. data/harvested/ ABSENT; no promotion code exists anywhere
migration state          Implemented and offline-proven; ZERO operational applies. No bundle retained
live-network state       ZERO requests ever made by this pipeline, at any stage, in its entire history
```

**Core pipeline implementation and offline verification.** The discovery → extraction →
classification → verification → faceting → record → artifact chain is implemented end to end in
`src/harvest/**` and verified offline: `bash scripts/validate_task.sh --all` exercises **58 wrappers
(19 legacy + 39 taxonomy), each exactly once, zero skips, exit 0** — one authoritative run at S8-2,
736 s. That is layer 1/2 verification of a **library and its driver function**, not of an operable
system.

**Has a real live taxonomy harvest occurred?** No. Stronger than "not yet approved": `run_cells.run()`
constructs its opener unconditionally as `fixtures.FixtureOpener` (`src/harvest/run_cells.py:794-806`).
There is no parameter, flag, or branch that would let it issue a network request. **A live harvest is
not currently possible without new production code.**

**Has an operational AX migration apply occurred?** No. `migrate.sh ax-cases --apply --state-root
PATH` works and is proven, but every apply in the repository's history went to an injected temporary
root that was then deleted. `state/taxonomy_harvest/` does not exist.

**Has any real `data/harvested/` publication occurred?** No — and no code could perform one.
`promotion_receipt`, `promotion_journal`, `publication_manifest`, `promote_staging`,
`promote_rollback` and `--publication-root` have **zero occurrences** in `src/`, `scripts/`,
`schemas/`, `config/` or `tests/`. Promotion exists only as design prose in
`IMPLEMENTATION_PLAN.md` §7.

**Next observable data-producing milestone.** A **retained runtime run** — 43 real files under
`state/taxonomy_harvest/`. Its blocking dependency is not approval; it is that **no command exists
that calls `run_cells.run()`**.

### 1.1 Four percentages, four different denominators

Percentages here are counts, not judgement. Each names its denominator explicitly; they are **not**
comparable to one another and must never be averaged.

| Dimension | Denominator | Value | Basis |
|---|---|---|---|
| **Named stage completion** | The **12** named stage labels: 0, 1, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10 | **10 of 12 closed = 83 %** | Stages 0, 1, 2, 2.5, 3, 4, 5, 6, 7, 8 closed; 9 and 10 not opened |
| **Implementation capability** | The 13 subsystems the master plan names as commands or producers (harvest driver, migrate, preflight-sources, smoke, smoke-model, compare-runs, linkcheck, refresh, promote, diff, publication manifest, promotion journal, `harvest.sh` dispatcher) | **2 of 13 = 15 %** | Only the run driver (as a *function*, not a command) and `migrate.sh` exist |
| **Live operational validation** | Any single live request | **0 of 1 = 0 %** | No request has ever been made |
| **Production publication** | 16 expected stable published JSON files (§6.3) | **0 of 16 = 0 %** | `data/harvested/` absent |

The gap between 83 % and 15 % is the single most important fact in this document: **stage completion
measures approved-and-verified checkpoints, not operable commands.** Stages 0–8 built a
comprehensively tested library. They did not build a program a human can run.

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

### Stage 9 — bounded deterministic live smoke

| Field | Value |
|---|---|
| Purpose | *As currently sketched in `TODO.md`:* `smoke`/`smoke_model` scripts + `preflight-sources`, a 12-category `--no-enrich` smoke run twice, `compare-runs --normalize`, `linkcheck --sample 20` |
| Status | **NOT OPEN, NOT APPROVED.** No `STAGE_9_IMPLEMENTATION_PLAN.md` exists |
| Principal capability | **None delivered** |
| Wrote only to temp roots? | n/a |
| Contacted network? | n/a — would be the **first** network contact in the project's history |
| Retained runtime output? | n/a — would be the first retained runtime output |
| Published output? | No — a smoke run is `publication_eligible: false` by derivation |
| Completion authority | n/a |
| Remaining dependency | **Every one of its named deliverables is unimplemented**, and so is the *prerequisite* nobody has scoped: a command that runs the pipeline at all, and a code path that lets it use the network. See §9 item G1 |

### Stage 10 — final report

| Field | Value |
|---|---|
| Purpose | `IMPLEMENTATION_REPORT.md` (every file created/changed, exact commands, results) and `CONVERGENCE_NOTE.md` (5 gates before matrix unification is reconsidered), plus unresolved issues and follow-ups |
| Status | **NOT OPEN** |
| Principal capability | None delivered |
| Wrote only to temp roots? | n/a |
| Contacted network? | n/a |
| Retained runtime output? | **No — and it never would.** Stage 10 is two markdown documents |
| Published output? | **No.** Stage 10 does **not** create or publish production JSON. Nothing in the committed tree or in `TODO.md` gives it that scope |
| Completion authority | n/a |
| Remaining dependency | Stage 9 |

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

### M2 — first real staged taxonomy output

- **Definition of done:** one **retained** run under `state/taxonomy_harvest/` — 43 real paths a
  human can open — produced from live sources.
- **Status:** **NOT STARTED, and blocked by missing code**, not only by missing approval. Two hard
  blockers: there is no command that invokes `run_cells.run()`, and `run()` cannot use the network.
- **Owner:** Stage 9 (the live-execution part), preceded by an unscoped implementation checkpoint.
- **Prerequisite:** M1; a run command; a live opener path; live-source preflight; explicit network
  approval immediately before the request.
- **Visible artifact:** `state/taxonomy_harvest/runs/<run_id>/**` + `ledgers/` + `rejections/` +
  `LATEST_RUN_ID` (43 paths).
- **Approval required:** **Yes — twice.** Once for the checkpoint, once immediately before the
  outbound request.
- **Scope:** part of the original task (Stage 9).

### M3 — repeatability and calibration

- **Definition of done:** two live smokes under a pinned bound, `compare-runs --normalize` showing
  only the enumerated clock-derived movement, and an explicit calibration decision on the S4-4A
  thresholds against **live** data.
- **Status:** **NOT STARTED.** `compare-runs` has no implementation anywhere in the tree.
- **Owner:** Stage 9.
- **Prerequisite:** M2 twice.
- **Visible artifact:** two run trees plus a comparison result (**no producer exists; the output
  form is undefined — the master plan §8 describes `content_changes[]` but names no file**).
- **Approval required:** Yes — a second live execution.
- **Scope:** part of the original task.

### M4 — link-health validation

- **Definition of done:** `linkcheck --sample 20` over a retained run, producing a run in
  `mode: "linkcheck"`.
- **Status:** **NOT STARTED.** `linkcheck` exists only as a `mode` enum value in
  `run_manifest.v1.json` and as prose; no producer.
- **Owner:** Stage 9.
- **Prerequisite:** M2.
- **Visible artifact:** a further run tree with `mode: "linkcheck"`.
- **Approval required:** Yes — live requests, and deliberately to arXiv, whose 15 s crawl-delay the
  plan treats as the point of the exercise.
- **Scope:** part of the original task.

### M5 — reviewed production candidate

- **Definition of done:** an **enrichment-complete** run (not `--no-enrich`), of publication quality,
  reviewed by a human against a defined acceptance record, with zero unresolved alias conflicts.
- **Status:** **NOT STARTED and UNOWNED.** No stage in `TODO.md` owns a production-quality enriched
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

### 4.1 Close the currently described Stage 0–10 plan

| Field | Value |
|---|---|
| Minimum expected checkpoints | **10** — Stage 9 plan of record · run-command implementation · live-opener implementation · preflight-sources · smoke · second smoke · compare-runs · linkcheck · Stage 9 closeout · Stage 10 report+convergence note |
| Likely corrective checkpoints | **3–6.** Precedent is strong: Stage 6 needed S6-0-C, S6-2-C, S6-6A, S6-6B, S6-T, S6-TD — six unplanned units. First contact with real feeds will surface adapter, encoding, robots and pacing defects that 25 synthetic fixtures could not |
| Total range | **13–18 checkpoints** |
| Major uncertainty | Whether the live-run capability is one checkpoint or three. `run()` takes no opener parameter and no mode; adding a live path touches the driver, the budget wiring and the manifest `mode` field, all of which sit under 33 wrappers that assert `config/` is clean and several that assert byte-freezes |
| External dependency | 25 real source endpoints must still exist, still serve the expected shape, and still permit crawling under RFC 9309 |
| Live/network approval | **Yes** — for `preflight-sources`, both smokes, and `linkcheck`. Four separate outbound-request approvals minimum |

### 4.2 Generate the first real staged JSON set (M2)

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

### 4.6 Roll-up

| To reach | Checkpoints (range) |
|---|---|
| M2 — first staged dataset | 5 – 7 |
| End of the described Stage 0–10 plan (≈ M4) | 13 – 18 |
| M5 — reviewed production candidate | +7 – 10 |
| M6 — published JSON | +8 – 10 |
| M7 — website integration | +6 – 10 |
| **M1 → M7 total** | **34 – 48 checkpoints** |

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

"Exists now?" means an executable owner was found in the tree. Planned syntax is **not** presented as
executable.

| Command | Exists now? | Owner | Network? | Writes real runtime state? | Files created/changed | Retained? | Publication impact | Approval required | Execution history | Milestone owner |
|---|---|---|---|---|---|---|---|---|---|---|
| `bash scripts/validate_task.sh --all` | **Yes** | `scripts/validate_task.sh` | **No** — offline by construction, mocked agents, temp state | **No** — and it *asserts* the four runtime paths are absent before **and** after, never deleting what it finds | None in the repository; temp trees only | No | None | No (routine gate) | **Run once authoritatively at S8-2** — exit 0, 736 s, 58/58 wrappers, zero skips | M1, done |
| `migrate.sh entity-assess` | **Yes** | `src/harvest/migrate/entity_assess.py` | No | **No** — stdout only, unless `--output PATH` | None (or exactly one explicit `--output` file) | Only if `--output` given | None | No | Run in S7-1/S7-4/S7-6; **1,161 entities assessed, 0 migrated** | Stage 7, done |
| `migrate.sh ax-cases --dry-run` (the default) | **Yes** | `src/harvest/migrate/ax_cases.py` | No | **No** — reads the protected registry, writes nothing | None | No | None | No | Run repeatedly; **231/231 accepted, exit 0**, byte-identical across runs | Stage 7, done |
| `migrate.sh ax-cases --apply --state-root <tmp>` | **Yes** | `ax_cases.apply_migration()` | No | **Into the injected root only** | 3 JSON in one bundle (§6.2) | Deleted after every test | **None** — not publication | Yes, per invocation | Run **only** under temp roots; an AST scan forbids `--apply` without `--state-root` | Stage 7, done |
| `migrate.sh ax-cases --apply` **against the default state root** | Recognised; **operationally unapproved** | same | No | **Yes** — would create `state/taxonomy_harvest/` | 3 JSON + 3 dirs | **Yes, permanently** | None — still not publication | **Yes, separately and explicitly** | **Never executed** | Unowned; would be its own checkpoint |
| **A command that runs a taxonomy harvest** | **NOT IMPLEMENTED** | — | — | — | — | — | — | — | — | **Unowned — the blocking gap for M2** (§9 G1) |
| `harvest.sh preflight-sources` | **NOT IMPLEMENTED** | — | Would be **first ever** network contact | Would | Undefined | — | None | Yes ×2 | Never | Stage 9 |
| `harvest.sh smoke` (first) | **NOT IMPLEMENTED** | — | Yes | Yes — 43 paths | 43 | Yes | `publication_eligible: false` by derivation | Yes ×2 | Never | Stage 9 / M2 |
| `harvest.sh smoke` (second) | **NOT IMPLEMENTED** | — | Yes | Yes — a second 43-path tree | 43 | Yes | None | Yes ×2 | Never | Stage 9 / M3 |
| `harvest.sh compare-runs --normalize` | **NOT IMPLEMENTED** — zero occurrences in the tree | — | No | Unknown — **output form undefined** | Undefined | Undefined | None | Yes (checkpoint) | Never | Stage 9 / M3 |
| `harvest.sh linkcheck --sample 20` | **NOT IMPLEMENTED** | — | Yes | Yes — a `mode: "linkcheck"` run | 43 (inferred) | Yes | None | Yes ×2 | Never | Stage 9 / M4 |
| `harvest.sh refresh` | **NOT IMPLEMENTED** as a taxonomy command | — | Yes | Yes | Undefined | — | None | Yes ×2 | Never | **Unowned** (M7) |
| `harvest.sh promote` | **NOT IMPLEMENTED** — zero occurrences | — | No | Yes — **writes tracked `data/harvested/**`** | Up to 16 stable JSON + a transient journal | **Yes, tracked** | **This is publication** | **Yes, strictest** | Never | **Unowned** (M6) |
| `harvest.sh smoke-model` | **NOT IMPLEMENTED**; its `model_search` adapter raises `AdapterNotImplemented` | — | Yes | Yes | Undefined | — | None | Yes ×2 | Never | Stage 9, opt-in (plan §14 cmd 24) |

**`scripts/harvest/harvest.sh` does not exist.** The master plan's acceptance commands invoke it
about ten times. `scripts/harvest/` contains exactly: `check_config.py`, `check_facets.py`,
`check_fixtures.py`, `gen_facet_schema.py`, `gen_protected_baseline.sh`, `hash_tree.py`,
`migrate.sh`, `protected_baseline.py`, `verify_protected_baseline.sh`.

---

## 9 · Risks, contradictions, and roadmap gaps

Classified, not solved. Categories: **[R]** already resolved · **[S9]** Stage 9 planning decision ·
**[PM]** later production milestone · **[OOS]** explicit out-of-scope follow-up · **[C]**
contradiction requiring correction before implementation.

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
| 2 | `tests/**` (58 wrappers, 39 taxonomy) | What is proven, and at which layer |
| 3 | `schemas/harvest/*.v1.json`, `config/harvest/**` | The data contracts and the 12-cell taxonomy |
| 4 | `docs/harvest/handoffs/HANDOFF_STAGE_<N>_COMPLETE_*.md` | Per-stage delivery record, measurements, carried-forward findings |
| 5 | `docs/harvest/STAGE_<N>_IMPLEMENTATION_PLAN.md` | The approved plan and errata for stages 2.5 – 8 |
| 6 | `docs/harvest/TODO.md` | The live checklist and current position |
| 7 | **This file** | Cross-stage roadmap, artifact lifecycle, gap register |
| 8 | `docs/harvest/IMPLEMENTATION_PLAN.md` | **Design input only.** Pre-Stage-3 in places, superseded by Stage 7 §11, and describes commands and paths that do not exist (G11) |

**Specific claims and where they were checked:**

- 43-path run set — `tests/harvest/test_target_determinism.py:149` (`expected_paths`) and `:397`
  (`test_the_tree_is_exactly_the_43_expected_paths`).
- Unconditional fixture opener — `src/harvest/run_cells.py:794-806`.
- No run CLI — no `__main__` or `argparse` in `src/harvest/run_cells.py`; `scripts/harvest/` listing.
- 3-file migration bundle — `src/harvest/migrate/base.py:200-210` (`BUNDLE_RELATIVE_PATHS`).
- Migration source corpus — `ax_cases.py:517` `DEFAULT_REGISTRY = "state/ax_case_harvest_registry.json"`,
  one of the 18 paths in `tests/fixtures/taxonomy/protected_paths.txt`.
- Runtime-path guard — `scripts/validate_task.sh:250` (`RUNTIME_PATHS`), checked before and after.
- Absent producers — repository-wide searches for `promotion_receipt`, `promotion_journal`,
  `publication_manifest`, `compare-runs`, `compare_runs`, `preflight-sources`, `preflight_sources`,
  `promote_staging`, `promote_rollback`, `--publication-root`: **zero matches** in `src/`, `scripts/`,
  `schemas/`, `config/`, `tests/`.
- 12 cells / 25 sources / 3 topics — `config/harvest/topics/*.v1.json` and
  `run_cells.configured_cells()`.
- Published-set derivation — `IMPLEMENTATION_PLAN.md` §1 path contract × the committed taxonomy.
  **Derived, not observed: none of those files exist.**
