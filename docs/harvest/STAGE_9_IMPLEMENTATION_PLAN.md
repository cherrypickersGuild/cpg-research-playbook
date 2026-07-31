# Stage 9 — bounded live validation: plan of record

```text
Status                    PROPOSED — S9-0, S9-1, S9-2 AND S9-3 APPROVED AND COMPLETE
                          S9-L1 remains MANDATORY and UNAPPROVED (E9-7 reorders it
                          after S9-3/S9-4; it still gates S9-L2)
                          S9-4 and every later checkpoint remain UNAPPROVED
Plan baseline             2bbc236a43bf76dc4aa241c8384911d8e5fda6dd
                          docs(harvest): correct roadmap stage percentage
S9-0 published at         720f114c6c3a840ab790935a2faaecec5762edd5
                          docs(harvest): plan stage 9 live validation
Next product milestone    M2 — the first real staged taxonomy dataset, UNMET
Live requests to date     ZERO. No live command is operational
Roadmap authority         docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md
Prior stage authority     docs/harvest/handoffs/HANDOFF_STAGE_8_COMPLETE_2026-07-31.md
```

## 0 · Errata

Recorded against this plan as implementation met it. Each corrects the plan; none widens a
checkpoint, and none is authorization for anything.

### E9-1 — wrapper accounting is per checkpoint, not per stage

The S9-1 validation row originally asked for a **63**-wrapper inventory. 63 is the **planned final**
Stage 9 count, reachable only once all five planned wrappers exist. Per checkpoint:

```text
before S9-1     58 wrappers   19 legacy + 39 taxonomy   ISOLATED[] 58
S9-1 adds     +  1            tests/test_taxonomy_cli.sh, and nothing else
after S9-1      59 wrappers   19 legacy + 40 taxonomy   ISOLATED[] 59
...
planned final   63 wrappers   after S9-2, S9-3, S9-4 and S9-6 each add their own
```

**No placeholder wrapper was created, and no route names a wrapper that does not exist**, to make an
inventory hit a number. A checkpoint's inventory proof asserts the count that checkpoint actually
produces.

### E9-2 — `--state-root` is required of state-bearing commands, not of all of them

D9-A §3.2 said "`--state-root` is required for every Stage 9 live execution", which over-reaches
against §6.1's own `preflight-sources` contract. The corrected rule:

- **Required** by every command that reads or writes a retained Stage 9 run — `smoke`, `validate`,
  `compare-runs`, `diff`, `linkcheck`.
- **`preflight-sources` is the deliberate exception**: it creates no run, reads no retained run,
  writes no state, and uses a temporary lease root removed when it exits. Requiring a retained root
  of a command that cannot use one would be an ignored option, which §6.1 already refuses on the
  committed `migrate.sh` precedent.

**The external retained-root decision is not weakened for any state-bearing command**, and D9-A's
other requirements stand unchanged. S9-1 selected no external root.

### E9-4 — S9-2 wrapper accounting and CLI routing

Wrapper accounting is **per checkpoint**, as E9-1 established:

```text
before S9-2     59 wrappers   19 legacy + 40 taxonomy   ISOLATED[] 59
S9-2 adds     +  1            tests/test_taxonomy_preflight.sh, and nothing else
after S9-2      60 wrappers   19 legacy + 41 taxonomy   ISOLATED[] 60
planned final   63            after S9-3, S9-4 and S9-6 each add their own
```

**The cumulative routing table in §5 omitted the preflight wrapper from the
`src/harvest/cli.py` arm. That is a plan defect, corrected here**: because S9-2
modifies `cli.py` to register the command, that arm must run **both**
`tests/test_taxonomy_cli.sh` and `tests/test_taxonomy_preflight.sh`. No future
nonexistent wrapper is routed.

### E9-5 — "no retained state", not "no temporary byte anywhere"

§6.1 said `preflight-sources` "creates and writes nothing, anywhere", which
over-claims against the committed HTTP stack: `HttpClient` coordinates through a
filesystem lease tree. The corrected contract:

- creates **no taxonomy run**;
- writes **no** cell, topic, ledger, rejection, coverage, conflict, manifest or
  pointer;
- requires and accepts **no `--state-root`**;
- writes **nothing inside the repository**;
- **retains nothing** after exit;
- **may** use one internally owned temporary lease root **outside** the
  repository;
- **removes** that root on success, on ordinary failure, and on interruption;
- never deletes a caller-owned or unrelated path.

The transient lease root is **infrastructure scratch, not a retained Stage 9
state root**. D9-A's external-root requirement is unweakened for every
state-bearing command; `preflight-sources` is the deliberate exception E9-2
already carved out.

### E9-6 — the exact stdout document shape

§6.1 left the top level unspecified. Resolved as the **minimum** contract:

- stdout is **one JSON array**;
- each item is exactly one committed `run_manifest.v1.json`
  `source_preflight[]` row;
- rows sorted by `source_id`;
- **no envelope** — no wrapper object, no `count`, no timestamp, no schema
  version, no second source-row schema;
- serialized by `artifacts.serialize`, never hand-assembled;
- stdout carries **JSON only**; usage and diagnostics go to stderr.

The array is therefore **directly reusable as a future manifest's
`source_preflight` value**, with no translation and no second schema to keep in
step.

### E9-7 — offline-first checkpoint order

S9-3's entry condition originally required a completed S9-L1 review. **Corrected:
S9-3 may begin once S9-2 is complete and S9-3 is separately approved.** S9-L1
remains a **mandatory operational gate** and may occur after S9-3 or S9-4, but it
**must be completed and reviewed before**: the authoritative pre-live full gate is
treated as sufficient for S9-L2 · S9-L2 receives checkpoint approval · any real
smoke command is executed. **No offline implementation checkpoint authorizes
S9-L1.**

This ordering was chosen deliberately, so that all safety-critical offline
construction — bounds, budgets, refusals, and the validator that can tell whether
a run is sound — is finished and reviewable **before** the first outbound request,
rather than being written under the pressure of already-live evidence.

### E9-8 — the validator needs a production owner

The original S9-3 path table assigned `validate --run-id` but named no module that
could own run-tree reading and cross-document checking. Without one those
responsibilities land in the CLI, which parses and renders, or in `run_cells.py`,
which writes — and the thing that writes should not also be the thing that judges
what was written. **`src/harvest/runvalidate.py` is added as the read-only owner:**

```text
cli.py          parses and renders
run_cells.py    writes
runvalidate.py  validates an existing tree
```

It reads, schema-checks, cross-checks and reports. It does **not** write, fetch,
classify, score, rebuild, repair, normalize or promote.

### E9-9 — anticipated spent guards

Two committed test paths were included in S9-3's declared set from the start,
because the checkpoint necessarily falsifies assertions in them:
`tests/harvest/test_run_cells.py`, whose E9-3 guard asserts `bounds` is absent
until S9-3; and `tests/harvest/test_preflight.py`, whose S9-2 snapshots assert
only `preflight-sources` is operational and that the whole of `cli.py` never calls
`run_cells.run()`. **Correcting a guard in the checkpoint that makes it false is
not scope drift** — see §7.3a for the one this erratum missed.

### E9-10 — S9-3 wrapper accounting

```text
before S9-3             60
S9-3 adds              + 1   tests/test_taxonomy_smoke.sh
after S9-3              61   19 legacy + 42 taxonomy
planned Stage 9 final   63   after S9-6
```

`63` remains the post-S9-6 inventory, never an S9-3 result.

### E9-11 — 43-path accounting across multiple runs

A fresh state root holding **one** complete run has **42 JSON documents + one
`LATEST_RUN_ID` = 43 files**. Those 42 decompose into two very different halves:

```text
18  SELECTED-RUN, under runs/<run-id>/
    12 cell artifacts · 3 topic artifacts · coverage · alias_conflicts · manifest
24  CROSS-RUN, shared and updated in place, never duplicated per run
    12 ledgers · 12 rejection logs
```

**A second run does not make 84 JSON documents.** It adds 18 under its own run
directory and updates the same 24. `validate --run-id` therefore enforces the 18
exactly and the 24 exactly, checks the pointer, **permits** other complete
historical run directories, rejects unexpected files inside the selected run or
the shared directories, and rejects `.tmp_*` debris anywhere under the root. For a
fresh one-run root the total is still exactly 43.

### E9-12 — the explicit run-id seam

`smoke [--run-id ID]` needs a production seam the cumulative `run()` signature
omitted. **One omission-compatible keyword-only `run_id_value=None` is added.**
Omitted, the committed clock-derived id is unchanged. Supplied, it is validated
against the **committed manifest schema pattern** — read from the schema, never a
second regex — refused before any artifact write when invalid, refused before the
integrated preflight when it already names a finished run, and passed unchanged to
every artifact and pointer owner.

### E9-13 — S9-4 scope is NINE paths, because two registry snapshots were spent

S9-4 was approved with an eight-path set. A read-only scan before editing found a **second** spent
S9-3 registry census outside it, and the checkpoint stopped and reported rather than widening itself.

Two committed snapshots asserted that `compare-runs` and `diff` must remain **planned**, and both
became false the moment S9-4 registered them:

```text
tests/harvest/test_cli.py     `for name in ("compare-runs", "diff", "linkcheck"): assertIn(name, planned)`
tests/harvest/test_smoke.py   test_compare_diff_and_linkcheck_remain_unimplemented   (the one outside the eight)
```

Both were **retired, not weakened**: the spent membership assertion was deleted, no replacement
census was written, and **no guard that `linkcheck` must remain planned** was added — that would be
the same mistake with a smaller number. The **durable registry-partition invariants remain intact**
in both files: implemented and planned stay disjoint, their union stays the exact six-command
surface, and every registered handler stays callable. `tests/harvest/test_compare.py` now owns the
durable fact that `compare-runs` and `diff` are registered and operational.

**Final approved S9-4 path set — nine:** `src/harvest/compare.py` (new) · `src/harvest/cli.py` ·
`tests/harvest/test_compare.py` (new) · `tests/test_taxonomy_compare.sh` (new) ·
`tests/harvest/test_cli.py` · `tests/harvest/test_smoke.py` · `scripts/validate_task.sh` · this plan ·
`TODO.md`.

This is the **third** consecutive checkpoint to hit E9-9's anticipated spent-guard problem (S9-1,
S9-2, now S9-4). The lesson stands: a checkpoint census written into a suite that does not own the
registry will be spent by the next checkpoint.

### E9-14 — `--normalize` is REMOVED, not deferred

§6.4 offered `compare-runs [--normalize]` and never settled what it would fold. **The option is
removed from the plan and was not implemented.** Comparison always enumerates and classifies the
actual differing JSON paths.

The reason is the committed S5-7/S6-7 rule: **a normalizer forgives every field it was not told
about**, so the day a sixth field starts moving it passes silently. There is therefore no
timestamp-name pattern, no wildcard deletion, no recursive "ignore these key names everywhere" and no
unknown-field normalization anywhere in `compare.py`.

Its replacement is a **three-class partition** in which every difference lands in exactly one section:

```text
permitted_changes     clock-derived, ENUMERATED EXACTLY (9 fields, below)
content_changes       legitimate editorial/content movement
invariant_violations  identity/idempotency breaches AND unclassified fields
```

The permitted set is the §6.4 contract **restricted to fields that actually occur in the 18
selected-run documents**: `harvest_run_id` · `generated_at` · `discovered_at` · `freshness_score` ·
`last_checked_at` · `started_at` · `finished_at` · `observed_at` · `detected_at`. The plan's
`rejected_at` and the ledger's four are deliberately **absent** — they live in the 24 shared
documents, which are not compared, so permitting them would permit movement nowhere real.

