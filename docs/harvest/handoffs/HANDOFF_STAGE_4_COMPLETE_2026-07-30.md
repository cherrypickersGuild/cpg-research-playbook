# Stage 4 completion handoff — extract, classify, verify, dedupe, facets, records

**Date:** 2026-07-30 · **Branch:** `main` · **Closing commit:** `b303d9db1e7433a740960bfbaaf83e82acfd8433`

A durable milestone summary, not a session log. It records what Stage 4 delivered and the state the
repository was in when Stage 4 closed. It approves nothing.

---

## 1 · Commit chain

```text
b303d9d  feat(harvest): add in-memory record construction          S4-5B
e1946a6  fix(harvest): remove ambiguous IT facet term              S4-5A-C  (corrective)
1624868  feat(harvest): add deterministic facet assignment         S4-5A
164722f  feat(harvest): add deterministic scoring and verification S4-4
d37d463  fix(harvest): make precedence keyword matching explicit   S4-3A    (corrective)
407f2e6  feat(harvest): add deterministic precedence classification S4-3
bf99819  feat(harvest): add deterministic metadata normalization   S4-2
8f07920  feat(harvest): add deterministic candidate ingest and dedupe S4-1
97aade4  docs(harvest): record stage 3 completion and stage 4 plan S4-0
68b6c26  Stage 3 closing commit
8865c54  implementation-start anchor (protected baseline measured against this)
```

Plan of record: `docs/harvest/STAGE_4_IMPLEMENTATION_PLAN.md`. Every checkpoint committed alone, each
gated by its narrowest test before the next began. S4-4A was a documentation-only calibration
conclusion and shipped no code or config.

## 2 · Delivered

**Production modules**

```text
src/harvest/dedupe.py       411  same-topic grouping and the ingest model; delivery(),
                                 group(); duplicate representation without a second identity
src/harvest/extract.py      258  metadata normalization; ExtractedCandidate, normalize_all();
                                 field_variants preserved, nothing invented
src/harvest/classify.py     439  deterministic precedence classification; Classification,
                                 Evidence, CompetingCategory; the committed whole-token matcher
src/harvest/verify.py       479  scoring and verification; Scores, Verdict, score(), decide(),
                                 verify(), verify_all(); every formula shape named and bounded
src/harvest/facetassign.py  285  deterministic case_facets assignment; FacetAssignment,
                                 assign(), assign_all(), applicability()
```

**No production module was added by S4-5B.** Record construction reuses the committed
`records.py`, which already accepted `case_facets` and already omitted the key when falsy — so the
checkpoint is test-only. See §2.1.

**Corrective checkpoints shipped alongside**

| ID | Correction |
|---|---|
| S4-3A | Precedence keyword matching made explicit and whole-token. Plurals of single-token nouns no longer match; the one authorized `precedence.v1.json` edit. Residual tuning recorded as CF-5 |
| S4-5A-C | The standalone synonym `IT` removed from `it-infrastructure`. Matching is case-insensitive and token-based by design, so `IT` was indistinguishable from the English pronoun and assigned the facet to any document containing an ordinary "It …", quoting the pronoun as evidence. Fixed in the **vocabulary, not the matcher**; `facets.generated.v1.json` regenerated mechanically because it pins the vocabulary's SHA-256. Closes CF-12 |

**Contracts fixed by Stage 4.** `dedupe.delivery(lane_id, result)` · `dedupe.group(deliveries, *,
sources) -> DedupeResult` · `extract.normalize_all(deduped) -> ExtractionResult` ·
`classify.classify(extracted) -> Classification` · `verify.verify(extracted, classification, *,
policy=None, categories=None, clock=None) -> Verdict` · `verify.verify_all(extraction,
classifications, ...)` · `facetassign.assign(extracted, classification, *, facets_dir=None) ->
FacetAssignment` · `facetassign.assign_all(extraction, classifications)` ·
`facetassign.applicability(classification)`.

### 2.1 · S4-5B — record construction, as shipped

Reconciled with commit `b303d9db1e7433a740960bfbaaf83e82acfd8433`.

- **Test-only.** `tests/harvest/test_records_build.py` (594 lines, 51 assertions) and
  `tests/test_taxonomy_records.sh`. **No production change was required**, because the existing
  `records.make_full_record` already supported the required contract: it accepts `case_facets` and
  omits the key entirely when falsy, which is what keeps "never enriched" distinct from "looked,
  found nothing".
- **The facet payload reaches the builder as `FacetAssignment.case_facets`.** S4-5A returns a
  `FacetAssignment`; S4-5B passes its `.case_facets` dict to the unmodified
  `records.make_full_record(..., case_facets=...)`. `make_cross_reference` is likewise unmodified.
