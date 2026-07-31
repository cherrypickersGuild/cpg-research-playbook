#!/usr/bin/env python3
"""test_compare.py — run comparison and publication diff (S9-4).

S9-4 adds the two commands that turn "two smokes exited 0" into "the two smokes
AGREE", and the one that proves live work never touched the publication path.
Both read. Seven failures this suite defends against:

  * A COMPARATOR THAT FORGIVES. There is no `--normalize` (E9-14). Every
    differing JSON path is enumerated and classified into exactly one of three
    sections, and a field belonging to no committed schema class is an INVARIANT
    VIOLATION rather than a silence. A normalizer forgives every field it was not
    told about; the day a sixth field starts moving, it passes.
  * AN IDENTITY THAT MOVED. `record_id`, `content_id`, `identity_url`, `cell_id`,
    `canonical_url`, the whole `classification` and `case_facets` subtrees and
    every non-freshness score must be identical for a record present in both
    runs. `freshness_score` is the one score that is a clock reading.
  * A COUNT CONTRADICTION RESOLVED THE WRONG WAY (E9-16). WITHIN one run,
    metadata must agree with that run's own records — a violation. BETWEEN runs, a
    changed count is content — not a violation.
  * A COMPARISON THAT DEMANDS A POINTER. Neither run need be `LATEST_RUN_ID`, and
    `runvalidate.validate_run()` is NOT weakened to achieve it: it still requires
    pointer agreement, because it answers a different question.
  * A REPORT WHOSE BYTES DEPEND ON ORDER. Reordering records, or the keys of a
    JSON object, must not change one byte of the report.
  * A `diff` THAT CANNOT COUNT TO FOUR. "Absent", "present but empty", "present
    with differences" and "present with none" are four distinguishable answers,
    and an absent publication root is a real result that exits 0.
  * A COMMAND THAT WRITES. Neither touches either run tree, the shared state,
    `LATEST_RUN_ID`, or the publication root — including the repository's
    `data/harvested/`, which `diff` names by default and must only look at.

The 24 shared ledger and rejection documents are never presented as historical
A/B snapshots: they are updated in place and have no per-run form.

Run via tests/test_taxonomy_compare.sh.
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, cli, compare, run_cells, runvalidate  # noqa: E402

COMPARE_PATH = os.path.join(ROOT, "src", "harvest", "compare.py")
RUN_A = "20260731T120000Z-201"
RUN_B = "20260731T130000Z-202"


def read_source(path):
    """Whole-file text, with the handle closed — these tests scan source a lot."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def run_cli(*argv):
    """The CLI as a real process, so exit codes are the shell's own."""
    return subprocess.run([sys.executable, "-m", "src.harvest.cli", *argv],
                          cwd=ROOT, capture_output=True)


def tree_hash(root):
    """A content hash of every file under `root`, path included."""
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            digest.update(os.path.relpath(full, root).replace(os.sep, "/").encode())
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def a_record(record_id, **overrides):
    """One full record carrying at least one field from each of the three classes."""
    record = {
        "record_id": record_id,
        "content_id": "content-%s" % record_id,
        "identity_url": "https://example.test/%s" % record_id,
        "canonical_url": "https://example.test/%s" % record_id,
        "cell_id": "cases__case-studies",
        "record_type": "full",
        "title": "Title %s" % record_id,
        "summary": "Summary %s" % record_id,
        "quality_score": 0.8,
        "relevance_score": 0.7,
        "audience_fit_score": 0.6,
        "freshness_score": 0.5,
        "discovered_at": "2026-07-31T12:00:00Z",
        "last_checked_at": "2026-07-31T12:00:00Z",
        "classification": {"primary": "cases", "confidence": 0.9},
        "case_facets": {"industries": ["software"]},
    }
    record.update(overrides)
    return record


