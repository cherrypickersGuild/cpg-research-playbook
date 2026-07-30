# Stage 7 implementation plan — AX corpus migration

**Status: `APPROVED — PLAN OF RECORD; S7-0, S7-1 AND S7-2 COMPLETE; NO FURTHER CHECKPOINT APPROVED`**

```text
plan opened at        0d2da6454e2ac898094f9b1eebe9a4b6370c79f0   Stage 6 closeout
predecessor boundary  docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_2026-07-30.md
anchor                8865c54e2cc8d879410576f247baac4aea149f34   protected baseline
gate at opening       38/38 suites green — 1,773 unittest + 42 shell = 1,815 assertions
protected baseline    18/18 byte-identical to the anchor
untracked baseline    508/508 byte-identical; drift 0, missing 0, extra 0
runtime paths         none — state/taxonomy_harvest, data/harvested, runs all absent
live requests         none, ever, by this pipeline
```

## 0 · Authority, and what this document does not authorize

**This document is the approved plan of record for Stage 7.** `S7-0` — writing it and the Stage 7
section of `docs/harvest/TODO.md` — is complete. **`S7-1`, the read-only entity assessment, is
complete**; it migrated **zero** entities, which is what it was for. **`S7-2`, the suspicious-URL
guard, is complete**; it refuses URLs and nothing else, and refuses **0 of the 231** protected AX
case pages.

**`S7-3` … `S7-C` remain unapproved**, and nothing in this document approves them: no AX mapping, no
CLI and no apply path exists, and none may be written until the checkpoint that owns it is approved
by name.

- **Approving this plan approves no implementation checkpoint.** Not S7-1, not any later one.
- **Listing a checkpoint's path set here does not authorize that checkpoint.** §9 exists so a
  checkpoint's scope is fixed *before* it is approved, not so approval can be inferred from it.
- **Each later checkpoint requires separate approval by name.** Approval of one grants nothing to the
  next; a completed predecessor authorizes nothing in its successor. This rule held for all fourteen
  Stage 6 checkpoints and for all eight in Stage 5, and it is restated here because it is the rule
  most easily lost between stages.
- **Each checkpoint is limited to the exact path set declared for it in §9.** The commit must contain
  that set and nothing more. If a path outside the set turns out to be genuinely required, the
  checkpoint **stops before editing and requests a plan correction** — it may not widen its own
  scope. That rule is what produced the corrective checkpoints S6-6A and S6-6B, and it is cheaper
  than the alternative. **A path appearing in this plan is not an approval to write it.**
- **Stage 6 remains closed.** It is not reopened, and no Stage 6 decision is revisited unless a
  concrete Stage 7 contract conflict requires it. Six such conflicts were found while writing this
  plan; all six are resolved in §4 **without** reopening Stage 6, and none changes a committed Stage
  6 module.
- **No live request, no promotion, no real runtime migration is authorized.** Stage 7 makes no
  network request of any kind. Nothing is promoted into `data/harvested/`. No checkpoint writes under
  the repository's real `state/taxonomy_harvest/`; every implementation and acceptance run uses an
  injected temporary root. S6-L remains unapproved, unexecuted and not implicitly authorized here.

**Supersession.** `docs/harvest/IMPLEMENTATION_PLAN.md` §11 is **pre-Stage-3 design input**, written
before Stages 3–6 existed and before the contracts they shipped. This plan reconciles it and
**supersedes it wherever the two differ**; the differences are enumerated as errata in §4.
`IMPLEMENTATION_PLAN.md` is not edited by Stage 7.

## 1 · What Stage 7 is

Stage 7 converts the **protected legacy AX case registry** into records of the committed
`record.v1.json` contract, and produces a **read-only assessment** of the entity registry that is
deliberately not migrated.

**Completion boundary.** Stage 7 is complete when, offline and against an injected temporary root:

1. `migrate.sh ax-cases` (dry-run) maps and schema-validates all 231 source cases in memory and
   writes nothing;
2. `migrate.sh ax-cases --apply` publishes exactly one self-contained bundle whose every document
   validates against its committed schema;
3. two applies over identical input produce identical accepted/rejected counts, identical ordered
   `record_id`s and `content_id`s, and byte-identical record payloads after removing only the
   run- and migration-clock-derived fields;
4. an interruption before publication leaves **no** final bundle and no debris;
5. `migrate.sh entity-assess` emits `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md` and
   migrates zero entities;
6. the protected inputs are byte-identical, the 508 untracked paths are byte-identical, no repository
   runtime path was created, and the full taxonomy gate (39 suites once the migration wrapper joins
   it) is green in one run.

**Non-goals, each owned elsewhere:** promotion into `data/harvested/` (§7 of the master plan,
unscheduled) · `refresh` / `linkcheck` / `diff` / `compare-runs` (unscheduled, erratum E11) ·
`validate_task.sh` wiring (Stage 8, CF-4) · threshold or weight calibration (Stage 9) · the bounded
live smoke (Stage 9; S6-L separately) · entity migration proper (a product decision, see D7-J) ·
concurrency (CF-1: any change that runs work concurrently fixes CF-1 first, in its own checkpoint).

## 2 · Inherited boundaries that Stage 7 does not touch

From `HANDOFF_STAGE_6_COMPLETE_2026-07-30.md` §6 and §7, carried forward unchanged:

- source and target request accounting stay **two key spaces**, never summed — Stage 7 adds no
  request of either kind and emits **no** `request_accounting` block at all;
- one fetch per owned canonical target identity — vacuous here: migration fetches nothing;
- deterministic and atomic artifact publication, one serializer and one atomic writer;
- **no resume of a partially published run**; determinism is what makes recovery safe;
- full-record identity fields are the sole property of `records.py` / `urlkey.py`;
- ledger target-evidence persistence and alias-conflict reporting are Stage 6 contracts; **Stage 7
  writes no ledger and no alias-conflict artifact** (it observes no alias and no page);
