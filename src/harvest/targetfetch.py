#!/usr/bin/env python3
"""targetfetch.py — one target page, fetched through the injected client (S6-2).

Stage 5 closed with every record honestly unverified, because nothing had ever
fetched an item's own page. This module performs that one fetch and reports what
was observed. It is the narrowest useful piece of Stage 6: one function, one
outcome, one mapping table.

WHAT IT DOES NOT OWN, and deliberately cannot reimplement, because the injected
`HttpClient` already owns each of them and is tested on them directly:

    robots decisions · domain throttling and pacing · redirect following and
    permanence classification · retries and backoff · timeout enforcement ·
    the response-size cap · reading the response body

This module sees exactly two things: the client's FINAL `Response`, or the
client's FINAL typed error. It never sees a partial body, and it cannot grow a
second opinion about any of the above. A fixture that could time out or answer
differently on a second call would break that separation, which is why the S6-1
corpus refuses transport-simulation directives.

It DOES carry outward the DV-8 `FetchAccounting` the client has already frozen
onto that final response or error (S6-6A, plan erratum E17) — copied, never
recomputed, and never diffed from the shared `client.stats`. Reading a number the
client computed is not owning the behaviour that produced it: nothing here branches
on an attempt, a hop count or a retry, and the counters travel unread exactly as
`body` and `content_type` do. An earlier draft of this docstring said the module
"never learns how many attempts were made"; that was a stronger claim than the
design needed, and it was the sole reason an exact target-attempt count was
unreachable from the run manifest.

WHAT IT ALSO DOES NOT DO: no alias or canonical adjudication (S6-3 — this module
carries the body and content type outward but never parses them), no candidate
pool, no record construction, no artifact write, no eligibility judgement, and no
re-scoring. A fetch supplies facts. It re-judges nothing.

The one judgement here is the mapping from a failure onto the committed
`access_status` vocabulary, and it is made by EXCEPTION CLASS rather than by
matching a message string. An unmapped `HttpError` subclass raises
`TargetFetchError` rather than being handed the nearest plausible status: a wrong
status is a false claim about a URL, and silence is how it would ship.
"""
import dataclasses

from . import httpclient as hc
from . import records as records_mod
from .budget import BudgetExhausted

# The committed `record.v1.json` access_status vocabulary, referenced by name so
# a typo cannot invent a twelfth value.
NOT_CHECKED = "not_checked"
OK = "ok"
REDIRECTED = "redirected"
NOT_FOUND = "not_found"
GONE = "gone"
AUTH_REQUIRED = "auth_required"
PAYWALLED = "paywalled"
SERVER_ERROR = "server_error"
TIMEOUT = "timeout"
ROBOTS_DENIED = "robots_denied"
UNREACHABLE = "unreachable"

# The committed `verification_status` values this module can earn. "fetched" means
# only that the fetch succeeded — never that a human judged the content, which is
# exactly why the schema does not call it "verified".
FETCHED = "fetched"
UNVERIFIED = "unverified"

# A sentinel, not a status: `ClientError` alone cannot decide, because 404 and 403
# are different facts about a URL. Resolved through CLIENT_STATUS_ACCESS_STATUS.
BY_CLIENT_STATUS = object()

# Keyed by CLASS. Resolution walks the exception's MRO, so a subclass added later
# under one of these keys inherits its mapping instead of vanishing.
#
# The `HttpError` entry is EXACT-MATCH ONLY (see EXACT_MATCH_ONLY below). Were it
# inherited like the others, it would sit in the MRO of every subclass and quietly
# answer for all of them — including a tenth subclass nobody had mapped, which is
# precisely the case that must fail loudly. Mapping the base class by inheritance
# would turn the fail-loud contract into a no-op.
ACCESS_STATUS_FOR_ERROR = {
    hc.RobotsDenied: ROBOTS_DENIED,
    hc.HttpTimeout: TIMEOUT,
    hc.DnsFailure: UNREACHABLE,
    hc.ServerError: SERVER_ERROR,
    hc.LeaseUnavailable: UNREACHABLE,
    # CF-16: reached, but nothing usable came back. The committed vocabulary has
    # no value for "too large" or "wrong type", so the exact class survives
    # verbatim in verification_evidence rather than a schema being widened.
    hc.ResponseTooLarge: UNREACHABLE,
    hc.UnexpectedContentType: UNREACHABLE,
    hc.EmptyResponse: UNREACHABLE,
    hc.ClientError: BY_CLIENT_STATUS,
    # The base class is genuinely raised by the committed client: a redirect
    # without a Location, more redirects than allowed, a redirect loop, a failed
    # connection, and a non-5xx retry status that outlived its attempts. Each
    # means the host was reached and the page was not obtained.
    hc.HttpError: UNREACHABLE,
}

