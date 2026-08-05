# Stage 10 — final report and convergence note: plan of record

```text
Status                    STAGE 10 CLOSED BY THE S10-C COMMIT CONTAINING THIS PLAN
                          AND HANDOFF_STAGE_10_COMPLETE_2026-08-04.md. The closeout
                          commit SHA is intentionally NOT self-recorded, and this plan
                          asserts nothing about the S10-C L0 result or publication.
                          [HISTORICAL, as written at S10-0:]
                          STAGE 10 OPEN FOR DOCUMENTATION-ONLY CLOSEOUT WORK.
                          S10-0 is the commit containing this file. Its SHA is
                          intentionally NOT self-recorded, and this plan asserts
                          nothing about whether that commit has been published.
Entry anchor              c3497fa18ed05268edd456472c738a800d0ee21f
                          docs(harvest): record stage 9 completion   (S9-C closeout)
                          A HISTORICAL CHECKPOINT ANCHOR, not a live-HEAD claim.
Closing executable        ec9bedc5f209927ffd2899126ff20c2b31af0245
implementation baseline   test(harvest): repair authoritative full-gate findings
of the whole task         Stage 10 adds NO executable change, so this baseline does
                          not move. NEVER present it as the repository tip.
Checkpoints               S10-0 (this file) · S10-1 · S10-2 · S10-C — four planned
                          commit checkpoints, none of which is approved by this file
Operational checkpoints   NONE. Stage 10 runs no command, live or offline.
Deliverables              docs/harvest/IMPLEMENTATION_REPORT.md
                          docs/harvest/CONVERGENCE_NOTE.md
Milestones                M2 ACHIEVED · M3 ACHIEVED · M4 ACHIEVED
                          M5 UNOPENED · M6 NOT STARTED · M7 NOT STARTED
Live requests in Stage 10 ZERO, and zero are planned. Stage 10 has no network step.
Publication / promotion   ZERO. data/harvested/ remains absent; no promotion code
                          exists; website consumption is ZERO.
Roadmap authority         docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md
Prior completion          docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md
authority
Prior plan of record      docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md
Retained Stage 9 root     C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_stage9_retained
                          RETAIN UNCHANGED through Stage 10. Its disposition is a
                          SEPARATE future approval, and Stage 10 does not discharge it.
```

**Checkpoint progress, recorded durably** (detail in §6; this block states position, never approval):

```text
S10-0   COMPLETE · VALIDATED · COMMITTED · PUBLISHED at ab99b32
S10-1   COMPLETE · VALIDATED · COMMITTED · PUBLISHED at b3b7ad9
S10-2   COMPLETE · FORMALLY L0-VALIDATED · ATOMICALLY COMMITTED ·
        PUBLISHED at 4e7abaf
S10-C   The closing checkpoint represented by the commit CONTAINING this plan
        and docs/harvest/handoffs/HANDOFF_STAGE_10_COMPLETE_2026-08-04.md.
```

**S10-C, stated durably.** The S10-C closeout document set is authored **for** the S10-C commit
containing these files. **That commit closes Stage 10 and the original Stage 0–10 documentation
task.** The closeout commit SHA is **intentionally not self-recorded**. **Formal L0 validation is a
separate required boundary before commit; publication is a separate later boundary; project-memory
synchronization is another separate later boundary.** This document does not prospectively assert the
result of any later boundary.

*Historical note: at the close of the S10-C document-edit boundary, formal L0 validation had not yet
run.*

**Stage 10 is closed by the S10-C commit containing the completion handoff.** The uncommitted
working-tree draft does not itself constitute the completed checkpoint.

**Nothing above approves anything below it.** A published checkpoint authorizes neither the next
checkpoint nor its validation, commit or push.

**Stage 10 closes only the originally described Stage 0–10 implementation task.** It is two markdown
documents plus their closeout. It creates no JSON, runs no harvest, produces no reviewed production
candidate, promotes nothing, publishes nothing, integrates with no website, establishes no recurring
refresh, achieves neither M5 nor M6 nor M7, changes no executable behaviour, and modifies no
protected matrix path. **"Stage 10 — final" does not mean "final delivery"** (roadmap G16).

**The existence of this file does not approve S10-1, S10-2 or S10-C.** Each still needs its own
approval by name with its exact allowed-path set. A completed checkpoint, a green gate and a closed
stage do not — separately or together — authorize the next one.

## 0 · Errata

Recorded against the previously committed Stage 10 references as this plan met them. Each corrects
the record; none widens a checkpoint, and none is authorization for anything.

### E10-1 — the five gates were never enumerated anywhere; S10-0 authors them

Three committed references to "the five gates" existed before this file, and **all three are forward
references to `CONVERGENCE_NOTE.md`, which did not exist**:

```text
ROADMAP_AND_ARTIFACT_LIFECYCLE.md §2   "(5 gates before matrix unification is reconsidered)"
TODO.md  Stage 10 checklist            "5 gates before matrix unification is reconsidered"
TODO.md  out-of-scope follow-ups       "Gated behind the 5 criteria in CONVERGENCE_NOTE.md"
```

