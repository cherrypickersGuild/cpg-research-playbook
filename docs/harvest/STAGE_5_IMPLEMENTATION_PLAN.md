# Stage 5 — artifact persistence: implementation plan

```text
Status: IN PROGRESS — S5-1 … S5-5 COMPLETE; S5-6, S5-7, S5-C NOT APPROVED
```

**Approving this plan approved the *plan*, not any checkpoint.** Each of S5-1 … S5-C requires its
own separate approval, named explicitly, before any file outside `docs/` changes. **Sequential cell execution and S5-1 … S5-5
were approved on 2026-07-30**; all five checkpoints shipped and are marked completed below.
Every remaining checkpoint is still unapproved — a completed predecessor and a green gate do not
together authorize the next one. This rule is restated at every checkpoint and in §12.

**Date:** 2026-07-30 · **Branch:** `main`

```text
stage_4_closing_commit:      b303d9db1e7433a740960bfbaaf83e82acfd8433
stage_4_closeout_commit:     5fd9f91e2209b6ecf775de167cf7d0c3746d857c
stage_4_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_4_COMPLETE_2026-07-30.md
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34
push_state:                  main synchronized with origin/main at 5fd9f91
assertions_at_plan_time:     940 across 23 suites, all green
```

Predecessors, still valid: `IMPLEMENTATION_PLAN.md` (§2 URL contract, §3 sources, §6 budgets, §10
filesystem layout and ignore rules, §13 allowed and prohibited paths) ·
`STAGE_4_IMPLEMENTATION_PLAN.md` (§5 permanent checkpoint execution policy, adopted here unchanged;
§11 Stage 5 opening condition) · `HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` (inherited constraints).
Where an older document conflicts with shipped code, the **code** is authority; such conflicts are
recorded in §11.

---

## 1 · Scope

**Stage 4 ended with a complete in-memory pipeline that writes nothing.** Stage 5 gives it a
filesystem: the same records, rejections and counts, serialized deterministically and atomically to
the committed artifact schemas. Stage 5 adds **no new judgement** — it does not classify, score,
facet or decide anything that Stage 4 did not already decide.

### 1.1 Goals

1. A deterministic, atomic, idempotent artifact writer for the eight committed artifact schemas.
2. A per-cell driver that runs the Stage 4 pipeline over the fixture corpus and emits one cell
   artifact, one rejection log and one ledger update per configured cell.
3. Topic-level merge, a coverage report, and a run manifest for the whole run.
4. Recovery semantics: an interrupted run leaves no readable partial artifact, and `LATEST_RUN_ID`
   never names an incomplete run.
5. Discharge of the carried-forward **coverage reporting wiring** item.

### 1.2 Explicit non-goals

Stage 5 does **not**:

- make any live network request, or fetch any target page — **Stage 6**;
- implement `sitemap` or `model_search` adapters — Stage 6 / Stage 9;
- migrate the legacy AX corpus — **Stage 7**;
- promote anything into `data/harvested/`, or write a publication manifest, promotion journal,
  staging or rollback tree — the `promote` command, later;
- wire `scripts/validate_task.sh` — **Stage 8** (CF-4);
- recalibrate any threshold, weight, half-life or the `0.68 / 0.32` split — **Stage 9** (§9.3);
- run cells concurrently — see §9.1 (CF-1);
- modify `pool.py`, `records.py`, `facets.py`, `verify.py`, `classify.py`, `extract.py`,
  `dedupe.py`, `facetassign.py`, `urlkey.py`, any schema, or any config file;
- add a new artifact schema. All eight already exist and are committed.

### 1.3 What Stage 5 does not modify

`src/harvest/**` **except** the new modules named in §6 · every file under `schemas/harvest/` ·
every file under `config/harvest/` · `scripts/harvest/**` · `tests/fixtures/**` · **any existing
test file** · `.gitignore` (already carries the single `/state/taxonomy_harvest/` line) · the 18
protected files · the 508 pre-existing untracked paths · `data/**` · production `state/` outside
`state/taxonomy_harvest/` · every prior plan and handoff.

**Prior handoffs and plans are read-only.** `HANDOFF_STAGE_4_COMPLETE_2026-07-30.md` in particular is
a closed historical record and is never edited.

---

## 2 · Data flow

The Stage 4 pipeline is unchanged and is called, not reimplemented:

```text
   configured cell (topic_slug, category_slug)          scheduler.configured_cells()
        │
        ▼
   AdapterResult per source                             adapters/*.discover() over FixtureOpener
        │
        ▼
   dedupe.delivery(lane_id, result) → dedupe.group()    same-topic grouping, one identity per URL
        │
        ▼
   extract.normalize_all()                              ExtractedCandidate
        │
        ▼
   classify.classify()                                  Classification
        │
        ├──────────────► verify.verify()                Verdict: accepted | rejection_reason
        │                     │
        │            accepted │            rejected ────────────► REJECTION LOG   (S5-3)
        │                     ▼
        └──────────────► facetassign.assign()           FacetAssignment
                              │
                              ▼  .case_facets
                    records.make_full_record(...)       full record   (S4-5B contract)
                    records.make_cross_reference(...)   pointer row
                              │
                              ▼
                    records.sort_records()              (topic, primary_category, record_id)
                              │
        ┌─────────────────────┼──────────────────────┬─────────────────────┐
        ▼                     ▼                      ▼                     ▼
  CELL ARTIFACT         LEDGER UPDATE          COVERAGE REPORT        RUN MANIFEST
     (S5-2)                 (S5-3)                 (S5-4)                (S5-5)
        │                                                                  ▲
        ▼                                                                  │
  TOPIC ARTIFACT (S5-2) ────────────────────────────────────────────── LATEST_RUN_ID
                                                                       written last (S5-5)
```

