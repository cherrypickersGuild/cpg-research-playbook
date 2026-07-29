#!/usr/bin/env python3
"""base.py — the adapter contract: one configured source -> bounded candidates.

An adapter turns ONE configured source into a bounded, deterministic list of
`RawCandidate` values. It is not a record builder, a classifier or a scorer:
`records.make_full_record` is never called from here, no facet is ever written,
and a lane_id never becomes evidence. Those belong to Stage 4.

Three boundaries this layer exists to hold:

  * FETCHING IS NOT OURS. Every source body comes through SourceFetchCache, so
    three lanes sharing a feed produce ONE logical fetch, a failed fetch is not
    retried by the next lane in the run, and no adapter ever pairs
    pool.acquire_source() with pool.establish_snapshot() itself. Accounting is
    copied from the cache result, never reconstructed from client.stats.
  * A ZERO RESULT IS NOT AN ERROR. A well-formed feed with no entries is
    `zero_result: no_items_in_window`. Conflating the two would make an
    uneventful week look like an outage.
  * THE ADAPTER DOES NOT KNOW WHERE BYTES CAME FROM. Fixture and live runs go
    through the identical Adapter -> SourceFetchCache -> HttpClient path; the
    opener is the only thing that differs, and it is injected far below here.

No network import appears in this package: fetch capability arrives by
injection, and a static test proves it.
"""
import dataclasses

from .. import sourcecache
from ..budget import BudgetExhausted
from ..httpclient import FetchAccounting, HttpError, ZERO_ACCOUNTING

# Stage 3 reads authoritative indexes only; no child body is ever fetched, so
# `record` mode is unreachable until Stage 4 introduces target-page fetching.
ADAPTER_MODE = "index"

# ------------------------------------------------------- result vocabulary
RESULT_OK = "ok"
RESULT_ZERO = "zero_result"
RESULT_ADAPTER_ERROR = "adapter_error"
RESULT_INFRASTRUCTURE_ERROR = "infrastructure_error"

# Exactly the manifest's enumerated reasons (IMPLEMENTATION_PLAN.md §3). Kept as
# frozensets rather than free strings so a typo cannot invent a new reason.
ZERO_RESULT_REASONS = frozenset({
    "no_items_in_window", "all_below_relevance_threshold", "all_rejected_quality",
    "all_duplicates_of_existing", "category_exclusion_applied",
    # seed-specific, per IMPLEMENTATION_PLAN.md §3.1
    "no_links_matched_allowlist", "all_children_already_known",
})
ADAPTER_ERROR_REASONS = frozenset({
    "feed_parse_error", "unexpected_content_type", "empty_response",
    "schema_mapping_failed", "response_too_large", "index_parse_failed",
    # sourcecache normalizes an unexpected non-HTTP exception to this
    "adapter_error",
})
INFRASTRUCTURE_ERROR_REASONS = frozenset({
    "robots_denied", "http_timeout", "http_4xx", "http_5xx", "dns_failure",
    "lease_timeout", "budget_exhausted", "circuit_open", "preflight_failed",
    "index_fetch_failed", "robots_denied_index",
})


def classify(reason):
    """Which manifest bucket a reason belongs to.

    An unrecognised reason is an ADAPTER error, not an infrastructure one: the
    network cannot produce a reason this module does not know about, so an
    unknown value means our own code went wrong and must not be reported as a
    remote failure.
    """
    if reason in ADAPTER_ERROR_REASONS:
        return RESULT_ADAPTER_ERROR
    if reason in INFRASTRUCTURE_ERROR_REASONS:
        return RESULT_INFRASTRUCTURE_ERROR
    return RESULT_ADAPTER_ERROR


class AdapterError(Exception):
    """A body arrived but could not be turned into candidates."""

    def __init__(self, message, reason):
        super().__init__(message)
        if reason not in ADAPTER_ERROR_REASONS:
            raise ValueError("not an adapter-error reason: %r" % (reason,))
        self.reason = reason


