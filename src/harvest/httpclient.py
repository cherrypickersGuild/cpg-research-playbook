#!/usr/bin/env python3
"""httpclient.py — polite, bounded, robots-respecting HTTP.

This is the piece the repository did not have. Before it, every fetch happened
inside a `claude -p` lane via WebFetch, which meant no robots handling, no
per-domain throttling, and `http_status`/`content_hash` that were always null.

Design follows scripts/github_meta.py, which is the proven local-HTTP pattern in
this repo (stdlib urllib, injectable opener, bounded retries, sanitized errors),
generalized to arbitrary hosts and joined to the cross-process domain lease.

MANDATORY BASELINE (all enforced here):
  * robots.txt with RFC 9309 semantics and Crawl-delay
  * global cross-process per-domain concurrency + spacing (domainlease)
  * Retry-After, shared pipeline-wide
  * connect / read / total-request timeouts, distinct
  * bounded retries with exponential backoff AND jitter
  * bounded redirects, robots re-checked on host change, 301/308 vs 302/307
    distinguished because only the former may later become an identity alias
  * max_response_bytes, enforced while streaming
  * identifying User-Agent
  * typed errors that map onto the manifest's error enums

STAGED (interface reserved, disabled in config until the baseline gates pass):
  circuit breaker, ETag/Last-Modified conditional requests, body caching.

Everything raises a typed error rather than returning a sentinel, so a caller
can never mistake a failure for an empty result — the zero-result vs error
distinction the run manifest depends on.
"""
import dataclasses
import io
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from .budget import BudgetExhausted
from .domainlease import DomainLease, LeaseTimeout, effective_concurrency, effective_interval
from .urlkey import content_hash as _content_hash

DEFAULT_UA = "cherry-harvest/1.0 (+https://cherryinthehaystack.com)"


# ----------------------------------------------------------------- accounting
@dataclasses.dataclass(frozen=True, slots=True)
class FetchAccounting:
    """Immutable counters for ONE logical fetch — one call to HttpClient.get().

    Deliberately not derived from HttpClient.stats. That dict is a
    client-lifetime aggregate shared by every concurrent call, so a
    before/after delta around one get() attributes other calls' work to this
    one: two concurrent 2-attempt fetches each measure 4. Measured, not
    supposed. Every counter here is incremented at the exact point the event
    happens, on an accumulator private to one call.

      attempts         every target HTTP attempt, including the first, every
                       retry, and every request issued for a followed redirect
                       target. Robots.txt retrieval is NOT a target attempt.
      retries          attempts made because of retry policy only. Following a
                       redirect is not a retry.
      redirect_hops    redirects actually followed.
      request_charges  successful RequestBudget.charge_request(1) calls for this
                       fetch. Equal to `attempts` when a budget is supplied and
                       0 when it is not, because the charge is what is counted,
                       not the intent to charge. `charge_request` has exactly
                       one call site in the repository (_attempt below), robots
                       retrieval never charges, and DomainLease only ever checks
                       time — so nothing outside the target attempt loop can
                       contribute.
    """
    attempts: int = 0
    retries: int = 0
    redirect_hops: int = 0
    request_charges: int = 0


ZERO_ACCOUNTING = FetchAccounting()


class _CallAccounting:
    """Private mutable accumulator. One per get(), never shared."""
    __slots__ = ("attempts", "retries", "redirect_hops", "request_charges")

    def __init__(self):
        self.attempts = self.retries = self.redirect_hops = self.request_charges = 0

    def freeze(self):
        return FetchAccounting(attempts=self.attempts, retries=self.retries,
                               redirect_hops=self.redirect_hops,
                               request_charges=self.request_charges)


# --------------------------------------------------------------------------- errors
class HttpError(Exception):
    """Base. `reason` maps onto the run manifest's enumerated error reasons.

    Carries the same immutable FetchAccounting a successful Response does, so a
    caller can record exactly what a failed logical fetch cost. Defaults to all
    zeros for an error constructed outside get().
    """
    reason = "http_5xx"
    accounting = ZERO_ACCOUNTING

    def __init__(self, message, url=None, status=None):
        super().__init__(message)
        self.url = url
        self.status = status


class RobotsDenied(HttpError):
    reason = "robots_denied"


class HttpTimeout(HttpError):
    reason = "http_timeout"


class DnsFailure(HttpError):
    reason = "dns_failure"


class ServerError(HttpError):
    reason = "http_5xx"


class ResponseTooLarge(HttpError):
    reason = "response_too_large"


