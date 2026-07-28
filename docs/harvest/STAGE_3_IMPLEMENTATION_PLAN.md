# Stage 3 — discovery adapters and fixture-backed discovery: implementation plan

**Status: APPROVED FOR IMPLEMENTATION** (documentation checkpoint only; no code written under this
document yet). **Date:** 2026-07-28 · **Branch:** `main`

```text
verified_code_checkpoint:    46ab67cde36acf4b2b403d17d4bc589eff3d5cb7   Stage 2.5 implementation
stage_2_5_completion:        84650cbaa6d6376dcb9827fd2f9df387dcb69b69   completion handoff
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  local only — nothing pushed to origin/main
assertions_at_plan_time:     387 across 14 suites (199 Stage 0–2 + 188 Stage 2.5), all green
```

This document is **standalone**. It supersedes the Stage 3 sketch in `TODO.md` and the two deferred
questions recorded in `handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md` §18. It does **not** modify
any frozen artifact; stale statements in frozen documents are recorded as errata in §2.

---

## 1 · Verification performed before this plan was written

Every claim in the Stage 2.5 completion handoff was treated as an assertion to check, not a fact to
inherit. All held:

| Check | Result |
|---|---|
| HEAD / branch | `84650cbaa6d6376dcb9827fd2f9df387dcb69b69` · `main` |
| Commit chain | all six checkpoint hashes match; anchor is an ancestor of HEAD |
| Tracked modifications | zero |
| Untracked baseline | 508 paths, **zero drift, zero missing** (set-diffed against `untracked_baseline.txt`) |
| Protected baseline | 18 files byte-match Git's rendering of the anchor |
| `.gitignore` vs anchor | exactly `1 insertion(+)` |
| Push state | 12 unpushed commits; nothing on `origin/main` |
| `check_facets.py` · `gen_facet_schema.py --check` · `check_config.py` | all exit 0 (`cells=12 sources=25 topics=3`) |
| Full suite | 14/14 suites exit 0; **387** assertions = **199** + **188**, matching per-suite |
| Stage 3 / runtime paths | `adapters/`, `migrate/`, `harvest.sh`, `tests/fixtures/harvest/`, `state/taxonomy_harvest/`, `data/harvested/`, `runs/` — all absent |
| `check_config.py` | untouched since `0edbf50` (DV-1 intact) |

---

## 2 · Errata — stale statements in frozen documents

Frozen documents are **not** rewritten. Their errors are recorded here, and this plan is the
authority where they conflict.

**E1 — `STAGE_2_5_IMPLEMENTATION_PLAN.md` §8.4 is superseded.** It reads "`canonical_query` is sorted
**only** for API adapters where order is provably insignificant; feed and seed URLs keep their
order." The separately approved correction removed adapter-class-driven sorting entirely. The shipped
contract: `query_order_policy` is keyword-only, defaults to `preserve` for **every** adapter and
source, and `ORDER_INSIGNIFICANT_ADAPTERS` does not exist (`test_pool.py:113` asserts its absence).
Authority: completion handoff §9 and `src/harvest/request_key.py:49-68`.

**E2 — `IMPLEMENTATION_PLAN.md` §3 overstates `test_taxonomy_config.sh`.** It claims the suite fails
when "any referenced fixture is missing". It does not: `check_config.py:131-137` checks `fixture_id`
**uniqueness only**, and never touches the filesystem. Fixture-existence checking is a Stage 3
responsibility and lands in a **new** file (`scripts/harvest/check_fixtures.py`), because DV-1
requires `check_config.py` to stay byte-unchanged.

**E3 — `test_pool.py::TestDeterminism` scoped determinism narrowly, and that scope is now
superseded.** Its comment at `tests/harvest/test_pool.py:358` reads "ownership provenance
legitimately reflects who arrived first; the SHAPE and the identity set must not", and `_run` compares
a **sorted projection** rather than the document. That is why 38 green pool assertions did not detect
the byte-nondeterminism proved in §5. DV-7 replaces this with full-document byte-determinism.

---

## 3 · Scope and non-goals

**In scope.** A pure adapter layer that turns one configured source into a bounded, deterministic list
of raw candidates; a run-scoped source-fetch coordinator that guarantees one logical fetch per request
key for both success and failure; synthetic fixtures for all 25 configured sources and all 19
configured hosts; an offline test suite.

An adapter emits `RawCandidate` objects — `{target_url, title, published_at, summary, publisher,
source_id, adapter, position}`. **Not records.** `records.make_full_record` is not called anywhere in
Stage 3.

**Non-goals, explicitly.** No extraction, classification, scoring, verification or dedupe beyond the
pool's canonical key (Stage 4) · no cell worker, orchestrator, `harvest.sh`, run manifest, cell
artifact or ledger write (Stage 5) · no refresh, link-check or promotion (Stage 6) · no migration
(Stage 7) · no `validate_task.sh` wiring (Stage 8) · **no live request of any kind** (Stage 9) · no
facet assignment: an adapter never writes `case_facets`, and a `lane_id` never becomes evidence.

