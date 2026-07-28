# Stage 2.5 — case facets and shared discovery: implementation plan

```text
document_status:             APPROVED plan — nothing implemented yet
approvals:                   DV-1 … DV-6 approved; D7 approach approved with the
                             reporting-state correction now folded into §8.3 and §10
verified_code_checkpoint:    3b85a8102fb89ae0585ef0fc080f518238e4c1bc  (short: 3b85a81)
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34  (short: 8865c54)
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e  (short: 0edbf50)
approved_facet_design:       3b85a8102fb89ae0585ef0fc080f518238e4c1bc  (short: 3b85a81)
push_state:                  local only — nothing pushed to origin/main
stage_2_5:                   NOT implemented
stage_3:                     NOT started, blocked
```

This document is **standalone**. It supersedes any session-local planning file and requires no
access to `.claude/plans/`.

---

## 1 · Context

The taxonomy harvest pipeline has Stages 0–2 implemented and tested — **199 assertions across 7
suites**, all green. Stage 2.5 (`case_facets` plus the shared-discovery contracts) is **designed and
approved but not implemented**, and Stage 3 is blocked behind it.

This plan converts the approved design in `docs/harvest/DOMAIN_FACETS_PROPOSAL.md` into an
executable change set, after an adversarial read of that design against the code that actually
exists. Intended outcome: three independent, evidence-grounded facet axes recorded on records; the
ownership, deduplication and coverage contracts Stage 3 will need; and a green rerun of the full
Stage 0–2 baseline — with `record_id`, `content_id`, `identity_url`, `cell_id`, publication paths
and the exact 12-cell set provably untouched.

---

## 2 · Verified checkpoint

Verified read-only at the start of the session that produced this document.

| Check | Command | Result |
|---|---|---|
| Path / branch | `pwd`, `git rev-parse --abbrev-ref HEAD` | `C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4` · `main` |
| Code checkpoint | `git rev-parse HEAD` | `3b85a8102fb89ae0585ef0fc080f518238e4c1bc` |
| History | `git log --oneline -3` | `3b85a81` · `0edbf50` · `8865c54` |
| Working tree | `git status --short --untracked-files=all` | 508 lines, **all `??`** — zero tracked modifications |
| Protected baseline | `bash scripts/harvest/verify_protected_baseline.sh` | rc=0 — 18 files byte-match Git's rendering of `8865c54e…` (bytes + pinned `eol_form` + blob_id + `git diff`) |
| Ignore rule | `git diff --stat 8865c54 HEAD -- .gitignore` | exactly `1 insertion(+)`: `/state/taxonomy_harvest/`; `git check-ignore -v` confirms it fires |
| Pre-existing noise | re-hash of `tests/fixtures/taxonomy/untracked_baseline.txt` | path set identical; **ok=508, drift=0, missing=0** |
| Stage 2.5 / 3 absence | filesystem probe | `state/taxonomy_harvest`, `data/harvested`, `src/harvest/adapters`, `facets.py`, `pool.py`, `coverage.py`, `scheduler.py`, `request_key.py`, `config/harvest/facets`, `coverage_targets.v1.json`, `facets.generated.v1.json`, `check_facets.py` — **all absent** |
| Push state | `git log --oneline origin/main..HEAD` | 8 local commits, none pushed |

**Task-owned vs pre-existing.** Every file this effort produced is *tracked* (committed in `0edbf50`
and `3b85a81`). The 508 untracked files are pre-existing scratch noise (`.scratch_ax/` 445 files, 56
`state/_*` scratch files, a 570 KB root log, 4 uncommitted agent specs) and are disjoint from the
task-owned set. A clean `git status` is **not** required and is never asserted.

---

## 3 · Scope and non-goals

**In scope.** Three facet vocabularies plus coverage targets and the legacy industry map · the
`case_facets` record contract and its schema conditionals · a generated standalone constraint schema
with drift protection · the semantic validator · the `source_request_key` / logical-owner /
candidate-pool contracts · coverage computation and the bounded adaptive scheduler as deterministic
logic over injected inputs · seven new test suites · a rerun of the full 199-assertion baseline ·
documentation.

**Out of scope for Stage 2.5.** Stage 3 discovery adapters and recorded fixtures · extraction,
classification implementation against live content, verification, dedupe (Stage 4) · cell workers
and orchestration (Stage 5) · refresh / link-check / promote (Stage 6) · the AX migration itself
(Stage 7) · any live harvest, network request, migration, refresh, link-check or promotion · any
write to production `state/` · pushing.

**Approved decisions this plan preserves, unchanged.** `case_facets` (not `domain_facets`) · 18
industries, 19 business functions, 22 use-case types · three separate axes · no bare `operations`
value · `legal-risk-compliance` separate from `information-security` · `customer-interaction`
strictly external-facing · `conversational-assistant` never satisfies Customer Interaction coverage
alone · `technology-software`, `cross-industry` and unclear/fallback industry values are
`record_only` · Case Studies coverage is report-only in v1 · no mid-run source revalidation · one
immutable run-scoped snapshot per `source_request_key` · logical fetch ownership distinct from
HTTP-attempt accounting · shared source fetch, shared candidate pool, early deduplication, one
extraction owner, multi-axis classification, coverage reporting, bounded adaptive gap filling ·
facets never affect `identity_url`, `record_id`, `content_id`, publication paths, or the exact
12-cell set · Stage 3 blocked until Stage 2.5 and all old and new tests pass.

---

## 4 · Design defects found against the actual code (D1–D10)

These are defects in the *design document* relative to the Stage 0–2 code as written. None changes
an approved decision; each is a "how", resolved below.

### D1 — the applicability conditional must live inside `$defs/full_record`

`schemas/harvest/record.v1.json` is a root `oneOf` over `full_record` and
`cross_reference_record`, and **both branches set `additionalProperties: false`**. A root-level
`allOf` requiring `case_facets` when `topic == cases` and `primary_category ==
domain-applications` would make every `cases__domain-applications` **cross_reference** row
*unsatisfiable*: the branch cannot legally carry `case_facets`, yet the root conditional would
demand it.

**Correction.** The conditional is placed **inside `#/$defs/full_record`** as a `full_record.allOf`.
`cross_reference_record` is not touched at all; its closed property set already forbids
`case_facets`, which is exactly the "forbidden on any `cross_reference` row" rule from the proposal.
A regression test asserts a `cases__domain-applications` cross_reference row still validates.

### D2 — use-case coverage totals

The proposal contradicts itself: §1.3 and §2.1 (and `docs/harvest/TODO.md`) say
10 priority / **11** standard / 1 record_only = 22, while §13's test row and handoff §4 say
"10/**10**/1" = 21.

**Correction — resolved to `10 priority / 11 standard / 1 record_only = 22`.** This is the only
reading consistent with the 22 approved values. Axis totals in full:

