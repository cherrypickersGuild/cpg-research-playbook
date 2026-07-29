# Stage 3 completion handoff — discovery adapters and fixture-backed discovery

**Date:** 2026-07-29 · **Branch:** `main` · **Closing commit:** `68b6c2628aca36187aab37a4b8c08e401820d261`

A durable milestone summary, not a session log. It records what Stage 3 delivered and the state the
repository was in when Stage 3 closed. It approves nothing.

---

## 1 · Commit chain

```text
68b6c26  feat(harvest): add fixture-backed discovery adapters       4B
bfde922  fix(harvest): fail closed when pace lock is unavailable    DV-9   (4A")
3957fac  feat(harvest): add run-scoped source fetch cache           4A
e3a8663  test(harvest): measure domain pacing at worker release     4A'
2841578  fix(harvest): expose per-fetch HTTP accounting             DV-8   (3A)
0a03fdd  fix(harvest): make candidate pool artifacts deterministic  DV-7   (3)
e271206  fix(harvest): classify client HTTP errors as 4xx           C4     (2)
ea992f1  docs(harvest): approve stage 3 implementation plan         (1)
8865c54  implementation-start anchor (protected baseline measured against this)
```

Plan of record: `docs/harvest/STAGE_3_IMPLEMENTATION_PLAN.md`. Every checkpoint committed alone, each
gated by its narrowest test before the next began.

## 2 · Delivered

**Production modules**

```text
src/harvest/sourcecache.py       SourceFetchCache, InMemoryStore claim/wait/complete/fail,
                                 FetchResult, FailureDescriptor — one logical fetch per
                                 source_request_key on success AND failure
src/harvest/adapters/__init__.py registry; typed AdapterNotImplemented for sitemap, model_search
src/harvest/adapters/base.py     Adapter ABC, RawCandidate, AdapterResult, the result/reason
                                 vocabulary, document-order cap enforcement, the single
                                 SourceFetchCache call site
src/harvest/adapters/feed.py     RSS 2.0 + Atom, stdlib xml.etree only          (22 sources)
src/harvest/adapters/jsonapi.py  items_path + dotted field_map                   (2 sources)
src/harvest/adapters/seed.py     bounded index reader, _SEED_DEPTH = 1           (1 source)
src/harvest/fixtures.py          FixtureOpener, loaders, FixtureMissing
scripts/harvest/check_fixtures.py  fixture completeness + manifest verification
```

**Corrections shipped alongside**

| ID | Correction |
|---|---|
| C4 | `ClientError.reason` is `http_4xx`; a dead configured feed is no longer reported as a server error |
| DV-7 | `CandidatePool.to_document()` is byte-deterministic: type-aware set normalization plus honest `designated_*` vocabulary that never claims to name the lane that executed the work |
| DV-8 | Per-logical-fetch `FetchAccounting` on `Response` and on every typed failure, never diffed from shared `client.stats` |
| DV-9 | `DomainLease.wait_turn` fails closed when the pace lock is unavailable; the caller translates it to a typed `lease_timeout` |

**Contracts fixed by Stage 3.** `discover(source, *, cache, client, budget=None, lane_id, round_=1,
clock=None) -> AdapterResult` · `RawCandidate{target_url, title, published_at, summary, publisher,
source_id, adapter, position}` · `AdapterResult{source_id, adapter, result, reason, candidates,
dropped_over_cap, requests_made, accounting, status, detail}` · results `ok | zero_result |
adapter_error | infrastructure_error` over three disjoint reason frozensets, with an unrecognised
reason deliberately classified `adapter_error` · only `adapter_mode="index"` is used; no child body
is ever fetched.

## 3 · Validation at closure

**567 assertions across 17 suites · all green · `OVERALL_FAIL=0`.**

```text
protected_baseline 24   config 18   identity 42   schema 35   http 80
domain_throttle 35      budget 16   facets 34     facet_ambiguity 28
facet_identity 16       facet_states 32           customer_interaction 13
pool 57                 coverage 27   source_cache 34
adapters 66             adapter_concurrency 10
```

**Checkers — all exit 0**

```text
python scripts/harvest/check_fixtures.py           25/25 configured sources have a fixture;
                                                   19/19 configured hosts have a robots fixture;
                                                   47 manifest entries byte- and hash-matched
bash   scripts/harvest/verify_protected_baseline.sh 18/18 protected files byte-match Git's
                                                   rendering of 8865c54e...
python scripts/harvest/check_facets.py             industries=18 business_functions=19
                                                   use_case_types=22
python scripts/harvest/gen_facet_schema.py --check  generated schema matches the vocabularies
python scripts/harvest/check_config.py             cells=12 sources=25 topics=3;
                                                   byte-unchanged since 0edbf50 (DV-1 intact)
```

**Fixture corpus.** 25 source fixtures + 22 robots fixtures (19 configured hosts plus three
non-counting policy extras), 47 manifest entries. All synthetic, carrying `authored_at` and
`authored_against`; none claims `captured_at`. **No live request was ever made** to author them.

**Architectural boundaries, verified by AST rather than text scan.** Adapters fetch only through
`SourceFetchCache`, at exactly one call site · adapters never establish `CandidatePool` source rows ·
no network implementation anywhere under `src/harvest/adapters/` · no fixture-specific branch in any
adapter or in `sourcecache.py` · the dependency arrow points one way, `adapters -> sourcecache` · no
Stage 4+ behaviour: no records, facets, classification, verification, dedupe, migration or
publication output, and `make_full_record` is never called.

## 4 · Repository state at closure

```text
HEAD                    68b6c2628aca36187aab37a4b8c08e401820d261
index                   empty
tracked modifications   zero
untracked baseline      508 files present and byte-identical (sha256 + length); drift 0
protected baseline      18/18 byte-match the implementation-start anchor 8865c54e...
.gitignore vs anchor    exactly 1 insertion(+)
push state              19 unpushed commits; NOTHING has ever been pushed to origin/main
```

**Stage 4 absent at closure** — confirmed:

```text
absent  src/harvest/extract.py     src/harvest/classify.py
absent  src/harvest/verify.py      src/harvest/dedupe.py
absent  src/harvest/migrate/       src/harvest/plan_cells.py
absent  scripts/harvest/harvest.sh scripts/harvest/harvest_cell.sh
absent  scripts/harvest/run_topics.sh
absent  state/taxonomy_harvest/    data/harvested/    runs/
```

No live source request, harvest, migration, refresh, link-check or promotion was performed at any
point in Stage 3. No write was made to production `state/`.

## 5 · What Stage 3 deliberately did not do

`sitemap` and `model_search` remain unimplemented and raise typed `AdapterNotImplemented` carrying
their recorded activation conditions — neither falls back to another parser and neither returns an
empty success. No conditional requests are sent (`conditional_requests.enabled` is `false`, and
`HttpClient` cannot deliver a 304 to a caller); every Stage 3 snapshot is established by `200`. No
per-source `query_order_policy` field was added; all 25 sources resolve through the default
`preserve`. The `seed` adapter reads its bounded index only: it never fetches a child body and never
assigns target-fetch or extraction ownership.

## 6 · Successor

`docs/harvest/STAGE_4_IMPLEMENTATION_PLAN.md` — **PROPOSED, pending deviation approval.** It is the
design authority for Stage 4 and authorizes no code. Target-page fetching, target fixtures,
target-fetch and extraction ownership, body parsing and alias adjudication are deferred to Stage 6.
