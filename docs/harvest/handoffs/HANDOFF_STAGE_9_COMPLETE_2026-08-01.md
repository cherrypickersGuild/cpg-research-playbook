# Handoff — Stage 9 COMPLETE (bounded live validation)

```text
Date                       2026-08-01
Closing executable         ec9bedc5f209927ffd2899126ff20c2b31af0245
implementation baseline    test(harvest): repair authoritative full-gate findings
Closeout commit            The S9-C closeout commit is the commit CONTAINING this
                           handoff. Its SHA is intentionally not self-recorded, and
                           this document asserts nothing about whether it has been
                           published.
Stage 9 plan of record     docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md
Prior stage authority      docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md
Milestones                 M2 ACHIEVED · M3 ACHIEVED · M4 ACHIEVED · M5 UNOPENED
Publication / promotion    ZERO
```

**This handoff approves nothing.** It records what Stage 9 delivered. **Stage 10, M5, promotion,
publication, website integration and any future network activity each require their own separate
approval by name**, with an exact allowed-path set declared up front.

**Stage 9 completion is not production readiness.** Stage 9 delivered a **retained, validated,
unpublished evidence corpus** — two smoke calibration runs and one linkcheck evidence run. It did
**not** deliver a production-quality enriched harvest, a reviewed production candidate, publication
eligibility, promotion into `data/harvested/`, website integration, recurring refresh, a production
`harvest` command, or `smoke-model`.

---

## 1 · Starting state

Stage 9 opened on the published Stage 8 tip `bf067303a01fa80d1421f9eef7030cbadf805733`, with:

- the discovery → extraction → classification → verification → faceting → record → artifact chain
  implemented and verified **offline only**;
- **58 wrappers** (19 legacy + 39 taxonomy) green under `validate_task.sh --all`;
- **zero network requests ever made** by this pipeline, at any stage in its history;
- `run_cells.run()` constructing its opener unconditionally as `fixtures.FixtureOpener` — **no
  parameter, flag or branch could make it reach the network**;
- **no command that invoked the run driver at all**; `scripts/harvest/harvest.sh` did not exist;
- the four repository runtime paths absent, `data/harvested/` absent, no promotion code.

The blocking gap was therefore not approval. It was that **a live harvest was impossible without new
production code**.

---

## 2 · Exact Stage 9 commit chain

`bf067303..ec9bedc` — **13 commits**, in chronological order, read from Git at closeout.

| # | SHA | Subject | Checkpoint | Paths |
|---|---|---|---|---|
| 1 | `5c825e87db0abae5673b6ed5929db1fc5d9440e6` | docs(harvest): map roadmap and artifact lifecycle | pre-S9 roadmap | 2 |
| 2 | `2bbc236a43bf76dc4aa241c8384911d8e5fda6dd` | docs(harvest): correct roadmap stage percentage | pre-S9 correction | 1 |
| 3 | `720f114c6c3a840ab790935a2faaecec5762edd5` | docs(harvest): plan stage 9 live validation | **S9-0** | 2 |
| 4 | `fddbbb7ea07c7e876ef188edcb9bcf8ac1ba9ff2` | feat(harvest): add live transport seam and CLI foundation | **S9-1** | 10 |
| 5 | `3e64d6e18fa582ec8d4c23a1cf79cea7568aab0f` | feat(harvest): add source preflight command | **S9-2** | 8 |
| 6 | `4d0d56d51cd7b09caeb82d9d70a6b7af19385981` | feat(harvest): add bounded smoke and run validation | **S9-3** | 11 |
| 7 | `238df98e57b6497e8b844b5514ed9660e3bf9fb3` | feat(harvest): add run comparison and publication diff | **S9-4** | 9 |
| 8 | `139cf0f15d25dbe35b43b99283ccc5f20b7114d6` | docs(harvest): calibrate live corpus | **S9-5** | 2 |
| 9 | `f228cb463d4273f11c15db7e5aa654aed86b7284` | fix(harvest): record actual run timing | **S9-5C1** | 5 |
| 10 | `05ef9e4a34a618a449daf01877708be7e1611833` | feat(harvest): record in-run candidate sightings | **S9-5C2** | 8 |
| 11 | `9d06b56ee6c473656883e1f2c282ddb162ba940b` | docs(harvest): defer immutable rejection snapshots | **S9-5C3 deferral** | 2 |
| 12 | `8479095cc79740f27acb82ee3b743f75a18253b9` | feat(harvest): add bounded link checking | **S9-6** | 13 |
| 13 | `ec9bedc5f209927ffd2899126ff20c2b31af0245` | test(harvest): repair authoritative full-gate findings | **S9-6A** | 4 |

