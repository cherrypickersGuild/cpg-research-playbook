#!/usr/bin/env python3
"""test_migration.py — Stage 7 migration: the entity assessment (S7-1) and the
suspicious-URL guard (S7-2).

S7-2's guard decides whether a legacy case page is refused, so the failures that
matter are the ones that would refuse a legitimate page or admit an index one:

  * substring matching creeping back in. Read as substrings, the master plan's
    wording refuses five real pages in the protected corpus — four
    `cloud.google.com` posts caught by `google.` and one LinkedIn article whose
    path contains a `/search/` segment (erratum E24). Both are pinned here as
    negative controls, alongside `research.example.com`, `/feeds/`, `/tags/`,
    `?faq=`, and a query VALUE containing a search token;
  * a rule that cannot fire. Each of the four has several positive examples, so
    "zero matches on the corpus" is a finding about the corpus rather than a
    guard that never worked;
  * unstable precedence. A URL satisfying two rules must always be reported under
    the same one, so the committed first-match order is pinned in both directions;
  * a malformed input being filed under a suspicious rule. "This is not a URL" and
    "this is a search page" are different findings, and the guard raises for the
    first rather than inventing a verdict;
  * a rewritten URL. The guard refuses and nothing else — `GuardMatch` has no
    field that could carry a replacement, and the suite checks the detail text
    too.

S7-1's assessment is a document a reviewer will make a product decision from, so
the failures worth pinning there are the ones that would make it quietly WRONG
rather than obviously broken:

The assessment is a document a reviewer will make a product decision from, so
the failures worth pinning are the ones that would make it quietly WRONG rather
than obviously broken:

  * a row skipped because it was malformed. Every count in the document would be
    wrong by an unknown amount and nothing would say so, which is why a bad row
    raises instead of being dropped;
  * a count that does not reconcile. Subtotals are checked against the population
    AND against the registry's own `metadata`, so a missing row cannot hide
    inside a plausible-looking table;
  * bytes that depend on input order. The registry is a merged file whose row
    order is an artefact of merging, so a document that changed when rows moved
    would produce a diff nobody could explain — reversal and a seeded shuffle
    must both render identically;
  * a committed document that has drifted from the implementation. It is
    generated, never hand-edited, and the suite fails if the two disagree;
  * a claim that entities were migrated. Zero is structural here: there is no
    migration path in this module, and the suite proves it rather than trusting
    the prose;
  * the protected source being touched. It is read-only, and its bytes are
    compared before and after.

Duplicate analysis gets its own independent recomputation: the module's grouped
result is checked against a differently-written calculation in the test, so a
shared helper cannot make both agree on the same mistake.

Offline: no socket, no clock, no network. The only write in this file goes to an
injected temporary directory.
"""
import ast
import copy
import dataclasses
import hashlib
import json
import os
import random
import tempfile
import unittest
from unittest import mock

from src.harvest.migrate import base
from src.harvest.migrate import entity_assess as ea

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, *ea.SOURCE_PATH.split("/"))
DOCUMENT = os.path.join(ROOT, *ea.DOCUMENT_PATH.split("/"))
AX_REGISTRY = os.path.join(ROOT, "state", "ax_case_harvest_registry.json")

# The corpus this checkpoint was written against. Asserted, not printed.
EXPECTED_TOTAL = 1161

# The protected AX corpus S7-2's guard is measured against.
EXPECTED_AX_CASES = 231


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def a_row(**over):
    """A minimal row carrying exactly the required field set."""
    row = {
        "entity_id": "ent-2026-0001",
        "entity_key": "agent|thing",
        "topic": "agent",
        "entity_type": "product",
        "name": "Thing",
        "description": "A thing.",
        "description_source": "verified",
        "maintainer_or_vendor": "Someone",
        "freshness_signal": "2026 footer",
        "related_topics": [],
        "corroboration_count": 1,
        "conflicting_evidence_log": [],
        "source_url": "https://example.test/thing",
        "target_url": "https://example.test/thing",
        "github_stars": None,
        "discovery": {"first_seen_at": "2026-07-06",
                      "last_corroborated_at": "2026-07-06",
                      "found_via": [{"hit_id": "hit-1", "platform": "web"}]},
    }
    row.update(over)
    return row


def a_registry(rows):
    return {
        "schema_version": 2,
        "last_merged_at": "2026-07-22T03:17:22Z",
        "metadata": {"topics": sorted({r["topic"] for r in rows}),
                     "entity_types": sorted({r["entity_type"] for r in rows}),
                     "total_entities": len(rows),
                     "entity_count_by_topic": {},
                     "entity_count_by_entity_type": {}},
        "entities": rows,
    }