- the **Stage 6 no-live-request record** stands, and Stage 7 extends it;
- **S6-L is not executed and not implicitly authorized**;
- the unresolved domain-throttle signatures remain **diagnostics, not accepted flakes**;
- **canonical robots evidence remains unwired** — every migrated record therefore carries
  `url_aliases: []` and `canonical_url == identity_url`, which is also what D7-D requires for an
  entirely different reason;
- **CF-1** deferred and guarded · **CF-13** (a post-acceptance inaccessible record has no rejection
  path) · **CF-15** (`urlkey.registrable_host` is the committed authority, best-effort last-two-labels)
  · **CF-16** (`ResponseTooLarge` / `UnexpectedContentType` / `EmptyResponse` collapse onto
  `unreachable`) · **CF-17** (`updated_at` stays null even when `Last-Modified` is present) — all
  carried forward at their current status. **CF-2 / CF-7** are not reopened: `ambiguous_legacy_url`
  is already in both committed rejection enums, so Stage 7 widens no vocabulary.
- **CF-6** applies to any checkpoint that edits `config/`. **No Stage 7 checkpoint edits `config/`**,
  so CF-6 is not triggered; the procedure stays documented for a later stage.
- These modules stay **byte-unchanged** through all of Stage 7: `pool.py`, `httpclient.py`,
  `ledger.py`, `coverage.py`, `facets.py`, `verify.py`, `classify.py`, `extract.py`, `dedupe.py`,
  `facetassign.py`, `records.py`, `artifacts.py`, `run_cells.py`, `targetfetch.py`, `aliases.py`,
  every schema and every config file. None of them appears in any Stage 7 path set (§9), which is the
  enforcement, not merely the intention.

## 3 · Approved decisions

### D7-A · Migration character

The AX migration is **offline**, **copy-on-write**, **non-destructive**, **regenerable from the
protected source registry**, **record-schema-v1 preserving**, and **separate from publication
promotion**. No schema version is introduced or bumped; every field the migration needs has been
storable since Stage 1.

**Inputs are read-only, and are themselves protected files** (entries 12 and 13 of the 18):

- `state/ax_case_harvest_registry.json`
- `state/entity_registry.json`

Neither is ever opened for writing, by any code path, in any mode. Both must still verify
byte-identical against the anchor after every checkpoint.

**The 508 pre-existing untracked paths do not participate in the migration.** None is an input, an
output or a fixture. They remain byte-identical, and that is asserted at every checkpoint.

**Roots are injected.** Stage 7 implementation and acceptance use temporary roots created by the test
or the caller. **A real write under `state/taxonomy_harvest/` is a separate, human-approved
operational action and is not required to close Stage 7.** No checkpoint performs one.

### D7-B · Exact AX migration output layout

`IMPLEMENTATION_PLAN.md` §11's `candidate_output/` sentence described a path that has never existed
in any committed tree (erratum **E22**). It is resolved as follows, and this is the whole layout.

An applied AX migration publishes **exactly one self-contained bundle**:

```text
<state-root>/migrations/<run_id>__ax_cases/
├── manifest.json
├── candidate_output/
│   └── cases__case-studies__harvest.json
└── rejections/
    └── cases__case-studies__rejections.json
```

**Exactly those three files.** The path set is asserted exactly, so an extra file fails as loudly as
a missing one.

Contracts:

| Path | Validates against |
|---|---|
| `manifest.json` | `run_manifest.v1.json` |
| `candidate_output/cases__case-studies__harvest.json` | `cell_artifact.v1.json` |
| `rejections/cases__case-studies__rejections.json` | `rejection.v1.json` |
| every accepted row inside the cell artifact | `record.v1.json` (full-record branch) |

- **No new schema version and no new artifact schema is introduced.**
- **Nothing is written under `runs/`, under `data/harvested/`, or to any `LATEST_RUN_ID`** — not the
  repository-level pointer and not a per-root one.
- **No migration pointer is introduced in Stage 7.** "Which bundle is current" is not a question this
  stage answers; inventing a pointer would create a second ordering contract with no reader.
- The candidate-output directory is **inside** the bundle. There is no shared top-level
  `candidate_output/`.

**Run identity.** The existing committed format is used: `YYYYMMDDTHHMMSSZ-<pid>`, produced by
`artifacts.run_id(clock=…, pid=…)`, both parts injectable. The directory suffix `__ax_cases` is a
property of the **directory name only** and is **not part of `harvest_run_id`** — the three documents
all carry the bare run id.

### D7-C · Atomicity, interruption, and repeated apply

**Dry-run writes nothing.** Not a temp file, not a directory, not a log.

**Apply must:**

1. create a **sibling staging directory outside the final path**, under the same parent, so the final
   rename is same-filesystem (`os.replace` is atomic only within one filesystem);
2. serialize deterministically with the **existing** JSON serializer and atomic file writer —
   `artifacts.serialize`, `artifacts.write_atomic`, `artifacts.write_document`;
3. **validate every document before publication** — `write_document` validates first, so an invalid
   document leaves the filesystem exactly as it was;
4. publish the complete bundle with **one final same-filesystem directory rename**;
5. leave the final bundle **absent** if interrupted before that rename — a reader sees a complete
   bundle or no bundle, never a partial one;
6. sweep its own staging files and directories, and **only** its own: a foreign staging path is left
   strictly alone (the S5-7 sweeper contract);
7. **refuse an already-finished identical `run_id` before writing anything**, checked before the
   source registry is even read;
8. implement **no resume semantics**. An interrupted apply is retried as an ordinary fresh apply.

**Do not reimplement the serializer or the atomic JSON writer.** There is one of each and Stage 7
uses it.

**Repeated apply.** Two applies with **different run ids** over identical input must produce:

- the same accepted and rejected counts;
- the same **ordered** `record_id` list;
- the same **ordered** `content_id` list;
- **byte-identical record payloads** after explicitly removing only the run- and
  migration-clock-derived fields — enumerated exhaustively, by recursive diff, never normalized away:
  `harvest_run_id` (manifest, cell artifact, rejection log), `generated_at`, `started_at`,
  `finished_at`, `rejected_at`, and `provenance.migration.migrated_at`. A sixth moving field fails
  the test rather than passing silently (the S5-7 / E19 discipline).

**"Apply twice, 231 stable" does not mean overwriting the first bundle or accepting the same run id
twice** (erratum **E28**). Two applies produce two bundles side by side; the second neither replaces
nor mutates the first, and an identical finished run id is refused per rule 7.

### D7-D · Honest evidence status

**The `verified → fetched` mapping from §11 is not preserved** (erratum **E23**). `record.v1.json`
defines `fetched` as "the fetch succeeded", and the schema's own description says the legacy field of
that name "was routinely misread as an editorial judgement". Stage 6 fixed the difference between a
fetched and an unfetched record at exactly six fields. A migration performs **no HTTP request**, so
it may not claim any of them.

**Every accepted migrated record carries:**

```text
access_status      "not_checked"
http_status        null
last_checked_at    null
content_hash       null
canonical_url      == identity_url
url_aliases        []
```

**Verification mapping — deterministic, two branches:**

- a non-empty retained `evidence_quote` ⇒ `verification_status: "snippet_only"`, and that exact quote
  is retained as `verification_evidence`;
- otherwise ⇒ `verification_status: "unverified"`, `verification_evidence: null`.

The original legacy `verification_status` is **unchanged in `provenance.raw`**, under its original
name and value.

`provenance.migration.assumptions` states, in fixed wording, that **no URL was refetched and no
current accessibility claim is made**.

**A migrated record may never claim `fetched` merely because the legacy registry once used the word
`verified`.** Measured against the corpus at HEAD: 208 cases say `verified` and 23 say
`snippet-only`, and **all 231 carry a non-empty `evidence_quote`** — so all 231 accepted records
become `snippet_only`, and the legacy distinction survives only in `provenance.raw`. That is the
honest outcome: neither value was ever a claim about the page being reachable today.

### D7-E · Target cell and classification

Every accepted AX case maps to:

```text
topic             "cases"
primary_category  "case-studies"
cell_id           "cases__case-studies"
record_type       "full"
```

**The ordinary ten-rule precedence classifier is neither called nor imitated.** `classify.py` is not
imported by any migration module, and a test asserts that.

Every accepted record carries **one deterministic migration-specific classification object**:

```json
{
  "rule_id": "migration.ax_case_registry.case_study",
  "rationale": "Assigned by migration: the protected AX case registry is an already-curated case-study corpus, so the destination cell is fixed by the source, not by discovery classification.",
  "evidence": [{ "signal": "legacy_registry", "matched": "ax_case_harvest_registry" }],
  "competing_categories": []
}
```

The rule id is namespaced `migration.` so no reader can mistake it for one of the ten committed
precedence rules (`R1`…`R10`). The evidence identifies the legacy registry as the classification
source and **does not claim that ordinary discovery classification ran**.

`records.make_full_record` substitutes an `R10_default_by_category` classification when the parameter
is `None`; the migration therefore always passes its own object explicitly and never relies on that
default. A test pins that the default never appears on a migrated record.

**`cases__domain-applications` is not the migration destination.** It is the facet-gated cell; a
corpus whose facets are mostly partial by construction does not belong behind a gate that would
withhold it.

### D7-F · Facet representation

**Every accepted migrated AX record carries a `case_facets` object**, including in the report-only
`cases__case-studies` cell. Absence would mean "enrichment was never attempted"
(`reporting_state: not_enriched`) and would hide the legacy industry value — which is exactly what
`check_facets.py`'s committed migrated-record rule refuses.

Only the committed vocabularies and the reviewed legacy-industry map are used. **No facet config and
no generated facet schema is edited in Stage 7.** `facets_version: 1` and `vocabulary_versions` are
read from `facets.vocabulary_versions()`, never hard-coded.

**Industry axis — four exhaustive branches, evaluated in this order:**

1. **Mapped, and the committed lexical-support gate accepts it** —
   `facets.lookup_legacy_industry(value)` returns a slug **and**
   `facets.evidence_supports("industry", slug, evidence)` is true for the legacy evidence item:
   - `industry.primary` = the reviewed mapped slug;
   - `industry.secondary` = `[]` — **no secondary industry ever** (CF-11: secondary means deployment
     context, never corporate portfolio, and lexical evidence cannot make that judgement);
   - one evidence item: `field: "legacy_field"`, `matched_term` and `quote` both the **exact** legacy
     string, unmodified;
   - `confidence: 1.0`, meaning **deterministic confidence in the reviewed mapping** — never
     confidence in URL verification, which did not happen.
2. **Mapped, but the committed lexical-support gate refuses it** (erratum **E27**) — no primary is
   asserted, and an `unresolved[]` entry is added: `axis: "industry"`, `state:
   "insufficient_evidence"`, `term` = the exact legacy value, and a deterministic detail naming both
   the reviewed slug and the gate that refused it. It is **not** `unmapped_legacy_value`: the value
   *is* mapped, and mislabelling it would send a reviewer to fix a map that is already correct.
   Asserting it anyway would fail `check_facets.py`.
3. **Non-empty and unmapped** — no primary; an `unresolved[]` entry with `axis: "industry"`,
   `state: "unmapped_legacy_value"`, `term` = the exact legacy value, and a deterministic
   explanatory detail. The unmapped string appears **only** in `term` — never as a `matched_term` or
   `quote` on any asserted value, which `check_facets.py` refuses outright.
4. **Missing or blank** — `state: "insufficient_evidence"`, not `unmapped_legacy_value`. There is no
   value to map, and reporting one would send a reviewer to look for a string that does not exist.