**The boundary Stage 5 must not cross:** everything above `records.sort_records()` is Stage 4 and is
called as committed. Everything below it is new. No Stage 5 module may re-derive a score, a
category, a facet or an identity — it reads what Stage 4 produced.

### 2.1 Filesystem layout

The layout is already fixed by `IMPLEMENTATION_PLAN.md` §10 and is adopted verbatim. Stage 5 creates
only the subset it needs:

```text
state/taxonomy_harvest/LATEST_RUN_ID                     "<run_id>\n", written LAST
state/taxonomy_harvest/runs/<run_id>/manifest.json       run_manifest.v1.json
state/taxonomy_harvest/runs/<run_id>/coverage.json       coverage_report.v1.json
state/taxonomy_harvest/runs/<run_id>/cells/<cell_id>.json    cell_artifact.v1.json
state/taxonomy_harvest/runs/<run_id>/topics/<topic_slug>.json topic_artifact.v1.json
state/taxonomy_harvest/rejections/<cell_id>.json         rejection.v1.json
state/taxonomy_harvest/ledgers/<cell_id>.json            ledger.v1.json
```

`run_id` format `YYYYMMDDTHHMMSSZ-<pid>`, per §10. `runs/<run_id>/` is per-run and immutable once
finished; `rejections/` and `ledgers/` are **cross-run, cell-owned, and merged** (§5.3). The whole
tree is gitignored by the single committed `/state/taxonomy_harvest/` line — Stage 5 adds no ignore
rule.

**Not created by Stage 5:** `logs/`, `tmp/`, `candidate_output/`, `alias_conflicts.json`,
`promote_staging/`, `promote_rollback/`, `promotion_receipt.json`, `registries/`, `cache/`,
`domains/`, `migrations/`, `locks/`. Each belongs to a later stage and is created by the stage that
first needs it.

---

## 3 · Contracts

### 3.1 Serialization — one function, one shape

Every artifact is serialized by a single function. Divergent serialization is how byte-determinism
dies, so there is exactly one:

```text
json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2, separators=(",", ": "))
+ "\n"                              trailing newline
encoded UTF-8, written with newline="\n"   LF on every platform, including Windows
```

`sort_keys=True` makes key order content-independent. `ensure_ascii=False` keeps non-ASCII titles
readable rather than escaped. The explicit `newline="\n"` matters here: the repository is checked out
on Windows and every other committed artifact convention is LF.

### 3.2 Atomic write

```text
write_atomic(path, data_bytes) :
    tmp = <dirname(path)>/.tmp_<uuid4().hex>_<basename(path)>
    write tmp · flush · os.fsync(fd) · close
    os.replace(tmp, path)                     atomic rename on the same filesystem
    fsync the containing directory where the platform supports it
```

The temp name is **unique per write** (`uuid4`), never a fixed `<file>.tmp` — CLAUDE.md's rule,
because a fixed name is a shared name and interleaves. `os.replace` is atomic on POSIX and on
Windows for same-volume renames, which is why the temp file is created in the destination directory
rather than a system temp dir. A reader therefore sees either the previous complete artifact or the
new complete artifact, never a partial one. `.tmp_*` files are never read by any Stage 5 code path.

### 3.3 Ordering — every artifact, every list

| List | Sort key |
|---|---|
| `cell_artifact.records`, `topic_artifact.records` | `records.sort_key` = `(topic, primary_category, record_id)` — the committed S4-5B contract, reused, not reimplemented |
| `rejection.rejections` | `(rejection_reason, identity_url)` |
| `ledger.entries` | `identity_url` |
| `run_manifest.cells` | `cell_id` |
| `coverage_report.by_category` | `(topic_slug, category_slug)` — as `coverage.build_coverage_report` already emits |

No list is ever ordered by completion time, discovery order, or dict insertion order.

### 3.4 Determinism and idempotency

- **Determinism.** With `HARVEST_CLOCK_UTC` pinned and a fixed fixture corpus, two runs produce
  **byte-identical** artifact bytes, modulo the `run_id` in the path and in the two
  `harvest_run_id` fields. A test asserts this by hashing the tree.
- **Order independence.** Shuffling source order, candidate order and cell order yields identical
  artifact bytes. This extends the S4-5B shuffle proof through persistence.
- **Idempotency.** Re-running an already-finished `run_id` is **refused** with a typed error, in the
  spirit of `pool.SnapshotExists` — it never silently overwrites a finished run. Re-running the
  *pipeline* into a fresh `run_id` over unchanged inputs produces byte-identical per-cell and
  per-topic artifacts.
- **Ledger idempotency.** Applying the same cell result to the ledger twice is a no-op beyond
  `last_seen_at` and `seen_count` — see §5.3.

### 3.5 Schema validation before write

Every artifact is validated **in memory against its committed schema before a single byte reaches
the filesystem**. A document that does not validate raises and writes nothing — no partial tree, no
"write it and check later". This is the property that makes the artifact tree trustworthy without
re-reading it.

### 3.6 Bounded execution and the no-live-request rule

- Tests use `fixtures.FixtureOpener` exclusively. `HttpClient` is **never constructed** in a Stage 5
  test, and a test asserts no socket is opened.
- Every Stage 5 entry point takes an injected `root=` (artifact root) and `clock=`. **No test ever
  writes to production `state/`**: each writes under its own temp root, and every wrapper epilogue
  asserts both the existing `state/` + `config/` cleanliness *and* that
  `state/taxonomy_harvest/` does not exist after the suite.
- Bounded: the driver caps cells per run (`MAX_CELLS`, default = the 12 configured cells) and
  respects the existing `budget.RequestBudget`. No unbounded loop, no retry storm.

---

## 4 · Risk tiers and validation

The Stage 4 §5 permanent checkpoint execution policy is adopted **unchanged**, with one addition for
filesystem work.

