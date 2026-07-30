#!/usr/bin/env python3
"""test_eligibility.py — alias-conflict artifact and the §8 eligibility proof (S6-6).

Two things get pinned here, and both are about a claim a reader will trust without
re-deriving it:

  * THE CONFLICT ARTIFACT. A conflict says two URLs were *not* merged and why. If
    its count disagrees with its rows, or its ordering wanders between runs, or a
    malformed row reaches disk, then the one artifact whose job is recording
    refused merges becomes untrustworthy. The count is DERIVED from the rows and
    re-read from the validated document, so the manifest and the artifact cannot
    drift. An empty set is a real answer and is still written: "this run found
    none" must be distinguishable from "nobody looked".
  * ELIGIBILITY, IN BOTH DIRECTIONS. §8's predicate decides whether a run may ever
    be published, so every clause is proved to fail on its own, and the whole is
    proved to succeed only when all of them hold. It is derived from run facts
    alone — a cross-reference pointer cannot create a missing-evidence finding, and
    the existence or size of the conflict artifact cannot change it either way.

S6-6 adds NO eligibility predicate. It proves the one S6-4 brought forward, routes
what S6-3 already adjudicated, and reports what the artifact already says.

Deliberately absent: alias adjudication itself (S6-3 owns every §4 row) and target
HTTP-attempt reporting, which the S6-6 preflight established cannot be derived from
the committed `TargetFetchOutcome` or `pool.accounting()` and is therefore left to a
separate accounting checkpoint. Nothing here estimates it.
"""
import datetime
import glob
import json
import os
import tempfile
import unittest

from src.harvest import aliases as aliases_mod
from src.harvest import artifacts
from src.harvest import run_cells
from src.harvest import schema

RUN_ID = "20260730T120000Z-1"
STAMP = "2026-07-30T12:00:00Z"
IDENT = "https://tgt.harvest.test/page"


def a_conflict(reason=aliases_mod.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED,
               identity_url=IDENT, proposed_alias="https://other-target.test/x",
               detail="probe conflict"):
    return aliases_mod.AliasConflict(reason=reason, identity_url=identity_url,
                                     proposed_alias=proposed_alias, detail=detail)


def build(conflicts):
    return artifacts.build_alias_conflicts(
        conflicts, harvest_run_id=RUN_ID, generated_at=STAMP)


