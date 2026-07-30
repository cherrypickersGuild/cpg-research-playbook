# Taxonomy harvest — task checklist

Updated as each item is completed **and tested**. An item is only ticked when its narrowest test
passes; "written" is not "done".

```text
verified_code_checkpoint:    68b6c2628aca36187aab37a4b8c08e401820d261   Stage 3 implementation
documentation_approval:      79389e1460a13492fcdc42ab8c96af5313ad9bca   approved plan
approved_facet_design:       3b85a8102fb89ae0585ef0fc080f518238e4c1bc
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e
stage_2_5_implementation:    46ab67cde36acf4b2b403d17d4bc589eff3d5cb7
stage_4_closing_commit:      b303d9db1e7433a740960bfbaaf83e82acfd8433   S4-5B
stage_4_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md
stage_5_closing_commit:      bc920b5b8b57907165b7a5f8d47239383b974212   S5-7
stage_5_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  origin/main at e178586 (S5-5); S5-6 and S5-7 local-only, 2 unpushed
assertions:                  1,324 across 30 suites, all green
                             (940 at Stage 4 close + 33 S5-1 + 44 S5-2 + 46 S5-3
                              + 43 S5-4 + 52 S5-5 + 90 S5-6 + 76 S5-7)
untracked_baseline:          508 files, byte-identical; drift 0
```

**STAGE 4 IS CLOSED** as of 2026-07-30 — see
`docs/harvest/handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` for the commit chain, closure
validation, repository state and successor constraints. `STAGE_4_IMPLEMENTATION_PLAN.md` reads
`COMPLETED — STAGE 4 CLOSED`; its §12 records the documentation-only closeout.

---

## Stage 5 — artifact persistence

**Plan of record:** `docs/harvest/STAGE_5_IMPLEMENTATION_PLAN.md` — **`COMPLETED — STAGE 5 CLOSED`**
(2026-07-30).

**STAGE 5 IS CLOSED** as of 2026-07-30 at `bc920b5b8b57907165b7a5f8d47239383b974212` — see
`docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md` for the commit chain, the S5-7
recovery and re-run contracts, closure validation, repository state and successor constraints.

**A completed stage authorizes nothing in the next one.** All eight checkpoints S5-1 … S5-C were
approved separately **by name**. **Stage 6 is not open**: its target fetching, live requests,
publication of verified records, concurrency and the CF-1 correction all remain **unimplemented and
unapproved**, and green tests alone do not open it (plan §10 condition 10, §12).

Stage 5 turns the completed in-memory Stage 4 pipeline into a deterministic, atomic, idempotent
artifact tree under `state/taxonomy_harvest/`. It adds no new judgement: no classification, scoring,
faceting or identity is re-derived. **Non-goals:** live requests and target fetching (Stage 6),
migration (Stage 7), promotion into `data/harvested/`, `validate_task.sh` wiring (Stage 8),
threshold calibration (Stage 9), and concurrent cell execution.

- [x] **S5-1** deterministic atomic artifact writer — `src/harvest/artifacts.py`: `serialize()` ·
      `write_atomic()` · `write_document()` · `run_id()` · `run_dir()` · `ArtifactError`. One
      serialization (`sort_keys`, UTF-8, LF, one trailing newline) so bytes follow content, not dict
      insertion order. Writes go to `.tmp_<uuid4hex>_<basename>` **beside the destination** —
      `os.replace` is only atomic within one filesystem — then fsync and rename, so a reader sees
      the old complete artifact or the new one, never a partial. Cleanup catches `BaseException`,
      so an interrupt leaks no temp file. `write_document` validates against the committed schema
      **before** serializing: an invalid document writes nothing at all. No locking, no concurrency,
      no network, no artifact semantics. **34 assertions**, `tests/test_taxonomy_artifacts.sh`
- [x] **S5-2** cell and topic artifacts — `build_cell_artifact()` · `build_topic_artifact()` ·
      `write_cell_artifact()` · `write_topic_artifact()` · `cell_artifact_path()` ·
      `topic_artifact_path()` · `project_classification_evidence()`, all in `artifacts.py` on top of
      the S5-1 writer. Records sorted by the committed `records.sort_key`; five shuffles give one
      hash. **Counts are derived and a caller may not supply one** — `metadata` carries only
      `sources` and the optional `rejected`, so a count can never disagree with the records beside
      it. A `cross_reference` is counted separately and never enters `by_category`, which counts
      **full records only** and therefore sums to `full_records`. Records are validated against
      `record.v1.json` **before** assembly, so a bad record is refused by `record_id` rather than
      swallowed. The topic artifact merges its cells, sorts, **then** deduplicates by `record_id`
      (that order matters: deduplicating first made the survivor depend on cell order — found and
      fixed by its own test). D2 has one home in `project_classification_evidence`.
      **45 assertions**, `tests/test_taxonomy_cell_artifact.sh`
