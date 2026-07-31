#!/usr/bin/env python3
"""test_manifest.py — the run manifest and LATEST_RUN_ID (S5-5).

The pointer makes exactly one promise: **it names a run whose manifest exists and
validates**. Everything here defends that promise.

  * THE POINTER MOVES LAST, OR NOT AT ALL. The manifest is persisted first. If
    that write fails for any reason, the pointer is never touched and the previous
    complete run stays the newest one. Asserted by actually breaking the write.
  * AN UNFINISHED RUN IS NEVER PUBLISHED. `finished_at: null` is refused, so the
    pointer cannot name a run that died mid-flight.
  * A FINISHED RUN IS NEVER OVERWRITTEN. Re-publishing a `run_id` that already has
    a manifest is refused — history is not silently rewritten.
  * TWELVE CONFIGURED CELLS, TWELVE ROWS. A cell that was never reached is
    `not_run`; one that ran and found nothing is `zero_result` with a committed
    reason. Neither is omitted, so a silently skipped cell cannot hide.
  * ELIGIBILITY IS DERIVED, NOT ASSERTED. Stage 5 fetches no target page, so every
    record is unverified and the run is honestly ineligible for publication, with
    the reason recorded.

S5-1's atomicity internals are reused, not re-proved. Offline and temp-rooted; no
network, no cell execution. Run via tests/test_taxonomy_manifest.sh.
"""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, scheduler, schema, verify as vf  # noqa: E402

RUN = "20260730T120000Z-4242"
OLDER = "20260729T090000Z-1111"
STARTED = "2026-07-30T12:00:00Z"
FINISHED = "2026-07-30T12:05:00Z"


def manifest(**over):
    kwargs = dict(harvest_run_id=RUN, started_at=STARTED, finished_at=FINISHED)
    kwargs.update(over)
    return artifacts.build_run_manifest(**kwargs)


def configured_cell_ids():
    return sorted(artifacts.configured_cell_rows())


class TempRootCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_manifest_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def break_write(self, exc=OSError("simulated write failure")):
        real = os.replace

        def boom(src, dst):
            raise exc

        os.replace = boom
        self.addCleanup(setattr, os, "replace", real)


# ------------------------------------------------------------------ document
class TestManifestDocument(unittest.TestCase):
    def test_it_validates(self):
        self.assertEqual(schema.validate(manifest(), "run_manifest.v1.json"), [])

    def test_every_required_key_is_present(self):
        doc = manifest()
        for key in schema.load_schema("run_manifest.v1.json")["required"]:
            self.assertIn(key, doc, key)

    def test_the_mode_is_harvest_for_stage_5(self):
        self.assertEqual(manifest()["mode"], artifacts.MODE_HARVEST)

    def test_the_other_five_modes_stay_unused(self):
        allowed = set(schema.load_schema("run_manifest.v1.json")
                      ["properties"]["mode"]["enum"])
        self.assertIn(artifacts.MODE_HARVEST, allowed)
        self.assertEqual(len(allowed), 6)

    def test_the_run_id_matches_the_committed_pattern(self):
        doc = manifest(harvest_run_id=artifacts.run_id(pid=7))
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_an_invented_top_level_field_is_refused(self):
        doc = manifest()
        doc["extra_field"] = "nope"
        self.assertNotEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_the_environment_is_the_one_this_run_used(self):
        env = manifest()["environment"]
        info = schema.check_environment()
        self.assertEqual(env["python_version"], info["python_version"])
        self.assertEqual(env["jsonschema_version"], info["jsonschema_version"])
        self.assertEqual(env["platform"], info["platform"])

    def test_rounds_are_omitted_rather_than_claimed_empty(self):
        self.assertNotIn("rounds", manifest())

    def test_coverage_and_accounting_are_omitted_when_absent(self):
        doc = manifest()
        self.assertNotIn("coverage", doc)
        self.assertNotIn("request_accounting", doc)