class RunTreeMixin:
    """Builds complete 18-document run trees. Writes only under its own temp root."""

    @classmethod
    def state_root(cls):
        return cls._root

    @classmethod
    def setUpClass(cls):
        cls._root = tempfile.mkdtemp(prefix="s94_state_")
        cls.addClassCleanup(shutil.rmtree, cls._root, True)

    def write_run(self, run_id, records=None, root=None, mutate=None):
        """Write one complete selected-run tree. Returns the state root."""
        root = root or self._root
        records = list(records if records is not None else [a_record("r1"),
                                                            a_record("r2")])
        run_directory = artifacts.run_dir(root, run_id)
        os.makedirs(os.path.join(run_directory, "cells"), exist_ok=True)
        os.makedirs(os.path.join(run_directory, "topics"), exist_ok=True)

        documents = {}
        cell_ids = runvalidate.configured_cell_ids()
        for cell_id in cell_ids:
            held = records if cell_id == "cases__case-studies" else []
            full = sum(1 for r in held if r.get("record_type") != "cross_reference")
            cross = len(held) - full
            documents["cells/%s.json" % cell_id] = {
                "schema_version": "1.0.0",
                "artifact_type": "cell",
                "harvest_run_id": run_id,
                "generated_at": "2026-07-31T12:00:00Z",
                "cell_id": cell_id,
                "records": list(held),
                "metadata": {"full_records": full, "cross_references": cross,
                             "total_records": full + cross},
            }
        for slug in runvalidate.configured_topic_slugs():
            held = records if slug == "cases" else []
            full = sum(1 for r in held if r.get("record_type") != "cross_reference")
            cross = len(held) - full
            documents["topics/%s.json" % slug] = {
                "schema_version": "1.0.0",
                "artifact_type": "topic",
                "harvest_run_id": run_id,
                "generated_at": "2026-07-31T12:00:00Z",
                "topic_slug": slug,
                "records": list(held),
                "metadata": {"full_records": full, "cross_references": cross,
                             "total_records": full + cross},
            }
        documents["coverage.json"] = {
            "schema_version": "1.0.0", "harvest_run_id": run_id,
            "generated_at": "2026-07-31T12:00:00Z",
            "records": [{"record_id": r["record_id"], "gap": 0} for r in records],
        }
        documents["alias_conflicts.json"] = {
            "schema_version": "1.0.0", "artifact_type": "alias_conflicts",
            "harvest_run_id": run_id, "generated_at": "2026-07-31T12:00:00Z",
            "alias_conflicts_count": 0, "conflicts": [],
        }
        documents["manifest.json"] = {
            "schema_version": "1.0.0", "harvest_run_id": run_id,
            "generated_at": "2026-07-31T12:00:00Z",
            "started_at": "2026-07-31T11:59:00Z",
            "finished_at": "2026-07-31T12:00:00Z",
            "mode": "smoke", "publication_eligible": False,
            "cells": [{"cell_id": cid, "status": "ok"} for cid in cell_ids],
        }
        if mutate is not None:
            mutate(documents)

        for name, document in documents.items():
            path = os.path.join(run_directory, name.replace("/", os.sep))
            with open(path, "wb") as handle:
                handle.write(artifacts.serialize(document))
        return root


