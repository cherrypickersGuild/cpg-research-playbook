#!/usr/bin/env python3
"""budget.py — bounded request counts and wall-clock, enforced not advertised.

A single RequestBudget is threaded through the HTTP client for the life of a
cell. EVERY attempt decrements it — including each retry and each redirect hop,
which is the whole point: a source that 500s three times and then redirects
twice has made five requests, not one, and a budget that only counted "logical
fetches" would be a fiction.

Scopes nest. An adapter's budget is charged at the same time as the cell's, so
one greedy adapter cannot starve the others and the cell as a whole still stops
where it said it would.

Exceeding a budget raises BudgetExhausted — a typed, recorded outcome. It is
never a silent truncation: partial results are kept and labelled, and the run
manifest names the cell that ran out.

Wall-clock includes pacing sleeps deliberately. Time spent waiting on a domain's
crawl-delay is time the cell is not finishing, and a budget that ignored it would
let a 15s/request source run for an hour inside a "120s" adapter budget.
"""
import time


class BudgetExhausted(Exception):
    """A budget was reached. Carries enough detail to record why."""

    def __init__(self, scope, kind, limit, observed):
        self.scope = scope          # "adapter:<id>" | "cell:<cell_id>" | "run"
        self.kind = kind            # "requests" | "seconds"
        self.limit = limit
        self.observed = observed
        super().__init__("%s budget exhausted for %s: limit=%s observed=%s"
                         % (kind, scope, limit, observed))

    @property
    def reason(self):
        """The manifest's error_reason enum value."""
        return "budget_exhausted"


class _Scope:
    __slots__ = ("name", "max_requests", "max_seconds", "requests", "started")

    def __init__(self, name, max_requests, max_seconds, now):
        self.name = name
        self.max_requests = max_requests
        self.max_seconds = max_seconds
        self.requests = 0
        self.started = now


class RequestBudget:
    """Nested request/time budgets with an injectable clock.

    The clock is injectable so budget tests are deterministic and instant —
    asserting a 120s budget by actually waiting 120s would make the suite
    unusable, and sleeping less would test nothing.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._scopes = []

    # ---------------------------------------------------------------- scopes
    def push(self, name, max_requests=None, max_seconds=None):
        self._scopes.append(_Scope(name, max_requests, max_seconds, self._clock()))
        return self

    def pop(self, name=None):
        if not self._scopes:
            return None
        if name is not None and self._scopes[-1].name != name:
            raise ValueError("budget scope mismatch: popping %r but top is %r"
                             % (name, self._scopes[-1].name))
        return self._scopes.pop()

    def scope(self, name, max_requests=None, max_seconds=None):
        """Context manager form: `with budget.scope("adapter:x", 25, 120): ...`"""
        return _ScopeCtx(self, name, max_requests, max_seconds)

    # ---------------------------------------------------------------- charge
    def charge_request(self, n=1):
        """Account for n network attempts. Call BEFORE the attempt.

        Charging up front means a budget can never be overspent by the request
        that discovers it is empty.
        """
        self.check_time()
        for s in self._scopes:
            if s.max_requests is not None and s.requests + n > s.max_requests:
                raise BudgetExhausted(s.name, "requests", s.max_requests, s.requests + n)
        for s in self._scopes:
            s.requests += n

    def check_time(self):
        """Raise if any scope has run out of wall-clock. Cheap; call often."""
        now = self._clock()
        for s in self._scopes:
            if s.max_seconds is not None:
                elapsed = now - s.started
                if elapsed > s.max_seconds:
                    raise BudgetExhausted(s.name, "seconds", s.max_seconds, round(elapsed, 3))

    def would_exceed_time(self, extra_seconds):
        """True if sleeping `extra_seconds` would break a budget.

        Used before a pacing sleep so the client fails fast with a typed error
        instead of sleeping into an inevitable timeout.
        """
        now = self._clock()
        for s in self._scopes:
            if s.max_seconds is not None and (now - s.started) + extra_seconds > s.max_seconds:
                return True
        return False

    # ---------------------------------------------------------------- report
    def remaining_requests(self):
        vals = [s.max_requests - s.requests for s in self._scopes if s.max_requests is not None]
        return min(vals) if vals else None

    def remaining_seconds(self):
        now = self._clock()
        vals = [s.max_seconds - (now - s.started)
                for s in self._scopes if s.max_seconds is not None]
        return min(vals) if vals else None

    def usage(self):
        now = self._clock()
        return [{"scope": s.name, "requests": s.requests, "max_requests": s.max_requests,
                 "elapsed_sec": round(now - s.started, 3), "max_seconds": s.max_seconds}
                for s in self._scopes]

    def total_requests(self):
        return self._scopes[0].requests if self._scopes else 0


class _ScopeCtx:
    def __init__(self, budget, name, max_requests, max_seconds):
        self._b, self._n = budget, name
        self._r, self._s = max_requests, max_seconds

    def __enter__(self):
        self._b.push(self._n, self._r, self._s)
        return self._b

    def __exit__(self, exc_type, exc, tb):
        self._b.pop(self._n)
        return False


def from_policy(policy, clock=time.monotonic):
    """Build a run-level budget from config/harvest/policy.v1.json."""
    b = policy.get("budgets", {})
    return RequestBudget(clock=clock), {
        "cell_max_requests": b.get("cell_max_requests", 60),
        "cell_budget_sec": b.get("cell_budget_sec", 300),
        "adapter_max_requests": b.get("adapter_max_requests", 25),
        "adapter_budget_sec": b.get("adapter_budget_sec", 120),
        "connect_timeout_sec": b.get("connect_timeout_sec", 5),
        "read_timeout_sec": b.get("read_timeout_sec", 15),
        "request_timeout_sec": b.get("request_timeout_sec", 20),
        "max_response_bytes": b.get("max_response_bytes", 8 * 1024 * 1024),
        "lease_wait_max_sec": b.get("lease_wait_max_sec", 60),
        "smoke_budget_sec": b.get("smoke_budget_sec", 1800),
    }
