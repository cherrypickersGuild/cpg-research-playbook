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
import inspect
import io
import json
import os
import random
import subprocess
import tempfile
import unittest
from unittest import mock

from src.harvest import aliases as aliases_mod
from src.harvest import facets as facets_mod
from src.harvest import records as records_mod
from src.harvest import schema as schema_mod
from src.harvest import urlkey
from src.harvest.migrate import ax_cases
from src.harvest.migrate import base
from src.harvest.migrate import entity_assess as ea

CANON = aliases_mod.load_canonicalization()

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

    def test_the_module_reaches_for_no_network_clock_or_process(self):
        """S7-5 made this module the migration PATH owner, so `os` and `re` are
        expected now. What must never appear is anything that could reach the
        network, a clock, a subprocess, or the record/schema/config machinery.
        """
        imported = set()
        for node in ast.walk(self.module_ast()):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(imported, {"dataclasses", "os", "re", "urllib.parse"})
        for forbidden in ("socket", "subprocess", "time", "datetime", "json",
                          "urllib.request", "shutil"):
            self.assertNotIn(forbidden, imported)

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


# ========================================================= S7-3 · the AX mapping
RUN_A = "20260731T000000Z-1234"
RUN_B = "20260801T111111Z-4321"
AT_A = "2026-07-31T00:00:00Z"
AT_B = "2026-08-01T11:11:11Z"


def load_ax():
    with open(AX_REGISTRY, encoding="utf-8") as handle:
        return json.load(handle)


