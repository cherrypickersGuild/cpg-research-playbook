# Stage 5 completion handoff — artifact persistence

**Date:** 2026-07-30 · **Branch:** `main` · **Closing commit:** `bc920b5b8b57907165b7a5f8d47239383b974212`

A durable milestone summary, not a session log. It records what Stage 5 delivered and the state the
repository was in when Stage 5 closed. **It approves nothing**, and in particular it does not open
Stage 6.

---

## 1 · Commit chain

```text
bc920b5b8b57907165b7a5f8d47239383b974212  feat(harvest): add recovery and re-run semantics      S5-7
5db50bd0156062a9f2381e04237866b53e9e368f  feat(harvest): add sequential cell driver             S5-6
e178586a3c30b1dbc82d8b536262752bc5630690  feat(harvest): add run manifest and latest run pointer S5-5
e93d897c8deb67079d6ec7b5ab2c8814db5e3c03  feat(harvest): add coverage report wiring             S5-4
b76ed3cf823ff2d0cf03e4016d51f68983d9eb33  feat(harvest): add rejection log and url ledger       S5-3
e179f5fa7c2e1a81fd71567cdeb0d5319173ef92  feat(harvest): add cell and topic artifacts           S5-2
071204d927163b066d8dee64919af4e3ad5f3b1d  feat(harvest): add deterministic atomic artifact writer S5-1
80505a16c4f2592ca25c2e954eb25906e2decd98  docs(harvest): plan stage 5                           S5-0
b303d9db1e7433a740960bfbaaf83e82acfd8433  Stage 4 closing commit
8865c54e2cc8d879410576f247baac4aea149f34  implementation-start anchor (protected baseline measured here)
```

Plan of record: `docs/harvest/STAGE_5_IMPLEMENTATION_PLAN.md`. Every checkpoint committed alone,
each separately approved **by name**, each gated by its narrowest suite before the next began.
Stage 5 produced **no corrective commit**: the three defects found during the stage were found by the
tests written for their own checkpoint and fixed before that checkpoint committed (§2.3).

## 2 · Delivered

**Production modules — three, and nothing else.**

```text
src/harvest/artifacts.py   708  the one serializer, the one atomic writer, and every artifact
                                shape: cell, topic, coverage, manifest, LATEST_RUN_ID, plus the
                                S5-7 recovery primitives (WriteJournal, write_journal,
                                run_is_finished, verify_latest_run_id)
src/harvest/ledger.py      237  rejection log and the cross-run URL ledger; merge semantics,
                                terminal outcomes, corrupt-ledger refusal
src/harvest/run_cells.py   799  the sequential cell driver: Stage 4's pipeline over the fixture
                                corpus, routed into the artifact contracts, one run at a time
```

**Test suites — seven, 384 assertions.**

```text
tests/harvest/test_artifacts.py        338   33  S5-1
tests/harvest/test_cell_artifact.py    417   44  S5-2
tests/harvest/test_ledger.py           446   46  S5-3
tests/harvest/test_coverage_report.py  456   43  S5-4
tests/harvest/test_manifest.py         420   52  S5-5
tests/harvest/test_run_cells.py        920   90  S5-6  (91 at S5-6; one guard deleted at S5-7)
tests/harvest/test_recovery.py         862   76  S5-7
```

Each has a `tests/test_taxonomy_<name>.sh` wrapper whose epilogue asserts production `state/` and
`config/` are unmodified **and** that the repository's own runtime paths were never created.

### 2.1 · What each checkpoint established

- **S5-1** — one serialization (`sort_keys`, UTF-8, LF, one trailing newline), so bytes follow content
  rather than dict insertion order. Writes go to `.tmp_<uuid4hex>_<basename>` **beside the
  destination** (`os.replace` is atomic only within one filesystem), fsync then rename. Cleanup
  catches `BaseException`, so an interrupt leaks nothing. `write_document` validates **before**
  serializing: an invalid document writes no file at all.
- **S5-2** — cell and topic artifacts. Counts are **derived and a caller may not supply one**, so a
  metadata block can never disagree with the records beside it. `by_category` counts full records
  only and therefore sums to `full_records`; a `cross_reference` never inflates a category. D2 — the
  `{signal, matched}` narrowing — got one home.
- **S5-3** — rejection log and the cross-run, cell-owned URL ledger. `first_seen_at` is written once;
  a terminal outcome is final; a corrupt ledger **raises** rather than resetting to empty, because
  losing a ledger silently re-harvests the whole cell. CF-2 pinned by enumerating verify's reasons
  from its AST.
