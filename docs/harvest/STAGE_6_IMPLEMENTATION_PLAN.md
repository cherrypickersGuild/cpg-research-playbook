# Stage 6 — target fetching and verification: implementation plan

```text
Status: APPROVED AS THE PLAN OF RECORD — CHECKPOINT-BY-CHECKPOINT · NO CHECKPOINT APPROVED
```

**Approved on 2026-07-30 as the plan of record, and only as a checkpoint-by-checkpoint plan of
record.** The approval settles what Stage 6 *is* and the order it will be built in. It authorizes no
production code, no test, no script, no schema, no config, no filesystem write outside `docs/`, **no
live network request**, and **not S6-1**. Every checkpoint S6-1 … S6-C still requires its own separate
approval, named explicitly, before any file outside `docs/` changes (§13, §15).

**The two open design decisions are RESOLVED** — D6-A and D6-B, both as recommended, recorded in §12.
Resolving a decision authorizes the *shape* of a future change, never the change itself: the
checkpoint each one unblocks (S6-5, S6-6) remains unapproved and unimplemented.

**Corrected on 2026-07-30 — S6-1 fixture scope.** An S6-1 preflight stopped without editing a file
because this plan's own corpus wording determined no literal, implementable fixture set. The correction
is recorded as erratum **E15** (§14) and applied in place: two cases relocated to S6-4, three transport
cases removed from Stage 6 outright, and the corpus replaced by two literal tables (§11, S6-1). Every
other previously approved Stage 6 decision — including D6-A and D6-B — is unchanged.