def canon_bytes(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")


def check_facets_module():
    """The committed facet checker, loaded from scripts/ by path."""
    import importlib.util
    path = os.path.join(ROOT, "scripts", "harvest", "check_facets.py")
    spec = importlib.util.spec_from_file_location("check_facets_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def a_case(**over):
    case = {
        "case_id": "case-2026-9001",
        "company": "Acme",
        "industry": "retail",
        "workflow_before": "Manual triage.",
        "workflow_after": "Assisted triage.",
        "ai_system_or_tool": "Acme Copilot",
        "measurable_kpi": "handling time",
        "kpi_value": "30% lower",
        "evidence_quote": "Handling time fell by 30%.",
        "source_url": "https://example.test/cases/acme",
        "source_title": "How Acme did it",
        "source_domain": "example.test",
        "transformation_date": "2025-06",
        "publication_date": "2026-01-15",
        "confidence": 0.9,
        "verification_status": "verified",
        "case_key": "acme|copilot",
        "corroboration_count": 1,
        "conflicting_evidence_log": [],
        "discovery": {"first_seen_at": "2026-07-14",
                      "last_corroborated_at": "2026-07-14",
                      "found_via": [{"hit_id": "hit-1", "platform": "web"}]},
    }
    case.update(over)
    return case


def a_ax_registry(cases):
    return {"schema_version": 1, "last_merged_at": "2026-07-22T03:17:22Z",
            "cases": cases}


def mapped(cases, **kw):
    kw.setdefault("harvest_run_id", RUN_A)
    kw.setdefault("migrated_at", AT_A)
    return ax_cases.map_registry(a_ax_registry(cases), **kw)


class TestMapperSurfaceIsPure(unittest.TestCase):

    MODULE_PATH = os.path.join(ROOT, "src", "harvest", "migrate", "ax_cases.py")

    def source(self):
        with open(self.MODULE_PATH, encoding="utf-8") as handle:
            return handle.read()

    def called_names(self):
        """Every dotted name the module actually CALLS — prose is not code."""
        names = set()
        for node in ast.walk(ast.parse(self.source())):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            parts = []
            while isinstance(target, ast.Attribute):
                parts.append(target.attr)
                target = target.value
            if isinstance(target, ast.Name):
                parts.append(target.id)
            if parts:
                names.add(".".join(reversed(parts)))
        return names

    MAPPING_FUNCTIONS = ("map_registry", "map_case", "build_case_facets",
                         "validate_registry", "_validate_reviews", "_compose",
                         "_tags", "_classification", "_assumptions", "_rejection")

    def mapping_calls(self):
        """Dotted names called from inside the MAPPING functions only.

        S7-4 added a CLI layer to this module, so purity is asserted where it is
        the contract — the mapping — rather than over the whole file. The CLI may
        read a file and consult a clock; the mapping may do neither.
        """
        tree = ast.parse(self.source())
        names = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or \
                    node.name not in self.MAPPING_FUNCTIONS:
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                target, parts = inner.func, []
                while isinstance(target, ast.Attribute):
                    parts.append(target.attr)
                    target = target.value
                if isinstance(target, ast.Name):
                    parts.append(target.id)
                if parts:
                    names.add(".".join(reversed(parts)))
        return names

    def test_the_mapping_reads_no_clock_no_file_and_no_environment(self):
        called = self.mapping_calls()
        self.assertIn("records_mod.make_full_record", called,
                      "the scan must actually be looking at the mapping")
        for forbidden in ("records_mod.utcnow", "artifacts_mod.run_id",
                          "datetime.now", "datetime.datetime.now", "time.time",
                          "argparse.ArgumentParser", "subprocess.run",
                          "socket.socket", "os.environ.get", "open", "input",
                          "print", "os.makedirs", "os.replace", "json.load",
                          "load_json_document", "parse_overrides"):
            self.assertNotIn(forbidden, called,
                             "the AX mapping must not call %r" % forbidden)

    def test_the_module_imports_no_network_clock_or_subprocess_module(self):
        imported = set()
        for node in ast.walk(ast.parse(self.source())):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for forbidden in ("time", "datetime", "socket", "subprocess",
                          "urllib.request", "http.client"):
            self.assertNotIn(forbidden, imported)

    def test_it_neither_classifies_nor_scores(self):
        imported = set()
        for node in ast.walk(ast.parse(self.source())):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
        self.assertNotIn("classify", imported)
        self.assertNotIn("verify", imported)
        self.assertNotIn("facetassign", imported)

    def test_the_mapping_writes_nothing_and_no_harvest_run_machinery_is_used(self):
        """S7-5 publishes, so writers exist — but not in the mapping, and never
        the ordinary run machinery.
        """
        mapping = self.mapping_calls()
        for forbidden in ("artifacts_mod.write_atomic", "artifacts_mod.write_document",
                          "os.replace", "os.makedirs", "os.mkdir", "os.rmdir",
                          "os.unlink"):
            self.assertNotIn(forbidden, mapping,
                             "the mapping must not write: %r" % forbidden)
        called = self.called_names()
        for forbidden in ("artifacts_mod.publish_run", "artifacts_mod.run_dir",
                          "artifacts_mod.cell_artifact_path",
                          "artifacts_mod.write_run_manifest",
                          "artifacts_mod.build_run_manifest",
                          "artifacts_mod.write_latest_run_id",
                          "artifacts_mod.latest_run_id_path",
                          "shutil.move", "shutil.rmtree", "shutil.copytree"):
            self.assertNotIn(forbidden, called,
                             "a migration is not a run: %r" % forbidden)
        self.assertIn("artifacts_mod.serialize", called,
                      "the report must reuse the committed rendering primitive")
        self.assertIn("artifacts_mod.write_document", called,
                      "the bundle must be written by the committed validating writer")

    def test_the_result_boundary_is_immutable_and_exactly_two_fields(self):
        result = mapped([a_case()])
        self.assertEqual(sorted(f.name for f in dataclasses.fields(result)),
                         ["accepted", "rejected"])
        self.assertIsInstance(result.accepted, tuple)
        self.assertIsInstance(result.rejected, tuple)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.accepted = ()

    def test_the_mapper_requires_an_explicit_clock(self):
        registry = a_ax_registry([a_case()])
        with self.assertRaises(TypeError):
            ax_cases.map_registry(registry)
        with self.assertRaises(ax_cases.AxMigrationError):
            ax_cases.map_registry(registry, harvest_run_id="", migrated_at=AT_A)
        for bad in ("2026-07-31", "2026-07-31T00:00:00", "2026-07-31T00:00:00.500Z",
                    "2026-07-31T00:00:00+00:00", None, 17):
            with self.subTest(bad=bad):
                with self.assertRaises(ax_cases.AxMigrationError):
                    ax_cases.map_registry(registry, harvest_run_id=RUN_A,
                                          migrated_at=bad)

    def test_discovered_at_is_always_supplied_so_no_clock_fallback_can_fire(self):
        record = mapped([a_case()]).accepted[0]
        self.assertEqual(record["discovered_at"], "2026-07-14T00:00:00Z")


class TestProtectedAxCorpusMapping(unittest.TestCase):
    """The real 231 cases, mapped in memory."""

    @classmethod
    def setUpClass(cls):
        cls.digest_before = sha256_file(AX_REGISTRY)
        cls.document = load_ax()
        cls.result = ax_cases.map_registry(cls.document, harvest_run_id=RUN_A,
                                           migrated_at=AT_A)
        cls.records = cls.result.accepted

    def test_the_corpus_is_exactly_231_cases(self):
        self.assertEqual(len(self.document["cases"]), EXPECTED_AX_CASES)

    def test_231_accepted_and_0_rejected(self):
        self.assertEqual(len(self.records), EXPECTED_AX_CASES)
        self.assertEqual(self.result.rejected, ())

    def test_every_record_validates_against_the_committed_schema(self):
        for record in self.records:
            schema_mod.validate_or_raise(record, "record.v1.json")

    def test_every_record_passes_the_committed_facet_checker(self):
        checker = check_facets_module()
        problems = []
        for record in self.records:
            problems += checker.validate_record_facets(record)
        self.assertEqual(problems, [])

    def test_all_identities_are_distinct(self):
        for field in ("record_id", "content_id", "identity_url"):
            values = [r[field] for r in self.records]
            self.assertEqual(len(set(values)), EXPECTED_AX_CASES, field)

    def test_duplicate_legacy_case_ids_exist_and_do_not_affect_identity(self):
        case_ids = [r["legacy_ids"][0]["id"] for r in self.records]
        self.assertLess(len(set(case_ids)), EXPECTED_AX_CASES,
                        "the corpus is expected to repeat case_id")
        self.assertEqual(len(set(case_ids)), 126)
        keys = [r["legacy_ids"][0]["key"] for r in self.records]
        self.assertEqual(len(set(keys)), EXPECTED_AX_CASES)
        self.assertEqual(len({r["record_id"] for r in self.records}), EXPECTED_AX_CASES)

    def test_every_record_is_routed_and_classified_by_migration(self):
        for record in self.records:
            self.assertEqual(record["topic"], "cases")
            self.assertEqual(record["primary_category"], "case-studies")
            self.assertEqual(record["cell_id"], "cases__case-studies")
            self.assertEqual(record["record_type"], "full")
            self.assertEqual(record["classification"], {
                "rule_id": "migration.ax_case_registry.case_study",
                "rationale": ax_cases.CLASSIFICATION_RATIONALE,
                "evidence": [{"signal": "legacy_registry",
                              "matched": "ax_case_harvest_registry"}],
                "competing_categories": []})
            self.assertNotEqual(record["classification"]["rule_id"],
                                "R10_default_by_category")

    def test_url_semantics_are_exact(self):
        by_key = {c["case_key"]: c for c in self.document["cases"]}
        for record in self.records:
            case = by_key[record["legacy_ids"][0]["key"]]
            self.assertEqual(record["target_url"], case["source_url"])
            self.assertIsNone(record["source_url"])
            self.assertEqual(record["canonical_url"], record["identity_url"])
            self.assertEqual(record["url_aliases"], [])
            self.assertEqual(record["identity_url"],
                             urlkey.canonicalize_string(
                                 case["source_url"],
                                 **{"tracking_params": CANON.get("tracking_params"),
                                    "domain_rules": CANON.get("domain_rules")}))
            self.assertEqual(record["record_id"],
                             urlkey.record_id("cases", record["identity_url"]))
            self.assertEqual(record["content_id"],
                             urlkey.content_id(record["identity_url"]))

    def test_every_record_is_snippet_only_with_its_own_quote(self):
        by_key = {c["case_key"]: c for c in self.document["cases"]}
        statuses = {r["verification_status"] for r in self.records}
        self.assertEqual(statuses, {"snippet_only"})
        for record in self.records:
            case = by_key[record["legacy_ids"][0]["key"]]
            self.assertEqual(record["verification_evidence"], case["evidence_quote"])

    def test_no_record_claims_a_fetch_that_never_happened(self):
        for record in self.records:
            self.assertEqual(record["access_status"], "not_checked")
            self.assertIsNone(record["http_status"])
            self.assertIsNone(record["content_hash"])
            self.assertIsNone(record["last_checked_at"])
            self.assertIsNone(record["updated_at"])
            self.assertNotEqual(record["verification_status"], "fetched")

    def test_the_33_unknown_publication_dates_become_null(self):
        unknown = [c for c in self.document["cases"]
                   if str(c["publication_date"]).strip().lower() == "unknown"]
        self.assertEqual(len(unknown), 33)
        nulls = [r for r in self.records if r["published_at"] is None]
        self.assertEqual(len(nulls), 33)
        for record in nulls:
            self.assertEqual(record["provenance"]["raw"]["publication_date"], "unknown")

    def test_legacy_unknowns_survive_verbatim_in_raw_and_domain_fields(self):
        for record in self.records:
            raw = record["provenance"]["raw"]
            self.assertEqual(raw["verification_status"],
                             record["domain_fields"].get("industry") is not None
                             and raw["verification_status"] or raw["verification_status"])
            self.assertIn(raw["verification_status"], ("verified", "snippet-only"))
            self.assertEqual(record["domain_fields"]["transformation_date"],
                             raw["transformation_date"])

    def test_all_four_scores_are_null(self):
        for record in self.records:
            for field in ("relevance_score", "quality_score",
                          "audience_fit_score", "freshness_score"):
                self.assertIsNone(record[field], field)

    def test_provenance_raw_is_the_complete_original_case(self):
        by_key = {c["case_key"]: c for c in self.document["cases"]}
        for record in self.records:
            case = by_key[record["legacy_ids"][0]["key"]]
            self.assertEqual(record["provenance"]["raw"], case)
            self.assertIsNot(record["provenance"]["raw"], case)
            self.assertEqual(record["provenance"]["source_id"], "ax_case_harvest_registry")
            self.assertEqual(record["provenance"]["source_adapter"], "migration")
            self.assertIsNone(record["provenance"]["source_tier"])
            self.assertEqual(record["provenance"]["discovered_via"],
                             case["discovery"]["found_via"])
            self.assertIsNot(record["provenance"]["discovered_via"],
                             case["discovery"]["found_via"])
            migration = record["provenance"]["migration"]
            self.assertEqual(sorted(migration), ["adapter", "assumptions", "migrated_at"])
            self.assertEqual(migration["adapter"], "ax_cases")
            self.assertEqual(migration["migrated_at"], AT_A)
            joined = " ".join(migration["assumptions"])
            for claim in ("own target page", "No HTTP request", "never promoted to",
                          "migration.ax_case_registry.case_study"):
                self.assertIn(claim, joined)
            for leak in ("C:/", "C:\\", "/Users/", ROOT):
                self.assertNotIn(leak, joined)

    def test_the_domain_block_is_exactly_the_twelve_approved_fields(self):
        by_key = {c["case_key"]: c for c in self.document["cases"]}
        for record in self.records:
            case = by_key[record["legacy_ids"][0]["key"]]
            self.assertEqual(sorted(record["domain_fields"]),
                             sorted(ax_cases.DOMAIN_FIELDS))
            self.assertEqual(len(ax_cases.DOMAIN_FIELDS), 12)
            for field in ax_cases.DOMAIN_FIELDS:
                self.assertEqual(record["domain_fields"][field], case[field], field)

    def test_facet_reporting_states_are_exactly_112_118_1(self):
        states = {}
        for record in self.records:
            state = facets_mod.reporting_state(record)
            states[state] = states.get(state, 0) + 1
        self.assertEqual(states, {"facet_partial": 112,
                                  "unmapped_legacy_value": 118,
                                  "unresolved": 1})
        self.assertEqual(sum(states.values()), EXPECTED_AX_CASES)

    def test_no_facet_state_withholds_a_report_only_record(self):
        for record in self.records:
            self.assertTrue(facets_mod.is_publication_eligible(record))
            self.assertFalse(facets_mod.is_facet_gated(record))

    def test_the_e27_case_records_its_reviewed_mapping_without_asserting_it(self):
        e27 = [r for r in self.records
               if r["provenance"]["raw"]["industry"] == "IT services"]
        self.assertEqual(len(e27), 1)
        facets = e27[0]["case_facets"]
        self.assertIsNone(facets["industry"]["primary"])
        self.assertEqual(facets["industry"]["evidence"], [])
        entry = [u for u in facets["unresolved"] if u["axis"] == "industry"][0]
        self.assertEqual(entry["state"], "insufficient_evidence")
        self.assertNotEqual(entry["state"], "unmapped_legacy_value")
        self.assertEqual(entry["term"], "IT services")
        self.assertIn("technology-software", entry["detail"])
        self.assertIn("lexical-support", entry["detail"])
        self.assertEqual(facets_mod.reporting_state(e27[0]), "unresolved")

    def test_no_business_function_or_use_case_is_ever_inferred(self):
        for record in self.records:
            facets = record["case_facets"]
            self.assertEqual(facets["business_functions"], [])
            self.assertEqual(facets["use_case_types"], [])
            self.assertEqual(facets["industry"]["secondary"], [])
            states = {u["axis"]: u["state"] for u in facets["unresolved"]}
            self.assertEqual(states["business_function"], "insufficient_evidence")
            self.assertEqual(states["use_case_type"], "insufficient_evidence")
            self.assertEqual(facets["vocabulary_versions"],
                             facets_mod.vocabulary_versions())
            self.assertEqual(facets["facets_version"], facets_mod.FACETS_VERSION)
            self.assertEqual(facets["classification_state"],
                             facets_mod.decide_classification_state(facets))

    def test_records_are_returned_in_the_committed_sort_order(self):
        self.assertEqual(list(self.records),
                         records_mod.sort_records(list(self.records)))

    def test_the_protected_registry_bytes_are_unchanged(self):
        self.assertEqual(sha256_file(AX_REGISTRY), self.digest_before)
        self.assertEqual(self.document, load_ax(),
                         "mapping mutated the in-memory source document")

    def test_no_runtime_path_is_created(self):
        for leak in ("state/taxonomy_harvest", "data/harvested", "runs", "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)), leak)


class TestMappingDeterminism(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.document = load_ax()
        cls.result = ax_cases.map_registry(cls.document, harvest_run_id=RUN_A,
                                           migrated_at=AT_A)

    def test_mapping_twice_with_the_same_clock_is_byte_identical(self):
        again = ax_cases.map_registry(load_ax(), harvest_run_id=RUN_A, migrated_at=AT_A)
        self.assertEqual(again, self.result)
        self.assertEqual(canon_bytes(list(again.accepted)),
                         canon_bytes(list(self.result.accepted)))

    def test_source_row_order_does_not_change_the_result(self):
        reversed_doc = load_ax()
        reversed_doc["cases"].reverse()
        self.assertNotEqual(reversed_doc["cases"], self.document["cases"])
        self.assertEqual(canon_bytes(list(ax_cases.map_registry(
            reversed_doc, harvest_run_id=RUN_A, migrated_at=AT_A).accepted)),
            canon_bytes(list(self.result.accepted)))
        for seed in (3, 11):
            shuffled = load_ax()
            random.Random(seed).shuffle(shuffled["cases"])
            self.assertNotEqual(shuffled["cases"], self.document["cases"])
            self.assertEqual(canon_bytes(list(ax_cases.map_registry(
                shuffled, harvest_run_id=RUN_A, migrated_at=AT_A).accepted)),
                canon_bytes(list(self.result.accepted)), "seed %d" % seed)

    def test_only_the_enumerated_leaves_change_with_the_clock(self):
        other = ax_cases.map_registry(load_ax(), harvest_run_id=RUN_B, migrated_at=AT_B)
        changed = set()

        def walk(left, right, path):
            if isinstance(left, dict):
                self.assertEqual(sorted(left), sorted(right), path)
                for key in left:
                    walk(left[key], right[key], path + "." + key)
            elif isinstance(left, list):
                self.assertEqual(len(left), len(right), path)
                for index, (a, b) in enumerate(zip(left, right)):
                    walk(a, b, "%s[%d]" % (path, index))
            elif left != right:
                changed.add(path)

        self.assertEqual(len(other.accepted), len(self.result.accepted))
        for old, new in zip(self.result.accepted, other.accepted):
            walk(old, new, "")
        self.assertEqual(changed, {".harvest_run_id", ".provenance.migration.migrated_at"})

    def test_rejection_rows_move_only_their_own_two_leaves(self):
        cases = [a_case(case_id="case-2026-9101", case_key="a|a",
                        source_url="https://example.test/tag/ai")]
        first = mapped(cases, allow_unmappable=True).rejected
        second = ax_cases.map_registry(a_ax_registry(cases), harvest_run_id=RUN_B,
                                       migrated_at=AT_B, allow_unmappable=True).rejected
        self.assertEqual(len(first), 1)
        differing = {k for k in first[0] if first[0][k] != second[0][k]}
        self.assertEqual(differing, {"rejected_at"})

    def test_review_decision_input_order_does_not_change_the_result(self):
        cases = [a_case(case_id="c1", case_key="k|1",
                        source_url="https://example.test/tag/ai"),
                 a_case(case_id="c2", case_key="k|2",
                        source_url="https://example.test/blog/feed")]
        reviews = [{"case_id": "c1", "legacy_source_url": "https://example.test/tag/ai",
                    "decision": "reject", "note": "index page"},
                   {"case_id": "c2", "legacy_source_url": "https://example.test/blog/feed",
                    "decision": "reject", "note": "feed"}]
        one = mapped(cases, reviewed=reviews)
        two = mapped(cases, reviewed=list(reversed(reviews)))
        self.assertEqual(canon_bytes(list(one.rejected)), canon_bytes(list(two.rejected)))

    def test_mapping_does_not_mutate_the_input_and_records_are_independent(self):
        document = load_ax()
        before = canon_bytes(document)
        result = ax_cases.map_registry(document, harvest_run_id=RUN_A, migrated_at=AT_A)
        self.assertEqual(canon_bytes(document), before)
        # Mutating the source afterwards cannot reach a finished record.
        document["cases"][0]["company"] = "MUTATED"
        document["cases"][0]["discovery"]["found_via"].append({"hit_id": "x",
                                                               "platform": "y"})
        for record in result.accepted:
            self.assertNotEqual(record["provenance"]["raw"].get("company"), "MUTATED")
            self.assertNotEqual(record["domain_fields"].get("company"), "MUTATED")
            self.assertLessEqual(len(record["provenance"]["discovered_via"]), 1)
        # Mutating one record cannot reach another.
        result.accepted[0]["domain_fields"]["company"] = "TOUCHED"
        self.assertNotEqual(result.accepted[1]["domain_fields"]["company"], "TOUCHED")


class TestMappingRefusesBadInput(unittest.TestCase):

    def assert_refused(self, registry, needle, **kw):
        kw.setdefault("harvest_run_id", RUN_A)
        kw.setdefault("migrated_at", AT_A)
        with self.assertRaises(ax_cases.AxMigrationError) as caught:
            ax_cases.map_registry(registry, **kw)
        self.assertIn(needle, str(caught.exception))

    def test_top_level_shape(self):
        self.assert_refused([], "must be a JSON object")
        registry = a_ax_registry([a_case()]); del registry["cases"]
        self.assert_refused(registry, "missing the top-level key 'cases'")
        registry = a_ax_registry([a_case()]); registry["cases"] = {}
        self.assert_refused(registry, "`cases` must be an array")

    def test_an_unexpected_registry_schema_version_is_refused(self):
        registry = a_ax_registry([a_case()]); registry["schema_version"] = 2
        self.assert_refused(registry, "refuses to guess")

    def test_a_row_missing_a_mapped_field_names_the_row_and_field(self):
        case = a_case(); del case["kpi_value"]
        self.assert_refused(a_ax_registry([case]),
                            "cases[0] is missing the required field 'kpi_value'")

    def test_a_row_that_is_not_an_object(self):
        registry = a_ax_registry([a_case()]); registry["cases"].append("nope")
        self.assert_refused(registry, "cases[1] must be an object")

    def test_blank_identity_fields_are_refused(self):
        for field in ("case_id", "case_key", "source_url"):
            with self.subTest(field=field):
                self.assert_refused(a_ax_registry([a_case(**{field: "  "})]),
                                    "%s must be a non-empty string" % field)

    def test_discovery_shape_and_parseable_first_seen(self):
        self.assert_refused(a_ax_registry([a_case(discovery=[])]),
                            "discovery must be an object")
        case = a_case(); del case["discovery"]["found_via"]
        self.assert_refused(a_ax_registry([case]), "discovery is missing 'found_via'")
        case = a_case(); case["discovery"]["first_seen_at"] = "unknown"
        self.assert_refused(a_ax_registry([case]), "not a parseable date")
        case = a_case(); case["discovery"]["found_via"] = [{"hit_id": "h", "extra": 1}]
        self.assert_refused(a_ax_registry([case]), "unrecognised key")

    def test_an_unusable_source_url_is_refused_before_mapping(self):
        for bad in ("unknown", "example.test/x", "ftp://example.test/x"):
            with self.subTest(bad=bad):
                self.assert_refused(a_ax_registry([a_case(source_url=bad)]),
                                    "source_url is unusable")

    def test_conflicting_evidence_log_must_be_a_list(self):
        self.assert_refused(a_ax_registry([a_case(conflicting_evidence_log="x")]),
                            "conflicting_evidence_log must be an array")

    def test_two_cases_sharing_a_target_url_fail_loudly(self):
        cases = [a_case(case_id="c1", case_key="k|1"),
                 a_case(case_id="c2", case_key="k|2")]
        self.assert_refused(a_ax_registry(cases), "share identity_url")

    def test_a_repeated_case_id_alone_stays_legal(self):
        cases = [a_case(case_id="dup", case_key="k|1",
                        source_url="https://example.test/a"),
                 a_case(case_id="dup", case_key="k|2",
                        source_url="https://example.test/b")]
        result = mapped(cases)
        self.assertEqual(len(result.accepted), 2)
        self.assertEqual({r["legacy_ids"][0]["id"] for r in result.accepted}, {"dup"})
        self.assertEqual(len({r["record_id"] for r in result.accepted}), 2)


class TestSuspiciousUrlReviewSemantics(unittest.TestCase):

    SUSPICIOUS = "https://example.test/tag/ai"

    def a_suspicious_case(self, **over):
        over.setdefault("source_url", self.SUSPICIOUS)
        over.setdefault("case_id", "case-2026-9500")
        over.setdefault("case_key", "sus|one")
        return a_case(**over)

    def test_unreviewed_suspicious_url_refuses_the_whole_mapping(self):
        with self.assertRaises(ax_cases.AxMigrationError) as caught:
            mapped([self.a_suspicious_case()])
        message = str(caught.exception)
        self.assertIn("case-2026-9500", message)
        self.assertIn("allow_unmappable", message)

    def test_allow_unmappable_keeps_the_rejection_and_admits_nothing(self):
        result = mapped([self.a_suspicious_case(), a_case(case_id="ok", case_key="ok|1")],
                        allow_unmappable=True)
        self.assertEqual(len(result.accepted), 1)
        self.assertEqual(len(result.rejected), 1)
        row = result.rejected[0]
        self.assertEqual(row["target_url"], self.SUSPICIOUS)
        self.assertEqual(row["rejection_reason"], "ambiguous_legacy_url")
        self.assertIn("case-2026-9500", row["detail"])
        self.assertIn("index_page", row["detail"])
        self.assertIsNone(row["scores"])
        self.assertEqual(row["rejected_at"], AT_A)
        self.assertEqual(row["source_id"], "ax_case_harvest_registry")
        self.assertEqual(row["title"], "How Acme did it")
        self.assertEqual(sorted(row), ["detail", "identity_url", "rejected_at",
                                       "rejection_reason", "scores", "source_id",
                                       "target_url", "title"])
        # The canonical form appears ONLY in the schema-required identity_url.
        self.assertNotEqual(row["identity_url"], "")
        self.assertNotIn(row["identity_url"], row["detail"])
        self.assertEqual(result.accepted[0]["legacy_ids"][0]["id"], "ok")

    def test_the_rejection_row_validates_inside_a_rejection_log(self):
        result = mapped([self.a_suspicious_case()], allow_unmappable=True)
        document = {"schema_version": 1, "cell_id": "cases__case-studies",
                    "harvest_run_id": RUN_A, "generated_at": AT_A,
                    "rejections": list(result.rejected)}
        schema_mod.validate_or_raise(document, "rejection.v1.json")

    def test_reviewed_admit_accepts_the_raw_url_verbatim(self):
        reviews = [{"case_id": "case-2026-9500", "legacy_source_url": self.SUSPICIOUS,
                    "decision": "admit", "note": "confirmed the case's own page"}]
        result = mapped([self.a_suspicious_case()], reviewed=reviews)
        self.assertEqual(len(result.accepted), 1)
        self.assertEqual(result.rejected, ())
        record = result.accepted[0]
        self.assertEqual(record["target_url"], self.SUSPICIOUS)
        joined = " ".join(record["provenance"]["migration"]["assumptions"])
        self.assertIn("a reviewer admitted it", joined)
        self.assertIn("not rewritten", joined)

    def test_reviewed_reject_stays_rejected_and_says_it_was_reviewed(self):
        reviews = [{"case_id": "case-2026-9500", "legacy_source_url": self.SUSPICIOUS,
                    "decision": "reject", "note": "an index page"}]
        result = mapped([self.a_suspicious_case()], reviewed=reviews)
        self.assertEqual(result.accepted, ())
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("a reviewer confirmed the rejection", result.rejected[0]["detail"])

    def test_a_reviewed_admit_is_not_needed_for_an_unsuspicious_url(self):
        record = mapped([a_case()]).accepted[0]
        joined = " ".join(record["provenance"]["migration"]["assumptions"])
        self.assertNotIn("reviewer admitted", joined)

    def test_malformed_and_mismatched_review_rows_are_refused(self):
        case = self.a_suspicious_case()
        bad_rows = (
            ("must be an object", "nope"),
            ("is missing 'decision'", {"case_id": "case-2026-9500",
                                       "legacy_source_url": self.SUSPICIOUS}),
            ("is not one of", {"case_id": "case-2026-9500",
                               "legacy_source_url": self.SUSPICIOUS,
                               "decision": "maybe"}),
            ("not a case in this registry", {"case_id": "ghost",
                                             "legacy_source_url": self.SUSPICIOUS,
                                             "decision": "admit"}),
            ("never a similar one", {"case_id": "case-2026-9500",
                                     "legacy_source_url": "https://example.test/other",
                                     "decision": "admit"}),
            ("unrecognised key", {"case_id": "case-2026-9500",
                                  "legacy_source_url": self.SUSPICIOUS,
                                  "decision": "admit", "surprise": 1}),
        )
        for needle, row in bad_rows:
            with self.subTest(needle=needle):
                with self.assertRaises(ax_cases.AxMigrationError) as caught:
                    mapped([case], reviewed=[row])
                self.assertIn(needle, str(caught.exception))

    def test_two_decisions_for_one_case_are_refused(self):
        rows = [{"case_id": "case-2026-9500", "legacy_source_url": self.SUSPICIOUS,
                 "decision": "admit"},
                {"case_id": "case-2026-9500", "legacy_source_url": self.SUSPICIOUS,
                 "decision": "reject"}]
        with self.assertRaises(ax_cases.AxMigrationError) as caught:
            mapped([self.a_suspicious_case()], reviewed=rows)
        self.assertIn("one case, one decision", str(caught.exception))

    def test_rejection_rows_are_deterministically_ordered(self):
        cases = [self.a_suspicious_case(case_id="c3", case_key="k|3",
                                        source_url="https://example.test/tag/z"),
                 self.a_suspicious_case(case_id="c1", case_key="k|1",
                                        source_url="https://example.test/tag/a"),
                 self.a_suspicious_case(case_id="c2", case_key="k|2",
                                        source_url="https://example.test/blog/feed")]
        rows = mapped(cases, allow_unmappable=True).rejected
        self.assertEqual([r["identity_url"] for r in rows],
                         sorted(r["identity_url"] for r in rows))
        shuffled = list(reversed(cases))
        self.assertEqual(canon_bytes(list(mapped(shuffled, allow_unmappable=True).rejected)),
                         canon_bytes(list(rows)))


class TestTemplatesAndTags(unittest.TestCase):

    def test_summary_and_curation_use_the_fixed_template(self):
        record = mapped([a_case()]).accepted[0]
        self.assertEqual(record["summary"],
                         "Before: Manual triage. | After: Assisted triage. | "
                         "AI system: Acme Copilot")
        self.assertEqual(record["curation_reason"],
                         "KPI: handling time | Reported: 30% lower | "
                         "Evidence: Handling time fell by 30%.")

    def test_a_missing_part_is_omitted_never_rendered_as_unknown(self):
        record = mapped([a_case(workflow_before="unknown", ai_system_or_tool="  ")]
                        ).accepted[0]
        self.assertEqual(record["summary"], "After: Assisted triage.")
        self.assertNotIn("unknown", record["summary"])

    def test_all_parts_missing_gives_null_not_an_empty_string(self):
        record = mapped([a_case(workflow_before="unknown", workflow_after="unknown",
                                ai_system_or_tool="unknown")]).accepted[0]
        self.assertIsNone(record["summary"])

    def test_tags_drop_unknown_and_blank_and_are_sorted_by_the_builder(self):
        record = mapped([a_case(industry="unknown")]).accepted[0]
        self.assertEqual(record["tags"], ["Acme Copilot"])
        record = mapped([a_case(industry="retail", ai_system_or_tool="retail")]).accepted[0]
        self.assertEqual(record["tags"], ["retail"])

    def test_unknown_title_publisher_and_quote_become_null(self):
        record = mapped([a_case(source_title="unknown", source_domain="unknown",
                                evidence_quote="unknown")]).accepted[0]
        self.assertIsNone(record["title"])
        self.assertIsNone(record["publisher"])
        self.assertIsNone(record["verification_evidence"])
        self.assertEqual(record["verification_status"], "unverified")
        self.assertEqual(record["provenance"]["raw"]["source_title"], "unknown")

    def test_honest_constants(self):
        record = mapped([a_case()]).accepted[0]
        self.assertEqual(record["content_type"], "other")
        self.assertIsNone(record["author"])
        self.assertIsNone(record["language"])
        self.assertIsNone(record["duplicate_of"])
        self.assertIsNone(record["rejection_reason"])
        self.assertNotIn("link_history", record)
        self.assertNotIn("multi_topic", record)

    def test_facets_for_a_blank_industry_are_insufficient_not_unmapped(self):
        record = mapped([a_case(industry="   ")]).accepted[0]
        entry = [u for u in record["case_facets"]["unresolved"]
                 if u["axis"] == "industry"][0]
        self.assertEqual(entry["state"], "insufficient_evidence")
        self.assertIsNone(entry["term"])
        self.assertEqual(facets_mod.reporting_state(record), "unresolved")

    def test_facets_for_an_unmapped_industry_report_the_exact_term(self):
        record = mapped([a_case(industry="artisanal widget polishing")]).accepted[0]
        entry = [u for u in record["case_facets"]["unresolved"]
                 if u["axis"] == "industry"][0]
        self.assertEqual(entry["state"], "unmapped_legacy_value")
        self.assertEqual(entry["term"], "artisanal widget polishing")
        self.assertIsNone(record["case_facets"]["industry"]["primary"])
        self.assertEqual(facets_mod.reporting_state(record), "unmapped_legacy_value")


class TestS71AssessmentStillIntact(unittest.TestCase):

    def test_the_committed_assessment_still_regenerates_byte_identically(self):
        _assessment, text = ea.build()
        with open(DOCUMENT, "rb") as handle:
            self.assertEqual(handle.read(), text.encode("utf-8"))


# ================================================ S7-4 · the CLI and the dry-run
MIGRATE_SH = os.path.join(ROOT, "scripts", "harvest", "migrate.sh")
OVERRIDES = os.path.join(ROOT, "config", "harvest", "migration_overrides.v1.json")
FIXED_RUN = ["--run-id", RUN_A, "--migrated-at", AT_A]


def run_cli(argv, module=ax_cases):
    """Call a module's main() with captured binary stdout and text stderr."""
    out, err = io.BytesIO(), io.StringIO()
    status = module.main(argv, stdout=out, stderr=err)
    return status, out.getvalue(), err.getvalue()


def run_wrapper(args, cwd=None):
    """The real shell wrapper, as a user would run it."""
    completed = subprocess.run(["bash", MIGRATE_SH] + args, capture_output=True,
                               cwd=cwd or ROOT)
    return completed.returncode, completed.stdout, completed.stderr


def tree_snapshot(root):
    """Every path under `root` with its bytes — the before/after no-write proof."""
    snapshot = {}
    for base_dir, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base_dir, name)
            with open(path, "rb") as handle:
                snapshot[os.path.relpath(path, root)] = hashlib.sha256(
                    handle.read()).hexdigest()
    return snapshot


def write_json(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
    return path


def an_overrides_document(rows=()):
    return {"config_version": 1, "ax_cases": {"reviewed_unmappable": list(rows)}}


def a_review_row(**over):
    row = {"case_id": "case-2026-9500",
           "legacy_source_url": "https://example.test/tag/ai",
           "matched_rule": "index_page",
           "reviewer": "sj",
           "reviewed_at": "2026-07-31T00:00:00Z",
           "decision": "admit",
           "note": "confirmed this is the case's own page"}
    row.update(over)
    return row


class TestWrapperDispatch(unittest.TestCase):

    def test_help_lists_both_commands_and_exits_zero(self):
        status, out, err = run_wrapper(["--help"])
        self.assertEqual(status, 0)
        text = (out + err).decode("utf-8")
        self.assertIn("ax-cases", text)
        self.assertIn("entity-assess", text)
        self.assertIn("--apply", text)

    def test_no_command_and_unknown_command_are_refused_with_usage(self):
        for args in ([], ["bogus"], ["ax_cases"]):
            with self.subTest(args=args):
                status, out, err = run_wrapper(args)
                self.assertNotEqual(status, 0)
                self.assertIn(b"usage: migrate.sh", err)
                self.assertEqual(out, b"")

    def test_a_malformed_option_is_refused_by_the_python_layer(self):
        status, _out, err = run_wrapper(["ax-cases", "--nonsense"])
        self.assertNotEqual(status, 0)
        self.assertIn(b"unrecognized arguments", err)

    def test_the_wrapper_forwards_paths_containing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = os.path.join(tmp, "a directory with spaces")
            os.makedirs(directory)
            registry = write_json(os.path.join(directory, "registry.json"),
                                  a_ax_registry([a_case()]))
            overrides = write_json(os.path.join(directory, "overrides.json"),
                                   an_overrides_document())
            status, out, err = run_wrapper(
                ["ax-cases", "--registry", registry, "--overrides", overrides,
                 "--expect-count", "1"] + FIXED_RUN)
            self.assertEqual(status, 0, err.decode("utf-8"))
            self.assertEqual(json.loads(out)["source_count"], 1)

    def test_the_wrapper_uses_no_eval_and_no_network_command(self):
        with open(MIGRATE_SH, "rb") as handle:
            source = handle.read()
        self.assertEqual(source.count(b"\r\n"), 0, "the wrapper must stay LF")
        text = source.decode("utf-8")
        for forbidden in ("eval ", "curl ", "wget ", "git ", "mktemp", "> /tmp"):
            self.assertNotIn(forbidden, text)
        self.assertIn("set -euo pipefail", text)
        self.assertIn('exec python -m src.harvest.migrate.ax_cases "$@"', text)


class TestAxDryRunOverTheProtectedCorpus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.digest_before = sha256_file(AX_REGISTRY)
        cls.status, cls.out, cls.err = run_cli(list(FIXED_RUN))
        cls.report = json.loads(cls.out.decode("utf-8"))

    def test_it_succeeds_and_prints_one_deterministic_json_document(self):
        self.assertEqual(self.status, 0, self.err)
        self.assertEqual(self.err, "")
        self.assertTrue(self.out.endswith(b"\n"))
        self.assertFalse(self.out.endswith(b"\n\n"))
        self.assertNotIn(b"\r\n", self.out)

    def test_the_counts_are_231_accepted_and_zero_rejected(self):
        self.assertEqual(self.report["source_count"], EXPECTED_AX_CASES)
        self.assertEqual(self.report["expected_count"], EXPECTED_AX_CASES)
        self.assertEqual(self.report["accepted_count"], EXPECTED_AX_CASES)
        self.assertEqual(self.report["rejected_count"], 0)
        self.assertEqual(self.report["unresolved_rejection_count"], 0)
        self.assertEqual(self.report["rejections"], [])
        self.assertTrue(self.report["dry_run"])

    def test_the_report_has_exactly_the_approved_field_set(self):
        self.assertEqual(sorted(self.report), [
            "accepted_count", "allow_unmappable", "dry_run", "expected_count",
            "harvest_run_id", "migrated_at", "operation", "rejected_count",
            "rejections", "report_type", "report_version", "reviewed_admit_count",
            "reviewed_reject_count", "source_count", "unresolved_case_ids",
            "unresolved_rejection_count"])
        self.assertEqual(self.report["report_type"], "ax_cases")   # E29
        self.assertEqual(self.report["operation"], "ax-cases")

    def test_it_dumps_no_accepted_records_and_no_machine_path(self):
        text = self.out.decode("utf-8")
        for forbidden in ("record_id", "content_id", "case_facets", "provenance",
                          "domain_fields", "C:/", "C:\\", "/Users/", ROOT,
                          "publication_eligible", "state/taxonomy_harvest"):
            self.assertNotIn(forbidden, text)

    def test_the_default_expected_count_is_231(self):
        self.assertEqual(ax_cases.DEFAULT_EXPECT_COUNT, EXPECTED_AX_CASES)
        status, out, _err = run_cli(list(FIXED_RUN))
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out)["expected_count"], EXPECTED_AX_CASES)

    def test_identical_run_context_gives_byte_identical_stdout(self):
        _status, again, _err = run_cli(list(FIXED_RUN))
        self.assertEqual(again, self.out)

    def test_the_protected_registry_is_untouched(self):
        self.assertEqual(sha256_file(AX_REGISTRY), self.digest_before)

    def test_no_runtime_path_was_created(self):
        for leak in ("state/taxonomy_harvest", "data/harvested", "runs", "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)), leak)


class TestDryRunWritesNothing(unittest.TestCase):

    def test_a_controlled_tree_is_byte_identical_before_and_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = write_json(os.path.join(tmp, "registry.json"),
                                  a_ax_registry([a_case()]))
            overrides = write_json(os.path.join(tmp, "overrides.json"),
                                   an_overrides_document())
            before = tree_snapshot(tmp)
            status, out, _err = run_cli(["--registry", registry,
                                         "--overrides", overrides,
                                         "--expect-count", "1"] + FIXED_RUN)
            after = tree_snapshot(tmp)
            self.assertEqual(status, 0)
            self.assertEqual(before, after, "the dry-run wrote into the input tree")
            self.assertEqual(sorted(after), ["overrides.json", "registry.json"])
            self.assertEqual(json.loads(out)["accepted_count"], 1)


class TestDryRunInputHandling(unittest.TestCase):

    def test_the_committed_empty_override_file_parses(self):
        with open(OVERRIDES, encoding="utf-8") as handle:
            document = json.load(handle)
        reviews, declared = ax_cases.parse_overrides(document)
        self.assertEqual(reviews, ())
        self.assertEqual(declared, ())

    def test_the_committed_override_file_is_not_modified_by_parsing(self):
        digest = sha256_file(OVERRIDES)
        run_cli(list(FIXED_RUN))
        self.assertEqual(sha256_file(OVERRIDES), digest)

    def test_a_missing_or_malformed_registry_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope.json")
            status, out, err = run_cli(["--registry", missing] + FIXED_RUN)
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertIn("AX case registry", err)
            broken = os.path.join(tmp, "broken.json")
            with open(broken, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            status, _out, err = run_cli(["--registry", broken] + FIXED_RUN)
            self.assertEqual(status, 1)
            self.assertIn("not valid JSON", err)

    def test_a_missing_or_malformed_override_document_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _out, err = run_cli(["--overrides", os.path.join(tmp, "nope.json")]
                                        + FIXED_RUN)
            self.assertEqual(status, 1)
            self.assertIn("reviewed-overrides document", err)
            bad = write_json(os.path.join(tmp, "bad.json"), {"config_version": 9})
            status, _out, err = run_cli(["--overrides", bad] + FIXED_RUN)
            self.assertEqual(status, 1)
            self.assertIn("config_version", err)

    def test_every_malformed_review_shape_is_refused(self):
        bad_rows = (
            ("must be an object", "not-a-row"),
            ("is missing", {k: v for k, v in a_review_row().items() if k != "note"}),
            ("unrecognised key", a_review_row(surprise=1)),
            ("is not one of", a_review_row(decision="maybe")),
            ("committed guard rule ids", a_review_row(matched_rule="whatever")),
            ("must be a non-empty string", a_review_row(reviewer="  ")),
            ("reviewed_at must be UTC", a_review_row(reviewed_at="2026-07-31")),
        )
        for needle, row in bad_rows:
            with self.subTest(needle=needle):
                with self.assertRaises(ax_cases.AxMigrationError) as caught:
                    ax_cases.parse_overrides(an_overrides_document([row]))
                self.assertIn(needle, str(caught.exception))

    def test_a_duplicate_review_row_is_refused(self):
        with self.assertRaises(ax_cases.AxMigrationError) as caught:
            ax_cases.parse_overrides(an_overrides_document([a_review_row(),
                                                            a_review_row()]))
        self.assertIn("one case, one decision", str(caught.exception))

    def test_a_count_mismatch_fails_with_both_numbers(self):
        status, out, err = run_cli(["--expect-count", "230"] + FIXED_RUN)
        self.assertEqual(status, 1)
        self.assertEqual(out, b"")
        self.assertIn("231", err)
        self.assertIn("230", err)

    def test_a_negative_or_non_numeric_count_is_refused(self):
        for bad in ("-1", "many"):
            with self.subTest(bad=bad):
                with self.assertRaises(SystemExit):
                    run_cli(["--expect-count", bad] + FIXED_RUN)

    def test_expect_count_asserts_the_input_and_does_not_truncate_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [a_case(case_id="c%d" % i, case_key="k|%d" % i,
                            source_url="https://example.test/case/%d" % i)
                     for i in range(4)]
            registry = write_json(os.path.join(tmp, "r.json"), a_ax_registry(cases))
            overrides = write_json(os.path.join(tmp, "o.json"),
                                   an_overrides_document())
            status, out, err = run_cli(["--registry", registry, "--overrides", overrides,
                                        "--expect-count", "4"] + FIXED_RUN)
            self.assertEqual(status, 0, err)
            report = json.loads(out)
            self.assertEqual(report["source_count"], 4)
            self.assertEqual(report["accepted_count"], 4)

    def test_an_invalid_run_context_is_refused(self):
        status, out, err = run_cli(["--migrated-at", "2026-07-31"] + ["--run-id", RUN_A])
        self.assertEqual(status, 1)
        self.assertEqual(out, b"")
        self.assertIn("migrated_at", err)


class TestDryRunWithSuspiciousCases(unittest.TestCase):

    SUSPICIOUS = "https://example.test/tag/ai"

    def corpus(self, tmp, rows=()):
        cases = [a_case(case_id="case-2026-9500", case_key="sus|1",
                        source_url=self.SUSPICIOUS),
                 a_case(case_id="case-2026-9501", case_key="ok|1",
                        source_url="https://example.test/cases/ok")]
        registry = write_json(os.path.join(tmp, "r.json"), a_ax_registry(cases))
        overrides = write_json(os.path.join(tmp, "o.json"),
                               an_overrides_document(rows))
        return ["--registry", registry, "--overrides", overrides,
                "--expect-count", "2"] + FIXED_RUN

    def test_unresolved_reports_completely_then_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_cli(self.corpus(tmp))
            self.assertEqual(status, 1)
            report = json.loads(out)
            self.assertEqual(report["rejected_count"], 1)
            self.assertEqual(report["unresolved_rejection_count"], 1)
            self.assertEqual(report["unresolved_case_ids"], ["case-2026-9500"])
            self.assertEqual(report["accepted_count"], 1)
            self.assertEqual(len(report["rejections"]), 1)
            self.assertEqual(report["rejections"][0]["target_url"], self.SUSPICIOUS)
            self.assertIn("--allow-unmappable", err)
            self.assertIn("case-2026-9500", err)

    def test_allow_unmappable_succeeds_and_keeps_every_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_cli(self.corpus(tmp) + ["--allow-unmappable"])
            self.assertEqual(status, 0, err)
            report = json.loads(out)
            self.assertTrue(report["allow_unmappable"])
            self.assertEqual(report["rejected_count"], 1)
            self.assertEqual(report["unresolved_rejection_count"], 1)
            self.assertEqual(report["accepted_count"], 1)
            self.assertEqual(report["rejections"][0]["rejection_reason"],
                             "ambiguous_legacy_url")

    def test_a_reviewed_admit_is_counted_and_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_cli(self.corpus(tmp, [a_review_row()]))
            self.assertEqual(status, 0, err)
            report = json.loads(out)
            self.assertEqual(report["reviewed_admit_count"], 1)
            self.assertEqual(report["reviewed_reject_count"], 0)
            self.assertEqual(report["unresolved_rejection_count"], 0)
            self.assertEqual(report["accepted_count"], 2)
            self.assertEqual(report["rejections"], [])

    def test_a_reviewed_reject_is_counted_and_stays_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_cli(
                self.corpus(tmp, [a_review_row(decision="reject",
                                               note="an index page, not the case")]))
            self.assertEqual(status, 0, err)
            report = json.loads(out)
            self.assertEqual(report["reviewed_reject_count"], 1)
            self.assertEqual(report["unresolved_rejection_count"], 0)
            self.assertEqual(report["accepted_count"], 1)
            self.assertEqual(report["rejected_count"], 1)
            self.assertIn("a reviewer confirmed the rejection",
                          report["rejections"][0]["detail"])

    def test_a_review_naming_the_wrong_rule_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _out, err = run_cli(
                self.corpus(tmp, [a_review_row(matched_rule="feed_path")]))
            self.assertEqual(status, 1)
            self.assertIn("declares matched_rule", err)

    def test_a_review_of_an_unsuspicious_case_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = a_review_row(case_id="case-2026-9501",
                               legacy_source_url="https://example.test/cases/ok")
            status, _out, err = run_cli(self.corpus(tmp, [row]))
            self.assertEqual(status, 1)
            self.assertIn("does not refuse at all", err)

    def test_rejections_are_ordered_and_row_order_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [a_case(case_id="c%d" % i, case_key="k|%d" % i,
                            source_url=url)
                     for i, url in enumerate(("https://example.test/tag/z",
                                              "https://example.test/tag/a",
                                              "https://example.test/blog/feed"))]
            overrides = write_json(os.path.join(tmp, "o.json"),
                                   an_overrides_document())
            first = write_json(os.path.join(tmp, "r1.json"), a_ax_registry(cases))
            second = write_json(os.path.join(tmp, "r2.json"),
                                a_ax_registry(list(reversed(cases))))
            args = ["--overrides", overrides, "--expect-count", "3",
                    "--allow-unmappable"] + FIXED_RUN
            status_one, out_one, _e1 = run_cli(["--registry", first] + args)
            status_two, out_two, _e2 = run_cli(["--registry", second] + args)
            self.assertEqual((status_one, status_two), (0, 0))
            self.assertEqual(out_one, out_two,
                             "source row order changed the report bytes")
            rows = json.loads(out_one)["rejections"]
            self.assertEqual([r["identity_url"] for r in rows],
                             sorted(r["identity_url"] for r in rows))
            self.assertEqual(len(rows), 3)

    def test_review_row_order_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [a_case(case_id="case-2026-9500", case_key="s|1",
                            source_url=self.SUSPICIOUS),
                     a_case(case_id="case-2026-9502", case_key="s|2",
                            source_url="https://example.test/blog/feed")]
            registry = write_json(os.path.join(tmp, "r.json"), a_ax_registry(cases))
            rows = [a_review_row(decision="reject", note="index"),
                    a_review_row(case_id="case-2026-9502",
                                 legacy_source_url="https://example.test/blog/feed",
                                 matched_rule="feed_path", decision="reject",
                                 note="a feed")]
            one = write_json(os.path.join(tmp, "o1.json"), an_overrides_document(rows))
            two = write_json(os.path.join(tmp, "o2.json"),
                             an_overrides_document(list(reversed(rows))))
            args = ["--registry", registry, "--expect-count", "2"] + FIXED_RUN
            _s1, out_one, _e1 = run_cli(args + ["--overrides", one])
            _s2, out_two, _e2 = run_cli(args + ["--overrides", two])
            self.assertEqual(out_one, out_two)


class TestNoTestEverAppliesToTheDefaultStateRoot(unittest.TestCase):
    """S7-4's `--apply` refusal is retired; this replaces what it protected.

    Once apply works, a bare `--apply` writes to the OPERATIONAL default,
    `state/taxonomy_harvest` — the real repository. Every apply in this suite
    therefore goes through `apply_cli`, which always injects `--state-root`, and
    this test proves no other invocation exists.
    """

    def test_the_apply_helper_always_injects_a_state_root(self):
        source = inspect.getsource(apply_cli)
        self.assertIn("--state-root", source)
        self.assertIn("--apply", source)

    def test_no_other_call_site_passes_apply_without_a_state_root(self):
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple)):
                continue
            literals = [e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if "--apply" in literals and "--state-root" not in literals:
                offenders.append(node.lineno)
        # The only exception is `apply_cli`'s own argument list, which injects
        # both, and the wrapper test that spells them out in full.
        self.assertEqual(offenders, [], "line(s) pass --apply with no --state-root")

    def test_the_operational_default_is_still_the_documented_one(self):
        self.assertEqual(ax_cases.DEFAULT_STATE_ROOT, "state/taxonomy_harvest")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "state", "taxonomy_harvest")),
                         "a test applied to the real repository state root")