- **S5-4** — coverage report, **wiring and not new logic**: `coverage.py` and `facets.py` are
  byte-unchanged, asserted in-suite. CF-11 protected by six assertions — an empty
  `industry.secondary` is never reported as a gap, and one test proves the counter is *live* so the
  design decision cannot decay into a broken counter.
- **S5-5** — run manifest and the pointer. Twelve configured cells, twelve rows; an unreached cell is
  `not_run`, never omitted. `publication_eligible` is **derived, never a parameter**. The pointer
  moves last, or not at all.
- **S5-6** — the sequential cell driver: the checkpoint that made Stage 5 a *stage* rather than a
  library. One run emits **42 files**, all validating; the file set is asserted **exactly**.
- **S5-7** — recovery and re-run semantics (§2.2).

### 2.2 · S5-7 — the recovery and re-run contracts, as shipped

These are the contracts a successor inherits, stated as behaviour rather than intent. Each was
measured by actually breaking `os.replace`, `os.unlink` or the pointer write.

- **Nothing partial is ever readable.** Every file on disk is a complete, schema-valid artifact, or
  it is absent. There is no third state, at any interruption point, for `OSError` or
  `KeyboardInterrupt` alike.
- **An interrupted, unmanifested run cannot advance `LATEST_RUN_ID`.** The pointer is written after
  the manifest is safely on disk, and only then. A run interrupted two artifacts in left both files
  valid, **no manifest**, **no temp debris**, and the pointer still naming the previous run.
  `verify_latest_run_id(root)` turns that promise into a checkable predicate: it returns the run the
  pointer names, or raises when that run's manifest is missing, unreadable, invalid, or names a
  different run.
- **A dying run does not half-update cross-run state.** The interrupted run above left the ledger at
  `seen_count: 1` with run 1's `last_seen_at` — the durable memory never claimed to have seen the
  corpus twice.
- **The manifest-without-pointer case is left in the safe direction, deliberately.** A run that dies
  between the two leaves a complete, valid, orphaned manifest and the previous pointer. An orphaned
  manifest is inert; a pointer naming a manifest that does not exist would break the pointer's only
  promise.
- **No resume policy was introduced, and a repeated completed run id is refused.** `run_is_finished`
  is checked **before the first byte is written**, so a refused repeat leaves the tree
  hash-identical. `publish_run` already refused a finished run, but only at the end — by which time
  the ledger had double-counted and the rejection log had been replaced, for a run that was never
  going to be published. An orphaned run is refused if repeated, not resumed; the operator runs a
  fresh `run_id`.
- **The sweeper proves ownership rather than pattern-matching.** `WriteJournal` removes only temp
  paths it watched being created; a foreign `.tmp_*` is left strictly alone, because glob-and-delete
  would destroy another writer's in-flight file — a worse failure than the debris it cleans. It
  refuses to unlink any name without the temp prefix even when told to, never raises (it runs from a
  `finally`, where raising would mask the interruption that called it), and is idempotent. A clean
  run sweeps nothing and says so.
- **Deterministic continuation.** Two consecutive runs into one root differ at exactly four JSON
  leaves — `harvest_run_id`, `generated_at`, `discovered_at`, `freshness_score` — all derived from the
  run instant, which is a genuine input. The difference set is **enumerated by a recursive JSON diff,
  not normalized away**, so a fifth moving field fails rather than passing silently. Every identity,
  classification, metadata count and the other three scores reproduce exactly: **a re-run does not
  re-judge.** Freshness is asserted to have *decayed*, so the field cannot silently freeze.
- **`ledgers/` merge; `rejections/` are replaced per cell and cannot merge.** `rejection.v1.json` is
  `additionalProperties: false`, carries exactly one `harvest_run_id`, and its entries carry no run
  field — a merged log could not name the run that produced its rows, and those rows would grow
  without bound and become indistinguishable. Bending the schema to fit the plan's summary sentence
  was rejected. The guarantee that matters is asserted instead: **a run never clobbers a cell it did
  not run.**

### 2.3 · Defects found and fixed inside their own checkpoint

None reached a commit; each was found by the test written for it.

1. **S5-2 — topic merge survivor depended on cell order.** The merge deduplicated in cell-iteration
   order and sorted afterwards. Sorting **before** deduplicating makes the survivor a function of
   content: `topic([a, b])` and `topic([b, a])` are now byte-identical.