**Unchanged by Stage 3:** record identity (`record_id`, `content_id`, `identity_url`, `cell_id`), the
exact 12-cell publication structure, case facets, publication eligibility, and the request-key
contract. Discovery provenance never influences any of them.

---

## 4 · Decisions carried into this plan

### C1 — adapters implemented (approved)

Three **concrete** adapters plus a contract layer:

| Module | Kind | Sources | Rationale |
|---|---|---:|---|
| `adapters/base.py` | **contract layer, not an adapter** | — | `Adapter` ABC, `RawCandidate`, `AdapterResult`, the result/reason vocabulary, cap enforcement |
| `adapters/feed.py` | concrete | **22** | RSS 2.0 **and** Atom, stdlib `xml.etree` only |
| `adapters/jsonapi.py` | concrete | **2** | `items_path` + dotted `field_map` incl. numeric index (`agencies.0.name`) |
| `adapters/seed.py` | concrete | **1** | Bounded index reader, depth hard-fixed at 1 |

`sitemap` and `model_search` stay **unimplemented**; the registry raises typed
`AdapterNotImplemented` for both. **No fake configured source is created to make either appear
implemented.** Activation conditions, recorded now:

- **`sitemap`** — activates only on an approved configured source **and** an approved bounded sitemap
  contract (index-vs-urlset handling, `sitemapindex` recursion depth, entry caps).
- **`model_search`** — activates only on an approved model-search lane **and** an approved
  orchestration contract; it additionally requires the Stage 5 model-lane machinery, so it cannot be
  completed inside Stage 3 even if a source appeared.

Both names remain in the `taxonomy.v1.json` adapter enum; the enum is not edited.

### C2 — no conditional requests in Stage 3 (approved)

Stage 3 sends **no** `If-None-Match` / `If-Modified-Since`. Every real Stage 3 source snapshot is
established by **`200`**. Two independent reasons:

1. `config/harvest/policy.v1.json → conditional_requests.enabled` is `false` (staged feature).
2. `HttpClient` cannot deliver a 304 to a caller. Verified empirically with a stub opener: status 304
   is not a redirect, not in `retry_status`, not 4xx/5xx, so it falls through to a zero-length body and
   `httpclient.py:531-532` raises `EmptyResponse` (`reason="empty_response"`, classified
   `adapter_error`).

The unit-level 304 snapshot semantics in `pool.py` and `test_pool.py` are **kept unchanged**.
`httpclient.py` is **not** modified for 304 in Stage 3. Integration is deferred to Stage 6, where
`refresh`/`linkcheck` need it and where `conditional_requests.enabled` is intended to flip.

### C5 — frozen documents not rewritten (approved)

`DOMAIN_FACETS_PROPOSAL.md` and `STAGE_2_5_IMPLEMENTATION_PLAN.md` remain frozen. The completion
handoff and this plan are authoritative for the shipped request-key contract. See erratum **E1**.

### C6 — active documentation corrected (approved)

`docs/harvest/TODO.md` only, in this same commit: the non-existent test name is replaced with
`tests/harvest/test_pool.py::TestQueryOrderPolicy`, the superseded adapter-wide sorting language is
restated as the shipped opt-in-per-request contract, and the Stage 3 section points here.

### Seed scope clarification (approved)

Stage 3's `seed` adapter fetches and parses **the bounded index only**. It may resolve child target
URLs, evaluate robots permission per child, and return those URLs as raw candidates. It **must not**
fetch child target-page bodies, and it **must not** assign target-fetch or extraction ownership —
those belong to Stage 4.

Consequently: in Stage 3 the only `adapter_mode` in use is **`index`**. Any earlier statement
suggesting an `index`-versus-`record` fetch against the same **child** URL is withdrawn — no child
body is fetched at all in Stage 3. `adapter_mode` remains in the request-key material
(`request_key.py:162`) and `record` becomes reachable only when Stage 4 introduces target-page
fetching.

---

## 5 · DV-7 — CandidatePool determinism and ownership semantics

### 5.1 The proof

A direct read-only probe built the same semantic discovery input under all **12** permutations of
3 lanes × 2 sources:

```text
orderings: 12    distinct serialized outputs: 12
```

Progressive normalization isolated the cause:

```text
baseline                                 : 12 distinct
+ sort/dedupe set-like arrays only       :  3 distinct
+ also normalize the owner scalars       :  1 distinct   ← invariant met
  (owner scalars only, arrays untouched) : 12 distinct
```

**Both corrections are necessary; neither alone is sufficient.**

Divergence is confined to six fields; candidate ordering, source ordering and per-object dict key
order are already deterministic (`to_document()` sorts by key at `pool.py:226-227`, verified).