| Axis | priority | standard | record_only | total |
|---|---:|---:|---:|---:|
| industries | 7 | 8 | 3 | **18** |
| business functions | 10 | 8 | 1 | **19** |
| use-case types | 10 | **11** | 1 | **22** |

Tests derive these counts from the vocabulary files and assert the totals; no tier triple is
hardcoded in more than one place.

### D3 — slug disjointness versus the shared sentinel

§13 demands "pairwise-disjoint slug sets" across the three axes, but `other-unclear` appears in
**all three** vocabularies by design (§1.1, §1.2, §1.3). Taken literally the rule contradicts the
vocabularies it governs.

**Correction.** Disjointness is asserted over `slug != "other-unclear"` — the sentinel is the single
explicitly shared value, and the validator names it as such rather than special-casing it silently.
The "cross-axis slug rejected on each axis" test uses a **real** cross-axis slug (e.g. offering the
business-function slug `data-analytics` on the use-case axis), never the sentinel, so it cannot pass
vacuously.

### D4 — §5 still names pre-V2 slugs

The ambiguity table's "legal" row says `legal-compliance` twice; decision V2 renamed it
`legal-risk-compliance`. Documentation-only defect; corrected in the proposal with an errata entry.

### D5 — `vocabulary_versions` is optional but load-bearing

§11 guardrail 5 requires runtime verification that `case_facets.vocabulary_versions` matches the
loaded vocabularies, but §3 leaves the key out of `case_facets.required`.

**Correction.** `vocabulary_versions` becomes **required inside `case_facets`**, with all three
sub-keys (`industries`, `business_functions`, `use_case_types`) required. Safe: `case_facets` itself
remains optional, so no existing record and no existing assertion is affected.

### D6 — the five coverage-reporting states have no precedence

A record can simultaneously look `facet_partial` and carry an `unmapped_legacy_value` entry.
Resolved as a total, exhaustive order in §8.3, with `unmapped_legacy_value` taking precedence over
every other state so it can never be silently folded into `unresolved` or `facet_partial`.

### D7 — "withheld from publication eligibility" has no representation

`publication_eligible` is a **run-level** boolean on `run_manifest.v1.json`. Records have no
eligibility field, and `rejection_reason` is the wrong home: an unresolved record is *retained and
auditable*, not rejected.

**Correction (approved).** Publication eligibility is a **derived predicate** — no new persisted
record flag. All **five** reporting states are preserved as explicit, mutually exclusive, separately
counted states, with `unmapped_legacy_value` first-class rather than collapsed into `unresolved`. The
predicate and the state are derived from the **complete record** — `record_type`, `topic`,
`primary_category`, `case_facets`, and legacy provenance — **not** from `case_facets` alone. A
`cases`/`domain-applications`/`full` record is eligible only in state `facet_complete`; the other
four are withheld. Case Studies stay report-only in v1, so their states block neither migration nor
publication unless another existing gate applies. Full specification in §8.3; six required assertions
in §10.

### D8 — the evidence `field` enum permits `publisher`

`facet_evidence.field` includes `publisher`, but §5.1 forbids inferring `technology-software` (and,
by extension, any industry) from the publisher, the AI vendor, the platform provider, or the host
site. A JSON Schema enum cannot express this.

**Correction.** A semantic rule in `check_facets.py` plus a test: `industry` evidence may not be
sourced from `field: "publisher"`, and `technology-software` may never be asserted from
publisher/vendor/platform evidence. The enum value stays — it is legitimate for other axes and for
recording what was seen.

### D9 — the generated schema enters a repository-wide cached registry

`src/harvest/schema.py::_build_registry()` loads **every** `*.json` in `schemas/harvest/` into one
`referencing.Registry`, registers each under both its bare filename and its `$id`, and caches the
result in a module-global `_REGISTRY`. Consequences:

- a malformed generated file breaks **all seven existing suites**, not just the facet suites;
- a duplicate `$id` silently shadows an existing schema (last-wins);
- the cache is built once per process, so a file written mid-process is not observed.

**Correction — five guardrails plus two forced by this finding.** Unique `$id`; deterministic
generation (sorted keys, `\n` newlines, fixed indent, no timestamps); a header recording each source
vocabulary's `config_version` **and** SHA-256; a header line stating the file is generated and never
hand-edited; a drift test that regenerates **into a temp directory** and byte-compares rather than
trusting the cached registry; generation writes via `mkstemp` + `os.replace` **in the target
directory**, so `schemas/harvest/` never contains a half-written file; and `check_facets.py` loads
and compiles the generated file standalone as its first check. Tests explicitly cover the
malformed-file failure mode and prove the existing suites still pass with the generated file present.

### D10 — the legacy industry map cannot be a complete table

Measured against `state/ax_case_harvest_registry.json`: **231 cases carry 173 distinct free-text
`industry` values** — `'grocery delivery / e-commerce'`, `'superapp (mobility, delivery, fintech)'`,
`'fintech (buy now pay later / digital banking)'`, and so on. A reviewed one-to-one mapping table is
not achievable and pretending otherwise would invite guessing.

**Correction.** `legacy_industry_map.v1.json` is a **reviewed seed**, keyed on the exact original
string after a documented minimal normalization (casefold + whitespace collapse only — the
normalization must not itself be a guess). Everything not in the seed becomes
`unmapped_legacy_value`: the exact original is preserved in `provenance.raw`, the term is carried in
the `unresolved[]` entry, **no slug is guessed**, and the legacy value is **never** presented as
classification evidence. Count stays 231; no ID changes; migration is never blocked on facet
quality.

### Two further constraints found (D11, D15 in working notes)

- **`source_request_key` must pin the canonicalization version.** It is built on
  `urlkey.canonicalize_string`, whose behaviour is driven by `config/harvest/canonicalization.v1.json`.
  Without `canonicalization_version` in the key material, a config bump silently changes keys.
- **`coverage_targets` overrides must not resurrect a `record_only` target.** A per-slug override
  above 0 for `cross-industry`, `technology-software` or `other-unclear` would contradict decisions
  R4 and C6. `check_facets.py` refuses it.

---

## 5 · Files to create or modify

**Create — config**

| Path | Contents |
|---|---|
| `config/harvest/facets/industries.v1.json` | 18 entries, tiers 7 / 8 / 3 |
| `config/harvest/facets/business-functions.v1.json` | 19 entries, tiers 10 / 8 / 1 |
| `config/harvest/facets/use-case-types.v1.json` | 22 entries, tiers 10 / 11 / 1 |
| `config/harvest/facets/legacy_industry_map.v1.json` | reviewed seed (D10) |
| `config/harvest/coverage_targets.v1.json` | tier targets 3 / 2 / 0 + per-slug overrides |

