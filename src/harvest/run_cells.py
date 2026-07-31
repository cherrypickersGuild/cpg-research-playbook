#!/usr/bin/env python3
"""run_cells.py — the cell driver (S5-6).

Stage 4 built a complete in-memory pipeline. S5-1 … S5-5 built the artifact
contracts. This module is the only thing between them: it runs the committed
pipeline over the fixture corpus once per configured cell and emits one run's
worth of artifacts. It adds no judgement of its own.

Three properties hold this together:

  * NOTHING IS REIMPLEMENTED. Discovery, dedupe, extraction, classification,
    verification, facet assignment and record construction are called exactly as
    committed; serialization, atomic writes, artifact assembly, the ledger, the
    coverage report and the manifest are the S5-1 … S5-5 functions. This module
    routes and counts. It never re-derives a score, a category, a facet or an
    identity, and it never decides what a record *is* — only where the committed
    decisions say it goes.
  * SEQUENTIAL, DELIBERATELY. Cells run one after another. That keeps CF-1
    untriggered — `pool.add_candidate`, `acquire_target_fetch` and
    `acquire_extraction` keep their zero concurrent callers — and it is also what
    makes byte-determinism straightforward to prove. Any later change that runs
    cells concurrently must fix CF-1 first, in its own checkpoint. There is no
    lock, thread, process or async call anywhere below.
  * ONE CELL'S FAILURE IS ONE CELL'S FAILURE. A source that raises is recorded as
    that source's outcome and that cell's status; the run continues and every
    other cell's artifact is written complete and valid. A failed cell is
    reported, never omitted.

Offline by DEFAULT, and offline by construction until a caller says otherwise:
`transport=None` builds the committed `fixtures.FixtureOpener` transport, so no
request leaves the machine. `HttpClient` is still the real client — the robots
cache, the RFC 9309 matcher, retries, redirects, content-type and byte-cap checks
and DV-8 accounting all run unmodified above the injected opener, exactly as in
the Stage 3 suite. Under the fixture transport pacing sleeps are suppressed: a
fixture is a local file and there is no remote host to be polite to.

S9-1 added the transport SEAM, and only the seam. `Transport` is one frozen value
carrying the opener, the sleep function and the lease root together, because those
three are one decision: a live opener paired with a no-op sleep would issue real
requests against hosts that mandate a crawl-delay, and that combination must be
unrepresentable rather than merely discouraged. This module owns the FIXTURE
constructor and no other — there is no live constructor here, and this file never
names the live opener at all. A live transport can only be built by `cli.py`,
which is the single reviewable owner of that decision, and a test asserts the
absence rather than trusting this sentence.

`mode`, `enrich` and `source_preflight` became omission-compatible seams in the
same checkpoint: omitted, every one of them reproduces the committed behaviour
byte-for-byte, on the D6-A / S6-6A sentinel idiom. S9-1 added no bound, no cap and
no probing — `bounds` belongs to S9-3 and row assembly to S9-2, and neither is
accepted here, because a parameter that is taken and ignored is worse than one
that does not exist.

S5-7 added the run's relationship with time and with itself. A `run_id` that
already has a manifest in this root is refused BEFORE the first byte is written,
because a finished run's artifacts are immutable and discovering the clash at
publication would mean the cross-run ledger had already counted every candidate
twice. Every write is journalled, so an interruption sweeps the temp files this
run created and provably nothing else, and a run that dies leaves the previous
run's artifacts and `LATEST_RUN_ID` exactly as it found them.

Not here: target-page fetching and live requests (Stage 6), promotion,
concurrency.
"""
import contextlib
import dataclasses
import datetime
import glob
import json
import os
import re
import shutil
import tempfile

from . import adapters
from . import aliases as aliases_mod
from . import artifacts
from . import classify as classify_mod
from . import dedupe as dedupe_mod
from . import extract as extract_mod
from . import facetassign as facetassign_mod
from . import fixtures as fixtures_mod
from . import httpclient as httpclient_mod
from . import ledger as ledger_mod
from . import pool as pool_mod
from . import records as records_mod
from . import request_key as request_key_mod
from . import scheduler
from . import schema as schema_mod
from . import sourcecache as sourcecache_mod
from . import targetfetch as targetfetch_mod
from . import urlkey
from . import verify as verify_mod
from .adapters import base as adapter_base
from .budget import BudgetExhausted, RequestBudget

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOPICS_DIR = os.path.join(ROOT, "config", "harvest", "topics")
POLICY_PATH = os.path.join(ROOT, "config", "harvest", "policy.v1.json")
PRECEDENCE_PATH = os.path.join(ROOT, "config", "harvest", "precedence.v1.json")

# The bound. Twelve is the approved configured-cell count (scripts/harvest/
# check_config.py is the authority on that), so the default cap is "everything
# that is configured and not one cell more". Cells beyond the cap are recorded as
# `not_run` rather than dropped — a bound that hides work is not a bound.
MAX_CELLS = 12

# A second, visible bound on the target-fetch phase, on top of the committed
# `cell:` request budget it nests inside. The accepted count per cell is small by
# construction (4 on the committed fixture corpus), so this is generous headroom
# rather than a throttle — its job is to make a runaway enrichment phase fail
# loudly instead of quietly spending a cell's whole request budget.
MAX_TARGET_FETCHES_PER_CELL = 25

# S6-6B. The target-derived fields an accepted record contributes to its ledger
# entry, copied verbatim from the finished record. A strict subset of the
# committed `ledger.OBSERVATION_FIELDS`, and no ledger field is added: the schema
# has carried all three since Stage 1, and this is the wiring that was missing.
# Named here rather than spelled out at the call site so the set is one thing a
# reader can check against the schema, not three strings inside a loop.
LEDGER_TARGET_EVIDENCE_FIELDS = ("http_status", "content_hash", "last_checked_at")


# ------------------------------------------------------------------ transport
def _no_pacing(seconds):
    """The fixture sleep. A local file has no host to be polite to.

    Named rather than written as a lambda so a test can assert by identity which
    sleep a transport carries, and so a reader can see that suppressing pacing is
    a property of the FIXTURE transport specifically — not of the driver.
    """
    return None


@dataclasses.dataclass(frozen=True)
class Transport:
    """Where a request goes, how fast, and where the leases live — as ONE value.

    Frozen and atomic on purpose. Split into three independent `run()` parameters
    these could be set half-way: a live `opener` inherited alongside the fixture's
    no-op `sleep` would issue real requests with pacing disabled, against hosts
    that mandate a crawl-delay. One value makes that unrepresentable.

    `lease_root` is the caller's. `run()` never replaces it and never deletes it;
    only the temporary root `run()` creates for itself is swept, and only by
    `run()`.
    """

    opener: object
    sleep: object
    lease_root: str


# ---------------------------------------------------------------- run bounds
# The one place a run id is validated. Read from the COMMITTED manifest schema
# rather than retyped, so `smoke --run-id` and `validate --run-id` cannot drift
# from each other or from the document they will be written into. It lives here,
# not in `runvalidate.py`, because `runvalidate` imports this module for the
# configured cell and topic sets and the dependency cannot run both ways.
_RUN_ID_RE = None


def run_id_pattern():
    """The committed `harvest_run_id` pattern, from the schema itself."""
    global _RUN_ID_RE
    if _RUN_ID_RE is None:
        doc = schema_mod.load_schema("run_manifest.v1.json")
        _RUN_ID_RE = re.compile(doc["properties"]["harvest_run_id"]["pattern"])
    return _RUN_ID_RE


