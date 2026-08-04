# Taxonomy harvest — implementation report

```text
Historical implementation coverage      8865c54e2cc8d879410576f247baac4aea149f34
                                          ..
                                        c3497fa18ed05268edd456472c738a800d0ee21f
                                        73 commits · 269 tracked paths · 267 A / 2 M

Current repository authority at         ab99b32781fa07e2e06de4097ef201dba6d765d1
S10-1 entry                             docs(harvest): plan stage 10 final report

Stage 10 state                          OPEN. The S10-1 REPORT-DRAFTING BOUNDARY is
                                        COMPLETE; the S10-1 CHECKPOINT remains
                                        INCOMPLETE until a separate formal L0
                                        validation passes and the validated
                                        three-path set is committed through a
                                        separately approved boundary.
                                        S10-2 and S10-C are UNAPPROVED.
```

**This report is the Stage 10 deliverable named by `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md`
§5.1.** It records no commit SHA of its own — a commit cannot contain its own identifier, and this
report asserts nothing about whether it has since been committed.

**Validation and commit are separate boundaries, and this document does not carry their result.**
This report neither claims that formal L0 validation has passed nor that it has not; that outcome
belongs to the checkpoint report of the validation boundary, not to the durable text here.

Every claim below is labelled by evidence class:

```text
[git]       derived from Git history at the fixed range above
[handoff]   recorded in a committed completion handoff
[roadmap]   recorded in docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md
[plan]      recorded in a committed stage plan
[code]      read from committed code at ab99b32
[obs]       current working-state observation, dated
[inference] reasoned, not measured — and flagged as such
```

---

## 1 · Executive summary and scope

**What the implementation accomplished.** Over 73 commits from the implementation-start anchor
`8865c54e` to the Stage 9 documentation closeout `c3497fa`, this task built a deterministic taxonomy
harvest pipeline: 12 configured cells across 3 topics and 25 sources, with discovery adapters,
canonical URL identity, cross-process per-domain pacing and budgets, extraction, precedence
classification, scoring and verification, facet assignment, record construction, atomic artifact
persistence, cross-run ledgers and rejection evidence, coverage and alias-conflict reporting, run
comparison, publication diff, bounded link checking, an AX-corpus migration path, and a
63-wrapper offline regression harness. **269 tracked paths, 267 added and 2 modified** `[git]`.

**What Stage 9 proved.** Stage 9 turned a fixture-only library into a program a human can run
against real sources, and then ran it — four separately approved outbound executions, each exactly
once, never retried `[handoff §2.1]`. It produced **three retained runs** in an external root: two
bounded smokes that validate and compare with **zero invariant violations and `idempotent: true`**
(M2, M3), and one bounded linkcheck with **19/19 records carrying a terminal link-health result**
(M4) `[handoff §6]`. The authoritative 63-wrapper gate passed at `ec9bedc` — **43 suites, 2,386
tests, 0 failures / 0 errors / 0 skips** `[handoff §5.4]`.

**What Stage 10 documentation is closing.** Stage 10 closes the *originally described Stage 0–10
task* — nothing more. It is two markdown documents plus a closeout `[plan §1]`. This report is the
first of them.

**What remains outside the completed implementation task.** A production `harvest` command does not
exist in any form; there is no reviewed production candidate, no promotion code, no published JSON,
no website consumer and no recurring refresh. Those are **M5, M6 and M7**, roughly **22–32 further
checkpoints**, mostly undesigned and currently unowned `[roadmap §4.0]`.

**This report establishes neither production readiness nor publication.** See §14.

---

## 2 · Authority and evidence model

Source hierarchy, unchanged from the roadmap's evidence index `[roadmap §11]`; each outranks the one
below where they differ:

1. committed implementation under `src/harvest/**` and `scripts/harvest/**`;
2. committed tests under `tests/**` — **63 wrappers**, 44 taxonomy;
3. committed `schemas/harvest/*.v1.json` and `config/harvest/**`;
4. completion handoffs, currently `docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md`;
5. earlier `docs/harvest/handoffs/HANDOFF_STAGE_<N>_COMPLETE_*.md`;
6. stage plans, `docs/harvest/STAGE_<N>_IMPLEMENTATION_PLAN.md`;
7. `docs/harvest/TODO.md` and `docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md`;
8. `docs/harvest/IMPLEMENTATION_PLAN.md` — **superseded design input only**, pre-Stage-3 in places
   and describing commands and runtime paths that do not exist `[roadmap G11]`;
9. project memory — a continuation aid, **never repository authority**.

Four categories that this report keeps apart and never merges:

| Category | Meaning | Example |
|---|---|---|
| **Current repository facts** | true of the tree at `ab99b32` | six commands in `cli.COMMANDS` `[code]` |
| **Historical facts** | true of a named past commit, and still true *of that commit* | the 63/63 gate failed at `8479095` `[handoff §5.2]` |
| **External retained evidence** | outside the repository and outside the 508-path untracked baseline | the retained Stage 9 root; scratchpad logs `[handoff §11.2]` |
| **Unexecuted design intentions** | written in a plan, never built or never run | `promote`, `smoke-model`, acceptance commands 23–24 `[plan]` |

`docs/harvest/HANDOFF_CURRENT.md` is **stale since Stage 2.5** and is deliberately not used as an
authority here; its update is S10-C's `[plan §10]`.

---

## 3 · Stage and checkpoint chronology

Derived from `git log --reverse 8865c54e..c3497fa` `[git]`; stage attribution comes from the commit
subjects and the committed handoffs, not from memory.

| Stage | Range within the task | Commits | Closing / completion authority |
|---|---|:--:|---|
| **0–2** | `0edbf50` | 1 | scaffold, baselines, config, schemas, identity, HTTP, budgets — landed as one commit |
| **2.5** | `3b85a81` … `84650cb` | 4 | `handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md` |
| **3** | `ea992f1` … `97aade4` | 9 | `handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md` |
| **4** | `8f07920` … `5fd9f91` | 9 | `handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` |
| **5** | `80505a1` … `6bf7f51` | 9 | `handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md` |
| **6** | `f2765de` … `0d2da64` | 15 | `handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md` |
| **7** | `ab40f65` … `b9a08a3` | 9 | `handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md` |
| **8** | `0657db8` … `bf06730` | 3 | `handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md` |
| roadmap | `5c825e8`, `2bbc236` | 2 | `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` (written between Stages 8 and 9) |
| **9** | `720f114` … `c3497fa` | 12 | `handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md` |
| | **total** | **73** | |

*(Counts computed from the commit list, contiguous and non-overlapping: 1 + 4 + 9 + 9 + 9 + 15 + 9 +
3 + 2 + 12 = 73, exactly the `git rev-list --count` figure `[git]`. Stage boundaries are drawn at the
subjects that name each stage's plan and completion commits; the two roadmap commits sit between
Stages 8 and 9 and belong to neither.)*

Stage summaries are deliberately short: each stage's detailed delivery record already exists in its
handoff, and this report **cites rather than duplicates** it `[plan §5.1]`.

- **Stages 0–2** — repository scaffold, the protected baseline and the untracked baseline, the
  namespace contract, dependency pinning, config and schemas, URL identity and canonicalization, the
  HTTP baseline with robots and redirect handling, cross-process domain leases and budgets.
- **Stage 2.5** — case facets and shared discovery; the facet vocabulary and generated facet schema.
- **Stage 3** — fixture-backed discovery adapters, the run-scoped source fetch cache, and pacing
  measured at worker release. Three defect fixes landed inside the stage (`e271206`, `0a03fdd`,
  `2841578`, `bfde922`) `[git]`.
- **Stage 4** — deterministic candidate ingest and dedupe, metadata normalization, precedence
  classification, scoring and verification, facet assignment, in-memory record construction.
- **Stage 5** — the atomic artifact writer, cell and topic artifacts, rejection log and URL ledger,
  coverage report, run manifest and `LATEST_RUN_ID`, the sequential cell driver, recovery and re-run
  semantics.