# ------------------------------------------------------- the protected corpus
class TestProtectedCorpus(unittest.TestCase):
    """The real registry, read-only."""

    @classmethod
    def setUpClass(cls):
        cls.digest_before = sha256_file(REGISTRY)
        cls.registry = ea.load_registry()
        cls.assessment = ea.assess(cls.registry)
        cls.text = ea.render(cls.assessment)

    def test_loads_and_holds_exactly_the_expected_corpus(self):
        self.assertEqual(len(self.registry["entities"]), EXPECTED_TOTAL)
        self.assertEqual(self.assessment["total"], EXPECTED_TOTAL)
        self.assertEqual(ea.EXPECTED_ENTITY_COUNT, EXPECTED_TOTAL)

    def test_declared_total_is_reconciled_not_trusted(self):
        rec = self.assessment["reconciliation"]
        self.assertEqual(rec["derived_total"], EXPECTED_TOTAL)
        self.assertEqual(rec["declared_total"], EXPECTED_TOTAL)
        self.assertTrue(rec["derived_matches_declared"])
        self.assertTrue(rec["derived_matches_expected"])
        # Non-vacuous: drop one row and the reconciliation must NOTICE, both
        # against metadata and against the expected corpus size.
        short = copy.deepcopy(self.registry)
        short["entities"].pop()
        broken = ea.assess(short)["reconciliation"]
        self.assertEqual(broken["derived_total"], EXPECTED_TOTAL - 1)
        self.assertFalse(broken["derived_matches_declared"])
        self.assertFalse(broken["derived_matches_expected"])

    def test_every_grouping_reconciles_to_the_population(self):
        a = self.assessment
        rec = a["reconciliation"]
        for key in ("topic_subtotal", "type_subtotal", "topic_type_subtotal",
                    "description_source_subtotal"):
            self.assertEqual(rec[key], EXPECTED_TOTAL, key)
        self.assertEqual(sum(c for _t, c in a["by_topic"]), EXPECTED_TOTAL)
        self.assertEqual(sum(c for _t, c in a["by_entity_type"]), EXPECTED_TOTAL)
        self.assertEqual(sum(c for _t, _e, c in a["by_topic_entity_type"]), EXPECTED_TOTAL)

    def test_groupings_agree_with_the_registrys_own_metadata(self):
        rec = self.assessment["reconciliation"]
        self.assertTrue(rec["declared_topic_agrees"])
        self.assertTrue(rec["declared_type_agrees"])
        # Non-vacuous: move one row to another topic and the agreement fails.
        moved = copy.deepcopy(self.registry)
        other = sorted({r["topic"] for r in moved["entities"]}
                       - {moved["entities"][0]["topic"]})[0]
        moved["entities"][0]["topic"] = other
        self.assertFalse(ea.assess(moved)["reconciliation"]["declared_topic_agrees"])

    def test_topic_by_type_matrix_is_sorted_and_complete(self):
        pairs = [(t, e) for t, e, _c in self.assessment["by_topic_entity_type"]]
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_source_bytes_are_unchanged_by_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            ea.write_assessment(os.path.join(tmp, "out.md"), self.text)
        self.assertEqual(sha256_file(REGISTRY), self.digest_before)