**Business-function and use-case-type axes.** Migration **infers neither**. Both asserted-value
arrays stay `[]`, and each axis gets an explicit `unresolved[]` entry with
`state: "insufficient_evidence"` and a deterministic detail. Nothing about a KPI sentence licenses a
function or use-case label, and `facetassign.py` is not called.

**`classification_state` is obtained by calling `facets.decide_classification_state(case_facets)`**
and written from its return value. It is never caller-asserted, and `check_facets.py` recomputes it.

**Consequences, stated so they are not discovered later as surprises:**

- a record with an assertable mapped industry and no functions or use-cases computes
  `classification_state: "unresolved"` and reports `facet_partial`;
- an unmapped-industry record reports `unmapped_legacy_value` (rule 1 of the reporting precedence
  outranks everything);
- a branch-2 record reports `unresolved` — nothing is populated and the reason is recorded;
- `classification_state == "unresolved"` requires at least one `unresolved[]` entry, which every
  migrated record has by construction;
- because `cases__case-studies` is in `FACET_REPORT_ONLY_CELLS`, **no facet state withholds any
  record** — `facets.is_publication_eligible` is true for all of them, and facet states are counted
  and reported, never a gate;
- **`check_facets.py --record` must pass on every accepted record**, and S7-6 runs it over the whole
  published cell artifact.

**Measured expectation over the corpus at HEAD `0d2da64`** (asserted by S7-3 and S7-6, not assumed):
231 cases, 0 blank industries, 173 distinct values; **113 records carry a mapped value, 118 an
unmapped one**; exactly **one** mapped value (`"IT services"` → `technology-software`, 1 record) is
refused by the lexical-support gate. Expected reporting states: **112 `facet_partial` · 118
`unmapped_legacy_value` · 1 `unresolved` · 0 `facet_complete` · 0 `not_enriched`**, summing to 231.
The shortest distinct legacy industry value is 6 characters, so the schema's `matched_term`
(min 2) and `quote` (min 3) minimums are satisfied by every mapped value.

### D7-G · Scores and otherwise unknown fields

Migration does **not** invoke Stage 4 verification, scoring or relevance. `verify.py` is not imported
by any migration module, and a test asserts that.

All four required score fields are **null**:

```text
relevance_score  quality_score  audience_fit_score  freshness_score
```

Null is admitted by the committed `score` definition (`number|null`) and is the honest value: no
score was computed. A null freshness is deliberately not 0.0, which would assert the item is old.

Honest unknown/default values where the legacy schema has no evidence:

```text
content_type  "other"      the legacy schema records no content type
author        null         no author field exists
language      null         never recorded, never guessed from the URL
updated_at    null         no update signal exists, and CF-17 forbids inventing one
duplicate_of  null         no duplicate adjudication is performed
rejection_reason  null     for every accepted record
```

**No score, date, author, language or content type is invented.**

### D7-H · Suspicious-URL rule vocabulary

Exactly the **four committed override rule ids** are used, and `config/harvest/migration_overrides.v1.json`
is **not edited** — not to add synonyms, not to add rules:

```text
search_engine_host · search_query_path · feed_path · index_page
```

The detailed patterns from the master plan group under those four ids:

| Rule id | Fires when |
|---|---|
| `search_engine_host` | the URL's **full host** equals a committed search-engine host, or begins with the label `search.` |
| `search_query_path` | the path's **last segment** is `search`, **or** a query parameter named `q`, `query` or `s` is present |
| `feed_path` | the path's **last segment** is `feed`, `rss` or `atom` |
| `index_page` | `raw.githubusercontent.com` + a path ending `README.md`; **or** a path segment beginning `awesome-`; **or** a `tag` or `category` path segment; **or** a trailing `/page/<n>` |

**Precedence (clarified at S7-2, the one design clarification that checkpoint was authorized to
make).** A URL can satisfy more than one rule — `https://www.google.com/search?q=x` satisfies the
first two, `https://example.test/tag/ai/feed` the last two. The rule ids above are an **ordered**
constant and the **first match wins**, in exactly that order: `search_engine_host` ·
`search_query_path` · `feed_path` · `index_page`. The order runs from the most specific claim about
the URL's origin to the most general claim about its shape, so the reported rule is the strongest
thing known about the URL. It is deterministic and pinned in both directions by the suite: one rule
never masks a lower one that fires on its own.

**The predicates are matched on structure — host equality and path segments — never on substrings**
(erratum **E24**). Measured against the corpus at HEAD: a literal substring reading of §11's wording
rejects **5 of 231 legitimate case pages** (4 `cloud.google.com` vendor-blog URLs caught by
`google.`, and one LinkedIn engineering article whose path contains a `/search/` segment); under the
structural predicates above, **0 of 231** trip the guard. The expected count is **asserted by the
checkpoint, not assumed**, and a fixture proves each of the four rules can actually fire.

The guard runs **before accepted-record construction** and **never rewrites a URL**. It only refuses.

**For a rejected candidate:**

- the **raw legacy URL is retained as `target_url`** in the rejection row, verbatim;
- a canonicalized form may appear **only** as the rejection row's required `identity_url`, because
  the schema requires that key — it is never presented as the case's page;
- **no accepted `record_id` or `content_id` is created** for it;
- the rejection row's `detail` deterministically names the **exact matched rule id** and the **legacy
  case id**; `rejection_reason` is `ambiguous_legacy_url`, already in both committed enums.

**Override semantics** (`config/harvest/migration_overrides.v1.json`, read, never written):

- a reviewed `admit` means a human confirmed the raw URL is the case's own page — the record is
  migrated **verbatim**, with no URL rewriting;
- a reviewed `reject` stays rejected, and is acknowledged as reviewed rather than reported as an
  outstanding to-do;
- `--allow-unmappable` **only permits completion with unresolved rejections**. It **never** admits a
  record and never rewrites a URL.

