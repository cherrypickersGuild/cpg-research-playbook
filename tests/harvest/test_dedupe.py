#!/usr/bin/env python3
"""test_dedupe.py — deterministic candidate ingest and same-topic dedupe (S4-1).

The properties that carry the weight:

  * three lanes sharing one cached source produce ONE observation, not three —
    the naive count triples and would make every duplicate metric wrong;
  * ordering comes from immutable content, so shuffling the deliveries, the
    sources, the candidates or the lanes cannot change a byte of the output;
  * nothing is discarded: two sources with different titles for one page both
    survive, and only the DISPLAY value is singular;
  * grouping is canonical equivalence and nothing else — no redirect, no
    canonical tag, no alias, no fetch.

Built on the REAL `RawCandidate` and `AdapterResult`, so the contract is proved
to fit rather than assumed to. Offline; no network, no pool, no records.
Run via tests/test_taxonomy_dedupe.sh.
"""
import ast
import inspect
import itertools
import json
import os
import random
import sys
import unittest
from dataclasses import FrozenInstanceError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import dedupe as dd                                  # noqa: E402
from src.harvest import request_key as rk, urlkey                     # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate     # noqa: E402

LANES = ("cell__cases__case-studies",
         "gap__business_function__marketing",
         "gap__industry__healthcare-life-sciences")

SOURCES = {
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
    "anthropic-customers": {"source_id": "anthropic-customers", "topic_slug": "cases",
                            "category_slug": "case-studies", "adapter": "seed",
                            "role": "validation_seed"},
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "techcrunch-ai": {"source_id": "techcrunch-ai", "topic_slug": "discourse",
                      "category_slug": "market-and-investment", "adapter": "feed",
                      "role": "discovery"},
}

PAGE = "https://openai.com/index/acme-support-automation/"
OTHER = "https://openai.com/index/beta-logistics/"


def raw(url, position=0, source_id="openai-news", adapter="feed", **kw):
    return RawCandidate(target_url=url, source_id=source_id, adapter=adapter,
                        position=position, **kw)


def result(source_id, candidates, adapter=None, outcome="ok"):
    adapter = adapter or SOURCES[source_id]["adapter"]
    return AdapterResult(source_id=source_id, adapter=adapter, result=outcome,
                         candidates=tuple(candidates))


def deliver(lane, res, key=None):
    return dd.delivery(lane, res, source_request_key=key)


def serialize(res):
    """A total, order-revealing rendering — the determinism assertions compare this."""
    return json.dumps({
        "observation_count": res.observation_count,
        "duplicate_observation_count": res.duplicate_observation_count,
        "unusable": [[u.source_id, u.position, u.target_url, u.reason]
                     for u in res.unusable],
        "groups": [{
            "candidate_key": g.candidate_key,
            "identity_url": g.identity_url,
            "contexts": [list(c) for c in g.contexts()],
            "lane_ids": list(g.lane_ids()),
            "source_request_keys": list(g.source_request_keys()),
            "retention": g.retention_payload(),
        } for g in res.groups],
    }, sort_keys=True, indent=None)