- **Stage 6** — target fetching and verification: the target fixture corpus, fetch outcomes, canonical
  domain policy alignment, alias adjudication and conflict reporting, target ownership, target
  evidence, request accounting, and determinism/recovery proofs.
- **Stage 7** — AX corpus migration: entity-registry assessment, the migration URL guard, in-memory
  AX case mapping, the dry-run CLI, atomic apply, and migration integration proofs.
- **Stage 8** — harness wiring: `scripts/validate_task.sh` gained all taxonomy wrappers with
  at-most-once execution and a four-runtime-path guard before *and* after every run. **CF-4 closed;
  nothing else** `[handoff Stage 8]`.
- **Stage 9** — bounded live validation. See §4, §5, §7 and §8.
- **S10-0** — the Stage 10 plan of record. See §3.1.

### 3.1 Stage 10 progress — recorded apart from the Stage 0–9 implementation

```text
ab99b32   docs(harvest): plan stage 10 final report        S10-0, PUBLISHED
          parent c3497fa · two paths, documentation only, no executable change
            docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md   (new)
            docs/harvest/TODO.md
```

S10-0 opened Stage 10, established the documentation-only contract, split the stage into
S10-0/S10-1/S10-2/S10-C, ratified the matrix-unification definition and authored the five
reconsideration gates, and recorded the L0-only validation policy `[plan]`.

> **`ab99b32` and its two paths are deliberately NOT part of the 269-path Stage 0–9 inventory in
> §9 and Appendix A.** That inventory ends at `c3497fa` by construction. Mixing S10-0's plan path
> into it would misattribute Stage 10 documentation work to the implementation task.

**This report — `docs/harvest/IMPLEMENTATION_REPORT.md` — is the S10-1 deliverable.** Its
**report-drafting boundary is complete**; the **S10-1 checkpoint remains open** until a separate
formal L0 validation passes and the validated three-path set is committed. It appears in no Git
inventory in this document, by construction. **S10-2 and S10-C are unapproved, and Stage 10 is not
closed.**

---

## 4 · Exact Stage 9 commit chain

Authority: `[handoff §2]`, reproduced here with the executable-vs-documentation distinction made
explicit. Stage 9 opened on the published Stage 8 tip `bf067303`.

| # | SHA | Subject | Checkpoint | What it changed |
|---|---|---|---|---|
| 1 | `5c825e8` | docs(harvest): map roadmap and artifact lifecycle | pre-S9 roadmap | docs only |
| 2 | `2bbc236` | docs(harvest): correct roadmap stage percentage | pre-S9 correction | docs only |
| 3 | `720f114` | docs(harvest): plan stage 9 live validation | **S9-0** | docs only |
| 4 | `fddbbb7` | feat(harvest): add live transport seam and CLI foundation | **S9-1** | **executable + tests** (10 paths) |
| 5 | `3e64d6e` | feat(harvest): add source preflight command | **S9-2** | **executable + tests** (8 paths) |
| 6 | `4d0d56d` | feat(harvest): add bounded smoke and run validation | **S9-3** | **executable + tests** (11 paths) |
| 7 | `238df98` | feat(harvest): add run comparison and publication diff | **S9-4** | **executable + tests** (9 paths) |
| 8 | `139cf0f` | docs(harvest): calibrate live corpus | **S9-5** | docs only (2 paths) |
| 9 | `f228cb4` | fix(harvest): record actual run timing | **S9-5C1** | **executable + tests** (5 paths) |
| 10 | `05ef9e4` | feat(harvest): record in-run candidate sightings | **S9-5C2** | **executable + schema + tests** (8 paths) |
| 11 | `9d06b56` | docs(harvest): defer immutable rejection snapshots | **S9-5C3 deferral** | docs only (2 paths) |
| 12 | `8479095` | feat(harvest): add bounded link checking | **S9-6** | **executable + schema + tests** (13 paths) |
| 13 | `ec9bedc` | test(harvest): repair authoritative full-gate findings | **S9-6A** | **tests only** (4 paths) |
| 14 | `c3497fa` | docs(harvest): record stage 9 completion | **S9-C** | docs only (4 paths) |

*(The handoff enumerates rows 1–13 as the `bf067303..ec9bedc` chain; row 14 is the S9-C closeout
that contains the handoff itself and therefore could not self-record its own SHA `[handoff §2]`.)*

Every commit was published by `safe_push_main.sh --execute`, **exactly once each**, fast-forward
only, with no retry, no manual `git push`, no fallback and no history rewrite `[handoff §2]`.

**Three commits, three different authorities — never conflate them:**

```text
ec9bedc   the LAST commit that changed executable or test behaviour anywhere in this
          task, and the tip at which the authoritative 63/63 gate PASSED.
          NOT the repository tip.
c3497fa   the Stage 9 DOCUMENTATION CLOSEOUT. No executable change, no gate rerun.
          NOT the repository tip.
ab99b32   the Stage 10 PLAN-OF-RECORD tip — the current published tip at S10-1 entry.
```

---

## 5 · Operational checkpoints that produced no commit

These are as much a part of the work as the commits `[handoff §2.1]`. **None is a commit, and none
may be rendered as one.**

| Operation | Date / tip | Outcome | Commit |
|---|---|---|---|
| **S8-2** full offline regression | Stage 8 | `validate_task.sh --all`, one invocation, exit 0 in 736 s, 58/58 wrappers each once, zero skips `[handoff Stage 8]` | none — verification only |
| **Authoritative gate 62/62** (pre-S9-L2) | at `238df98` | PASSED, exit 0, 62 wrappers (19 legacy + 43 taxonomy) each exactly once, 0 FAIL, 0 `WARN - skipping` `[handoff §5.1]` | none |
| **S9-L1** live source preflight | 2026-07-31T08:21:16Z | rc **1** — "a source failed", not a crash. 25 rows, 19 `ok` / 6 `robots_denied` `[handoff §6.1]` | none |
| **S9-L2** first live smoke | 2026-07-31T11:35Z | rc 0, run `20260731T113526Z-23992` — **M2** `[handoff §6.2]` | none |
| **S9-L3** second smoke + validate + compare | 2026-07-31T12:07Z | rc 0, run `20260731T120702Z-20188`, comparison 0 invariant violations — **M3** `[handoff §6.3]` | none |
| **Authoritative gate 63/63** | at `8479095` | **FAILED rc 1** — 61 pass / 2 FAIL `[handoff §5.2]` | none |
| **Authoritative gate 63/63** | at `ec9bedc` | PASSED exit 0 — 63/63, 2,386 tests `[handoff §5.4]` | none |
| **S9-L4** live linkcheck | 2026-08-01T08:58:29Z | rc 0, run `20260801T085829Z-40852` — **M4** `[handoff §6.4]` | none |
| Read-only audits | Stage 9 | S9-5C scope preflight, S9-6 contract audit, S9-L4 contract audit and its correction `[handoff §2.1]` | none — analysis only |
| Read-only **Stage 10 contract audit** | 2026-08-01 | produced the Stage 10 contract that S10-0 ratified `[plan §0]` | none |

**Every row above is an operation that was actually executed.** The table counts executed
commit-free operations only.

> **Pending boundary — not an entry in the table above.** The **S10-1 formal L0 validation** is a
> required commit-free boundary of the same kind, but *at the close of the S10-1 document-edit
> boundary it had not run*, so it is deliberately excluded from the executed-operation record. Its
> result is recorded by its own checkpoint report, never prospectively here.

Two structural rules that produced this shape: **live checkpoints never commit**, and **every live
execution needs approval twice — once as a checkpoint and again immediately before the outbound
request** `[plan Stage 9 §7]`.

---

## 6 · Implemented command surface

Read from committed code at `ab99b32`, not from prose `[code]`.

`src/harvest/cli.py:596` defines `COMMANDS` with **exactly six keys**, and `cli.py:88` defines
`PLANNED_COMMANDS = {}`:

| Command | Owner module | Live-exercised? |
|---|---|---|
| `preflight-sources` | `preflight.py` | **yes** — once, S9-L1 |
| `smoke` | `run_cells.py` via `cli.cmd_smoke` | **yes** — twice, S9-L2 and S9-L3 |
| `validate` | `runvalidate.py` | **yes** — against real retained runs, three times |
| `compare-runs` | `compare.py` | **yes** — once, on two real runs |
| `diff` | `compare.py` | **no** — never run against real data |
| `linkcheck` | `linkcheck.py` | **yes** — once, S9-L4 |

**There is no production `harvest` command.** `grep '"harvest"' src/harvest/cli.py` returns **0
matches** `[code]`. `mode: "harvest"` is the only mode `derive_publication_eligibility` accepts, and
it has never run — which is why every retained run is `publication_eligible: false` **by derivation,
not by convention**, and why **M5 is blocked directly** `[handoff §10]`.

**Absent or refused, and recorded as such:**

```text
harvest       DOES NOT EXIST — no key in cli.COMMANDS
promote       DOES NOT EXIST — zero promotion vocabulary anywhere in src/, scripts/,
              schemas/, config/ or tests/, re-checked at ec9bedc [roadmap §11]
refresh       ABSENT; runvalidate REFUSES the mode
smoke-model   ABSENT; runvalidate REFUSES the mode
```

`src/harvest/runvalidate.py:52-53` states the contract directly: `smoke` and `linkcheck` qualify;
**`harvest`, `refresh`, `smoke_model` and `migration` stay REFUSED** — a validator with no semantics
for a mode must refuse it, not agree with it `[code]`.

The **implemented ∩ planned = ∅** partition and the six-command surface are asserted by five
committed guards across four suites `[plan Stage 9]`.

Beyond the CLI, `scripts/harvest/migrate.sh` provides `ax-cases` (dry-run by default, `--apply` under
an explicit `--state-root`) and `entity-assess` `[code]`.

---

## 7 · Live execution and retained evidence

**Four outbound executions in the project's entire history**, each separately approved immediately
before its request, each run exactly once, none retried `[handoff §2.1, §6]`.

### 7.1 S9-L1 — first outbound traffic

`preflight-sources --timeout-sec 20`, 2026-07-31T08:21:16Z, **exit 1**. 25 unique rows sorted by
`source_id`: **19 `ok` · 6 `infrastructure_error`, all `robots_denied`**. No failed row was dropped.
Five of the six share the GitHub `releases.atom` pattern — one root cause, not five.
`microsoft-blogs` reported the only non-null `crawl_delay_sec`: **10.0**. stderr empty, no retry, no
leaked lease root `[handoff §6.1]`.

### 7.2 S9-L2 — M2

One smoke, rc 0, run **`20260731T113526Z-23992`**. 42 JSON + `LATEST_RUN_ID` = 43 paths; 12 cells →
**10 `ok`, 2 `zero_result`** (both `all_below_relevance_threshold`); **32 records**; enrich false.
Validated offline: **`valid: true`**, 42 documents / 43 paths, pointer agreeing. All 62 retained
files hashed before and after validation were byte-identical `[handoff §6.2]`.

**Robots state is time-varying:** `netflix-techblog` was denied at S9-L1 and permitted here.

### 7.3 S9-L3 — M3

Second smoke, rc 0, run **`20260731T120702Z-20188`**, same bounds. Run 1 stayed **byte-identical**,
proved three times (aggregate `58e55eee…56e8f`, 18 documents). `compare-runs`, one invocation,
offline: **18 documents compared / 18 expected · 24 shared excluded · 197 permitted clock changes ·
23 content changes, all manifest `source_preflight[].elapsed_ms` · 0 invariant violations ·
`idempotent: true`** `[handoff §6.3]`.

The 24 shared ledger/rejection documents are **updated in place** and are never presented as
historical A/B snapshots (E9-15). **There is no `--normalize`** (E9-14) — it was removed from the
plan, not implemented quietly.

### 7.4 S9-L4 — M4

One live linkcheck, 2026-08-01T08:58:29Z, rc 0 in both the rc file and at the process boundary,
stderr empty. Base `20260731T120702Z-20188` → run **`20260801T085829Z-40852`** `[handoff §6.4]`:

```text
mode linkcheck · sample requested 20 (19 accepted full records available)
records_checked 19 · identities_fetched 19 · publication_eligible false
19 current-run link_history entries · 0 missing · 0 duplicate · 0 not_checked
access_status   ok 14   ·   robots_denied 5
cells           ok 7    ·   not_run 5
target_http_attempts 19 · target_retries 0 · target_redirect_hops 5
target_fetch_owners 19 · conditional_revalidations 0
```

All 14 `ok` entries returned HTTP 200 with a content hash; the five `robots_denied` entries carry no
HTTP status and no content hash. **`changed_materially` is absent on all 19** — correctly, because
the base records held no prior content hash. **8 of the 19 targets were `arxiv.org`**, the first
target-page pacing on that host. Validated offline: **`valid: true`**, 42 documents / 43 paths.

> **M4 was declared achieved only after BOTH the validator and a separate 19-entry completeness
> inspection**, because `runvalidate` never inspects `access_status`: a run whose entries were all
> `not_checked` would validate cleanly while proving nothing about link health `[handoff §6.4]`.

### 7.5 Retained-root identity and disposition

```text
C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_stage9_retained

20260731T113526Z-23992   smoke       S9-L2   M2
20260731T120702Z-20188   smoke       S9-L3   M3 · linkcheck base
20260801T085829Z-40852   linkcheck   S9-L4   M4

3 run directories x 18 selected-run JSON  = 54
12 ledgers + 12 rejection logs            = 24
1 LATEST_RUN_ID pointer                   =  1
20 next_allowed_at lock files             = 20
                                   total  = 99 regular files · 54 directories
LATEST_RUN_ID   20260801T085829Z-40852
full aggregate  0a14269a00695fb2b259816b570c88a4df40a64f88e782d447f6a1abccab18e3
transient       0 slot_*.lease · 0 owner · 0 pace.lock · 0 .tmp_*
```

`[handoff §7]`. **Disposition, binding:** retain unchanged through Stage 10 and until a **separately
approved disposition checkpoint** — not deleted, cleaned, moved, promoted, treated as publication, or
silently reused. `locks/` is separate pacing infrastructure outside the 43-path contract: **preserve
it, never clean it.** No run was revalidated and no aggregate recomputed while writing this report.

*(Historical only: before S9-L4 the root held two runs, 80 regular files and aggregate
`1dcdfff3…8a94` — the pre-S9-L4 baseline, never the current one.)*

### 7.6 Known attribution limits

- **Per-record attribution of fetch attempts, retries and redirect hops is NOT retained** and cannot
  be reconstructed from the published artifact; only run-level aggregates exist `[handoff §10]`.
- **The 12/5 caps are not fully observable.** Candidates outside a cap are never logged, and **two**
  caps sit between the sighting measurement and `cells[].candidates`, so truncation is **not
  attributable** `[handoff §8]`.
- **Run-1 rejection history is unrecoverable** — the 12 rejection logs are shared cross-run documents
  that run 2 overwrote in place. Never imply a run-1 rejection distribution exists `[handoff §10]`.
- Per-cell manifest `accepted` does **not** necessarily equal that cell's artifact record count,
  because cross-topic classification files a record under the cell its `owner_topic` names. Globally
  they reconcile exactly, 19 = 19 `[plan Stage 9 §5.2]`.
- The five `robots_denied` linkcheck outcomes are *consistent with* a redirect whose destination was
  disallowed. That is recorded in the handoff as an **`[inference]`**, never as per-record evidence.

---

## 8 · Authoritative regression and gate history

**Three authoritative `validate_task.sh --all` invocations, and they must never be conflated**
`[handoff §5]`. None produced a commit.

### 8.1 62/62 at `238df98` — PASSED

One execution: exit 0, **62 wrappers (19 legacy + 43 taxonomy) each exactly once**, executed set
exactly equal to the on-disk `tests/*.sh` set, **0 FAIL, 0 `WARN - skipping`**, runtime paths absent
before and after, production `state/` unchanged, no network `[handoff §5.1]`.