`content_changes` is **derived from the committed schemas**, not hand-typed: every property name the
six selected-run schemas declare, minus the permitted and invariant classes. The consequence is the
point — **a field present on disk but in no committed schema belongs to no class and is reported as
`unclassified_field`, an invariant violation.** An unenumerated moving field fails loudly instead of
disappearing.

### E9-15 — historical comparison covers the 18 SELECTED-RUN documents only

`compare-runs` compares the **18 selected-run documents** under each `runs/<run-id>/` — 12 cell
artifacts, 3 topic artifacts, coverage, alias conflicts, manifest.

**The 24 shared documents (12 ledgers, 12 rejection logs) are NOT compared, and must never be
presented as historical A/B snapshots.** By E9-11 they are updated **in place** and are not
per-run snapshots, so no historical pair exists to compare; reading today's copy twice and calling it
a comparison of two runs would be a fabricated result. The report states the exclusion as a number
and a sentence rather than as an empty section.

**Both runs may be historical.** `runvalidate.validate_run()` is **not weakened, not called and not
consulted** for pointer agreement: it still requires its run to be the one `LATEST_RUN_ID` names,
because it answers "is the run this root points at sound?". S9-4 owns a separate historical-run
reader, and a test asserts the `validate` contract still holds.

### E9-16 — within-run versus between-run metadata counts

§6.4 listed "every metadata count" as an identity invariant while §6.4's own content class listed a
changed count as reportable. Resolved as two different questions:

```text
WITHIN one run    metadata counts MUST agree with that run's own records   -> invariant violation
BETWEEN runs      a count that CHANGED is a content change                 -> reported, not a failure
```

Two live runs minutes apart legitimately see different feed windows, so a differing `total_records`
between them is evidence of the corpus moving, not of identity breaking. A count that disagrees with
the records **beside it** is a broken document either way. The intra-run half **reuses the committed
`runvalidate` count check** rather than restating it, so "a count agrees with its records" has
exactly one definition in the tree.

### E9-17 — S9-4 wrapper accounting and the corrected gate sequence

```text
before S9-4             61   19 legacy + 42 taxonomy
S9-4 adds              + 1   tests/test_taxonomy_compare.sh
after S9-4              62   19 legacy + 43 taxonomy
planned Stage 9 final   63   after S9-6
```

**62 is an inventory, not a gate result.** The corrected sequence:

| When | Gate | Expects |
|---|---|---|
| S9-4 itself | **Focused validation only** — the three owned suites plus explicit-mode harness routing | no `--all` |
| after S9-4 review, before S9-L2 | the **authoritative** `bash scripts/validate_task.sh --all`, separately approved | **62/62**, each exactly once, zero `WARN - skipping`, exit 0 |
| S9-6 | adds the final wrapper | inventory becomes 63 |
| before S9-L4 | a **new** authoritative full gate | **63/63** |

§8.2's single authoritative `--all` therefore expects **62/62**, not 63/63: it runs at the final code
baseline before the first live smoke, which is after S9-4 and before S9-6. The 63/63 run is a
**second** authoritative gate, owed before S9-L4.

### E9-3 — the D9-B signature is cumulative across checkpoints

§4.3's target signature describes Stage 9 **at its end**, not S9-1. S9-1 implements the `transport`,
`mode`, `enrich` and `source_preflight` seams and **does not implement, claim or accept smoke
bounds**. `bounds` arrives in **S9-3, atomically with its enforcement**, because a parameter accepted
and ignored would let a manifest report a cap that never bound anything — the same honesty S6-5
established for `config.enrich`. A test asserts `bounds` is absent from `run()` at S9-1.

**Writing this plan, and committing it, approved no implementation and no live command.** S9-0 was
the only approved checkpoint when it was written; **S9-1, S9-2, S9-3 and S9-4 have since each been
separately approved by name, implemented and completed, and the operational checkpoint S9-L1 has
been approved, executed exactly once and completed** (§7). **S9-L2 and every later checkpoint remain
unapproved**; nothing else below is scheduled. `preflight-sources`, `smoke`, `validate`,
`compare-runs` and `diff` are implemented; **only `preflight-sources` has ever been pointed at a real
source**, once, at S9-L1.

**Every later checkpoint requires its own separate approval by name, with its exact allowed-path set
declared up front.** If a path outside that set turns out to be required, the checkpoint stops and
reports rather than widening scope. This is the rule that has held since Stage 4's closeout and it is
not relaxed here.

**The existence of this file does not open Stage 9.** A completed checkpoint, a green gate, and a
pushed stage do not — separately or together — authorize the next one.

---

## 1 · What Stage 9 is

Stage 9 is the bounded transition from

> a **fixture-only, temporary-root-proven** pipeline

to

> **real-source, retained-but-not-published staged taxonomy runs**, with repeatability evidence, a
> live-corpus calibration decision, and bounded link-health evidence.

Stage 9 ends **no further than approximately M4** on the roadmap's milestone map.

### 1.1 Stage 9 does NOT own

| Not Stage 9 | Owner |
|---|---|
| A publication-eligible production run | M5, unopened |
| Production enrichment of the full corpus | M5, unopened |
| Human review workflow (artifact, schema, acceptance criteria) | M5b, unopened — roadmap G9 |
| Promotion implementation | M6, unopened — roadmap G7 |
| Real `data/harvested/` publication | M6, unopened |
| Website / consumer integration | M7a, unopened — roadmap G10 |
| Recurring refresh operation | M7b, unopened — roadmap G6 |
| Matrix convergence | Out of scope, `CONVERGENCE_NOTE.md` gates |
| Entity-registry migration (1,161 assessed, 0 migrated) | Open product decision |
| `smoke-model` | Opt-in, separately opened if ever — its `model_search` adapter raises `AdapterNotImplemented` |
| Stage 10 final report | Stage 10, unopened |

### 1.2 The sentence that must not be softened

**A Stage 9 smoke is not a production candidate and cannot be promoted.**

This is not merely policy — it is already a *derived* property of committed code. `smoke` is one of
the five non-`harvest` values in `run_manifest.v1.json`'s `mode` enum, and
`artifacts.derive_publication_eligibility` refuses every non-`harvest` mode
(`tests/harvest/test_eligibility.py:262` loops all five and asserts refusal;
`test_manifest.py:211-213` asserts the ineligibility reason names the smoke). A Stage 9 run is
therefore `publication_eligible: false` **by derivation, not by convention**, and Stage 9 adds no
predicate to change that.

`IMPLEMENTATION_PLAN.md` §7.1 independently rejects `"initial deterministic smoke"` **by name** as a
promotion reason. Both statements stand.

---

## 2 · Audit findings that shape this plan

Read-only source inspection at `2bbc236a`. **No module was imported, no test run, no checker
executed, no source contacted.** Committed code and executable tests outrank master-plan syntax.

### 2.1 What does NOT exist (the real Stage 9 workload)

| Named in the master plan | Occurrences in `src/`, `scripts/`, `schemas/`, `config/`, `tests/` |
|---|---|
| `scripts/harvest/harvest.sh` | **File does not exist.** `scripts/harvest/` holds only `check_config.py`, `check_facets.py`, `check_fixtures.py`, `gen_facet_schema.py`, `gen_protected_baseline.sh`, `hash_tree.py`, `migrate.sh`, `protected_baseline.py`, `verify_protected_baseline.sh` |
| `preflight-sources` | **Zero** as a command |
| `compare-runs` / `compare_runs` | **Zero, anywhere** |
| `diff --run-id` | **Zero** as a command |
| `linkcheck` | Only a `mode` enum value + prose |
| `refresh` | Only a `mode` enum value + prose. (`scripts/refresh.sh` is the **legacy AX deck pipeline** — unrelated; roadmap G6) |
| `smoke` | Only a `mode` enum value + a `policy.v1.json` block + `smoke_budget_sec` |
| `smoke-model` / `smoke_model` | Only a `mode` enum value |
| Any CLI reaching `run_cells.run()` | **None.** `src/harvest/run_cells.py` has no `__main__`, no `argparse`; no shell script invokes it |

### 2.2 What DOES exist, and materially shrinks Stage 9

These are the load-bearing discoveries. Stage 9 is smaller than the roadmap's §4.1 estimate implied
in several places, because much of the machinery is already committed and merely **unreachable**.

1. **The real transport is already the library default.**
   `httpclient.default_opener(req, timeout=20)` exists (`httpclient.py:421`) and performs a genuine
   non-redirect-following request. `HttpClient.__init__(self, policy, lease_root,
   opener=default_opener, clock=time.time, sleep=time.sleep, monotonic=time.monotonic, …)` already
   **defaults to live**. Live transport is therefore not new code — it is a parameter the driver
   currently overrides.

2. **The driver is what forces offline, in exactly two places.**
   `run_cells.run()` builds `fixtures_mod.FixtureOpener(...)` unconditionally at `run_cells.py:794-806`
   and passes `sleep=lambda seconds: None` at `:818`. There is no opener parameter, no mode switch,
   no live branch. **That, and only that, is why no request can leave the machine.**

3. **`HttpClient.preflight()` already exists and already returns the manifest row shape.**
   `httpclient.py:745` — "Returns a dict shaped for `run_manifest.source_preflight[]`. Availability
   is re-checked on every live run because planning-time success is informational only." It never
   raises; it maps `HttpError` to `adapter_error` / `infrastructure_error`, records
   `robots_allowed`, `crawl_delay_sec`, `http_status`, `content_type`, `bytes`, `elapsed_ms`.
   **`preflight-sources` is assembly and a CLI, not new probing logic.**
   One gap: `preflight()` returns `url` but **not** `source_id`, which
   `run_manifest.v1.json` lists as **required** on every `source_preflight[]` row. The caller stamps
   it — from the configuration, never from the probe.

4. **`source_preflight` is already a REQUIRED manifest field.**
   `run_manifest.v1.json` `required` = `[schema_version, harvest_run_id, mode, started_at,
   finished_at, environment, config, cells, source_preflight, classification_decisions,
   publication_eligible]`, and `artifacts.build_run_manifest(…, source_preflight=())` already
   accepts and sorts rows. Today's fixture runs write `[]`. A Stage 9 smoke must populate **25** rows.

5. **`link_history` already exists end to end in the record contract.**
   `record.v1.json` `$defs.link_history_entry` (`checked_at` + `access_status` required; optional
   `http_status`, `final_url`, `content_hash`, `changed_materially`, `note`), described as
   "Link-check never deletes a record; it appends here. This is the retained history."
   `records.make_full_record(…, link_history=None)` already accepts and projects it
   (`records.py:197, 276-277`). **Linkcheck's data shape is committed; its producer is not.**

6. **`config.enrich` is already an honest, required, threaded field** — `_config_block(cells,
   max_cells, *, enrich)` is keyword-only and required precisely so a caller cannot silently
   re-acquire a dishonest default (S6-5). `run()` currently binds `enrich = True` unconditionally at
   `run_cells.py:828`. The `false` branch is proved **at the `_config_block` boundary** but has never
   been proved **end to end**.

7. **The smoke bounds are configured and enforced by nothing.**
   `policy.v1.json` `smoke` = `{max_candidates_per_cell: 12, max_accepted_per_cell: 5, enrich:
   false}`. Repository-wide search: **zero consumers.** `smoke_budget_sec` (1800) is read into
   `budget.from_policy`'s dict (`budget.py:165`) and no scope opens it. Stage 9 must implement
   enforcement; it must not assume it exists.

8. **`config.bounds` already reports every cap the run enforced** — `{max_cells,
   max_target_fetches_per_cell}` (S6-6). New Stage 9 caps go here, so a capped run is visible in the
   manifest rather than only in the code.

