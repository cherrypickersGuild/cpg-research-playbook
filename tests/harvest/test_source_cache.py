#!/usr/bin/env python3
"""test_source_cache.py — one logical fetch per request key, success AND failure.

The properties that carry the weight:

  * N lanes racing one key produce exactly ONE fetch_fn call, whether it
    succeeds or fails — a failing source must not become N identical requests;
  * a failure leaves NO CandidatePool row, so the serialized pool stays
    schema-valid (the acquire-then-fail orphan produced five schema errors);
  * DONE is not observable until the complete pool row exists;
  * waiters receive equivalent typed failures, never the owner's exception
    object, which carries traceback state and is unsafe to share;
  * a bounded wait that expires changes nothing — the owner keeps working.

Threads and events, not sleeps. Offline; no network, no adapters, no parsing.
Run via tests/test_taxonomy_source_cache.sh.
"""
import os
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import httpclient as hc, pool as pool_mod, schema  # noqa: E402
from src.harvest import sourcecache as sc                           # noqa: E402
from src.harvest.budget import BudgetExhausted, RequestBudget       # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"
FEED = "https://openai.com/blog/rss.xml"
LANES = ("cell__cases__case-studies",
         "gap__industry__healthcare-life-sciences",
         "gap__business_function__marketing")


def response(status=200, body=b"<rss/>", accounting=None, final_url=FEED):
    return hc.Response(url=FEED, final_url=final_url, status=status,
                       headers={"content-type": "application/rss+xml"},
                       body=body, elapsed_sec=0.01, redirects=0,
                       permanent_redirect=False,
                       accounting=accounting or hc.FetchAccounting(
                           attempts=1, retries=0, redirect_hops=0, request_charges=1))


class Base(unittest.TestCase):
    def setUp(self):
        self.pool = pool_mod.CandidatePool(RUN)
        self.cache = sc.SourceFetchCache(self.pool, clock=lambda: NOW)
        self.key = self.pool.request_key("openai-news", FEED)

    def result(self, resp=None):
        return sc.FetchResult.from_response(self.key, resp or response(), NOW)

    def race(self, fetch_fn, lanes=LANES, timeout=10.0):
        """Run one call per lane simultaneously, released by a barrier."""
        start = threading.Barrier(len(lanes))
        out, errs = {}, {}

        def worker(lane):
            start.wait(timeout=timeout)
            try:
                out[lane] = self.cache.get_or_fetch(
                    self.key, fetch_fn, lane_id=lane, source_id="openai-news",
                    timeout=timeout)
            except Exception as exc:                      # noqa: BLE001
                errs[lane] = exc

        threads = [threading.Thread(target=worker, args=(l,)) for l in lanes]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=timeout + 5)
        return out, errs


class TestOneLogicalFetch(Base):
    def test_1_three_simultaneous_callers_fetch_once(self):
        out, errs = self.race(lambda: self.result())
        self.assertEqual(errs, {})
        self.assertEqual(self.cache.fetch_calls, 1)
        self.assertEqual(len(out), 3)

    def test_2_all_receive_identical_body_and_equivalent_metadata(self):
        out, _ = self.race(lambda: self.result())
        results = list(out.values())
        first = results[0]
        for r in results[1:]:
            self.assertEqual(r.body, first.body)
            self.assertEqual(r.body_sha256, first.body_sha256)
            self.assertEqual(dict(r.headers), dict(first.headers))
            self.assertEqual(r.accounting, first.accounting)
            self.assertEqual(r.status, first.status)

    def test_3_three_simultaneous_callers_on_a_failure_fetch_once(self):
        def boom():
            raise hc.ClientError("gone", url=FEED, status=404)
        out, errs = self.race(boom)
        self.assertEqual(out, {})
        self.assertEqual(self.cache.fetch_calls, 1)
        self.assertEqual(len(errs), 3)

    def test_4_equivalent_typed_failures_as_distinct_instances(self):
        def boom():
            exc = hc.ClientError("gone", url=FEED, status=404)
            exc.accounting = hc.FetchAccounting(attempts=1, request_charges=1)
            raise exc
        _, errs = self.race(boom)
        excs = list(errs.values())
        self.assertEqual(len(excs), 3)
        for exc in excs:
            self.assertIsInstance(exc, hc.ClientError)
            self.assertEqual(exc.reason, "http_4xx")
            self.assertEqual(exc.status, 404)
            self.assertEqual(str(exc), "gone")
        # equivalent semantics, DISTINCT objects
        self.assertEqual(len({id(e) for e in excs}), 3)

    def test_10_one_owner_may_carry_three_attempts(self):
        acct = hc.FetchAccounting(attempts=3, retries=1, redirect_hops=1,
                                  request_charges=3)
        out, _ = self.race(lambda: self.result(response(accounting=acct)))
        self.assertEqual(self.cache.fetch_calls, 1)
        for r in out.values():
            self.assertEqual(r.accounting, acct)
        row = self.pool.sources[self.key]["http_attempts"]
        self.assertEqual((row["attempts"], row["retries"], row["redirect_hops"],
                          row["budget_charged"]), (3, 1, 1, 3))