Each vocabulary entry carries `slug`, `display_name`, `definition`, `positive_terms`, `synonyms`,
`exclusions`, `disambiguation`, `parent_group` (UI navigation only, never semantic),
`coverage_policy`, `status` (`active`|`deprecated`), `replaced_by`.

**Create — schemas** (`schemas/harvest/`)

| Path | Why |
|---|---|
| `facet_vocabulary.v1.json` | **not in the proposal** — the shape contract for the three vocabulary files, mirroring how `taxonomy.v1.json` validates topic configs. Without it the vocabularies are the only unvalidated config in the tree |
| `facets.generated.v1.json` | generated, never hand-edited (D9) |
| `candidate_pool.v1.json` | pool + logical-owner contract |
| `discovery_lane.v1.json` | lane identity, provenance, per-lane quality metrics |
| `coverage_report.v1.json` | per-run coverage output |

**Modify — schemas**

- `record.v1.json` — `case_facets` added to `full_record.properties`; five new `$defs`
  (`facet_slug`, `facet_evidence`, `facet_axis_single`, `facet_axis_multi`, `facet_unresolved`); one
  `allOf` **inside `full_record`** (D1); five added `rejection_reason` values
  (`not_a_case_trend_piece`, `not_a_case_product_announcement`, `not_a_case_tutorial`,
  `not_a_case_hypothetical`, `keyword_only_match`).
- `run_manifest.v1.json` — declare optional `rounds[]`, `coverage[]`, `lane_quality[]`. The root is
  `additionalProperties: false`, so they must be declared; they must **not** be added to `required`,
  or `test_run_manifest_valid` breaks.

**Create — code**

| Path | Responsibility |
|---|---|
| `src/harvest/facets.py` | vocabulary loading, tier lookup, classification and ambiguity contract, resolved/unresolved decision, `is_publication_eligible` |
| `src/harvest/request_key.py` | `source_request_key`; reuses `urlkey.canonicalize_string` |
| `src/harvest/pool.py` | candidate pool, logical-owner registry, run-scoped immutable source snapshots, early dedup |
| `src/harvest/coverage.py` | coverage computation, the five reporting states, 7-factor gap ranking |
| `src/harvest/scheduler.py` | bounded adaptive rounds over injected results and an injected clock |
| `scripts/harvest/gen_facet_schema.py` | deterministic generator for `facets.generated.v1.json` |
| `scripts/harvest/check_facets.py` | semantic validator (config-level and record-level) |

**Modify — code**

- `src/harvest/records.py` — one keyword-only `case_facets=None` parameter, omitted from the emitted
  record when falsy. See the deviation table (§6, DV-2) for the full rationale.

**Not modified.** `scripts/harvest/check_config.py` (§6, DV-1) · `src/harvest/urlkey.py` ·
`slug.py` · `schema.py` · `budget.py` · `domainlease.py` · `httpclient.py` · every existing test.

**Docs.** `docs/harvest/FACET_VOCABULARY.md` (new) · this file · `DOMAIN_FACETS_PROPOSAL.md`
(revision header + errata) · `TODO.md` · `HANDOFF_CURRENT.md` · the durable handoff.

**Protected-baseline safety.** None of the 18 protected paths is touched. The protected list is the
five matrix scripts, two mandatory regression tests, four reused utilities
(`lockdir.sh`, `clean_json.sh`, `github_meta.py`, `merge_entity_registry.sh`) and seven production
state files.

---

## 6 · Deviations from the approved proposal — decision table

Six deviations. Each preserves every approved decision; none changes the vocabularies, the axes, the
coverage policy, or the identity exclusion. **DV-1 through DV-6 are APPROVED.**

| ID | Approved proposal said | Actual code constraint | Proposed deviation | Files affected | Tests affected | Risk if rejected | Recommendation |
|---|---|---|---|---|---|---|---|
| **DV-1** | §13: "Modified code — `scripts/harvest/check_config.py` only." | `check_config.py` holds the hard-coded `APPROVED_CELLS` set (the specification the config is checked *against*); `tests/test_taxonomy_config.sh` case A asserts exit 0 **and** the literal summary substrings `cells=12` and `sources=25`; case H asserts `config/` has no tracked modification. | Leave `check_config.py` **byte-unchanged**. All facet-config validation lives in the new `scripts/harvest/check_facets.py`. | none modified; `scripts/harvest/check_facets.py` created | none broken; `test_taxonomy_config.sh` (18) provably untouched | Editing `check_config.py` risks the 18 config assertions on an exact-string summary line, and mixes two specifications (the 12-cell taxonomy and the facet vocabularies) into one gate. If rejected, `check_config.py` must gain facet checks *without* altering its summary line, and the 18 assertions must be rerun on every facet edit. | **Accept.** Separate validators, separate specifications, zero risk to a passing suite. |
| **DV-2** | §13: implies `records.py` is untouched ("Untouched: `src/harvest/{urlkey,slug,records,schema,budget,domainlease,httpclient}.py`"). | `records.make_full_record` is the only builder producing schema-shaped full records; there is no other path by which a record can acquire `case_facets`. | Add one keyword-only parameter `case_facets=None`, emitted **only when truthy**, matching the existing `legacy_ids` / `link_history` / `domain_fields` idiom at `records.py:206-213`. | `src/harvest/records.py` (one parameter, one conditional) | `tests/harvest/test_schema.py` (35) rerun unchanged; new compatibility assertions added | Without it, facets can only be attached by post-hoc dict mutation outside the builder — which bypasses the honest-defaults discipline the module exists to enforce, and leaves no single place to assert the omit-when-empty rule. | **Accept.** Purely additive, keyword-only, default-off. See DV-2 detail below. |
| **DV-3** | §13 lists 4 new schemas (`facets.generated`, `candidate_pool`, `discovery_lane`, `coverage_report`). | The three vocabulary files would be the only configuration in the repository with no schema; every other config (`config/harvest/topics/*`) is validated against `schemas/harvest/taxonomy.v1.json`. | Add a 5th: `schemas/harvest/facet_vocabulary.v1.json`. | `schemas/harvest/facet_vocabulary.v1.json` created | `test_taxonomy_facets.sh` (new) validates all three vocabularies against it | A malformed vocabulary would be caught only by ad-hoc Python checks, and a published consumer could not validate a vocabulary file at all. | **Accept.** Consistent with the existing config-validation pattern. |
| **DV-4** | Handoff §4 and proposal §13 state use-case tiers "10/10/1". | §1.3 lists 22 values with 10 priority, 11 standard, 1 record_only; §2.1's table and `TODO.md` agree on 22 and on 10-11-1. "10/10/1" sums to 21 and cannot describe 22 values. | Resolve to **10 priority / 11 standard / 1 record_only = 22**; tests derive counts from the vocabulary files. | `config/harvest/facets/use-case-types.v1.json`; proposal errata | `test_taxonomy_facets.sh`, `test_taxonomy_coverage.sh` (new) | Implementing "10/10/1" would require deleting one approved standard value or leaving one value tierless — either contradicts the approved 22. | **Accept.** The approved total of 22 is the binding decision (D2). |
| **DV-5** | §13: "`record.v1.json` (add `case_facets`, 5 `$defs`, one `allOf`)" — location unstated. | Root `oneOf` with `additionalProperties:false` on both branches. A root-level `allOf` makes every `cases__domain-applications` cross_reference row unsatisfiable. | Place the `allOf` **inside `#/$defs/full_record`**. | `schemas/harvest/record.v1.json` | `test_taxonomy_schema.sh` (35) rerun; `test_taxonomy_facet_states.sh` (new) adds the cross_reference regression | A root-level conditional silently breaks the cross-topic `cross_reference` policy for one of the twelve cells — a defect that would surface only at Stage 5. | **Accept.** Required for correctness (D1). |
| **DV-6** | §3: `case_facets.required` omits `vocabulary_versions`. | §11 guardrail 5 requires runtime verification that `vocabulary_versions` matches the loaded vocabularies — impossible to enforce when the key may be absent. | Make `vocabulary_versions` **required inside `case_facets`**, all three sub-keys required. | `schemas/harvest/record.v1.json` | `test_taxonomy_facets.sh` (new); no existing assertion touched (`case_facets` itself stays optional) | The version-match guardrail becomes advisory, and a record classified under vocabulary v1 is indistinguishable from one classified under a later revision. | **Accept.** Cheap, and the guardrail is otherwise unenforceable (D5). |