### 2.3 Harness inventory

```text
tests/*.sh committed                58
tests/test_taxonomy_*.sh            39
ISOLATED[] entries                  58  (19 legacy + 39 taxonomy, legacy verbatim as a prefix)
```

**Any new `tests/test_*.sh` is discovered by `--all` and silently `WARN - skipping` unless it is
added to `ISOLATED[]`.** Stage 8's zero-skip acceptance is what makes that failure mode invisible
rather than loud. §5 below therefore plans every wrapper and its harness wiring in the **same**
checkpoint that creates it.

---

## 3 · D9-A — the Stage 9 runtime root · **RESOLVED**

This is a blocking design decision and is settled here, not left implicit.

### 3.1 The conflict

| Fact | Source |
|---|---|
| Every repository checkpoint requires `state/taxonomy_harvest/` to be **absent** | Stage 5-8 closure conditions; project memory |
| `scripts/validate_task.sh` **fails the run** if any of the four runtime paths exists, checked before **and** after, and never deletes what it finds | `validate_task.sh:250` `RUNTIME_PATHS=(state/taxonomy_harvest data/harvested runs LATEST_RUN_ID)` |
| 33 of 39 taxonomy wrappers additionally assert production `state/` is unmodified | CF-6, Stage 8 handoff §9.2 |
| Stage 9 must **retain** real live JSON long enough to validate, compare, review and link-check it | This plan §1 |

Writing the first live output into the repository default root would invalidate the clean-checkpoint
assumption and the Stage 8 harness guard simultaneously.

### 3.2 The decision

> **Stage 9 live executions use an explicitly supplied, retained external state root OUTSIDE the
> repository.**

Requirements, all binding:

- The path is **chosen and reported before the first live execution**, in the S9-L1 approval request.
- It is **not** a transient `mktemp` directory deleted at command exit.
- It is **not** under the repository, and not under any path git can see.
- It holds the real Stage 9 run tree and `LATEST_RUN_ID`.
- It **survives** first smoke → second smoke → comparison → calibration review → linkcheck.
- It is **never** presented as production publication.
- The four repository runtime paths remain **absent throughout Stage 9**, and every checkpoint
  re-asserts that.
- The Stage 9 completion handoff records the external root path **and its disposition**.
- **Automatic deletion is forbidden** without separate approval. A live run's output is evidence.

`--state-root` is therefore **required** for every Stage 9 live execution, exactly as `migrate.sh`
already requires it for `--apply` (and refuses it without `--apply`). The committed precedent and its
AST-scan enforcement (`tests/harvest/test_migration.py:2041`) are the model.

### 3.3 What this defers, and what it does not weaken

A live run against the **repository default root** (`state/taxonomy_harvest/`) is **deferred to the
later production-candidate milestone (M5)** and is not planned here. Should a future plan choose the
default root instead, it must **first** define a separate corrective checkpoint covering: harness
behaviour in the presence of retained runtime state · baseline semantics · checkpoint validation ·
runtime backup and recovery · cleanup ownership.

**The Stage 8 runtime guard is not weakened, narrowed, disabled, or made conditional by Stage 9.**
`RUNTIME_PATHS` keeps all four entries and keeps failing the run when any exists. Stage 9 satisfies
it by writing somewhere else, not by relaxing it.

---

## 4 · D9-B — live-run architecture · **RESOLVED**

The smallest architecture that reuses the committed pipeline without duplicating it.

### 4.1 The two new owners

| Layer | Path | Owns |
|---|---|---|
| **Shell** | `scripts/harvest/harvest.sh` | Dispatch **only**. `set -euo pipefail`, `"$@"` forwarded verbatim, no `eval`, no temp file, no network, no Git. Modelled byte-for-byte on the committed `migrate.sh` (68 lines) |
| **Python** | `src/harvest/cli.py` | Argument parsing, root resolution, transport construction, subcommand dispatch, deterministic report rendering |

**`cli.py` performs no pipeline judgement.** No classification, no scoring, no identity derivation,
no artifact assembly, no schema validation of its own. It composes committed modules and renders
their output. A test asserts by AST scan that `cli.py` imports no vocabulary and defines no second
matcher, canonicalizer or serializer — on the committed `test_migration.py` / `test_verify.py`
idiom.

**Shell code may not implement classification, scoring, identity, artifact assembly, or schema
validation.** `harvest.sh` is a dispatcher and nothing else.

### 4.2 D9-B1 — generalize `run_cells.run()`; do NOT extract a new engine

**Decision: generalize `run_cells.run()` with keyword-only, default-`None` parameters.**

Rationale, from the audit rather than from taste:

- At least six committed suites call `run_cells.run(root, clock=…)` directly
  (`test_run_cells.py`, `test_recovery.py`, `test_eligibility.py`, `test_target_ownership.py`,
  `test_target_determinism.py`, `test_target_evidence.py`). Extracting an engine moves all of them.
- The repository already has a **committed idiom** for exactly this: D6-A's keyword-only
  `url_aliases=None` on `make_full_record`, and S6-6A's `target_outcomes=None` sentinel — in both
  cases *"omission keeps the committed behaviour byte-for-byte, so every committed caller is
  byte-identically unaffected."* S9-1 repeats it.
- S5-6's suite asserts eleven composed modules are **byte-unchanged against HEAD**. An engine
  extraction would have to retire or rewrite those guards; a parameter addition does not.

**Rejected alternative:** extracting `src/harvest/engine.py`. It buys nothing Stage 9 needs and costs
six suites plus a byte-freeze guard set.

### 4.3 D9-B2 — one atomic transport seam

`run()` gains **one** transport parameter, not several, so it cannot be half-configured:

```text
run_cells.Transport            frozen dataclass: (opener, sleep, lease_root)
run_cells.FIXTURE_TRANSPORT    the committed behaviour, named

run(root, *, cells=None, clock=None, fixtures_dir=None, max_cells=MAX_CELLS,
    transport=None,          # None -> the committed fixture transport, byte-identically
    mode=None,               # None -> MODE_HARVEST
    enrich=None,             # None -> True (the committed binding at run_cells.py:828)
    bounds=None,             # None -> no additional caps
    source_preflight=None)   # None -> () , the committed empty manifest array
```

Why one object rather than three parameters: a live opener paired with the fixture's
`sleep=lambda s: None` would issue real requests **with pacing disabled**, against hosts that mandate
a crawl-delay. That combination must be unrepresentable, not merely discouraged. A single frozen
`Transport` makes it so, and S9-1 asserts the fixture and live constructors are the only two ways to
build one.

| Concern | Resolution |
|---|---|
| Fixture callers stay byte-compatible | `transport=None` reconstructs today's `FixtureOpener(sources=…, robots=…, targets=…)` and `sleep=lambda s: None` exactly. A test hashes a `transport=None` tree against a `transport` -omitted tree and requires byte identity |
| Live transport construction | `cli.py` builds `Transport(opener=httpclient.default_opener, sleep=time.sleep, lease_root=<state-root>/locks)` — the library default, not a new client |
| Real pacing restored | `sleep=time.sleep`. The crawl-delay is **already read and honoured** by every code path; today it simply has nothing to wait for. Live gives it something |
| Lease state location | `<state-root>/locks/` — the directory `IMPLEMENTATION_PLAN.md` §1 already names. `lease_root=None` keeps today's `tempfile.mkdtemp(prefix="harvest_leases_")` |
| `--state-root` required | Enforced in `cli.py` for every live subcommand, and asserted by an AST scan of the Stage 9 suites, on the `test_migration.py:2041` precedent |
| `--no-enrich` genuinely disables fetching | `enrich=False` skips the target-fetch phase **and** sets `config.enrich: false`. The two cannot disagree — S6-5 bound them to one variable, and S9-3 proves the `false` branch **end to end**, which no committed test does |
| Honest mode recording | `mode="smoke"` reaches the manifest. `publication_eligible` stays **derived** — a non-`harvest` mode is already refused by `derive_publication_eligibility`. **No new predicate** |
| Global bounds enforced | `bounds` carries `max_candidates_per_cell` / `max_accepted_per_cell` from `policy.v1.json` `smoke`, currently enforced by nothing (§2.2 item 7), and every enforced cap is echoed into `config.bounds` |
| Interruption / repeat refusal intact | Untouched. `run_is_finished` still refuses a finished `run_id` **before the first byte**, `WriteJournal` still sweeps only its own temp files, the pointer still moves last. S9-3 re-proves all three against a live-shaped tree |

---

## 5 · Harness reconciliation — exact wrapper plan

Stage 8 closed at **58 wrappers, zero skips**. Stage 9 adds **five**, each wired in the same
checkpoint that creates it.

| Wrapper | Test module | Created by | Localizes |
|---|---|---|---|
| `tests/test_taxonomy_cli.sh` | `tests/harvest/test_cli.py` | **S9-1** | Transport seam, `--state-root`, mode/enrich honesty, fixture byte-compatibility |
| `tests/test_taxonomy_preflight.sh` | `tests/harvest/test_preflight.py` | **S9-2** | Source-preflight rows, failure mapping, determinism |
| `tests/test_taxonomy_smoke.sh` | `tests/harvest/test_smoke.py` | **S9-3** | Bounds, 43-path accounting, `validate --run-id`, interruption/repeat |
| `tests/test_taxonomy_compare.sh` | `tests/harvest/test_compare.py` | **S9-4** | `compare-runs` invariants, `diff --run-id` |
| `tests/test_taxonomy_linkcheck.sh` | `tests/harvest/test_linkcheck.py` | **S9-6** | Sample determinism, `link_history`, base-run immutability |

```text
wrappers before Stage 9      58   (19 legacy + 39 taxonomy)
wrappers added by Stage 9   + 5
wrappers after Stage 9       63   (19 legacy + 44 taxonomy)

ISOLATED[] before            58 entries
ISOLATED[] after             63 entries   — five appended individually, the 58 preserved verbatim
```

**Five wrappers, not one.** A single aggregate wrapper would report "Stage 9 failed" and localize
nothing; the five map one-to-one onto the five code checkpoints, so a red wrapper names its owner.
This also matches the S8-1 decision that rejected an aggregate taxonomy wrapper.

**Exact `scripts/validate_task.sh` additions**, per checkpoint:

- `ISOLATED[]` — append the new wrapper basename (one line per checkpoint).
- Case-table routing, by **ownership**, not import fan-out, with no blanket arm:

| Changed path | Routes to |
|---|---|
| `src/harvest/cli.py` | `test_taxonomy_cli.sh`, `test_taxonomy_smoke.sh` |
| `scripts/harvest/harvest.sh` | `test_taxonomy_cli.sh` |
| `src/harvest/run_cells.py` | *(existing arm)* `test_taxonomy_run_cells.sh`, `test_taxonomy_recovery.sh` — **plus** `test_taxonomy_cli.sh`, `test_taxonomy_smoke.sh` |
| `src/harvest/preflight.py` *(if a module is added at S9-2)* | `test_taxonomy_preflight.sh` |
| `src/harvest/compare.py` *(S9-4)* | `test_taxonomy_compare.sh` |
| `src/harvest/linkcheck.py` *(S9-6)* | `test_taxonomy_linkcheck.sh` |

Rules preserved without exception: every target spelled **`tests/<name>.sh`** (which is what makes
`add_test` de-duplicate on the exact path string and gives **at-most-once execution**); every
`tests/*.sh` wrapper executes **exactly once** under `--all`; **zero `WARN - skipping`** remains the
acceptance condition; the 19 legacy arms stay byte-identical.