| Field | Class | Current code | Duplicates possible | Multiplicity meaningful |
|---|---|---|---|---|
| `sources[].contributing_lanes` | set-like provenance | `pool.py:75-77`, `139-140` | no (guarded) | no |
| `candidates[].contributing_lanes` | set-like provenance | `pool.py:163`, `173-174` | no (guarded) | no |
| `candidates[].source_request_keys` | set-like provenance | `pool.py:164`, `175-176` | no (guarded) | no |
| `sources[].reused_in_rounds` | set-like, **numeric** | `pool.py:140-141` | no (guarded) | no |
| `sources[].owner_lane_id` | race-determined scalar | `pool.py:83` | — | — |
| `candidates[].first_seen_lane_id` | race-determined scalar | `pool.py:162` | — | — |
| `candidates[].target_fetch_owner` | race-determined scalar, **required** | `pool.py:181-184` | — | — |
| `candidates[].extraction_owner` | race-determined scalar, **required** | `pool.py:189-192` | — | — |

### 5.2 Normalization point

All normalization happens in **`to_document()` only** — the single place the artifact is produced.
Live in-memory state keeps encounter order and the **actual** runtime owner, which execution,
accounting and diagnostics need. Normalizing at append would mutate live state and break four
existing assertions that read the in-memory dicts (`test_pool.py:217, 235, 314, 336`); normalizing at
acquisition would change control flow and let two lanes fetch the same source.

### 5.3 Type-aware set normalization

No single generic comparator. Per field, by type:

| Field | Normalization |
|---|---|
| `contributing_lanes` (source and candidate) | deduplicate, sort **lexically** (strings) |
| `source_request_keys` | deduplicate, sort **lexically** (16-hex strings) |
| `reused_in_rounds` | deduplicate, sort **numerically** — must serialize `1, 2, 10`, never `1, 10, 2` |

**Untouched, because their order is meaningful:** feed item order, JSON `items_path` item order,
anchor document order, and repeated query-parameter order (which stays governed solely by
`request_key.QUERY_ORDER_*` and is not changed here).

### 5.4 Designation is not execution — artifact vocabulary corrected

The actual race winner stays **internal**. The deterministic artifact publishes a **designation**,
under names that say so. No Stage 3 artifact has been produced and no external consumer exists, so
the vocabulary is corrected now rather than preserving misleading names.

| In-memory (actual, nondeterministic) | Serialized (designated, deterministic) |
|---|---|
| `sources[].owner_lane_id` | `sources[].designated_owner_lane_id` |
| `candidates[].first_seen_lane_id` | `candidates[].primary_discovery_lane_id` |
| `candidates[].target_fetch_owner` | `candidates[].designated_target_fetch_owner_lane_id` |
| `candidates[].extraction_owner` | `candidates[].designated_extraction_owner_lane_id` |

**Policy for v1.**

- Designated lane = the **lexical minimum of the relevant eligible lane set** (`contributing_lanes`).
- **Null remains null** when the operation has not occurred — a candidate never fetched keeps
  `designated_target_fetch_owner_lane_id: null`, and null never means "designated".
- The actual runtime owner is **omitted** from the deterministic artifact. Emitting it later, in a
  Stage 5 run log, is available if operational debugging requires it.
- Schema descriptions must **explicitly distinguish designation from execution**. Because the
  target-fetch and extraction designations are derived from all contributing lanes rather than from a
  dedicated requester set, their descriptions state **administrative responsibility** — they are not
  evidence that the named lane requested or performed the operation.
- `contributing_lanes` remains the honest, complete provenance set, and remains the only field any
  consumer should read to learn which lanes were involved.

The one-owner guarantee is unaffected and is still proved by `http_attempts`: exactly one physical
fetch occurred, which is the finding; which thread performed it is an execution detail.

### 5.5 Schema correction (approved, part of the DV-7 checkpoint)

`schemas/harvest/candidate_pool.v1.json` only — property **names**, `required` lists, and
descriptions, so the document represents deterministic designation truthfully.

**No other schema changes.** `record.v1.json`, `facets.generated.v1.json`, `taxonomy.v1.json`,
`run_manifest.v1.json`, `coverage_report.v1.json`, `discovery_lane.v1.json` and every identity,
facet, request-key and publication schema are untouched.

Registry hazard, mitigated: `schema.py::_build_registry()` loads every `*.json` in `schemas/harvest/`
into one cached registry, so a malformed edit there breaks all 14 suites. The edit is therefore made
in one pass and immediately gated by `test_taxonomy_schema.sh` before anything else runs.

### 5.6 Compatibility with the existing 38 pool assertions

| Assertion | Reads | Effect |
|---|---|---|
| `test_pool.py:217` `contributing_lanes == lanes` (encounter order) | in-memory `p.sources[k]` | unaffected |
| `:235` `reused_in_rounds == [2, 3]` | in-memory | unaffected (already ascending) |
| `:314` `cand["contributing_lanes"] == lanes` | in-memory dict | unaffected |
| `:336` `first_seen_lane_id == …` | in-memory | unaffected — the in-memory name does not change |
| `:366` `test_identical_under_shuffled_worker_and_round_timing` | `to_document()` | still passes; its projection already sorts. Becomes a strict subset of the new assertion; its `:358` comment is superseded (E3) |
| `:371` `test_documents_validate` | `to_document()` | **must be updated** for the renamed properties — the only existing assertion this checkpoint edits |