No committed document enumerated them. The nearest raw material is
`INVENTORY_AND_REUSE_MAP.md` §3.2, which tabulates **six** deliberately duplicated primitives with
convergence risk — six risks, not five gates, and a risk is not a reconsideration criterion.

**The five gates in §4 are therefore newly authored and ratified at S10-0.** They must never be
described as previously enumerated, recovered, or restored from an older document. The count five is
honoured because the approving instruction ratified five gates, not because five were found.

### E10-2 — "matrix unification" was used but never defined; S10-0 ratifies a definition

The term appears in the roadmap and `TODO.md` without a definition anywhere in the committed tree.
The definition in §3 is a **newly ratified S10-0 planning definition**, not a historical requirement
that already existed. It is recorded so the eventual `CONVERGENCE_NOTE.md` gates something with a
fixed meaning rather than an implied one.

### E10-3 — the 1–2 checkpoint forecast is superseded by four · **forecast variance**

`ROADMAP_AND_ARTIFACT_LIFECYCLE.md` §4.0 forecasts **Stage 10 at 1–2 checkpoints**. Stage 10 is
planned here as **four commit checkpoints**. This is a **forecast variance**, in the same class as
the variance the roadmap already records for Stage 9 — *"The forecast's shape held; its scope did
not."* Four checkpoints were **not** always planned, and this plan does not rewrite the forecast to
pretend otherwise.

The variance has four causes, each a genuine difference in ownership, risk, reviewability or path
scope rather than formality:

1. **The five gates required a new approved definition** (E10-1). A convergence note that defined its
   own gate set would be self-authorizing — exactly what this project's operating rules forbid — so
   the definition had to land in a plan first.
2. **The implementation report and the convergence note have different subjects and different
   failure modes.** The report's subject is this pipeline and its failure mode is overclaiming; the
   note's subject is the *protected* matrix pipeline and its failure mode is an undefined gate set.
   Separating them also lets the report land if the convergence decision stalls.
3. **The closeout authorities have a separate path scope** — the roadmap, a new handoff and
   `HANDOFF_CURRENT.md` are touched by no other checkpoint.
4. **Commit, push and project-memory synchronization remain separate boundaries**, as they have been
   since Stage 6.

The roadmap's forecast row is **not edited by S10-0**; `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` belongs to
S10-C.

### E10-4 — `HANDOFF_CURRENT.md` is stale by seven stages; its update belongs to S10-C

See §10. It is recorded here, and deliberately **not fixed here**, because its correct content names
the Stage 10 completion authority, which does not exist until S10-C.

### E10-5 — `TODO.md` header debt, corrected at S10-0 without creating new debt

Two header entries were stale at the Stage 10 entry anchor:

- **`push_state:`** recorded `bf067303…` (the Stage 8 published tip) as HEAD. It carried its own
  caveat and was therefore stale-but-honest rather than false — but a live-HEAD-shaped entry goes
  stale on the very next commit by construction. S10-0 **reframes it as a Stage 10 entry anchor** at
  `c3497fa…`, explicitly labelled a historical checkpoint anchor and not the live HEAD.
- **`roadmap:`** described the gap register as **G1–G17**. The roadmap carries **G18** (the `cli.py`
  pre-request refusal comment). Corrected to **G1–G18**.

**Neither correction closes any gap.** G18 remains open and carried forward.

### E10-6 — the L0 text-format expectation, measured rather than assumed

**The rule is "worktree EOL matching sibling docs."** The read-only Stage 10 audit asserted that
those siblings were **CRLF**; **that was wrong, and it is corrected here.** The CRLF reading came
from a defective measurement — a `grep -c` whose carriage-return pattern silently degenerated to an
empty pattern and so matched every line, making LF-only files look uniformly CRLF.

Measured instead by direct byte inspection: **at the `c3497fa` Stage 10 entry anchor, 25 tracked
markdown paths existed under `docs/harvest/**`, and all 25 of those pre-existing sibling files are
LF-only in the working tree** — 0 CRLF line endings among them.
`docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` **did not exist at that anchor**: it is new at S10-0,
and it is **also LF-only**. The current working tree therefore holds **26 LF-only markdown files**
under `docs/harvest/**` — the 25 measured siblings plus this plan. **Never state that 26 existed at
`c3497fa`**, and never quote the current count as an entry-anchor measurement.

The repository does set `core.autocrlf = true` and carries **no `.gitattributes`**, which is what
made CRLF a plausible guess. It does not apply here: these files were **authored in this worktree and
never checked out**, so nothing ever converted them. `autocrlf` normalizes CRLF→LF on add and leaves
LF alone, so an LF file written here stays LF on disk and LF in the blob.

**A new Stage 10 document is therefore LF in the working tree**, matching its siblings. §7.2 states
the resulting form. Do not copy the CRLF claim forward from the audit. See also the project-memory
note on this repository's mixed-EOL trap: an EOL round-trip is silent under `git diff`, so the
working form is measured per directory, never assumed from a global setting.

## 1 · What Stage 10 is

Stage 10 is the **documentation-only closeout of the originally described Stage 0–10 implementation
task**. It produces two substantive documents and the closeout that records them:

```text
docs/harvest/IMPLEMENTATION_REPORT.md   the whole-task retrospective
docs/harvest/CONVERGENCE_NOTE.md        the matrix-convergence decision record
```

