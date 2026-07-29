#!/usr/bin/env python3
"""test_adapter_concurrency.py — many lanes, one logical fetch, one document.

The properties that only show up under a real race:

  * N lanes discovering the same source issue ONE HTTP request, and the waiters
    parse the retained body rather than fetching it again;
  * a source that failed is not re-fetched by the next lane in the run, and
    leaves no CandidatePool row behind;
  * independent sources still make progress in parallel — the single-fetch
    guarantee must not serialize the whole run;
  * shuffled lane and source completion order produces a byte-identical pool
    document (DV-7), including when the rows were written by adapters.

Real threads released by a barrier, never sleeps standing in for a race.
"""
import glob
import itertools
import json
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import adapters, fixtures, httpclient as hc          # noqa: E402
from src.harvest import pool as pool_mod, schema, sourcecache as sc    # noqa: E402
from src.harvest.adapters import base                                  # noqa: E402
from src.harvest.budget import RequestBudget                           # noqa: E402

NOW = "2026-07-29T00:00:00Z"
RUN = "20260729T000000Z-4bc"
LANES = ("cell__cases__domain-applications",
         "gap__industry__healthcare-life-sciences",
         "gap__business_function__marketing")


def configured_sources():
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "config/harvest/topics/*.json"))):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        for category in doc.get("categories", []):
            out.extend(category.get("sources", []))
    return out


SOURCES = configured_sources()
BY_ID = {s["source_id"]: s for s in SOURCES}
POLICY = {
    "user_agent": "cherry-harvest-test/1.0",
    "budgets": {"request_timeout_sec": 3, "max_response_bytes": 1 << 20,
                "lease_wait_max_sec": 5},
    "retry": {"max_attempts": 2, "backoff_base_sec": 0.0, "jitter_frac": 0.0,
              "retry_on_status": [503], "max_redirects": 3},
    "robots": {"enabled": True, "respect_crawl_delay": False, "cache_ttl_sec": 3600,
               "unavailable_4xx_policy": "allow", "unreachable_5xx_policy": "disallow"},
    "domain_defaults": {"max_concurrency": 4, "min_interval_sec": 0.0,
                        "lease_stale_sec": 120},
    "domain_overrides": {},
}