class TestFailureLeavesNoRow(Base):
    def _fail_with(self, exc):
        def boom():
            raise exc
        with self.assertRaises(type(exc)):
            self.cache.get_or_fetch(self.key, boom, lane_id=LANES[0],
                                    source_id="openai-news")

    def test_5_failure_leaves_no_pool_source_row(self):
        self._fail_with(hc.RobotsDenied("disallowed", url=FEED))
        self.assertEqual(self.pool.sources, {})

    def test_6_pool_serialization_stays_schema_valid_after_failure(self):
        self._fail_with(hc.HttpTimeout("timed out", url=FEED))
        doc = self.pool.to_document(NOW)
        self.assertEqual(doc["sources"], [])
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])

    def test_6b_every_failure_class_leaves_the_document_valid(self):
        for exc in (hc.DnsFailure("dns", url=FEED),
                    hc.ServerError("500", url=FEED, status=500),
                    hc.EmptyResponse("empty", url=FEED, status=200),
                    hc.ResponseTooLarge("too big", url=FEED),
                    hc.UnexpectedContentType("html", url=FEED, status=200),
                    BudgetExhausted("cell:x", "requests", 10, 11),
                    ValueError("an adapter bug")):
            with self.subTest(exc=type(exc).__name__):
                cache = sc.SourceFetchCache(self.pool, clock=lambda: NOW)
                def boom():
                    raise exc
                with self.assertRaises(Exception):
                    cache.get_or_fetch(self.key, boom, lane_id=LANES[0],
                                       source_id="openai-news")
                self.assertEqual(self.pool.sources, {})
                self.assertEqual(
                    schema.validate(self.pool.to_document(NOW),
                                    "candidate_pool.v1.json"), [])

    def test_7_unexpected_exception_becomes_failed_and_releases_waiters(self):
        # NOTE: an ordinary exception inside a LIVE interpreter. This makes no
        # claim about process termination or machine failure — that is Stage 5's
        # persistent store.
        def boom():
            raise ValueError("adapter bug: unparsed item")
        _, errs = self.race(boom)
        self.assertEqual(len(errs), 3, "every waiter must be released")
        for exc in errs.values():
            self.assertIsInstance(exc, sc.InternalFetchError)
            self.assertIn("ValueError", str(exc))
            self.assertIn("adapter bug", str(exc))
        self.assertEqual(self.cache.store.state(self.key), sc.FAILED)
        self.assertEqual(self.pool.sources, {})

    def test_8_no_test_here_claims_process_death_recovery(self):
        import inspect
        text = inspect.getsource(sc).lower()
        self.assertIn("not recovery from process termination", text)
        for claim in ("survives process death", "crash-safe", "crash safe"):
            self.assertNotIn(claim, text)