# ------------------------------------------------------------------ grouping
class TestGrouping(unittest.TestCase):
    def test_a_single_candidate_becomes_one_group(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        self.assertEqual(res.group_count, 1)
        self.assertEqual(res.observation_count, 1)
        self.assertEqual(res.duplicate_observation_count, 0)

    def test_duplicates_within_one_source_collapse_to_one_group(self):
        # The same page linked twice in one feed: two ITEMS, one identity.
        res = dd.group([deliver(LANES[0], result(
            "openai-news", [raw(PAGE, 0), raw(PAGE + "?utm_source=x", 1)]))],
            sources=SOURCES)
        self.assertEqual(res.group_count, 1)
        self.assertEqual(res.observation_count, 2)
        self.assertEqual(res.duplicate_observation_count, 1)
        self.assertTrue(res.groups[0].is_duplicated)

    def test_duplicates_across_sources_collapse_to_one_group(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [raw(PAGE)])),
            deliver(LANES[0], result("aws-ml-blog",
                                     [raw(PAGE, source_id="aws-ml-blog")])),
        ], sources=SOURCES)
        self.assertEqual(res.group_count, 1)
        self.assertEqual(res.observation_count, 2)
        self.assertEqual(res.duplicate_observation_count, 1)
        self.assertEqual(res.groups[0].source_ids(),
                         ("aws-ml-blog", "openai-news"))

    def test_distinct_pages_stay_distinct(self):
        res = dd.group([deliver(LANES[0], result(
            "openai-news", [raw(PAGE, 0), raw(OTHER, 1)]))], sources=SOURCES)
        self.assertEqual(res.group_count, 2)
        self.assertEqual(res.duplicate_observation_count, 0)

    def test_groups_are_sorted_by_candidate_key(self):
        res = dd.group([deliver(LANES[0], result(
            "openai-news", [raw(PAGE, 0), raw(OTHER, 1)]))], sources=SOURCES)
        keys = [g.candidate_key for g in res.groups]
        self.assertEqual(keys, sorted(keys))

    def test_zero_result_and_error_results_contribute_nothing(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [], outcome="zero_result")),
            deliver(LANES[0], result("aws-ml-blog", [],
                                     outcome="infrastructure_error")),
        ], sources=SOURCES)
        self.assertEqual(res.group_count, 0)
        self.assertEqual(res.observation_count, 0)


# ------------------------------------------------------------------- identity
class TestIdentity(unittest.TestCase):
    def test_candidate_key_is_the_committed_function(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        expected_key, expected_canonical = rk.candidate_key(PAGE)
        self.assertEqual(res.groups[0].candidate_key, expected_key)
        self.assertEqual(res.groups[0].identity_url, expected_canonical)

    def test_identity_url_is_canonicalize_string(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        self.assertEqual(res.groups[0].identity_url,
                         urlkey.canonicalize_string(PAGE))

    def test_canonical_equivalent_urls_group(self):
        variants = [
            "https://openai.com:443/index/acme/",          # default port
            "https://openai.com/index/acme/?utm_source=x",  # tracking param
            "https://openai.com/index/./acme/",             # dot-segment
            "https://OpenAI.com/index/acme/",               # host case
        ]
        res = dd.group([deliver(LANES[0], result(
            "openai-news", [raw(u, i) for i, u in enumerate(variants)]))],
            sources=SOURCES)
        self.assertEqual(res.group_count, 1)
        self.assertEqual(res.observation_count, 4)
        self.assertEqual(res.duplicate_observation_count, 3)

    def test_canonical_distinct_urls_do_not_group(self):
        variants = [
            "https://openai.com/a/?ref=news",     # ref= is never stripped
            "https://openai.com/a/?a=1&b=2",      # order is significant
            "https://openai.com/a/?b=2&a=1",      # ...so this is different
            "https://openai.com/a/#intro",        # fragments are preserved
            "https://openai.com/a/",
        ]
        res = dd.group([deliver(LANES[0], result(
            "openai-news", [raw(u, i) for i, u in enumerate(variants)]))],
            sources=SOURCES)
        self.assertEqual(res.group_count, 5)
        self.assertEqual(res.duplicate_observation_count, 0)

    def test_http_and_https_are_never_merged(self):
        # Alias-only per urlkey.py; merging them needs redirect evidence (Stage 6).
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw("http://openai.com/a/", 0), raw("https://openai.com/a/", 1)]))],
            sources=SOURCES)
        self.assertEqual(res.group_count, 2)

    def test_trailing_slash_and_www_are_never_merged(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw("https://openai.com/a", 0),
            raw("https://openai.com/a/", 1),
            raw("https://www.openai.com/a/", 2)]))], sources=SOURCES)
        self.assertEqual(res.group_count, 3)