| Tier | Meaning | Validation |
|---|---|---|
| **L0** | Documentation only | Diff inspection · `git diff --check` · exact path set · 508-file baseline once. **No test suites.** |
| **L1** | Additive module, injected root, no existing file modified | Own focused suite repeatedly during work · **full gate once** before commit |
| **L2** | Touches an existing module or a shared contract | L1 plus targeted regression tests where relevant |
| **+FS** | *(new)* Any checkpoint that writes to the filesystem | Additionally: temp-root isolation assertion · `state/taxonomy_harvest/` absent after the suite · atomicity test (interrupted write leaves no readable artifact) · determinism test (tree hash stable) |

**Full gate** (once, before each commit from S5-1 onward): every `tests/test_taxonomy_*.sh` ·
`check_fixtures.py` · `verify_protected_baseline.sh` · `check_facets.py` ·
`gen_facet_schema.py --check` · `check_config.py` ·
`git diff --exit-code -- scripts/harvest/check_config.py` ·
`git status --porcelain --untracked-files=no` · the 508-file untracked baseline ·
`git diff --stat 8865c54e… HEAD -- .gitignore` still exactly `1 insertion(+)`.

`scripts/validate_task.sh` is **not** the Stage 5 gate (CF-4). Capture command output to a file
rather than piping; the guard hook blocks piping a protected command into `head`/`tail`/`grep`/
`sed`/`awk`/`tee`.

**No Stage 5 checkpoint should trigger CF-6**, because none edits `config/`. If one ever must, it
inherits the CF-6 procedure: all behavioural assertions green pre-commit, commit atomically, full
gate green from the committed tree.

---

## 5 · Checkpoints

Every checkpoint requires **separate approval**. This document authorizes none of them.

### S5-1 · Deterministic atomic artifact writer *(completed)*

**Approved and shipped 2026-07-30. 34 assertions, `tests/test_taxonomy_artifacts.sh`.** As built:
`serialize` is content-addressed — a document and the same document with reversed insertion order
hash identically (`ba65e645…`), LF, one trailing newline. `write_atomic` writes to
`.tmp_<uuid4hex>_<basename>` beside the destination, fsyncs, then `os.replace`s; a simulated crash
between write and rename left the previous 126-byte artifact byte-identical and valid, with no temp
debris. Cleanup catches `BaseException`, so `KeyboardInterrupt` leaks nothing. `write_document`
validates first: an invalid document raised and created no file. Parent directories are created by
`write_atomic` so nested layouts do not push that duty onto every caller. **No deviation from the
contract below.**

- **Goal.** One serializer, one atomic writer, one run-directory resolver. No artifact semantics.
- **Allowed paths.** `src/harvest/artifacts.py` (A) · `tests/harvest/test_artifacts.py` (A) ·
  `tests/test_taxonomy_artifacts.sh` (A) · this file (M) · `docs/harvest/TODO.md` (M).
- **API.** `serialize(doc) -> bytes` · `write_atomic(path, data)` · `write_document(path, doc,
  schema_name)` (validate → serialize → atomic write) · `run_id(clock=None, pid=None)` ·
  `run_dir(root, run_id)` · `ArtifactError`.
- **Invariants.** §3.1 serialization exactly · §3.2 unique temp name and `os.replace` · §3.5
  validate-before-write · LF on Windows · no schema, config or existing module touched · writes only
  under the injected `root`.
- **Focused tests.** Byte-identical output across repeated serialization · non-ASCII survives
  unescaped · trailing newline present · LF not CRLF on Windows · a rejected document writes **no**
  file · temp name is unique across concurrent writes and never a fixed `.tmp` · a simulated crash
  between write and rename leaves the previous artifact intact and readable · directory contains no
  `.tmp_*` after a successful write.
- **Risk tier.** L1 +FS.
- **Commit / stop boundary.** One commit. **Stop** if `os.replace` cannot be made atomic on the
  target filesystem — that is a platform finding, not something to work around in code.
- **Depends on.** Nothing. This is the base of the stage.

### S5-2 · Cell and topic artifacts *(completed)*

**Approved and shipped 2026-07-30. 45 assertions, `tests/test_taxonomy_cell_artifact.sh`.** As built:
`build_cell_artifact` / `build_topic_artifact` plus `write_cell_artifact` / `write_topic_artifact`
and the two `*_artifact_path` helpers encoding §2.1. Five shuffles of the same records produced one
hash (`71f92b39…`). Counts are **derived**, and a caller that supplies one is refused — two sources
of truth for "how many records are here" is how an artifact starts describing a set it does not
contain; `metadata` carries only `sources` and the optional `rejected`. A `cross_reference` is
counted separately and never contributes to `by_category`. Records are validated against
`record.v1.json` **before** assembly, so a `cases__domain-applications` record missing its facets is
refused by `record_id`. D2 lives in `project_classification_evidence`, and a test proves an
unprojected record cannot reach an artifact.

**One defect found and fixed during the checkpoint, by the test written for it:** the topic merge
originally deduplicated in cell-iteration order and sorted afterwards, so which duplicate survived
depended on cell order. Sorting **before** deduplicating makes the survivor a function of content —
`topic([a, b])` and `topic([b, a])` are now byte-identical.

**Contract clarified while building** (no deviation, the schema is silent): `by_category` counts
**full records only**, so it sums to `full_records` and a pointer never inflates a category's
coverage. `test_taxonomy_artifacts.sh`'s boundary test was narrowed from "no cell/topic semantics"
to "no S5-3 … S5-5 semantics" — the exclusion list shrinks by one entry per approved checkpoint.

- **Goal.** Turn a sorted record set into `cell_artifact.v1.json` and `topic_artifact.v1.json`.
- **Allowed paths.** `src/harvest/artifacts.py` (M) · `tests/harvest/test_artifacts.py` (M) ·
  `tests/harvest/test_cell_artifact.py` (A) · `tests/test_taxonomy_cell_artifact.sh` (A) ·
  this file (M) · `docs/harvest/TODO.md` (M).