Every commit was published by `safe_push_main.sh --execute`, **exactly once each**, fast-forward
only, with no retry, no manual `git push`, no fallback and no history rewrite.

### 2.1 Operations that produced NO commit

These are as much a part of Stage 9 as the commits, and omitting them would misrepresent the work:

| Operation | Commit? | Why |
|---|---|---|
| **S9-L1** source preflight | none | Live checkpoints never commit |
| **S9-L2** first smoke | none | " |
| **S9-L3** second smoke + validate + compare | none | " |
| **S9-L4** linkcheck | none | " |
| **Authoritative gate, 62/62** (pre-S9-L2) | none | Verification only |
| **Authoritative gate, 63/63 @ `8479095` — FAILED** | none | Verification only; a real, retained result |
| **Authoritative gate, 63/63 @ `ec9bedc` — PASSED** | none | Verification only |
| Read-only audits (S9-5C scope preflight, S9-6 contract audit, S9-L4 contract audit and its correction) | none | Analysis only |

---

## 3 · Checkpoint and operational timeline

```text
S9-0    plan of record .................... 720f114c
S9-1    live transport seam + CLI ......... fddbbb7
S9-2    source preflight .................. 3e64d6e
S9-3    bounded smoke + run validation .... 4d0d56d
S9-L1   LIVE source preflight ............. 2026-07-31T08:21:16Z   rc 1, no commit
S9-4    compare-runs + diff ............... 238df98
GATE    authoritative 62/62 ............... PASSED, exit 0, one run
S9-L2   LIVE smoke #1 ..................... 2026-07-31T11:35Z      rc 0   M2
S9-L3   LIVE smoke #2 + validate + compare  2026-07-31T12:07Z      rc 0   M3
S9-5    live-corpus calibration ........... 139cf0f
S9-5C1  actual run timing ................. f228cb4
S9-5C2  in-run candidate sightings ........ 05ef9e4
S9-5C3  rejection-history retention ....... 9d06b56   EXPLICITLY DEFERRED
S9-6    bounded linkcheck (offline) ....... 8479095
GATE    authoritative 63/63 @ 8479095 ..... FAILED rc 1   61 pass / 2 FAIL
S9-6A   repair the gate findings .......... ec9bedc
GATE    authoritative 63/63 @ ec9bedc ..... PASSED exit 0   63/63, 2,386 tests
S9-L4   LIVE linkcheck .................... 2026-08-01T08:58:29Z   rc 0   M4
S9-C    closeout .......................... this commit
```

---

## 4 · Delivered command and safety contract

**D9-B architecture.** `scripts/harvest/harvest.sh` dispatches only and `exec`s the CLI;
`src/harvest/cli.py` owns parsing, root resolution, transport construction and dispatch. **No
judgement lives in the shell or CLI layer** — asserted by AST scan. `run_cells.run()` was
*generalized*, not replaced.

**The six-command surface.** `cli.COMMANDS` = `preflight-sources`, `smoke`, `validate`,
`compare-runs`, `diff`, `linkcheck`; `PLANNED_COMMANDS` is empty. **There is no `"harvest"` key** —
this is the single most consequential absence in the whole stage (§10).

**One atomic transport seam.** `Transport` is frozen and carries opener, pacing sleep and lease root
as one value, so **a live opener can never be paired with disabled pacing**. A test asserts no
independent `opener` / `sleep` / `lease_root` parameter exists. `cli.live_transport()` is the only
place in the tree where `httpclient.default_opener` and `time.sleep` are named together.

**Safety properties that held throughout Stage 9:**

- **The four repository runtime paths stayed absent** — every live byte went to an explicitly
  supplied **external** retained root (D9-A). The harness asserts their absence before *and* after
  every run and **never deletes what it finds**.
- **A caller-supplied lease root is never deleted.**
- **Every live execution needed approval twice** — once as a checkpoint, once immediately before the
  outbound request — ran **exactly once**, and was **never retried**.
- **No retry-until-green, ever.** A failed gate is a result, not a rehearsal.
- **`config/` and `schemas/` were never edited** to improve a live result. 33 taxonomy wrappers
  assert `config/` is unmodified, so the constraint is mechanically enforced.

---

## 5 · Authoritative gate evidence

Three invocations. **They must never be conflated.**

### 5.1 Pre-S9-L2 — 62/62, PASSED

