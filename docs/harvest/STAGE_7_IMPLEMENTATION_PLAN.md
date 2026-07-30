# Stage 7 implementation plan — AX corpus migration

**Status: `COMPLETED — STAGE 7 CLOSED`**

**Completion handoff:** `docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md`

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
case pages. **`S7-3`, the in-memory AX mapping, is complete**; it maps **231 accepted / 0 rejected**
and writes nothing at all. **`S7-4`, the CLI and dry-run, is complete**; `migrate.sh ax-cases`
reports and writes nothing, and **`--apply` is refused**.

**`S7-5`, the atomic apply, is complete**; it publishes one three-file bundle by a single directory
rename, and **every apply in this repository so far has been to an injected temporary root** — the
real `state/taxonomy_harvest/` does not exist.

**`S7-6`, the integration proof, is complete**; it added no capability and proved S7-1 … S7-5 are one
offline workflow, with every apply confined to a temporary state root that no longer exists.
**`S7-C`, the closeout, is complete through this documentation closeout commit.**

**STAGE 7 IS CLOSED.** The durable summary is
`docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md`.

**Closure approves nothing.** A **push** (`origin/main` is at `0d2da64`; all Stage 7 commits are
local-only), an **operational apply** against the repository's default `state/taxonomy_harvest/`
root, **promotion** into `data/harvested/`, **network or live activity**, and **Stage 8**
(`validate_task.sh` wiring, CF-4) each remain **unapproved** and each needs its own explicit
approval. A completed stage and a green gate do not together open the next one.

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
E29  S7-4's report family was misnamed as a MODE. `REPORT_TYPE = "ax_cases_dry_run"` named one
     execution mode even though the report already carries `operation: "ax-cases"` and a
     `dry_run` boolean, so an apply result would have been published under a false label.
     Resolved at S7-5: `report_type: "ax_cases"` names the stable AX-migration report FAMILY;
     `report_version` stays 1; `operation` is unchanged; `dry_run` is the sole dry-run/apply
     discriminator; the sixteen-field shape is unchanged. No `ax_cases_apply` type, no alias, no
     compatibility value, and no version bump — the shape never changed and the old value was a
     false label rather than a separate valid family. The S7-4 shipped description and its
     assertion were corrected in the same checkpoint.
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

**S7-1 … S7-6 and S7-C are complete; Stage 7 is closed.** Each was approved separately by name and
limited to its declared path set — S7-C's established by its own read-only closeout preflight. Every checkpoint includes updates to this
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

### S7-3 · In-memory AX mapping — **COMPLETE**

The §5 mapping, D7-D…D7-G, validated against `record.v1.json` in memory. **No filesystem output.**

```text
src/harvest/migrate/ax_cases.py
tests/harvest/test_migration.py
tests/test_taxonomy_migration.sh
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

**As shipped.** Public surface, three names plus the constants the tests pin:

```text
AxMigrationError    a registry, row or review decision the mapping refuses to paper over
MappingResult       frozen, value-comparable, exactly two fields: accepted, rejected — both tuples
map_registry(document, *, harvest_run_id, migrated_at, reviewed=None,
             allow_unmappable=False, facets_dir=None)
```

`map_case` and `build_case_facets` exist beside them as the per-case seams the suite exercises
directly. There is **no registry path default, no file convenience wrapper, no CLI alias, no report
and no artifact builder** — those are S7-4 and S7-5, and none of them is anticipated here.

**The clock is the caller's.** `harvest_run_id` and `migrated_at` are required, `migrated_at` is
validated against the committed UTC second-precision pattern, and `discovered_at` is **always**
passed from the legacy `discovery.first_seen_at`, so `make_full_record` can never reach its
`utcnow()` fallback. An AST test proves the module calls no clock, no CLI, no socket, no subprocess
and no `open` — it imports `copy`, `dataclasses`, `re` and the committed harvest modules, and nothing
else.

**Composition, not reimplementation.** `urlkey.canonicalize_string` / `content_id` / `record_id`,
`records.make_full_record` / `to_iso8601_utc` / `null_if_unknown` / `sort_records`, the committed
facet loader, reviewed legacy-industry lookup, lexical-support predicate, vocabulary versions and
classification-state decision, `aliases.load_canonicalization` for the committed canonicalization
policy, `base.suspicious_url_match` for the guard, and `schema.validate_or_raise` against
`record.v1.json`. `classify.py`, `verify.py` and `facetassign.py` are **not imported** — a test
asserts that, because a migration that re-judged its corpus would not be a migration.

**Measured on the protected corpus: 231 accepted, 0 rejected.**

```text
identity            231 distinct record_id · 231 content_id · 231 identity_url
legacy case_id      126 distinct over 231 — repeated by design, and it changes nothing
legacy case_key     231 distinct
evidence            231/231 snippet_only; 0 records claim `fetched`, a status, a hash
                    or a check time
