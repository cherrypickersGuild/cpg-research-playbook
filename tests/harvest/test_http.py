#!/usr/bin/env python3
"""test_http.py — robots, redirects, timeouts, retries, Retry-After, byte caps.

Fully mocked: a scripted opener stands in for the network, following the
MockOpener pattern already used by tests/test_github_meta.py. No request leaves
the machine, and no test sleeps for real.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import httpclient as hc  # noqa: E402
from src.harvest.budget import RequestBudget, BudgetExhausted  # noqa: E402


class Scripted:
    """Opener returning canned responses keyed by URL.

    Each entry is (status, headers, body) or an Exception to raise. A list of
    entries is consumed one per call, so retry behaviour can be scripted.
    """

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=20):
        url = req.full_url
        self.calls.append(url)
        entry = self.routes.get(url)
        if entry is None:
            return 404, {}, b"not found"
        if isinstance(entry, list):
            entry = entry.pop(0) if len(entry) > 1 else entry[0]
        if isinstance(entry, Exception):
            raise entry
        status, headers, body = entry
        return status, {k.lower(): v for k, v in headers.items()}, body


def policy(**over):
    p = {
        "user_agent": "test-agent",
        "budgets": {"connect_timeout_sec": 1, "read_timeout_sec": 2,
                    "request_timeout_sec": 3, "max_response_bytes": 1024,
                    "lease_wait_max_sec": 2},
        "retry": {"max_attempts": 3, "backoff_base_sec": 0.0, "backoff_multiplier": 1.0,
                  "jitter_frac": 0.0, "retry_on_status": [429, 500, 502, 503, 504],
                  "max_redirects": 3},
        "robots": {"enabled": True, "respect_crawl_delay": True, "cache_ttl_sec": 3600,
                   "unavailable_4xx_policy": "allow", "unreachable_5xx_policy": "disallow"},
        "domain_defaults": {"max_concurrency": 4, "min_interval_sec": 0.0,
                            "lease_stale_sec": 120},
        "domain_overrides": {},
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(p.get(k), dict):
            p[k].update(v)
        else:
            p[k] = v
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.slept = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, routes, pol=None, **kw):
        self.opener = Scripted(routes)
        return hc.HttpClient(pol or policy(), lease_root=self.tmp,
                             opener=self.opener, sleep=self.slept.append, **kw)

    @staticmethod
    def robots(body="User-agent: *\nAllow: /\n", status=200):
        return (status, {"content-type": "text/plain"}, body.encode())


class TestRobotsRulesRFC9309(unittest.TestCase):
    """Longest-match-wins, not first-match-in-order.

    urllib.robotparser implements the 1996 draft's first-match rule. These cases
    pin the RFC 9309 behaviour, including the one where the stdlib would be
    UNSAFE (permitting a path the publisher disallowed).
    """

    def test_longest_match_wins_allow_after_disallow(self):
        r = hc.RobotsRules("User-agent: *\nDisallow: /\nAllow: /ok\n")
        self.assertTrue(r.allowed("bot", "/ok"))
        self.assertFalse(r.allowed("bot", "/other"))

    def test_longest_match_wins_disallow_after_allow_UNSAFE_for_stdlib(self):
        # First-match would return ALLOW for /private/x because `Allow: /` is
        # listed first. RFC 9309 says the longer `/private` rule wins.
        r = hc.RobotsRules("User-agent: *\nAllow: /\nDisallow: /private\n")
        self.assertFalse(r.allowed("bot", "/private/x"))
        self.assertTrue(r.allowed("bot", "/public/x"))

    def test_allow_wins_equal_length_tie(self):
        r = hc.RobotsRules("User-agent: *\nDisallow: /a\nAllow: /a\n")
        self.assertTrue(r.allowed("bot", "/a"))

    def test_empty_disallow_means_allow_all(self):
        r = hc.RobotsRules("User-agent: *\nDisallow:\n")
        self.assertTrue(r.allowed("bot", "/anything"))

    def test_wildcards(self):
        r = hc.RobotsRules("User-agent: *\nDisallow: /*.pdf$\nAllow: /\n")
        self.assertFalse(r.allowed("bot", "/docs/a.pdf"))
        self.assertTrue(r.allowed("bot", "/docs/a.pdf?x=1"))   # $ anchors the end
        self.assertTrue(r.allowed("bot", "/docs/a.html"))

    def test_star_in_middle(self):
        r = hc.RobotsRules("User-agent: *\nDisallow: /a/*/secret\n")
        self.assertFalse(r.allowed("bot", "/a/b/secret"))
        self.assertTrue(r.allowed("bot", "/a/b/public"))

    def test_specific_agent_group_beats_star(self):
        r = hc.RobotsRules(
            "User-agent: *\nDisallow: /\n\n"
            "User-agent: cherry-harvest\nAllow: /\n")
        self.assertTrue(r.allowed("cherry-harvest/1.0", "/a"))
        self.assertFalse(r.allowed("other-bot", "/a"))

    def test_multiple_agents_share_a_group(self):
        r = hc.RobotsRules("User-agent: a\nUser-agent: b\nDisallow: /x\n")
        self.assertFalse(r.allowed("a", "/x"))
        self.assertFalse(r.allowed("b", "/x"))

    def test_crawl_delay_per_group(self):
        r = hc.RobotsRules(
            "User-agent: *\nCrawl-delay: 15\nAllow: /\n\n"
            "User-agent: fastbot\nCrawl-delay: 1\nAllow: /\n")
        self.assertEqual(r.crawl_delay("anything"), 15)
        self.assertEqual(r.crawl_delay("fastbot"), 1)

    def test_comments_and_blank_lines_ignored(self):
        r = hc.RobotsRules("# hello\n\nUser-agent: *  # all\nDisallow: /x  # nope\n")
        self.assertFalse(r.allowed("bot", "/x"))

    def test_no_applicable_group_allows(self):
        r = hc.RobotsRules("User-agent: someoneelse\nDisallow: /\n")
        self.assertTrue(r.allowed("bot", "/a"))

    def test_real_arxiv_shape(self):
        # arxiv.org lists Allow lines before Disallow lines; both orderings must
        # produce the documented result.
        r = hc.RobotsRules(
            "User-agent: *\nCrawl-delay: 15\n"
            "Allow: /abs\nAllow: /pdf\n"
            "Disallow: /find\nDisallow: /src\n")
        self.assertTrue(r.allowed("bot", "/abs/2507.19457"))
        self.assertFalse(r.allowed("bot", "/find?query=x"))
        self.assertEqual(r.crawl_delay("bot"), 15)


class TestRobots(Base):
    def test_disallow_is_respected(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots("User-agent: *\nDisallow: /\n"),
            "https://x.test/a": (200, {}, b"body"),
        })
        with self.assertRaises(hc.RobotsDenied) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "robots_denied")
        self.assertNotIn("https://x.test/a", self.opener.calls)

    def test_allow_specific_path(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots("User-agent: *\nDisallow: /\nAllow: /ok\n"),
            "https://x.test/ok": (200, {}, b"body"),
        })
        self.assertEqual(c.get("https://x.test/ok").status, 200)

    def test_404_robots_means_allow_all_rfc9309(self):
        c = self.client({
            "https://x.test/robots.txt": (404, {}, b""),
            "https://x.test/a": (200, {}, b"body"),
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)

    def test_5xx_robots_means_disallow_rfc9309(self):
        # "Unreachable" -> assume complete disallow. Getting this backwards is
        # the difference between skipping a site and hammering one asking us to stop.
        c = self.client({
            "https://x.test/robots.txt": (503, {}, b""),
            "https://x.test/a": (200, {}, b"body"),
        })
        with self.assertRaises(hc.RobotsDenied):
            c.get("https://x.test/a")

    def test_crawl_delay_is_read(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots("User-agent: *\nCrawl-delay: 15\nAllow: /\n"),
            "https://x.test/a": (200, {}, b"body"),
        })
        self.assertEqual(c.robots.crawl_delay("https://x.test/a"), 15)

    def test_robots_cached_per_origin(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b"a"),
            "https://x.test/b": (200, {}, b"b"),
        })
        c.get("https://x.test/a")
        c.get("https://x.test/b")
        self.assertEqual(self.opener.calls.count("https://x.test/robots.txt"), 1)

    def test_robots_can_be_disabled(self):
        pol = policy(robots={"enabled": False})
        c = self.client({"https://x.test/a": (200, {}, b"body")}, pol)
        self.assertEqual(c.get("https://x.test/a").status, 200)
        self.assertNotIn("https://x.test/robots.txt", self.opener.calls)


class TestRedirects(Base):
    def _routes(self, status):
        return {
            "https://x.test/robots.txt": self.robots(),
            "https://y.test/robots.txt": self.robots(),
            "https://x.test/a": (status, {"location": "https://x.test/b"}, b""),
            "https://x.test/b": (200, {}, b"final"),
            "https://y.test/a": (200, {}, b"cross"),
        }

    def test_permanent_redirect_flagged(self):
        for status in (301, 308):
            c = self.client(self._routes(status))
            r = c.get("https://x.test/a")
            self.assertEqual(r.final_url, "https://x.test/b")
            self.assertTrue(r.permanent_redirect, status)

    def test_temporary_redirect_not_flagged(self):
        # A 302/307 must never be allowed to rewrite an immutable identity.
        for status in (302, 303, 307):
            c = self.client(self._routes(status))
            r = c.get("https://x.test/a")
            self.assertFalse(r.permanent_redirect, status)

    def test_mixed_chain_is_not_permanent(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (301, {"location": "https://x.test/b"}, b""),
            "https://x.test/b": (302, {"location": "https://x.test/c"}, b""),
            "https://x.test/c": (200, {}, b"final"),
        })
        r = c.get("https://x.test/a")
        self.assertEqual(r.redirects, 2)
        self.assertFalse(r.permanent_redirect)

    def test_redirect_cap(self):
        routes = {"https://x.test/robots.txt": self.robots()}
        for i in range(8):
            routes["https://x.test/%d" % i] = (301, {"location": "https://x.test/%d" % (i + 1)}, b"")
        c = self.client(routes)
        with self.assertRaises(hc.HttpError) as cm:
            c.get("https://x.test/0")
        self.assertIn("redirects", str(cm.exception))

    def test_redirect_loop_detected(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (301, {"location": "https://x.test/b"}, b""),
            "https://x.test/b": (301, {"location": "https://x.test/a"}, b""),
        })
        with self.assertRaises(hc.HttpError) as cm:
            c.get("https://x.test/a")
        self.assertIn("loop", str(cm.exception))

    def test_robots_rechecked_on_host_change(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://y.test/robots.txt": self.robots("User-agent: *\nDisallow: /\n"),
            "https://x.test/a": (301, {"location": "https://y.test/a"}, b""),
            "https://y.test/a": (200, {}, b"should not be fetched"),
        })
        with self.assertRaises(hc.RobotsDenied):
            c.get("https://x.test/a")
        self.assertNotIn("https://y.test/a", self.opener.calls)

    def test_redirect_without_location(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (301, {}, b""),
        })
        with self.assertRaises(hc.HttpError):
            c.get("https://x.test/a")


class TestRetries(Base):
    def test_retries_then_succeeds(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(503, {}, b""), (503, {}, b""), (200, {}, b"ok")],
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)
        self.assertEqual(self.opener.calls.count("https://x.test/a"), 3)

    def test_gives_up_after_max_attempts(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (500, {}, b""),
        })
        with self.assertRaises(hc.ServerError) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "http_5xx")
        self.assertEqual(self.opener.calls.count("https://x.test/a"), 3)

    def test_4xx_is_not_retried(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (404, {}, b""),
        })
        with self.assertRaises(hc.ClientError):
            c.get("https://x.test/a")
        self.assertEqual(self.opener.calls.count("https://x.test/a"), 1)

    def test_timeout_retried_then_raised(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": hc.HttpTimeout("timed out"),
        })
        with self.assertRaises(hc.HttpTimeout) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "http_timeout")

    def test_dns_failure_typed(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": hc.DnsFailure("no such host"),
        })
        with self.assertRaises(hc.DnsFailure) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "dns_failure")

    def test_backoff_has_jitter(self):
        import random
        pol = policy(retry={"backoff_base_sec": 1.0, "jitter_frac": 0.25})
        c = self.client({"https://x.test/robots.txt": self.robots(),
                         "https://x.test/a": (500, {}, b"")}, pol,
                        rng=random.Random(7))
        with self.assertRaises(hc.ServerError):
            c.get("https://x.test/a")
        self.assertTrue(self.slept)
        for s in self.slept:
            self.assertGreater(s, 0.0)
            self.assertLess(s, 2.0)
        self.assertNotEqual(len(set(self.slept)), 1, "jitter should vary the waits")


class TestRetryAfter(Base):
    def test_retry_after_seconds_respected(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(429, {"retry-after": "7"}, b""), (200, {}, b"ok")],
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)
        self.assertIn(7.0, self.slept)

    def test_retry_after_penalizes_the_shared_gate(self):
        # The gate is on disk so EVERY worker on this domain backs off, which is
        # the whole reason the lease is not in-process.
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(503, {"retry-after": "5"}, b""), (200, {}, b"ok")],
        })
        c.get("https://x.test/a")
        gate = os.path.join(self.tmp, "x.test", "next_allowed_at")
        self.assertTrue(os.path.exists(gate))
        with open(gate) as f:
            self.assertGreater(float(f.read().strip()), 0.0)

    def test_retry_after_http_date(self):
        import email.utils, datetime
        when = email.utils.format_datetime(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=4))
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(429, {"retry-after": when}, b""), (200, {}, b"ok")],
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)
        self.assertTrue(any(2.0 <= s <= 5.0 for s in self.slept), self.slept)

    def test_garbage_retry_after_falls_back_to_backoff(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(429, {"retry-after": "soon"}, b""), (200, {}, b"ok")],
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)


class TestBodyHandling(Base):
    def test_byte_cap_enforced(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b"x" * 2048),      # cap is 1024
        })
        with self.assertRaises(hc.ResponseTooLarge) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "response_too_large")

    def test_at_the_cap_is_allowed(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b"x" * 1024),
        })
        self.assertEqual(len(c.get("https://x.test/a").body), 1024)

    def test_empty_body_is_typed(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b""),
        })
        with self.assertRaises(hc.EmptyResponse) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "empty_response")

    def test_content_type_expectation(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {"content-type": "text/html"}, b"<html>"),
        })
        with self.assertRaises(hc.UnexpectedContentType) as cm:
            c.get("https://x.test/a", expect_content_types=["xml"])
        self.assertEqual(cm.exception.reason, "unexpected_content_type")

    def test_content_hash_computed(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b"hello"),
        })
        r = c.get("https://x.test/a")
        self.assertRegex(r.content_hash, r"^[0-9a-f]{64}$")

    def test_charset_decoding(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {"content-type": "text/html; charset=latin-1"},
                                 "café".encode("latin-1")),
        })
        self.assertIn("café", c.get("https://x.test/a").text)


class TestBudgetIntegration(Base):
    def test_every_attempt_charges(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (500, {}, b""),
        })
        b = RequestBudget()
        b.push("cell", max_requests=10)
        with self.assertRaises(hc.ServerError):
            c.get("https://x.test/a", budget=b)
        self.assertEqual(b.usage()[0]["requests"], 3)   # 3 attempts, not 1

    def test_redirect_hops_charge(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (301, {"location": "https://x.test/b"}, b""),
            "https://x.test/b": (301, {"location": "https://x.test/c"}, b""),
            "https://x.test/c": (200, {}, b"end"),
        })
        b = RequestBudget()
        b.push("cell", max_requests=10)
        c.get("https://x.test/a", budget=b)
        self.assertEqual(b.usage()[0]["requests"], 3)

    def test_budget_exhaustion_propagates(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (200, {}, b"ok"),
        })
        b = RequestBudget()
        b.push("cell", max_requests=1)
        c.get("https://x.test/a", budget=b)
        with self.assertRaises(BudgetExhausted):
            c.get("https://x.test/a", budget=b)


class TestPreflight(Base):
    def test_ok(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/feed": (200, {"content-type": "application/rss+xml"}, b"<rss/>"),
        })
        out = c.preflight("https://x.test/feed")
        self.assertEqual(out["result"], "ok")
        self.assertEqual(out["http_status"], 200)
        self.assertTrue(out["robots_allowed"])
        self.assertIsNotNone(out["elapsed_ms"])

    def test_never_raises_and_classifies(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots("User-agent: *\nDisallow: /\n"),
            "https://x.test/feed": (200, {}, b"<rss/>"),
        })
        out = c.preflight("https://x.test/feed")
        self.assertEqual(out["result"], "infrastructure_error")
        self.assertEqual(out["reason"], "robots_denied")

    def test_adapter_error_vs_infrastructure_error(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/feed": (200, {"content-type": "text/html"}, b"<html>"),
        })
        out = c.preflight("https://x.test/feed", expect_content_types=["xml"])
        self.assertEqual(out["result"], "adapter_error")
        self.assertEqual(out["reason"], "unexpected_content_type")


class TestClientErrorIsClassifiedAs4xx(Base):
    """A non-retryable 4xx is `http_4xx`, never the server-error bucket.

    A dead configured feed answers 404. Reporting that as `http_5xx` sends an
    operator hunting an outage that never happened, and the manifest's
    infrastructure_error vocabulary then describes the wrong failure class. The
    numeric status was always carried; the reason string was simply wrong.
    """

    def _get(self, status):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (status, {}, b""),
        })
        with self.assertRaises(hc.ClientError) as cm:
            c.get("https://x.test/a")
        return cm.exception

    def test_404_is_http_4xx_with_status_preserved(self):
        exc = self._get(404)
        self.assertEqual(exc.reason, "http_4xx")
        self.assertEqual(exc.status, 404)

    def test_401_and_403_are_http_4xx_with_status_preserved(self):
        for status in (401, 403):
            with self.subTest(status=status):
                exc = self._get(status)
                self.assertEqual(exc.reason, "http_4xx")
                self.assertEqual(exc.status, status)

    def test_robots_denial_stays_robots_denied(self):
        # Raised before any response exists, so it can never be reclassified
        # as a status-bearing 4xx.
        c = self.client({
            "https://x.test/robots.txt": self.robots("User-agent: *\nDisallow: /\n"),
            "https://x.test/a": (200, {}, b"ok"),
        })
        with self.assertRaises(hc.RobotsDenied) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "robots_denied")
        self.assertNotEqual(cm.exception.reason, "http_4xx")

    def test_server_failure_stays_http_5xx(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (500, {}, b""),
        })
        with self.assertRaises(hc.ServerError) as cm:
            c.get("https://x.test/a")
        self.assertEqual(cm.exception.reason, "http_5xx")
        self.assertEqual(cm.exception.status, 500)

    def test_retryable_4xx_behaviour_is_unchanged(self):
        # 429 is in retry_on_status, so it is NOT a ClientError: it is retried,
        # and on exhaustion raised as the generic HttpError, which keeps
        # http_5xx. This correction deliberately does not touch that path.
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": (429, {}, b""),
        })
        with self.assertRaises(hc.HttpError) as cm:
            c.get("https://x.test/a")
        self.assertNotIsInstance(cm.exception, hc.ClientError)
        self.assertEqual(cm.exception.reason, "http_5xx")
        self.assertEqual(cm.exception.status, 429)
        self.assertEqual(self.opener.calls.count("https://x.test/a"), 3)

    def test_retryable_4xx_that_recovers_still_succeeds(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/a": [(429, {}, b""), (200, {}, b"ok")],
        })
        self.assertEqual(c.get("https://x.test/a").status, 200)
        self.assertEqual(self.opener.calls.count("https://x.test/a"), 2)

    def test_http_4xx_is_never_used_for_a_statusless_error(self):
        # The reason names an HTTP status class, so it must not leak onto
        # transport failures that never received a response.
        for exc_cls in (hc.HttpTimeout, hc.DnsFailure, hc.RobotsDenied,
                        hc.ResponseTooLarge, hc.EmptyResponse,
                        hc.UnexpectedContentType, hc.ServerError, hc.HttpError):
            with self.subTest(cls=exc_cls.__name__):
                self.assertNotEqual(exc_cls.reason, "http_4xx")
        self.assertEqual(hc.ClientError.reason, "http_4xx")

    def test_preflight_reports_a_404_as_infrastructure_http_4xx(self):
        c = self.client({
            "https://x.test/robots.txt": self.robots(),
            "https://x.test/feed": (404, {}, b""),
        })
        out = c.preflight("https://x.test/feed")
        self.assertEqual(out["result"], "infrastructure_error")
        self.assertEqual(out["reason"], "http_4xx")
        self.assertEqual(out["http_status"], 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
