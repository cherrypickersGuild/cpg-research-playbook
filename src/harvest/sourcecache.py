#!/usr/bin/env python3
r"""sourcecache.py — one logical fetch per source_request_key, success AND failure.

Two earlier sketches were both wrong, and the reasons are worth keeping:

  * fetch-first-then-acquire lets two lanes racing the same key issue two real
    HTTP requests before either claims ownership;
  * acquire-first-then-fetch leaves an orphan when the owner fails — a
    CandidatePool source row with source_id, normalized_url and established_by
    all null, which produces five schema errors on serialization.

So ownership is claimed atomically BEFORE any request, and the pool is written
only on the success path, after the complete row has been validated:

    ABSENT --claim--> PENDING --complete--> DONE
                             \--fail-----> FAILED

DONE and FAILED are terminal and immutable, which is what makes "a failure is
never silently retried by a later lane in the same run" true rather than hoped
for. Waiters block on a per-entry event and never hold the entry-table lock.

SCOPE OF THE GUARANTEE. This is an in-process, thread-safe implementation. An
ordinary Python exception — including an unexpected one — transitions the entry
to FAILED and releases every waiter. That is a try/finally guarantee inside a
live interpreter. It is NOT recovery from process termination, interpreter
termination or machine failure; cross-process stale-owner recovery belongs to
the Stage 5 persistent store, alongside the existing domainlease machinery.

No network, no adapters, no parsing. `fetch_fn` is injected.
"""
import dataclasses
import hashlib
import threading
import time
import uuid
from types import MappingProxyType

from . import httpclient as hc
from .budget import BudgetExhausted

# ------------------------------------------------------------------- states
ABSENT = "absent"
PENDING = "pending"
DONE = "done"
FAILED = "failed"
TERMINAL = (DONE, FAILED)


# ------------------------------------------------------------------- errors
class SourceCacheError(Exception):
    """A source-cache contract violation."""


class WaitTimeout(SourceCacheError):
    """A bounded wait expired. The owner is untouched and still working."""
    reason = "lease_timeout"


class OwnershipError(SourceCacheError):
    """A non-owner, a stale token, or a second terminal transition."""


class InternalFetchError(SourceCacheError):
    """An unexpected, non-HTTP exception escaped fetch_fn.

    Deliberately its own type: an adapter bug must not be reported as though the
    remote server had failed. The original class name and message are preserved
    on the descriptor for diagnosis.
    """
    reason = "adapter_error"


# --------------------------------------------------------------- success result
@dataclasses.dataclass(frozen=True, slots=True)
class FetchResult:
    """The run's immutable view of one source, shared by every lane.

    Built straight from a DV-8 `httpclient.Response`. `accounting` is copied from
    `Response.accounting` — never reconstructed, and never derived by diffing the
    shared `client.stats`, which attributes concurrent calls' work to each other.
    """
    source_request_key: str
    status: int
    final_url: str
    headers: MappingProxyType
    body: bytes
    body_sha256: str
    elapsed_sec: float
    redirects: int
    permanent_redirect: bool
    accounting: hc.FetchAccounting
    established_at: str
    established_by: str = "200"

    @classmethod
    def from_response(cls, key, response, established_at):
        body = response.body or b""
        return cls(
            source_request_key=key,
            status=response.status,
            final_url=response.final_url,
            # Frozen so one reusing lane cannot mutate what every other lane sees.
            headers=MappingProxyType(dict(response.headers or {})),
            body=body,
            body_sha256=hashlib.sha256(body).hexdigest(),
            elapsed_sec=response.elapsed_sec,
            redirects=response.redirects,
            permanent_redirect=response.permanent_redirect,
            accounting=response.accounting,
            established_at=established_at,
            # Stage 3 sends no conditional requests, so every real snapshot is a
            # 200. The 304 path stays unit-tested in pool.py and belongs to the
            # Stage 6 refresh/linkcheck work.
            established_by="304" if response.status == 304 else "200",
        )