published_at        33 null, exactly the 33 rows whose publication_date is "unknown"
facet states        112 facet_partial · 118 unmapped_legacy_value · 1 unresolved  (= 231)
facet checker       check_facets.validate_record_facets: 0 problems over all 231
```

**Two contract details S7-3 had to settle inside the approved decisions.**

First, **the lexical-support gate is applied exactly where the committed contract applies it** —
`facets.LEXICAL_SUPPORT_REQUIRED`, i.e. `technology-software` and `cross-industry`. Applying it to
every mapped slug was tried and rejected on evidence: it withholds six further reviewed mappings
(`audio streaming`, `beauty / cosmetics`, `music streaming`, `professional information services
(legal, tax)`, `semiconductors`, `video hosting / streaming`) that `check_facets.py` itself accepts,
and it moves the distribution to 106/118/7. For any slug the committed contract does not gate, the
**reviewed map is the authority**. E27 is therefore exactly one record — `"IT services"` →
`technology-software` — and it records the reviewed mapping in an `insufficient_evidence` entry
naming both the slug and the gate, rather than asserting it or mislabelling it `unmapped_legacy_value`.

Second, the §5 rejected-row description said `scores` were "omitted"; the shipped row carries
**`"scores": null`**. Null states that nothing was scored; absence leaves a reader to infer it. The
row is otherwise exactly §5: raw legacy URL in `target_url`, the canonical form only in the
schema-required `identity_url`, `rejection_reason: ambiguous_legacy_url`, and a deterministic
`detail` naming the legacy `case_id` and the exact guard rule id. The complete row validates inside a
`rejection.v1.json` document, asserted in the suite.

**Review semantics (D7-H) are in-memory only** — S7-3 opens no override file. Unreviewed suspicious
URLs **refuse the whole mapping** rather than returning a partial accepted set; `allow_unmappable`
lets it complete with the rejections intact and admits nothing; a reviewed `admit` takes the raw URL
verbatim and records that decision in `provenance.migration.assumptions`; a reviewed `reject` stays
rejected and says it was reviewed. Malformed rows, unknown decisions, duplicate decisions for one
case, a URL that is not that case's own, and a review of a nonexistent case are each refused by name.

**Determinism.** Accepted records come back in the committed `records.sort_key` order; rejection rows
are sorted by `(identity_url, detail)`. Source row order (reversed and two seeded shuffles) and
review-decision order change no byte. Two mappings differing only in run id and migration instant are
diffed **recursively**, and exactly two leaves move: `harvest_run_id` and
`provenance.migration.migrated_at` (a rejection row moves `rejected_at` only).

**Validation:** focused `tests/test_taxonomy_migration.sh` **133 assertions (43 + 28 + 62)**, plus
`records` 51, `schema` 35, `identity` 42, `facets` 34, `eligibility` 48; the S7-1 assessment still
regenerates byte-identically; then the full gate once — **39/39 suites, 1,948 assertions (1,906
unittest + 42 shell)**; then all five checkers exit 0. Both protected registries are byte-identical
under the EOL-aware baseline, no runtime path was created, and no request of any kind was made.

### S7-4 · CLI and dry-run — **COMPLETE**

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

**As shipped — the command surface.** `scripts/harvest/migrate.sh` is environment and dispatch only:
`set -euo pipefail`, root resolved from `BASH_SOURCE`, `"$@"` forwarded verbatim (a path with spaces
survives, asserted), `exec python -m src.harvest.migrate.<module>`. No `eval`, no temp file, no
network, no Git, no string re-parsing. It is stored `100644` like every other shell script in this
repository, which invokes them as `bash …`. Unknown or absent commands print usage on stderr and exit
2.

```text
migrate.sh ax-cases [--registry PATH] [--overrides PATH] [--facets-dir PATH]
                    [--expect-count N] [--allow-unmappable]
                    [--run-id ID] [--migrated-at YYYY-MM-DDTHH:MM:SSZ] [--apply]