- [x] **S5-3** rejection log and ledger — `src/harvest/ledger.py`: `build_rejection_log()` ·
      `write_rejection_log()` · `empty_ledger()` · `load_ledger()` · `merge_ledger()` ·
      `write_ledger()` · `LedgerError`. `artifacts.py` gained only the two **cross-run, cell-owned**
      paths (`ledgers/<cell_id>.json`, `rejections/<cell_id>.json` — deliberately *not* under
      `runs/<run_id>/`, since the ledger is what one run knows that the next should not have to
      rediscover). Bytes reach disk only through the S5-1 writer.
      **`first_seen_at` is written once**: a re-merge advances `last_seen_at`/`seen_count` and
      nothing else. A terminal outcome is **final** — a contradictory terminal→terminal change
      raises, and a later `pending` sighting never un-decides a decided URL. A `rejected` entry is
      retained on purpose, or every run re-fetches and re-rejects it. A corrupt, invalid or foreign
      ledger **raises**: treating it as empty would silently re-harvest the whole cell.
      **CF-2 is pinned** — the test enumerates reasons from `verify.decide`'s AST (exactly six) and
      proves all six are storable, so a seventh fails the test rather than a live write.
      `build_rejection_log` takes `(extracted, verdict)` pairs, since a `Verdict` carries no
      identity. **46 assertions**, `tests/test_taxonomy_ledger.sh`
- [x] **S5-4** coverage report — `coverage_report_path()` · `build_coverage_report()` ·
      `write_coverage_report()` in `artifacts.py`. **Wiring, not new coverage logic:** `coverage.py`
      and `facets.py` are **byte-unchanged**, asserted in-suite with `git diff --exit-code`. The
      delegate adds only persistence concerns — it sorts by the committed `records.sort_key` first
      (the committed builder sorts `by_category` but projects per-record rows in *input* order, so
      shuffled input produced different bytes), and validates records against `record.v1.json` before
      counting. `thresholds_constant` is **reported, never derived**: no S4-4 threshold is
      recalibrated. The five states agree with `facets.count_states` and sum exactly to
      `applicable_full_records`; `not_enriched` stays distinct from `unresolved`;
      `unmapped_legacy_value` outranks `facet_partial`; a `cross_reference` is excluded from every
      count and from the records projection. **CF-11 protected by six assertions** — the word
      `secondary` appears nowhere in the serialized report, an empty `secondary` changes no count and
      withholds no record, and one test proves the counter is *live* so the design decision stays
      visible rather than decaying into a broken counter.
      **This discharges the carried-forward coverage reporting wiring item.**
      **43 assertions**, `tests/test_taxonomy_coverage_report.sh`
- [x] **S5-5** run manifest and `LATEST_RUN_ID` — `run_manifest_path()` · `latest_run_id_path()` ·
      `configured_cell_rows()` · `policy_thresholds()` · `environment_block()` ·
      `derive_publication_eligibility()` · `build_run_manifest()` · `write_run_manifest()` ·
      `read_latest_run_id()` · `write_latest_run_id()` · `publish_run()`, all in `artifacts.py`.
      12 configured cells → **12 unique rows** sorted by `cell_id`; an unreached cell is `not_run`
      and one that found nothing is `zero_result` with a committed reason — neither is omitted, so a
      silently skipped cell cannot hide. `topic_slug`/`category_slug` are stamped from the
      configuration, never trusted from the caller.
      **`publication_eligible` is derived, not a parameter** (a test asserts it is absent from the
      signature): a Stage 5 run is honestly ineligible because no target page was fetched, and the
      derivation is proved *live* — a verified run with healthy cells is eligible, a failed cell or a
      non-`harvest` mode is not. Thresholds are **recorded from `policy.v1.json`, never
      recalibrated**.
      **The pointer moves last, or not at all.** `publish_run` writes the manifest then advances
      `LATEST_RUN_ID`; an unfinished run, a mismatched `harvest_run_id`, and a re-publish of a
      finished run are all refused. An invalid manifest, a crashed write and a `KeyboardInterrupt`
      each left the *previous* pointer intact with no debris. The pointer is one line, one trailing
      newline, no CRLF. **52 assertions**, `tests/test_taxonomy_manifest.sh`