- **API.** `build_cell_artifact(records, *, topic, topic_slug, category, category_slug, cell_id,
  harvest_run_id, generated_at, metadata) -> dict` · `build_topic_artifact(...)` · matching
  `write_*` helpers.
- **Invariants.** Records ordered by `records.sort_key`, never by arrival · both schemas are
  `additionalProperties: false`, so no field is invented · a `cross_reference` row may appear in a
  cell artifact and is **not** counted as an independent record · the topic artifact is the merge of
  its cells' records, re-sorted, with no duplicate `record_id` · **D2 lives here**: the
  `classification.evidence` projection to `{signal, matched}` gets one home and is not re-derived
  per call site · every record validates against `record.v1.json` before the artifact is assembled.
- **Focused tests.** A cell artifact validates · required keys present · records sorted · shuffled
  input yields identical bytes · a topic artifact merges its cells and de-duplicates by `record_id`
  · an invented top-level field is refused · a `cases__domain-applications` record without facets is
  refused before it can reach an artifact · the D2 projection is applied exactly once.
- **Risk tier.** L1 +FS.
- **Depends on.** S5-1.

### S5-3 · Rejection log and ledger *(completed)*

**Approved and shipped 2026-07-30. 46 assertions, `tests/test_taxonomy_ledger.sh`.** As built:
`src/harvest/ledger.py` holds the semantics — `build_rejection_log`, `write_rejection_log`,
`empty_ledger`, `load_ledger`, `merge_ledger`, `write_ledger`, `LedgerError` — and `artifacts.py`
gained only the two **cross-run, cell-owned** paths (`ledgers/<cell_id>.json`,
`rejections/<cell_id>.json`, deliberately *not* under `runs/<run_id>/`). Bytes reach disk only
through the S5-1 writer.

Measured: `first_seen_at` survives a re-merge while `last_seen_at`/`seen_count` advance (run 1
`first=…07-30 seen=1 rejected` → run 2 `first=…07-30 last=…07-31 seen=2 rejected`); a terminal
outcome is final, and a later `pending` sighting does not un-decide it; a corrupt ledger raises
naming re-harvest rather than resetting to empty; 5 shuffles of the same observations give one hash.

**CF-2 is now pinned, not merely believed.** The test enumerates rejection reasons from
`verify.decide`'s **AST** rather than typing them in: verify emits exactly six
(`below_quality_threshold`, `below_relevance_threshold`, `category_exclusion_applied`,
`developer_only_audience`, `insufficient_evidence`, `off_topic`) and all six are storable. The day a
seventh is added, this test fails instead of a live artifact write.

**Contract clarified while building** (no deviation; recorded because the plan's API line is
narrower than the data requires): **`build_rejection_log` takes `(extracted, verdict)` pairs**, not
bare verdicts. A `Verdict` names the reason, detail and scores but carries no `identity_url`,
`target_url`, `title` or `source_id` — those live on the `ExtractedCandidate` — so the candidate has
to travel with its verdict. `source_id` is the first of `source_ids` in committed dedupe order: a
candidate offered by several sources is still one rejection. Rejections sort by
`(rejection_reason, identity_url)` per §3.3.

Two refusals were added because the alternative is silent data loss, not as speculative guardrails:
an observation may not set `first_seen_at`/`last_seen_at`/`seen_count` (the merge owns them), and a
contradictory terminal→terminal outcome change raises rather than being quietly dropped.
`test_taxonomy_artifacts.sh`'s boundary list shrank to `coverage_report`, `run_manifest`,
`LATEST_RUN_ID`.

**Allowed-path addition, approved 2026-07-30: `tests/harvest/test_cell_artifact.py` (M).** S5-2 left
behind an assertion that `src/harvest/ledger.py` and `run_cells.py` **do not exist** — a guard that
measures checkpoint progress rather than a contract, and that therefore cannot survive the approval
of the checkpoint it names. It was **deleted**, not narrowed, and not replaced with another
future-file absence assertion. The same landmine in `test_ledger.py` was removed in the same pass.
**Rule for the remaining checkpoints:** a boundary test asserts facts about the surface of the module
under test, never about which files happen to exist yet.

- **Goal.** Persist what was rejected and why, and the cross-run URL ledger.
- **Allowed paths.** `src/harvest/ledger.py` (A) · `tests/harvest/test_ledger.py` (A) ·
  `tests/test_taxonomy_ledger.sh` (A) · `src/harvest/artifacts.py` (M) ·
  `tests/harvest/test_artifacts.py` (M) · this file (M) · `docs/harvest/TODO.md` (M).
- **API.** `build_rejection_log(verdicts, *, cell_id, harvest_run_id, generated_at) -> dict` ·
  `load_ledger(root, cell_id)` · `merge_ledger(existing, observations, *, now) -> dict` ·
  `write_ledger(root, cell_id, doc)`.
- **Merge semantics.** Keyed by `identity_url`. First observation sets `first_seen_at` and
  `seen_count = 1`; each subsequent observation advances `last_seen_at` and increments `seen_count`,
  and **never rewrites `first_seen_at`**. `outcome` transitions are explicit and one-way within a
  run: `pending → accepted | rejected | duplicate`. A `rejected` entry is retained deliberately —
  without it a rejected URL is re-fetched and re-rejected every run.
- **Invariants.** Ledger merge is **idempotent**: applying the same observation set twice changes
  only `last_seen_at`/`seen_count`, never `first_seen_at`, never `outcome`, never entry count ·
  entries sorted by `identity_url` · a corrupt or unreadable existing ledger raises rather than
  being silently reset to empty — **losing a ledger silently re-harvests the whole corpus** ·
  rejection reasons come from `Verdict.rejection_reason` and are never re-derived.