Predicted: 38/38 green with **one** test updated for the rename. This is verified by running the
suite, never asserted.

### 5.7 New assertions (10)

1. Actual in-memory owner **may vary** with race order (the nondeterminism is real and retained).
2. The serialized designation is **invariant** across all orderings.
3. The actual owner is never exposed in the document as deterministic evidence (static check: the
   in-memory-only names do not appear in `to_document()` output keys).
4. Null operation ownership stays null; null is never replaced by a designation.
5. **Full document** byte-identical across all 12 orderings — the document, not a projection.
6. `reused_in_rounds` sorts **numerically** (`[1, 2, 10]`, never `[1, 10, 2]`).
7. `contributing_lanes` deduplicated and lexically sorted in the document.
8. `source_request_keys` deduplicated and lexically sorted in the document.
9. In-memory state still carries encounter order — normalization is serialization-only.
10. `accounting()` and `budget_charged()` are unchanged by normalization.

### 5.8 Identity and request-key non-impact

`to_document()` touches no `record_id`, `content_id`, `identity_url`, `canonical_url`, `cell_id`,
artifact filename or record sort key; it never calls `urlkey` or `request_key`; `candidate_key` and
`source_request_key` are read, never recomputed. The 42 identity assertions and the facet-identity
proof are structurally out of reach. `test_pool.py:395` continues to assert `pool.py` never mentions
facets.

---

## 6 · N1 — `SourceFetchCache`: one logical fetch, success **and** failure

`pool.py` gains one atomic method (§6.3) but is otherwise unmodified; the coordinator is a new module.

### 6.1 Why the earlier sketches were wrong

- **Fetch-first, acquire-on-success** permits two lanes to issue duplicate concurrent requests.
- **Acquire-first, fetch-after** leaves an orphan when the owner fails: a probe confirmed that a
  source acquired but never established serializes with five schema errors
  (`source_id`, `normalized_url`, `established_by`, `established_at` all `null`).
- `CandidatePool` has no release, abandon or failure transition, so neither order is repairable
  inside the pool alone.

### 6.2 State machine

```
                    ┌───────────────────────────────────────────────┐
   lane calls       │                  ABSENT                       │
 get_or_fetch(key) ─┤  no entry for source_request_key              │
                    └───────────────┬───────────────────────────────┘
                       first claimer│ becomes OWNER (atomic claim)
                                    ▼
                    ┌───────────────────────────────────────────────┐
                    │                 PENDING                       │
                    │  owner executes fetch_fn()                    │
                    │  later lanes WAIT — they issue no request     │
                    └───────┬───────────────────────────┬───────────┘
              200 + body    │                           │ typed failure
                            ▼                           ▼
        ┌───────────────────────────────┐   ┌───────────────────────────────────┐
        │            DONE               │   │             FAILED                │
        │ body + metadata retained      │   │ immutable FailureDescriptor       │
        │ pool row already complete and │   │ pool NOT touched — no row at all  │
        │ schema-valid BEFORE waking    │   │ result_class: adapter_error |     │
        │ any waiter (§6.3)             │   │               infrastructure_error│
        └───────────────┬───────────────┘   └───────────────┬───────────────────┘
                        │ each waiter:                      │ each waiter raises an
                        │ pool.reuse_snapshot(key,lane,rnd) │ EQUIVALENT typed error
                        │ + re-parses the retained body     │ rebuilt from the descriptor
                        ▼                                   ▼
                   terminal — never re-entered in this run
```

`ABSENT → PENDING` is the only racing transition and is resolved by one atomic claim. Terminal states
are never re-opened, so **a failure is never silently retried by a later lane in the same run**, and
**no mid-run revalidation** can occur. `pool.establish_snapshot` raising `SnapshotExists` remains a
second, independent guard.

### 6.3 Success atomicity — `pool.record_established_source()`

The existing two-step `acquire_source` → `establish_snapshot` can leave an incomplete row if the
second call raises. Stage 3 therefore adds **one** atomic method to `CandidatePool`:

```text
record_established_source(key, *, source_id, normalized_url, established_by, established_at,
                          owner_lane_id, body_sha256=None, etag=None, last_modified=None,
                          adapter_mode="index", canonicalization_version=None,
                          attempts=1, retries=0, redirect_hops=0,
                          conditional_revalidations=0, budget_charged=None)
```

Semantics: build the complete row **off to the side**, validate it, and insert it into
`self.sources` **only** if validation passes — one lock, one visible transition. On any failure it
raises and `self.sources` is left exactly as it was. `acquire_source` and `establish_snapshot` are
**retained unchanged** so all existing assertions keep passing; the coordinator uses only the new
atomic method.

A cache entry does **not** become `DONE` and does **not** release waiters until that complete,
schema-valid row is present.

Required tests (4):

1. Successful completion exposes a **complete** source row *before* any waiter wakes.
2. An insertion/validation failure leaves **no** source row.
3. `to_document()` remains schema-valid after **every** failure path.
4. No waiter can observe `PENDING` state as a completed snapshot.