- [x] **S5-6** the cell driver — `src/harvest/run_cells.py`: `run()` · `configured_cells()` ·
      `RunResult` · `CellRun` · `RunCellsError` · `MAX_CELLS`. The checkpoint that makes Stage 5 a
      *stage* rather than a library: the committed Stage 4 pipeline is driven over the fixture
      corpus, cell by cell, and one run's artifacts land on disk. **No other file was modified**, and
      the eleven modules it composes (`pool`, `records`, `coverage`, `facets`, `verify`, `classify`,
      `extract`, `dedupe`, `facetassign`, `artifacts`, `ledger`) are asserted **byte-unchanged
      against HEAD inside the suite** — if composition had required editing one of them, it was not
      composition.
      One run emits **42 files** (12 cell artifacts · 3 topic artifacts · 12 rejection logs ·
      12 ledgers · coverage · manifest · `LATEST_RUN_ID`); the file set is asserted **exactly**, so
      an extra path fails as loudly as a missing one, and all 42 validate. Two runs with a pinned
      clock hash identically, and so does a run with its 12 cells **shuffled**.
      **11 zero-result cells and one `ok` cell (4 records) is a real finding about the corpus, not a
      harness failure** — every zero cell reports `all_below_relevance_threshold`, which is what the
      committed relevance lists actually say about these items. The bar was not lowered.
      **One translation exists, and only one:** `verify.decide`'s six reasons onto the manifest's
      five-value `zero_result_reason` enum, dominant-by-count with ties broken by a committed
      precedence list, enumerated from verify's **AST** so a seventh reason fails the test rather
      than a live cell. A cell whose source fixture is deleted reports `adapter_error`, still gets a
      complete valid artifact, and leaves the other eleven cells, the manifest and the pointer
      untouched. **0 target-fetch owners → the run is honestly ineligible for publication**, derived.
      **CF-1 stays untriggered and is now guarded by a static scan**, not merely intended.
      **91 assertions**, `tests/test_taxonomy_run_cells.sh`
- [x] **S5-7** recovery and re-run semantics — `artifacts.py` gained `WriteJournal` ·
      `write_journal()` · `run_is_finished()` · `verify_latest_run_id()`; `run_cells.py` gained an
      up-front repeat refusal and wrapped its whole write phase in the journal. No signature changed,
      no schema changed, and the nine Stage 4 modules stayed byte-unchanged.
      **Interruption was measured, not reasoned about** — `os.replace`, `os.unlink` and the pointer
      write were each actually broken. A run interrupted two artifacts in: both files that landed
      validate, the interrupted run has **no manifest**, there is **no temp debris**, the pointer
      still names run 1, and **the cross-run ledger was not half-updated** (`seen_count` still 1).
      A `KeyboardInterrupt` behaves identically. A run dying between manifest and pointer leaves a
      complete orphaned manifest and the previous pointer — the safe direction — and is then
      **refused if repeated rather than resumed**; no resume policy was invented.
      **The repeat refusal moved to the front**, which is its whole point: `publish_run` refused a
      finished `run_id` only at the end, by which time the ledger had double-counted and the
      rejection log had been replaced. A refused repeat now leaves the tree **hash-identical**.
      **The sweeper proves ownership** — it removes only temp paths it watched being created, leaves
      a foreign `.tmp_*` strictly alone (globbing and deleting would destroy another writer's
      in-flight file), refuses to unlink any name without the temp prefix, never raises, and is
      idempotent. A clean run sweeps nothing and says so.
      **Two consecutive runs differ in exactly four clock-derived fields** — `harvest_run_id`,
      `generated_at`, `discovered_at`, `freshness_score` — **enumerated by a recursive JSON diff, not
      normalized away**, so a fifth moving field fails instead of passing silently. Every identity,
      classification, metadata count and the other three scores are reproduced exactly: **a re-run
      does not re-judge.** Freshness is asserted to have *decayed*, so the field cannot silently
      freeze.
      **`ledgers/` merge; `rejections/` are replaced per cell and cannot merge** — `rejection.v1.json`
      is `additionalProperties: false` with one `harvest_run_id` and run-less entries, so a merged log
      could not name the run that produced its rows. The guarantee that matters is asserted instead:
      **a run never clobbers a cell it did not run.**
      **Writing this suite found a defect in S5-6's own test scaffolding**: the interruption injection
      counted every `os.replace`, and HttpClient writes domain leases atomically, so the budget was
      spent on lease files and the run died before writing any artifact — the partial-tree tests
      passed while proving nothing. Now scoped to renames under the artifact root, with an assertion
      that the interruption really was part-way through.
      **76 assertions**, `tests/test_taxonomy_recovery.sh`
- [x] **S5-C** Stage 5 closeout, documentation only —
      `docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md` plus the plan's status header
      and this file. Exactly the three paths **declared up front** before Stage 5 wrote a line of
      code, so the authorization gap hit at Stage 4 closeout **did not recur**: writing the handoff
      needed no separate path-set approval. L0 validation only — exact three-path diff,
      `git diff --check`, nothing touched under `src/`, `tests/`, `scripts/`, `config/`, `schemas/`,
      `state/`, `data/` or any run artifact, protected baseline and the 508-file untracked baseline
      unchanged. Per its own risk tier the focused suites and the full gate were **not** rerun for a
      documentation-only change. Records the user's ratification of S5-7's inclusion of
      `tests/harvest/test_run_cells.py` for its two corrective test changes, with the S5-7
      implementation commit left unrewritten.

**Carried-forward findings reconciled during Stage 5 planning** (detail in §9 of that plan):

- **CF-1 stays deferred, and is now guarded.** It was recorded against "Stage 5"; Stage 5 runs cells
  **sequentially**, so the unlocked pool paths keep zero concurrent callers. S5-6 shipped that way and
  a static scan of `run_cells.py` — extended to `artifacts.py` by S5-7 — fails on any concurrency
  primitive. S5-7's write journal is the second thing a concurrency checkpoint must revisit: it is a
  module-level handle (every writer funnels through `write_atomic`, and `ledger.py`'s two could not
  take a parameter) and it **refuses to nest** rather than cross-attributing two runs' temp files.
  Any later change that runs cells concurrently must fix CF-1 **first**, in its own checkpoint.