# ------------------------------------------------------------ lane provenance
class TestLaneProvenance(unittest.TestCase):
    def deliveries(self):
        shared = result("openai-news", [raw(PAGE, 0), raw(OTHER, 1)])
        return [deliver(lane, shared, key="a1b2c3d4e5f60718") for lane in LANES]

    def test_three_lanes_do_not_inflate_the_observation_count(self):
        res = dd.group(self.deliveries(), sources=SOURCES)
        self.assertEqual(res.observation_count, 2)
        self.assertEqual(res.duplicate_observation_count, 0)
        self.assertEqual(res.group_count, 2)

    def test_every_lane_is_preserved(self):
        res = dd.group(self.deliveries(), sources=SOURCES)
        for group in res.groups:
            self.assertEqual(group.lane_ids(), tuple(sorted(LANES)))

    def test_lane_ids_are_deduplicated_and_lexically_sorted(self):
        shared = result("openai-news", [raw(PAGE)])
        res = dd.group([deliver(LANES[2], shared), deliver(LANES[0], shared),
                        deliver(LANES[2], shared), deliver(LANES[1], shared)],
                       sources=SOURCES)
        lanes = res.groups[0].observations[0].lane_ids
        self.assertEqual(lanes, tuple(sorted(set(LANES))))
        self.assertEqual(len(lanes), 3)

    def test_source_request_keys_are_deduplicated_and_sorted(self):
        shared = result("openai-news", [raw(PAGE)])
        res = dd.group([deliver(LANES[0], shared, key="ffff000011112222"),
                        deliver(LANES[1], shared, key="0000aaaabbbbcccc"),
                        deliver(LANES[2], shared, key="ffff000011112222")],
                       sources=SOURCES)
        self.assertEqual(res.groups[0].source_request_keys(),
                         ("0000aaaabbbbcccc", "ffff000011112222"))

    def test_duplicate_count_ignores_repeated_lane_delivery(self):
        # Two DISTINCT source observations of one page, delivered by three lanes
        # each: the duplicate count is 1, never 5.
        a = result("openai-news", [raw(PAGE)])
        b = result("aws-ml-blog", [raw(PAGE, source_id="aws-ml-blog")])
        res = dd.group([deliver(l, r) for r in (a, b) for l in LANES],
                       sources=SOURCES)
        self.assertEqual(res.observation_count, 2)
        self.assertEqual(res.duplicate_observation_count, 1)

    def test_a_missing_request_key_is_simply_absent(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        self.assertEqual(res.groups[0].source_request_keys(), ())


# --------------------------------------------------------- metadata retention
class TestMetadataRetention(unittest.TestCase):
    def conflicting(self):
        return [
            deliver(LANES[0], result("openai-news", [raw(
                PAGE, title="Acme cuts handle time 38%",
                summary="Acme deployed an assistant.", publisher="OpenAI",
                published_at="Mon, 06 Jul 2026 09:00:00 GMT")])),
            deliver(LANES[1], result("aws-ml-blog", [raw(
                PAGE, source_id="aws-ml-blog",
                title="How Acme automated support",
                summary="A different summary entirely.", publisher="AWS",
                published_at="2026-07-07T00:00:00Z")])),
        ]

    def test_conflicting_titles_are_both_retained(self):
        group = dd.group(self.conflicting(), sources=SOURCES).groups[0]
        values = [v for v, _ in group.variants("title")]
        self.assertIn("Acme cuts handle time 38%", values)
        self.assertIn("How Acme automated support", values)
        self.assertTrue(group.has_conflict("title"))

    def test_conflicting_publishers_summaries_and_dates_are_retained(self):
        group = dd.group(self.conflicting(), sources=SOURCES).groups[0]
        for field in ("publisher", "summary", "published_at"):
            self.assertTrue(group.has_conflict(field), field)
            self.assertEqual(len(group.variants(field)), 2, field)

    def test_variants_name_the_sources_that_asserted_them(self):
        group = dd.group(self.conflicting(), sources=SOURCES).groups[0]
        mapping = dict(group.variants("publisher"))
        self.assertEqual(mapping["OpenAI"], ("openai-news",))
        self.assertEqual(mapping["AWS"], ("aws-ml-blog",))

    def test_a_silent_source_is_not_a_competing_opinion(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [raw(PAGE, title="Acme")])),
            deliver(LANES[0], result("aws-ml-blog",
                                     [raw(PAGE, source_id="aws-ml-blog")])),
        ], sources=SOURCES)
        group = res.groups[0]
        self.assertEqual(len(group.variants("title")), 1)
        self.assertFalse(group.has_conflict("title"))

    def test_target_url_variants_are_retained(self):
        # Two raw URLs, one identity: the difference is worth keeping.
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw(PAGE, 0), raw(PAGE + "?utm_source=news", 1)]))], sources=SOURCES)
        self.assertEqual(len(res.groups[0].variants("target_url")), 2)

    def test_retention_payload_holds_every_observation(self):
        payload = dd.group(self.conflicting(), sources=SOURCES).groups[0] \
            .retention_payload()
        self.assertEqual(len(payload["observations"]), 2)
        self.assertIn("title", payload["field_variants"])
        self.assertEqual(
            sorted(o["source_id"] for o in payload["observations"]),
            ["aws-ml-blog", "openai-news"])

    def test_retention_payload_is_plain_json_data_not_a_record(self):
        payload = dd.group(self.conflicting(), sources=SOURCES).groups[0] \
            .retention_payload()
        json.dumps(payload)                       # must not raise
        self.assertNotIn("record_id", payload)
        self.assertNotIn("schema_version", payload)
        self.assertNotIn("classification", payload)