At the S9-4 baseline `238df98`, one execution: exit 0, 62 wrappers (19 legacy + 43 taxonomy) each
exactly once, executed set exactly equal to the on-disk `tests/*.sh` set, **0 FAIL, 0
`WARN - skipping`**, runtime paths absent before and after, production `state/` unchanged, no
network.

### 5.2 63/63 at `8479095` — **FAILED, rc 1**

One invocation, no retry, no wrapper rerun.

```text
final line   == validate_task.sh: FAIL ==
wrappers     63 discovered / 63 executed / each exactly once
             61 passed · 2 FAILED · 0 WARN - skipping
failing      tests/test_taxonomy_target_determinism.sh   8 failures
             tests/test_taxonomy_linkcheck.sh            1 failure
unittest     43 suites · 2,384 tests · 9 failures · 0 errors
repository and retained root unchanged
```

**This is valid historical evidence for that tip and must never be described as superseded or
void.** It is the evidence that S9-6A was necessary.

**Finding A** — `test_target_determinism.py` was the **fourth** whole-tree determinism guard site,
missed by S9-5C1's scope. `cells[].elapsed_sec` is a real monotonic measurement, and that suite
pinned only the UTC clock. It was invisible to C1 because the harness routes `run_cells.py` to
run_cells / recovery / cli / smoke while that suite routes from `targetfetch.py`, and **neither C1
nor C2 ran `--all`**. *Durable lesson: a checkpoint that changes what `run_cells.run()` writes must
search **every** suite that compares two runs' bytes, not only the suites its own routing arm
selects.*

**Finding B** — `test_only_the_manifest_schema_moved` asserted a **non-empty**
`git diff --name-only HEAD -- schemas/harvest`, true only while S9-6 was uncommitted. After the S9-6
commit the diff is correctly empty, so **it failed because the checkpoint succeeded** — E9-9's
spent-guard family for the sixth time, and the first spent by its own checkpoint's commit.

### 5.3 S9-6A — the repair

Test-only, four paths, **wrapper inventory unchanged at 63**, no production/schema/fixture/config/
harness/validator/comparator change, S9-5C3 not reopened. **Neither finding was a production
defect.** Finding A was repaired by a suite-local `pinned_monotonic()` patching **only**
`run_cells._monotonic` (never `time.monotonic` process-wide, never `RequestBudget`) with a fresh
sequence per run at four sites, plus anti-vacuity assertions requiring `elapsed_sec == 0.25 > 0` on
both compared runs. **Nothing was weakened**: no tree hash removed, no content normalized,
`elapsed_sec` neither excluded nor zeroed, and it was **not** added to any permitted-difference set.
Finding B's spent census was **retired and replaced** by a durable clean-tree assertion — explicitly
a *different and weaker* contract, because the checkpoint-diff fact belongs to the commit and is
unrecoverable from a clean worktree.

Focused validation, each command exactly once: `py_compile` ×2 rc 0 · determinism **90** ·
linkcheck **48** · run_cells **137** · cli **58** — **333 tests, 0 failures / errors / skips**.
*(run_cells is 137, not the older C1-era 115, because S9-5C2 added 22 sighting tests.)*

### 5.4 63/63 at `ec9bedc` — **PASSED, exit 0**

```text
final line   == validate_task.sh: PASS ==
wrappers     63 discovered / 63 executed / 63 distinct / each EXACTLY ONCE
             executed set exactly equal to the on-disk tests/*.sh set
             0 WARN - skipping · 0 FAIL
unittest     43 suites · 2,386 tests · 0 failures · 0 errors · 0 skips
             (2,384 + the two S9-6A anti-vacuity tests; every suite printed a
              BARE "OK", which is positive proof of zero skips)
shell        20 wrappers expose their own totals, all "0 failed"
exit code    0 in the external rc file AND at the outward process status — they AGREE
repository and retained root unchanged · no network
```

**The pre-S9-L4 authoritative 63/63 requirement is satisfied.**

> **Launcher rule, learned the hard way at 5.2:** the gate exited 1 while the enclosing background
> compound command surfaced 0, because a trailing command replaced the outward status. Always use
> `cmd >out 2>err; rc=$?; printf '%s\n' "$rc" >rc_file; exit "$rc"`.

---

## 6 · M2, M3 and M4 evidence

### 6.1 S9-L1 — first outbound traffic in the project's history

