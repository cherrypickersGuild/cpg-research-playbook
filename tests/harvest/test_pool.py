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
        # NOTE: this projection is a WEAKER check than the contract requires and
        # is retained only because it exercises a different construction path.
        # It compares shape and the identity set after sorting, so it cannot see
        # ordering defects inside a row. Full-document byte-determinism — the
        # actual contract (DV-7) — is asserted by TestArtifactDeterminism below.
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


# --------------------------------------------------------------------- DV-7
LANES = ["cell__cases__domain-applications",
         "gap__industry__healthcare-life-sciences",
         "gap__business_function__marketing"]
SOURCES = [("openai-news", FEED),
           ("aws-ml-blog", "https://aws.amazon.com/blogs/machine-learning/feed/")]
PAGE = "https://example.com/story/alpha"


def _blob(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def build_pool(lane_order, source_order, pages=(PAGE,), own=True):
    """One run, driven in a caller-chosen encounter order.

    Every ordering here is semantically identical input: the same lanes see the
    same sources and the same pages. Only *when* each worker arrives differs.
    """
    p = pool.CandidatePool(RUN)
    for sid, url in source_order:
        for lane in lane_order:
            k = p.request_key(sid, url)
            if p.acquire_source(k, lane):
                p.establish_snapshot(k, source_id=sid, normalized_url=url,
                                     established_by="200", established_at=NOW,
                                     body_sha256="0" * 64, attempts=1)
            else:
                p.reuse_snapshot(k, lane, round_=2)
            for page in pages:
                cand, _ = p.add_candidate(page, lane, source_request_key=k)
                if own:
                    p.acquire_target_fetch(cand["candidate_key"], lane)
                    p.acquire_extraction(cand["candidate_key"], lane)
    return p


def all_orderings(lanes=LANES, sources=SOURCES):
    import itertools
    for lo in itertools.permutations(lanes):
        for so in itertools.permutations(sources):
            yield list(lo), list(so)


class TestArtifactDeterminism(unittest.TestCase):
    """The full document, not a projection, must be byte-identical.

    Both defects this pins were live and invisible to the 38 pre-DV-7
    assertions: set-like provenance kept encounter order, and four scalars
    recorded whichever worker won a race. Twelve semantically identical
    orderings produced twelve distinct documents.
    """

    def test_twelve_orderings_produce_one_byte_identical_document(self):
        blobs = {_blob(build_pool(lo, so).to_document(NOW))
                 for lo, so in all_orderings()}
        self.assertEqual(len(blobs), 1,
                         "the complete pool document must not depend on encounter order")

    def test_a_larger_case_is_also_byte_identical(self):
        lanes = LANES + ["gap__use_case_type__risk-fraud-compliance"]
        sources = SOURCES + [("nvidia-blog", "https://blogs.nvidia.com/feed/")]
        pages = ("https://example.com/story/alpha",
                 "https://example.com/story/beta",
                 "https://example.com/story/gamma")
        blobs = {_blob(build_pool(lo, so, pages=pages).to_document(NOW))
                 for lo, so in all_orderings(lanes, sources)}
        self.assertEqual(len(blobs), 1)

    def test_document_validates_after_normalization(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])