2. **S5-4 — the committed coverage builder projected per-record rows in input order.** It sorts
   `by_category` but not its records projection, so shuffled input produced different bytes. The
   delegate sorts by the committed `records.sort_key` first. That fix belongs in the persistence
   wrapper, not in `coverage.py`, which stayed byte-unchanged.
3. **S5-7 — S5-6's interruption injection was vacuous.** It counted every `os.replace`; `HttpClient`
   writes its domain leases atomically too, so the budget was spent on lease files during discovery
   and the run died *before writing any artifact* — the partial-tree tests passed while proving
   nothing. The injection is now scoped to renames under the artifact root, with an assertion that the
   interruption really was part-way through (exactly two artifacts present) so the class cannot go
   vacuous again.

### 2.4 · Deviations and allowed-path additions, each separately approved

Recorded here as well as at their checkpoints, so the authorization trail is in one place.

```text
S5-3  M tests/harvest/test_cell_artifact.py   deleted an assertion that ledger.py and run_cells.py
                                              do not exist — a checkpoint-progress guard, not a
                                              contract. The same landmine was removed from
                                              test_ledger.py in the same pass.
S5-4  M tests/harvest/test_artifacts.py       one line: "coverage_report" deleted from the boundary
                                              guard's prohibited-token tuple.
S5-5  M tests/harvest/test_artifacts.py       one deletion: the entire
                                              test_it_knows_nothing_about_later_checkpoint_semantics
                                              method, not replaced with a later-checkpoint guard.
S5-7  M tests/harvest/test_run_cells.py       two corrective test changes (see below).
```

**S5-7's inclusion of `tests/harvest/test_run_cells.py` was ratified by the user on 2026-07-30**, for
exactly the two corrective test changes reported, and with the direction not to reopen, amend, revert
or rewrite the S5-7 implementation commit `bc920b5b8b57907165b7a5f8d47239383b974212`:

1. **Deletion of the temporary guard that prohibited S5-7 semantics.** `test_it_does_not_begin_s5_7_or_stage_6`
   forbade the token `sweep` in `run_cells.py` — precisely this checkpoint's semantics. Per the S5-5
   precedent the **entire** method was deleted rather than narrowed, and was **not** replaced with a
   guard against S5-C or Stage 6. Renaming the sweeper to dodge the scan was rejected on S5-4's
   precedent: it would obfuscate code to satisfy a test.
2. **Correction of the byte-unchanged assertion.** `test_the_stage_4_modules_are_byte_unchanged`
   listed Stage 5-owned `artifacts.py` and `ledger.py` among modules asserted unchanged against HEAD,
   but §8 of the plan states outright that `artifacts.py` accretes across S5-2, S5-3, S5-4, S5-5 **and
   S5-7**. The assertion asserted something the plan says is false, and would have made every future
   checkpoint red pre-commit — a CF-6 shape on a checkpoint that edits no config. It now covers the
   **nine Stage 4 modules** it always claimed to cover: `pool`, `records`, `coverage`, `facets`,
   `verify`, `classify`, `extract`, `dedupe`, `facetassign`.

**The rule these four share, and which the successor inherits:** a boundary test asserts facts about
the surface of the module under test — never about which files happen to exist yet, and never about
how the working tree compares to HEAD.

## 3 · Validation at closure

**1,324 assertions across 30 suites · all green**, in one full-gate run before the S5-7 commit, with
the three focused suites S5-7 touches re-run green from the committed tree afterwards.

```text
protected_baseline 24   config 18   identity 42   schema 35   http 80
domain_throttle 35      budget 16   facets 34     facet_ambiguity 28
facet_identity 16       facet_states 32           customer_interaction 13
pool 57                 coverage 27   source_cache 34
adapters 66             adapter_concurrency 10
dedupe 55               extract 58    classify 78   verify 63
facetassign 68          records 51
artifacts 33            cell_artifact 44   ledger 46   coverage_report 43
manifest 52             run_cells 90       recovery 76
```

940 inherited from Stage 4 + 33 S5-1 + 44 S5-2 + 46 S5-3 + 43 S5-4 + 52 S5-5 + 90 S5-6 + 76 S5-7 =
**1,324**. Every prior assertion remained green throughout. The only existing test file Stage 5
edited is `tests/harvest/test_run_cells.py` — Stage 5's own — and only for the two ratified
corrective changes in §2.4; no Stage 0–4 test was modified.

**Checkers — all exit 0**