- **CF-2 / CF-7 are reconciled here, and are not blockers.** §9.2 records the measurement: every
  reason `verify.decide` can emit is already storable in `rejection.v1.json`.
- **Focused tests.** A rejection log validates · every reason `verify.decide` emits is accepted by
  the schema (enumerated from the module, not typed into the test) · `detail` names the actual rule
  and number for the composite gate · double-merge is a no-op beyond `last_seen_at`/`seen_count` ·
  `first_seen_at` survives a re-merge · a corrupt ledger raises · entries sorted.
- **Risk tier.** L1 +FS.
- **Depends on.** S5-1.

### S5-4 · Coverage report *(completed — discharges the carried-forward coverage wiring)*

**Approved and shipped 2026-07-30. 43 assertions, `tests/test_taxonomy_coverage_report.sh`.** As
built: `coverage_report_path` (`runs/<run_id>/coverage.json`), a `build_coverage_report` delegate and
`write_coverage_report`, all in `artifacts.py`. **`coverage.py` and `facets.py` are byte-unchanged**,
asserted inside the suite with `git diff --exit-code` — if either moved, this was not wiring.

The delegate adds exactly two things, both about persistence. **Ordering:** the committed builder
sorts `by_category` but projects its per-record rows in **input order**, so shuffled input produced
different bytes; the wrapper sorts by `records.sort_key` first. That fix belongs here, not in
`coverage.py`. **Refusal:** records are validated against `record.v1.json` before counting, so a
malformed record is named rather than silently tallied. `thresholds_constant` is passed through as
*reported* — all three values round-trip unchanged, and no S4-4 threshold is recalibrated or
reinterpreted.

Measured: the five states agree with `facets.count_states` and sum exactly to
`applicable_full_records`; `not_enriched` (1) is distinct from `unresolved` (1) with
`not_enriched: 0` inside the gated cell; `unmapped_legacy_value` outranks `facet_partial`; a
`cross_reference` is excluded from every count *and* from the records projection
(`with_pointer["by_category"] == without["by_category"]`); only `cases/domain-applications` is gated;
eligible + withheld = applicable; 5 shuffles give identical bytes.

**CF-11 is protected by six assertions, not by assumption.** The word `secondary` appears **nowhere**
in the serialized report, so an empty `industry.secondary` cannot read as a gap or a deficiency; it
changes no count, never withholds a record, and a `facet_complete` record without one stays complete
and eligible. Critically, one test proves the counting machinery is **live** — a populated
`secondary` *would* be observed — so CF-11 stays a visible design decision rather than decaying into
a broken counter.

**Allowed-path addition, approved 2026-07-30: `tests/harvest/test_artifacts.py` (M), one line.** Its
boundary guard listed `coverage_report` among the tokens forbidden in `artifacts.py`, which is
precisely what this checkpoint must add; the guard is designed to shrink by one entry per approved
checkpoint, but S5-4's path list predates the guard. `"coverage_report"` was deleted from that one
tuple, leaving `("run_manifest", "LATEST_RUN_ID")` prohibited until S5-5. Nothing else in the file
changed. Dodging the guard by deriving the schema filename or renaming the delegate was rejected: it
would obfuscate code to satisfy a test.

- **Goal.** Drive the committed, **unmodified** `coverage.build_coverage_report` from a real record
  set and persist `coverage_report.v1.json`.
- **Allowed paths.** `src/harvest/artifacts.py` (M) · `tests/harvest/test_coverage_report.py` (A) ·
  `tests/test_taxonomy_coverage_report.sh` (A) · this file (M) · `docs/harvest/TODO.md` (M).
- **Invariants.** `coverage.py` and `facets.py` are **byte-unchanged** — this checkpoint is wiring,
  not new coverage logic · `vocabulary_versions` from `facets.vocabulary_versions()` ·
  `reporting_state` from `facets.reporting_state`, never recomputed · **CF-11 is respected**: an
  empty `industry.secondary` is *by design*, and the coverage report must not report it as a gap or
  a deficiency (§9.4) · a `not_enriched` record is counted distinctly from an `unresolved` one.
- **Focused tests.** The report validates · counts match `facets.count_states` on the same set · an
  empty `secondary` produces no gap row · `not_enriched` ≠ `unresolved` in the counts · deterministic
  under shuffled record order · `coverage.py` unchanged (byte assertion against HEAD).
- **Risk tier.** L1 +FS.
- **Depends on.** S5-2.

### S5-5 · Run manifest and `LATEST_RUN_ID` *(completed)*

**Approved and shipped 2026-07-30. 52 assertions, `tests/test_taxonomy_manifest.sh`.** As built:
`run_manifest_path`, `latest_run_id_path`, `configured_cell_rows`, `policy_thresholds`,
`environment_block`, `derive_publication_eligibility`, `build_run_manifest`, `write_run_manifest`,
`read_latest_run_id`, `write_latest_run_id`, `publish_run`.

Measured: 12 configured cells → 12 unique rows, sorted by `cell_id`, with a status tally of
`{zero_result: 1, ok: 1, not_run: 10}` — an unreached cell is **recorded**, never omitted, so a
silently skipped cell cannot hide behind a shorter list. `topic_slug`/`category_slug` are stamped
from the configuration, so a caller cannot relabel a cell. Input cell order does not change the
bytes over 5 shuffles; preflight and classification-decision rows sort by their own keys.

**`publication_eligible` is derived from facts, never asserted** — it is not a parameter of
`build_run_manifest`, and a test asserts that. Stage 5 fetches no target page, so every Stage 5 run
is honestly ineligible: `"no target page was fetched, so every record is unverified (target fetching
arrives in Stage 6)"`. The derivation is proved **live** rather than hard-coded: a run with
`target_fetch_owners=5` and healthy cells is eligible with a null reason, a failed cell makes it
ineligible naming the cell, and a non-`harvest` mode is ineligible naming the mode.

