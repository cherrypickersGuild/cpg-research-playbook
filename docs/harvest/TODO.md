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
stage_6_closing_commit:      7aa1ccec439162d238ad87fd00c3b543ed3e8f55   S6-7
stage_6_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md
stage_6_closeout_commit:     0d2da6454e2ac898094f9b1eebe9a4b6370c79f0   S6-C, PUSHED
stage_7_plan_of_record:      docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md   COMPLETED — STAGE 7 CLOSED
stage_7_closing_commit:      c3d982c572844cf39787b5b2368e975bfb198986   S7-6, closing
                             implementation baseline
stage_7_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md
stage_7_gate:                39/39 suites green — 2,023 unittest + 42 shell = 2,065 total
                             (1,815 at Stage 6 close · +43 S7-1 · +28 S7-2 · +62 S7-3
                              · +42 S7-4 · +49 net S7-5 · +26 S7-6; migration wrapper
                              250 assertions — the only suite Stage 7 added or changed)
stage_7_ax_mapping:          231 accepted / 0 rejected, in memory only — nothing written.
                             Facet states 112 facet_partial · 118 unmapped_legacy_value
                             · 1 unresolved
stage_7_cli:                 scripts/harvest/migrate.sh — ax-cases (dry-run by default,
                             --apply publishes one bundle under --state-root) and
                             entity-assess.
stage_7_apply:               works, and is exercised ONLY under injected temporary
                             roots. NO migration runtime bundle is retained:
                             state/taxonomy_harvest/ does not exist. An operational
                             default-root apply needs separate human approval.
stage_8_plan_of_record:      docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md   COMPLETED —
                             STAGE 8 CLOSED
stage_8_state:               CLOSED AND PUBLISHED. All four checkpoints approved by name and
                             complete: S8-0 (plan of record), S8-1 (harness wiring), S8-2
                             (full offline regression, verification-only, NO COMMIT) and
                             S8-C (closeout). Published tip bf067303a01fa80d1421f9eef7030cbadf805733.
stage_8_0_commit:            0657db8a65e311ea0f20b43a2fbf2c0e811d5ee5   docs(harvest): plan
                             stage 8 harness wiring — 2 documentation paths
stage_8_1_commit:            01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c   feat(harvest): wire
                             taxonomy into validation harness — 3 paths
stage_8_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md
stage_8_2_regression:        bash scripts/validate_task.sh --all — ONE invocation, exit 0 in
                             736 s, final line "== validate_task.sh: PASS ==". 58/58 wrappers
                             each exactly once (legacy 19/19 + taxonomy 39/39); ZERO
                             "WARN - skipping"; matrix "64 passed, 0 failed"; parallel
                             "62 passed, 0 failed"; no "FAIL - offline" and no FAIL line of
                             any kind; no runtime-leak and no production-state-change
                             diagnostic. No separate taxonomy loop was run — after S8-1
                             --all contains all 39 taxonomy wrappers exactly once, so the
                             loop would only duplicate them. S8-2 made no commit and edited
                             nothing. The external log lived outside the repository and was
                             deleted after verification; no log artifact is retained here.
cf_4_state:                  CLOSED by the S8-2 regression. scripts/validate_task.sh --all
                             now exercises the entire taxonomy wrapper set and passes
                             offline with zero skips. No other carried-forward item is
                             closed by Stage 8.
stage_8_1_harness:           scripts/validate_task.sh — ISOLATED[] 19 -> 58 entries (all 39
                             taxonomy wrappers individually, the 19 legacy entries verbatim
                             as a prefix); 50 additive taxonomy case arms / 91 add_test calls
                             routing all 39 wrappers, with the 19 legacy arms byte-identical
                             to b9a08a3; RUNTIME_PATHS `[ -e ]` check before AND after the
                             run for state/taxonomy_harvest, data/harvested, runs and
                             LATEST_RUN_ID, which never deletes what it finds. No test file
                             changed; no timeout, version gate, summary counter,
                             argument-parser change or concurrency added.
stage_8_1_validation:        focused only — bash -n; a 39-check static inventory/semantics/
                             containment proof; 5 explicit-mode routing samples (one per
                             routing shape) plus the protected-baseline arm, each rc 0 with
                             zero WARN skips and the expected wrapper set exactly once; and
                             an omission proof that the two unmapped paths route to zero
                             wrappers. domain_throttle deliberately not exercised. The full
                             taxonomy gate and --all were NOT run at S8-1; --all was run
                             once at S8-2, where domain_throttle passed. That is one
                             observation, not a resolution: an intermittent domain-throttle
                             signature stays an unresolved diagnostic, never an accepted
                             permanent flake.
stage_7_entity_assessment:   docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md   generated,
                             read-only; 1,161 entities assessed, 0 migrated
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  SYNCHRONIZED. HEAD = local main = local origin/main =
                             bf067303a01fa80d1421f9eef7030cbadf805733, 0 behind / 0 ahead.
                             Stage 7 implementation and closeout through
                             e5dc558234727ea58ffeea269b7d52d6f65a603a were published to
                             origin/main on 2026-07-31 by safe_push_main.sh --execute as a
                             fast-forward from 0d2da64; all three Stage 8 commits (S8-0,
                             S8-1, S8-C) were published on top of that on the same day, and
                             bf067303 is the published Stage 8 tip. This records the state
                             at the 2026-07-31 roadmap checkpoint, not the live status of
                             any later commit; verify refs with local refs before new work.
                             Every future push still needs its own explicit approval, via
                             safe_push_main.sh --check then a separately approved --execute.
gate_after_stage_8:          `bash scripts/validate_task.sh --all` is now the closing gate
                             and CONTAINS the taxonomy gate: 58 wrappers (19 legacy + 39
                             taxonomy), each exactly once, zero skips. The standalone loop
                             `for t in tests/test_taxonomy_*.sh; do bash "$t"; done` remains
                             documented for taxonomy-focused development only; running it
                             alongside --all only duplicates the same 39 wrappers.
assertions:                  see stage_7_gate above for the current figure — Stage 8 added
                             no suite and no assertion; it wired the existing 39 into the
                             harness. At the Stage 6
                             close this line read 38/38 suites — 1,773 unittest + 42 shell
                             = 1,815 total (1,773 across 36 unittest suites; 42 across 2
                             shell suites, config 18 + protected baseline 24). Basis stated
                             because it changed during Stage 6: the Stage 5 figure of 1,324
                             across 30 suites included the shell suites, the interim Stage 6
                             figures did not. Stage 7 added exactly one suite.
untracked_baseline:          508 files, byte-identical; drift 0, missing 0, extra 0
roadmap:                     docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md — the durable
                             cross-stage map: artifact lifecycle and JSON catalog, exact
                             file-set accounting, command-to-artifact matrix, product
                             milestones M1-M7, remaining-checkpoint forecast, and the gap
                             register G1-G17. Read it before scoping Stage 9.
stage_9_plan_of_record:      docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md   PROPOSED —
                             S9-0, S9-1, S9-2, S9-3 AND S9-4 APPROVED AND COMPLETE;
                             S9-L1 EXECUTED AND COMPLETE. Settles D9-A (external
                             retained state root) and D9-B (harvest.sh + cli.py;
                             run_cells.run() generalized, no new engine; one atomic
                             Transport seam), every command contract, the wrapper plan
                             and the exit criteria. Errata E9-1 (wrapper accounting is
                             per checkpoint: 58 -> 59 at S9-1; 63 is the PLANNED FINAL
                             count), E9-2 (--state-root is required of state-bearing
                             commands; preflight-sources is the deliberate exception)
                             and E9-3 (bounds belongs to S9-3, atomically with its
                             enforcement), E9-4 (S9-2 accounting 59 -> 60; the cli.py
                             arm must route to BOTH wrappers — a plan defect,
                             corrected), E9-5 (preflight retains no state but owns
                             one transient lease root outside the repository) and
                             E9-6 (stdout is one bare sorted JSON array of committed
                             source_preflight rows, no envelope).
                             E9-7 (offline-first order: S9-3 may precede S9-L1,
                             which stays MANDATORY before S9-L2), E9-8 (runvalidate.py
                             is the read-only validation owner), E9-9 (anticipated
                             spent guards), E9-10 (S9-3 accounting 60 -> 61; 63 is
                             post-S9-6), E9-11 (42 JSON = 18 selected-run + 24 shared;
                             a 2nd run adds 18 and updates the same 24) and E9-12
                             (explicit run_id_value seam, pattern read from the
                             committed schema).
                             E9-13 (S9-4 is NINE paths; two spent registry snapshots
                             retired, partition invariants intact), E9-14 (--normalize
                             REMOVED, never implemented; three-class partition; the
                             content class is DERIVED from the committed schemas so an
                             unenumerated field fails loudly), E9-15 (comparison covers
                             the 18 selected-run documents ONLY — the 24 shared ones are
                             updated in place and are never presented as historical A/B
                             snapshots; both runs may be historical and runvalidate is
                             NOT weakened) and E9-16 (metadata counts: an invariant
                             WITHIN a run, a content change BETWEEN runs), E9-17 (S9-4
                             accounting 61 -> 62; the pre-S9-L2 authoritative gate
                             expects 62/62, and 63/63 is a SECOND gate owed before
                             S9-L4).
                             S9-0..S9-4 PUBLISHED at 238df98; the pre-S9-L2
                             AUTHORITATIVE GATE RAN ONCE AND PASSED 62/62 exit 0
                             (62 wrappers each exactly once, 19 legacy + 43 taxonomy,
                             0 FAIL, 0 WARN-skipping); the external retained root is
                             SELECTED and VERIFIED; S9-L1, S9-L2 and S9-L3 are COMPLETE
                             and S9-5 is COMPLETE. **M2 AND M3 ACHIEVED; M4 UNMET.**
                             STILL OWED: the 63/63 gate after S9-6, one bounded
                             linkcheck run, and the completion handoff.
                             S9-5C1 and S9-5C2 are now COMPLETE; S9-6, S9-L4,
                             closeout AND S9-5C3 REMAIN UNAPPROVED.
stage_9_l2_l3_execution:     BOTH COMPLETE — **M2 AND M3 ACHIEVED**.
                             S9-L2 smoke ONCE, rc 0, run 20260731T113526Z-23992;
                             S9-L3 smoke ONCE, rc 0, run 20260731T120702Z-20188.
                             No retry, no third smoke. Each stdout carried exactly
                             json_artifacts 42 / mode smoke / pointer LATEST_RUN_ID /
                             publication_eligible false / source_preflight_rows 25 /
                             its own run id; both stderr empty.
                             Retained root now holds TWO runs: 18 + 18 selected JSON,
                             24 shared updated IN PLACE, = 60 JSON + 1 pointer naming
                             run 2. NOT 84 (E9-11). locks/ (58 entries, 19 hosts,
                             slots/ + next_allowed_at) is SEPARATE infrastructure —
                             never say the root holds only 43 entries.
                             Run 1's 18-document aggregate
                             58e55eee47e601841a16a5908ca98d6fda1fccd67aeb556458d6f74a35756e8f
                             held before the 2nd smoke, after it, and after validation
                             and comparison. Shared docs, the pointer and locks/ are the
                             MUTABLE half and did change — do not claim otherwise.
                             Each run validated ONCE, offline: rc 0, valid true,
                             errors [], json_documents_checked 42, paths_checked 43 —
                             42/43 scopes to the NAMED run; historical runs are
                             permitted but NOT added to that count.
                             compare-runs ran ONCE, offline: rc 0, run_a=run1,
                             run_b=run2, documents_compared 18, documents_expected 18,
                             shared_documents_excluded 24, errors [], invariant
                             violations 0, idempotent true. diff was NOT run.
                             Validation and comparison changed ZERO retained bytes
                             (80-file hash manifests identical before/after).
                             Both runs are smoke-mode: NOT production candidates, NOT
                             publication-eligible, NOT promoted, NOT consumed by any
                             website. Publication and promotion remain ZERO.
                             OPEN: manifests do not retain live duration —
                             started_at == finished_at and cell elapsed_sec is None, so
                             the ~54.7 s (run 1) wall clock survives only in the
                             external command logs.