class TestReuse(Base):
    def test_9_reuse_costs_no_fetch_and_no_budget_charge(self):
        budget = RequestBudget().push("cell", max_requests=5)
        first = self.cache.get_or_fetch(self.key, lambda: self.result(),
                                        lane_id=LANES[0], source_id="openai-news")
        self.assertEqual(self.cache.fetch_calls, 1)
        charged_after_first = budget.usage()[0]["requests"]

        def must_not_run():
            raise AssertionError("a reusing lane must never fetch")

        for lane in LANES[1:]:
            again = self.cache.get_or_fetch(self.key, must_not_run, lane_id=lane,
                                            source_id="openai-news", round_=2)
            self.assertIs(again, first)
            self.assertEqual(again.body, first.body)
        self.assertEqual(self.cache.fetch_calls, 1)
        self.assertEqual(budget.usage()[0]["requests"], charged_after_first)

        snap = self.pool.sources[self.key]
        self.assertEqual(snap["contributing_lanes"], list(LANES))
        self.assertEqual(snap["reused_in_rounds"], [2])
        self.assertEqual(schema.validate(self.pool.to_document(NOW),
                                         "candidate_pool.v1.json"), [])

    def test_11_dv8_accounting_is_copied_exactly_on_success(self):
        acct = hc.FetchAccounting(attempts=2, retries=1, redirect_hops=0,
                                  request_charges=2)
        res = self.cache.get_or_fetch(self.key, lambda: self.result(response(accounting=acct)),
                                      lane_id=LANES[0], source_id="openai-news")
        self.assertIs(res.accounting, acct)
        self.assertEqual(self.pool.sources[self.key]["http_attempts"]["attempts"], 2)

    def test_12_dv8_accounting_is_copied_exactly_on_typed_failure(self):
        acct = hc.FetchAccounting(attempts=3, retries=2, redirect_hops=0,
                                  request_charges=3)

        def boom():
            exc = hc.ServerError("500 after 3", url=FEED, status=500)
            exc.accounting = acct
            raise exc

        _, errs = self.race(boom)
        for exc in errs.values():
            self.assertEqual(exc.accounting, acct)
            self.assertEqual(exc.accounting.retries, 2)

    def test_24_frozen_headers_cannot_be_mutated_by_a_reusing_lane(self):
        res = self.cache.get_or_fetch(self.key, lambda: self.result(),
                                      lane_id=LANES[0], source_id="openai-news")
        with self.assertRaises(TypeError):
            res.headers["content-type"] = "text/html"
        with self.assertRaises(dataclasses_FrozenError()):
            res.status = 500

    def test_after_failure_no_caller_retries_the_source_in_this_run(self):
        def boom():
            raise hc.ServerError("500", url=FEED, status=500)
        with self.assertRaises(hc.ServerError):
            self.cache.get_or_fetch(self.key, boom, lane_id=LANES[0],
                                    source_id="openai-news")
        with self.assertRaises(hc.ServerError):
            self.cache.get_or_fetch(self.key, boom, lane_id=LANES[1],
                                    source_id="openai-news")
        self.assertEqual(self.cache.fetch_calls, 1, "a failure is not retried")
        self.assertEqual(self.pool.sources, {})


def dataclasses_FrozenError():
    import dataclasses
    return dataclasses.FrozenInstanceError