**Prohibited:** hiding Stage 9 tests under an existing unrelated wrapper to avoid touching the
harness; adding a wrapper without planning its wiring in the same or an earlier checkpoint; adding a
blanket fallback arm.

---

## 6 · Command contracts

### 6.1 `harvest.sh preflight-sources` — **NOT IMPLEMENTED** (S9-2)

```text
bash scripts/harvest/harvest.sh preflight-sources [--sources ID[,ID…]] [--timeout-sec N]
```

| Property | Contract |
|---|---|
| Network | **Yes** — live, bounded |
| State root | **Read-only with respect to it.** Creates and writes nothing, anywhere |
| Scope | One structured row per configured source (**25** when unrestricted) |
| Checks | URL validity · robots accessibility (`robots_allowed`, `crawl_delay_sec`) · HTTP status · content type · adapter reachability — all through the **existing** `HttpClient` policy, robots matcher, budget and pacing |
| Target pages | **Never fetched.** Preflight probes sources only |
| Output | One deterministic JSON document on **binary stdout**, rendered by the committed `artifacts.serialize` — no second serializer |
| Row shape | Exactly `run_manifest.v1.json` `source_preflight[]` items: `source_id` (**required**, stamped from configuration — never from the probe) · `result` (**required**, `ok` / `adapter_error` / `infrastructure_error`) · `url` · `reason` · `http_status` · `content_type` · `robots_allowed` · `crawl_delay_sec` · `bytes` · `elapsed_ms`. `additionalProperties: false` |
| Producer | `HttpClient.preflight()`, **unchanged**. S9-2 adds assembly, `source_id` stamping and the CLI |
| Artifacts | **None** — not in the repository, not in the state root |
| Failure rule | A failing source is **reported, never dropped**. Exit `0` when every row is `ok`; exit `1` when any row is not, **after printing the complete document** — the committed `migrate.sh` dry-run idiom |
| Relationship to smoke | `smoke` runs an equivalent preflight of its own and **persists the rows in its manifest**. A standalone preflight informs a human; it does not license a smoke |

### 6.2 `harvest.sh smoke` — **NOT IMPLEMENTED** (S9-3)

```text
bash scripts/harvest/harvest.sh smoke --state-root PATH [--no-enrich]
      [--max-candidates N] [--max-accepted N] [--run-id ID]
```