**Corrected on 2026-07-30 — canonical domain authority.** An S6-3 preflight stopped without editing a
file because this plan said same-domain canonical trust "is implemented as identical host", which the
committed `urlkey.registrable_host` contradicts. Recorded as erratum **E16** (§14) and applied in §4,
§9.7 (CF-15), §11 (S6-1 fixture #3 and the S6-3 test allocation). **`urlkey.registrable_host` is the
single authority**; no second host comparison is added and the helper itself is unchanged. D6-A and
D6-B remain resolved and unchanged, and no S6-3 implementation is approved or present.

**Date:** 2026-07-30 · **Branch:** `main`

```text
stage_5_closing_commit:      bc920b5b8b57907165b7a5f8d47239383b974212   S5-7
stage_5_closeout_commit:     6bf7f51362863bdc12749a2cc86fb8a0668bc737   S5-C
stage_5_completion_handoff:  docs/harvest/handoffs/HANDOFF_STAGE_5_COMPLETE_2026-07-30.md
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  main synchronized with origin/main at 6bf7f51
assertions_at_plan_time:     1,324 across 30 suites, all green
untracked_baseline:          508 files, byte-identical; drift 0
```

The Stage 5 handoff records `origin/main at e178586; S5-6 and S5-7 unpushed` — that is a **closeout
snapshot taken before the final push** and is historically correct. The authoritative Git state is
the synchronized `6bf7f51` above.

Predecessors, still valid and read-only: `IMPLEMENTATION_PLAN.md` (§2 URL contract and alias trust,
§3 sources, §6 budgets and enrichment, §10 filesystem layout and ignore rules, §13 allowed and
prohibited paths) · `STAGE_4_IMPLEMENTATION_PLAN.md` §5 (permanent checkpoint execution policy,
adopted unchanged) · `STAGE_5_IMPLEMENTATION_PLAN.md` (§3 contracts, §4 risk tiers, §7 commit and
stop boundaries, §10 opening conditions) · `HANDOFF_STAGE_5_COMPLETE_2026-07-30.md` (inherited
constraints, §7). **Prior plans and handoffs are never edited.** Where an older document conflicts
with shipped code, the **code** is authority; such conflicts are recorded in §14.

---

## 1 · Scope

Stage 5 ended with a complete, deterministic, atomic artifact tree in which **every record is
honestly unverified**: `access_status: "not_checked"`, `verification_status: "unverified"`,
`http_status: null`, `content_hash: null`, `canonical_url == identity_url`, `url_aliases: []`, and
`target_fetch_owners: 0` — which is exactly why `publication_eligible` derives to `false`.

Stage 6 fetches the item's **own page** and records what the fetch observed. It supplies facts;
**it re-judges nothing.** No score moves, no category changes, no facet is reassigned, no identity is
recomputed, and no accepted record becomes rejected.

### 1.1 Goals

1. A target-page fetcher built on the **committed** `HttpClient` — one fetch per canonical candidate
   per run, owned through the committed `pool.acquire_target_fetch` gate.
2. Target-derived evidence on every accepted record: `access_status`, `http_status`, `content_hash`,
   `last_checked_at`, `verification_status: "fetched"`, `verification_evidence`.
3. Redirect and `rel=canonical` adjudication under the committed trust tiers: `canonical_url` and
   `url_aliases` may move; `identity_url`, `record_id` and `content_id` **never** do.
4. Publication eligibility that can honestly become `true` — derived, never asserted (§8).
5. A fixture corpus for target pages, discharging **CF-3**, with **no live request in any test**.
6. One separately approved, bounded live-smoke checkpoint that proves the contracts hold against a
   real host without ever claiming byte-reproducibility (§11).

### 1.2 Explicit non-goals

Stage 6 does **not**:

- **re-judge anything.** A fetched body is never relevance, quality, audience-fit or freshness
  evidence, never facet evidence, and never a reason to accept or reject. `verify.py`, `classify.py`,
  `facetassign.py`, `coverage.py`, `facets.py`, `pool.py`, `dedupe.py`, `extract.py` and `urlkey.py`
  stay **byte-unchanged**;
- **change identity.** `identity_url` is fixed at first acceptance and is immutable forever. No
  redirect, canonical tag, body or config rule may mint, merge or move a `record_id` or `content_id`;
- **extract content from a body.** Body parsing is bounded to exactly two purposes: the
  `content_hash` the committed `Response` already computes, and `<link rel="canonical">`. No title,
  summary, author, date, language or `content_type` is read from a target page;
- **produce `corroborated`, `contradicted` or `snippet_only`.** Those need cross-source content
  comparison or editorial judgement. Only `fetched` is earned by a fetch;
- **implement the fetched-body fragment-anchor rules** (`IMPLEMENTATION_PLAN.md` §2.4 cases 12e/12f).
  They would let a body change `identity_url`, which §1.2 forbids. Carried forward, unimplemented;
- **resolve an alias conflict, or merge two records.** Conflicts are recorded and counted, never
  resolved; `resolve-alias` and `domain_migrations`-driven merges are later work;
- **promote anything.** No `data/harvested/` write, no publication manifest, no promotion journal, no
  staging or rollback tree, no `promote` / `refresh` / `linkcheck` / `diff` / `compare-runs`
  subcommand. Eligibility becoming `true` is a *fact about a run*, not a promotion;
- **run cells or fetches concurrently** — see §9.1 (CF-1). Throughput is not a Stage 6 goal;
- implement `sitemap` or `model_search` adapters (Stage 9 / later) · migrate the legacy AX corpus
  (Stage 7) · wire `scripts/validate_task.sh` (Stage 8, CF-4) · recalibrate any threshold, weight,
  half-life or the `0.68 / 0.32` split (Stage 9, §9.5);
- **edit `config/`.** No `target_max_requests` policy key is added; §7.5 explains why, and CF-6 stays
  untriggered as a consequence;
- add a second HTTP client, robots matcher, tokenizer, hasher, serializer, artifact writer, validator
  or cache. Every one of those already exists exactly once and is reused.

### 1.3 What Stage 6 does not modify

The 18 protected files · the 508 pre-existing untracked paths · `.gitignore` (stays at exactly
`1 insertion(+)` against the anchor; the committed `/state/taxonomy_harvest/` line already covers the
runtime namespace) · every file under `config/harvest/` · `data/**` · production `state/` outside
`state/taxonomy_harvest/` · every prior plan and handoff · `scripts/harvest/check_config.py`
(byte-frozen by DV-1) · the nine Stage 4 modules listed in §1.2 · every existing schema **except** as
decided in §12 · **any existing test file**.

---

## 2 · The boundary: source discovery vs. target-page fetching

These are two different operations against two different key spaces, and Stage 6's single most
important structural rule is that they never merge.

| | Source discovery *(Stage 3, shipped)* | Target-page fetching *(Stage 6)* |
|---|---|---|
| What is fetched | the feed, API endpoint or index page that **surfaces** items | the item's **own** page |
| Unit of work | one `source_request_key` | one `candidate_key` (canonical identity) |
| `adapter_mode` | `"index"` (`adapters.base.ADAPTER_MODE`) | `"record"` |
| Ownership | `pool.record_established_source` via `SourceFetchCache` | `pool.acquire_target_fetch` |
| Counter | `request_accounting.source_fetch_owners` | `request_accounting.target_fetch_owners` |
| Yields | candidates | **no candidates, ever** |
| Runs for | every configured source in every selected cell | **accepted candidates only** |

**A target page yields no candidates.** No adapter is invoked on one, nothing is parsed out of one to
be harvested, and no link on one is followed. This is the line between an enrichment step and a
crawler, and it is asserted, not merely intended.

**Target fetching is post-acceptance.** It runs after `verify.verify_all` and
`facetassign.assign_all`, over the accepted set only. Three consequences, all deliberate: the fetch
count is bounded by the accept count rather than the candidate count (4 rather than 109 on the
committed fixture corpus); a fetched body cannot influence a decision that was already made, which is
what makes §1.2's no-re-judging rule structural rather than a promise; and a rejected candidate is
never fetched, so rejection stays a metadata verdict and the rejection log keeps its committed shape.

**Position in the pipeline** — everything above the new step is called exactly as committed:

```text
adapters.discover  →  dedupe.group  →  extract.normalize_all  →  classify.classify_all
      →  verify.verify_all  →  facetassign.assign_all
                                   │
                      accepted ────┤──── rejected  →  rejection log      (unchanged)
                                   ▼
                    ┌──────────────────────────────┐
                    │  S6-4  ownership gate        │  pool.add_candidate
                    │        (once per candidate)  │  pool.acquire_target_fetch
                    │  S6-2  fetch_target          │  the committed HttpClient
                    │  S6-3  adjudicate            │  redirects + rel=canonical
                    └──────────────────────────────┘
                                   ▼
              S6-5  records.make_full_record  →  S5-1 … S5-7 artifact tree
                                                 (writer, journal, manifest, pointer unchanged)
```

---

## 3 · Target-fetch ownership and URL deduplication

**The fetch unit is `candidate_key`**, the canonical identity produced by `request_key.candidate_key`
inside `pool.add_candidate` — not the raw `target_url`, not the record, and not the (cell, URL) pair.

```text
pool.add_candidate(target_url, lane_id)          → (candidate, is_new)   canonical identity
pool.acquire_target_fetch(candidate_key, lane_id) → True exactly once per candidate per run
```

Guarantees Stage 6 must assert:

- **Once per run, per canonical identity.** Two sources in one cell surfacing the same URL produce one
  candidate and **one** fetch. `acquire_target_fetch` returning `False` is the normal path for the
  second sighting, not an error.
- **Once across topics.** `candidate_key` is derived from the canonical URL alone, so the same URL
  accepted under two topics is **one fetch** whose evidence is written onto **both** records
  (`record_id` is per-topic, `content_id` and the fetch are not). This is the one place Stage 6 makes
  cross-topic behaviour observable. It is proved at **S6-4 with test-local synthetic candidate and
  pool inputs** — not with a fixture, and not by editing a source fixture or a topic config: a shared
  identity is a property of what the feeds surfaced, which no target-page fixture can create (§11,
  S6-1 and S6-4). The committed Stage 4 dedupe contract is not reopened or re-proved; what S6-4 adds
  is only the Stage 6 fact that **one identity means one fetch, and one outcome reaches every record
  owning it.**
- **Tracking-parameter and default-port variants collapse** before the fetch, because canonicalization
  already ran. `?ref=` and `?source=` variants stay distinct and are therefore two fetches — the
  committed conservative direction (§14, `canonicalization.v1.json`).
- **Two distinct candidates that redirect to one final URL are two fetches.** Identity is per
  candidate; discovering the coincidence after the fact does not retroactively merge them, it produces
  an alias on each (§4). Preferring a false negative over a destructive merge is the committed rule.
- **No new cache.** `SourceFetchCache` is deliberately **not** reused: it calls
  `pool.record_established_source`, which would inflate `source_fetch_owners` with target fetches and
  corrupt the accounting distinction §2 exists to preserve. Within one sequential run the ownership
  gate *is* the deduplication, and a second store would be a second source of truth.
  `conditional_requests.enabled` is `false` in the committed policy, so
  `conditional_revalidations` stays `0` and no ETag/Last-Modified revalidation path is built.
- **Ownership designation stays honest.** `designated_target_fetch_owner_lane_id` becomes non-null
  once a fetch is acquired, and remains the committed *designation* derived from the whole lane set
  (DV-7) — never the lane that happened to run it.

---

## 4 · Canonical URL, redirects, and `rel=canonical`

Adjudication is a **pure function** in one module (S6-3): it reads
`config/harvest/canonicalization.v1.json` **as data**, and holds no configured host, domain or rule
id as a string literal — the S4-3A/S4-4 precedent, pinned the same way.

```python
adjudicate(identity_url, canonical_url, outcome, config) -> (canonical_url, url_aliases, conflicts)
```

**Invariant, asserted in every case below:** `identity_url`, `record_id` and `content_id` are
byte-identical before and after. There is no code path from a fetch to an identity.

| Observation | `canonical_url` | `url_aliases` | `access_status` |
|---|---|---|---|
| 200, `final_url == url` | unchanged | — | `ok` |
| Every hop 301/308 (`Response.permanent_redirect` true) | `final_url` | `+{kind: "permanent_redirect", evidence: {http_status, location}}` | `redirected` |
| Any 302/307 in the chain | **unchanged** | **none** | `ok` — the temporary final URL is noted in `verification_evidence` only |
| `rel=canonical`, **same registrable domain**, absolute, syntactically valid, non-circular, robots-allowed | that URL | `+{kind: "canonical_tag", evidence: {rel_canonical}}` | as fetched |
| `rel=canonical`, **different registrable domain**, with a matching `domain_migrations` rule | that URL | `+{kind: "domain_rule", evidence: {rule_id, config}}` | as fetched |
| `rel=canonical`, **different registrable domain**, no rule and no independent 301/308 to the same target | **unchanged** | **none** | as fetched · **alias conflict recorded** |
| Malformed, relative-unresolvable, circular (A→B→A), or two conflicting `<link rel=canonical>` | **unchanged** | **none** | as fetched · **alias conflict recorded** |

Notes that are decisions, not details:

- **"Same registrable domain" is decided by the committed `urlkey.registrable_host`, and by nothing
  else.** Corrected on 2026-07-30 (§14, E16). This plan previously said the check "is implemented as
  identical host", justified by there being no public-suffix library. The justification was true and
  the conclusion was wrong: `urlkey.registrable_host` was committed at Stage 1 for exactly this
  purpose — its docstring says "used only for same-domain trust checks" — and it makes the same
  no-public-suffix tradeoff deliberately, taking the last two labels.

  The operative rule, therefore:

  - **same registrable domain** ⇒ the same-domain branch. Exact hostname equality is a *subset* of
    this: two different hostnames that `registrable_host` maps to one value (`example.com` and
    `www.example.com`; `a.example.com` and `b.example.com`) take the same-domain branch.
  - **different `registrable_host` values** ⇒ the cross-domain branch.
  - Every other prerequisite on those rows is **unchanged**: absolute and syntactically valid,
    non-circular, robots-allowed, and — on the cross-domain row — a matching `domain_migrations` rule
    or independent 301/308 evidence.

  Stage 6 adds **no second hostname comparison, no public-suffix implementation and no special-case
  host list**, and this checkpoint does not change `registrable_host` itself. The broader Stage 1
  URL-identity design is not reopened or re-audited.
- **Robots is checked before a canonical tag is trusted**, via the committed
  `HttpClient.robots.allowed` — no second matcher. That check may itself cost an HTTP attempt, which
  is budgeted and accounted like any other.
- **`rel=canonical` extraction is bounded**: stdlib `html.parser` over at most the first
  `CANONICAL_SCAN_BYTES` of a decoded HTML body, `<head>` only, stopping at `</head>`. Non-HTML
  content types are not scanned at all. No regex over markup, no new dependency, no full DOM.
- **A conflict never mutates a record.** Both records survive unchanged, no identity moves, nothing is
  deleted, and `resolution` is written as `"unresolved"` — the committed §2.3 semantics.
- **`url_aliases` is sorted and deduplicated by `(kind, url)`** so two runs over one input produce one
  byte sequence.

---

## 5 · Robots, throttling, retry, timeout, cache and budget contracts

Every contract here is **already implemented and tested** in `httpclient.py`, `domainlease.py` and
`budget.py`. Stage 6's obligation is to *use* them on a new class of URL and to map their outcomes
honestly — not to reimplement or relax one.

### 5.0 · Transport ownership — the line Stage 6 does not cross

Stated first because it decides what the fixture corpus may contain, and a corpus that simulated
transport would quietly become a second HTTP implementation.

- **Retry behaviour is owned by the committed `HttpClient`** (`retry.max_attempts`, backoff, jitter,
  `Retry-After`, `retry_on_status`), and is already covered by 80 assertions in
  `tests/test_taxonomy_http.sh`. Stage 6 adds no retry logic and **duplicates no retry test.**
- **Timeout and response-size enforcement are owned by the committed `HttpClient`**
  (`connect/read/request_timeout_sec`, `max_response_bytes`, `_read_capped`). Stage 6 adds no timeout
  or size logic and duplicates neither test.
- **`targetfetch.py` consumes only the injected client's final response or its typed error.** It sees
  one `Response` or one `HttpError`, and it never sees a partial body. **Amended by S6-6A (erratum
  E17):** it *does* read the DV-8 `FetchAccounting` the client has already frozen onto that final
  response or error, and carries it outward unread — exactly as it already carries `body` and
  `content_type`. What it still does not do is form an opinion: it never branches on an attempt, a
  hop count or a retry, and it independently implements and interprets **no** retry, redirect,
  timeout, body-size or transport policy. Reporting a number the client computed is not owning the
  behaviour that produced it; recomputing or second-guessing it would be.
- **S6-2's tests raise the existing typed errors from a stub or injected client** to verify the
  `access_status` mapping. That is the whole of Stage 6's failure-mode surface, and it needs no
  fixture, no socket and no transport simulation.
- **Stage 6 adds no fixture directive DSL.** No `raise`, no `responses` sequence, no `delay`, no
  generated oversized body, and nothing equivalent. A fixture is **static bytes with a status and
  headers** — the committed `FixtureOpener` contract — and S6-1's checker refuses a target fixture
  carrying any transport-simulation key (§11, S6-1). A fixture that could time out or answer
  differently on the second call is a transport simulator, and building one would mean Stage 6 owned
  retry and timeout semantics after all.

The consequence for the corpus is concrete: a **terminal** 5xx is expressible as static bytes and is
kept, because what it proves is the `ServerError → server_error` mapping end to end. A
**`500 → 200`** sequence is not expressible, is **not relocated to another checkpoint**, and is
**removed from Stage 6 entirely** — the committed retry loop already proves it, and asserting it again
here would duplicate a passing test with a mechanism this stage refuses to build.

- **Robots, per target origin.** A target page is frequently on a host no configured source uses, so
  its origin's `robots.txt` is fetched and cached (`robots.cache_ttl_sec` 3600) exactly as for a
  source. RFC 9309 longest-match, 4xx → allow-all, **5xx or unreachable → disallow (fail closed)**,
  all committed. Offline, `FixtureOpener` **raises** for a host with no robots fixture — "a missing
  robots policy is never treated as permission" — so S6-1 must ship a robots fixture for every target
  host, and a missing one is a loud test failure rather than a silent fetch.
- **Domain throttling.** `domainlease` cross-process slots and the shared `next_allowed_at` gate are
  unchanged; the effective interval stays
  `max(min_interval_sec, robots Crawl-delay, per-domain override)`. Target hosts inherit
  `domain_defaults` (`min_interval_sec: 2.0`); the committed `arxiv.org: 15.0` override applies to a
  target page on that host exactly as to its feed. Fixture runs keep Stage 5's
  `sleep=lambda _: None` — the delay is still **read and honoured by every other path**, there is
  simply no remote host to be polite to.
- **Retry and timeout.** `retry.max_attempts` 3, `backoff_base_sec` 0.5 × 2.0 with 0.25 jitter,
  `retry_on_status` [429, 500, 502, 503, 504], `Retry-After` honoured pipeline-wide,
  `max_redirects` 3, `connect/read/request_timeout_sec` 5/15/20, `max_response_bytes` 8 MiB. Unchanged
  and unconfigured by Stage 6.
- **Typed error → `access_status`, one mapping, one place.** `record.v1.json`'s committed
  `access_status` enum is not widened. The table lives as a single module constant in S6-2, and its
  test **enumerates `httpclient`'s `HttpError` subclasses from the AST** — the CF-2 precedent — so a
  new error class fails a test rather than falling through to a wrong status on a live run.

  ```text
  RobotsDenied                              → robots_denied
  HttpTimeout                               → timeout
  DnsFailure                                → unreachable
  ServerError                               → server_error
  LeaseUnavailable                          → unreachable
  ClientError 404 → not_found · 410 → gone · 401/403 → auth_required · 402 → paywalled
               other 4xx                    → unreachable
  ResponseTooLarge / UnexpectedContentType / EmptyResponse → unreachable   (CF-16)
  BudgetExhausted                           → not_checked   (§7.5 — we truly did not check)
  ```

  Every non-`ok`/`redirected` outcome keeps `verification_status: "unverified"` and names the exact
  class, status and reason in `verification_evidence`.
- **Budget.** Target fetching runs **inside the existing `cell:<cell_id>` scope**, so the committed
  `cell_max_requests` 60 and `cell_budget_sec` 300 bound it with no config change. A Stage-6-owned
  `MAX_TARGET_FETCHES_PER_CELL` provides a second, visible bound and is **reported** in the manifest's
  `config.bounds` so a capped run cannot be mistaken for a complete one. Charge-before-attempt is
  unchanged. No unbounded loop, no retry storm, no second budget object.

---

## 6 · Target-derived verification evidence

On a successful fetch, and only from what was observed:

```text
access_status        "ok" | "redirected"                    from the response, per §4
http_status          Response.status                        the final hop
content_hash         Response.content_hash                  the committed urlkey.content_hash
last_checked_at      the run instant                        the one clock, read once
verification_status  "fetched"                              never "verified" — see the schema's note
verification_evidence a deterministic one-line summary: final status, final URL, byte length,
                     and, when relevant, the temporary-redirect target or the exact failure class
canonical_url        per §4                                 identity_url unless evidence moved it
url_aliases          per §4                                 sorted, deduplicated, evidence-bearing
```

Deliberately **not** set:

- **`updated_at` stays `null`**, even when the response carries `Last-Modified`. Promoting a transport
  header to a content-update claim would also make it disagree with a `freshness_score` computed
  before the fetch from `published_at`. The header is recorded in `verification_evidence`; the claim
  is not made. Carried forward as **CF-17**.
- **No score changes.** `relevance_score`, `quality_score`, `audience_fit_score` and
  `freshness_score` are byte-identical to what Stage 4 computed. A test asserts this over a corpus
  where every target fetch succeeded.
- **No facet changes.** `case_facets` is byte-identical with and without target evidence, and
  `industry.secondary` stays empty (CF-11, §9.4).
- **`link_history`** stays absent. It is link-check's append-only structure, and link-check is not
  Stage 6.

---

## 7 · Failure, rejection, partial-run and recovery semantics

### 7.1 A failed fetch is a recorded status, never a lost record

An accepted record whose target fetch failed is written **complete and schema-valid**, carrying the
honest `access_status` from §5 and `verification_status: "unverified"`. It is **not** rejected: the
committed gate accepted it on metadata, and re-deciding after the fact is §1.2's forbidden re-judging.
`record.v1.json` has an `inaccessible` rejection reason and Stage 6 deliberately does not use it —
recorded as **CF-13**, a fidelity question, not a defect to fix by widening behaviour.

### 7.2 One candidate's failure is one candidate's failure

The `_discover` precedent, applied one level down: the fetcher **never raises** to its caller. Every
`HttpError`, `BudgetExhausted` and unexpected exception becomes that candidate's outcome. The other
candidates in the cell are fetched, the other cells run, and every artifact is written complete. A
cell is **not** marked `adapter_error` because a target fetch failed — the adapter succeeded; the
enrichment did not. `zero_result_reason` is untouched, so the CF-2/CF-7 translation table in
`run_cells.ZERO_RESULT_FOR_REJECTION` needs no widening.

### 7.3 Partial runs need no new machinery, and get none

**All target fetching completes before the first artifact byte is written.** The whole fetch phase is
in-memory, above the S5-1 writer, so an interruption during it leaves the tree exactly as Stage 5
guarantees: every file on disk complete and valid or absent, no manifest for the dying run, no temp
debris, `LATEST_RUN_ID` still naming the previous run, and the cross-run ledger not half-updated.

Therefore Stage 6 adds **no** journal, **no** resume policy, **no** per-candidate checkpoint file and
**no** partial-fetch state file. S5-7's `WriteJournal` (module-level, refuses to nest),
`run_is_finished` up-front repeat refusal, `verify_latest_run_id`, and "the pointer moves last or not
at all" are inherited **unchanged and unmodified**. A repeated finished `run_id` is still refused
before the first byte — and now also before the first *request*, which is strictly better: a refused
repeat makes no network call at all. That is asserted.

### 7.4 The ledger records the fetch, because that is what it is for

`ledger.v1.json` already carries `http_status`, `content_hash` and `last_checked_at` per entry — the
exact target-derived triple — and `ledger.merge_ledger` has always stored them, because all three
have been in `OBSERVATION_FIELDS` since Stage 1. **What was missing until S6-6B was the wiring**, and
this section previously described the finished flow as though it existed. It did not: `run_cells.py`
built its ledger observation from `identity_url`, `content_id`, `source_id`, `outcome` and
`record_id`/`rejection_reason` only, so the one structure whose job is remembering what a previous
run learned about a URL remembered everything except what the fetch saw (erratum **E18**).

The implemented flow, as of S6-6B:

```text
_full_record(candidate, …, outcome=…)      the finished record — the only thing that decided
        │                                  whether the fetch's observation or Stage 4's honest
        │                                  defaults apply
        ▼
full_records_by_id[record_id]              full records only; a cross_reference was never a page
        │
        ▼
observation[http_status | content_hash | last_checked_at]      COPIED, per
        │                                  run_cells.LEDGER_TARGET_EVIDENCE_FIELDS
        ▼
ledger.merge_ledger  →  ledgers/<cell_id>.json                 the committed store, unchanged
```

Three properties make this a wiring change and not a new judgement. **The record is the source of
truth** — nothing is recomputed from the `TargetFetchOutcome`, because a second derivation could
disagree with the record written beside it in the same run. **No clock is read**: `last_checked_at`
is the record's own, and a fresh instant would claim a check that did not happen then. **A field is
written only when the record carries a non-null value** — a metadata-only record contributes none of
the three, a budget-skipped target contributes no status and no hash, and a rejected candidate
contributes nothing at all, because a null written here would be a claim rather than the absence of
one, and `merge_ledger` already reads a null as "no news".

`first_seen_at` is still written once, a terminal outcome is still final, and a corrupt ledger still
raises. **No ledger field is added, `ledger.py` is byte-unchanged, and no schema is touched.**

### 7.5 Budget exhaustion is `not_checked`, and it makes the run ineligible

A candidate skipped because a budget was reached carries `access_status: "not_checked"` — the honest
statement that no check occurred — and the run is **ineligible for publication** under §8, so a
partially enriched run can never be mistaken for a verified one. This is why no
`target_max_requests` config key is needed: the honest failure mode is already visible without one,
and adding a key would edit `config/` and trigger CF-6 for no behavioural gain.

---

## 8 · How a Stage 5 publication-ineligible record becomes eligible

`artifacts.derive_publication_eligibility` is the **single, derived** authority (a Stage 5 test
asserts `publication_eligible` is absent from `build_run_manifest`'s signature). Today it reads:

```text
mode != "harvest"          → ineligible
target_fetch_owners == 0   → ineligible: "no target page was fetched, so every record is
                              unverified (target fetching arrives in Stage 6)"
any cell in an error state → ineligible
otherwise                  → eligible
```

`target_fetch_owners > 0` alone is **too weak** for Stage 6: a run that fetched 1 of 4 accepted
records would pass. S6-6 therefore extends the same function — one home, still derived, still not a
parameter — with a count of accepted records lacking target evidence:

```text
records_without_target_evidence > 0 → ineligible: "<n> of <m> accepted records carry no target
                                       evidence (access_status not_checked)"
```

so a run is eligible when, and only when, it is a `harvest` run, no cell failed, at least one target
fetch was owned, **and every accepted record was actually checked**. A robots-denied or 404 record
counts as *checked* — it has a real observed status; a budget-skipped record does not. The derivation
is proved **live in both directions**, as Stage 5 proved the existing one: a fully enriched clean run
is eligible, and each of `mode`, a failed cell, zero owners and one unchecked record independently
makes it ineligible with its own precise reason.

Eligibility is a **fact about a run**, not permission to publish. Nothing is promoted in Stage 6;
`data/harvested/` stays absent.

---

## 9 · Carried-forward findings

Each is treated explicitly, and none is redesigned. **No unrelated stage is reopened.**

### 9.1 CF-1 — pool concurrency. Deferred, guarded, and explicitly addressed *before* any concurrency

Stage 6 introduces the **first caller** of `pool.acquire_target_fetch` and of `pool.add_candidate`.
There is still exactly **one** caller, running **sequentially**, so the unlocked check-then-set paths
keep zero *concurrent* callers and remain harmless. Stage 6 adds no thread, process, `async def`,
`await`, `Lock(` or `Semaphore(` anywhere, and the existing static scan over `run_cells.py` and
`artifacts.py` is **extended to `targetfetch.py` and `aliases.py`** by the checkpoint that creates
each. Throughput is not a goal: a 4-fetch run needs no parallelism, and adding it would trade a
measured guarantee for an unmeasured one.

**The rule, restated so it cannot be missed:** any future change that runs cells or fetches
concurrently must fix CF-1 **first, in its own separately approved checkpoint, before the concurrency
lands.** That checkpoint must revisit three things, not two: the sequential cell loop, S5-7's
module-level `WriteJournal` (which refuses to nest), and — new in Stage 6 — the target-fetch
ownership gate, whose once-per-candidate guarantee is currently held by sequential execution rather
than by a lock. **CF-1 remains deferred and uncorrected by Stage 6.**

### 9.2 CF-2 / CF-7 — rejection vocabulary. Untouched, and not widened

Stage 6 adds **no rejection reason and no rejection path**. A failed fetch is an `access_status`, not
a verdict (§7.1), so `verify.decide`'s six reasons, `rejection.v1.json`, and the
`ZERO_RESULT_FOR_REJECTION` translation are all unchanged. The AST pins that prove exactly six
reasons exist stay green untouched. Both remain carried forward as fidelity questions.

### 9.3 CF-3 — no target fixtures. Discharged by S6-1

The reason target fetching was deferred out of Stage 4. S6-1 ships the target-page corpus and the
robots fixtures its hosts require, all synthetic and hand-authored with `authored_at` /
`authored_against` provenance, verified by `check_fixtures.py`. **CF-3 closes at S6-1** and is
recorded as discharged in the closeout.

### 9.4 CF-11 — `industry.secondary` stays empty, and stays protected

A fetched body is **not** facet evidence (§1.2). The committed definition — deployment context, never
corporate portfolio — is unchanged, `facetassign.py` and `facets.py` stay byte-unchanged, and S5-4's
six coverage assertions (including the one proving the counter is *live*) must stay green. Stage 6
creates no pressure to fill `secondary`, because it adds no lexical evidence at all.

### 9.5 S4-4 provisional calibration. Untouched; calibration stays Stage 9

`SATURATION=3`, the `0.68 / 0.32` required-versus-boost split, all four thresholds, every weight and
the 90-day half-life stay **provisionally approved and unrevisited**. Target evidence enters no score
(§6), `freshness_score` still derives from `published_at` alone, and the manifest continues to merely
*record* the thresholds used so Stage 9 can compare against a real run. Stage 6 changes what a run
*observes*, not what it *judges* — which is precisely why it does not reopen S4-4.

### 9.6 D2 — classification evidence narrowing. One home, unchanged

`artifacts.project_classification_evidence` remains the single projection of `{signal, matched}`.
Stage 6 adds no second projection and no second place that knows the record's shape.

### 9.7 New findings this stage will carry forward

Recorded here so they are visible at the closeout rather than discovered later.

```text
CF-13  a post-acceptance inaccessible record has no rejection path, deliberately (§7.1)
CF-15  CORRECTED 2026-07-30 (§14 E16). Its premise — that same-domain trust was limited to
       identical hostnames, so a www. variant became a conflict — was false: the committed
       urlkey.registrable_host has decided this since Stage 1. The permanent boundary that
       replaces it: same registrable domain is decided by that committed helper; a canonical
       on a DIFFERENT registrable domain stays conflict-or-policy-controlled exactly per the
       §4 table; and the helper's own best-effort limitation (last two labels, so a.co.uk and
       b.co.uk compare equal) is an inherited Stage 1 tradeoff, gated behind the syntax and
       robots check — not a new Stage 6 redesign task. This corrects only that premise and
       claims nothing broader about canonical-domain handling.
CF-16  ResponseTooLarge / UnexpectedContentType / EmptyResponse collapse onto `unreachable`;
       the exact class survives verbatim in verification_evidence (§5)
CF-17  `updated_at` stays null even when Last-Modified is present (§6)
```

### 9.8 Unchanged and not Stage 6's business

**CF-4** (`validate_task.sh` wiring) → Stage 8 · **CF-5 / CF-8** (keyword tuning, unmatchable terms) →
the relevance-tuning stage · **CF-6** (config-editing checkpoints cannot pass the full gate
pre-commit) → Stage 8, and untriggered here because no checkpoint edits `config/` · **CF-9** (source
tiers from `role`) → the relevance-tuning stage · **CF-12** — closed at S4-5A-C.

---

## 10 · Reproducibility boundaries for external network responses

Two regimes, and the plan never conflates them.

**Offline (every test, every checkpoint S6-1 … S6-7).** Byte-determinism is required and proved.
Stage 5 proved two consecutive runs differ at exactly **four** JSON leaves — `harvest_run_id`,
`generated_at`, `discovered_at`, `freshness_score` — enumerated by a recursive JSON diff rather than
normalized away. Stage 6 adds exactly **one**: `last_checked_at`. The difference set becomes **five,
enumerated the same way**, so a sixth moving field fails a test rather than passing silently.

**The five are a property of the record-bearing artifacts over the COMMITTED corpus**, and S6-7 says
so exactly rather than approximately (§14, E19). Measured across the complete tree, three other
families carry instants of their own, each enumerated exactly and none excused:

```text
cells/ · topics/ · coverage.json · alias_conflicts.json   exactly the five
runs/<id>/manifest.json      + started_at · finished_at   the run's own clock, in the document
                                                          that describes the run
rejections/<cell>.json       + rejected_at · freshness    when this run rejected it; `freshness`
                                                          is the record's `freshness_score` under
                                                          the name rejection.v1.json gives it
ledgers/<cell>.json          updated_at · first_seen_at · last_seen_at · last_checked_at
                                                          a CROSS-RUN store whose whole job is
                                                          recording when a URL was seen
```

Two consequences worth stating plainly. A **composed** corpus that adopts an alias or records a
conflict legitimately moves `observed_at` and `detected_at` as well; those runs are therefore compared
**same-clock**, and the five-leaf allowlist is never enlarged to admit leaves the committed corpus does
not have. And the ledger's timestamps moving is the **feature** — a cross-run memory that reported the
same instant twice would be broken — which is why it is enumerated apart rather than folded in.
`content_hash`, `http_status`, `access_status`, `verification_status`, `verification_evidence`,
`canonical_url` and `url_aliases` are all **derived from fixture bytes** and must therefore reproduce
**exactly**. Determinism is proved under shuffled source, candidate and cell orderings, as before.

**Live (S6-L only).** A live response is **not reproducible** and is explicitly outside the
determinism contract. `content_hash` will differ between two live runs of the same URL whenever the
page carries a nonce, a timestamp or an ad; a status may change; a redirect may appear. S6-L
therefore asserts **contracts, never bytes**: robots was consulted and honoured, no budget was
exceeded, no identity moved, every artifact validates against its committed schema, and every field
Stage 6 sets is one the response actually justified. Live output is written to a temp root, is
**never committed**, and is **never promoted to a fixture** without a separate recording checkpoint
that carries `captured_at` provenance — a distinction `check_fixtures.py` already enforces, refusing
any mixture of synthetic and recorded metadata.

---

## 11 · Checkpoints

**Every checkpoint requires separate approval, named explicitly. This document authorizes none of
them.** Risk tiers are Stage 5 §4 unchanged: **L0** documentation · **L1** additive module, injected
root, no existing file modified · **L2** touches an existing module or shared contract · **+FS** any
checkpoint that writes to the filesystem.

### S6-0 · This plan — L0, documentation only

```text
A  docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md
M  docs/harvest/TODO.md                          registration and approval status only
```

Validation: exact two-path diff · `git diff --check` · nothing under `src/`, `tests/`, `scripts/`,
`config/`, `schemas/`, `state/`, `data/`, `runs/` or any existing handoff · protected baseline and the
508-file untracked baseline unchanged. **The taxonomy full gate is not run for planning
documentation** (Stage 5 §4, L0). Commit: `docs(harvest): plan stage 6`. **No push.**

### S6-1 · Target-page fixtures, the loader, and the checker — L2

Discharges **CF-3**. **Corrected on 2026-07-30** after a preflight found the original corpus wording
neither literal nor implementable within S6-1's path set (§14, E15). S6-1 is now exactly four things:
static repository-local target and robots fixtures · target fixture loading · manifest and provenance
checking · permanent fixture-infrastructure tests.

S6-1 contains **no** fetching implementation, **no** transport simulation, **no** source-overlap
construction, **no** candidate or pool ownership logic, **no** record construction, **no** artifact
writing, **no** publication logic and **no** live request.

#### S6-1 allowed paths — the literal set, and the whole of it

```text
A  <the 24 target fixtures in the table below>   tests/fixtures/harvest/targets/
A  tests/fixtures/harvest/robots/tgt.harvest.test.json
A  tests/fixtures/harvest/robots/tgt-robots-denied.harvest.test.json
M  tests/fixtures/harvest/MANIFEST.json          bytes + SHA-256 per new file
M  src/harvest/fixtures.py                       load_target_fixtures(); FixtureOpener(targets=…)
M  scripts/harvest/check_fixtures.py             target-tree completeness, provenance, no-DSL refusal
A  tests/harvest/test_target_fixtures.py
A  tests/test_taxonomy_target_fixtures.sh
```

**Only the two literal tables below authorize the creation of a fixture file.** The
`targets/` and `robots/` directory names and the `tgt_<case>_<hop>.json` convention are explanatory —
a directory glob is **not** permission to add a file. No other path may change; in particular no
existing target or robots fixture is modified, no source fixture is touched, `check_config.py` stays
byte-unchanged (DV-1), and no config or schema is edited.

#### The 24 target fixtures

All are synthetic, repository-local, deterministic bytes with `provenance: "synthetic"`,
`authored_at`, `authored_against` and a `contract_intent` line naming the permanent purpose. A target
fixture carries **no `source_id`** — it maps to no configured source — and **no transport-simulation
key** (§5.0).

**Group A — client-level contract cases.** Driven through the real `HttpClient` over
`FixtureOpener` at an explicit URL, so robots, redirect classification, status mapping and
content-type handling are exercised by the committed client rather than by a mock.

| # | filename | URL | status | permanent contract purpose | robots host |
|---|---|---|---|---|---|
| 1 | `tgt_ok_plain.json` | `https://tgt.harvest.test/ok-plain` | 200 `text/html` | §4 row 1: a clean fetch with **no** canonical tag — `canonical_url` stays `identity_url`, `access_status: ok`, `verification_status: fetched`. The baseline every other row is compared against | `tgt.harvest.test` † |
| 2 | `tgt_canonical_same_host.json` | `https://tgt.harvest.test/canonical-same-host` | 200 `text/html` | same-host `rel=canonical`, absolute and non-circular → auto-accepted, alias `kind: canonical_tag` | `tgt.harvest.test` |
| 3 | `tgt_canonical_cross_host.json` | `https://tgt.harvest.test/canonical-cross-host` | 200 `text/html` | canonical names `https://other-target.test/elsewhere` — a **different registrable domain** — with no `domain_migrations` rule → **alias conflict, no alias**, identity unmoved. Corrected 2026-07-30 (§14 E16): it previously named `tgt-alt.harvest.test`, which `registrable_host` maps to the same `harvest.test` and which therefore exercised the *same-domain* branch, not this row | `tgt.harvest.test` |
| 4 | `tgt_canonical_conflicting.json` | `https://tgt.harvest.test/canonical-conflicting` | 200 `text/html` | two conflicting `<link rel=canonical>` on one page → conflict, no alias | `tgt.harvest.test` |
| 5 | `tgt_canonical_circular_1.json` | `https://tgt.harvest.test/canonical-circular` | 301 → #6 | hop 1 of the circular case | `tgt.harvest.test` |
| 6 | `tgt_canonical_circular_2.json` | `https://tgt.harvest.test/canonical-circular-b` | 200 `text/html` | its canonical names #5's URL — already in **this fetch's own redirect chain** → conflict, no alias. This is the only circular form Stage 6 can observe, because §1.2 forbids following a canonical to check it | `tgt.harvest.test` |
| 7 | `tgt_redirect_permanent_1.json` | `https://tgt.harvest.test/redirect-permanent` | 301 → #8 | hop 1, permanent-only chain | `tgt.harvest.test` |
| 8 | `tgt_redirect_permanent_2.json` | `https://tgt.harvest.test/redirect-permanent-b` | 301 → #9 | hop 2 | `tgt.harvest.test` |
| 9 | `tgt_redirect_permanent_3.json` | `https://tgt.harvest.test/redirect-permanent-c` | 200 `text/html` | terminus of `301 → 301 → 200`: every hop permanent → `canonical_url = final_url`, alias `kind: permanent_redirect`, `access_status: redirected`, **identity unchanged** | `tgt.harvest.test` |
| 10 | `tgt_redirect_temporary_1.json` | `https://tgt.harvest.test/redirect-temporary` | 301 → #11 | hop 1 | `tgt.harvest.test` |
| 11 | `tgt_redirect_temporary_2.json` | `https://tgt.harvest.test/redirect-temporary-b` | 302 → #12 | hop 2 — **the temporary hop** | `tgt.harvest.test` |
| 12 | `tgt_redirect_temporary_3.json` | `https://tgt.harvest.test/redirect-temporary-c` | 200 `text/html` | terminus of `301 → 302 → 200`: **this is the fixture that proves any 302 in the chain prevents permanent alias adoption** — `permanent_redirect` false → no alias, `canonical_url` unchanged, `access_status: ok` | `tgt.harvest.test` |
| 13 | `tgt_not_found.json` | `https://tgt.harvest.test/not-found` | 404 | `ClientError 404 → not_found`; the record is still complete and schema-valid (§7.1) | `tgt.harvest.test` |
| 14 | `tgt_gone.json` | `https://tgt.harvest.test/gone` | 410 | `410 → gone` | `tgt.harvest.test` |
| 15 | `tgt_forbidden.json` | `https://tgt.harvest.test/forbidden` | 403 | `403 → auth_required` | `tgt.harvest.test` |
| 16 | `tgt_server_error.json` | `https://tgt.harvest.test/server-error` | 500 | a **terminal** 5xx → `ServerError → server_error`. **Not a retry test** (§5.0): what the committed client does between the first 500 and the raise is its own tested contract | `tgt.harvest.test` |
| 17 | `tgt_non_html_pdf.json` | `https://tgt.harvest.test/paper.pdf` | 200 `application/pdf` | non-HTML: `content_hash` computed, **no** canonical scan attempted | `tgt.harvest.test` |
| 18 | `tgt_non_html_json.json` | `https://tgt.harvest.test/item.json` | 200 `application/json` | non-HTML: same contract on a second content type | `tgt.harvest.test` |
| 19 | `tgt_empty_body.json` | `https://tgt.harvest.test/empty` | 200, zero-length body | `EmptyResponse → unreachable`, with the exact class surviving in `verification_evidence` (CF-16) | `tgt.harvest.test` |
| 20 | `tgt_robots_denied.json` | `https://tgt-robots-denied.harvest.test/denied` | 200 (**never served**) | robots disallows the host, so `RobotsDenied → robots_denied` is decided **before any request**. The fixture exists precisely so a test can assert it was **never opened** — proving the denial preceded the fetch rather than followed it | `tgt-robots-denied.harvest.test` † |

**Group B — end-to-end enrichment cases.** The four accepted candidates the committed corpus actually
produces, so a run can enrich real records. Their URLs are not invented here: they are what
`dedupe → extract → classify → verify` yields today from `fx_lm_eval_harness_releases`, all in
`research-and-models__benchmark-and-datasets`, all on `github.com`, whose robots fixture **already
exists** and allows `/posts/…` with no crawl-delay. All four are plain 200s on purpose: a fully
checked run is what §8 needs in order to prove `publication_eligible` can honestly become `true`.

| # | filename | URL | status | permanent contract purpose | robots host |
|---|---|---|---|---|---|
| 21 | `tgt_accepted_1.json` | `https://github.com/posts/lm-eval-harness-releases-1` | 200 `text/html` | end-to-end enrichment of accepted record 1 | `github.com` ‡ |
| 22 | `tgt_accepted_2.json` | `https://github.com/posts/lm-eval-harness-releases-2` | 200 `text/html` | accepted record 2 | `github.com` ‡ |
| 23 | `tgt_accepted_3.json` | `https://github.com/posts/lm-eval-harness-releases-3` | 200 `text/html` | accepted record 3 | `github.com` ‡ |
| 24 | `tgt_accepted_4.json` | `https://github.com/posts/lm-eval-harness-releases-4` | 200 `text/html` | accepted record 4 — with all four, every accepted record is checked and the run is eligible | `github.com` ‡ |

The numeric suffix in `tgt_accepted_<n>` indexes the four accepted candidates; it is **not** a
redirect hop. Only `tgt_canonical_circular_*`, `tgt_redirect_permanent_*` and
`tgt_redirect_temporary_*` use the `_<hop>` suffix in its hop sense.

#### The 2 robots fixtures

Hosts are reused wherever robots behaviour is identical; a distinct host is allocated **only** when a
different robots response is itself the contract.

| filename | host | robots response | why this host exists |
|---|---|---|---|
| `tgt.harvest.test.json` | `tgt.harvest.test` | 200, `User-agent: *` / `Allow: /`, no crawl-delay | † the single allow-all host for all 19 Group A cases whose contract is the **HTTP** outcome, not the robots outcome |
| `tgt-robots-denied.harvest.test.json` | `tgt-robots-denied.harvest.test` | 200, `User-agent: *` / `Disallow: /` | † the one case where the **robots response is the contract** |

‡ `github.com` needs no new robots fixture — `tests/fixtures/harvest/robots/github.com.json` is
committed, allows `/posts/…` and declares no crawl-delay. It is **not modified.**
`other-target.test` (the cross-domain canonical target in fixture #3) gets **no** robots fixture and
**no** target fixture: a canonical on a different registrable domain is refused on domain policy
**before** any robots check or fetch (§4), so a fixture for it would be inert — and nothing in Stage 6
ever fetches or probes a discovered canonical URL. `.test` is RFC 2606-reserved and can never resolve,
which is why the synthetic hosts use it — the existing `robots-5xx.test` control set the precedent.

**S6-7 composes this corpus; it does not extend it.** To put several §5 failure modes into one run,
S6-7 builds a **temp** fixture tree from the committed corpus — copying Group B and substituting a
Group A body — rather than S6-1 shipping failure-variant duplicates of the accepted URLs. No
additional committed fixture is required for that, and none is authorized.

#### Loader and checker

`FixtureOpener` gains **one** URL index, not a second one: targets merge into the existing `_by_url`
map with the same duplicate refusal, so nothing above the opener can tell a target from a source —
which is the property that makes the corpus a real test of `HttpClient`. All committed source-fixture
behaviour and every existing caller are preserved unchanged. The loader **fails explicitly** — never
silently skips, resets or invents — for a malformed fixture, a duplicate `fixture_id`, a duplicate
URL, a fixture claiming a foreign shape, or data inconsistent with the manifest.

`check_fixtures.py` is extended for exactly three target-tree contracts: completeness against the
literal table, the same synthetic/recorded provenance rules the corpus already enforces, and refusal
of any transport-simulation key (§5.0).

Focused suite: `tests/test_taxonomy_target_fixtures.sh` + `check_fixtures.py`, run repeatedly during
work. **Full gate once** before commit. Its tests assert deterministic loading, exact URL
ownership and indexing, manifest integrity, target-tree completeness, provenance requirements,
malformed and duplicate rejection, preservation of existing source-fixture behaviour, and zero network
access. They assert nothing about which later file exists, nothing about the working tree versus HEAD,
and no checkpoint-progress invariant (§13).

### S6-2 · `src/harvest/targetfetch.py` — the fetch and the status mapping — L1

```text
A  src/harvest/targetfetch.py       TargetFetchOutcome · fetch_target() · ACCESS_STATUS_FOR_ERROR
                                    · TargetFetchError
A  tests/harvest/test_target_fetch.py
A  tests/test_taxonomy_target_fetch.sh
```

One function, one outcome dataclass, one mapping table. It takes an **injected** `client`, `budget`
and `clock`, constructs no `HttpClient`, opens no socket, writes no file, touches no pool, builds no
record, and **never raises to its caller** (§7.2). Its test enumerates `httpclient`'s `HttpError`
subclasses **from the AST** and proves every one maps to a committed `access_status` value.

### S6-3 · `src/harvest/aliases.py` — redirect and canonical adjudication — L1

```text
A  src/harvest/aliases.py           adjudicate() · extract_rel_canonical() · AliasConflict
                                    · CANONICAL_SCAN_BYTES · AliasError
A  tests/harvest/test_aliases.py
A  tests/test_taxonomy_aliases.sh
```

A pure function: no I/O, no clock beyond the injected instant, no network. Reads
`canonicalization.v1.json` as data; a test asserts no configured host, domain or rule id appears as a
string literal in production `aliases.py`, with the forbidden values derived **dynamically from the
committed policy** rather than typed into the test. Proves the §4 table row by row, and proves
`identity_url`, `record_id` and `content_id` are byte-identical in every row — including every conflict
row — using test-local sentinel data, never by importing record construction.

**Same-domain trust uses the committed `urlkey.registrable_host` and adds no second host comparison**
(§4). Two consequences for S6-3's tests, recorded here from the 2026-07-30 preflight (§14, E16):

- **The same-domain branch needs a test-local synthetic case, not a fixture.** Two *different*
  hostnames that `registrable_host` maps to one value — e.g. two synthetic subdomains under
  `harvest.test` — must select the **same-domain** branch. The case is derived **through the committed
  helper**, never from typed-in hostnames, and carries an anti-vacuity assertion proving both halves of
  what makes it interesting: the host strings **differ**, and their `registrable_host` values are
  **equal**. **No further permanent S6-1 fixture is added for this**; it is test-local by design.
- **The opposing branch is covered by the corrected fixture.** `tgt_canonical_cross_host.json` now
  names `https://other-target.test/elsewhere`, a genuinely different registrable domain, so it
  exercises the cross-domain conflict row it was always meant to.

**Policy loading, from the same preflight.** `adjudicate()` and `extract_rel_canonical()` stay **pure
relative to their explicit inputs** and **must not open a file during adjudication**. No committed API
returns the whole canonicalization document — `request_key.canonicalization_version` yields only the
`config_version` int — so where the document is needed, `aliases.py` may own a private, cached
module-boundary loader following the committed idiom of `verify.load_policy` and
`classify.load_precedence`, with the document passed **into** the two functions as data. It must not
become a competing hostname parser and must not duplicate a configured domain or rule literal.

### S6-4 · Ownership, deduplication and bounds in the driver — L2

```text
M  src/harvest/run_cells.py         the fetch phase: add_candidate → acquire_target_fetch →
                                    fetch_target → adjudicate, over the accepted set only
A  tests/harvest/test_target_ownership.py
A  tests/test_taxonomy_target_ownership.sh
```

No record field changes yet — this checkpoint proves **who fetches what, how often, and within which
bounds**: once per canonical identity, `MAX_TARGET_FETCHES_PER_CELL` respected and reported, target
fetching nested inside the committed `cell:` budget scope, `target_fetch_owners` and
`extraction_owners` flowing through `pool.accounting()`, `source_fetch_owners` **unchanged** by target
fetching, and the CF-1 static scan extended to the two new modules. Also proves a target page yields
no candidate and no adapter is invoked on one.

**S6-4 also owns the shared-identity ownership contract relocated here from S6-1** (§3, and §14 E15).
It is proved with **test-local synthetic candidate and pool inputs** — two accepted rows constructed in
the test that share one canonical identity — because a shared identity is a property of what the feeds
surfaced, and no target-page fixture can create one. Exactly two facts are asserted:

1. **one canonical target identity is fetched exactly once**, whether the two owners sit in one cell or
   in two topics; and
2. **every accepted record owning that identity receives the same target-fetch outcome** — one
   observation, not two, and not a re-fetch per record.

**No source fixture and no topic config is read, added or modified**, and neither is authorized here.
The committed Stage 4 dedupe contract — 55 assertions on how identities group — is **not reopened, not
duplicated and not re-proved**; S6-4 asserts only the Stage 6 fact that one identity buys one fetch
whose outcome reaches every record owning it.

**No allowed-path change is required for this relocation**: `tests/harvest/test_target_ownership.py`
is already S6-4's declared focused test and is the owning path for both assertions.

### S6-5 · Target evidence on records — L2

```text
M  src/harvest/run_cells.py         _full_record consumes the outcome instead of the verdict's
                                    honest no-enrichment defaults; passes adjudicated aliases
M  src/harvest/records.py           one keyword-only `url_aliases=None` and its validation,
                                    normalization and projection — §12.1 D6-A, RESOLVED
M  tests/harvest/test_run_cells.py  retire `test_no_target_page_was_fetched` — and nothing
                                    else in that file (predeclared, see below)
A  tests/harvest/test_target_evidence.py
A  tests/test_taxonomy_target_evidence.sh
```

Exactly five paths. `src/harvest/records.py` is authorized here by §12.1 and nowhere else, for that one
additive parameter and nothing more.

**`tests/harvest/test_run_cells.py` is predeclared for exactly one deletion.**
`test_no_target_page_was_fetched` asserts every full record carries
`access_status: "not_checked"`. That is true of Stage 5 and remains true of S6-4 — and S6-5 exists
precisely to make it false, by writing observed target evidence onto full records. It is therefore a
spent Stage 5 progress guard from the moment S6-5 is approved, and it is retired **then, not before**:
S6-4 leaves it passing and untouched. Declaring it here rather than discovering it mid-checkpoint is
the lesson of §14.2 — guards of exactly this class stopped S6-4 twice.

Proves §6 exactly: the six evidence fields set from observation; `verification_status` is `"fetched"`
and never `"verified"`; `updated_at` stays null; all four scores, every facet payload, `record_id`,
`content_id` and `identity_url` byte-identical to a no-fetch run; a failed fetch still yields a
complete, schema-valid record with an honest status; the cross-topic case writes **one fetch's**
evidence onto **two** records.

### S6-6 · Eligibility, alias conflicts and manifest reporting — L2 +FS

```text
M  src/harvest/artifacts.py         derive_publication_eligibility extended (§8); alias-conflict
                                    artifact path and builder; alias_conflicts_count derived
M  src/harvest/run_cells.py         config.enrich, config.bounds, conflict routing
A  schemas/harvest/alias_conflict.v1.json        §12.2 D6-B, RESOLVED
A  tests/harvest/test_eligibility.py             owns the new schema's assertions
A  tests/test_taxonomy_eligibility.sh
```

Exactly five paths. `schemas/harvest/alias_conflict.v1.json` is authorized here by §12.2 and nowhere
else; `tests/harvest/test_eligibility.py` is its owning focused test, so no additional test path is
needed for it.

Eligibility proved live in **both** directions and in each failing direction independently (§8). The
conflict artifact is written by the **single S5-1 writer**, serialized by the
**single S5-1 serializer**, and validated against its committed schema **before** any byte reaches
disk. No second writer, no second serializer, no second validator. The Stage 5 file-set assertion is
updated from an exact 42 to an exact new number, still asserted **exactly**.

### S6-6A · Target request accounting — L2

The checkpoint §14.4 said was required and deliberately left undeclared: its scope came from a
read-only ownership and path audit, not from a guess. **S6-7 is blocked behind it**, because a
manifest whose request accounting is about to change shape is not a stable thing to pin.

```text
M  src/harvest/targetfetch.py       TargetFetchOutcome.accounting, copied from the client's final
                                    response or typed error; never recomputed
M  src/harvest/artifacts.py         target_request_accounting(); build_run_manifest(target_outcomes=)
M  src/harvest/run_cells.py         passes the run-scoped outcome map — one call site
M  schemas/harvest/run_manifest.v1.json   three optional integer keys inside request_accounting
M  tests/harvest/test_target_fetch.py     field set, StubResponse, pass-through
M  tests/harvest/test_target_ownership.py StubResponse
M  tests/harvest/test_eligibility.py      the spent progress guard, retired in part
A  tests/harvest/test_target_accounting.py
M  tests/test_taxonomy_eligibility.sh     header prose, which the retired guard made false
A  tests/test_taxonomy_target_accounting.sh
M  docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md   §5.0 erratum E17, this section, §11.1, §14.4
M  docs/harvest/TODO.md                          checkpoint registration
```

Exactly twelve paths, and the documentation is **inside** this checkpoint rather than split into a
commit of its own: §5.0's superseded sentence and the code that supersedes it are one contract, and
shipping either without the other leaves the plan disagreeing with the tree.

**`pool.py` is not among them, and that is the finding.** `pool.accounting()["http_attempts"]` sums
`self.sources`, which only `record_established_source` populates and which the target path is
forbidden to call (§3) — so the pool can never see a target fetch, and routing target attempts
through it would put the two key spaces one function call apart. Every fact needed is already frozen
onto the objects `targetfetch` holds. `pool.py` therefore stays byte-frozen and
`test_run_cells.py::test_the_stage_4_modules_are_byte_unchanged` needs no retirement.

**What is reported, and what is not.** Three optional keys inside `request_accounting` —
`target_http_attempts`, `target_retries`, `target_redirect_hops` — summed **once**, at the manifest
boundary, over the **run-scoped** outcome map. One outcome per owned canonical identity, so a URL
accepted in two cells or under two topics is counted **once**, which is the S6-4 guarantee expressed
as a number. Deliberately absent: `total_http_attempts` (folding the two key spaces is precisely what
§2 forbids), `request_charges` (no source counterpart in this block; it stays on the outcome for a
later checkpoint), target conditional revalidations (no counter exists, no revalidation path is
built) and robots retrievals (DV-8 excludes them from `attempts` by contract). **`http_attempts`,
`retries` and `redirect_hops` keep their existing source-only meaning**, unchanged in value and in
wording. No estimate, and no `client.stats` delta.

**Omission and zero are different answers.** `target_outcomes` defaults to a `None` sentinel: omitted,
the three keys are absent and every committed caller is byte-identically unaffected; supplied — even
empty — all three appear, at zero. "This run fetched no target" must stay distinguishable from "this
run did not report".

**The names are the obvious ones on purpose.** `test_eligibility.py`'s S6-6 guard forbids the exact
strings `target_http_attempts`, `target_retries` and `target_redirect_hops`. That guard is spent and
is retired for those three; choosing different key names to keep it green is the move S6-4 already
rejected on the S5-4 precedent. Its `total_http_attempts` prohibition is **not** spent and is kept.

### S6-6B · Ledger target observation propagation — L2, corrective

Found by the **read-only S6-7 preflight**, which stopped without editing a file: §7.4 described the
ledger carrying the target-derived triple as a finished flow, and the tree did not implement it. The
storage was never missing — `ledger.v1.json` admits all three fields, `merge_ledger` stores them and
`OBSERVATION_FIELDS` lists them — only the observation the driver built. Corrected **before** S6-7,
because S6-7 pins ledger determinism across runs and a ledger about to gain three fields is not a
stable thing to pin.

```text
M  src/harvest/run_cells.py       LEDGER_TARGET_EVIDENCE_FIELDS; the finished-record lookup; the
                                  three copied observation fields
M  tests/harvest/test_run_cells.py  the run-boundary integration proof
M  docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md   §7.4 rewritten, erratum E18, this section, §11.1
M  docs/harvest/TODO.md                          checkpoint registration
```

Exactly four paths. **`ledger.py` is not among them and is byte-unchanged**, and neither is any
schema: the correction is entirely in what the driver observes. No fixture, no config, no accounting
change — `request_accounting` and both key spaces are untouched by this checkpoint.

**Proved at the run boundary, not against `merge_ledger`.** The storage already had its own tests;
what had never been asserted was that a real run's ledger row carries what that run's record says.
The proof runs the committed corpus into a temp root and joins each of the four target-fetched
records to its ledger entry by `record_id`, asserting field-for-field equality, distinct per-page
content hashes, no fabricated values on rejected entries or in the eleven cells that fetched nothing,
schema validity, and byte-identical reproduction by a second identical run. It **fails against
`88d40ca`** — 12 failures and 15 errors on all four records — which is what makes it a proof rather
than a description.

### S6-7 · Determinism, failure modes and partial runs, end to end — L1 +FS

**S6-7 follows this correction** and is unchanged by it beyond now having a stable ledger to pin. It
remains unapproved, and its own preflight findings on enumeration scope and expressible failure modes
are recorded where they were found, not pre-decided here.

```text
A  tests/harvest/test_target_determinism.py
A  tests/test_taxonomy_target_determinism.sh
M  docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md      this section, §10, errata E19-E21
M  docs/harvest/TODO.md                             checkpoint registration
```

Exactly four paths. **No production module, schema, config or committed fixture changes**, and a test
asserts `tests/fixtures/harvest` is unmodified afterwards — a composer bug would otherwise edit the
corpus every other suite reads.

The five-leaf difference set enumerated by recursive JSON diff (§10) · byte-determinism under
shuffled source, candidate and cell orderings · every §5 failure mode **the committed corpus can
express**, across deterministic scenarios rather than one impossible run · an interruption during the
fetch phase writing **nothing at all** · a repeated finished `run_id` refused **before the first
request** · `verify_latest_run_id` still a checkable predicate · a run that never fetched still
honestly ineligible.

**Scenario corpora are copies.** A composed corpus is the committed fixture tree copied to a temp
directory with target-fixture **content** substituted in the copy — `status`, `headers` and body only.
`fixture_id`, the filename and the URL stay exactly as committed, because the loader keys the corpus
by filename and indexes it by URL, and because an accepted record's identity must not move or the
scenario stops being comparable to the clean run. The copied `MANIFEST.json` no longer describes the
substituted bytes, and that is correct: it pins the **repository** corpus for `check_fixtures.py`, and
the loader validates shape rather than provenance. Four scenarios, because the four accepted slots
cannot hold every family at once:

```text
terminal failures   404 · 410 · 403 · terminal 500          all four still eligible (§8)
bodies & redirects  empty · non-HTML · 301-only · 302 hop    one alias adopted
canonical           cross-domain · same-domain-robots-unverified · two tags · self
                                                             three conflicts, no alias
budget skip         the committed corpus with the per-cell cap lowered test-locally
                                                             two not_checked → INELIGIBLE
```

**A composed scenario is compared same-clock, never folded into the five.** A permanent redirect
adopts an alias, which carries `observed_at`; a conflict carries `detected_at`. Both are legitimate
sixth and seventh clock-derived leaves — and both are **absent from the committed corpus**, which
adopts no alias and records no conflict. Enlarging the §10 allowlist to admit them would weaken the
committed-corpus contract to buy nothing, so the alias- and conflict-producing corpora prove
determinism by **byte identity under one clock** instead, and the two leaves are asserted to equal the
run instant where they appear.

**Robots-denied is not composed at run level, and that is a finding rather than an omission.** All
four accepted targets live on `github.com`, and so does `fx_lm_eval_harness`, the source feed that
surfaces them. Denying that host in a composed robots tree stops **discovery**, so the run produces no
candidates and therefore no denied *record* — the scenario would prove nothing it claims to. The
contract keeps its existing owner: `RobotsDenied → robots_denied` is asserted directly in
`tests/harvest/test_target_fetch.py`, and fixture #20 exists precisely so a test can prove the denial
preceded the fetch by asserting the file was never opened. **No production fixture or source input is
altered to force this case into the new suite** (§14, E20).

**The §5.0 exclusions stand unchanged.** No timeout sequencing, no `500 → 200` retry transition, no
over-cap body, and no fixture carrying a transport directive — asserted for the composed corpora too,
against the committed `FORBIDDEN_TARGET_KEYS`. Where a scenario does involve retries (the terminal
500 does), the suite asserts the **DV-8 accounting identity** rather than a retry count: what the
client does between the first 500 and the raise remains its own tested contract.

The failure modes in one run come from **composing the committed corpus in a temp fixture tree**
(§11, S6-1) — copying Group B and substituting a Group A body — not from new committed fixtures, of
which S6-7 authorizes none. The transport modes Stage 6 does not own are **not asserted here**: no
timeout, no `500 → 200` retry sequence and no over-cap body, each of which belongs to the committed
`HttpClient` and its own tested contract (§5.0).

### S6-L · Bounded live smoke — **separately approved, and approved again at the moment of running**

**This is the only checkpoint that makes a network request, and planning approval does not authorize
it.** It requires explicit human confirmation immediately before execution, per CLAUDE.md's
stop-and-ask rule for external side effects.

Bounds, all hard:

```text
≤ 3 target URLs, from ≤ 3 distinct hosts, each already a configured source's own domain
robots consulted and obeyed; a single robots denial ends the run, reported as success of the contract
committed retry/timeout/redirect/byte-cap policy, unmodified
artifact root = a temp directory; NOTHING is written under state/ or data/
output is NEVER committed and NEVER becomes a fixture without a separate recording checkpoint
mode is recorded honestly in the manifest; no threshold is touched
```

Asserts **contracts, not bytes** (§10). Deliverable: a short report appended to the closeout handoff.
Distinct from **Stage 9**'s bounded 12-cell live smoke, which this does not open, replace or
pre-approve.

```text
A/M  docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_<date>.md   (the report section only)
```

### S6-C · Stage 6 closeout — L0, documentation only

**Paths declared now, in advance**, so the authorization gap hit at the Stage 4 closeout cannot recur
and writing the handoff needs no separate path-set approval:

```text
A  docs/harvest/handoffs/HANDOFF_STAGE_6_COMPLETE_<YYYY-MM-DD>.md
M  docs/harvest/STAGE_6_IMPLEMENTATION_PLAN.md      status header only
M  docs/harvest/TODO.md                             closeout registration
```

Exactly those three paths. L0 validation only: exact three-path diff · `git diff --check` · nothing
under `src/`, `tests/`, `scripts/`, `config/`, `schemas/`, `state/`, `data/` or any run artifact ·
protected baseline and the 508-file untracked baseline unchanged. Per its own risk tier the focused
suites and the full gate are **not** rerun for a documentation-only change. It must record: the commit
chain, every deviation with its approval, CF-3 discharged, CF-1 still deferred, CF-13/15/16/17 carried
forward, the final assertion count, and the exact repository state.

### 11.1 Dependency graph

```text
S6-0 ── S6-1 ──┬── S6-2 ──┐
               └── S6-3 ──┴── S6-4 ── S6-5 ── S6-6 ── S6-6A ── S6-6B ── S6-7 ── S6-L(opt) ── S6-C
```

**S6-6A sits between S6-6 and S6-7 by necessity, not by preference** (§14.4): S6-6 could not derive an
exact target-attempt count inside its own ownership boundary, and S6-7 pins a manifest that S6-6A
changes the shape of. **S6-6B sits there for the same structural reason** (§7.4, E18): S6-7 pins
ledger determinism, and the ledger was about to gain three fields.

S6-2 and S6-3 are independently reviewable once S6-1 lands; S6-3 does not depend on S6-2. **S6-L is
optional to closing Stage 6** — a green offline Stage 6 is a complete stage, and the live smoke is
not a completion requirement (`IMPLEMENTATION_PLAN.md` §7.1's precedent for the live smoke staying
staged).

---

## 12 · Design decisions — both RESOLVED on 2026-07-30

Two, both minimal, each blocking exactly one checkpoint. **Both are now resolved as recommended.**
A resolved decision fixes the *shape* of a future change and nothing else: S6-5 and S6-6 remain
unapproved and unimplemented, and neither may begin on the strength of this section.

### 12.1 · D6-A — RESOLVED: one keyword-only parameter on `records.make_full_record` (S6-5)

`records.py` hardcodes `"url_aliases": []` with no parameter, so §4's adjudicated aliases could not
reach a record. **Approved: one backward-compatible keyword-only parameter**, exactly mirroring the
DV-2 `case_facets` precedent:

```python
url_aliases=None
```

The alternative — mutating the completed record dict in `run_cells.py` after construction — was
**rejected**: it creates a second place that knows the persistent record's shape, which is precisely
the drift D2 exists to prevent.

What this decision records, and what S6-5 must therefore honour:

- **`make_full_record` remains the sole owner of the persistent record shape.** No other module
  assembles, reshapes or completes a record. There is one builder, and after S6-5 there is still one.
- **`make_full_record` owns validation, normalization and projection of `url_aliases`** — the shape
  check against `record.v1.json`'s `url_alias` definition, the sort-and-deduplicate by `(kind, url)`
  from §4, and the projection of admitted keys. `run_cells.py` supplies adjudicated aliases; it does
  not decide how they are stored.
- **Existing callers keep the committed behaviour.** Omitting the argument, or passing `None` or an
  empty sequence, yields `"url_aliases": []` byte-for-byte as today. The parameter is additive,
  keyword-only, and changes no existing call site — Stage 4's S4-5B already proved this builder accepts
  a new keyword payload without disturbing `record_id`, `content_id` or `identity_url`.
- **`run_cells.py` passes aliases; it never mutates the completed record dict.** Asserted by S6-5, not
  merely intended.
- **`records.py` stops being byte-unchanged since `b303d9d`.** That is the authorized cost of this
  decision, recorded here as the explicit authorization the Stage 5 handoff §7 requires, and confined
  to this one additive parameter. No other line of `records.py` changes.

**The S6-5 allowed-path declaration in §11 now includes `src/harvest/records.py` unconditionally**, and
every other path this decision requires — and no unrelated path.

### 12.2 · D6-B — RESOLVED: a committed schema for the alias-conflict artifact (S6-6)

`IMPLEMENTATION_PLAN.md` §2.3 already specifies the artifact (`runs/<run_id>/alias_conflicts.json`)
and its per-conflict fields (`conflict_id`, `kind`, `record_ids[]`, `proposed_alias`, `evidence`,
`detected_at`, `resolution`), but no schema was ever committed for it — and §3.5's rule is that
nothing is written without validating against a committed schema **first**. **Approved: commit
`schemas/harvest/alias_conflict.v1.json`** at the exact future path declared by S6-6 in §11.

The alternative — reporting only the manifest's already-committed `alias_conflicts_count` and dropping
the per-conflict detail — was **rejected**: a bare count tells an operator that a conflict exists but
not which records or what evidence, which makes the eventual `resolve-alias` step guesswork.

What this decision records, and what S6-6 must therefore honour:

- **The committed schema validates the complete artifact**, not merely one conflict entry — the whole
  `runs/<run_id>/alias_conflicts.json` document shape, either directly or through an explicitly
  committed wrapper object carrying the entries. A schema that validated only an entry would leave the
  document's own envelope unvalidated, which is the gap §3.5 exists to close.
- **The artifact is validated before it is written.** It goes through the single S5-1
  `write_document` path — validate in memory, then serialize, then atomically rename — so an invalid
  document writes no file at all. No second validator, serializer or writer.
- **`alias_conflicts_count` is derived from the validated artifact contents.** It is never a
  caller-supplied parameter and never an independently maintained counter, so the manifest's count
  cannot disagree with the conflicts beside it — the same rule S5-2 established for every artifact
  count.
- **The schema carries no vocabulary hash.** It is therefore **not** part of the atomic
  vocabulary-plus-generated-schema contract, needs no `gen_facet_schema.py` run, and cannot fall out of
  sync with a vocabulary file. `gen_facet_schema.py --check` and `check_facets.py` are unaffected.
- Stage 6 adds **exactly one** schema file, the first since Stage 2.5, and no existing schema changes.

**The S6-6 allowed-path declaration in §11 now includes the new schema and its owning focused tests
unconditionally** — and no unrelated path.

---

## 13 · Risk tiers, gates, commit, rollback and stop boundaries

**Full gate** (once, before each commit from S6-1 onward, Stage 5 §4 unchanged): every
`tests/test_taxonomy_*.sh` · `check_fixtures.py` · `verify_protected_baseline.sh` ·
`check_facets.py` · `gen_facet_schema.py --check` · `check_config.py` ·
`git diff --exit-code -- scripts/harvest/check_config.py` ·
`git status --porcelain --untracked-files=no` · the 508-file untracked baseline ·
`git diff --stat 8865c54e… HEAD -- .gitignore` still exactly `1 insertion(+)`.
`scripts/validate_task.sh` is **not** the Stage 6 gate (CF-4). Capture command output to a file rather
than piping — the guard hook blocks piping a protected command into `head`/`tail`/`grep`/`sed`/`awk`/
`tee`, and piping would mask the exit code.

**Focused suite** = the checkpoint's own `tests/test_taxonomy_*.sh`, run repeatedly during work. Each
new wrapper carries the committed epilogue: production `state/` and `config/` unmodified **and** the
repository's own runtime paths (`state/taxonomy_harvest`, `data/harvested`, `runs`, `LATEST_RUN_ID`)
never created.

**+FS additionally**: temp-root isolation · `state/taxonomy_harvest/` absent after the suite ·
atomicity (an interrupted write leaves no readable artifact) · determinism (tree hash stable).

**Every test asserts no live request.** `HttpClient` is constructed only over `FixtureOpener`, and a
test asserts no socket is opened. This holds for S6-1 … S6-7 without exception; S6-L is the single,
separately approved exception and runs nothing under `state/` or `data/`.

**Commit.** One commit per checkpoint, atomically, over that checkpoint's declared paths only, via
`bash scripts/safe_commit.sh -m "…" <explicit files>`. Never `-A`, never `.`, never a glob. Commit
messages omit the Claude co-author trailer, per this repository's convention.

**Do not push.** Pushing is a separate, explicitly approved action (`safe_push_main.sh --check`, then
`--execute`), never bundled into a checkpoint.

**Rollback.** S6-1 … S6-7 are additive apart from `TODO.md`, this file, and the declared `M` paths:
`rm` the checkpoint's new files, `git checkout --` the modified ones, re-run the full gate. `run_cells.py`
accretes across S6-4, S6-5 and S6-6 and `artifacts.py` across S6-6, so rolling back one of those means
reverting that commit — each is a single atomic commit precisely so this is possible.

**Rollback triggers.** Any of the 1,324 prior assertions turning red · any existing test needing an
edit that is not a ratified corrective change · protected-baseline failure · drift in the 508
pre-existing untracked files · a write outside the injected root · **any live request outside S6-L** ·
`identity_url`, `record_id` or `content_id` moving · a score, category or facet changing between a
fetch and a no-fetch run · discovering that a Stage 6 module cannot meet a committed contract without
changing a Stage 4 module, a config file or an existing schema — which returns for an explicit
deviation rather than being bent in code.

**Stop and ask** for: any live network request · material scope expansion · a contradiction between
committed contracts · a data-integrity risk · a production `state/` write · anything needing
credentials · any need to touch a path outside the checkpoint's declared set. Nothing else justifies
pausing mid-checkpoint.

**Never claim success** unless the latest full-gate run is green and the exact declared path set — no
more, no less — is what changed.

**A boundary test asserts facts about the surface of the module under test** — never which files
happen to exist yet, and never how the working tree compares to HEAD. Stage 5 learned this four
times; Stage 6 inherits it. Concretely: **no future-file absence assertions**, no
`test_it_does_not_begin_S6_n` guards, and no `git diff --exit-code` against HEAD for a module the same
stage is authorized to edit.

---

## 14 · Errata — stale statements in earlier documents

Earlier documents are not rewritten. This plan is the authority for Stage 6 where they conflict.

**E11 — `TODO.md`'s "Stage 6 — refresh, link-check, diff, promote" heading is broader than this
stage.** That heading's checklist bundles the `refresh` / `linkcheck` / `promote` / `diff` /
`compare-runs` subcommands, the transaction journal and the promotion tests together with target
fetching. This plan scopes Stage 6 to **target fetching and verification only**; the subcommand and
promotion items under that heading stay **unscheduled, unapproved and untouched**, and this plan opens
none of them. The heading is not wrong, merely broader than what is being planned.

**E12 — `IMPLEMENTATION_PLAN.md` §6 says target-page fetching is exercised "by `linkcheck`."** Written
before the stage boundaries existed. Target fetching arrives here, in the harvest path, over fixtures;
`linkcheck` remains unimplemented, and its `link_history` append-only structure is untouched (§6).
`smoke.enrich` stays `false` in the committed policy and Stage 6 does not change it.

**E13 — `IMPLEMENTATION_PLAN.md` §10 lists runtime directories no stage has created yet.** Stage 5
created `runs/`, `rejections/` and `ledgers/`; Stage 6 adds nothing beyond, at most, one file inside
the existing `runs/<run_id>/` (§12.2 D6-B). `logs/`, `tmp/`, `candidate_output/`, `promote_staging/`,
`promote_rollback/`, `promotion_receipt.json`, `registries/`, `cache/`, `domains/`, `migrations/` and
`locks/` each remain the property of the stage that first needs one.

**E14 — the Stage 5 handoff's `push_state` line is a pre-push snapshot.** Recorded in the header
above: the authoritative state is `main` synchronized with `origin/main` at `6bf7f51`.

**E15 — this plan's own first S6-1 corpus wording was neither literal nor implementable, and is
corrected in place.** Found by an S6-1 preflight on 2026-07-30, which **stopped without editing a
single file** rather than resolving the gap by improvising fixtures. Three distinct defects, all in
this document and none in shipped code:

1. **Two corpus items were not properties of a target-page fixture at all.** "One URL surfaced by two
   sources in one cell" and "one URL reachable from two topics" describe what the *feeds* surfaced. The
   preflight measured the committed corpus through the committed adapters and `dedupe.group`: **109
   candidates, 109 distinct identities, 0 surfaced by ≥2 sources, 0 appearing in ≥2 topics.** Satisfying
   either item would have required editing a source fixture body or adding a source to a topic config —
   neither in S6-1's path set, and the config edit would also have triggered CF-6. **Relocated to S6-4**
   as a synthetic-input ownership test (§3, S6-4); **not** fixed by widening S6-1.
2. **Three items required transport behaviour a static fixture cannot express.** A timeout needs the
   opener to raise `HttpTimeout`; `500 → 200` needs per-URL response sequencing; an over-cap body needs
   >8 MiB of committed bytes or a generator. Each would have meant inventing a fixture directive DSL and
   thereby owning retry, timeout and body-cap semantics that the committed `HttpClient` already owns and
   tests. **All three removed from Stage 6** — §5.0 now states the ownership boundary outright, and the
   `500 → 200` assertion is removed rather than relocated.
3. **The corpus was declared as directory globs and prose, so no exact filename set followed from it.**
   Chain lengths, host allocation and naming were all underdetermined. **Replaced by the two literal
   tables in S6-1**, which are now the only authorization to create a fixture file.

The rule this leaves behind, which is why the preflight was right to stop: **a checkpoint's fixture
authorization is a literal file list, never a directory glob.** A glob cannot be reviewed, and a
corpus that has to be improvised at implementation time was never specified.

**E16 — this plan asserted that same-domain canonical trust "is implemented as identical host". It is
not, and never was.** Found by an S6-3 preflight on 2026-07-30, which **stopped without editing a
file**. `urlkey.registrable_host` has been committed since Stage 1, documented as "used only for
same-domain trust checks", and takes the last two labels — so it already made the no-public-suffix
tradeoff this plan cited as the reason no such helper could exist. The wording was wrong in a way that
mattered rather than cosmetically:

```text
tgt.harvest.test        → registrable_host → harvest.test
tgt-alt.harvest.test    → registrable_host → harvest.test        SAME registrable domain
```

so `tgt_canonical_cross_host.json`, the one fixture built to prove the cross-domain conflict row, was
in fact a **same-domain** case. The two rules returned **opposite verdicts** on it: identical-host said
conflict, the committed helper said auto-accept. Whichever was implemented, one committed artifact
would have been stating something false, and neither could be fixed from inside S6-3's three paths.

Corrected here, in one checkpoint, without touching `registrable_host` or reopening Stage 1:

1. **§4 now reads "same / different registrable domain"**, with the committed helper named as the sole
   authority and exact hostname equality noted as a subset of it. No second comparison, no
   public-suffix implementation, no special-case host list. Every other prerequisite on those rows —
   syntax, non-circularity, robots, `domain_migrations`, independent 301/308 — is unchanged.
2. **CF-15's premise is corrected** (§9.7) and its replacement boundary recorded. The correction is
   deliberately narrow: it claims nothing broader about canonical-domain handling, and the helper's own
   best-effort limitation stays an inherited Stage 1 tradeoff.
3. **The fixture's canonical target became `https://other-target.test/elsewhere`** — a genuinely
   different registrable domain — with its `contract_intent` and its single `MANIFEST.json` entry
   updated. Same filename; no fixture added, removed or renamed; no robots fixture for the new host,
   because a cross-domain canonical is refused before any robots check and Stage 6 never probes a
   discovered canonical.
4. **The same-domain branch is allocated to a test-local synthetic case** in S6-3, with an anti-vacuity
   assertion, rather than to a new permanent fixture.

The rule this one leaves behind: **when a plan states what an existing API does, check the API.** This
note's justification was sound reasoning from a premise nobody had verified, and it survived plan
approval, a decision-record checkpoint and a fixture-scope correction before a preflight caught it.

**E17 — §5.0 said `targetfetch.py` "never observes an attempt, a hop count, a retry". Amended by
S6-6A.** The sentence conflated two different things and only one of them was ever the contract.
S6-2 wrote it to fence off *transport ownership*: no retry loop, no timeout, no redirect following, no
body cap, no second opinion about how many requests should be made. That fence stands and is still
asserted. But the wording also forbade *reading a number the client had already computed and frozen*,
and that prohibition had no purpose — it was the sole structural reason §14.4 found an exact target
attempt count unreachable, and it made the outcome discard `Response.accounting` on the success path
and `HttpError.accounting` on the failure path, both of which DV-8 exists to provide.

The corrected line: **`targetfetch.py` carries the client-frozen `FetchAccounting` outward without
independently implementing or interpreting retry, redirect, timeout, body-size or transport policy.**
It never branches on a counter; it copies one object, exactly as it already copies `body`,
`content_type`, `final_url` and `permanent_redirect` without parsing or reclassifying any of them.
`fetch_target` still makes exactly one logical client call, still raises on an unmapped `HttpError`
subclass, and still has no retry, timeout or size logic of its own — all of which remain pinned by
`tests/harvest/test_target_fetch.py`.

The rule this one leaves behind: **an isolation boundary should name the judgement it forbids, not the
data it refuses to look at.** "Forms no opinion about attempts" would have been true for the whole of
Stage 6; "never observes an attempt" was a stronger claim than the design needed, and it cost a
checkpoint to walk back.

**E18 — §7.4 said Stage 6 "populates" the ledger's target triple. It did not, until S6-6B.** Found by
the read-only S6-7 preflight on 2026-07-30, which **stopped without editing a file**. The section was
not describing a design decision that later slipped; it was written in the present tense about a flow
nobody had built. Everything it named was real except the last link:

```text
ledger.v1.json        admits http_status, content_hash, last_checked_at        ✓ since Stage 1
OBSERVATION_FIELDS    lists all three                                          ✓ since S5-3
merge_ledger          stores them, and treats a null as "no news"              ✓ since S5-3
run_cells observation supplied none of them                                    ✗ the gap
```

No test caught it because none existed to catch it: `test_ledger.py` never mentions the three fields,
and `test_run_cells.py`'s ledger assertions checked entry counts, outcomes, `seen_count`,
`first_seen_at` and sort order — every property except the one §7.4 claimed. It fell between S6-5,
whose declared paths covered records rather than the ledger, and S6-7, which is test-only.

Corrected in **S6-6B** (§11), with §7.4 rewritten to the flow that now exists and a run-boundary test
that fails against `88d40ca`. **The carried-forward finding is closed, not deferred.**

The rule this one leaves behind: **a plan section written in the present tense is a claim, and a claim
with no test is a guess.** §7.4's three sentences read exactly like the six other sections around them
that *were* implemented, which is why it survived plan approval, four checkpoints and two audits — the
prose gave a reader no way to tell a description from an intention.

**E19 — "the difference set is five" is true of the record-bearing artifacts, not of every file.**
§10 stated the five-leaf contract without saying which documents it ranges over, and Stage 5's test
happened to range over exactly two families — `cells/` and `topics/` — so the question never came up.
S6-7 extends the recursive diff to the complete tree and finds three more families with instants of
their own: the manifest's `started_at`/`finished_at`, a rejection log's `rejected_at` and `freshness`,
and a ledger's `updated_at`/`first_seen_at`/`last_seen_at`/`last_checked_at`. **None is a determinism
defect and none is excused**: each family is enumerated exactly, in its own assertion, so a new moving
leaf still fails. §10 now carries the full table.

The `freshness` entry is worth naming on its own: `rejection.v1.json`'s `scores` block is
`{relevance, quality, audience_fit, freshness}` while `record.v1.json` uses `*_score`, so the same
clock-derived quantity appears under two leaf names depending on which document you read. S6-7
enumerates both rather than normalizing them together, because the leaf that moved is the leaf the
document actually has.

**E20 — S6-7's "every §5 failure mode the committed corpus can express" excludes a run-level
`robots_denied`, and always did.** The wording implied a set the corpus cannot produce. All four
accepted targets are on `github.com`, and so is `fx_lm_eval_harness`, the feed that surfaces them:
denying that host in a composed robots tree stops discovery, so the run yields no candidates and
therefore no denied record. Forcing the case would require editing a source fixture or a topic config
in the scenario — exactly what E15 refused for the same reason. The contract keeps its existing and
better owner: `test_target_fetch.py` asserts `RobotsDenied → robots_denied` directly, and fixture #20
proves the denial preceded the request by never being opened at all.

**E21 — the S6-7 scenario corpus is four scenarios, not one run.** §11's "in one run" was written
before the fixture corpus existed. The committed corpus accepts exactly four records, so four target
slots is the whole budget, and terminal failures, body and redirect handling, canonical adjudication
and budget skipping cannot all occupy them simultaneously — several are mutually exclusive on a single
URL. S6-7 therefore runs four deterministic scenarios, each a separate composed corpus, rather than
forcing an impossible single run. Every scenario emits a complete 43-path tree in which every artifact
validates, which is the property "in one run" was reaching for.

---

## 14.1 · S6-T / S6-TD — the `domain_throttle` instability, unexplained

Recorded here rather than as a carried-forward finding, because it is not a Stage 6
design question: it is an unexplained test-suite instability that Stage 6 happened to
surface, and it must not quietly become an accepted exception.

**Three failure signatures observed, all inside full-gate runs, all in
`tests/test_taxonomy_domain_throttle.sh`:**

```text
1  test_minimum_interval_enforced_across_processes
   0.2970s / 0.2974s against the 0.300s minimum — a sub-1% undershoot     seen 2x
2  test_cap_of_two_is_respected_and_used
   "cap of 2 never actually used" — the subprocesses did not overlap      seen 1x
3  test_six_workers_respect_max_concurrency_one
   a worker LeaseTimeout after 30s with max_concurrency=1                 seen 1x
```

**S6-T attempted a diagnosis and found no reproducible production defect.** What was
measured, so a successor does not repeat it:

- **The faithful process-based reproduction is green.** Six real worker processes, two
  acquisitions each, `max_concurrency=1`, fresh temp root: **12/12 acquired, 0 timeouts,
  no orphaned slot and no leftover owner file, across 3 runs.** Acquisition, release and
  reclamation all behave.
- **The backoff-starvation hypothesis is disproven.** `acquire`'s jittered backoff
  escalates to 0.5–1.5s per poll and its attempt counter never resets, which looks like
  a starvation mechanism. Capping the poll interval at 0.05s changed **nothing**; and in
  the failing runs the waiters that did succeed had made 0–1 polls with a 0.117s maximum
  wait, so they were not backing off at all.
- **Artificial CPU load does not reproduce it.** Twelve busy-looping processes alongside
  `TestCrossProcessConcurrency`, twice: both green.
- **Overlap is currently deterministic.** Peak overlap with `max_concurrency=2` measured
  **2 in 8 of 8 runs**, so signature 2's anti-vacuity assertion is not fragile on an
  unloaded machine.
- **One reproduction was obtained and then discarded as an artifact.** A *thread*-based
  harness starved hard — 40 `LeaseTimeout`s with the slot free ~99% of the time — but
  threads share one PID, which changes both `release`'s ownership check and
  `_try_break_stale`'s liveness check, and they contend under the GIL with 2ms holds.
  The process-based equivalent never starves. It is recorded as a **discarded lead**.

**S6-TD therefore adds failure-only instrumentation instead of a speculative
correction.** No production file changed: `domainlease.py`, `httpclient.py` and
`tests/test_taxonomy_domain_throttle.sh` are byte-unchanged. `throttle_worker.py` now
emits one bounded `LEASE_TIMEOUT_DIAGNOSTIC ` JSON record to stderr **on the
`LeaseTimeout` path only**, then re-raises, so the exception, the exit status and every
assertion the suite already makes are unchanged. The record describes the lease tree the
worker timed out against — each slot's existence, owner text, parsed owner pid and epoch,
mtime and age, whether anything vanished mid-collection, the pace lock, `next_allowed_at`,
and any collection error — which is precisely what the three bare tracebacks could not
say. Collection is best-effort and can never mask the original failure.

A deterministic regression proves the path without waiting 30 seconds and without
scheduler luck: **the test itself holds the only slot**, and the worker is launched with a
test-only `--wait-max-sec` whose **default remains 30 seconds**, so every existing caller
is unaffected.

**The three signatures remain unexplained, and none is an accepted permanent exception.**
The one-time gate-failure exception granted for S6-3 was exactly that — one time, for one
checkpoint. Whichever checkpoint next sees a `LeaseTimeout` should read the payload rather
than reason about the mechanism, and only then decide between a production defect and test
orchestration. **S6-4 remains unapproved.**

## 14.2 · S6-4 — the eligibility ordering defect, and two spent Stage 5 guards

S6-4 was approved for ownership, deduplication and bounds. Implementing it surfaced an ordering
defect in this plan and two Stage 5 guards that had outlived their purpose. All three are recorded
here because each is a lesson about sequencing, not about the code.

**The ordering defect.** `derive_publication_eligibility` treated `target_fetch_owners > 0` as
sufficient. S6-4 is what first makes that count non-zero — so the moment ownership landed, a run
claimed `publication_eligible: true` while all four of its records still said
`access_status: "not_checked"`. §8 had already identified the weakness and assigned the fix to
**S6-6**, two checkpoints after the symptom. Measured on the committed corpus:

```text
before the guard   target_fetch_owners 4 · publication_eligible TRUE  · records all not_checked
after the guard    target_fetch_owners 4 · publication_eligible FALSE
                   reason "4 of 4 accepted records carry no target evidence (access_status not_checked)"
```

**The missing-target-evidence guard was therefore brought forward from S6-6 into S6-4**, and only that
guard: a run is ineligible whenever any **full** accepted record lacks target evidence;
`target_fetch_owners > 0` is necessary but never sufficient; a budget-skipped `not_checked` record keeps
the run ineligible; `cross_reference` rows are excluded from both sides of the count, since a pointer
carries no `access_status` and counting one would invent a finding out of the cross-topic policy. The
condition and its reason stay **derived** — `publication_eligible` remains absent from
`build_run_manifest`'s signature, and a test asserts it.

**S6-6 keeps everything else**: alias-conflict artifact writing and its schema, `alias_conflicts_count`
manifest reporting, target HTTP-attempt reporting (`pool.accounting` still sums `http_attempts` from
source snapshots only, so target fetches are absent from that total), `config.enrich` / `config.bounds`,
and the **positive** eligibility completion proof, which belongs with the evidence wiring that can make
a run eligible at all.

**Two spent Stage 5 progress guards were retired**, each having prohibited exactly the semantics S6-4
legitimately introduced:

```text
tests/harvest/test_recovery.py    test_no_target_fetching_was_introduced — DELETED entirely.
                                  A token scan forbidding `acquire_target_fetch` in run_cells.py,
                                  commented "Stage 6 territory". Deleted rather than narrowed, and
                                  NOT replaced with a guard against S6-5 — the S5-5/S5-7 precedent.
tests/harvest/test_run_cells.py   one assertion deleted from
                                  test_a_stage_5_run_is_honestly_ineligible_for_publication:
                                  `target_fetch_owners == 0`. Its two substantive assertions —
                                  that the run is ineligible, and that the reason concerns target
                                  evidence — are unchanged and now pass for the RIGHT reason.
```

Renaming `acquire_target_fetch` to slip past the scan was rejected on the S5-4 precedent: it would
obfuscate code to satisfy a test. **The rule this reinforces, for the third time in this repository:** a
guard that says "the next checkpoint has not happened yet" is spent the moment that checkpoint is
approved, and belongs in the *approving* checkpoint's declared path set. S6-5's own such guard is
predeclared in §11 (S6-5) rather than left to be discovered.

**Robots evidence stays unwired in S6-4.** `adjudicate` receives
`canonical_robots_allowed=None`, so no `canonical_tag` alias is adopted and a
`canonical_robots_not_verified` conflict is recorded instead — truthful, because the driver genuinely
did not verify it. **S6-5 must preflight** whether an existing API can supply *cached* robots evidence
without a new network request: a same-host canonical is a robots cache hit, since the client already
fetched that origin's `robots.txt` during the target fetch, whereas a different-host canonical in the
same registrable domain is a new origin and therefore a real probe.

## 14.3 · S6-5 — `config.enrich` brought forward, and four spent Stage 5 guards

**`config.enrich` moved from S6-6 into S6-5**, and only that field. S6-5 is what first
makes the old hardcoded `False` untrue: a run that fetched four target pages and wrote
observed evidence onto four records had enrichment enabled, and reporting `enrich: false`
beside a `publication_eligible: true` **derived from that very evidence** would put two
contradictory statements in one manifest.

It is derived from **whether the target-fetch phase was enabled** — the driver's own
explicit decision, bound once in `run()` and threaded to both the fetch phase and
`_config_block`, so the reported fact and the behaviour cannot disagree. Deliberately
**not** derived from `publication_eligible`, and **not** from how many records came back
checked: a run that enabled enrichment and had every fetch fail still enriched, and must
say so. The parameter is keyword-only and **required**, so a caller cannot omit it and
silently re-acquire the dishonest default.

`run()`'s public signature is unchanged — `test_recovery.py` pins it to five parameters,
and an `enrich=` argument there would have broken it. The consequence, stated plainly:
`run()` currently has exactly one mode, so the `false` branch is proved at the
`_config_block` boundary and by a cell run without a pool, rather than end-to-end. That
is a real limitation of the proof, not of the derivation.

**S6-6 keeps everything else**: `config.bounds`, target HTTP-attempt reporting, conflict
routing, the alias-conflict artifact and its schema, and the final positive/negative
eligibility proof.

**Six spent progress guards retired**, each false by design once S6-5 landed:

```text
test_run_cells.py  test_no_target_page_was_fetched              DELETED (predeclared in §11)
                   asserted every full record is `not_checked`; S6-5 exists to change that
test_run_cells.py  Stage 4 byte-unchanged tuple                 `src/harvest/records.py` REMOVED
                   D6-A authorizes that file to change; asserting otherwise asserts something
                   the plan states is false — the S5-7 correction, repeated
test_run_cells.py  test_a_stage_5_run_is_honestly_ineligible…   DELETED entirely
                   its premise is a run that fetched nothing; the positive eligibility proof
                   is S6-6's, so it was deleted rather than retargeted
test_run_cells.py  assertFalse(config["enrich"])                one line REMOVED
                   the direct consequence of the correction above; both directions are now
                   owned by tests/harvest/test_target_evidence.py
test_recovery.py   CLOCK_DERIVED                                "last_checked_at" ADDED
                   plan §10's predicted fifth clock-derived leaf; still exactly enumerated,
                   so a SIXTH moving field fails rather than passing silently
test_target_ownership.py  two S6-4 tests               DELETED entirely
                   test_the_run_is_still_honestly_ineligible and
                   test_the_records_still_say_nobody_checked_them — S6-4's own guards
                   against S6-5, whose premise ("records still say not_checked") S6-5
                   exists to falsify. Every ownership, deduplication, budget and
                   synthetic eligibility-predicate test in that file is preserved.
```

**The pattern, now visible three checkpoints running.** S6-4 was blocked by two such guards,
S6-5 predeclared one and was blocked by three more. Predeclaration worked; what was missing
was a sweep of the *whole file* for other assertions whose truth depended on Stage 6 not
having landed. **Before S6-6 is approved, `test_run_cells.py` and `test_recovery.py` should
be audited once for that shape and the results predeclared**, rather than discovered a
checkpoint at a time.

**Robots evidence remains unwired.** `canonical_robots_allowed=None`, so no `canonical_tag`
alias forms and every integrated-run record carries `url_aliases: []` with
`canonical_url == identity_url`. A test pins that, so the day robots evidence is wired the
change is visible rather than silent. The S6-5 preflight established **why** it stays
unwired: `RobotsCache.get`, `.allowed` and `.crawl_delay` all fall through to `_fetch()` on a
miss or expired TTL, so none of them can be called without risking a request, and
`self._cache` is private state that reading would duplicate the TTL logic. There is no
committed cached-verdict API.

## 14.4 · S6-6 — target request accounting is BLOCKED, and no longer S6-6's

**The S6-6 preflight proved an exact target HTTP-attempt count cannot be derived
within S6-6's ownership boundary.** Two independent reasons, both structural:

- **`pool.accounting()["http_attempts"]` can never see a target fetch.** It sums
  `self.sources` only, and source snapshots are created by
  `record_established_source`, which exclusively the *source*-fetch path calls. A
  target fetch adds nothing to that map, so its attempts, retries and redirect hops
  are invisible to that aggregate — the under-reporting first observed at S6-4
  (`http_attempts: 25` after four target fetches).
- **The committed S6-2 `TargetFetchOutcome` does not carry the count.** `HttpClient`
  freezes a DV-8 `FetchAccounting` onto every `Response` and every typed error, but
  `targetfetch.py` deliberately never reads it — its docstring says so: *"It never
  learns how many attempts were made, how many redirect hops were followed."* That
  was S6-2's declared isolation boundary, and it is why the number is unreachable.

**Consequences, recorded so nobody re-derives them:**

- **S6-6 no longer owns target-attempt reporting.** It reports none.
- **No estimate is permitted, and no `client.stats` delta.** DV-8 exists precisely
  to forbid diffing shared counters — a target fetch interleaved with a robots
  fetch would mis-attribute, and a plausible-looking wrong number is worse than an
  absent one.
- **Source and target request accounting must remain DISTINCT.** §2 makes them
  different key spaces with different owners and different counters; folding target
  attempts into `http_attempts` would erase that boundary. **`http_attempts` keeps
  its existing source-only meaning and must not be newly described as including
  target attempts.**
- **A separate accounting checkpoint is required after S6-6 and before S6-7.** Its
  exact paths are **not declared here**: it needs a read-only ownership and path
  audit first, because the candidate routes touch `targetfetch.py` (add a field to
  the outcome) or `pool.py` (record target attempts), and `pool.py` is byte-frozen
  by the Stage 5 successor constraints. Guessing the path set is what produced three
  consecutive mid-checkpoint stops.
- **S6-7 is blocked until the accounting contract is resolved.** S6-7 asserts
  determinism and failure modes over a full run's artifacts, and a manifest whose
  request accounting is about to change shape is not a stable thing to pin.

**RESOLVED by S6-6A** (§11, `S6-6A · Target request accounting`). The read-only audit
this section demanded was performed before a file was edited, and it settled the two
open questions:

- **The route is `targetfetch.py`, not `pool.py`.** The client already freezes an
  exact `FetchAccounting` onto the final response and onto every typed error; the
  only gap was that `_success` and `_failure` discarded it. The outcome now carries
  that committed object — copied, never reconstructed, the same rule
  `sourcecache.py` states for the source lane. `pool.py` and `httpclient.py` are
  **untouched**, so the byte-freeze holds and no guard is retired for them.
- **The two key spaces stay distinct in the manifest, by name.** Three new optional
  keys, `target_http_attempts` / `target_retries` / `target_redirect_hops`, sit
  beside the owner counters that already describe both lanes. `http_attempts`,
  `retries` and `redirect_hops` keep their **source-only** meaning, unchanged in
  value and in wording, and `total_http_attempts` remains forbidden by a live test.
  Nothing is estimated and no `client.stats` delta is taken; every number is the sum
  of counters the client incremented at the moment each event occurred.

**S6-7 is unblocked** by S6-6A landing green, and remains **unapproved**.

**What S6-6 did ship**: the alias-conflict artifact and its committed schema, the
derived `alias_conflicts_count` read back from the validated document, `config.bounds`
reporting every cap the run enforced, and the §8 eligibility proof in both
directions. Canonical robots evidence remains unwired.

## 15 · Approval status, and what this approval does not do

Stage 5 §10's conditions 1–9 are met at `bc920b5b…` and evidenced in §3 and §4 of the Stage 5
completion handoff. **Condition 10 — explicit approval — was given on 2026-07-30 for this plan, as the
plan of record and nothing more.** Stage 6 is now *planned*; it is not *open for implementation*.

**Approving this document approves the plan only.** It authorizes:

- no production code, test, script, config or schema change;
- no filesystem write outside `docs/`;
- **no live network request, of any kind, to any host**;
- not even S6-1.

Each checkpoint S6-1 … S6-C must be approved **separately and by name** before any file outside
`docs/` changes, and S6-L must be approved **twice** — once as a checkpoint and once immediately
before it runs. A green gate, an approved plan and a completed predecessor checkpoint do **not**
together authorize the next one. **Planning approval authorizes neither implementation nor live
network access.**