# ------------------------------------------------------- primary and display
class TestPrimarySelection(unittest.TestCase):
    def authority_pair(self, order):
        seed = result("anthropic-customers", [raw(
            PAGE, source_id="anthropic-customers", adapter="seed",
            title="Anthropic customer story")])
        feed = result("openai-news", [raw(PAGE, title="OpenAI newsroom item")])
        pairs = {"seed": deliver(LANES[0], seed), "feed": deliver(LANES[1], feed)}
        return [pairs[name] for name in order]

    def test_validation_seed_outranks_discovery(self):
        group = dd.group(self.authority_pair(("feed", "seed")),
                         sources=SOURCES).groups[0]
        self.assertEqual(group.primary.source_id, "anthropic-customers")
        self.assertEqual(group.display("title"), "Anthropic customer story")

    def test_authority_does_not_depend_on_delivery_order(self):
        a = dd.group(self.authority_pair(("feed", "seed")), sources=SOURCES)
        b = dd.group(self.authority_pair(("seed", "feed")), sources=SOURCES)
        self.assertEqual(serialize(a), serialize(b))
        self.assertEqual(a.groups[0].primary.source_id, "anthropic-customers")

    def test_same_role_falls_back_to_the_deterministic_key(self):
        res = dd.group([
            deliver(LANES[0], result("techcrunch-ai", [raw(
                PAGE, source_id="techcrunch-ai", title="TC")])),
            deliver(LANES[0], result("aws-ml-blog", [raw(
                PAGE, source_id="aws-ml-blog", title="AWS")])),
        ], sources=SOURCES)
        # both are `discovery`, so source_id decides: aws-ml-blog < techcrunch-ai
        self.assertEqual(res.groups[0].primary.source_id, "aws-ml-blog")
        self.assertEqual(res.groups[0].display("title"), "AWS")

    def test_position_breaks_a_tie_within_one_source(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw(PAGE, 0, title="first"),
            raw(PAGE + "?utm_id=z", 1, title="second")]))], sources=SOURCES)
        self.assertEqual(res.groups[0].display("title"), "first")

    def test_display_falls_through_a_blank_primary_value(self):
        res = dd.group([
            deliver(LANES[0], result("anthropic-customers", [raw(
                PAGE, source_id="anthropic-customers", adapter="seed",
                title="   ", publisher=None)])),
            deliver(LANES[0], result("openai-news",
                                     [raw(PAGE, title="Acme", publisher="OpenAI")])),
        ], sources=SOURCES)
        group = res.groups[0]
        self.assertEqual(group.primary.source_id, "anthropic-customers")
        self.assertEqual(group.display("title"), "Acme")
        self.assertEqual(group.display("publisher"), "OpenAI")

    def test_display_is_none_when_nobody_supplied_the_field(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        self.assertIsNone(res.groups[0].display("title"))

    def test_display_does_not_depend_on_lane_identity(self):
        base = result("openai-news", [raw(PAGE, title="Acme")])
        first = dd.group([deliver(LANES[0], base)], sources=SOURCES)
        last = dd.group([deliver(LANES[2], base)], sources=SOURCES)
        self.assertEqual(first.groups[0].display("title"),
                         last.groups[0].display("title"))

    def test_an_unknown_field_is_refused(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        with self.assertRaises(dd.DedupeError):
            res.groups[0].display("relevance_score")


# ------------------------------------------------------------------- contexts
class TestContexts(unittest.TestCase):
    def test_every_discovery_context_is_retained(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [raw(PAGE)])),
            deliver(LANES[0], result("aws-ml-blog",
                                     [raw(PAGE, source_id="aws-ml-blog")])),
            deliver(LANES[0], result("techcrunch-ai",
                                     [raw(PAGE, source_id="techcrunch-ai")])),
        ], sources=SOURCES)
        contexts = res.groups[0].contexts()
        self.assertEqual(len(contexts), 3)
        self.assertIn(("cases", "case-studies"), contexts)
        self.assertIn(("cases", "domain-applications"), contexts)
        self.assertIn(("discourse", "market-and-investment"), contexts)

    def test_repeated_contexts_collapse_but_are_not_lost(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [raw(PAGE)])),
            deliver(LANES[1], result("anthropic-customers", [raw(
                PAGE, source_id="anthropic-customers", adapter="seed")])),
        ], sources=SOURCES)
        self.assertEqual(res.groups[0].contexts(), (("cases", "case-studies"),))

    def test_contexts_are_ordered_by_the_total_order(self):
        res = dd.group([
            deliver(LANES[0], result("techcrunch-ai",
                                     [raw(PAGE, source_id="techcrunch-ai")])),
            deliver(LANES[0], result("aws-ml-blog",
                                     [raw(PAGE, source_id="aws-ml-blog")])),
        ], sources=SOURCES)
        self.assertEqual(res.groups[0].contexts(),
                         (("cases", "domain-applications"),
                          ("discourse", "market-and-investment")))