class TestStoreProtocol(Base):
    def test_13_a_wrong_owner_token_cannot_complete(self):
        store = sc.InMemoryStore()
        token = store.claim(self.key)
        self.assertIsNotNone(token)
        self.assertIsNone(store.claim(self.key), "only one claimant wins")
        with self.assertRaises(sc.OwnershipError):
            store.complete(self.key, "not-the-token", self.result())
        self.assertEqual(store.state(self.key), sc.PENDING)

    def test_14_a_wrong_owner_token_cannot_fail(self):
        store = sc.InMemoryStore()
        store.claim(self.key)
        desc = sc.FailureDescriptor.from_exception(hc.HttpTimeout("t", url=FEED))
        with self.assertRaises(sc.OwnershipError):
            store.fail(self.key, "not-the-token", desc)
        self.assertEqual(store.state(self.key), sc.PENDING)

    def test_15_done_is_terminal_and_immutable(self):
        store = sc.InMemoryStore()
        token = store.claim(self.key)
        store.complete(self.key, token, self.result())
        with self.assertRaises(sc.OwnershipError):
            store.complete(self.key, token, self.result())
        with self.assertRaises(sc.OwnershipError):
            store.fail(self.key, token,
                       sc.FailureDescriptor.from_exception(hc.DnsFailure("x")))
        self.assertEqual(store.state(self.key), sc.DONE)

    def test_16_failed_is_terminal_and_immutable(self):
        store = sc.InMemoryStore()
        token = store.claim(self.key)
        desc = sc.FailureDescriptor.from_exception(hc.DnsFailure("x", url=FEED))
        store.fail(self.key, token, desc)
        with self.assertRaises(sc.OwnershipError):
            store.fail(self.key, token, desc)
        with self.assertRaises(sc.OwnershipError):
            store.complete(self.key, token, self.result())
        self.assertEqual(store.state(self.key), sc.FAILED)

    def test_19_a_waiter_never_observes_pending_as_success(self):
        store = sc.InMemoryStore()
        store.claim(self.key)
        state, payload = store.peek(self.key)
        self.assertEqual(state, sc.PENDING)
        self.assertIsNone(payload)
        with self.assertRaises(sc.WaitTimeout):
            store.wait(self.key, timeout=0.05)

    def test_a_failure_descriptor_never_names_a_class_from_a_string(self):
        import inspect
        text = inspect.getsource(sc)
        for banned in ("importlib", "__import__", "eval(", "globals()["):
            self.assertNotIn(banned, text)
        # the rebuild table is a fixed dict keyed by class
        self.assertIn("_CLASS_OF_TYPE", text)
        self.assertTrue(all(isinstance(k, str) for k in sc._CLASS_OF_TYPE))


class TestBoundedWaiting(Base):
    def test_20_21_22_23_timeout_does_not_cancel_the_owner(self):
        release = threading.Event()
        claimed = threading.Event()
        owner_result = {}

        def slow_fetch():
            claimed.set()
            release.wait(timeout=10)
            return self.result()

        def owner():
            owner_result["r"] = self.cache.get_or_fetch(
                self.key, slow_fetch, lane_id=LANES[0], source_id="openai-news")

        t = threading.Thread(target=owner)
        t.start()
        self.assertTrue(claimed.wait(timeout=5))

        # 20/21: a bounded waiter times out, starts no fetch, cancels nothing
        with self.assertRaises(sc.WaitTimeout):
            self.cache.get_or_fetch(self.key, lambda: self.fail("must not fetch"),
                                    lane_id=LANES[1], source_id="openai-news",
                                    timeout=0.05)
        self.assertEqual(self.cache.fetch_calls, 1)
        self.assertEqual(self.cache.store.state(self.key), sc.PENDING)

        # 22: the owner finishes afterwards
        release.set()
        t.join(timeout=10)
        self.assertEqual(self.cache.store.state(self.key), sc.DONE)
        self.assertIn("r", owner_result)

        # 23: a later caller observes the completed result
        later = self.cache.get_or_fetch(self.key, lambda: self.fail("must not fetch"),
                                        lane_id=LANES[2], source_id="openai-news",
                                        round_=3)
        self.assertIs(later, owner_result["r"])
        self.assertEqual(self.cache.fetch_calls, 1)

    def test_a_deadline_is_accepted_as_well_as_a_timeout(self):
        import time as _t
        store = sc.InMemoryStore()
        store.claim(self.key)
        with self.assertRaises(sc.WaitTimeout):
            store.wait(self.key, deadline=_t.monotonic() + 0.05)