The state Stage 10 opens against, and the state it must leave intact:

```text
Stage 9                CLOSED AND PUBLISHED
Stage 10               OPEN FOR DOCUMENTATION-ONLY CLOSEOUT WORK

M2                     achieved
M3                     achieved
M4                     achieved
M5                     unopened
M6                     not started
M7                     not started

publication            zero
promotion              zero
website consumption    zero
```

### 1.1 Stage 10 does NOT own

| Not Stage 10 | Owner |
|---|---|
| Production JSON of any kind | M6, unopened |
| A production `harvest` command | M5, unopened — it does not exist in any form |
| A reviewed production candidate | M5, unopened and unowned (roadmap G4, G9) |
| Promotion into `data/harvested/` | M6, unopened (roadmap G7) — zero lines exist |
| Publication of any artifact | M6, unopened — publication remains 0 of 16 |
| Website / downstream consumer integration | M7a, unowned and outside this repository (G10) |
| Recurring scheduling or refresh | M7b, undesigned (G6) |
| Any executable or schema change | a separately approved code checkpoint |
| Any change to a protected matrix path | a separately approved implementation checkpoint |
| Reopening S9-5C3 | a new design plus explicit approval by name |
| The `cli.py` `CliError` comment defect (G18) | a separate maintenance checkpoint |
| Disposition of the retained Stage 9 evidence root | a separate future approval |
| Any network activity | nothing in Stage 10; Stage 10 has no network step |

### 1.2 The sentence that must not be softened

> **Stage 10 completion is not production readiness, publication eligibility, human-review
> completion, production promotion, website integration or recurring refresh. It is the closeout of
> a documentation task. M5, M6 and M7 remain roughly 22–32 further checkpoints, mostly undesigned
> and currently unowned.**

Reading "only Stage 10 remains" as "publication is one stage away" is wrong, and the roadmap and the
Stage 9 handoff both say so already.

## 2 · Source hierarchy

Stage 10 uses the committed authority hierarchy established by the read-only Stage 10 audit, which is
the roadmap §11 evidence index unchanged. Each outranks the one below it where they differ:

1. committed production code under `src/harvest/**` and `scripts/harvest/**`;
2. committed tests under `tests/**` — **63 wrappers**, 44 taxonomy;
3. committed schemas `schemas/harvest/*.v1.json` and configuration `config/harvest/**`;
4. the published Stage 9 completion handoff,
   `docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md`;
5. earlier completion handoffs, `docs/harvest/handoffs/HANDOFF_STAGE_<N>_COMPLETE_*.md`;
6. `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md`;
7. earlier stage plans, `docs/harvest/STAGE_<N>_IMPLEMENTATION_PLAN.md`;
8. `docs/harvest/TODO.md`;
9. `docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md`;
10. `docs/harvest/IMPLEMENTATION_PLAN.md` — **superseded design input only**, used where it is
    consistent with 1–9. It is pre-Stage-3 in places, superseded by Stage 7 §11, and describes
    commands and runtime paths that do not exist (roadmap G11).

**Project memory may corroborate these authorities. It must never silently override committed
repository evidence.** Where memory and the committed tree disagree, the tree wins and the
disagreement is recorded, not smoothed over.

## 3 · D10-A — matrix unification, ratified definition · **NEW AT S10-0**

### 3.1 The definition

> **Matrix unification** means a future product-and-architecture decision to replace the current
> deliberate separation between the **protected matrix harvest family** and the **taxonomy harvest
> family** with a shared canonical implementation or semantic contract — especially for **identity**,
> **duplicate handling**, **merge behaviour**, **artifact lifecycle** and **orchestration**.

This is a **newly ratified S10-0 planning definition** (E10-2), not a historical requirement.

### 3.2 The boundary — what is and is not unification

**Not automatically matrix unification:**

- Isolated reuse of a helper that **provably preserves both pipelines' existing contracts**. The two
  families already share idioms by deliberate duplication — `INVENTORY_AND_REUSE_MAP.md` §3.2 records
  six such primitives with their risk stated — and that duplication is an accepted state, not a
  partial unification.

**Matrix unification:**

- replacing matrix identity semantics;
- deprecating matrix scripts;
- making taxonomy semantics canonical for matrix output;
- consolidating the two pipelines behind one canonical artifact or merge contract.

### 3.3 What this definition does not authorize

- **The matrix path is not deprecated.** `TODO.md` already says so, and this plan repeats it.
- **This definition authorizes no code change.**
- **Any future modification of a protected matrix path requires a separately approved implementation
  checkpoint.** Seven of the eighteen protected paths belong to the matrix family — five scripts
  (`run_matrix.sh`, `matrix_spec.py`, `merge_matrix.sh`, `expand_queries_cell.sh`,
  `harvest_matrix_cell.sh`) and two mandatory regression wrappers (`tests/test_matrix_harvest.sh`,
  `tests/test_parallel_harvest.sh`), all byte-frozen to the implementation-start anchor
  `8865c54e2cc8d879410576f247baac4aea149f34`.