migrate.sh entity-assess [--registry PATH] [--output PATH]
migrate.sh --help
```

Defaults: registry `state/ax_case_harvest_registry.json`, overrides
`config/harvest/migration_overrides.v1.json`, committed facets directory, `--expect-count 231`. The
run context is derived through the **committed owners only** — `artifacts.run_id()` and
`records.utcnow()` — and `--run-id` / `--migrated-at` inject it for tests. No second timestamp format
was created and no Git state is read.

**`--apply` was recognised and REFUSED at S7-4**, exiting 1 with a message naming S7-5 and writing
nothing. **S7-5 replaced that refusal with a working apply**, exactly as anticipated — and with it,
the tests that pinned the refusal, because once apply works a bare `--apply` writes to the
operational default root.

**The dry-run report** is one deterministic JSON document on **binary** stdout (a Windows text stream
would rewrite its LFs), rendered by the committed `artifacts.serialize` — no second serializer —
with exactly these sixteen fields:

```text
report_type ("ax_cases" — E29; the value shipped at S7-4 was "ax_cases_dry_run" and was corrected
            at S7-5, because it named a mode rather than the report family)
report_version (1) · operation ("ax-cases") · dry_run (true in this mode)
harvest_run_id · migrated_at · expected_count · source_count
accepted_count · rejected_count · reviewed_admit_count · reviewed_reject_count
unresolved_rejection_count · unresolved_case_ids[] · allow_unmappable
rejections[]  — the S7-3 rows verbatim, in their committed order
```

It carries **no accepted-record payload, no path, no Git or environment fact, no bundle path and no
publication eligibility** — asserted by name. **On the protected corpus: `source_count` 231,
`accepted_count` 231, `rejected_count` 0, `unresolved_rejection_count` 0, exit status 0**, 444 bytes,
byte-identical across runs with the same explicit run context and unchanged by reordering source rows
or review rows.

**Completeness before failure.** The mapping always runs with unmappable cases retained, so the
report is whole; success is decided **separately**, from the unresolved count. Unresolved suspicious
URLs still print the complete report — every rejection, not the first — and only then exit 1, with
stderr naming each case and the two ways forward. A reviewed `reject` is an acknowledged decision,
not an unresolved one. `--allow-unmappable` completes with every rejection intact and **admits,
repairs and rewrites nothing**.

**Override parsing** validates the committed shape completely: `config_version`,
`ax_cases.reviewed_unmappable` as a list, all seven row fields present, no unrecognised key, decision
in `admit`/`reject`, `matched_rule` one of the four S7-2 ids, non-empty reviewer and note,
UTC-second-precision `reviewed_at`, no duplicate row — and then, against the registry, that the
declared `matched_rule` is the rule the guard **actually** fires and that the case is one the guard
refuses at all. The committed file (zero reviews) parses, and is never modified.

**A dry-run writes nothing**, proved by hashing every file under an injected root before and after
rather than by trusting `git status`, and no repository runtime path is created.

**`entity-assess`** exposes S7-1 unchanged: without `--output` the deterministic Markdown goes to
stdout and equals the committed document byte-for-byte; with `--output` exactly those bytes go to
that path and nothing to stdout. It migrates nothing and selects no destination.

**Validation:** focused `tests/test_taxonomy_migration.sh` **175 assertions (43 + 28 + 62 + 42)**,
plus `records` 51, `schema` 35, `identity` 42, `facets` 34, `eligibility` 48; the S7-1 assessment
regenerates byte-identically; then the full gate once — **39/39 suites, 1,990 assertions (1,948
unittest + 42 shell)**; then all five checkers exit 0. Both protected registries are byte-identical
under the EOL-aware baseline, no runtime path exists, and no request of any kind was made.

**One test narrowing, recorded rather than buried.** S7-3's purity assertions covered the whole
`ax_cases.py` file; S7-4 adds a CLI layer there by approval, so those two assertions were **scoped to
the mapping functions** — the mapping still calls no clock, no `open`, no `print` and no loader, and
the module still imports no clock, socket or subprocess module. Nothing about the mapping's
guarantees was weakened; `base.py` was left **byte-unchanged**, so the S7-2 guard purity assertions
stand exactly as committed.

### S7-5 · Atomic apply and repeated-run semantics — **COMPLETE**

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

**No apply against the repository's real state root was executed as part of this checkpoint's
delivered validation**, and `state/taxonomy_harvest/` does not exist. See the incident note at the
end of this section: two bundles were written there during implementation by the retired S7-4
refusal tests, were removed, and are now prevented by an assertion.

**CLI.** `migrate.sh ax-cases` gains `--apply` and `--state-root PATH` (operational default
`state/taxonomy_harvest`). `--state-root` without `--apply` is **refused**, not ignored: a dry-run
has no state root. Every other option keeps its S7-4 behaviour, and the wrapper still forwards
`"$@"` verbatim — a state root containing spaces is asserted end to end.

**Path ownership (`base.py`).** `MIGRATIONS_DIRNAME` · `BUNDLE_SUFFIX` · `BUNDLE_RELATIVE_PATHS` ·
`STAGING_PREFIX` · `RUN_ID_PATTERN` · `MigrationPathError` · `validate_run_id` · `migrations_root` ·
`bundle_dirname` · `bundle_path` · `manifest_path` · `candidate_artifact_path` ·
`rejection_artifact_path` · `staging_name` · `owns_staging`. They **derive and create nothing**;
every one goes through the anchored run-id pattern, so a separator, a `..` or an absolute path never
reaches the filesystem. The ordinary `runs/<run_id>` builders are neither used nor duplicated.

**The published bundle, exactly three files:**

```text
<state-root>/migrations/<run_id>__ax_cases/
├── manifest.json                                        run_manifest.v1.json
├── candidate_output/cases__case-studies__harvest.json    cell_artifact.v1.json
└── rejections/cases__case-studies__rejections.json       rejection.v1.json
```

No topic artifact, coverage artifact, alias-conflict artifact, ledger, pointer, report file, journal,
checksum sidecar, second manifest or placeholder. Nothing under `runs/`, no `LATEST_RUN_ID`, no
promotion. The report stays on stdout.

**The sequence, and why that order.** Final path derived → **finished-run refusal** → registry and
overrides read → expected-count enforced → complete in-memory mapping → unresolved-review policy →
all three documents built → **all three schema-validated** → `migrations/` created if needed → one
uniquely named sibling staging directory `.tmp_migration_<run_id>_<uuid4hex>` → the three documents
written through the committed `artifacts.write_document` (validate, deterministic bytes, temp
cleanup, fsync, atomic replace) → staged path set asserted to be **exactly** the three → destination
rechecked → **one `os.replace` of the directory** → only then the report. Staging is a sibling
because `os.replace` is atomic only within one filesystem; a system temp directory would make
publication a copy.

**Eligibility is derived, never asserted.** `artifacts.unchecked_full_records` must report every
accepted record `not_checked`, or bundle construction is refused rather than publishing a false
claim; `publication_eligible` is then `false` with a deterministic reason ("all 231 of 231 accepted
records carry no target evidence…"). `artifacts.build_run_manifest` is deliberately unused — it
expands to the twelve configured cells and refuses any other cell id, which is a harvest contract,
not this one.

**Same run id is never reused.** A destination existing in **any** form — file or directory —
refuses, **before the registry, overrides or facets are read**, proved with a counting loader that a
control case shows would otherwise have recorded both reads. The first bundle stays byte-identical,
no staging appears, and no success report is printed.

**Cleanup owns exactly one path.** On any `BaseException` before the rename, only the staging
directory this invocation created is removed — proved twice, from the exact retained path and from
`owns_staging` (right parent, right prefix, right run id). A foreign `.tmp_migration_*` sibling, an
unrelated file and a pre-existing `migrations/` all survive; a `migrations/` this apply created is
removed only when empty; the original exception is preserved, `KeyboardInterrupt` included.

**Proved by fault injection at five boundaries** — before the first write, after each content write,
after the manifest write, and during the rename — each leaving the state root path-identical to its
pre-call snapshot. At the rename boundary the destination is observed absent and the staging tree
observed complete immediately before, and complete immediately after: no state exists with one or two
files. A sentinel bundle created mid-staging is **left byte-identical** and publication refuses.

**Two distinct runs, exact moving leaves.** Both bundles publish side by side and agree on every
count, ordered `record_id`, ordered `content_id` and facet-state distribution. The recursive diff
permits exactly: candidate artifact — `generated_at`, `harvest_run_id`, and per record
`harvest_run_id` and `provenance.migration.migrated_at` (462 record leaves over 231 records, counted);
manifest — `harvest_run_id`, `started_at`, `finished_at`; rejection document — `generated_at`,
`harvest_run_id` (and `rejected_at` per row where rejections exist). Normalizing precisely those
makes all three byte-equal. Source-row order does not change published bytes.

**Protected corpus, applied under a temporary root: 231 accepted, 0 rejected**, three files, all
three validating, manifest ineligible by derivation, exit 0, report printed only after the rename.

**Incident, recorded rather than buried.** While implementing this checkpoint, the S7-4 tests that
pinned the `--apply` refusal ran against the new implementation. They pass no `--state-root`, so two
bundles were written into the repository's real `state/taxonomy_harvest/`. That path is gitignored,
so no tracked file, the 508-file untracked baseline and the 18 protected files were all unaffected —
verified. Both bundles and the directory were removed, and the class was replaced by
`TestNoTestEverAppliesToTheDefaultStateRoot`, which asserts the apply helper always injects a state
root and **scans the suite's own AST** for any other call site passing `--apply` without one. The
lesson is the general one: retiring a refusal retires the tests that leaned on it, in the same
checkpoint.

**Validation:** focused `tests/test_taxonomy_migration.sh` **224 assertions**, plus `artifacts` 33,
`manifest` 52, `cell_artifact` 44, `recovery` 75, `run_cells` 99, `records` 51, `schema` 35,
`identity` 42, `facets` 34, `eligibility` 48; the S7-1 assessment regenerates byte-identically; then
the full gate once — **39/39 suites, 2,039 assertions (1,997 unittest + 42 shell)**; then all five
checkers exit 0. Both protected registries and the override config are byte-identical, no real
runtime path exists, and no request of any kind was made.

### S7-6 · Final migration integration — **COMPLETE**

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

**As shipped — test and documentation only.** S7-6 adds no capability, no format and no semantics.
It is the only place S7-1 … S7-5 are proved to be **one workflow**, driven through the real
`scripts/harvest/migrate.sh` over the protected committed inputs.

**The scenario, in one class.** Snapshot the AX registry, the entity registry, the override config,
the committed assessment and the repository's runtime-path state → run `entity-assess` and compare
its stdout with the committed document **byte for byte** → run `ax-cases` dry-run with an explicit
run context → apply the same corpus into a temporary `--state-root` → apply it again under a second
run id and instant → retry the first, finished run id → read both bundles into memory → **delete the
temporary root** → and only then assert. Every assertion therefore runs against a repository with no
runtime state at all.

**Dry-run versus apply, from actual CLI stdout** (not two calls to one renderer): both are exit 0,
both carry `report_type: "ax_cases"`, `report_version: 1`, `operation: "ax-cases"`, both have the
same sixteen fields, and **the only differing field is `dry_run`** — true then false. The protected
result is **231 accepted / 0 rejected**, with reviewed and unresolved counts zero, an empty rejection
list, no accepted-record payload and no absolute path in either report.

**Cross-document reconciliation, not isolated validation.** Report counts equal the candidate
artifact's rows, its derived metadata totals, the rejection document's length and the manifest cell's
`accepted` / `rejected` / `candidates`; one `harvest_run_id` appears in the report, the artifact,
every record, the rejection document and the manifest; one migration instant appears as the
artifact's and rejection document's `generated_at`, the manifest's `started_at` and `finished_at`,
and every record's `provenance.migration.migrated_at`. The manifest carries exactly one migration
cell, no `request_accounting`, and `publication_eligible: false` whose reason accounts for all
**231 of 231** records remaining `not_checked` — cross-checked against the records themselves.

**The persisted records carry every Stage 7 contract**, read back from disk: 231 distinct
`identity_url` / `content_id` / `record_id` over **126 distinct legacy `case_id`s**, all
`snippet_only` and none `fetched`, 33 null `published_at`, four null scores, facet states
**112 / 118 / 1**, and `check_facets.py` reporting zero problems. The guard refuses **0 of 231**.

**Distinct runs and ordering.** The recursive diff permits exactly the leaves each family may move —
candidate: `generated_at`, `harvest_run_id`, and per record `harvest_run_id` and
`provenance.migration.migrated_at` (462 leaves over 231 records, counted); manifest: three;
rejections: two — and normalizing precisely those makes the bundles byte-equal. Reversing **both**
source rows and review rows changes no published byte.

**Review matrix, command to artifact.** Unresolved without `--allow-unmappable` prints the complete
report, exits 1 and creates no root; `--allow-unmappable` publishes with the suspicious row still
rejected and absent from the records; a reviewed `admit` is published verbatim with its decision in
`provenance.migration.assumptions`; a reviewed `reject` persists as a reviewed rejection. Malformed
review shapes stay owned by S7-3/S7-4 and are not duplicated here.

**Atomicity is consolidated, not duplicated.** One observation at the rename boundary proves the
destination absent and the staging tree complete immediately before, the complete final tree
immediately after, no staging residue, and no state with one or two files. **All five detailed S7-5
fault-injection boundaries are retained unchanged**, and none was found order-dependent or vacuous.

**Default-root safety.** The S7-5 incident note stands as written: two obsolete S7-4 tests briefly
executed apply against the default repository state root during S7-5 development; the bundles and the
directory were removed before that commit; no protected, tracked or baseline file changed; the tests
were corrected before the delivered validation; and the repository contains no runtime migration
state. S7-6 adds the forward guarantees: every apply call site in the suite is asserted — by an AST
scan of the suite itself — to name a `--state-root`, all apply roots are descendants of temporary
directories, the injected root is proved deleted, and the repository's runtime paths are proved
absent before and after.

**Validation:** focused `tests/test_taxonomy_migration.sh` **250 assertions**, plus `artifacts` 33,
`manifest` 52, `cell_artifact` 44, `recovery` 75, `run_cells` 99, `records` 51, `schema` 35,
`identity` 42, `facets` 34, `eligibility` 48; the S7-1 assessment regenerates byte-identically; then
the full gate once — **39/39 suites, 2,065 assertions (2,023 unittest + 42 shell)**; then all five
checkers exit 0. Both protected registries and the override config are byte-identical, no temporary
root remains, no repository runtime path exists, and no request of any kind was made.

**Stage 7 implementation is complete: S7-1 … S7-6 are all delivered. Stage 7 itself remains OPEN**
pending `S7-C`, which is **unapproved** and whose exact documentation path set requires its own
read-only closeout preflight.

### S7-C · Closeout — **COMPLETE**

Documentation only, L0 validation only.

Its path set was **not** declared in advance and no handoff filename was pre-authorized or guessed:
S7-C ran **its own read-only closeout preflight** first — the same discipline that let Stage 5 and
Stage 6 close without the authorization gap that hit Stage 4. That preflight established the set from
the committed precedents (`0d2da64` S6-C, `6bf7f51` S5-C, `5fd9f91` S4-C each changed exactly a plan,
this file and one new handoff), and S7-C changed exactly those three:

```text
docs/harvest/handoffs/HANDOFF_STAGE_7_COMPLETE_2026-07-31.md   (new)
docs/harvest/STAGE_7_IMPLEMENTATION_PLAN.md
docs/harvest/TODO.md
```

**L0 validation only** — exact three-path diff, `git diff --check`, nothing touched under `src/`,
`tests/`, `scripts/`, `config/`, `schemas/`, `state/`, `data/` or any runtime path, protected baseline
18/18, the 508-file untracked baseline unchanged, no runtime path and no temporary root, and
cross-document consistency across completion status, handoff filename, closing implementation hash,
commit chain, validation totals, push-state wording, non-goals and the incident record. **Per its own
risk tier the focused suites and the full gate were NOT rerun**: the closing gate is S7-6's, 39/39
suites green in one run before `c3d982c`, and §3 of the handoff attributes the figures to it rather
than re-measuring them.

The preflight also found the one factual defect this closeout had to fix: the TODO's `push_state`
line still described the Stage 6 position (`0 behind / 0 ahead` at `0d2da64`), which stopped being
true the moment S7-0 committed.

## 10 · Not Stage 7

Recorded so they are not absorbed by accident: entity migration proper and its destination taxonomy
(a product decision) · promotion into `data/harvested/` · `refresh` / `linkcheck` / `diff` /
`compare-runs` and the promotion transaction journal (unscheduled, E11) · `validate_task.sh` wiring
(Stage 8, CF-4) · threshold calibration (Stage 9) · the bounded live smoke and S6-L · cleaning or
gitignoring the 508 pre-existing untracked paths · matrix convergence · the GitHub star backfill and
the harvest→pipeline bridge in the legacy pipeline.