- **CF-2 / CF-7 are measured and non-blocking.** `verify.decide` can emit exactly six rejection
  reasons and **all six are already storable** in `rejection.v1.json`; the five record-only
  `not_a_case_*` / `keyword_only_match` values are unreachable from Stage 5's automated gate. No
  schema change is required. S5-6 met the same gap from the other side — the manifest's
  `zero_result_reason` enum has no `off_topic` and no composite value — and translated it in exactly
  one place rather than widening a schema; the precise reason and number still survive verbatim in
  the cell's rejection log. Both remain carried forward as fidelity questions.
- **CF-11 unchanged and protected.** S5-4 must prove an empty `industry.secondary` is not reported
  as a coverage gap, so the report cannot create pressure to manufacture the findings CF-11 exists
  to prevent.
- **S4-4 calibration untouched.** No threshold or weight is revisited; the run manifest merely
  records the thresholds used so Stage 9 can compare. Calibration stays Stage 9.
- **D2 gets one home.** The `{signal, matched}` projection is implemented once in S5-2 rather than
  re-derived per call site.

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
- [x] **S4-5B** in-memory record construction and schema validation. The pipeline's output
      (dedupe → extract → classify → verify → facetassign) is handed to the **unmodified**
      `records.make_full_record` / `make_cross_reference` and validated against `record.v1.json`
      in memory. **No production module was added** — `records.py` already accepts `case_facets`,
      so S4-5B is test-only. Both schema conditionals are proved from the schema's own behaviour:
      a `cases__domain-applications` full record without facets is **refused**, and a
      `research-and-models` / `discourse` full record **with** them is refused (absent or explicit
      null both accepted). A `cases__domain-applications` **cross_reference** row stays satisfiable
      — the conditionals sit inside the full-record branch precisely so one of the twelve cells is
      not made impossible. `cross_reference` refuses `title`, `summary`, `relevance_score`,
      `classification` and `case_facets`. Facets are inert for identity: `record_id`, `content_id`,
      `identity_url`, `cell_id` and `canonical_url` are byte-identical with and without a payload,
      and `urlkey.py` contains no facet reference. Order is `(topic, primary_category, record_id)`;
      shuffled input yields a byte-identical artifact over 5 shuffles. Nothing is written.
      **51 assertions**, `tests/test_taxonomy_records.sh`

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

**S4-5B gate:** 940 assertions across 23 suites, all green (889 prior + 51 S4-5B). All prior
assertions unchanged and unmodified — S4-5B is purely additive, touching no existing test. All five
checkers exit 0; the 508 pre-existing untracked files byte-identical; `.gitignore` still exactly
`1 insertion(+)`. `records.py`, `facetassign.py`, `facets.py`, `verify.py`, `classify.py`,
`extract.py`, `dedupe.py`, `pool.py`, every schema and every config file are byte-unchanged.

**S4-5B divergence D1 — DISCHARGED by the Stage 4 closeout.** The plan's S4-5B API line was stale:
it stated `facetassign.assign(extracted, *, facets_dir=None) -> case_facets | None`, whereas the
**committed** S4-5A contract is `assign(extracted, classification, *, facets_dir=None) ->
FacetAssignment`. S4-5B used the committed signature and left `facetassign.py` byte-unchanged;
following the stale line would have broken S4-5A for wording written before S4-5A was carved out of
S4-5B. `STAGE_4_IMPLEMENTATION_PLAN.md` was not in S4-5B's allowed paths, so the correction waited
for the closeout, which had it in scope. **The plan now carries the committed contract**, records
that record construction passes `FacetAssignment.case_facets` to the existing builder, and records
that no production change was required. No further action.

**S4-5B finding D2 — the record schema deliberately narrows classification evidence.**
`classify.Evidence` carries `{signal, matched, field}`, but `record.v1.json`'s
`classification.evidence` items are `{signal, matched}` with `additionalProperties: false`. A
builder that forwards the dataclass wholesale is refused by the schema. Record construction
therefore projects the two admitted keys, and a test pins both the narrowing and the refusal.

**Carried forward from S4-5B (→ Stage 5): coverage reporting wiring — DISCHARGED by S5-4.**
`coverage.py` and `facets.count_states` / `reporting_state` are now driven from a built record set and
persisted as `coverage_report.v1.json`, with both modules byte-unchanged. No further action.

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