### 8.2 63/63 at `8479095` — **FAILED, rc 1**

One invocation, no retry, no wrapper rerun `[handoff §5.2]`:

```text
final line   == validate_task.sh: FAIL ==
wrappers     63 discovered / 63 executed / each exactly once
             61 passed · 2 FAILED · 0 WARN - skipping
failing      tests/test_taxonomy_target_determinism.sh   8 failures
             tests/test_taxonomy_linkcheck.sh            1 failure
unittest     43 suites · 2,384 tests · 9 failures · 0 errors
repository and retained root unchanged
```

**This is valid historical evidence for that tip. It is not void, not erased, and not superseded out
of history** — it is the evidence that S9-6A was necessary.

- **Finding A** — `test_target_determinism.py` was the **fourth** whole-tree determinism guard site,
  missed by S9-5C1's scope: `cells[].elapsed_sec` is a real monotonic measurement and that suite
  pinned only the UTC clock. It was invisible because the harness routes `run_cells.py` to
  run_cells / recovery / cli / smoke while that suite routes from `targetfetch.py`, and **neither C1
  nor C2 ran `--all`**. *Durable lesson: a checkpoint that changes what `run_cells.run()` writes must
  search **every** suite that compares two runs' bytes.*
- **Finding B** — a spent working-tree census asserting a **non-empty** schema diff, true only while
  S9-6 was uncommitted. **It failed because the checkpoint succeeded.**

**Neither finding was a production defect** `[handoff §5.3]`.

### 8.3 S9-6A — the repair, and 63/63 at `ec9bedc` — PASSED

S9-6A was **test-only, four paths**, wrapper inventory unchanged at 63, no production / schema /
fixture / config / harness / validator / comparator change, and S9-5C3 was not reopened. Nothing was
weakened: no tree hash removed, no content normalized, `elapsed_sec` neither excluded nor zeroed nor
added to any permitted-difference set; anti-vacuity assertions were **added**. Finding B's spent
census was **retired and replaced** by a durable clean-tree assertion, explicitly a *different and
weaker* contract `[handoff §5.3]`.

```text
final line   == validate_task.sh: PASS ==
wrappers     63 discovered / 63 executed / 63 distinct / each EXACTLY ONCE
             executed set exactly equal to the on-disk tests/*.sh set
             0 WARN - skipping · 0 FAIL
unittest     43 suites · 2,386 tests · 0 failures · 0 errors · 0 skips
             (2,384 + the two S9-6A anti-vacuity tests; every suite printed a
              BARE "OK", positive proof of zero skips)
shell        20 wrappers expose their own totals, all "0 failed"
exit code    0 in the external rc file AND at the outward process status — they AGREE
repository and retained root unchanged · no network
```

`[handoff §5.4]`. **The pre-S9-L4 authoritative 63/63 requirement is satisfied.**

> **Launcher rule, learned the hard way at 8.2:** the gate exited 1 while an enclosing background
> compound command surfaced 0, because a trailing command replaced the outward status. Always use
> `cmd >out 2>err; rc=$?; printf '%s\n' "$rc" >rc_file; exit "$rc"`.

**No gate was rerun to produce this report**, and none may be rerun to restate this evidence: Stage
10 changes no executable byte, so `ec9bedc` remains the authoritative executable baseline `[plan §7]`.

---

## 9 · Complete tracked-file inventory

**Range, fixed and deterministic** `[git]`:

```text
git merge-base --is-ancestor 8865c54e2cc8d879410576f247baac4aea149f34 \
                             c3497fa18ed05268edd456472c738a800d0ee21f      → ancestor: YES
git rev-list --count 8865c54e..c3497fa                                     → 73
git diff --name-status 8865c54e..c3497fa                                   → 269 paths
                                                                              267 A · 2 M
```

The **two modified paths** are the only two pre-existing tracked files this task ever touched:

```text
M  .gitignore                 the ONE authorized runtime-namespace ignore line
                              (IMPLEMENTATION_PLAN.md §10.1)
M  scripts/validate_task.sh   Stage 8 harness wiring (CF-4)
```

**No protected path appears in the diff** — a grep of the 269 rows against the 18 protected paths
returns **0 matches** `[git]`. That is the strongest single statement this report makes about the
matrix boundary: the protected matrix family was proved untouched by construction, not by assertion.

### 9.1 Distribution, reconciled

| Group | Paths | A | M |
|---|---:|---:|---:|
| `tests/fixtures/**` | 77 | 77 | 0 |
| `tests/harvest/**` | 44 | 44 | 0 |
| `tests/test_taxonomy_*.sh` (wrappers) | 44 | 44 | 0 |
| `src/harvest/**` | 39 | 39 | 0 |
| `docs/harvest/**` | 25 | 25 | 0 |
| `schemas/harvest/**` | 13 | 13 | 0 |
| `config/harvest/**` | 13 | 13 | 0 |
| `scripts/harvest/**` | 10 | 10 | 0 |
| root support files | 4 | 2 | 2 |
| **total** | **269** | **267** | **2** |

This reproduces the accepted read-only audit's distribution exactly, with **one classification point
that must be stated rather than forced**:

> The audit's reference figures listed **"legacy wrappers 19"**. Those 19 wrappers **do not appear in
> this range at all**, and correctly so: they pre-date the implementation-start anchor `8865c54e`.
> The range adds **44 taxonomy wrappers**; 44 + 19 = the **63** current inventory. Likewise
> `requirements.txt` and `constraints.txt` (1 each) are folded into the 4 "root support files"
> alongside the two modified paths. **The authoritative total of 269 is unchanged.**

**Appendix A lists all 269 paths individually**, grouped by stable repository area, with each path's
Git status in the range. No path is omitted for repetitiveness.

---

## 10 · Schemas, artifacts and lifecycle

Thirteen committed JSON Schemas at `schemas/harvest/` `[code]`: `taxonomy.v1` · `facet_vocabulary.v1`
· `facets.generated.v1` · `discovery_lane.v1` · `candidate_pool.v1` · `record.v1` · `cell_artifact.v1`
· `topic_artifact.v1` · `run_manifest.v1` · `ledger.v1` · `rejection.v1` · `alias_conflict.v1` ·
`coverage_report.v1`. **No `schema_version` was ever bumped**: both S9-5C2's four sighting integers
and S9-6's `base_run_id` were shaped so pre-existing manifests stay valid untouched `[plan Stage 9]`.

**Exact run accounting** `[roadmap §6.1]`:

```text
12 cell JSON + 3 topic JSON + 1 coverage + 1 alias_conflicts + 1 manifest = 18 SELECTED-RUN
12 shared ledgers + 12 shared rejection logs                              = 24 SHARED
                                                          42 JSON + 1 pointer = 43 paths
```

**E9-11 in practice:** two runs are **60 JSON + 1 pointer**, not 84 — each adds its own 18 and both
update the same 24.

Five lifecycle classes, kept strictly apart:

| Class | Contents | Behaviour |
|---|---|---|
| **Per-run immutable output** | `runs/<id>/**` — the 18 selected-run documents | written once; run 1 proved byte-identical across a second run, a validation and a comparison |
| **Shared mutable state** | the 12 ledgers and 12 rejection logs | **updated in place**, cross-run, latest-state only — never historical snapshots (E9-15) |
| **Unpersisted deterministic stdout** | `preflight-sources` bare JSON array; `compare-runs` and `diff` reports; the smoke/linkcheck summaries | rendered by `artifacts.serialize`, never written to disk |
| **Repository publication paths** | `data/harvested/**` | **absent.** `diff` distinguishes absent from present-but-empty and **never creates it** |
| **External retained evidence** | the Stage 9 root and its `locks/` | outside the repository and outside the 508-path baseline |

The pointer `LATEST_RUN_ID` moves **last, or not at all**; a linkcheck is a **new run derived from a
base run** with the same 43-path shape, `mode: "linkcheck"`, append-only `link_history`, deterministic
first-N sampling, and **absolute base-run byte-immutability** `[plan Stage 9 §6.6]`.