### DV-2 in detail — the `records.py` change

**Exact current signature** (`src/harvest/records.py:91-136`) — keyword-only throughout, 45
parameters after the bare `*`:

```python
def make_full_record(
    *,
    record_id, content_id, topic_slug, category_slug, cell_id,
    identity_url, target_url, harvest_run_id, source_id, source_adapter,
    canonical_url=None, source_url=None, title=None, summary=None,
    curation_reason=None, publisher=None, author=None, published_at=None,
    updated_at=None, discovered_at=None, last_checked_at=None,
    content_type="article", language=None, access_status="not_checked",
    http_status=None, verification_status="unverified", verification_evidence=None,
    relevance_score=None, quality_score=None, audience_fit_score=None,
    freshness_score=None, duplicate_of=None, content_hash=None, tags=None,
    classification=None, provenance_extra=None, source_tier=None,
    discovered_via=None, raw=None, legacy_ids=None, link_history=None,
    domain_fields=None, rejection_reason=None,
):
```

**Proposed addition** — one keyword-only parameter with a `None` default, plus one conditional
appended to the existing optional-key block:

```python
    domain_fields=None,
    rejection_reason=None,
    case_facets=None,          # <-- added
):
    ...
    if domain_fields:
        rec["domain_fields"] = domain_fields
    if case_facets:            # <-- added; omitted entirely when None/empty
        rec["case_facets"] = case_facets
    return rec
```

**Why an additive keyword argument is necessary.** `make_full_record` is the only code path that
produces a schema-shaped full record, and the module's stated contract is that every emitted record
carries honest defaults and that optional keys are *omitted rather than carried as empty containers*
(`records.py:206-207`). Attaching facets by mutating the returned dict elsewhere would place the
omit-when-empty rule outside the module that owns it, so nothing could assert it in one place. The
parameter is keyword-only (the signature begins with a bare `*`), so it cannot shift any positional
argument, and it defaults to `None`, so the emitted record is byte-identical for every existing
caller.

**Every caller that could be affected.** Repository-wide grep for `make_full_record` returns exactly
two hits:

| Location | Kind |
|---|---|
| `src/harvest/records.py:91` | the definition itself |
| `tests/harvest/test_schema.py:27` | the only call site — the `full_record()` fixture helper |

There are no production callers: Stages 3–7 do not exist yet. `make_cross_reference` is **not**
changed (`cross_reference` rows may never carry facets), and its only call site is
`tests/harvest/test_schema.py:41`.

**Compatibility tests proving existing callers are unchanged.**

1. `test_taxonomy_schema.sh` (35 assertions) is rerun verbatim — its `full_record()` helper passes no
   `case_facets`, so every existing assertion exercises the unchanged path.
2. New in `test_taxonomy_facet_identity.sh`: `make_full_record(**args)` and
   `make_full_record(**args, case_facets=None)` produce **dictionaries that compare equal and
   serialise to identical JSON**, and neither contains a `case_facets` key.
3. New in `test_taxonomy_facet_identity.sh`: adding, changing, removing or nulling `case_facets`
   leaves `record_id`, `content_id`, `identity_url`, `cell_id` and the artifact filename
   byte-identical.
4. New in `test_taxonomy_facet_states.sh`: a record built with `case_facets={}` (falsy) omits the key
   entirely, so `not_enriched` stays distinguishable from an attempted-but-empty classification.

### DV-1 in detail — why `check_config.py` should stay untouched

`scripts/harvest/check_config.py:39-52` hard-codes `APPROVED_CELLS`, the set of twelve
`topic__category` cells. The module docstring and `INVENTORY_AND_REUSE_MAP.md` both state the
reason: this set is the **specification the configuration is validated against**, so deriving it
from that configuration would make the check vacuous. Invariant 3 of the handoff repeats it.

Three concrete risks in editing the file for facet validation:

1. **Exact-string coupling.** `tests/test_taxonomy_config.sh:36-38` asserts exit code 0 *and* that
   the output contains the literal substrings `cells=12` and `sources=25`. Any change to the summary
   line, or any new failure mode reached before it prints, breaks assertions that have nothing to do
   with facets.
2. **Two specifications in one gate.** The 12-cell taxonomy and the three facet vocabularies are
   independent specifications with independent version numbers. Merging their gates means a
   vocabulary edit can fail the cell check's suite, and the failure message no longer says which
   specification was violated.
3. **Vacuity by proximity.** The facet vocabularies are *also* configuration. If facet validation
   moves into the same file, the natural next step is to derive the expected vocabulary size from
   the file being checked — precisely the mistake `APPROVED_CELLS` exists to prevent. Keeping the
   facet validator separate makes its own hard-coded expectations (18 / 19 / 22 and the tier splits)
   visible as a specification rather than a derivation.

Facet vocabulary validation therefore lives in `scripts/harvest/check_facets.py`, which hard-codes
its own expectations exactly as `check_config.py` does, and which the new
`tests/test_taxonomy_facets.sh` drives. `check_config.py` remains byte-unchanged and its 18
assertions remain a pure regression gate.

---

## 7 · Schema changes in detail (`record.v1.json`)

New `$defs`:

```text
facet_slug        ^[a-z0-9]+(-[a-z0-9]+)*$

facet_evidence    { field ∈ [title, summary, body, publisher, target_url, legacy_field],
                    matched_term minLength 2,
                    quote minLength 3 maxLength 400,
                    offset integer|null }

facet_axis_single { primary slug|null,
                    secondary array maxItems 2 uniqueItems,
                    confidence number 0..1|null,
                    evidence array }
                  + if primary is a string -> evidence minItems 1 and confidence must be a number

facet_axis_multi  { slug, confidence number 0..1, evidence minItems 1 }

facet_unresolved  { axis ∈ [industry, business_function, use_case_type],
                    state ∈ [other-unclear, unmapped_legacy_value,
                             insufficient_evidence, not_applicable],
                    term string|null,
                    detail minLength 3 }
```

`full_record.properties.case_facets` — type `["object", "null"]`, `additionalProperties: false`,
required inner keys: `facets_version` (const 1), `vocabulary_versions` (**required**, all three
sub-keys required — DV-6), `classification_state` ∈ {`resolved`, `unresolved`}, `industry`
(`facet_axis_single`), `business_functions` (array, maxItems 4, `facet_axis_multi`),
`use_case_types` (array, maxItems 4, `facet_axis_multi`); optional `unresolved[]`
(`facet_unresolved`).

`full_record.allOf` — **inside the branch, never at the document root** (DV-5 / D1):

| if | then |
|---|---|
| `topic == "cases"` ∧ `primary_category == "domain-applications"` | `required: ["case_facets"]`, and `case_facets` must be an object (not null) |
| `topic ∈ {"research-and-models", "discourse"}` | `case_facets` must be **absent or null** |

`cases`/`case-studies` and `cases`/`product-discovery` remain schema-optional.
`cross_reference_record` is untouched.

`case_facets` is **not** added to `full_record.required`, so
`test_every_required_field_is_actually_required` — which walks the `required` array and deletes each
key in turn — is unaffected.

Five added `rejection_reason` enum values. The existing assertions only require that `null` and
`seo_spam` validate and that `"i didn't like it"` does not, so extending the enum is safe.

---

## 8 · Semantics

### 8.1 Vocabulary source of truth and generated constraints

`config/harvest/facets/*.v1.json` are the **single source of truth**. `gen_facet_schema.py` emits
`schemas/harvest/facets.generated.v1.json` with real enums — Option A from §11 of the proposal,
because artifacts published to `cherryinthehaystack.com` must validate standalone with any
off-the-shelf validator, by consumers with no repository access. Guardrails are listed under D9. The
semantic validator is retained for what a schema cannot express: the non-trivial requirement, axis
disjointness, deprecation, evidence-source rules, and the `record_only`-override refusal.

### 8.2 Classification and ambiguity contract (`facets.py`)

- **Evidence-grounded only.** A value may be asserted only with at least one `facet_evidence` quoted
  from the extracted document.
- **Discovery provenance never forces a label.** A record found via `gap__function__marketing` gets
  no marketing label for that reason. A lane's *query terms* may become evidence **only** when
  independently found in the fetched body; the `lane_id` itself never is.
- **Axis separation** per §5 of the proposal, using the V2 slug names: finance, legal, retail,
  manufacturing, operations, education, technology, risk, security, chat-UI.
- **`customer-interaction` is strictly external** — customers, users, patients, citizens, members,
  guests, clients. A conversational interface alone never proves it. An internal employee copilot
  receives `conversational-assistant` only. Both may co-occur only when each is independently
  evidenced, and `conversational-assistant` can never satisfy the Customer Interaction coverage
  target on its own.
- **`technology-software`** is never inferred from the publisher, the AI vendor, the platform
  provider, or the host site. A vendor-published customer story takes the **customer's** industry.
- **Secondary industries** cap at 2 and mean *deployment context*, not corporate portfolio.
- **`cross-industry`** only for a genuinely horizontal or documented multi-industry deployment.
- **No bare `operations`.** Generic "improving business operations" prose assigns neither
  `supply-chain-operations` nor `production-operations`; the term goes to `unresolved[]`.
- Ambiguity is *recorded*, never forced: competing values with their evidence, plus `unresolved[]`.

### 8.3 Unresolved states, reporting states, and publication eligibility (D6, D7)

**Resolved** (for `cases`/`domain-applications`) requires **both**: `industry.primary` is a supported
value other than `other-unclear` (`cross-industry` counts), **and** at least one supported
`business_functions[]` or `use_case_types[]` entry. Otherwise `classification_state: "unresolved"`
with at least one `unresolved[]` entry.

**Four unresolved states, never collapsed:** `other-unclear` · `unmapped_legacy_value` ·
`insufficient_evidence` · `not_applicable`.

**Five reporting states — mutually exclusive, exhaustive, and derived from the complete record.**

`src/harvest/coverage.py::reporting_state(record) -> str | None` returns exactly one of the five for
every **applicable** record, and `None` for records outside scope.

**Scope.** Applicable = `record_type == "full"`. **`cross_reference` rows are excluded entirely** —
they are pointers, cannot carry `case_facets`, and are never counted in any of the five states.

**Inputs.** The state is derived from the *complete record*, not from `case_facets` alone. It reads:

| Input | Used for |
|---|---|
| `record_type` | scope — excludes `cross_reference` |
| `topic` · `primary_category` | which policy applies (required / optional / forbidden; gated vs report-only) |
| `case_facets` | `classification_state`, `industry.primary`, `business_functions[]`, `use_case_types[]`, `unresolved[]`; and its absence/`null` |
| legacy provenance — `provenance.migration`, `provenance.raw` | determining and corroborating `unmapped_legacy_value` |

**Precedence — first match wins. The order is total, so a record can never be counted twice:**

| # | State | Condition |
|---:|---|---|
| 0 | *(not applicable — excluded)* | `record_type != "full"` |
| 1 | `unmapped_legacy_value` | `case_facets.unresolved[]` contains at least one entry with `state == "unmapped_legacy_value"` |
| 2 | `not_enriched` | `case_facets` is absent or `null` |
| 3 | `facet_complete` | `case_facets.classification_state == "resolved"` |
| 4 | `facet_partial` | `classification_state == "unresolved"` **and** at least one axis is populated (`industry.primary` non-null, or `business_functions[]` non-empty, or `use_case_types[]` non-empty) |
| 5 | `unresolved` | `classification_state == "unresolved"` **and** no axis is populated |

*Why the order is total and exhaustive:* after rule 0 removes non-`full` records, rule 1 either fires
or does not; if not, `case_facets` is either absent/`null` (rule 2) or present, in which case the
schema constrains `classification_state` to exactly `resolved` (rule 3) or `unresolved`, which rules
4 and 5 partition on "any axis populated". No record satisfies two rules, and none escapes all five.