**Plan of record for target fetching:** `docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md` —
**`APPROVED AS THE PLAN OF RECORD — CHECKPOINT-BY-CHECKPOINT · NO CHECKPOINT APPROVED`**
(2026-07-30). It scopes Stage 6 to **target fetching and verification only**; the `refresh` /
`linkcheck` / `promote` / `diff` / `compare-runs` subcommands, the transaction journal and the
promotion tests listed under this heading stay **unscheduled, unapproved and untouched** (plan §14
erratum E11). Checkpoint sequence
**S6-0 · S6-1 · S6-2 · S6-3 · S6-4 · S6-5 · S6-6 · S6-7 · S6-L · S6-C**, each requiring its own
separate approval **by name**; S6-C's handoff path and allowed paths are declared in advance in
plan §11. **S6-L (bounded live smoke) is the only checkpoint that makes a network request** and needs
approval twice — once as a checkpoint and once immediately before it runs.

**Four things this heading deliberately keeps apart:**

1. **The plan is approved as the plan of record**, checkpoint-by-checkpoint (plan §15). What Stage 6
   *is*, and the order it will be built in, are settled.
2. **D6-A and D6-B are RESOLVED** (plan §12), both as recommended. A resolved decision fixes the
   *shape* of a future change and authorizes nothing else.
3. **S6-1 through S6-C are unapproved and unimplemented.** No production module, test, schema,
   script, config or fixture exists for Stage 6, and none may be written until its own checkpoint is
   approved by name. Approving the plan approved **not even S6-1**.
4. **Live network access is not authorized.** No Stage 6 request has been made and none may be; every
   checkpoint S6-1 … S6-7 is fixture-backed with a no-socket assertion, and S6-L is the single
   separately approved exception, still pending both of its approvals.

- [x] **S6-0** Stage 6 plan and decision record, documentation only —
      `docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md` plus this registration. Two commits: the plan
      (`docs(harvest): plan stage 6`) and the resolutions
      (`docs(harvest): resolve stage 6 design decisions`). CF-1 stays deferred and must be fixed in its
      own checkpoint before any concurrency lands (plan §9.1); CF-2/CF-7 are not widened, CF-3 is
      discharged only when S6-1 ships, CF-11 stays protected, D2 keeps one home, and S4-4's provisional
      calibration is untouched (plan §9). New findings CF-13/15/16/17 are carried forward (plan §9.7).
      - **D6-A — RESOLVED** (plan §12.1): one backward-compatible keyword-only `url_aliases=None` on
        `records.make_full_record`, which stays the **sole owner of the persistent record shape** and
        owns the validation, normalization and projection of aliases. Omitting the argument keeps the
        committed empty-list behaviour byte-for-byte. `run_cells.py` **passes** adjudicated aliases and
        never mutates the completed record dict. Authorizes `src/harvest/records.py` in the S6-5
        allowed-path set for that one additive parameter — and nowhere else. **Blocks S6-5 no longer;
        S6-5 remains unapproved.**
      - **D6-B — RESOLVED** (plan §12.2): commit `schemas/harvest/alias_conflict.v1.json` at the exact
        path S6-6 declares. It validates the **complete** `runs/<run_id>/alias_conflicts.json` document
        — directly or through an explicitly committed wrapper — and the artifact is **validated before
        it is written**, through the single S5-1 writer. `alias_conflicts_count` is **derived from the
        validated artifact contents**, never a caller-supplied source of truth. The schema carries **no
        vocabulary hash** and needs no generator run. Authorizes the schema and its owning focused
        tests in the S6-6 allowed-path set — and no unrelated path. **Blocks S6-6 no longer; S6-6
        remains unapproved.**
- [x] **S6-0-C** Stage 6 fixture-scope correction, documentation only
      (`docs(harvest): correct stage 6 fixture scope`). **An S6-1 preflight stopped without editing a
      single file**: plan §11's corpus wording determined no literal, implementable fixture set. The
      mismatch was **corrected in the plan, not by widening S6-1** — the preflight authorized no fixture,
      no path and no improvisation. Recorded as plan erratum **E15** (§14):
      - **Two cases relocated to S6-4.** "One URL surfaced by two sources in one cell" and "one URL
        reachable from two topics" are not properties of a target-page fixture. Measured through the
        committed adapters and `dedupe.group`: **109 candidates, 109 distinct identities, 0 shared across
        sources, 0 shared across topics** — so either case would have needed a source-fixture or
        topic-config edit, neither authorized. S6-4 now proves the Stage 6 ownership fact (one identity →
        one fetch → one outcome on every record owning it) from **test-local synthetic candidate and pool
        inputs**, with **no allowed-path change** and **no reopening of the committed Stage 4 dedupe
        contract**.
      - **Three transport cases removed from Stage 6 outright** — timeout, `500 → 200` retry sequencing,
        and over-cap body generation. Retry, timeout and response-size enforcement stay owned by the
        committed `HttpClient`; `targetfetch.py` consumes only the injected client's final response or
        typed error; S6-2 raises existing typed errors from a stub client. **No fixture directive DSL**
        (`raise`, `responses`, generated oversized bodies or equivalent) may be added, and no existing
        retry or body-cap test is duplicated. The `500 → 200` assertion is **removed, not relocated**.
      - **The corpus is now two literal tables** — 24 target fixtures and 2 new robots fixtures, each
        with its exact URL, status, contract purpose and robots host. **Only the tables authorize a
        fixture file; the directory globs no longer do.**
      - **D6-A and D6-B remain RESOLVED and unchanged**, as does every other approved Stage 6 decision.