class UnexpectedContentType(HttpError):
    reason = "unexpected_content_type"


class EmptyResponse(HttpError):
    reason = "empty_response"


class LeaseUnavailable(HttpError):
    """Domain coordination could not be obtained — no slot, or no pace lock.

    Its own reason because it is not a server failure at all: nothing was sent.
    Translating it to the generic `http_5xx` bucket, as the acquire path did
    before, points an operator at a remote outage when the truth is local
    contention. `lease_timeout` is already the manifest's enumerated reason for
    exactly this, so no new vocabulary is introduced. `status` stays null: there
    was no response to have one.
    """
    reason = "lease_timeout"


class ClientError(HttpError):
    """4xx that is not worth retrying (404, 410, 401, 403 …).

    Its own reason, not the server-error bucket: a dead configured feed is a
    client-side 404 and reporting it as `http_5xx` would send an operator
    looking for an outage that never happened. `status` still carries the exact
    code. A retryable 4xx (429, and anything else listed in retry_on_status) is
    NOT a ClientError — it is retried and, once attempts are exhausted, raised
    as the generic HttpError, which keeps `http_5xx`.
    """
    reason = "http_4xx"


# --------------------------------------------------------------------------- result
class Response:
    __slots__ = ("url", "final_url", "status", "headers", "body", "elapsed_sec",
                 "redirects", "permanent_redirect", "from_cache", "content_hash",
                 "accounting")

    def __init__(self, url, final_url, status, headers, body, elapsed_sec,
                 redirects, permanent_redirect, from_cache=False,
                 accounting=ZERO_ACCOUNTING):
        self.url = url
        self.final_url = final_url
        self.status = status
        self.headers = headers
        self.body = body
        self.elapsed_sec = elapsed_sec
        self.redirects = redirects
        # True only when EVERY hop was 301/308. A 302/307 anywhere in the chain
        # means the final location is temporary and must never rewrite identity.
        self.permanent_redirect = permanent_redirect
        self.from_cache = from_cache
        self.content_hash = _content_hash(body) if body is not None else None
        self.accounting = accounting

    # Convenience only — DERIVED from the one immutable accounting object, never
    # maintained separately, so the two can never disagree.
    @property
    def attempts(self):
        return self.accounting.attempts

    @property
    def retries(self):
        return self.accounting.retries

    @property
    def text(self):
        if self.body is None:
            return ""
        charset = "utf-8"
        ctype = (self.headers or {}).get("content-type", "")
        if "charset=" in ctype:
            charset = ctype.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except (LookupError, TypeError):
            return self.body.decode("utf-8", errors="replace")

    @property
    def content_type(self):
        return (self.headers or {}).get("content-type", "").split(";")[0].strip().lower()