# --------------------------------------------------------------------- cells
class TestCells(unittest.TestCase):
    def test_every_configured_cell_appears_exactly_once(self):
        rows = manifest()["cells"]
        ids = [r["cell_id"] for r in rows]
        self.assertEqual(sorted(ids), configured_cell_ids())
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), len(scheduler.configured_cells()))

    def test_an_unreached_cell_is_not_run_never_omitted(self):
        for row in manifest()["cells"]:
            self.assertEqual(row["status"], artifacts.STATUS_NOT_RUN)

    def test_a_cell_that_found_nothing_is_zero_result_with_a_reason(self):
        target = configured_cell_ids()[0]
        doc = manifest(cells=[{"cell_id": target, "status": "zero_result",
                               "zero_result_reason": "no_items_in_window",
                               "candidates": 0, "accepted": 0}])
        row = next(r for r in doc["cells"] if r["cell_id"] == target)
        self.assertEqual(row["status"], "zero_result")
        self.assertEqual(row["zero_result_reason"], "no_items_in_window")
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_an_uncommitted_zero_result_reason_is_refused_by_the_schema(self):
        doc = manifest(cells=[{"cell_id": configured_cell_ids()[0],
                               "status": "zero_result",
                               "zero_result_reason": "we_gave_up"}])
        self.assertNotEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_an_uncommitted_error_reason_is_refused_by_the_schema(self):
        doc = manifest(cells=[{"cell_id": configured_cell_ids()[0],
                               "status": "adapter_error",
                               "error_reason": "gremlins"}])
        self.assertNotEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_a_committed_error_reason_validates(self):
        doc = manifest(cells=[{"cell_id": configured_cell_ids()[0],
                               "status": "adapter_error",
                               "error_reason": "feed_parse_error"}])
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_rows_are_sorted_by_cell_id(self):
        ids = [r["cell_id"] for r in manifest()["cells"]]
        self.assertEqual(ids, sorted(ids))

    def test_the_topic_and_category_come_from_the_configuration(self):
        # A caller cannot relabel a cell by passing a different topic.
        target = configured_cell_ids()[0]
        doc = manifest(cells=[{"cell_id": target, "status": "ok",
                               "topic_slug": "wrong", "category_slug": "wrong"}])
        row = next(r for r in doc["cells"] if r["cell_id"] == target)
        expected = artifacts.configured_cell_rows()[target]
        self.assertEqual(row["topic_slug"], expected["topic_slug"])
        self.assertEqual(row["category_slug"], expected["category_slug"])

    def test_an_unconfigured_cell_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError) as caught:
            manifest(cells=[{"cell_id": "invented__cell", "status": "ok"}])
        self.assertIn("invented__cell", str(caught.exception))

    def test_cell_order_in_the_input_does_not_change_the_bytes(self):
        outcomes = [{"cell_id": cid, "status": "zero_result",
                     "zero_result_reason": "no_items_in_window"}
                    for cid in configured_cell_ids()]
        expected = artifacts.serialize(manifest(cells=outcomes))
        rng = random.Random(20260730)
        for _ in range(5):
            shuffled = list(outcomes)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(manifest(cells=shuffled)), expected)


# -------------------------------------------------------------- eligibility
class TestPublicationEligibility(unittest.TestCase):
    def test_a_stage_5_run_is_honestly_ineligible(self):
        doc = manifest()
        self.assertFalse(doc["publication_eligible"])
        self.assertIn("unverified", doc["publication_ineligible_reason"])

    def test_the_reason_names_the_missing_fetch(self):
        self.assertIn("Stage 6", manifest()["publication_ineligible_reason"])

    def test_a_verified_run_with_healthy_cells_is_eligible(self):
        # Proves the derivation is live rather than hard-coded to False.
        doc = manifest(target_fetch_owners=5,
                       cells=[{"cell_id": cid, "status": "ok"}
                              for cid in configured_cell_ids()])
        self.assertTrue(doc["publication_eligible"])
        self.assertIsNone(doc["publication_ineligible_reason"])

    def test_a_failed_cell_makes_a_verified_run_ineligible(self):
        target = configured_cell_ids()[0]
        doc = manifest(target_fetch_owners=5,
                       cells=[{"cell_id": target, "status": "infrastructure_error",
                               "error_reason": "http_timeout"}])
        self.assertFalse(doc["publication_eligible"])
        self.assertIn(target, doc["publication_ineligible_reason"])

    def test_a_non_harvest_mode_is_ineligible(self):
        doc = manifest(mode="smoke", target_fetch_owners=5)
        self.assertFalse(doc["publication_eligible"])
        self.assertIn("smoke", doc["publication_ineligible_reason"])

    def test_eligibility_cannot_be_asserted_by_the_caller(self):
        # publication_eligible is not a parameter; it is computed.
        import inspect
        params = inspect.signature(artifacts.build_run_manifest).parameters
        self.assertNotIn("publication_eligible", params)
        self.assertNotIn("publication_ineligible_reason", params)


