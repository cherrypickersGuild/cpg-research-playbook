#!/usr/bin/env python3
"""test_adapters.py — feed, jsonapi and seed against the offline fixture corpus.

Everything runs the real path: Adapter -> SourceFetchCache -> HttpClient ->
FixtureOpener. The robots cache, the RFC 9309 matcher, retries, redirects,
content-type and byte-cap checks and DV-8 accounting are all the shipped code;
only the opener is injected. There is no fixture branch inside any adapter or
inside the cache, and this suite proves that statically as well as behaviourally.

Offline: no request leaves the machine, and an unfixtured URL or host raises
rather than being answered.
"""
import glob
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import adapters, fixtures, httpclient as hc          # noqa: E402
from src.harvest import pool as pool_mod, schema, sourcecache as sc    # noqa: E402
from src.harvest.adapters import base, feed as feed_mod                # noqa: E402
from src.harvest.adapters import jsonapi as jsonapi_mod                # noqa: E402
from src.harvest.adapters import seed as seed_mod                      # noqa: E402
from src.harvest.budget import RequestBudget                           # noqa: E402

NOW = "2026-07-29T00:00:00Z"
RUN = "20260729T000000Z-4b"
LANE = "cell__cases__domain-applications"


def code_only(source_text):
    """Executable code with docstrings and comments removed.

    Static boundary checks must read what a module DOES, not what it says about
    itself. A raw substring scan fails on the very sentence that documents the
    guarantee — "records.make_full_record is never called from here" contains
    the name it forbids — so it would either be permanently red or have to be
    weakened until it proved nothing.
    """
    import ast
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
    return ast.unparse(tree)


def module_code(module):
    import inspect
    return code_only(inspect.getsource(module))


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