```text
python scripts/harvest/check_fixtures.py             exit 0
bash   scripts/harvest/verify_protected_baseline.sh  exit 0   18/18 byte-match 8865c54e...
python scripts/harvest/check_facets.py               exit 0
python scripts/harvest/gen_facet_schema.py --check    exit 0
python scripts/harvest/check_config.py               exit 0
git diff --exit-code -- scripts/harvest/check_config.py       byte-unchanged (DV-1 intact)
```

**CF-6 was never triggered.** No Stage 5 checkpoint edited `config/`, so every checkpoint passed the
full gate before its own commit. The CF-6 procedure stays documented for whichever later checkpoint
must edit config.

**A representative end-to-end run**, over the committed fixture corpus with a pinned clock:

```text
42 files     12 cell artifacts · 3 topic artifacts · 12 rejection logs · 12 ledgers ·
             coverage.json · manifest.json · LATEST_RUN_ID
             all 42 validate; the file set is asserted exactly
outcome      11 zero_result cells (all_below_relevance_threshold) · 1 ok cell, 4 records
accounting   source_fetch_owners 25 · http_attempts 25 · target_fetch_owners 0
eligibility  publication_eligible: false — "no target page was fetched, so every record is
             unverified (target fetching arrives in Stage 6)"
determinism  two runs and a shuffled-cell run hash identically
```

**The corpus yielding 11 zero-result cells is a finding, not a harness failure.** Every zero cell
reports `all_below_relevance_threshold`, which is what the committed relevance lists actually say
about these fixture items. The bar was never lowered to manufacture a result.

## 4 · Repository state at closure

```text
HEAD                    bc920b5b8b57907165b7a5f8d47239383b974212
index                   empty
tracked modifications   zero
untracked baseline      508 files, byte-identical; drift 0, missing 0
protected baseline      18/18 byte-match the implementation-start anchor 8865c54e...
.gitignore vs anchor    exactly 1 insertion(+) — Stage 5 added no ignore rule
push state              origin/main at e178586 (S5-5); S5-6 and S5-7 are local-only, 2 unpushed
commits since anchor    31
```