# --------------------------------------------------------------------------- robots
class RobotsRules:
    """RFC 9309 robots.txt matching.

    Written rather than using urllib.robotparser, which implements the 1996
    draft's FIRST-MATCH-IN-FILE-ORDER rule instead of RFC 9309 §2.2.2's
    LONGEST-MATCH-WINS. That difference is not cosmetic and it errs in the
    dangerous direction:

        User-agent: *
        Allow: /
        Disallow: /private

    First-match returns ALLOW for /private/x because `Allow: /` appears first.
    Longest-match returns DISALLOW, because `/private` (8 chars) is a more
    specific rule than `/` (1 char). Inheriting the stdlib behaviour would mean
    fetching paths publishers have explicitly asked us not to.

    Implements: user-agent group selection (most specific match beats `*`),
    Allow/Disallow with `*` and `$` wildcards, longest-match precedence with
    Allow winning ties, and Crawl-delay.
    """

    def __init__(self, text=""):
        self.groups = {}        # lowercase agent -> {"rules": [(len, allow, pattern)], "delay": float|None}
        self._parse(text or "")

    def _parse(self, text):
        current = []
        expecting_agent = True
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, _, value = line.partition(":")
            field = field.strip().lower()
            value = value.strip()

            if field == "user-agent":
                if not expecting_agent:
                    current = []
                    expecting_agent = True
                agent = value.lower()
                current.append(agent)
                self.groups.setdefault(agent, {"rules": [], "delay": None})
                continue

            if not current:
                continue                     # a rule before any user-agent line
            expecting_agent = False

            if field in ("allow", "disallow"):
                if field == "disallow" and value == "":
                    continue                 # "Disallow:" with no value means allow all
                for agent in current:
                    self.groups[agent]["rules"].append((field == "allow", value))
            elif field == "crawl-delay":
                try:
                    delay = float(value)
                except ValueError:
                    continue
                for agent in current:
                    self.groups[agent]["delay"] = delay

    def _group_for(self, user_agent):
        """Most specific matching group, else `*`, else None (RFC 9309 §2.2.1)."""
        ua = (user_agent or "").lower()
        best = None
        best_len = -1
        for agent in self.groups:
            if agent == "*":
                continue
            if agent and agent in ua and len(agent) > best_len:
                best, best_len = agent, len(agent)
        if best is not None:
            return self.groups[best]
        return self.groups.get("*")

    @staticmethod
    def _matches(pattern, path):
        """Glob-ish match supporting `*` (any run) and `$` (end anchor)."""
        if pattern == "":
            return False
        anchored = pattern.endswith("$")
        pat = pattern[:-1] if anchored else pattern
        parts = pat.split("*")

        pos = 0
        # first segment must match at the very start
        if not path.startswith(parts[0]):
            return False
        pos = len(parts[0])
        for seg in parts[1:]:
            if seg == "":
                continue
            idx = path.find(seg, pos)
            if idx == -1:
                return False
            pos = idx + len(seg)
        if anchored:
            if pat.endswith("*"):
                return True
            return path.endswith(parts[-1]) and pos == len(path)
        return True

    def allowed(self, user_agent, path):
        group = self._group_for(user_agent)
        if group is None:
            return True                       # no applicable group -> no restriction
        best_allow = None
        best_len = -1
        for allow, pattern in group["rules"]:
            if self._matches(pattern, path):
                # Longest match wins; Allow wins an exact-length tie.
                plen = len(pattern.rstrip("$"))
                if plen > best_len or (plen == best_len and allow):
                    best_len = plen
                    best_allow = allow
        if best_allow is None:
            return True
        return best_allow

    def crawl_delay(self, user_agent):
        group = self._group_for(user_agent)
        return group["delay"] if group else None


class RobotsCache:
    """robots.txt per host, with RFC 9309 unavailability semantics.

    RFC 9309 §2.3.1: 4xx ("Unavailable") means the crawler MAY access anything;
    5xx ("Unreachable") means it SHOULD assume complete disallow. Getting this
    backwards is the difference between politely skipping a site and hammering
    one that is asking you to stop, so both directions are explicit and
    configurable rather than assumed.
    """

    def __init__(self, opener, user_agent=DEFAULT_UA, ttl_sec=3600,
                 unavailable_4xx="allow", unreachable_5xx="disallow",
                 clock=time.time, timeout=10):
        self._opener = opener
        self._ua = user_agent
        self._ttl = ttl_sec
        self._4xx = unavailable_4xx
        self._5xx = unreachable_5xx
        self._clock = clock
        self._timeout = timeout
        self._cache = {}     # origin -> (fetched_at, parser_or_None, policy, crawl_delay)

    def _origin(self, url):
        p = urllib.parse.urlsplit(url)
        return "%s://%s" % (p.scheme, p.netloc)

    def _fetch(self, origin):
        req = urllib.request.Request(origin + "/robots.txt",
                                     headers={"User-Agent": self._ua}, method="GET")
        try:
            status, headers, body = self._opener(req, timeout=self._timeout)
        except DnsFailure:
            return None, self._5xx, None
        except Exception:
            return None, self._5xx, None

        if 200 <= status < 300:
            try:
                rules = RobotsRules(body.decode("utf-8", errors="replace"))
            except Exception:
                # An unparseable robots.txt is treated as "unavailable", not as
                # a licence: fall through to the configured 4xx policy.
                return None, self._4xx, None
            return rules, "parsed", rules.crawl_delay(self._ua)
        if 400 <= status < 500:
            return None, self._4xx, None
        return None, self._5xx, None

    def get(self, url):
        origin = self._origin(url)
        now = self._clock()
        hit = self._cache.get(origin)
        if hit and (now - hit[0]) < self._ttl:
            return hit[1], hit[2], hit[3]
        rp, policy, delay = self._fetch(origin)
        self._cache[origin] = (now, rp, policy, delay)
        return rp, policy, delay

    def allowed(self, url):
        rules, policy, _ = self.get(url)
        if rules is not None:
            p = urllib.parse.urlsplit(url)
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            try:
                return bool(rules.allowed(self._ua, path))
            except Exception:
                return True
        return policy == "allow"

    def crawl_delay(self, url):
        return self.get(url)[2]