**The complete rejection list appears in the dry-run report and in the applied rejection artifact.**
Neither truncates.

### D7-I · Migration manifest

The manifest is a `run_manifest.v1.json` document with:

- `mode: "migration"` — already in the committed enum;
- the normal committed run-id format (D7-B);
- **exactly one cell row**, for `cases__case-studies`, carrying accurate `candidates`, `accepted` and
  `rejected` counts and a `status` of `ok` or `zero_result`;
- `source_preflight: []` — there is no source to preflight;
- `classification_decisions: []` — no content was seen in more than one topic;
- **no `request_accounting` block at all**, because migration makes no request. Emitting one with
  zeros would put a migration into a key space that exists to count fetches;
- `publication_eligible: false`, **derived** by the committed
  `artifacts.derive_publication_eligibility("migration", …)`, which returns false for any non-harvest
  mode and again for records that are all `not_checked`. It is never caller-forced to true, and a
  test asserts a caller cannot supply it.

**Twelve fictitious configured-cell rows are not emitted.** The committed
`artifacts.build_run_manifest` starts from `configured_cell_rows()` and always produces all twelve,
refusing any `cell_id` outside them — correct for a harvest run, wrong for a migration that ran no
cell (erratum **E25**). Since `artifacts.py` is in **no** Stage 7 path set and must stay
byte-unchanged, the migration **composes its manifest document itself**, inside
`src/harvest/migrate/`, and writes it through the committed `artifacts.write_document`, which
validates it against `run_manifest.v1.json` before a byte is serialized. The schema's `cells` array
has no minimum, so a one-row manifest is a valid manifest.

**The migration manifest describes the AX migration only.** The entity-registry non-migration is
recorded in the assessment document (D7-J) and in the Stage 7 completion handoff — **not** in the AX
run manifest, which would otherwise assert something about a corpus it never read.

### D7-J · Entity registry boundary

`migrate.sh entity-assess`:

- reads `state/entity_registry.json` **without modifying it** (a protected path, verified after);
- **migrates zero entities**;
- emits **no taxonomy record and no migration bundle**;
- produces `docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md`;
- reports counts by topic and entity type, schema and key shapes, candidate destination taxonomies,
  fields that cannot be mapped safely, duplicate risks, and `entity_id` stability risks (per
  `docs/entity_id_collision_note.md`, `entity_id` is not globally unique);
- **records explicitly that the destination taxonomy remains an open product decision.** No `Dev
  Tools` topic, or any other, is invented to receive them.

The implementation is **deterministic and testable against an injected output path**: the document is
**generated from the protected input**, not hand-written, and a test proves regeneration is
byte-stable and that the committed document matches what the generator produces.

### D7-K · Dry-run and apply CLI

`scripts/harvest/migrate.sh` exposes exactly three invocations:

```text
migrate.sh ax-cases                 dry-run (the default)
migrate.sh ax-cases --apply         publish one bundle
migrate.sh entity-assess            read-only assessment
```

**AX dry-run:**

- maps and schema-validates the **full** source in memory;
- makes **no repository or runtime write** of any kind;
- reports the source count, accepted count, rejected count and the **complete** rejected list;
- **exits non-zero** when an unresolved suspicious URL remains — unless every one is reviewed in
  `migration_overrides.v1.json` or `--allow-unmappable` is supplied.

**AX apply:**

- remains **offline**;
- defaults to an expected source count of **231** and **fails loudly on any other count** unless
  `--expect-count N` is explicitly supplied;
- requires an **injectable state root** for tests;
- **never opens the source registry for writing**;
- performs **no promotion**.

**No actual apply against the repository's real state root is authorized by any implementation
checkpoint.**

## 4 · Errata against `IMPLEMENTATION_PLAN.md` §11 and §14

Numbering continues from Stage 6's E21; none is renumbered.

```text
E22  §11's `candidate_output/` names a path no committed tree has ever had, and no committed path
     builder produces. Resolved by D7-B: it is a directory INSIDE the migration bundle, and the
     bundle's three paths are the whole layout.
E23  §11's `verified → fetched` remap contradicts record.v1.json's own definition of `fetched` and
     the Stage 6 six-field evidence contract. Resolved by D7-D: snippet_only / unverified, and the
     legacy value survives verbatim in provenance.raw.
E24  §11's guard wording, read as substring matching, rejects 5 of 231 legitimate case pages
     (measured). Resolved by D7-H: host equality and path segments, never substrings; expected 0
     rejections, asserted rather than assumed.
E25  artifacts.build_run_manifest always emits all 12 configured cell rows and refuses a cell_id
     outside them — correct for a harvest, wrong for a migration that ran no cell. Resolved by D7-I:
     the migration composes its own manifest document and writes it through the committed validating
     writer; artifacts.py stays byte-unchanged.
E26  §11 maps legacy_ids.id to `case_id`, which is NOT unique: 126 distinct case_ids over 231 cases
     (measured). `case_key` is unique (231/231). Resolved in §5: both are retained, `case_id` as a
     legacy label and `case_key` as `.key`; record identity remains derived solely from the URL, and
     the 231 source URLs canonicalize to 231 distinct identity_urls with zero collisions (measured).
E27  check_facets' lexical-support gate refuses `technology-software` grounded on the legacy string
     "IT services" (1 record). Resolved by D7-F branch 2: reviewed-but-unsupportable never asserts a
     primary; it records insufficient_evidence naming the slug and the gate.
E28  §14's "apply twice" is about record stability, not about reusing a run id or overwriting a
     bundle. Resolved by D7-C: two applies, two run ids, two bundles, identical normalized records.
```

## 5 · Complete legacy → record mapping

Every **required** `full_record` field appears below, plus every optional field the migration sets.
**No required field is left to implementation judgement.**

`"unknown"` → `null` everywhere, with the original always retained in `provenance.raw`.