def validate_run_id_value(value):
    """Return `value` if the committed schema would accept it, else raise."""
    if not isinstance(value, str) or not run_id_pattern().match(value):
        raise RunCellsError(
            "%r is not a committed run id. The manifest schema requires %s, so a "
            "run id that would be refused at write time is refused here instead — "
            "before a single artifact exists."
            % (value, run_id_pattern().pattern))
    return value


@dataclasses.dataclass(frozen=True)
class RunBounds:
    """The bounded-smoke limits, as ONE immutable value.

    Independent `max_candidates` / `max_accepted` / `smoke_budget` parameters on
    `run()` could be set inconsistently — an accepted cap above the candidate cap
    is not a bound, it is a bug that never binds. One frozen value validated at
    construction makes the incoherent combinations unrepresentable, exactly as
    `Transport` does for the network decision.

    `elapsed_before_run_sec` is the wall clock the CALLER already spent before the
    run phase began — the integrated source preflight. The smoke budget is
    command-wide, so that time is subtracted here rather than silently forgiven.
    It is deliberately NOT reported in `config.bounds`: the configured budget is a
    stable fact about the run, and how much of it preflight happened to consume is
    not.
    """

    max_candidates_per_cell: int
    max_accepted_per_cell: int
    smoke_budget_sec: float
    elapsed_before_run_sec: float = 0.0

    def __post_init__(self):
        for name in ("max_candidates_per_cell", "max_accepted_per_cell"):
            value = getattr(self, name)
            # Booleans are ints in Python and a `True` cap is never intended.
            if isinstance(value, bool) or not isinstance(value, int):
                raise RunCellsError("%s must be an int, got %r" % (name, value))
            if value < 1:
                raise RunCellsError("%s must be >= 1, got %r" % (name, value))
        if self.max_accepted_per_cell > self.max_candidates_per_cell:
            raise RunCellsError(
                "max_accepted_per_cell (%d) may not exceed max_candidates_per_cell "
                "(%d): a cap that can never bind is not a bound."
                % (self.max_accepted_per_cell, self.max_candidates_per_cell))
        for name in ("smoke_budget_sec", "elapsed_before_run_sec"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RunCellsError("%s must be a number, got %r" % (name, value))
            if value != value or value in (float("inf"), float("-inf")):
                raise RunCellsError("%s must be finite, got %r" % (name, value))
        if self.smoke_budget_sec <= 0:
            raise RunCellsError("smoke_budget_sec must be > 0, got %r"
                                % (self.smoke_budget_sec,))
        if self.elapsed_before_run_sec < 0:
            raise RunCellsError("elapsed_before_run_sec must be >= 0, got %r"
                                % (self.elapsed_before_run_sec,))

    @property
    def remaining_run_sec(self):
        """What is left of the command-wide budget for the run phase."""
        return self.smoke_budget_sec - self.elapsed_before_run_sec


def _apply_candidate_cap(extraction, cap):
    """Keep the first `cap` candidates in the committed deterministic order.

    `ExtractionResult.candidates` is already sorted by `candidate_key`, which is
    content-derived, so the prefix is a function of what was discovered and never
    of when it arrived. Sliced BEFORE classification, so a candidate outside the
    cap genuinely receives no classification, no facets and no record — it is
    unprocessed, which is a different thing from rejected, and it appears in no
    rejection log.
    """
    if cap is None or len(extraction.candidates) <= cap:
        return extraction
    return dataclasses.replace(extraction,
                               candidates=tuple(extraction.candidates[:cap]))


def _accepted_prefix(candidates, verdicts, cap):
    """The prefix ending at the `cap`-th accepted candidate, or all of them.

    Deterministic and verdict-preserving: nothing is relabelled, no rejection
    reason is invented, and the retained rejected candidates keep the verdicts
    the committed gate gave them. `accepted + rejected == candidates` still holds
    over the retained set, because the retained set is a prefix and every member
    of it has a verdict.
    """
    if cap is None:
        return candidates
    seen = 0
    for index, candidate in enumerate(candidates):
        if verdicts[candidate.candidate_key].accepted:
            seen += 1
            if seen >= cap:
                return tuple(candidates[:index + 1])
    return candidates


def fixture_transport(lease_root, *, fixtures_dir=None):
    """The committed offline transport, reconstructed from a fixture directory.

    This is the only transport constructor in this module, and it cannot reach a
    network: `FixtureOpener` answers from disk. `fixtures_dir` is honoured here
    rather than captured in a module-level singleton, because `run(fixtures_dir=…)`
    is a committed contract and several suites compose their own corpora.
    """
    fixture_root = fixtures_dir or fixtures_mod.FIXTURE_ROOT
    opener = fixtures_mod.FixtureOpener(
        sources=fixtures_mod.load_source_fixtures(
            os.path.join(fixture_root, "sources")),
        robots=fixtures_mod.load_robots_fixtures(
            os.path.join(fixture_root, "robots")),
        # S6-5: the target corpus, so an accepted candidate's own page is
        # answerable. Without it every target fetch would fail as `unreachable` —
        # a true statement about a missing fixture, and a useless one about the
        # page. The opener keeps ONE URL index, so a target is indistinguishable
        # from a source to everything above it.
        targets=fixtures_mod.load_target_fixtures(
            os.path.join(fixture_root, "targets")))
    return Transport(opener=opener, sleep=_no_pacing, lease_root=lease_root)

# The artifact timestamp format the cell and topic schemas pin with a pattern.
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

STATUS_OK = "ok"
STATUS_ZERO = "zero_result"

# verify.decide can emit six reasons; the manifest's zero_result_reason enum
# admits five values, none of which is `off_topic` or a bare `insufficient
# evidence`. This is the mapping onto the committed vocabulary, and it is the
# only place a rejection reason is translated:
#
#   off_topic / below_relevance_threshold -> all_below_relevance_threshold
#       Both mean the candidate did not clear the relevance bar; `off_topic` is
#       the more specific statement that no required term matched at all.
#   below_quality_threshold               -> all_rejected_quality
#   insufficient_evidence                 -> all_rejected_quality
#       CF-7's gap, seen from the other side: `insufficient_evidence` carries the
#       composite and audience-fit failures because the rejection vocabulary has
#       no `below_composite_threshold`, and the zero-result vocabulary has no
#       nearer value than "we looked and they were not good enough". The precise
#       reason and number survive verbatim in the cell's rejection log.
#   developer_only_audience               -> category_exclusion_applied
#       The topic configuration states this outcome explicitly: "A cell that
#       returns zero because every candidate was a dev tool reports
#       category_exclusion_applied."
#   category_exclusion_applied            -> category_exclusion_applied
ZERO_RESULT_FOR_REJECTION = {
    "off_topic": "all_below_relevance_threshold",
    "below_relevance_threshold": "all_below_relevance_threshold",
    "below_quality_threshold": "all_rejected_quality",
    "insufficient_evidence": "all_rejected_quality",
    "developer_only_audience": "category_exclusion_applied",
    "category_exclusion_applied": "category_exclusion_applied",
}

# Ties in the dominant-reason vote break by this order, so the reported reason is
# a function of the rejections and never of the order candidates were scored in.
ZERO_RESULT_PRECEDENCE = ("no_items_in_window", "all_below_relevance_threshold",
                          "all_rejected_quality", "all_duplicates_of_existing",
                          "category_exclusion_applied")

# `error_reason` on a manifest cell row is a closed enum, and it is NARROWER than
# the adapter vocabulary: `http_4xx`, `index_fetch_failed`, `robots_denied_index`
# and the generic `adapter_error` have no manifest value. Those are passed through
# only when the enum admits them; otherwise the manifest row carries a null
# reason and the adapter's own reason value survives, uncensored, in the cell
# artifact's `metadata.sources[].reason`, which the schema leaves free-form.
MANIFEST_ERROR_REASONS = frozenset({
    "feed_parse_error", "unexpected_content_type", "empty_response",
    "schema_mapping_failed", "response_too_large", "index_parse_failed",
    "robots_denied", "http_timeout", "http_5xx", "dns_failure", "lease_timeout",
    "budget_exhausted", "circuit_open", "preflight_failed",
})


class RunCellsError(Exception):
    """A contract violation this driver refuses to paper over."""


# ------------------------------------------------------------------ clock
def _default_clock():
    """The run instant, honouring the same pin the rest of the pipeline honours.

    One instant is read once and used for every timestamp in the run — the run
    id, every `generated_at`, every `discovered_at`, the verify clock and the
    ledger's `now`. Reading the wall clock per artifact instead would make two
    artifacts from one run disagree about when the run happened.
    """
    pinned = os.environ.get("HARVEST_CLOCK_UTC")
    if pinned:
        try:
            return datetime.datetime.strptime(pinned, STAMP_FORMAT).replace(
                tzinfo=datetime.timezone.utc)
        except (TypeError, ValueError) as exc:
            raise RunCellsError("HARVEST_CLOCK_UTC=%r is not %s (%s)"
                                % (pinned, STAMP_FORMAT, exc)) from exc
    return datetime.datetime.now(datetime.timezone.utc)


# ------------------------------------------------------------ configuration
def configured_cells(topics_dir=None):
    """Every configured cell with the display names and sources it owns.

    `scheduler.configured_cells()` stays the authority on WHICH cells exist; this
    reads the same topic configs for the parts the scheduler does not carry (the
    display `topic`/`category` strings and the source list) and then checks the
    two agree. A disagreement means the two readers have drifted, which is worth
    a loud failure rather than a quietly shorter run.
    """
    directory = topics_dir or TOPICS_DIR
    cells = []
    for path in sorted(glob.glob(os.path.join(directory, "*.v1.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
        for category in doc.get("categories", []):
            cells.append({
                "cell_id": "%s__%s" % (doc["topic_slug"], category["category_slug"]),
                "topic": doc["topic"],
                "topic_slug": doc["topic_slug"],
                "category": category["category"],
                "category_slug": category["category_slug"],
                "sources": list(category.get("sources", [])),
            })
    cells.sort(key=lambda cell: cell["cell_id"])

    expected = {lane[len("cell__"):] if lane.startswith("cell__") else lane
                for lane in scheduler.configured_cells(directory)}
    got = {cell["cell_id"] for cell in cells}
    if expected != got:
        raise RunCellsError(
            "cell list disagrees with scheduler.configured_cells(): only here %s; "
            "only there %s" % (sorted(got - expected), sorted(expected - got)))
    return cells


def _run_policy():
    """The committed policy document, read and returned UNMODIFIED.

    No threshold, weight, exclusion, retry rule or crawl-delay is touched, so what
    verify applies and what the manifest records are the committed values. Pacing
    is not relaxed here either — it is handled where it belongs, by injecting a
    no-op `sleep` into the client (see `run`).
    """
    with open(POLICY_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _config_block(cells, max_cells, *, enrich, bounds=None):
    """The config facts this run used. `enrich` is REQUIRED, not defaulted.

    S6-5 brought this one field forward from S6-6, because S6-5 is what first makes
    the old hardcoded `False` untrue: a run that fetched four target pages and wrote
    observed evidence onto four records had enrichment enabled, and reporting
    otherwise would put a false statement in the manifest beside a
    `publication_eligible: true` derived from that very evidence.

    It is derived from whether the target-fetch phase was ENABLED for the run — the
    driver's own explicit decision, threaded from where it is made. Deliberately
    NOT from `publication_eligible`, nor from how many records happened to come
    back checked: a run that enabled enrichment and had every fetch fail still
    enriched, and must say so. Keyword-only and required so a caller cannot omit it
    and silently re-acquire the old dishonest default.
    """
    with open(PRECEDENCE_PATH, "r", encoding="utf-8") as handle:
        precedence = json.load(handle)
    with open(POLICY_PATH, "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    return {
        "topics": sorted({cell["topic_slug"] for cell in cells}),
        "policy_version": policy.get("config_version"),
        "precedence_version": precedence.get("config_version"),
        "canonicalization_version": request_key_mod.canonicalization_version(),
        "cross_topic_policy": precedence.get("cross_topic_policy"),
        "enrich": bool(enrich),
        # Every bound this run actually enforced, so a capped run is visible in the
        # manifest rather than only in the code. S6-6, extended by S9-3.
        #
        # The three smoke keys appear ONLY when bounds were supplied and therefore
        # enforced. Reporting them at their policy defaults on an unbounded run
        # would claim a cap that never bound anything — the same dishonesty
        # `config.enrich` was created to avoid. `elapsed_before_run_sec` is
        # deliberately absent: the configured budget is a stable fact, how much of
        # it preflight consumed is not.
        "bounds": ({"max_cells": max_cells,
                    "max_target_fetches_per_cell": MAX_TARGET_FETCHES_PER_CELL}
                   if bounds is None else
                   {"max_cells": max_cells,
                    "max_target_fetches_per_cell": MAX_TARGET_FETCHES_PER_CELL,
                    "max_candidates_per_cell": bounds.max_candidates_per_cell,
                    "max_accepted_per_cell": bounds.max_accepted_per_cell,
                    "smoke_budget_sec": bounds.smoke_budget_sec}),
    }


# ------------------------------------------------------------------- results
class CellRun:
    """One cell's raw outcome, before anything is routed or written."""

    __slots__ = ("cell", "sources", "extracted", "classifications", "verdicts",
                 "assignments", "failures", "fetch_outcomes", "adjudications")

    def __init__(self, cell):
        self.cell = cell
        self.sources = []          # metadata.sources[] rows, sorted by source_id
        self.extracted = ()        # tuple of ExtractedCandidate, by candidate_key
        self.classifications = {}  # candidate_key -> Classification
        self.verdicts = {}         # candidate_key -> Verdict
        self.assignments = {}      # candidate_key -> FacetAssignment
        self.failures = []         # (source_id, result, reason) for failed sources
        # S6-4. Keyed by the candidate's own key, but the OUTCOME behind a shared
        # target identity is one object reused by every owner — that identity is
        # fetched once per run, not once per owner.
        self.fetch_outcomes = {}   # candidate_key -> TargetFetchOutcome
        self.adjudications = {}    # candidate_key -> (canonical_url, aliases, conflicts)

    @property
    def cell_id(self):
        return self.cell["cell_id"]

    @property
    def accepted(self):
        return [c for c in self.extracted
                if self.verdicts[c.candidate_key].accepted]

    @property
    def rejected(self):
        return [c for c in self.extracted
                if not self.verdicts[c.candidate_key].accepted]


class RunResult:
    """What one run produced. Returned so a caller need not re-read the tree."""

    __slots__ = ("run_id", "root", "started_at", "finished_at", "cells", "records",
                 "manifest", "coverage", "paths", "ran", "swept")

    def __init__(self, **kw):
        for name in self.__slots__:
            setattr(self, name, kw.get(name))

    @property
    def record_count(self):
        return len(self.records or ())

    def status(self, cell_id):
        for row in self.cells or ():
            if row["cell_id"] == cell_id:
                return row["status"]
        return None


# --------------------------------------------------------------- one cell
def _discover(cell, source, *, cache, client, budget, clock):
    """One source, through the committed adapter. Never raises.

    `adapters.discover` already converts every HTTP, budget and cache failure into
    an AdapterResult. Anything else reaching here — a missing fixture, a broken
    parser — is this run's own problem, and it is recorded as that source's
    adapter error rather than allowed to take the run down with it.
    """
    try:
        return adapters.discover(source, cache=cache, client=client, budget=budget,
                                 lane_id="cell__" + cell["cell_id"], clock=clock)
    except BudgetExhausted as exc:
        return adapter_base.AdapterResult(
            source_id=source["source_id"], adapter=source.get("adapter", ""),
            result=adapter_base.RESULT_INFRASTRUCTURE_ERROR, reason=exc.reason,
            detail=str(exc))
    except Exception as exc:                                  # noqa: BLE001
        return adapter_base.AdapterResult(
            source_id=source["source_id"], adapter=source.get("adapter", ""),
            result=adapter_base.RESULT_ADAPTER_ERROR, reason="adapter_error",
            detail="%s: %s" % (type(exc).__name__, exc))


def _source_row(result, candidates_by_source, accepted_by_source):
    row = {
        "source_id": result.source_id,
        "adapter": result.adapter,
        "result": result.result,
        "reason": result.reason,
        "candidates": candidates_by_source.get(result.source_id, 0),
        "accepted": accepted_by_source.get(result.source_id, 0),
        "requests_made": int(result.requests_made or 0),
    }
    return row


def _budget_skipped_outcome(url, stamp):
    """The honest outcome for a target the budget stopped us from checking.

    Built through the committed S6-2 dataclass rather than a new type: a skipped
    target is `not_checked` — the absence of a check, never a failed one — and no
    client call is made for it at all.
    """
    return targetfetch_mod.TargetFetchOutcome(
        requested_url=url,
        access_status=targetfetch_mod.NOT_CHECKED,
        verification_status=targetfetch_mod.UNVERIFIED,
        verification_evidence="budget exhausted before this target was fetched; "
                              "no request was made",
        last_checked_at=stamp,
    )


def _fetch_targets(run, *, client, budget, pool, outcomes, clock, canon_policy):
    """Fetch each accepted candidate's own page — once per canonical identity.

    Three properties, and they are the whole of this checkpoint:

      * ONLY ACCEPTED CANDIDATES. A rejected candidate was rejected on metadata by
        the committed gate; fetching it would be work whose result can change
        nothing, and re-deciding afterwards is the re-judging Stage 6 forbids.
      * ONCE PER CANONICAL IDENTITY, ACROSS THE WHOLE RUN. Ownership is the
        committed `pool.acquire_target_fetch` gate over `pool.add_candidate`'s
        canonical key, and `pool` is run-scoped — so the same URL accepted in two
        cells, or under two topics, is ONE fetch whose outcome reaches every owner.
        `acquire_target_fetch` returning False is the normal second-sighting path,
        not an error.
      * BOUNDED, AND IT STOPS. Nested inside the caller's committed `cell:` budget
        scope, plus MAX_TARGET_FETCHES_PER_CELL. Once the budget is exhausted no
        further client call is attempted: the remaining targets are recorded as
        `not_checked`, which is true, rather than each one re-charging a spent
        budget to discover the same thing.

    Sequential by construction — one candidate at a time, in the committed sort
    order — so `acquire_target_fetch`'s unlocked check-then-set keeps exactly one
    caller and CF-1 stays untriggered. There is no thread, process or lock here.
    """
    stamp = clock() if callable(clock) else clock
    lane_id = "cell__" + run.cell_id
    exhausted = False
    fetched_here = 0

    # The committed order, so which identity wins the fetch is a function of
    # content rather than of iteration accident.
    for candidate in sorted(run.accepted, key=lambda c: c.candidate_key):
        target_url = candidate.target_url or candidate.identity_url
        cand, _is_new = pool.add_candidate(target_url, lane_id)
        key = cand["candidate_key"]

        if pool.acquire_target_fetch(key, lane_id):
            if exhausted or fetched_here >= MAX_TARGET_FETCHES_PER_CELL:
                outcomes[key] = _budget_skipped_outcome(target_url, stamp)
            else:
                outcome = targetfetch_mod.fetch_target(
                    target_url, client=client, budget=budget, clock=clock)
                fetched_here += 1
                # A budget stop is terminal for this cell's fetch phase: the next
                # call would charge a spent budget and learn nothing new.
                if outcome.access_status == targetfetch_mod.NOT_CHECKED:
                    exhausted = True
                outcomes[key] = outcome
        # else: another owner already fetched this identity; reuse its outcome.

        outcome = outcomes[key]
        run.fetch_outcomes[candidate.candidate_key] = outcome

        # Per owner, because identity_url and canonical_url are the owner's own.
        # `canonical_robots_allowed` is left UNKNOWN on purpose: S6-4 must not
        # robots-probe a discovered canonical URL, and aliases.adjudicate treats
        # unknown as "decline to alias" — the conservative direction. Wiring a
        # real robots verdict is a later, separately authorized step.
        run.adjudications[candidate.candidate_key] = aliases_mod.adjudicate(
            candidate.identity_url, candidate.canonical_url, outcome, canon_policy,
            canonical_robots_allowed=None, observed_at=stamp)
    return run


def _run_one_cell(cell, *, cache, client, budget, policy, clock, pool=None,
                  outcomes=None, canon_policy=None, bounds=None):
    """Discover, dedupe, extract, classify, verify, assign — all committed calls.

    `pool`, `outcomes` and `canon_policy` enable the S6-4 target-fetch phase. They
    default to None so every existing caller — and every Stage 5 test — keeps the
    metadata-only behaviour it was written against: without a pool there is no
    ownership gate to acquire, so no target is fetched.

    `bounds` (S9-3) caps what this cell PROCESSES; it never caps what it asks the
    configured sources for. Discovery and the committed request budgets are
    untouched, so a bounded smoke still exercises every source exactly as a full
    run would — the bound limits judgement, not traffic.
    """
    run = CellRun(cell)
    source_map = {source["source_id"]: source for source in cell["sources"]}

    results = []
    fetch_phase = pool is not None and outcomes is not None
    # ONE committed `cell:` scope around everything this cell does, so the target
    # fetches are charged against the same cell_max_requests / cell_budget_sec as
    # discovery was. The in-memory stages between them issue no request; they sit
    # inside the scope only so the fetch phase can share it rather than opening a
    # second scope of the same name, which would hand the cell a fresh budget.
    with budget.scope("cell:" + cell["cell_id"],
                      policy["budgets"].get("cell_max_requests"),
                      policy["budgets"].get("cell_budget_sec")):
        for source in cell["sources"]:
            with budget.scope("adapter:" + source["source_id"],
                              source.get("max_requests"),
                              policy["budgets"].get("adapter_budget_sec")):
                results.append(_discover(cell, source, cache=cache, client=client,
                                         budget=budget, clock=clock))

        for result in results:
            if result.failed:
                run.failures.append((result.source_id, result.result, result.reason))

        # Only sources that actually produced items reach dedupe; a zero-result or
        # a failed source carries no candidates and is recorded, not grouped.
        deliveries = [dedupe_mod.delivery("cell__" + cell["cell_id"], result)
                      for result in results]
        grouped = dedupe_mod.group(deliveries, sources=source_map)
        extraction = extract_mod.normalize_all(grouped)

        # S9-3, first cap. Sliced HERE — before any judgement — so a candidate
        # outside the cap is genuinely unprocessed: no classification, no facets,
        # no record, and no rejection row claiming it was considered and refused.
        if bounds is not None:
            extraction = _apply_candidate_cap(extraction,
                                              bounds.max_candidates_per_cell)

        classifications = classify_mod.classify_all(extraction)
        verdicts = verify_mod.verify_all(extraction, classifications, clock=clock)

        # S9-3, second cap. The boundary cannot be known without verdicts — that
        # is what "the Nth ACCEPTED candidate" means — so the committed batch gate
        # runs over the candidate-capped set and the prefix is taken from its
        # results. Nothing past the boundary produces a facet, a record, a
        # rejection row or a count; no verdict is changed and no reason invented.
        if bounds is not None:
            by_key = {v.candidate_key: v for v in verdicts}
            kept = _accepted_prefix(extraction.candidates, by_key,
                                    bounds.max_accepted_per_cell)
            if len(kept) != len(extraction.candidates):
                keys = {candidate.candidate_key for candidate in kept}
                extraction = dataclasses.replace(extraction, candidates=kept)
                classifications = [c for c in classifications
                                   if c.candidate_key in keys]
                verdicts = [v for v in verdicts if v.candidate_key in keys]

        assignments = facetassign_mod.assign_all(extraction, classifications)

        run.extracted = extraction.candidates
        run.classifications = {c.candidate_key: c for c in classifications}
        run.verdicts = {v.candidate_key: v for v in verdicts}
        run.assignments = {a.candidate_key: a for a in assignments}

        # S6-4: accepted candidates only, after every committed decision is made.
        if fetch_phase:
            _fetch_targets(run, client=client, budget=budget, pool=pool,
                           outcomes=outcomes, clock=clock,
                           canon_policy=canon_policy
                           if canon_policy is not None
                           else aliases_mod.load_canonicalization())

    candidates_by_source, accepted_by_source = {}, {}
    for candidate in run.extracted:
        accepted = run.verdicts[candidate.candidate_key].accepted
        for source_id in candidate.source_ids:
            candidates_by_source[source_id] = candidates_by_source.get(source_id, 0) + 1
            if accepted:
                accepted_by_source[source_id] = accepted_by_source.get(source_id, 0) + 1

    run.sources = sorted(
        (_source_row(r, candidates_by_source, accepted_by_source) for r in results),
        key=lambda row: row["source_id"])
    return run


# --------------------------------------------------------------- outcomes
def _zero_result_reason(run):
    """The dominant rejection reason, translated to the committed vocabulary.

    Dominant by count, ties broken by `ZERO_RESULT_PRECEDENCE`, so the reported
    reason is a function of the rejections themselves and never of the order they
    were produced in.
    """
    if not run.extracted:
        return "no_items_in_window"
    tally = {}
    for candidate in run.rejected:
        reason = run.verdicts[candidate.candidate_key].rejection_reason
        mapped = ZERO_RESULT_FOR_REJECTION.get(reason)
        if mapped is None:
            raise RunCellsError(
                "verify emitted rejection reason %r, which has no committed "
                "zero_result_reason. Add it to ZERO_RESULT_FOR_REJECTION "
                "deliberately rather than letting a cell report the wrong reason."
                % (reason,))
        tally[mapped] = tally.get(mapped, 0) + 1
    if not tally:
        return "no_items_in_window"
    return min(tally, key=lambda value: (-tally[value],
                                         ZERO_RESULT_PRECEDENCE.index(value)))


def _cell_row(run, artifact_records):
    """One manifest `cells[]` row. Counts describe what the cell PROCESSED.

    `candidates`/`accepted`/`rejected` are about the candidates this cell
    discovered; the artifact holds what the classifier assigned to this cell.
    Those are usually the same set and are deliberately not forced to be: a cell
    finding an item that belongs to another category is a real outcome, and
    conflating discovery with ownership would hide it.
    """
    accepted = run.accepted
    row = {
        "cell_id": run.cell_id,
        "candidates": len(run.extracted),
        "accepted": len(accepted),
        "rejected": len(run.rejected),
        "requests_made": sum(int(s["requests_made"]) for s in run.sources),
        "adapters_used": sorted({s["adapter"] for s in run.sources if s["adapter"]}),
    }

    if accepted or artifact_records:
        row["status"] = STATUS_OK
        return row

    if run.extracted:
        row["status"] = STATUS_ZERO
        row["zero_result_reason"] = _zero_result_reason(run)
        return row

    if run.failures:
        # Infrastructure outranks adapter: if the network never delivered a body,
        # that is the more truthful account of why the cell is empty.
        classes = {result for _, result, _ in run.failures}
        row["status"] = (adapter_base.RESULT_INFRASTRUCTURE_ERROR
                         if adapter_base.RESULT_INFRASTRUCTURE_ERROR in classes
                         else adapter_base.RESULT_ADAPTER_ERROR)
        reasons = sorted({reason for _, _, reason in run.failures if reason})
        admitted = [r for r in reasons if r in MANIFEST_ERROR_REASONS]
        row["error_reason"] = admitted[0] if admitted else None
        return row

    row["status"] = STATUS_ZERO
    row["zero_result_reason"] = "no_items_in_window"
    return row


# ---------------------------------------------------------------- records
def _full_record(candidate, classification, verdict, assignment, *,
                 source_map, harvest_run_id, discovered_at, outcome=None,
                 adjudication=None):
    """The S4-5B construction, called as committed. Nothing is re-derived here.

    S6-5: when a target page was fetched, the observed evidence REPLACES the
    verdict's honest no-enrichment defaults. `verify.Verdict` carries
    `access_status: "not_checked"` and friends because Stage 4 could not fetch
    anything; once a fetch has happened those defaults are stale, and the outcome
    is the only thing that actually saw the page.

    Nothing else moves. Every score, the classification, the facet payload,
    `record_id`, `content_id` and `identity_url` are exactly what they were without
    a fetch — a fetch supplies facts and re-judges nothing. `canonical_url` and
    `url_aliases` come from the S6-3 adjudication, which is evidence-gated.
    """
    topic = classification.topic_slug
    category = classification.category_slug
    source_id = candidate.source_ids[0] if candidate.source_ids else None
    if not source_id:
        raise RunCellsError("candidate %r has no source_id" % candidate.candidate_key)
    source = source_map.get(source_id)
    if source is None:
        raise RunCellsError("candidate %r names unconfigured source %r"
                            % (candidate.candidate_key, source_id))

    payload = assignment.case_facets if assignment.applicable else None

    # Observed evidence when a fetch happened; the committed Stage 4 defaults when
    # it did not. Read from the outcome rather than recomputed — this module has no
    # opinion about what a fetch saw.
    canonical_url = candidate.canonical_url
    url_aliases = None
    if adjudication is not None:
        canonical_url, url_aliases, _conflicts = adjudication
    if outcome is not None:
        access_status = outcome.access_status
        http_status = outcome.http_status
        verification_status = outcome.verification_status
        verification_evidence = outcome.verification_evidence
        content_hash = outcome.content_hash
        last_checked_at = outcome.last_checked_at
    else:
        access_status = verdict.access_status
        http_status = verdict.http_status
        verification_status = verdict.verification_status
        verification_evidence = verdict.verification_evidence
        content_hash = verdict.content_hash
        last_checked_at = None

    return records_mod.make_full_record(
        record_id=urlkey.record_id(topic, candidate.identity_url),
        content_id=candidate.content_id,
        topic_slug=topic, category_slug=category,
        cell_id="%s__%s" % (topic, category),
        identity_url=candidate.identity_url,
        target_url=candidate.target_url,
        canonical_url=canonical_url,
        harvest_run_id=harvest_run_id,
        source_id=source_id, source_adapter=source.get("adapter", ""),
        title=candidate.title, summary=candidate.summary,
        publisher=candidate.publisher, author=candidate.author,
        published_at=candidate.published_at, language=candidate.language,
        content_type=candidate.content_type,
        discovered_at=discovered_at,
        access_status=access_status,
        http_status=http_status,
        verification_status=verification_status,
        verification_evidence=verification_evidence,
        last_checked_at=last_checked_at,
        url_aliases=url_aliases,
        relevance_score=verdict.scores.relevance,
        quality_score=verdict.scores.quality,
        audience_fit_score=verdict.scores.audience_fit,
        freshness_score=verdict.scores.freshness,
        content_hash=content_hash,
        classification={
            "rule_id": classification.rule_id,
            "rationale": classification.rationale,
            # D2 has one home: artifacts.project_classification_evidence.
            "evidence": artifacts.project_classification_evidence(
                classification.evidence),
            "competing_categories": [c.payload()
                                     for c in classification.competing_categories],
        },
        raw=candidate.provenance_raw,
        case_facets=payload)


def _cross_reference_rows(candidate, classification, *, harvest_run_id,
                          discovered_at, configured):
    """The committed cross-topic policy, applied — not invented.

    `precedence.v1.json` states it: "Owning topic (highest precedence rank) emits
    a full record; every other qualifying topic emits a cross_reference row
    pointing at it." The owner and the other qualifying cells are both already
    chosen by `classify.classify` — this reads them and calls the committed
    builder.

    Within one topic nothing is emitted: duplicate suppression inside a topic is
    mandatory and not configurable, so a pointer beside its own full record would
    be exactly the duplicate the rule forbids.
    """
    owner_topic = classification.topic_slug
    owner_record_id = urlkey.record_id(owner_topic, candidate.identity_url)

    rows, seen = [], set()
    for competing in classification.competing_categories:
        if competing.topic == owner_topic:
            continue
        cell_id = "%s__%s" % (competing.topic, competing.category)
        if cell_id in seen:
            continue
        seen.add(cell_id)
        if cell_id not in configured:
            raise RunCellsError(
                "classification of %s names competing cell %r, which is not "
                "configured; a pointer has nowhere to live"
                % (candidate.identity_url, cell_id))
        rows.append((cell_id, records_mod.make_cross_reference(
            record_id=urlkey.record_id(competing.topic, candidate.identity_url),
            content_id=candidate.content_id,
            identity_url=candidate.identity_url,
            topic_slug=competing.topic, category_slug=competing.category,
            duplicate_of=owner_record_id,
            owner_topic=owner_topic,
            reason="owned by %s__%s" % (owner_topic,
                                        classification.category_slug),
            harvest_run_id=harvest_run_id,
            discovered_at=discovered_at,
            cell_id=cell_id)))
    rows.sort(key=lambda pair: pair[0])
    return rows


def _dedupe_records(rows):
    """At most one record per record_id, chosen by CONTENT.

    Two cells can discover the same URL. `records.sort_key` is
    (topic, primary_category, record_id), which is identical for two records of
    the same identity and therefore cannot break the tie on its own — so the tie
    breaks on the serialized bytes. The survivor is then a function of what the
    records say, never of which cell happened to run first.
    """
    ordered = sorted(rows, key=lambda rec: (records_mod.sort_key(rec),
                                            artifacts.serialize(rec)))
    out, seen = [], set()
    for record in ordered:
        record_id = record.get("record_id")
        if record_id in seen:
            continue
        seen.add(record_id)
        out.append(record)
    return out


# -------------------------------------------------------------------- run
def run(root, *, cells=None, clock=None, fixtures_dir=None, max_cells=MAX_CELLS,
        transport=None, mode=None, enrich=None, source_preflight=None,
        bounds=None, run_id_value=None):
    """Run the configured cells sequentially and emit one run's artifacts.

    `root` is the artifact root — every byte this writes lands under it. `cells`
    selects a subset by `cell_id`; the rest are still reported, as `not_run`.
    `clock` returns a timezone-aware UTC datetime and is read ONCE. `fixtures_dir`
    points at a `tests/fixtures/harvest`-shaped directory.

    Order matters at the end: the manifest is written and only then does
    `LATEST_RUN_ID` advance, so the pointer can never name an incomplete run.

    Re-run semantics (S5-7): a `run_id` that already has a manifest in this root
    is refused **before the first byte is written**, and every write of the run is
    journalled so an interruption sweeps its own temp files and nothing else.

    S9-1 seams, every one omission-compatible — omit them all and this function
    behaves byte-for-byte as it did at `720f114c`:

      * `transport` — one frozen `Transport`. `None` builds the committed fixture
        transport over `fixtures_dir` and a temporary lease root that this call
        creates and, on the way out, removes. A SUPPLIED transport is used
        verbatim: its lease root is neither replaced nor deleted, because it is
        the caller's.
      * `mode` — `None` means the committed `artifacts.MODE_HARVEST`. The value is
        reported; no eligibility predicate is added, and none is needed —
        `derive_publication_eligibility` already refuses every non-`harvest` mode.
      * `enrich` — `None` means the committed `True`. Bound ONCE below and used
        for both the target-fetch phase and `config.enrich`, so the reported fact
        and the behaviour cannot disagree.
      * `source_preflight` — `None` means the committed empty array. Rows are
        passed through to the manifest builder; nothing is probed and no row is
        assembled here. That is S9-2's, and it does not exist yet.

    S9-3 seams, also omission-compatible:

      * `bounds` — one frozen `RunBounds`. `None` means unbounded, byte-for-byte
        as before. Supplied, it caps candidates and accepted records PER CELL and
        gives the run phase a wall-clock scope; every cap it enforces is echoed
        into `config.bounds`, so a bounded run cannot be mistaken for a full one.
        It never caps discovery: the committed request budgets still decide how
        much traffic a cell may generate.
      * `run_id_value` — `None` keeps the committed clock-derived id. Supplied, it
        is validated against the COMMITTED manifest schema pattern and refused
        before a single byte is written, so an id the manifest would reject can
        never reach an artifact.
    """
    now = (clock() if clock is not None else _default_clock())
    stamp = now.strftime(STAMP_FORMAT)
    harvest_run_id = (artifacts.run_id(clock=lambda: now) if run_id_value is None
                      else validate_run_id_value(run_id_value))

    # Refused HERE, not at publication. A finished run's artifacts are immutable;
    # discovering the clash after the cells had run would mean the cross-run
    # ledger had already counted every candidate twice and the rejection logs had
    # already been replaced — for a run that was never going to be published.
    if artifacts.run_is_finished(root, harvest_run_id):
        raise RunCellsError(
            "run %s already finished in this root: %s exists. Refusing to re-run "
            "a finished run_id — its artifacts are immutable and the cross-run "
            "ledger would count every candidate a second time. Run again with a "
            "fresh run_id."
            % (harvest_run_id, artifacts.run_manifest_path(root, harvest_run_id)))

    def verify_clock():
        return stamp

    # The three reported facts, each bound ONCE, here, before anything can read
    # them. `enrich` in particular drives both the target-fetch phase and
    # `config.enrich`; binding it in one place is what keeps the manifest's claim
    # and the run's behaviour from drifting apart (S6-5).
    run_mode = artifacts.MODE_HARVEST if mode is None else mode
    enrich = True if enrich is None else bool(enrich)
    preflight_rows = () if source_preflight is None else tuple(source_preflight)

    configured = configured_cells()
    by_id = {cell["cell_id"]: cell for cell in configured}
    source_map = {source["source_id"]: source
                  for cell in configured for source in cell["sources"]}

    if cells is None:
        selected = list(configured)
    else:
        selected = []
        for cell_id in cells:
            if cell_id not in by_id:
                raise RunCellsError("cell %r is not one of the %d configured cells"
                                    % (cell_id, len(configured)))
            selected.append(by_id[cell_id])
        selected.sort(key=lambda cell: cell["cell_id"])

    if max_cells is not None and len(selected) > int(max_cells):
        # Bounded, and visibly so: the cells past the cap keep their `not_run`
        # row in the manifest, so a capped run cannot be mistaken for a full one.
        selected = selected[:int(max_cells)]

    policy = _run_policy()

    # The lease tree is HttpClient's coordination scratch, not an artifact. When
    # this call builds its own transport the tree lives in its own temp directory,
    # so `root` holds exactly the committed layout and nothing else — §2.1 names
    # no `locks/` for Stage 5. A SUPPLIED transport brings its own lease root, and
    # that one belongs to the caller: it is used as given and never swept here.
    owned_lease_root = None
    if transport is None:
        owned_lease_root = tempfile.mkdtemp(prefix="harvest_leases_")
        transport = fixture_transport(owned_lease_root, fixtures_dir=fixtures_dir)
    try:
        client = httpclient_mod.HttpClient(
            policy, lease_root=transport.lease_root, opener=transport.opener,
            # Under the fixture transport this is `_no_pacing`: a fixture is a
            # local file, pacing exists to protect a remote host, and there is
            # none; the crawl-delay is still READ and honoured by every other code
            # path, it simply has nothing to wait for. A live transport supplies a
            # real sleep, which is why the two travel together.
            sleep=transport.sleep)
        pool = pool_mod.CandidatePool(harvest_run_id)
        cache = sourcecache_mod.SourceFetchCache(pool, clock=lambda: stamp)
        budget = RequestBudget()

        # ---------------------------------------------------- sequential drive
        runs = []
        # RUN-scoped, not cell-scoped: this is what makes one canonical target
        # identity a single fetch across every cell and every topic in the run.
        # The pool already owns the ownership gate; this map holds the one outcome
        # each owned identity produced, so a second owner reuses it rather than
        # re-fetching the same page.
        target_outcomes = {}
        canon_policy = aliases_mod.load_canonicalization()
        # S9-3. The command-wide smoke budget, as a committed `run` time scope
        # over the whole cell phase — not a new timeout implementation. It is
        # checked BEFORE and AFTER each cell, so an expiry is discovered at a cell
        # boundary and raises out of this block before the artifact-writing phase
        # is reached: a run that ran out of time publishes no manifest and does
        # not move the pointer. `remaining_run_sec` is what the caller's preflight
        # left of it.
        run_scope = (budget.scope("run", None, bounds.remaining_run_sec)
                     if bounds is not None else contextlib.nullcontext())
        with run_scope:
            for cell in selected:                   # one cell at a time. See §9.1.
                if bounds is not None:
                    budget.check_time()
                runs.append(_run_one_cell(cell, cache=cache, client=client,
                                          budget=budget, policy=policy,
                                          clock=verify_clock,
                                          pool=pool if enrich else None,
                                          outcomes=(target_outcomes if enrich
                                                    else None),
                                          canon_policy=canon_policy,
                                          bounds=bounds))
                if bounds is not None:
                    budget.check_time()
    finally:
        # Only what this call created. A caller-supplied lease root is the
        # caller's to keep — a live run's leases outlive the command that made
        # them, and deleting another owner's coordination tree is exactly the
        # mistake the S5-7 sweeper exists to refuse.
        if owned_lease_root is not None:
            shutil.rmtree(owned_lease_root, ignore_errors=True)

    ran = {run_.cell_id for run_ in runs}

    # ------------------------------------------------------------- routing
    by_cell = {cell_id: [] for cell_id in ran}
    all_records = []
    decisions = []
    for run_ in runs:
        for candidate in run_.accepted:
            key = candidate.candidate_key
            classification = run_.classifications[key]
            record = _full_record(
                candidate, classification, run_.verdicts[key],
                run_.assignments[key], source_map=source_map,
                harvest_run_id=harvest_run_id, discovered_at=stamp,
                # Both absent for a run that fetched nothing, which is how the
                # committed Stage 4 defaults keep applying unchanged.
                outcome=run_.fetch_outcomes.get(key),
                adjudication=run_.adjudications.get(key))
            owner_cell = record["cell_id"]
            if owner_cell not in by_cell:
                raise RunCellsError(
                    "%s was classified into cell %r, which did not run in this "
                    "run; refusing to drop an accepted record"
                    % (candidate.identity_url, owner_cell))
            by_cell[owner_cell].append(record)
            all_records.append(record)

            pointers = _cross_reference_rows(
                candidate, classification, harvest_run_id=harvest_run_id,
                discovered_at=stamp, configured=set(by_id))
            for cell_id, row in pointers:
                if cell_id not in by_cell:
                    raise RunCellsError(
                        "%s needs a cross_reference in cell %r, which did not run "
                        "in this run" % (candidate.identity_url, cell_id))
                by_cell[cell_id].append(row)
                all_records.append(row)
            if pointers:
                topics = sorted({classification.topic_slug} |
                                {cid.split("__")[0] for cid, _ in pointers})
                decisions.append({
                    "content_id": candidate.content_id,
                    "topics": topics,
                    "owner_topic": classification.topic_slug,
                    "policy_applied": "cross_reference",
                    "reason": "%s assigned %s__%s; every other qualifying topic "
                              "points at it"
                              % (classification.rule_id,
                                 classification.topic_slug,
                                 classification.category_slug),
                })

    # Run-level, deduplicated by content: two owners sharing one identity produce
    # the same conflict, and it is one finding rather than two. S6-6 routes what
    # S6-3 already adjudicated; it re-adjudicates nothing and requests nothing.
    conflict_rows, seen_conflicts = [], set()
    for run_ in runs:
        for key in sorted(run_.adjudications):
            _canonical, _aliases, conflicts = run_.adjudications[key]
            for conflict in conflicts:
                payload = conflict.payload()
                fingerprint = (payload["reason"], payload["identity_url"],
                               payload["proposed_alias"])
                if fingerprint in seen_conflicts:
                    continue
                seen_conflicts.add(fingerprint)
                conflict_rows.append(conflict)

    for cell_id in by_cell:
        by_cell[cell_id] = _dedupe_records(by_cell[cell_id])
    all_records = _dedupe_records(all_records)

    # S6-6B. The finished FULL records, by `record_id`, so the ledger can record
    # the target evidence its committed schema has always had room for.
    #
    # Keyed by `record_id` because that is the join the ledger observation already
    # computes for an accepted candidate — no second identity is introduced. Only
    # full records enter: a `cross_reference` is a pointer at a record in another
    # cell, it was never a page anyone fetched, and it carries no evidence to copy.
    full_records_by_id = {record["record_id"]: record for record in all_records
                          if record.get("record_type") == "full"}

    # Every write from here to the pointer is journalled, so an interruption
    # sweeps exactly the temp files THIS run created and provably nothing
    # else. Sequential by contract: the journal refuses to nest.
    with artifacts.write_journal(owner=harvest_run_id) as journal:
        # ------------------------------------------------------------- artifacts
        paths = []
        cell_artifacts = {}
        for run_ in runs:
            cell = run_.cell
            artifact = artifacts.build_cell_artifact(
                by_cell[run_.cell_id],
                topic=cell["topic"], topic_slug=cell["topic_slug"],
                category=cell["category"], category_slug=cell["category_slug"],
                cell_id=run_.cell_id, harvest_run_id=harvest_run_id,
                generated_at=stamp,
                metadata={"sources": run_.sources, "rejected": len(run_.rejected)})
            cell_artifacts[run_.cell_id] = artifact
            paths.append(artifacts.write_cell_artifact(
                artifacts.cell_artifact_path(root, harvest_run_id, run_.cell_id),
                artifact))

        for topic_slug in sorted({run_.cell["topic_slug"] for run_ in runs}):
            members = [run_ for run_ in runs if run_.cell["topic_slug"] == topic_slug]
            artifact = artifacts.build_topic_artifact(
                [cell_artifacts[m.cell_id] for m in sorted(members,
                                                           key=lambda m: m.cell_id)],
                topic=members[0].cell["topic"], topic_slug=topic_slug,
                harvest_run_id=harvest_run_id, generated_at=stamp)
            paths.append(artifacts.write_topic_artifact(
                artifacts.topic_artifact_path(root, harvest_run_id, topic_slug),
                artifact))

        # ------------------------------------------------- rejections and ledger
        for run_ in runs:
            pairs = [(candidate, run_.verdicts[candidate.candidate_key])
                     for candidate in run_.rejected]
            paths.append(ledger_mod.write_rejection_log(
                root, run_.cell_id,
                ledger_mod.build_rejection_log(pairs, cell_id=run_.cell_id,
                                               harvest_run_id=harvest_run_id,
                                               generated_at=stamp)))

            observations = []
            for candidate in run_.extracted:
                verdict = run_.verdicts[candidate.candidate_key]
                classification = run_.classifications[candidate.candidate_key]
                observation = {
                    "identity_url": candidate.identity_url,
                    "content_id": candidate.content_id,
                    "source_id": (candidate.source_ids[0]
                                  if candidate.source_ids else None),
                    "outcome": "accepted" if verdict.accepted else "rejected",
                }
                if verdict.accepted:
                    record_id = urlkey.record_id(
                        classification.topic_slug, candidate.identity_url)
                    observation["record_id"] = record_id
                    # S6-6B: the target evidence the ledger has always been able to
                    # hold. Plan §7.4 described this flow from the start; the
                    # observation simply never carried the three values, so a
                    # re-run had to re-derive from the artifacts what the ledger
                    # exists to remember.
                    #
                    # COPIED FROM THE FINISHED RECORD, never recomputed from the
                    # outcome: `_full_record` is what actually decided whether a
                    # fetch's observation or Stage 4's honest defaults apply, and a
                    # second derivation here could disagree with the record beside
                    # it. No clock is read — `last_checked_at` is the record's, and
                    # inventing a fresh instant would claim a check that never
                    # happened at that moment.
                    #
                    # A FIELD IS WRITTEN ONLY WHEN THE RECORD HAS ONE. A run that
                    # fetched nothing leaves all three null, a budget-skipped
                    # target has no status and no hash, and a null written here
                    # would be a claim rather than the absence of one. `merge_ledger`
                    # already treats a null as "no news" and would keep an earlier
                    # run's value; writing one anyway would make that path depend on
                    # a distinction the caller never meant to draw.
                    record = full_records_by_id.get(record_id)
                    if record is not None:
                        for field in LEDGER_TARGET_EVIDENCE_FIELDS:
                            value = record.get(field)
                            if value is not None:
                                observation[field] = value
                else:
                    observation["rejection_reason"] = verdict.rejection_reason
                observations.append(observation)
            observations.sort(key=lambda o: o["identity_url"])

            paths.append(ledger_mod.write_ledger(
                root, run_.cell_id,
                ledger_mod.merge_ledger(ledger_mod.load_ledger(root, run_.cell_id),
                                        observations, now=stamp,
                                        cell_id=run_.cell_id)))

        # -------------------------------------------------------------- coverage
        thresholds = artifacts.policy_thresholds()
        coverage = artifacts.build_coverage_report(
            all_records, harvest_run_id=harvest_run_id, generated_at=stamp,
            # One round, and the thresholds it applied were read once from the
            # committed policy. Proved rather than asserted: the manifest's reading
            # and the scheduler's independent reading of the same file must agree.
            thresholds_constant=(thresholds == scheduler.load_thresholds()))
        paths.append(artifacts.write_coverage_report(
            artifacts.coverage_report_path(root, harvest_run_id), coverage))

        # Written BEFORE the manifest, because the manifest reports the count read
        # back from this validated document rather than a number carried beside it.
        alias_conflicts = artifacts.build_alias_conflicts(
            conflict_rows, harvest_run_id=harvest_run_id, generated_at=stamp)
        paths.append(artifacts.write_alias_conflicts(
            artifacts.alias_conflicts_path(root, harvest_run_id), alias_conflicts))

        # -------------------------------------------------------------- manifest
        rows = [_cell_row(run_, by_cell[run_.cell_id]) for run_ in runs]
        accounting = pool.accounting()
        manifest = artifacts.build_run_manifest(
            harvest_run_id=harvest_run_id, started_at=stamp, finished_at=stamp,
            cells=rows, mode=run_mode,
            config=_config_block(configured, max_cells, enrich=enrich,
                                 bounds=bounds),
            # A preflight is a bounded re-check of live sources at the start of a
            # live run. Omitted — the fixture default — the honest value stays
            # "none performed". Rows only ever arrive from a caller that actually
            # probed; this driver assembles none and probes nothing.
            source_preflight=preflight_rows,
            classification_decisions=decisions,
            request_accounting=accounting,
            target_fetch_owners=accounting.get("target_fetch_owners", 0),
            # S6-6A. The RUN-scoped map, not per-cell outcomes and not per-record:
            # it holds one outcome per owned canonical identity, so an identity
            # accepted in two cells or under two topics contributes its attempts
            # once. Passed as facts; `build_run_manifest` derives the counters, so
            # no target number is ever caller-asserted. Sorted for a deterministic
            # summation order — the total is order-independent, but the argument
            # should not depend on dict insertion order either.
            # S9-1: omission and zero stay different answers. With enrichment
            # DISABLED the target lane never ran, so the honest report is the
            # committed `None` sentinel and the three `target_*` keys are ABSENT.
            # Passing an empty list would say "the lane ran and found nothing",
            # which is a claim this run has not earned.
            target_outcomes=([target_outcomes[key]
                              for key in sorted(target_outcomes)]
                             if enrich else None),
            # Passed so eligibility is derived from what the records actually say,
            # not from the owner count alone: acquiring one target-fetch owner must
            # not make a run publishable while its records still say not_checked.
            records=all_records,
            # The artifact is the single source of truth about how many conflicts
            # this run found; the manifest reads it back rather than restating it.
            alias_conflicts=alias_conflicts)

        # Manifest first, pointer second — S5-5's one promise.
        paths.append(artifacts.publish_run(root, harvest_run_id, manifest))

    # The journal has swept on the way out of the block above; on a clean run
    # there is nothing to sweep, and saying so is worth more than assuming it.
    return RunResult(run_id=harvest_run_id, root=root, started_at=stamp,
                     finished_at=stamp, cells=manifest["cells"],
                     records=all_records, manifest=manifest, coverage=coverage,
                     paths=paths, ran=sorted(ran), swept=tuple(journal.swept))