# -------------------------------------------------- thresholds, recorded only
class TestThresholds(unittest.TestCase):
    def test_they_come_from_committed_policy(self):
        got = artifacts.policy_thresholds()
        limits = vf.load_policy()["scoring"]["thresholds"]
        for key in ("min_relevance", "min_quality", "accept_composite"):
            self.assertEqual(got[key], limits[key])

    def test_a_round_records_them_and_validates(self):
        doc = manifest(rounds=[{"round": 1, "lanes": scheduler.configured_cells(),
                                "stop_reason": "all_targets_met",
                                "thresholds": artifacts.policy_thresholds()}])
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])
        self.assertEqual(doc["rounds"][0]["thresholds"],
                         artifacts.policy_thresholds())

    def test_nothing_here_recalibrates_a_threshold(self):
        import inspect
        src = inspect.getsource(artifacts.policy_thresholds)
        for literal in ("0.35", "0.3", "0.4", "0.68", "0.32"):
            self.assertNotIn(literal, src)


# ------------------------------------------------------- pointer publication
class TestPublishRun(TempRootCase):
    def test_publishing_writes_the_manifest_and_advances_the_pointer(self):
        path = artifacts.publish_run(self.root, RUN, manifest())
        self.assertTrue(os.path.exists(path))
        self.assertEqual(artifacts.read_latest_run_id(self.root), RUN)

    def test_the_manifest_lands_at_the_committed_path(self):
        artifacts.publish_run(self.root, RUN, manifest())
        self.assertTrue(os.path.exists(
            os.path.join(self.root, "runs", RUN, "manifest.json")))

    def test_the_pointer_is_a_single_line_with_a_trailing_newline(self):
        artifacts.publish_run(self.root, RUN, manifest())
        with open(artifacts.latest_run_id_path(self.root), "rb") as fh:
            raw = fh.read()
        self.assertEqual(raw, (RUN + "\n").encode("utf-8"))
        self.assertEqual(raw.count(b"\n"), 1)
        self.assertNotIn(b"\r\n", raw)

    def test_no_pointer_exists_before_any_run_finishes(self):
        self.assertIsNone(artifacts.read_latest_run_id(self.root))

    def test_the_published_manifest_reparses_and_validates(self):
        doc = manifest()
        path = artifacts.publish_run(self.root, RUN, doc)
        with open(path, "rb") as fh:
            written = json.loads(fh.read().decode("utf-8"))
        self.assertEqual(written, doc)
        self.assertEqual(schema.validate(written, "run_manifest.v1.json"), [])

    def test_the_pointer_names_a_run_whose_manifest_exists(self):
        artifacts.publish_run(self.root, RUN, manifest())
        named = artifacts.read_latest_run_id(self.root)
        self.assertTrue(os.path.exists(artifacts.run_manifest_path(self.root, named)))

    def test_an_unfinished_run_is_never_published(self):
        with self.assertRaises(artifacts.ArtifactError) as caught:
            artifacts.publish_run(self.root, RUN, manifest(finished_at=None))
        self.assertIn("did not finish", str(caught.exception))
        self.assertIsNone(artifacts.read_latest_run_id(self.root))
        self.assertFalse(os.path.exists(artifacts.run_manifest_path(self.root, RUN)))

    def test_a_mismatched_run_id_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.publish_run(self.root, OLDER, manifest())
        self.assertIsNone(artifacts.read_latest_run_id(self.root))

    def test_republishing_a_finished_run_is_refused(self):
        artifacts.publish_run(self.root, RUN, manifest())
        with self.assertRaises(artifacts.ArtifactError) as caught:
            artifacts.publish_run(self.root, RUN, manifest())
        self.assertIn("already has a manifest", str(caught.exception))

    def test_an_empty_pointer_write_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_latest_run_id(self.root, "")


