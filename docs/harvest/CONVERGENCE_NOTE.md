# Matrix convergence note — decision record

```text
Genre                     DECISION RECORD. Not an implementation plan, not a
                          migration plan, not a deprecation notice, and not
                          authorization for any code or schema change.
Checkpoint                S10-2, the second Stage 10 deliverable
Subject                   the deliberate separation between the PROTECTED matrix
                          harvest family and the taxonomy harvest family
Gate authority            docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md §4
                          — five gates NEWLY AUTHORED AND RATIFIED AT S10-0
Definition authority      docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md §3
                          — a NEW S10-0 planning definition (erratum E10-2)
Retrospective authority    docs/harvest/IMPLEMENTATION_REPORT.md
                          fixed historical range 8865c54e..c3497fa
                          73 commits · 269 paths · 267 A / 2 M
Decision                  MATRIX UNIFICATION REMAINS DEFERRED
Gate outcome              Gate 1 UNMET · Gate 2 UNMET · Gate 3 PARTIALLY EVIDENCED
                          Gate 4 PARTIALLY EVIDENCED · Gate 5 UNMET
Matrix path               NOT DEPRECATED
Code change authorized    NONE
Milestones                M5 UNOPENED · M6 NOT STARTED · M7 NOT STARTED
Publication               ZERO · promotion ZERO · website consumption ZERO
```

---

## 1 · Decision summary

**Matrix unification remains deferred.**

Assessed against the five reconsideration gates ratified at S10-0, the committed repository supports
no reconsideration of matrix unification. Three gates are **UNMET** and two are **PARTIALLY
EVIDENCED**. No gate is satisfied.

The two gates that carry real evidence — Gate 3 (operational-contract compatibility) and Gate 4
(stable independent baselines) — are partially evidenced because the *underlying facts* are
committed and verifiable, while the *artifacts each gate actually requires* — a completed
difference classification, and representative comparable outputs from both families — do not exist.
Documenting a difference is not classifying it, and a green regression suite is not a representative
output.

The three gates that are unmet are unmet for one shared reason: **the decision Gate 1 names has no
owner.** Gate 1 is a product decision, Gate 5 is an ownership and authority decision, and Gate 2's
mapping cannot be authored without knowing which identity semantics the mapping targets. No amount
of further engineering evidence discharges any of the three.

Deferral here means *not now, and not yet decidable*. It does not mean the matrix path is going
away, and it must never be read as a step toward retiring it. **The matrix path is not deprecated.**

---

## 2 · Scope and non-authorization

This note is:

```text
a decision record
```

This note is **not**:

```text
an implementation plan
a migration plan
a deprecation notice
a recommendation to converge or to diverge further
authorization for any code, schema, configuration, test or artifact change
authorization to reconsider matrix unification
```

Stated explicitly, as the Stage 10 plan requires:

> **The matrix path is not deprecated.**
> **This note authorizes no protected-path change.**

Nothing in this note may be cited as approval for a patch, however small, and no gate assessment
below may be read as a proposal for the work that would close it. Describing the evidence a gate
requires is not scheduling that evidence, and naming a protected matrix path in this document is a
documentation reference, not a mutation — `IMPLEMENTATION_PLAN.md` §5 scopes the static
matrix-reference check to production implementation files and excludes `docs/**` by construction,
*"because the boundary test and the convergence note must name the matrix path"* `[plan §3.3]`.

**Both the five gates and the definition of matrix unification were authored and ratified at S10-0.**
They were not recovered, restored or reconstructed from an older document. Before S10-0 the tree
held three forward references to "the five gates" and none of them enumerated a gate; the term
"matrix unification" was used and never defined `[plan §0, errata E10-1 and E10-2]`. This note
assesses the S10-0 gate set and neither adds a gate, removes a gate, nor weakens one.

---

## 3 · Authority and evidence model

Sources used, in the committed authority order `[plan §2]`:

| Rank | Source | Used for |
|---|---|---|
| 1 | `src/harvest/**`, `scripts/harvest/**`, and the protected matrix scripts under `scripts/**` | identity rules, driver concurrency, robots, leases, ledger keying, merge semantics |
| 2 | `tests/**` — 63 wrappers, 44 taxonomy | regression evidence for both families; the protected-baseline verifier |
| 3 | `schemas/harvest/*.v1.json`, `config/harvest/**` | the taxonomy artifact contract, and the absence of any matrix schema |
| 4 | `handoffs/HANDOFF_STAGE_9_COMPLETE_2026-08-01.md` | Stage 9 execution and retained evidence |
| 6–7 | `docs/harvest/STAGE_10_IMPLEMENTATION_PLAN.md`, earlier stage plans | the gates (§4) and the ratified definition (§3) |
| 8–9 | `docs/harvest/TODO.md`, `ROADMAP_AND_ARTIFACT_LIFECYCLE.md` | carried-forward state, gap register |
| n/a | `docs/harvest/IMPLEMENTATION_REPORT.md` | the authoritative whole-task retrospective, **cited rather than re-derived**; it postdates the ranked list and does not displace ranks 1–3 |
| n/a | `docs/harvest/INVENTORY_AND_REUSE_MAP.md` | the reuse and duplication analysis written at implementation start — see §3.3 |

Rank 5 (earlier completion handoffs) is unused: nothing below Stage 9 bears on the matrix boundary.

`docs/harvest/IMPLEMENTATION_PLAN.md` is **superseded design input only** and is used below in exactly
one place — its §5 statement that the convergence note may name the matrix path — where it is
consistent with everything above it. **Project memory corroborates but never outranks the committed
tree.**

### 3.1 Evidence classes, kept apart

| Class | Meaning | Marked |
|---|---|---|
| **Committed evidence** | true of the tree at the entry commit, readable now | `[code]` `[schema]` `[test]` |
| **Historical evidence** | true of a named past commit, and still true *of that commit* | `[handoff]` `[report]` |
| **Current repository state** | a dated observation of the working tree | `[obs]` |
| **Inference** | a conclusion drawn from evidence, not itself observed | `[inference]` |
| **Missing product decision** | no committed artifact exists; the absence is the finding | `[absent]` |

An `[absent]` marker is a positive finding of this note: it records that a search of the committed
tree found nothing, not that the search was not performed.

### 3.2 Seven output classes, kept strictly apart

Statements below about what a pipeline "has produced" are meaningless without a class. These seven
are **never used interchangeably, never aliased, and never merged**; membership of one class does
**not** imply membership of any other, and no claim in this note collapses two of them together:

| # | Class | Meaning | Matrix family | Taxonomy family |
|:--:|---|---|---|---|
| 1 | **Test-generated temporary output** | artifacts written by a test under an isolated temporary root, discarded when that root is removed | **exists** — `tests/test_matrix_harvest.sh` drives the real scripts and writes `matrix/manifest.json`, per-cell query sets, per-cell harvest files and `matrix_union.json` under temp roots with a **mocked Claude backend and no network** `[test]` | exists — the fixture-backed suites |
| 2 | **Committed output** | artifacts tracked in the repository | none | none |
| 3 | **Retained output** | artifacts preserved outside the repository as evidence | none | **exists** — the retained Stage 9 root, 3 runs `[report §7.5]` |
| 4 | **Current working-state output** | artifacts present in the working tree now | none — no `state/matrix/` in the working tree `[obs]` | none — the four runtime paths absent `[obs]` |
| 5 | **Live output** | output of an execution against **real external sources or real live services**, rather than against a mocked test backend | **none recorded** | **exists** — the three bounded Stage 9 live validation runs against real sources, held in the external retained root; all three `publication_eligible: false` `[report §7, §14]` |
| 6 | **Production-state output** | artifacts written through the **designated production-state path or root** — for the taxonomy family `state/taxonomy_harvest/`, and for publication `data/harvested/` | **none recorded** | **none** |
| 7 | **Representative comparison evidence** | outputs of both families comparable against each other at the level Gate 4 requires | **none** | none at a production-representative level |

**Classes 5 and 6 are distinct, and the distinction is load-bearing.** *Live* describes what a run
talked to; *production-state* describes where it wrote. A run can be one without being the other,
and the taxonomy family is exactly that case:

```text
taxonomy live output              EXISTS — 3 bounded Stage 9 runs against real sources
taxonomy production-state output  NONE
matrix live output                none recorded
matrix production-state output    none recorded
```

**The three retained Stage 9 taxonomy runs were not written to the repository production state
root.** They ran under an **explicitly supplied external retained state root** — *"ran against an
**external retained root**, not the `state/taxonomy_harvest/` path"* `[report §11 row 19]` — and
therefore **do not constitute production-state output**. They are bounded validation runs and
retained evidence: they are **not publication**, they **do not establish publication eligibility**
(every one is `publication_eligible: false` by derivation, because `smoke` and `linkcheck` are
non-`harvest` modes `[report §14]`), and they establish **no production promotion and no website
consumption**. The repository's own production runtime paths remain absent — `state/taxonomy_harvest`,
`data/harvested`, `runs`, `LATEST_RUN_ID` `[obs]`. **No broader notion of "production" is used
anywhere in this note.**

**Test-generated temporary output is real output.** It is produced by the real, byte-frozen scripts
and it is asserted against. It is simply not committed, retained, current-working-tree, **live**,
production-state or comparison output — and in particular **the matrix family's temporary test
artifacts are not live output**, because that wrapper uses a mocked Claude backend and makes no
network request. This note never counts test output as any other class, nor does it pretend it does
not exist.

### 3.3 One standing caveat about `INVENTORY_AND_REUSE_MAP.md`

That document was written **at implementation start** (`8865c54e`) from a direct reading of the
source. Its *matrix-side* readings remain current by construction: all five matrix scripts are
byte-frozen to that same anchor by the protected baseline, so a reading taken there still describes
them. Its *taxonomy-side* column describes the design that was then intended, and one row of it did
not land as written — see §4.4. The distinction is applied throughout: matrix readings from that
document are treated as committed evidence; taxonomy readings from it are checked against the code
that actually exists.

---

## 4 · The current architecture boundary

### 4.1 Two families, deliberately separate

| | Protected matrix family | Taxonomy harvest family |
|---|---|---|
| Orchestrator | `scripts/run_matrix.sh` | `src/harvest/run_cells.py::run()` — a Python function with **no CLI** `[roadmap §4]` |
| Cell worker | `expand_queries_cell.sh` + `harvest_matrix_cell.sh` | in-process, adapter-driven |
| Merge | `scripts/merge_matrix.sh` | `records.py` + `artifacts.py`, per run |
| State | `state/matrix/<cell>.json` → derived `matrix_union.json` | `runs/<id>/**` + 12 shared ledgers + 12 shared rejection logs |
| Discovery | model-driven: `claude -p` with `--allowedTools "Read,WebSearch,WebFetch"` `[code]` | deterministic adapters over a frozen fixture corpus `[code]` |
| Identity | `(category, topic, name)`, normalized, last-wins `[code: merge_matrix.sh]` | `identity_url` + precedence + cross-category duplicate constraints `[code: ledger.py, urlkey.py]` |
| JSON Schema | **none exists** `[schema]` | 13 committed schemas under `schemas/harvest/` `[schema]` |
| Run against real sources — **live** (§3.2 class 5) | **no** — no live matrix run is recorded | **yes** — three bounded Stage 9 validation runs against real sources, all `publication_eligible: false` `[report §7, §14]` |
| Run against production state (§3.2 class 6) | **no** — no committed, current-working-tree or baseline-recorded `state/matrix/` corpus exists (§3.2, §8) | **no** — those three runs used an **explicitly supplied external retained state root**, not `state/taxonomy_harvest/` `[report §11 row 19]` |
| Offline behaviour exercised | **yes** — `tests/test_matrix_harvest.sh` drives the real scripts end to end under temporary roots with a mocked Claude backend and no network; this is test execution, **neither live nor production-state** `[test]` | yes — 44 taxonomy wrappers over a frozen fixture corpus `[test]` |

Seven of the eighteen protected paths belong to the matrix family — five scripts (`run_matrix.sh`,
`matrix_spec.py`, `merge_matrix.sh`, `expand_queries_cell.sh`, `harvest_matrix_cell.sh`) and two
mandatory regression wrappers (`tests/test_matrix_harvest.sh`, `tests/test_parallel_harvest.sh`) —
all byte-frozen to `8865c54e` `[code: tests/fixtures/taxonomy/protected_paths.txt]`.

**Protected-baseline membership is not evidentiary relevance, and the two wrappers differ.** Both are
byte-frozen and both are mandatory in the 63-wrapper inventory, but only one is evidence about the
matrix:

```text
tests/test_matrix_harvest.sh    DIRECT protected matrix regression evidence.
                                Drives the real matrix scripts end to end under
                                temporary roots with a mocked Claude backend.
                                64 assertions in the authoritative successful gate.

tests/test_parallel_harvest.sh  ENTITY-LANE regression evidence, 62 assertions.
                                Covers split_entity_registry.py, harvest_entities.sh
                                and merge_building_blocks.sh. NOT direct matrix
                                regression evidence, and never counted as such here
                                — protection and historical adjacency to matrix
                                material do not make a wrapper a matrix wrapper.
```

### 4.2 The semantic identity fork

This is the centre of the whole question, and it was identified before any of this task's code was
written:

> **Merge/dedup identity.** Matrix `merge_matrix.sh:84-85`, `(category, topic, name)`. New:
> `identity_url` + precedence. **Medium — the real semantic fork.** The matrix *deliberately wants*
> the same tool in two cells to be two findings ("matters for healthcare agents" / "…for finance
> agents"). This taxonomy forbids independent duplication across categories. **Convergence needs a
> product decision, not a refactor.**
>
> — `INVENTORY_AND_REUSE_MAP.md` §3.2

Confirmed against the frozen source: `merge_matrix.sh` builds `matrix_key` as
`norm(category) | norm(topic) | norm(name)` and folds with `INDEX(.matrix_key)` — last row wins
within a key, and two cells holding the same tool produce two surviving rows `[code]`. `CLAUDE.md`
states the same rule for operators: *"union identity is (category, topic, name), not `entity_key` —
the same tool in two cells is two findings, not a duplicate."*

The taxonomy side keys on canonical identity instead: *"THE LEDGER IS KEYED BY IDENTITY, NOT BY THE
RAW STRING. `identity_url` is the …"* `[code: src/harvest/ledger.py]`, with precedence
classification and alias adjudication layered above it.

**These are not two implementations of one rule. They are two rules.** One treats cell membership as
part of what a finding *is*; the other treats a URL identity as the thing and cell membership as an
attribute of it. Neither is a defect. Choosing between them changes what the product means by "a
finding", which is why it is a product decision and not a refactor.

### 4.3 Shared and duplicated primitives

`INVENTORY_AND_REUSE_MAP.md` §3.1 records three components reused **unmodified** — `lockdir.sh`,
`clean_json.sh` and `github_meta.py`, all three of them protected paths — and §3.2 records **six**
deliberately duplicated primitives with their convergence risk stated: bounded worker pool (Low),
atomic write-then-rename (Low, cross-language and unshareable), ledger seed/patch (Medium, two
ledger schemas coexisting indefinitely), merge/dedup identity (Medium — the fork), cell manifest
(Low), query expansion (Low).

**Six risks are not five gates, and a risk is not a reconsideration criterion** `[plan E10-1]`. The
six rows are evidence *for* the gate assessments below; they are not themselves a gate set, and this
note does not renumber them into one.

### 4.4 One inventory row that did not land as designed

The bounded-worker-pool row of §3.2 names `scripts/harvest/run_topics.sh` (~35 lines) as the
taxonomy counterpart to the matrix pool at `run_matrix.sh:157-193`. **That file does not exist in the
committed tree** `[obs]`. What landed instead is a strictly sequential driver:

> *SEQUENTIAL, DELIBERATELY. Cells run one after another. … There is no lock, thread, process or
> async call anywhere below.* … *Running cells concurrently must fix CF-1 first, in its own
> checkpoint.*
> — `src/harvest/run_cells.py` `[code]`

This is recorded here because it changes a Gate 3 answer: on the "bounded concurrency" dimension the
two families are not two implementations of one idiom, but **one implementation and one deliberate
absence**, with the taxonomy side carrying an open carried-forward item (CF-1) that gates ever
building the other half `[roadmap §4]`. It is stated as a correction to a start-of-implementation
design document, not as a defect in either family.

### 4.5 Helper reuse versus full unification

The S10-0 boundary, applied:

| Action | Unification? |
|---|---|
| Isolated reuse of a helper that **provably preserves both families' existing contracts** | **No.** The three §3.1 components are already reused unmodified and that is an accepted state, not a partial unification |
| Accepting continued duplication of the six §3.2 primitives | **No.** Deliberate duplication is the current design, not a step toward or away from convergence |
| Replacing matrix identity semantics | **Yes** |
| Deprecating matrix scripts | **Yes** |
| Making taxonomy semantics canonical for matrix output | **Yes** |
| Consolidating both families behind one canonical artifact or merge contract | **Yes** |

The distinction matters because the easiest way to overstate progress here would be to point at
shared `lockdir.sh` or at two families both using atomic write-then-rename and call convergence
"already partly done". It is not. **Shared idioms are not a shared contract**, and no committed
artifact makes any semantic claim across the two families.

### 4.6 Why this is a product decision and not a refactor

A refactor preserves observable behaviour. Unification cannot: whichever identity rule survives,
the other family's output changes meaning. If `identity_url` becomes canonical, the matrix loses its
ability to report one tool as two cell-scoped findings — which is the matrix's stated purpose. If
`(category, topic, name)` becomes canonical, the taxonomy loses its cross-category duplicate
constraint, its precedence rules and its alias adjudication. There is no mapping that keeps both,
because the two rules disagree about how many findings exist for the same input. That disagreement
is the product's, not the code's.

---

## 5 · Gate 1 — Product identity semantics · **UNMET**

**Gate definition.** A named product decision must resolve the semantic fork between matrix identity
`(category, topic, name)` — where the same entity in multiple cells may remain multiple deliberate
findings — and taxonomy identity `identity_url` plus precedence and cross-category duplicate
constraints. Required evidence: an explicit product owner or decision authority; accepted duplicate
and cross-category semantics; treatment of provenance and cell membership; worked examples covering
the same entity appearing in multiple cells or categories `[plan §4 Gate 1]`.

**Current status.** UNMET, and unowned.

**Committed supporting evidence.**

- Both identity rules exist, are implemented, and are precisely readable: `merge_matrix.sh` builds
  the normalized three-part `matrix_key` and folds with `INDEX` `[code]`; `src/harvest/ledger.py`
  keys on `identity_url`, with `urlkey.py`, `classify.py` and `aliases.py` supplying canonicalization,
  precedence and alias adjudication `[code]`.
- The fork is named and classified as *"the real semantic fork"*, with the explicit finding that
  *"convergence needs a product decision, not a refactor"* `[inventory §3.2]`.
- The operator-facing contract states the matrix rule in the same terms `[CLAUDE.md]`.

**Partial evidence.**

- An illustrative example of intended duplicate semantics exists in prose — the same tool mattering
  for "healthcare agents" and for "finance agents" `[inventory §3.2]`. It is an illustration of the
  matrix rule, not a worked example of a *resolved* rule.

**Missing or insufficient evidence.**

- **No product owner or decision authority is named anywhere in the committed tree** `[absent]`.
- **No accepted duplicate or cross-category semantics.** Nothing states which rule a converged
  system would follow, or whether both could be retained under some discriminator `[absent]`.
- **No treatment of provenance or cell membership** under a converged identity: whether cell
  membership becomes an attribute, a set, or a first-class part of identity is undecided `[absent]`.
- **No worked examples over real data are possible today.** No committed, current-working-tree or
  baseline-recorded `state/matrix/` corpus exists; **no live matrix run is recorded, and no
  production-state matrix run is recorded** — two separate absences (§3.2 classes 5 and 6) — so
  there is no real-data matrix output to draw an example from (§3.2, §8). The
  temporary artifacts written by `tests/test_matrix_harvest.sh` are synthetic, mock-driven and
  discarded with their temporary roots — a worked example built from them would illustrate the
  fixture, not the product.
- A closely related product question is independently open: the destination taxonomy for the 1,161
  assessed entity-registry entities is *"an open product decision"* `[TODO, follow-up 2]`.

**Current blocker.** There is no decision authority. This gate cannot be advanced by engineering
work of any kind, because its output is a decision, not an artifact.

**Required product or implementation authority.** A **named product decision owner** with authority
over what the product means by "a finding" across both families.

**Exact evidence required for reconsideration.**

1. A named product decision owner, recorded in the repository.
2. A written, approved statement of duplicate and cross-category semantics for a converged identity.
3. An explicit treatment of provenance and cell membership under that identity.
4. Worked examples covering (a) one entity in multiple cells of one category, (b) one entity across
   multiple categories, (c) one entity whose canonical URL differs from its matrix `name` key —
   each showing the resulting finding count under the decided rule.

**Conclusion.** **UNMET.** No committed evidence supports any element of this gate beyond the
statement of the problem.

---

## 6 · Gate 2 — Lossless contract mapping · **UNMET**

**Gate definition.** A field-level and artifact-level mapping must show how both families' inputs,
manifests, entities, ledgers, rejection evidence, provenance, schemas and lifecycle states could
converge without silent information loss — with explicit handling of information present in one
family and absent in the other, a schema/version compatibility strategy, and **no assumption that
similarly named artifacts are semantically equivalent** `[plan §4 Gate 2]`.

**Current status.** UNMET. No such mapping exists in any form.

**Committed supporting evidence.**

- The **taxonomy side is fully specified**: 13 committed JSON Schemas (`taxonomy` · `facet_vocabulary`
  · `facets.generated` · `discovery_lane` · `candidate_pool` · `record` · `cell_artifact` ·
  `topic_artifact` · `run_manifest` · `ledger` · `rejection` · `alias_conflict` · `coverage_report`)
  `[schema]`; an exact per-run accounting of 18 selected-run + 24 shared = 42 JSON + 1 pointer = 43
  paths `[report §10]`; and five lifecycle classes kept strictly apart — per-run immutable output,
  shared mutable state, unpersisted deterministic stdout, repository publication paths (absent), and
  external retained evidence `[report §10]`.
- The **matrix side is specified only by its scripts**: `state/matrix/manifest.json` written by
  `matrix_spec.py`, per-cell `state/matrix/<cell>.json`, and a derived `matrix_union.json` from
  `merge_matrix.sh` `[code]`.
- The ledger divergence is already documented at the row level: *"Two ledger schemas coexist
  indefinitely: the legacy one keys raw `source_url` with no canonicalization, the new one keys a
  canonicalized immutable identity"* `[inventory §3.2]`.
- The gate's own warning has already cost this project a checkpoint: **E9-20 — the same schema is
  not the same semantic validator.** The committed `runvalidate` rejected any mode other than
  `smoke` and would have refused a correct linkcheck run, even though the schema was unchanged
  `[TODO stage_9_6_linkcheck]`. Two artifacts sharing a name — "ledger", "manifest", "cell" — are
  not thereby the same contract.

**Partial evidence.**

- Exactly one of the many field-level relationships has a written characterization: the two ledgers'
  keying difference `[inventory §3.2]`. That is one row of a mapping that would need to cover every
  artifact in both families.

**Missing or insufficient evidence.**

- **No field-by-field mapping exists** `[absent]`. **No artifact-by-artifact mapping exists**
  `[absent]`.
- **No JSON Schema exists for any matrix artifact.** All 13 committed schemas are taxonomy schemas
  under `schemas/harvest/` `[schema]`. The matrix artifacts are jq-shaped and schema-less, so one
  side of the required mapping has no formal contract to map *from*.
- **Information present in one family and absent in the other is unhandled.** The asymmetries are
  large in both directions: the matrix has no run manifest, no run identity, no pointer, no rejection
  log, no coverage report and no alias-conflict report; the taxonomy has no positional cell
  identity, no query set and no per-cell query-expansion state. Nothing states what happens to any
  of it under convergence `[absent]`.
- **No schema or version compatibility strategy across the families exists** `[absent]`. The
  taxonomy's own versioning discipline is strong — *"No `schema_version` was ever bumped"*, because
  both the S9-5C2 sighting integers and S9-6's `base_run_id` were shaped so pre-existing manifests
  stay valid untouched `[report §10]` — but that is within-family discipline, and there is no
  cross-family version concept at all.
- **Positional cell identity is unmapped and known to be fragile.** `matrix_spec.py` names cells
  `category#i_topic#j` from 1-based indices into the lists *as typed*, so *"reordering the input
  lists renames every cell"* `[inventory §2.3]` `[code]`. Any mapping must state what a taxonomy
  slug-keyed cell corresponds to under that scheme.

**Current blocker.** The mapping's *target* is undecided. A lossless mapping is a mapping onto some
converged contract, and Gate 1 has not chosen one — so authoring the mapping now would mean
inventing the destination it is supposed to map to.

**Required product or implementation authority.** A **named implementation owner** to author the
mapping, working **after** the Gate 1 product decision fixes the target semantics.

**Exact evidence required for reconsideration.**

1. A field-by-field mapping across both families' inputs, manifests, entities, ledgers, rejection
   evidence, provenance and lifecycle states.
2. An artifact-by-artifact mapping, naming for every artifact in each family either its counterpart
   or its explicit absence.
3. An explicit disposition for every one-sided field: preserved, derived, dropped-by-decision, or
   blocking.
4. A schema and version compatibility strategy, including a formal contract for the matrix artifacts
   that today have none.
5. A statement, per similarly named artifact pair, of whether the names denote the same contract —
   with the E9-20 precedent applied rather than assumed away.

**Conclusion.** **UNMET.** The gate requires an artifact that does not exist and cannot be correctly
authored before Gate 1.

---

## 7 · Gate 3 — Operational-contract compatibility · **PARTIALLY EVIDENCED**

**Gate definition.** Every material difference between the two families' operational contracts must
be classified as **equivalent**, **intentionally different**, or **blocking**, across at minimum:
bounded concurrency, determinism, atomic persistence, resume and recovery, failure isolation, query
expansion, ledger ownership, robots and network behaviour, throttling, and run identity and
pointers. The gate requires **evidence, not implementation** `[plan §4 Gate 3]`.

**Current status.** PARTIALLY EVIDENCED. The underlying facts are committed and readable for most
dimensions on both sides. **The classification the gate actually requires has never been performed
and does not exist in any committed document** `[absent]`.

**Committed supporting evidence.** Dimension by dimension, what is committed today:

| Dimension | Matrix family `[code, byte-frozen at 8865c54e]` | Taxonomy family `[code]` |
|---|---|---|
| **Bounded concurrency** | `jobs -rp` pool, `MAX_PARALLEL` default 4, `STAGGER_SEC` default 15 between lane launches; `run_matrix.sh:157-193` | **None.** `run_cells.run()` is strictly sequential; *"no lock, thread, process or async call anywhere"*; CF-1 must be fixed first (§4.4) |
| **Determinism** | no whole-run determinism contract is asserted by any committed test, and discovery is model-driven; the fold *is* asserted idempotent offline by `tests/test_matrix_harvest.sh` `[test]` | whole-tree byte-identity guards under equal inputs, equal ordering, equal injected UTC **and** equal injected monotonic clocks `[TODO stage_9_5c1_scope_expansion]` |
| **Atomic persistence** | inline `mktemp` + `mv` across ~8 bash scripts, unique temp names | Python `mkstemp` + `os.replace` in `src/harvest/artifacts.py`; validates before writing |
| **Resume and recovery** | completion decided by **re-running `--check`**, never by trusting a child's exit code `[code: run_matrix.sh:253-255]` | `recovery.py` plus explicit re-run semantics and a finished-run refusal `[code]` |
| **Failure isolation** | per-cell lane; a failed lane is re-checked, not inferred | per-cell status `ok` / `not_run` / raised; a raised cell carries no duration and no sighting tuple `[TODO stage_9_5c1_timing, stage_9_5c2_sightings]` |
| **Query expansion** | per-cell Stage 1A `expand_queries_cell.sh`; expansion refuses to shrink an existing set `[CLAUDE.md]` | **not used** — deterministic adapters need no generated query set `[inventory §3.2]` |
| **Ledger ownership** | `harvest_matrix_cell.sh:200-252` (jq), keyed on raw `source_url`, no canonicalization | Python, keyed on `identity_url`; 12 shared ledgers updated in place, cross-run, latest-state only `[report §10]` |
| **Robots and network** | **no robots handling anywhere**; all fetching inside a `claude -p` lane via `WebSearch`/`WebFetch` under `--allowedTools` `[inventory §2.1]` `[code]` | local `httpclient.py`: *"robots.txt with RFC 9309 semantics and Crawl-delay"*, bounded redirects, robots re-checked on host change `[code]` |
| **Throttling** | `throttled_domains[]` is a field the agent spec asks the *model* to return, and **no script ever reads it back**; pacing is the launch stagger only `[inventory §2.1]` | cross-process per-domain leases (`domainlease.py`), `effective_interval` / `effective_concurrency`, request budgets `[code]` |
| **Run identity and pointers** | **none** — no run id, no pointer; `state/matrix/<cell>.json` is current-state only | `runs/<id>/**`, `LATEST_RUN_ID` moving **last, or not at all**, linkcheck runs carrying `base_run_id` lineage `[report §10]` |

**Partial evidence.**

- Every dimension above has committed facts on the taxonomy side, and eight of the ten have committed
  facts on the matrix side.
- The two families' *reasons* for several differences are documented rather than merely observed —
  the `jobs -rp` idiom's avoidance of `kill -0` and `wait -n`, and the "unique temp names, never a
  fixed `<file>.tmp`" rule, are both recorded with their rationale `[inventory §3.2, §4]`.
- **Selected matrix operational behaviour is observed offline, not merely read from code.**
  `tests/test_matrix_harvest.sh` drives the real, byte-frozen matrix scripts end to end under
  temporary state roots with a mocked Claude backend and no network, and asserts — among its 64
  assertions — concurrency and `MAX_PARALLEL` handling, lane locking (same cell refused, different
  cells free), per-cell write isolation with `category`/`topic` stamped from the manifest, merge
  folding, cross-cell distinctness, idempotence, and refusal semantics `[test]`. That touches four
  of the ten dimensions — bounded concurrency, failure isolation, query expansion and the merge half
  of ledger ownership — with behavioural rather than purely textual evidence.
- **What that wrapper does not prove, stated so it is never over-read**: it does not prove live model
  behaviour, production network behaviour, representative production performance, production-state
  recovery, production compatibility with the taxonomy pipeline, or completion of this gate's
  required classification. It is offline, mock-driven evidence about the real scripts, and nothing
  more.

**Missing or insufficient evidence.**

- **No classification exists.** Not one difference above is recorded anywhere as *equivalent*,
  *intentionally different*, or *blocking* `[absent]`. The gate's deliverable is that classification;
  the table above is its raw material, not the deliverable.
- **Two dimensions cannot be classified from current evidence at all.**
  - *Bounded concurrency*: the taxonomy has no concurrent path to compare, and building one is
    itself gated by CF-1 `[roadmap §4]`. "Different" and "not yet implemented" are not the same
    finding and must not be recorded as one.
  - *Determinism*: the matrix's discovery is model-driven, and **no committed test asserts a
    whole-run matrix determinism contract** `[absent]` — the offline fold-idempotence assertion is
    narrower and does not stand in for one. Absence of a determinism guarantee is not evidence of
    non-determinism, and neither may be assumed.
- **No live operational behaviour and no production-state operational behaviour have been observed
  for the matrix family.** These are two separate absences (§3.2 classes 5 and 6): **no live matrix
  run is recorded** and **no production-state matrix run is recorded** (§3.2, §8), so nothing in the
  table above rests on either. Six of the ten dimensions — determinism, atomic persistence, resume and
  recovery, robots and network, throttling, and run identity and pointers — remain readings of code
  rather than of observed behaviour of any kind.
- **The offline evidence above does not close this gap, and must not be presented as if it did.**
  Mock-driven behaviour under a temporary root is evidence about the scripts; it is not evidence
  about how they behave against real sources, at real rates, under real failure, or beside the
  taxonomy pipeline. Robots and throttling in particular are unexercised by it, because the mock
  performs no network access at all.
- **Robots and throttling are the strongest candidates for a `blocking` classification**, since one
  family enforces RFC 9309 locally and the other has no robots concept anywhere — but calling that
  *blocking* would itself be the classification this gate requires, and this note does not perform
  it `[inference, not recorded as a finding]`.

**Current blocker.** The classification has never been authored, and two of its ten required
dimensions have no comparable evidence on one side. A classification produced now would be
incomplete by construction and would silently convert "not implemented" into "intentionally
different".

**Required product or implementation authority.** A **named implementation owner** to author the
classification; **product authority is required for any dimension classified as blocking**, because
declaring a difference blocking constrains what convergence could ever mean.

**Exact evidence required for reconsideration.**

1. A written classification of every material difference as equivalent, intentionally different, or
   blocking, covering all ten named dimensions with none silently omitted.
2. For bounded concurrency: either a resolution of CF-1 with a comparable taxonomy path, or an
   explicit record that the dimension is unclassifiable until then.
3. For determinism: a stated whole-run determinism contract for the matrix family, or an explicit
   record that none exists and that the difference is therefore unclassified.
4. For the six dimensions the offline wrapper does not reach: **live** operational evidence for the
   matrix family (a run against real sources), and separately any **production-state** operational
   evidence required (a run through the designated production-state root) — each obtained without
   modifying any protected path and under a separate approval that this note does not grant.
5. A statement of which classified differences would survive convergence and which would have to be
   abandoned — with the abandonment named, not implied.

**Conclusion.** **PARTIALLY EVIDENCED.** Substantial committed evidence exists on both sides; the
required classification does not, and two dimensions are not classifiable from current evidence.
**This gate is not satisfied.**

---

## 8 · Gate 4 — Stable independent baselines and comparison evidence · **PARTIALLY EVIDENCED**

**Gate definition.** Both pipelines need stable, reproducible, independently validated baselines and
representative comparison evidence before reconsideration. The protected matrix baseline must remain
intact — 18/18 byte-identical to `8865c54e`. Authoritative regression evidence must exist for both
families; representative outputs must be comparable **without mutating retained Stage 9 evidence**;
known differences, data-loss risks and rollback constraints must be documented. **No unified
implementation or migration experiment is authorized merely to satisfy this gate** `[plan §4 Gate 4]`.

**Current status.** PARTIALLY EVIDENCED. Baselines and repeatable offline regression evidence are in
good order **for both families**. **What is missing is specifically the representative comparison
corpus this gate requires** — a retained corpus from a **live** run, plus any separately required
**production-state** evidence — **not test output in general**, and it cannot be produced under any
current authorization.

**Committed supporting evidence.**

- **The protected baseline mechanism is committed and specific.** `tests/fixtures/taxonomy/protected_paths.txt`
  defines the 18 paths; `protected_baseline.py` verifies the working tree against
  Git's own rendering of `8865c54e`, pinning the observed `eol_form` per file so that an EOL-only
  rewrite fails verification even though `git diff` calls the file clean `[code]` `[inventory §5.1]`.
  `tests/test_taxonomy_protected_baseline.sh` case C proves exactly that `[test]`.
- **The protected baseline was 18/18 at the last formal L0 validation** and was deliberately not
  rerun for the implementation report `[report §15]`. **This note ran no verifier of any kind**
  (§13); the 18/18 figure here is cited historical evidence, not a fresh observation.
- **Authoritative regression evidence exists for both families, in one run.** The 63-wrapper gate
  passed at `ec9bedc` — 43 suites, 2,386 tests, 0 failures / 0 errors / 0 skips `[report §1, §8.3]`.
  **The direct matrix regression evidence in that gate is `tests/test_matrix_harvest.sh`, 64 passed**
  `[report §11 row 13]`. `tests/test_parallel_harvest.sh`, 62 passed, is in the same gate and is
  equally protected, but its subject is the **entity lanes** — `split_entity_registry.py`,
  `harvest_entities.sh`, `merge_building_blocks.sh` — so it is **not** matrix regression evidence and
  is not counted as such here (§4.1).
- **The matrix family has a stable, repeatable offline regression baseline.** The five matrix scripts
  and the direct matrix wrapper are byte-pinned to `8865c54e`, and that wrapper drives the real
  scripts end to end under temporary roots, so the matrix side is reproducibly exercised rather than
  merely frozen `[test]`.
- **The matrix boundary is enforced structurally, not by assertion**: the protected-baseline verifier
  plus `git diff --exit-code` over the seven matrix paths; the once-planned
  `test_taxonomy_matrix_boundary.sh` never existed and was not needed `[report §11 row 12]`.
- **The retained Stage 9 evidence root is identified and frozen**: three runs, 99 regular files, 54
  directories, `LATEST_RUN_ID = 20260801T085829Z-40852`, full aggregate `0a14269a…18e3`; disposition
  **retain unchanged** pending a separately approved disposition checkpoint `[report §7.5]`.
- **Failed regression evidence is preserved as evidence**, not overwritten by the later success: the
  63/63 gate **failed rc 1** at `8479095` and passed at `ec9bedc`, and the two are recorded as
  distinct historical facts `[report §8.2, §8.3]`.

**Partial evidence.**

- The taxonomy family has representative outputs — but only three bounded runs, all in the external
  retained root, all `publication_eligible: false` **by derivation** because `smoke` and `linkcheck`
  are non-`harvest` modes `[report §14]`. They are legitimate regression and milestone evidence; they
  are not a production-representative corpus.
- Known differences are documented for six primitives with a risk rating each `[inventory §3.2]` —
  which is a risk register, not the differences/data-loss/rollback documentation this gate names.

**Missing or insufficient evidence.**

- **Four separate absences, enumerated rather than merged** (§3.2 classes 3, 5, 6 and 7):

  ```text
  1  No committed or retained representative matrix corpus from a LIVE run is available.
  2  No matrix PRODUCTION-STATE corpus is available.
  3  The taxonomy family has three retained bounded LIVE runs, but NO production-state corpus.
  4  No representative cross-family COMPARISON corpus exists at the level Gate 4 requires.
  ```

  Absences 1 and 2 are different findings about different classes and are never treated as one.
  Absence 3 is why the taxonomy side cannot supply the missing half either: a live corpus exists,
  but it is bounded validation evidence in an external retained root, not a production-state corpus.
- **The temporary test artifacts do not fill any of those four gaps.** The real matrix scripts *have*
  produced `matrix/manifest.json`, per-cell query sets, per-cell harvest files and `matrix_union.json`
  under the isolated test roots used by `tests/test_matrix_harvest.sh` with a mocked Claude backend
  and no network. **Those artifacts are discarded with their temporary roots and are class-1 test
  output only — not committed, retained, current-working-tree, live, production-state or comparison
  output** (§3.2). The persistent form is absent: **no committed, current-working-tree, or
  baseline-recorded `state/matrix/` corpus exists**, and the source description is *"implemented and
  tested but has never been run against production state"* `[inventory §1]`. **Gate 4's comparison
  operand is therefore missing at the representative-comparison level — not empty in the sense that
  no matrix output of any kind has ever been produced.**
- **No data-loss risk documentation exists** for a hypothetical convergence `[absent]`.
- **No rollback constraints are documented** `[absent]`.
- **The gate's own trap is live here.** Producing the missing comparison evidence would require
  running the matrix family against real state, or building a shared path to compare through — and
  the gate explicitly authorizes **no** unified implementation or migration experiment merely to
  satisfy itself. *A gate that can be satisfied only by building the thing it gates is not a gate*
  `[plan §4 Gate 4]`. Nothing in this note authorizes such a run, and the reconsideration package
  below deliberately does not schedule one.
- **Comparison must not touch the retained Stage 9 root.** That root is the taxonomy family's only
  representative output and is bound to remain unchanged `[report §7.5]`, so it cannot serve as a
  working comparison corpus.

**Current blocker.** The matrix comparison operand is missing at the representative level — no
retained corpus from a live matrix run, and no production-state matrix corpus — and the
authorization needed to create either is exactly what this gate forbids granting for the gate's own
sake. **No approved matrix run or migration experiment is authorized merely to create that corpus**,
and this note grants no such authorization.

**Required product or implementation authority.** A **named implementation owner**, plus a
**separate approval** — outside this note and outside Stage 10 — for **either** a matrix execution
against real sources (a live run) **or** a matrix execution through a designated production-state
root, which are two distinct authorizations for two distinct classes. Neither run is recorded, and
the matrix scripts are protected. Offline execution under the existing regression wrapper needs no
new authority, is neither live nor production-state, and does not discharge this requirement.

**Exact evidence required for reconsideration.**

1. At least one **representative** matrix output: a **retained corpus from a live matrix run**, plus
   any separately required **production-state** matrix evidence — two distinct items, each produced
   under its own separately approved boundary. The byte-pinned protected baseline and the offline
   regression wrapper already supply the *stable, reproducible, independently validated baseline*
   half of this requirement; it is the representative corpus that is missing.
2. A stable, reproducible taxonomy baseline that is **not** the retained Stage 9 root, so comparison
   never mutates retained evidence.
3. A fresh 18/18 protected-baseline verification at the reconsideration boundary.
4. Authoritative regression evidence for both families, current as of that boundary.
5. Documented known differences, data-loss risks and rollback constraints — as documents, not as a
   risk-rating table.
6. An explicit record that no unified implementation or migration experiment was performed to
   produce any of the above.

**Conclusion.** **PARTIALLY EVIDENCED.** Baselines, boundary enforcement and repeatable offline
regression evidence are strong and current **for both families**. What is absent on the matrix side
is a retained representative corpus from a **live** run, and separately any **production-state**
corpus — neither obtainable without an authorization the gate itself withholds; and the taxonomy
side, which does have three retained live runs, has **no production-state corpus** to pair with
them. **This gate is not satisfied.**

---

## 9 · Gate 5 — Ownership, migration and rollback authority · **UNMET**

**Gate definition.** Reconsideration requires a named implementation owner, a named product decision
owner, an approved migration boundary, a compatibility and deprecation policy, rollback criteria, a
protected-path approval process, and continued matrix support until a later approved decision
`[plan §4 Gate 5]`.

**Current status.** UNMET. Two of the seven requirements have committed support; five have none.

**Committed supporting evidence.**

- **A protected-path approval process exists and is enforced.** The path list is committed
  (`tests/fixtures/taxonomy/protected_paths.txt`, 18 paths, 7 of them matrix); verification is
  committed (`protected_baseline.py`, `verify_protected_baseline.sh`) and wrapper-tested
  (`test_taxonomy_protected_baseline.sh`); every checkpoint is approved **by name with an exact
  allowed-path set**, and a checkpoint that discovers it needs a path outside that set **stops and
  reports rather than widening itself** — a rule S9-1, S9-2 and S9-4 each hit in practice
  `[plan §6]`. Commits go through `safe_commit.sh` with explicit paths, never `-A` or a glob, and
  every push requires its own approval `[CLAUDE.md]` `[plan §7.3]`.
- **Continued matrix support is explicitly confirmed.** *"The matrix path is not deprecated"* is
  stated in `TODO.md`, repeated in the Stage 10 plan `[plan §3.3]`, and restated in this note (§2,
  §12). Matrix-path deprecation and matrix unification are both listed among the implementation
  report's explicit non-claims `[report §14]`.

**Partial evidence.**

- Ownership *of checkpoints* is well established — every checkpoint in this task had an approving
  authority and an exact path set. That is a process for approving work, not an owner for a decision.
  The two must not be conflated: an approval process can authorize a decision it cannot make.

**Missing or insufficient evidence.**

- **No implementation owner is named for convergence work** `[absent]`.
- **No product decision owner is named** `[absent]` — the same absence that blocks Gate 1.
- **No migration boundary is proposed or approved** `[absent]`.
- **No compatibility or deprecation policy exists** `[absent]`. Note that the taxonomy family has
  strong *within-family* compatibility discipline — no `schema_version` bump was ever needed, and
  both S9-5C2 and S9-6 were shaped so pre-existing manifests stayed valid untouched `[report §10]` —
  but that is a practice, not a cross-family policy, and it says nothing about deprecation.
- **No rollback criteria exist** `[absent]`. Nothing states what observation would cause a
  convergence attempt to be reverted, or how.
- **Related ownership gaps are already recorded as open**: M5 has no owner and its review artifact,
  schema and acceptance process are undefined; promotion has no implementation; website integration
  is unowned `[report §13]` `[roadmap G4, G7, G9, G10]`. Convergence ownership would be a further
  unowned decision in a set that already has several.

**Current blocker.** No owner exists on either axis, so there is no one who could approve a migration
boundary, a compatibility policy or a rollback criterion.

**Required product or implementation authority.** Both — a **named product decision owner** and a
**named implementation owner** — recorded before any of the remaining five requirements can be
authored.

**Exact evidence required for reconsideration.**

1. A named implementation owner for convergence work.
2. A named product decision owner for identity semantics.
3. A proposed and approved migration boundary, stating exactly which paths could ever change.
4. A compatibility and deprecation policy covering both families' artifacts and consumers.
5. Rollback criteria: what is observed, who decides, and how the prior state is restored.
6. A protected-path approval process explicitly extended to convergence work — the existing one is
   sound and would need naming, not replacing.
7. An explicit, dated confirmation that the matrix path remains supported until a later approved
   decision says otherwise.

**Conclusion.** **UNMET.** Five of seven requirements have no committed support.

---

## 10 · Cross-gate dependencies

```text
Gate 1  Product identity semantics
          |
          |  fixes the target semantics that a mapping maps ONTO
          v
Gate 2  Lossless contract mapping
          |
          |  a mapping is what makes a difference classifiable as
          |  "equivalent" rather than merely "different"
          v
Gate 3  Operational-contract compatibility  ---- feeds ---->  Gate 4 comparison design
          |
          v
Gate 4  Stable independent baselines and comparison evidence

Gate 5  Ownership, migration and rollback authority
          |
          +-- supplies the PRODUCT owner Gate 1 needs
          +-- supplies the IMPLEMENTATION owner Gates 2, 3 and 4 need
```

Read plainly:

- **Gate 1 is upstream of Gates 2 and 3.** Gate 2's mapping needs a destination; Gate 3's
  classification needs to know which differences would have to survive. Authoring either before
  Gate 1 means inventing the answer Gate 1 is supposed to give.
- **Gate 5 is upstream of everything**, because it supplies the owners the other four gates require.
  Gate 5's product-owner requirement and Gate 1's decision authority are the **same missing person**;
  satisfying one does not satisfy the other, but neither can be satisfied while that role is
  unfilled.
- **Gate 4 is partly independent and partly downstream.** Its baseline and regression half stands on
  its own and is in good order today. Its comparison half depends on Gate 3 to say what a meaningful
  comparison would even measure.
- **Gates 3 and 4 are the only gates that further engineering evidence can advance**, and neither can
  reach *satisfied* alone.

**Independent technical evidence cannot replace the product identity decision.** A complete Gate 3
classification, a fresh 18/18 baseline, green regression suites on both families and comparable
representative outputs would — together — still leave Gate 1 exactly where it is. That is by design:
Gate 1's output is a decision about what the product means by a finding, and no measurement produces
it.

---

## 11 · Reconsideration evidence package

The complete package that a future reconsideration checkpoint would need. **This is a list of what
would be required, not a schedule, a plan, or an authorization to produce any of it.**

**A · Ownership and authority (Gate 5, and Gate 1's authority)**

1. Named product decision owner for identity semantics.
2. Named implementation owner for convergence work.
3. Approved migration boundary, path-explicit.
4. Compatibility and deprecation policy across both families.
5. Rollback criteria — observation, decider, restoration method.
6. Protected-path approval process named as applying to convergence work.
7. Dated confirmation that the matrix path remains supported until a later approved decision.

**B · The product identity decision (Gate 1)**

8. Written, approved duplicate and cross-category semantics for a converged identity.
9. Provenance and cell-membership treatment under that identity.
10. Worked examples: one entity in multiple cells of one category; one entity across categories; one
    entity whose canonical URL and matrix `name` key disagree — with resulting finding counts.

**C · The mapping (Gate 2)**

11. Field-by-field mapping across inputs, manifests, entities, ledgers, rejection evidence,
    provenance and lifecycle states.
12. Artifact-by-artifact mapping, with explicit absences named as absences.
13. Per-field disposition: preserved, derived, dropped-by-decision, or blocking.
14. Schema and version compatibility strategy, including a formal contract for the matrix artifacts
    that currently have none.
15. Per similarly named artifact pair, an explicit same-contract / different-contract finding, with
    E9-20 applied.

**D · The operational classification (Gate 3)**

16. Every material difference classified equivalent / intentionally different / blocking, across all
    ten named dimensions.
17. Bounded concurrency: CF-1 resolved with a comparable path, or the dimension recorded as
    unclassifiable.
18. Determinism: a stated whole-run matrix determinism contract, or an explicit record that none
    exists.
19. For the six dimensions the offline regression wrapper does not reach: **live** matrix
    operational evidence, plus any separately required **production-state** matrix operational
    evidence — each under its own separate approval.

**E · Baselines and comparison (Gate 4)**

20. At least one **representative** matrix output: a retained corpus from a **live** matrix run,
    plus any separately required **production-state** matrix evidence — two distinct items, each
    under its own separately approved boundary. The stable, byte-pinned, independently validated
    matrix baseline already exists; the representative corpus does not.
21. A taxonomy baseline that is **not** the retained Stage 9 root.
22. A fresh 18/18 protected-baseline verification at the reconsideration boundary.
23. Current authoritative regression evidence for both families.
24. Documented known differences, data-loss risks and rollback constraints.
25. An explicit record that no unified implementation or migration experiment was performed to
    satisfy any gate.

**Two standing constraints on the package itself.** Nothing in it may be produced by building a
unified implementation or running a migration experiment `[plan §4 Gate 4]`, and nothing in it may
mutate the retained Stage 9 evidence root `[report §7.5]`. A package assembled in violation of either
constraint does not satisfy the gates it appears to satisfy.

---

## 12 · Decision and successor boundary

```text
Matrix unification is DEFERRED.
  The gate assessment does not prove otherwise: three gates UNMET,
  two PARTIALLY EVIDENCED, none SATISFIED.

The matrix path is NOT DEPRECATED.
  It remains supported. Deferral is not deprecation and must never
  be recorded, summarized or cited as deprecation.

NO CODE CHANGE IS AUTHORIZED by this note.
  No production, script, schema, configuration, test, fixture or
  artifact change. This note authorizes no protected-path change.

FUTURE RECONSIDERATION requires a separate approved PRODUCT decision.
  Assembling the §11 evidence package does not itself authorize
  reconsideration, and this note does not schedule its assembly.

FUTURE IMPLEMENTATION requires ANOTHER separate approved checkpoint.
  Satisfying all five gates would authorize only a reconsideration.
  Reconsideration would not authorize implementation.
```

Three boundaries, and none of them collapses into the next: **evidence → reconsideration →
implementation.** Each needs its own approval by name with its own exact allowed-path set. A
completed gate assessment, a green gate and a closed stage do not — separately or together —
authorize the next step `[plan §6]`.

**S10-2 defines no new gate and weakens no existing gate.** The five gates and the ratified
definition of matrix unification are exactly as authored at S10-0; this note assessed them and
changed neither.

---

## 13 · Milestones and non-claims

```text
M5                     UNOPENED
M6                     NOT STARTED
M7                     NOT STARTED
publication            ZERO   (0 of 16 expected stable published JSON files)
promotion              ZERO   (no promotion code exists in any form)
website consumption    ZERO   (unowned, outside this repository)
```

**This note does NOT claim:**

```text
matrix unification                    matrix-path deprecation
approval to reconsider unification    any gate satisfied
production readiness                  a reviewed production candidate
publication eligibility               promotion or published JSON
website integration                   recurring refresh
M5, M6 or M7 progress of any kind     resolution of any carried-forward item
```

**What this note did not do, stated positively.** It ran no validation, no test wrapper, no full
gate, no protected-baseline verifier, no harvest command, no network request and no read of the
retained Stage 9 evidence root beyond citing its recorded identity. Every figure quoted from a prior
verification — 18/18, 63/63, 2,386 tests, the retained-root counts — is **cited historical
evidence**, never a fresh measurement taken here.

**Retained Stage 9 evidence root**, unchanged and restated:

```text
C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4_stage9_retained
3 runs · 99 regular files · 54 directories
LATEST_RUN_ID  20260801T085829Z-40852
Disposition    RETAIN UNCHANGED through Stage 10 and until a separately
               approved disposition checkpoint. Stage 10 does not discharge it.
```

**Stage 10 status at the close of this note's drafting boundary.** S10-0 and S10-1 are complete and
published; the S10-2 convergence-note drafting boundary is complete; **the S10-2 checkpoint as a
whole is incomplete** — formal L0 validation and the atomic commit are separate required boundaries,
whose outcomes this note does not assert in either direction. **S10-C is unapproved and Stage 10 is
not closed.**

---

## 14 · Open limitations

Carried forward, **none of them resolved by this note.** Recording a limitation closes nothing; each
would need its own approved checkpoint by name.

**Limitations this note's subject owns:**

```text
matrix identity fork ........ OPEN. Gated by the five S10-0 gates, and gating is
                              not resolution.
no representative matrix .... No committed, current-working-tree, or baseline-
corpus                        recorded state/matrix/ corpus exists. TWO SEPARATE
                              ABSENCES follow (§3.2 classes 5 and 6): no LIVE matrix
                              run is recorded, and no PRODUCTION-STATE matrix run is
                              recorded. The real scripts DO produce temporary
                              artifacts under the isolated roots of
                              tests/test_matrix_harvest.sh with a mocked Claude
                              backend; those are class-1 test output, discarded with
                              their roots, and are neither live, production-state nor
                              a comparison corpus. This note authorizes no run that
                              would produce one.
no live matrix behaviour .... Offline mock-driven behaviour IS observed by that
                              wrapper (concurrency and MAX_PARALLEL, lane locking,
                              per-cell write isolation, merge folding, cross-cell
                              distinctness, idempotence, refusal semantics). LIVE
                              behaviour is not observed, and PRODUCTION-STATE
                              behaviour is separately not observed; six of the ten
                              Gate 3 dimensions remain code readings.
no taxonomy production- ..... The taxonomy family HAS three retained bounded LIVE
state corpus                  runs against real sources, but they used an explicitly
                              supplied external retained state root, not
                              state/taxonomy_harvest/. Taxonomy production-state
                              output is NONE, and the live runs never become
                              production-state evidence by being retained.
no matrix JSON Schema ....... all 13 committed schemas are taxonomy schemas.
                              One side of any future mapping has no formal contract.
two ledger schemas .......... coexisting indefinitely: raw source_url vs
                              canonicalized identity_url.
positional cell identity .... category#i_topic#j depends on list order as typed;
                              reordering the input lists renames every cell.
CF-1 ........................ unlocked pool paths deferred; the taxonomy driver is
                              deliberately sequential and a concurrent path cannot
                              be built before CF-1 is fixed.
inventory §3.2 pool row ..... names scripts/harvest/run_topics.sh, which does not
                              exist (§4.4). Corrected here, not repaired.
```

**Limitations carried forward from Stage 9 and recorded in the report §13 and the plan §9** — listed
so that this note does not appear to have closed any of them, and **not** re-derived here:

```text
editorial thresholds provisional            the 12/5 caps provisional and not
                                            fully attributable
S9-5C3 explicitly deferred                  run-1 rejection reasons unrecoverable
no production `harvest` command             smoke-model and refresh absent
M5 review artifact undefined                promotion implementation absent
website integration unowned                 domain-throttle signatures unresolved
changed-mode routing misses                 per-record fetch accounting not
tests/harvest/*.py                          retained
cli.py CliError comment stale (G18)         508 untracked baseline out of scope (G17)
retained Stage 9 root pending its own disposition checkpoint
```

The convergence note carries only the matrix identity fork as its own subject; the remainder are
listed because they remain open, not because this note addresses them `[plan §9]`.

---

*Observed 2026-08-04. Repository entry state for this note's drafting boundary: `HEAD = local main =
local origin/main = b3b7ad92994148b7ccde18827ac9cef3cfc4dc5b`, 0 behind / 0 ahead, tracked worktree
clean and index empty before editing `[obs]`. A dated observation, not an enduring claim.*
