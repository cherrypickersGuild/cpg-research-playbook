# Stage 8 completion handoff — harness wiring and full offline regression

**Date:** 2026-07-31 · **Branch:** local `main` · **Closing implementation baseline:**
`01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c`

A durable milestone summary, not a session log. It records what Stage 8 delivered and the state the
repository was in when Stage 8 closed.

**It approves nothing.** It does not authorize a push, an operational apply against the
repository's default state root, promotion into `data/harvested/`, network access, Stage 9, or any
other successor activity. A completed stage and a green gate do not together open the next one —
the rule that governed every checkpoint below does not lapse at closure.

**Stage 8 is closed LOCALLY and UNPUSHED.** `origin/main` remains at
`b9a08a33ff215ce226c885a7f70c97cd4974ccad`, the Stage 7 boundary.

---

## 1 · Starting state

Stage 8 began on the published Stage 7 tip:

```text
b9a08a33ff215ce226c885a7f70c97cd4974ccad   Stage 7 push-state record; local main = origin/main
                                           = remote main, 0 behind / 0 ahead
```

At that point, verified rather than assumed:

```text
tracked worktree and index   unmodified
untracked baseline           508/508 byte-identical, drift 0 / missing 0 / extra 0
protected baseline           18/18 byte-identical to anchor 8865c54e
state/taxonomy_harvest/      absent
data/harvested/              absent
runs/                        absent
LATEST_RUN_ID                absent
Stage 7 temporary apply root none remained
scripts/validate_task.sh     contained zero occurrences of the string "taxonomy" (CF-4)
```

## 2 · Commit chain

```text
01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c  feat(harvest): wire taxonomy into validation   S8-1
                                          harness                          3 paths
0657db8a65e311ea0f20b43a2fbf2c0e811d5ee5  docs(harvest): plan stage 8 harness wiring     S8-0
                                                                           2 paths
b9a08a33ff215ce226c885a7f70c97cd4974ccad  Stage 7 push-state record
                                          Stage 8 starting baseline
```

**S8-2 is a verification-only checkpoint and produced NO COMMIT.** It ran one regression, edited
nothing, and has no hash. It sits between `01d2999a` and this closeout in time, not in the graph.

This documentation closeout commit (S8-C) sits on top of `01d2999a` and changes exactly three
documentation paths; following the convention of every prior closeout in this pipeline, its hash is
reported in the execution record rather than written into the files it commits.

Plan of record: `docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md`. Every checkpoint was approved
separately **by name**, with its exact allowed-path set restated at approval time, and each was
gated by its own validation before the next began.

## 3 · Delivered — the harness contract

Stage 8 changed **exactly one production file across its whole life**: `scripts/validate_task.sh`.
It added no test, no module, no schema, no config file and no fixture.

### 3.1 · `ISOLATED[]` — 19 → 58 entries

All **39** committed `tests/test_taxonomy_*.sh` wrappers are listed **individually**, by basename,
as one commented block. There is no aggregate taxonomy wrapper, no wildcard, no glob and no dynamic
discovery.

```text
tests/*.sh on disk           58   = 19 legacy + 39 taxonomy
ISOLATED[] entries           58   each wrapper exactly one entry
legacy entries              19   preserved VERBATIM, in original order, as a prefix —
                                  proved by comparison against b9a08a3
duplicates                    0
entries naming a missing file 0
```

`ISOLATED[]` remains what it always was: an **audited allowlist of basenames**, matched by
`is_isolated()` against `basename "$1"`. It confers no isolation mechanism. Membership decides only
whether a wrapper is executed or WARN-skipped; every member runs identically, as a direct `bash`
child, serially, in the same environment.

### 3.2 · Case table — 50 additive taxonomy arms

Routed by **ownership** — each production file selects the wrapper whose declared subject is that
file's contract, plus any wrapper that committed evidence shows drives it as its subject. Routing
by import fan-out was rejected: `src/harvest/schema.py` is imported by 25 of the 39 suites and
`urlkey.py` by 17, so an import map would have been a blanket "run all 39" arm in disguise.
**There is no blanket arm.**