- [x] **S6-1** target-page fixtures, the loader and the checker — `4df5380`
      (`test(harvest): add target fixture corpus`). Discharges **CF-3**. 24 literal target fixtures and
      2 new robots fixtures under `tgt.harvest.test` / `tgt-robots-denied.harvest.test`;
      `fixtures.load_target_fixtures()` and `FixtureOpener(targets=…)` sharing **one** exact-URL index
      with a collision that names both claimants; `check_fixtures.py` treating `TARGET_FIXTURE_IDS` as a
      declared set checked in both directions and refusing any transport-simulation key, importing that
      forbidden-key set from `fixtures.py` rather than re-listing it. `targets=None` means **no** targets,
      so every committed caller is byte-identically unaffected. **70 assertions.**
- [x] **S6-2** the injected target-fetch adapter and the error mapping — `e4a12b9`
      (`feat(harvest): add target fetch outcomes`). `targetfetch.py`: `TargetFetchOutcome` ·
      `fetch_target()` · `ACCESS_STATUS_FOR_ERROR` · `TargetFetchError`. Exactly one logical client call;
      injected client, budget and clock; no system clock; retries, robots, redirects, timeouts and the
      body cap all left to the committed `HttpClient`, whose final response or final typed error is the
      only thing consumed. All ten committed `HttpError` classes mapped, enumerated from the AST and each
      one instantiated and exercised; an unmapped subclass raises rather than receiving the nearest
      plausible status. **61 assertions.**
      - **Defect found by its own test:** a uniform MRO walk let the `HttpError` base entry answer for
        every subclass, silently defeating the fail-loud contract. Fixed with `EXACT_MATCH_ONLY`, so the
        base class answers only for itself while genuine subclass inheritance still works.
- [x] **S6-2-C** canonical-domain authority correction, plan + one fixture
      (`fix(harvest): align canonical domain policy`). **An S6-3 preflight stopped without editing a
      file.** The blocker was a three-way contradiction: plan §4 said same-domain trust was "identical
      host", `tgt_canonical_cross_host.json`'s `contract_intent` claimed a cross-domain conflict, and the
      committed `urlkey.registrable_host` maps both `tgt.harvest.test` and `tgt-alt.harvest.test` to
      `harvest.test` — so the two rules returned **opposite verdicts** on the one fixture built to prove
      that row. Corrected to make **`urlkey.registrable_host` the single committed authority** (plan
      erratum **E16**): §4 now reads "same / different registrable domain" with exact hostname equality a
      subset of it; **CF-15's premise is corrected** and narrowed to the resulting boundary; the fixture's
      canonical target is now `https://other-target.test/elsewhere`, a genuinely different registrable
      domain, with only its own `MANIFEST.json` entry regenerated. No second host comparison, no
      public-suffix implementation, no change to `registrable_host`, and Stage 1's URL-identity design is
      not reopened. The same-domain branch is allocated to a **test-local synthetic** S6-3 case with an
      anti-vacuity assertion, not to a new fixture.
- [x] **S6-3** redirect and `rel=canonical` adjudication — `39b709b`
      (`feat(harvest): add alias adjudication`). `aliases.py`: `adjudicate()` ·
      `extract_rel_canonical()` · `AliasConflict` · `AliasError` · `CANONICAL_SCAN_BYTES` ·
      `load_canonicalization()`. Both public functions pure relative to explicit inputs; the cached
      loader is the one impure function and sits outside them, on the `verify.load_policy` idiom.
      `urlkey.registrable_host` is the sole host authority. Permanence read from the S6-2 outcome's
      flag, never inferred from a hop count. `identity_url` compared but never returned;
      `record_id`/`content_id` unreachable, proved with test-local sentinels across all eight row
      shapes. Robots arrives as an injected verdict — `False` **and** unknown both decline.
      **81 assertions.**
      - **Committed under a one-time gate-failure exception.** The single full-gate run was **red**:
        32/33 suites green, sole failure `domain_throttle` with a worker `LeaseTimeout` — a **third**
        signature, not either previously characterized one. The isolated diagnostic was green but did
        **not** replace the full-gate result. **Not an accepted permanent flaky signature.**
- [x] **S6-T** attempted throttle diagnosis — **no reproducible production defect found**, and **no
      file changed**. Measured: the faithful process-based reproduction is green (12/12 acquired, 0
      timeouts, no orphaned slot, 3 runs); the backoff-starvation hypothesis is **disproven** (capping
      the poll interval changed nothing); artificial CPU load does not reproduce it; overlap is
      deterministic (2 in 8/8). One reproduction came from a *thread* harness and was **discarded as an
      artifact** — threads share a PID, which changes the ownership and liveness checks. Detail in plan
      §14.1.