### 6.4 Failure descriptor — not a shared exception instance

Exception objects carry traceback state and are unsuitable as shared immutable cache values. A
`FAILED` entry retains an immutable `FailureDescriptor`:

```text
FailureDescriptor(error_type, reason, status, message, attempts, budget_charged, result_class)
```

`result_class ∈ {adapter_error, infrastructure_error}`. Each waiter **receives or raises an
equivalent typed failure reconstructed from the descriptor** — not the owner's exception object.
Tests compare `type`, `reason`, `status` and `message`; **never object identity**.

### 6.5 Crash guarantee — stated accurately

For Stage 3's **in-process** implementation:

- Any ordinary Python exception raised by `fetch_fn`, **including unexpected `Exception` subclasses**,
  transitions the entry to `FAILED` and unblocks every waiter.
- This is a `try/finally` guarantee **within a live interpreter only**. It does **not** protect
  against process termination, interpreter termination, or machine failure, and this plan makes no
  such claim.
- Cross-process stale-owner recovery belongs to Stage 5's persistent store implementation, alongside
  the existing `domainlease.py` stale-lease machinery.

Test naming follows: the relevant test is named for *an exception in a live process*, never
"owner crash".

### 6.6 Store protocol — the Stage 5 injection boundary

A `dict` holding `threading.Event` objects and Python exceptions is **not** substitutable by a
filesystem mapping, and this plan does not imply that it is. The boundary is a **protocol**:

```text
claim(key)   -> True if this caller became the owner, False if an entry already exists
wait(key)    -> blocks until terminal; returns (state, payload)
complete(key, result)             -> DONE, then releases waiters
fail(key, failure_descriptor)     -> FAILED, then releases waiters
```

- **Stage 3** ships `InMemoryStore` — one `threading.Lock` for the entry table, one
  `threading.Event` per entry. Waiters hold no lock while blocked.
- **Stage 5** may later ship a lockdir/filesystem-backed implementation with stale-owner recovery,
  reusing `scripts/lib/lockdir.sh` idioms. It implements the same four operations; it does not reuse
  the Stage 3 `Entry` object.

`SourceFetchCache(store=InMemoryStore())` takes the store by injection.

### 6.7 Response-body cache contract

| Property | Specification |
|---|---|
| **Owning module** | `src/harvest/sourcecache.py`, class `SourceFetchCache` |
| **Key** | `source_request_key` (16 hex) — the same key `pool.sources` uses, nothing else |
| **Stored on DONE** | `status`, `final_url`, `headers`, `body` (bytes), `body_sha256`, `elapsed_sec`, `redirects`, `permanent_redirect`, `attempts`, `retries`, `redirect_hops`, `budget_charged`, `established_at` |
| **Stored on FAILED** | the `FailureDescriptor` of §6.4 |
| **Lifecycle** | Created empty per run, keyed by `harvest_run_id`; terminal entries immutable; the whole cache is discarded at run end. No cross-run persistence — that is Stage 6 |
| **Concurrency** | Per §6.6. Owner sets the terminal state and releases waiters in a `finally` |
| **Maximum body handling** | None of its own: `HttpClient` enforces `max_response_bytes` (8 MiB) and raises `ResponseTooLarge` before a body materializes. A `total_bytes` counter is recorded in run accounting |
| **Relationship to CandidatePool** | Strictly upstream, one-way. The cache is the **only** caller of `record_established_source` and `reuse_snapshot`. `pool.py` has no knowledge of the cache |
| **Fixture implementation** | `fetch_fn` closes over a real `HttpClient` built with `FixtureOpener`, so the identical code path runs offline and (later) live |
| **Stage 5 injection point** | the `store` protocol of §6.6 |

### 6.8 Coordinator concurrency tests (6)

1. Three simultaneous lanes, one source → `fetch_fn` invoked **once**; all three receive the same body.
2. Three simultaneous lanes, failing source → `fetch_fn` invoked **once**; all three receive an
   equivalent typed failure (type, reason, status, message compared — not identity).
3. After (2): `pool.sources == {}` and `to_document()` validates clean.
4. A successful body is reused with **zero** further `fetch_fn` calls and zero budget charge.
5. One logical owner may still perform multiple budgeted HTTP attempts (1 redirect + 1 retry ⇒
   1 owner, 3 attempts, budget charged 3).
6. An unexpected non-`HttpError` exception in a live process still transitions to `FAILED` and
   unblocks every waiter — no deadlock.

---

## 7 · C4 — the `http_4xx` corrective checkpoint (approved, commits **before** DV-7)

**Root cause.** `src/harvest/httpclient.py:85-87` — `ClientError.reason = "http_5xx"` for every
non-retryable 4xx, so a 404 on a dead configured feed is reported as a server error.

**Change.** `ClientError.reason = "http_4xx"`, and the misleading comment removed. One line.

