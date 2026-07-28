#!/usr/bin/env python3
"""test_pool.py — request keys, shared snapshots, and ownership accounting.

Three properties carry the weight:

  * a source_request_key is stable across runs and sensitive to everything that
    genuinely changes the request — INCLUDING the canonicalization config
    version, without which a config bump would silently change every key;
  * the run-scoped source snapshot is immutable: established once by a 200 or a
    304, reused by every later lane and round, and never revalidated mid-run;
  * logical ownership (one owner) and HTTP attempts (retries, redirect hops) are
    counted separately, so a redirect plus a retry is still ONE logical fetch.

Run via tests/test_taxonomy_pool.sh.
"""
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import pool, request_key as rk, schema      # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"
FEED = "https://openai.com/blog/rss.xml"


def key(**over):
    kw = dict(source_id="openai-news", url=FEED, adapter="feed",
              adapter_mode="default", method="GET")
    kw.update(over)
    return rk.source_request_key(**kw)


class TestRequestKeyStability(unittest.TestCase):
    def test_shape_and_determinism(self):
        k = key()
        self.assertRegex(k, r"^[0-9a-f]{16}$")
        self.assertEqual(k, key())

    def test_tracking_parameters_do_not_change_the_key(self):
        self.assertEqual(key(url=FEED + "?utm_source=twitter"), key(url=FEED))

    def test_a_different_source_id_is_a_different_request(self):
        self.assertNotEqual(key(source_id="other-news"), key())

    def test_adapter_mode_separates_index_from_record(self):
        self.assertNotEqual(key(adapter_mode="index"), key(adapter_mode="record"))

    def test_method_and_body_are_significant(self):
        self.assertNotEqual(key(method="POST"), key())
        self.assertNotEqual(key(method="POST", body='{"q":1}'),
                            key(method="POST", body='{"q":2}'))

    def test_only_allowlisted_headers_matter(self):
        self.assertEqual(key(headers={"User-Agent": "cherry-harvest/1.0"}), key())
        self.assertEqual(key(headers={"Authorization": "Bearer secret"}), key())
        self.assertNotEqual(key(headers={"Accept": "application/json"}), key())

    def test_no_secret_can_reach_the_key_material(self):
        self.assertNotIn("authorization", [h.lower() for h in rk.SIGNIFICANT_HEADERS])
        self.assertNotIn("user-agent", [h.lower() for h in rk.SIGNIFICANT_HEADERS])

    def test_canonicalization_version_is_in_the_key(self):
        # Without this, bumping canonicalization.v1.json would silently change
        # every key and two runs would disagree about what was already fetched.
        import tempfile
        tmp = tempfile.mkdtemp(prefix="canonver_")
        path = os.path.join(tmp, "canonicalization.v1.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"config_version": 99}, f)
        rk._CANON_CACHE.clear()
        try:
            self.assertNotEqual(key(canonicalization_path=path), key())
        finally:
            rk._CANON_CACHE.clear()

    def test_one_source_may_produce_several_keys(self):
        # An API queried by a broad lane and by a gap lane is two requests and
        # two fetches, correctly.
        broad = key(url="https://api.x.com/search?q=ai", adapter="jsonapi")
        gap = key(url="https://api.x.com/search?q=ai+hospital", adapter="jsonapi")
        self.assertNotEqual(broad, gap)


class TestQueryOrderPolicy(unittest.TestCase):
    """Normalization is opt-in per request. Adapter class authorizes nothing.

    Reordering a query merges two requests into one logical owner and one
    immutable run-scoped snapshot, so a wrong guess about insignificance
    silently discards a response. The default therefore preserves everything,
    and the one opt-in policy is deliberately narrow.
    """

    def test_default_policy_is_preserve(self):
        import inspect
        p = inspect.signature(rk.source_request_key).parameters["query_order_policy"]
        self.assertEqual(p.default, rk.QUERY_ORDER_PRESERVE)
        self.assertEqual(p.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_adapter_class_alone_never_reorders_anything(self):
        # 1 — jsonapi must behave exactly like every other adapter by default.
        for pair in (("https://x.com/api?b=2&a=1", "https://x.com/api?a=1&b=2"),
                     ("https://x.com/api?tag=b&tag=a", "https://x.com/api?tag=a&tag=b")):
            for adapter in ("feed", "sitemap", "seed", "model_search", "jsonapi"):
                self.assertNotEqual(key(url=pair[0], adapter=adapter),
                                    key(url=pair[1], adapter=adapter), adapter)

    def test_no_adapter_wide_ordering_constant_survives(self):
        self.assertFalse(hasattr(rk, "ORDER_INSIGNIFICANT_ADAPTERS"))
        self.assertEqual(set(rk.QUERY_ORDER_POLICIES),
                         {"preserve", "sort-distinct-keys-stable"})

    def test_adapter_mode_never_authorizes_reordering(self):
        for mode in ("default", "index", "record", "api"):
            self.assertNotEqual(key(url="https://x.com/api?b=2&a=1", adapter_mode=mode),
                                key(url="https://x.com/api?a=1&b=2", adapter_mode=mode), mode)

    def test_2_preserve_distinguishes_distinct_key_order(self):
        self.assertNotEqual(key(url="https://x.com/api?a=1&b=2"),
                            key(url="https://x.com/api?b=2&a=1"))

    def test_3_preserve_distinguishes_repeated_key_value_order(self):
        self.assertNotEqual(key(url="https://x.com/api?tag=b&tag=a"),
                            key(url="https://x.com/api?tag=a&tag=b"))

    def test_4_multiplicity_is_preserved(self):
        self.assertNotEqual(key(url="https://x.com/api?tag=a&tag=a"),
                            key(url="https://x.com/api?tag=a"))

    def test_5_sort_distinct_keys_stable_collapses_only_distinct_key_reorder(self):
        pol = rk.QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE
        self.assertEqual(key(url="https://x.com/api?a=1&b=2", query_order_policy=pol),
                         key(url="https://x.com/api?b=2&a=1", query_order_policy=pol))

    def test_6_repeated_key_value_order_stays_significant_under_the_policy(self):
        pol = rk.QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE
        self.assertNotEqual(key(url="https://x.com/api?tag=b&tag=a", query_order_policy=pol),
                            key(url="https://x.com/api?tag=a&tag=b", query_order_policy=pol))

    def test_7_interleaved_repeats_keep_their_same_key_value_order(self):
        pol = rk.QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE
        # ?tag=b&page=1&tag=a normalizes to tag=b, tag=a, page=1 — the two `tag`
        # values keep their given order and are NOT swapped to a, b.
        self.assertEqual(key(url="https://x.com/api?tag=b&page=1&tag=a",
                             query_order_policy=pol),
                         key(url="https://x.com/api?tag=b&tag=a&page=1",
                             query_order_policy=pol))
        self.assertNotEqual(key(url="https://x.com/api?tag=b&page=1&tag=a",
                                query_order_policy=pol),
                            key(url="https://x.com/api?tag=a&page=1&tag=b",
                                query_order_policy=pol))

    def test_8_blank_and_duplicate_blank_values_stay_represented(self):
        for pol in rk.QUERY_ORDER_POLICIES:
            self.assertNotEqual(key(url="https://x.com/api?a=", query_order_policy=pol),
                                key(url="https://x.com/api", query_order_policy=pol), pol)
            self.assertNotEqual(key(url="https://x.com/api?a=&a=", query_order_policy=pol),
                                key(url="https://x.com/api?a=", query_order_policy=pol), pol)

    def test_9_semantically_distinct_requests_get_different_logical_owners(self):
        p = pool.CandidatePool(RUN)
        a = p.request_key("api", "https://x.com/api?filter=region&filter=date")
        b = p.request_key("api", "https://x.com/api?filter=date&filter=region")
        self.assertNotEqual(a, b)
        self.assertTrue(p.acquire_source(a, "lane-a"))
        self.assertTrue(p.acquire_source(b, "lane-b"),
                        "ordered repeats must not collapse into one owner")
        self.assertEqual(p.accounting()["source_fetch_owners"], 2)

    def test_10_no_policy_changes_any_record_identity_field(self):
        from src.harvest import records, urlkey
        url = "https://x.com/api?tag=b&tag=a"
        base = {"record_id": urlkey.record_id("cases", url),
                "content_id": urlkey.content_id(url),
                "identity_url": urlkey.canonicalize_string(url)}
        for pol in rk.QUERY_ORDER_POLICIES:
            key(url=url, query_order_policy=pol)
            self.assertEqual({"record_id": urlkey.record_id("cases", url),
                              "content_id": urlkey.content_id(url),
                              "identity_url": urlkey.canonicalize_string(url)}, base, pol)
        # candidate_key is a dedup key, not an identity claim, and takes no policy
        import inspect
        self.assertNotIn("query_order_policy",
                         inspect.signature(rk.candidate_key).parameters)

    def test_an_unknown_policy_is_refused_rather_than_defaulted(self):
        with self.assertRaises(rk.RequestKeyError):
            key(url="https://x.com/api?a=1", query_order_policy="sort")

    def test_no_generic_sort_mode_is_exposed(self):
        for banned in ("sort", "order-insignificant", "sorted", "normalize"):
            self.assertNotIn(banned, rk.QUERY_ORDER_POLICIES)


class TestSharedSnapshot(unittest.TestCase):
    def setUp(self):
        self.p = pool.CandidatePool(RUN)
        self.k = self.p.request_key("openai-news", FEED)

    def test_three_lanes_produce_one_logical_owner_and_one_attempt(self):
        lanes = ["cell__cases__domain-applications",
                 "gap__industry__healthcare-life-sciences",
                 "gap__business_function__marketing"]
        owners = [self.p.acquire_source(self.k, lane) for lane in lanes]
        self.assertEqual(owners, [True, False, False])

        self.p.establish_snapshot(self.k, source_id="openai-news", normalized_url=FEED,
                                  established_by="200", established_at=NOW, attempts=1)
        acct = self.p.accounting()
        self.assertEqual(acct["source_fetch_owners"], 1)
        self.assertEqual(acct["http_attempts"], 1)
        self.assertEqual(self.p.sources[self.k]["contributing_lanes"], lanes)

    def test_a_304_establishes_the_snapshot_just_as_a_200_does(self):
        self.p.acquire_source(self.k, "lane-a")
        snap = self.p.establish_snapshot(self.k, source_id="openai-news",
                                         normalized_url=FEED, established_by="304",
                                         etag='W/"abc"', attempts=1,
                                         conditional_revalidations=1)
        self.assertEqual(snap["established_by"], "304")

    def test_the_snapshot_is_reused_across_every_round(self):
        self.p.acquire_source(self.k, "lane-a")
        self.p.establish_snapshot(self.k, source_id="openai-news", normalized_url=FEED,
                                  established_by="304", attempts=1,
                                  conditional_revalidations=1)
        for rnd, lane in ((2, "gap__industry__retail-cpg"),
                          (3, "gap__use_case_type__decision-support")):
            snap = self.p.reuse_snapshot(self.k, lane, rnd)
        self.assertEqual(snap["reused_in_rounds"], [2, 3])
        # reuse issues no request at all
        self.assertEqual(self.p.accounting()["http_attempts"], 1)
        self.assertEqual(self.p.accounting()["conditional_revalidations"], 1)

    def test_no_second_conditional_request_within_a_run(self):
        self.p.acquire_source(self.k, "lane-a")
        self.p.establish_snapshot(self.k, source_id="openai-news", normalized_url=FEED,
                                  established_by="200", attempts=1)
        # round 2 tries to claim ownership again -> refused, it must reuse
        self.assertFalse(self.p.acquire_source(self.k, "lane-b"))
        with self.assertRaises(pool.SnapshotExists):
            self.p.establish_snapshot(self.k, source_id="openai-news",
                                      normalized_url=FEED, established_by="304",
                                      attempts=1, conditional_revalidations=1)
        self.assertEqual(self.p.accounting()["conditional_revalidations"], 0)

    def test_a_new_run_may_revalidate_and_see_a_newer_version(self):
        self.p.acquire_source(self.k, "lane-a")
        self.p.establish_snapshot(self.k, source_id="openai-news", normalized_url=FEED,
                                  established_by="200", etag='W/"v1"',
                                  body_sha256="a" * 64, attempts=1)
        later = pool.CandidatePool("20260729T120000Z-1")
        k2 = later.request_key("openai-news", FEED)
        self.assertEqual(k2, self.k, "the key is stable across runs — that is the point")
        self.assertTrue(later.acquire_source(k2, "lane-a"))
        snap = later.establish_snapshot(k2, source_id="openai-news", normalized_url=FEED,
                                        established_by="200", etag='W/"v2"',
                                        body_sha256="b" * 64, attempts=1,
                                        conditional_revalidations=1)
        self.assertEqual(snap["etag"], 'W/"v2"')
        self.assertNotEqual(snap["body_sha256"],
                            self.p.sources[self.k]["body_sha256"])

    def test_establishing_without_ownership_is_refused(self):
        with self.assertRaises(pool.PoolError):
            self.p.establish_snapshot("deadbeefdeadbeef", source_id="x",
                                      normalized_url=FEED, established_by="200")

    def test_only_200_or_304_establishes_a_snapshot(self):
        self.p.acquire_source(self.k, "lane-a")
        with self.assertRaises(pool.PoolError):
            self.p.establish_snapshot(self.k, source_id="x", normalized_url=FEED,
                                      established_by="500")


class TestOwnersVersusAttempts(unittest.TestCase):
    def test_redirect_plus_retry_is_one_owner_three_attempts_budget_three(self):
        p = pool.CandidatePool(RUN)
        k = p.request_key("openai-news", FEED)
        p.acquire_source(k, "lane-a")
        # 301 hop, then a 503 that is retried, then the 200.
        p.establish_snapshot(k, source_id="openai-news", normalized_url=FEED,
                             established_by="200", attempts=3, retries=1,
                             redirect_hops=1, budget_charged=3)
        acct = p.accounting()
        self.assertEqual(acct["source_fetch_owners"], 1)
        self.assertEqual(acct["http_attempts"], 3)
        self.assertEqual(acct["retries"], 1)
        self.assertEqual(acct["redirect_hops"], 1)
        self.assertEqual(p.budget_charged(), 3)

    def test_one_target_fetch_owner_and_one_extraction_owner(self):
        p = pool.CandidatePool(RUN)
        url = "https://example.com/case/a"
        lanes = ["lane-a", "lane-b", "lane-c", "lane-d"]
        for lane in lanes:
            cand, is_new = p.add_candidate(url, lane)
            self.assertEqual(is_new, lane == "lane-a")
        ck = cand["candidate_key"]

        self.assertEqual([p.acquire_target_fetch(ck, l) for l in lanes],
                         [True, False, False, False])
        self.assertEqual([p.acquire_extraction(ck, l) for l in lanes],
                         [True, False, False, False])

        acct = p.accounting()
        self.assertEqual(acct["target_fetch_owners"], 1)
        self.assertEqual(acct["extraction_owners"], 1)
        self.assertEqual(cand["contributing_lanes"], lanes)


class TestEarlyDeduplication(unittest.TestCase):
    def test_url_variants_collapse_before_extraction(self):
        p = pool.CandidatePool(RUN)
        variants = ["https://example.com/case/a",
                    "https://example.com/case/a?utm_source=x",
                    "https://EXAMPLE.com/case/a",
                    "https://example.com/case/./a"]
        for i, u in enumerate(variants):
            _, is_new = p.add_candidate(u, "lane-%d" % i)
            self.assertEqual(is_new, i == 0, u)
        self.assertEqual(len(p.candidates), 1)

    def test_every_contributing_lane_is_preserved(self):
        p = pool.CandidatePool(RUN)
        for lane in ("gap__industry__healthcare-life-sciences",
                     "cell__cases__domain-applications",
                     "gap__use_case_type__decision-support"):
            cand, _ = p.add_candidate("https://example.com/case/b", lane)
        self.assertEqual(len(cand["contributing_lanes"]), 3)
        self.assertEqual(cand["first_seen_lane_id"],
                         "gap__industry__healthcare-life-sciences")


class TestDeterminism(unittest.TestCase):
    """Output must not depend on when a worker or round happened to run."""

    def _run(self, order, seed):
        p = pool.CandidatePool(RUN)
        rnd = random.Random(seed)
        lanes = list(order)
        rnd.shuffle(lanes)
        k = p.request_key("openai-news", FEED)
        for i, lane in enumerate(lanes):
            if p.acquire_source(k, lane):
                p.establish_snapshot(k, source_id="openai-news", normalized_url=FEED,
                                     established_by="200", established_at=NOW, attempts=1)
            else:
                p.reuse_snapshot(k, lane, round_=2)
            for u in ("https://example.com/case/a", "https://example.com/case/b"):
                p.add_candidate(u, lane)
        doc = p.to_document(NOW)
        # ownership provenance legitimately reflects who arrived first; the
        # SHAPE and the identity set must not.
        return json.dumps({
            "sources": [s["source_request_key"] for s in doc["sources"]],
            "candidates": [c["candidate_key"] for c in doc["candidates"]],
            "lane_sets": sorted(sorted(c["contributing_lanes"]) for c in doc["candidates"]),
        }, sort_keys=True)

    def test_identical_under_shuffled_worker_and_round_timing(self):
        order = ["lane-a", "lane-b", "lane-c", "lane-d"]
        outs = {self._run(order, seed) for seed in range(12)}
        self.assertEqual(len(outs), 1, "pool output must not depend on lane ordering")

    def test_documents_validate(self):
        p = pool.CandidatePool(RUN)
        k = p.request_key("openai-news", FEED)
        p.acquire_source(k, "cell__cases__domain-applications")
        p.establish_snapshot(k, source_id="openai-news", normalized_url=FEED,
                             established_by="304", established_at=NOW,
                             etag='W/"x"', body_sha256="c" * 64,
                             canonicalization_version=1,
                             attempts=1, conditional_revalidations=1)
        cand, _ = p.add_candidate("https://example.com/case/a",
                                  "cell__cases__domain-applications", k)
        p.acquire_target_fetch(cand["candidate_key"], "cell__cases__domain-applications")
        p.acquire_extraction(cand["candidate_key"], "cell__cases__domain-applications")

        doc = p.to_document(NOW)
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])

        lane = p.register_lane("gap__industry__healthcare-life-sciences", round_=2,
                               kind="gap", axis="industry",
                               slug="healthcare-life-sciences",
                               query_terms=["hospital", "clinician"],
                               source_request_keys=[k])
        self.assertEqual(schema.validate(lane, "discovery_lane.v1.json"), [])

    def test_a_lane_id_is_never_facet_evidence(self):
        # Lane membership is provenance only. The pool records it and nothing
        # else; no facet value can be derived from this module.
        import inspect
        text = inspect.getsource(pool).lower()
        for needle in ("case_facets", "facet_evidence", "classification_state"):
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