class TestSelectedDocumentSet(RunTreeMixin, unittest.TestCase):
    def test_exactly_the_eighteen_selected_documents_are_named(self):
        names = compare.selected_document_names()
        self.assertEqual(len(names), 18)
        self.assertEqual(len(names), compare.SELECTED_DOCUMENTS)
        self.assertEqual(len([n for n in names if n.startswith("cells/")]), 12)
        self.assertEqual(len([n for n in names if n.startswith("topics/")]), 3)
        for name in ("coverage.json", "alias_conflicts.json", "manifest.json"):
            self.assertIn(name, names)

    def test_the_twenty_four_shared_documents_are_never_named(self):
        """Ledgers and rejection logs have no historical A/B form."""
        names = compare.selected_document_names()
        for name in names:
            self.assertFalse(name.startswith("ledgers/"), name)
            self.assertFalse(name.startswith("rejections/"), name)
        self.assertEqual(compare.SHARED_DOCUMENTS, 24)
        self.assertEqual(compare.SELECTED_DOCUMENTS + compare.SHARED_DOCUMENTS,
                         runvalidate.TOTAL_JSON)

    def test_the_report_states_the_exclusion_rather_than_hiding_it(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(report["shared_documents_excluded"], 24)
        self.assertIn("updated in place", report["shared_documents_note"])
        self.assertEqual(report["documents_compared"], 18)


class TestFieldClassPartition(unittest.TestCase):
    def test_the_three_classes_are_disjoint(self):
        permitted = compare.PERMITTED_CLOCK_FIELDS
        invariant = compare.INVARIANT_FIELDS | compare.INVARIANT_SUBTREES
        content = compare.CONTENT_FIELDS
        self.assertEqual(permitted & invariant, set())
        self.assertEqual(permitted & content, set())
        self.assertEqual(invariant & content, set())

    def test_the_permitted_set_is_enumerated_and_small(self):
        """Exactly the S9-4 contract, restricted to selected-run documents."""
        self.assertEqual(compare.PERMITTED_CLOCK_FIELDS, frozenset({
            "harvest_run_id", "generated_at", "discovered_at", "freshness_score",
            "last_checked_at", "started_at", "finished_at", "observed_at",
            "detected_at"}))
        # The shared documents' clock fields are deliberately absent: those
        # documents are never compared, so permitting movement in them would
        # permit it nowhere real.
        for name in ("rejected_at", "first_seen_at", "checked_at"):
            self.assertNotIn(name, compare.PERMITTED_CLOCK_FIELDS)

    def test_freshness_is_permitted_and_every_other_score_is_not(self):
        self.assertIn("freshness_score", compare.PERMITTED_CLOCK_FIELDS)
        for score in ("quality_score", "relevance_score", "audience_fit_score"):
            self.assertIn(score, compare.INVARIANT_FIELDS)

    def test_content_fields_are_derived_from_the_committed_schemas(self):
        """Not hand-typed: a list of ~190 names would drift on the first change."""
        self.assertIn("title", compare.CONTENT_FIELDS)
        self.assertIn("total_records", compare.CONTENT_FIELDS)
        self.assertIn("full_records", compare.CONTENT_FIELDS)
        self.assertNotIn("record_id", compare.CONTENT_FIELDS)
        self.assertNotIn("generated_at", compare.CONTENT_FIELDS)
        self.assertGreater(len(compare.CONTENT_FIELDS), 100)


class TestComparison(RunTreeMixin, unittest.TestCase):
    def setUp(self):
        for run_id in (RUN_A, RUN_B):
            shutil.rmtree(artifacts.run_dir(self.state_root(), run_id), True)

    def test_two_identical_runs_are_idempotent(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B, mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(report["invariant_violations"], [])
        self.assertEqual(report["content_changes"], [])
        self.assertTrue(report["idempotent"])

    @staticmethod
    def _same_run_id(documents):
        for document in documents.values():
            document["harvest_run_id"] = RUN_A

    def test_neither_run_must_be_the_pointer(self):
        """Comparison asks a different question than `validate`."""
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        pointer = artifacts.latest_run_id_path(self.state_root())
        self.assertFalse(os.path.exists(pointer),
                         "this fixture writes no pointer at all")
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(report["documents_compared"], 18)
        self.assertEqual(report["invariant_violations"], [])

    def test_validate_run_still_requires_its_pointer(self):
        """S9-4 must not weaken `runvalidate` to make comparison historical."""
        source = read_source(os.path.join(ROOT, "src", "harvest",
                                          "runvalidate.py"))
        self.assertIn("LATEST_RUN_ID names %r, not the requested run %r", source)
        self.write_run(RUN_A)
        report = runvalidate.validate_run(self.state_root(), RUN_A)
        self.assertFalse(report["valid"])
        self.assertTrue(any("LATEST_RUN_ID" in e for e in report["errors"]))

    def test_permitted_clock_movement_is_reported_and_does_not_fail(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)          # different harvest_run_id in every document
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertTrue(report["permitted_changes"])
        for row in report["permitted_changes"]:
            self.assertEqual(row["reason"], "clock_derived")
        self.assertEqual(report["invariant_violations"], [])
        self.assertTrue(report["idempotent"])

    def test_an_added_or_removed_record_is_content_not_failure(self):
        self.write_run(RUN_A, records=[a_record("r1")])
        self.write_run(RUN_B, records=[a_record("r1"), a_record("r2")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(report["invariant_violations"], [])
        self.assertTrue(report["idempotent"])
        added = [r for r in report["content_changes"] if r["kind"] == "added"]
        self.assertTrue(added)
        self.assertTrue(any("record_id=r2" in r["path"] for r in added))

    def test_a_changed_title_is_content_not_failure(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B, records=[a_record("r1", title="Rewritten"),
                                       a_record("r2")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(report["invariant_violations"], [])
        titles = [r for r in report["content_changes"]
                  if r["path"].endswith(".title")]
        self.assertTrue(titles)
        self.assertEqual(titles[0]["run_b"], "Rewritten")

    def test_a_changed_count_between_runs_is_content_not_identity(self):
        """E9-16, the INTER-run half."""
        self.write_run(RUN_A, records=[a_record("r1")])
        self.write_run(RUN_B, records=[a_record("r1"), a_record("r2")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        counts = [r for r in report["content_changes"]
                  if r["path"].endswith("metadata.total_records")]
        self.assertTrue(counts, "a changed count must be reported as content")
        self.assertEqual(report["invariant_violations"], [])

    def test_a_count_disagreeing_within_one_run_is_a_violation(self):
        """E9-16, the INTRA-run half — the opposite verdict, deliberately."""
        def wrong(documents):
            documents["cells/cases__case-studies.json"]["metadata"][
                "total_records"] = 99
        self.write_run(RUN_A)
        self.write_run(RUN_B, mutate=wrong)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertFalse(report["idempotent"])
        within = [r for r in report["invariant_violations"]
                  if r["kind"] == "within_run_count"]
        self.assertTrue(within)

    def test_an_identity_change_is_a_violation(self):
        for field, value in (("content_id", "other"),
                             ("identity_url", "https://example.test/moved"),
                             ("canonical_url", "https://example.test/moved"),
                             ("quality_score", 0.1)):
            with self.subTest(field=field):
                self.setUp()
                self.write_run(RUN_A)
                self.write_run(RUN_B,
                               records=[a_record("r1", **{field: value}),
                                        a_record("r2")],
                               mutate=self._same_run_id)
                report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
                self.assertFalse(report["idempotent"])
                hits = [r for r in report["invariant_violations"]
                        if r["path"] and r["path"].endswith("." + field)]
                self.assertTrue(hits, "%s must fail as an identity invariant" % field)
                self.assertEqual(hits[0]["reason"], "identity_invariant")

    def test_a_change_inside_the_classification_subtree_is_a_violation(self):
        self.setUp()
        self.write_run(RUN_A)
        self.write_run(RUN_B,
                       records=[a_record("r1", classification={
                           "primary": "cases", "confidence": 0.1}),
                           a_record("r2")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        hits = [r for r in report["invariant_violations"]
                if r["reason"] == "invariant_subtree"]
        self.assertTrue(hits)
        self.assertFalse(report["idempotent"])

    def test_a_new_nested_key_under_a_facet_payload_still_fails(self):
        """A subtree invariant covers keys nobody enumerated."""
        self.setUp()
        self.write_run(RUN_A)
        self.write_run(RUN_B,
                       records=[a_record("r1", case_facets={
                           "industries": ["software"], "brand_new": "x"}),
                           a_record("r2")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertTrue([r for r in report["invariant_violations"]
                         if r["reason"] == "invariant_subtree"])

    def test_an_unclassified_moving_field_fails_loudly(self):
        """The whole point of having no `--normalize`."""
        self.setUp()
        self.write_run(RUN_A, records=[a_record("r1", wobble="a")])
        self.write_run(RUN_B, records=[a_record("r1", wobble="b")],
                       mutate=self._same_run_id)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertFalse(report["idempotent"])
        hits = [r for r in report["invariant_violations"]
                if r["reason"] == "unclassified_field"]
        self.assertTrue(hits, "a field in no committed schema must not be ignored")

    def test_every_difference_lands_in_exactly_one_section(self):
        self.setUp()
        self.write_run(RUN_A, records=[a_record("r1", wobble="a")])
        self.write_run(RUN_B, records=[a_record("r1", wobble="b",
                                                title="T", content_id="moved")])
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        seen = {}
        for section in ("permitted_changes", "content_changes",
                        "invariant_violations"):
            for row in report[section]:
                key = (row["document"], row["path"], row["kind"])
                self.assertNotIn(key, seen,
                                 "%r appears in %s and %s" % (key, seen.get(key),
                                                              section))
                seen[key] = section
        self.assertTrue(seen)

    def test_comparing_a_run_with_itself_is_refused(self):
        self.write_run(RUN_A)
        with self.assertRaises(compare.CompareError):
            compare.compare_runs(self.state_root(), RUN_A, RUN_A)

    def test_a_missing_document_is_an_error_not_a_crash(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        os.remove(os.path.join(artifacts.run_dir(self.state_root(), RUN_B),
                               "coverage.json"))
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertTrue(report["errors"])
        self.assertEqual(report["documents_compared"], 17)
        self.assertFalse(report["idempotent"])


class TestDeterminism(RunTreeMixin, unittest.TestCase):
    def setUp(self):
        for run_id in (RUN_A, RUN_B):
            shutil.rmtree(artifacts.run_dir(self.state_root(), run_id), True)

    def test_record_order_cannot_change_the_report_bytes(self):
        records = [a_record("r1"), a_record("r2"), a_record("r3")]
        self.write_run(RUN_A, records=records)
        self.write_run(RUN_B, records=records, mutate=TestComparison._same_run_id)
        first = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))

        self.setUp()
        self.write_run(RUN_A, records=records)
        self.write_run(RUN_B, records=list(reversed(records)),
                       mutate=TestComparison._same_run_id)
        second = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))
        self.assertEqual(first, second,
                         "reordering records changed the report bytes")

    def test_json_key_order_cannot_change_the_report_bytes(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B, mutate=TestComparison._same_run_id)
        first = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))

        # Rewrite one document with its keys in reverse order, same content.
        path = os.path.join(artifacts.run_dir(self.state_root(), RUN_B),
                            "manifest.json")
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        reordered = {k: document[k] for k in reversed(list(document))}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(reordered, handle)
        second = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))
        self.assertEqual(first, second, "key order changed the report bytes")

    def test_the_report_is_stable_across_repeated_runs(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        one = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))
        two = artifacts.serialize(
            compare.compare_runs(self.state_root(), RUN_A, RUN_B))
        self.assertEqual(one, two)


class TestReadOnly(RunTreeMixin, unittest.TestCase):
    def setUp(self):
        for run_id in (RUN_A, RUN_B):
            shutil.rmtree(artifacts.run_dir(self.state_root(), run_id), True)

    def test_both_run_trees_are_byte_identical_after_comparison(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        before = tree_hash(self.state_root())
        compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(before, tree_hash(self.state_root()),
                         "comparison modified a run tree")

    def test_a_broken_tree_survives_being_examined(self):
        """A comparator that repairs is a writer wearing a comparator's name."""
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        path = os.path.join(artifacts.run_dir(self.state_root(), RUN_B),
                            "coverage.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        before = tree_hash(self.state_root())
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertTrue(report["errors"])
        self.assertEqual(before, tree_hash(self.state_root()))

    def test_the_pointer_is_never_created_or_moved(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        pointer = artifacts.latest_run_id_path(self.state_root())
        compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        compare.diff_publication(self.state_root(), RUN_A,
                                 os.path.join(self._root, "nope"))
        self.assertFalse(os.path.exists(pointer))

    def test_the_module_opens_nothing_for_writing(self):
        """An AST scan: no write mode reaches `open` anywhere in this module."""
        tree = ast.parse(read_source(COMPARE_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                modes = [a.value for a in node.args[1:]
                         if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in node.keywords
                          if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                for mode in modes:
                    for forbidden in ("w", "a", "+", "x"):
                        self.assertNotIn(forbidden, mode)

    def test_the_module_names_no_writer_or_network_api(self):
        source = read_source(COMPARE_PATH)
        tree = ast.parse(source)
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                called.add(node.attr)
        for forbidden in ("makedirs", "mkdir", "remove", "unlink", "rmtree",
                          "rename", "write_atomic", "write_document",
                          "publish_run", "write_latest_run_id", "socket",
                          "urlopen", "sleep", "HttpClient", "live_transport"):
            self.assertNotIn(forbidden, called,
                             "compare.py must not reach %r" % forbidden)
        self.assertNotIn("import socket", source)
        self.assertNotIn("json.dumps", source)


class TestPublicationDiff(RunTreeMixin, unittest.TestCase):
    def setUp(self):
        shutil.rmtree(artifacts.run_dir(self.state_root(), RUN_A), True)
        self.write_run(RUN_A)
        self.publication = os.path.join(self._root, "pub")
        shutil.rmtree(self.publication, True)

    def test_the_sixteen_expected_publication_paths_are_derived(self):
        names = compare.publication_document_names()
        self.assertEqual(len(names), 16)
        self.assertEqual(len([n for n in names if n.endswith("__all__harvest.json")]), 3)
        self.assertIn("publication_manifest.json", names)
        self.assertIn("cases/cases__case-studies__harvest.json", names)

    def test_an_absent_publication_root_is_a_first_class_result(self):
        report = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        self.assertEqual(report["publication_root_state"], "absent")
        self.assertEqual(report["published_documents"], [])
        self.assertEqual(len(report["only_in_run"]), 16)
        self.assertFalse(os.path.exists(self.publication),
                         "diff created the publication root it was asked about")

    def test_absent_and_present_but_empty_are_different_answers(self):
        absent = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        os.makedirs(self.publication)
        empty = compare.diff_publication(self.state_root(), RUN_A,
                                         self.publication)
        self.assertEqual(absent["publication_root_state"], "absent")
        self.assertEqual(empty["publication_root_state"], "empty")
        self.assertNotEqual(absent["publication_root_state"],
                            empty["publication_root_state"])

    def test_a_populated_publication_root_reports_differences(self):
        os.makedirs(os.path.join(self.publication, "cases"))
        with open(os.path.join(self.publication, "stray.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{}")
        report = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        self.assertEqual(report["publication_root_state"], "differs")
        self.assertIn("stray.json", report["only_in_publication"])

    def test_a_fully_populated_root_reports_no_difference(self):
        for name in compare.publication_document_names():
            path = os.path.join(self.publication, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")
        report = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        self.assertEqual(report["publication_root_state"], "identical")
        self.assertEqual(report["only_in_run"], [])
        self.assertEqual(report["only_in_publication"], [])
        self.assertEqual(len(report["present_in_both_not_compared"]), 16)

    def test_no_projection_is_fabricated(self):
        report = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        self.assertFalse(report["projection_available"])
        self.assertIn("never fabricates", report["projection_note"])

    def test_paths_are_relative_and_deterministic(self):
        os.makedirs(os.path.join(self.publication, "cases"))
        with open(os.path.join(self.publication, "cases", "z.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{}")
        report = compare.diff_publication(self.state_root(), RUN_A,
                                          self.publication)
        for name in report["published_documents"] + report["only_in_run"]:
            self.assertFalse(os.path.isabs(name), name)
            self.assertNotIn("\\", name)
        self.assertEqual(report["only_in_run"], sorted(report["only_in_run"]))


class TestCliSurface(RunTreeMixin, unittest.TestCase):
    def setUp(self):
        for run_id in (RUN_A, RUN_B):
            shutil.rmtree(artifacts.run_dir(self.state_root(), run_id), True)

    def test_both_commands_are_registered_and_operational(self):
        """The durable fact this suite owns, replacing the two spent snapshots."""
        for name in ("compare-runs", "diff"):
            self.assertIn(name, cli.COMMANDS)
            self.assertNotIn(name, cli.PLANNED_COMMANDS)
            self.assertTrue(callable(cli.COMMANDS[name]))
        self.assertIs(cli.COMMANDS["compare-runs"], cli.cmd_compare_runs)
        self.assertIs(cli.COMMANDS["diff"], cli.cmd_diff)

    def test_the_six_command_surface_still_partitions(self):
        surface = {"preflight-sources", "smoke", "validate", "compare-runs",
                   "diff", "linkcheck"}
        registered, planned = set(cli.COMMANDS), set(cli.PLANNED_COMMANDS)
        self.assertEqual(registered & planned, set())
        self.assertEqual(registered | planned, surface)

    def test_compare_runs_exits_zero_when_invariants_hold(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B, mutate=TestComparison._same_run_id)
        proc = run_cli("compare-runs", "--state-root", self.state_root(),
                       "--run-id", RUN_A, "--run-id", RUN_B)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertTrue(report["idempotent"])

    def test_compare_runs_prints_the_whole_report_then_exits_one(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B, records=[a_record("r1", content_id="moved"),
                                       a_record("r2")],
                       mutate=TestComparison._same_run_id)
        proc = run_cli("compare-runs", "--state-root", self.state_root(),
                       "--run-id", RUN_A, "--run-id", RUN_B)
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertTrue(report["invariant_violations"])
        self.assertEqual(report["documents_compared"], 18)

    def test_diff_exits_zero_with_an_absent_publication_root(self):
        self.write_run(RUN_A)
        proc = run_cli("diff", "--state-root", self.state_root(),
                       "--run-id", RUN_A,
                       "--publication-root", os.path.join(self._root, "gone"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(report["publication_root_state"], "absent")

    def test_the_default_publication_root_is_the_repository_path_and_stays_absent(self):
        self.write_run(RUN_A)
        expected = os.path.join(ROOT, "data", "harvested")
        self.assertFalse(os.path.exists(expected),
                         "data/harvested/ must be absent before this test")
        proc = run_cli("diff", "--state-root", self.state_root(),
                       "--run-id", RUN_A)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(report["publication_root_state"], "absent")
        self.assertTrue(report["publication_root"].endswith("data/harvested"))
        self.assertFalse(os.path.exists(expected),
                         "diff CREATED the repository publication path")

    def test_misuse_exits_two_before_reading_anything(self):
        refused = [
            ["compare-runs"],                                  # no --state-root
            ["compare-runs", "--state-root", os.path.join(ROOT, "state"),
             "--run-id", RUN_A, "--run-id", RUN_B],            # inside the repo
            ["compare-runs", "--state-root", "relative/path",
             "--run-id", RUN_A, "--run-id", RUN_B],
            ["compare-runs", "--state-root", tempfile.gettempdir(),
             "--run-id", RUN_A],                               # only one side
            ["compare-runs", "--state-root", tempfile.gettempdir(),
             "--run-id", RUN_A, "--run-id", RUN_B, "--run-id", RUN_A],
            ["compare-runs", "--state-root", tempfile.gettempdir(),
             "--run-id", "nope", "--run-id", RUN_B],           # bad run id
            ["compare-runs", "--state-root", tempfile.gettempdir(),
             "--normalize", "--run-id", RUN_A, "--run-id", RUN_B],
            ["diff"],
            ["diff", "--state-root", tempfile.gettempdir(), "--run-id", "nope"],
            ["diff", "--state-root", os.path.join(ROOT, "state"),
             "--run-id", RUN_A],
        ]
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            for argv in refused:
                self.assertEqual(cli.main(list(argv)), 2,
                                 "%r must be refused with exit 2" % (argv,))

    def test_the_normalize_option_does_not_exist(self):
        """E9-14: it was removed from the plan, not implemented quietly."""
        self.assertNotIn("--normalize",
                         read_source(os.path.join(ROOT, "src", "harvest",
                                                  "cli.py")))
        # Below compare.py's own docstring, which explains WHY there is none.
        self.assertNotIn("normalize", read_source(COMPARE_PATH).split('"""', 2)[2])

    def test_neither_command_ever_builds_a_live_transport(self):
        calls = []
        real = cli.live_transport
        cli.live_transport = lambda *a, **kw: (calls.append(a), real(*a, **kw))[1]
        self.addCleanup(setattr, cli, "live_transport", real)

        class Bytes:
            def __init__(self):
                self.buffer = io.BytesIO()

            def flush(self):
                pass

        self.write_run(RUN_A)
        self.write_run(RUN_B)
        captured, real_stdout = Bytes(), sys.stdout
        sys.stdout = captured
        try:
            cli.main(["compare-runs", "--state-root", self.state_root(),
                      "--run-id", RUN_A, "--run-id", RUN_B])
            cli.main(["diff", "--state-root", self.state_root(),
                      "--run-id", RUN_A,
                      "--publication-root", os.path.join(self._root, "gone")])
        finally:
            sys.stdout = real_stdout
        self.assertEqual(calls, [],
                         "an offline command constructed a live transport")

    def test_help_lists_both_commands(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"compare-runs", proc.stdout)
        self.assertIn(b"diff", proc.stdout)

    def test_reports_use_the_committed_serializer(self):
        self.write_run(RUN_A)
        self.write_run(RUN_B)
        proc = run_cli("compare-runs", "--state-root", self.state_root(),
                       "--run-id", RUN_A, "--run-id", RUN_B)
        report = compare.compare_runs(self.state_root(), RUN_A, RUN_B)
        self.assertEqual(proc.stdout, artifacts.serialize(report))


if __name__ == "__main__":
    unittest.main()