# ------------------------------------------------- failure preserves the pointer
class TestFailurePreservesThePointer(TempRootCase):
    def publish_older(self):
        artifacts.publish_run(self.root, OLDER,
                              manifest(harvest_run_id=OLDER))
        self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)

    def test_an_invalid_manifest_leaves_the_previous_pointer(self):
        self.publish_older()
        bad = manifest()
        bad["extra_field"] = "nope"
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.publish_run(self.root, RUN, bad)
        self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)
        self.assertFalse(os.path.exists(artifacts.run_manifest_path(self.root, RUN)))

    def test_a_failed_manifest_write_leaves_the_previous_pointer(self):
        self.publish_older()
        self.break_write()
        with self.assertRaises(OSError):
            artifacts.publish_run(self.root, RUN, manifest())
        self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)

    def test_an_unfinished_run_leaves_the_previous_pointer(self):
        self.publish_older()
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.publish_run(self.root, RUN, manifest(finished_at=None))
        self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)

    def test_an_interruption_leaves_the_previous_pointer(self):
        self.publish_older()
        self.break_write(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            artifacts.publish_run(self.root, RUN, manifest())
        self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)

    def test_a_failed_publication_leaves_no_temp_debris(self):
        self.publish_older()
        self.break_write()
        with self.assertRaises(OSError):
            artifacts.publish_run(self.root, RUN, manifest())
        import glob
        for directory in (self.root, os.path.join(self.root, "runs", RUN)):
            if os.path.isdir(directory):
                self.assertEqual(
                    glob.glob(os.path.join(directory, artifacts.TEMP_PREFIX + "*")), [])

    def test_the_pointer_only_advances_on_success(self):
        self.publish_older()
        for attempt in (lambda: artifacts.publish_run(self.root, RUN,
                                                     manifest(finished_at=None)),
                        lambda: artifacts.publish_run(self.root, OLDER, manifest())):
            with self.assertRaises(artifacts.ArtifactError):
                attempt()
            self.assertEqual(artifacts.read_latest_run_id(self.root), OLDER)
        artifacts.publish_run(self.root, RUN, manifest())
        self.assertEqual(artifacts.read_latest_run_id(self.root), RUN)