stage_9_5c_preflight:        COMPLETE, read-only. Split the three S9-5 observability
                             corrections into C1 (timing) / C2 (duplicate
                             observability) / C3 (rejection-history layout),
                             PROVEN not assumed: no two share a production owner,
                             a schema or a recovery concern.
                             CORRECTED BY THE C2 AUDIT: the preflight's C2 finding
                             ("CandidatePool is the owner; relax
                             request_accounting additionalProperties:false") was
                             WRONG ON BOTH COUNTS and is superseded by
                             stage_9_5c2_sightings below. Keep the correction
                             attached: pool.add_candidate runs only under
                             enrich=True, so it was NEVER CALLED in either live
                             smoke, and request_accounting is an owners-vs-attempts
                             key space that a sighting count does not belong in.
                             C3 needs comparator scope, the runvalidate
                             run-directory guard and the 18/24/42/60 arithmetic all
                             decided first. C3 REMAINS UNAPPROVED AND UNSTARTED.
stage_9_5c1_timing:          COMPLETE. FIVE paths: src/harvest/run_cells.py,
                             tests/harvest/test_run_cells.py,
                             tests/harvest/test_cli.py, the plan, this file.
                             CONTRACT: first UTC read stays the artifact-timestamp
                             authority (run id, generated_at, discovered_at,
                             rejection/ledger stamps, detected_at); a SECOND UTC
                             read after all cells and all pre-manifest artifact
                             work supplies ONLY manifest + RunResult finished_at
                             (no third read; it is NOT post-pointer); per-cell
                             duration comes from time.monotonic via the private
                             _monotonic(), one read either side of each
                             _run_one_cell, rounded once at ELAPSED_PRECISION=3
                             into run_manifest.cells[].elapsed_sec. Negative delta
                             REFUSED, never clamped. A raised or not_run cell gets
                             NO elapsed_sec — omitted, never zero. Wall-clock
                             subtraction is never a duration; RequestBudget keeps
                             its own untouched monotonic authority.
                             cell_artifact.metadata.sources[].elapsed_sec is a
                             DIFFERENT pre-existing per-source field and is
                             untouched; no cell-level duration was added there.
                             NO schema change (cells[].elapsed_sec already optional
                             and non-negative), no harness/routing/validator/
                             comparator/CLI/config change, wrapper inventory
                             stays 62.
stage_9_5c1_scope_expansion: RATIFIED, one path (four -> FIVE). The scope preflight
                             MISSED three whole-tree byte-identity guards —
                             TestDeterminism x2 in test_run_cells.py and
                             TestOmissionIsByteCompatible in test_cli.py. It had
                             searched for assertions NAMING started_at/elapsed_sec
                             and found none, which was true and misleading: the
                             breaking assertions are whole-tree hashes that name no
                             field. Implementation STOPPED WITHOUT COMMITTING and
                             reported; tests/harvest/test_cli.py was then added by
                             explicit approval.
                             THIS IS NOT RETIREMENT OF A SPENT GUARD. All three stay
                             EXACT byte-identity proofs — nothing excluded,
                             normalized, zeroed, diff-ignored or compared as a
                             subset. The durable contract is now: equal inputs +
                             equal ordering + equal injected UTC clock + equal
                             injected MONOTONIC clock => byte-identical trees. UTC
                             was always injectable; monotonic is the second
                             authority, injected the same way via the internal
                             run_cells._monotonic (never time.monotonic
                             process-wide, never RequestBudget). Production still
                             records ACTUAL durations, so two real executions are
                             NOT expected to agree — that is the measurement
                             working, not determinism failing. Each corrected guard
                             gained anti-vacuity: the trees must agree BECAUSE both
                             recorded the same real durations.
stage_9_5c1_validation:      FOCUSED ONLY, all green — run_cells 115 (incl. 16 new
                             timing tests), recovery 74, cli 58, smoke 56 — plus
                             py_compile x3 and one explicit-mode harness run over
                             src/harvest/run_cells.py at exit 0, every routed
                             wrapper exactly once, zero WARN skips. `--all` was NOT
                             run. NO network. C1 is EVIDENCE-ONLY: no verdict,
                             ordering, bound, artifact identity or publication
                             change; retained M2/M3 runs remain valid WITHOUT
                             migration or backfill (manifests lacking
                             cells[].elapsed_sec stay schema-valid); NO fresh live
                             smoke pair required.
stage_9_5c2_sightings:       COMPLETE. EIGHT paths: src/harvest/run_cells.py,
                             src/harvest/runvalidate.py,
                             schemas/harvest/run_manifest.v1.json,
                             tests/harvest/test_run_cells.py,
                             tests/harvest/test_manifest.py,
                             tests/harvest/test_smoke.py, the plan, this file.
                             CONTRACT: four integers on run_manifest.cells[],
                             captured in _run_one_cell at the DedupeResult seam
                             BEFORE BOTH caps —
                               candidate_observations  (= observation_count)
                               unique_candidate_keys   (= group_count)
                               repeated_candidate_observations
                                                       (= duplicate_observation_count)
                               uncanonicalizable_candidate_observations
                                                       (= len(unusable))
                             candidate_observations == unique_candidate_keys +
                             repeated_candidate_observations. The fourth is
                             counted BESIDE the three and is EXCLUDED from the
                             sum: an uncanonicalizable item never became an
                             observation and never became a group. It means
                             failure of target canonicalization AT THE DEDUPE
                             BOUNDARY — not a later extraction issue, which is a
                             NormalizationIssue and still yields a candidate.
                             The denominator is AFTER repeated source-snapshot
                             delivery to multiple lanes has been merged: three
                             lanes sharing one feed are ONE observation, not
                             three. unique_candidate_keys is canonical GROUPING
                             KEYS, NOT the post-cap cells[].candidates beside it.
                             NO RATE IS STORED — it is derived as
                             repeated/observations and is undefined at zero, so
                             there is no zero-denominator representation to get
                             wrong. NO fifth count, no run() parameter, no clock
                             read, no network. not_run and raised cells carry
                             NOTHING (the C1 elapsed_sec distinction); a
                             zero-observation completed cell emits integer
                             zeroes; a partial tuple is refused at the producer.
                             pool.py, dedupe.py, extract.py, artifacts.py and
                             compare.py are BYTE-UNCHANGED.
stage_9_5c2_ownership:       THE PREFLIGHT WAS WRONG ON BOTH COUNTS; keep the
                             correction attached. (1) CandidatePool is NOT the
                             owner: pool.add_candidate is reached only via
                             _fetch_targets, and run_cells passes
                             `pool=pool if enrich else None`, so with --no-enrich
                             it was NEVER CALLED ONCE in either live smoke — a
                             pool-owned metric would have read 0 sightings across
                             both achieved milestones while 127 candidates were
                             processed. Its input is also the accepted,
                             twice-capped set. (2) request_accounting is NOT the
                             location: that block is owners-vs-attempts in two
                             separate key spaces, and it is run-level.
                             dedupe.group() ALREADY computes all three numbers
                             with the invariant holding by construction at
                             dedupe.py:407 — C2 is WIRING, NOT MEASUREMENT — and
                             dedupe/extract/pool are byte-frozen, so reading the
                             existing DedupeResult from run_cells.py is the only
                             owner that breaks no guard.
stage_9_5c2_cap_retraction:  THE FIRST AUDIT'S `iff` CAP CLAIM IS RETRACTED, and
                             NOT for the reason first suspected. Extraction does
                             NOT reduce cardinality: normalize_all is a total,
                             non-filtering map, so DedupeResult.group_count ==
                             len(ExtractionResult.candidates) pre-cap — already
                             proved by test_extract.py's
                             test_one_candidate_per_valid_group and
                             test_a_malformed_optional_field_never_removes_a_candidate.
                             The real defect: TWO caps sit between the
                             measurement and cells[].candidates —
                             _apply_candidate_cap AND _accepted_prefix, the
                             latter proved to move that number by
                             test_smoke.py's
                             test_the_accepted_cap_binds_on_a_deterministic_prefix.
                             WHICH cap truncated a cell is NOT ATTRIBUTABLE. C2
                             claims nothing about it and adds no fifth count.
                             **The S9-5 conclusion stands: the 12/5 caps remain
                             PROVISIONAL and NOT FULLY OBSERVABLE.**
stage_9_5c2_enforcement:     THREE-WAY SPLIT (E9-19), stated exactly because the
                             halves are not interchangeable.
                             SCHEMA owns all-or-none presence + integer type +
                             minimum 0, via four-direction dependentRequired on
                             cells[] — in EVERY mode and AT WRITE TIME, since
                             artifacts.write_document validates before writing.
                             RUNVALIDATE owns the ARITHMETIC only, conditional on
                             all three being present, and is SMOKE-ONLY:
                             validate_run already requires mode=="smoke" and
                             config.enrich==false, and C2 does NOT widen it.
                             PRODUCER TESTS own correct capture, independent of
                             whether a validator ever looks.
                             JSON Schema CANNOT express the arithmetic (no
                             cross-property arithmetic keyword in 2020-12), so the
                             split is FORCED, not chosen. The schema also cannot
                             tell a newly completed row from a pre-C2 completed
                             row, so MANDATORY PRESENCE ON NEW WORK stays a
                             producer contract in run_cells._cell_row.
                             Precedent: _check_counts (total_records !=
                             full_records + cross_references) and the topic
                             by_category sum are both conditional cross-field
                             arithmetic on optional fields. The check imports
                             nothing, recomputes nothing and uses no bare assert —
                             asserted by AST scan, because the docstring names
                             `dedupe` to record the boundary and `candidate_key`
                             is a substring of `unique_candidate_keys`.
                             compare.py NEEDED NO CHANGE: CONTENT_FIELDS is
                             derived from the committed schemas.
stage_9_5c2_compatibility:   NO migration, NO backfill, NO schema_version bump
                             (stays 1). dependentRequired fires only when a key is
                             PRESENT, so every pre-C2 manifest and every not_run
                             row stays valid untouched. The retained M2/M3 runs
                             remain authoritative evidence and simply carry no C2
                             fields — the honest record, since the numbers were
                             never measured. NO fresh live smoke pair required.
                             ANTI-VACUITY NEEDED SYNTHETIC INPUT: the committed
                             fixture corpus has NO repeated sighting and NO
                             uncanonicalizable target (all 12 cells report 0 and
                             0), and the corpus is byte-frozen, so the repeat
                             cases are built in-test from the real AdapterResult /
                             RawCandidate through the real dedupe.group — the S6-7
                             technique.
stage_9_5c2_validation:      FOCUSED ONLY, all green, each command run EXACTLY
                             ONCE — run_cells 137 (was 115; +22 new sighting
                             tests), recovery 74 (unchanged), cli 58 (unchanged),
                             smoke 62 (was 56; +6 validator tests), manifest 63
                             (was 52; +11 schema tests) — plus py_compile over the
                             five changed Python modules and `jq empty` on the
                             schema. ONE explicit-mode harness invocation over
                             src/harvest/run_cells.py + src/harvest/runvalidate.py
                             + schemas/harvest/run_manifest.v1.json: EXIT 0, PASS,
                             the union of run_cells/recovery/cli/smoke/manifest
                             routed and each executed EXACTLY ONCE, zero
                             WARN-skipping, zero FAIL, runtime paths absent before
                             and after, production state/ unchanged. NO routing
                             edit and NO new wrapper: inventory stays 62.
                             `--all` was NOT run — the 63/63 gate owed before
                             S9-L4 will cover C1 and C2, and covers C3 ONLY if C3
                             is separately approved and landed before it. NO
                             network, NO live smoke rerun. Wrapper paths are
                             tests/test_taxonomy_*.sh (NOT tests/harvest/*.sh).
stage_9_5_calibration:       COMPLETE, documentation only, two paths (this file + the plan).
                             PRIMARY DECISION: **THRESHOLDS STAY PROVISIONAL**.
                             Evidence: 2 runs ~32 min apart, ONE reproduced corpus =
                             19 accepted full records + 13 cross-references (NOT 64;
                             the runs are not independent samples). Both validate;
                             comparison 197 permitted / 23 content / 0 violations,
                             idempotent — and all 23 content changes were manifest
                             source_preflight[].elapsed_ms. Corpus reproduced exactly.
                             CELLS/CAPS: 10 of 12 cells at candidate cap 12, 2 at
                             accepted cap 5; two cells BELOW the cap (community 3,
                             benchmark-and-datasets 4). Truncation is UNPROVABLE —
                             cap-outside candidates are never logged. Caps NOT FULLY
                             OBSERVABLE. accepted+rejected==candidates in every cell.
                             Manifest `accepted` != artifact record count per cell
                             (cross-topic ownership relocates records) but reconciles
                             globally 19==19.
                             SCORES: relevance min 0.453 vs 0.35 (+0.1033), 4 distinct
                             values. quality AND audience_fit are SATURATED at 1.000
                             across all 19 — one distinct value each, margins +0.70 and
                             +0.80, and they rejected NOTHING. Analytical composite
                             (recomputed from committed weights, NOT stored) min 0.7621
                             vs 0.40. No per-cell threshold override exists.
                             REJECTIONS (run 2 ONLY — run 2 overwrote the logs; run-1
                             per-reason history is UNAVAILABLE): 108 entries reconcile
                             exactly per cell and globally. Two reasons only: off_topic
                             89 (detail: "no required term for <cell> matched") and
                             below_relevance_threshold 19. quality/audience_fit/
                             composite gates NEVER fired. Closest failure 0.3333 vs 0.35
                             = -0.0167 (microsoft-blogs); all others <= 0.2267.
                             SOURCES: 5 GitHub releases.atom denials persistent across
                             all three probes; netflix-techblog denied at S9-L1 but
                             PERMITTED in both smokes — robots is TIME-VARYING, and it
                             matters: netflix is the #2 contributor (4 of 19). Only
                             8 of 25 sources produced any accepted record; 12 reachable
                             sources produced rejections only (producthunt 12->0,
                             techcrunch-ai 12->0). Attribution = provenance.source_id,
                             corroborated by field_variants 19/19 single-source.
                             REPEAT SIGHTINGS: ledgers cumulative, 130 identities,
                             seen_count==2 for 124 (95.4%). This is CROSS-RUN
                             repeat-sighting, NOT an in-run duplicate rate — that rate
                             is NOT recoverable from retained artifacts.
                             COVERAGE: 2 zero-result cells (both all_below_relevance_
                             threshold); 5 cells hold no full record; 2 supported only
                             by cross-references; research-and-models holds 12 of 19
                             (63%). alias_conflicts 0 and stable; 7 classification
                             decisions identical; coverage report identical apart from
                             clock fields.
                             AUXILIARY DECISIONS: caps STAY PROVISIONAL; source roster
                             and robots entries STAY PROVISIONAL (no change approved);
                             timing evidence NEEDS CORRECTION; rejection-history
                             retention NEEDS CORRECTION; duplicate-rate observability
                             NEEDS CORRECTION. ALL THREE corrections are
                             EVIDENCE/OBSERVABILITY-ONLY, none verdict-affecting, so
                             NONE would require a fresh pair of live smokes.
                             S9-5C PROPOSED ONLY — not approved, not started; its exact
                             path set could NOT be established read-only, so a SEPARATE
                             SCOPE PREFLIGHT is required before it can be approved.
                             NO config, schema, code, retained-root byte or operational
                             log was changed.
stage_9_l1_execution:        COMPLETE. `preflight-sources --timeout-sec 20` executed
                             EXACTLY ONCE at 2026-07-31T08:21:16Z, all 25 configured
                             sources, no --sources subset, exit code 1 (complete JSON,
                             at least one source failed — not a crash). 25 unique rows
                             sorted by source_id: 19 ok, 0 adapter_error, 6
                             infrastructure_error, ALL SIX robots_denied
                             (lm-eval-harness-releases, netflix-techblog,
                             openai-evals-releases, oss-langchain-releases,
                             oss-mcp-servers-releases, oss-ollama-releases — five share
                             the GitHub releases.atom pattern). microsoft-blogs reports
                             crawl_delay_sec 10.0. stderr empty; NO retry and no second
                             invocation; no lease root leaked; no commit. Logs retained
                             OUTSIDE the repository at
                             ../scratchpad/s9_l1_preflight_20260731T082116Z_540.{stdout.json,stderr.log,rc}.
                             THE FIRST OUTBOUND TRAFFIC THIS PIPELINE HAS EVER MADE.
                             The six denied rows are PRESERVED OBSERVATIONS, not
                             approved corrections: no source, policy, timeout or robots
                             config was changed, and none may be changed to improve a
                             live result. Disposition belongs to S9-5 calibration.
stage_9_4_scope_expansion:   RATIFIED, one path (eight -> NINE). A read-only scan before
                             editing found a SECOND spent S9-3 registry census outside
                             the approved set —
                             test_smoke.py::test_compare_diff_and_linkcheck_remain_unimplemented
                             — asserting compare-runs and diff must remain PLANNED, which
                             registering them necessarily falsifies. The checkpoint
                             STOPPED WITHOUT COMMITTING and reported; tests/harvest/
                             test_smoke.py was then added by explicit approval, making
                             S9-4 nine paths in ONE atomic commit. Both spent guards
                             were RETIRED, not weakened: no replacement census, no
                             "linkcheck must stay planned" guard, and no smoke
                             behaviour, bounds, recovery, validation,
                             publication-ineligibility or no-network assertion touched.
                             THIRD consecutive checkpoint to hit E9-9's problem.
stage_9_4_harness:           61 -> 62 wrappers (19 legacy + 43 taxonomy); ISOLATED[]
                             61 -> 62 with the committed 61 byte-identical as an ordered
                             prefix; exactly one wrapper appended; one routing arm added
                             (compare.py) and one extended (cli.py); every target
                             canonical tests/<name>.sh; no future-wrapper target, no
                             aggregate, no blanket arm.
stage_9_4_validation:        FOCUSED ONLY, 162 assertions green — compare 48, cli 58,
                             smoke 56 — plus py_compile x5, bash -n x2 and one
                             explicit-mode harness run over compare.py and cli.py at
                             exit 0 with four wrappers each exactly once and zero WARN
                             skips. `--all` was NOT run: §8.2 places the authoritative
                             full gate at the final code baseline before the first live
                             smoke, and E9-17 corrects its expectation to 62/62. NO
                             network request of any kind; data/harvested/ was looked at
                             by `diff` and REMAINS ABSENT.
stage_9_3_scope_expansion:   RATIFIED, one path. E9-9 anticipated the duplicated
                             `bounds` snapshot in test_run_cells.py but MISSED the
                             same guard in test_cli.py, whose live-transport AST scan
                             was also over-broad (ast.walk descends into function
                             bodies, so it rejected calls inside DEFINITIONS). The
                             checkpoint STOPPED WITHOUT COMMITTING and reported;
                             tests/harvest/test_cli.py was then added by explicit
                             approval, keeping S9-3 ELEVEN paths in ONE atomic commit.
                             No production workaround for either scan.
stage_9_3_validation:        FOCUSED ONLY, 453 assertions green — smoke 57, cli 58,
                             preflight 65, run_cells 99, recovery 74, manifest 52,
                             eligibility 48 — plus py_compile x7 and one explicit-mode
                             harness sample at exit 0 with five wrappers each exactly
                             once and zero WARN skips. `--all` was NOT run. NO
                             configured source contacted; every smoke used the fixture
                             transport under a socket guard proved wired by tripping it.
stage_9_2_scope_expansion:   RATIFIED, one path. S9-2's seven-path set could not hold:
                             three S9-1 registry SNAPSHOTS in tests/harvest/test_cli.py
                             asserted COMMANDS == {} and a fixed planned set, and
                             registering an operational command necessarily falsifies
                             them. The checkpoint STOPPED WITHOUT COMMITTING and
                             reported; tests/harvest/test_cli.py was then added by
                             explicit approval, making S9-2 eight paths in ONE atomic
                             commit. No production workaround; no permanent S9-1
                             boundary weakened.
cli_registry_invariant:      DURABLE, replaces two spent snapshots. The Stage 9 surface
                             is exactly six commands; COMMANDS and PLANNED_COMMANDS are
                             DISJOINT and their UNION is that surface; every handler is
                             callable; every planned entry names its owning checkpoint;
                             help reports both honestly. Stays true as each command
                             moves across. NO exact registry-size assertion remains in
                             the permanent CLI suite; per-checkpoint facts live in the
                             suite that owns the command.
                             CORRECTED at S9-4: this block previously claimed S9-3, S9-4
                             and S9-6 "will not re-encounter this blocker". S9-4 DID —
                             not in test_cli.py, whose invariant held exactly as
                             designed, but via a DUPLICATE census S9-3 wrote into
                             test_smoke.py. The invariant only protects the file that
                             holds it; a checkpoint census written into any other suite
                             is still spent by the next checkpoint (E9-13).
stage_9_2_validation:        FOCUSED ONLY, 122 assertions green — preflight 65, cli 57 —
                             plus py_compile x4 and one explicit-mode harness sample at
                             exit 0 with both wrappers exactly once and zero WARN skips.
                             `--all` was NOT run. NO outbound request: the only traffic
                             is a loopback server the suite binds and shuts down, and a
                             socket-level guard refuses every non-loopback host and is
                             proved wired by tripping it.
stage_9_1_scope_expansion:   RATIFIED. S9-1's eight-path set could not hold: three
                             committed progress guards pinned the very interface S9-1
                             was approved to change. The checkpoint STOPPED WITHOUT
                             COMMITTING and reported; tests/harvest/test_run_cells.py
                             and tests/harvest/test_recovery.py were then added by
                             explicit approval, making S9-1 ten paths in ONE atomic
                             commit. No production code was shaped to satisfy a source
                             scan; no behavioural or recovery assertion was weakened.
stage_9_1_harness:           58 -> 59 wrappers (19 legacy + 40 taxonomy); ISOLATED[]
                             58 -> 59 with the committed 58 byte-identical as an ordered
                             prefix; three routing arms added/extended; every target
                             canonical tests/<name>.sh; no future-wrapper target, no
                             aggregate, no blanket arm.
stage_9_1_validation:        FOCUSED ONLY, 366 assertions green — cli 57, run_cells 99,
                             recovery 74, eligibility 48, target_determinism 88 — plus
                             bash -n, py_compile and one explicit-mode harness sample at
                             exit 0 with test_taxonomy_cli.sh run exactly once and zero
                             WARN skips. `--all` was NOT run: §8.2 places the
                             authoritative full gate at the final code baseline before
                             the first live smoke. NO network request of any kind.
```

## Progress dashboard

Five **independent** dimensions. They are not stages, and a high number in one says nothing about
the others. Detail, evidence and denominators in `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §1 and §3.

| Dimension | State | Evidence |
|---|---|---|
| **Implementation** | Stages 0-8 closed (10 of the 12 named stage labels). But only **2 of the 13** commands/producers the master plan names actually exist: the run driver — as a **Python function with no CLI** — and `migrate.sh` | `validate_task.sh --all` exit 0, 58/58 wrappers, zero skips (S8-2) |
| **Live staging** | **NONE.** Zero network requests have ever been made by this pipeline. `run_cells.run()` builds its opener unconditionally as `fixtures.FixtureOpener`, so a live run is **not currently possible without new production code** | `state/taxonomy_harvest/`, `runs/`, `LATEST_RUN_ID` all absent |
| **Production candidate** | **NONE**, and **unowned.** Stage 9 produces `--no-enrich` smokes, which `IMPLEMENTATION_PLAN.md` §7.1 explicitly disqualifies from promotion. No stage owns the enriched production run, and human review has no artifact, schema or acceptance process | roadmap G4, G9 |
| **Publication** | **NONE.** `data/harvested/` absent. `promotion_receipt`, `promotion_journal`, `publication_manifest`, `promote_staging`, `promote_rollback` and `--publication-root` have **zero occurrences** anywhere in the tree | roadmap §5.4, G7 |
| **Website integration** | **NONE, unscoped, unowned.** No interface contract, no consumer code, no cadence | roadmap G10 |

**Stage 9 and Stage 10 are NOT the last two steps before publication.** Stage 9 is a bounded live
smoke; **Stage 10 is two markdown documents and creates no JSON and publishes nothing.** Closing the
described Stage 0-10 plan takes an estimated **13-18 checkpoints** and ends at a live smoke plus a
link check. A reviewed production candidate, a promotion implementation, an actual publication into
`data/harvested/`, and a consuming website are a further estimated **21-30 checkpoints**, and they
are **additional production milestones** — mostly undesigned and currently unowned. See
`ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §4.

**STAGE 4 IS CLOSED** as of 2026-07-30 — see
`docs/harvest/handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` for the commit chain, closure
validation, repository state and successor constraints. `STAGE_4_IMPLEMENTATION_PLAN.md` reads
`COMPLETED — STAGE 4 CLOSED`; its §12 records the documentation-only closeout.

**STAGE 6 IS CLOSED** as of 2026-07-30 at `7aa1ccec439162d238ad87fd00c3b543ed3e8f55` — see
`docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md` for the commit chain, the delivered
target-fetching contracts, closure validation, repository state, carried-forward findings and
successor constraints. `STAGE_6_IMPLEMENTATION_PLAN.md` reads `COMPLETED — STAGE 6 CLOSED`; its
§11 S6-C section records the documentation-only closeout.

**S6-L, the bounded live smoke, was optional to that closure and was NOT RUN** — it needed approval
twice, once as a checkpoint and once immediately before execution, and neither was given. **Live
network access was never authorized and no Stage 6 request of any kind was made.** It is not marked
complete, passed, failed or waived anywhere in this file.

**A completed stage authorizes nothing in the next one.** **Stage 6 remains closed** at `0d2da64`,
which `origin/main` held until Stage 7 was published on top of it — see `push_state` above for the
published Stage 7 boundary.

**STAGE 7 IS CLOSED** as of 2026-07-31 at `c3d982c572844cf39787b5b2368e975bfb198986` — see
`docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md` for the commit chain, the delivered
migration contracts, closure validation, repository state, carried-forward findings and successor
constraints. `STAGE_7_IMPLEMENTATION_PLAN.md` reads `COMPLETED — STAGE 7 CLOSED`; its §9 S7-C section
records the documentation-only closeout.
S7-1, the read-only entity assessment, **migrated 0 of 1,161 entities**, which is what it was for;
S7-2, the suspicious-URL guard, refuses **0 of the 231** protected AX case pages and rewrites
nothing; S7-3 maps **231 accepted / 0 rejected** in memory and writes nothing at all; S7-4 adds
`migrate.sh` with `ax-cases` and `entity-assess`; S7-5 makes `--apply` publish one three-file bundle
by a single directory rename, **exercised only under injected temporary roots**; S7-6 proves the five
are one offline workflow, end to end through the wrapper; S7-C is this documentation closeout.

**Closure approves nothing.** **No migration runtime bundle is retained — `state/taxonomy_harvest/`
does not exist**, and that is the intended closing state. A **push**, an **operational apply** against
the default state root, **promotion** into `data/harvested/`, any **live request**, and **Stage 8**
(`validate_task.sh` wiring, CF-4) each remain unapproved and each needs its own explicit approval.
**Stage 8 is not opened by this closure.** Green tests alone open nothing.

**Baseline at Stage 7 opening**, carried from the Stage 6 closure and re-verified before S7-0 edited
a line: **38/38 suites · 1,815 counted assertions · protected 18/18 · untracked 508/508 with drift 0,
missing 0, extra 0 · no runtime path (`state/taxonomy_harvest`, `data/harvested`, `runs` all absent)
· no live request ever made by this pipeline.**

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
**`COMPLETED — STAGE 6 CLOSED`** (2026-07-30). It scopes Stage 6 to **target fetching and
verification only**; the `refresh` /
`linkcheck` / `promote` / `diff` / `compare-runs` subcommands, the transaction journal and the
promotion tests listed under this heading stay **unscheduled, unapproved and untouched** (plan §14
erratum E11). Checkpoint sequence
**S6-0 · S6-1 · S6-2 · S6-3 · S6-4 · S6-5 · S6-6 · S6-6A · S6-6B · S6-7 · S6-L · S6-C**, each requiring
its own separate approval **by name** (S6-6A was added between S6-6 and S6-7 by plan §14.4, which found
target request accounting underivable inside S6-6's boundary; S6-6B by the S6-7 preflight, which found
plan §7.4 describing an unimplemented ledger flow — erratum E18); S6-C's handoff path and allowed paths are declared in advance in
plan §11. **S6-L (bounded live smoke) is the only checkpoint that makes a network request** and needs
approval twice — once as a checkpoint and once immediately before it runs.

**Four things this heading deliberately keeps apart** *(recorded as they stood at planning; items 1
and 2 are unchanged, items 3 and 4 are updated at closure)*:

1. **The plan was approved as the plan of record**, checkpoint-by-checkpoint (plan §15). What Stage 6
   *is*, and the order it was built in, were settled there.
2. **D6-A and D6-B are RESOLVED** (plan §12), both as recommended. A resolved decision fixes the
   *shape* of a future change and authorizes nothing else; each shipped inside the checkpoint it
   unblocked, D6-A at S6-5 and D6-B at S6-6.
3. **S6-1 through S6-C were each approved by name and have shipped.** Approving the plan approved
   **not even S6-1**; every checkpoint below carries its own approval and its own commit.
4. **Live network access was never authorized, and no Stage 6 request of any kind was made.** Every
   checkpoint S6-1 … S6-7 is fixture-backed with a no-socket assertion. **S6-L, the single exception,
   needed both of its approvals and received neither, so it was never run** — see the closure note at
   the head of this file.

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
        **S6-7 is blocked until the accounting contract is resolved.** — **DISCHARGED by S6-6A.**
      - **One defect found by its own test**: the `conflict_id` content-derivation test indexed a row by
        position after the rows are sorted, so it was asserting the sort order rather than the id. The
        production hash was correct; the test now selects by `identity_url`.
- [x] **S6-6A** target request accounting (`feat(harvest): report target request accounting`) — the
      checkpoint §14.4 demanded and deliberately left undeclared, **scoped by a read-only ownership and
      path audit that edited no file, ran no test and made no request.** `TargetFetchOutcome` gained one
      field, `accounting`, **copied** from the client's final `Response` or its typed error — never
      recomputed, never diffed from `client.stats`, on the idiom `sourcecache.py` already states for the
      source lane. A failure uses the committed `getattr(error, "accounting", ZERO_ACCOUNTING)`, since
      `BudgetExhausted` carries no class default; a budget-skipped target keeps **genuine zeros**,
      because no request was made. `artifacts.target_request_accounting()` sums the map **once**, at the
      manifest boundary.
      - **The route was `targetfetch.py`, and `pool.py` never needed to move.**
        `pool.accounting()["http_attempts"]` sums `self.sources`, which only `record_established_source`
        populates and which the target path is forbidden to call — so the pool structurally cannot see a
        target fetch. `pool.py` and `httpclient.py` are **byte-unchanged**, the Stage 4 byte-freeze holds
        and **no guard was retired for them**.
      - **One outcome per owned canonical identity, so a shared URL is counted once** — the S6-4
        ownership guarantee stated as a number rather than re-proved.
      - **Three keys, and the boundary they respect**: `target_http_attempts`, `target_retries`,
        `target_redirect_hops`, optional and inside `request_accounting` beside the owner counters that
        already describe both lanes. `http_attempts`, `retries` and `redirect_hops` keep their
        **source-only** meaning, unchanged in value and wording. **No `total_http_attempts`** — folding
        the two key spaces is what §2 forbids, and the prohibition is still asserted by a live test. No
        `request_charges` projection, no target conditional revalidations, no robots retrievals, no
        estimate.
      - **Omission and zero are different answers.** `target_outcomes` defaults to a `None` sentinel:
        omitted, the three keys are absent and every committed caller is byte-identically unaffected;
        supplied — **including empty** — all three appear at zero. "Fetched nothing" must stay
        distinguishable from "did not report".
      - **Plan erratum E17.** §5.0's "never observes an attempt, a hop count, a retry" was a stronger
        claim than the design needed: it fenced off transport *ownership*, but the wording also forbade
        reading a number the client had already frozen, which was the sole structural reason §14.4 called
        the count unreachable. The fence stands — one logical call, no retry/timeout/redirect/body-size
        logic, no branch on any counter — and the sentence now says so. **The documentation is in this
        commit, not a separate one**: the superseded sentence and the code superseding it are one
        contract.
      - **One spent progress guard retired in part**, `test_eligibility.py::test_no_target_attempt_total_
        is_reported`: the three `target_*` names it forbade are now the shipped keys and are asserted by
        **exact value** instead, while its `total_http_attempts` prohibition is **kept** because that one
        is not spent. Renaming the keys to keep the guard green was rejected on the S6-4/S5-4 precedent.
        Two independent `StubResponse` helpers and the exact `TargetFetchOutcome` field set were updated
        for the same reason.
- [x] **S6-6B** ledger target observation propagation (`fix(harvest): persist target evidence in
      ledgers`) — **corrective, found by the read-only S6-7 preflight, which stopped without editing a
      file.** Plan §7.4 described the ledger carrying `http_status` / `content_hash` /
      `last_checked_at` as a finished flow; the tree did not implement it. Everything that section
      named was real except the last link: `ledger.v1.json` has admitted all three since Stage 1,
      `OBSERVATION_FIELDS` has listed them since S5-3, `merge_ledger` has stored them since S5-3 —
      and `run_cells.py`'s observation supplied **none** of them. Recorded as plan erratum **E18**;
      §7.4 now carries the flow that exists.
      - **The correction is four paths and no more.** `ledger.py` is **byte-unchanged**, no schema
        moved, no fixture or config was touched, and `request_accounting` and both key spaces are
        exactly as S6-6A left them. Only what the driver *observes* changed.
      - **The record is the source of truth.** `LEDGER_TARGET_EVIDENCE_FIELDS` are **copied** from the
        finished full record, joined by the `record_id` the observation already computes — never
        recomputed from the `TargetFetchOutcome`, because a second derivation could disagree with the
        record written beside it in the same run. **No clock is read**: `last_checked_at` is the
        record's own. A `cross_reference` is excluded — it was never a page anyone fetched.
      - **A field is written only when the record carries a non-null value.** A metadata-only record
        contributes none of the three, a budget-skipped target contributes no status and no hash, and
        a rejected candidate contributes nothing at all. A null written here would be a claim rather
        than the absence of one, and `merge_ledger` already reads a null as "no news".
      - **Proved at the run boundary, not against `merge_ledger`** — the storage already had its own
        tests, and what had never been asserted was that a real run's ledger row says what that run's
        record says. Each of the four target-fetched records is joined to its ledger entry and
        compared field for field, with distinct per-page content hashes, no fabricated values on
        rejected entries or in the eleven cells that fetched nothing, schema validity, and
        byte-identical reproduction by a second identical run. **It fails against `88d40ca`** — 12
        failures and 15 errors across all four records — which is what makes it a proof.
      - **Why no test caught this for four checkpoints**: `test_ledger.py` never mentioned the three
        fields, and `test_run_cells.py`'s ledger assertions covered entry counts, outcomes,
        `seen_count`, `first_seen_at` and sort order — every property except the one §7.4 claimed.
        The gap fell between S6-5, whose paths covered records rather than the ledger, and S6-7, which
        is test-only.
- [x] **S6-7** determinism, failure modes and partial runs, end to end
      (`test(harvest): prove target determinism and recovery`). **Test and documentation only** —
      exactly four paths, no production module, schema, config or committed fixture, and a test
      asserts `tests/fixtures/harvest` is unmodified afterwards, because a composer bug would edit the
      corpus every other suite reads. **88 assertions.**
      - **Same-clock byte determinism over the whole tree.** Two equivalent runs into two roots: the
        exact **43-path** file set, one hash, and then a file-by-file byte comparison, because a tree
        hash alone would pass on two empty trees. Every artifact validates, and the suite-local
        `schema_for()` names `alias_conflicts.json` — the mapping S6-6 missed in a private copy of that
        helper, which is why it is spelled out here.
      - **Order cannot reach the output.** Cell order shuffled through `run()`; **source** order
        shuffled by handing `_run_one_cell` a reordered `sources` list, since `run()` takes cell IDs and
        reads sources from the committed configuration; **candidate** order shuffled at the fetch-phase
        boundary over real candidates from a real cell run. Each shuffle is asserted to have actually
        shuffled before anything is compared.
      - **Four composed scenarios, not one impossible run** (plan erratum **E21**). The committed corpus
        accepts four records, so four target slots is the whole budget and several families are mutually
        exclusive on one URL. Terminal failures (404 · 410 · 403 · terminal 500), bodies and redirects
        (empty · non-HTML · 301-only · a 302 hop), canonical adjudication (cross-domain ·
        same-domain-robots-unverified · two tags · self) and budget skipping each get their own
        deterministic scenario. Every scenario emits a complete valid 43-path tree.
      - **A composed corpus is a COPY.** Target `status`, `headers` and body are substituted in a temp
        tree; `fixture_id`, filename and URL stay exactly as committed, or the record's identity moves
        and the scenario stops being comparable to the clean run.
      - **The five clock-derived leaves are a committed-corpus property** (erratum **E19**). Extended to
        the complete tree, three more families carry instants of their own — the manifest's
        `started_at`/`finished_at`, a rejection log's `rejected_at` and `freshness`, and the cross-run
        ledger's four — each **enumerated exactly and none excused**. An alias carries `observed_at` and
        a conflict `detected_at`, both absent from the committed corpus, so the alias- and
        conflict-producing scenarios are proved by **same-clock byte identity** rather than by enlarging
        the allowlist to admit leaves the committed corpus does not have.
      - **`request_accounting` is identical across the two clocks**, target counters included: an
        estimate would have no reason to survive a clock change.
      - **An interruption in the fetch phase publishes nothing at all** — no run artifact, no
        `ledgers/`, no `rejections/`, no pointer, no temp debris — and the retry is an **ordinary fresh
        run** producing a tree hash-identical to a clean one. No resume was introduced. A finished
        `run_id` is refused **before the first request and before the fixture corpus is even loaded**,
        proved with counters that a control case shows would have caught real traffic.
      - **Robots-denied is not composed at run level** (erratum **E20**), because all four accepted
        targets and the feed that surfaces them share `github.com`: denying that host stops discovery,
        so the scenario would prove nothing about a denied record. It keeps its existing owner in
        `test_target_fetch.py` and fixture #20. The §5.0 transport exclusions stand — no timeout
        sequencing, no `500 → 200` transition, no over-cap body, and the composed corpora are asserted
        to carry no forbidden transport key either.
      - **One defect found by its own test, in the suite itself**: the interruption class re-read the
        artifact root per test while one of its own tests deliberately wrote into it, so the emptiness
        assertion passed or failed on alphabetical method order. The post-interruption state is now
        **captured once in `setUpClass`** — a suite about determinism does not get to be order-dependent.
- [x] **S6-C** Stage 6 closeout, documentation only (`docs(harvest): record stage 6 completion`) —
      `docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md` plus the plan's status area and
      S6-C section, and this file. Exactly the three paths **declared up front** in plan §11 before
      Stage 6 wrote a line of code, so the authorization gap hit at the Stage 4 closeout did not recur
      for the second stage running. L0 validation only — exact three-path diff, `git diff --check`,
      nothing touched under `src/`, `tests/`, `scripts/`, `config/`, `schemas/`, `state/`, `data/` or
      any run artifact, protected baseline 18/18, the 508-file untracked baseline unchanged, no runtime
      path created. Per its own risk tier the focused suites and the full gate were **not** rerun for a
      documentation-only change: the closing gate is S6-7's, **38/38 suites green in one run** before
      `7aa1cce`.
- [ ] **S6-L** — **optional to closure, never approved, NOT RUN.** It needs approval twice, once as a
      checkpoint and once immediately before execution; neither was given. **Live network access
      remains unauthorized and no Stage 6 request of any kind was made.** Left unticked deliberately:
      this is not a deferred task with work owing, it is an authorized-and-declined option. It is not
      recorded as passed, failed, waived or complete. **D6-A and D6-B remain resolved and both are
      delivered.**
- [ ] `scripts/harvest/{refresh,linkcheck,promote}` subcommands — **`diff` and `compare-runs` were
      reassigned to Stage 9 and implemented at S9-4**; `linkcheck` is owned by S9-6; `refresh` and
      `promote` remain descoped by E11 with no owner
- [ ] Transaction journal, before-images, per-operation commit record, rollback, resume
- [ ] `--publication-root` for isolated testing
- [ ] `tests/test_taxonomy_linkcheck.sh`
- [ ] `tests/test_taxonomy_promote_txn.sh` — 4 fault-injection points + add/remove/partial modes

## Stage 7 — AX corpus migration ⟵ **CLOSED.** All checkpoints S7-0 … S7-C complete.

**Plan of record:** `docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md` — **`APPROVED — PLAN OF RECORD;
S7-0 COMPLETE; NO IMPLEMENTATION CHECKPOINT APPROVED`**. It reconciles and **supersedes**
`IMPLEMENTATION_PLAN.md` §11, which
is pre-Stage-3 design input; the seven differences are recorded there as errata **E22 … E28**.
`IMPLEMENTATION_PLAN.md` is not edited by Stage 7.

Stage 7 converts the **protected** AX case registry into committed `record.v1.json` records —
offline, copy-on-write, non-destructive, regenerable, schema-v1 preserving, and separate from
promotion — and produces a **read-only** assessment of the entity registry that is deliberately not
migrated. Decisions **D7-A … D7-K** are settled in the plan, not left as options. **Non-goals:**
promotion into `data/harvested/`, `refresh`/`linkcheck`/`diff`/`compare-runs`, `validate_task.sh`
wiring (Stage 8), calibration (Stage 9), the live smoke, entity migration proper, and concurrency.

- [x] **S7-0** plan of record, documentation only (`docs(harvest): plan stage 7 migration`) —
      `docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md`
      plus this section and the header block. Exactly the two paths **declared up front**, so the
      authorization gap hit at the Stage 4 closeout does not recur for the third stage running.
      Records D7-A migration character and read-only protected inputs · D7-B the exact three-file
      bundle `<state-root>/migrations/<run_id>__ax_cases/` · D7-C staging-then-one-rename atomicity,
      repeat refusal and **no resume** · D7-D honest evidence (`snippet_only`/`unverified`, never
      `fetched`) · D7-E the fixed `cases__case-studies` cell and the `migration.` classification
      rule · D7-F facet representation with the committed vocabularies and no inference ·
      D7-G null scores and honest unknowns · D7-H the four committed guard rule ids, matched
      structurally · D7-I a one-row `mode: migration` manifest with derived
      `publication_eligible: false` · D7-J the entity-registry boundary · D7-K the dry-run/apply CLI.
      L0 validation only — exact two-path diff, `git diff --check`, nothing touched under `src/`,
      `tests/`, `scripts/`, `config/`, `schemas/`, `state/`, `data/`, protected baseline 18/18, the
      508-file untracked baseline unchanged, no runtime path created. Per its own risk tier the
      focused suites and the full gate were **not** rerun for a documentation-only change.
      **Six plan-vs-code contradictions were found while writing it and resolved without reopening
      Stage 6** (E22, E23, E24, E25, E26, E27); a seventh (E28) corrects §14's "apply twice".

- [x] **S7-1** entity registry migration assessment, read-only
      (`feat(harvest): assess entity registry`) — `src/harvest/migrate/{__init__,entity_assess}.py`,
      `tests/harvest/test_migration.py`, `tests/test_taxonomy_migration.sh`,
      `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md`, plus the plan and this file. Exactly
      the seven paths declared in plan §9. **0 of 1,161 entities migrated** — no taxonomy record, no
      migration bundle, no runtime state, and the destination taxonomy stays an open product
      decision. Four separated layers (load · assess · render · write-to-an-explicit-path), no clock,
      no network, no git state, no absolute path, no module-global mutable state. **The committed
      document is generated by the module and never hand-edited**, and the suite compares its bytes
      against a fresh render, so drift fails instead of accumulating. A malformed top level, row,
      field, `discovery` block or `found_via` **raises** — nothing is skipped, because a skipped row
      would silently make every count wrong. Reversal and three seeded shuffles each render
      byte-identically, and each reordering is asserted non-vacuous. Counts reconcile three ways
      (subtotals to the population, derived against the registry's own `metadata`, derived against
      the expected corpus size), and each reconciliation is proved to *notice* a dropped or moved row.
      **Measured:** `entity_id` distinct **721 of 1,161** — 51 values reused by 491 rows, 49 of them
      spanning topics, largest group 23; topic-qualifying raises it only to 831, so **topic
      qualification does not repair uniqueness**; only `entity_key` is unique (1,161/1,161) and it is
      a merge artefact; **0 exact duplicate rows**, so every repeat is a repeated *identifier*, not a
      repeated row. **137 rows carry `target_url: "unknown"`** and **77 rows share a URL with another
      row** (36 URLs) — the two structural blockers on any URL-identified migration, recorded without
      proposing a fix. No replacement identifier is selected: that is item 2 of the document's
      follow-up checklist. Focused suite **43 assertions**; full gate **39/39 suites, 1,858
      assertions (1,816 unittest + 42 shell)**; five checkers exit 0; the protected registry is
      byte-identical before and after; no runtime path; no request of any kind.

- [x] **S7-2** migration base and the suspicious-URL guard (`feat(harvest): add migration URL guard`)
      — `src/harvest/migrate/base.py`, `tests/harvest/test_migration.py`,
      `tests/test_taxonomy_migration.sh`, plus the plan and this file. Exactly the five paths declared
      in plan §9, and **no config edit**. Public surface: the immutable ordered `SUSPICIOUS_RULE_IDS`
      (`search_engine_host` · `search_query_path` · `feed_path` · `index_page` — the vocabulary
      **and** the precedence), `MigrationInputError`, the frozen two-field `GuardMatch`,
      `suspicious_url_match()` and its boolean delegate `looks_like_index_or_search()`.
      **First-match precedence** was the one design clarification S7-2 was authorized to make, and it
      is recorded in D7-H. **The guard refuses and nothing else:** `GuardMatch` has no field that
      could carry a replacement, and the detail text is asserted to contain no URL — nothing is
      rewritten, repaired, percent-decoded or given a scheme. Matching is **structural**: host
      equality plus a first-label `search.` check, whole path segments, and query parameter **names**
      parsed rather than searched. `urlkey.registrable_host` is deliberately unused — the registrable
      domain of `cloud.google.com` is `google.com`, which is the E24 defect — and an AST test pins
      that `base.py` imports exactly `dataclasses` and `urllib.parse`, executes nothing at import
      beyond definitions, and defines no second canonicalizer. **Measured: 0 of 231 protected AX
      `source_url` values are suspicious**, proved non-vacuous by ten fabricated positives run
      through the same loop; each rule carries at least two positive examples, and the negative
      controls include all four `cloud.google.com` blog URLs and the E24 LinkedIn article. **The
      override reader and the bundle path builders were deliberately NOT written** — neither is
      needed to decide whether one URL is suspicious. Focused suites: migration **71 (43 + 28)**,
      identity 42, records 51, schema 35; full gate **39/39 suites, 1,886 assertions (1,844 unittest
      + 42 shell)**; five checkers exit 0; both protected registries byte-identical; the S7-1
      assessment still regenerates byte-identically; no runtime path; no request of any kind.

- [x] **S7-3** in-memory AX mapping (`feat(harvest): map AX cases in memory`) —
      `src/harvest/migrate/ax_cases.py`, `tests/harvest/test_migration.py`,
      `tests/test_taxonomy_migration.sh`, plus the plan and this file. Exactly the five paths declared
      in plan §9. **Nothing is written: no file, no bundle, no manifest, no serialization** — the CLI,
      the dry-run report and the apply path do not exist. Public surface: `AxMigrationError`, the
      frozen two-tuple `MappingResult`, and
      `map_registry(document, *, harvest_run_id, migrated_at, reviewed=None, allow_unmappable=False,
      facets_dir=None)`, which takes an **already-loaded** document and opens no registry or override
      file. **The clock is the caller's** — both instants are required, `migrated_at` is validated
      against the committed UTC second-precision pattern, and `discovered_at` is always supplied so
      `make_full_record` cannot reach its fallback; an AST test proves the module calls no clock, CLI,
      socket, subprocess or `open`. `classify.py`, `verify.py` and `facetassign.py` are **not
      imported**: a migration that re-judged its corpus would not be a migration.
      **Measured: 231 accepted / 0 rejected** · 231 distinct `record_id` / `content_id` /
      `identity_url` from **126 distinct legacy `case_id`s**, which change nothing because identity is
      URL-derived · **231/231 `snippet_only`**, none claiming `fetched`, a status, a hash or a check
      time · **33 `"unknown"` publication dates → null**, the originals intact in `provenance.raw` ·
      all four scores null · facet states **112 `facet_partial` · 118 `unmapped_legacy_value` ·
      1 `unresolved`**, and `check_facets.py` reports **0 problems** over all 231. The lexical-support
      gate is applied exactly where the committed contract applies it — applying it to every mapped
      slug was tried and rejected on evidence (it withholds six reviewed mappings `check_facets`
      accepts and moves the distribution to 106/118/7), so **E27 is exactly the one `"IT services"`
      record**, which records its reviewed mapping instead of asserting it. Review semantics are
      in-memory: an unreviewed suspicious URL refuses the whole mapping, `allow_unmappable` completes
      with rejections intact and admits nothing, a reviewed `admit` takes the raw URL verbatim and
      says so in the migration assumptions, a reviewed `reject` stays rejected. Two mappings differing
      only in run id and migration instant move **exactly two leaves**, found by recursive diff.
      Focused: migration **133 (43 + 28 + 62)**, records 51, schema 35, identity 42, facets 34,
      eligibility 48; full gate **39/39 suites, 1,948 assertions (1,906 unittest + 42 shell)**; five
      checkers exit 0; both protected registries byte-identical; the S7-1 assessment still regenerates
      byte-identically; no runtime path; no request of any kind.

- [x] **S7-4** the migration CLI and dry-run (`feat(harvest): add migration dry-run CLI`) —
      `scripts/harvest/migrate.sh`, `src/harvest/migrate/{base,ax_cases,entity_assess}.py`,
      `tests/harvest/test_migration.py`, `tests/test_taxonomy_migration.sh`, plus the plan and this
      file. Exactly the eight paths declared in plan §9 — and `base.py` was left **byte-unchanged**,
      so the S7-2 guard purity assertions stand as committed. **No migration bundle, manifest,
      staging directory, rename or runtime output exists**; the CLI writes nothing anywhere except an
      explicit `entity-assess --output` path. Surface: `migrate.sh ax-cases` (dry-run by default,
      `--registry` · `--overrides` · `--facets-dir` · `--expect-count` (default **231**) ·
      `--allow-unmappable` · `--run-id` · `--migrated-at`), `migrate.sh entity-assess`
      (`--registry` · `--output`), `migrate.sh --help`; unknown or absent commands exit 2 with usage.
      The wrapper is dispatch only — `set -euo pipefail`, `"$@"` forwarded verbatim (a path with
      spaces is asserted to survive), no `eval`, no temp file, no network, no Git.
      **`--apply` is recognised and REFUSED** with a message naming S7-5: nothing is read or written,
      no staging or final path appears, and a before/after hash snapshot of a controlled temp tree
      proves it. **The dry-run report** is one deterministic 16-field JSON document on **binary**
      stdout, rendered by the committed `artifacts.serialize` — no second serializer, no
      accepted-record dump, no path, no environment, no publication eligibility. On the protected
      corpus: **231 source / 231 accepted / 0 rejected / 0 unresolved, exit 0**, byte-identical
      across runs and unchanged by reordering source or review rows. **Unresolved suspicious URLs
      still print the COMPLETE report** — every rejection — and only then exit 1; a reviewed `reject`
      is an acknowledged decision, not unresolved; `--allow-unmappable` completes with every
      rejection intact and admits nothing. Override parsing validates the committed shape completely
      and additionally refuses a review whose declared `matched_rule` is not the rule the guard
      actually fires, or that names a case the guard does not refuse at all; the committed file
      (zero reviews) parses and is never modified. `entity-assess` stdout equals the committed
      assessment byte-for-byte and `--output` writes exactly those bytes. Focused: migration
      **175 (43 + 28 + 62 + 42)**, records 51, schema 35, identity 42, facets 34, eligibility 48;
      full gate **39/39 suites, 1,990 assertions (1,948 unittest + 42 shell)**; five checkers exit 0;
      both protected registries byte-identical; the S7-1 assessment still regenerates
      byte-identically; no runtime path; no request of any kind.

- [x] **S7-5** atomic apply and repeated-run semantics (`feat(harvest): add atomic migration apply`)
      — `src/harvest/migrate/{base,ax_cases}.py`, `scripts/harvest/migrate.sh`,
      `tests/harvest/test_migration.py`, `tests/test_taxonomy_migration.sh`, plus the plan and this
      file. Exactly the seven paths declared in plan §9. **Apply works, and every apply so far has
      been to an injected temporary root — the real `state/taxonomy_harvest/` does not exist.**
      CLI: `--apply` and `--state-root PATH` (operational default `state/taxonomy_harvest`);
      `--state-root` without `--apply` is refused rather than ignored. `base.py` became the Stage 7
      **path owner** — `migrations_root` · `bundle_path` · `manifest_path` ·
      `candidate_artifact_path` · `rejection_artifact_path` · `staging_name` · `owns_staging` ·
      `validate_run_id` · `MigrationPathError` — deriving paths and **creating none**, every one
      behind an anchored run-id pattern so a separator or `..` never reaches the filesystem; the
      ordinary `runs/<run_id>` builders are neither used nor duplicated. **The bundle is exactly
      three files** (`manifest.json`, `candidate_output/cases__case-studies__harvest.json`,
      `rejections/cases__case-studies__rejections.json`) — no topic, coverage, alias-conflict,
      ledger, pointer, journal, sidecar or placeholder, nothing under `runs/`, no `LATEST_RUN_ID`,
      no promotion. **Everything is built and schema-validated before a staging directory exists**;
      the three documents are written through the committed `artifacts.write_document` into a
      uniquely named **sibling** staging directory, the staged path set is asserted to be exactly
      three, the destination is rechecked, and publication is **one `os.replace` of the directory** —
      the report prints only after it. **Eligibility is derived**: every accepted record must be
      `not_checked` or the bundle is refused, and `publication_eligible` is false with a
      deterministic reason. **A used run id is refused before the registry, overrides or facets are
      read**, proved with a counting loader; the first bundle stays byte-identical. **Cleanup owns
      exactly one path**, proved from both the retained path and `owns_staging`; a foreign
      `.tmp_migration_*`, an unrelated file and a pre-existing `migrations/` all survive, and a
      `migrations/` this apply created is removed only when empty. **Five fault-injection boundaries**
      each leave the state root path-identical, and a sentinel bundle appearing mid-staging is left
      byte-identical rather than overwritten. **Two distinct runs move exactly the enumerated
      leaves** (candidate: `generated_at`, `harvest_run_id`, and per record `harvest_run_id` +
      `provenance.migration.migrated_at`; manifest: three; rejections: two) and are byte-equal once
      normalized. Protected corpus under a temp root: **231 accepted / 0 rejected**.
      **E29 applied in the same checkpoint:** `report_type` is now `ax_cases` for both modes —
      `dry_run` is the sole discriminator, the sixteen-field shape is unchanged, and there is no
      `ax_cases_apply` type and no alias. **Incident recorded:** the retired S7-4 apply-refusal tests
      wrote two bundles into the real gitignored `state/taxonomy_harvest/` during implementation;
      they were removed, tracked files and both baselines were never affected, and a new assertion
      scans the suite's own AST so no call site can pass `--apply` without `--state-root` again.
      Focused: migration **224**, artifacts 33, manifest 52, cell_artifact 44, recovery 75,
      run_cells 99, records 51, schema 35, identity 42, facets 34, eligibility 48; full gate
      **39/39 suites, 2,039 assertions (1,997 unittest + 42 shell)**; five checkers exit 0; both
      protected registries and the override config byte-identical; the S7-1 assessment still
      regenerates byte-identically; no real runtime path; no request of any kind.

- [x] **S7-6** final migration integration, test and documentation only
      (`test(harvest): prove migration integration`) — `tests/harvest/test_migration.py`,
      `tests/test_taxonomy_migration.sh`, plus the plan and this file. Exactly the four paths
      declared in plan §9; **no production, shell, schema, config, fixture or protected path
      changed**, and S7-6 adds no capability. It proves S7-1 … S7-5 are **one workflow**, driven
      through the real `scripts/harvest/migrate.sh` over the protected committed inputs: snapshot →
      `entity-assess` (stdout equals the committed assessment **byte for byte**) → dry run → apply
      into a temporary `--state-root` → apply again under a second run id and instant → retry the
      finished run id → read both bundles into memory → **delete the temporary root** → then assert.
      **Dry-run and apply are compared as actual CLI stdout**, not two calls to one renderer: same
      sixteen fields, same `report_type "ax_cases"` / `report_version 1` / `operation "ax-cases"`,
      differing **only** in `dry_run`, at **231 accepted / 0 rejected**. The bundle is
      **cross-checked between documents**: report counts equal the candidate rows, its derived
      metadata, the rejection document and the manifest cell; one run id and one instant appear in
      all four; the manifest is one migration cell with no request accounting and
      `publication_eligible: false` whose reason accounts for all 231 records remaining
      `not_checked`. Records read back from disk carry every contract — 231 distinct identities over
      126 legacy `case_id`s, all `snippet_only`, 33 null dates, four null scores, facet states
      **112 / 118 / 1**, `check_facets.py` clean, guard **0/231**. Two runs move exactly the
      permitted leaves and are byte-equal once normalized; reversing **both** source and review rows
      changes nothing. The four review outcomes are proved command-to-artifact. Atomicity is
      consolidated into one all-or-nothing observation at the rename boundary, and **all five
      detailed S7-5 fault-injection boundaries are retained unchanged**. Every apply names an
      explicit temporary `--state-root` (asserted by an AST scan of the suite itself), the injected
      root is proved deleted, and the repository's runtime paths are proved absent before and after.
      Focused: migration **250**, artifacts 33, manifest 52, cell_artifact 44, recovery 75,
      run_cells 99, records 51, schema 35, identity 42, facets 34, eligibility 48; full gate
      **39/39 suites, 2,065 assertions (2,023 unittest + 42 shell)**; five checkers exit 0; both
      protected registries and the override config byte-identical; the S7-1 assessment still
      regenerates byte-identically; no temporary root remains; no real runtime path; no request of
      any kind.

- [x] **S7-C** Stage 7 closeout, documentation only (`docs(harvest): record stage 7 completion`) —
      `docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md` plus the plan's status area and
      S7-C section, and this file. Its path set was **not** declared in advance and no handoff
      filename was pre-authorized: S7-C ran **its own read-only closeout preflight** first, which
      established the three paths from the committed precedents (`0d2da64` S6-C, `6bf7f51` S5-C,
      `5fd9f91` S4-C each changed exactly a plan, this file and one new handoff) and found the one
      factual defect this closeout had to fix — the `push_state` line still described the Stage 6
      position. L0 validation only: exact three-path diff, `git diff --check`, nothing touched under
      `src/`, `tests/`, `scripts/`, `config/`, `schemas/`, `state/`, `data/`, protected baseline
      18/18, the 508-file untracked baseline unchanged, no runtime path, no temporary root, and
      cross-document consistency. Per its own risk tier the focused suites and the full gate were
      **not** rerun: the closing gate is S7-6's, **39/39 suites green in one run** before `c3d982c`,
      and the handoff attributes its figures to that run rather than re-measuring them.

**Migration implementation, offline integration and closeout are COMPLETE. STAGE 7 IS CLOSED.**
**No migration runtime bundle is retained** — `state/taxonomy_harvest/` does not exist, which is the
intended closing state. A **push**, an **operational default-root apply**, **promotion**, any **live
request** and **Stage 8** each remain unapproved and need explicit approval by name. **Stage 8 is not
opened by this closure.**

**Measured against the corpus at `0d2da64`, asserted by the checkpoints rather than assumed:** 231
cases · 231 unique `source_url` → **231 distinct `identity_url`, zero collisions** · `case_key`
unique but **`case_id` is not** (126 distinct — E26) · 173 distinct industry values, 113 records
mapped / 118 unmapped, 1 mapped value refused by the lexical-support gate (E27) · 33
`publication_date: "unknown"` → null · all 231 carry an `evidence_quote`, so all 231 become
`snippet_only` · **0 of 231 trip the suspicious-URL guard** under D7-H's structural predicates,
where a substring reading of §11 would wrongly reject 5 (E24).

## Stage 8 — harness wiring and full offline regression

**STAGE 8 IS CLOSED** as of 2026-07-31, at the S8-C documentation closeout on top of
`01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c` — see
`docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md` for the commit chain, the delivered
harness contract, the authoritative S8-2 regression evidence, closure validation, repository state,
carried-forward findings and successor constraints. `STAGE_8_IMPLEMENTATION_PLAN.md` reads
`COMPLETED — STAGE 8 CLOSED`; its §8 S8-C section records this documentation-only closeout.

**CLOSED AND PUBLISHED** at `bf067303a01fa80d1421f9eef7030cbadf805733`; HEAD, local `main` and local
`origin/main` are synchronized, **0 behind / 0 ahead**. Every future push still needs its own
approval.

Both broad deliverables are met:

- [x] `scripts/validate_task.sh` — new tests in the case table and `ISOLATED[]`
- [x] `bash scripts/validate_task.sh --all` green, including the 64 unchanged matrix assertions

**Plan of record: `docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md`.** It settles the wiring pattern,
the exact `ISOLATED[]` additions, the exact case-table mapping, the definition of full offline
regression, and what is explicitly not Stage 8.

- [x] **S8-0 — plan of record.** Documentation only, own commit, L0 validation only. Settled: all
      39 taxonomy wrappers wired individually (no aggregate gate, no wrapper modified); `ISOLATED[]`
      goes 19 → 58 entries; the case table is extended by ownership, not import fan-out, with no
      blanket fallback; "full offline regression" means `--all` exits 0 with all 58 wrappers run
      exactly once and **zero skips**; matrix 64 is read from captured output rather than parsed by
      the harness; the four runtime paths get a harness-level pre/post `[ -e ]` check; `--all`
      becomes the closing gate and contains the taxonomy gate, so the standalone taxonomy loop is
      not rerun. Excluded by decision: harness self-test, aggregate wrapper, baseline change,
      `CLAUDE.md` change, version gate, timeout, summary counter, argument-parser change,
      concurrency, network, real migration apply, promotion.
- [x] **S8-1 — harness wiring.** `scripts/validate_task.sh` — all 39 taxonomy basenames added to
      `ISOLATED[]` individually (19 → 58 entries, the legacy 19 preserved verbatim as a prefix); 50
      additive taxonomy case arms / 91 `add_test` calls routing all 39 wrappers, every target
      spelled `tests/<name>.sh`, the 19 legacy arms byte-identical to `b9a08a3`; the two documented
      omissions implemented as explicit empty arms ahead of the wildcards; and a `RUNTIME_PATHS`
      `[ -e ]` check before **and** after execution for the four runtime paths, which sets the
      existing sticky `FAIL=1` and never deletes what it finds. Sequential execution, WARN-skip
      semantics, `--all` argument positioning and the `state/` byte snapshot all preserved.
      Focused validation only — `--all` was **not** run.
- [x] **S8-2 — full offline regression. PASSED.** Verification-only: no write paths, **no commit**,
      no edit. One unfiltered `bash scripts/validate_task.sh --all`, output redirected outside the
      repository and inspected there. **Exit 0 in 736 s**, final line `== validate_task.sh: PASS ==`;
      **58/58 wrappers each exactly once** (legacy 19/19 + taxonomy 39/39); **zero
      `WARN - skipping`**; matrix **64 passed, 0 failed**; parallel **62 passed, 0 failed**; no
      `FAIL - offline` and no FAIL line of any kind; no runtime-leak and no production-state-change
      diagnostic, with both harness positive assertions printed. Post-run: protected 18/18,
      untracked 508/508 drift 0, all four runtime paths absent, worktree byte-identical to
      `01d2999a`. The expected wrapper list was built from `git ls-files tests/`, not from the log.
      No separate taxonomy loop was run — `--all` already contains all 39 taxonomy wrappers exactly
      once. The external log was outside the repository and was deleted after verification; **no
      log artifact is retained**.
- [x] **S8-C — closeout.** Documentation only: this file, the plan, and one new handoff.
      `CLAUDE.md` deliberately not in the set. L0 validation only; `--all` **not** rerun.

**Stage 8 is closed and CF-4 is closed.** `scripts/validate_task.sh --all` now exercises the entire
taxonomy wrapper set and passes offline with zero skips, which is exactly what CF-4 asked for.
**Nothing else is closed by Stage 8** — every other carried-forward item stands at its existing
status, S6-L remains unexecuted and unauthorized, and Stage 9 is not opened. Stage 8 contained no
network access, no operational migration apply, no promotion, and no retained runtime output. **A
push remains a separate approval**, via `safe_push_main.sh --check` then a separately approved
`--execute`.

## Stage 9 — bounded deterministic live smoke ⟵ **NOT OPEN, NOT APPROVED.**

**No `STAGE_9_IMPLEMENTATION_PLAN.md` exists.** Stage 8's closure opens nothing here; a green gate
and a published stage do not, separately or together, authorize the next stage. Nothing below is
scheduled, and no checkpoint name below is approved.

**Read `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §9-§10 before scoping this stage.** Two audited facts
change what Stage 9 *is*:

1. **There is no command that runs the pipeline** (roadmap G1). `run_cells.run()` is a Python
   function; `src/harvest/run_cells.py` has no `__main__` and no `argparse`, and no shell script
   invokes it. `scripts/harvest/harvest.sh` — which the master plan's acceptance commands invoke
   about ten times — **does not exist**.
2. **`run()` cannot reach the network.** It builds its opener unconditionally as
   `fixtures.FixtureOpener` (`run_cells.py:794-806`); there is no opener parameter, mode switch or
   live branch. A live request therefore needs **new production code first**, not merely approval.

`compare-runs` and `preflight-sources` have **zero occurrences** anywhere in the tree; `smoke`,
`smoke_model`, `refresh` and `linkcheck` exist only as `run_manifest.v1.json` `mode` enum values and
prose. The `model_search` adapter raises a typed `AdapterNotImplemented`. None of these has a
producer.

**Plan of record: `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md`** — `PROPOSED — S9-0 ONLY APPROVED`,
baseline `2bbc236a`. It settles **D9-A** (the Stage 9 runtime root: an explicitly supplied, retained
**external** state root outside the repository — the Stage 8 runtime guard is not weakened) and
**D9-B** (a thin `scripts/harvest/harvest.sh` dispatcher over one `src/harvest/cli.py` owner, with
`run_cells.run()` **generalized** by keyword-only default-`None` parameters on the committed D6-A /
S6-6A sentinel idiom — **no new engine module**, and one atomic `Transport` seam so a live opener can
never be paired with disabled pacing). It also settles every command contract, the wrapper plan
(**58 → 63**), the validation policy and the exit criteria.

**Writing that plan approved no implementation and no live command.** Each checkpoint below needs its
own approval **by name**, with its exact allowed-path set declared up front. Code checkpoints and
network executions are strictly separate, and **every live execution needs approval twice** — once as
a checkpoint, once immediately before the outbound request.

- [x] **S9-0** plan of record, documentation only (`docs(harvest): plan stage 9 live validation`) —
      `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` plus this section. Exactly the two paths declared
      up front. L0 validation only. **Approves nothing further.**
- [x] **S9-1** live execution seam and CLI foundation
      (`feat(harvest): add live transport seam and CLI foundation`) — code and offline tests only,
      **no network**, **no retained external state root**, **no live command**. Ten paths after a
      **ratified expansion**: `scripts/harvest/harvest.sh` · `src/harvest/cli.py` ·
      `src/harvest/run_cells.py` · `tests/harvest/test_cli.py` · `tests/test_taxonomy_cli.sh` ·
      `scripts/validate_task.sh` · `tests/harvest/test_run_cells.py` ·
      `tests/harvest/test_recovery.py` · the plan · this file.
      - **`run_cells.Transport` is one frozen `(opener, sleep, lease_root)`**, and `run()` takes one
        transport rather than three independent parameters, so a live opener can never inherit the
        fixture's suppressed pacing — a test asserts that half-live API does not exist. `run()`'s
        four new seams are keyword-only and `None`-defaulted on the D6-A / S6-6A idiom: omitted,
        every one reproduces the behaviour committed at `720f114c` **byte-for-byte**, proved by
        running the old call shape and the explicit all-`None` shape at one pinned clock and
        comparing all **43 paths file by file** — non-vacuously, over a record-bearing tree.
      - `transport=None` rebuilds the fixture transport over `fixtures_dir` and sweeps only the
        temporary lease root it created; **a supplied lease root is the caller's** and is never
        replaced or deleted. `mode="smoke"` is publication-ineligible through the **committed**
        derivation — **no new predicate**, asserted. `enrich=False` fetches no target page and leaves
        the three `target_*` accounting keys **ABSENT rather than zero**, because "the lane did not
        run" and "the lane ran and found nothing" are different answers (S6-6A's sentinel).
        **No `bounds` parameter** — E9-3 gives it to S9-3, atomically with its enforcement.
      - `cli.py` registers **no subcommand**: all six planned commands exit **2** naming the
        checkpoint that owns them, and none falsely exits 0. `validate_state_root` refuses empty,
        non-absolute, the repository root, any repository descendant, the four prohibited runtime
        paths and `..`-traversal back inside; it **creates nothing and deletes nothing**.
        `live_transport` is the only place `default_opener` and `time.sleep` are named together;
        constructing one makes no directory and issues no request, and **nothing calls it.**
        An AST scan proves `cli.py` owns no vocabulary and defines no matcher, canonicalizer,
        serializer, scorer or classifier. `harvest.sh` is 20 lines of `exec` — no `eval`, no parsing,
        no Git, no network, no temp file, and no second usage document.
      - **No-network proof, non-vacuous:** a sentinel supplied as a transport opener **is** reached,
        which is what makes the other half meaningful — the same sentinel installed over
        `httpclient.default_opener` records **zero** calls during a default run, and `time.sleep`
        records zero.
      - **Three spent progress guards retired, and the expansion that required it.** S9-1's original
        eight-path set could not hold: `test_run_cells.py` pinned `run()`'s parameter list to a
        **closed** five-name list and pinned `FixtureOpener` to a **source location** inside `run()`,
        and `test_recovery.py` repeated the same closed list. The checkpoint **stopped without
        committing and reported** rather than widening itself; the two-path expansion was then
        ratified explicitly. **No production code was shaped to keep a source scan green** — keeping
        the literal inside `run()` was available and was rejected on the S6-4 / S6-6A / S5-4
        precedent. Before the correction those two suites were **171 of 174 green**: all three
        failures were a signature list and a source substring, never a behavioural regression. The
        opener guard was **narrowed** from implementation location to the permanent
        ownership/offline boundary and asserted behaviourally; the signature guard was **rewritten**
        as an omission-compatible prefix contract; the recovery guard was **deleted outright**
        because it asserted no recovery property, and every genuine recovery assertion beside it is
        untouched and green. Detail in plan §7.1a.
      - **Focused validation only, 366 assertions green:** cli **57** · run_cells **99** · recovery
        **74** (75 → 74, the deleted guard) · eligibility **48** · target_determinism **88**; plus
        `bash -n`, `py_compile`, and one explicit-mode harness sample
        (`validate_task.sh scripts/harvest/harvest.sh src/harvest/cli.py`) at **exit 0**, with
        `test_taxonomy_cli.sh` run **exactly once** despite two mapped files, **zero
        `WARN - skipping`**, no FAIL line and no runtime leak. **`--all` was NOT run** — §8.2 places
        the authoritative full gate at the final code baseline before the first live smoke.
      - **Harness: 58 → 59 wrappers** (19 legacy + **40** taxonomy), `ISOLATED[]` 58 → 59 with the
        committed 58 byte-identical as an **ordered prefix**; three routing arms
        (`harvest.sh` → cli, `cli.py` → cli, and `run_cells.py` extended with cli beside its existing
        run_cells and recovery targets). Every target canonical `tests/<name>.sh`; **no future
        wrapper target, no aggregate, no blanket arm** — E9-1 records that **63 is the planned final
        Stage 9 count**, not S9-1's.
- [x] **S9-2** source-preflight implementation (`feat(harvest): add source preflight command`) —
      code and offline tests only, **no outbound request**, **no retained state**, **no real source
      contacted**. Eight paths after a **ratified expansion**: `src/harvest/preflight.py` ·
      `src/harvest/cli.py` · `tests/harvest/test_preflight.py` · `tests/test_taxonomy_preflight.sh` ·
      `scripts/validate_task.sh` · `tests/harvest/test_cli.py` · the plan · this file.
      - **`preflight-sources` is the first operational Stage 9 command.** All **25** configured
        sources resolve through the committed `run_cells.configured_cells()` reader — no second
        interpretation of the topic files — sorted by `source_id` and probed **exactly once** each.
        Selection strips whitespace, and **refuses** an empty id, a duplicate id (never
        deduplicates), unknown ids as a set, and an empty selection — **every refusal before the
        first request**, proved by counting probes afterwards. Reversing the configuration order
        changes no serialized byte.
      - **A failure is a ROW, never an exception.** `HttpClient.preflight()` never raises and neither
        does assembly: a dead source keeps its committed reason and every other selected source is
        still probed and reported, so "25 rows all ok" can never be confused with "3 rows all ok".
        `source_id` is stamped from **configuration** — the probe is handed a URL and has no notion
        of identity — while the classification, reason and every measurement are the probe's,
        **copied verbatim**.
      - **E9-6 output:** one bare **JSON array** of committed `source_preflight[]` rows, sorted, with
        **no envelope, count, timestamp or second schema**, serialized by `artifacts.serialize`. It
        is therefore directly reusable as a future manifest's `source_preflight` value. Exit **0**
        all-ok · **1** any failure *after* printing the complete array · **2** bad arguments with
        **empty stdout and no probe**. No retry-until-green.
      - **`--timeout-sec` through the one committed seam.** `HttpClient(policy, …)` reads its
        timeouts from `policy["budgets"]`; `preflight()` takes no per-call timeout and emulating one
        would be a second HTTP implementation. Numeric, finite, positive, and **bounded above by the
        configured `request_timeout_sec` (20)** — narrowed, never widened — with connect and read
        **clamped down** so a `--timeout-sec 2` is not defeated by the configured 15 s read timeout.
        The committed policy document is not mutated.
      - **E9-5, the transient lease root.** The command creates no run and writes nothing in the
        repository, but the committed HTTP stack coordinates through a filesystem lease tree, so it
        owns **one temporary root outside the repository** and removes it on success, on a reported
        source failure and on an injected `KeyboardInterrupt`. That is infrastructure scratch, **not**
        a retained Stage 9 state root; **no `--state-root` is accepted or required**, and D9-A is
        unweakened for every state-bearing command.
      - **`httpclient.py`, `run_cells.py`, `harvest.sh`, every config and every schema are
        byte-unchanged**, asserted in-suite against `fddbbb7`. Rows are validated against the
        **committed** `run_manifest.v1.json` item read from the schema file, `additionalProperties:
        false` included — no second schema was created.
      - **Three spent S9-1 registry snapshots replaced by a durable invariant.** S9-2's seven-path
        set could not hold: registering an operational command necessarily makes `COMMANDS != {}`.
        The checkpoint **stopped without committing and reported**; the one-path expansion was then
        ratified. **No production workaround** — leaving the command in `PLANNED_COMMANDS` while
        registering it would have kept two guards green and put a false statement in `--help`.
        `test_no_subcommand_is_registered_at_s9_1` was **deleted** and deliberately **not** replaced
        by an exact one-command count, which would expire again at S9-3; the live-transport guard now
        protects **non-operational and refused paths** (import, parser, `--help`, unknown command,
        planned commands, bad arguments) instead of forbidding every operational caller, since
        S9-3 and S9-6 will add two more approved ones; and the planned-set snapshot became
        **`COMMANDS ∩ PLANNED = ∅`, `COMMANDS ∪ PLANNED = the six-command surface`**, with callable
        handlers, declared owning checkpoints and honest help. That **stays true as each command
        moves across**, so S9-3, S9-4 and S9-6 do not meet this blocker again. **No exact registry
        size assertion remains in the permanent CLI suite**; the S9-2-specific fact lives in the
        preflight suite.
      - **Focused validation only, 122 assertions green:** preflight **65** · cli **57**; plus
        `py_compile` ×4 and one explicit-mode harness sample
        (`validate_task.sh src/harvest/preflight.py src/harvest/cli.py`) at **exit 0**, both wrappers
        **exactly once**, **zero `WARN - skipping`**, zero FAIL, runtime paths absent. **`--all` was
        NOT run.**
      - **Harness: 59 → 60 wrappers** (19 legacy + **41** taxonomy), `ISOLATED[]` 59 → 60 with the
        committed 59 byte-identical as an **ordered prefix**; `preflight.py` routes only to the
        preflight wrapper and `cli.py` routes to **both** (E9-4 corrects the plan's omission). No
        future-wrapper target, no aggregate, no blanket arm.
      - **Outbound refusal, non-vacuous:** a socket-level guard refuses every non-loopback host and
        is **proved wired by tripping it**. The only traffic is a `ThreadingHTTPServer` the suite
        binds on `127.0.0.1:0` and shuts down itself, used to drive the **real** client so
        `robots_allowed`, `crawl_delay_sec`, `http_status` and the failure classification
        demonstrably originate in committed code.
- [ ] **S9-2** source-preflight implementation — code, **no network**
- [ ] **S9-L1** live source-preflight execution — **NETWORK**, verification-only, no commit —
      **UNAPPROVED and MANDATORY.** **E9-7** made the sequence offline-first: S9-3 (and S9-4) may
      precede it, but it must be **completed and reviewed before S9-L2 is approved** and before any
      real smoke runs. No offline checkpoint authorizes it.
- [x] **S9-3** bounded smoke and read-only run validation
      (`feat(harvest): add bounded smoke and run validation`) — code and offline tests only, **no
      outbound request**, **no real source contacted**, **no retained live root**. Eleven paths after
      a **ratified expansion**: `src/harvest/runvalidate.py` · `src/harvest/cli.py` ·
      `src/harvest/run_cells.py` · `tests/harvest/test_smoke.py` · `tests/test_taxonomy_smoke.sh` ·
      `tests/harvest/test_run_cells.py` · `tests/harvest/test_preflight.py` ·
      `tests/harvest/test_cli.py` · `scripts/validate_task.sh` · the plan · this file.
      - **`RunBounds` is frozen and validated at construction** — int caps ≥ 1 (a `bool` is refused),
        accepted ≤ candidates, finite positive budget. `run()` gains **only** `bounds=None` and
        `run_id_value=None`, keyword-only; there is no independent `max_candidates`, `max_accepted`
        or `smoke_budget` parameter, just as there is none for opener/sleep/lease-root.
      - **The candidate cap slices before classification**, so a capped-out candidate gets no
        classification, no facets, no record and **no rejection row** — unprocessed is not rejected.
        It caps judgement, never traffic: discovery and the committed request budgets are untouched.
        **The accepted cap keeps the deterministic prefix** ending at the Nth accepted candidate;
        verdicts are preserved, nothing relabelled, no reason invented, and
        `accepted + rejected == candidates` holds over the processed set. Measured: the uncapped cell
        accepts 4; capped to 2 it reports 2 accepted with **fewer** rejections, never more.
      - **The smoke budget is command-wide.** `time.monotonic()` starts before the integrated
        preflight, the elapsed time is subtracted, and the run phase gets only the remainder as a
        committed `run` time scope checked **before and after every cell**. Expiry aborts before the
        write phase: **no manifest, no pointer movement, previous runs untouched.** A preflight that
        consumes the whole budget is refused before the run starts. No new timeout was implemented.
      - **`config.bounds` carries the three smoke keys only when they were enforced**; omitted bounds
        reproduce the committed two-key block byte-for-byte, and `elapsed_before_run_sec` is never
        reported — the configured budget is a stable fact, how much preflight used is not.
      - **`smoke --state-root PATH [--no-enrich] [--max-candidates N] [--max-accepted N]
        [--run-id ID]`** — caps may only **narrow** the policy values; every argument, the external
        root and a finished-run clash are decided **before any transport is built**. Prints one
        deterministic timestamp-free summary; exit **0** only on complete publication (42 JSON with
        the pointer naming the run), non-zero otherwise, **2** on argument misuse. A failed run
        publishes no manifest and partial artifacts are left as **evidence**, not deleted.
      - **`validate --state-root PATH --run-id ID`** — offline, read-only, repairs nothing.
        `runvalidate.py` (**E9-8**, the read-only owner: cli parses, run_cells writes, runvalidate
        validates) imports no HTTP/adapter/judgement owner, has no write or repair call, and opens
        every file read-only — all AST-asserted. Enforces **E9-11**: 42 JSON = **18 selected-run + 24
        shared**, so a second run adds 18 and updates the same 24 rather than making 84. Checks all
        42 schemas, run-id agreement, count relations, `alias_conflicts_count`, mode/enrich/bounds/
        eligibility, 25 sorted preflight rows, pointer consistency, and `.tmp_*` debris anywhere.
        Exit **0** valid, **1** invalid after printing the report, **2** on argument misuse.
      - **Two production defects found by these tests and fixed:** `RunValidateError` and
        `RunCellsError` escaped `main()` as tracebacks instead of exit 2, and `argparse`'s
        `SystemExit` escaped, breaking `main()`'s promise to return an exit code rather than raise.
      - **Four spent snapshots retired across three suites.** E9-9 anticipated two
        (`test_run_cells.py`'s `bounds`-absent guard, `test_preflight.py`'s S9-2 registry snapshots)
        and **missed the same `bounds` guard duplicated in `test_cli.py`** — the checkpoint stopped
        without committing and reported, and the one-path expansion was ratified so S9-3 stays **one
        atomic commit** instead of splitting production from the guard corrections it forces. The
        duplicate was **deleted**, not replaced: the permanent `run()` contract belongs to
        `test_run_cells.py` alone. `test_cli.py`'s live-transport AST scan was **over-broad since
        S9-1** — it walked `tree.body` meaning "module-level execution" but `ast.walk` descends into
        function bodies, so it rejected calls inside function *definitions*, which is not execution.
        Corrected to distinguish module-level execution · inert and refused paths (including refused
        `smoke`/`validate` arguments, which must fail **before** the network decision) · approved
        registered handlers. **No production code was altered to fool either scan**, no handler was
        hidden outside `COMMANDS`, and **no exact command-count snapshot was introduced.**
      - **One defect in the S9-3 suite itself, fixed:** `TestFullOfflineSmoke` stranded a whole
        43-path run tree in the system temp directory when `setUpClass` failed partway, since
        `tearDownClass` does not run then. Switched to `addClassCleanup`, and the wrapper now fails
        on any leaked `s93_*` root — a guard the suite owns cannot catch the suite crashing.
      - **Focused validation only, 453 assertions green:** smoke **57** · cli **58** · preflight
        **65** · run_cells **99** · recovery **74** · manifest **52** · eligibility **48**; plus
        `py_compile` ×7 and one explicit-mode harness sample at **exit 0** with **five wrappers each
        exactly once**, **zero `WARN - skipping`**, zero FAIL. **`--all` was NOT run.**
      - **Harness: 60 → 61 wrappers** (19 legacy + **42** taxonomy), `ISOLATED[]` 60 → 61 with the
        committed 60 byte-identical as an **ordered prefix** (**E9-10**; 63 remains the post-S9-6
        figure). `runvalidate.py` → smoke; `cli.py` → cli + preflight + smoke; `run_cells.py` →
        run_cells + recovery + cli + smoke. No future-wrapper target, no aggregate, no blanket arm.
- [ ] **S9-4** `compare-runs` and `diff --run-id` implementation — code, **no network**
- [ ] **S9-L2** first bounded live smoke — **NETWORK**, verification-only, no commit · **this is M2**
- [ ] **S9-L3** second bounded live smoke + normalized comparison — **NETWORK**, no commit
- [ ] **S9-5** live-corpus calibration decision — documentation only; **no config or code change**
      (a correction needs its own approved `S9-5C` under the CF-6 committed-tree procedure)
- [ ] **S9-6** linkcheck implementation — code, **no network**
- [ ] **S9-L4** bounded live linkcheck execution — **NETWORK**, no commit
- [ ] **S9-C** Stage 9 closeout — documentation only; push and memory sync remain separate approvals

**S9-0, S9-1, S9-2 and S9-3 are complete. Stage 9 is NOT complete.** **S9-L1 remains mandatory and
unapproved** — **E9-7** reorders it after S9-3/S9-4 but it still gates S9-L2 — and **S9-4 and every
later checkpoint remain unapproved.** `preflight-sources`, `smoke` and `validate` are implemented but
**none has ever contacted a real source**; no outbound request has ever been made by this pipeline;
no retained external Stage 9 state root exists or has been selected; **live operation remains zero
and M2 is unmet**. Each remaining checkpoint needs
its own approval by name with its exact allowed-path set; every live execution needs approval twice,
the second immediately before the outbound request.

## Stage 10 — final report ⟵ **NOT OPEN.**

**Stage 10 creates no JSON and publishes nothing.** It is two markdown documents. "Stage 10 — final"
does not mean "final delivery".

- [ ] `docs/harvest/IMPLEMENTATION_REPORT.md` — every file created/changed, exact commands, results
- [ ] `docs/harvest/CONVERGENCE_NOTE.md` — 5 gates before matrix unification is reconsidered
- [ ] Unresolved issues, limitations, blocked sources, recommended follow-up

## After Stage 10 — additional production milestones, none opened or owned

Closing Stages 9 and 10 does **not** produce a published dataset. These four are separate
post-Stage-9 milestones, mostly undesigned; see `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §3 and §10.

- [ ] **M5 — production enriched run and human review.** Unowned (roadmap G4, G9). Stage 9's
      `--no-enrich` smoke output is explicitly disqualified from promotion by
      `IMPLEMENTATION_PLAN.md` §7.1, and human review has no artifact, schema or acceptance process
- [ ] **M6 — production promotion into `data/harvested/`.** Unowned (roadmap G7). Designed in detail
      in `IMPLEMENTATION_PLAN.md` §7; **zero lines implemented**. Listed above under Stage 6, where
      plan §14 erratum E11 descoped it. Expected stable published set: **16 JSON files** (12 category
      + 3 topic aggregates + 1 publication manifest) — **none of which exist**
- [ ] **M7a — website / downstream consumer integration.** Unowned, unscoped, outside this
      repository (roadmap G10)
- [ ] **M7b — recurring scheduling / refresh operation.** Undesigned; note the name collision with
      the legacy AX pipeline's `scripts/refresh.sh` (roadmap G6)

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