def policy(**over):
    p = {
        "user_agent": "cherry-harvest-test/1.0",
        "budgets": {"request_timeout_sec": 3, "max_response_bytes": 1 << 20,
                    "lease_wait_max_sec": 2},
        "retry": {"max_attempts": 2, "backoff_base_sec": 0.0,
                  "backoff_multiplier": 1.0, "jitter_frac": 0.0,
                  "retry_on_status": [429, 500, 502, 503, 504], "max_redirects": 3},
        # Crawl-delay is READ but not slept in this suite: pacing is proved by
        # tests/test_taxonomy_domain_throttle.sh, and honouring Microsoft's
        # declared 10s here would add 10s per run for nothing.
        "robots": {"enabled": True, "respect_crawl_delay": False,
                   "cache_ttl_sec": 3600, "unavailable_4xx_policy": "allow",
                   "unreachable_5xx_policy": "disallow"},
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


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pool = pool_mod.CandidatePool(RUN)
        self.cache = sc.SourceFetchCache(self.pool, clock=lambda: NOW)

    def build(self, source_fixtures=None, robots_fixtures=None, pol=None):
        self.opener = fixtures.FixtureOpener(
            sources=source_fixtures, robots=robots_fixtures)
        self.client = hc.HttpClient(pol or policy(), lease_root=self.tmp,
                                    opener=self.opener, sleep=lambda s: None)
        return self.client

    def run_source(self, source, lane_id=LANE, budget=None, **kw):
        if not hasattr(self, "client"):
            self.build()
        return adapters.discover(source, cache=self.cache, client=self.client,
                                 budget=budget, lane_id=lane_id, clock=lambda: NOW,
                                 **kw)

    @staticmethod
    def inline(source, body, ctype, status=200):
        """A one-off fixture for a source, so malformed bodies stay out of the
        committed corpus (which must remain format-conformant)."""
        import base64
        return {source["fixture_id"]: {
            "fixture_id": source["fixture_id"], "source_id": source["source_id"],
            "url": source["url"], "provenance": "synthetic", "authored_at": NOW,
            "authored_against": "test-local", "status": status,
            "headers": {"content-type": ctype},
            "body_b64": base64.b64encode(body.encode("utf-8")).decode("ascii")}}


# ------------------------------------------------------------------ registry
class TestRegistry(Harness):
    def test_every_configured_adapter_name_resolves(self):
        names = {s["adapter"] for s in SOURCES}
        self.assertEqual(names, {"feed", "jsonapi", "seed"})
        for name in names:
            self.assertEqual(adapters.get_adapter(name).name, name)

    def test_deferred_adapters_raise_rather_than_falling_back(self):
        for name in ("sitemap", "model_search"):
            with self.subTest(name=name):
                with self.assertRaises(adapters.AdapterNotImplemented) as cm:
                    adapters.get_adapter(name)
                self.assertEqual(cm.exception.name, name)

    def test_an_unknown_adapter_name_raises(self):
        with self.assertRaises(adapters.AdapterNotImplemented):
            adapters.get_adapter("telepathy")

    def test_deferred_adapters_never_return_an_empty_success(self):
        source = dict(BY_ID["aws-ml-blog"], adapter="sitemap")
        with self.assertRaises(adapters.AdapterNotImplemented):
            self.run_source(source)

    def test_result_and_reason_vocabularies_are_disjoint_and_classified(self):
        self.assertFalse(base.ZERO_RESULT_REASONS & base.ADAPTER_ERROR_REASONS)
        self.assertFalse(base.ZERO_RESULT_REASONS & base.INFRASTRUCTURE_ERROR_REASONS)
        self.assertFalse(base.ADAPTER_ERROR_REASONS & base.INFRASTRUCTURE_ERROR_REASONS)
        self.assertEqual(base.classify("feed_parse_error"), base.RESULT_ADAPTER_ERROR)
        self.assertEqual(base.classify("robots_denied"), base.RESULT_INFRASTRUCTURE_ERROR)
        self.assertEqual(base.classify("http_4xx"), base.RESULT_INFRASTRUCTURE_ERROR)
        # an unknown reason is OUR bug, never reported as a remote failure
        self.assertEqual(base.classify("something_new"), base.RESULT_ADAPTER_ERROR)

    def test_all_25_configured_sources_execute_through_their_fixture(self):
        self.build()
        results = [self.run_source(s) for s in SOURCES]
        self.assertEqual(len(results), 25)
        for source, result in zip(SOURCES, results):
            with self.subTest(source=source["source_id"]):
                self.assertTrue(result.ok, "%s -> %s/%s: %s" % (
                    source["source_id"], result.result, result.reason, result.detail))
                self.assertEqual(result.adapter, source["adapter"])
        self.assertEqual(len(self.pool.sources), 25, "one snapshot per source")

    def test_the_cap_is_strict_and_applied_in_document_order(self):
        self.build()
        for source in SOURCES:
            with self.subTest(source=source["source_id"]):
                result = self.run_source(source, lane_id="lane-%s" % source["source_id"])
                self.assertLessEqual(len(result.candidates), source["max_candidates"])
                self.assertEqual([c.position for c in result.candidates],
                                 list(range(len(result.candidates))))

    def test_a_cap_of_one_keeps_the_first_entry_only(self):
        source = dict(BY_ID["aws-ml-blog"], max_candidates=1)
        full = self.run_source(BY_ID["aws-ml-blog"])
        capped = self.run_source(source, lane_id="lane-capped")
        self.assertEqual(len(capped.candidates), 1)
        self.assertEqual(capped.candidates[0].target_url, full.candidates[0].target_url)
        self.assertEqual(capped.dropped_over_cap, len(full.candidates) - 1)


# ---------------------------------------------------------------------- feed
class TestFeedAdapter(Harness):
    RSS = ('<?xml version="1.0"?><rss version="2.0" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
           "<title>Chan</title><link>https://aws.amazon.com/</link>"
           "<item><title>First &amp; best</title>"
           "<link>https://aws.amazon.com/a</link>"
           "<description><![CDATA[Body <b>one</b>]]></description>"
           "<pubDate>Mon, 20 Jul 2026 00:00:00 GMT</pubDate>"
           "<dc:creator>Rita</dc:creator></item>"
           "<item><title>Second</title><link>/relative-two</link>"
           "<description>Body two</description></item>"
           "</channel></rss>")

    ATOM = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            "<title>Releases</title>"
            "<entry><title>v2</title>"
            '<link rel="enclosure" href="https://github.com/pkg.zip"/>'
            '<link rel="alternate" href="https://github.com/o/r/releases/v2"/>'
            "<summary>Notes</summary><updated>2026-07-20T00:00:00Z</updated>"
            "<author><name>Ada</name></author></entry></feed>")

    def rss_source(self):
        return BY_ID["aws-ml-blog"]

    def test_representative_rss_2_0(self):
        s = self.rss_source()
        self.build(self.inline(s, self.RSS, "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_OK)
        first = r.candidates[0]
        self.assertEqual(first.target_url, "https://aws.amazon.com/a")
        self.assertEqual(first.title, "First & best")
        self.assertEqual(first.summary, "Body <b>one</b>")
        self.assertEqual(first.published_at, "Mon, 20 Jul 2026 00:00:00 GMT")
        self.assertEqual(first.publisher, "Rita")

    def test_representative_atom(self):
        s = BY_ID["oss-ollama-releases"]
        self.build(self.inline(s, self.ATOM, "application/atom+xml"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_OK)
        self.assertEqual(r.candidates[0].title, "v2")
        self.assertEqual(r.candidates[0].publisher, "Ada")

    def test_atom_link_selection_prefers_alternate_over_enclosure(self):
        s = BY_ID["oss-ollama-releases"]
        self.build(self.inline(s, self.ATOM, "application/atom+xml"))
        r = self.run_source(s)
        self.assertEqual(r.candidates[0].target_url,
                         "https://github.com/o/r/releases/v2")
        self.assertNotIn("pkg.zip", r.candidates[0].target_url)

    def test_namespaces_are_handled_without_source_specific_branches(self):
        s = self.rss_source()
        self.build(self.inline(s, self.RSS, "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.candidates[0].publisher, "Rita")   # dc:creator
        source_text = module_code(feed_mod)
        for source_id in BY_ID:
            self.assertNotIn(source_id, source_text,
                             "feed.py must contain no per-source branch")

    def test_relative_links_resolve_against_the_document_base(self):
        s = self.rss_source()
        self.build(self.inline(s, self.RSS, "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.candidates[1].target_url,
                         "https://aws.amazon.com/relative-two")

    def test_an_entry_without_any_link_is_skipped_not_fatal(self):
        body = ('<rss version="2.0"><channel><title>c</title>'
                "<item><title>no link here</title></item>"
                "<item><title>has one</title>"
                "<link>https://aws.amazon.com/kept</link></item>"
                "</channel></rss>")
        s = self.rss_source()
        self.build(self.inline(s, body, "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_OK)
        self.assertEqual(len(r.candidates), 1)
        self.assertEqual(r.candidates[0].target_url, "https://aws.amazon.com/kept")

    def test_a_permalink_guid_substitutes_for_a_missing_link(self):
        body = ('<rss version="2.0"><channel><title>c</title><item>'
                "<title>guid only</title>"
                "<guid>https://aws.amazon.com/from-guid</guid>"
                "</item></channel></rss>")
        s = self.rss_source()
        self.build(self.inline(s, body, "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.candidates[0].target_url, "https://aws.amazon.com/from-guid")

    def test_malformed_xml_is_an_adapter_error(self):
        s = self.rss_source()
        self.build(self.inline(s, "<rss><channel><item></rss", "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ADAPTER_ERROR)
        self.assertEqual(r.reason, "feed_parse_error")
        self.assertEqual(len(self.pool.sources), 1,
                         "the fetch succeeded; only parsing failed")

    def test_a_well_formed_empty_feed_is_a_zero_result_not_an_error(self):
        s = self.rss_source()
        self.build(self.inline(s, '<rss version="2.0"><channel>'
                                  "<title>c</title></channel></rss>",
                               "application/rss+xml"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ZERO)
        self.assertEqual(r.reason, "no_items_in_window")
        self.assertFalse(r.failed)
        self.assertTrue(r.ok)

    def test_html_served_as_a_feed_is_an_adapter_error(self):
        s = self.rss_source()
        self.build(self.inline(s, "<html><body>nope</body></html>", "text/html"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ADAPTER_ERROR)
        self.assertEqual(r.reason, "unexpected_content_type")

    def test_output_is_deterministic_across_repeated_runs(self):
        blobs = set()
        for i in range(5):
            self.setUp()
            self.build()
            r = self.run_source(BY_ID["techcrunch-ai"])
            blobs.add(json.dumps([c.__getstate__() if hasattr(c, "__getstate__")
                                  else [c.target_url, c.title, c.position]
                                  for c in r.candidates], sort_keys=True))
        self.assertEqual(len(blobs), 1)


# ------------------------------------------------------------------- jsonapi
class TestJsonApiAdapter(Harness):
    def test_both_configured_apis_map_their_fields(self):
        self.build()
        fr = self.run_source(BY_ID["federal-register-ai"])
        self.assertEqual(fr.result, base.RESULT_OK)
        self.assertEqual(fr.candidates[0].publisher, "Agency Number 1")
        self.assertTrue(fr.candidates[0].target_url.startswith(
            "https://www.federalregister.gov/documents/"))
        self.assertEqual(fr.candidates[0].published_at, "2026-07-11")

        hn = self.run_source(BY_ID["hn-algolia"], lane_id="lane-hn")
        self.assertEqual(hn.result, base.RESULT_OK)
        self.assertEqual(hn.candidates[0].publisher, "poster1")

    def test_numeric_list_indexing_in_a_dotted_path(self):
        self.assertEqual(
            jsonapi_mod.resolve_path({"agencies": [{"name": "A"}, {"name": "B"}]},
                                     "agencies.0.name"), "A")
        self.assertEqual(
            jsonapi_mod.resolve_path({"agencies": [{"name": "A"}, {"name": "B"}]},
                                     "agencies.1.name"), "B")

    def test_a_missing_path_yields_missing_not_an_exception(self):
        self.assertIs(jsonapi_mod.resolve_path({"a": 1}, "a.b.c"),
                      jsonapi_mod._MISSING)
        self.assertIs(jsonapi_mod.resolve_path({"a": [1]}, "a.7"),
                      jsonapi_mod._MISSING)

    def test_optional_missing_fields_become_none(self):
        s = BY_ID["hn-algolia"]
        body = json.dumps({"hits": [{"url": "https://example.com/x"}]})
        self.build(self.inline(s, body, "application/json"))
        r = self.run_source(s)
        c = r.candidates[0]
        self.assertIsNone(c.title)
        self.assertIsNone(c.publisher)
        self.assertIsNone(c.published_at)

    def test_an_item_without_a_usable_target_url_is_skipped(self):
        self.build()
        fr = self.run_source(BY_ID["federal-register-ai"])
        self.assertEqual(len(fr.candidates), 3, "the 4th item has no html_url")
        hn = self.run_source(BY_ID["hn-algolia"], lane_id="lane-hn2")
        self.assertEqual(len(hn.candidates), 3, "the 4th hit has url null")

    def test_a_relative_target_url_is_refused_rather_than_guessed(self):
        s = BY_ID["hn-algolia"]
        body = json.dumps({"hits": [{"url": "/relative", "title": "t"}]})
        self.build(self.inline(s, body, "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ZERO)

    def test_malformed_json_is_a_mapping_error(self):
        s = BY_ID["hn-algolia"]
        self.build(self.inline(s, "{not json", "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ADAPTER_ERROR)
        self.assertEqual(r.reason, "schema_mapping_failed")

    def test_a_wrong_items_container_type_is_a_mapping_error(self):
        s = BY_ID["hn-algolia"]
        self.build(self.inline(s, json.dumps({"hits": {"not": "a list"}}),
                               "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ADAPTER_ERROR)
        self.assertEqual(r.reason, "schema_mapping_failed")

    def test_a_missing_items_path_is_a_mapping_error(self):
        s = BY_ID["hn-algolia"]
        self.build(self.inline(s, json.dumps({"other": []}), "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.reason, "schema_mapping_failed")

    def test_scalars_where_objects_belong_are_a_mapping_error(self):
        s = BY_ID["hn-algolia"]
        self.build(self.inline(s, json.dumps({"hits": [1, 2, 3]}),
                               "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.reason, "schema_mapping_failed")

    def test_an_empty_items_array_is_a_zero_result(self):
        s = BY_ID["hn-algolia"]
        self.build(self.inline(s, json.dumps({"hits": []}), "application/json"))
        r = self.run_source(s)
        self.assertEqual(r.result, base.RESULT_ZERO)
        self.assertEqual(r.reason, "no_items_in_window")

    def test_there_is_no_per_api_hard_coded_parser(self):
        text = module_code(jsonapi_mod).lower()
        for needle in ("federal", "algolia", "hn-", "federalregister"):
            self.assertNotIn(needle, text)

    def test_the_cap_applies_after_deterministic_traversal(self):
        s = dict(BY_ID["hn-algolia"], max_candidates=2)
        r = self.run_source(s)
        self.assertEqual(len(r.candidates), 2)
        self.assertEqual(r.dropped_over_cap, 1)


# ---------------------------------------------------------------------- seed
class TestSeedAdapter(Harness):
    def source(self):
        return BY_ID["anthropic-customers"]

    def test_absolute_and_relative_allowlisted_links_are_kept(self):
        self.build()
        r = self.run_source(self.source())
        urls = [c.target_url for c in r.candidates]
        self.assertIn("https://www.anthropic.com/customers/acme-industrial", urls)
        self.assertIn("https://www.anthropic.com/customers/initech-finance", urls)

    def test_off_host_and_disallowed_paths_are_excluded(self):
        self.build()
        urls = [c.target_url for c in self.run_source(self.source()).candidates]
        self.assertNotIn("https://example.com/customers/off-host", urls)
        for url in urls:
            self.assertTrue(url.startswith("https://www.anthropic.com/customers/"))
        self.assertFalse([u for u in urls if u.endswith("/pricing")])

    def test_a_relative_link_resolving_outside_the_allowlist_is_dropped(self):
        # href="sub-page" resolves to https://www.anthropic.com/sub-page, which
        # is not under /customers/ — proving resolution happens BEFORE filtering.
        self.build()
        urls = [c.target_url for c in self.run_source(self.source()).candidates]
        self.assertNotIn("https://www.anthropic.com/sub-page", urls)

    def test_non_http_schemes_are_ignored(self):
        self.build()
        urls = [c.target_url for c in self.run_source(self.source()).candidates]
        self.assertFalse([u for u in urls if u.startswith("mailto:")])

    def test_in_page_duplicates_collapse_preserving_document_order(self):
        self.build()
        urls = [c.target_url for c in self.run_source(self.source()).candidates]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(urls[0], "https://www.anthropic.com/customers/acme-industrial")

    def test_depth_is_structurally_one_and_a_child_index_is_not_expanded(self):
        self.build()
        result = self.run_source(self.source())
        urls = [c.target_url for c in result.candidates]
        # the fixture contains a child that is itself an index; it is a
        # candidate, never something the adapter follows
        self.assertIn("https://www.anthropic.com/customers/index-of-more", urls)
        fetched = [u for u in self.opener.calls if not u.endswith("robots.txt")]
        self.assertEqual(fetched, [self.source()["url"]],
                         "exactly one body fetched: the index itself")

    def test_no_child_target_page_is_ever_fetched(self):
        self.build()
        self.run_source(self.source())
        for url in self.opener.calls:
            self.assertFalse(url.startswith("https://www.anthropic.com/customers/"),
                             "seed must not fetch a child body in Stage 3")

    def test_depth_is_a_module_constant_with_no_expansion_path(self):
        self.assertEqual(seed_mod._SEED_DEPTH, 1)
        text = module_code(seed_mod).lower()
        for banned in ("while queue", "recurs", "depth +", "depth+1", "depth = 2"):
            self.assertNotIn(banned, text)

    def test_an_empty_allowlist_fails_closed(self):
        s = dict(self.source())
        s["seed"] = dict(s["seed"], path_prefix_allowlist=[])
        self.build()
        r = self.run_source(s, lane_id="lane-closed")
        self.assertEqual(r.result, base.RESULT_ZERO)
        self.assertEqual(r.reason, "no_links_matched_allowlist")
        self.assertEqual(len(r.candidates), 0)

    def test_a_missing_allowlist_also_fails_closed(self):
        s = dict(self.source())
        s["seed"] = {"mode": "index"}
        self.build()
        r = self.run_source(s, lane_id="lane-closed2")
        self.assertEqual(r.result, base.RESULT_ZERO)

    def test_max_children_bounds_output_in_document_order(self):
        s = dict(self.source())
        s["seed"] = dict(s["seed"], max_children=2)
        self.build()
        r = self.run_source(s, lane_id="lane-two")
        self.assertEqual(len(r.candidates), 2)
        self.assertEqual(r.candidates[0].target_url,
                         "https://www.anthropic.com/customers/acme-industrial")

    def test_malformed_html_cannot_create_an_unbounded_crawl(self):
        s = self.source()
        body = ('<html><body><a href="/customers/one">one<a href="/customers/two">'
                "two<div><a href=/customers/three>three</body>")
        self.build(self.inline(s, body, "text/html"))
        r = self.run_source(s)
        self.assertTrue(r.ok)
        self.assertLessEqual(len(r.candidates), s["max_candidates"])
        fetched = [u for u in self.opener.calls if not u.endswith("robots.txt")]
        self.assertEqual(len(fetched), 1)


# ------------------------------------------------------------ fixtures/robots
class TestFixtureAndRobotsPath(Harness):
    def test_every_configured_source_fixture_resolves(self):
        opener = fixtures.FixtureOpener()
        for source in SOURCES:
            with self.subTest(source=source["source_id"]):
                self.assertIsNotNone(opener.fixture_for_source(source))

    def test_every_configured_host_has_a_robots_fixture(self):
        from urllib.parse import urlsplit
        opener = fixtures.FixtureOpener()
        for host in sorted({urlsplit(s["url"]).hostname for s in SOURCES}):
            with self.subTest(host=host):
                self.assertIn(host, opener.robots)

    def test_an_unfixtured_url_fails_loudly(self):
        self.build()
        source = dict(BY_ID["aws-ml-blog"], url="https://aws.amazon.com/not-fixtured")
        with self.assertRaises(fixtures.FixtureMissing):
            self.opener(_Req("https://aws.amazon.com/not-fixtured"))

    def test_an_unfixtured_host_robots_fails_loudly_never_implicitly_allows(self):
        self.build()
        with self.assertRaises(fixtures.FixtureMissing):
            self.opener(_Req("https://never-configured.test/robots.txt"))

    def test_404_robots_means_allow_all_through_the_real_matcher(self):
        self.build()
        self.assertEqual(self.opener.robots["rss.arxiv.org"]["status"], 404)
        self.assertTrue(self.client.robots.allowed("https://rss.arxiv.org/rss/cs.AI"))

    def test_500_robots_fails_closed_through_the_real_matcher(self):
        self.build()
        self.assertEqual(self.opener.robots["robots-5xx.test"]["status"], 500)
        self.assertFalse(self.client.robots.allowed("https://robots-5xx.test/anything"))

    def test_a_declared_crawl_delay_is_read_from_the_fixture(self):
        self.build()
        self.assertEqual(
            self.client.robots.crawl_delay("https://blogs.microsoft.com/feed/"), 10)
        self.assertEqual(self.client.robots.crawl_delay("https://arxiv.org/abs/1"), 15)

    def test_declared_disallow_rules_are_enforced(self):
        self.build()
        self.assertFalse(self.client.robots.allowed("https://export.arxiv.org/abs/1"))
        self.assertFalse(self.client.robots.allowed("https://www.anthropic.com/internal/x"))
        self.assertTrue(self.client.robots.allowed("https://www.anthropic.com/customers"))

    def test_a_robots_denied_source_is_an_infrastructure_error_not_a_zero_result(self):
        source = dict(BY_ID["aws-ml-blog"])
        robots = dict(fixtures.load_robots_fixtures())
        robots["aws.amazon.com"] = dict(robots["aws.amazon.com"],
                                        body="User-agent: *\nDisallow: /\n")
        self.build(robots_fixtures=robots)
        r = self.run_source(source)
        self.assertEqual(r.result, base.RESULT_INFRASTRUCTURE_ERROR)
        self.assertEqual(r.reason, "robots_denied")
        self.assertEqual(self.pool.sources, {}, "no snapshot for a denied source")

    def test_no_adapter_or_cache_contains_a_fixture_special_case(self):
        # Checked on executable code, not prose: base.py's docstring explains
        # the fixture/live equivalence and would match a raw text scan.
        for module in (base, feed_mod, jsonapi_mod, seed_mod, adapters, sc):
            with self.subTest(module=module.__name__):
                text = module_code(module).lower()
                for needle in ("fixture", "is_test", "offline", "testmode"):
                    self.assertNotIn(needle, text)


class _Req:
    def __init__(self, url):
        self.full_url = url


# ------------------------------------------------------------ static boundary
class TestStaticBoundaries(Harness):
    ADAPTER_FILES = ("__init__.py", "base.py", "feed.py", "jsonapi.py", "seed.py")

    def _adapter_sources(self):
        """(filename, executable code) — docstrings and comments stripped."""
        directory = os.path.join(ROOT, "src", "harvest", "adapters")
        for name in self.ADAPTER_FILES:
            with open(os.path.join(directory, name), encoding="utf-8") as f:
                yield name, code_only(f.read())

    def test_no_network_module_is_imported_by_any_adapter(self):
        import ast
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                imported = set()
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Import):
                        imported.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".")[0])
                self.assertEqual(
                    imported & {"requests", "httpx", "aiohttp", "socket", "http",
                                "ssl", "subprocess", "asyncio"}, set())

    def test_no_adapter_opens_a_connection_itself(self):
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                for banned in ("urlopen(", "urlretrieve(", "socket.", "curl ",
                               "wget ", "getresponse("):
                    self.assertNotIn(banned, text)

    def test_adapters_do_not_import_the_fixture_module(self):
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                self.assertNotIn("fixtures", text)

    def test_no_adapter_writes_records_or_facets(self):
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                for banned in ("make_full_record", "case_facets", "facet_evidence",
                               "classification_state", "record_id", "identity_url"):
                    self.assertNotIn(banned, text)

    def test_no_adapter_establishes_a_pool_snapshot_directly(self):
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                for banned in ("acquire_source", "establish_snapshot",
                               "record_established_source", "reuse_snapshot"):
                    self.assertNotIn(banned, text)

    def test_no_adapter_passes_a_query_order_policy(self):
        for name, text in self._adapter_sources():
            with self.subTest(file=name):
                self.assertNotIn("query_order_policy", text)
                self.assertNotIn("sort-distinct-keys-stable", text)

    def test_the_request_key_uses_the_committed_default_policy(self):
        from src.harvest import request_key as rk
        self.build()
        source = BY_ID["federal-register-ai"]
        self.run_source(source)
        expected = rk.source_request_key(source["source_id"], source["url"],
                                         adapter="jsonapi", adapter_mode="index")
        self.assertIn(expected, self.pool.sources)

    def test_only_index_adapter_mode_is_used_in_stage_3(self):
        self.build()
        for source in SOURCES:
            self.run_source(source, lane_id="lane-mode-%s" % source["source_id"])
        modes = {snap["adapter_mode"] for snap in self.pool.sources.values()}
        self.assertEqual(modes, {"index"})


# ----------------------------------------------------------- pool integration
class TestPoolIntegration(Harness):
    def test_the_pool_document_validates_after_every_source(self):
        self.build()
        for source in SOURCES:
            self.run_source(source, lane_id="lane-%s" % source["source_id"])
        doc = self.pool.to_document(NOW)
        self.assertEqual(schema.validate(doc, "candidate_pool.v1.json"), [])
        self.assertEqual(len(doc["sources"]), 25)

    def test_accounting_comes_from_the_response_not_from_client_stats(self):
        self.build()
        budget = RequestBudget().push("cell", max_requests=50)
        result = self.run_source(BY_ID["aws-ml-blog"], budget=budget)
        self.assertEqual(result.accounting.attempts, 1)
        self.assertEqual(result.accounting.retries, 0)
        self.assertEqual(result.accounting.request_charges, 1)
        self.assertEqual(result.requests_made, 1)
        snapshot = list(self.pool.sources.values())[0]["http_attempts"]
        self.assertEqual(snapshot["attempts"], 1)
        self.assertEqual(snapshot["budget_charged"], 1)

    def test_a_retry_is_reported_as_one_owner_with_several_attempts(self):
        import base64
        source = BY_ID["aws-ml-blog"]
        good = fixtures.load_source_fixtures()[source["fixture_id"]]
        calls = {"n": 0}
        real = fixtures.FixtureOpener()

        def flaky(req, timeout=20):
            if req.full_url == source["url"]:
                calls["n"] += 1
                if calls["n"] == 1:
                    import io
                    return 503, {}, io.BytesIO(b"")
            return real(req, timeout)

        self.client = hc.HttpClient(policy(), lease_root=self.tmp, opener=flaky,
                                    sleep=lambda s: None)
        self.opener = real
        budget = RequestBudget().push("cell", max_requests=50)
        result = adapters.discover(source, cache=self.cache, client=self.client,
                                   budget=budget, lane_id=LANE, clock=lambda: NOW)
        self.assertEqual(result.result, base.RESULT_OK)
        self.assertEqual(result.accounting.attempts, 2)
        self.assertEqual(result.accounting.retries, 1)
        self.assertEqual(len(self.pool.sources), 1, "still ONE logical owner")
        self.assertEqual(self.pool.accounting()["http_attempts"], 2)

    def test_a_failed_source_leaves_no_pool_row_and_a_valid_document(self):
        source = BY_ID["aws-ml-blog"]
        self.build(self.inline(source, "", "application/rss+xml", status=200))
        result = self.run_source(source)
        self.assertTrue(result.failed)
        self.assertEqual(result.reason, "empty_response")
        self.assertEqual(self.pool.sources, {})
        self.assertEqual(schema.validate(self.pool.to_document(NOW),
                                         "candidate_pool.v1.json"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