# --------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def scenario(self):
        return [
            deliver(LANES[0], result("openai-news", [
                raw(PAGE, 0, title="Acme cuts handle time"),
                raw(OTHER, 1, title="Beta logistics"),
            ]), key="1111111111111111"),
            deliver(LANES[1], result("openai-news", [
                raw(PAGE, 0, title="Acme cuts handle time"),
                raw(OTHER, 1, title="Beta logistics"),
            ]), key="1111111111111111"),
            deliver(LANES[2], result("aws-ml-blog", [
                raw(PAGE, 0, source_id="aws-ml-blog", title="AWS view of Acme"),
                raw("https://aws.amazon.com/x/", 1, source_id="aws-ml-blog"),
            ]), key="2222222222222222"),
            deliver(LANES[0], result("anthropic-customers", [
                raw(PAGE, 0, source_id="anthropic-customers", adapter="seed",
                    title="Anthropic customer story"),
            ]), key="3333333333333333"),
            deliver(LANES[1], result("techcrunch-ai", [
                raw(OTHER, 0, source_id="techcrunch-ai", title="TC on Beta"),
            ]), key="4444444444444444"),
        ]

    def test_every_permutation_of_deliveries_gives_one_output(self):
        base = self.scenario()
        outputs = {serialize(dd.group(list(order), sources=SOURCES))
                   for order in itertools.permutations(base)}
        self.assertEqual(len(outputs), 1, "delivery order changed the output")
        self.assertEqual(len(list(itertools.permutations(base))), 120)

    def test_shuffled_source_map_order_gives_one_output(self):
        base = self.scenario()
        outputs = set()
        rng = random.Random(4242)
        for _ in range(12):
            keys = list(SOURCES)
            rng.shuffle(keys)
            outputs.add(serialize(dd.group(
                base, sources={k: SOURCES[k] for k in keys})))
        self.assertEqual(len(outputs), 1, "source map order changed the output")

    def test_shuffled_lane_assignment_gives_one_grouping(self):
        # Lanes are provenance. Which lane delivered which result may change the
        # lane sets, but never the grouping, ordering or display values.
        base = self.scenario()
        rng = random.Random(99)
        shapes = set()
        for _ in range(12):
            reshuffled = [dd.delivery(rng.choice(LANES), d.result,
                                      d.source_request_key) for d in base]
            res = dd.group(reshuffled, sources=SOURCES)
            shapes.add(json.dumps([[g.candidate_key, g.identity_url,
                                    g.display("title"), g.primary.source_id]
                                   for g in res.groups], sort_keys=True))
        self.assertEqual(len(shapes), 1, "lane order changed the grouping")

    def test_shuffled_candidate_order_within_a_source_gives_one_output(self):
        # Position is content, so reordering the tuple must not matter.
        items = [raw(PAGE, 0, title="a"), raw(OTHER, 1, title="b"),
                 raw("https://openai.com/c/", 2, title="c")]
        outputs = {serialize(dd.group(
            [deliver(LANES[0], result("openai-news", list(order)))],
            sources=SOURCES)) for order in itertools.permutations(items)}
        self.assertEqual(len(outputs), 1)

    def test_repeated_runs_are_byte_identical(self):
        base = self.scenario()
        self.assertEqual(serialize(dd.group(base, sources=SOURCES)),
                         serialize(dd.group(base, sources=SOURCES)))