class TestEntityAssessCli(unittest.TestCase):

    def test_stdout_equals_the_renderer_and_the_committed_document(self):
        status, out, err = run_cli([], module=ea)
        self.assertEqual(status, 0, err)
        _assessment, text = ea.build()
        self.assertEqual(out, text.encode("utf-8"))
        with open(DOCUMENT, "rb") as handle:
            self.assertEqual(out, handle.read())

    def test_an_explicit_output_path_receives_exactly_those_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "assessment.md")
            status, out, err = run_cli(["--output", target], module=ea)
            self.assertEqual(status, 0, err)
            self.assertEqual(out, b"", "with --output nothing goes to stdout")
            with open(target, "rb") as handle:
                written = handle.read()
            _status, stdout_bytes, _err = run_cli([], module=ea)
            self.assertEqual(written, stdout_bytes)
            self.assertEqual(sorted(os.listdir(tmp)), ["assessment.md"])

    def test_an_injected_registry_path_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = write_json(os.path.join(tmp, "entities.json"),
                                  a_registry([a_row()]))
            status, out, err = run_cli(["--registry", registry], module=ea)
            self.assertEqual(status, 0, err)
            self.assertIn(b"migrates 0 entities", out)

    def test_a_malformed_registry_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = os.path.join(tmp, "broken.json")
            with open(broken, "w", encoding="utf-8") as handle:
                handle.write("{")
            status, out, err = run_cli(["--registry", broken], module=ea)
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertIn("entity-assess", err)

    def test_it_creates_no_taxonomy_record_or_bundle(self):
        status, out, _err = run_cli([], module=ea)
        self.assertEqual(status, 0)
        text = out.decode("utf-8")
        self.assertIn("migrates 0 entities", text)
        for leak in ("state/taxonomy_harvest/", "data/harvested/", "runs/"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak.rstrip("/"))))


