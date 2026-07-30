# Stage 8 — harness wiring and full offline regression

**Status: S8-0 APPROVED AND COMPLETE. S8-1, S8-2 and S8-C are NOT APPROVED.**

```text
plan_of_record:        docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md   (this file)
approved_checkpoint:   S8-0 only — the documentation checkpoint that produced this file
start_anchor:          b9a08a33ff215ce226c885a7f70c97cd4974ccad   Stage 7 push-state record
predecessor:           docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md
origin:                CF-4, first recorded at STAGE_4_IMPLEMENTATION_PLAN.md §"Carried forward"
deliverable:           bash scripts/validate_task.sh --all runs all 58 committed shell
                       wrappers with zero skips and exits 0, fully offline
protected_baseline:    18/18 byte-identical to 8865c54e (unchanged by any Stage 8 checkpoint)
untracked_baseline:    508 files, drift 0 / missing 0 / extra 0 (unchanged by any checkpoint)
```

## 0 · What this document approves, and what it does not

**S8-0 is the only currently approved checkpoint.** It is documentation-only: it produced this
file and the Stage 8 section of `docs/harvest/TODO.md`, and nothing else.

**Committing this plan does not approve S8-1, S8-2 or S8-C.** A plan of record describes what
Stage 8 *would* do if each of its checkpoints were separately approved. It is a specification, not
an authorization. The rule that governed every checkpoint of Stages 2.5 through 7 does not lapse
because a plan now exists:

> **Every stage and every checkpoint needs its own approval by name, with an exact allowed-path set
> declared up front.** A completed predecessor, an approved plan and a green gate do not together
> authorize the next thing. If a path outside the set turns out to be required, stop and report
> rather than widening scope.

Concretely, and stated so no successor session can read this file as permission:

- **S8-1 (harness wiring) is unapproved.** `scripts/validate_task.sh` must not be edited until a
  human approves S8-1 by name and restates its allowed paths.
- **S8-2 (full offline regression) is unapproved**, and is verification-only when it is approved:
  it has no allowed write paths and produces no commit.
- **S8-C (closeout) is unapproved.**
- **A push is unapproved**, at every point, and remains a separate explicit approval after S8-C.

**Stage 8 contains none of the following, at any checkpoint:**

```text
network access            No checkpoint issues a request of any kind. Stage 8 adds no fetch, no
                          live model call, no remote git operation. This pipeline has never made a
                          live request and Stage 8 does not change that.
operational migration     No `migrate.sh ax-cases --apply` against the repository's default state
apply                     root. Apply is exercised only inside test_taxonomy_migration.sh, which
                          injects `--state-root` at every call site and proves it by AST scan of
                          its own source. Stage 8 runs that suite; it does not add a call site.
publication promotion     Nothing is promoted into data/harvested/, which remains absent.
retained runtime output   No state/taxonomy_harvest/ bundle, no runs/ tree, no LATEST_RUN_ID.
                          Their continued absence is asserted, not assumed — see §6.
```

**S6-L, Stage 6's bounded live smoke, remains unexecuted and unauthorized.** Stage 9 remains
unopened.

## 1 · Why Stage 8 exists

`CLAUDE.md` states that `scripts/validate_task.sh` is *"the single allowlisted, offline validation
entry point"*. It is not, for the taxonomy pipeline. The script contains zero occurrences of the
string `taxonomy`.

This was found and recorded during Stage 4, as **CF-4**:

> `scripts/validate_task.sh` contains zero taxonomy references, so CLAUDE.md's stated validation
> entry point exercises none of the 567 assertions — *`STAGE_4_IMPLEMENTATION_PLAN.md`, carried
> forward to Stage 8.*

The figure has since grown from 567 to **2,065**. The gap has a precise present-day shape, measured
against the committed tree at `b9a08a3`:

- `scripts/validate_task.sh --all` enumerates `tests/*.sh`, a flat glob that today matches **58
  files** — 19 legacy wrappers and 39 `tests/test_taxonomy_*.sh` wrappers.
- Every candidate is then filtered through `is_isolated()` against the `ISOLATED[]` allowlist.
  `ISOLATED[]` holds **19 basenames**, which is exactly the set of legacy wrappers.
- All **39 taxonomy wrappers are therefore WARN-skipped**, and a WARN does not set `FAIL`.

So `--all` is green today **while running none of the taxonomy work**. That is the defect Stage 8
closes. Nothing about the run is wrong; the harness is honest about skipping, in a line most
readers will not count. Stage 8 makes the skip count zero so that "green" and "complete" become the
same statement.

**Stage 8 changes no behavior of the pipeline it validates.** It is wiring: one production file,
plus the documentation that records it.

## 2 · The harness as committed — the contract S8-1 must not break

`scripts/validate_task.sh` is 133 lines, a single file, sourcing nothing. Line numbers below are
against `b9a08a3` and are given so S8-1 can be reviewed against a stated baseline rather than a
remembered one.

| Behavior | Owner | Contract S8-1 preserves |
|---|---|---|
| Shell / options | `#!/usr/bin/env bash`, `set -euo pipefail` (L18) | unchanged |
| Working directory | L19–20 derive `ROOT` from `$BASH_SOURCE`, then `cd "$ROOT"` | unchanged; every path stays repo-relative |
| Temp dir | L22 `WORK=$(mktemp -d)`, L23 `trap 'rm -rf "$WORK"' EXIT` | unchanged |
| Agent isolation | L24–30 write `$WORK/mock_claude.sh` (exit 97) and export `CLAUDE_BIN` | unchanged |
| State redirection | L31 exports `STATE_DIR="$WORK/state"` | unchanged |
| Modes | L59–66: `changed` (default), `all` (only when `--all` is `$1`), `explicit` | unchanged — **no argument-parser change** |
| Lint dispatch | L74–78: `bash -n` / `py_compile` / `jq empty` by extension | unchanged |
| Case table | L79–95, 16 arms mapping a changed production file to `add_test` calls | **extended** (§4) |
| De-duplication | L70 `add_test`, substring match on `" ${TESTS[*]} "` — **path-string-exact** | unchanged, and relied upon (§4.1) |
| `--all` enumeration | L97 `for t in tests/*.sh; do add_test "$t"; done` | unchanged |
| Allowlist | `ISOLATED[]` L37–47 + `is_isolated()` L48–52, basename exact match | **extended** (§3) |
| Skip semantics | L101–105 print `WARN - skipping …`; a WARN does not set `FAIL` | unchanged mechanically; **the skip count becomes 0** |
| Execution | L118 `bash "$t"`, one direct child per wrapper, **serial** | unchanged — **no concurrency** |
| Failure propagation | `run()` L55–57 sets a sticky `FAIL=1`; every test still runs | unchanged — **sticky `FAIL=1` preserved** |
| Exit code | L132 `exit "$FAIL"` — 1 for any number of failures | unchanged — **no summary counter** |
| Output | unbuffered, unredirected, uncaptured, untruncated | unchanged |
| Production-state proof | `snapshot_state()` L108–115, compared L116/L120–127, never auto-restores | **extended** (§6) |
| Timeouts | none | unchanged — **none added** |
| Network | none | unchanged |