class TestAtomicPoolInsertion(Base):
    def test_17_a_complete_row_exists_before_done_is_observable(self):
        observed = {}

        class WatchingStore(sc.InMemoryStore):
            def complete(inner, key, token, result):
                # At the instant DONE is set, the row must already be complete.
                observed["sources"] = dict(self.pool.sources)
                observed["doc_errors"] = schema.validate(
                    self.pool.to_document(NOW), "candidate_pool.v1.json")
                return super().complete(key, token, result)

        cache = sc.SourceFetchCache(self.pool, store=WatchingStore(),
                                    clock=lambda: NOW)
        cache.get_or_fetch(self.key, lambda: self.result(), lane_id=LANES[0],
                           source_id="openai-news")
        row = observed["sources"][self.key]
        for field in ("source_request_key", "source_id", "normalized_url",
                      "adapter_mode", "established_by", "http_attempts",
                      "contributing_lanes"):
            self.assertIsNotNone(row[field], "%s was null when DONE was set" % field)
        self.assertEqual(observed["doc_errors"], [])

    def test_18_injected_insertion_failure_leaves_no_row_and_produces_failed(self):
        class FailingPool(pool_mod.CandidatePool):
            def record_established_source(inner, key, **kw):
                raise pool_mod.PoolError("injected validation failure")

        bad_pool = FailingPool(RUN)
        cache = sc.SourceFetchCache(bad_pool, clock=lambda: NOW)
        with self.assertRaises(Exception) as cm:
            cache.get_or_fetch(self.key, lambda: self.result(), lane_id=LANES[0],
                               source_id="openai-news")
        self.assertIn("injected validation failure", str(cm.exception))
        self.assertEqual(bad_pool.sources, {})
        self.assertEqual(cache.store.state(self.key), sc.FAILED)
        self.assertEqual(schema.validate(bad_pool.to_document(NOW),
                                         "candidate_pool.v1.json"), [])

    def test_insertion_failure_releases_waiters_rather_than_hanging_them(self):
        class FailingPool(pool_mod.CandidatePool):
            def record_established_source(inner, key, **kw):
                raise pool_mod.PoolError("injected")

        self.pool = FailingPool(RUN)
        self.cache = sc.SourceFetchCache(self.pool, clock=lambda: NOW)
        _, errs = self.race(lambda: self.result())
        self.assertEqual(len(errs), 3)
        self.assertEqual(self.pool.sources, {})

    def test_validation_rejects_an_incomplete_row_before_publishing(self):
        bad = [
            dict(established_by="500"),
            dict(normalized_url="not-a-url"),
            dict(source_id=""),
            dict(owner_lane_id=""),
            dict(attempts=-1),
            dict(body_sha256="short"),
        ]
        for override in bad:
            with self.subTest(**override):
                kw = dict(source_id="openai-news", normalized_url=FEED,
                          established_by="200", owner_lane_id=LANES[0],
                          established_at=NOW, body_sha256="0" * 64, attempts=1)
                kw.update(override)
                with self.assertRaises(pool_mod.PoolError):
                    self.pool.record_established_source(self.key, **kw)
                self.assertEqual(self.pool.sources, {}, "nothing may be published")

    def test_duplicate_establishment_is_refused_consistently(self):
        kw = dict(source_id="openai-news", normalized_url=FEED,
                  established_by="200", owner_lane_id=LANES[0], established_at=NOW)
        self.pool.record_established_source(self.key, **kw)
        with self.assertRaises(pool_mod.SnapshotExists):
            self.pool.record_established_source(self.key, **kw)
        self.assertEqual(len(self.pool.sources), 1)

    def test_a_bad_key_is_refused(self):
        with self.assertRaises(pool_mod.PoolError):
            self.pool.record_established_source(
                "not-hex", source_id="x", normalized_url=FEED,
                established_by="200", owner_lane_id=LANES[0])