**`unmapped_legacy_value` is a first-class state, never collapsed into `unresolved`.** It applies
when a legacy source carries a **non-empty** value for which **no reviewed mapping exists**.
Specifically:

- **Detection** is the `unresolved[]` entry with `state == "unmapped_legacy_value"`, emitted by the
  migration adapter when a non-empty legacy value misses `legacy_industry_map.v1.json`. It takes
  precedence over every other state, including `facet_partial` — a record whose functions and use
  cases were populated but whose industry came from an unmapped legacy string is reported as
  `unmapped_legacy_value`, because that is the fact a reviewer must act on.
- **The exact source value is preserved** verbatim in `provenance.raw` (the complete original object
  with its original field names) **and** carried in the entry's `term`. Nothing is normalized away
  in the record; the casefold + whitespace-collapse normalization exists only to look the value up.
- **It is never classification evidence.** No `facet_evidence` may cite it, and `field:
  "legacy_field"` provenance becomes usable only after a reviewed entry in
  `legacy_industry_map.v1.json` assigns a real slug. `check_facets.py` rejects any record that
  presents an unmapped legacy value as evidence.
- **Consistency rule (prevents silent degradation to `not_enriched`).** If `provenance.migration` is
  present and `provenance.raw` carries a non-empty legacy industry value with no reviewed mapping,
  then `case_facets` **must** exist and **must** carry the corresponding `unresolved[]` entry.
  `check_facets.py` errors otherwise — a migrated record may not hide an unmapped value by simply
  omitting `case_facets`.
- **It is counted separately** in `run_manifest.coverage[]` and in `coverage_report.v1.json`, never
  folded into the `unresolved` count.

Counted separately per `(topic, category)` per run. Weak facets are never invented to improve a
number.

**Publication eligibility — derived, never persisted (D7):**

- **Where implemented.** `src/harvest/facets.py::is_publication_eligible(record) -> bool`, built on
  `coverage.reporting_state(record)`. Same inputs as the table above — `record_type`, `topic`,
  `primary_category`, `case_facets`, and legacy provenance.
- **The rule.** A `cases` / `domain-applications` / `full` record is eligible **only** when its
  reporting state is `facet_complete`. `facet_partial`, `unresolved`, `not_enriched` **and**
  `unmapped_legacy_value` are all **withheld**.
- **Case Studies stay report-only in v1.** States are counted and reported for
  `cases`/`case-studies` and `cases`/`product-discovery`, but never gate anything: they do not block
  migration and do not withhold publication. Another existing gate — `rejection_reason`, the
  run-level `publication_eligible` boolean, a link-check outcome — may still withhold such a record,
  and this predicate does not override it.
- **Withheld is not rejected.** An ineligible record is retained and auditable: it keeps its
  `record_id`, carries no `rejection_reason`, and is excluded only from the published set until
  reviewed.
- **`cross_reference` rows** are outside the five states and outside this predicate; their
  eligibility is unchanged by facets.
- **How it appears in the run manifest.** `run_manifest.coverage[]` gains, per `(topic, category)`:
  all **five** state counts (`facet_complete`, `facet_partial`, `unresolved`, `not_enriched`,
  `unmapped_legacy_value`), `applicable_full_records`, `publication_eligible_records`,
  `publication_withheld_records`, and the per-axis target-versus-observed table. The five counts sum
  exactly to `applicable_full_records`. The run-level `publication_eligible` boolean keeps its
  existing meaning (smoke runs are ineligible) and is not overloaded.
- **How promotion checks it.** Stage 6 `promote` calls `is_publication_eligible` per record and
  writes the withheld count, broken down by reporting state, into its transaction record. Because the
  predicate reads only fields that already exist, promote needs no schema change and no new record
  property.
- **How a consumer distinguishes all five without an unsupported record property.** Each state is
  derivable by applying the precedence table above to the complete record — `case_facets` alone is
  **not** sufficient, because `unmapped_legacy_value` corroboration and the applicability rules need
  `record_type`, `topic`, `primary_category` and legacy provenance. For consumers that would rather
  not re-derive anything, `coverage_report.v1.json` publishes the per-record reporting state and the
  eligibility flag keyed by `record_id`. **No new property is added to `record.v1.json`.** Should a
  persisted record-level flag later prove necessary, it returns as a separate, explicit schema
  change proposal.

### 8.4 Ownership contracts (`request_key.py`, `pool.py`)

```text
source_request_key = sha256( source_id | normalized_url | method | canonical_query |
                             body_hash | significant_headers | adapter_mode |
                             canonicalization_version )[:16]
```

`normalized_url` uses the Stage 1 canonicalizer. `canonical_query` is sorted **only** for API
adapters where order is provably insignificant; feed and seed URLs keep their order.
`significant_headers` is an allowlist (`Accept`, `Accept-Language`) — never `User-Agent`, never auth
material. `adapter_mode` distinguishes seed `index` from seed `record` against the same URL.
`canonicalization_version` is pinned so a config bump cannot silently change keys.

**Run-scoped immutable snapshot (decision R3 — no mid-run revalidation).** The first logical fetch
per key in a run may use `ETag` / `Last-Modified` carried over from a *previous* run; a `200` **or**
`304` establishes the snapshot; every lane and every adaptive round in that run reuses it from
`pool/sources/<request_key>.json`; **no later round may revalidate or replace it.** A changed source
requires a new run, or an explicit `refresh` / `linkcheck`.

**Logical owners (asserted) versus HTTP attempts (observed).** One source-fetch owner per
`source_request_key` per run · one target-fetch owner per canonical candidate per run · one
extraction owner per accepted response body · one record per `(topic, identity_url)`. Retries,
redirect hops and conditional revalidations are legitimate multiple attempts, counted separately as
`http_attempts` / `retries` / `redirect_hops` / `conditional_revalidations` and charged to the
existing Stage 2 `RequestBudget`, which is not modified.

**Early deduplication** happens in the pool on `urlkey.canonicalize_string(target_url)` **before**
extraction, and every contributing `lane_id` is preserved on the surviving candidate.

`pool.py` and `scheduler.py` are pure contract plus deterministic logic over **injected** results and
an **injected clock** — no adapters, no network. Stage 3 does not exist yet, and Stage 2.5 must not
require it.

### 8.5 Coverage policy and bounded adaptive gap filling

`coverage_targets.v1.json`: `priority → target_min 3`, `standard → 2`, `record_only → 0`, plus
per-slug `overrides`. **Scheduler hints, never acceptance gates** — `min_relevance`, `min_quality`
and `accept_composite` are read once per run from `config/harvest/policy.v1.json` and are never
touched by the scheduler. It changes *where* it looks, never *what* it accepts. An unmet target is
reported as an unmet target.