| Property | Contract |
|---|---|
| Cells | All **12** configured |
| Sources | Real, live discovery sources — `Transport(default_opener, time.sleep, <state-root>/locks)` |
| Enrichment | `--no-enrich` **is the Stage 9 default**, per `policy.v1.json` `smoke.enrich: false` and its recorded reason (arXiv's mandated 15 s crawl-delay makes enriching 12 candidates from that source alone cost ≥180 s, infeasible under `adapter_budget_sec`) |
| Bounds | `smoke.max_candidates_per_cell` = **12**, `smoke.max_accepted_per_cell` = **5**, `smoke_budget_sec` = **1800**, plus the committed `MAX_CELLS` = 12. **All currently enforced by nothing** (§2.2 item 7). Every enforced cap is echoed into `config.bounds` |
| State root | `--state-root` **required**; external and retained (D9-A). Absent ⇒ refuse, do not default |
| Output | **One retained complete run** — **42 JSON + 1 `LATEST_RUN_ID` pointer = 43 paths** when all 12 cells run (§6.1 of the roadmap) |
| Preflight | Rows persisted in `manifest.source_preflight[]` — a **required** field |
| Mode | `mode: "smoke"` |
| Publication | `publication_eligible: false`, **derived** from the non-`harvest` mode. No new predicate |
| Promotion | None. Not possible — no promotion code exists |
| Invocations | **Exactly one per live checkpoint. No automatic retry.** A failure is evidence |
| Exit | `0` on a complete published run; non-zero otherwise, with the pointer left naming the previous run (or absent). A partial run publishes **no manifest and no pointer** — the committed S5-7 behaviour |

### 6.3 `harvest.sh validate --run-id` — **NOT IMPLEMENTED** (S9-3)

```text
bash scripts/harvest/harvest.sh validate --state-root PATH --run-id ID
```

Offline. **No network request. Writes nothing, anywhere.** Reads one retained run and checks:

- the **exact** path set (43 paths for a full run; an extra path fails as loudly as a missing one);
- every document against its committed schema, via `schema.py` — whose `referencing` registry is
  local, so validation never touches the network;
- manifest ↔ pointer consistency (`verify_latest_run_id`);
- cell ↔ topic ↔ count consistency, including that `by_category` sums to `full_records` and that
  cross-references are counted separately;
- `alias_conflicts_count` agreeing with the validated conflict document;
- runtime-tree integrity: no `.tmp_*` debris, no unexpected file.

This is the command that turns "the smoke exited 0" into "the dataset is real". **It runs after every
live execution**, offline, in the same checkpoint.

### 6.4 `harvest.sh compare-runs` — **IMPLEMENTED** (S9-4)

```text
bash scripts/harvest/harvest.sh compare-runs --state-root PATH --run-id A --run-id B
```

> **As delivered, this section is amended by E9-14, E9-15 and E9-16.** `--normalize` was **removed
> and never implemented**; comparison covers the **18 selected-run documents only**, never the 24
> shared ones; and metadata counts are an invariant **within** a run and a content change **between**
> runs. The two field classes below stand as written, with the permitted list restricted to fields
> that actually occur in the selected-run documents.

Offline; both runs under the same external state root. Deterministic JSON on binary stdout via
`artifacts.serialize`. **No new runtime JSON** — Stage 9 establishes no schema and no lifecycle for a
comparison artifact, so it writes none.

Two field classes, kept strictly apart:

| Class | Members | Rule |
|---|---|---|
| **Permitted to move** — clock-derived | `harvest_run_id` · `generated_at` · `discovered_at` · `freshness_score` · `last_checked_at`; the manifest's `started_at`/`finished_at`; a rejection log's `rejected_at`; the ledger's four; an alias's `observed_at`; a conflict's `detected_at` | **Enumerated exactly**, never normalized away. The committed S5-7/S6-7 rule: a normalizer silently forgives every field it was not told about, so the day a sixth starts moving it passes |
| **Identity / idempotency invariants** | `record_id` · `content_id` · `identity_url` · `cell_id` · `canonical_url` · classification · facet payload · the other three scores · every metadata count | **Must be identical** for a record present in both runs. A difference is a failure, not a report |

Everything else — a record present in one run and not the other, a changed title, a changed count —
is a **reported content change**, emitted in `content_changes[]` (the committed
`IMPLEMENTATION_PLAN.md` §8 vocabulary) and **not** a failure: two live runs minutes apart legitimately
see different feed windows.

**No normalization may conceal an unapproved moving field.** Exit `0` when every invariant holds
(content changes present or not); non-zero when an invariant is violated or an unenumerated field
moved.

### 6.5 `harvest.sh diff --run-id` — **IMPLEMENTED** (S9-4) · contradiction resolved

**The contradiction:** `IMPLEMENTATION_PLAN.md` §14 and `TODO.md`'s Stage 6 heading both list a
`diff` subcommand (alongside `refresh`/`linkcheck`/`promote`/`compare-runs`); Stage 6's plan §14
erratum **E11 descoped all five**; and `TODO.md`'s Stage 9 block omits `diff` entirely. It has had no
owner since.

**Resolution: `diff --run-id` is assigned to Stage 9, at S9-4.** Dropping it silently would leave
Stage 9 unable to satisfy the master plan's acceptance commands 21-22, which exist precisely to prove
that live work did not touch the publication path.

```text
bash scripts/harvest/harvest.sh diff --state-root PATH --run-id ID
      [--publication-root DIR]     # default: data/harvested/
```

| Property | Contract |
|---|---|
| Network | **None** |
| Writes | **Nothing** |
| Compares | One staged run against the current publication root |
| Expected Stage 9 result | The real `data/harvested/` is **absent** — reported as such, exactly, not as an empty diff |
| Promotion | **Out of scope.** `diff` describes a difference; it cannot act on one |
| Output | Deterministic JSON on binary stdout |

An absent publication root is a **first-class, distinguishable answer**, not an error and not "no
changes".

**As delivered**, `diff` reports **four** distinguishable states — `absent`, `empty`, `differs`,
`identical` — and exits **0** once it has read, in every one of them: it describes a difference and
has no authority to act on one. The expected publication set is the **16 committed paths** of
ROADMAP §6.3 (12 category files + 3 topic aggregates + `publication_manifest.json`). Only the
**layout** is committed — no projection from a run to publication bytes exists anywhere in the tree —
so `diff` reports publication-side **paths** and **never fabricates content** for them, and a file
present on both sides is listed as present-and-not-compared rather than diffed against invented
bytes. Inventing a projection here would be writing the promotion S9-4 is forbidden to write. The
default publication root is the repository's `data/harvested/`, which `diff` **looks at and never
creates** — a test asserts it is still absent afterwards.

### 6.6 `harvest.sh linkcheck` — **NOT IMPLEMENTED** (S9-6)

```text
bash scripts/harvest/harvest.sh linkcheck --state-root PATH --run-id BASE --sample N
```

Every question the roadmap flagged as unspecified is settled here.

| Question | Decision |
|---|---|
| New run ID? | **Yes.** A linkcheck is a run: it gets its own `run_id` and its own `runs/<run_id>/` directory, with `mode: "linkcheck"` |
| Artifacts produced | The **same 43-path shape** as a harvest run. A linkcheck that produced a bespoke tree would need its own schema, its own validator and its own recovery semantics — three things Stage 9 does not have budget to design well |
| Cell/topic artifacts: copied, rebuilt, or referenced? | **Rebuilt from the base run's records, with `link_history` appended** — through the committed `records.make_full_record(link_history=…)` and the committed `artifacts.build_cell_artifact`. Not copied (a copy would drift), not referenced (a reference is not a validatable artifact) |
| `link_history[]` update | **Append-only.** One entry per checked record: `checked_at` + `access_status` (both required) plus `http_status`, `final_url`, `content_hash`, `changed_materially`, `note`. The committed schema description is binding: *"Link-check never deletes a record; it appends here."* |
| Sample determinism | The first `N` accepted full records of the base run in the committed `records.sort_key` order. **No RNG, no clock, no set iteration.** The same base run and the same `N` select the same records, always |
| Request cap | `--sample N`, default **20**; hard-capped by the committed per-cell `cell_max_requests` (60) and `MAX_TARGET_FETCHES_PER_CELL` (25), and echoed into `config.bounds`. arXiv's 15 s crawl-delay is honoured, which `policy.v1.json` explicitly frames as the point of the exercise |
| One fetch per canonical identity? | **Yes** — the committed S6-4 run-scoped ownership guarantee, reused unchanged. A URL shared by two records is fetched once and both owners see the same outcome object |
| `LATEST_RUN_ID` movement | **It moves**, to the linkcheck run, by the committed `publish_run` — pointer last, or not at all. The pointer means "newest complete run", not "newest harvest" |
| Base-run immutability | **Absolute.** The linkcheck writes only under its own `runs/<new_run_id>/` plus the cross-run `ledgers/`. A test hashes the base run's directory before and after and requires byte identity |
| Validation | Through the same `validate --run-id` as any other run — 43 paths, every schema, pointer consistency |
| Why it cannot delete a record | The schema says so (`link_history` is *"the retained history"`), and a link check measures **availability**, not **truth**. A 404 today does not unmake a case that existed |
| Why it is not promotion | `mode: "linkcheck"` is a non-`harvest` mode ⇒ `publication_eligible: false` by derivation; it writes under the external state root; and no promotion code exists |

### 6.7 Explicit exclusions — recorded as NOT Stage 9

`refresh` · `promote` · `smoke-model` · a production default-root run · any website-consumer change.

None of these is assigned to Stage 9. The roadmap's milestone boundary (M5/M6/M7) stands and this
plan does not argue with it.

---

## 7 · Checkpoint decomposition

Ten checkpoints. **Code checkpoints and operational network executions strictly alternate and are
never combined.** An approval to write a live command is never an approval to run it.

**Every live execution (`S9-L*`) requires explicit approval immediately before the outbound request,
in addition to its checkpoint approval.** That rule is not discharged by any earlier approval in this
plan.

### S9-0 — plan of record · **THIS CHECKPOINT**

| Field | Value |
|---|---|
| Purpose | Settle D9-A (runtime root), D9-B (architecture), every command contract, the wrapper plan, the exit criteria |
| Allowed paths | `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` (new) · `docs/harvest/TODO.md` |
| Risk tier | Documentation only |
| Validation | **L0 only** (§8.1) |
| `--all`? | **No** |
| Network | **No** |
| External state written | **No** |
| Commit | Own commit, `docs(harvest): plan stage 9 live validation` |
| Entry | Stage 8 closed and published; tip `2bbc236a`; Stage 9 unopened |
| Exit | This file committed; `TODO.md` carries the decomposition; **no implementation checkpoint approved** |
| Why separate | A plan that arrives with code has already made its decisions unreviewably |

### S9-1 — live execution seam and CLI foundation · **COMPLETE**

| Field | Value |
|---|---|
| Purpose | Make a live run *possible*; do not make one *happen* |
| Owns | `harvest.sh` dispatcher · `cli.py` · the `Transport` seam · required `--state-root` · transport injection · real pacing · `--no-enrich` · honest mode/`config` reporting · harness wiring for `test_taxonomy_cli.sh` |
| Allowed paths | **TEN, after a ratified expansion** (§7.1a): `scripts/harvest/harvest.sh` (new) · `src/harvest/cli.py` (new) · `src/harvest/run_cells.py` · `tests/harvest/test_cli.py` (new) · `tests/test_taxonomy_cli.sh` (new) · `scripts/validate_task.sh` · **`tests/harvest/test_run_cells.py`** · **`tests/harvest/test_recovery.py`** · this plan · `TODO.md` |
| Risk tier | Code — production module modified (`run_cells.py`) |
| Validation | `bash -n`; `py_compile`; the new focused suite; **`test_taxonomy_run_cells.sh`, `test_taxonomy_recovery.sh`, `test_taxonomy_eligibility.sh`, `test_taxonomy_target_determinism.sh`** (the direct dependants of `run()`); a harness inventory proof (**59** wrappers — see E9-1 — each routed exactly once); a **no-socket assertion**; a byte-identity proof that `transport=None` reproduces today's tree exactly |
| `--all`? | **No** — deferred to the final code baseline (§8.2) |
| Network | **No.** The live path exists and is not exercised |
| External state written | **No** |
| Commit | Own commit, `feat(harvest): add live transport seam and CLI foundation` |
| Entry | S9-0 committed; S9-1 separately approved by name |
| Exit | A live run is *constructible* and provably not *constructed*; fixture callers byte-unchanged |
| Why separate | The single largest under-estimated item in the roadmap (G1). It deserves its own review, and it must land before anything can even be preflighted |

#### §7.1a — the ratified two-path expansion, and why it was needed

S9-1's original eight-path set was **insufficient, and the shortfall was structural rather than an
oversight in scoping**. Three committed assertions pinned the very interface S9-1 was approved to
change:

| Guard | Home | What it pinned | Why S9-1 falsified it |
|---|---|---|---|
| `test_the_entry_point_has_the_planned_signature` | `test_run_cells.py::TestBoundary` | `list(params) == ["root","cells","clock","fixtures_dir","max_cells"]` — a **closed** list | Any added seam trips it. Unavoidable under every implementation of the approved interface |
| `test_the_opener_is_the_fixture_opener` | `test_run_cells.py::TestOffline` | `"FixtureOpener" in inspect.getsource(run_cells.run)` — an implementation **location** | §5 requires a named factory that honours `fixtures_dir`, so construction moved out of `run()`'s own source text |
| `test_the_driver_signature_did_not_change` | `test_recovery.py::TestBoundary` | the same closed five-name list | Same as the first |

The checkpoint **stopped without committing and reported**, rather than widening its own scope — the
rule that has held since Stage 4's closeout. The expansion to ten paths was then **ratified
explicitly**, and it is an expansion of S9-1, not a new checkpoint and not authorization for S9-2.

**No production code was shaped to keep a source scan green.** That was available — keeping the
literal `FixtureOpener` inside `run()` would have kept guard 2 passing — and it was rejected on the
committed precedent: S6-4 refused to rename a pool method to dodge a token scan, and S6-6A refused
to rename three accounting keys to keep a guard green, both citing S5-4. The transport factory was
neither renamed nor duplicated to fool an assertion.

**All three were spent progress guards, not behavioural regressions.** Before the correction the two
suites ran **171 of 174 assertions green**, and the three failures were a signature list and a source
substring. The byte-compatibility proof in `test_cli.py` independently establishes that the artifact
tree did not move.

Treatment, one line each:

- **`test_the_opener_is_the_fixture_opener` → `test_the_default_transport_is_fixture_only_and_live_is_not_owned_here`.**
  The implementation-location assertion is **removed**. What remains is the permanent boundary, and
  it is now asserted behaviourally rather than textually: the fixture transport really carries a
  `FixtureOpener` and a non-pacing sleep, and `run_cells.py` still does not name the live opener at
  all — that pairing belongs to `cli.py`. The complete transport contract is **not** duplicated here;
  `test_cli.py` owns it, and the existing no-socket test is untouched.
- **`test_the_entry_point_has_the_planned_signature` → `test_the_entry_point_stays_omission_compatible`.**
  Rewritten from immutability to **omission compatibility**, which is what committed callers actually
  depend on: the five Stage 5 parameters keep their **order as a prefix** and their defaults; the
  four S9-1 seams follow, each keyword-only and `None`-defaulted; `bounds` is asserted **absent**
  (E9-3); and no independent `opener` / `sleep` / `lease_root` parameter exists. It names no future
  S9-3 parameter and adds no "later Stage file must not exist" guard.
- **`test_the_driver_signature_did_not_change` — DELETED outright, not replaced.** It asserted no
  recovery property. Recovery is owned by the surrounding assertions in that file — repeat refusal
  before writes, journal ownership, interruption cleanup, manifest-before-pointer ordering, pointer
  consistency — every one of which is **unmodified and green**. The S9-1 interface has two proper
  owners now, and restating it in a recovery suite only duplicated a guard in a file with no claim to
  it. No replacement signature or progress guard was added, on the S6-4 / S6-5 precedent.

**No genuine behavioural or recovery assertion was weakened, removed, or narrowed.** The expanded
S9-1 commit remains **atomic**: ten paths, one commit.

#### S9-1 as delivered — the actual contract

`run_cells.Transport` is a **frozen** dataclass of exactly `(opener, sleep, lease_root)`. `run()`
takes **one** transport, never three independent parameters, so a live opener can never inherit the
fixture's suppressed pacing — a test asserts that half-live API does not exist.

- `transport=None` → `fixture_transport(temp_lease_root, fixtures_dir=…)`, the committed behaviour
  reconstructed exactly, including `fixtures_dir` injection. The temporary lease root is created by
  `run()` and swept by `run()`. **A supplied lease root is the caller's**: used verbatim, never
  replaced, never deleted.
- `mode=None` → `MODE_HARVEST`. A `mode="smoke"` run is publication-ineligible through the
  **committed** `derive_publication_eligibility` — **no new predicate was added**, and a test asserts
  `run_cells.py` never passes `publication_eligible` or its reason at all.
- `enrich=None` → `True`, bound **once** and used for both the fetch phase and `config.enrich`. With
  `enrich=False` no target page is fetched, source discovery still runs, records keep the committed
  honest no-enrichment values, and the three `target_*` accounting keys are **ABSENT rather than
  zero** — the S6-6A sentinel, because "the lane did not run" and "the lane ran and found nothing"
  are different answers.
- `source_preflight=None` → `()`. Supplied rows reach the manifest unchanged; nothing is probed here
  and no row is assembled. `HttpClient.preflight()` is **byte-unchanged** and unused by this module.
- **No `bounds` parameter** (E9-3).

`cli.py` is parser construction, root resolution, `validate_state_root`, `live_transport` and
deterministic usage — and nothing else. `COMMANDS` is **empty**; all six planned commands exit **2**
naming the checkpoint that owns them. `validate_state_root` refuses empty, non-absolute,
repository-root, any repository descendant, the four prohibited runtime paths, and `..`-traversal
back inside; it creates nothing and deletes nothing. `live_transport` is the only place
`httpclient.default_opener` and `time.sleep` are named together; constructing one makes no directory
and issues no request, and **nothing calls it from an operational command, because there is none.**

`harvest.sh` is 20 lines: `set -euo pipefail`, repository root, `exec python -m src.harvest.cli "$@"`.
No `eval`, no option parsing, no Git, no network, no temp file, no state-root selection, no retry —
and **no second usage document**, which is why the zero-argument case is forwarded rather than
intercepted.

#### S9-1 focused results, as actually run

```text
bash -n scripts/harvest/harvest.sh                      ok
py_compile cli.py · run_cells.py · test_cli.py          ok
bash tests/test_taxonomy_cli.sh                         57 tests   OK
bash tests/test_taxonomy_run_cells.sh                   99 tests   OK
bash tests/test_taxonomy_recovery.sh                    74 tests   OK   (75 -> 74: one spent guard deleted)
bash tests/test_taxonomy_eligibility.sh                 48 tests   OK
bash tests/test_taxonomy_target_determinism.sh          88 tests   OK
                                                       ---------
                                                        366 assertions, all green

bash scripts/validate_task.sh scripts/harvest/harvest.sh src/harvest/cli.py
    exit 0 · PASS · test_taxonomy_cli.sh run EXACTLY ONCE despite two mapped
    files · zero "WARN - skipping" · no FAIL line · runtime paths absent · no
    production-state change

harness inventory   59 wrappers = 19 legacy + 40 taxonomy; ISOLATED[] 59 unique;
                    allowlist == file set both directions; the 58 committed
                    entries byte-identical as an ORDERED PREFIX against 720f114c;
                    exactly one appended entry; all 59 targets canonical
                    tests/<name>.sh; zero future-wrapper targets; no blanket or
                    aggregate arm
```

**`validate_task.sh --all` was NOT run**, per §8.2: the authoritative full offline gate belongs at the
final code baseline before the first live smoke. **No network request of any kind was made.** No
retained external Stage 9 state root exists, and none was selected.

**S9-2 and every `S9-L*` checkpoint remain unapproved. No live command is operational, and M2 is
unmet.**

### S9-2 — source-preflight implementation · **COMPLETE**

| Field | Value |
|---|---|
| Purpose | `preflight-sources`, offline-tested |
| Owns | Row assembly over the committed `HttpClient.preflight()` · `source_id` stamping from configuration · bounded failure mapping · deterministic output · harness wiring for `test_taxonomy_preflight.sh` |
| Allowed paths | **EIGHT, after a ratified expansion** (§7.2a): `src/harvest/preflight.py` (new) · `src/harvest/cli.py` · `tests/harvest/test_preflight.py` (new) · `tests/test_taxonomy_preflight.sh` (new) · `scripts/validate_task.sh` · **`tests/harvest/test_cli.py`** · this plan · `TODO.md` |
| Risk tier | Code — additive; `httpclient.py` **byte-unchanged**, asserted in-suite |
| Validation | Focused suite driving the real client against a **test-owned loopback server**, plus a stub client for the assembly contracts; a socket-level outbound refusal proved wired by tripping it; determinism over reversed configuration order |
| `--all`? | No |
| Network | **No outbound request.** Loopback the suite binds and shuts down itself |
| External state written | **No retained state.** One transient lease root outside the repository, removed on every exit path (E9-5) |
| Commit | Own commit, `feat(harvest): add source preflight command` |
| Entry | S9-1 complete; S9-2 separately approved |
| Exit | `preflight-sources` implemented and **never yet pointed at a real host** |
| Why separate | It is the cheapest possible first contact. Building it apart from the smoke keeps the first live request small |

#### §7.2a — the ratified one-path expansion, and why it was required

S9-2's seven-path set could not hold, for the same structural reason S9-1's eight
could not: three **S9-1 registry snapshots** in `tests/harvest/test_cli.py`
asserted the very state S9-2 was approved to change. Registering an operational
command necessarily makes `COMMANDS != {}`, so no implementation of S9-2 left them
green.

The checkpoint **stopped without committing and reported**, and the expansion to
eight paths was then ratified explicitly. **No production workaround was made**:
leaving `preflight-sources` in `PLANNED_COMMANDS` while registering it would have
kept two guards green and put a false statement in `--help`, and hiding the
command outside `COMMANDS` or renaming registry objects to evade a test were
rejected on the same S6-4 / S6-6A / S5-4 precedent S9-1 cited.

**The failures were registry shape, not behaviour**: `test_taxonomy_cli.sh` was
**54 of 57** green, and all three failures were assertions about the size and
membership of two dicts.

| Guard | Treatment |
|---|---|
| `test_no_subcommand_is_registered_at_s9_1` | **DELETED.** Its name states its own expiry. **Not replaced by "exactly one command is registered"** — that is the same spent-snapshot mistake with a different number, and would expire again at S9-3 |
| `test_no_operational_command_calls_it` | **REWRITTEN** → `test_the_live_transport_is_inert_until_an_operational_handler_calls_it`. Forbidding *every* operational caller was always the wrong claim: an operational command reaching the network is the constructor's purpose, and S9-3 and S9-6 will add two more approved callers. It now proves the **complement**, which is permanent — import (statically, since a behavioural probe cannot observe an import that already happened), parser construction, `--help`, an unknown command, every still-planned command, and a *refused* `preflight-sources` invocation must **all** leave the constructor untouched |
| `test_planned_commands_name_the_full_stage_9_set` | **REPLACED** by `test_registered_and_planned_commands_partition_the_stage_9_surface` |

**The durable invariant that replaces two snapshots.** The Stage 9 command
surface is exactly six names — `preflight-sources`, `smoke`, `validate`,
`compare-runs`, `diff`, `linkcheck` — and:

```text
COMMANDS ∩ PLANNED_COMMANDS = ∅          nothing is both implemented and planned
COMMANDS ∪ PLANNED_COMMANDS = surface    nothing approved vanishes from both
COMMANDS ⊆ surface                       no unplanned seventh command
every COMMANDS value is callable
every PLANNED_COMMANDS value names its owning checkpoint
help reports implemented and planned status honestly
```

This **stays true as each command moves from one side to the other**, so S9-3,
S9-4 and S9-6 do not re-encounter this blocker — while still failing loudly on
the two mistakes worth catching: a command registered without a plan entry, and
an approved command quietly disappearing from both registries. **No exact
`COMMANDS` or `PLANNED_COMMANDS` size assertion remains in the permanent CLI
suite.**

The checkpoint-specific fact that *only* `preflight-sources` is operational at
S9-2 lives in `tests/harvest/test_preflight.py`, the suite that owns the command,
alongside a proof that invoking it reaches its handler.

**Every permanent S9-1 boundary is unmodified and green**: the frozen atomic
`Transport`, the absence of separate opener/sleep/lease-root parameters, fixture
byte-compatibility, state-root validation, the `cli.py` AST boundary, shell
argument forwarding and exit-code preservation, and the fact that constructing
`live_transport` creates no directory and issues no request.

#### S9-2 as delivered — the actual contract

```text
bash scripts/harvest/harvest.sh preflight-sources [--sources ID[,ID...]] [--timeout-sec N]
```

- **Inventory.** All **25** configured sources resolve through the committed
  `run_cells.configured_cells()` reader — no second interpretation of the topic
  files. A duplicated or url-less `source_id` **raises before any probe**.
- **Selection.** Whitespace around an id is stripped deliberately; an **empty** id
  (`a,,b`, trailing comma) is **refused**; a **duplicate** id is **refused, not
  deduplicated**; unknown ids are refused **as a set** so three typos report
  three; an empty selection is refused. Every refusal happens **before the first
  request**, proved by counting probes afterwards.
- **Ordering.** Sorted by `source_id`, once, so neither configuration order nor
  the order the caller typed their ids can reach the output — proved by reversing
  the configuration and comparing serialized bytes.
- **Rows.** One probe per selected source, exactly once. `source_id` is stamped
  from **configuration**; the probe is handed a URL and has no notion of identity,
  so it cannot name a different source even when it tries. The result
  classification, reason and every measurement are the probe's, **copied
  verbatim** — reinterpreting one would make two authorities disagree about what a
  `404` means. Only the schema-admitted keys are emitted
  (`additionalProperties: false`).
- **Failures are rows.** A dead source is reported with its committed reason and
  every other selected source is still probed and still reported. "25 rows all ok"
  can never be confused with "3 rows all ok".
- **Exit.** `0` when every row is `ok`; `1` when any is not, **after printing the
  complete array**; `2` for usage, invalid selection or invalid option, **with
  empty stdout and no probe**. No retry-until-green.
- **`--timeout-sec`.** Implemented through the ONE committed seam:
  `HttpClient(policy, …)` reads its timeouts from `policy["budgets"]`.
  `HttpClient.preflight()` takes no per-call timeout, and emulating one above a
  client that already owns it would be a second HTTP implementation. The value
  must be numeric, finite and positive, and is **bounded above by the configured
  `request_timeout_sec` (20)** — a probe may be **narrowed, never widened**.
  `connect_timeout_sec` and `read_timeout_sec` are **clamped down** to it, or a
  `--timeout-sec 2` would be silently defeated by the configured 15-second read
  timeout. The committed policy document is **not mutated**.
- **`httpclient.py`, `run_cells.py`, `harvest.sh`, every config and every schema
  are byte-unchanged**, asserted in-suite against `fddbbb7`.

#### S9-2 focused results, as actually run

```text
py_compile preflight.py · cli.py · test_preflight.py · test_cli.py     ok
bash tests/test_taxonomy_preflight.sh                    65 tests   OK
bash tests/test_taxonomy_cli.sh                          57 tests   OK
                                                        ---------
                                                         122 assertions, all green

bash scripts/validate_task.sh src/harvest/preflight.py src/harvest/cli.py
    exit 0 · PASS · test_taxonomy_preflight.sh and test_taxonomy_cli.sh each
    EXACTLY ONCE · no other wrapper · zero "WARN - skipping" · zero FAIL ·
    runtime paths absent · no production-state change

harness inventory   60 wrappers = 19 legacy + 41 taxonomy; ISOLATED[] 60 unique;
                    allowlist == file set both directions; the 59 committed
                    entries byte-identical as an ORDERED PREFIX against fddbbb7;
                    exactly one appended entry; preflight.py routes only to the
                    preflight wrapper; cli.py routes to BOTH; all targets
                    canonical tests/<name>.sh; no future-wrapper target; no
                    blanket or aggregate arm
```

**`validate_task.sh --all` was NOT run** (§8.2). **No configured source has ever
been contacted** — the only traffic is a `ThreadingHTTPServer` the suite binds on
`127.0.0.1:0` and shuts down itself, and a socket-level guard refuses every
non-loopback host and is proved wired by tripping it deliberately. No retained
external Stage 9 state root exists or was selected; zero transient lease roots
leaked.

**S9-L1 remains unapproved. Live operation remains zero and M2 is unmet.**

### S9-L1 — live source-preflight execution · **NETWORK**

| Field | Value |
|---|---|
| Purpose | The project's **first outbound request, ever** |
| Owns | One authorized `preflight-sources` invocation |
| Allowed paths | **None.** Verification-only; no repository write path |
| Risk tier | Operational — irreversible in the sense that it cannot be un-sent |
| Validation | §8.3 |
| `--all`? | No |
| Network | **YES — requires explicit approval immediately before the request** |
| External state written | **No** — preflight writes nothing |
| Commit | **None** |
| Entry | S9-2 complete; S9-L1 approved as a checkpoint; **and approved again immediately before execution** |
| Exit | Complete external log preserved; every row reviewed by a human; **no retry-until-green**; no retained taxonomy run |
| Why separate | A source that is gone, moved, or robots-denied must be discovered before a 12-cell smoke spends 1800 s finding out |

### S9-3 — smoke and run-validation implementation · **COMPLETE**

| Field | Value |
|---|---|
| Purpose | `smoke` and `validate --run-id`, offline-tested |
| Owns | Global bounds enforcement (previously enforced by **nothing**) · all 12 cells · `--no-enrich` proved **end to end** · external-root behaviour · exact 43-path accounting · `validate --run-id` · interruption, repeat refusal and incomplete-run behaviour · harness wiring for `test_taxonomy_smoke.sh` |
| Allowed paths | **ELEVEN, after a ratified expansion** (§7.3a): `src/harvest/runvalidate.py` (new, E9-8) · `src/harvest/cli.py` · `src/harvest/run_cells.py` · `tests/harvest/test_smoke.py` (new) · `tests/test_taxonomy_smoke.sh` (new) · `tests/harvest/test_run_cells.py` (E9-9) · `tests/harvest/test_preflight.py` (E9-9) · **`tests/harvest/test_cli.py`** (§7.3a) · `scripts/validate_task.sh` · this plan · `TODO.md` |
| Risk tier | Code — production module modified |
| Validation | Focused suites only; a proof that a `smoke`-mode run is `publication_eligible: false` **by derivation**; a proof that bounds actually bind and are reported in `config.bounds`; a socket-level outbound refusal proved wired by tripping it |
| `--all`? | No |
| Network | **No outbound request.** Every smoke runs on the fixture transport |
| External state written | **Injected temp roots only**, all removed |
| Commit | Own commit, `feat(harvest): add bounded smoke and run validation` |
| Entry | S9-2 complete; S9-3 separately approved. **E9-7**: a completed S9-L1 is no longer the entry condition |
| Exit | A bounded 12-cell run is constructible against fixtures and validates offline |
| Why separate | The bounds are the whole safety story of a live smoke. They must be proved binding before a real host is involved |

#### §7.3a — the ratified one-path expansion, and why it was required

**E9-9 anticipated the duplicated `bounds` snapshot in `test_run_cells.py` but
missed the same snapshot in `test_cli.py`.** Both files carried an assertion that
`bounds` is absent from `run()`, and S9-3 is required to add it. `test_cli.py`
also carried a second, subtler defect. The checkpoint **stopped without committing
and reported**; the one-path expansion to eleven was then ratified, keeping S9-3
**one atomic commit** rather than splitting a production change from the guard
corrections it forces and leaving a red commit between them.

| Guard | Treatment |
|---|---|
| `test_bounds_is_not_accepted_at_s9_1` | **DELETED**, not replaced. The permanent `run()` interface contract belongs to `test_run_cells.py`, which now verifies the five-parameter prefix, the S9-1 seams, `bounds=None`, `run_id_value=None`, keyword-only omission compatibility, and the atomic absence of split transport and split bound parameters. Two copies of one contract are two authorities that expire independently. No replacement was added — not a current parameter list, not "only the S9-3 seams exist", not a future-stage absence guard |
| `test_the_live_transport_is_inert_until_an_operational_handler_calls_it` | **CORRECTED**, because its implementation contradicted its own stated contract |

**The AST scan was over-broad, and had been since S9-1.** It walked `tree.body`
intending "no module-level executable statement calls `live_transport`", but
`ast.walk` **descends into function bodies**, so it also rejected calls inside
function *definitions*. Defining a function that contains a call is not executing
one. The defect was invisible while no handler called the constructor and became
visible the moment `cmd_smoke` — an **approved, registered** handler — legitimately
did.

The corrected test distinguishes three things the original conflated:

1. **Module-level execution** — the static scan now skips `FunctionDef`,
   `AsyncFunctionDef` and `ClassDef` bodies and proves that importing `cli.py`
   executes no call to `live_transport`, `run_cells.run`, or any command handler.
2. **Inert and refused paths** — parser construction, `--help`, `-h`, no
   arguments, an unknown command, every still-planned command, and **refused
   operational arguments** (missing `--state-root`, a repository-contained root, a
   relative root, a malformed cap, a malformed run id, for both `smoke` and
   `validate`) all leave a patched sentinel untouched. A refusal must land
   **before** the network decision, not after it.
3. **Approved registered handlers** — the test no longer asserts that *no*
   function may call the constructor. It asserts that only `COMMANDS` is
   dispatchable, that the registry keeps its disjoint-union invariant over the six
   declared commands, that `smoke` and `validate` are registered while
   `compare-runs`, `diff` and `linkcheck` stay planned, and that **`validate` —
   registered but offline — never builds a live transport even on a valid
   invocation.**

**No production code was altered to fool either scan**, no valid smoke handler was
hidden or moved outside `COMMANDS`, and **no exact current command-count snapshot
was introduced** anywhere. That a valid `smoke` reaches the transport seam under an
injected offline transport, and contacts no configured host, is proved by
`test_smoke.py`, which owns that command; it is not duplicated in the CLI suite.

#### S9-3 as delivered

**`RunBounds`** is frozen and validated at construction: `max_candidates_per_cell`
and `max_accepted_per_cell` are ints ≥ 1 (a `bool` is refused), accepted may not
exceed candidates, `smoke_budget_sec` is finite and positive, and
`elapsed_before_run_sec` ≥ 0. `run()` gains **only** `bounds=None` and
`run_id_value=None`, both keyword-only; there is no independent `max_candidates`,
`max_accepted` or `smoke_budget` parameter, exactly as there is no independent
opener/sleep/lease-root.

**Candidate cap** — the extraction is sliced **before classification**, so a
candidate outside the cap receives no classification, no facets, no record and no
rejection row. It is *unprocessed*, which is not *rejected*, and it appears in no
log. Discovery is untouched: the cap limits judgement, not traffic, and the
committed per-adapter and per-cell request budgets still decide how much a cell may
ask for.

**Accepted cap** — the deterministic prefix ending at the Nth accepted candidate is
retained. Verdicts are preserved, nothing is relabelled, no rejection reason is
invented, and `accepted + rejected == candidates` still holds over the processed
set. Measured on the committed corpus: the uncapped cell accepts 4; capped to 2 it
reports 2 accepted with **fewer** rejections, never more — capping drops
candidates, it does not convert them.

**Smoke budget** — command-wide. `time.monotonic()` starts immediately before the
integrated preflight; the elapsed time is subtracted; the run phase receives only
`remaining_run_sec` as a committed `budget.scope("run", None, …)` time scope,
checked **before and after every cell**. Expiry raises before the artifact-writing
phase: **no manifest, no pointer movement, previous runs untouched.** A preflight
that consumes the whole budget is refused before the run starts. No new timeout
implementation was written.

**`config.bounds`** carries `max_candidates_per_cell`, `max_accepted_per_cell` and
`smoke_budget_sec` **only when bounds were supplied and therefore enforced**;
omitted bounds reproduce the committed two-key block byte-for-byte.
`elapsed_before_run_sec` is deliberately never reported — the configured budget is a
stable fact, how much of it preflight consumed is not.

**`smoke`** requires an external `--state-root`, accepts `--no-enrich` (the only
mode — there is no `--enrich`), `--max-candidates` and `--max-accepted` which may
only **narrow** the policy caps, and `--run-id`. Every argument, the state root and
a finished-run clash are decided **before** any transport is built. It prints one
deterministic timestamp-free summary and exits `0` only on complete publication —
42 JSON artifacts with the pointer naming the run — non-zero otherwise, `2` on
argument misuse. A failed run publishes no manifest, and partial artifacts are left
as evidence rather than deleted.

**`validate --run-id`** is offline and read-only. `runvalidate.py` imports no HTTP,
adapter or judgement owner, contains no write or repair call, and opens every file
read-only — all asserted by AST scan. It enforces the E9-11 decomposition, all 42
schemas, run-id agreement, cell/topic count relations, `alias_conflicts_count`
against the artifact, mode/enrich/bounds/eligibility, the 25 sorted preflight rows,
pointer consistency via the committed `verify_latest_run_id`, and `.tmp_*` debris
anywhere. Its report is sorted, deterministic, timestamp-free and unpersisted; exit
`0` valid, `1` invalid after printing, `2` on argument misuse before reading. A
test hashes a **broken** tree before and after validation and requires byte
identity: evidence must survive being examined.

**Two production defects found by these tests and fixed:** `RunValidateError` and
`RunCellsError` escaped `main()` as tracebacks instead of exit 2; and `argparse`'s
`SystemExit` escaped, breaking `main()`'s documented promise to return an exit code
rather than raise.

#### S9-3 focused results, as actually run

```text
py_compile × 7                                           ok
bash tests/test_taxonomy_smoke.sh            57 tests   OK
bash tests/test_taxonomy_cli.sh              58 tests   OK
bash tests/test_taxonomy_preflight.sh        65 tests   OK
bash tests/test_taxonomy_run_cells.sh        99 tests   OK
bash tests/test_taxonomy_recovery.sh         74 tests   OK
bash tests/test_taxonomy_manifest.sh         52 tests   OK
bash tests/test_taxonomy_eligibility.sh      48 tests   OK
                                            ---------
                                             453 assertions, all green

bash scripts/validate_task.sh src/harvest/runvalidate.py src/harvest/run_cells.py src/harvest/cli.py
    exit 0 · PASS · smoke, cli, preflight, run_cells and recovery wrappers each
    EXACTLY ONCE · no other wrapper · zero "WARN - skipping" · zero FAIL ·
    runtime paths absent · no production-state change

harness inventory   61 wrappers = 19 legacy + 42 taxonomy; ISOLATED[] 61 unique;
                    allowlist == file set both directions; the 60 committed
                    entries byte-identical as an ORDERED PREFIX against 3e64d6e;
                    exactly one appended entry; runvalidate.py routes only to the
                    smoke wrapper; cli.py routes to cli + preflight + smoke;
                    run_cells.py routes to run_cells + recovery + cli + smoke;
                    all canonical; no future-wrapper target, no blanket arm
```

**`validate_task.sh --all` was NOT run** (§8.2). **No configured source has ever
been contacted** — every smoke uses the fixture transport, and a socket-level guard
refuses every non-loopback host and is proved wired by tripping it. No retained
external Stage 9 state root exists or was selected; zero temp or lease roots leaked.

**One defect in the S9-3 test suite itself, found and fixed:**
`TestFullOfflineSmoke` stranded a complete 43-path run tree in the system temp
directory when `setUpClass` failed partway, because `tearDownClass` does not run in
that case. Switched to `addClassCleanup`, and the wrapper now fails on any leaked
`s93_*` root — a guard the suite owns cannot catch the suite crashing.

**E9-7 remains in force: S9-L1 is mandatory and unapproved, and must be completed
and reviewed before S9-L2. S9-4 and every later checkpoint remain unapproved.
`smoke` and `validate` have never been used against a real source. Live operation
remains zero and M2 is unmet.**

### S9-4 — run comparison and publication-diff implementation · **COMPLETE**

| Field | Value |
|---|---|
| Purpose | `compare-runs` and `diff --run-id`, offline-tested |
| Owns | Identity/idempotency invariants versus reportable content changes · deterministic stdout report · `diff --run-id` · proof that a live smoke does not alter the publication path |
| Allowed paths | **NINE, per E9-13**: `src/harvest/compare.py` (new) · `src/harvest/cli.py` · `tests/harvest/test_compare.py` (new) · `tests/test_taxonomy_compare.sh` (new) · `tests/harvest/test_cli.py` · `tests/harvest/test_smoke.py` · `scripts/validate_task.sh` · this plan · `TODO.md` |
| Risk tier | Code — additive |
| Validation | Focused suite over synthetic run pairs; a proof that an **unenumerated** moving field fails rather than being normalized away; a proof that `diff` reports an **absent** publication root distinguishably from an empty one |
| `--all`? | No |
| Network | **No** |
| External state written | Injected temp roots only |
| Commit | Own commit |
| Entry | S9-3 complete; S9-4 separately approved |
| Exit | Two runs can be compared before two runs exist |
| Why separate | Writing the comparator *after* seeing the live data invites tuning it to pass |

**As delivered.** `src/harvest/compare.py` owns every comparison and publication-diff judgement;
`cli.py` parses, dispatches and serializes and does nothing else. Both commands are read-only and
offline: an AST scan asserts the module opens nothing for writing and names no writer, socket,
transport or sleep API, and a test asserts neither command constructs a live transport. Errata
**E9-13** (nine paths, two spent guards retired), **E9-14** (`--normalize` removed; three-class
partition; schema-derived content class), **E9-15** (18 selected documents only; both runs may be
historical; `runvalidate` not weakened) and **E9-16** (within- versus between-run counts) record the
four contract corrections. Focused validation: `test_taxonomy_compare.sh` **48**,
`test_taxonomy_cli.sh` **58**, `test_taxonomy_smoke.sh` **56**, all green, plus explicit-mode harness
routing over `compare.py` and `cli.py`. Inventory **62 = 19 legacy + 43 taxonomy** (E9-17). **No
`--all` was run**, no network request was made, no external retained root was selected, and
`data/harvested/` remains absent.

### S9-L2 — first bounded live smoke · **NETWORK** · **M2**

| Field | Value |
|---|---|
| Purpose | The first real staged taxonomy dataset |
| Owns | One exact `smoke` invocation; establishing the external retained root |
| Allowed paths | **None** in the repository |
| Risk tier | Operational |
| Validation | §8.3, then `validate --run-id` **offline** after the network command |
| `--all`? | No |
| Network | **YES — explicit approval immediately before the request** |
| External state written | **YES — the retained external root, which must survive** |
| Commit | **None** |
| Entry | S9-4 complete; the authoritative `--all` baseline green (§8.2); the external root path chosen and reported; S9-L2 approved as a checkpoint **and again immediately before execution** |
| Exit | **42 JSON + 1 pointer = 43 paths** if all 12 cells run; the tree validates offline; full output and runtime tree preserved; source failures **reported, not fixed by editing policy**; **no automatic retry** |
| Why separate | It is the milestone. Combining it with implementation would let a code change be justified by a live result |

**This checkpoint achieves M2 only if the complete retained staged dataset validates.** An exit-0
smoke whose tree fails `validate --run-id` is not M2.

### S9-L3 — second bounded live smoke and comparison · **NETWORK** · **M3**

| Field | Value |
|---|---|
| Purpose | Repeatability evidence |
| Owns | One second `smoke` under the **same** external root, with a **fresh run ID**; then offline validation and offline `compare-runs` |
| Allowed paths | **None** in the repository |
| Risk tier | Operational |
| Validation | §8.3; `validate --run-id` on run 2; `compare-runs A B` offline |
| `--all`? | No |
| Network | **YES — explicit approval immediately before the second smoke** |
| External state written | **YES — both runs preserved** |
| Commit | **None** |
| Exit | Two validating runs; identity/idempotency invariants hold; content changes reported separately; **no third smoke**; **no automatic retry** |
| Why separate | One run proves the plumbing; two prove the determinism claim that every prior stage asserted against fixtures |

### S9-5 — live-corpus calibration decision

| Field | Value |
|---|---|
| Purpose | Discharge S4-4A, whose conclusion was that **synthetic fixtures are unsuitable for tuning editorial acceptance thresholds** and that calibration is deferred to a live corpus |
| Owns | Accepted/rejected counts by cell · rejection reasons · source failures · score distribution · which thresholds actually bound · duplicate rate · coverage gaps · comparison stability · **the decision**: thresholds stay provisional, are accepted, or need correction |
| Allowed paths | `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` · `docs/harvest/TODO.md` *(analysis recorded in the plan; a separate document only if the analysis outgrows it, declared by exact name before writing)* |
| Risk tier | Documentation only |
| Validation | L0 only |
| `--all`? | **No** |
| Network | **No** |
| External state written | **No** — reads the retained root, writes nothing |
| Commit | Own commit |
| Exit | A recorded decision with its evidence |
| Why separate | A measurement checkpoint that may also change config is a checkpoint that will change config |

**No config or production-code change is permitted in S9-5.** If a threshold, vocabulary, source or
policy change is recommended:

1. **Do not make it in S9-5.**
2. Propose a **separately approved corrective checkpoint** (`S9-5C`).
3. List its exact paths up front: the config file, the **generated schema** if a vocabulary moves
   (`facets.generated.v1.json` pins the vocabulary SHA-256 — vocabulary and generated schema are one
   atomic contract and go in **one commit**), the affected tests, the affected checkers, this plan,
   and `TODO.md`.
4. Apply the **CF-6 committed-tree procedure**: 33 of 39 taxonomy wrappers assert `config/` is
   unmodified against HEAD, so the suites are red pre-commit and green immediately after the atomic
   commit. Measure both, and record both, exactly as S4-3A and S4-5A-C did.
5. **Require a fresh pair of live smoke runs** — and their own approvals — **only if** the change can
   alter live verdicts. A comment or a version bump cannot; a relevance term or a threshold can.

### S9-6 — linkcheck implementation

| Field | Value |
|---|---|
| Purpose | `linkcheck`, offline-tested |
| Owns | Deterministic sample selection · bounded target checks · `link_history` append behaviour · base-run immutability · the exact linkcheck artifact tree · validation and recovery · harness wiring for `test_taxonomy_linkcheck.sh` |
| Allowed paths | `src/harvest/linkcheck.py` (new) · `src/harvest/cli.py` · `tests/harvest/test_linkcheck.py` (new) · `tests/test_taxonomy_linkcheck.sh` (new) · `scripts/validate_task.sh` · this plan · `TODO.md` |
| Risk tier | Code — additive; `records.py` **byte-unchanged** (`link_history` already exists), asserted in-suite |
| Validation | Focused suite; a **byte-identity proof of the base run before and after**; sample-selection determinism over shuffles; `test_taxonomy_target_fetch.sh` and `test_taxonomy_target_ownership.sh`; no-socket assertion |
| `--all`? | No |
| Network | **No** |
| External state written | Injected temp roots only |
| Commit | Own commit |
| Why separate | Link-checking mutates a *second* run from a *first* one. Getting immutability wrong here silently corrupts the M2 dataset |

### S9-L4 — bounded live linkcheck execution · **NETWORK** · **M4**

| Field | Value |
|---|---|
| Purpose | Link-health evidence |
| Owns | One exact `linkcheck` invocation |
| Allowed paths | **None** in the repository |
| Risk tier | Operational |
| Validation | §8.3; `validate --run-id` on the linkcheck run offline |
| `--all`? | No |
| Network | **YES — explicit approval immediately before the request** |
| External state written | **YES** |
| Commit | **None** |
| Exit | The linkcheck run validates; both smokes preserved; base run byte-unchanged; **no retry-until-green** |
| Why separate | It is the one Stage 9 execution that deliberately fetches target pages, and the one that meets arXiv's 15 s crawl-delay in earnest |

### S9-C — Stage 9 closeout

| Field | Value |
|---|---|
| Purpose | Record what Stage 9 delivered, honestly |
| Allowed paths | `docs/harvest/STAGE_9_IMPLEMENTATION_PLAN.md` · `docs/harvest/TODO.md` · `docs/harvest/handoffs/HANDOFF_STAGE_9_COMPLETE_<date>.md` (new) · **`docs/harvest/ROADMAP_AND_ARTIFACT_LIFECYCLE.md`** — included by exact name **here, in advance**, because Stage 9 evidence will change its current-state dashboard (live operation ceases to be 0 %; M2-M4 statuses move). Declaring it now is what stops a later widening |
| Risk tier | Documentation only |
| Validation | **L0 only.** No test rerun |
| `--all`? | **No** |
| Network | **No** |
| Commit | Own commit |
| Exit | Handoff exists; the external live root's path **and disposition** recorded; §9 exit criteria all met |

**Stage 9 push and project-memory synchronization remain separate approvals after closeout**, each in
its own checkpoint, exactly as at Stages 7 and 8.

---

## 8 · Validation policy

### 8.1 Documentation-only checkpoints — L0

Exact path diff · `git diff --check` · protected baseline **18/18** · untracked baseline **508/508**
drift 0 / missing 0 / extra 0 · all four repository runtime paths **absent** · **no tests**.

Applies to: S9-0, S9-5, S9-C.

### 8.2 Code checkpoints

- Syntax / static validation (`bash -n`, AST scans).
- The **new** focused suite in full.
- The **directly affected** existing suites, named per checkpoint in §7 — by ownership, not by import
  fan-out.
- A **harness inventory proof**: the expected wrapper list built from `git ls-files tests/`, not from
  a log; every wrapper routed exactly once; zero unrouted new paths.
- A **no-socket assertion** on every offline suite.
- **One** full `bash scripts/validate_task.sh --all`, at the **final code baseline before the first
  live smoke** — i.e. after S9-4 and before S9-L2 — expecting **62/62 wrappers each exactly once,
  zero `WARN - skipping`, exit 0**, no runtime leak, no production-state change (**corrected by
  E9-17**: 62 is the inventory at that baseline; 63 arrives only with S9-6). A later corrective code
  commit (S9-5C, S9-6) requires a **new** authoritative run before the next live execution that
  depends on it — and the post-S9-6 run, owed before S9-L4, expects **63/63**.

  **Neither authoritative run has happened.** As of S9-4 the full gate has not been run at all.

**The full gate is not rerun after every small code checkpoint merely to restate existing evidence.**
That was Stage 8's own conclusion and it holds.

### 8.3 Live execution checkpoints

| Rule | |
|---|---|
| Repository write paths | **None** |
| Commit | **None** |
| Approval | The exact command, approved **immediately before execution**, in addition to the checkpoint approval |
| Log | Complete stdout **and** stderr, captured **outside the repository**, uniquely named |
| Exit code | **Original code preserved** — never piped into a filter |
| Invocations | **Exactly one.** **No retry-until-green** |
| Failure | Diagnostics preserved; **no automatic retry, no policy edit to make it pass** |
| Repository | Verified untouched before and after — worktree, index, both baselines, all four runtime paths |
| Inspection | Only the **existing** run is inspected afterwards, offline |
| External root | **Expected, retained, and inventoried** — path, file count, and disposition recorded |
| Promotion | **None.** Not attempted, not possible |

### 8.4 Domain throttle

Existing diagnostics are **preserved, not replaced**. `test_taxonomy_domain_throttle.sh` launches real
subprocesses against a **local** recording server and measures timing; it is the suite most likely to
fail under live-run load.

**The three intermittent signatures remain unresolved diagnostics.** A live pass is **one
observation**, never a resolution. No permanent-flake status may be granted. **No blind retry.**

---

## 9 · Stage 9 exit criteria

Stage 9 may close only when **all** of the following hold:

1. Live CLI and transport seam implemented and offline-tested.
2. Every new wrapper wired into `scripts/validate_task.sh`.
3. The authoritative offline harness runs are green — **62/62 before S9-L2, then 63/63 after S9-6
   and before S9-L4** (E9-17). Two runs, not one; neither has happened yet.
4. Live source preflight executed **once** and reviewed.
5. The first real 12-cell staged run exists in the external retained root **and validates**.
6. A second staged run exists **and validates**.
7. Comparison passes the identity/idempotency invariants.
8. Content changes are reported **separately** from invariant violations.
9. The calibration decision is **documented**.
10. One bounded linkcheck run exists **and validates**.
11. The repository publication path remains **absent or byte-unchanged**.
12. **No production promotion occurred.**
13. **No website integration occurred.**
14. The external live root's **disposition is recorded**.
15. **Every** network execution was separately approved, immediately before its request.
16. The completion handoff exists.
17. M2-M4 status updated **honestly**.
18. **M5 remains unopened.**

### 9.1 What Stage 9 completion must NOT claim

- publication eligibility;
- production readiness;
- production promotion;
- recurring refresh;
- website consumption.

A Stage 9 that meets every criterion above has produced a **retained, validated, unpublished** staged
dataset and evidence about it. That is the whole claim.

---

## 10 · Deferred and recorded, not acted on

- **Roadmap gaps G1, G8, G12** are addressed by this plan (the missing CLI, the over-broad Stage 9,
  two of the four unimplemented manifest modes). **G3, G13, G14, G15** are carried into Stage 9's
  execution and named in §7-§8. **G4, G5, G6, G7, G9, G10** remain post-Stage-9 milestone work and are
  **not** opened here.
- **CF-1** stays deferred and guarded: Stage 9 introduces **no concurrency**, so the unlocked pool
  paths keep zero concurrent callers, and the committed static scan continues to fail on any
  concurrency primitive. Any future change that runs cells concurrently must fix CF-1 **first**, in
  its own checkpoint.
- **CF-2 / CF-7, CF-5 / CF-8 / CF-9, CF-11, CF-13, CF-15, CF-16, CF-17** and the Stage 8 set
  **S8-CF-1 … S8-CF-7** all retain the status recorded in the Stage 8 handoff. Stage 9 closes none of
  them except where §7 names one explicitly.
- **CF-16** (robots evidence unwired) is unchanged: `RobotsCache.get` / `.allowed` / `.crawl_delay`
  all fall through to `_fetch()` on a miss or expired TTL, so no cached verdict can be read without
  risking a request. `canonical_robots_allowed=None` stands.
- **S6-L**, Stage 6's bounded live smoke, remains **unexecuted and unauthorized**. Stage 9's S9-L2 is
  not S6-L and does not retroactively satisfy it.
- **One factual defect found during this audit, recorded not fixed** (this checkpoint's allowed paths
  do not include the roadmap): the roadmap's **§4.1 minimum-checkpoint estimate of 10** counted a
  separate "live-opener implementation" checkpoint and omitted `diff --run-id` entirely. This plan
  decomposes Stage 9 into **10 checkpoints (S9-0 … S9-C)**, folding the opener into S9-1 and adding
  `diff` to S9-4. The roadmap's **13-18 range remains sound**; only its internal breakdown differs.
  Correct it at **S9-C**, where the roadmap is already in the allowed-path set.