**Preserved:** `RobotsDenied.reason == "robots_denied"` (raised at `httpclient.py:492`, before any
status exists, so it cannot be reclassified) · `ServerError`/`HttpError` keep `http_5xx` · the numeric
`status` on every HTTP failure that has one.

**No schema change:** `run_manifest.v1.json → source_preflight[].reason` and
`cell_artifact.v1.json → sources[].reason` are both `["string","null"]`, not enums. Verified.

**Files.**

```text
M  src/harvest/httpclient.py            one line + comment
M  tests/harvest/test_http.py           ~5 new assertions, ≤1 modified
M  docs/harvest/IMPLEMENTATION_PLAN.md  §3 infrastructure_error vocabulary gains http_4xx
```

**New assertions:** 404 ⇒ `ClientError`, `reason == "http_4xx"`, `status == 404` · 401 and 403
likewise · robots denial still `robots_denied`, **not** `http_4xx` · 500 after retries still
`http_5xx` with `status == 500` · `preflight()` on a 404 ⇒ `result == "infrastructure_error"`,
`reason == "http_4xx"`, `http_status == 404`.

**Gate.** All **387** existing assertions plus the new focused HTTP assertions green,
`verify_protected_baseline.sh` and all three checkers exit 0, the 508 untracked re-verified. Committed
**alone**, before DV-7 and before any adapter file exists.

---

## 8 · Ordered checkpoints

Each ends with its own commit. **C4 and DV-7 are never combined.**

| # | Checkpoint | Commit contains | Gate |
|---:|---|---|---|
| **1** | **Stage 3 plan approval** (this document) | `STAGE_3_IMPLEMENTATION_PLAN.md`, `TODO.md` | documentation only; 387 unchanged |
| **2** | **C4 — `http_4xx`** | `httpclient.py`, `test_http.py`, `IMPLEMENTATION_PLAN.md` | 387 + new HTTP assertions green |
| **3** | **DV-7 — pool determinism and ownership semantics** | `pool.py`, `candidate_pool.v1.json`, `test_pool.py` | previous total + 10 new green; `test_taxonomy_schema.sh` run **first** after the schema edit |
| **4** | **Stage 3 — coordinator and adapters** | everything in §9 | full gate of §11 |

Checkpoint 4 is itself built in order, each step gated by its narrowest test before the next begins:
`base` + registry → `fixtures.py` + fixtures + `check_fixtures.py` → `sourcecache.py` → `feed` →
`jsonapi` → `seed` → concurrency → full regression.

---

## 9 · Exact files

**Checkpoint 2 — C4**

```text
M  src/harvest/httpclient.py
M  tests/harvest/test_http.py
M  docs/harvest/IMPLEMENTATION_PLAN.md
```

**Checkpoint 3 — DV-7**

```text
M  src/harvest/pool.py                        _normalized(), to_document(),
                                              record_established_source()
M  schemas/harvest/candidate_pool.v1.json     property names, required, descriptions
M  tests/harvest/test_pool.py                 +10 assertions, 1 updated for the rename
```

**Checkpoint 4 — Stage 3**

```text
A  src/harvest/sourcecache.py                 SourceFetchCache, Entry, FailureDescriptor,
                                              InMemoryStore, the claim/wait/complete/fail protocol
A  src/harvest/adapters/__init__.py           registry, AdapterNotImplemented
A  src/harvest/adapters/base.py               Adapter ABC, RawCandidate, AdapterResult,
                                              result/reason vocabulary constants
A  src/harvest/adapters/feed.py               RSS 2.0 + Atom            (22 sources)
A  src/harvest/adapters/jsonapi.py            items_path + field_map     (2 sources)
A  src/harvest/adapters/seed.py               bounded index, depth hard-fixed at 1  (1 source)
A  src/harvest/fixtures.py                    loader, FixtureOpener, robots fixture serving
A  tests/fixtures/harvest/MANIFEST.json       fixture_id -> sha256, bytes, authored_at, provenance
A  tests/fixtures/harvest/sources/*.json      25 — one per configured source
A  tests/fixtures/harvest/robots/*.json       19 configured hosts (+ optional policy extras)
A  scripts/harvest/check_fixtures.py          existence + manifest hashes + host completeness
A  tests/harvest/test_adapters.py
A  tests/harvest/test_source_cache.py
A  tests/harvest/test_adapter_concurrency.py
A  tests/test_taxonomy_adapters.sh
A  tests/test_taxonomy_source_cache.sh
A  tests/test_taxonomy_adapter_concurrency.sh
M  docs/harvest/TODO.md                       Stage 3 boxes ticked as each test passes
```

**Never modified by Stage 3:** `scripts/harvest/check_config.py` (DV-1) · `src/harvest/urlkey.py` ·
`src/harvest/slug.py` · `src/harvest/request_key.py` · `src/harvest/facets.py` ·
`src/harvest/records.py` · `schemas/harvest/record.v1.json` · `schemas/harvest/taxonomy.v1.json` ·
`config/harvest/**` · `.gitignore` beyond its single added line · the 18 protected files.

---

## 10 · Source configuration and fixtures