# ---------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def test_repeated_construction_is_byte_identical(self):
        self.assertEqual(artifacts.serialize(manifest()),
                         artifacts.serialize(manifest()))

    def test_preflight_rows_are_sorted(self):
        rows = [{"source_id": s, "result": "ok"} for s in ("zeta", "alpha", "mid")]
        doc = manifest(source_preflight=rows)
        ids = [r["source_id"] for r in doc["source_preflight"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_classification_decisions_are_sorted(self):
        rows = [{"content_id": c, "topics": ["cases"], "owner_topic": "cases",
                 "policy_applied": "cross_reference", "reason": "r"}
                for c in ("c3", "c1", "c2")]
        doc = manifest(classification_decisions=rows)
        ids = [r["content_id"] for r in doc["classification_decisions"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_it_uses_the_shared_writer(self):
        import inspect
        src = inspect.getsource(artifacts.publish_run)
        self.assertIn("write_run_manifest", src)
        self.assertIn("write_latest_run_id", src)

    def test_the_pointer_is_written_after_the_manifest(self):
        # Order is the whole contract, so it is asserted on the source too.
        import inspect
        src = inspect.getsource(artifacts.publish_run)
        self.assertLess(src.index("write_run_manifest("),
                        src.index("write_latest_run_id("))

    def test_it_does_not_execute_cells(self):
        import inspect
        src = inspect.getsource(artifacts)
        for later in ("discover(", "FixtureOpener", "HttpClient", "run_cells"):
            self.assertNotIn(later, src)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("build_run_manifest", "write_run_manifest", "run_manifest_path",
                     "read_latest_run_id", "write_latest_run_id",
                     "latest_run_id_path", "publish_run"):
            self.assertTrue(hasattr(artifacts, name), name)


class TestSightingCounterSchema(unittest.TestCase):
    """S9-5C2 - the four sighting counters are ONE schema-level tuple.

    The producer decides whether a completed cell is measured; the SCHEMA decides
    that a measurement is never partial. That split matters because the schema
    cannot tell a newly completed row from a pre-C2 completed row - both are just
    rows - so mandatory presence on new work stays a producer contract, owned by
    `run_cells._cell_row` and its suite, while all-or-none is enforced here in
    every mode and at write time (`artifacts.write_document` validates first).

    `dependentRequired` is the exact tool: it fires only when a key is PRESENT, so
    every pre-C2 manifest and every `not_run` row stays valid untouched. That is
    what makes C2 need no migration, no backfill and no schema-version bump.
    """

    FIELDS = ("candidate_observations", "unique_candidate_keys",
              "repeated_candidate_observations",
              "uncanonicalizable_candidate_observations")

    def row(self, **over):
        """One measured cell row, complete unless a test removes something."""
        cell_id = configured_cell_ids()[0]
        base = {"cell_id": cell_id, "status": "ok", "candidates": 4,
                "accepted": 1, "rejected": 3,
                "candidate_observations": 10, "unique_candidate_keys": 7,
                "repeated_candidate_observations": 3,
                "uncanonicalizable_candidate_observations": 2}
        base.update(over)
        return base

    def validate(self, row):
        return schema.validate(manifest(cells=[row]), "run_manifest.v1.json")

    def test_a_complete_tuple_is_accepted(self):
        self.assertEqual(self.validate(self.row()), [])

    def test_a_manifest_omitting_all_four_remains_valid(self):
        """Every M2/M3 manifest is this shape. C2 must not invalidate them."""
        row = self.row()
        for name in self.FIELDS:
            del row[name]
        self.assertEqual(self.validate(row), [])

    def test_removing_any_one_of_the_four_is_refused(self):
        for name in self.FIELDS:
            with self.subTest(missing=name):
                row = self.row()
                del row[name]
                self.assertNotEqual(
                    self.validate(row), [],
                    "a partial tuple must be refused; %s was dropped" % name)

    def test_each_field_alone_is_refused(self):
        """All four directions of the dependency, proved from the other side."""
        for name in self.FIELDS:
            with self.subTest(only=name):
                row = self.row()
                for other in self.FIELDS:
                    if other != name:
                        del row[other]
                self.assertNotEqual(self.validate(row), [])

    def test_a_negative_count_is_refused(self):
        for name in self.FIELDS:
            with self.subTest(name):
                self.assertNotEqual(self.validate(self.row(**{name: -1})), [])

    def test_a_non_integer_count_is_refused(self):
        for bad in (1.5, "3", None, True, [3], {"n": 3}):
            with self.subTest(repr(bad)):
                self.assertNotEqual(
                    self.validate(self.row(candidate_observations=bad)), [])

    def test_zero_is_a_legitimate_measurement(self):
        row = self.row(**{name: 0 for name in self.FIELDS})
        self.assertEqual(self.validate(row), [])

    def test_the_dependency_is_declared_in_all_four_directions(self):
        items = (schema.load_schema("run_manifest.v1.json")["properties"]
                 ["cells"]["items"])
        dependent = items["dependentRequired"]
        for name in self.FIELDS:
            with self.subTest(name):
                self.assertEqual(sorted(dependent[name]),
                                 sorted(f for f in self.FIELDS if f != name))

    def test_the_row_still_refuses_an_invented_field(self):
        """`additionalProperties: false` survives the addition."""
        self.assertNotEqual(self.validate(self.row(invented_counter=1)), [])

    def test_the_schema_version_is_unchanged(self):
        """Additive optional properties do not bump the version."""
        doc = schema.load_schema("run_manifest.v1.json")
        self.assertEqual(doc["properties"]["schema_version"]["const"], 1)
        self.assertEqual(manifest()["schema_version"], 1)

    def test_no_rate_property_was_added_to_a_cell_row(self):
        properties = (schema.load_schema("run_manifest.v1.json")["properties"]
                      ["cells"]["items"]["properties"])
        for forbidden in ("duplicate_rate", "repeat_rate", "sighting_rate"):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, properties)


if __name__ == "__main__":
    unittest.main(verbosity=2)