**The expected stable publication set is 16 JSON files** — 12 category artifacts + 3 topic aggregates
+ 1 publication manifest — and **none of them exists** `[roadmap §6.3]`. The AX migration apply bundle
is exactly 3 JSON files and has never been produced against the repository default root.

---

## 11 · Validation-command ledger

Spine: the acceptance commands **0–24** of `docs/harvest/IMPLEMENTATION_PLAN.md` §14 — **design
input, corrected here against what actually happened.** Its "completion requires 0–22 green, plus
23" clause was **not** the standard Stage 8/9 actually applied.

> **Naming correction, stated rather than silently rewritten.** Seven wrapper names in §14 were never
> built under those names: `test_taxonomy_fixture_determinism.sh`, `test_taxonomy_cross_topic.sh`,
> `test_taxonomy_cell.sh`, `test_taxonomy_concurrency.sh`, `test_taxonomy_promote_txn.sh`,
> `test_taxonomy_matrix_boundary.sh`, `test_taxonomy_staging_isolation.sh` — all **absent** `[code]`.
> The delivered 44-wrapper set covers the same concerns under different names (e.g. determinism lives
> in `test_taxonomy_target_determinism.sh`). §14's numbering is preserved below for traceability, not
> because it describes the shipped harness.

| # | Purpose | Actually run? | Evidence / checkpoint | Result | Data | Limits |
|---|---|---|---|---|---|---|
| 0 | protected baseline · ignore probe · version print | **yes**, repeatedly | every documentation checkpoint incl. S10-0 L0 | rc 0, **18/18** | repo | `harvest.sh preflight` as spelled in §14 is not a command; `preflight-sources` is |
| 1 | configuration completeness / cell-set exactness | **yes** | `test_taxonomy_config.sh`, inside every full gate | green | fixture | — |
| 2 | fixture determinism | **yes, under other names** | `test_taxonomy_target_determinism.sh` (90 tests at S9-6A) | green | fixture | §14's wrapper name never existed |
| 3 | schema validation incl. discriminated union | **yes** | `test_taxonomy_schema.sh` | green | fixture | — |
| 4 | identity, canonicalization, alias trust/conflicts | **yes** | `test_taxonomy_identity.sh`, `_aliases.sh` | green | fixture | — |
| 5 | HTTP baseline: robots, redirects, timeouts, retries | **yes** | `test_taxonomy_http.sh` | green | fixture | — |
| 6 | cross-process per-domain concurrency and spacing | **yes** | `test_taxonomy_domain_throttle.sh` | green in every gate | local server | **intermittent signatures UNRESOLVED**; never accept as a permanent flake |
| 7 | request-count and wall-clock budgets | **yes** | `test_taxonomy_budget.sh` | green | fixture | — |
| 8 | adapters incl. bounded seed adapter | **yes** | `test_taxonomy_adapters.sh` | green | fixture | — |
| 9 | classification precedence, dedupe, cross-topic | **partly renamed** | `_classify.sh`, `_dedupe.sh`; no `_cross_topic.sh` | green | fixture | cross-topic covered inside classify/records suites |
| 10 | cell worker, concurrency, recovery | **partly renamed** | `_recovery.sh`, `_adapter_concurrency.sh`, `_cell_artifact.sh` | green | fixture | `_cell.sh` / `_concurrency.sh` never existed |
| 11 | transaction-safe promotion, fault-injected | **NEVER RUN** | — | — | — | **`promote` does not exist**; descoped by plan §14 erratum E11 |
| 12 | matrix boundary | **partly** | protected-baseline verifier + `git diff --exit-code` over the 7 matrix paths | rc 0 | repo | `_matrix_boundary.sh` never existed; the boundary is enforced by the protected baseline |
| 13 | existing suites unchanged (mandatory gate) | **yes** | `test_matrix_harvest.sh` 64 passed · `test_parallel_harvest.sh` 62 passed, inside `--all` | green | fixture | — |
| 14 | staging isolation / untracked-baseline scoping | **yes, by other means** | the harness's four-runtime-path guard before *and* after; the 508-path baseline check | green | repo | `_staging_isolation.sh` never existed |
| 15 | AX migration dry-run + apply twice | **yes, ONLY under injected temporary roots** | `test_taxonomy_migration.sh` | green | fixture / temp root | **no operational default-root `--apply` has ever occurred**; `state/taxonomy_harvest/` is absent by intent |
| 16 | entity-registry read-only assessment | **yes** | `migrate.sh entity-assess` → `ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md` | 1,161 assessed, **0 migrated** | real registry | read-only; destination taxonomy is an open product decision |
| 17 | full offline suite | **yes — 4 documented invocations** | S8-2 58/58 · 62/62 @ `238df98` · 63/63 @ `8479095` **FAILED** · 63/63 @ `ec9bedc` PASSED | see §8 | fixture | run only at its documented checkpoints; never rerun to restate a result |
| 18 | live source preflight | **yes — once** | S9-L1 | rc 1, 19 ok / 6 denied | **real** | exit 1 means a source failed, not a crash |
| 19 | bounded live smoke + validate | **yes — once** | S9-L2 → M2 | rc 0, `valid: true` | **real** | ran against an **external retained root**, not the `state/taxonomy_harvest/` path §14 assumes |
| 20 | second smoke + validate + comparison | **yes — once** | S9-L3 → M3 | rc 0, 0 violations, `idempotent: true` | **real** | **`--normalize` does not exist** (E9-14); it was removed from the plan, not implemented quietly |
| 21 | linkcheck + validate | **yes — once** | S9-L4 → M4 | rc 0, `valid: true`, 19/19 checked | **real** | run id supplied explicitly; pointer moved last |
| 22 | prove tracked publication output unchanged | **NOT RUN ON REAL DATA** | `diff` exercised only against temp roots and an absent `data/harvested/` | — | fixture only | `data/harvested/` remains **absent**; `diff` reports absence as a real answer and exits 0 |
| 23 | promotion on the verified fixture, isolated root | **NEVER RUN** | — | — | — | **`promote` does not exist**; zero lines implemented |
| 24 | opt-in model-search smoke | **NEVER RUN** | — | — | — | **`smoke-model` does not exist**; `runvalidate` refuses the mode |

**Summary: 0–10 and 12–21 were satisfied in substance (several under different wrapper names);
22 was never run on real data; 23 and 24 were never run at all.** The plan's own completion clause
("0–22 green, plus 23") was therefore **never met as written**, and Stage 9 did not claim it was —
Stage 9's exit criteria are its own, all 18 met `[plan Stage 9 §9]`.

---

## 12 · Product milestones M1–M7

`[roadmap §3]`:

| Milestone | Status | Evidence |
|---|---|---|
| **M1** — core engine and offline regression | **COMPLETE** | `validate_task.sh --all` exit 0, 58/58 wrappers, zero skips (S8-2) |
| **M2** — first real staged taxonomy output | **COMPLETE 2026-07-31** | run `20260731T113526Z-23992`, validated |
| **M3** — repeatability and calibration | **COMPLETE 2026-07-31** | run `20260731T120702Z-20188`; comparison 0 violations, `idempotent: true` |
| **M4** — link-health validation | **COMPLETE 2026-08-01** | run `20260801T085829Z-40852`; 19/19 terminal results |
| **M5** — reviewed production candidate | **UNOPENED** | needs a production `harvest` command that does not exist, an enrichment budget design, a candidate artifact and producer, and a review artifact with acceptance criteria (G4, G9) |
| **M6** — published JSON dataset | **NOT STARTED** | `promote` has zero lines against a detailed design (G7); publication **0 of 16** |
| **M7** — website integration / recurring refresh | **NOT STARTED** | unowned, outside this repository (G10, G6) |

**Closing the original Stage 0–10 task is not equivalent to M5, M6 or M7.** The roadmap places
M5→M7 at **22–32 further checkpoints** from the Stage 9 close, mostly undesigned `[roadmap §4.0]`.
Stage 10 delivers documents; it delivers no milestone.

---

## 13 · Known limitations and deferred work