# ============================================ S7-5 · atomic apply and re-run
RUN_C = "20260802T090000Z-77"
AT_C = "2026-08-02T09:00:00Z"
BUNDLE_FILES = ("candidate_output/cases__case-studies__harvest.json",
                "manifest.json",
                "rejections/cases__case-studies__rejections.json")


def bundle_tree(root, run_id):
    """The published bundle's relative paths and bytes."""
    bundle = base.bundle_path(root, run_id)
    tree = {}
    for base_dir, dirs, files in os.walk(bundle):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base_dir, name)
            with open(path, "rb") as handle:
                tree[os.path.relpath(path, bundle).replace(os.sep, "/")] = handle.read()
    return tree


def state_root_paths(root):
    """Every path under a state root, relative and sorted — files and dirs."""
    found = []
    for base_dir, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs) + sorted(files):
            found.append(os.path.relpath(os.path.join(base_dir, name),
                                         root).replace(os.sep, "/"))
    return sorted(found)


def apply_cli(root, argv=(), run_id=RUN_A, migrated_at=AT_A):
    return run_cli(["--apply", "--state-root", root, "--run-id", run_id,
                    "--migrated-at", migrated_at] + list(argv))


def synthetic_inputs(tmp, cases, rows=()):
    registry = write_json(os.path.join(tmp, "r.json"), a_ax_registry(cases))
    overrides = write_json(os.path.join(tmp, "o.json"), an_overrides_document(rows))
    return ["--registry", registry, "--overrides", overrides,
            "--expect-count", str(len(cases))]