- [x] **S6-TD** lease-timeout diagnostics (`test(harvest): add lease timeout diagnostics`).
      **Instrumentation, not a fix — the instability is not fixed and is not claimed to be.** No
      production path changed: `domainlease.py`, `httpclient.py` and
      `tests/test_taxonomy_domain_throttle.sh` are **byte-unchanged**. `throttle_worker.py` emits one
      bounded `LEASE_TIMEOUT_DIAGNOSTIC` JSON record to stderr **on the `LeaseTimeout` path only**, then
      re-raises — same exception, same exit status, same assertions. The record carries the lease tree
      the worker timed out against: per-slot existence, owner text, parsed pid and epoch, mtime, age,
      vanished-during-collection flags, the pace lock, `next_allowed_at` and any collection error.
      Collection is best-effort and never masks the original failure. A deterministic regression holds
      the only slot from the test process and uses a test-only `--wait-max-sec` whose **default stays
      30s**, so it neither waits 30 seconds nor depends on scheduler luck. **The three signatures remain
      unexplained; none is an accepted permanent exception.**
- [x] **S6-4** target-fetch ownership, deduplication and bounds
      (`feat(harvest): add target fetch ownership`). `run_cells.py` gained the fetch phase:
      accepted candidates only, in committed `candidate_key` order; `pool.add_candidate` →
      `pool.acquire_target_fetch` as the ownership gate; one `fetch_target()` per canonical identity with
      the **same outcome object** reused by every owner; a **run-scoped** pool and outcome map, so one
      identity is one fetch across cells *and* topics; per-owner `adjudicate()`;
      `MAX_TARGET_FETCHES_PER_CELL = 25` on top of the committed `cell:` budget, which the whole pipeline
      now shares so fetches charge the same `cell_max_requests` as discovery; budget-skipped targets
      recorded as `not_checked` through the committed S6-2 dataclass with **no client call**. Sequential
      throughout — no thread, process, lock or async — so CF-1 stays untriggered with exactly one caller
      of the unlocked gate. `run()`'s public signature is unchanged. **32 assertions.**
      - **Ordering defect surfaced and corrected.** Ownership alone flipped a run to
        `publication_eligible: true` while every record still said `not_checked`, because
        `target_fetch_owners > 0` was treated as sufficient. **The missing-target-evidence guard was
        brought forward from S6-6 to S6-4** — and only that guard: a run is ineligible whenever any
        **full** accepted record lacks target evidence, a budget-skipped record keeps it ineligible, and
        `cross_reference` rows are excluded from both sides of the count. Still derived, never
        caller-supplied. **S6-6 retains** alias-conflict artifacts and their schema,
        `alias_conflicts_count` reporting, target HTTP-attempt reporting, and the positive
        eligibility-completion proof.
      - **Two temporary Stage 5 progress guards retired**, each having prohibited exactly the semantics
        S6-4 legitimately introduced: `test_recovery.py::test_no_target_fetching_was_introduced` deleted
        entirely (not narrowed, and **not** replaced with a guard against S6-5 — the S5-5/S5-7
        precedent), and the single `target_fetch_owners == 0` assertion removed from
        `test_run_cells.py::test_a_stage_5_run_is_honestly_ineligible_for_publication`, whose
        substantive ineligibility assertions are unchanged and now pass for the right reason. Renaming
        the pool method to dodge the token scan was rejected on the S5-4 precedent.
      - **Robots evidence stays unwired**: `canonical_robots_allowed=None`, so no `canonical_tag` alias
        is adopted and a `canonical_robots_not_verified` conflict is recorded instead. **S6-5 must
        preflight** whether cached robots evidence is available without a new request.