class TestSetLikeNormalization(unittest.TestCase):
    def test_source_contributing_lanes_are_deduplicated_and_lexically_sorted(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        for src in doc["sources"]:
            lanes = src["contributing_lanes"]
            self.assertEqual(lanes, sorted(set(lanes)))
            self.assertEqual(len(lanes), len(set(lanes)))
            self.assertEqual(sorted(lanes), sorted(LANES))

    def test_candidate_contributing_lanes_are_deduplicated_and_lexically_sorted(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        for cand in doc["candidates"]:
            lanes = cand["contributing_lanes"]
            self.assertEqual(lanes, sorted(set(lanes)))
            self.assertEqual(len(lanes), len(set(lanes)))

    def test_source_request_keys_are_deduplicated_and_lexically_sorted(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        keys = doc["candidates"][0]["source_request_keys"]
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys, sorted(set(keys)))

    def test_reused_in_rounds_is_deduplicated_and_sorted_NUMERICALLY(self):
        # The bug a generic key=str comparator would leave behind: round 10
        # sorting between 1 and 2. Rounds arrive out of order and repeated.
        p = pool.CandidatePool(RUN)
        k = p.request_key("openai-news", FEED)
        p.acquire_source(k, "lane-a")
        p.establish_snapshot(k, source_id="openai-news", normalized_url=FEED,
                             established_by="200", established_at=NOW, attempts=1)
        for rnd in (10, 2, 1, 10, 2):
            p.reuse_snapshot(k, "lane-b", round_=rnd)
        rounds = p.to_document(NOW)["sources"][0]["reused_in_rounds"]
        self.assertEqual(rounds, [1, 2, 10])
        self.assertNotEqual(rounds, sorted({10, 2, 1}, key=str))

    def test_meaningful_order_is_not_touched_by_this_module(self):
        # The pool must not contain any general-purpose sorter that could reach
        # feed/anchor/JSON item order or repeated query-key values.
        import inspect
        text = inspect.getsource(pool)
        self.assertNotIn("sorted(pairs", text)
        self.assertNotIn("parse_qsl", text)
        for needle in ("_LEXICAL_SET_FIELDS", "_NUMERIC_SET_FIELDS"):
            self.assertIn(needle, text)


class TestDesignationIsNotExecution(unittest.TestCase):
    """Runtime truth stays in memory; the artifact publishes a designation."""

    def test_in_memory_state_keeps_encounter_order_and_the_actual_owner(self):
        order = list(reversed(LANES))
        p = build_pool(order, SOURCES)
        k = p.request_key(*SOURCES[0])
        # encounter order, not sorted
        self.assertEqual(p.sources[k]["contributing_lanes"], order)
        self.assertEqual(p.sources[k]["owner_lane_id"], order[0])
        cand = list(p.candidates.values())[0]
        self.assertEqual(cand["contributing_lanes"], order)
        self.assertEqual(cand["first_seen_lane_id"], order[0])
        self.assertEqual(cand["target_fetch_owner"], order[0])
        self.assertEqual(cand["extraction_owner"], order[0])

    def test_actual_runtime_owner_varies_but_the_designation_does_not(self):
        actual, designated = set(), set()
        for lo, so in all_orderings():
            p = build_pool(lo, so)
            k = p.request_key(*SOURCES[0])
            actual.add(p.sources[k]["owner_lane_id"])
            row = [s for s in p.to_document(NOW)["sources"]
                   if s["source_request_key"] == k][0]
            designated.add(row["designated_owner_lane_id"])
        self.assertGreater(len(actual), 1, "the race winner really does vary")
        self.assertEqual(len(designated), 1)
        self.assertEqual(designated, {min(LANES)})

    def test_primary_discovery_lane_is_invariant_when_the_first_seen_lane_changes(self):
        actual, designated = set(), set()
        for lo, so in all_orderings():
            p = build_pool(lo, so)
            actual.add(list(p.candidates.values())[0]["first_seen_lane_id"])
            designated.add(p.to_document(NOW)["candidates"][0]["primary_discovery_lane_id"])
        self.assertGreater(len(actual), 1)
        self.assertEqual(designated, {min(LANES)})

    def test_the_actual_owner_names_never_reach_the_document(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        stale = ("owner_lane_id", "first_seen_lane_id",
                 "target_fetch_owner", "extraction_owner")
        for src in doc["sources"]:
            for name in stale:
                self.assertNotIn(name, src)
        for cand in doc["candidates"]:
            for name in stale:
                self.assertNotIn(name, cand)

    def test_designations_are_null_when_the_operation_did_not_occur(self):
        doc = build_pool(LANES, SOURCES, own=False).to_document(NOW)
        cand = doc["candidates"][0]
        self.assertIsNone(cand["designated_target_fetch_owner_lane_id"])
        self.assertIsNone(cand["designated_extraction_owner_lane_id"])
        # null means "has not happened" — it is never a designation
        self.assertIsNotNone(cand["primary_discovery_lane_id"])
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])

    def test_non_null_designations_are_deterministic_and_belong_to_the_lane_set(self):
        for lo, so in all_orderings():
            cand = build_pool(lo, so).to_document(NOW)["candidates"][0]
            lanes = cand["contributing_lanes"]
            for field in ("designated_target_fetch_owner_lane_id",
                          "designated_extraction_owner_lane_id",
                          "primary_discovery_lane_id"):
                self.assertIn(cand[field], lanes)
                self.assertEqual(cand[field], min(lanes))

    def test_the_old_misleading_property_names_are_rejected_by_the_schema(self):
        doc = build_pool(LANES, SOURCES).to_document(NOW)
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])
        for row, old, new in (
                (doc["sources"][0], "owner_lane_id", "designated_owner_lane_id"),
                (doc["candidates"][0], "first_seen_lane_id", "primary_discovery_lane_id"),
                (doc["candidates"][0], "target_fetch_owner",
                 "designated_target_fetch_owner_lane_id"),
                (doc["candidates"][0], "extraction_owner",
                 "designated_extraction_owner_lane_id")):
            with self.subTest(old=old):
                row[old] = row[new]
                self.assertNotEqual(schema.validate(doc, "candidate_pool.v1.json"), [],
                                    "additionalProperties:false must reject %r" % old)
                del row[old]
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])


class TestDV7ChangesNothingElse(unittest.TestCase):
    """Normalization is serialization-only and must not reach anything else."""

    def test_identity_and_request_keys_are_untouched(self):
        import inspect
        text = inspect.getsource(pool)
        for needle in ("record_id", "content_id", "identity_url", "canonical_url",
                       "cell_id", "query_order_policy"):
            self.assertNotIn(needle, text)

    def test_candidate_and_request_keys_are_unchanged_by_ordering(self):
        keys = set()
        for lo, so in all_orderings():
            doc = build_pool(lo, so).to_document(NOW)
            keys.add((tuple(s["source_request_key"] for s in doc["sources"]),
                      tuple(c["candidate_key"] for c in doc["candidates"]),
                      tuple(c["canonical_key"] for c in doc["candidates"])))
        self.assertEqual(len(keys), 1)

    def test_accounting_and_budget_are_unaffected_by_serialization(self):
        p = build_pool(LANES, SOURCES)
        before = (dict(p.accounting()), p.budget_charged())
        p.to_document(NOW)
        self.assertEqual((dict(p.accounting()), p.budget_charged()), before)
        # three lanes still produce ONE logical owner per source
        self.assertEqual(p.accounting()["source_fetch_owners"], len(SOURCES))

    def test_to_document_does_not_mutate_live_rows(self):
        p = build_pool(list(reversed(LANES)), SOURCES)
        k = p.request_key(*SOURCES[0])
        snap_before = json.dumps(p.sources[k], sort_keys=False)
        cand_before = json.dumps(list(p.candidates.values())[0], sort_keys=False)
        p.to_document(NOW)
        p.to_document(NOW)
        self.assertEqual(json.dumps(p.sources[k], sort_keys=False), snap_before)
        self.assertEqual(json.dumps(list(p.candidates.values())[0], sort_keys=False),
                         cand_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