- **Naming the matrix path in documentation is already permitted and is not a boundary breach.**
  `IMPLEMENTATION_PLAN.md` §5 scopes the static matrix-reference check to production implementation
  files and excludes `tests/**` and `docs/**` by construction, *"because the boundary test and the
  convergence note must name the matrix path."* That is the only committed statement about the
  convergence note's content, and it is permissive, not prohibitive.

## 4 · D10-B — the five reconsideration gates · **NEWLY AUTHORED AND RATIFIED AT S10-0**

**These five gates were authored at S10-0. They were not previously enumerated in any document**
(E10-1). Each states what must exist **before matrix unification may be reconsidered**; none of them
authorizes unification, and satisfying all five would authorize only a *reconsideration*, which would
itself need its own approval by name.

### Gate 1 — Product identity semantics

A **named product decision** must resolve the semantic fork between:

```text
matrix identity      (category, topic, name)
                     the same tool in multiple cells may remain multiple deliberate
                     findings — "matters for healthcare agents" / "…for finance agents"

taxonomy identity    identity_url plus precedence and cross-category duplicate
                     constraints — independent duplication across categories is
                     forbidden
```

Evidence required before reconsideration:

- an explicit **product owner or decision authority**;
- **accepted duplicate and cross-category semantics**;
- **treatment of provenance and cell membership**;
- **worked examples** covering the same entity appearing in multiple cells or categories.

`INVENTORY_AND_REUSE_MAP.md` §3.2 already classifies this as *"the real semantic fork"* and states
that *"convergence needs a product decision, not a refactor."* Gate 1 is that decision, and no
engineering evidence alone discharges it.

### Gate 2 — Lossless contract mapping

A **documented mapping** must show how both pipelines' inputs, manifests, entities, ledgers,
rejection evidence, provenance, schemas and lifecycle states can coexist or converge **without silent
information loss**.

Evidence required before reconsideration:

- a **field-by-field and artifact-by-artifact** mapping;
- **explicit handling of information present in one pipeline and absent in the other**;
- a **schema / version compatibility strategy**;
- **no assumption that similarly named artifacts are semantically equivalent.**

The last point is load-bearing and has already cost this project a checkpoint: E9-20 records that the
same schema is **not** the same semantic validator. Two artifacts sharing a name — "ledger",
"manifest", "cell" — are not thereby the same contract.

### Gate 3 — Operational-contract compatibility

The two families' **operational contracts** must be compared and **every difference classified** as
*equivalent*, *intentionally different*, or *blocking*.

At minimum, the comparison must cover:

```text
bounded concurrency          resume and recovery        robots and network behaviour
determinism                  failure isolation          throttling
atomic persistence           query expansion            run identity and pointers
                             ledger ownership
```

**This gate does not require implementing unification.** It requires sufficient *current* evidence to
judge whether convergence is technically coherent at all.

### Gate 4 — Stable independent baselines and comparison evidence

Both existing pipelines must have **stable, reproducible, independently validated baselines** before
reconsideration.

Evidence required before reconsideration:

- the **protected matrix baseline remains intact** — 18/18 byte-identical to `8865c54e…`;
- **authoritative regression evidence exists for both families**;
- **representative outputs can be compared without mutating retained Stage 9 evidence**;
- **known differences, data-loss risks and rollback constraints are documented**;
- **no unified implementation or migration experiment is authorized merely to satisfy this gate.**

The last clause is the trap this gate exists to close: a gate that can be satisfied only by building
the thing it gates is not a gate.

### Gate 5 — Ownership, migration and rollback authority

A **named owner** and an **approved decision process** must exist for any future convergence work.

Evidence required before reconsideration:

- an **implementation owner**;
- a **product decision owner**;
- a **proposed migration boundary**;
- a **compatibility and deprecation policy**;
- **rollback criteria**;
- a **protected-path approval process**;
- **explicit confirmation that the matrix path remains supported** until a later approved decision
  says otherwise.

### 4.6 How `CONVERGENCE_NOTE.md` must use these gates

- It must **assess the current status of each of the five gates**.
- **S10-0 defines the gates and does not mark any of them satisfied.** The note must not treat
  definition as satisfaction, and must not report a gate as met without naming the committed evidence
  that meets it.
- A gate whose status is *unmet, unowned* is a correct and expected finding. Five unmet gates is a
  legitimate outcome of S10-2.

## 5 · Deliverables

### 5.1 `docs/harvest/IMPLEMENTATION_REPORT.md` — content contract

The report must cover **at least** the following sixteen heads:

| # | Head | Notes |
|---|---|---|
| 1 | Stages and checkpoints completed | Stages 0–10, including corrective and read-only units |
| 2 | Commit history and the **exact Stage 9 chain** | `720f114c → fddbbb7 → 3e64d6e → 4d0d56d → 238df98 → 139cf0f → f228cb4 → 05ef9e4 → 9d06b56 → 8479095 → ec9bedc → c3497fa` |
| 3 | **Operational checkpoints that produced no commit** | S9-L1 … S9-L4, S8-2, and the read-only audits — live checkpoints never commit |
| 4 | Commands actually implemented | the six: `preflight-sources` `smoke` `validate` `compare-runs` `diff` `linkcheck`; `PLANNED_COMMANDS == {}`; **no `"harvest"` key exists** |
| 5 | Live execution evidence | four separately approved outbound executions, one invocation each, never retried |
| 6 | **The failed and the successful authoritative gate histories, as distinct historical facts** | 62/62 PASS · **63/63 FAIL rc 1 at `8479095`** · 63/63 PASS rc 0 at `ec9bedc`. The failed run is evidence, never "superseded" |
| 7 | **Every tracked file created or modified across the whole task** | see below |
| 8 | Schemas, configuration, artifact layouts and lifecycle | including the 18 / 24 / 42 / 43 accounting and the two-run 60 + 1 arithmetic (E9-11) |
| 9 | Retained Stage 9 evidence | three runs, file and directory counts, pointer, aggregate, and the **unchanged** disposition |
| 10 | **M1–M7 status** | M1–M4 achieved; M5 unopened; M6 and M7 not started |
| 11 | Known limitations and deferred work | §9 of this plan, none of them closed |
| 12 | **Explicit non-claims** | §1.2, plus Stage 9 handoff §9 |
| 13 | Validation commands, and **whether each was run or never run** | `IMPLEMENTATION_PLAN.md` §14 acceptance commands 0–24 as the spine |
| 14 | Repository-state snapshot **with a date and an anchor** | a dated snapshot, not an enduring claim |
| 15 | References to external evidence **without treating it as repository content** | scratchpad logs and the external HTML progress report both live outside the repository and outside the 508-path untracked baseline |
| 16 | Publication, promotion and website-consumption status | **zero / zero / zero**; publication 0 of 16 |

**Head 7 — scope and method.** "Every file created/changed" means **every tracked path across the
whole task**, from the implementation-start anchor to the Stage 9 closeout. It must be **generated
deterministically from Git**, not reconstructed from memory or from any handoff:

```text
git diff --name-status 8865c54e2cc8d879410576f247baac4aea149f34..c3497fa18ed05268edd456472c738a800d0ee21f
```

The report must state what that inventory **excludes** and why: the 508 pre-existing untracked paths
(out of scope, roadmap G17), the retained external Stage 9 root (not repository content), the
external HTML progress report, and gitignored interpreter artifacts.

**Two structural constraints.**

- **Cite, do not duplicate.** The report cites the per-stage completion handoffs rather than
  re-deriving their detailed evidence. Where a handoff already settles a fact, the report references
  it; it does not restate it at length and it does not silently paraphrase it into a weaker claim.
- **It must not record its own future commit SHA as though that SHA were knowable before commit.**
  The S9-C precedent applies: refer to "the commit containing this section".

### 5.2 `docs/harvest/CONVERGENCE_NOTE.md` — content contract

**Genre: a decision record.** Not a forecast, not a recommendation, not an implementation plan.
`TODO.md` files matrix convergence under follow-ups explicitly out of scope for this task, and that
placement fixes the note's genre.

Required content:

- an **assessment of each of the five newly ratified gates** in §4, with current status and the
  committed evidence behind each status;
- an explanation of **the semantic fork** (§3.1, §4 Gate 1);
- **what remains deferred**;
- **the evidence required for reconsideration**, gate by gate;
- an explicit statement that **the note authorizes no code change**;
- an explicit restatement that **the matrix path is not deprecated**;
- an explicit statement that the gates and the definition were **authored at S10-0**, not recovered
  from an older document.

The note may name the matrix path and `state/matrix/**` (§3.3). It may not modify them.

**Status of this contract.** The note has been drafted and satisfies every required-content bullet
above; see the S10-2 progress block in §6. Its **checkpoint** completion still depends on formal L0
validation and an atomic commit, each a separate boundary — a satisfied content contract is not a
completed checkpoint.

### 5.3 What Stage 10 does not create

```text
production JSON of any kind          a promotion journal, receipt or manifest
a candidate or review artifact       any change under src/, scripts/, schemas/, config/ or tests/
a publication manifest               any new wrapper — the inventory stays 63
```

## 6 · Checkpoint decomposition

Four commit checkpoints. **None of them is approved by this file.** Each needs its own approval by
name with its exact allowed-path set declared up front; if a path outside that set turns out to be
required, the checkpoint **stops and reports** rather than widening itself — the rule that has held
since Stage 4's closeout and that S9-1, S9-2 and S9-4 each hit in practice.

### S10-0 — plan of record · **THIS CHECKPOINT**

| Field | Value |
|---|---|
| Purpose | Ratify the Stage 10 contract; define matrix unification (§3); define the five reconsideration gates (§4); declare the later checkpoint scopes; correct Stage 10 planning and `TODO.md` documentation debt |
| Allowed paths | **TWO, exactly:** `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` (new) · `docs/harvest/TODO.md` |
| Risk tier | Documentation only |
| Validation | **L0 only** (§7), after a separate approval |
| Tests / `--all`? | **No** |
| Network | **No** |
| External state written | **No** |
| Retained root | **Not touched** |
| Commit | Own commit, `docs(harvest): plan stage 10 final report` |
| Entry | Stage 9 closed and published; entry anchor `c3497fa`; Stage 10 unopened |
| Exit | This file and the `TODO.md` Stage 10 block exist; **no later checkpoint approved** |
| Does NOT authorize | either deliverable · the closeout handoff · `HANDOFF_CURRENT.md` · the roadmap · formal L0 validation · staging · commit · push · memory synchronization |
| Why separate | The gate set had to be defined before the note that assesses it. A note that defined its own gates would be self-authorizing |