class CountingOpener:
    """The fixture opener, plus a per-URL call counter and an optional gate."""

    def __init__(self, gate=None, fail_urls=(), fail_status=404):
        self.inner = fixtures.FixtureOpener()
        self.counts = {}
        self.lock = threading.Lock()
        self.gate = gate
        # A STATUS, not a raised exception: every HttpError coming out of an
        # opener is retryable, and a retry is a second HTTP attempt of the SAME
        # logical fetch. A non-retryable 404 keeps physical attempts at 1 so
        # these tests measure logical fetches and nothing else.
        self.fail_urls = set(fail_urls)
        self.fail_status = fail_status

    def __call__(self, req, timeout=20):
        url = req.full_url
        if not url.endswith("/robots.txt"):
            with self.lock:
                self.counts[url] = self.counts.get(url, 0) + 1
            if self.gate is not None:
                self.gate.wait(timeout=10)
            if url in self.fail_urls:
                import io
                return self.fail_status, {}, io.BytesIO(b"gone")
        return self.inner(req, timeout)

    def body_calls(self, url):
        return self.counts.get(url, 0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pool = pool_mod.CandidatePool(RUN)
        self.cache = sc.SourceFetchCache(self.pool, clock=lambda: NOW)

    def client_for(self, opener):
        return hc.HttpClient(POLICY, lease_root=self.tmp, opener=opener,
                             sleep=lambda s: None)

    def race(self, source, lanes=LANES, opener=None, budget=None):
        """One discover() per lane, all released together."""
        opener = opener or CountingOpener()
        client = self.client_for(opener)
        # Warm the robots cache first so the barrier measures the SOURCE fetch,
        # not whichever thread happened to fetch robots.txt.
        client.robots.allowed(source["url"])
        start = threading.Barrier(len(lanes))
        results, errors = {}, {}

        def worker(lane):
            start.wait(timeout=10)
            try:
                results[lane] = adapters.discover(
                    source, cache=self.cache, client=client, budget=budget,
                    lane_id=lane, clock=lambda: NOW)
            except Exception as exc:                       # noqa: BLE001
                errors[lane] = exc

        threads = [threading.Thread(target=worker, args=(l,)) for l in lanes]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        return opener, results, errors


class TestSharedSourceFetch(Base):
    def test_three_lanes_on_one_source_cause_one_logical_fetch(self):
        source = BY_ID["aws-ml-blog"]
        opener, results, errors = self.race(source)
        self.assertEqual(errors, {})
        self.assertEqual(len(results), 3)
        self.assertEqual(opener.body_calls(source["url"]), 1,
                         "the source body must be fetched exactly once")
        self.assertEqual(len(self.pool.sources), 1)

    def test_waiters_parse_the_retained_body_and_get_equal_candidates(self):
        source = BY_ID["aws-ml-blog"]
        _, results, _ = self.race(source)
        signatures = {tuple((c.target_url, c.title, c.position)
                            for c in r.candidates) for r in results.values()}
        self.assertEqual(len(signatures), 1, "every lane saw the same body")
        for result in results.values():
            self.assertEqual(result.result, base.RESULT_OK)
            self.assertTrue(result.candidates)

    def test_reuse_adds_no_attempt_and_no_request_charge(self):
        source = BY_ID["aws-ml-blog"]
        budget = RequestBudget().push("cell", max_requests=20)
        opener, results, _ = self.race(source, budget=budget)
        self.assertEqual(opener.body_calls(source["url"]), 1)
        self.assertEqual(budget.usage()[0]["requests"], 1,
                         "only the owner's single attempt is charged")
        snapshot = list(self.pool.sources.values())[0]
        self.assertEqual(snapshot["http_attempts"]["attempts"], 1)
        self.assertEqual(snapshot["http_attempts"]["budget_charged"], 1)
        for result in results.values():
            self.assertEqual(result.accounting.attempts, 1)

    def test_every_contributing_lane_is_preserved_on_the_snapshot(self):
        source = BY_ID["aws-ml-blog"]
        self.race(source)
        snapshot = list(self.pool.sources.values())[0]
        self.assertEqual(sorted(snapshot["contributing_lanes"]), sorted(LANES))

    def test_a_shared_failure_is_not_refetched_and_leaves_no_pool_row(self):
        source = BY_ID["nvidia-blog"]
        opener = CountingOpener(fail_urls={source["url"]})
        _, results, errors = self.race(source, opener=opener)
        self.assertEqual(errors, {}, "a failure is an AdapterResult, not a raise")
        self.assertEqual(self.cache.fetch_calls, 1,
                         "one LOGICAL fetch even when it fails")
        self.assertEqual(opener.body_calls(source["url"]), 1,
                         "a non-retryable 404 is one physical attempt too")
        for result in results.values():
            self.assertEqual(result.result, base.RESULT_INFRASTRUCTURE_ERROR)
            self.assertEqual(result.reason, "http_4xx")
            self.assertEqual(result.status, 404)
        self.assertEqual(self.pool.sources, {})
        self.assertEqual(schema.validate(self.pool.to_document(NOW),
                                         "candidate_pool.v1.json"), [])

    def test_a_terminal_entry_is_not_re_entered_by_a_later_lane(self):
        source = BY_ID["nvidia-blog"]
        opener = CountingOpener(fail_urls={source["url"]})
        client = self.client_for(opener)
        for lane in LANES:
            result = adapters.discover(source, cache=self.cache, client=client,
                                       lane_id=lane, clock=lambda: NOW)
            self.assertEqual(result.reason, "http_4xx")
        self.assertEqual(self.cache.fetch_calls, 1,
                         "the terminal FAILED entry is never re-entered")
        self.assertEqual(opener.body_calls(source["url"]), 1)

    def test_independent_sources_progress_independently(self):
        # A barrier of 2 that only releases when BOTH sources are in flight:
        # if the cache serialized unrelated keys this would deadlock and the
        # join would time out.
        gate = threading.Barrier(2, timeout=10)
        opener = CountingOpener(gate=gate)
        client = self.client_for(opener)
        first, second = BY_ID["aws-ml-blog"], BY_ID["nvidia-blog"]
        for source in (first, second):
            client.robots.allowed(source["url"])
        out = {}

        def worker(source, lane):
            out[lane] = adapters.discover(source, cache=self.cache, client=client,
                                          lane_id=lane, clock=lambda: NOW)

        threads = [threading.Thread(target=worker, args=(first, "lane-a")),
                   threading.Thread(target=worker, args=(second, "lane-b"))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(len(out), 2, "both sources completed — no deadlock")
        for result in out.values():
            self.assertEqual(result.result, base.RESULT_OK)
        self.assertEqual(len(self.pool.sources), 2)


class TestDeterministicPoolDocument(Base):
    SOURCES_UNDER_TEST = ("aws-ml-blog", "nvidia-blog", "hn-algolia")

    def _run(self, lane_order, source_order):
        pool = pool_mod.CandidatePool(RUN)
        cache = sc.SourceFetchCache(pool, clock=lambda: NOW)
        client = self.client_for(CountingOpener())
        for source_id in source_order:
            source = BY_ID[source_id]
            for lane in lane_order:
                result = adapters.discover(source, cache=cache, client=client,
                                           lane_id=lane, clock=lambda: NOW)
                for candidate in result.candidates:
                    pool.add_candidate(candidate.target_url, lane)
        return json.dumps(pool.to_document(NOW), sort_keys=True,
                          separators=(",", ":")), pool

    def test_shuffled_lane_and_source_order_gives_one_byte_identical_document(self):
        blobs = set()
        for lane_order in itertools.permutations(LANES):
            for source_order in itertools.permutations(self.SOURCES_UNDER_TEST):
                blob, _ = self._run(list(lane_order), list(source_order))
                blobs.add(blob)
        self.assertEqual(len(blobs), 1,
                         "the pool document must not depend on completion order")

    def test_that_document_is_schema_valid(self):
        _, pool = self._run(list(LANES), list(self.SOURCES_UNDER_TEST))
        doc = pool.to_document(NOW)
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])
        self.assertEqual(len(doc["sources"]), len(self.SOURCES_UNDER_TEST))

    def test_no_caller_derives_per_fetch_accounting_from_shared_stats(self):
        import inspect
        from src.harvest.adapters import feed as feed_mod, jsonapi as j, seed as s
        for module in (base, feed_mod, j, s, adapters, sc):
            text = inspect.getsource(module)
            for banned in ('stats["requests"]', "stats['requests']",
                           'stats["retries"]', "stats['retries']"):
                self.assertNotIn(banned, text, module.__name__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