- **Classification evidence is projected, not forwarded.** `classify.Evidence` carries
  `{signal, matched, field}`, but `record.v1.json`'s `classification.evidence` items admit
  `{signal, matched}` only, with `additionalProperties: false`. Record construction therefore
  projects the two schema-admitted fields and drops the internal `field` property. Forwarding the
  dataclass wholesale is refused by the schema — a test pins both the narrowing and the refusal.
- **Both `case_facets` conditionals are proved from the schema's own behaviour.** A
  `cases__domain-applications` full record built without facets is refused; a `research-and-models`
  or `discourse` full record built with them is refused (absent and explicit null both accepted). A
  `cases__domain-applications` **cross_reference** row stays satisfiable — the conditionals sit
  inside the full-record branch precisely so one of the twelve cells is not made impossible.
- **`cross_reference` remains a pointer.** It refuses `title`, `summary`, `relevance_score`,
  `classification` and `case_facets`.
- **Facets are inert for identity.** `record_id`, `content_id`, `identity_url`, `cell_id` and
  `canonical_url` are identical with and without a payload; `urlkey.py` contains no facet reference.
- **Order is content, not timing.** `(topic, primary_category, record_id)`; shuffled input yields a
  byte-identical artifact across five shuffles.
- **Nothing is written.** No artifact, manifest, ledger or rejection file; no live request.

## 3 · Validation at closure

**940 assertions across 23 suites · all green.**

```text
protected_baseline 24   config 18   identity 42   schema 35   http 80
domain_throttle 35      budget 16   facets 34     facet_ambiguity 28
facet_identity 16       facet_states 32           customer_interaction 13
pool 57                 coverage 27   source_cache 34
adapters 66             adapter_concurrency 10
dedupe 55               extract 58    classify 78   verify 63
facetassign 68          records 51
```

567 prior + 55 S4-1 + 58 S4-2 + 78 S4-3/S4-3A + 63 S4-4 + 68 S4-5A/S4-5A-C + 51 S4-5B = **940**.
Every prior assertion remained green and unmodified throughout; the only existing test file Stage 4
edited was `tests/harvest/test_facetassign.py`, and only at S4-5A-C, where the CF-12 pin was
replaced by six regression tests.

**Checkers — all exit 0**

```text
python scripts/harvest/check_fixtures.py            25/25 configured sources have a fixture;
                                                    19/19 configured hosts have a robots fixture;
                                                    47 manifest entries byte- and hash-matched
bash   scripts/harvest/verify_protected_baseline.sh 18/18 protected files byte-match Git's
                                                    rendering of 8865c54e...
python scripts/harvest/check_facets.py              industries=18 business_functions=19
                                                    use_case_types=22
python scripts/harvest/gen_facet_schema.py --check   generated schema matches the vocabularies
python scripts/harvest/check_config.py              cells=12 sources=25 topics=3;
                                                    byte-unchanged (DV-1 intact)
```

**The CF-6 pre-commit limitation, measured twice.** No checkpoint that edits `config/` can pass the
full gate *before* committing: taxonomy suites assert `git status --porcelain --untracked-files=no
-- state/ config/` is empty, a guard that compares the working tree to HEAD and so cannot tell an
authorized checkpoint edit from a test mutating production config. At S4-3A, 755/756 behavioural
assertions were green pre-commit with the guard as the single failure. At S4-5A-C, 16 suites failed
on the guard alone — 15 wrapper epilogues plus `test_taxonomy_config.sh` section H — every one naming
only the authorized path, with all behavioural assertions green; all suites were green immediately
after the atomic commit. CF-6 records 14 suites, measured when there were 20; the count grew with the
two suites added since. Carried to Stage 8.

## 4 · Repository state at closure

```text
HEAD                    b303d9db1e7433a740960bfbaaf83e82acfd8433
index                   empty
tracked modifications   zero
untracked baseline      508 files present and byte-identical (sha256 + length); drift 0, missing 0
protected baseline      18/18 byte-match the implementation-start anchor 8865c54e...
.gitignore vs anchor    exactly 1 insertion(+)
push state              28 unpushed commits; NOTHING has ever been pushed to origin/main
```