**Thresholds are recorded, never recalibrated** (§9.3). `policy_thresholds()` reads
`policy.v1.json` — `{min_relevance: 0.35, min_quality: 0.3, accept_composite: 0.4}` — so what the
manifest records is what verify applied; a test asserts no threshold literal appears in that
function.

**The pointer moves last, or not at all.** `publish_run` persists the manifest, *then* advances
`LATEST_RUN_ID`, and a test asserts that order on the source itself. Three refusals protect the
pointer's one promise — that it names a run whose manifest exists and validates: an unfinished run
(`finished_at` null), a manifest whose `harvest_run_id` disagrees with the path, and a run that
already has a manifest. Failure preservation was measured against a previously published run: an
invalid manifest, an unfinished run, a crashed `os.replace` and a `KeyboardInterrupt` each left
`LATEST_RUN_ID` naming the older run, with no `RUN` manifest and no temp debris. The pointer is a
single line with exactly one trailing newline and no CRLF.

**Allowed-path addition, approved 2026-07-30: `tests/harvest/test_artifacts.py` (M), one deletion.**
The S5-1 boundary guard still prohibited the tokens `run_manifest` and `LATEST_RUN_ID` — precisely
this checkpoint's semantics. Per approval the **entire** `test_it_knows_nothing_about_later_checkpoint_semantics`
method was deleted rather than emptied, and **not** replaced with a guard against S5-6 or any later
checkpoint. That was the last downstream-semantic prohibition, so no such reconciliation remains for
S5-6 or S5-7. The surviving boundary tests in that file assert properties of the module itself: no
network, no locking or concurrency, no reimplemented schema validation, the committed contract
surface, and the runtime-path leak check.

**One in-scope simplification, worth recording.** The surviving
`test_it_does_not_reimplement_schema_validation` guard scans for the substring `jsonschema`, and
`environment_block` initially re-listed the schema's five `environment` keys — including
`jsonschema_version`, a *field name* the schema requires, not library use. Rather than edit a guard
outside this checkpoint's approval, `environment_block` now passes
`schema.check_environment()` through wholesale: its keys already match the schema's `environment`
block exactly, so the copy could only have drifted from it. Simpler code, and no obfuscation of an
approved API.

- **Goal.** One manifest per run, and the pointer that names the newest **complete** run.
- **Allowed paths.** `src/harvest/artifacts.py` (M) · `tests/harvest/test_manifest.py` (A) ·
  `tests/test_taxonomy_manifest.sh` (A) · this file (M) · `docs/harvest/TODO.md` (M).
- **Invariants.** `mode` is `"harvest"` for Stage 5; the other five enum values stay unused until
  their stage · `cells[]` carries one row per configured cell with a `status` from the committed
  enum, and `zero_result_reason` / `error_reason` only from their committed enums ·
  `publication_eligible` is **derived**, never persisted as a judgement Stage 5 invented ·
  the thresholds actually used are recorded so Stage 9 can compare against them without re-running
  (§9.3) · **`LATEST_RUN_ID` is written LAST**, after the manifest is safely on disk, so it can never
  name an incomplete run.
- **Focused tests.** The manifest validates · every configured cell appears exactly once · a cell
  that produced nothing is `zero_result` with a committed reason, not silently omitted ·
  `LATEST_RUN_ID` still names the previous run if the manifest write fails · `LATEST_RUN_ID` is a
  single line with a trailing newline · re-running a finished `run_id` is refused.
- **Risk tier.** L1 +FS.
- **Depends on.** S5-2, S5-3, S5-4.

### S5-6 · The cell driver

- **Goal.** Run the Stage 4 pipeline over the fixture corpus for each configured cell and emit the
  full artifact set for one run. This is the checkpoint that makes Stage 5 a *stage* rather than a
  library.
- **Allowed paths.** `src/harvest/run_cells.py` (A) · `tests/harvest/test_run_cells.py` (A) ·
  `tests/test_taxonomy_run_cells.sh` (A) · this file (M) · `docs/harvest/TODO.md` (M).
- **API.** `run(root, *, cells=None, clock=None, fixtures_dir=None, max_cells=MAX_CELLS) ->
  RunResult`.
- **Invariants.** **Sequential over cells** — see §9.1; concurrency is not introduced and CF-1 stays
  untriggered · every Stage 4 module is called as committed, none reimplemented · one cell's failure
  is recorded as that cell's `status` and does not abort the run or corrupt another cell's artifact ·
  no live request: `FixtureOpener` only · writes only under the injected `root`.
- **Focused tests.** A full run over the fixture corpus emits every expected artifact and all
  validate · the whole tree is byte-identical across two runs with a pinned clock · shuffled cell
  order yields an identical tree · a cell whose adapter fails yields `adapter_error` and leaves the
  other cells' artifacts intact and valid · no socket is opened · production `state/` is untouched.
- **Risk tier.** L2 +FS — it composes six committed modules.
- **Depends on.** S5-1 … S5-5.

### S5-7 · Recovery and re-run semantics

- **Goal.** Prove the tree survives interruption, and define what a second run does.
- **Allowed paths.** `src/harvest/artifacts.py` (M) · `src/harvest/run_cells.py` (M) ·
  `tests/harvest/test_recovery.py` (A) · `tests/test_taxonomy_recovery.sh` (A) · this file (M) ·
  `docs/harvest/TODO.md` (M).
- **Invariants.** An interruption at any point leaves **no readable partial artifact** — only
  `.tmp_*` files, which no code path reads · a `.tmp_*` sweeper removes only files it can prove are
  its own run's, and never touches a finished artifact · `LATEST_RUN_ID` always names a run whose
  manifest exists and validates · a re-run into a fresh `run_id` over unchanged inputs reproduces
  identical cell and topic artifacts · cross-run `ledgers/` and `rejections/` merge rather than being
  clobbered.