# ------------------------------------------------------------ identity claims
class TestIdentityAnalysis(unittest.TestCase):
    """Duplicate and repeated-identifier maths, recomputed independently."""

    @classmethod
    def setUpClass(cls):
        cls.registry = ea.load_registry()
        cls.rows = cls.registry["entities"]
        cls.identity = ea.assess(cls.registry)["identity"]

    def test_distinct_entity_id_matches_an_independent_count(self):
        seen = []
        for row in self.rows:
            if row["entity_id"] not in seen:
                seen.append(row["entity_id"])
        self.assertEqual(self.identity["entity_id_distinct"], len(seen))
        self.assertLess(self.identity["entity_id_distinct"], len(self.rows),
                        "entity_id is expected to be non-unique in this corpus")

    def test_repeated_group_totals_recomputed_a_different_way(self):
        tally = {}
        for row in self.rows:
            tally[row["entity_id"]] = tally.get(row["entity_id"], 0) + 1
        repeated = {k: v for k, v in tally.items() if v > 1}
        self.assertEqual(self.identity["repeated_id_groups"], len(repeated))
        self.assertEqual(self.identity["repeated_id_rows"], sum(repeated.values()))
        self.assertEqual(self.identity["largest_repeated_group"],
                         max(repeated.values()))
        # The arithmetic that ties the two together: excess rows == rows - distinct.
        self.assertEqual(len(self.rows) - self.identity["entity_id_distinct"],
                         sum(repeated.values()) - len(repeated))

    def test_duplicate_group_rows_sum_to_the_repeated_row_count(self):
        groups = self.identity["duplicate_groups"]
        self.assertEqual(sum(g["rows"] for g in groups),
                         self.identity["repeated_id_rows"])
        self.assertEqual(len(groups), self.identity["repeated_id_groups"])
        self.assertEqual([g["entity_id"] for g in groups],
                         [g["entity_id"] for g in
                          sorted(groups, key=lambda g: (-g["rows"], g["entity_id"]))])
        for group in groups:
            self.assertEqual(sorted(group["entity_keys"]), group["entity_keys"])
            self.assertEqual(len(group["entity_keys"]), group["rows"])

    def test_topic_qualification_does_not_repair_uniqueness(self):
        qualified = {(r["topic"], r["entity_id"]) for r in self.rows}
        self.assertEqual(self.identity["topic_qualified_distinct"], len(qualified))
        self.assertLess(len(qualified), len(self.rows))

    def test_entity_key_is_the_unique_one(self):
        self.assertEqual(self.identity["entity_key_distinct"], len(self.rows))
        self.assertEqual(self.identity["entity_key_blank"], 0)

    def test_exact_duplicate_rows_are_measured_separately_from_repeated_ids(self):
        canon = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in self.rows]
        self.assertEqual(self.identity["exact_duplicate_rows"],
                         len(canon) - len(set(canon)))
        # The two measurements are genuinely different: repeated ids exist here,
        # exact duplicate rows do not.
        self.assertEqual(self.identity["exact_duplicate_rows"], 0)
        self.assertGreater(self.identity["repeated_id_rows"], 0)

    def test_synthetic_corpus_with_known_answers(self):
        rows = [
            a_row(entity_id="ent-1", entity_key="agent|a", topic="agent"),
            a_row(entity_id="ent-1", entity_key="mcp|b", topic="mcp"),
            a_row(entity_id="ent-1", entity_key="skill|c", topic="skill"),
            a_row(entity_id="ent-2", entity_key="agent|d", topic="agent"),
        ]
        identity = ea.assess(a_registry(rows))["identity"]
        self.assertEqual(identity["entity_id_distinct"], 2)
        self.assertEqual(identity["repeated_id_groups"], 1)
        self.assertEqual(identity["repeated_id_rows"], 3)
        self.assertEqual(identity["largest_repeated_group"], 3)
        self.assertEqual(identity["repeated_id_groups_cross_topic"], 1)
        self.assertEqual(identity["repeated_id_groups_single_topic"], 0)
        self.assertEqual(identity["topic_qualified_distinct"], 4)
        self.assertEqual(identity["exact_duplicate_rows"], 0)

    def test_exact_duplicate_rows_are_detected_when_they_exist(self):
        rows = [a_row(), a_row(), a_row(entity_key="agent|other")]
        identity = ea.assess(a_registry(rows))["identity"]
        self.assertEqual(identity["exact_duplicate_rows"], 1)

    def test_url_measurements_recomputed_independently(self):
        urls = ea.assess(self.registry)["urls"]
        usable = [r["target_url"] for r in self.rows
                  if r["target_url"].startswith(("http://", "https://"))]
        self.assertEqual(urls["target_usable"], len(usable))
        self.assertEqual(urls["target_unusable"], len(self.rows) - len(usable))
        self.assertEqual(urls["distinct_usable_targets"], len(set(usable)))
        self.assertEqual(urls["target_usable"] + urls["target_unusable"], len(self.rows))
        self.assertGreater(urls["target_unusable"], 0)