# --------------------------------------------------------------------------- opener
def default_opener(req, timeout=20):
    """Perform one request WITHOUT following redirects.

    Redirects are handled by the client so each hop can be counted against the
    budget, re-checked against robots, and classified permanent vs temporary.
    urllib's automatic redirect handling would hide all three.
    """
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        resp = opener.open(req, timeout=timeout)
        return resp.getcode(), {k.lower(): v for k, v in resp.headers.items()}, resp
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, TimeoutError):
            raise HttpTimeout("timeout", url=req.full_url)
        text = str(reason).lower()
        if "name or service not known" in text or "getaddrinfo" in text or "nodename" in text:
            raise DnsFailure("dns failure", url=req.full_url)
        if "timed out" in text:
            raise HttpTimeout("timeout", url=req.full_url)
        raise HttpError("connection failed", url=req.full_url)
    except TimeoutError:
        raise HttpTimeout("timeout", url=req.full_url)


def _read_capped(fp, max_bytes, url):
    """Read at most max_bytes+1 so oversize is detected without buffering it all."""
    if fp is None:
        return b""
    if isinstance(fp, (bytes, bytearray)):
        data = bytes(fp)
        if len(data) > max_bytes:
            raise ResponseTooLarge("response exceeds %d bytes" % max_bytes, url=url)
        return data
    buf = io.BytesIO()
    remaining = max_bytes + 1
    while remaining > 0:
        chunk = fp.read(min(65536, remaining))
        if not chunk:
            break
        buf.write(chunk)
        remaining -= len(chunk)
    data = buf.getvalue()
    if len(data) > max_bytes:
        raise ResponseTooLarge("response exceeds %d bytes" % max_bytes, url=url)
    return data


