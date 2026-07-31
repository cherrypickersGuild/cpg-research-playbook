#!/usr/bin/env python3
"""test_run_cells.py — the cell driver (S5-6).

S5-6 is the checkpoint that makes Stage 5 a stage rather than a library: the
committed Stage 4 pipeline is driven over the fixture corpus, cell by cell, and
one run's worth of artifacts lands on disk. What this suite defends:

  * THE WHOLE TREE, AND ALL OF IT VALID. Every configured cell that ran produces a
    cell artifact, a rejection log and a ledger; every topic produces a topic
    artifact; the run produces a coverage report, a manifest and a pointer. Every
    one of them is validated against its committed schema, and the file set is
    asserted EXACTLY — an extra path is as much a defect as a missing one.
  * BYTES FOLLOW CONTENT, NOT ORDER. Two runs with a pinned clock produce
    byte-identical trees, and so does a run whose cell order is shuffled. This
    extends the S4-5B shuffle proof and S5-2's artifact proof through the whole
    driver.
  * ONE CELL'S FAILURE IS ONE CELL'S FAILURE. A cell whose source fixture is gone
    is reported as `adapter_error` and still gets a complete, valid artifact; the
    other eleven cells are untouched, and the run still publishes.
  * NOTHING IS REIMPLEMENTED. The driver calls the committed pipeline and the
    committed S5-1 … S5-5 writers. Asserted statically as well as behaviourally,
    so a future edit that starts re-deriving a score or a category fails here.
  * NOTHING LIVE, NOTHING SHARED, NOTHING PRODUCTION. No socket is opened, no
    concurrency primitive is used, and every byte lands under an injected temp
    root.

The zero-result mapping is enumerated from `verify.decide`'s AST rather than typed
in, the same technique S5-3 used to pin CF-2: the day verify gains a seventh
reason, this suite fails instead of a live cell reporting the wrong reason.

Run via tests/test_taxonomy_run_cells.sh.
"""
import ast
import datetime
import hashlib
import inspect
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, run_cells, schema             # noqa: E402
from src.harvest import classify as cl, verify as vf             # noqa: E402
from src.harvest.adapters import base as adapter_base            # noqa: E402

NOW = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
STAMP = "2026-07-30T12:00:00Z"
FIXTURE_ROOT = os.path.join(ROOT, "tests", "fixtures", "harvest")

SCHEMA_FOR_DIR = {
    "cells": "cell_artifact.v1.json",
    "topics": "topic_artifact.v1.json",
    "rejections": "rejection.v1.json",
    "ledgers": "ledger.v1.json",
}

# The committed zero_result_reason enum, read from the schema rather than typed
# here, so a schema change cannot leave this suite quietly agreeing with itself.
ZERO_RESULT_ENUM = frozenset(
    v for v in schema.load_schema("run_manifest.v1.json")["properties"]["cells"]
    ["items"]["properties"]["zero_result_reason"]["enum"] if v)


# --------------------------------------------------------------------- helpers
def code_only(source_text):
    """Executable code with docstrings removed — the committed static-scan idiom.

    A boundary check must read what a module DOES, not what it says about itself.
    `run_cells.py` documents CF-1 by naming `acquire_target_fetch`, so a raw
    substring scan for that name would be permanently red on the very sentence
    that records the guarantee. Same helper as tests/harvest/test_adapters.py.
    """
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