**Byte-unchanged since `b303d9d` (Stage 4's closing commit):** `pool.py`, `records.py`, `coverage.py`,
`facets.py`, `verify.py`, `classify.py`, `extract.py`, `dedupe.py`, `facetassign.py`, `urlkey.py`,
`schema.py`, every adapter, every file under `schemas/harvest/`, and every file under
`config/harvest/`. Stage 5 changed **no schema and no config**.

**Absent at closure — confirmed:**

```text
absent  state/taxonomy_harvest/   data/harvested/   runs/   LATEST_RUN_ID
absent  src/harvest/migrate/      scripts/harvest/harvest.sh
```

Every byte Stage 5 ever wrote went to an injected temp root. **No live request was made at any point
in Stage 5**, no target page was fetched, no production `state/` write occurred, and nothing was
promoted. The `.gitignore` line `/state/taxonomy_harvest/` was committed at Stage 0 and covers the
runtime namespace when a real run is eventually authorized.

## 5 · What Stage 5 deliberately did not do

Each of the following is **unimplemented and unapproved**, and none is a defect:

- **Stage 6 target fetching.** No target page was fetched, so every record carries
  `access_status: "not_checked"` and `verification_status: "unverified"`. The target-fetch
  coordinator, target-page fixtures, per-child robots, `adapter_mode="record"`, body parsing,
  `content_hash` and alias adjudication all remain Stage 6.
  `designated_target_fetch_owner_lane_id` and `designated_extraction_owner_lane_id` stay null, which
  is their committed meaning.
- **Live requests.** Every run used `fixtures.FixtureOpener`; a test asserts no socket is opened.
- **Publication of verified records.** `publication_eligible` is **derived** and is honestly `false`
  for every Stage 5 run, because `target_fetch_owners` is 0. Nothing was promoted into
  `data/harvested/`; no publication manifest, promotion journal, staging or rollback tree exists.
- **Concurrency, and CF-1.** Cells run **sequentially by design**, so `pool.add_candidate`,
  `acquire_target_fetch` and `acquire_extraction` keep their zero concurrent callers and the unlocked
  check-then-set paths stay harmless. Static scans of `run_cells.py` and `artifacts.py` fail on
  `threading`, `multiprocessing`, `asyncio`, `async def`, `await`, `Lock(` or `Semaphore(`.
  **CF-1 remains deferred and uncorrected.**
- **`sitemap` and `model_search` adapters** — Stage 6 / Stage 9. **Legacy AX corpus migration** —
  Stage 7. **`validate_task.sh` wiring** — Stage 8 (CF-4). **Threshold calibration** — Stage 9; no
  threshold, weight, half-life or the `0.68 / 0.32` split was revisited, and the manifest merely
  *records* the thresholds used so Stage 9 can compare against a real run.

## 6 · Carried-forward findings

Retained as they stand. None was redesigned by Stage 5.

- **CF-1 — pool concurrency. Deferred, and now guarded.** Any later change that runs cells
  concurrently must fix CF-1 **first, in its own checkpoint, before the concurrency lands.** Two
  things that checkpoint must revisit: the sequential cell loop, and S5-7's write journal — a
  module-level handle in `artifacts.py`, because every writer funnels through `write_atomic` and
  `ledger.py`'s two writers could not take a parameter. It **refuses to nest**, so two overlapping
  runs in one process raise rather than cross-attributing their temp files.
- **CF-2 / CF-7 — rejection vocabulary. Measured, non-blocking, still carried as fidelity
  questions.** `verify.decide` emits exactly six reasons and all six are storable in
  `rejection.v1.json`; the five record-only `not_a_case_*` / `keyword_only_match` values are
  unreachable from Stage 5's automated gate. S5-6 met the same gap from the other side — the
  manifest's `zero_result_reason` enum has no `off_topic` and no composite value — and translated it
  in exactly one place (`run_cells.ZERO_RESULT_FOR_REJECTION`) rather than widening a schema. The
  precise reason and number survive verbatim in the cell's rejection log. Both mappings are pinned by
  enumerating verify's reasons from its **AST**, so a seventh reason fails a test rather than a live
  write.
- **CF-11 — `industry.secondary` stays empty by design, and is protected.** The committed definition
  means deployment context, never corporate portfolio, and lexical evidence cannot make that
  judgement. Six assertions prove the coverage report never reports an empty `secondary` as a gap,
  and one proves the counter is *live* — so the decision stays visible rather than decaying into a
  broken counter.
- **CF-3** (no target fixtures) → Stage 6 · **CF-4** (`validate_task.sh` wiring) → Stage 8 ·
  **CF-5 / CF-8** (keyword-list tuning, unmatchable terms) → the relevance-tuning stage · **CF-6**
  (config-editing checkpoints cannot pass the full gate pre-commit) → Stage 8 · **CF-9** (source tiers
  from `role`) → the relevance-tuning stage.
- **Discharged by Stage 5:** the coverage-reporting wiring item carried from S4-5B, closed by S5-4,
  which drives `coverage.py` and `facets.count_states` / `reporting_state` **unmodified**. **D2** —
  the classification-evidence narrowing — got one home in S5-2 rather than being re-derived per call
  site.
- **S4-4 live-corpus calibration** stays provisionally approved and untouched. Calibration is Stage 9.

## 7 · Successor

**Stage 6 is not open.** `STAGE_5_IMPLEMENTATION_PLAN.md` §10 lists ten conditions; conditions 1–9
are met at this commit and recorded above. **Condition 10 — explicit approval — is not given, and
green tests alone do not open Stage 6.** No Stage 6 planning document exists.

**Exact starting point for the successor**

```text
start commit    bc920b5b8b57907165b7a5f8d47239383b974212  (this handoff's closing commit)
anchor          8865c54e2cc8d879410576f247baac4aea149f34  (protected baseline measured here)
assertions      1,324 across 30 suites, all green
push state      origin/main at e178586; S5-6 and S5-7 unpushed
```

**Constraints the successor inherits.** The 18 protected files and the 508 pre-existing untracked
paths stay byte-identical; `.gitignore` stays at exactly `1 insertion(+)` against the anchor.
`pool.py`, `records.py`, `coverage.py` and `facets.py` remain byte-unchanged unless a checkpoint
explicitly authorizes otherwise. A vocabulary file and `facets.generated.v1.json` are **one atomic
contract** — the schema pins the vocabulary's SHA-256, so any vocabulary edit must regenerate the
schema mechanically in the same commit, never by hand. Any checkpoint that edits `config/` inherits
the CF-6 procedure. Every artifact is serialized by the single S5-1 function and written by the single
S5-1 atomic writer; adding a second serialization or a second writer is how byte-determinism dies.
`LATEST_RUN_ID` is written last, or not at all. A boundary test asserts facts about the surface of the
module under test — never which files exist yet, never how the working tree compares to HEAD.

**One structural note for Stage 6.** Target fetching is the first thing that will make
`target_fetch_owners` non-zero, and therefore the first thing that can make a run
`publication_eligible`. The derivation already exists and is proved live in both directions; Stage 6
supplies the fact, not the judgement.