# ------------------------------------------------------------ zero migration
class TestMigratesNothing(unittest.TestCase):

    def test_module_reports_zero_migrated_entities(self):
        self.assertEqual(ea.MIGRATED_ENTITY_COUNT, 0)
        assessment = ea.assess(ea.load_registry())
        self.assertEqual(assessment["migrated"], 0)

    def test_no_taxonomy_record_is_produced_anywhere(self):
        assessment, text = ea.build()
        # A record would be a dict carrying the committed identity fields. None
        # of the assessment's values is one, at any depth.
        record_markers = {"record_id", "content_id", "identity_url", "cell_id",
                          "primary_category", "verification_status"}

        def walk(node):
            if isinstance(node, dict):
                self.assertFalse(record_markers & set(node),
                                 "assessment carries record-shaped keys: %s"
                                 % sorted(record_markers & set(node)))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(assessment)
        self.assertIn("migrates 0 entities", text)

    def test_the_module_builds_no_records_and_writes_no_artifacts(self):
        """Structural: it does not even import the record or artifact machinery."""
        module_path = os.path.join(ROOT, "src", "harvest", "migrate", "entity_assess.py")
        with open(module_path, encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("make_full_record", "make_cross_reference",
                          "write_document", "write_atomic", "publish_run",
                          "import requests", "urllib.request", "socket"):
            self.assertNotIn(forbidden, source,
                             "entity_assess must not reach for %r" % forbidden)


# ------------------------------------------------------------ document bytes
class TestDeterministicDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = ea.load_registry()
        cls.text = ea.render(ea.assess(cls.registry))

    def test_rendering_twice_is_byte_identical(self):
        again = ea.render(ea.assess(ea.load_registry()))
        self.assertEqual(again.encode("utf-8"), self.text.encode("utf-8"))

    def test_reversed_rows_render_identically(self):
        reversed_registry = copy.deepcopy(self.registry)
        reversed_registry["entities"].reverse()
        self.assertNotEqual(reversed_registry["entities"], self.registry["entities"],
                            "the reversal must be non-vacuous")
        self.assertEqual(ea.render(ea.assess(reversed_registry)), self.text)

    def test_shuffled_rows_render_identically(self):
        for seed in (1, 7, 99):
            shuffled = copy.deepcopy(self.registry)
            random.Random(seed).shuffle(shuffled["entities"])
            self.assertNotEqual(shuffled["entities"], self.registry["entities"])
            self.assertEqual(ea.render(ea.assess(shuffled)), self.text,
                             "shuffle seed %d changed the document" % seed)

    def test_document_carries_no_timestamp_no_absolute_path_no_python_repr(self):
        # `last_merged_at` is the registry's own value and is allowed; a
        # generation timestamp is not, and would have to come from a clock.
        self.assertIn(self.registry["last_merged_at"], self.text)
        for token in ("C:/", "C:\\", "/Users/", "AppData", "Temp"):
            self.assertNotIn(token, self.text)
        for token in ("Counter(", "dict_keys", "defaultdict", "{'", "': '"):
            self.assertNotIn(token, self.text)

    def test_document_ends_with_exactly_one_newline(self):
        self.assertTrue(self.text.endswith("\n"))
        self.assertFalse(self.text.endswith("\n\n"))

    def test_required_sections_are_present_and_in_order(self):
        headings = [line for line in self.text.split("\n") if line.startswith("## ")]
        self.assertEqual(len(headings), 6)
        for index, expected in enumerate(
                ["Source and scope", "Population breakdown",
                 "Identity and duplicate analysis", "Field-mapping assessment",
                 "Candidate destinations", "Migration risks and required decisions"]):
            self.assertIn(expected, headings[index])

    def test_document_states_the_five_boundary_claims(self):
        for claim in ("migrates 0 entities",
                      "creates no taxonomy record",
                      "no migration bundle and no runtime state",
                      "unresolved product decision",
                      "does not classify entity rows as Product Discovery records"):
            self.assertIn(claim, self.text)

    def test_no_candidate_destination_is_described_as_approved(self):
        self.assertIn("None is approved, recommended or chosen", self.text)
        self.assertNotIn("we recommend", self.text.lower())

    def test_committed_document_matches_the_renderer(self):
        with open(DOCUMENT, "rb") as handle:
            committed = handle.read()
        self.assertEqual(committed, self.text.encode("utf-8"),
                         "the committed assessment is stale — regenerate it with "
                         "src/harvest/migrate/entity_assess.py rather than editing it")

    def test_field_mapping_covers_exactly_the_registry_fields(self):
        classified = sorted(f for f, _c, _n in ea.FIELD_CLASSIFICATION)
        self.assertEqual(classified, sorted(ea.REQUIRED_ROW_FIELDS))
        # Non-vacuous: a registry field the table does not classify must raise.
        assessment = ea.assess(self.registry)
        assessment["row_fields"] = list(assessment["row_fields"]) + ["surprise"]
        with self.assertRaises(ea.AssessmentError):
            ea.render(assessment)


# ------------------------------------------------------------- injected write
class TestInjectedOutputPath(unittest.TestCase):

    def test_writes_only_where_told(self):
        _assessment, text = ea.build()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "assessment.md")
            written = ea.write_assessment(out, text)
            with open(out, "rb") as handle:
                data = handle.read()
            self.assertEqual(data, text.encode("utf-8"))
            self.assertEqual(written, len(data))
            self.assertEqual(sorted(os.listdir(tmp)), ["assessment.md"])

    def test_an_empty_path_is_refused_rather_than_defaulted(self):
        with self.assertRaises(ea.AssessmentError):
            ea.write_assessment("", "text\n")

    def test_load_accepts_an_injected_registry_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "registry.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(a_registry([a_row()]), handle)
            self.assertEqual(len(ea.load_registry(path)["entities"]), 1)

    def test_no_repository_runtime_path_is_created(self):
        _assessment, text = ea.build()
        with tempfile.TemporaryDirectory() as tmp:
            ea.write_assessment(os.path.join(tmp, "out.md"), text)
        for leak in ("state/taxonomy_harvest", "data/harvested", "runs",
                     "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)),
                             "assessment created the runtime path %r" % leak)


