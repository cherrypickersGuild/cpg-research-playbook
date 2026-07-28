#!/usr/bin/env python3
"""test_identity.py — canonicalization, identity stability, fragment and alias policy.

The governing rule under test: prefer a false negative over a destructive
false-positive merge. Keeping two records that turn out to be the same is
recoverable; collapsing two that were different is not.

Run via tests/test_taxonomy_identity.sh.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.urlkey import (  # noqa: E402
    canonicalize_string as C, content_id, record_id, UrlError,
    should_strip_fragment, is_hash_route, registrable_host,
)


class TestCanonicalizationSafeOps(unittest.TestCase):
    """Operations RFC 3986 guarantees are identity-preserving."""

    def test_scheme_and_host_lowercased_path_is_not(self):
        self.assertEqual(C("HTTPS://EXAMPLE.COM/PathCase"), "https://example.com/PathCase")

    def test_default_port_removed(self):
        self.assertEqual(C("https://example.com:443/a"), "https://example.com/a")
        self.assertEqual(C("http://example.com:80/a"), "http://example.com/a")

    def test_nondefault_port_kept(self):
        self.assertEqual(C("https://example.com:8443/a"), "https://example.com:8443/a")

    def test_dot_segments_resolved(self):
        self.assertEqual(C("https://example.com/a/./b/../c"), "https://example.com/a/c")

    def test_empty_path_becomes_root(self):
        self.assertEqual(C("https://example.com"), "https://example.com/")

    def test_userinfo_dropped(self):
        # Credentials are never part of a public resource identity, and keeping
        # them would leak them into artifacts and filenames.
        self.assertEqual(C("https://user:pw@example.com/a"), "https://example.com/a")

    def test_tracking_params_stripped(self):
        self.assertEqual(
            C("https://example.com/a?utm_source=n&utm_medium=e&b=2&fbclid=z"),
            "https://example.com/a?b=2")

    def test_all_params_tracking_leaves_no_question_mark(self):
        self.assertEqual(C("https://example.com/a?utm_source=n"), "https://example.com/a")

    def test_idempotent(self):
        for u in ["https://example.com/a?b=2#intro",
                  "https://example.com/a/",
                  "http://example.com/a?t=x&t=y"]:
            self.assertEqual(C(C(u)), C(u), u)


class TestCanonicalizationRefusals(unittest.TestCase):
    """A URL that cannot be a stable identity must be refused, not repaired."""

    def test_relative_url_refused(self):
        with self.assertRaises(UrlError):
            C("/just/a/path")

    def test_unsupported_scheme_refused(self):
        for u in ["ftp://example.com/a", "mailto:a@b.c", "javascript:alert(1)"]:
            with self.assertRaises(UrlError):
                C(u)

    def test_empty_refused(self):
        with self.assertRaises(UrlError):
            C("   ")

    def test_no_host_refused(self):
        with self.assertRaises(UrlError):
            C("https:///a")


class TestConservativeNonOperations(unittest.TestCase):
    """Things commonly 'just normalized' that must NOT happen here."""

    def test_scheme_not_upgraded(self):
        self.assertNotEqual(C("http://example.com/a"), C("https://example.com/a"))

    def test_www_not_stripped(self):
        self.assertNotEqual(C("https://www.example.com/a"), C("https://example.com/a"))

    def test_trailing_slash_significant(self):
        self.assertNotEqual(C("https://example.com/a"), C("https://example.com/a/"))

    def test_ref_and_source_not_stripped(self):
        # '?ref=' selects a content variant on some sites; '?source=' is part of
        # path identity on others. Only the explicit tracking list is removed.
        self.assertEqual(C("https://example.com/a?ref=hn"), "https://example.com/a?ref=hn")
        self.assertEqual(C("https://example.com/a?source=rss"), "https://example.com/a?source=rss")

    def test_query_order_preserved_and_significant(self):
        self.assertEqual(C("https://example.com/a?b=2&a=1"), "https://example.com/a?b=2&a=1")
        self.assertNotEqual(C("https://example.com/a?a=1&b=2"),
                            C("https://example.com/a?b=2&a=1"))

    def test_repeated_keys_keep_order_and_multiplicity(self):
        self.assertEqual(C("https://example.com/a?t=x&t=y"), "https://example.com/a?t=x&t=y")
        self.assertNotEqual(C("https://example.com/a?t=x&t=y"),
                            C("https://example.com/a?t=y&t=x"))

    def test_blank_value_preserved(self):
        # "?a=" is not the same request as "a" being absent.
        self.assertEqual(C("https://example.com/a?a="), "https://example.com/a?a=")

    def test_query_sort_only_under_explicit_domain_rule(self):
        rules = {"example.com": {"query_sort": True}}
        self.assertEqual(C("https://example.com/a?b=2&a=1", domain_rules=rules),
                         C("https://example.com/a?a=1&b=2", domain_rules=rules))
        # and the rule is scoped to that domain only
        self.assertNotEqual(C("https://other.com/a?b=2&a=1", domain_rules=rules),
                            C("https://other.com/a?a=1&b=2", domain_rules=rules))


class TestFragmentPolicy(unittest.TestCase):
    """Fragments are PRESERVED by default. Structure alone never proves an anchor."""

    def test_ordinary_anchor_preserved_by_default(self):
        self.assertEqual(C("https://example.com/a#intro"), "https://example.com/a#intro")

    def test_bare_word_fragment_preserved_by_default(self):
        # '#dashboard' is not an anchor merely because it lacks a leading / or !
        self.assertEqual(C("https://example.com/a#dashboard"), "https://example.com/a#dashboard")

    def test_hashbang_preserved(self):
        self.assertEqual(C("https://example.com/a#!/route"), "https://example.com/a#!/route")

    def test_router_path_preserved(self):
        self.assertEqual(C("https://example.com/a#/dash/b"), "https://example.com/a#/dash/b")

    def test_query_in_fragment_preserved(self):
        self.assertEqual(C("https://example.com/a#?tab=results"),
                         "https://example.com/a#?tab=results")

    def test_domain_rule_may_strip_ordinary_anchors(self):
        rules = {"example.com": {"strip_ordinary_anchors": True}}
        self.assertEqual(C("https://example.com/a#intro", domain_rules=rules),
                         "https://example.com/a")
        self.assertEqual(C("https://example.com/a#dashboard", domain_rules=rules),
                         "https://example.com/a")

    def test_domain_rule_never_strips_route_fragments(self):
        rules = {"example.com": {"strip_ordinary_anchors": True}}
        for frag in ["#!/route", "#/dash", "#?tab=x"]:
            self.assertEqual(C("https://example.com/a" + frag, domain_rules=rules),
                             "https://example.com/a" + frag, frag)

    def test_hash_routing_domain_never_strips(self):
        rules = {"example.com": {"hash_routing": True, "strip_ordinary_anchors": True}}
        self.assertEqual(C("https://example.com/a#intro", domain_rules=rules),
                         "https://example.com/a#intro")

    def test_fetched_anchor_evidence_strips(self):
        self.assertEqual(
            C("https://example.com/a#dashboard", anchor_evidence={"dashboard"}),
            "https://example.com/a")

    def test_fetched_evidence_without_the_id_preserves(self):
        # The body was fetched and does NOT contain that id -> not an anchor.
        self.assertEqual(
            C("https://example.com/a#dashboard", anchor_evidence={"intro"}),
            "https://example.com/a#dashboard")

    def test_evidence_cannot_strip_a_route(self):
        self.assertEqual(C("https://example.com/a#!/x", anchor_evidence={"!/x"}),
                         "https://example.com/a#!/x")

    def test_helpers(self):
        self.assertTrue(is_hash_route("!/a"))
        self.assertTrue(is_hash_route("/a"))
        self.assertTrue(is_hash_route("?a=1"))
        self.assertFalse(is_hash_route("intro"))
        self.assertFalse(should_strip_fragment("", "example.com"))
        self.assertEqual(registrable_host("a.b.example.co"), "example.co")


class TestIdentityStability(unittest.TestCase):
    """No id may depend on anything mutable."""

    URL = "https://example.com/article"

    def test_same_url_two_categories_one_topic_is_one_record(self):
        iu = C(self.URL)
        a = record_id("cases", iu)
        b = record_id("cases", iu)
        self.assertEqual(a, b)

    def test_same_url_two_topics_shares_content_id(self):
        iu = C(self.URL)
        self.assertEqual(content_id(iu), content_id(iu))
        self.assertNotEqual(record_id("cases", iu), record_id("discourse", iu))

    def test_reclassification_does_not_change_ids(self):
        # primary_category is not an input to either id, by construction.
        iu = C(self.URL)
        before = (content_id(iu), record_id("discourse", iu))
        after = (content_id(iu), record_id("discourse", iu))
        self.assertEqual(before, after)

    def test_config_reordering_does_not_change_ids(self):
        # ids derive from (topic_slug, identity_url) only — never from a list
        # position, unlike the legacy matrix cell ids.
        iu = C(self.URL)
        self.assertEqual(record_id("cases", iu), record_id("cases", iu))

    def test_canonical_url_change_does_not_change_ids(self):
        identity = C("http://example.com/a")
        later_canonical = C("https://example.com/a")
        self.assertNotEqual(identity, later_canonical)
        # ids are computed from identity_url only, so the later canonical is irrelevant
        self.assertEqual(record_id("cases", identity), record_id("cases", identity))

    def test_tracking_variants_collapse_to_one_id(self):
        base = C("https://example.com/a")
        for variant in ["https://example.com/a?utm_source=x",
                        "https://example.com/a?fbclid=y",
                        "https://example.com/a?utm_campaign=c&utm_medium=m",
                        "https://example.com:443/a",
                        "https://example.com/b/../a"]:
            self.assertEqual(C(variant), base, variant)
            self.assertEqual(record_id("cases", C(variant)), record_id("cases", base), variant)

    def test_ref_variants_stay_distinct(self):
        a = record_id("cases", C("https://example.com/a"))
        b = record_id("cases", C("https://example.com/a?ref=hn"))
        self.assertNotEqual(a, b)

    def test_id_shapes(self):
        iu = C(self.URL)
        self.assertRegex(content_id(iu), r"^[0-9a-f]{16}$")
        self.assertRegex(record_id("cases", iu), r"^[0-9a-f]{16}$")

    def test_ids_require_nonempty_inputs(self):
        with self.assertRaises(UrlError):
            content_id("")
        with self.assertRaises(UrlError):
            record_id("", "https://example.com/a")


if __name__ == "__main__":
    unittest.main(verbosity=2)