class TestMigrationPathHelpers(unittest.TestCase):

    def test_paths_are_derived_and_nothing_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "state")
            self.assertEqual(base.migrations_root(root), os.path.join(root, "migrations"))
            self.assertEqual(base.bundle_dirname(RUN_A), RUN_A + "__ax_cases")
            bundle = base.bundle_path(root, RUN_A)
            self.assertEqual(base.manifest_path(root, RUN_A),
                             os.path.join(bundle, "manifest.json"))
            self.assertEqual(base.candidate_artifact_path(root, RUN_A),
                             os.path.join(bundle, "candidate_output",
                                          "cases__case-studies__harvest.json"))
            self.assertEqual(base.rejection_artifact_path(root, RUN_A),
                             os.path.join(bundle, "rejections",
                                          "cases__case-studies__rejections.json"))
            self.assertFalse(os.path.exists(root), "deriving a path created one")

    def test_the_relative_path_set_is_exactly_three_files(self):
        self.assertEqual(base.BUNDLE_RELATIVE_PATHS, BUNDLE_FILES)

    def test_an_invalid_or_traversing_run_id_is_refused(self):
        for bad in ("", "..", "../../etc", "20260731T000000Z-1/../x", "run-1",
                    "20260731T000000Z", "20260731t000000z-1", None, 17,
                    "20260731T000000Z-1\\x"):
            with self.subTest(bad=bad):
                with self.assertRaises(base.MigrationPathError):
                    base.bundle_path("root", bad)

    def test_an_empty_state_root_is_refused(self):
        for bad in ("", "   ", None):
            with self.subTest(bad=bad):
                with self.assertRaises(base.MigrationPathError):
                    base.migrations_root(bad)

    def test_the_staging_name_carries_the_prefix_and_the_run_id(self):
        name = base.staging_name(RUN_A, "abc123")
        self.assertTrue(name.startswith(base.STAGING_PREFIX))
        self.assertIn(RUN_A, name)
        self.assertTrue(name.endswith("_abc123"))
        for bad in ("", "a/b", "..", None):
            with self.subTest(bad=bad):
                with self.assertRaises(base.MigrationPathError):
                    base.staging_name(RUN_A, bad)

    def test_ownership_is_proved_from_the_parent_and_the_name(self):
        root = os.path.join("some", "state")
        mine = os.path.join(base.migrations_root(root),
                            base.staging_name(RUN_A, "deadbeef"))
        self.assertTrue(base.owns_staging(mine, root, RUN_A))
        self.assertFalse(base.owns_staging(mine, root, RUN_B))
        self.assertFalse(base.owns_staging(mine, os.path.join("other", "state"), RUN_A))
        self.assertFalse(base.owns_staging(
            os.path.join(base.migrations_root(root), ".tmp_other_thing"), root, RUN_A))
        self.assertFalse(base.owns_staging(
            os.path.join(base.migrations_root(root), RUN_A + "__ax_cases"), root, RUN_A))
        self.assertFalse(base.owns_staging(None, root, RUN_A))

    def test_the_guard_is_still_pure_after_the_path_helpers_arrived(self):
        """S7-2's contract, kept: the guard path touches no filesystem."""
        import socket
        with mock.patch("builtins.open", side_effect=AssertionError("opened a file")), \
                mock.patch.object(socket, "socket",
                                  side_effect=AssertionError("opened a socket")), \
                mock.patch("os.path.exists", side_effect=AssertionError("stat")), \
                mock.patch("os.makedirs", side_effect=AssertionError("mkdir")):
            self.assertIsNone(base.suspicious_url_match("https://example.test/a"))
            self.assertEqual(base.suspicious_url_match(
                "https://example.test/a/feed").rule_id, "feed_path")
            self.assertTrue(base.looks_like_index_or_search("https://example.test/tag/x"))

    def test_the_guard_functions_reach_no_path_helper(self):
        with open(os.path.join(ROOT, "src", "harvest", "migrate", "base.py"),
                  encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        guard = {"suspicious_url_match", "looks_like_index_or_search", "_parts",
                 "_segments", "_query_keys", "_search_engine_host",
                 "_search_query_path", "_feed_path", "_index_page"}
        forbidden = {"os", "open", "makedirs", "rmdir", "unlink", "replace",
                     "migrations_root", "bundle_path", "staging_name"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name not in guard:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name):
                    self.assertNotIn(inner.id, forbidden, node.name)
                if isinstance(inner, ast.Attribute):
                    self.assertNotIn(inner.attr, forbidden, node.name)


class TestReportFamilyE29(unittest.TestCase):
    """E29: `report_type` names the family; `dry_run` is the discriminator."""

    def test_the_public_constant_is_the_family_not_a_mode(self):
        self.assertEqual(ax_cases.REPORT_TYPE, "ax_cases")
        self.assertEqual(ax_cases.REPORT_VERSION, 1)

    def test_dry_run_and_apply_share_the_family_and_differ_only_in_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            root = os.path.join(tmp, "state")
            status, dry, _err = run_cli(args + FIXED_RUN)
            self.assertEqual(status, 0)
            status, applied, err = apply_cli(root, args)
            self.assertEqual(status, 0, err)
            dry_report, apply_report = json.loads(dry), json.loads(applied)
            self.assertEqual(dry_report["report_type"], "ax_cases")
            self.assertEqual(apply_report["report_type"], "ax_cases")
            self.assertTrue(dry_report["dry_run"])
            self.assertFalse(apply_report["dry_run"])
            self.assertEqual(sorted(dry_report), sorted(apply_report))
            self.assertEqual(len(sorted(dry_report)), 16)
            differing = {k for k in dry_report if dry_report[k] != apply_report[k]}
            self.assertEqual(differing, {"dry_run"})

    def test_no_output_carries_the_retired_mode_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            root = os.path.join(tmp, "state")
            _s, dry, _e = run_cli(args + FIXED_RUN)
            _s, applied, _e = apply_cli(root, args)
            for payload in (dry, applied):
                self.assertNotIn(b"ax_cases_dry_run", payload)
                self.assertNotIn(b"ax_cases_apply", payload)
            for data in bundle_tree(root, RUN_A).values():
                self.assertNotIn(b"ax_cases_dry_run", data)

    def test_relabelling_changed_no_dry_run_behaviour(self):
        """Counts, ordering, exit status and the no-write guarantee are intact."""
        status, out, err = run_cli(list(FIXED_RUN))
        report = json.loads(out)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual((report["source_count"], report["accepted_count"],
                          report["rejected_count"]), (231, 231, 0))
        with tempfile.TemporaryDirectory() as tmp:
            cases = [a_case(case_id="c%d" % i, case_key="k|%d" % i, source_url=url)
                     for i, url in enumerate(("https://example.test/tag/z",
                                              "https://example.test/tag/a"))]
            args = synthetic_inputs(tmp, cases)
            before = tree_snapshot(tmp)
            status, out, err = run_cli(args + FIXED_RUN)
            self.assertEqual(status, 1)
            rows = json.loads(out)["rejections"]
            self.assertEqual([r["identity_url"] for r in rows],
                             sorted(r["identity_url"] for r in rows))
            self.assertEqual(tree_snapshot(tmp), before)


class TestApplyOverTheProtectedCorpus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = os.path.join(cls.tmp.name, "state")
        cls.digest_before = sha256_file(AX_REGISTRY)
        cls.status, cls.out, cls.err = apply_cli(cls.root)
        cls.report = json.loads(cls.out) if cls.out else {}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_it_publishes_and_reports_231_accepted_0_rejected(self):
        self.assertEqual(self.status, 0, self.err)
        self.assertEqual(self.err, "")
        self.assertFalse(self.report["dry_run"])
        self.assertEqual(self.report["accepted_count"], EXPECTED_AX_CASES)
        self.assertEqual(self.report["rejected_count"], 0)
        self.assertEqual(self.report["source_count"], EXPECTED_AX_CASES)
        self.assertTrue(self.out.endswith(b"\n"))
        self.assertFalse(self.out.endswith(b"\n\n"))

    def test_the_bundle_is_exactly_three_files(self):
        tree = bundle_tree(self.root, RUN_A)
        self.assertEqual(tuple(sorted(tree)), BUNDLE_FILES)
        bundle = "migrations/%s__ax_cases" % RUN_A
        self.assertEqual(state_root_paths(self.root), sorted([
            "migrations",
            bundle,
            bundle + "/candidate_output",
            bundle + "/candidate_output/cases__case-studies__harvest.json",
            bundle + "/manifest.json",
            bundle + "/rejections",
            bundle + "/rejections/cases__case-studies__rejections.json",
        ]))

    def test_all_three_documents_validate_against_the_committed_schemas(self):
        tree = bundle_tree(self.root, RUN_A)
        for relative, schema_name in (
                (BUNDLE_FILES[0], "cell_artifact.v1.json"),
                (BUNDLE_FILES[1], "run_manifest.v1.json"),
                (BUNDLE_FILES[2], "rejection.v1.json")):
            schema_mod.validate_or_raise(json.loads(tree[relative]), schema_name)

    def test_the_candidate_artifact_carries_derived_counts_and_one_source_row(self):
        artifact = json.loads(bundle_tree(self.root, RUN_A)[BUNDLE_FILES[0]])
        self.assertEqual(artifact["cell_id"], "cases__case-studies")
        self.assertEqual(artifact["topic"], "Cases")
        self.assertEqual(artifact["category"], "Case Studies")
        self.assertEqual(artifact["harvest_run_id"], RUN_A)
        self.assertEqual(artifact["generated_at"], AT_A)
        self.assertEqual(len(artifact["records"]), EXPECTED_AX_CASES)
        meta = artifact["metadata"]
        self.assertEqual(meta["total_records"], EXPECTED_AX_CASES)
        self.assertEqual(meta["full_records"], EXPECTED_AX_CASES)
        self.assertEqual(meta["cross_references"], 0)
        self.assertEqual(meta["rejected"], 0)
        self.assertEqual(meta["sources"], [{"source_id": "ax_case_harvest_registry",
                                            "adapter": "migration", "result": "ok",
                                            "candidates": EXPECTED_AX_CASES,
                                            "accepted": EXPECTED_AX_CASES,
                                            "requests_made": 0}])
        self.assertNotIn("elapsed_sec", json.dumps(meta))

    def test_the_rejection_artifact_is_written_even_when_empty(self):
        document = json.loads(bundle_tree(self.root, RUN_A)[BUNDLE_FILES[2]])
        self.assertEqual(document["rejections"], [])
        self.assertEqual(document["cell_id"], "cases__case-studies")
        self.assertEqual(document["harvest_run_id"], RUN_A)
        self.assertEqual(document["generated_at"], AT_A)

    def test_the_manifest_is_one_migration_cell_and_is_ineligible_by_derivation(self):
        manifest = json.loads(bundle_tree(self.root, RUN_A)[BUNDLE_FILES[1]])
        self.assertEqual(manifest["mode"], "migration")
        self.assertEqual(len(manifest["cells"]), 1)
        self.assertEqual(manifest["cells"][0], {
            "cell_id": "cases__case-studies", "topic_slug": "cases",
            "category_slug": "case-studies", "status": "ok",
            "candidates": EXPECTED_AX_CASES, "accepted": EXPECTED_AX_CASES,
            "rejected": 0, "requests_made": 0, "adapters_used": ["migration"]})
        self.assertEqual(manifest["source_preflight"], [])
        self.assertEqual(manifest["classification_decisions"], [])
        self.assertEqual(manifest["config"], {"topics": ["cases"], "enrich": False,
                                              "bounds": {"expected_source_count": 231}})
        self.assertFalse(manifest["publication_eligible"])
        self.assertIn("231 of 231", manifest["publication_ineligible_reason"])
        for absent in ("request_accounting", "coverage", "rounds",
                       "alias_conflicts_count", "lane_quality", "merges"):
            self.assertNotIn(absent, manifest)

    def test_nothing_else_is_created_anywhere(self):
        paths = state_root_paths(self.root)
        for forbidden in ("LATEST_RUN_ID", "runs", "ledgers", "coverage", "topics",
                          "alias_conflicts", "data"):
            self.assertFalse(any(forbidden in p for p in paths), forbidden)
        for leak in ("state/taxonomy_harvest", "data/harvested", "runs", "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)), leak)

    def test_the_protected_registry_is_untouched(self):
        self.assertEqual(sha256_file(AX_REGISTRY), self.digest_before)


class TestSameRunIdIsRefused(unittest.TestCase):

    def test_a_second_apply_refuses_before_reading_any_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args)
            self.assertEqual(status, 0, err)
            first = bundle_tree(root, RUN_A)
            before = state_root_paths(root)

            calls = []
            real_loader = ax_cases.load_json_document

            def counting_loader(path, label):
                calls.append(label)
                return real_loader(path, label)

            with mock.patch.object(ax_cases, "load_json_document", counting_loader):
                status, out, err = apply_cli(root, args)
            self.assertEqual(status, 1)
            self.assertEqual(out, b"", "a refused apply printed a report")
            self.assertIn("already exists", err)
            self.assertEqual(calls, [], "the refusal read an input first")
            self.assertEqual(bundle_tree(root, RUN_A), first,
                             "the first bundle was disturbed")
            self.assertEqual(state_root_paths(root), before)

    def test_the_counting_loader_is_not_vacuous(self):
        """A successful apply DOES read both inputs through the same seam."""
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            calls = []
            real_loader = ax_cases.load_json_document

            def counting_loader(path, label):
                calls.append(label)
                return real_loader(path, label)

            with mock.patch.object(ax_cases, "load_json_document", counting_loader):
                status, _out, err = apply_cli(os.path.join(tmp, "state"), args)
            self.assertEqual(status, 0, err)
            self.assertEqual(calls, ["AX case registry", "reviewed-overrides document"])

    def test_a_file_or_a_directory_at_the_destination_both_refuse(self):
        for kind in ("file", "directory"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as tmp:
                    args = synthetic_inputs(tmp, [a_case()])
                    root = os.path.join(tmp, "state")
                    final = base.bundle_path(root, RUN_A)
                    os.makedirs(os.path.dirname(final))
                    if kind == "file":
                        with open(final, "w", encoding="utf-8") as handle:
                            handle.write("occupied")
                    else:
                        os.makedirs(final)
                    status, out, err = apply_cli(root, args)
                    self.assertEqual(status, 1)
                    self.assertEqual(out, b"")
                    self.assertIn("already exists", err)


class TestDistinctRunsAreDeterministic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = os.path.join(cls.tmp.name, "state")
        cls.status_a, _out_a, cls.err_a = apply_cli(cls.root, run_id=RUN_A,
                                                    migrated_at=AT_A)
        cls.status_b, _out_b, cls.err_b = apply_cli(cls.root, run_id=RUN_C,
                                                    migrated_at=AT_C)
        cls.first = bundle_tree(cls.root, RUN_A)
        cls.second = bundle_tree(cls.root, RUN_C)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_both_runs_published_side_by_side(self):
        self.assertEqual((self.status_a, self.status_b), (0, 0),
                         self.err_a + self.err_b)
        self.assertEqual(tuple(sorted(self.first)), BUNDLE_FILES)
        self.assertEqual(tuple(sorted(self.second)), BUNDLE_FILES)
        self.assertEqual(sorted(os.listdir(base.migrations_root(self.root))),
                         sorted([RUN_A + "__ax_cases", RUN_C + "__ax_cases"]))

    def differences(self, relative):
        left = json.loads(self.first[relative])
        right = json.loads(self.second[relative])
        changed = set()

        def walk(a, b, path):
            if isinstance(a, dict):
                self.assertEqual(sorted(a), sorted(b), path)
                for key in a:
                    walk(a[key], b[key], path + "." + key)
            elif isinstance(a, list):
                self.assertEqual(len(a), len(b), path)
                for index, (x, y) in enumerate(zip(a, b)):
                    walk(x, y, "%s[%d]" % (path, index))
            elif a != b:
                changed.add(path)

        walk(left, right, "")
        return changed

    def test_the_candidate_artifact_moves_exactly_four_leaf_families(self):
        changed = self.differences(BUNDLE_FILES[0])
        record_leaves = {p for p in changed if p.startswith(".records[")}
        top = changed - record_leaves
        self.assertEqual(top, {".generated_at", ".harvest_run_id"})
        suffixes = {p.split("]", 1)[1] for p in record_leaves}
        self.assertEqual(suffixes, {".harvest_run_id",
                                    ".provenance.migration.migrated_at"})
        self.assertEqual(len(record_leaves), EXPECTED_AX_CASES * 2)

    def test_the_manifest_moves_exactly_three_leaves(self):
        self.assertEqual(self.differences(BUNDLE_FILES[1]),
                         {".harvest_run_id", ".started_at", ".finished_at"})

    def test_the_rejection_document_moves_only_its_own_two_leaves(self):
        self.assertEqual(self.differences(BUNDLE_FILES[2]),
                         {".generated_at", ".harvest_run_id"})

    def test_normalizing_exactly_those_leaves_makes_the_bytes_equal(self):
        def normalize(document):
            document = copy.deepcopy(document)
            for key in ("harvest_run_id", "generated_at", "started_at", "finished_at"):
                document.pop(key, None)
            for record in document.get("records", ()):
                record.pop("harvest_run_id", None)
                record["provenance"]["migration"].pop("migrated_at", None)
            for row in document.get("rejections", ()):
                row.pop("rejected_at", None)
            return json.dumps(document, sort_keys=True, ensure_ascii=False)

        for relative in BUNDLE_FILES:
            with self.subTest(relative=relative):
                self.assertEqual(normalize(json.loads(self.first[relative])),
                                 normalize(json.loads(self.second[relative])))

    def test_the_two_runs_agree_on_every_count_and_ordering(self):
        first = json.loads(self.first[BUNDLE_FILES[0]])
        second = json.loads(self.second[BUNDLE_FILES[0]])
        self.assertEqual(len(first["records"]), EXPECTED_AX_CASES)
        self.assertEqual([r["record_id"] for r in first["records"]],
                         [r["record_id"] for r in second["records"]])
        self.assertEqual([r["content_id"] for r in first["records"]],
                         [r["content_id"] for r in second["records"]])
        states = [facets_mod.reporting_state(r) for r in first["records"]]
        self.assertEqual(states, [facets_mod.reporting_state(r)
                                  for r in second["records"]])
        self.assertEqual(first["metadata"], second["metadata"])
        for manifest in (json.loads(self.first[BUNDLE_FILES[1]]),
                         json.loads(self.second[BUNDLE_FILES[1]])):
            self.assertFalse(manifest["publication_eligible"])

    def test_input_row_order_does_not_change_the_published_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [a_case(case_id="c%d" % i, case_key="k|%d" % i,
                            source_url="https://example.test/case/%d" % i)
                     for i in range(5)]
            forward = write_json(os.path.join(tmp, "r1.json"), a_ax_registry(cases))
            backward = write_json(os.path.join(tmp, "r2.json"),
                                  a_ax_registry(list(reversed(cases))))
            overrides = write_json(os.path.join(tmp, "o.json"),
                                   an_overrides_document())
            roots = []
            for index, registry in enumerate((forward, backward)):
                root = os.path.join(tmp, "state%d" % index)
                status, _out, err = apply_cli(
                    root, ["--registry", registry, "--overrides", overrides,
                           "--expect-count", "5"])
                self.assertEqual(status, 0, err)
                roots.append(bundle_tree(root, RUN_A))
            self.assertEqual(roots[0], roots[1])


class TestFaultInjectionLeavesNothingBehind(unittest.TestCase):
    """Five boundaries. Every one must leave the state root as it was found."""

    def prepared(self, tmp, pre_existing_migrations=False):
        args = synthetic_inputs(tmp, [a_case()])
        root = os.path.join(tmp, "state")
        os.makedirs(root)
        # An unrelated sibling and an unrelated staging-like directory: neither
        # may be touched by any cleanup.
        with open(os.path.join(root, "unrelated.txt"), "w", encoding="utf-8") as h:
            h.write("keep me")
        if pre_existing_migrations:
            migrations = base.migrations_root(root)
            os.makedirs(os.path.join(migrations, base.STAGING_PREFIX + "someone_else"))
            with open(os.path.join(migrations, "note.txt"), "w",
                      encoding="utf-8") as h:
                h.write("not mine")
        return args, root

    def assert_nothing_published(self, root, before):
        self.assertFalse(os.path.exists(base.bundle_path(root, RUN_A)))
        self.assertEqual(state_root_paths(root), before)
        migrations = base.migrations_root(root)
        if os.path.isdir(migrations):
            for name in os.listdir(migrations):
                self.assertFalse(name.startswith(base.STAGING_PREFIX + RUN_A),
                                 "owned staging survived: %s" % name)

    def test_boundary_1_failure_before_the_first_document_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp, pre_existing_migrations=True)
            before = state_root_paths(root)
            with mock.patch.object(ax_cases.artifacts_mod, "write_document",
                                   side_effect=RuntimeError("boundary 1")):
                with self.assertRaises(RuntimeError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3],
                                             expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assert_nothing_published(root, before)

    def test_boundaries_2_and_3_failure_after_a_document_write(self):
        for stop_after in (1, 2):
            with self.subTest(stop_after=stop_after):
                with tempfile.TemporaryDirectory() as tmp:
                    args, root = self.prepared(tmp)
                    before = state_root_paths(root)
                    real = ax_cases.artifacts_mod.write_document
                    calls = []

                    def failing(path, document, schema_name):
                        calls.append(path)
                        if len(calls) > stop_after:
                            raise RuntimeError("boundary after %d" % stop_after)
                        return real(path, document, schema_name)

                    with mock.patch.object(ax_cases.artifacts_mod, "write_document",
                                           failing):
                        with self.assertRaises(RuntimeError):
                            ax_cases.apply_migration(
                                state_root=root, registry_path=args[1],
                                overrides_path=args[3], expected_count=1,
                                harvest_run_id=RUN_A, migrated_at=AT_A)
                    self.assertEqual(len(calls), stop_after + 1)
                    self.assert_nothing_published(root, before)

    def test_boundary_4_failure_after_every_write_before_the_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            before = state_root_paths(root)
            with mock.patch.object(ax_cases, "_verify_staged_paths",
                                   side_effect=RuntimeError("boundary 4")):
                with self.assertRaises(RuntimeError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assert_nothing_published(root, before)

    def test_boundary_5_failure_during_the_final_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            before = state_root_paths(root)
            with mock.patch.object(ax_cases.os, "replace",
                                   side_effect=OSError("boundary 5")):
                with self.assertRaises(OSError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assert_nothing_published(root, before)

    def test_a_keyboard_interrupt_behaves_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            before = state_root_paths(root)
            with mock.patch.object(ax_cases.artifacts_mod, "write_document",
                                   side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assert_nothing_published(root, before)

    def test_an_unrelated_staging_directory_and_sibling_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp, pre_existing_migrations=True)
            foreign = os.path.join(base.migrations_root(root),
                                   base.STAGING_PREFIX + "someone_else")
            note = os.path.join(base.migrations_root(root), "note.txt")
            with mock.patch.object(ax_cases.os, "replace",
                                   side_effect=OSError("nope")):
                with self.assertRaises(OSError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assertTrue(os.path.isdir(foreign), "a foreign staging dir was removed")
            with open(note, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "not mine")
            self.assertTrue(os.path.exists(os.path.join(root, "unrelated.txt")))

    def test_a_pre_existing_migrations_parent_is_never_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            migrations = base.migrations_root(root)
            os.makedirs(migrations)
            with mock.patch.object(ax_cases.os, "replace", side_effect=OSError("x")):
                with self.assertRaises(OSError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assertTrue(os.path.isdir(migrations),
                            "a parent this apply did not create was removed")

    def test_a_newly_created_empty_migrations_parent_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            migrations = base.migrations_root(root)
            self.assertFalse(os.path.isdir(migrations))
            with mock.patch.object(ax_cases.os, "replace", side_effect=OSError("x")):
                with self.assertRaises(OSError):
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assertFalse(os.path.isdir(migrations),
                             "the parent this apply created was left behind")

    def test_cleanup_refuses_a_path_it_does_not_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "state")
            foreign = os.path.join(base.migrations_root(root), "not-staging")
            os.makedirs(foreign)
            self.assertFalse(ax_cases._remove_owned_staging(foreign, root, RUN_A))
            self.assertTrue(os.path.isdir(foreign))
            elsewhere = os.path.join(tmp, "elsewhere")
            os.makedirs(elsewhere)
            self.assertFalse(ax_cases._remove_owned_staging(elsewhere, root, RUN_A))
            self.assertTrue(os.path.isdir(elsewhere))

    def test_the_rename_boundary_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, root = self.prepared(tmp)
            final = base.bundle_path(root, RUN_A)
            observed = {}
            real_replace = os.replace

            def observing(src, dst):
                observed["final_absent_before"] = not os.path.exists(final)
                observed["staged"] = tuple(sorted(ax_cases._staged_paths(src)))
                return real_replace(src, dst)

            with mock.patch.object(ax_cases.os, "replace", observing):
                published = ax_cases.apply_migration(
                    state_root=root, registry_path=args[1], overrides_path=args[3],
                    expected_count=1, harvest_run_id=RUN_A, migrated_at=AT_A)[1]
            self.assertTrue(observed["final_absent_before"])
            self.assertEqual(observed["staged"], BUNDLE_FILES)
            self.assertEqual(tuple(sorted(bundle_tree(root, RUN_A))), BUNDLE_FILES)
            self.assertEqual(published, final)
            for name in os.listdir(base.migrations_root(root)):
                self.assertFalse(name.startswith(base.STAGING_PREFIX))


class TestLateDestinationAppearance(unittest.TestCase):

    def test_a_bundle_appearing_during_staging_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            root = os.path.join(tmp, "state")
            final = base.bundle_path(root, RUN_A)
            sentinel_bytes = b"sentinel bundle"
            real_verify = ax_cases._verify_staged_paths

            def verify_then_squat(staging):
                found = real_verify(staging)
                os.makedirs(final)
                with open(os.path.join(final, "manifest.json"), "wb") as handle:
                    handle.write(sentinel_bytes)
                return found

            with mock.patch.object(ax_cases, "_verify_staged_paths",
                                   verify_then_squat):
                with self.assertRaises(ax_cases.AxMigrationError) as caught:
                    ax_cases.apply_migration(state_root=root, registry_path=args[1],
                                             overrides_path=args[3], expected_count=1,
                                             harvest_run_id=RUN_A, migrated_at=AT_A)
            self.assertIn("appeared while this bundle was being staged",
                          str(caught.exception))
            with open(os.path.join(final, "manifest.json"), "rb") as handle:
                self.assertEqual(handle.read(), sentinel_bytes)
            self.assertEqual(sorted(os.listdir(final)), ["manifest.json"])
            for name in os.listdir(base.migrations_root(root)):
                self.assertFalse(name.startswith(base.STAGING_PREFIX),
                                 "owned staging survived the refusal")


class TestApplyPolicyAndCli(unittest.TestCase):

    SUSPICIOUS = "https://example.test/tag/ai"

    def suspicious_inputs(self, tmp, rows=()):
        cases = [a_case(case_id="case-2026-9500", case_key="s|1",
                        source_url=self.SUSPICIOUS),
                 a_case(case_id="case-2026-9501", case_key="ok|1",
                        source_url="https://example.test/cases/ok")]
        return synthetic_inputs(tmp, cases, rows)

    def test_unresolved_without_allow_reports_completely_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.suspicious_inputs(tmp)
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args)
            self.assertEqual(status, 1)
            report = json.loads(out)
            self.assertEqual(report["unresolved_rejection_count"], 1)
            self.assertEqual(len(report["rejections"]), 1)
            self.assertFalse(report["dry_run"])
            self.assertIn("--allow-unmappable", err)
            self.assertFalse(os.path.exists(root), "a refused apply created a root")

    def test_allow_unmappable_publishes_the_accepted_and_the_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.suspicious_inputs(tmp)
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args + ["--allow-unmappable"])
            self.assertEqual(status, 0, err)
            tree = bundle_tree(root, RUN_A)
            artifact = json.loads(tree[BUNDLE_FILES[0]])
            rejections = json.loads(tree[BUNDLE_FILES[2]])
            self.assertEqual(len(artifact["records"]), 1)
            self.assertEqual(artifact["metadata"]["rejected"], 1)
            self.assertEqual(len(rejections["rejections"]), 1)
            self.assertEqual(rejections["rejections"][0]["target_url"], self.SUSPICIOUS)
            for record in artifact["records"]:
                self.assertNotEqual(record["target_url"], self.SUSPICIOUS)
            manifest = json.loads(tree[BUNDLE_FILES[1]])
            self.assertEqual(manifest["cells"][0]["rejected"], 1)
            self.assertEqual(manifest["cells"][0]["accepted"], 1)

    def test_a_reviewed_admit_publishes_the_raw_url_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.suspicious_inputs(tmp, [a_review_row()])
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args)
            self.assertEqual(status, 0, err)
            artifact = json.loads(bundle_tree(root, RUN_A)[BUNDLE_FILES[0]])
            urls = {r["target_url"] for r in artifact["records"]}
            self.assertIn(self.SUSPICIOUS, urls)
            self.assertEqual(len(artifact["records"]), 2)
            self.assertEqual(json.loads(out)["reviewed_admit_count"], 1)

    def test_a_reviewed_reject_publishes_it_as_a_reviewed_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.suspicious_inputs(tmp, [a_review_row(decision="reject",
                                                             note="an index page")])
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args)
            self.assertEqual(status, 0, err)
            tree = bundle_tree(root, RUN_A)
            rejections = json.loads(tree[BUNDLE_FILES[2]])["rejections"]
            self.assertEqual(len(rejections), 1)
            self.assertIn("a reviewer confirmed the rejection", rejections[0]["detail"])
            self.assertEqual(json.loads(out)["reviewed_reject_count"], 1)

    def test_a_count_mismatch_or_malformed_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = synthetic_inputs(tmp, [a_case()])
            root = os.path.join(tmp, "state")
            status, out, err = apply_cli(root, args[:-2] + ["--expect-count", "9"])
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertFalse(os.path.exists(root))
            status, out, err = apply_cli(root, ["--registry",
                                                os.path.join(tmp, "missing.json")])
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertFalse(os.path.exists(root))

    def test_state_root_without_apply_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_cli(["--state-root", tmp] + list(FIXED_RUN))
            self.assertEqual(status, 1)
            self.assertEqual(out, b"")
            self.assertIn("only meaningful with --apply", err)
            self.assertEqual(os.listdir(tmp), [])

    def test_the_wrapper_forwards_a_state_root_containing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "a state root with spaces")
            directory = os.path.join(tmp, "inputs with spaces")
            os.makedirs(directory)
            registry = write_json(os.path.join(directory, "r.json"),
                                  a_ax_registry([a_case()]))
            overrides = write_json(os.path.join(directory, "o.json"),
                                   an_overrides_document())
            status, out, err = run_wrapper(
                ["ax-cases", "--apply", "--state-root", root,
                 "--registry", registry, "--overrides", overrides,
                 "--expect-count", "1", "--run-id", RUN_A, "--migrated-at", AT_A])
            self.assertEqual(status, 0, err.decode("utf-8"))
            self.assertFalse(json.loads(out)["dry_run"])
            self.assertEqual(tuple(sorted(bundle_tree(root, RUN_A))), BUNDLE_FILES)

    def test_no_apply_ever_writes_to_the_real_repository_state_root(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "state", "taxonomy_harvest")))
        for leak in ("data/harvested", "runs", "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, leak)), leak)

    def test_the_protected_inputs_are_byte_identical(self):
        self.assertEqual(sha256_file(AX_REGISTRY), sha256_file(AX_REGISTRY))
        digest = sha256_file(OVERRIDES)
        with tempfile.TemporaryDirectory() as tmp:
            apply_cli(os.path.join(tmp, "state"))
        self.assertEqual(sha256_file(OVERRIDES), digest)
        self.assertEqual(sha256_file(REGISTRY), sha256_file(REGISTRY))


if __name__ == "__main__":
    unittest.main()