# ------------------------------------------------------------- the artifact
class TestAliasConflictArtifact(unittest.TestCase):

    def test_an_empty_set_still_produces_a_valid_artifact(self):
        """"none found" must be distinguishable from "nobody looked"."""
        doc = build([])
        self.assertEqual(schema.validate(doc, "alias_conflict.v1.json"), [])
        self.assertEqual(doc["conflicts"], [])
        self.assertEqual(doc["alias_conflicts_count"], 0)

    def test_a_single_conflict_validates(self):
        doc = build([a_conflict()])
        self.assertEqual(schema.validate(doc, "alias_conflict.v1.json"), [])
        self.assertEqual(doc["alias_conflicts_count"], 1)

    def test_multiple_conflicts_validate(self):
        doc = build([a_conflict(identity_url=IDENT + "-a"),
                     a_conflict(identity_url=IDENT + "-b"),
                     a_conflict(reason=aliases_mod.CONFLICT_MULTIPLE_CANONICALS)])
        self.assertEqual(schema.validate(doc, "alias_conflict.v1.json"), [])
        self.assertEqual(doc["alias_conflicts_count"], 3)

    def test_the_envelope_carries_the_run_and_the_instant(self):
        doc = build([a_conflict()])
        self.assertEqual(doc["harvest_run_id"], RUN_ID)
        self.assertEqual(doc["generated_at"], STAMP)
        self.assertEqual(doc["artifact_type"], "alias_conflicts")
        self.assertEqual(doc["schema_version"], 1)

    def test_every_row_is_unresolved(self):
        """A resolved conflict is not a conflict, and Stage 6 resolves none."""
        doc = build([a_conflict(), a_conflict(identity_url=IDENT + "-b")])
        for row in doc["conflicts"]:
            self.assertEqual(row["resolution"], "unresolved")

    def test_each_row_carries_a_detected_at(self):
        for row in build([a_conflict()])["conflicts"]:
            self.assertEqual(row["detected_at"], STAMP)

    def test_a_detail_is_always_present(self):
        """The row exists to tell an operator what to look at."""
        doc = build([a_conflict(detail="")])
        self.assertTrue(doc["conflicts"][0]["detail"])

    def test_every_committed_reason_is_storable(self):
        reasons = (aliases_mod.CONFLICT_MULTIPLE_CANONICALS,
                   aliases_mod.CONFLICT_CIRCULAR_CANONICAL,
                   aliases_mod.CONFLICT_MALFORMED_CANONICAL,
                   aliases_mod.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED,
                   aliases_mod.CONFLICT_ROBOTS_UNVERIFIED)
        for reason in reasons:
            with self.subTest(reason):
                doc = build([a_conflict(reason=reason)])
                self.assertEqual(schema.validate(doc, "alias_conflict.v1.json"), [])

    def test_a_null_proposed_alias_is_accepted(self):
        """Malformed evidence may be too broken to name an alias at all."""
        doc = build([a_conflict(reason=aliases_mod.CONFLICT_MALFORMED_CANONICAL,
                                proposed_alias=None)])
        self.assertEqual(schema.validate(doc, "alias_conflict.v1.json"), [])
        self.assertIsNone(doc["conflicts"][0]["proposed_alias"])

    # -- the derived count ------------------------------------------------
    def test_the_count_is_derived_from_the_rows(self):
        for size in (0, 1, 2, 5):
            with self.subTest(size=size):
                doc = build([a_conflict(identity_url=IDENT + str(i))
                             for i in range(size)])
                self.assertEqual(doc["alias_conflicts_count"], len(doc["conflicts"]))
                self.assertEqual(doc["alias_conflicts_count"], size)

    def test_the_count_is_not_a_caller_parameter(self):
        import inspect
        parameters = inspect.signature(artifacts.build_alias_conflicts).parameters
        self.assertNotIn("alias_conflicts_count", parameters)
        self.assertNotIn("count", parameters)

    def test_reading_the_count_back_refuses_a_tampered_document(self):
        doc = build([a_conflict()])
        doc["alias_conflicts_count"] = 99
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.alias_conflicts_count(doc)

    def test_reading_the_count_back_agrees_with_the_builder(self):
        doc = build([a_conflict(), a_conflict(identity_url=IDENT + "-b")])
        self.assertEqual(artifacts.alias_conflicts_count(doc), 2)

    def test_a_document_without_a_conflicts_list_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.alias_conflicts_count({"alias_conflicts_count": 0})

    # -- ordering and determinism ----------------------------------------
    def test_rows_are_sorted_by_reason_then_identity_then_alias(self):
        doc = build([
            a_conflict(reason=aliases_mod.CONFLICT_MULTIPLE_CANONICALS,
                       identity_url=IDENT + "-z"),
            a_conflict(reason=aliases_mod.CONFLICT_CIRCULAR_CANONICAL,
                       identity_url=IDENT + "-b"),
            a_conflict(reason=aliases_mod.CONFLICT_CIRCULAR_CANONICAL,
                       identity_url=IDENT + "-a")])
        keys = [(r["reason"], r["identity_url"], r["proposed_alias"] or "")
                for r in doc["conflicts"]]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_input_produces_identical_bytes(self):
        rows = [a_conflict(identity_url=IDENT + s) for s in ("a", "b", "c")]
        first = artifacts.serialize(build(rows))
        second = artifacts.serialize(build(list(reversed(rows))))
        self.assertEqual(first, second)

    def test_the_conflict_id_is_content_derived_not_positional(self):
        """The same contradiction gets the same id in every run.

        Selected by identity_url rather than by index on purpose: the rows are
        sorted, so an index would test the sort order instead of the id.
        """
        alone = build([a_conflict()])["conflicts"][0]
        with_company = build([a_conflict(identity_url=IDENT + "-other"),
                              a_conflict()])["conflicts"]
        same = [row for row in with_company if row["identity_url"] == IDENT]
        self.assertEqual(len(same), 1)
        self.assertEqual(alone["conflict_id"], same[0]["conflict_id"])

    def test_different_conflicts_get_different_ids(self):
        doc = build([a_conflict(identity_url=IDENT + "-a"),
                     a_conflict(identity_url=IDENT + "-b")])
        ids = {row["conflict_id"] for row in doc["conflicts"]}
        self.assertEqual(len(ids), 2)

    def test_the_id_is_sixteen_hex_characters(self):
        row = build([a_conflict()])["conflicts"][0]
        self.assertRegex(row["conflict_id"], r"^[0-9a-f]{16}$")

    # -- refusal before write --------------------------------------------
    def test_a_conflict_without_a_reason_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError):
            build([{"identity_url": IDENT, "detail": "d"}])

    def test_a_conflict_without_an_identity_url_is_refused(self):
        with self.assertRaises(artifacts.ArtifactError):
            build([{"reason": "cross_registrable_domain_without_rule", "detail": "d"}])

    def test_an_uncommitted_reason_is_refused_by_the_schema_before_writing(self):
        doc = build([{"reason": "invented_reason", "identity_url": IDENT,
                      "detail": "d"}])
        self.assertNotEqual(schema.validate(doc, "alias_conflict.v1.json"), [])
        root = tempfile.mkdtemp(prefix="s6_6_refuse_")
        path = artifacts.alias_conflicts_path(root, RUN_ID)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with self.assertRaises(Exception):
            artifacts.write_alias_conflicts(path, doc)
        self.assertFalse(os.path.exists(path), "an invalid document wrote a file")

    def test_it_is_written_through_the_committed_writer(self):
        root = tempfile.mkdtemp(prefix="s6_6_write_")
        path = artifacts.alias_conflicts_path(root, RUN_ID)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        artifacts.write_alias_conflicts(path, build([a_conflict()]))
        raw = open(path, "rb").read()
        self.assertEqual(raw, artifacts.serialize(build([a_conflict()])))
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))