- [x] **S6-5** target evidence on full records (`feat(harvest): add target evidence`).
      `records.py` gained **only** the resolved D6-A parameter: keyword-only `url_aliases=None`, plus
      `normalize_url_aliases()` and `RecordError`. `make_full_record` stays the **sole owner of the
      persistent record shape** — it validates, projects to the four schema-admitted keys (`url_alias` is
      `additionalProperties: false`), deduplicates and orders by `(kind, url)`, and **refuses before the
      record is assembled**. Omission still yields `"url_aliases": []` byte-for-byte, so every committed
      caller is unaffected. `run_cells._full_record` consumes the committed `TargetFetchOutcome` instead
      of the Stage 4 no-enrichment defaults and **passes aliases in** — no completed record dict is
      mutated. The driver's `FixtureOpener` now serves the target corpus; without it every fetch failed as
      `unreachable`, a true statement about a missing fixture and a useless one about the page.
      **47 assertions.**
      - **Difference set measured exactly.** Between a fetch and a no-fetch record, precisely six fields
        move: `access_status`, `http_status`, `verification_status`, `verification_evidence`,
        `content_hash`, `last_checked_at`. Every score, the classification, the facet payload,
        `record_id`, `content_id`, `identity_url`, `cell_id` and `target_url` are byte-identical — a fetch
        supplies facts and re-judges nothing. `updated_at` stays null (CF-17); `verification_status` is
        never `"verified"`; cross-reference rows carry no target evidence at all.
      - **`config.enrich` brought forward from S6-6**, and only that field: derived from whether the
        target-fetch phase was **enabled**, bound once in `run()` and threaded to both the fetch phase and
        `_config_block`, keyword-only and required. Never derived from `publication_eligible` or from how
        many records came back checked. `run()`'s signature is unchanged, so the `false` branch is proved
        at the `_config_block` boundary rather than end-to-end. **S6-6 keeps** `config.bounds`,
        target-attempt reporting, conflict routing, alias-conflict artifacts and the final
        positive/negative eligibility proof.
      - **Six spent progress guards retired**, each false by design once S6-5 landed. Four in
        `test_run_cells.py`: `test_no_target_page_was_fetched` deleted (predeclared at S6-4);
        `src/harvest/records.py` removed from the Stage 4 byte-unchanged tuple (D6-A authorizes it — the
        S5-7 correction repeated); `test_a_stage_5_run_is_honestly_ineligible_for_publication` deleted
        entirely, since its premise is a run that fetched nothing and the positive proof is S6-6's; and
        the single `assertFalse(config["enrich"])` line, the direct consequence of the correction above.
        One in `test_recovery.py`: `"last_checked_at"` added to `CLOCK_DERIVED`, plan §10's predicted
        fifth clock-derived leaf — still **exactly** enumerated at five, so a sixth moving field fails.
        Two in `test_target_ownership.py`: `test_the_run_is_still_honestly_ineligible` and
        `test_the_records_still_say_nobody_checked_them`, S6-4's own guards against S6-5, deleted
        entirely with every ownership, deduplication, budget and synthetic eligibility-predicate test in
        that file preserved. None was replaced with a guard against S6-6.
      - **Robots evidence stays unwired**, and the preflight established why: `RobotsCache.get`,
        `.allowed` and `.crawl_delay` all fall through to `_fetch()` on a miss or expired TTL, so none can
        be called without risking a request, and `self._cache` is private state. No committed
        cached-verdict API exists, so `canonical_robots_allowed=None` stands and every record carries
        `url_aliases: []` with `canonical_url == identity_url`.
      - **Publication eligibility is now honestly `true`** for the integrated fixture run: all four
        predicate clauses hold on real observed evidence (4 owners, four `ok`/`fetched` records with
        distinct content hashes). Per plan §8 and §1.1 goal 4 that is the intended Stage 6 outcome, not a
        premature one — S6-6 owns the *proof in both directions*, not an extra predicate.
- [x] **S6-6** alias-conflict artifact, reporting and the eligibility proof
      (`feat(harvest): add alias conflict reporting`) — **minus target HTTP-attempt reporting, which the
      preflight proved undeliverable in this boundary.** `schemas/harvest/alias_conflict.v1.json` is
      committed (**D6-B, RESOLVED**) and validates the **complete** document, envelope included, so a
      count disagreeing with its own rows cannot be written. `artifacts.py` gained
      `alias_conflicts_path()` · `conflict_id()` · `build_alias_conflicts()` · `write_alias_conflicts()` ·
      `alias_conflicts_count()`; the driver routes conflicts S6-3 already adjudicated, deduplicated
      run-wide by content so two owners of one identity yield one finding. Written through the single S5-1
      atomic writer, **before** the manifest, which then reads the count back from the validated
      document — so artifact and manifest cannot drift. `conflict_id` is a content hash, never positional.
      An empty set still produces the artifact: "found none" must be distinguishable from "nobody
      looked". `config.bounds` now reports every cap the run enforced. **47 assertions.**
      - **§8 eligibility proved in both directions**: true only when all four clauses hold; false for each
        clause failing alone, with the committed priority; derived from run facts only; a
        `cross_reference` row cannot manufacture a missing-evidence finding; and neither the existence nor
        the size of the conflict artifact moves it either way. **No new predicate was added.**
      - **Target request accounting is BLOCKED and no longer S6-6's** (plan §14.4). `pool.accounting()`
        sums source snapshots only, and the committed `TargetFetchOutcome` deliberately carries no
        `FetchAccounting` — so an exact count is unreachable from these paths. **Nothing was estimated and
        no `client.stats` delta was taken.** `http_attempts` keeps its **source-only** meaning and must
        not be newly described as including target attempts. Source and target accounting stay distinct.
      - **A separate accounting checkpoint is required after S6-6 and before S6-7.** It is **not
        approved**, and its exact paths are **not declared**: it needs a read-only ownership/path audit
        first, since the candidate routes touch `targetfetch.py` or the byte-frozen `pool.py`.
        **S6-7 is blocked until the accounting contract is resolved.**
      - **One defect found by its own test**: the `conflict_id` content-derivation test indexed a row by
        position after the rows are sorted, so it was asserting the sort order rather than the id. The
        production hash was correct; the test now selects by `identity_url`.
- [ ] **S6-7, S6-L, S6-C** — **not approved, not implemented.** **S6-7 is blocked** behind the target
      request-accounting checkpoint (plan §14.4), whose own scope needs a read-only ownership audit
      first. **Live network access remains unauthorized** and no Stage 6 request has been made.
      **D6-A and D6-B remain resolved**; D6-B is now delivered.
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