| Record field | Source / value | Rule |
|---|---|---|
| `schema_version` | `records_mod.SCHEMA_VERSION` | const 1, from the module |
| `record_type` | `"full"` | D7-E |
| `record_id` | `urlkey.record_id("cases", identity_url)` | committed helper; never derived from `case_id` |
| `content_id` | `urlkey.content_id(identity_url)` | committed helper |
| `topic` | `"cases"` | D7-E |
| `primary_category` | `"case-studies"` | D7-E |
| `cell_id` | `"cases__case-studies"` | D7-E |
| `tags` | `[industry, ai_system_or_tool]` | trimmed; `"unknown"`/blank dropped; deduplicated; **sorted**; `uniqueItems` holds by construction |
| `title` | `source_title` | `"unknown"` → null |
| `summary` | composed from `workflow_before` / `workflow_after` / `ai_system_or_tool` | one fixed deterministic template; a null part is **omitted**, never rendered as the word "unknown"; all three null ⇒ summary null |
| `curation_reason` | composed from `measurable_kpi` / `kpi_value` / `evidence_quote` | same rule, same template discipline |
| `source_url` | **`null`** | the legacy schema has no separate feed, index, search or citing URL. Schema-admitted and documented for exactly this case |
| `target_url` | `source_url` | **verbatim, unmodified** — the case's own page |
| `identity_url` | `urlkey.canonicalize_string(target_url, …)` with the committed `canonicalization.v1.json` | immutable; 231 → 231 distinct, zero collisions (measured) |
| `canonical_url` | `= identity_url` | D7-D — no fetch, so no canonical evidence exists |
| `url_aliases` | `[]` | D7-D |
| `publisher` | `source_domain` | `"unknown"` → null |
| `author` | `null` | D7-G |
| `published_at` | `publication_date` via `records.to_iso8601_utc` | 33 values are exactly `"unknown"` → null (measured); no other value fails to parse |
| `updated_at` | `null` | D7-G / CF-17 |
| `discovered_at` | `discovery.first_seen_at` via `records.to_iso8601_utc` | all 231 parse (measured); date-only becomes `T00:00:00Z` |
| `last_checked_at` | `null` | D7-D |
| `content_type` | `"other"` | D7-G |
| `language` | `null` | D7-G |
| `access_status` | `"not_checked"` | D7-D |
| `http_status` | `null` | D7-D |
| `verification_status` | `"snippet_only"` when a non-empty `evidence_quote` is retained, else `"unverified"` | D7-D; all 231 have one (measured) |
| `verification_evidence` | the retained `evidence_quote`, else `null` | D7-D |
| `relevance_score` | `null` | D7-G |
| `quality_score` | `null` | D7-G |
| `audience_fit_score` | `null` | D7-G |
| `freshness_score` | `null` | D7-G |
| `duplicate_of` | `null` | D7-G |
| `content_hash` | `null` | D7-D |
| `harvest_run_id` | the bundle's run id | D7-B; without the `__ax_cases` suffix |
| `classification` | the fixed `migration.ax_case_registry.case_study` object | D7-E; passed explicitly, never defaulted |
| `provenance.source_id` | `"ax_case_harvest_registry"` | the protected registry, named once |
| `provenance.source_adapter` | `"migration"` | already in the committed enum |
| `provenance.source_tier` | `null` | CF-9: no configured source declares a tier |
| `provenance.discovered_via` | `discovery.found_via[]` | `{hit_id, platform}` — **never treated as a URL**, as the schema says in so many words |
| `provenance.raw` | **the complete original case object, original field names intact** | including `source_url`, `industry` and the legacy `verification_status` under their own names; nothing dropped |
| `provenance.migration` | `{adapter, migrated_at, assumptions[]}` | `adapter: "ax_cases"`; `migrated_at` from the injected clock; `assumptions` states no refetch and no accessibility claim (D7-D) |
| `legacy_ids` | `[{system: "ax_case_harvest_registry", id: case_id, key: case_key}]` | E26: `case_id` is a label (126 distinct / 231), `case_key` is unique; neither is an identity |
| `domain_fields` | `company`, `industry`, `workflow_before`, `workflow_after`, `ai_system_or_tool`, `measurable_kpi`, `kpi_value`, `evidence_quote`, `transformation_date`, `confidence`, `corroboration_count`, `conflicting_evidence_log` | surfaced **and** retained in `provenance.raw`; nothing dropped. `transformation_date` stays a domain field and is **never** conflated with `published_at` |
| `case_facets` | per D7-F | always present on an accepted record |
| `rejection_reason` | `null` for accepted records | D7-G |
| `link_history` | omitted | no link check ran |
| `multi_topic` / `multi_topic_reason` | omitted | one topic, no cross-topic decision |

**Rejected candidates** produce no record at all. They appear only as rejection rows:
`identity_url` (required by the schema), `target_url` = the **raw** legacy URL, `source_id` =
`"ax_case_harvest_registry"`, `title` = `source_title`, `rejection_reason` =
`"ambiguous_legacy_url"`, `detail` naming the matched rule id and legacy case id, `rejected_at` from
the injected clock, `scores` omitted (nothing was scored).

## 6 · Measured corpus facts

Measured read-only at HEAD `0d2da64` while writing this plan. Each is **asserted by a checkpoint**,
never assumed at implementation time; if the corpus changes, the assertion fails and the plan is
corrected rather than the number quietly updated.

```text
cases                          231     schema_version + last_merged_at + cases[]
fields per case                20      exactly those §11 names — no drift
unique source_url              231
distinct identity_url          231     zero canonicalization collisions
unique case_key                231
distinct case_id               126     NOT unique — see E26
industry blank                 0
distinct industry values       173     113 records mapped · 118 unmapped
lexical-support refusals       1       "IT services" → technology-software
publication_date "unknown"     33      → published_at null
publication_date otherwise     198     all parse
first_seen_at parse failures   0
legacy verification_status     208 "verified" · 23 "snippet-only"
evidence_quote empty           0       ⇒ all 231 become snippet_only
suspicious-URL hits            0       under the D7-H structural predicates (5 under a substring reading)
```