# --------------------------------------------------------------- candidates
@dataclasses.dataclass(frozen=True, slots=True)
class RawCandidate:
    """One discovered target, before anything is decided about it.

    Deliberately raw: no score, no facet, no identity claim. `target_url` is the
    URL exactly as the source published it (resolved against the document base
    where the source used a relative reference); canonicalization for dedup is
    the pool's job, via urlkey, and happens later.
    """
    target_url: str
    title: str = None
    published_at: str = None
    summary: str = None
    publisher: str = None
    source_id: str = ""
    adapter: str = ""
    position: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class AdapterResult:
    """What one source produced, shaped for cell_artifact.metadata.sources[].

    `result` and `reason` are never conflated: `ok` and `zero_result` both mean
    the source worked, and only the two error classes mean it did not.
    """
    source_id: str
    adapter: str
    result: str
    reason: str = None
    candidates: tuple = ()
    dropped_over_cap: int = 0
    requests_made: int = 0
    accounting: FetchAccounting = ZERO_ACCOUNTING
    status: int = None
    detail: str = None

    @property
    def ok(self):
        return self.result in (RESULT_OK, RESULT_ZERO)

    @property
    def failed(self):
        return self.result in (RESULT_ADAPTER_ERROR, RESULT_INFRASTRUCTURE_ERROR)


# ------------------------------------------------------------------ adapter
class Adapter:
    """Base class. Subclasses implement `parse` and declare their content types."""

    name = ""
    expect_content_types = None
    parse_error_reason = "adapter_error"
    empty_reason = "no_items_in_window"

    # -------------------------------------------------------------- parsing
    def parse(self, body, source, base_url):
        raise NotImplementedError

    # ------------------------------------------------------------ discovery
    def discover(self, source, *, cache, client, budget=None, lane_id,
                 round_=1, clock=None):
        """Fetch (at most once per run) and parse one configured source."""
        source_id = source["source_id"]
        url = source["url"]

        try:
            fetched = self._fetch(source, cache=cache, client=client,
                                  budget=budget, lane_id=lane_id, round_=round_,
                                  clock=clock)
        except (HttpError, BudgetExhausted, sourcecache.SourceCacheError) as exc:
            reason = getattr(exc, "reason", None) or "adapter_error"
            return AdapterResult(
                source_id=source_id, adapter=self.name,
                result=classify(reason), reason=reason,
                requests_made=getattr(exc, "accounting", ZERO_ACCOUNTING).attempts,
                accounting=getattr(exc, "accounting", ZERO_ACCOUNTING),
                status=getattr(exc, "status", None), detail=str(exc))

        try:
            candidates = list(self.parse(fetched.body, source, fetched.final_url))
        except AdapterError as exc:
            return AdapterResult(
                source_id=source_id, adapter=self.name,
                result=RESULT_ADAPTER_ERROR, reason=exc.reason,
                requests_made=fetched.accounting.attempts,
                accounting=fetched.accounting, status=fetched.status,
                detail=str(exc))

        if not candidates:
            return AdapterResult(
                source_id=source_id, adapter=self.name,
                result=RESULT_ZERO, reason=self.empty_reason,
                requests_made=fetched.accounting.attempts,
                accounting=fetched.accounting, status=fetched.status)

        # Cap in DOCUMENT ORDER. Not by score — there are no scores yet, and a
        # score-based cut here would silently make discovery non-reproducible.
        cap = int(source.get("max_candidates", len(candidates)))
        kept, dropped = candidates[:cap], max(0, len(candidates) - cap)
        kept = tuple(dataclasses.replace(c, position=i, source_id=source_id,
                                         adapter=self.name)
                     for i, c in enumerate(kept))
        return AdapterResult(
            source_id=source_id, adapter=self.name, result=RESULT_OK,
            candidates=kept, dropped_over_cap=dropped,
            requests_made=fetched.accounting.attempts,
            accounting=fetched.accounting, status=fetched.status)

    # -------------------------------------------------------------- fetching
    def _fetch(self, source, *, cache, client, budget, lane_id, round_, clock):
        """One logical source fetch, through the cache. Never a direct request."""
        url = source["url"]
        # Default query-order policy, always: `preserve`. Nothing here passes
        # query_order_policy, and a static test proves no adapter ever does.
        key = cache.pool.request_key(source["source_id"], url,
                                     adapter=source["adapter"],
                                     adapter_mode=ADAPTER_MODE)

        def fetch_fn():
            response = client.get(url, budget=budget,
                                  expect_content_types=self.expect_content_types)
            established_at = clock() if clock else cache._clock()
            return sourcecache.FetchResult.from_response(key, response, established_at)

        return cache.get_or_fetch(key, fetch_fn, lane_id=lane_id,
                                  source_id=source["source_id"],
                                  adapter_mode=ADAPTER_MODE, round_=round_)


def decode(body, headers=None):
    """Bytes -> text using the declared charset, falling back to UTF-8."""
    charset = "utf-8"
    ctype = (headers or {}).get("content-type", "")
    if "charset=" in ctype:
        charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return body.decode("utf-8", errors="replace")