### 10.1 No source configuration change

The deferred per-source `query_order_policy` field is **not added**, this stage or later, unless a
source demands it:

- `taxonomy.v1.json → $defs/source` is `additionalProperties: false`, so the field would require
  editing a Stage 1 schema and its own deviation.
- **No configured source needs it.** Both `jsonapi` URLs carry only **distinct** keys
  (`conditions[term]`/`per_page`/`order`; `tags`/`query`/`hitsPerPage`). Under `preserve` with a fixed
  config string they are already stable.
- Flipping the policy **changes the key** and is therefore cache-invalidating: `federal-register-ai`
  `e24f8274…` → `e23045d8…`, `hn-algolia` `ae85b6b0…` → `079d324f…`. An unused knob buys silent
  invalidation risk for nothing.

A test asserts all 25 sources resolve through the default and that no code under
`src/harvest/adapters/` passes a non-default policy.

### 10.2 Wire fidelity

The request is issued against the **configured URL verbatim**; canonicalization is used only for the
request key and for `normalized_url`. This matters: `urlkey.canonicalize_string` rewrites
`artificial+intelligence` to `artificial%20intelligence` on the Federal Register URL. Both decode to a
space, but Stage 3 does not gamble a live endpoint on that. Pinned by a test.

### 10.3 Source fixtures — synthetic, honestly labelled

**No live harvest.** Fixtures are hand-authored, format-conformant synthetic documents, not
recordings. Synthetic beats recorded here: it needs no network so it cannot violate the
no-live-request rule; it carries no third-party content into a tracked repository; and each fixture
can be authored to exercise one specific behaviour.

```json
{ "fixture_id": "fx_aws_ml_blog", "source_id": "aws-ml-blog",
  "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
  "provenance": "synthetic",
  "authored_at": "2026-07-XX",
  "authored_against": "RSS 2.0 specification",
  "status": 200,
  "headers": { "content-type": "application/rss+xml; charset=utf-8" },
  "body_b64": "…" }
```

`captured_at` is used **only** for a genuinely recorded response, which additionally carries
`provenance: "recorded"` and the capture URL. `check_fixtures.py` refuses `provenance: "recorded"`
without `captured_at`, and refuses `captured_at` on a `synthetic` fixture.

### 10.4 Robots fixtures — origin-specific, host-exact

Robots policy is **origin/host-specific**. Completeness is measured against the **exact host of each
configured source URL**: a fixture for `arxiv.org` does **not** satisfy a source hosted at
`rss.arxiv.org`.

The 19 configured hosts, from the config:

```text
aws.amazon.com · blog.cloudflare.com · blog.google · blogs.microsoft.com · blogs.nvidia.com
engineering.fb.com · github.com · hn.algolia.com · huggingface.co · netflixtechblog.com
openai.com · rss.arxiv.org · simonwillison.net · techcrunch.com · www.anthropic.com
www.federalregister.gov · www.nist.gov · www.oneusefulthing.org · www.producthunt.com
```

These are **policy fixtures**: synthetic robots documents that exercise our RFC 9309 matcher. They
are **not** claimed to reproduce any real site's current robots policy, and none carries recorded
provenance.

```json
{ "host": "rss.arxiv.org", "status": 404, "body": "",
  "provenance": "synthetic", "authored_at": "2026-07-XX",
  "authored_against": "RFC 9309",
  "policy_intent": "absent robots.txt — RFC 9309 allow-all" }
```

Served by `FixtureOpener` at `https://<host>/robots.txt`, so `RobotsCache` and the real
`httpclient.RobotsRules` matcher run unmodified. Extra fixtures for non-configured hosts (e.g.
`export.arxiv.org` for a `Disallow: /` case) may exist as targeted policy tests but **do not count
toward configured-host completeness**.

`check_fixtures.py` asserts: every configured source has a source fixture; every source fixture maps
to a configured source; **every configured host has a robots fixture keyed by that exact host**; all
`MANIFEST.json` SHA-256 values match; and the provenance rules of §10.3 hold. A request to a host
without a fixture **fails the test** rather than silently being allowed.

---

## 11 · Tests, counts and the regression gate

| Suite | Status | Planned assertions |
|---|---|---:|
| Existing 14 suites | unchanged | **387** |
| `test_http.py` | C4 additions | +5 |
| `test_pool.py` | DV-7 additions (§5.7) + §6.3 atomicity (4) | +14 |
| `test_source_cache.py` | new — §6.8 (6) + descriptor, lifecycle, store protocol | ~19 |
| `test_adapters.py` | new — feed ~20 · jsonapi ~12 · seed ~14 · fixtures/robots ~10 · negative ~10 · determinism/policy ~8 | ~74 |
| `test_adapter_concurrency.py` | new — real threads and subprocesses | ~10 |

Target on completion: **~509 assertions**, zero regressions.