def listing(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            out.append(os.path.relpath(os.path.join(dirpath, name), root)
                       .replace("\\", "/"))
    return sorted(out)


def tree_hash(root):
    """A hash over every relative path and every byte. Paths included on purpose:
    a tree that moved a file is not the same tree."""
    digest = hashlib.sha256()
    for rel in listing(root):
        digest.update(rel.encode("utf-8"))
        with open(os.path.join(root, rel), "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def read(root, *parts):
    with open(os.path.join(root, *parts), "rb") as handle:
        return handle.read()


def load(root, *parts):
    return json.loads(read(root, *parts).decode("utf-8"))


def schema_for(rel):
    parts = rel.split("/")
    if parts[-1] == "manifest.json":
        return "run_manifest.v1.json"
    if parts[-1] == "coverage.json":
        return "coverage_report.v1.json"
    if parts[-1] == "alias_conflicts.json":
        return "alias_conflict.v1.json"
    return SCHEMA_FOR_DIR[parts[-2]]


def expected_paths(run_id, cell_ids, topic_slugs):
    paths = ["LATEST_RUN_ID",
             "runs/%s/alias_conflicts.json" % run_id,
             "runs/%s/coverage.json" % run_id,
             "runs/%s/manifest.json" % run_id]
    for cell_id in cell_ids:
        paths.append("runs/%s/cells/%s.json" % (run_id, cell_id))
        paths.append("rejections/%s.json" % cell_id)
        paths.append("ledgers/%s.json" % cell_id)
    for topic_slug in topic_slugs:
        paths.append("runs/%s/topics/%s.json" % (run_id, topic_slug))
    return sorted(paths)


_BASELINE = {}


def baseline():
    """One full run, shared by every read-only assertion.

    A run is ~1.3s; re-running it for each of thirty assertions would make the
    suite slow enough that it stops being run, which is a worse outcome than
    sharing one immutable result.
    """
    if not _BASELINE:
        root = tempfile.mkdtemp(prefix="s5_run_cells_base_")
        _BASELINE["root"] = root
        _BASELINE["result"] = run_cells.run(root, clock=lambda: NOW)
    return _BASELINE["root"], _BASELINE["result"]


def tearDownModule():
    if _BASELINE:
        shutil.rmtree(_BASELINE["root"], ignore_errors=True)


class RunCase(unittest.TestCase):
    """A case that needs its own root and its own run."""

    def temp_root(self, prefix="s5_run_cells_"):
        root = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def temp_fixtures(self, drop=()):
        """A copy of the committed fixture corpus, minus the named source files.

        Deleting a source fixture is how an adapter failure is produced without
        editing the committed corpus, which must stay format-conformant.
        """
        base = self.temp_root("s5_run_cells_fx_")
        target = os.path.join(base, "harvest")
        shutil.copytree(FIXTURE_ROOT, target)
        for name in drop:
            os.unlink(os.path.join(target, "sources", name))
        return target


# ------------------------------------------------------------------ full run
class TestFullRun(unittest.TestCase):
    def setUp(self):
        self.root, self.result = baseline()

    def test_the_run_id_matches_the_committed_pattern(self):
        pattern = schema.load_schema("run_manifest.v1.json")["properties"][
            "harvest_run_id"]["pattern"]
        import re
        self.assertRegex(self.result.run_id, pattern)

    def test_every_configured_cell_produced_a_cell_artifact(self):
        for cell in run_cells.configured_cells():
            self.assertTrue(os.path.exists(artifacts.cell_artifact_path(
                self.root, self.result.run_id, cell["cell_id"])), cell["cell_id"])

    def test_the_tree_is_exactly_the_expected_file_set(self):
        cells = [c["cell_id"] for c in run_cells.configured_cells()]
        topics = sorted({c["topic_slug"] for c in run_cells.configured_cells()})
        self.assertEqual(listing(self.root),
                         expected_paths(self.result.run_id, cells, topics))

    def test_every_artifact_validates_against_its_committed_schema(self):
        for rel in listing(self.root):
            if rel == "LATEST_RUN_ID":
                continue
            name = schema_for(rel)
            self.assertEqual(schema.validate(load(self.root, rel), name), [],
                             "%s (%s)" % (rel, name))

    def test_one_topic_artifact_per_topic(self):
        topics = sorted({c["topic_slug"] for c in run_cells.configured_cells()})
        for topic_slug in topics:
            self.assertTrue(os.path.exists(artifacts.topic_artifact_path(
                self.root, self.result.run_id, topic_slug)), topic_slug)

    def test_a_rejection_log_and_a_ledger_per_cell(self):
        for cell in run_cells.configured_cells():
            self.assertTrue(os.path.exists(
                artifacts.rejection_log_path(self.root, cell["cell_id"])))
            self.assertTrue(os.path.exists(
                artifacts.ledger_path(self.root, cell["cell_id"])))

    def test_the_pointer_names_this_run(self):
        self.assertEqual(artifacts.read_latest_run_id(self.root),
                         self.result.run_id)

    def test_the_pointer_is_one_line_with_a_trailing_newline(self):
        raw = read(self.root, "LATEST_RUN_ID")
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(raw.count(b"\n"), 1)
        self.assertNotIn(b"\r", raw)

    def test_no_temp_debris_survives(self):
        for rel in listing(self.root):
            self.assertNotIn(artifacts.TEMP_PREFIX, rel, rel)

    def test_every_artifact_is_lf_with_one_trailing_newline(self):
        for rel in listing(self.root):
            raw = read(self.root, rel)
            self.assertNotIn(b"\r\n", raw, rel)
            self.assertTrue(raw.endswith(b"\n"), rel)
            self.assertFalse(raw.endswith(b"\n\n"), rel)

    def test_the_run_produced_records(self):
        # The corpus is what it is: if it ever stops yielding a single accepted
        # record, the rest of this suite would be asserting over an empty tree.
        self.assertGreater(self.result.record_count, 0)

    def test_a_record_lands_in_the_cell_it_was_classified_into(self):
        for rel in listing(self.root):
            if "/cells/" not in rel:
                continue
            artifact = load(self.root, rel)
            for record in artifact["records"]:
                self.assertEqual(record["cell_id"], artifact["cell_id"], rel)
                self.assertEqual(record["topic"], artifact["topic_slug"], rel)
                self.assertEqual(record["primary_category"],
                                 artifact["category_slug"], rel)

    def test_the_topic_artifact_is_the_merge_of_its_cells(self):
        for topic_slug in sorted({c["topic_slug"]
                                  for c in run_cells.configured_cells()}):
            topic = load(self.root, "runs/%s/topics/%s.json"
                         % (self.result.run_id, topic_slug))
            from_cells = []
            for cell in run_cells.configured_cells():
                if cell["topic_slug"] != topic_slug:
                    continue
                from_cells.extend(load(self.root, "runs/%s/cells/%s.json"
                                       % (self.result.run_id, cell["cell_id"]))
                                  ["records"])
            self.assertEqual(sorted(r["record_id"] for r in topic["records"]),
                             sorted({r["record_id"] for r in from_cells}))

    def test_the_topic_cell_rows_cover_every_cell_of_that_topic(self):
        for topic_slug in sorted({c["topic_slug"]
                                  for c in run_cells.configured_cells()}):
            topic = load(self.root, "runs/%s/topics/%s.json"
                         % (self.result.run_id, topic_slug))
            expected = sorted(c["cell_id"] for c in run_cells.configured_cells()
                              if c["topic_slug"] == topic_slug)
            self.assertEqual([row["cell_id"] for row in topic["metadata"]["cells"]],
                             expected)

    def test_counts_in_a_cell_artifact_are_derived_from_its_records(self):
        for rel in listing(self.root):
            if "/cells/" not in rel:
                continue
            artifact = load(self.root, rel)
            meta = artifact["metadata"]
            self.assertEqual(meta["total_records"], len(artifact["records"]), rel)
            self.assertEqual(meta["full_records"] + meta["cross_references"],
                             meta["total_records"], rel)

    def test_the_coverage_report_covers_the_runs_records(self):
        report = load(self.root, "runs/%s/coverage.json" % self.result.run_id)
        self.assertEqual(report["harvest_run_id"], self.result.run_id)
        self.assertEqual(report["generated_at"], STAMP)
        self.assertTrue(report["thresholds_constant"])

    def test_every_timestamp_comes_from_the_one_injected_instant(self):
        for rel in listing(self.root):
            if rel == "LATEST_RUN_ID":
                continue
            doc = load(self.root, rel)
            for key in ("generated_at", "updated_at", "started_at", "finished_at"):
                if key in doc:
                    self.assertEqual(doc[key], STAMP, "%s %s" % (rel, key))

    def test_the_manifest_records_this_run(self):
        manifest = load(self.root, "runs/%s/manifest.json" % self.result.run_id)
        self.assertEqual(manifest["harvest_run_id"], self.result.run_id)
        self.assertEqual(manifest["mode"], artifacts.MODE_HARVEST)

    def test_the_config_block_names_the_committed_versions(self):
        config = load(self.root, "runs/%s/manifest.json"
                      % self.result.run_id)["config"]
        self.assertEqual(config["cross_topic_policy"], "cross_reference")
        # `enrich` is no longer asserted here: S6-5 made it a derived fact about
        # whether the target-fetch phase was enabled, and this run enables it.
        # tests/harvest/test_target_evidence.py owns both directions of that.
        self.assertEqual(config["topics"],
                         sorted({c["topic_slug"]
                                 for c in run_cells.configured_cells()}))

    def test_no_preflight_is_claimed(self):
        # A preflight re-checks LIVE sources. Nothing here is live, so the honest
        # value is an empty list rather than a fabricated set of ok rows.
        manifest = load(self.root, "runs/%s/manifest.json" % self.result.run_id)
        self.assertEqual(manifest["source_preflight"], [])

    def test_rounds_are_not_claimed(self):
        manifest = load(self.root, "runs/%s/manifest.json" % self.result.run_id)
        self.assertNotIn("rounds", manifest)

    def test_the_result_reports_what_ran(self):
        self.assertEqual(self.result.ran,
                         sorted(c["cell_id"] for c in run_cells.configured_cells()))


# ------------------------------------------------------------------ statuses
class TestCellStatus(unittest.TestCase):
    def setUp(self):
        self.root, self.result = baseline()
        self.manifest = load(self.root, "runs/%s/manifest.json"
                             % self.result.run_id)

    def test_every_configured_cell_appears_exactly_once(self):
        ids = [row["cell_id"] for row in self.manifest["cells"]]
        self.assertEqual(sorted(ids), sorted(set(ids)))
        self.assertEqual(sorted(ids),
                         sorted(artifacts.configured_cell_rows()))

    def test_rows_are_sorted_by_cell_id(self):
        ids = [row["cell_id"] for row in self.manifest["cells"]]
        self.assertEqual(ids, sorted(ids))

    def test_no_cell_was_left_not_run(self):
        for row in self.manifest["cells"]:
            self.assertNotEqual(row["status"], artifacts.STATUS_NOT_RUN,
                                row["cell_id"])

    def test_a_cell_that_found_nothing_is_zero_result_with_a_committed_reason(self):
        zero = [r for r in self.manifest["cells"]
                if r["status"] == run_cells.STATUS_ZERO]
        self.assertTrue(zero, "the corpus should produce at least one zero cell")
        for row in zero:
            self.assertIn(row["zero_result_reason"], ZERO_RESULT_ENUM,
                          row["cell_id"])

    def test_a_zero_result_cell_still_has_an_artifact(self):
        for row in self.manifest["cells"]:
            if row["status"] != run_cells.STATUS_ZERO:
                continue
            artifact = load(self.root, "runs/%s/cells/%s.json"
                            % (self.result.run_id, row["cell_id"]))
            self.assertEqual(artifact["records"], [])
            self.assertEqual(artifact["metadata"]["total_records"], 0)

    def test_an_ok_cell_accepted_something(self):
        for row in self.manifest["cells"]:
            if row["status"] != run_cells.STATUS_OK:
                continue
            self.assertGreater(row["accepted"], 0, row["cell_id"])

    def test_candidates_equal_accepted_plus_rejected(self):
        for row in self.manifest["cells"]:
            if "candidates" not in row:
                continue
            self.assertEqual(row["candidates"],
                             row["accepted"] + row["rejected"], row["cell_id"])

    def test_a_zero_result_is_never_reported_as_an_error(self):
        for row in self.manifest["cells"]:
            if row["status"] == run_cells.STATUS_ZERO:
                self.assertIsNone(row.get("error_reason"), row["cell_id"])

    def test_adapters_used_comes_from_the_configured_sources(self):
        configured = {c["cell_id"]: sorted({s["adapter"] for s in c["sources"]})
                      for c in run_cells.configured_cells()}
        for row in self.manifest["cells"]:
            self.assertEqual(row["adapters_used"], configured[row["cell_id"]],
                             row["cell_id"])

    def test_the_rejection_log_explains_a_zero_result(self):
        for row in self.manifest["cells"]:
            if row["status"] != run_cells.STATUS_ZERO or not row["rejected"]:
                continue
            log = load(self.root, "rejections/%s.json" % row["cell_id"])
            self.assertEqual(len(log["rejections"]), row["rejected"],
                             row["cell_id"])

    def test_the_ledger_records_every_candidate_the_cell_saw(self):
        for row in self.manifest["cells"]:
            if "candidates" not in row:
                continue
            entries = load(self.root, "ledgers/%s.json"
                           % row["cell_id"])["entries"]
            self.assertEqual(len(entries), row["candidates"], row["cell_id"])
            for entry in entries:
                self.assertIn(entry["outcome"], ("accepted", "rejected"))
                self.assertEqual(entry["seen_count"], 1)
                self.assertEqual(entry["first_seen_at"], STAMP)

    def test_ledger_entries_are_sorted_by_identity_url(self):
        for cell in run_cells.configured_cells():
            entries = load(self.root, "ledgers/%s.json" % cell["cell_id"])["entries"]
            urls = [e["identity_url"] for e in entries]
            self.assertEqual(urls, sorted(urls), cell["cell_id"])


# ------------------------------------------------- target evidence in the ledger
class TestLedgerCarriesTargetEvidence(unittest.TestCase):
    """S6-6B: the ledger records the fetch, because that is what it is for.

    `ledger.v1.json` has carried `http_status`, `content_hash` and
    `last_checked_at` since Stage 1 and `merge_ledger` has always stored them, but
    the run's observation never supplied any of the three — so the one structure
    whose job is remembering what a previous run learned about a URL remembered
    everything except what the fetch saw, and the next run could only recover it by
    re-reading the artifacts.

    Asserted at the RUN boundary over the committed corpus, not against
    `merge_ledger` in isolation: the storage was never the missing part.
    """

    CELL = "research-and-models__benchmark-and-datasets"
    FIELDS = ("http_status", "content_hash", "last_checked_at")

    def setUp(self):
        self.root, self.result = baseline()
        self.entries = {
            entry["identity_url"]: entry
            for entry in load(self.root,
                              "ledgers/%s.json" % self.CELL)["entries"]}
        # The finished records this run actually wrote, which are the only
        # admissible source of truth for what the ledger should say.
        self.records = {
            record["record_id"]: record
            for record in load(self.root, "runs/%s/cells/%s.json"
                               % (self.result.run_id, self.CELL))["records"]
            if record["record_type"] == "full"}
        self.fetched = [record for record in self.records.values()
                        if record["access_status"] not in (None, "not_checked")]

    def test_the_run_really_did_fetch_something(self):
        """Anti-vacuity: every assertion below is empty without this."""
        self.assertGreaterEqual(len(self.fetched), 1)
        for record in self.fetched:
            with self.subTest(record["identity_url"]):
                self.assertEqual(record["verification_status"], "fetched")

    def test_a_fetched_records_ledger_row_carries_all_three_values(self):
        for record in self.fetched:
            entry = self.entries[record["identity_url"]]
            for field in self.FIELDS:
                with self.subTest(url=record["identity_url"], field=field):
                    self.assertIn(field, entry)
                    self.assertIsNotNone(entry[field])

    def test_each_value_equals_the_records_own(self):
        """Copied, never recomputed — a second derivation could disagree with the
        record sitting beside it in the same run."""
        for record in self.fetched:
            entry = self.entries[record["identity_url"]]
            for field in self.FIELDS:
                with self.subTest(url=record["identity_url"], field=field):
                    self.assertEqual(entry[field], record[field])

    def test_the_row_names_the_same_record(self):
        for record in self.fetched:
            entry = self.entries[record["identity_url"]]
            self.assertEqual(entry["record_id"], record["record_id"])
            self.assertEqual(entry["outcome"], "accepted")

    def test_the_hashes_are_the_pages_own_and_not_one_shared_value(self):
        """A join that lost the record would still pass an is-not-null check."""
        hashes = {self.entries[r["identity_url"]]["content_hash"]
                  for r in self.fetched}
        self.assertEqual(len(hashes), len(self.fetched))

    def test_last_checked_at_is_the_runs_instant_not_a_second_clock_read(self):
        for record in self.fetched:
            self.assertEqual(
                self.entries[record["identity_url"]]["last_checked_at"], STAMP)

    def test_a_rejected_entry_receives_no_fabricated_evidence(self):
        """Nothing fetched it, so the ledger must claim nothing about it — not a
        null, not a zero, not an empty string."""
        rejected = [entry for entry in self.entries.values()
                    if entry["outcome"] == "rejected"]
        self.assertGreaterEqual(len(rejected), 1)
        for entry in rejected:
            for field in self.FIELDS:
                with self.subTest(url=entry["identity_url"], field=field):
                    self.assertNotIn(field, entry)

    def test_a_cell_that_fetched_nothing_writes_no_evidence_at_all(self):
        """The eleven zero-result cells accept nothing, so nothing is fetched."""
        checked = 0
        for cell in run_cells.configured_cells():
            if cell["cell_id"] == self.CELL:
                continue
            for entry in load(self.root, "ledgers/%s.json"
                              % cell["cell_id"])["entries"]:
                checked += 1
                for field in self.FIELDS:
                    with self.subTest(cell=cell["cell_id"], field=field):
                        self.assertNotIn(field, entry)
        self.assertGreater(checked, 0, "no other cell had a ledger entry to check")

    def test_the_fields_are_a_subset_of_the_committed_observation_contract(self):
        """No ledger field is invented here: all three were already storable."""
        from src.harvest import ledger as ledger_mod
        self.assertEqual(set(run_cells.LEDGER_TARGET_EVIDENCE_FIELDS),
                         set(self.FIELDS))
        for field in self.FIELDS:
            with self.subTest(field):
                self.assertIn(field, ledger_mod.OBSERVATION_FIELDS)

    def test_the_ledger_still_validates(self):
        self.assertEqual(
            schema.validate(load(self.root, "ledgers/%s.json" % self.CELL),
                            "ledger.v1.json"), [])

    def test_the_ledger_is_reproduced_byte_for_byte_by_an_identical_run(self):
        """Determinism is what makes the values worth storing: they come from the
        record, and the record is already proved stable across runs."""
        again = tempfile.mkdtemp(prefix="s6_6b_ledger_")
        self.addCleanup(shutil.rmtree, again, ignore_errors=True)
        run_cells.run(again, clock=lambda: NOW)
        self.assertEqual(read(again, "ledgers/%s.json" % self.CELL),
                         read(self.root, "ledgers/%s.json" % self.CELL))


# -------------------------------------------------------------- determinism
class TestDeterminism(RunCase):
    def test_two_runs_with_a_pinned_clock_are_byte_identical(self):
        base_root, _ = baseline()
        again = self.temp_root("s5_run_cells_again_")
        run_cells.run(again, clock=lambda: NOW)
        self.assertEqual(tree_hash(again), tree_hash(base_root))

    def test_shuffled_cell_order_yields_an_identical_tree(self):
        base_root, _ = baseline()
        ids = [c["cell_id"] for c in run_cells.configured_cells()]
        random.Random(20260730).shuffle(ids)
        self.assertNotEqual(ids, sorted(ids), "the shuffle must actually shuffle")
        shuffled = self.temp_root("s5_run_cells_shuffled_")
        run_cells.run(shuffled, cells=ids, clock=lambda: NOW)
        self.assertEqual(tree_hash(shuffled), tree_hash(base_root))

    def test_the_record_set_is_stable_across_runs(self):
        _, result = baseline()
        again = self.temp_root("s5_run_cells_records_")
        other = run_cells.run(again, clock=lambda: NOW)
        self.assertEqual([r["record_id"] for r in other.records],
                         [r["record_id"] for r in result.records])


# ---------------------------------------------------------- failure isolation
class TestFailureIsolation(RunCase):
    def setUp(self):
        self.fixtures = self.temp_fixtures(drop=("fx_producthunt.json",))
        self.root = self.temp_root("s5_run_cells_fail_")
        self.result = run_cells.run(self.root, clock=lambda: NOW,
                                    fixtures_dir=self.fixtures)
        self.manifest = load(self.root, "runs/%s/manifest.json"
                             % self.result.run_id)
        self.broken = "cases__product-discovery"

    def rows(self):
        return {row["cell_id"]: row for row in self.manifest["cells"]}

    def test_the_broken_cell_reports_an_adapter_error(self):
        self.assertEqual(self.rows()[self.broken]["status"],
                         adapter_base.RESULT_ADAPTER_ERROR)

    def test_the_run_did_not_abort(self):
        for row in self.manifest["cells"]:
            self.assertNotEqual(row["status"], artifacts.STATUS_NOT_RUN,
                                row["cell_id"])

    def test_the_other_cells_are_intact_and_valid(self):
        for cell in run_cells.configured_cells():
            if cell["cell_id"] == self.broken:
                continue
            artifact = load(self.root, "runs/%s/cells/%s.json"
                            % (self.result.run_id, cell["cell_id"]))
            self.assertEqual(schema.validate(artifact, "cell_artifact.v1.json"), [])

    def test_the_broken_cell_still_has_a_complete_valid_artifact(self):
        artifact = load(self.root, "runs/%s/cells/%s.json"
                        % (self.result.run_id, self.broken))
        self.assertEqual(schema.validate(artifact, "cell_artifact.v1.json"), [])
        self.assertEqual(artifact["records"], [])

    def test_the_failing_source_is_recorded_with_its_result(self):
        artifact = load(self.root, "runs/%s/cells/%s.json"
                        % (self.result.run_id, self.broken))
        rows = artifact["metadata"]["sources"]
        self.assertEqual([r["source_id"] for r in rows], ["producthunt"])
        self.assertEqual(rows[0]["result"], adapter_base.RESULT_ADAPTER_ERROR)
        self.assertIn(rows[0]["reason"], adapter_base.ADAPTER_ERROR_REASONS)

    def test_an_error_reason_outside_the_manifest_enum_becomes_null(self):
        # The manifest's error_reason enum is narrower than the adapter
        # vocabulary. Reporting a value it does not admit would fail validation;
        # inventing a nearby one would be a lie. Null, and the artifact keeps the
        # real reason.
        self.assertIsNone(self.rows()[self.broken].get("error_reason"))

    def test_the_run_still_published(self):
        self.assertEqual(artifacts.read_latest_run_id(self.root),
                         self.result.run_id)

    def test_the_tree_is_still_complete(self):
        cells = [c["cell_id"] for c in run_cells.configured_cells()]
        topics = sorted({c["topic_slug"] for c in run_cells.configured_cells()})
        self.assertEqual(listing(self.root),
                         expected_paths(self.result.run_id, cells, topics))

    def test_the_working_cells_still_produced_their_records(self):
        self.assertGreater(self.result.record_count, 0)


# ------------------------------------------------------------------- offline
class TestOffline(RunCase):
    def test_no_socket_is_opened(self):
        import socket
        real = socket.socket

        def refuse(*a, **kw):
            raise AssertionError("a socket was opened during a Stage 5 run")

        socket.socket = refuse
        self.addCleanup(setattr, socket, "socket", real)
        run_cells.run(self.temp_root("s5_run_cells_offline_"), clock=lambda: NOW)

    def test_the_default_transport_is_fixture_only_and_live_is_not_owned_here(self):
        """The permanent boundary, stated without pinning an implementation site.

        This was `test_the_opener_is_the_fixture_opener` until S9-1, and it
        asserted that the literal `FixtureOpener` appeared inside the source text
        of `run_cells.run`. That was a Stage 5 *implementation location*, not a
        contract: S9-1 moved construction into the named `fixture_transport`
        factory so `run(fixtures_dir=…)` could still be honoured while the
        transport became one atomic value. The location assertion was spent, and
        it is gone rather than worked around — the production code was NOT shaped
        to keep a source scan green.

        What survives is what actually matters, and all of it is still true:
        an omitted transport is fixture-backed and offline, and the live opener
        is not this module's to name. `cli.live_transport` is the single owner of
        that decision, so a live pairing cannot appear here by accident.
        """
        transport = run_cells.fixture_transport(self.temp_root("s5_fixture_tr_"))
        self.assertIsInstance(transport.opener,
                              run_cells.fixtures_mod.FixtureOpener)
        self.assertIsNone(transport.sleep(1234), "the fixture sleep must not pace")
        self.assertNotIn("default_opener", inspect.getsource(run_cells))

    def test_nothing_is_written_outside_the_injected_root(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs",
                     "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_the_repository_config_and_fixtures_are_not_touched(self):
        watched = ("config/harvest", "tests/fixtures/harvest", "schemas/harvest")
        before = {p: os.path.getmtime(os.path.join(ROOT, p)) for p in watched}
        run_cells.run(self.temp_root("s5_run_cells_readonly_"), clock=lambda: NOW)
        after = {p: os.path.getmtime(os.path.join(ROOT, p)) for p in watched}
        self.assertEqual(before, after)

    def test_the_lease_scratch_does_not_land_in_the_artifact_root(self):
        root = self.temp_root("s5_run_cells_leases_")
        result = run_cells.run(root, clock=lambda: NOW)
        self.assertNotIn("locks", listing(root))
        for rel in listing(root):
            self.assertFalse(rel.startswith("leases/"), rel)
        self.assertTrue(result.run_id)


# -------------------------------------------------------------------- bounds
class TestBounds(RunCase):
    def test_a_subset_run_runs_only_that_subset(self):
        root = self.temp_root("s5_run_cells_subset_")
        result = run_cells.run(root, cells=["cases__case-studies"],
                               clock=lambda: NOW)
        self.assertEqual(result.ran, ["cases__case-studies"])
        self.assertEqual(listing(root),
                         expected_paths(result.run_id, ["cases__case-studies"],
                                        ["cases"]))

    def test_the_unrun_cells_are_recorded_as_not_run(self):
        root = self.temp_root("s5_run_cells_notrun_")
        result = run_cells.run(root, cells=["cases__case-studies"],
                               clock=lambda: NOW)
        rows = {r["cell_id"]: r for r in result.manifest["cells"]}
        self.assertEqual(len(rows), len(artifacts.configured_cell_rows()))
        for cell_id, row in rows.items():
            if cell_id == "cases__case-studies":
                continue
            self.assertEqual(row["status"], artifacts.STATUS_NOT_RUN, cell_id)

    def test_max_cells_caps_the_run_without_hiding_a_cell(self):
        root = self.temp_root("s5_run_cells_cap_")
        result = run_cells.run(root, clock=lambda: NOW, max_cells=2)
        self.assertEqual(len(result.ran), 2)
        self.assertEqual(len(result.manifest["cells"]),
                         len(artifacts.configured_cell_rows()))
        not_run = [r for r in result.manifest["cells"]
                   if r["status"] == artifacts.STATUS_NOT_RUN]
        self.assertEqual(len(not_run),
                         len(artifacts.configured_cell_rows()) - 2)

    def test_the_cap_takes_cells_in_committed_order(self):
        root = self.temp_root("s5_run_cells_caporder_")
        result = run_cells.run(root, clock=lambda: NOW, max_cells=3)
        self.assertEqual(result.ran,
                         [c["cell_id"] for c in run_cells.configured_cells()][:3])

    def test_an_unknown_cell_is_refused(self):
        with self.assertRaises(run_cells.RunCellsError):
            run_cells.run(self.temp_root("s5_run_cells_unknown_"),
                          cells=["cases__does-not-exist"], clock=lambda: NOW)

    def test_the_default_cap_is_the_configured_cell_count(self):
        self.assertEqual(run_cells.MAX_CELLS, len(run_cells.configured_cells()))

    def test_the_cell_list_agrees_with_the_scheduler(self):
        from src.harvest import scheduler
        self.assertEqual(
            sorted(c["cell_id"] for c in run_cells.configured_cells()),
            sorted(lane[len("cell__"):] for lane in scheduler.configured_cells()))


# ---------------------------------------------------------------- cross-topic
def classification(topic="cases", category="case-studies", competing=()):
    return cl.Classification(
        candidate_key="k", topic_slug=topic, category_slug=category,
        rule_id="R1_org_implementation_with_results", rationale="because",
        competing_categories=tuple(
            cl.CompetingCategory(topic=t, category=c, rule_id="R2_industry_pattern")
            for t, c in competing),
        contexts=((topic, category),))


class FakeCandidate:
    """The two fields a pointer needs. Ids come from urlkey, never invented."""
    from src.harvest import urlkey as _urlkey
    identity_url = "https://example.com/item/"
    content_id = _urlkey.content_id("https://example.com/item/")


class TestCrossTopicPointers(unittest.TestCase):
    """The committed policy is applied, never invented.

    precedence.v1.json states it: the owning topic emits the full record, every
    other qualifying topic emits a cross_reference pointing at it. The owner and
    the qualifying cells are both chosen by the committed classifier.
    """

    def rows(self, cls):
        return run_cells._cross_reference_rows(
            FakeCandidate(), cls, harvest_run_id="20260730T120000Z-1",
            discovered_at=STAMP,
            configured={c["cell_id"] for c in run_cells.configured_cells()})

    def test_no_competition_yields_no_pointer(self):
        self.assertEqual(self.rows(classification()), [])

    def test_a_competing_cell_in_another_topic_yields_a_pointer(self):
        rows = self.rows(classification(
            competing=[("discourse", "insights-and-opinions")]))
        self.assertEqual([cell_id for cell_id, _ in rows],
                         ["discourse__insights-and-opinions"])

    def test_the_pointer_points_at_the_owner_record(self):
        _, row = self.rows(classification(
            competing=[("discourse", "insights-and-opinions")]))[0]
        from src.harvest import urlkey
        self.assertEqual(row["record_type"], "cross_reference")
        self.assertEqual(row["owner_topic"], "cases")
        self.assertEqual(row["duplicate_of"],
                         urlkey.record_id("cases", FakeCandidate.identity_url))
        self.assertEqual(row["record_id"],
                         urlkey.record_id("discourse", FakeCandidate.identity_url))

    def test_a_pointer_validates_as_a_record(self):
        _, row = self.rows(classification(
            competing=[("discourse", "insights-and-opinions")]))[0]
        self.assertEqual(schema.validate(row, "record.v1.json"), [])

    def test_a_competing_cell_in_the_same_topic_yields_nothing(self):
        # Duplicate suppression WITHIN a topic is mandatory and not configurable,
        # so a pointer beside its own full record would be the very duplicate the
        # rule forbids.
        self.assertEqual(self.rows(classification(
            competing=[("cases", "domain-applications")])), [])

    def test_pointers_are_sorted_by_cell_id(self):
        rows = self.rows(classification(competing=[
            ("research-and-models", "papers"),
            ("discourse", "insights-and-opinions")]))
        self.assertEqual([cell_id for cell_id, _ in rows],
                         sorted(cell_id for cell_id, _ in rows))

    def test_an_unconfigured_competing_cell_is_refused(self):
        with self.assertRaises(run_cells.RunCellsError):
            self.rows(classification(competing=[("nowhere", "at-all")]))

    def test_the_corpus_needs_no_pointer(self):
        # Recorded rather than assumed: the committed fixture corpus produces no
        # cross-topic competition, so the driver's pointer path is exercised by
        # the unit tests above and by nothing in the baseline run.
        _, result = baseline()
        self.assertEqual(result.manifest["classification_decisions"], [])
        self.assertTrue(all(r["record_type"] == "full" for r in result.records))


# ------------------------------------------------------- zero-result mapping
def verify_rejection_reasons():
    """Every reason `verify.decide` can emit, read from its AST.

    Typed into the test they would agree with themselves forever; read from the
    module, a seventh reason fails this suite instead of a live cell reporting
    the wrong zero_result_reason. Same technique S5-3 used to pin CF-2.
    """
    tree = ast.parse(inspect.getsource(vf.decide))
    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "verdict"):
            continue
        for arg in node.args[1:2]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.add(arg.value)
            elif isinstance(arg, ast.IfExp):
                for branch in (arg.body, arg.orelse):
                    if isinstance(branch, ast.Constant):
                        found.add(branch.value)
    return found


class TestZeroResultMapping(unittest.TestCase):
    def test_verify_emits_exactly_the_reasons_we_map(self):
        self.assertEqual(verify_rejection_reasons(),
                         set(run_cells.ZERO_RESULT_FOR_REJECTION))

    def test_every_mapped_value_is_in_the_committed_enum(self):
        for value in run_cells.ZERO_RESULT_FOR_REJECTION.values():
            self.assertIn(value, ZERO_RESULT_ENUM, value)

    def test_the_precedence_list_covers_the_committed_enum(self):
        self.assertEqual(set(run_cells.ZERO_RESULT_PRECEDENCE), ZERO_RESULT_ENUM)

    def test_an_empty_cell_is_no_items_in_window(self):
        run = run_cells.CellRun({"cell_id": "cases__case-studies"})
        self.assertEqual(run_cells._zero_result_reason(run), "no_items_in_window")

    def test_the_dominant_reason_wins(self):
        run = self.fake([("off_topic", 3), ("below_quality_threshold", 1)])
        self.assertEqual(run_cells._zero_result_reason(run),
                         "all_below_relevance_threshold")

    def test_a_tie_breaks_by_committed_precedence(self):
        run = self.fake([("off_topic", 2), ("below_quality_threshold", 2)])
        order = run_cells.ZERO_RESULT_PRECEDENCE
        self.assertEqual(run_cells._zero_result_reason(run),
                         min(("all_below_relevance_threshold",
                              "all_rejected_quality"), key=order.index))

    def test_an_unmapped_reason_is_refused_rather_than_guessed(self):
        run = self.fake([("seo_spam", 1)])
        with self.assertRaises(run_cells.RunCellsError):
            run_cells._zero_result_reason(run)

    def test_a_dev_tool_sweep_reports_category_exclusion(self):
        run = self.fake([("developer_only_audience", 4)])
        self.assertEqual(run_cells._zero_result_reason(run),
                         "category_exclusion_applied")

    @staticmethod
    def fake(pairs):
        run = run_cells.CellRun({"cell_id": "cases__case-studies"})
        candidates, verdicts = [], {}
        index = 0
        for reason, count in pairs:
            for _ in range(count):
                key = "k%d" % index
                index += 1
                candidates.append(type("C", (), {"candidate_key": key})())
                verdicts[key] = vf.Verdict(candidate_key=key, accepted=False,
                                           scores=vf.Scores(),
                                           rejection_reason=reason)
        run.extracted = tuple(candidates)
        run.verdicts = verdicts
        return run


# --------------------------------------------------------------- record dedupe
class TestRecordDedupe(unittest.TestCase):
    """Two cells can discover the same URL. The survivor must be content-chosen."""

    @staticmethod
    def record(record_id, title):
        return {"record_type": "full", "record_id": record_id, "topic": "cases",
                "primary_category": "case-studies", "title": title}

    def test_a_duplicate_record_id_survives_once(self):
        rows = [self.record("r1", "b"), self.record("r1", "a")]
        self.assertEqual(len(run_cells._dedupe_records(rows)), 1)

    def test_the_survivor_does_not_depend_on_input_order(self):
        a, b = self.record("r1", "b"), self.record("r1", "a")
        self.assertEqual(run_cells._dedupe_records([a, b]),
                         run_cells._dedupe_records([b, a]))

    def test_sort_key_alone_cannot_break_the_tie(self):
        # The reason the serialized bytes enter the sort at all: two records of
        # one identity have the same (topic, primary_category, record_id).
        from src.harvest import records as records_mod
        a, b = self.record("r1", "b"), self.record("r1", "a")
        self.assertEqual(records_mod.sort_key(a), records_mod.sort_key(b))

    def test_distinct_records_all_survive_sorted(self):
        rows = [self.record("r2", "x"), self.record("r1", "y")]
        out = run_cells._dedupe_records(rows)
        self.assertEqual([r["record_id"] for r in out], ["r1", "r2"])


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def source(self):
        # Docstrings stripped: this scans what the module does, not what it says.
        return code_only(inspect.getsource(run_cells))

    def test_it_introduces_no_concurrency(self):
        # CF-1 stays untriggered only while cells run sequentially (plan §9.1).
        for token in ("threading", "multiprocessing", "asyncio", "ThreadPool",
                      "ProcessPool", "concurrent.futures", "async def", "await ",
                      "Lock(", "Semaphore("):
            self.assertNotIn(token, self.source(), token)

    def test_it_does_not_reimplement_schema_validation(self):
        self.assertNotIn("jsonschema", self.source())

    def test_it_writes_only_through_the_committed_writers(self):
        # No open(..., "w"), no os.replace, no direct serialization: every byte
        # goes through S5-1's writer via the S5-2 … S5-5 helpers.
        for token in ("os.replace", "\"wb\"", "'wb'", "\"w\"", "'w'"):
            self.assertNotIn(token, self.source(), token)

    def test_it_calls_the_committed_pipeline_rather_than_reimplementing_it(self):
        src = self.source()
        for call in ("adapters.discover(", "dedupe_mod.group(",
                     "extract_mod.normalize_all(", "classify_mod.classify_all(",
                     "verify_mod.verify_all(", "facetassign_mod.assign_all(",
                     "records_mod.make_full_record(",
                     "records_mod.make_cross_reference("):
            self.assertIn(call, src, call)

    def test_it_calls_the_committed_artifact_writers(self):
        src = self.source()
        for call in ("artifacts.write_cell_artifact(",
                     "artifacts.write_topic_artifact(",
                     "artifacts.write_coverage_report(",
                     "ledger_mod.write_rejection_log(",
                     "ledger_mod.write_ledger(", "artifacts.publish_run("):
            self.assertIn(call, src, call)

    def test_it_does_not_rescore_or_reclassify(self):
        # Stage 5 adds no judgement: no threshold literal, no scoring weight, no
        # second copy of the reporting-state machine.
        src = self.source()
        for token in ("min_relevance =", "accept_composite =", "0.35", "0.68",
                      "reporting_state(", "count_states("):
            self.assertNotIn(token, src, token)

    def test_the_pointer_is_published_last(self):
        src = inspect.getsource(run_cells.run)
        self.assertLess(src.index("artifacts.write_coverage_report("),
                        src.index("artifacts.publish_run("))
        self.assertEqual(src.count("artifacts.publish_run("), 1)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("run", "RunResult", "RunCellsError", "MAX_CELLS",
                     "configured_cells"):
            self.assertTrue(hasattr(run_cells, name), name)

    def test_the_entry_point_stays_omission_compatible(self):
        """The committed interface is a PREFIX, not a closed list.

        This was `test_the_entry_point_has_the_planned_signature` until S9-1, and
        it pinned the parameter list to exactly the five Stage 5 names. That made
        the interface unable to evolve at all, which is a stronger claim than the
        contract needs: what every committed caller actually depends on is that
        the five keep their order and their defaults, so a call written at Stage 5
        still means what it meant. S9-1 added four keyword-only seams behind them,
        each defaulting to `None` and each reproducing the committed behaviour on
        omission — the D6-A / S6-6A sentinel idiom.

        So this now guards **omission compatibility** rather than immutability,
        and it still fails loudly on the two mistakes that would matter: a
        reordered or re-defaulted prefix, and a seam that stops defaulting to
        omission.
        """
        params = inspect.signature(run_cells.run).parameters
        names = list(params)

        committed = ["root", "cells", "clock", "fixtures_dir", "max_cells"]
        self.assertEqual(names[:len(committed)], committed,
                         "the Stage 5 parameters must keep their order")
        self.assertIsNone(params["cells"].default)
        self.assertIsNone(params["clock"].default)
        self.assertIsNone(params["fixtures_dir"].default)
        self.assertEqual(params["max_cells"].default, run_cells.MAX_CELLS)

        # The S9-1 seams. Keyword-only and `None`-defaulted is what makes every
        # committed call site byte-identically unaffected.
        for seam in ("transport", "mode", "enrich", "source_preflight"):
            self.assertIn(seam, params)
            self.assertEqual(params[seam].kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIsNone(params[seam].default)

        # E9-3: `bounds` belongs to S9-3 and arrives WITH its enforcement. A
        # parameter accepted and ignored would let a manifest report a cap that
        # never bound anything.
        self.assertNotIn("bounds", params)

        # The transport is one atomic value. Separate parameters could be set
        # half-way — a live opener inheriting the fixture's suppressed pacing,
        # against hosts that mandate a crawl-delay.
        for split in ("opener", "sleep", "lease_root"):
            self.assertNotIn(split, params)

    def test_the_stage_4_modules_are_byte_unchanged(self):
        # S5-6 composes Stage 4; if it had to edit it, it was not composition.
        # STAGE 4 ONLY. `artifacts.py` and `ledger.py` are Stage 5's own modules
        # and the plan (§8) says outright that `artifacts.py` accretes across
        # S5-2, S5-3, S5-4, S5-5 and S5-7 — asserting they never move would be
        # asserting something the plan states is false, and would make this a
        # guard on the working tree rather than on the composition boundary.
        import subprocess
        # `records.py` was removed from this list at S6-5: decision D6-A authorizes
        # exactly one additive `url_aliases=None` parameter there, so asserting it
        # never moves would assert something the plan states is false — the same
        # correction S5-7 made when this list wrongly included artifacts.py.
        for path in ("src/harvest/pool.py",
                     "src/harvest/coverage.py", "src/harvest/facets.py",
                     "src/harvest/verify.py", "src/harvest/classify.py",
                     "src/harvest/extract.py", "src/harvest/dedupe.py",
                     "src/harvest/facetassign.py"):
            rc = subprocess.call(["git", "diff", "--exit-code", "--quiet",
                                  "HEAD", "--", path], cwd=ROOT)
            self.assertEqual(rc, 0, path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