```text
src/harvest/**       26 arms   (25 mapping + 1 deliberate no-op)
scripts/harvest/**    7 arms   ( 6 mapping + 1 deliberate no-op)
config/harvest/**     8 arms
schemas/harvest/**    9 arms
                     --------
                     50 arms   91 add_test calls   39/39 taxonomy wrappers routed
```

The 19 pre-existing legacy arms are **byte-identical and in order** against `b9a08a3`; the taxonomy
arms are purely additive and adjacent. The largest taxonomy arm adds 6 wrappers
(`config/harvest/facets/*.v1.json`).

**Canonical spelling and at-most-once execution.** Every target is spelled `tests/<name>.sh`,
byte-identical to what the `tests/*.sh` glob emits. This is load-bearing: `add_test` de-duplicates
on the exact path **string**, so `./tests/x.sh` and `tests/x.sh` would both be added and the suite
would run twice. Verified: every target matches `tests/[a-z0-9_]+\.sh` and exists on disk.

**Deliberate no-op omissions**, implemented as explicit empty arms placed **before** the wildcard
patterns so `case`'s first-match-wins ordering stops a later glob from silently claiming them —
making the omission visible in code, not only in the plan:

```text
src/harvest/__init__.py
src/harvest/adapters/__init__.py     package plumbing with no behavioural surface; a change that
src/harvest/migrate/__init__.py      matters lands in a mapped sibling

scripts/harvest/hash_tree.py         zero consumers anywhere in src/harvest/**, scripts/harvest/**
                                     or tests/**; mapping it would invent coverage that does not
                                     exist
```

Also recorded in the plan, and not automatically routed:

- **`config/harvest/watchlists/oss-milestones.v1.json`** has zero consumers in production code or
  tests. It routes to `tests/test_taxonomy_config.sh` **only**, because `check_config.py` is its
  sole committed authority. **No behavioural suite is claimed for it.**
- **`tests/harvest/*.py` and `tests/fixtures/harvest/**`** are test implementations and test
  inputs, not production surfaces. **Editing a test module does not select its wrapper in `changed`
  mode.** This is a real limitation, stated so no reader assumes otherwise; `changed` mode still
  lints these files, and `--all` covers them unconditionally.
- **`config/harvest/facets/legacy_industry_map.v1.json`** is consumed by `migrate/ax_cases.py` but
  is knowingly left in the facets arm and **not** additionally routed to the 250-assertion
  migration suite.

### 3.3 · Runtime-path containment — harness level, before and after

```bash
RUNTIME_PATHS=(state/taxonomy_harvest data/harvested runs LATEST_RUN_ID)
```

Checked with `[ -e ]` once **before** the first wrapper and once **after** the last. Either
detection sets the existing sticky `FAIL=1` and prints the offending path.

`[ -e ]` rather than `git status`, for two independent reasons: `/state/taxonomy_harvest/` is
gitignored, so porcelain cannot see a leaked migration bundle at all; and `data/harvested/`,
`runs/` and `LATEST_RUN_ID` sit at the repository root, outside the `state/` tree that
`snapshot_state()` walks.

**Nothing is deleted, restored, relocated or concealed** — matching the `state/` snapshot's
deliberate refusal to auto-restore. A leak is evidence; removing it destroys the evidence.

**Preserved, not replaced:** `snapshot_state()` is untouched and still `find`-based, so it remains
the independent second witness for `state/taxonomy_harvest`. The 16 wrapper-owned leak guards are
untouched and unweakened.

### 3.4 · Unchanged by decision

Verified statically at S8-1 and unchanged at closure:

```text
--all enumeration            single `for t in tests/*.sh` glob
--all argument positioning   honoured only as $1 (pre-existing, not changed)
WARN-skip semantics          unchanged; a skip still does not set FAIL
failure model                sticky FAIL=1, every test still runs after a failure
exit code                    exit "$FAIL" — 1 for any number of failures, child rc not normalized
execution                    strictly sequential, one direct `bash "$t"` child per wrapper
state/ snapshot              content hashes + porcelain, before and after, never auto-restored
```

**Not added, by decision:** timeout or watchdog · Python/Bash/jq/Git version gate · test-count
parsing or new summary format · concurrency · harness self-test (`tests/test_validate_task.sh` was
**not** created) · aggregate wrapper · baseline or fixture change · `CLAUDE.md` change.

## 4 · Authoritative S8-2 evidence

```text
command       bash scripts/validate_task.sh --all
invocations   exactly one
exit code     0
elapsed       736 s
final line    == validate_task.sh: PASS ==
wrappers      58/58 executed, each exactly once — legacy 19/19, taxonomy 39/39
skips         zero "WARN - skipping" lines
matrix        == test_matrix_harvest.sh: 64 passed, 0 failed ==
parallel      == test_parallel_harvest.sh: 62 passed, 0 failed ==
failures      no "FAIL - offline" line; no FAIL line of any kind
diagnostics   no runtime-leak and no production-state-change diagnostic; both harness
              positive assertions printed:
                ok   - production state/ unchanged
                ok   - repository runtime paths absent (state/taxonomy_harvest
                       data/harvested runs LATEST_RUN_ID)
```

Run unfiltered, with complete stdout and stderr redirected to a uniquely named file **outside the
repository**, and that file inspected afterwards — never piped into an output filter, which the
repository's guard hook blocks for protected commands anyway.

**The expected wrapper list was built from `git ls-files tests/`** — the committed tree — and
compared against the completed log, rather than being derived from the log itself.

Post-run, verified independently:

```text
HEAD                    01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c, unchanged
tracked worktree/index  unmodified; working tree byte-identical to 01d2999a
untracked baseline      508/508, drift 0 / missing 0 / extra 0
protected baseline      18/18
runtime paths           all four absent
temporary output        none inside the repository
local divergence        0 behind / 2 ahead
```

**No separate taxonomy loop was run**, and none was needed: after S8-1, `--all` contains all 39
taxonomy wrappers, each exactly once, so `for t in tests/test_taxonomy_*.sh; do bash "$t"; done`
would have duplicated them for no additional information. **The zero-skip count is what proves the
containment.**

**S8-2 produced no commit and edited nothing.** During it there was no edit, commit, migration
apply, promotion, memory update, push, fetch, remote query, or network request.

**The external log is not retained.** It lived outside the repository and was deleted after
verification, because no failure diagnostic required preserving. **No log artifact exists in the
repository, and none is claimed.** The figures above and in the plan's §8 are the durable record of
that run.

## 5 · CF-4 closure

**CF-4 is CLOSED.**

CF-4 was recorded in Stage 4 as: *"`scripts/validate_task.sh` contains zero taxonomy references, so
CLAUDE.md's stated validation entry point exercises none of the 567 assertions."* By the Stage 7
close the figure had grown to 2,065, and the defect had a precise shape: `--all` globbed all 58
wrappers, but `ISOLATED[]` held only the 19 legacy basenames, so **all 39 taxonomy wrappers were
WARN-skipped** — and because a WARN does not set `FAIL`, `--all` was green *while running none of
the taxonomy work*.

**What closes it:** `scripts/validate_task.sh --all` now executes the entire taxonomy wrapper set —
39/39, each exactly once — and passed offline with **zero skips**. `CLAUDE.md`'s claim that
`validate_task.sh` is the single allowlisted offline validation entry point is, for the taxonomy
pipeline, true for the first time.

**CF-4 and nothing else.** The runtime-path check (§3.3) and the case-table routing (§3.2) were
delivered by the same checkpoint but are not part of CF-4's claim, and are not described as such.
No other carried-forward item is closed, narrowed or renumbered by Stage 8.

## 6 · Preserved boundaries

Held throughout Stage 8, at every checkpoint:

```text
network                   no request of any kind, at any point, by any checkpoint. This
                          pipeline has still never made a live request.
remote contact            none. Only the existing local origin/main ref was read; no fetch,
                          no ls-remote, no query.
operational migration     no `migrate.sh ax-cases --apply` against the default state root.
apply                     Apply is exercised only inside test_taxonomy_migration.sh, which
                          injects --state-root at every call site and proves it by AST scan of
                          its own source. Stage 8 ran that suite; it added no call site.
retained runtime tree     state/taxonomy_harvest/ never existed at any point and does not
                          exist now. Neither do data/harvested/, runs/ or LATEST_RUN_ID.
promotion                 nothing promoted into data/harvested/, which remains absent.
taxonomy wrappers         not one byte changed in any of the 39.
source/schema/config      tests/, src/, config/, schemas/, state/, data/ and .claude/ all
fixtures/baselines        byte-unchanged since b9a08a3. No fixture or baseline was edited —
                          editing them is how the invariants get faked, not verified.
protected files           18/18 byte-identical to anchor 8865c54e, at every checkpoint.
untracked files           508/508 byte-identical, drift 0, at every checkpoint.
CLAUDE.md                 unchanged, deliberately, including at closeout (plan decision D17).
project memory            not updated by any Stage 8 checkpoint.
git stash                 never used — a stash round-trip silently rewrites LF to CRLF in this
                          mixed-EOL repository and git diff normalizes it away.
S6-L                      Stage 6's bounded live smoke remains UNEXECUTED and UNAUTHORIZED.
Stage 7 default-root      the S7-5 development incident stands exactly as Stage 7 recorded it.
incident                  Stage 8 neither reinterprets nor closes it.
domain throttle           test_taxonomy_domain_throttle.sh passed in the S8-2 run. That is ONE
                          OBSERVATION, NOT A RESOLUTION. Plan decision D12 stands: an
                          intermittent signature is an unresolved diagnostic, never an
                          accepted permanent flake. The suite launches real subprocesses
                          against a local recording server and measures timing; it remains
                          the one suite in the gate whose result depends on scheduling.
CF-6                      NOT tripped, and NOT closed. Its scope has GROWN since Stage 4
                          recorded it: 33 of 39 taxonomy wrappers now assert config/ is
                          unmodified (32 over `state/ config/`, plus test_taxonomy_config.sh
                          over config/ alone), against the 14 files Stage 4 measured. Stage 8
                          did not trip it because no checkpoint had config/ in its path set.
```

**All previously carried-forward findings remain carried forward at their existing status, and are
not reinterpreted here:** CF-1 (deferred and still guarded — Stage 8 added no concurrency, so the
unlocked pool paths keep zero concurrent callers) · CF-2 / CF-7 · CF-5 / CF-8 / CF-9 · CF-6 (above)
· CF-11 · CF-13 · CF-15 · CF-16 · CF-17.

## 7 · Known limitations and carried-forward items

Recorded by the plan as Stage 8's own carried-forward set. **None is closed, renumbered or
silently dropped.**

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

Restated plainly, because it is the limitation most likely to be misread: **direct edits to test
implementation paths (`tests/harvest/*.py`) and fixture paths (`tests/fixtures/harvest/**`) are not
automatically routed to any wrapper in `changed` mode.** Those paths have no changed-mode coverage,
and this handoff does not claim they do. They are covered by `--all`.

Likewise, `scripts/harvest/hash_tree.py` and `config/harvest/watchlists/oss-milestones.v1.json`
have **no behavioural suite**. The first routes to nothing; the second routes only to the
configuration-completeness check.

## 8 · Validation at closure

**S8-0** — L0 only: exact two-path diff · `git diff --check` · nothing under `src/`, `scripts/`,
`tests/`, `config/`, `schemas/`, `state/`, `data/` · protected 18/18 · untracked 508/508 · four
runtime paths absent. No suite run.

**S8-1** — focused only, and deliberately **not** the full gate, so the gate would run once against
final committed bytes:

```text
bash -n scripts/validate_task.sh                                      rc 0
static inventory / semantics / containment proof, 39 checks           all pass
  incl. legacy arms byte-identical vs b9a08a3, legacy ISOLATED[]
  prefix verbatim, 39/39 wrappers routed, no blanket arm
explicit-mode routing samples, one per routing shape, each rc 0,
each ending PASS with 0 skips and the expected wrapper set once:
  src/harvest/budget.py                 -> budget                     1:1 arm
  src/harvest/urlkey.py                 -> identity aliases
                                           facet_identity             fan-out arm
  scripts/harvest/migrate.sh            -> migration                  CLI arm
  config/harvest/topics/cases.v1.json   -> config adapters
                                           adapter_concurrency        config wildcard
  schemas/harvest/run_manifest.v1.json  -> manifest                   schema arm
  scripts/harvest/protected_baseline.py -> protected_baseline         shell-native suite
omission proof: src/harvest/__init__.py + scripts/harvest/hash_tree.py
route to ZERO wrappers while still being linted                       rc 0
```

`test_taxonomy_domain_throttle.sh` was deliberately not exercised at S8-1 — no sample routes to it
— so no domain-throttle diagnostic arose there.

**S8-2** — the closing gate, §4. Run once.

**S8-C** — this closeout. L0 only: exact three-path diff · `git diff --check` · nothing touched
under `src/`, `scripts/`, `tests/`, `config/`, `schemas/`, `state/`, `data/`, `.claude/` or
`CLAUDE.md` · `scripts/validate_task.sh` byte-identical to `01d2999a` · protected 18/18 · untracked
508/508 · four runtime paths absent · no temporary file inside the repository · no EOL rewrite · no
network contact. Per its own risk tier **the full gate was NOT rerun**: the closing gate is S8-2's
single run, and the figures above are attributed to that run rather than re-measured.

## 9 · Repository state at closure

```text
closing implementation baseline   01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c
this closeout                     one commit on top of it, three documentation paths
tracked worktree and index        unmodified
untracked baseline                508/508 byte-identical, drift 0 / missing 0 / extra 0
protected baseline                18/18 byte-identical to anchor 8865c54e
state/taxonomy_harvest/           absent
data/harvested/                   absent
runs/                             absent
LATEST_RUN_ID                     absent
.gitignore                        still exactly 1 insertion(+) against the anchor
gate                              bash scripts/validate_task.sh --all — 58 wrappers, zero skips
assertions                        unchanged by Stage 8: 39/39 taxonomy suites, 2,023 unittest
                                  + 42 shell = 2,065. Stage 8 added no suite and no assertion;
                                  it wired the existing 39 into the harness.
```

## 10 · Successor

**Stage 8 is closed. Nothing is open.** This handoff approves no successor activity, and a green
gate approves none either.

**Unapproved, and each needing its own explicit approval by name:**

```text
push                      LOCAL COMMITS ARE UNPUSHED. origin/main is still b9a08a3, the Stage 7
                          boundary. After this closeout the expected position is
                          0 behind / 3 ahead. Publishing requires
                          `bash scripts/safe_push_main.sh --check`, then a SEPARATELY APPROVED
                          `bash scripts/safe_push_main.sh --execute`. The push itself always
                          requires explicit human approval.
Stage 9                   the bounded deterministic live smoke. NOT opened by this closure.
                          It needs outbound requests and production runtime state, and so
                          needs approval twice — once as a checkpoint, once immediately
                          before execution.
operational apply         a real `migrate.sh ax-cases --apply` against state/taxonomy_harvest/
                          is a production state write and a separate human-approved action.
promotion                 data/harvested/ remains absent; promotion is unscheduled.
network / live activity   no request has ever been made by this pipeline; S6-L remains
                          unauthorized.
```

**Exact starting point for the successor**

```text
start commit    this documentation closeout commit, on top of
                01d2999a3f382d3fcf51ace8f1d7b4fc9445ad6c
plan of record  docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md   COMPLETED — STAGE 8 CLOSED
push state      origin/main at b9a08a3 (Stage 7 boundary); every Stage 8 commit unpushed
```

**Constraints the successor inherits.** The 18 protected files and the 508 pre-existing untracked
paths stay byte-identical; `.gitignore` stays at exactly `1 insertion(+)` against the anchor. The
protected registries are **read-only inputs** and are never opened for writing. Every checkpoint
needs its own approval by name with an exact allowed-path set declared up front — if a path outside
the set turns out to be required, stop and report rather than widening scope. **The full gate is
now `bash scripts/validate_task.sh --all`**, which contains the taxonomy gate; the standalone loop
`for t in tests/test_taxonomy_*.sh; do bash "$t"; done` remains useful for taxonomy-focused
development but is not an additional closing run. A documentation-only closeout runs **L0
validation only** and deliberately does not rerun the gate.