One invocation, 2026-07-31T08:21:16Z, `preflight-sources --timeout-sec 20`. **Exit 1 — meaning "a
source failed", not a crash.** 25 unique rows sorted by `source_id`: **19 `ok` · 6
`infrastructure_error`, all `robots_denied`**. No failed row was dropped. Five of the six share the
GitHub `releases.atom` pattern — one root cause, not five. `microsoft-blogs` reported the only
non-null `crawl_delay_sec`: **10.0**. stderr empty; no retry; no leaked lease root.

### 6.2 S9-L2 — M2

One smoke, rc 0, run **`20260731T113526Z-23992`**. 42 JSON + `LATEST_RUN_ID`; 12 cells → **10 `ok`,
2 `zero_result`** (both `all_below_relevance_threshold`), **32 records**; enrich false. Validated
offline: **`valid: true`**, 42 documents / 43 paths, pointer agreeing. All 62 retained files were
hashed before and after validation and were byte-identical.

**Robots is time-varying:** `netflix-techblog` was denied at S9-L1 and permitted here.

### 6.3 S9-L3 — M3

Second smoke, rc 0, run **`20260731T120702Z-20188`**, same bounds. Run 1 stayed **byte-identical**,
proved three times (aggregate `58e55eee47e601841a16a5908ca98d6fda1fccd67aeb556458d6f74a35756e8f`).

`compare-runs`, one invocation, offline: **18 documents compared, 18 expected, 24 shared excluded,
197 permitted clock changes, 23 content changes — all manifest `source_preflight[].elapsed_ms` —
0 invariant violations, `idempotent: true`.** The corpus reproduced identically while only per-probe
latency moved.

> The 24 shared ledger/rejection documents are **updated in place** and are never presented as
> historical A/B snapshots (E9-15). **There is no `--normalize`** (E9-14).

### 6.4 S9-L4 — M4

One live linkcheck, 2026-08-01T08:58:29Z, rc 0 in both the rc file and at the process boundary,
**stderr empty**. Base `20260731T120702Z-20188` → run **`20260801T085829Z-40852`**.

```text
mode linkcheck · sample requested 20 (19 accepted full records available)
records_checked 19 · identities_fetched 19 · publication_eligible false
19 current-run link_history entries · 0 missing · 0 duplicate · 0 not_checked
access_status   ok 14   ·   robots_denied 5
cells           ok 7    ·   not_run 5
```

All 14 `ok` entries returned **HTTP 200** with a content hash present; the five `robots_denied`
entries carry **no** HTTP status and **no** content hash. **`changed_materially` is absent on all
19** — correctly, because the base records held no prior content hash and a `false` would claim a
page was unchanged when nobody could tell.

**`robots_denied` is legitimate link-health evidence, not a failed command.** Availability is not
truth: no record was deleted, downgraded or re-judged, and `link_history` is append-only.

**8 of the 19 targets were `arxiv.org`**, whose 15 s crawl-delay the plan treated as the point of the
exercise. `locks/arxiv.org/` did not previously exist — the smokes only ever paced `rss.arxiv.org` —
so this was the pipeline's **first target-page pacing on that host**.

Run-level accounting: `target_http_attempts` **19** · `target_retries` **0** ·
`target_redirect_hops` **5** · `target_fetch_owners` **19** · `conditional_revalidations` **0**.

Validated offline, one invocation: **`valid: true`**, errors `[]`, 42 documents / 43 paths,
`run_id == pointer_run_id`.

> **M4 was declared achieved only after BOTH the validator and a separate 19-entry completeness
> inspection**, because `runvalidate` never inspects `access_status`: a run whose entries were all
> `not_checked` would validate cleanly while proving nothing about link health.

---

## 7 · Retained-root inventory and disposition

```text
C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_stage9_retained
```

| Run ID | Mode | Checkpoint | Milestone |
|---|---|---|---|
| `20260731T113526Z-23992` | `smoke` | S9-L2 | M2 |
| `20260731T120702Z-20188` | `smoke` | S9-L3 | M3 · linkcheck base |
| `20260801T085829Z-40852` | `linkcheck` | S9-L4 | M4 |

```text
3 run directories x 18 selected-run JSON   = 54
12 ledgers + 12 rejection logs             = 24
1 LATEST_RUN_ID pointer                    =  1
20 next_allowed_at lock files              = 20
                                    total  = 99 regular files · 54 directories

LATEST_RUN_ID   20260801T085829Z-40852
full aggregate  0a14269a00695fb2b259816b570c88a4df40a64f88e782d447f6a1abccab18e3
run 1 aggregate 58e55eee47e601841a16a5908ca98d6fda1fccd67aeb556458d6f74a35756e8f  (18 docs)
transient       0 slot_*.lease · 0 owner · 0 pace.lock · 0 .tmp_*
```