Two properties of the committed script that S8-1 must understand rather than "fix":

- **`A && { B; }` at L60, L97 and L129 does not trip `set -e`.** A failed left operand of `&&` is
  exempt from `set -e`. The current behavior is correct and must not be rewritten into `if`.
- **`snapshot_state()`'s `find state -type f` sees gitignored files.** `.gitignore` contains
  `/state/taxonomy_harvest/`, so `git status -- state/` cannot see a leaked migration bundle but
  the content-hash snapshot can. This is the harness's strongest existing containment guarantee and
  §6 extends it rather than replacing it.

### 2.1 · What `ISOLATED[]` actually means

`ISOLATED[]` is **an audited allowlist of basenames, and nothing else.** It confers no isolation.

Every member of `SAFE[]` runs identically — `bash "$t"` as a direct child, same cwd, same inherited
environment, serially. Membership changes exactly one thing: whether a wrapper is **executed** or
**WARN-skipped**. There is no subprocess sandbox, no temporary worktree, no environment reset, no
separate scheduling class, and no path-resolution change.

What the list *records* is the claim in the script's own header (L33–36): each listed test *"was
inspected and confirmed to run under a temp dir / temp `STATE_DIR` with a mock or `false`
`CLAUDE_BIN`, contact no real remote, and never write the production `state/` dir."* It is an
auditor's assertion, enforced downstream by the before/after `state/` snapshot.

This distinction matters for two S8-1 decisions:

- Adding all 39 wrappers **duplicates no isolation**, because the list performs no work. The 39
  wrappers already own their own isolation: each derives `ROOT` itself, each writes only under its
  own `mktemp -d` or injected `--state-root`, and each asserts afterwards that production `state/`
  (and, in 33 of 39, `config/`) is unmodified.
- `ISOLATED[]` membership and case-table routing are **independent**. Membership decides *whether a
  wrapper may run at all*; the case table decides *which wrappers a changed file selects in
  `changed` and `explicit` modes*. Under `--all` the case table is not consulted, so `--all`
  correctness depends only on §3.

## 3 · Decision — wire all 39 wrappers individually

**Decision: all 39 existing `tests/test_taxonomy_*.sh` basenames are added to `ISOLATED[]`
individually. No aggregate taxonomy-gate wrapper is created. No existing taxonomy wrapper is
modified.**

### 3.1 · Why individually, and not an aggregate gate

| Criterion | 39 individual entries | one aggregate gate wrapper |
|---|---|---|
| Failure localization | `FAIL - offline tests/test_taxonomy_pool.sh` names the suite | one status line for 2,065 assertions |
| Duplicate execution | none possible | the new file is either matched by the `tests/*.sh` glob **and** invoked internally — every suite twice — or must be named outside the glob, inventing a naming exception |
| Isolation | each wrapper already self-isolates | one process wrapping 39, hiding which one leaked |
| Runtime | 39 interpreter starts | the same 39, plus a shell |
| Output clarity | 39 `ok` lines interleaved with each suite's `-v` output | identical output volume, one status |
| Harness compatibility | native — `ISOLATED[]` *is* a basename allowlist, and the 19 legacy wrappers are wired exactly this way | requires a concept the harness does not have |
| Diff size | one array extension | a new file plus glob-exclusion logic |

Individual wiring is not merely convenient; it is **the pattern the harness already uses**, and it
is the pattern the wrappers were built for. Five taxonomy wrappers say so in their own headers, in
committed bytes:

> *"Thin wrapper so `scripts/validate_task.sh` (which only executes `tests/*.sh` from its audited
> allowlist) can run the python suite, matching the existing `tests/test_github_meta.sh` pattern."*
> — `tests/test_taxonomy_identity.sh`, and in the same words `test_taxonomy_schema.sh`,
> `test_taxonomy_budget.sh`, `test_taxonomy_http.sh`, `test_taxonomy_domain_throttle.sh`

The 39 wrappers exist *because* of this Stage 8 wiring. Building an aggregate gate now would
discard the reason they were written one-per-suite.

### 3.2 · The exact 39 basenames S8-1 adds

Appended to `ISOLATED[]` as a clearly commented block, leaving the existing 19 entries untouched
and in their current order:

```text
test_taxonomy_adapter_concurrency.sh   test_taxonomy_adapters.sh
test_taxonomy_aliases.sh               test_taxonomy_artifacts.sh
test_taxonomy_budget.sh                test_taxonomy_cell_artifact.sh
test_taxonomy_classify.sh              test_taxonomy_config.sh
test_taxonomy_coverage.sh              test_taxonomy_coverage_report.sh
test_taxonomy_customer_interaction.sh  test_taxonomy_dedupe.sh
test_taxonomy_domain_throttle.sh       test_taxonomy_eligibility.sh
test_taxonomy_extract.sh               test_taxonomy_facet_ambiguity.sh
test_taxonomy_facet_identity.sh        test_taxonomy_facet_states.sh
test_taxonomy_facetassign.sh           test_taxonomy_facets.sh
test_taxonomy_http.sh                  test_taxonomy_identity.sh
test_taxonomy_ledger.sh                test_taxonomy_manifest.sh
test_taxonomy_migration.sh             test_taxonomy_pool.sh
test_taxonomy_protected_baseline.sh    test_taxonomy_records.sh
test_taxonomy_recovery.sh              test_taxonomy_run_cells.sh
test_taxonomy_schema.sh                test_taxonomy_source_cache.sh
test_taxonomy_target_accounting.sh     test_taxonomy_target_determinism.sh
test_taxonomy_target_evidence.sh       test_taxonomy_target_fetch.sh
test_taxonomy_target_fixtures.sh       test_taxonomy_target_ownership.sh
test_taxonomy_verify.sh
```