Round 1 is the 12 configured cells. Later rounds rank gaps over seven factors — remaining gap,
configured priority, historical acceptance yield, duplicate rate, quality-rejection rate,
credible-source availability, remaining global budget — and open bounded lanes only where a credible
source exists; otherwise `stop_reason: "no_credible_source"` is recorded and the gap reported
honestly. Stop conditions: `max_rounds` (default 3), new-accepted below `no_progress_min`,
duplicate rate above threshold, global or lane budget exhausted, or all targets met.

`cross-industry` never launches a gap lane and never closes or reduces a concrete industry gap.
Mandatory smoke stays **round 1 only**.

### 8.6 AX migration compatibility

The 231 cases land in `cases`/`case-studies`, where `case_facets` is schema-optional, so **migration
is never blocked on facet quality**. Count stays 231; no ID changes. Legacy `industry` maps only via
the reviewed seed (D10); anything unmapped becomes `unmapped_legacy_value` in `unresolved[]` with the
exact original preserved in `provenance.raw` — never guessed, never presented as evidence. Business
functions and use cases are populated only where `workflow_after` / `ai_system_or_tool` yield a
quotable phrase; otherwise `[]` ("looked, found nothing"), which is distinct from `null`.
`config/harvest/migration_overrides.v1.json` keeps its separate job (the suspicious-URL guard) and is
**not** merged into the facet map.

---

## 9 · Implementation stages

Each step ends with its narrowest test passing before the next begins.

| # | Step | Gate |
|---:|---|---|
| 1 | Rerun the 199-assertion baseline at `3b85a81`, unmodified; record the output | 199 green |
| 2 | `facet_vocabulary.v1.json` → the three vocabularies → `check_facets.py` config checks | `test_taxonomy_facets.sh` |
| 3 | `coverage_targets.v1.json` + `legacy_industry_map.v1.json` | `test_taxonomy_facets.sh` |
| 4 | `gen_facet_schema.py` → `facets.generated.v1.json` | drift test + all 199 still green (D9) |
| 5 | `record.v1.json`: `$defs`, `case_facets`, the in-branch `allOf`, rejection reasons | rerun `test_taxonomy_schema.sh` **immediately**, then `test_taxonomy_facet_identity.sh`, `test_taxonomy_facet_states.sh` |
| 6 | `facets.py` + the `records.py` hook | `test_taxonomy_facet_ambiguity.sh`, `test_taxonomy_customer_interaction.sh` |
| 7 | `request_key.py` + `pool.py` + `candidate_pool` / `discovery_lane` schemas | `test_taxonomy_pool.sh` |
| 8 | `coverage.py` + `scheduler.py` + `coverage_report.v1.json` + `run_manifest` additions | `test_taxonomy_coverage.sh` |
| 9 | Docs; full 199 + 7 new suites; `verify_protected_baseline.sh` | everything green |

---

## 10 · Tests

Seven `tests/test_taxonomy_*.sh` wrappers over `tests/harvest/test_*.py`, following the existing
`tests/test_taxonomy_schema.sh` pattern exactly: offline, `python -m unittest discover`, and an
assertion afterwards that `git status --porcelain --untracked-files=no -- state/ config/` is clean.

| Suite | Proves |
|---|---|
| `test_taxonomy_facets.sh` | vocabulary shape against `facet_vocabulary.v1.json` · totals **18 / 19 / 22** and tiers **7-8-3 / 10-8-1 / 10-11-1** · generated-schema drift (regenerate into a temp dir, byte-compare) · a malformed generated file fails loudly and does not silently shadow a schema · `vocabulary_versions` runtime match · deprecated values still validate historically but cannot be newly assigned · a `record_only` override above 0 is refused |
| `test_taxonomy_facet_ambiguity.sh` | pairwise-disjoint slug sets excluding the `other-unclear` sentinel · a **real** cross-axis slug rejected on each axis · finance / legal / retail / manufacturing / operations / education fixtures · a conglomerate article naming four business lines yields **zero** secondary industries · a vendor-published customer case takes the **customer's** industry · `technology-software` not inferred from publisher / vendor / platform / host site · `legal-risk-compliance` + `risk-fraud-compliance` co-occur without being flagged duplicate or conflicting · `information-security` not assigned for contract or audit work · "improving business operations" assigns **neither** operations function · no bare `operations` slug exists on any axis |
| `test_taxonomy_customer_interaction.sh` | an external customer-support assistant may receive `customer-interaction` · an **internal employee copilot does not** · a conversational UI alone does not prove customer interaction · one external assistant may carry **both** values only when each is independently evidenced · `conversational-assistant` alone never satisfies the Customer Interaction coverage target |
| `test_taxonomy_facet_identity.sh` | add / change / remove / null `case_facets` ⇒ `record_id`, `content_id`, `identity_url`, `cell_id` and the artifact filename all byte-identical · `make_full_record()` and `make_full_record(case_facets=None)` are equal and both omit the key (DV-2) · static grep proving `urlkey.py` and `slug.py` never mention facets · `APPROVED_CELLS` is still exactly 12 |
| `test_taxonomy_facet_states.sh` | the four unresolved states are distinct · `other-unclear` alone fails the domain-applications requirement · the five-state precedence order is total and deterministic · unresolved records are withheld by `is_publication_eligible` yet retained with no `rejection_reason` · `unmapped_legacy_value` never becomes evidence · **a `cases__domain-applications` cross_reference row is still valid** (D1 regression) · a `research-and-models` full record carrying `case_facets` is rejected · `case_facets={}` omits the key · **plus the six D7 assertions below** |
| `test_taxonomy_pool.sh` | `source_request_key` stability and sensitivity, including `canonicalization_version` · one logical owner across 3 lanes · a `304` snapshot reused across all rounds · **no second conditional request within a run** · a **new** run may revalidate · redirect + one 503 retry ⇒ 1 logical owner / 3 HTTP attempts / budget charged 3 · every contributing `lane_id` preserved · output identical under shuffled worker and round timing |
| `test_taxonomy_coverage.sh` | tier targets · 7-factor gap ranking · `no_credible_source` reported, not invented · **thresholds provably constant across rounds** · all stop conditions · ten `cross-industry` records leave a `healthcare-life-sciences` gap and a `manufacturing-industrial` gap unchanged · no `gap__industry__cross-industry` lane is ever scheduled · the five reporting states counted separately · Case Studies coverage reported, never gated |

### The six D7 reporting-state assertions

Required by the approval of D7. They live in `tests/harvest/test_facet_states.py` (driven by
`tests/test_taxonomy_facet_states.sh`), except T5 and T6 which also appear in
`test_taxonomy_coverage.sh` because they are aggregate properties.