# ----------------------------------------------------------------- integrity
class TestIntegrity(unittest.TestCase):
    def test_a_non_delivery_is_refused(self):
        with self.assertRaises(dd.DedupeError):
            dd.group([result("openai-news", [raw(PAGE)])], sources=SOURCES)

    def test_an_unconfigured_source_is_refused(self):
        with self.assertRaises(dd.DedupeError):
            dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                     sources={})

    def test_a_candidate_stamped_with_a_foreign_source_is_refused(self):
        bad = AdapterResult(source_id="openai-news", adapter="feed", result="ok",
                            candidates=(raw(PAGE, source_id="aws-ml-blog"),))
        with self.assertRaises(dd.DedupeError):
            dd.group([deliver(LANES[0], bad)], sources=SOURCES)

    def test_two_deliveries_disagreeing_on_payload_are_refused(self):
        a = result("openai-news", [raw(PAGE, title="one")])
        b = result("openai-news", [raw(PAGE, title="two")])
        with self.assertRaises(dd.DedupeError):
            dd.group([deliver(LANES[0], a), deliver(LANES[1], b)],
                     sources=SOURCES)

    def test_an_uncanonicalizable_target_is_reported_not_silent(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw(PAGE, 0), raw("ftp://openai.com/x", 1)]))], sources=SOURCES)
        self.assertEqual(res.group_count, 1)
        self.assertEqual(len(res.unusable), 1)
        self.assertEqual(res.unusable[0].reason, "uncanonicalizable_target_url")
        self.assertEqual(res.unusable[0].target_url, "ftp://openai.com/x")

    def test_an_unusable_candidate_is_not_counted_as_an_observation(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [
            raw(PAGE, 0), raw("not-a-url", 1)]))], sources=SOURCES)
        self.assertEqual(res.observation_count, 1)
        self.assertEqual(res.duplicate_observation_count, 0)

    def test_no_survivor_is_ever_marked_dropped(self):
        res = dd.group([
            deliver(LANES[0], result("openai-news", [raw(PAGE)])),
            deliver(LANES[0], result("aws-ml-blog",
                                     [raw(PAGE, source_id="aws-ml-blog")])),
        ], sources=SOURCES)
        blob = serialize(res)
        for token in ("dropped", "duplicate_in_pool", "duplicate_of",
                      "not_fetched"):
            self.assertNotIn(token, blob)
        self.assertEqual(res.group_count, 1)

    def test_observations_and_groups_are_immutable(self):
        res = dd.group([deliver(LANES[0], result("openai-news", [raw(PAGE)]))],
                       sources=SOURCES)
        with self.assertRaises(FrozenInstanceError):
            res.groups[0].observations[0].title = "rewritten"
        with self.assertRaises(FrozenInstanceError):
            res.groups[0].candidate_key = "0000000000000000"


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    """Stage 4 is metadata-only and in-memory. Proved on the import graph and
    the call graph, not on a text scan: this module's prose legitimately
    discusses aliases, pools and fetching, and a substring search would either
    fail spuriously or be weakened until it proved nothing."""

    def setUp(self):
        self.tree = ast.parse(inspect.getsource(dd))

    def imported(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.split(".")[0])
                names.update(a.name for a in node.names)
        return names

    def test_no_network_or_parsing_dependency(self):
        banned = {"urllib", "requests", "httpx", "aiohttp", "socket", "http",
                  "ssl", "subprocess", "asyncio", "xml", "html", "feedparser",
                  "bs4", "lxml", "os", "io"}
        self.assertEqual(self.imported() & banned, set(),
                         "dedupe must contain no network, filesystem or parsing "
                         "dependency")

    def test_no_pool_cache_adapter_or_record_dependency(self):
        banned = {"pool", "CandidatePool", "sourcecache", "SourceFetchCache",
                  "records", "make_full_record", "make_cross_reference",
                  "httpclient", "fixtures", "schema", "facets", "coverage",
                  "scheduler"}
        self.assertEqual(self.imported() & banned, set(),
                         "Stage 5 owns the pool; Stage 4 S4-1 owns neither it "
                         "nor record construction")

    def test_it_uses_the_committed_identity_functions_only(self):
        self.assertIn("request_key", self.imported())
        self.assertIn("urlkey", self.imported())
        called = {n.func.attr for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("candidate_key", called)
        # No second identity system: nothing here hashes or canonicalizes itself.
        for forbidden in ("sha256", "md5", "canonicalize_string", "record_id",
                          "content_id", "source_request_key"):
            self.assertNotIn(forbidden, called, forbidden)

    def test_no_later_stage_or_ownership_symbol_is_referenced(self):
        referenced = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
        for forbidden in ("add_candidate", "acquire_target_fetch",
                          "acquire_extraction", "target_fetch_owner",
                          "extraction_owner", "record_established_source",
                          "reuse_snapshot", "url_aliases", "canonical_tag",
                          "permanent_redirect", "case_facets", "classification",
                          "relevance_score", "verification_status",
                          "access_status", "content_hash", "get_or_fetch"):
            self.assertNotIn(forbidden, referenced, forbidden)

    def test_stage_4_writes_nothing(self):
        called = {n.func.id for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("open", called)
        self.assertNotIn("print", called)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("Delivery", "CandidateObservation", "CandidateGroup",
                     "DedupeResult", "group", "DedupeError"):
            self.assertTrue(hasattr(dd, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