**Recording an item does not resolve it.** Every entry below is **OPEN**, and each would need its own
approved checkpoint by name `[handoff §10]`, `[plan §9]`.

| # | Item | Class |
|---|---|---|
| 1 | Editorial thresholds remain **provisional** — quality and audience-fit saturated at 1.000 and rejected nothing; only 19 scored records over a ~32-minute horizon | evidence limitation |
| 2 | The **12/5 caps** remain provisional and **not fully attributable** — two caps sit between the sighting measurement and `cells[].candidates` | evidence limitation |
| 3 | **Immutable per-run rejection snapshots (S9-5C3) EXPLICITLY DEFERRED** — reopening needs a new design and explicit approval; it must **not** be treated as a small additive schema change | product decision |
| 4 | **Run-1 rejection reasons unrecoverable** — run 2 overwrote the shared logs in place | evidence limitation |
| 5 | **No production `harvest` command** — blocks M5 directly | implementation limitation |
| 6 | **`smoke-model` and `refresh` absent**; `runvalidate` refuses both, plus `harvest` and `migration` | implementation limitation |
| 7 | **M5 review artifact and acceptance process undefined** — no artifact, no schema, no owner | successor milestone |
| 8 | **Promotion implementation absent** — zero promotion vocabulary anywhere | successor milestone |
| 9 | **Website integration unowned** — outside this repository | successor milestone |
| 10 | **Domain-throttle intermittent signatures UNRESOLVED** — green in every gate is an observation, never a resolution, and never a permanent flake | operational debt |
| 11 | **Changed-mode routing does not select `tests/harvest/*.py`** — only `--all` covers them; an explicit-mode run over a test module routes to **zero wrappers** and must never be reported as validation | operational debt |
| 12 | **Per-record retry/redirect attribution absent** and not reconstructable | evidence limitation |
| 13 | **Stale `cli.py` pre-request `CliError` comment** — true for five commands, false for `linkcheck`, whose refusals can fire after fetching and after partial writes (roadmap G18) | documentation debt |
| 14 | **The original 508-path untracked baseline is out of scope** (roadmap G17) — baseline-verified and used as an invariant; cleaning or gitignoring it is a separate decision | out of scope |
| 15 | **Matrix identity semantic fork OPEN** — gated by the five S10-0 reconsideration gates, and **gating is not resolution**; no gate is marked satisfied | product decision |
| 16 | **Retained Stage 9 root disposition pending** its own approved checkpoint | operational debt |
| 17 | **S6-L, Stage 6's bounded live smoke, remains UNEXECUTED and UNAUTHORIZED** — no Stage 9 execution discharges it | operational debt |
| 18 | **Operational `migrate.sh ax-cases --apply` against the repository default root remains unapproved**; `state/taxonomy_harvest/` is absent **by intent** | operational debt |
| 19 | **CF-6:** 33 of the taxonomy wrappers assert `config/` is unmodified, so no checkpoint that edits `config/` can pass the gate before committing | operational debt |
| 20 | **Stage 7's temporary default-root incident during S7-5 development is historical fact** and must not be rewritten as though it never happened | documentation debt |
| 21 | `scripts/harvest/hash_tree.py` and `config/harvest/watchlists/oss-milestones.v1.json` have **zero consumers and no behavioural suite** | implementation limitation |
| 22 | The roadmap's §1.1 stage percentage still reads `10 of 12 = 83 %`, correct only up to the S9-C closeout | documentation debt |

---

## 14 · Explicit non-claims

**This implementation report does NOT claim:**

```text
production readiness
a reviewed production candidate
publication eligibility
promotion
published JSON
website integration
recurring refresh
matrix-path deprecation
matrix unification
M5, M6 or M7 completion
```

And, stated plainly because these are the numbers most easily overclaimed:

```text
publication          = ZERO   (0 of 16 expected stable published JSON files)
promotion            = ZERO   (no promotion code exists in any form)
website consumption  = ZERO   (unowned, outside this repository)
```

Every retained run is `publication_eligible: false` **by derivation**, not by convention: `smoke` and
`linkcheck` are non-`harvest` modes and `derive_publication_eligibility` refuses every non-`harvest`
mode `[code]`. **A Stage 9 smoke is not a production candidate and can never be promoted.**

Nor does this report claim anything about its own status beyond the drafting boundary: **the S10-1
report-drafting boundary is complete, and the S10-1 checkpoint remains incomplete until a separate
formal L0 validation passes and the validated three-path set is committed. This report does not
assert the outcome of that validation in either direction. S10-2 and S10-C are unapproved; Stage 10
is not closed.**

---

## 15 · Repository state snapshot at S10-1 entry

**A dated snapshot, not an enduring invariant.** Observed 2026-08-02, before this document existed
`[obs]`:

```text
HEAD = local main = local origin/main   ab99b32781fa07e2e06de4097ef201dba6d765d1
subject                                 docs(harvest): plan stage 10 final report
parent                                  c3497fa18ed05268edd456472c738a800d0ee21f
divergence                              0 behind / 0 ahead
tracked worktree                        clean · index empty
untracked baseline                      the original 508-name set, 0 added / 0 missing
protected baseline                      18/18 — carried from the S10-0 formal L0 validation,
                                        NOT rerun for this report
wrapper inventory                       63 (19 legacy + 44 taxonomy)
runtime paths                           state/taxonomy_harvest · data/harvested · runs ·
                                        LATEST_RUN_ID — ALL ABSENT
```

The protected-baseline verifier was **deliberately not rerun** merely to restate its prior result;
Stage 10 documentation checkpoints are **L0 only** `[plan §7]`.

---

## 16 · External evidence references

**All of the following live outside the repository and outside the 508-path untracked baseline.**
None has a repository path, and none may be given one `[handoff §11.2]`.

| Evidence | Location / identity |
|---|---|
| Retained Stage 9 evidence root | `ClaudeWorkspace\axCaseResearch4_stage9_retained` — 3 runs, 99 files / 54 dirs, aggregate `0a14269a…18e3` |
| Retained run IDs | `20260731T113526Z-23992` · `20260731T120702Z-20188` · `20260801T085829Z-40852` |
| S9-L1 preflight logs | `ClaudeWorkspace\scratchpad\s9_l1_preflight_20260731T082116Z_540.*` |
| S9-L2 smoke + validate | `…\s9_l2_smoke_20260731T113503Z_1650.*` |
| S9-L3 smoke + validate + compare | `…\s9_l3_smoke_20260731T120639Z_1156.*` |
| 62/62 gate | `…\s9_authoritative_full_gate_20260731T100012Z_785.*` |
| 63/63 gate — FAILED | `…\s9_authoritative_63_gate_20260801T035233Z.*` |
| 63/63 gate — PASSED | `…\s9_authoritative_63_gate_ec9bedc_20260801T064238Z.*` |
| S9-L4 before/after + live + validate | `…\s9_l4_evidence_20260801T085807Z\` · `…\s9_l4_linkcheck_20260801T085829Z.*` · `…\s9_l4_validate_…*` |
| Progress report (supporting material, **not** authority) | `ClaudeWorkspace\axCaseResearch4_reports\HARVEST_PROGRESS_REPORT.html`, sha256 `ee9f7edd859502c365de2a9f175c65d2769d281905fb23f4c50a52af45ec859f` |

Each log set is `stdout` / `stderr` / `rc`. **No log artifact is retained inside the repository**, and
that is deliberate: it is what kept the untracked baseline at exactly 508 for the authoritative gate.

---

## 17 · Publication and successor state

```text
Stage 9            CLOSED AND PUBLISHED                       c3497fa
S10-0              PUBLISHED                                  ab99b32
S10-1              REPORT-DRAFTING BOUNDARY COMPLETE.
                   The CHECKPOINT remains OPEN until a separate formal L0
                   validation passes AND the validated three-path set is
                   committed through a separately approved boundary.