*Historical: before S9-L4 the root held two runs, 80 regular files and aggregate
`1dcdfff3642e3abded6d8edd95810db4fa37dd497e9a1db9b27d3eea0fd58a94` — the pre-S9-L4 baseline only.*

**`locks/` is separate pacing infrastructure**, outside the 43-path contract. **Preserve it; never
clean it.**

### 7.1 Disposition

> **Retain the external Stage 9 root unchanged as durable Stage 9 evidence through Stage 10 and until
> a separately approved disposition checkpoint.**

It must **not** be deleted, cleaned, moved, promoted, treated as publication, or silently reused for
another live run. **Any future mutation requires its own approval and its own before/after
evidence.**

---

## 8 · Calibration decisions and limitations

**S9-5 primary decision: EDITORIAL THRESHOLDS STAY PROVISIONAL.**

The sample was **19 accepted full records from ONE corpus observed twice** ~32 minutes apart — not
38 and not 64. `relevance` (min 0.4533 vs threshold 0.35) was the **only discriminating gate**;
**`quality` and `audience_fit` were saturated at 1.000 across all 19 and rejected nothing**.
`composite` was recomputed analytically and is **never stored**.

Rejections: 108 entries **from run 2 only** — `off_topic` 89, `below_relevance_threshold` 19; the
quality, audience-fit and composite gates fired on nothing. Closest miss 0.3333 vs 0.35.

**The 12/5 smoke caps remain PROVISIONAL and NOT FULLY OBSERVABLE:** candidates outside a cap are
never logged, and **two** caps sit between the sighting measurement and `cells[].candidates`, so
truncation is **not attributable**.

Only **8 of 25 sources** contributed accepted records; `netflix-techblog` was the **second-largest
contributor** despite having been robots-denied at S9-L1.

**Conclusion, stated precisely: strong SHORT-HORIZON repeatability. No proof of long-horizon source
stability, no proof of production readiness, no proof of threshold optimality.**

---

## 9 · Preserved boundaries and non-claims

**Stage 9 completion does NOT claim:**

```text
production readiness · publication eligibility · human review
production promotion · website consumption · recurring refresh
```

Also still true, and unchanged by Stage 9:

- **S6-L, Stage 6's bounded live smoke, remains UNEXECUTED and UNAUTHORIZED.** No Stage 9 execution
  discharges it.
- **An operational `migrate.sh ax-cases --apply` against the repository default root remains
  separately unapproved**; `state/taxonomy_harvest/` does not exist, and that absence is intended.
- **Promotion into `data/harvested/` remains separately unapproved**; the directory remains absent.
- **Network activity requires separate approval given immediately before each outbound request**, in
  addition to the checkpoint's own approval.
- **Stage 7's temporary default-root incident during S7-5 development is historical fact** and must
  not be rewritten as though it never happened.

---

## 10 · Known limitations and carried-forward work

**None of these is closed by this handoff, and this handoff authorizes no fix for any of them.**

1. **Editorial thresholds remain provisional** (§8).
2. **The 12/5 caps remain provisional and not fully attributable** (§8).
3. **S9-5C3 remains EXPLICITLY DEFERRED** — reopening it needs a new design and explicit approval,
   and it must **not** be treated as a small additive schema change.
4. **Run-1 rejection reasons are unrecoverable.** The 12 rejection logs are shared cross-run
   documents that run 2 overwrote in place. **Never imply a run-1 rejection distribution exists.**
5. **The three retained runs are not production candidates** — `publication_eligible: false` by
   derivation for both `smoke` and `linkcheck`.
6. **No production `harvest` command exists.** `cli.COMMANDS` has six keys and none is `"harvest"`.
   `mode: "harvest"` is the only mode `derive_publication_eligibility` accepts, and it has **never
   run live**. This blocks M5 directly.
7. **`smoke-model` and `refresh` are absent**; `runvalidate` **refuses** `harvest`, `refresh`,
   `smoke_model` and `migration` modes — a validator with no semantics for a mode must refuse it.
8. **M5 has no review artifact and no acceptance process.**
9. **Promotion code is absent** — zero occurrences of the promotion vocabulary anywhere.
10. **Website integration is unowned.**
11. **Domain-throttle intermittent signatures remain UNRESOLVED diagnostics.** The suite passed in
    every Stage 9 gate; that is an observation, not a resolution, and it must never be accepted as a
    permanent flake.