- **Focused tests.** Interrupt before rename → previous artifact intact · interrupt after the
  manifest but before `LATEST_RUN_ID` → pointer still names the previous run · a stale `.tmp_*` is
  swept and a finished artifact is not · two consecutive runs produce equal cell-artifact bytes ·
  the ledger accumulates across the two runs without losing `first_seen_at`.
- **Risk tier.** L2 +FS.
- **Depends on.** S5-6.

### S5-C · Stage 5 closeout *(documentation only)*

**This checkpoint exists so the Stage 4 authorization gap cannot recur.** At Stage 4 closeout, §11
required a committed handoff but no checkpoint declared a path set for writing one; the gap had to be
reported and separately approved. Stage 5 declares it up front.

- **Goal.** The Stage 5 completion handoff and documentation reconciliation.
- **Allowed paths — exactly three, declared now:**

  ```text
  A  docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_<YYYY-MM-DD>.md
  M  docs/harvest/STAGE_5_IMPLEMENTATION_PLAN.md   (this file)
  M  docs/harvest/TODO.md
  ```

- **Contents.** Commit chain · delivered checkpoints and any correctives · closure validation with
  the assertion total and suite count · repository state and baselines at closure · intentional
  non-goals and carried-forward findings · the successor's exact starting point and inherited
  constraints. Structural precedent: `HANDOFF_STAGE_4_COMPLETE_2026-07-30.md`.
- **Invariants.** Prior handoffs and plans are **not** edited · the status header of this file moves
  to `COMPLETED — STAGE 5 CLOSED` · every deviation applied is recorded here with its approval.
- **Risk tier.** L0 — diff and static validation only; **the full gate is not rerun for a
  documentation-only change.**
- **Depends on.** S5-7.

### 5.1 Dependency graph

```text
S5-1 ──┬── S5-2 ──┬── S5-4 ──┐
       │          │          ├── S5-5 ── S5-6 ── S5-7 ── S5-C
       └── S5-3 ──┴──────────┘
```

S5-2, S5-3 and S5-4 are independently reviewable once S5-1 lands. S5-3 does not depend on S5-2.

---

## 6 · Files

```text
S5-1  A  src/harvest/artifacts.py        A  tests/harvest/test_artifacts.py
      A  tests/test_taxonomy_artifacts.sh
S5-2  M  src/harvest/artifacts.py        A  tests/harvest/test_cell_artifact.py
      A  tests/test_taxonomy_cell_artifact.sh
S5-3  A  src/harvest/ledger.py           A  tests/harvest/test_ledger.py
      A  tests/test_taxonomy_ledger.sh   M  src/harvest/artifacts.py
S5-4  M  src/harvest/artifacts.py        A  tests/harvest/test_coverage_report.py
      A  tests/test_taxonomy_coverage_report.sh
S5-5  M  src/harvest/artifacts.py        A  tests/harvest/test_manifest.py
      A  tests/test_taxonomy_manifest.sh
S5-6  A  src/harvest/run_cells.py        A  tests/harvest/test_run_cells.py
      A  tests/test_taxonomy_run_cells.sh
S5-7  M  src/harvest/artifacts.py        M  src/harvest/run_cells.py
      A  tests/harvest/test_recovery.py  A  tests/test_taxonomy_recovery.sh
S5-C  A  docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_<date>.md
every M  docs/harvest/TODO.md            M  this file
```

**Two production modules total** — `artifacts.py` and `ledger.py` — plus one driver, `run_cells.py`.
Nothing else. See §1.3 for the exhaustive not-modified list.

---

## 7 · Commit and stop boundaries

- **One commit per checkpoint**, atomically, over that checkpoint's declared paths only, via
  `bash scripts/safe_commit.sh -m "…" <explicit files>`. Never `-A`, never `.`, never a glob.
- **Do not push.** Pushing is a separate, explicitly approved action (`safe_push_main.sh --check`
  then `--execute`), never bundled into a checkpoint.
- **Stop and ask** for: material scope expansion · a contradiction between committed contracts · a
  data-integrity risk · any need to touch a path outside the checkpoint's declared set. Nothing else
  justifies pausing mid-checkpoint.
- **Never claim success** unless the latest full-gate run is green and the exact declared path set —
  no more, no less — is what changed.

## 8 · Rollback

S5-1 … S5-7 are additive apart from `TODO.md` and this file: `rm` the checkpoint's new files,
`git checkout --` the two documents, and re-run the full gate. `artifacts.py` accretes across S5-2,
S5-3, S5-4, S5-5 and S5-7, so rolling back one of those means reverting that commit rather than
deleting a file — each is a single atomic commit precisely so this is possible.

**Triggers:** any of the 940 prior assertions turning red · any existing test needing an edit ·
protected-baseline failure · drift in the 508 pre-existing untracked files · a write outside the
injected root · a live request · discovering that a Stage 5 module cannot meet a committed contract
without changing `pool.py`, `records.py`, `coverage.py` or a schema — which returns for an explicit
deviation rather than being bent in code.

---

## 9 · Carried-forward findings

### 9.1 CF-1 — pool concurrency. **Deferred, and Stage 5 keeps it deferred.**

CF-1 was recorded against "the stage that first drives candidate rows concurrently — Stage 5". On
inspection that framing is avoidable: **Stage 5 runs cells sequentially** (S5-6), so
`pool.add_candidate`, `acquire_target_fetch` and `acquire_extraction` keep their zero concurrent
callers and the unlocked check-then-set paths stay harmless.

**Rule:** any later change that runs cells concurrently must fix CF-1 **first**, in its own
checkpoint, before the concurrency lands. Sequential execution is a deliberate Stage 5 constraint,
not an oversight, and it is also what makes the byte-determinism proofs in §3.4 straightforward.