S10-2              UNAPPROVED   (docs/harvest/CONVERGENCE_NOTE.md — absent)
S10-C              UNAPPROVED   (Stage 10 completion handoff — absent)
M5, M6, M7         OPEN
retained root      PRESERVED, unchanged, disposition pending its own approval
publication        ZERO · promotion ZERO · website consumption ZERO
```

**S10-1's remaining boundaries are formal L0 validation and an atomic commit**, over exactly three
paths — `docs/harvest/IMPLEMENTATION_REPORT.md` (new),
`docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` and `docs/harvest/TODO.md` — each separately approved.
**Which of them is next at any given moment is a property of the checkpoint record, not of this
report**, and this report does not assert that either has or has not occurred. Nothing here
authorizes any of them, nor S10-2, S10-C, or any successor milestone.

---

## Appendix A — complete file inventory

All **269** tracked paths changed in the fixed historical range
`8865c54e2cc8d879410576f247baac4aea149f34..c3497fa18ed05268edd456472c738a800d0ee21f`, grouped by
stable repository area and sorted within each group. Status is the Git status **in this range**:
`A` added, `M` modified. Generated from `git diff --name-status`; no path is omitted.

**This inventory ends at `c3497fa` by construction.** It contains no Stage 10 path: neither S10-0's
`STAGE_10_IMPLEMENTATION_PLAN.md` nor this report appears in it.

### A1 — `src/harvest/**` — production Python (39)

```text
A   src/harvest/__init__.py
A   src/harvest/adapters/__init__.py
A   src/harvest/adapters/base.py
A   src/harvest/adapters/feed.py
A   src/harvest/adapters/jsonapi.py
A   src/harvest/adapters/seed.py
A   src/harvest/aliases.py
A   src/harvest/artifacts.py
A   src/harvest/budget.py
A   src/harvest/classify.py
A   src/harvest/cli.py
A   src/harvest/compare.py
A   src/harvest/coverage.py
A   src/harvest/dedupe.py
A   src/harvest/domainlease.py
A   src/harvest/extract.py
A   src/harvest/facetassign.py
A   src/harvest/facets.py
A   src/harvest/fixtures.py
A   src/harvest/httpclient.py
A   src/harvest/ledger.py
A   src/harvest/linkcheck.py
A   src/harvest/migrate/__init__.py
A   src/harvest/migrate/ax_cases.py
A   src/harvest/migrate/base.py
A   src/harvest/migrate/entity_assess.py
A   src/harvest/pool.py
A   src/harvest/preflight.py
A   src/harvest/records.py
A   src/harvest/request_key.py
A   src/harvest/run_cells.py
A   src/harvest/runvalidate.py
A   src/harvest/scheduler.py
A   src/harvest/schema.py
A   src/harvest/slug.py
A   src/harvest/sourcecache.py
A   src/harvest/targetfetch.py
A   src/harvest/urlkey.py
A   src/harvest/verify.py
```

### A2 — `scripts/harvest/**` — entry points and checkers (10)

```text
A   scripts/harvest/check_config.py
A   scripts/harvest/check_facets.py
A   scripts/harvest/check_fixtures.py
A   scripts/harvest/gen_facet_schema.py
A   scripts/harvest/gen_protected_baseline.sh
A   scripts/harvest/harvest.sh
A   scripts/harvest/hash_tree.py
A   scripts/harvest/migrate.sh
A   scripts/harvest/protected_baseline.py
A   scripts/harvest/verify_protected_baseline.sh
```

### A3 — `schemas/harvest/**` — JSON Schemas (13)

```text
A   schemas/harvest/alias_conflict.v1.json
A   schemas/harvest/candidate_pool.v1.json
A   schemas/harvest/cell_artifact.v1.json
A   schemas/harvest/coverage_report.v1.json
A   schemas/harvest/discovery_lane.v1.json
A   schemas/harvest/facet_vocabulary.v1.json
A   schemas/harvest/facets.generated.v1.json
A   schemas/harvest/ledger.v1.json
A   schemas/harvest/record.v1.json
A   schemas/harvest/rejection.v1.json
A   schemas/harvest/run_manifest.v1.json
A   schemas/harvest/taxonomy.v1.json
A   schemas/harvest/topic_artifact.v1.json
```

### A4 — `config/harvest/**` — taxonomy, policy, vocabularies (13)

```text
A   config/harvest/canonicalization.v1.json
A   config/harvest/coverage_targets.v1.json
A   config/harvest/facets/business-functions.v1.json
A   config/harvest/facets/industries.v1.json
A   config/harvest/facets/legacy_industry_map.v1.json
A   config/harvest/facets/use-case-types.v1.json
A   config/harvest/migration_overrides.v1.json
A   config/harvest/policy.v1.json
A   config/harvest/precedence.v1.json
A   config/harvest/topics/cases.v1.json
A   config/harvest/topics/discourse.v1.json
A   config/harvest/topics/research-and-models.v1.json
A   config/harvest/watchlists/oss-milestones.v1.json
```

### A5 — `tests/harvest/**` — Python test modules (44)

```text
A   tests/harvest/__init__.py
A   tests/harvest/test_adapter_concurrency.py
A   tests/harvest/test_adapters.py
A   tests/harvest/test_aliases.py
A   tests/harvest/test_artifacts.py
A   tests/harvest/test_budget.py
A   tests/harvest/test_cell_artifact.py
A   tests/harvest/test_classify.py
A   tests/harvest/test_cli.py
A   tests/harvest/test_compare.py
A   tests/harvest/test_coverage.py
A   tests/harvest/test_coverage_report.py
A   tests/harvest/test_customer_interaction.py
A   tests/harvest/test_dedupe.py
A   tests/harvest/test_domain_throttle.py
A   tests/harvest/test_eligibility.py
A   tests/harvest/test_extract.py
A   tests/harvest/test_facet_ambiguity.py
A   tests/harvest/test_facet_identity.py
A   tests/harvest/test_facet_states.py
A   tests/harvest/test_facetassign.py
A   tests/harvest/test_facets.py
A   tests/harvest/test_http.py
A   tests/harvest/test_identity.py
A   tests/harvest/test_ledger.py
A   tests/harvest/test_linkcheck.py
A   tests/harvest/test_manifest.py
A   tests/harvest/test_migration.py
A   tests/harvest/test_pool.py
A   tests/harvest/test_preflight.py
A   tests/harvest/test_records_build.py
A   tests/harvest/test_recovery.py
A   tests/harvest/test_run_cells.py
A   tests/harvest/test_schema.py
A   tests/harvest/test_smoke.py
A   tests/harvest/test_source_cache.py
A   tests/harvest/test_target_accounting.py
A   tests/harvest/test_target_determinism.py
A   tests/harvest/test_target_evidence.py
A   tests/harvest/test_target_fetch.py
A   tests/harvest/test_target_fixtures.py
A   tests/harvest/test_target_ownership.py
A   tests/harvest/test_verify.py
A   tests/harvest/throttle_worker.py
```

### A6 — `tests/fixtures/**` — frozen fixture corpus (77)

```text
A   tests/fixtures/harvest/MANIFEST.json
A   tests/fixtures/harvest/robots/arxiv.org.json
A   tests/fixtures/harvest/robots/aws.amazon.com.json
A   tests/fixtures/harvest/robots/blog.cloudflare.com.json
A   tests/fixtures/harvest/robots/blog.google.json
A   tests/fixtures/harvest/robots/blogs.microsoft.com.json
A   tests/fixtures/harvest/robots/blogs.nvidia.com.json
A   tests/fixtures/harvest/robots/engineering.fb.com.json
A   tests/fixtures/harvest/robots/export.arxiv.org.json
A   tests/fixtures/harvest/robots/github.com.json
A   tests/fixtures/harvest/robots/hn.algolia.com.json
A   tests/fixtures/harvest/robots/huggingface.co.json
A   tests/fixtures/harvest/robots/netflixtechblog.com.json
A   tests/fixtures/harvest/robots/openai.com.json
A   tests/fixtures/harvest/robots/robots-5xx.test.json
A   tests/fixtures/harvest/robots/rss.arxiv.org.json
A   tests/fixtures/harvest/robots/simonwillison.net.json
A   tests/fixtures/harvest/robots/techcrunch.com.json
A   tests/fixtures/harvest/robots/tgt-robots-denied.harvest.test.json
A   tests/fixtures/harvest/robots/tgt.harvest.test.json
A   tests/fixtures/harvest/robots/www.anthropic.com.json
A   tests/fixtures/harvest/robots/www.federalregister.gov.json
A   tests/fixtures/harvest/robots/www.nist.gov.json
A   tests/fixtures/harvest/robots/www.oneusefulthing.org.json
A   tests/fixtures/harvest/robots/www.producthunt.com.json
A   tests/fixtures/harvest/sources/fx_anthropic_customers.json
A   tests/fixtures/harvest/sources/fx_arxiv_cs_ai.json
A   tests/fixtures/harvest/sources/fx_arxiv_cs_lg.json
A   tests/fixtures/harvest/sources/fx_aws_ml_blog.json
A   tests/fixtures/harvest/sources/fx_cloudflare_blog.json
A   tests/fixtures/harvest/sources/fx_federal_register_ai.json
A   tests/fixtures/harvest/sources/fx_google_ai_blog.json
A   tests/fixtures/harvest/sources/fx_google_blog.json
A   tests/fixtures/harvest/sources/fx_hf_blog.json
A   tests/fixtures/harvest/sources/fx_hn_algolia.json
A   tests/fixtures/harvest/sources/fx_lm_eval_harness.json
A   tests/fixtures/harvest/sources/fx_meta_engineering.json
A   tests/fixtures/harvest/sources/fx_microsoft_blogs.json
A   tests/fixtures/harvest/sources/fx_netflix_techblog.json
A   tests/fixtures/harvest/sources/fx_nist_news.json
A   tests/fixtures/harvest/sources/fx_nvidia_blog.json
A   tests/fixtures/harvest/sources/fx_oneusefulthing.json
A   tests/fixtures/harvest/sources/fx_openai_evals.json
A   tests/fixtures/harvest/sources/fx_openai_news.json
A   tests/fixtures/harvest/sources/fx_oss_langchain.json
A   tests/fixtures/harvest/sources/fx_oss_mcp_servers.json
A   tests/fixtures/harvest/sources/fx_oss_ollama.json
A   tests/fixtures/harvest/sources/fx_producthunt.json
A   tests/fixtures/harvest/sources/fx_simonwillison.json
A   tests/fixtures/harvest/sources/fx_techcrunch_ai.json
A   tests/fixtures/harvest/targets/tgt_accepted_1.json
A   tests/fixtures/harvest/targets/tgt_accepted_2.json
A   tests/fixtures/harvest/targets/tgt_accepted_3.json
A   tests/fixtures/harvest/targets/tgt_accepted_4.json
A   tests/fixtures/harvest/targets/tgt_canonical_circular_1.json
A   tests/fixtures/harvest/targets/tgt_canonical_circular_2.json
A   tests/fixtures/harvest/targets/tgt_canonical_conflicting.json
A   tests/fixtures/harvest/targets/tgt_canonical_cross_host.json
A   tests/fixtures/harvest/targets/tgt_canonical_same_host.json
A   tests/fixtures/harvest/targets/tgt_empty_body.json
A   tests/fixtures/harvest/targets/tgt_forbidden.json
A   tests/fixtures/harvest/targets/tgt_gone.json
A   tests/fixtures/harvest/targets/tgt_non_html_json.json
A   tests/fixtures/harvest/targets/tgt_non_html_pdf.json
A   tests/fixtures/harvest/targets/tgt_not_found.json
A   tests/fixtures/harvest/targets/tgt_ok_plain.json
A   tests/fixtures/harvest/targets/tgt_redirect_permanent_1.json
A   tests/fixtures/harvest/targets/tgt_redirect_permanent_2.json
A   tests/fixtures/harvest/targets/tgt_redirect_permanent_3.json
A   tests/fixtures/harvest/targets/tgt_redirect_temporary_1.json
A   tests/fixtures/harvest/targets/tgt_redirect_temporary_2.json
A   tests/fixtures/harvest/targets/tgt_redirect_temporary_3.json
A   tests/fixtures/harvest/targets/tgt_robots_denied.json
A   tests/fixtures/harvest/targets/tgt_server_error.json
A   tests/fixtures/taxonomy/protected_paths.txt
A   tests/fixtures/taxonomy/protected_sha256.txt
A   tests/fixtures/taxonomy/untracked_baseline.txt
```

### A7 — `tests/test_taxonomy_*.sh` — wrappers (44)

```text
A   tests/test_taxonomy_adapter_concurrency.sh
A   tests/test_taxonomy_adapters.sh
A   tests/test_taxonomy_aliases.sh
A   tests/test_taxonomy_artifacts.sh
A   tests/test_taxonomy_budget.sh
A   tests/test_taxonomy_cell_artifact.sh
A   tests/test_taxonomy_classify.sh
A   tests/test_taxonomy_cli.sh
A   tests/test_taxonomy_compare.sh
A   tests/test_taxonomy_config.sh
A   tests/test_taxonomy_coverage.sh
A   tests/test_taxonomy_coverage_report.sh
A   tests/test_taxonomy_customer_interaction.sh
A   tests/test_taxonomy_dedupe.sh
A   tests/test_taxonomy_domain_throttle.sh
A   tests/test_taxonomy_eligibility.sh
A   tests/test_taxonomy_extract.sh
A   tests/test_taxonomy_facet_ambiguity.sh
A   tests/test_taxonomy_facet_identity.sh
A   tests/test_taxonomy_facet_states.sh
A   tests/test_taxonomy_facetassign.sh
A   tests/test_taxonomy_facets.sh
A   tests/test_taxonomy_http.sh
A   tests/test_taxonomy_identity.sh
A   tests/test_taxonomy_ledger.sh
A   tests/test_taxonomy_linkcheck.sh
A   tests/test_taxonomy_manifest.sh
A   tests/test_taxonomy_migration.sh
A   tests/test_taxonomy_pool.sh
A   tests/test_taxonomy_preflight.sh
A   tests/test_taxonomy_protected_baseline.sh
A   tests/test_taxonomy_records.sh
A   tests/test_taxonomy_recovery.sh
A   tests/test_taxonomy_run_cells.sh
A   tests/test_taxonomy_schema.sh
A   tests/test_taxonomy_smoke.sh
A   tests/test_taxonomy_source_cache.sh
A   tests/test_taxonomy_target_accounting.sh
A   tests/test_taxonomy_target_determinism.sh
A   tests/test_taxonomy_target_evidence.sh
A   tests/test_taxonomy_target_fetch.sh
A   tests/test_taxonomy_target_fixtures.sh
A   tests/test_taxonomy_target_ownership.sh
A   tests/test_taxonomy_verify.sh
```

### A8 — `docs/harvest/**` — plans, handoffs, roadmap (25)

```text
A   docs/harvest/DOMAIN_FACETS_PROPOSAL.md
A   docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md
A   docs/harvest/FACET_VOCABULARY.md
A   docs/harvest/HANDOFF_CURRENT.md
A   docs/harvest/IMPLEMENTATION_PLAN.md
A   docs/harvest/INVENTORY_AND_REUSE_MAP.md
A   docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md
A   docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_3_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_4_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_5_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_8_IMPLEMENTATION_PLAN.md
A   docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md
A   docs/harvest/TODO.md
A   docs/harvest/handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md
A   docs/harvest/handoffs/HANDOFF_STAGE_2_FACETS_APPROVED_DESIGN_2026-07-28.md
A   docs/harvest/handoffs/HANDOFF_STAGE_3_COMPLETE_2026-07-29.md
A   docs/harvest/handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md
A   docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md
A   docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md
A   docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md
A   docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md
A   docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md
```

### A9 — root support files (4)

```text
M   .gitignore
A   constraints.txt
A   requirements.txt
M   scripts/validate_task.sh
```

**Appendix A total: 269 paths, reconciling exactly with the 269 reported in §9.**
Generated from `git diff --name-status 8865c54e..c3497fa`; not hand-transcribed.