## 7 · What Stage 7 must not introduce

- **future-file-absence guards** — a boundary test asserts facts about the surface of the module
  under test, never which files exist yet;
- **raw-token blacklists** over source text;
- **new byte-freeze assertions over unrelated production modules** — the existing ones are not
  extended to modules Stage 7 has no relationship with;
- **a duplicate serializer, atomic writer, HTTP client or path-building convention** — there is one
  of each and Stage 7 uses it; the three bundle paths are built once, in `migrate/base.py`, and
  nowhere else;
- **live access** of any kind;
- **promotion**;
- **resume semantics**;
- **concurrency** — every migration path is sequential, keeping CF-1 untriggered.

## 8 · Validation policy

| Tier | Applies to | Validation |
|---|---|---|
| **L0 — documentation only** | S7-0, S7-C | exact declared-path diff · `git diff --check` · nothing touched outside the set · protected baseline 18/18 · untracked baseline 508/508 · no runtime path created. **No focused suite and no full gate.** |
| **Pure / additive** | S7-1, S7-2, S7-3 | focused migration suite · the directly affected contract suites (`test_taxonomy_records.sh`, `test_taxonomy_schema.sh`, `test_taxonomy_identity.sh`, `test_taxonomy_facets.sh` as applicable) · `check_config.py`, `check_facets.py`, `gen_facet_schema.py --check`, `check_fixtures.py`, `verify_protected_baseline.sh` · then the **full taxonomy gate once** |
| **Filesystem-writing** | S7-4, S7-5 | the above · injected temp-root isolation · deterministic bytes over two runs · interruption and atomicity · the runtime-leak check (`state/taxonomy_harvest`, `data/harvested`, `runs`, `LATEST_RUN_ID` absent) · then the **full gate once** |
| **Integration** | S7-6 | the complete Stage 7 acceptance set of §9 · then the **full gate once** |

- **`scripts/validate_task.sh` remains Stage 8 and is not edited by any Stage 7 checkpoint.**
- The migration wrapper joins `tests/test_taxonomy_*.sh`, so **the full gate becomes 39 suites** once
  it is introduced. Both the suite count and the assertion total are restated at each checkpoint.
- **No gate is rerun repeatedly merely to obtain green after an unrelated failure.** A failure is
  diagnosed and either fixed or recorded.
- **Domain-throttle diagnostics and the existing no-permanent-flake policy are unchanged.** The
  unresolved throttle signatures remain diagnostics, not accepted flakes.
- Every suite runs offline with no socket, as every taxonomy suite already does.

## 9 · Checkpoint decomposition

**S7-1 and S7-2 are complete. None of the remaining checkpoints is approved.** Each requires separate
approval by name, and each is limited to the exact path set below. Every checkpoint includes updates to this
plan and to `docs/harvest/TODO.md`.

### S7-1 · Entity assessment — **COMPLETE**

Read-only assessment; migrates nothing. Owns D7-J.

```text
src/harvest/migrate/__init__.py
src/harvest/migrate/entity_assess.py
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

**As shipped.** `entity_assess.py` separates four layers — `load_registry()` validating the expected
shape, `assess()` deriving the data, `render()` producing the Markdown, and `write_assessment()`, the
only function that touches the filesystem and only at an explicitly supplied path. The analysis and
the renderer are called directly by the suite; no shell script is involved. There is no clock, no
network, no git state, no absolute path, no module-global mutable state, and no reliance on input
order: every grouping is sorted by a total key, and reversal plus three seeded shuffles are each
asserted non-vacuous and each render byte-identical output. A malformed top level, a malformed row, a
missing required field, an **unrecognised** field, a bad `discovery` block and a non-array `found_via`
all raise `AssessmentError` naming the row and the field — nothing is skipped, because a skipped row
would make every count wrong by an unknown amount.

The committed document is **generated by the module and never hand-edited**; the suite compares the
committed bytes against a fresh render, so drift fails rather than accumulates. Counts are reconciled
three ways — derived against the registry's own `metadata`, against the expected corpus size, and by
subtotals that must sum to the population — and each reconciliation is proved to *notice* a dropped
or moved row.

**Measured, and asserted rather than assumed** (`state/entity_registry.json`, `schema_version` 2,
`last_merged_at` `2026-07-22T03:17:22Z`):

```text
entities                 1,161      migrated: 0
topics                   agent 293 · mcp 305 · prompt 204 · skill 359
entity types             16 values; 22 of 64 topic x type pairs populated
description_source       verified 975 · snippet-only 186
entity_id distinct       721 of 1,161 — NOT unique
repeated entity_id       51 values reused by 491 rows; largest group 23
                         49 of the 51 span more than one topic
topic-qualified ids      831 of 1,161 — topic qualification does NOT repair it
entity_key distinct      1,161 of 1,161 — the only unique key, and a merge artefact
exact duplicate rows     0 — every repeat is a repeated IDENTIFIER, not a repeated row
usable target_url        1,024 of 1,161; 137 carry the "unknown" sentinel
shared target_url        36 URLs shared by 77 rows
distinct usable targets  983 across 231 hosts
found_via drift          1,247 items, 40 of them empty objects
```

Two of those are structural blockers on any URL-identified migration, and the assessment says so
without proposing a fix: **137 rows have no URL to derive an identity from**, and **77 rows share a
URL with another row**, so URL-derived identity would merge entities the registry treats as distinct.
`docs/entity_id_collision_note.md` recorded the `entity_id` collision qualitatively; the numbers above
are its current extent. **No replacement identifier is selected or proposed** — that is a product
decision, and it is item 2 of the document's follow-up checklist.

**Validation:** focused suite `tests/test_taxonomy_migration.sh` — **43 assertions**; then the full
gate once — **39/39 suites green, 1,858 assertions (1,816 unittest + 42 shell)**; then all five
checkers exit 0. The protected registry is byte-identical before and after, asserted inside the
suite; the 18 protected files and the 508 untracked paths are unchanged; no runtime path was created;
no request of any kind was made.

### S7-2 · Migration base and suspicious-URL guard — **COMPLETE**

The four rule ids, the structural predicates, the override reader, the bundle path builders. Pure —
no filesystem output. **No config edit.**

```text
src/harvest/migrate/base.py
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