# Classes whose mapping applies to that exact class and never to a subclass.
EXACT_MATCH_ONLY = (hc.HttpError,)

# 4xx is not one fact. Only these five are distinguishable in the committed
# vocabulary; every other 4xx is honestly just "we could not get it".
CLIENT_STATUS_ACCESS_STATUS = {
    401: AUTH_REQUIRED,
    402: PAYWALLED,
    403: AUTH_REQUIRED,
    404: NOT_FOUND,
    410: GONE,
}
CLIENT_STATUS_DEFAULT = UNREACHABLE

# A budget stop is not a failed check — it is the absence of one. Saying anything
# else would claim we looked at a URL we never requested.
ACCESS_STATUS_FOR_BUDGET = NOT_CHECKED

SUCCESS_STATUSES = (OK, REDIRECTED)


class TargetFetchError(Exception):
    """A contract violation this module refuses to paper over.

    Raised for exactly two things, both of which would otherwise put a false
    claim on a record: an `HttpError` subclass with no committed mapping, and a
    clock that does not yield a usable timestamp.
    """


@dataclasses.dataclass(frozen=True, slots=True)
class TargetFetchOutcome:
    """What one target fetch observed. Facts only; no judgement, no persistence.

    `body` and `content_type` travel outward unparsed so S6-3 can look for a
    `rel=canonical` without this module growing an HTML parser. `final_url` and
    `permanent_redirect` are the client's own classification, passed through: this
    module never decides whether a redirect was permanent.

    `accounting` travels the same way (S6-6A): it is the client's own immutable
    per-logical-fetch `FetchAccounting`, copied off the final response or the final
    typed error. It is what makes an EXACT target request count reportable without
    estimating one and without diffing shared counters — the run manifest sums it
    over the run-scoped outcome map, one entry per owned canonical identity, so a URL
    accepted twice is counted once. `ZERO_ACCOUNTING` is the honest default for an
    outcome no client call produced, such as a budget skip.
    """
    requested_url: str
    access_status: str
    verification_status: str
    verification_evidence: str
    last_checked_at: str
    http_status: int = None
    final_url: str = None
    permanent_redirect: bool = False
    content_hash: str = None
    content_type: str = None
    body: bytes = None
    error_class: str = None
    accounting: hc.FetchAccounting = hc.ZERO_ACCOUNTING

    @property
    def succeeded(self):
        """True when a page was actually obtained."""
        return self.access_status in SUCCESS_STATUSES


def _stamp(clock):
    """The fetch instant, from the INJECTED clock only.

    Normalized through the committed `records.to_iso8601_utc`, never a second date
    formatter. There is deliberately no system-clock fallback: a target fetch that
    silently timestamped itself from the wall clock would break the byte
    determinism every artifact contract depends on.
    """
    if clock is None:
        raise TargetFetchError(
            "fetch_target requires an injected clock; a system-clock fallback "
            "would make last_checked_at nondeterministic")
    value = clock() if callable(clock) else clock
    stamp = records_mod.to_iso8601_utc(value)
    if not stamp:
        raise TargetFetchError(
            "the injected clock yielded %r, which is not a usable UTC timestamp; "
            "refusing to invent last_checked_at" % (value,))
    return stamp


def access_status_for(error):
    """The committed `access_status` for one client failure, decided by class.

    Walks the MRO so the most specific mapping wins and an inherited one still
    applies — except for the classes in EXACT_MATCH_ONLY, which answer only for
    themselves. An `HttpError` subclass nobody mapped raises: handing it the
    nearest plausible status would publish a claim about a URL that no observation
    supports.
    """
    if isinstance(error, BudgetExhausted):
        return ACCESS_STATUS_FOR_BUDGET
    actual = type(error)
    for klass in actual.__mro__:
        if klass not in ACCESS_STATUS_FOR_ERROR:
            continue
        if klass in EXACT_MATCH_ONLY and klass is not actual:
            continue
        status = ACCESS_STATUS_FOR_ERROR[klass]
        if status is BY_CLIENT_STATUS:
            return CLIENT_STATUS_ACCESS_STATUS.get(
                getattr(error, "status", None), CLIENT_STATUS_DEFAULT)
        return status
    raise TargetFetchError(
        "%s has no committed access_status mapping. Add one to "
        "ACCESS_STATUS_FOR_ERROR deliberately — an unmapped failure must not be "
        "given the nearest plausible status." % type(error).__name__)