# ------------------------------------------------------------ failure descriptor
# A FIXED table. Nothing is imported or instantiated from a stored string: an
# error_type that is not a key here cannot name a class.
_TYPE_OF_CLASS = {
    hc.RobotsDenied: "robots_denied",
    hc.HttpTimeout: "http_timeout",
    hc.DnsFailure: "dns_failure",
    hc.ClientError: "http_4xx",
    hc.ServerError: "http_5xx",
    hc.ResponseTooLarge: "response_too_large",
    hc.UnexpectedContentType: "unexpected_content_type",
    hc.EmptyResponse: "empty_response",
    hc.HttpError: "http_error",
    BudgetExhausted: "budget_exhausted",
    InternalFetchError: "internal_fetch_error",
}
_CLASS_OF_TYPE = {v: k for k, v in _TYPE_OF_CLASS.items()}

# Which manifest bucket each failure belongs to. Mirrors httpclient.preflight().
_ADAPTER_ERROR_REASONS = frozenset({
    "unexpected_content_type", "empty_response", "response_too_large",
    "adapter_error",
})


def _result_class(reason):
    return "adapter_error" if reason in _ADAPTER_ERROR_REASONS else "infrastructure_error"


@dataclasses.dataclass(frozen=True, slots=True)
class FailureDescriptor:
    """An immutable failure, cached instead of the exception object.

    Exceptions carry traceback state and are not safe to share as a cache value,
    so waiters receive an EQUIVALENT reconstructed error, not the owner's
    instance. Equivalence is on type, reason, status and message — never object
    identity.
    """
    error_type: str
    reason: str
    message: str
    result_class: str
    accounting: hc.FetchAccounting
    status: int = None
    url: str = None
    exception_class_name: str = ""
    detail: tuple = ()          # type-specific rebuild args, already immutable

    @classmethod
    def from_exception(cls, exc):
        etype = _TYPE_OF_CLASS.get(type(exc))
        if etype is None:
            # Unknown/ordinary exception: normalize to the dedicated internal
            # type, keeping the real class name and message for diagnosis.
            return cls(error_type="internal_fetch_error",
                       reason=InternalFetchError.reason,
                       message=str(exc),
                       result_class=_result_class(InternalFetchError.reason),
                       accounting=hc.ZERO_ACCOUNTING,
                       exception_class_name=type(exc).__name__)

        if etype == "budget_exhausted":
            return cls(error_type=etype, reason=exc.reason, message=str(exc),
                       result_class=_result_class(exc.reason),
                       accounting=getattr(exc, "accounting", hc.ZERO_ACCOUNTING),
                       exception_class_name=type(exc).__name__,
                       detail=(exc.scope, exc.kind, exc.limit, exc.observed))

        return cls(error_type=etype, reason=exc.reason, message=str(exc),
                   result_class=_result_class(exc.reason),
                   accounting=getattr(exc, "accounting", hc.ZERO_ACCOUNTING),
                   status=exc.status, url=exc.url,
                   exception_class_name=type(exc).__name__)

    def rebuild(self):
        """A NEW equivalent typed exception. Never the cached owner's instance."""
        cls_ = _CLASS_OF_TYPE[self.error_type]
        if cls_ is BudgetExhausted:
            exc = BudgetExhausted(*self.detail)
        elif cls_ is InternalFetchError:
            exc = InternalFetchError("%s: %s" % (self.exception_class_name, self.message))
        else:
            exc = cls_(self.message, url=self.url, status=self.status)
        exc.accounting = self.accounting
        return exc


# --------------------------------------------------------------------- store
class _Entry:
    __slots__ = ("state", "token", "event", "payload")

    def __init__(self, token):
        self.state = PENDING
        self.token = token
        self.event = threading.Event()
        self.payload = None