# ---------------------------------------------------------- malformed inputs
class TestMalformedInputRaises(unittest.TestCase):
    """Nothing is skipped. Every one of these is a hard, specific failure."""

    def assert_refused(self, registry, needle):
        with self.assertRaises(ea.AssessmentError) as caught:
            ea.assess(registry)
        self.assertIn(needle, str(caught.exception))

    def test_top_level_must_be_an_object(self):
        self.assert_refused([], "must be a JSON object")

    def test_missing_top_level_key(self):
        registry = a_registry([a_row()])
        del registry["metadata"]
        self.assert_refused(registry, "missing the top-level key 'metadata'")

    def test_entities_must_be_an_array(self):
        registry = a_registry([a_row()])
        registry["entities"] = {"nope": True}
        self.assert_refused(registry, "`entities` must be an array")

    def test_metadata_must_be_an_object(self):
        registry = a_registry([a_row()])
        registry["metadata"] = []
        self.assert_refused(registry, "`metadata` must be an object")

    def test_row_must_be_an_object(self):
        registry = a_registry([a_row()])
        registry["entities"].append("not-a-row")
        self.assert_refused(registry, "entities[1] must be an object")

    def test_row_missing_a_required_field_names_row_and_field(self):
        row = a_row()
        del row["entity_key"]
        self.assert_refused(a_registry([row]),
                            "entities[0] is missing the required field 'entity_key'")

    def test_row_with_an_unrecognised_field_is_refused_not_ignored(self):
        self.assert_refused(a_registry([a_row(surprise="x")]),
                            "unrecognised field(s) 'surprise'")

    def test_discovery_must_be_an_object_with_its_three_keys(self):
        self.assert_refused(a_registry([a_row(discovery=[])]),
                            "discovery must be an object")
        broken = a_row()
        del broken["discovery"]["found_via"]
        self.assert_refused(a_registry([broken]), "discovery is missing 'found_via'")

    def test_found_via_must_be_an_array(self):
        row = a_row()
        row["discovery"]["found_via"] = {"hit_id": "x"}
        self.assert_refused(a_registry([row]), "found_via must be an array")

    def test_a_malformed_row_stops_the_run_rather_than_being_dropped(self):
        rows = [a_row(entity_key="agent|a"), a_row(entity_key="agent|b")]
        del rows[1]["name"]
        with self.assertRaises(ea.AssessmentError):
            ea.assess(a_registry(rows))

    def test_unreadable_and_invalid_json_paths_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope.json")
            with self.assertRaises(ea.AssessmentError):
                ea.load_registry(missing)
            broken = os.path.join(tmp, "broken.json")
            with open(broken, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            with self.assertRaises(ea.AssessmentError):
                ea.load_registry(broken)


# ============================================================== S7-2 · the guard
class TestGuardVocabulary(unittest.TestCase):

    def test_rule_ids_are_exactly_the_four_committed_ones_in_order(self):
        self.assertEqual(base.SUSPICIOUS_RULE_IDS,
                         ("search_engine_host", "search_query_path",
                          "feed_path", "index_page"))
        self.assertIsInstance(base.SUSPICIOUS_RULE_IDS, tuple)

    def test_rule_ids_match_the_committed_override_config_vocabulary(self):
        """The config names the same four. It is READ here, never written."""
        path = os.path.join(ROOT, "config", "harvest", "migration_overrides.v1.json")
        with open(path, encoding="utf-8") as handle:
            shape = json.load(handle)["ax_cases"]["_reviewed_unmappable_shape"]
        declared = [part.strip() for part in shape["matched_rule"].split("|")]
        self.assertEqual(sorted(declared), sorted(base.SUSPICIOUS_RULE_IDS))

    def test_guard_match_is_frozen_value_comparable_and_carries_no_url(self):
        one = base.GuardMatch(rule_id="feed_path", detail="d")
        two = base.GuardMatch(rule_id="feed_path", detail="d")
        self.assertEqual(one, two)
        self.assertNotEqual(one, base.GuardMatch(rule_id="feed_path", detail="e"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            one.rule_id = "index_page"
        self.assertEqual(sorted(f.name for f in dataclasses.fields(one)),
                         ["detail", "rule_id"])


class TestGuardPositives(unittest.TestCase):
    """Every rule has several examples, so none of them is inert."""

    CASES = (
        ("search_engine_host", "https://www.google.com/search?q=ai"),
        ("search_engine_host", "https://google.com/"),
        ("search_engine_host", "https://www.bing.com/search?q=llm"),
        ("search_engine_host", "https://duckduckgo.com/?q=agents"),
        ("search_engine_host", "https://yandex.ru/"),
        ("search_engine_host", "https://search.marginalia.nu/thing"),
        ("search_query_path", "https://example.test/blog/search"),
        ("search_query_path", "https://example.test/blog/search/"),
        ("search_query_path", "https://example.test/posts?q=ai"),
        ("search_query_path", "https://example.test/posts?query=ai"),
        ("search_query_path", "https://example.test/posts?s=ai"),
        ("search_query_path", "https://example.test/posts?page=2&q="),
        ("feed_path", "https://example.test/blog/feed"),
        ("feed_path", "https://example.test/feed/"),
        ("feed_path", "https://example.test/blog/rss"),
        ("feed_path", "https://example.test/blog/atom"),
        ("index_page", "https://raw.githubusercontent.com/o/r/main/README.md"),
        ("index_page", "https://raw.githubusercontent.com/o/r/refs/heads/main/README.md"),
        ("index_page", "https://example.test/awesome-mcp-servers"),
        ("index_page", "https://example.test/lists/awesome-agents/readme"),
        ("index_page", "https://example.test/tag/ai"),
        ("index_page", "https://example.test/category/ml/x"),
        ("index_page", "https://example.test/blog/page/2"),
        ("index_page", "https://example.test/blog/page/17"),
    )

    def test_each_case_matches_its_expected_rule(self):
        for expected, url in self.CASES:
            with self.subTest(url=url):
                match = base.suspicious_url_match(url)
                self.assertIsNotNone(match, "%s should have matched" % url)
                self.assertEqual(match.rule_id, expected)
                self.assertTrue(base.looks_like_index_or_search(url))

    def test_every_rule_has_at_least_two_positive_examples(self):
        seen = {}
        for expected, _url in self.CASES:
            seen[expected] = seen.get(expected, 0) + 1
        for rule_id in base.SUSPICIOUS_RULE_IDS:
            self.assertGreaterEqual(seen.get(rule_id, 0), 2, rule_id)

    def test_details_are_deterministic_and_name_the_structural_fact(self):
        for _expected, url in self.CASES:
            with self.subTest(url=url):
                first = base.suspicious_url_match(url)
                second = base.suspicious_url_match(url)
                self.assertEqual(first, second)
                self.assertEqual(first.detail, second.detail)
                self.assertTrue(first.detail.strip())
                for noise in ("0x", "object at", "{", "}", "set()", ROOT):
                    self.assertNotIn(noise, first.detail)

    def test_the_detail_never_offers_a_replacement_url(self):
        for _expected, url in self.CASES:
            with self.subTest(url=url):
                detail = base.suspicious_url_match(url).detail
                self.assertNotIn("http://", detail)
                self.assertNotIn("https://", detail)

    def test_the_raw_url_is_not_mutated(self):
        url = "https://example.test/blog/page/2?q=ai"
        before = str(url)
        match = base.suspicious_url_match(url)
        self.assertIsNotNone(match)
        self.assertEqual(url, before)
        self.assertFalse(hasattr(match, "url"))
        self.assertFalse(hasattr(match, "rewritten_url"))
        self.assertFalse(hasattr(match, "suggested_url"))


class TestGuardNegatives(unittest.TestCase):
    """Structure, not substrings. Every one of these is a legitimate page."""

    LEGITIMATE = (
        # The four E24 vendor-blog controls: registrable domain google.com,
        # host cloud.google.com — full-host equality must not catch them.
        "https://cloud.google.com/blog/products/ai-machine-learning/how-commerzbank-is-transforming-financial-advisory-workflows-with-gen-ai",
        "https://cloud.google.com/transform/loreal-ai-content-creation-veo-imagen-creaitech-next25",
        "https://cloud.google.com/customers/aes",
        "https://developers.google.com/some/article",
        # The E24 LinkedIn control: an interior `/search/` path segment.
        "https://www.linkedin.com/blog/engineering/search/introducing-semantic-capability-in-linkedins-content-search-engine",
        # Words that merely contain a rule token.
        "https://research.example.com/paper",
        "https://example.test/searching/for-answers",
        "https://example.test/feeds/latest",
        "https://example.test/blog/feedback",
        "https://example.test/atomic-design",
        "https://example.test/tags/ai",
        "https://example.test/categories/ml",
        "https://example.test/awesome/thing",
        "https://example.test/blog/page/two",
        "https://example.test/README.md",
        "https://github.com/o/r/blob/main/README.md",
        # Query keys that merely contain a search key name, and values that do.
        "https://example.test/posts?faq=1",
        "https://example.test/posts?queryset=1",
        "https://example.test/posts?qty=3",
        "https://example.test/posts?ref=query",
        "https://example.test/posts?utm_source=q",
        "https://example.test/blog/search-engine-optimisation",
    )

    def test_no_legitimate_url_is_refused(self):
        for url in self.LEGITIMATE:
            with self.subTest(url=url):
                self.assertIsNone(base.suspicious_url_match(url))
                self.assertFalse(base.looks_like_index_or_search(url))

    def test_query_keys_are_matched_exactly_not_by_substring_or_value(self):
        self.assertIsNone(base.suspicious_url_match("https://example.test/a?qq=1"))
        self.assertIsNone(base.suspicious_url_match("https://example.test/a?sq=1"))
        self.assertIsNone(base.suspicious_url_match("https://example.test/a?x=q"))
        self.assertIsNotNone(base.suspicious_url_match("https://example.test/a?q=1"))

    def test_path_predicates_are_segment_wise_not_full_url_substring(self):
        # The whole-URL text contains 'feed', 'tag' and 'search' in each of these.
        for url in ("https://example.test/feedstock/report",
                    "https://example.test/vintage/thing",
                    "https://example.test/researchers/paper"):
            with self.subTest(url=url):
                self.assertIsNone(base.suspicious_url_match(url))

    def test_readme_rule_is_not_generalised_to_all_readmes_or_all_github(self):
        self.assertIsNone(base.suspicious_url_match(
            "https://raw.githubusercontent.com/o/r/main/docs/guide.md"))
        self.assertIsNone(base.suspicious_url_match(
            "https://github.com/o/r/blob/main/README.md"))
        self.assertIsNotNone(base.suspicious_url_match(
            "https://raw.githubusercontent.com/o/r/main/README.md"))


class TestGuardPrecedence(unittest.TestCase):
    """First match in the committed order wins, always."""

    def test_overlapping_urls_report_the_first_matching_rule(self):
        cases = (
            # host beats path and query
            ("search_engine_host", "https://www.google.com/search?q=ai"),
            ("search_engine_host", "https://search.example.com/blog/feed"),
            ("search_engine_host", "https://www.bing.com/tag/ai"),
            # query/path search beats feed and index
            ("search_query_path", "https://example.test/awesome-list/search"),
            ("search_query_path", "https://example.test/tag/ai?q=x"),
            # feed beats index
            ("feed_path", "https://example.test/tag/ai/feed"),
            ("feed_path", "https://example.test/awesome-things/rss"),
        )
        for expected, url in cases:
            with self.subTest(url=url):
                self.assertEqual(base.suspicious_url_match(url).rule_id, expected)

    def test_precedence_is_the_declared_constant_order(self):
        self.assertEqual(list(base.SUSPICIOUS_RULE_IDS).index("search_engine_host"), 0)
        self.assertEqual(list(base.SUSPICIOUS_RULE_IDS).index("search_query_path"), 1)
        self.assertEqual(list(base.SUSPICIOUS_RULE_IDS).index("feed_path"), 2)
        self.assertEqual(list(base.SUSPICIOUS_RULE_IDS).index("index_page"), 3)

    def test_a_lower_rule_still_fires_when_the_higher_one_does_not(self):
        """Non-vacuous: the overlap cases above are decided, not accidental."""
        self.assertEqual(base.suspicious_url_match(
            "https://example.test/blog/feed").rule_id, "feed_path")
        self.assertEqual(base.suspicious_url_match(
            "https://example.test/tag/ai").rule_id, "index_page")


class TestGuardRefusesMalformedInput(unittest.TestCase):
    """Not-a-URL is a different finding from this-is-a-search-page."""

    BAD = ("", "   ", None, 42, [], {},
           "example.test/blog/search",          # relative: no scheme
           "//example.test/feed",               # protocol-relative
           "ftp://example.test/feed",
           "mailto:someone@example.test",
           "file:///c:/tmp/feed",
           "javascript:alert(1)",
           "https://",                          # no host
           "http:///feed",
           "unknown")                           # the legacy sentinel

    def test_each_is_refused_loudly_and_is_never_a_suspicious_match(self):
        for value in self.BAD:
            with self.subTest(value=value):
                with self.assertRaises(base.MigrationInputError):
                    base.suspicious_url_match(value)
                with self.assertRaises(base.MigrationInputError):
                    base.looks_like_index_or_search(value)

    def test_the_refusal_names_the_input_and_offers_no_repair(self):
        with self.assertRaises(base.MigrationInputError) as caught:
            base.suspicious_url_match("example.test/blog")
        message = str(caught.exception)
        self.assertIn("example.test/blog", message)
        self.assertIn("refuses", message)

    def test_a_malformed_input_is_not_silently_coerced(self):
        for value in ("example.test/blog/search", "unknown"):
            with self.subTest(value=value):
                try:
                    base.suspicious_url_match(value)
                except base.MigrationInputError as exc:
                    self.assertNotIn("https://" + value, str(exc))


class TestGuardOverProtectedAxCorpus(unittest.TestCase):
    """0 of 231 — measured, and proved not to be vacuous."""

    @classmethod
    def setUpClass(cls):
        cls.digest_before = sha256_file(AX_REGISTRY)
        with open(AX_REGISTRY, encoding="utf-8") as handle:
            cls.cases = json.load(handle)["cases"]

    def test_the_corpus_is_the_expected_size_and_every_url_is_present(self):
        self.assertEqual(len(self.cases), EXPECTED_AX_CASES)
        for case in self.cases:
            self.assertTrue(case["source_url"].strip(), case["case_id"])
            self.assertTrue(case["source_url"].startswith(("http://", "https://")))

    def test_exactly_zero_of_the_231_source_urls_are_suspicious(self):
        flagged = [(c["case_id"], c["source_url"], base.suspicious_url_match(c["source_url"]))
                   for c in self.cases]
        refused = [row for row in flagged if row[2] is not None]
        self.assertEqual(len(flagged), EXPECTED_AX_CASES)
        self.assertEqual(refused, [], "the guard refused a legitimate AX case page")

    def test_the_zero_is_not_vacuous_because_the_guard_is_demonstrably_active(self):
        """Fabricated positives run through the SAME loop as the corpus."""
        fabricated = ["https://www.google.com/search?q=" + c["case_id"]
                      for c in self.cases[:5]]
        fabricated += ["https://example.test/tag/" + c["case_id"] for c in self.cases[:5]]
        matches = [base.suspicious_url_match(u) for u in fabricated]
        self.assertEqual(len(matches), 10)
        self.assertTrue(all(m is not None for m in matches))
        self.assertEqual({m.rule_id for m in matches},
                         {"search_engine_host", "index_page"})

    def test_the_protected_ax_registry_is_unchanged(self):
        self.assertEqual(sha256_file(AX_REGISTRY), self.digest_before)


class TestGuardIsPure(unittest.TestCase):

    MODULE_PATH = os.path.join(ROOT, "src", "harvest", "migrate", "base.py")

    def module_ast(self):
        with open(self.MODULE_PATH, encoding="utf-8") as handle:
            return ast.parse(handle.read())

    def test_calling_the_guard_opens_no_file_and_no_socket(self):
        import socket
        with mock.patch("builtins.open", side_effect=AssertionError("opened a file")), \
                mock.patch.object(socket, "socket",
                                  side_effect=AssertionError("opened a socket")):
            self.assertIsNone(base.suspicious_url_match("https://example.test/a"))
            self.assertIsNotNone(base.suspicious_url_match("https://example.test/a/feed"))
            self.assertTrue(base.looks_like_index_or_search("https://example.test/tag/x"))

    def test_the_module_imports_only_standard_url_parsing(self):
        imported = set()
        for node in ast.walk(self.module_ast()):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(imported, {"dataclasses", "urllib.parse"},
                         "base.py must stay pure: no filesystem, network, clock, "
                         "config, schema or record dependency")

    def test_importing_the_module_only_defines_things(self):
        """Import-time side effects are impossible if nothing executes at import."""
        allowed = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
                   ast.ClassDef, ast.FunctionDef)
        for node in self.module_ast().body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue                       # the module docstring
            self.assertIsInstance(node, allowed)

    def test_no_second_url_normalizer_is_introduced(self):
        """The committed primitives stay the authority; this module adds none."""
        with open(self.MODULE_PATH, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        defined = {node.name for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)}
        for forbidden in ("canonicalize_string", "registrable_host", "normalize_url",
                          "canonical_url", "rewrite_url"):
            self.assertNotIn(forbidden, defined)

    def test_no_runtime_path_is_created_by_the_guard(self):
        for case in ("https://example.test/a", "https://www.google.com/search?q=1"):
            base.suspicious_url_match(case)
        for leak in ("state/taxonomy_harvest", "data/harvested", "runs", "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)), leak)

    def test_repeated_calls_are_stateless(self):
        url = "https://example.test/tag/ai"
        first = base.suspicious_url_match(url)
        for _ in range(50):
            self.assertEqual(base.suspicious_url_match(url), first)


if __name__ == "__main__":
    unittest.main()