class TestCompatibility(Base):
    def test_25_actual_owner_and_serialized_designation_stay_distinct(self):
        # The owner is the LAST lane lexically, so a designation that merely
        # echoed the real owner would be caught.
        owner_lane = max(LANES)
        self.cache.get_or_fetch(self.key, lambda: self.result(),
                                lane_id=owner_lane, source_id="openai-news")
        for lane in LANES:
            if lane != owner_lane:
                self.cache.get_or_fetch(self.key, lambda: self.fail("no fetch"),
                                        lane_id=lane, source_id="openai-news",
                                        round_=2)
        self.assertEqual(self.pool.sources[self.key]["owner_lane_id"], owner_lane)
        row = self.pool.to_document(NOW)["sources"][0]
        self.assertEqual(row["designated_owner_lane_id"], min(LANES))
        self.assertNotEqual(row["designated_owner_lane_id"], owner_lane)
        self.assertNotIn("owner_lane_id", row)

    def test_dv7_determinism_survives_cache_written_rows(self):
        import itertools, json
        blobs = set()
        for order in itertools.permutations(LANES):
            pool = pool_mod.CandidatePool(RUN)
            cache = sc.SourceFetchCache(pool, clock=lambda: NOW)
            key = pool.request_key("openai-news", FEED)
            for lane in order:
                cache.get_or_fetch(key, lambda: sc.FetchResult.from_response(
                    key, response(), NOW), lane_id=lane, source_id="openai-news")
            blobs.add(json.dumps(pool.to_document(NOW), sort_keys=True,
                                 separators=(",", ":")))
        self.assertEqual(len(blobs), 1, "DV-7 determinism must survive")

    def test_pool_accounting_is_unchanged_by_this_path(self):
        self.cache.get_or_fetch(self.key, lambda: self.result(),
                                lane_id=LANES[0], source_id="openai-news")
        acct = self.pool.accounting()
        self.assertEqual(acct["source_fetch_owners"], 1)
        self.assertEqual(acct["http_attempts"], 1)
        self.assertEqual(self.pool.budget_charged(), 1)

    def test_keys_identity_and_query_policy_are_untouched(self):
        import inspect
        text = inspect.getsource(sc)
        for needle in ("record_id", "content_id", "identity_url", "canonical_url",
                       "cell_id", "case_facets", "query_order_policy",
                       "sort-distinct-keys-stable"):
            self.assertNotIn(needle, text)
        # the cache never recomputes a key; it is handed one
        self.assertNotIn("source_request_key(", text.replace("FetchResult", ""))

    def test_26_no_adapter_network_or_parsing_implementation_is_introduced(self):
        # Checked on the IMPORT GRAPH, not on raw text: a substring scan matches
        # ordinary prose ("... turns one bad source into N identical requests.")
        # and would either fail spuriously or have to be weakened until it proved
        # nothing.
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(sc))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        banned = {"urllib", "requests", "httpx", "aiohttp", "socket", "http",
                  "feedparser", "xml", "html", "json", "bs4", "lxml"}
        self.assertEqual(imported & banned, set(),
                         "the cache must contain no network or parsing dependency")
        # and it calls no fetching/parsing API of its own — fetch_fn is injected.
        # Only unambiguous names: `get` and `read` are dict and file methods too.
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for name in ("urlopen", "request", "fromstring", "feed", "getresponse"):
            self.assertNotIn(name, called, "unexpected %r call in sourcecache" % name)
        # Stage 4B has since landed, so "these paths must not exist" has served
        # its purpose. What it was really protecting is permanent and stronger:
        # the dependency arrow points ONE WAY. Adapters build on the cache; the
        # cache must never learn about adapters or about fixtures, or the
        # offline test path would stop being the same code as the live one.
        for path in ("src/harvest/adapters", "tests/fixtures/harvest",
                     "src/harvest/fixtures.py", "scripts/harvest/check_fixtures.py"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, path)),
                            "%s is a Stage 4B deliverable and must exist" % path)

        dotted = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dotted.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * (node.level or 0) + (node.module or "")
                dotted.add(prefix)
                dotted.update("%s.%s" % (prefix, a.name) for a in node.names)
        for forbidden in ("adapters", "fixtures"):
            offenders = sorted(d for d in dotted
                               if forbidden in d.replace(".", " ").split())
            self.assertEqual(offenders, [],
                             "sourcecache must not depend on %r (found %r)"
                             % (forbidden, offenders))

        # …and the arrow really does point the other way, so this is a genuine
        # one-way boundary rather than two modules that simply never met.
        adapter_base = os.path.join(ROOT, "src", "harvest", "adapters", "base.py")
        with open(adapter_base, encoding="utf-8") as f:
            adapter_tree = ast.parse(f.read())
        adapter_imports = set()
        for node in ast.walk(adapter_tree):
            if isinstance(node, ast.ImportFrom):
                adapter_imports.update(a.name for a in node.names)
        self.assertIn("sourcecache", adapter_imports,
                      "adapters are expected to depend on SourceFetchCache")


if __name__ == "__main__":
    unittest.main(verbosity=2)