def _evidence(parts):
    """A deterministic one-line summary.

    Every part is derived from the response or the exception CLASS — never from a
    traceback, a repr, an object address or a platform message, because those
    would move between runs and land in a persisted record.
    """
    return "; ".join(part for part in parts if part)


def _success(url, response, stamp):
    # The client has already classified permanence: every hop 301/308 or not.
    # This module reads that flag and does not recompute it.
    redirected = bool(response.permanent_redirect)
    body = response.body
    evidence = _evidence([
        "http %s" % response.status,
        "final_url %s" % response.final_url,
        "%d bytes" % (len(body) if body is not None else 0),
        ("permanent redirect" if redirected
         else ("temporary or mixed redirect chain" if response.redirects
               else None)),
    ])
    return TargetFetchOutcome(
        requested_url=url,
        access_status=REDIRECTED if redirected else OK,
        verification_status=FETCHED,
        verification_evidence=evidence,
        last_checked_at=stamp,
        http_status=response.status,
        final_url=response.final_url,
        permanent_redirect=redirected,
        # The committed hash, computed once by Response from the exact bytes.
        content_hash=response.content_hash,
        content_type=response.content_type,
        body=body,
        # The client's own frozen counters, read straight off the response. Not
        # recomputed here, and deliberately not derived from `client.stats`, whose
        # lifetime aggregate would attribute another call's work to this one.
        accounting=response.accounting,
    )


def _failure(url, error, stamp, *, access_status):
    detail = str(error)
    status = getattr(error, "status", None)
    evidence = _evidence([
        type(error).__name__,
        ("http %s" % status) if status is not None else None,
        detail or None,
    ])
    return TargetFetchOutcome(
        requested_url=url,
        access_status=access_status,
        verification_status=UNVERIFIED,
        verification_evidence=evidence,
        last_checked_at=stamp,
        http_status=status if isinstance(status, int) else None,
        error_class=type(error).__name__,
        # A failed logical fetch cost exactly as much as a successful one, and the
        # client freezes the same counters onto it. `getattr` rather than attribute
        # access because only `HttpError` carries a class-level default: a
        # `BudgetExhausted` raised before `get()` ever ran — or any other exception
        # this module did not expect — has no accounting to read, and zeros are then
        # the truth about how many requests it produced.
        accounting=getattr(error, "accounting", hc.ZERO_ACCOUNTING),
    )


def fetch_target(url, *, client, budget=None, clock=None):
    """Fetch one target page and report what was observed.

    `client`, `budget` and `clock` are all injected: this constructs no
    `HttpClient`, opens no socket, reads no fixture directory and writes no file.
    Exactly ONE logical call is made to the client, whose retries and redirect
    hops are its own business.

    Returns an outcome for every ordinary result — success, and every committed
    client failure class — rather than raising, so one candidate's inaccessible
    page never takes down the cell around it. Two things still raise, on purpose:
    an unmapped `HttpError` subclass, and an unusable clock. `KeyboardInterrupt`,
    `SystemExit` and `GeneratorExit` are NOT caught and propagate untouched — a
    fetch is not entitled to swallow an interruption.
    """
    stamp = _stamp(clock)
    try:
        response = client.get(url, budget=budget)
    except (hc.HttpError, BudgetExhausted) as error:
        # access_status_for may raise TargetFetchError for an unmapped subclass.
        # Raised from inside this handler, it propagates rather than being caught
        # by the ordinary-Exception handler below — which is the intent: fail loud.
        return _failure(url, error, stamp, access_status=access_status_for(error))
    except Exception as error:                                    # noqa: BLE001
        # Not a class this module claims to understand. It still becomes this
        # candidate's outcome rather than the cell's crash, and the evidence names
        # the class so an unexpected failure mode is visible rather than absorbed.
        # Deliberately NOT a catch-all for HttpError subclasses: those are
        # resolved above, where an unmapped one fails loudly.
        return _failure(url, error, stamp, access_status=UNREACHABLE)
    return _success(url, response, stamp)