### S10-1 — implementation report · **COMPLETE, VALIDATED, COMMITTED AND PUBLISHED**

> **S10-1 is complete.** `docs/harvest/IMPLEMENTATION_REPORT.md` was drafted, formally validated at
> L0, committed atomically over its three approved paths, and **published at
> `b3b7ad92994148b7ccde18827ac9cef3cfc4dc5b`** — `docs(harvest): record the implementation report`,
> parent `ab99b32` (S10-0). The fixed historical range and its inventory were generated
> deterministically from Git — `8865c54e..c3497fa`, 73 commits · 269 tracked paths · 267 A / 2 M,
> with the complete path-level listing in the report's Appendix A.
>
> The report is now the **authoritative whole-task retrospective** for the Stage 0–9 implementation.
>
> *Historical note: at the close of the S10-1 document-edit boundary, formal L0 validation had not
> yet run; it ran and passed afterwards, and the commit followed it. The report's own §17 records
> only the drafting boundary because it was written before either — that is a correct
> point-in-time statement of a document that must not be edited to describe its own successor.*

| Field | Value |
|---|---|
| Purpose | Produce the whole-task retrospective (§5.1); account for every tracked path created or modified from the task's Git anchor through the Stage 9 closeout; record commands, schemas, lifecycle, operational evidence, validation history, limitations, non-claims, retained evidence and milestone status |
| Candidate paths | `docs/harvest/IMPLEMENTATION_REPORT.md` (new) · `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` · `docs/harvest/TODO.md` |
| Risk tier | Documentation only |
| Validation | **L0 only** |
| Tests / `--all`? | **No** |
| Network | **No** |
| Commit | Own commit, `docs(harvest): record the implementation report` |
| Entry | S10-0 committed; S10-1 separately approved by name |
| Exit | Every §5.1 head present; the file inventory **generated deterministically from Git**; every non-claim stated |
| Does NOT authorize | closing any carried-forward item · any milestone claim · the convergence note · the closeout |
| Why separate | Different subject and different failure mode from S10-2, and it must be able to land even if the convergence decision stalls |

### S10-2 — convergence note · **COMPLETE, L0-VALIDATED, COMMITTED AND PUBLISHED**

> **S10-2 is complete.** `docs/harvest/CONVERGENCE_NOTE.md` was drafted, formally validated at L0,
> committed atomically over its three approved paths, and **published at
> `4e7abaf3a359d24661c7cb9121a7d24635de660a`** — `docs(harvest): record the convergence assessment`,
> parent `b3b7ad9` (S10-1). It assesses each of the five S10-0 gates against committed evidence and
> reaches **matrix unification remains deferred** — Gate 1 UNMET · Gate 2 UNMET · Gate 3 PARTIALLY
> EVIDENCED · Gate 4 PARTIALLY EVIDENCED · Gate 5 UNMET; **no gate satisfied**. It records the gates
> and the ratified definition as **authored at S10-0**, states that the matrix path is **not
> deprecated**, and states that it **authorizes no code change and no protected-path change**.
> **S10-2 defined no new gate and weakened no existing gate.**
>
> *Historical note: two L0 runs failed before the passing one — the first on absolute
> matrix-history and operational-behaviour claims that exceeded their evidence, the second on
> merging live output with production-state output. Both were corrected under separately approved
> bounded document-edit boundaries. The failed runs are evidence for their own candidates and are
> never described as superseded.*

| Field | Value |
|---|---|
| Purpose | Assess each of the five newly ratified gates; explain the semantic fork; state what remains deferred; define the evidence required for reconsideration; explicitly authorize no code change; restate that the matrix path is not deprecated |
| Candidate paths | `docs/harvest/CONVERGENCE_NOTE.md` (new) · `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` · `docs/harvest/TODO.md` |
| Risk tier | Documentation only — **but its subject is the protected matrix family**, so the L0 protected-baseline check is asserted explicitly and by name |
| Validation | **L0 only** |
| Tests / `--all`? | **No** |
| Network | **No** |
| Commit | Own commit, `docs(harvest): record the matrix convergence note` |
| Entry | S10-0 committed (the gates exist); S10-2 separately approved by name |
| Exit | Five gates assessed with status and evidence; the definition and the gates recorded as **S10-0 authorship**; the no-code-change clause present |
| Does NOT authorize | any matrix change · any taxonomy identity change · deprecating the matrix path · reopening S9-5C3 · any reconsideration of unification |
| Why separate | Its subject is a different, protected pipeline, and its principal risk — an undefined or overstated gate set — is unrelated to the report's |

### S10-C — documentation closeout · **CLOSEOUT DOCUMENT SET AUTHORED FOR THE COMMIT CONTAINING IT**