12. **Changed-mode routing does not select `tests/harvest/*.py`** — only `--all` covers them. An
    explicit-mode harness run over a test module routes to **zero wrappers** and **must never be
    reported as validation**.
13. **Per-record retry/redirect accounting is not retained.** The run carries run-level aggregates
    only; **per-record attribution of attempts, retries and redirect hops cannot be reconstructed
    exactly from the published artifact.**
14. **`src/harvest/cli.py`'s `CliError` handler comment is wrong for `linkcheck`** (roadmap G18). It
    claims every such refusal happens before the first request; two `LinkcheckError` paths fire
    **after** fetching and after partial writes, so an exit 2 from `linkcheck` does **not** guarantee
    that no artifact was written. **Carried forward for a separate maintenance checkpoint. S9-C
    deliberately did not widen its scope to touch a production path.**
15. **Roadmap documentation debt corrected during S9-C**, recorded so the correction is traceable:
    the plan previously claimed a linkcheck writes the cross-run `ledgers/`. **It writes none** —
    proved by S9-L4, after which all 24 shared documents were byte-identical.

---

## 11 · Closeout validation and repository state

**S9-C is documentation-only, four paths, L0 validation only:**

```text
docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md
docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md   (new)
```

No executable change. **No test, wrapper, gate or syntax command was run, and none is required.** No
network, no retained-root mutation, no project-memory edit.

### 11.1 Repository state observed at closure — a dated snapshot, not an enduring claim

```text
observed 2026-08-01, during S9-C, BEFORE the closeout commit
HEAD = local main = local origin/main = ec9bedc, 0 behind / 0 ahead
tracked worktree clean · index empty
untracked baseline 508 paths, zero drift
protected baseline 18/18 byte-identical to anchor 8865c54e
wrapper inventory 63 · four repository runtime paths ABSENT
```

**This snapshot describes the moment of closure.** It is not a claim about the state after the
closeout commit, and it says nothing about whether that commit has been published — publication and
project-memory synchronization are separate checkpoints.

### 11.2 External evidence

Authoritative evidence roots, outside the repository:

```text
ClaudeWorkspace\scratchpad\
  s9_l1_preflight_20260731T082116Z_540.*                       S9-L1
  s9_l2_smoke_20260731T113503Z_1650.*  + validate              S9-L2
  s9_l3_smoke_20260731T120639Z_1156.*  + validate + compare    S9-L3
  s9_authoritative_full_gate_20260731T100012Z_785.*            62/62 gate
  s9_authoritative_63_gate_20260801T035233Z.*                  63/63 FAILED
  s9_authoritative_63_gate_ec9bedc_20260801T064238Z.*          63/63 PASSED
  s9_l4_evidence_20260801T085807Z\                             S9-L4 BEFORE/AFTER
  s9_l4_linkcheck_20260801T085829Z.*                           S9-L4 live
  s9_l4_validate_20260801T085829Z-40852_20260801T090150Z.*     S9-L4 validation
```

Each set is `stdout` / `stderr` / `rc`. **No log artifact is retained inside the repository.**

Supporting material, **not repository authority** and outside the 508-file untracked baseline:

```text
C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_reports\HARVEST_PROGRESS_REPORT.html
SHA-256  ee9f7edd859502c365de2a9f175c65d2769d281905fb23f4c50a52af45ec859f
```

---

## 12 · Successor

**Stage 9 is closed. Nothing is authorized by that fact.**

The next candidate boundaries, each needing its own approval by name with an exact allowed-path set:

1. **Publication of the S9-C closeout commit** and **project-memory synchronization** — two separate
   checkpoints.
2. **Stage 10** — `IMPLEMENTATION_REPORT.md` and `CONVERGENCE_NOTE.md`. Its prerequisite is now
   satisfied, but it is **not opened**. **Stage 10 creates no JSON and publishes nothing.**
3. **A maintenance checkpoint for the `cli.py` comment defect** (§10.14).
4. **M5** — which needs, in order: a production `harvest` command that does not exist, an enrichment
   budget design, a candidate artifact and producer, and a human-review artifact with acceptance
   criteria. **Unopened and unowned.**

Reading "only Stage 10 remains" as "publication is one stage away" is wrong. **M5, M6 and M7 are
roughly 22–32 further checkpoints**, mostly undesigned, and Stage 10 is two markdown documents.

**A completed stage, a green gate, three retained runs and three achieved milestones do not —
separately or together — authorize the next thing.**