### 9.2 CF-2 and CF-7 — rejection vocabulary. **Measured, non-blocking.**

CF-2 was recorded for "Stage 5, when that log is first written". Measured against the committed code:

- `rejection.v1.json` admits **13** reasons; `record.v1.json` admits those 13 plus **5** more
  (`not_a_case_trend_piece`, `not_a_case_product_announcement`, `not_a_case_tutorial`,
  `not_a_case_hypothetical`, `keyword_only_match`).
- `verify.decide` can emit exactly **six**: `developer_only_audience`, `category_exclusion_applied`,
  `insufficient_evidence`, `off_topic`, `below_relevance_threshold`, `below_quality_threshold`.
  **All six are in the rejection log's enum.**

So the five record-only values are unreachable from Stage 5's automated gate — they describe an
editorial "this is not a case study" judgement that no Stage 5 code makes. **No schema change is
required, and CF-2 is not a Stage 5 blocker.** S5-3 pins this with a test that enumerates the
reasons from `verify.py` rather than typing them into the test, so the day a new reason is added the
test fails instead of the artifact.

CF-7 (`below_composite_threshold` absent) is likewise non-blocking: `verify.decide` already reports
the closest honest reason with the detail naming the actual rule and number. Both stay carried
forward as **fidelity** questions for whichever stage revisits the rejection vocabulary.

### 9.3 S4-4 live-corpus calibration. **Untouched by Stage 5.**

`accept_composite = 0.40`, `min_quality`, `min_audience_fit`, `SATURATION = 3` and the
`0.68 / 0.32` split remain provisionally approved and are **not** revisited. Stage 5 changes no
threshold and no weight. Its one contribution is to **record the thresholds actually used in the run
manifest** (S5-5), so the Stage 9 bounded live corpus can compare against a real run without
re-deriving them. Calibration remains Stage 9.

### 9.4 CF-11 — `industry.secondary`. **Unchanged, and protected.**

`industry.secondary` stays empty by design: the committed definition means deployment context, never
corporate portfolio, and lexical evidence cannot make that judgement. Stage 5 must not fill it, and
S5-4 carries an explicit test that an empty `secondary` is **not** reported as a coverage gap —
otherwise the coverage report would create pressure to manufacture exactly the findings CF-11 exists
to prevent.

### 9.5 Coverage reporting wiring. **Discharged by S5-4.**

The item carried forward from S4-5B — `coverage.py` and `facets.count_states` / `reporting_state`
not yet driven from a built record set — is closed by S5-4, which wires them **unmodified**.

### 9.6 D2 — classification evidence narrowing. **Recorded, given one home.**

`classify.Evidence` carries `{signal, matched, field}`; `record.v1.json` admits `{signal, matched}`
under `additionalProperties: false`. S5-2 gives the projection a single implementation so it is not
re-derived at each call site. No schema change; no action beyond that.

### 9.7 Unchanged and not Stage 5's business

CF-3 (no target fixtures) → Stage 6 · CF-4 (`validate_task.sh` wiring) → Stage 8 · CF-5 and CF-8
(keyword-list tuning, unmatchable terms) → the relevance-tuning stage · CF-6 (config-editing
checkpoints cannot pass the full gate pre-commit) → Stage 8 · CF-9 (source tiers from `role`) → the
relevance-tuning stage.

---

## 10 · Stage 6 opening condition

Stage 6 planning may begin only when all of the following hold **in one final run**:

1. `tests/test_taxonomy_{artifacts,cell_artifact,ledger,coverage_report,manifest,run_cells,recovery}.sh`
   are green;
2. every prior assertion — the 940 — is green in that same run, unchanged and unmodified;
3. `verify_protected_baseline.sh`, `check_fixtures.py`, `check_facets.py`,
   `gen_facet_schema.py --check` and `check_config.py` all exit 0, and `check_config.py` is
   byte-unchanged;
4. the 508 pre-existing untracked files are byte-identical and `.gitignore` still shows exactly
   `1 insertion(+)` against the anchor — Stage 5 adds no ignore rule;
5. a full artifact tree validates against all eight committed artifact schemas;
6. byte-determinism is proved under shuffled source, candidate and cell orderings;
7. `data/harvested/` is still **absent**; nothing was promoted; no live request was made; production
   `state/` outside `state/taxonomy_harvest/` is untouched;
8. `pool.py`, `records.py`, `coverage.py`, `facets.py` and every schema and config file are
   byte-unchanged since `5fd9f91`;
9. every deviation applied is recorded here with its approval, and the Stage 5 completion handoff is
   committed in-repo at the path declared in **S5-C**;
10. **explicit approval is given.** Green tests alone do not open Stage 6.

## 11 · Errata — stale statements in earlier documents

Earlier documents are not rewritten. This plan is the authority for Stage 5 where they conflict.

**E9 — `IMPLEMENTATION_PLAN.md` §10 lists more runtime directories than Stage 5 creates.** The
layout names `logs/`, `tmp/`, `candidate_output/`, `registries/`, `cache/`, `domains/`,
`migrations/` and `locks/`. Stage 5 creates only `runs/`, `rejections/` and `ledgers/` (§2.1); each
remaining directory is created by the stage that first needs it. The layout is not wrong, merely
ahead of what has shipped.

**E10 — CF-1's stated target stage is superseded.** It reads "the stage that first drives candidate
rows concurrently — Stage 5". Stage 5 is sequential by design, so CF-1 moves to whichever stage
first introduces concurrent cell execution (§9.1).

## 12 · What approving this plan does and does not do

**Approving this document approves the plan only.** It authorizes:

- no production code, test, script, config or schema change;
- no filesystem write outside `docs/`;
- not even S5-1.

Each checkpoint S5-1 … S5-C must be approved **separately and by name** before any file outside
`docs/` changes. Green tests, an approved plan, and a completed predecessor checkpoint do **not**
together authorize the next one.