class InMemoryStore:
    """Thread-safe in-process store: claim / wait / complete / fail.

    Stage 5 may later supply a lockdir-backed implementation of the same four
    operations with stale-owner recovery. It will NOT reuse this _Entry — an
    object holding a threading.Event is not substitutable by a filesystem
    mapping, and this module does not pretend otherwise.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._entries = {}

    def claim(self, key):
        """Atomically become the owner, or return None for every later caller."""
        with self._lock:
            if key in self._entries:
                return None
            token = uuid.uuid4().hex          # opaque; not derivable by a waiter
            self._entries[key] = _Entry(token)
            return token

    def state(self, key):
        with self._lock:
            entry = self._entries.get(key)
            return ABSENT if entry is None else entry.state

    def peek(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return ABSENT, None
            return entry.state, (entry.payload if entry.state in TERMINAL else None)

    def wait(self, key, timeout=None, deadline=None):
        """Block until terminal. Returns (state, payload). Never holds the lock.

        Bounded by construction so a caller can pass whatever remains of its
        run/cell/adapter budget. A timeout raises and changes nothing: the owner
        keeps working and may still reach DONE or FAILED.
        """
        if deadline is not None:
            timeout = max(0.0, deadline - time.monotonic())
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                raise SourceCacheError("no entry for %s — claim it first" % key)
            if entry.state in TERMINAL:
                return entry.state, entry.payload
            event = entry.event
        if not event.wait(timeout):
            raise WaitTimeout(
                "waited %ss for %s; the owner is still working and was not cancelled"
                % (timeout, key))
        with self._lock:
            entry = self._entries[key]
            return entry.state, entry.payload

    def complete(self, key, owner_token, result):
        return self._terminate(key, owner_token, DONE, result)

    def fail(self, key, owner_token, descriptor):
        return self._terminate(key, owner_token, FAILED, descriptor)

    def _terminate(self, key, owner_token, state, payload):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                raise OwnershipError("no entry for %s" % key)
            if entry.token != owner_token:
                raise OwnershipError(
                    "only the logical owner may %s %s" % (state, key))
            if entry.state in TERMINAL:
                raise OwnershipError(
                    "%s is already %s — terminal states are immutable" % (key, entry.state))
            entry.state = state
            entry.payload = payload
            event = entry.event
        event.set()               # released only after the state is visible
        return payload


# ----------------------------------------------------------------- the cache
class SourceFetchCache:
    """One per run. Guarantees one logical fetch per source_request_key.

    Success and failure are BOTH cached, so a source that failed is not retried
    by the next lane in the same run — which would turn one bad source into N
    identical requests.
    """

    def __init__(self, pool, store=None, clock=None):
        self.pool = pool
        self.store = store if store is not None else InMemoryStore()
        self._clock = clock or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                      time.gmtime()))
        self.fetch_calls = 0
        self._calls_lock = threading.Lock()

    # ------------------------------------------------------------------ api
    def get_or_fetch(self, key, fetch_fn, *, lane_id, source_id, adapter_mode="index",
                     round_=1, timeout=None, deadline=None):
        """Return the run's single FetchResult for `key`, fetching at most once.

        The owner performs the fetch, writes the COMPLETE pool row, and only then
        transitions to DONE. Every other lane waits and reuses. Any failure —
        HTTP, budget, unexpected, or pool insertion — becomes FAILED with no pool
        row, and every caller receives an equivalent typed error.
        """
        token = self.store.claim(key)
        if token is None:
            return self._await_existing(key, lane_id=lane_id, round_=round_,
                                        timeout=timeout, deadline=deadline)

        try:
            with self._calls_lock:
                self.fetch_calls += 1
            result = fetch_fn()
        except BaseException as exc:                       # noqa: BLE001
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            descriptor = FailureDescriptor.from_exception(exc)
            self.store.fail(key, token, descriptor)
            raise descriptor.rebuild() from exc

        # The pool row must exist and be complete BEFORE any waiter is released.
        try:
            self.pool.record_established_source(
                key,
                source_id=source_id,
                normalized_url=result.final_url,
                established_by=result.established_by,
                established_at=result.established_at,
                owner_lane_id=lane_id,
                body_sha256=result.body_sha256,
                adapter_mode=adapter_mode,
                attempts=result.accounting.attempts,
                retries=result.accounting.retries,
                redirect_hops=result.accounting.redirect_hops,
                budget_charged=result.accounting.request_charges,
            )
        except BaseException as exc:                       # noqa: BLE001
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            # Insertion is all-or-nothing, so there is nothing to roll back —
            # but the entry must not be left PENDING for waiters to hang on.
            descriptor = FailureDescriptor.from_exception(exc)
            self.store.fail(key, token, descriptor)
            raise descriptor.rebuild() from exc

        self.store.complete(key, token, result)
        return result

    # -------------------------------------------------------------- internal
    def _await_existing(self, key, *, lane_id, round_, timeout, deadline):
        state, payload = self.store.wait(key, timeout=timeout, deadline=deadline)
        if state == DONE:
            # Safe only here: DONE means the complete source row already exists.
            self.pool.reuse_snapshot(key, lane_id, round_)
            return payload
        raise payload.rebuild()