**As shipped — the guard only.** S7-2 delivered the minimal foundation the guard needs and nothing
else: **the override reader and the bundle path builders were NOT written**, because neither is
required to decide whether one URL is suspicious, and a checkpoint does not build what it does not
need. They stay available to the checkpoint that first has a caller for them.

Public surface, four names:

```text
SUSPICIOUS_RULE_IDS       ("search_engine_host", "search_query_path", "feed_path", "index_page")
                          one immutable ordered constant — the vocabulary AND the precedence
MigrationInputError       input that is not an absolute http(s) URL. Deliberately NOT one of the
                          four verdicts: "not a URL" and "a search page" are different findings
GuardMatch                frozen, value-comparable, exactly two fields: rule_id and detail. There
                          is no field that could carry a replacement URL
suspicious_url_match(url) the complete match, or None
looks_like_index_or_search(url)   the boolean convenience predicate, delegating to the above
```

**Precedence is first-match in the constant's order**, pinned in both directions:
`https://www.google.com/search?q=ai` → `search_engine_host`; `https://example.test/tag/ai/feed` →
`feed_path`; and each lower rule still fires on its own when no higher one does.

**`urlkey.registrable_host` is deliberately not used**, and a test asserts `base.py` imports exactly
`dataclasses` and `urllib.parse`. The registrable domain of `cloud.google.com` is `google.com`, so
resolving hosts that way would reintroduce the E24 defect. Host **equality** against a committed
full-host set — plus a first-label `search.` check — is the contract. No second canonicalizer,
registrable-domain parser or URL normalizer was created.

**Refusal only.** The guard never rewrites, repairs, percent-decodes or prepends a scheme; the raw
input is examined and returned untouched, and the suite asserts the detail text contains no URL at
all. `config/harvest/migration_overrides.v1.json` is **read by a test to prove the four ids match its
declared `matched_rule` vocabulary** and is otherwise untouched.

**Measured against the protected AX corpus: `0 of 231` suspicious URLs** — and the zero is proved
non-vacuous rather than asserted: the corpus is checked to be exactly 231 rows with non-empty
absolute URLs, and ten fabricated positives run through the same loop and are all refused. Each of
the four rules has at least two positive examples; the negative controls include all four
`cloud.google.com` vendor-blog URLs, the E24 LinkedIn article with its interior `/search/` segment,
`research.example.com`, `/feeds/latest`, `/tags/ai`, `/awesome/thing`, `?faq=1`, `?queryset=1`,
`?ref=query`, and `github.com/.../README.md` (the README rule is scoped to
`raw.githubusercontent.com` and is not generalised).

**Validation:** focused `tests/test_taxonomy_migration.sh` **71 assertions (43 S7-1 + 28 S7-2)**,
plus `identity` 42, `records` 51 and `schema` 35; then the full gate once — **39/39 suites,
1,886 assertions (1,844 unittest + 42 shell)**; then all five checkers exit 0. The S7-1 assessment
still regenerates byte-identically; both protected registries are byte-identical; no runtime path was
created; no request of any kind was made.

### S7-3 · In-memory AX mapping

The §5 mapping, D7-D…D7-G, validated against `record.v1.json` in memory. **No filesystem output.**

```text
src/harvest/migrate/ax_cases.py
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

### S7-4 · CLI and dry-run

```text
scripts/harvest/migrate.sh
src/harvest/migrate/base.py
src/harvest/migrate/ax_cases.py
src/harvest/migrate/entity_assess.py
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

### S7-5 · Atomic apply and repeated-run semantics

D7-B's bundle and D7-C's protocol. **All apply validation uses an injected temporary root.**

```text
src/harvest/migrate/base.py
src/harvest/migrate/ax_cases.py
scripts/harvest/migrate.sh
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

### S7-6 · Final migration integration

```text
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

This checkpoint owns, and proves:

- **apply twice with stable normalized records** — identical counts, identical ordered `record_id`
  and `content_id` lists, byte-identical payloads after removing only the six enumerated
  clock-derived fields;
- **the exact bundle path set** — three paths, asserted exactly;
- **interruption and no partial publication** — the final bundle absent, no debris, retry as an
  ordinary fresh apply;
- **protected-source byte identity** — both registries unchanged, 18/18 after;
- **no repository runtime leak** — `state/taxonomy_harvest`, `data/harvested`, `runs`,
  `LATEST_RUN_ID` all still absent;
- the **final focused and full Stage 7 gate**, in one run.

### S7-C · Closeout

Documentation only, L0 validation only.

**Its exact documentation path set is not declared here, and no handoff filename is pre-authorized or
guessed.** S7-C requires **its own read-only closeout preflight** to establish that set — the same
discipline that let Stage 5 and Stage 6 close without the authorization gap that hit Stage 4.

## 10 · Not Stage 7

Recorded so they are not absorbed by accident: entity migration proper and its destination taxonomy
(a product decision) · promotion into `data/harvested/` · `refresh` / `linkcheck` / `diff` /
`compare-runs` and the promotion transaction journal (unscheduled, E11) · `validate_task.sh` wiring
(Stage 8, CF-4) · threshold calibration (Stage 9) · the bounded live smoke and S6-L · cleaning or
gitignoring the 508 pre-existing untracked paths · matrix convergence · the GitHub star backfill and
the harvest→pipeline bridge in the legacy pipeline.