`ISOLATED[]` becomes **58 entries**, matching the 58 files `tests/*.sh` matches. Every entry is a
basename, because `is_isolated()` compares `basename "$1"`.

### 3.3 · The audit that justifies membership

Each of the 39 satisfies the criterion the header states, established from committed bytes:

- **Uniform structure.** All 39 are `set -uo pipefail`; all derive `ROOT` and `cd "$ROOT"`; 37
  delegate to exactly one `python -m unittest discover -s tests/harvest -p '<module>' -v`, capture
  `EC=$?`, run epilogue guards and `exit "$EC"`. Two are shell-native
  (`test_taxonomy_config.sh`, `test_taxonomy_protected_baseline.sh`).
- **No production `state/` write.** All 39 assert `git status --porcelain --untracked-files=no` is
  empty afterwards — 32 over `state/ config/`, 6 over `state/` alone, and
  `test_taxonomy_config.sh` over `config/` alone.
- **No repository runtime write.** 16 of 39 additionally assert the runtime paths do not exist: 12
  check `state/taxonomy_harvest data/harvested runs LATEST_RUN_ID`, 4 check the first three. The
  remaining 23 write nothing outside their own temp directory. §6 makes this guarantee uniform at
  the harness level rather than depending on which wrapper happens to carry the loop.
- **No remote contact.** `tests/harvest/test_source_cache.py` AST-bans
  `urllib requests httpx aiohttp socket http` from the cache module.
  `test_taxonomy_domain_throttle.sh` binds a **local** recording HTTP server on loopback; it issues
  no outbound request.
- **No `CLAUDE_BIN` use.** No taxonomy wrapper or module invokes an agent, so the mock at L30 is
  inert for them — correct, and not relied upon.
- **No default-root migration apply.** `test_taxonomy_migration.sh` injects `--state-root` at every
  apply, deletes that root before its assertions, and proves by AST scan of its own source that no
  call site passes `--apply` without one.

### 3.4 · Cross-suite interaction that S8-1 accepts and S8-2 must read correctly

The 16 runtime-leak epilogues run in repo-root cwd, **after** their own suite. Under `--all`, in
glob order, they therefore become cross-suite guards: if an earlier wrapper leaked a runtime path,
a later wrapper fails and names itself.

This is a **failure-attribution hazard, not a correctness defect** — the leak is still caught, just
attributed to the wrong suite. §6's harness-level pre/post check is the resolution: it brackets the
whole run, so a leak is reported once, by the harness, in addition to whichever wrapper trips.
S8-1 does not modify the wrappers to fix attribution.

## 4 · Decision — the exact case-table extension