Adapter-suite highlights: RSS and Atom both parse · missing date ⇒ `None`, never invented · relative
link resolved against the feed base · overflow past `max_candidates` dropped in **document order**,
never by score · empty-but-valid feed ⇒ `zero_result: no_items_in_window`, never
`feed_parse_error` · malformed XML ⇒ `adapter_error: feed_parse_error` · seed depth never exceeds 1,
with a static proof that no expansion path exists · empty `path_prefix_allowlist` qualifies nothing ·
robots denied on a child drops only that child · **no child body is fetched** · unknown adapter ⇒
`AdapterNotImplemented` · `sitemap` and `model_search` raise rather than no-op · no facet field ever
written · lane ID never becomes evidence · no network symbol in `src/harvest/adapters/`.

**Offline determinism.** `HARVEST_CLOCK_UTC` pins the clock; `HttpClient` takes injected
`sleep`/`monotonic`/`rng`/`opener`; leases use a temp root; any unfixtured URL raises. The full pool
document must be byte-identical across 12 shuffled lane/source orderings. Every wrapper asserts
`git status --porcelain --untracked-files=no -- state/ config/` is clean, per the existing pattern.

**Per-domain pacing**, reused unmodified: `github.com` 5 sources at 2.0 s ⇒ ≥8 s serialized;
`rss.arxiv.org` 2 at 5.0 s; `blog.google` 2 at 2.0 s; `blogs.microsoft.com` 10.0 s. All 19 hosts are
`max_concurrency: 1`. The five `github.com` feeds live in three different cells, so cross-cell
parallelism does not relieve them — they serialize on the shared `next_allowed_at` gate.

**Budgets**, reused unmodified: run → cell (`cell_max_requests` 60 / `cell_budget_sec` 300) → adapter
(`adapter_max_requests` 25 / `adapter_budget_sec` 120), each source additionally capped by its own
`max_requests`. Config totals: **sum(max_requests) = 74**, **sum(max_candidates) = 144** across 25
sources; the heaviest cell is `discourse__community` at 4 sources / 8 requests. Charge-before-attempt
already holds in `httpclient._attempt`. Stage 3 adds the same `would_exceed_time` check before a
**lease** wait, so mandatory pacing is charged rather than silently overrunning
`adapter_budget_sec`. `pool.accounting()` and `budget_charged()` must agree with the client's
attempt counters — asserted.

---

## 12 · Rollback criteria

**Checkpoint 2 (C4).** `git checkout -- src/harvest/httpclient.py tests/harvest/test_http.py
docs/harvest/IMPLEMENTATION_PLAN.md`, then rerun 387.

**Checkpoint 3 (DV-7).** `git checkout -- src/harvest/pool.py
schemas/harvest/candidate_pool.v1.json tests/harvest/test_pool.py`, then rerun the checkpoint-2 total.

**Checkpoint 4 (Stage 3).** Purely additive except `TODO.md`:
`rm -rf src/harvest/adapters tests/fixtures/harvest src/harvest/sourcecache.py
src/harvest/fixtures.py scripts/harvest/check_fixtures.py tests/harvest/test_adapters.py
tests/harvest/test_source_cache.py tests/harvest/test_adapter_concurrency.py
tests/test_taxonomy_adapters.sh tests/test_taxonomy_source_cache.sh
tests/test_taxonomy_adapter_concurrency.sh`, then `git checkout -- docs/harvest/TODO.md`.

**Triggers.** Any prior assertion turning red · any existing test needing an edit beyond the single
documented DV-7 rename · protected-baseline failure · drift in the 508 pre-existing untracked files ·
discovering that an adapter or the coordinator cannot satisfy the committed ownership contract without
a further `pool.py` change — in which case it returns for an explicit deviation rather than being bent
in code.

---

## 13 · Stage 4 opening condition

Stage 4 (extract, classify, verify, dedupe) may begin only when **all** of the following hold
simultaneously, in one final run:

1. `test_taxonomy_adapters.sh`, `test_taxonomy_source_cache.sh` and
   `test_taxonomy_adapter_concurrency.sh` are green;
2. every prior assertion — the 387 plus the C4 and DV-7 additions — is green **in that same run**;
3. `verify_protected_baseline.sh`, `check_facets.py`, `gen_facet_schema.py --check` and
   `check_config.py` all exit 0, and `check_config.py` is byte-unchanged;
4. `check_fixtures.py` exits 0 — 25 source fixtures, **19 configured-host** robots fixtures, manifest
   hashes matching, provenance rules enforced;
5. the full-document byte-determinism proof is green over 12 shuffled orderings;
6. the coordinator proofs are green: one logical fetch on success **and** on failure, no source row
   after any failure path, `to_document()` schema-valid after every failure path;
7. no network symbol appears in `src/harvest/adapters/` or `src/harvest/sourcecache.py`, and **no live
   request has been performed**;
8. `state/taxonomy_harvest/` and `data/harvested/` remain absent; the 508 pre-existing untracked files
   are byte-identical; `.gitignore` still shows exactly `1 insertion(+)` against the anchor;
9. a Stage 3 completion handoff is committed; and
10. **explicit approval is given.** Green tests alone do not open Stage 4.