| # | Assertion | Fixture |
|---:|---|---|
| **T1** | An unmapped legacy value is counted **only** as `unmapped_legacy_value` | a migrated `case-studies` record whose legacy `industry` is a non-empty string absent from `legacy_industry_map.v1.json`, with functions and use cases populated. `reporting_state` returns `unmapped_legacy_value`, and the record appears in exactly one of the five counts |
| **T2** | It is **not** counted as generic `unresolved` — and not as `facet_partial` either | the same fixture: the `unresolved` and `facet_partial` counts are both unchanged by adding it, proving precedence rule 1 beats rules 4 and 5 rather than shadowing them silently |
| **T3** | It cannot make a Domain Applications record publication-eligible | the same legacy condition on a `cases`/`domain-applications` full record ⇒ `is_publication_eligible` is `False`, `rejection_reason` is `null`, and `record_id` is unchanged |
| **T4** | It does **not** block Case Studies migration under the v1 report-only policy | a `cases`/`case-studies` record in state `unmapped_legacy_value` validates against `record.v1.json`, is not withheld by the facet predicate, and the migration count stays **231** |
| **T5** | The five counts sum **exactly** to the number of applicable full records | a mixed fixture set containing at least one record in each of the five states: `sum(five counts) == applicable_full_records`, asserted against both `run_manifest.coverage[]` and `coverage_report.v1.json` |
| **T6** | `cross_reference` records are excluded from all five counts | add N cross_reference rows to the same fixture set: every one of the five counts and `applicable_full_records` are unchanged, and `reporting_state` returns `None` for each row |

Two supporting assertions in `test_taxonomy_facets.sh`: the consistency rule fires (a migrated record
with a non-empty unmapped legacy value but **no** `case_facets` is rejected by `check_facets.py`,
rather than degrading to `not_enriched`), and a record presenting an unmapped legacy value as
`facet_evidence` is rejected.

### The 199 existing assertions that must be rerun

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"
for t in protected_baseline config identity schema http domain_throttle budget; do
  bash "tests/test_taxonomy_${t}.sh"
done
bash scripts/harvest/verify_protected_baseline.sh
```

| Suite | Assertions | Exposure to Stage 2.5 |
|---|---:|---|
| `tests/test_taxonomy_protected_baseline.sh` | 24 | none — no protected path is touched |
| `tests/test_taxonomy_config.sh` | 18 | **watch:** case A asserts exit 0 plus the literal `cells=12` / `sources=25`; case H asserts `config/` has no tracked modification. Protected by DV-1 |
| `tests/test_taxonomy_identity.sh` | 42 | none — `urlkey.py` untouched |
| `tests/test_taxonomy_schema.sh` | 35 | **highest risk:** `test_every_required_field_is_actually_required`, `test_unknown_field_rejected`, `test_exactly_one_branch_matches`, `test_run_manifest_valid` and every artifact test load through the shared registry (D9, D12) |
| `tests/test_taxonomy_http.sh` | 48 | none |
| `tests/test_taxonomy_domain_throttle.sh` | 16 | none |
| `tests/test_taxonomy_budget.sh` | 16 | indirect — `pool.py` charges the existing `RequestBudget` but does not modify it |
| **Total** | **199** | |

Run this baseline **before** the first edit (proving green at `3b85a81`) and **after** the last one.

---

## 11 · Completion criteria

1. All 7 new suites pass **and** all 199 existing assertions pass in the same final run.
2. `bash scripts/harvest/verify_protected_baseline.sh` exits 0 — 18 files unchanged.
3. `git diff --stat 8865c54 HEAD -- .gitignore` still reads exactly `1 insertion(+)`.
4. The 508 pre-existing untracked files re-hash to `untracked_baseline.txt` with zero drift.
5. `python scripts/harvest/check_facets.py` exits 0, and `facets.generated.v1.json` is byte-identical
   to a fresh regeneration.
6. `APPROVED_CELLS` is still exactly 12 and `scripts/harvest/check_config.py` is byte-unchanged.
7. Facet identity proof green: adding, changing, removing or nulling `case_facets` changes no id, no
   `cell_id`, and no artifact filename.
8. No live harvest, migration, refresh, link-check or promotion was run; `state/taxonomy_harvest/`
   and `data/harvested/` remain absent.
9. Documentation updated; `TODO.md` Stage 2.5 boxes ticked only where the narrowest test passes.
10. Nothing pushed. Commits only on explicit request, via `bash scripts/safe_commit.sh -m "…"` with
    explicit file paths — never `-A`, never `.`, never a glob.

---

## 12 · Rollback criteria

Everything is additive except three files, so rollback to `3b85a81` is mechanical:

```bash
git checkout -- schemas/harvest/record.v1.json \
                schemas/harvest/run_manifest.v1.json \
                src/harvest/records.py

rm -rf config/harvest/facets \
       config/harvest/coverage_targets.v1.json \
       schemas/harvest/facet_vocabulary.v1.json \
       schemas/harvest/facets.generated.v1.json \
       schemas/harvest/candidate_pool.v1.json \
       schemas/harvest/discovery_lane.v1.json \
       schemas/harvest/coverage_report.v1.json \
       src/harvest/facets.py src/harvest/pool.py src/harvest/coverage.py \
       src/harvest/scheduler.py src/harvest/request_key.py \
       scripts/harvest/gen_facet_schema.py scripts/harvest/check_facets.py \
       tests/test_taxonomy_facets.sh tests/test_taxonomy_facet_ambiguity.sh \
       tests/test_taxonomy_facet_identity.sh tests/test_taxonomy_facet_states.sh \
       tests/test_taxonomy_customer_interaction.sh tests/test_taxonomy_pool.sh \
       tests/test_taxonomy_coverage.sh \
       tests/harvest/test_facets.py tests/harvest/test_facet_ambiguity.py \
       tests/harvest/test_facet_identity.py tests/harvest/test_facet_states.py \
       tests/harvest/test_customer_interaction.py tests/harvest/test_pool.py \
       tests/harvest/test_coverage.py \
       docs/harvest/FACET_VOCABULARY.md

for t in protected_baseline config identity schema http domain_throttle budget; do
  bash "tests/test_taxonomy_${t}.sh"
done
bash scripts/harvest/verify_protected_baseline.sh
```

**Rollback triggers.**

- Any existing assertion that cannot be made green **without editing an existing test** — that would
  mean Stage 2.5 changed a Stage 0–2 contract, which is out of scope.
- Any protected-baseline failure.
- Any drift in the 508 pre-existing untracked files.
- Discovery that the approved vocabularies cannot be expressed without changing an approved
  decision — in which case the design returns for re-approval rather than being bent in code.

---

## 13 · Stage 3 opening condition

**Stage 3 remains blocked** until every item in §11 holds simultaneously — specifically: the seven
new facet suites pass, the 199 existing assertions pass in the same run, the protected baseline
verifies, `check_facets.py` exits 0 with no generated-schema drift, and the facet identity proof is
green. Only then may `src/harvest/adapters/` and the Stage 3 fixtures begin.