The case table serves `changed` and `explicit` mode only; `--all` never consults it. It is
nevertheless part of Stage 8 because `TODO.md` names it ("new tests in the case table and
`ISOLATED[]`") and because a wired allowlist with an empty table would leave taxonomy work
unvalidated in the mode this repository actually uses day to day.

### 4.1 · Mapping principle: ownership, not import fan-out

A map built from the import graph is unusable. Measured over the committed tree,
`src/harvest/schema.py` is imported by 25 of the 39 suites and `src/harvest/urlkey.py` by 17;
routing by imports would run most of the gate for almost any change and would be the "run all 39
for every change" fallback in disguise.

The mapping below therefore routes each production file to its **owner suite** — the dedicated
wrapper whose declared subject is that file's contract — plus any suite that committed evidence
shows **directly drives that file as its subject**, not merely as a collaborator or fixture
builder. This is the same principle the 16 committed legacy arms use: `scripts/lib/clean_json.sh`
routes to `tests/test_clean_json.sh` alone, while the `harvest_entities.sh` orchestrator routes to
eight suites because eight suites drive it.

Ownership was established from committed bytes, not inferred: each wrapper's header states its
subject (`test_taxonomy_classify.sh — the ten committed precedence rules (S4-3)`), and each
config/schema file's consumers were traced through `src/harvest/**` and `scripts/harvest/**`.

**Every target is spelled `tests/<name>.sh`** — byte-identical to what the `tests/*.sh` glob emits
at L97. `add_test`'s de-duplication is a substring match on the exact path string, so
`./tests/x.sh` and `tests/x.sh` would both be added and the suite would run twice. Canonical
spelling is what makes "at most once per invocation" true.

### 4.2 · `src/harvest/**` — core modules

| Case pattern | Wrappers added | Evidence |
|---|---|---|
| `src/harvest/adapters/*.py` | `adapters`, `adapter_concurrency` | the only two adapter suites; both glob `config/harvest/topics/*.json` and drive `base/feed/jsonapi/seed` |
| `src/harvest/aliases.py` | `aliases`, `eligibility` | `aliases` owns S6-3 redirect/rel=canonical adjudication; `eligibility` is titled "alias conflicts and the ≤8 eligibility proof (S6-6)" |
| `src/harvest/artifacts.py` | `artifacts`, `cell_artifact`, `ledger`, `coverage_report`, `manifest` | `artifacts` owns the S5-1 atomic writer; S5-2/3/4/5 each own one document family written through it and assert its behavior via that document |
| `src/harvest/budget.py` | `budget` | sole dedicated suite for request-count and wall-clock caps |
| `src/harvest/classify.py` | `classify` | owns the ten committed precedence rules (S4-3) |
| `src/harvest/coverage.py`, `src/harvest/scheduler.py` | `coverage`, `coverage_report` | `coverage` is titled "coverage targets, gap ranking, adaptive scheduling", which is `scheduler.py`'s whole surface; `coverage_report` is the S5-4 wiring |
| `src/harvest/dedupe.py` | `dedupe` | owns deterministic ingest and same-topic dedupe |
| `src/harvest/domainlease.py` | `domain_throttle`, `http` | `domain_throttle` owns the cross-process cap; `httpclient.py` is `domainlease.py`'s only production consumer besides `sourcecache.py` |
| `src/harvest/extract.py` | `extract` | owns deterministic metadata normalization (S4-2) |
| `src/harvest/facetassign.py` | `facetassign` | owns deterministic `case_facets` assignment (S4-5A) |
| `src/harvest/facets.py` | `facets`, `facet_ambiguity`, `facet_identity`, `facet_states`, `customer_interaction` | the five facet-contract suites; each is titled for one property of the vocabulary this module loads |
| `src/harvest/fixtures.py` | `adapters`, `source_cache`, `target_fixtures` | the offline fixture opener; `test_source_cache.py` asserts it exists as a Stage 4B deliverable, and the adapter/target-fixture suites read through it |
| `src/harvest/httpclient.py` | `http`, `domain_throttle` | `http` owns robots/redirects/timeouts/retries/byte caps; `domain_throttle` measures the cap through this client |
| `src/harvest/ledger.py` | `ledger` | owns the S5-3 rejection log and URL ledger |
| `src/harvest/migrate/*.py` | `migration` | the sole Stage 7 suite; nothing else imports `migrate/` |
| `src/harvest/pool.py` | `pool` | owns request keys, shared snapshots, ownership accounting |
| `src/harvest/records.py` | `records`, `schema` | `records` owns S4-5B in-memory construction; `schema` owns the discriminated union it is validated against |
| `src/harvest/request_key.py` | `pool`, `dedupe` | `pool`'s title names request keys; `dedupe` is the other direct consumer |
| `src/harvest/run_cells.py` | `run_cells`, `recovery` | `run_cells` owns the S5-6 driver; `recovery` is S5-7 re-run semantics over the same driver |
| `src/harvest/schema.py` | `schema`, `records` | the validator and its principal subject |
| `src/harvest/slug.py` | `facet_identity`, `facets`, `config` | the only three suites that reference slug generation directly |
| `src/harvest/sourcecache.py` | `source_cache` | owns the run-scoped source fetch cache |
| `src/harvest/targetfetch.py` | `target_fetch`, `target_ownership`, `target_evidence`, `target_accounting`, `target_determinism` | the five dedicated Stage 6 target suites (S6-2, S6-4, S6-5, S6-6A, S6-7), each driving this module as its subject |
| `src/harvest/urlkey.py` | `identity`, `aliases`, `facet_identity` | `identity` owns canonicalization and identity stability; `aliases` adjudicates against it; `facet_identity` exists to prove facets cannot move `record_id` |
| `src/harvest/verify.py` | `verify` | owns the four committed scores and the accept/reject gate |

### 4.3 · `scripts/harvest/**` — CLI and checkers

| Case pattern | Wrappers added | Evidence |
|---|---|---|
| `scripts/harvest/migrate.sh` | `migration` | the CLI that suite drives end to end |
| `scripts/harvest/check_config.py` | `config` | `test_taxonomy_config.sh` invokes it as `CHECK` |
| `scripts/harvest/check_facets.py` | `facets`, `migration` | `facets` owns the vocabulary; `test_taxonomy_migration.sh` validates every migrated record against the committed `check_facets.py` |
| `scripts/harvest/check_fixtures.py` | `source_cache`, `target_fixtures`, `adapters` | referenced by `test_source_cache.py`, `test_target_fixtures.py`, `test_target_determinism.py`; `adapters` is the third fixture consumer |
| `scripts/harvest/gen_facet_schema.py` | `facets`, `facetassign` | generates `facets.generated.v1.json`, which `facetassign` validates against |
| `scripts/harvest/protected_baseline.py`, `gen_protected_baseline.sh`, `verify_protected_baseline.sh` | `protected_baseline` | the sole suite for the baseline generator and verifier |

### 4.4 · `config/harvest/**`

| Case pattern | Wrappers added | Evidence |
|---|---|---|
| `config/harvest/topics/*.v1.json` | `config`, `adapters`, `adapter_concurrency` | `check_config.py` is the completeness authority; both adapter suites glob `config/harvest/topics/*.json` |
| `config/harvest/facets/*.v1.json` | `facets`, `facet_ambiguity`, `facet_states`, `facet_identity`, `customer_interaction`, `facetassign` | all four vocabulary files are loaded by `src/harvest/facets.py`; these six suites own the vocabulary's contracts |
| `config/harvest/precedence.v1.json` | `classify` | the ten precedence rules; `classify` is the only suite that owns them |
| `config/harvest/policy.v1.json` | `verify` | the four score weights and thresholds |
| `config/harvest/coverage_targets.v1.json` | `coverage`, `facets` | read by `coverage.py`, `scheduler.py`, `facets.py` and `check_facets.py` |
| `config/harvest/canonicalization.v1.json` | `aliases`, `pool` | read by `aliases.py` and `request_key.py`; those are the two suites that assert it |
| `config/harvest/migration_overrides.v1.json` | `migration` | the S7-4 review shape |
| `config/harvest/watchlists/*.v1.json` | `config` | see §4.6 — no consumer exists; `check_config.py` is its only authority |

### 4.5 · `schemas/harvest/**`

| Case pattern | Wrappers added | Evidence |
|---|---|---|
| `schemas/harvest/record.v1.json` | `schema`, `records` | the discriminated union and its builder |
| `schemas/harvest/taxonomy.v1.json` | `config` | the config's own schema |
| `schemas/harvest/facet_vocabulary.v1.json`, `facets.generated.v1.json` | `facets`, `facetassign` | the vocabulary schema and its generated constraints |
| `schemas/harvest/cell_artifact.v1.json`, `topic_artifact.v1.json` | `cell_artifact` | the S5-2 document families |
| `schemas/harvest/ledger.v1.json`, `rejection.v1.json` | `ledger` | the S5-3 document families |
| `schemas/harvest/run_manifest.v1.json` | `manifest` | the S5-5 manifest and `LATEST_RUN_ID` |
| `schemas/harvest/coverage_report.v1.json` | `coverage_report` | the S5-4 document |
| `schemas/harvest/alias_conflict.v1.json` | `aliases`, `eligibility` | the S6-3 conflict document and the S6-6 proof that consumes it |
| `schemas/harvest/candidate_pool.v1.json`, `discovery_lane.v1.json` | `pool` | both read by `pool.py` and asserted by `test_pool.py` alone |

### 4.6 · Taxonomy-owned paths deliberately **omitted** from changed-mode dispatch

Each omission is a decision with a reason, not an oversight.

- **`src/harvest/__init__.py`, `src/harvest/adapters/__init__.py`,
  `src/harvest/migrate/__init__.py`.** Package plumbing with no behavioral surface. Any change that
  matters lands in a sibling module that is mapped; mapping the `__init__` files would attach a
  suite selection to a re-export edit.
- **`scripts/harvest/hash_tree.py`.** Traced across `src/harvest/**`, `scripts/harvest/**` and
  `tests/**`: it has **zero consumers**. No committed suite exercises it. Mapping it to any wrapper
  would invent coverage that does not exist. It is left unmapped, and this omission is recorded
  rather than hidden.
- **`config/harvest/watchlists/oss-milestones.v1.json`.** Same trace, same result: **zero
  consumers** in production code or tests. It is routed to `config` only, because
  `check_config.py` is the sole committed authority that reads the configuration tree for
  completeness. No behavioral suite is claimed for it.
- **`tests/harvest/*.py` and `tests/fixtures/harvest/**`.** These are test implementations and test
  inputs, not production surfaces. Editing `tests/harvest/test_pool.py` will not select
  `tests/test_taxonomy_pool.sh` in `changed` mode. This is a real limitation and is stated so a
  reader does not assume otherwise; routing test files is outside the production/migration/schema/
  config surface this checkpoint covers, and would be a **separate approved deviation** if wanted.
  `--all` covers them unconditionally, and `changed` mode still lints them (`py_compile`).
- **`config/harvest/facets/legacy_industry_map.v1.json` → `migration`.** Consumed by
  `migrate/ax_cases.py`, so it is arguably a migration surface too. It is left in the
  `config/harvest/facets/*.v1.json` arm and **not** additionally routed to `migration`, because
  `migration` is the single most expensive suite (250 assertions) and the facet suites already
  cover the file's own contract. Recorded here as a knowingly narrow choice.

### 4.7 · No blanket fallback

**No "run all 39 for any repository change" arm is added.** A narrower correct mapping exists and
is specified above, so the condition under which a fallback would be permitted is not met. Every
one of the 39 wrappers appears at least once in §4.2–§4.5, so the mapping is complete over the
suite set as well as over the production surface.

## 5 · Decision — what "full offline regression" means

**Definition: `bash scripts/validate_task.sh --all` exits 0, all 58 committed wrappers execute
exactly once, and the run emits zero `WARN - skipping` lines.**

The skip count is load-bearing. `--all` is *already* green today while skipping 39 suites, so exit
0 alone distinguishes nothing. The pair — exit 0 **and** zero skips — is what changes state between
before and after.

### 5.1 · Planning figures, and which of them become assertions

Committed figures, used as planning evidence:

```text
wrappers under tests/*.sh        58   (19 legacy + 39 taxonomy)
taxonomy gate at Stage 7 close   39/39 suites — 2,023 unittest + 42 shell = 2,065
                                 (shell: config 18 + protected baseline 24)
matrix regression                64 assertions   IMPLEMENTATION_PLAN.md, matrix compatibility gate
parallel regression              62 assertions   2026-07-22 parallel-harvest report
```

**These counts are planning evidence, not production assertions.** In particular, S8-1 adds **no**
assertion on the total Python method count. A static count of `def test_` in `tests/harvest/**`
yields 2,019 against a committed figure of 2,023 — the difference being subtest and parametrized
expansion — which is exactly why such a number makes a brittle gate. Pinning it would create a
check that fails on an honest test addition and says nothing about correctness.

**The hard closing assertions are, and are only:**

1. exit code 0;
2. zero `WARN - skipping` lines;
3. all 58 wrappers executed, each exactly once;
4. the captured matrix summary line contains `64 passed, 0 failed`;
5. `tests/test_parallel_harvest.sh` executed and passed;
6. protected baseline 18/18;
7. untracked baseline 508/508, drift 0 / missing 0 / extra 0;
8. tracked worktree and index unmodified;
9. all four runtime paths absent.

### 5.2 · How matrix 64 is verified

`tests/test_matrix_harvest.sh` prints its own summary as its last line:

```text
== test_matrix_harvest.sh: 64 passed, 0 failed ==
```

That runtime counter is the only source of the figure; it is asserted nowhere in the repository,
and `validate_task.sh` neither parses nor preserves it.

**Decision: the figure is verified by reading captured `--all` output. `validate_task.sh` is not
changed to parse, count or summarize anything.** Adding a parser would put a second, divergent
definition of "how many matrix assertions there are" into the harness.

**Decision: `tests/test_matrix_harvest.sh` and `tests/test_parallel_harvest.sh` are not modified.**
Both are among the 18 protected files, listed in `tests/fixtures/taxonomy/protected_paths.txt`
under *"mandatory regression gates: must stay byte-identical"*. The parallel regression stays in
`ISOLATED[]` and therefore stays part of `--all`.

**Operational constraint on capture.** `.claude/hooks/guard_command.py` classes `validate_task.sh`,
`safe_push_main.sh` and any `test_*.sh` as PROTECTED, and blocks piping a PROTECTED command's live
output into `head|tail|grep|sed|awk|tee`. S8-2 must therefore **redirect to a file outside the
repository and then inspect that file** — never pipe. (A second, cosmetic guard interaction: a
command containing both the word `clean` and a flag matching `-[A-Za-z]*[fdx]`, which
`--untracked-files=no` does, trips the `git clean` heuristic. Phrase closing commands to avoid it.)

### 5.3 · `--all` contains the taxonomy gate

After S8-1, `--all` globs `tests/*.sh`, a strict superset of `tests/test_taxonomy_*.sh`, and runs
each match once as `bash "$t"` — byte-identically to the manual loop.

**Decision: the closing regression is `bash scripts/validate_task.sh --all` alone.** Running
`for t in tests/test_taxonomy_*.sh; do bash "$t"; done` in addition would execute all 39 suites a
second time for no additional information. Assertion 2 of §5.1 — zero skips — is precisely what
proves containment, and is the only thing the second loop would otherwise tell you.

**Decision: the standalone taxonomy loop remains documented, for taxonomy-focused development
only.** It is not an additional Stage 8 closing run.

## 6 · Decision — harness-level runtime-path absence

**Decision: S8-1 adds a pre/post absence check, at harness level, for exactly four paths:**

```text
state/taxonomy_harvest/     gitignored (`.gitignore`: /state/taxonomy_harvest/)
data/harvested/             not ignored
runs/                       not ignored
LATEST_RUN_ID               not ignored
```

Why the harness needs this even though 16 wrappers already check:

- **Coverage is not uniform.** 12 wrappers check all four, 4 check three (omitting
  `LATEST_RUN_ID`), and 23 check none. A reader would reasonably assume the guarantee is uniform;
  it is not.
- **Attribution is wrong under `--all`.** A wrapper's epilogue runs after its own suite in
  repo-root cwd, so an earlier suite's leak is reported by a later suite (§3.4).
- **The existing harness check does not reach three of the four.** `snapshot_state()` covers
  `state/**` only. `data/harvested/`, `runs/` and `LATEST_RUN_ID` sit at repository root, outside
  it. They are not gitignored, so they would eventually surface as untracked drift — but nothing in
  the harness looks, and the untracked baseline is checked by a separate tool.
- **`git status` cannot see the first one.** `/state/taxonomy_harvest/` is gitignored, which is why
  the wrappers use `[ -e ]` rather than porcelain. The harness check must use `[ -e ]` too.

The check brackets the whole run — once before the first wrapper, once after the last — and on
detection sets the existing sticky `FAIL=1` and reports the offending path. It **does not delete
anything**, matching the existing `state/` snapshot's deliberate refusal to auto-restore: a leak is
evidence, and removing it destroys the evidence.

This is the only behavioral addition in Stage 8. It is in scope because "no retained runtime
output" is a Stage 7 closing invariant that Stage 8 must preserve while running, for the first
time, every suite capable of producing one.

## 7 · Decisions of record

Recorded here so no successor session re-litigates them, and so a deviation is visible as a
deviation:

```text
D1   All 39 taxonomy wrappers are wired individually.                            §3
D2   No aggregate taxonomy-gate wrapper is created.                              §3.1
D3   Existing taxonomy wrappers are NOT modified — not one byte.                 §3
D4   All 39 enter ISOLATED[], bringing it to 58 entries.                         §3.2
D5   Each wrapper runs at most once per harness invocation; canonical
     `tests/<name>.sh` spelling is what makes add_test de-duplication hold.      §4.1
D6   "Full offline regression" = --all exits 0, 58 wrappers executed, 0 skips.   §5
D7   Matrix 64 is verified from captured output. validate_task.sh is NOT
     changed to parse, count or summarize it.                                    §5.2
D8   tests/test_parallel_harvest.sh remains in ISOLATED[] and part of --all.
     Both it and test_matrix_harvest.sh stay byte-identical (protected).         §5.2
D9   The harness checks the four runtime paths before AND after the run,
     with [ -e ], and never deletes what it finds.                               §6
D10  --all is the Stage 8 closing gate and contains the taxonomy gate.           §5.3
D11  The standalone taxonomy loop stays documented for focused development
     only; it is NOT an additional closing run.                                  §5.3
D12  A domain-throttle failure is an unresolved diagnostic, never an accepted
     permanent flake.                                                            §9.3
D13  The case table routes by OWNERSHIP, not import fan-out; no blanket
     "run all 39" fallback is added.                                             §4.1, §4.7
D14  Planning figures (2,065 / 64 / 62 / 58) are evidence. Only the nine
     hard assertions in §5.1 gate the close. No total-method-count assertion.    §5.1

NOT part of Stage 8, by decision:
D15  No harness self-test (tests/test_validate_task.sh is NOT created).
D16  No baseline or fixture change.
D17  No CLAUDE.md change — including at closeout.
D18  No Python/jq/bash version gate. Observed at planning time: python 3.13.9,
     jq 1.8.2, bash 5.3.9. Recorded as environment, not asserted.
D19  No timeout, no summary counter, no argument-parser change, no concurrency.
D20  No network access, no operational migration apply, no promotion.
D21  No separate intentionally-failing test commit; S8-1 is one green commit.
```

**D15 rationale.** The preflight audit found no `tests/test_validate_task.sh` and no assertion
anywhere in `tests/` that enumerates test names, counts, case-table length or the `ISOLATED[]` set
— so S8-1 breaks no existing assertion, and a self-test is not needed to protect one. A harness
contract test (pinning "zero unexpected skips under `--all`") has independent merit and would guard
against a future wrapper being added without an `ISOLATED[]` entry and silently skipped forever.
**It is deliberately excluded from Stage 8** and would require an approved plan deviation. It is
recorded in §11 as a successor candidate rather than dropped.

**D17 rationale.** `CLAUDE.md:47` calls `validate_task.sh` *"the single allowlisted, offline
validation entry point"* — a claim that becomes true for the taxonomy pipeline only after S8-1, and
which `CLAUDE.md` never qualifies because it does not mention the taxonomy pipeline at all.
Updating it is therefore defensible, and it was raised as a candidate. It is excluded so that S8-C
matches the committed three-path closeout precedent exactly (`0d2da64` S6-C, `6bf7f51` S5-C,
`5fd9f91` S4-C each changed a plan, `TODO.md` and one new handoff). Recorded in §11.

## 8 · Checkpoints

Each checkpoint below states its purpose, its **exact allowed-path set**, its risk tier, its
validation and its commit boundary. **Only S8-0 is approved.** The path set of an unapproved
checkpoint is a specification of what that checkpoint *would* be allowed to touch; it is not
permission to touch it.

### S8-0 — plan of record · APPROVED · COMPLETE

**Purpose.** Settle every open Stage 8 design decision before any code exists: individual wiring
versus aggregate gate, the exact `ISOLATED[]` additions, the exact case-table mapping, the
definition of full offline regression, how matrix 64 is preserved, how runtime-path absence is
checked, how a domain-throttle failure is treated, and what is explicitly *not* Stage 8.

**Allowed paths (exact, and the complete set):**

```text
docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md    new
docs/harvest/TODO.md                           Stage 8 section + header block
```

**Risk tier.** L0 — documentation only.

**Validation.** L0 only: exact two-path diff · `git diff --check` · nothing modified under `src/`,
`scripts/`, `tests/`, `config/`, `schemas/`, `state/`, `data/` · protected baseline 18/18 ·
untracked baseline 508/508 with drift 0 / missing 0 / extra 0 · all four runtime paths absent · no
network contact. **No test, no wrapper, no taxonomy gate and no `validate_task.sh --all`.**

**Full taxonomy gate or `--all`?** No. A documentation-only checkpoint runs L0 only — the
convention held by S4-C, S5-C, S6-C and S7-C.

**Commit boundary.** Its own commit, both paths atomically.

**Why not combined with S8-1.** The entire purpose is that the specification is reviewable *before*
the code it authorizes exists. Folding it into the wiring commit would make the plan a description
of a decision already taken.

### S8-1 — harness wiring · NOT APPROVED

**Purpose.** Make `--all` run every committed shell wrapper.

**Allowed paths (exact):**

```text
scripts/validate_task.sh
docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

**Scope — S8-1 does exactly six things:**

1. adds the 39 basenames of §3.2 to `ISOLATED[]`, individually, leaving the existing 19 untouched;
2. adds the case-table arms of §4.2–§4.5, and nothing else;
3. spells every case-table target `tests/<name>.sh`, byte-identical to the `tests/*.sh` glob output;
4. adds the harness-level pre/post absence check of §6 for the four runtime paths;
5. preserves sequential execution and sticky `FAIL=1` semantics;
6. makes **no** other change — no CLI or argument-parser change, no timeout, no interpreter-version
   check, no output summary or counter, no concurrency, no workflow-document edit.

**Explicitly not in S8-1:** no `tests/test_validate_task.sh` or other harness self-test (D15); no
new wrapper; no modification of any existing wrapper (D3); no separate intentionally-failing test
commit (D21).

**Risk tier.** H — it edits the sole allowlisted validation entry point. A defect here makes every
subsequent "green" untrustworthy.

**Validation, focused, in this order:** `bash -n scripts/validate_task.sh` · a read-back of the
resulting `ISOLATED[]` and case table against §3.2 and §4.2–§4.5, entry by entry · a **sampled**
direct run of four representative wrappers chosen for structural coverage — one that writes nothing
(`tests/test_taxonomy_identity.sh`), one temp-writing (`tests/test_taxonomy_artifacts.sh`), the
migration suite (`tests/test_taxonomy_migration.sh`), and the shell-native baseline suite
(`tests/test_taxonomy_protected_baseline.sh`) · protected 18/18 · untracked 508/508 · four runtime
paths absent.

**Full taxonomy gate or `--all`?** **No.** Both are deferred to S8-2 so the closing gate runs
**once**, against the final committed bytes, rather than being run repeatedly during development
until it turns green.

**Commit boundary.** One green commit, and the last commit before the regression.

**Why not combined with S8-2.** S8-2 must observe committed bytes. A regression run inside the
wiring checkpoint would validate a working tree that no commit records.

### S8-2 — full offline regression · NOT APPROVED · verification-only

**Purpose.** The single authoritative closing observation.

**Allowed paths.** **None.** S8-2 performs no edit and produces no commit.

**Risk tier.** H — it is the closing gate.

**The one command:**

```bash
bash scripts/validate_task.sh --all
```

Run **unfiltered**, with output redirected to a file **outside the repository**, and that file
inspected afterwards. Never piped (§5.2).

**Acceptance contract — all of:**

```text
exit code 0
all 58 wrappers execute, each exactly once
zero "WARN - skipping" lines
captured matrix summary contains "64 passed, 0 failed"
tests/test_parallel_harvest.sh executes and passes
protected baseline 18/18
untracked baseline 508/508, drift 0 / missing 0 / extra 0
tracked worktree and index unmodified
state/taxonomy_harvest/, data/harvested/, runs/, LATEST_RUN_ID all absent
no network request, no operational migration apply, no promotion
```

**Do not additionally run the taxonomy loop.** After S8-1, `--all` contains all 39 taxonomy
wrappers; running both duplicates them (§5.3, D11).

**On failure.** Preserve the captured output. **If `tests/test_taxonomy_domain_throttle.sh` fails,
preserve its diagnostic and stop** — do not retry until green, and do not classify any signature as
a permanent flake (D12, §9.3). Any code correction returns to **S8-1 under a newly approved
instruction**; S8-2 itself never edits.

**Commit boundary.** None. Its result is recorded by S8-C.

### S8-C — closeout · NOT APPROVED

**Purpose.** Record the outcome durably and close the stage.

**Allowed paths (exact):**

```text
docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md               status -> COMPLETED — STAGE 8 CLOSED
docs/harvest/TODO.md                                      tick both Stage 8 boxes, update header
docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_<date>.md  new
```

**`CLAUDE.md` is NOT in this set** (D17). This matches the three-path closeout precedent of
`0d2da64` S6-C, `6bf7f51` S5-C and `5fd9f91` S4-C exactly.

**Risk tier.** L0 — documentation only.

**Validation.** L0 only: exact three-path diff · `git diff --check` · nothing under `src/`,
`scripts/`, `tests/`, `config/`, `schemas/`, `state/`, `data/` · protected 18/18 · untracked
508/508 · four runtime paths absent · cross-document consistency. **`--all` is NOT rerun** — S8-2's
run is the closing gate, and the handoff attributes its figures to that run rather than
re-measuring them.

**Commit boundary.** Its own commit.

**Push.** Remains a separate explicit approval, after closeout, via
`bash scripts/safe_push_main.sh --check` then `--execute`. It is not authorized by this plan.

## 9 · Standing constraints for every Stage 8 checkpoint

### 9.1 · Invariants carried from Stage 7

```text
no operational default-root migration apply
no retained runtime migration tree (state/taxonomy_harvest/ stays absent)
no promotion into data/harvested/
no network request of any kind
protected baseline 18/18, byte-identical to anchor 8865c54e
untracked baseline 508/508, drift 0 / missing 0 / extra 0
.gitignore stays at exactly 1 insertion(+) against the anchor
the protected registries are read-only inputs and are never opened for writing
```

### 9.2 · CF-6 — the config guard, and why Stage 8 does not trip it

CF-6, recorded in Stage 4, says no checkpoint that edits `config/` can pass the full gate *before*
committing: the wrappers assert `git status --porcelain -- config/` is empty, which cannot
distinguish an authorized checkpoint edit from a test mutating production config.

**Its scope has grown since it was recorded.** Stage 4 measured 14 suites; the present tree has
**33 of 39** taxonomy wrappers asserting on `config/` — 32 over `state/ config/` plus
`test_taxonomy_config.sh` over `config/` alone.

**Stage 8 does not trip CF-6**, because no Stage 8 checkpoint has `config/` in its allowed-path
set. This is stated explicitly rather than left to chance: if a successor finds a `config/` edit
necessary, that is a scope change requiring new approval, and CF-6 becomes live at 33 files.

### 9.3 · Domain throttle

`tests/test_taxonomy_domain_throttle.sh` is the only timing-sensitive suite in the gate: its header
records that it *"launches real subprocesses against a local recording HTTP server and measures
observed concurrency and inter-arrival gaps"*, and *"takes ~15s"*. It is offline — the server binds
loopback — but it is the one suite whose result depends on scheduling.

**Decision (D12): a failure is an unresolved diagnostic.** Preserve the captured output, report it
as a finding, and stop. Do not rerun until green. Do not record any failure signature as an
accepted or permanent flake. If instability proves real, the response is an approved plan
deviation, not a retry loop.

### 9.4 · Repository-specific traps

- **Mixed EOL.** `core.autocrlf=true`, no `.gitattributes`. 8 of the 18 protected files are pinned
  in `filtered` (CRLF) form and 10 in `blob` (LF) form. An LF-only rewrite is invisible to
  `git diff` and is exactly what `test_taxonomy_protected_baseline.sh` case C exists to catch.
  **Do not use `git stash` in any Stage 8 checkpoint** — a stash round-trip silently rewrites
  LF→CRLF. Use `git show HEAD:<path>` or a copy outside the repository.
- **Guard hook.** Do not pipe `validate_task.sh` or any `test_*.sh` into an output filter (§5.2).
- **Commits.** Use `bash scripts/safe_commit.sh -m "…" <explicit files>` with the paths named. Never
  `-A`, `.` or a glob.
- **`--all` is position-sensitive.** It is honoured only as `$1`; `validate_task.sh foo.sh --all`
  silently becomes `explicit` mode. Pre-existing, unchanged by Stage 8, noted so S8-2 types the
  command correctly.

## 10 · Validation policy by checkpoint

| Checkpoint | Focused validation | Taxonomy gate | `--all` | Commit |
|---|---|---|---|---|
| **S8-0** | L0 only — two-path diff, `git diff --check`, baselines, runtime paths | no | no | yes |
| **S8-1** | `bash -n`, table read-back, 4 sampled wrappers, baselines | no | no | yes |
| **S8-2** | — | contained by `--all` | **yes, once** | no |
| **S8-C** | L0 only — three-path diff, `git diff --check`, baselines, consistency | no | no | yes |

Preserved throughout: documentation-only checkpoints run L0 only; code checkpoints run focused
tests first; the taxonomy gate is **not** rerun repeatedly to obtain green; the final regression is
fully offline; a domain-throttle diagnostic is preserved and never accepted as a flake; no real
migration apply, promotion or network access is any part of Stage 8; `--all` must leave no runtime
state; and the protected and untracked baselines hold at every checkpoint.

## 11 · Recorded for the successor, not acted on

Raised during Stage 8 planning, deliberately excluded, and preserved so they are not lost:

```text
S8-CF-1  Harness contract test. No tests/test_validate_task.sh exists, and nothing in tests/
         asserts test names, counts, case-table length or the ISOLATED[] set. A test pinning
         "zero unexpected skips under --all" would stop a future wrapper being added without an
         ISOLATED[] entry and silently skipped forever. Excluded from Stage 8 by D15.
S8-CF-2  CLAUDE.md accuracy. CLAUDE.md calls validate_task.sh the single validation entry point
         and never mentions the taxonomy pipeline. After S8-1 the claim becomes true and could be
         stated. Excluded by D17 to keep S8-C at the committed three-path precedent.
S8-CF-3  Changed-mode routing for tests/harvest/*.py. Editing a test module does not select its
         wrapper (§4.6). Mechanical to add; outside the production-surface scope of S8-1.
S8-CF-4  Unwired taxonomy paths. scripts/harvest/hash_tree.py and
         config/harvest/watchlists/oss-milestones.v1.json have zero consumers in committed code
         or tests. Either they are dead, or a consumer is missing. Product question, not harness.
S8-CF-5  Non-uniform wrapper leak guards. 12 wrappers check four runtime paths, 4 check three,
         23 check none. §6 makes the guarantee uniform at harness level; harmonizing the wrappers
         themselves would touch 39 protected-by-convention test files and is not Stage 8 work.
S8-CF-6  Exit-code granularity. FAIL is sticky 0/1, so the number of failing suites and the
         child's real rc are lost. Across 58 suites this makes triage harder. Excluded by D19.
S8-CF-7  CF-6 has grown from 14 files to 33 (§9.2). Whoever finally fixes the guard — "config is
         unchanged BY THIS TEST" rather than "config is unmodified" — now edits 33 wrappers.
```

Carried forward unchanged at their existing status, and not reinterpreted here: **CF-1** (deferred
and still guarded — Stage 8 adds no concurrency, so the unlocked pool paths keep zero concurrent
callers), **CF-2 / CF-7**, **CF-5 / CF-8 / CF-9**, **CF-6** (§9.2), **CF-11**, **CF-13**,
**CF-15**, **CF-16**, **CF-17**.

## 12 · Closing statement

**S8-0 is complete. Stage 8 implementation is not approved.** `scripts/validate_task.sh` is
unchanged and CF-4 remains open. S8-1, S8-2 and S8-C each require separate approval by name with
the allowed-path set restated at approval time. A push remains a separate approval after closeout.