# --------------------------------------------------- §8 eligibility, both ways
class TestEligibilityMatrix(unittest.TestCase):
    """The §8 predicate: harvest mode · no failed cell · ≥1 owner · all checked."""

    OK_CELLS = ({"cell_id": "cases__case-studies", "status": "ok"},)

    def full(self, access_status="ok"):
        return {"record_type": "full", "access_status": access_status}

    def derive(self, **over):
        kw = dict(mode=artifacts.MODE_HARVEST, cells=self.OK_CELLS,
                  target_fetch_owners=1, records=[self.full()])
        kw.update(over)
        return artifacts.derive_publication_eligibility(
            kw["mode"], kw["cells"], target_fetch_owners=kw["target_fetch_owners"],
            records=kw["records"])

    # -- true when every clause holds ------------------------------------
    def test_eligible_when_all_four_clauses_hold(self):
        eligible, reason = self.derive()
        self.assertTrue(eligible, reason)
        self.assertIsNone(reason)

    def test_eligible_with_several_checked_records(self):
        eligible, reason = self.derive(records=[self.full()] * 4,
                                       target_fetch_owners=4)
        self.assertTrue(eligible, reason)

    def test_every_observed_failure_still_counts_as_checked(self):
        for status in ("ok", "redirected", "not_found", "gone", "auth_required",
                       "paywalled", "server_error", "timeout", "robots_denied",
                       "unreachable"):
            with self.subTest(status):
                eligible, reason = self.derive(records=[self.full(status)])
                self.assertTrue(eligible, reason)

    # -- false, one clause at a time -------------------------------------
    def test_ineligible_when_the_mode_is_not_harvest(self):
        for mode in ("smoke", "smoke_model", "refresh", "linkcheck", "migration"):
            with self.subTest(mode):
                eligible, reason = self.derive(mode=mode)
                self.assertFalse(eligible)
                self.assertIn("infrastructure tests", reason)

    def test_ineligible_when_no_target_fetch_was_owned(self):
        eligible, reason = self.derive(target_fetch_owners=0)
        self.assertFalse(eligible)
        self.assertIn("no target page was fetched", reason)

    def test_ineligible_when_a_cell_failed(self):
        for status in ("adapter_error", "infrastructure_error"):
            with self.subTest(status):
                eligible, reason = self.derive(
                    cells=({"cell_id": "cases__case-studies", "status": status},))
                self.assertFalse(eligible)
                self.assertIn("cell(s) failed", reason)

    def test_ineligible_when_any_record_is_unchecked(self):
        eligible, reason = self.derive(records=[self.full(), self.full("not_checked")])
        self.assertFalse(eligible)
        self.assertIn("1 of 2", reason)
        self.assertIn("no target evidence", reason)

    def test_the_failing_clauses_keep_their_committed_priority(self):
        """Mode first, then owners, then failed cells, then missing evidence."""
        eligible, reason = self.derive(
            mode="smoke", target_fetch_owners=0,
            cells=({"cell_id": "cases__case-studies", "status": "adapter_error"},),
            records=[self.full("not_checked")])
        self.assertFalse(eligible)
        self.assertIn("infrastructure tests", reason)

    # -- derived from run facts only -------------------------------------
    def test_a_cross_reference_row_cannot_create_a_missing_evidence_finding(self):
        records = [self.full(), {"record_type": "cross_reference"},
                   {"record_type": "cross_reference"}]
        eligible, reason = self.derive(records=records)
        self.assertTrue(eligible, reason)
        self.assertEqual(artifacts.unchecked_full_records(records), (0, 1))

    def test_a_run_with_only_cross_reference_rows_is_eligible_on_this_clause(self):
        """No full record means nothing unchecked; the other clauses still apply."""
        eligible, reason = self.derive(records=[{"record_type": "cross_reference"}])
        self.assertTrue(eligible, reason)

    def test_eligibility_is_not_a_manifest_parameter(self):
        import inspect
        parameters = inspect.signature(artifacts.build_run_manifest).parameters
        self.assertNotIn("publication_eligible", parameters)
        self.assertNotIn("publication_ineligible_reason", parameters)

    # -- conflicts do not touch eligibility ------------------------------
    def test_a_nonzero_conflict_count_does_not_make_a_run_ineligible(self):
        doc = build([a_conflict(), a_conflict(identity_url=IDENT + "-b")])
        manifest = artifacts.build_run_manifest(
            harvest_run_id=RUN_ID, started_at=STAMP, finished_at=STAMP,
            cells=[{"cell_id": "cases__case-studies", "status": "ok"}],
            target_fetch_owners=1, records=[self.full()], alias_conflicts=doc)
        self.assertEqual(manifest["alias_conflicts_count"], 2)
        self.assertTrue(manifest["publication_eligible"])

    def test_a_zero_conflict_count_does_not_make_a_run_eligible(self):
        manifest = artifacts.build_run_manifest(
            harvest_run_id=RUN_ID, started_at=STAMP, finished_at=STAMP,
            cells=[{"cell_id": "cases__case-studies", "status": "ok"}],
            target_fetch_owners=0, records=[self.full()], alias_conflicts=build([]))
        self.assertEqual(manifest["alias_conflicts_count"], 0)
        self.assertFalse(manifest["publication_eligible"])

    def test_the_manifest_count_comes_from_the_artifact_not_a_parameter(self):
        doc = build([a_conflict()])
        manifest = artifacts.build_run_manifest(
            harvest_run_id=RUN_ID, started_at=STAMP, finished_at=STAMP,
            cells=[{"cell_id": "cases__case-studies", "status": "ok"}],
            target_fetch_owners=1, records=[self.full()], alias_conflicts=doc)
        self.assertEqual(manifest["alias_conflicts_count"],
                         len(doc["conflicts"]))

    def test_a_tampered_artifact_is_refused_by_the_manifest_builder(self):
        doc = build([a_conflict()])
        doc["alias_conflicts_count"] = 7
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.build_run_manifest(
                harvest_run_id=RUN_ID, started_at=STAMP, finished_at=STAMP,
                cells=[{"cell_id": "cases__case-studies", "status": "ok"}],
                target_fetch_owners=1, records=[self.full()], alias_conflicts=doc)

    def test_the_count_is_omitted_when_no_artifact_is_supplied(self):
        manifest = artifacts.build_run_manifest(
            harvest_run_id=RUN_ID, started_at=STAMP, finished_at=STAMP,
            cells=[{"cell_id": "cases__case-studies", "status": "ok"}],
            target_fetch_owners=1, records=[self.full()])
        self.assertNotIn("alias_conflicts_count", manifest)