> **S10-C position.** The five-path closeout set has been authored for the S10-C commit containing
> it: `docs/harvest/handoffs/HANDOFF_STAGE_10_COMPLETE_2026-08-04.md` (new), the roadmap, this plan,
> `TODO.md` and `HANDOFF_CURRENT.md`. **The completion date `2026-08-04` was fixed at this boundary
> using the actual Seoul date and does not move if a later boundary crosses midnight.**
>
> **That commit closes Stage 10 and the original Stage 0–10 documentation task.** Its SHA is
> **intentionally not self-recorded**. **Formal L0 validation is a separate required boundary before
> commit, publication is a separate later boundary, and project-memory synchronization is another
> separate later boundary** — no result is asserted for any of them here.
>
> *Historical note: at the close of the S10-C document-edit boundary, formal L0 validation had not
> yet run.*

| Field | Value |
|---|---|
| Purpose | Close Stage 10 and the original Stage 0–10 task; point `HANDOFF_CURRENT.md` at the new completion authority; leave M5–M7 and all carried-forward product work open; preserve the retained Stage 9 root disposition |
| Candidate paths | `docs/harvest/handoffs/HANDOFF_STAGE_10_COMPLETE_<completion-date>.md` (new) · `docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md` · `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md` · `docs/harvest/TODO.md` · `docs/harvest/HANDOFF_CURRENT.md` |
| Risk tier | Documentation only |
| Validation | **L0 only** |
| Tests / `--all`? | **No** |
| Network | **No** |
| Commit | Own commit, `docs(harvest): record stage 10 completion` |
| Entry | S10-1 and S10-2 committed; S10-C separately approved by name |
| Exit | Roadmap Stage 10 row reads CLOSED with a completion authority; **M5, M6 and M7 rows unchanged**; the carried-forward set restated as open; the retained-root disposition restated as pending its own approval |
| Does NOT authorize | push · project-memory synchronization · retained-root disposition · M5 · anything after Stage 10 |

**The completion date in the handoff filename is fixed and approved at the S10-C boundary**, using
the actual Seoul completion date. **Do not create the handoff during S10-0, and do not guess the
date.** The existing files use the `HANDOFF_STAGE_<N>_COMPLETE_<YYYY-MM-DD>.md` form.

### 6.1 After S10-C — three separate boundaries, none of them part of Stage 10

```text
push                              separate approval — safe_push_main.sh --check,
                                  then a separately approved --execute. One
                                  invocation, no retry, no manual git push.
project-memory synchronization    separate approval, AFTER publication. It
                                  authorizes nothing.
retained-root disposition         separate future approval, with its own before /
                                  after evidence.
```

## 7 · Validation policy — **L0 only, for every Stage 10 checkpoint**

Stage 10 changes no executable byte, so the authoritative 63/63 gate at `ec9bedc` stands unchanged
and **must not be rerun to restate Stage 9 evidence**.

### 7.1 The L0 checklist

```text
exact approved path-scope check          zero extras, zero missing
git diff --check                         rc 0
protected baseline                       18/18 byte-identical to 8865c54e
untracked baseline                       the original 508 paths preserved (see §7.3)
wrapper inventory                        63
four repository runtime paths            state/taxonomy_harvest · data/harvested ·
                                         runs · LATEST_RUN_ID — ALL ABSENT
cheap retained-root identity check       LATEST_RUN_ID = 20260801T085829Z-40852 ·
                                         3 run directories · 99 regular files ·
                                         54 directories
```

**No test wrapper, no full gate, no live command, no fetch and no network access is required or
permitted.** The full retained-root aggregate is **not** recomputed for a documentation checkpoint;
the four cheap facts above already discriminate the current root from every prior state.

### 7.2 Text format for new documents

```text
UTF-8 without BOM
worktree EOL matching sibling docs — MEASURED from the actual files, not assumed
                                     docs/harvest/**: 25 tracked markdown paths existed
                                     at the c3497fa entry anchor and all 25 are LF-only;
                                     this plan did not exist there and is also LF-only,
                                     so the working tree now holds 26 LF-only files
committed blob LF
final newline present
```

**The binding rule is "matching sibling docs", and the working form is measured from the actual files
per directory rather than inferred from `core.autocrlf`** (E10-6). Requiring CRLF here — as the
read-only audit did — would flag a correctly authored file, and so would requiring LF in a directory
whose siblings are CRLF. An EOL round-trip in this repository is silent under `git diff`, which is
exactly why the check measures instead of assuming — and why the entry-anchor count (25) and the
current count (26) are stated separately rather than conflated.

### 7.3 Untracked-baseline accounting for an approved new file

A new, not-yet-committed Stage 10 document makes `git status --porcelain -uall` report **509**
untracked paths rather than 508. That is **not baseline drift**. The check is:

```text
the ORIGINAL 508 pre-existing untracked paths       byte-identical
                                                    drift 0 · missing 0
the ONLY additional untracked paths                 exactly the declared new
                                                    Stage 10 path(s)
```

After the atomic commit the file is tracked and the count returns to 508. Committing uses
`bash scripts/safe_commit.sh -m "…" <explicit paths>` — **never** `-A`, `.` or a glob.

### 7.4 What is explicitly NOT run at any Stage 10 checkpoint

```text
scripts/validate_task.sh (any mode)     any tests/*.sh wrapper
the authoritative full gate             any harvest.sh command, live or offline
git fetch · git push                    any network access
any write to the retained Stage 9 root  any project-memory edit
```

## 8 · Stage 10 exit criteria

