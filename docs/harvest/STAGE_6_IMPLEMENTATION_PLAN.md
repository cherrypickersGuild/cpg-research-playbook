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
  cross-topic behaviour observable, and it must be proved with a fixture.
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
| `rel=canonical`, **same host**, absolute, syntactically valid, non-circular, robots-allowed | that URL | `+{kind: "canonical_tag", evidence: {rel_canonical}}` | as fetched |
| `rel=canonical`, **different host**, with a matching `domain_migrations` rule | that URL | `+{kind: "domain_rule", evidence: {rule_id, config}}` | as fetched |
| `rel=canonical`, **different host**, no rule and no independent 301/308 to the same target | **unchanged** | **none** | as fetched · **alias conflict recorded** |
| Malformed, relative-unresolvable, circular (A→B→A), or two conflicting `<link rel=canonical>` | **unchanged** | **none** | as fetched · **alias conflict recorded** |

Notes that are decisions, not details:

- **"Same registrable domain" is implemented as "identical host."** No public-suffix library is
  available (`jsonschema` is the only pinned dependency) and inventing suffix rules is how a
  destructive merge gets shipped. `example.com` → `www.example.com` is therefore treated as
  cross-domain: no alias, one recorded conflict. Conservative in the safe direction, and recorded as
  **CF-15** rather than papered over.
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
exact target-derived triple. Stage 6 populates them through the committed
`ledger.merge_ledger`/`OBSERVATION_FIELDS` path. `first_seen_at` is still written once, a terminal
outcome is still final, and a corrupt ledger still raises. No ledger field is added.

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
CF-15  "same registrable domain" is implemented as "identical host"; www. variants become
       conflicts rather than aliases (§4)
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

Discharges **CF-3**. No fetching logic, no records, no writes.

```text
A  tests/fixtures/harvest/targets/*.json         synthetic target pages, authored_at/authored_against
A  tests/fixtures/harvest/robots/*.json          one per NEW target host; existing files untouched
M  tests/fixtures/harvest/MANIFEST.json          bytes + SHA-256 per new file
M  src/harvest/fixtures.py                       load_target_fixtures(); FixtureOpener(targets=…)
M  scripts/harvest/check_fixtures.py             target-tree completeness and provenance
A  tests/harvest/test_target_fixtures.py
A  tests/test_taxonomy_target_fixtures.sh
```

`FixtureOpener` gains **one** URL index, not a second one: targets merge into the existing `_by_url`
map with the same duplicate refusal, so nothing above the opener can tell a target from a source —
which is the property that makes the corpus a real test of `HttpClient`. `check_config.py` stays
byte-unchanged (DV-1).

The corpus must cover, at minimum: 200 HTML with a same-host `rel=canonical` · 200 with a
cross-host canonical · 200 with two conflicting canonicals · 200 with a circular canonical · a
301→301→200 chain · a 302 chain · 404 · 410 · 403 · 500-then-200 (retry) · 500-always · a
timeout · a robots-denied host · an over-cap body · a non-HTML body (PDF and JSON) · an empty
body · one URL reachable from **two topics** (§3) · one URL surfaced by **two sources in one
cell**.

Focused suite: `tests/test_taxonomy_target_fixtures.sh` + `check_fixtures.py`. Full gate before
commit.

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
string literal. Proves the §4 table row by row, and proves `identity_url`, `record_id` and
`content_id` are byte-identical in every row — including every conflict row.

### S6-4 · Ownership, deduplication and bounds in the driver — L2

```text
M  src/harvest/run_cells.py         the fetch phase: add_candidate → acquire_target_fetch →
                                    fetch_target → adjudicate, over the accepted set only
A  tests/harvest/test_target_ownership.py
A  tests/test_taxonomy_target_ownership.sh
```

No record field changes yet — this checkpoint proves **who fetches what, how often, and within which
bounds**: once per canonical identity, once across topics, `MAX_TARGET_FETCHES_PER_CELL` respected and
reported, target fetching nested inside the committed `cell:` budget scope, `target_fetch_owners` and
`extraction_owners` flowing through `pool.accounting()`, `source_fetch_owners` **unchanged** by target
fetching, and the CF-1 static scan extended to the two new modules. Also proves a target page yields
no candidate and no adapter is invoked on one.

### S6-5 · Target evidence on records — L2

```text
M  src/harvest/run_cells.py         _full_record consumes the outcome instead of the verdict's
                                    honest no-enrichment defaults; passes adjudicated aliases
M  src/harvest/records.py           one keyword-only `url_aliases=None` and its validation,
                                    normalization and projection — §12.1 D6-A, RESOLVED
A  tests/harvest/test_target_evidence.py
A  tests/test_taxonomy_target_evidence.sh
```

Exactly four paths. `src/harvest/records.py` is authorized here by §12.1 and nowhere else, for that one
additive parameter and nothing more.

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

### S6-7 · Determinism, failure modes and partial runs, end to end — L1 +FS

```text
A  tests/harvest/test_target_determinism.py
A  tests/test_taxonomy_target_determinism.sh
```

The five-leaf difference set enumerated by recursive JSON diff (§10) · byte-determinism under
shuffled source, candidate and cell orderings · every §5 failure mode present in one run, every
record validating · an interruption during the fetch phase writing **nothing at all** · a repeated
finished `run_id` refused **before the first request** · `verify_latest_run_id` still a checkable
predicate · a run that never fetched still honestly ineligible.

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
               └── S6-3 ──┴── S6-4 ── S6-5 ── S6-6 ── S6-7 ── S6-L(optional) ── S6-C
```

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

---

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