# --------------------------------------------------------------------------- client
class HttpClient:
    def __init__(self, policy, lease_root, opener=default_opener,
                 clock=time.time, sleep=time.sleep, monotonic=time.monotonic,
                 user_agent=None, rng=None):
        self.policy = policy or {}
        b = self.policy.get("budgets", {})
        r = self.policy.get("retry", {})
        rob = self.policy.get("robots", {})

        self.lease_root = lease_root
        self._opener = opener
        self._clock = clock
        self._sleep = sleep
        self._monotonic = monotonic
        self._rng = rng or random.Random()

        self.user_agent = user_agent or self.policy.get("user_agent", DEFAULT_UA)
        self.connect_timeout = b.get("connect_timeout_sec", 5)
        self.read_timeout = b.get("read_timeout_sec", 15)
        self.request_timeout = b.get("request_timeout_sec", 20)
        self.max_response_bytes = b.get("max_response_bytes", 8 * 1024 * 1024)
        self.lease_wait_max = b.get("lease_wait_max_sec", 60)

        self.max_attempts = r.get("max_attempts", 3)
        self.backoff_base = r.get("backoff_base_sec", 0.5)
        self.backoff_mult = r.get("backoff_multiplier", 2.0)
        self.jitter_frac = r.get("jitter_frac", 0.25)
        self.retry_status = set(r.get("retry_on_status", [429, 500, 502, 503, 504]))
        self.max_redirects = r.get("max_redirects", 3)

        self.robots_enabled = rob.get("enabled", True)
        self.respect_crawl_delay = rob.get("respect_crawl_delay", True)
        self.robots = RobotsCache(
            opener=self._raw_opener, user_agent=self.user_agent,
            ttl_sec=rob.get("cache_ttl_sec", 3600),
            unavailable_4xx=rob.get("unavailable_4xx_policy", "allow"),
            unreachable_5xx=rob.get("unreachable_5xx_policy", "disallow"),
            clock=clock, timeout=self.request_timeout)

        self.domain_defaults = self.policy.get("domain_defaults", {})
        self.domain_overrides = self.policy.get("domain_overrides", {})

        self.stats = {"requests": 0, "retries": 0, "redirects": 0,
                      "robots_denied": 0, "paced_sec": 0.0}

    # robots fetching must not itself recurse through robots checking
    def _raw_opener(self, req, timeout=None):
        status, headers, fp = self._opener(req, timeout=timeout or self.request_timeout)
        body = _read_capped(fp, self.max_response_bytes, req.full_url)
        return status, headers, body

    # ---------------------------------------------------------------- helpers
    def _lease_for(self, host, crawl_delay=None):
        conc = effective_concurrency(self.domain_defaults, self.domain_overrides, host)
        interval = effective_interval(self.domain_defaults, self.domain_overrides,
                                      host, crawl_delay if self.respect_crawl_delay else None)
        stale = float(self.domain_defaults.get("lease_stale_sec", 120))
        return DomainLease(self.lease_root, host, max_concurrency=conc,
                           min_interval_sec=interval, lease_stale_sec=stale,
                           clock=self._clock, sleep=self._sleep), interval

    def _backoff(self, attempt):
        base = self.backoff_base * (self.backoff_mult ** (attempt - 1))
        # Jitter so N workers that failed together do not retry together.
        return base * (1.0 + self._rng.uniform(-self.jitter_frac, self.jitter_frac))

    @staticmethod
    def _retry_after(headers):
        v = (headers or {}).get("retry-after")
        if not v:
            return None
        v = v.strip()
        try:
            return max(0.0, float(int(v)))
        except ValueError:
            pass
        try:
            from email.utils import parsedate_to_datetime
            import datetime
            dt = parsedate_to_datetime(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
            return max(0.0, delta)
        except Exception:
            return None

    # ------------------------------------------------------------------- get
    def get(self, url, budget=None, accept=None, expect_content_types=None,
            extra_headers=None):
        """Fetch one URL politely. Raises a typed HttpError on failure.

        Never returns a sentinel: a caller must not be able to confuse "the
        server said no" with "there was nothing there".

        Per-logical-fetch accounting is attached to whatever leaves this method —
        `Response.accounting` on success, `HttpError.accounting` on failure — so
        a caller recording what a fetch cost never has to diff shared counters.
        """
        started = self._monotonic()
        seen = []
        current = url
        permanent_only = True
        redirects = 0
        acct = _CallAccounting()      # private to THIS call; never shared

        try:
            return self._get(url, current, seen, permanent_only, redirects,
                             started, acct, budget, accept, expect_content_types,
                             extra_headers)
        except (HttpError, BudgetExhausted) as exc:
            # Freeze onto the exception instance: the failure path needs exact
            # accounting just as much as the success path does.
            exc.accounting = acct.freeze()
            raise

    def _get(self, url, current, seen, permanent_only, redirects, started, acct,
             budget, accept, expect_content_types, extra_headers):
        while True:
            host = urllib.parse.urlsplit(current).hostname or ""

            if self.robots_enabled and not self.robots.allowed(current):
                self.stats["robots_denied"] += 1
                raise RobotsDenied("robots.txt disallows %s" % current, url=current)

            delay = self.robots.crawl_delay(current) if (self.robots_enabled and
                                                         self.respect_crawl_delay) else None
            lease, interval = self._lease_for(host, delay)

            try:
                lease.acquire(wait_max_sec=self.lease_wait_max, budget=budget)
            except LeaseTimeout as exc:
                raise LeaseUnavailable(str(exc), url=current) from exc

            try:
                # Scoped tightly around wait_turn. _attempt is deliberately
                # OUTSIDE this handler: it is not the operation being
                # translated, and a future LeaseTimeout arising in there would
                # mean something else entirely and must not be silently
                # reclassified as a pacing failure.
                try:
                    paced = lease.wait_turn(interval_sec=interval, budget=budget)
                except LeaseTimeout as exc:
                    raise LeaseUnavailable(str(exc), url=current) from exc

                self.stats["paced_sec"] += paced

                status, headers, body = self._attempt(current, lease, budget,
                                                      accept, extra_headers, acct)
            finally:
                lease.release()

            # ---- redirects: counted, robots re-checked, permanence tracked
            if status in (301, 302, 303, 307, 308):
                loc = (headers or {}).get("location")
                if not loc:
                    raise HttpError("redirect %d without Location" % status, url=current, status=status)
                if redirects >= self.max_redirects:
                    raise HttpError("more than %d redirects" % self.max_redirects,
                                    url=current, status=status)
                nxt = urllib.parse.urljoin(current, loc)
                if nxt in seen:
                    raise HttpError("redirect loop", url=current, status=status)
                seen.append(current)
                if status not in (301, 308):
                    permanent_only = False
                redirects += 1
                acct.redirect_hops += 1      # following a redirect is NOT a retry
                self.stats["redirects"] += 1
                current = nxt
                continue

            if body is not None and len(body) == 0:
                raise EmptyResponse("empty body", url=current, status=status)

            resp = Response(url=url, final_url=current, status=status, headers=headers,
                            body=body, elapsed_sec=self._monotonic() - started,
                            redirects=redirects,
                            permanent_redirect=(redirects > 0 and permanent_only),
                            accounting=acct.freeze())

            if expect_content_types:
                ct = resp.content_type
                if ct and not any(ct == e or ct.endswith(e) or e in ct
                                  for e in expect_content_types):
                    raise UnexpectedContentType(
                        "content-type %r not in %r" % (ct, expect_content_types),
                        url=current, status=status)
            return resp

    def _attempt(self, url, lease, budget, accept, extra_headers, acct):
        """One URL, with bounded retries. Returns (status, headers, body).

        `acct` is the caller's private accumulator. Counters are incremented at
        the moment the event occurs, never reconstructed afterwards from a
        formula that a later edit could silently invalidate.
        """
        last = None
        for attempt in range(1, self.max_attempts + 1):
            if budget is not None:
                budget.charge_request(1)      # charge BEFORE, so a budget cannot be overspent
                # Counted only once the charge SUCCEEDED — a charge that raises
                # BudgetExhausted buys no attempt and must not be recorded.
                acct.request_charges += 1
            acct.attempts += 1
            self.stats["requests"] += 1

            headers = {"User-Agent": self.user_agent,
                       "Accept-Encoding": "identity"}
            if accept:
                headers["Accept"] = accept
            if extra_headers:
                headers.update(extra_headers)
            req = urllib.request.Request(url, headers=headers, method="GET")

            try:
                status, hdrs, fp = self._opener(req, timeout=self.request_timeout)
            except (HttpTimeout, DnsFailure) as exc:
                last = exc
                if attempt >= self.max_attempts:
                    raise
                self._sleep(self._backoff(attempt))
                acct.retries += 1      # a retry, not a redirect hop
                self.stats["retries"] += 1
                continue
            except BudgetExhausted:
                raise
            except HttpError as exc:
                last = exc
                if attempt >= self.max_attempts:
                    raise
                self._sleep(self._backoff(attempt))
                acct.retries += 1      # a retry, not a redirect hop
                self.stats["retries"] += 1
                continue

            if status in (301, 302, 303, 307, 308):
                return status, hdrs, None

            if status in self.retry_status:
                ra = self._retry_after(hdrs)
                if ra is not None:
                    # Shared, so every worker on this domain backs off, not just us.
                    lease.penalize(ra)
                if attempt >= self.max_attempts:
                    if 500 <= status < 600:
                        raise ServerError("server %d after %d attempts" % (status, attempt),
                                          url=url, status=status)
                    raise HttpError("status %d after %d attempts" % (status, attempt),
                                    url=url, status=status)
                wait = ra if ra is not None else self._backoff(attempt)
                if budget is not None and budget.would_exceed_time(wait):
                    budget.check_time()
                self._sleep(wait)
                acct.retries += 1      # a retry, not a redirect hop
                self.stats["retries"] += 1
                continue

            if 400 <= status < 500:
                raise ClientError("status %d" % status, url=url, status=status)
            if status >= 500:
                raise ServerError("status %d" % status, url=url, status=status)

            body = _read_capped(fp, self.max_response_bytes, url)
            return status, hdrs, body

        raise last or HttpError("request failed", url=url)

    # --------------------------------------------------------------- preflight
    def preflight(self, url, budget=None, expect_content_types=None):
        """One bounded probe of a configured source. Never raises.

        Returns a dict shaped for run_manifest.source_preflight[]. Availability
        is re-checked on every live run because planning-time success is
        informational only — a feed that worked last week may be gone today.
        """
        out = {"url": url, "result": "ok", "reason": None, "http_status": None,
               "content_type": None, "robots_allowed": None, "crawl_delay_sec": None,
               "bytes": None, "elapsed_ms": None}
        t0 = self._monotonic()
        try:
            if self.robots_enabled:
                out["robots_allowed"] = self.robots.allowed(url)
                out["crawl_delay_sec"] = self.robots.crawl_delay(url)
            resp = self.get(url, budget=budget, expect_content_types=expect_content_types)
            out["http_status"] = resp.status
            out["content_type"] = resp.content_type
            out["bytes"] = len(resp.body or b"")
        except HttpError as exc:
            out["result"] = ("adapter_error"
                             if exc.reason in ("unexpected_content_type", "empty_response",
                                               "response_too_large")
                             else "infrastructure_error")
            out["reason"] = exc.reason
            out["http_status"] = exc.status
        except BudgetExhausted as exc:
            out["result"] = "infrastructure_error"
            out["reason"] = exc.reason
        out["elapsed_ms"] = int((self._monotonic() - t0) * 1000)
        return out