**Byte-unchanged since `68b6c26`:** `src/harvest/pool.py`, `records.py`, `facets.py`, `urlkey.py`,
`schema.py`, `coverage.py`, every adapter, every schema **except** `facets.generated.v1.json`, and
every config file **except** the two authorized corrections — `precedence.v1.json` (S4-3A) and the
`business-functions.v1.json` / `facets.generated.v1.json` pair (S4-5A-C, one atomic contract because
the schema pins the vocabulary's hash).

**Stage 5+ absent at closure** — confirmed:

```text
absent  src/harvest/migrate/        src/harvest/plan_cells.py
absent  scripts/harvest/harvest.sh  scripts/harvest/harvest_cell.sh
absent  scripts/harvest/run_topics.sh
absent  state/taxonomy_harvest/     data/harvested/     runs/
```

No live source request, harvest, migration, refresh, link-check or promotion was performed at any
point in Stage 4. No write was made to production `state/`. Stage 4 was metadata-only and entirely
in-memory throughout.

## 5 · What Stage 4 deliberately did not do

No target page was fetched, so every Stage 4 record carries `access_status: "not_checked"` and
`verification_status: "unverified"` — not `"ok"`/`"fetched"`, which would be a claim not earned.
`pool.py` was never touched: §1.3 proves Stage 4 does not need it, and the unlocked check-then-set
paths in it stay harmless while they have zero callers (CF-1). No artifact, manifest, ledger or
rejection file was written, so the rejection-log vocabulary question stays open (CF-2). No target
fixtures were authored (CF-3). `industry.secondary` is left empty by design (CF-11) — the committed
definition means deployment context, never corporate portfolio, and filling it with runners-up would
manufacture findings.

**Carried-forward findings at closure**

| # | Finding | Belongs to |
|---|---|---|
| CF-1 | Unlocked check-then-set / read-modify-write in `pool.add_candidate`, `acquire_target_fetch`, `acquire_extraction`; harmless while all three have zero callers | Stage 5 |
| CF-2 | `rejection.v1.json` cannot store the five `not_a_case_*` / `keyword_only_match` values `record.v1.json` admits | Stage 5, when that log is first written |
| CF-3 | No target-page fixtures exist | Stage 6 |
| CF-4 | `scripts/validate_task.sh` has zero taxonomy references, so CLAUDE.md's stated entry point exercises none of the 940 assertions | Stage 8 |
| CF-5 | Keyword-list tuning under S4-3A token semantics | whichever stage revisits relevance |
| CF-6 | No `config/`-editing checkpoint can pass the full gate pre-commit; the guard compares to HEAD | Stage 8, with the `validate_task.sh` wiring |
| CF-7 | `record.v1.json` has no `below_composite_threshold`; the honest reason must name the actual rule | Stage 5 |
| CF-8 | Two configured category terms are unmatchable | the relevance-tuning stage |
| CF-9 | `policy.v1.json` defines four tier weights not yet driven from `role` | the relevance-tuning stage |
| CF-11 | `industry.secondary` left empty by design | the facet-quality stage |
| ~~CF-12~~ | **Closed** by S4-5A-C | — |
| D1 | The plan's original S4-5B API line was stale; corrected at closeout | closed |
| D2 | `record.v1.json` narrows `classification.evidence` to `{signal, matched}` | recorded, no action |
| — | Coverage reporting wiring: `coverage.py` and `facets.count_states` / `reporting_state` are not yet driven from a built record set | Stage 5 |

**S4-4 calibration is provisional, not committed policy.** `min_audience_fit` is structurally
non-binding under the current binary audience fit; `accept_composite = 0.40` is slack on this corpus
and functional when raised, but no candidate came within 0.31 of it; `min_quality` is capable of
binding but was pre-empted by the relevance gates on every candidate. The synthetic parser fixtures
are unsuitable for tuning editorial acceptance — 102 of 102 `off_topic` candidates would also have
missed `require_any` in their discovery cell, so the corpus measures plumbing, not content.
`SATURATION = 3` and the `0.68 / 0.32` required-versus-boost split are provisionally approved.
**Calibration of audience fit, the composite threshold and acceptance rates is deferred to the
Stage 9 bounded live corpus.**

## 6 · Successor

Stage 5 is **not open.** `STAGE_4_IMPLEMENTATION_PLAN.md` §11 lists ten conditions; conditions 1–9
are met at this commit and recorded above. **Condition 10 — explicit approval — is not given, and
green tests alone do not open Stage 5.** No Stage 5 planning document exists yet.

**Exact starting point for the successor**

```text
start commit    b303d9db1e7433a740960bfbaaf83e82acfd8433  (this handoff's closing commit)
anchor          8865c54e2cc8d879410576f247baac4aea149f34  (protected baseline measured here)
assertions      940 across 23 suites, all green
push state      local only — nothing pushed to origin/main
```

**Constraints the successor inherits.** The 18 protected files and the 508 pre-existing untracked
paths stay byte-identical; `.gitignore` stays at exactly `1 insertion(+)` against the anchor.
`pool.py` and `records.py` remain byte-unchanged unless a checkpoint explicitly authorizes
otherwise. A vocabulary file and `facets.generated.v1.json` are **one atomic contract** — the schema
pins the vocabulary's SHA-256, so any vocabulary edit must regenerate the schema mechanically in the
same commit, never by hand. Any checkpoint that edits `config/` inherits the CF-6 procedure: all
behavioural assertions green pre-commit, commit atomically, then the full gate green from the
committed tree. Target-page fetching, target fixtures, target-fetch and extraction ownership, body
parsing and alias adjudication remain deferred to Stage 6; migration to Stage 7; `validate_task.sh`
wiring to Stage 8; live smoke, `model_search` and threshold calibration to Stage 9.