Stage 10 may close only when **all** of the following hold:

1. `docs/harvest/IMPLEMENTATION_REPORT.md` exists and covers all sixteen heads in §5.1.
2. Its whole-task file inventory was **generated deterministically from Git**, not reconstructed.
3. `docs/harvest/CONVERGENCE_NOTE.md` exists and **assesses all five gates** from §4.
4. The note records the definition and the gates as **authored at S10-0**, not as previously
   enumerated.
5. The note states explicitly that it **authorizes no code change** and that **the matrix path is not
   deprecated**.
6. The protected baseline is **18/18** and no protected matrix path changed.
7. The wrapper inventory is **63** and no executable, schema or configuration byte changed.
8. The four repository runtime paths are **absent**.
9. The retained Stage 9 root is **unchanged**, and its disposition is restated as pending a separate
   approval.
10. **No carried-forward item from §9 is marked resolved.**
11. **M5 remains unopened; M6 and M7 remain not started; publication, promotion and website
    consumption remain zero.**
12. The completion handoff exists at
    `docs/harvest/handoffs/HANDOFF_STAGE_10_COMPLETE_<completion-date>.md`.
13. `HANDOFF_CURRENT.md` points at that handoff (§10).
14. Push, project-memory synchronization and the retained-root disposition remain **separate,
    unapproved boundaries**.

### 8.1 What Stage 10 completion must NOT claim

Stage 10 completion must never be described as production readiness · publication eligibility ·
human-review completion · production promotion · website integration · recurring refresh · a
production candidate · progress toward M5, M6 or M7 · resolution of any carried-forward item · or
approval to reconsider matrix unification.

## 9 · Carried forward — recorded, not resolved

**None of these is closed by Stage 10, and recording one closes nothing.** Each would need its own
approved checkpoint by name. The authority is `HANDOFF_STAGE_9_COMPLETE_2026-08-01.md` §10, plus the
closeout debt recorded there.

```text
editorial thresholds ......... remain PROVISIONAL
the 12/5 caps ................ PROVISIONAL and NOT FULLY ATTRIBUTABLE
S9-5C3 ....................... EXPLICITLY DEFERRED (new design + approval to reopen;
                               it must NOT be treated as a small additive schema change)
run-1 rejection reasons ...... UNRECOVERABLE (run 2 overwrote the shared logs)
production `harvest` command . DOES NOT EXIST — blocks M5 directly
smoke-model .................. ABSENT; runvalidate REFUSES the mode
refresh ...................... ABSENT; runvalidate REFUSES the mode
M5 candidate/review artifact . UNDEFINED — no artifact, no acceptance process, no owner
promotion implementation ..... ABSENT (zero promotion vocabulary anywhere)
website integration .......... UNOWNED
domain-throttle signatures ... UNRESOLVED diagnostics — never accept as a permanent flake
changed-mode routing ......... still does NOT select tests/harvest/*.py; only --all covers
                               them, and an explicit-mode run over a test module routes to
                               ZERO wrappers and must never be reported as validation
per-record fetch accounting .. NOT RETAINED and not reconstructable
cli.py CliError comment ...... stale for linkcheck (roadmap G18); separately scoped
                               maintenance defect
508 untracked baseline ....... OUT OF SCOPE (roadmap G17), used as an invariant
matrix identity fork ......... OPEN — gated by §4, and gating is not resolution
retained Stage 9 root ........ RETAIN UNCHANGED pending a separate disposition checkpoint
```

The report (§5.1 head 11) and the closeout handoff must both carry this set. The convergence note
carries only the matrix identity fork; the others are not its subject.

## 10 · `HANDOFF_CURRENT.md` disposition · **DISCHARGED AT S10-C**

> **Status: done.** At S10-C the file was **replaced with a concise pointer** at
> `docs/harvest/handoffs/HANDOFF_STAGE_10_COMPLETE_2026-08-04.md`, dated `2026-08-04`. Every
> Stage 2.5-era statement below was removed — the old pointer, the Stage 3 blocker, the
> "nothing pushed" state, the assertion and wrapper counts, the verification command block, the file
> map and the seven Stage 3 invariants. The paragraph that follows is the **historical record of the
> defect**, retained so the disposition can be audited; it is no longer a description of the file.

**Historical — the state that made this disposition necessary.**
`docs/harvest/HANDOFF_CURRENT.md` described itself as *"Pointer file. Read this first."* It was last
updated on **2026-07-28** in the Stage 2.5 session, pointed at
`handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md`, and records
`push_state: local only — nothing pushed to origin/main`. All three statements are now false, and it
appears in neither the roadmap §11 evidence index nor the project-memory reading order — so the tree
contains a document instructing readers to start seven stages behind, while two authorities silently
route around it. Stages 3 through 9 each declined to touch it.

**Approved disposition:**

- **It is stale, and it is updated only at S10-C**, together with the Stage 10 completion handoff —
  because its correct content names a completion authority that does not exist until then.
- At S10-C it must **point to the Stage 10 completion authority** and explain that the Stage 10
  handoff **closes the original Stage 0–10 documentation task while M5, M6 and M7 remain open**.
- **S10-0 does not modify it.** It is outside this checkpoint's two-path set.