# --------------------------------------------------------- the integrated run
class TestIntegratedRun(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s6_6_run_")
        moment = datetime.datetime(2026, 7, 30, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        cls.result = run_cells.run(cls.root, clock=lambda: moment)
        cls.manifest = json.load(open(glob.glob(os.path.join(
            cls.root, "runs", "*", "manifest.json"))[0], encoding="utf-8"))
        cls.artifact = json.load(open(glob.glob(os.path.join(
            cls.root, "runs", "*", "alias_conflicts.json"))[0], encoding="utf-8"))

    def test_the_artifact_exists_and_validates(self):
        self.assertEqual(schema.validate(self.artifact, "alias_conflict.v1.json"), [])

    def test_the_committed_corpus_produces_no_conflict(self):
        """A real finding about the corpus: no accepted target declares a
        canonical tag, so nothing is contradictory. Recorded, not manufactured."""
        self.assertEqual(self.artifact["conflicts"], [])
        self.assertEqual(self.artifact["alias_conflicts_count"], 0)

    def test_the_manifest_agrees_with_the_artifact(self):
        self.assertEqual(self.manifest["alias_conflicts_count"],
                         self.artifact["alias_conflicts_count"])

    def test_the_artifact_names_this_run(self):
        self.assertEqual(self.artifact["harvest_run_id"], self.result.run_id)

    def test_the_bounds_report_every_cap_the_run_enforced(self):
        bounds = self.manifest["config"]["bounds"]
        self.assertEqual(bounds["max_cells"], run_cells.MAX_CELLS)
        self.assertEqual(bounds["max_target_fetches_per_cell"],
                         run_cells.MAX_TARGET_FETCHES_PER_CELL)

    def test_the_run_is_eligible_because_every_clause_holds(self):
        self.assertTrue(self.manifest["publication_eligible"])
        self.assertIsNone(self.manifest["publication_ineligible_reason"])

    def test_no_target_attempt_total_is_reported(self):
        """The S6-6 preflight established an exact target-attempt count cannot be
        derived from the committed TargetFetchOutcome or pool.accounting(). It is
        therefore NOT reported rather than estimated, and `http_attempts` keeps its
        existing source-only meaning until a separate accounting checkpoint."""
        accounting = self.manifest["request_accounting"]
        self.assertEqual(accounting["source_fetch_owners"], 25)
        self.assertEqual(accounting["http_attempts"], 25)
        for invented in ("target_http_attempts", "target_attempts",
                         "target_retries", "target_redirect_hops",
                         "total_http_attempts"):
            with self.subTest(invented):
                self.assertNotIn(invented, accounting)

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(leaked))


if __name__ == "__main__":
    unittest.main(verbosity=2)
