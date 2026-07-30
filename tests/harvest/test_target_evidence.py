#!/usr/bin/env python3
"""test_target_evidence.py — observed evidence on full records (S6-5).

The failures worth pinning here are the ones that would put a FALSE CLAIM into a
persisted record, where nothing downstream can detect or undo it:

  * a record claiming `fetched` when the fetch failed, or `not_checked` when it
    succeeded — either makes access_status useless as evidence;
  * a fetch changing something it has no business changing. A score, a category, a
    facet payload or an identity moving between a fetch and a no-fetch run would
    mean the fetch re-judged the item, which Stage 6 forbids outright;
  * a cross_reference row growing independent target evidence. It is a pointer at a
    full record in another cell; giving it its own access_status invents a second
    opinion about one page;
  * a malformed alias reaching a written artifact. An alias asserts two URLs are
    the same resource, so a bad one is a destructive claim, and it must be refused
    BEFORE the record exists rather than caught by the schema afterwards;
  * alias order or duplication varying between runs, which would put a moving
    field into a byte-compared artifact;
  * a completed record dict being mutated after construction, which would make
    `make_full_record` stop being the sole owner of record shape.

`updated_at` staying null is asserted too: a `Last-Modified` header is not a
content-update claim (CF-17), and promoting one would disagree with a freshness
score computed before the fetch.
"""
import datetime
import glob
import json
import os
import tempfile
import unittest

from src.harvest import records as records_mod
from src.harvest import run_cells
from src.harvest import targetfetch as targetfetch_mod

STAMP = "2026-07-30T12:00:00Z"
URL = "https://tgt.harvest.test/page"


def an_outcome(**over):
    base = dict(requested_url=URL, access_status=targetfetch_mod.OK,
                verification_status=targetfetch_mod.FETCHED,
                verification_evidence="http 200; final_url %s; 42 bytes" % URL,
                last_checked_at=STAMP, http_status=200, final_url=URL,
                permanent_redirect=False, content_hash="a" * 64,
                content_type="text/html", body=b"<html></html>")
    base.update(over)
    return targetfetch_mod.TargetFetchOutcome(**base)


def an_alias(url=URL + "-preferred", kind="canonical_tag", **over):
    row = {"url": url, "kind": kind, "evidence": {"rel_canonical": url},
           "observed_at": STAMP}
    row.update(over)
    return row


# --------------------------------------------------- records.py: the D6-A parameter
class TestUrlAliasesParameter(unittest.TestCase):
    """`make_full_record` stays the sole owner of the persistent record shape."""

    def record(self, **over):
        kw = dict(record_id="r" * 16, content_id="c" * 16, topic_slug="cases",
                  category_slug="case-studies", cell_id="cases__case-studies",
                  identity_url=URL, target_url=URL, harvest_run_id="20260730T120000Z-1",
                  source_id="s", source_adapter="feed", title="t", summary="s")
        kw.update(over)
        return records_mod.make_full_record(**kw)

    def test_omitting_it_still_produces_an_empty_list(self):
        self.assertEqual(self.record()["url_aliases"], [])

    def test_passing_none_still_produces_an_empty_list(self):
        self.assertEqual(self.record(url_aliases=None)["url_aliases"], [])

    def test_passing_an_empty_sequence_still_produces_an_empty_list(self):
        self.assertEqual(self.record(url_aliases=())["url_aliases"], [])

    def test_it_is_keyword_only(self):
        import inspect
        parameter = inspect.signature(records_mod.make_full_record).parameters["url_aliases"]
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_one_alias_is_projected_with_the_admitted_keys_only(self):
        alias = an_alias()
        alias["extra_key"] = "dropped"
        row = self.record(url_aliases=[alias])["url_aliases"][0]
        self.assertEqual(set(row), {"url", "kind", "evidence", "observed_at"})

    def test_aliases_are_ordered_by_kind_then_url(self):
        rows = self.record(url_aliases=[
            an_alias(url=URL + "-z", kind="permanent_redirect"),
            an_alias(url=URL + "-b", kind="canonical_tag"),
            an_alias(url=URL + "-a", kind="canonical_tag")])["url_aliases"]
        self.assertEqual([(r["kind"], r["url"]) for r in rows],
                         [("canonical_tag", URL + "-a"),
                          ("canonical_tag", URL + "-b"),
                          ("permanent_redirect", URL + "-z")])

    def test_a_repeated_claim_is_deduplicated_rather_than_refused(self):
        rows = self.record(url_aliases=[an_alias(), an_alias()])["url_aliases"]
        self.assertEqual(len(rows), 1)

    def test_the_same_url_under_two_kinds_is_two_claims(self):
        rows = self.record(url_aliases=[
            an_alias(kind="canonical_tag"),
            an_alias(kind="permanent_redirect")])["url_aliases"]
        self.assertEqual(len(rows), 2)

    def test_ordering_is_deterministic_under_shuffled_input(self):
        given = [an_alias(url=URL + "-c"), an_alias(url=URL + "-a"),
                 an_alias(url=URL + "-b")]
        first = self.record(url_aliases=given)["url_aliases"]
        second = self.record(url_aliases=list(reversed(given)))["url_aliases"]
        self.assertEqual(first, second)

    def test_the_caller_s_list_is_not_mutated(self):
        given = [an_alias(url=URL + "-b"), an_alias(url=URL + "-a")]
        before = json.dumps(given, sort_keys=True)
        self.record(url_aliases=given)
        self.assertEqual(json.dumps(given, sort_keys=True), before)

    # -- refusals, all before the record exists ---------------------------
    def test_a_non_object_alias_is_refused(self):
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=["not an object"])

    def test_a_bare_dict_instead_of_a_sequence_is_refused(self):
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=an_alias())

    def test_a_missing_required_key_is_refused(self):
        for key in ("url", "kind", "evidence", "observed_at"):
            with self.subTest(key):
                alias = an_alias()
                del alias[key]
                with self.assertRaises(records_mod.RecordError):
                    self.record(url_aliases=[alias])

    def test_an_uncommitted_alias_kind_is_refused(self):
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=[an_alias(kind="invented_kind")])

    def test_every_committed_kind_is_accepted(self):
        for kind in records_mod.ALIAS_KINDS:
            with self.subTest(kind):
                rows = self.record(url_aliases=[an_alias(kind=kind)])["url_aliases"]
                self.assertEqual(rows[0]["kind"], kind)

    def test_a_relative_alias_url_is_refused(self):
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=[an_alias(url="/relative")])

    def test_a_non_object_evidence_is_refused(self):
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=[an_alias(evidence="why")])

    def test_a_refused_alias_produces_no_record_at_all(self):
        """Refuse before assembly: a half-built record must never escape."""
        with self.assertRaises(records_mod.RecordError):
            self.record(url_aliases=[an_alias(kind="nope")])

    def test_a_cross_reference_still_refuses_url_aliases_entirely(self):
        import inspect
        self.assertNotIn("url_aliases",
                         inspect.signature(records_mod.make_cross_reference).parameters)


# ------------------------------------------------ run_cells.py: the projection
class TestEvidenceProjection(unittest.TestCase):
    """`_full_record` reads the outcome; it recomputes nothing."""

    def build(self, outcome=None, adjudication=None):
        candidate, classification, verdict, assignment = _pipeline_stubs()
        return run_cells._full_record(
            candidate, classification, verdict, assignment,
            source_map={"s": {"adapter": "feed"}},
            harvest_run_id="20260730T120000Z-1", discovered_at=STAMP,
            outcome=outcome, adjudication=adjudication)

    def test_without_an_outcome_the_committed_stage_4_defaults_apply(self):
        record = self.build()
        self.assertEqual(record["access_status"], "not_checked")
        self.assertEqual(record["verification_status"], "unverified")
        self.assertIsNone(record["http_status"])
        self.assertIsNone(record["content_hash"])
        self.assertIsNone(record["last_checked_at"])

    def test_a_successful_fetch_replaces_every_evidence_field(self):
        record = self.build(an_outcome())
        self.assertEqual(record["access_status"], "ok")
        self.assertEqual(record["verification_status"], "fetched")
        self.assertEqual(record["http_status"], 200)
        self.assertEqual(record["content_hash"], "a" * 64)
        self.assertEqual(record["last_checked_at"], STAMP)
        self.assertIn("http 200", record["verification_evidence"])

    def test_it_never_claims_verified(self):
        self.assertNotEqual(self.build(an_outcome())["verification_status"], "verified")

    def test_observed_failures_stay_honest_and_checked(self):
        for status in ("not_found", "gone", "auth_required", "paywalled",
                       "server_error", "timeout", "robots_denied", "unreachable"):
            with self.subTest(status):
                record = self.build(an_outcome(
                    access_status=status,
                    verification_status=targetfetch_mod.UNVERIFIED,
                    http_status=404 if status == "not_found" else None,
                    content_hash=None,
                    verification_evidence="%s; probe" % status))
                self.assertEqual(record["access_status"], status)
                self.assertEqual(record["verification_status"], "unverified")
                self.assertIsNone(record["content_hash"])
                # Still stamped: we did look, and when we looked is a fact.
                self.assertEqual(record["last_checked_at"], STAMP)

    def test_a_budget_skipped_outcome_stays_not_checked(self):
        record = self.build(an_outcome(
            access_status=targetfetch_mod.NOT_CHECKED,
            verification_status=targetfetch_mod.UNVERIFIED,
            http_status=None, content_hash=None,
            verification_evidence="budget exhausted before this target was fetched; "
                                  "no request was made"))
        self.assertEqual(record["access_status"], "not_checked")
        self.assertIn("no request was made", record["verification_evidence"])

    def test_a_redirected_outcome_is_recorded_as_redirected(self):
        record = self.build(an_outcome(access_status=targetfetch_mod.REDIRECTED,
                                       permanent_redirect=True))
        self.assertEqual(record["access_status"], "redirected")

    def test_updated_at_stays_null_even_after_a_successful_fetch(self):
        """CF-17: a transport header is not a content-update claim."""
        self.assertIsNone(self.build(an_outcome())["updated_at"])

    def test_the_adjudicated_canonical_url_reaches_the_record(self):
        preferred = URL + "-preferred"
        record = self.build(an_outcome(),
                            adjudication=(preferred, (an_alias(preferred),), ()))
        self.assertEqual(record["canonical_url"], preferred)
        self.assertEqual(record["url_aliases"][0]["url"], preferred)

    def test_without_alias_evidence_canonical_url_stays_the_identity(self):
        record = self.build(an_outcome(), adjudication=(URL, (), ()))
        self.assertEqual(record["canonical_url"], URL)
        self.assertEqual(record["url_aliases"], [])

    def test_conflicts_are_not_projected_onto_the_record(self):
        """A conflict is recorded elsewhere; it never becomes a record field."""
        record = self.build(an_outcome(), adjudication=(URL, (), ("a conflict",)))
        self.assertEqual(record["url_aliases"], [])
        self.assertNotIn("alias_conflicts", record)

    # -- nothing else may move -------------------------------------------
    def test_identity_fields_are_byte_identical_with_and_without_a_fetch(self):
        without = self.build()
        with_fetch = self.build(an_outcome())
        for field in ("record_id", "content_id", "identity_url", "cell_id",
                      "target_url"):
            with self.subTest(field):
                self.assertEqual(without[field], with_fetch[field])

    def test_no_score_moves(self):
        without = self.build()
        with_fetch = self.build(an_outcome())
        for field in ("relevance_score", "quality_score", "audience_fit_score",
                      "freshness_score"):
            with self.subTest(field):
                self.assertEqual(without[field], with_fetch[field])

    def test_the_classification_and_facets_are_unchanged(self):
        without = self.build()
        with_fetch = self.build(an_outcome())
        self.assertEqual(without["classification"], with_fetch["classification"])
        self.assertEqual(without.get("case_facets"), with_fetch.get("case_facets"))

    def test_only_the_evidence_fields_differ(self):
        without = self.build()
        with_fetch = self.build(an_outcome(), adjudication=(URL, (), ()))
        moved = {k for k in set(without) | set(with_fetch)
                 if without.get(k) != with_fetch.get(k)}
        self.assertEqual(moved, {"access_status", "http_status",
                                 "verification_status", "verification_evidence",
                                 "content_hash", "last_checked_at"})


def _pipeline_stubs():
    """Minimal stand-ins for the committed Stage 4 outputs `_full_record` reads."""
    class Scores:
        relevance = 0.9
        quality = 0.8
        audience_fit = 1.0
        freshness = 0.5

    class Verdict:
        accepted = True
        scores = Scores()
        access_status = "not_checked"
        http_status = None
        verification_status = "unverified"
        verification_evidence = None
        content_hash = None

    class Classification:
        topic_slug = "cases"
        category_slug = "case-studies"
        rule_id = "R10_default_by_category"
        rationale = "probe"
        evidence = ()
        competing_categories = ()

    class Candidate:
        candidate_key = "k1"
        identity_url = URL
        target_url = URL
        canonical_url = URL
        content_id = "c" * 16
        source_ids = ("s",)
        title = "Probe"
        summary = "A probe candidate."
        publisher = None
        author = None
        published_at = None
        language = None
        content_type = "article"
        provenance_raw = None

    class Assignment:
        applicable = False
        case_facets = None

    return Candidate(), Classification(), Verdict(), Assignment()


# ------------------------------------------------------------- integrated run
class TestIntegratedRun(unittest.TestCase):
    """The whole driver over the committed corpus, into an injected temp root."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s6_5_run_")
        moment = datetime.datetime(2026, 7, 30, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        cls.result = run_cells.run(cls.root, clock=lambda: moment)
        cls.manifest = json.load(open(glob.glob(
            os.path.join(cls.root, "runs", "*", "manifest.json"))[0],
            encoding="utf-8"))
        cls.full = [r for r in cls.result.records if r["record_type"] == "full"]

    def test_every_accepted_record_carries_observed_evidence(self):
        self.assertTrue(self.full)
        for record in self.full:
            with self.subTest(record["identity_url"]):
                self.assertEqual(record["access_status"], "ok")
                self.assertEqual(record["verification_status"], "fetched")
                self.assertEqual(record["http_status"], 200)
                self.assertTrue(record["content_hash"])
                self.assertEqual(record["last_checked_at"], "2026-07-30T12:00:00Z")

    def test_each_record_hashes_its_own_page(self):
        hashes = {r["content_hash"] for r in self.full}
        self.assertEqual(len(hashes), len(self.full))

    def test_one_fetch_per_identity_still_holds(self):
        self.assertEqual(self.manifest["request_accounting"]["target_fetch_owners"],
                         len(self.full))

    def test_no_alias_is_adopted_without_a_robots_verdict(self):
        """S6-4/S6-5 pass canonical_robots_allowed=None, so no canonical_tag
        alias forms. Recorded so the day robots evidence is wired, this changes
        visibly rather than silently."""
        for record in self.full:
            with self.subTest(record["identity_url"]):
                self.assertEqual(record["url_aliases"], [])
                self.assertEqual(record["canonical_url"], record["identity_url"])

    def test_no_cross_reference_row_carries_target_evidence(self):
        for record in self.result.records:
            if record["record_type"] == "full":
                continue
            with self.subTest(record["record_id"]):
                self.assertNotIn("access_status", record)
                self.assertNotIn("url_aliases", record)
                self.assertNotIn("content_hash", record)

    def test_every_artifact_still_validates(self):
        from src.harvest import schema
        for path in glob.glob(os.path.join(self.root, "runs", "*", "cells", "*.json")):
            with self.subTest(os.path.basename(path)):
                with open(path, "r", encoding="utf-8") as handle:
                    schema.validate(json.load(handle), "cell_artifact.v1.json")

    def test_the_manifest_says_the_run_enriched(self):
        """The one S6-6 reporting field brought forward: a run that fetched four
        pages and wrote evidence onto four records must not report enrich: false
        beside a publication_eligible derived from that very evidence."""
        self.assertTrue(self.manifest["config"]["enrich"])

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(leaked))


class TestEnrichIsReportedTruthfully(unittest.TestCase):
    """`config.enrich` is derived from whether the fetch phase was ENABLED."""

    def cells(self):
        return run_cells.configured_cells()

    def test_an_enriching_run_reports_true(self):
        block = run_cells._config_block(self.cells(), 12, enrich=True)
        self.assertIs(block["enrich"], True)

    def test_a_metadata_only_run_reports_false(self):
        block = run_cells._config_block(self.cells(), 12, enrich=False)
        self.assertIs(block["enrich"], False)

    def test_it_is_required_rather_than_defaulted(self):
        """A default would let a caller silently re-acquire the old dishonest
        `False` on a run that actually enriched."""
        import inspect
        parameter = inspect.signature(run_cells._config_block).parameters["enrich"]
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(parameter.default, inspect.Parameter.empty)
        with self.assertRaises(TypeError):
            run_cells._config_block(self.cells(), 12)

    def test_it_is_not_derived_from_eligibility_or_record_counts(self):
        """A run that enabled enrichment and had every fetch fail still enriched.
        The flag follows the decision, not the outcome."""
        block = run_cells._config_block(self.cells(), 12, enrich=True)
        self.assertIs(block["enrich"], True)
        self.assertNotIn("publication_eligible", block)

    def test_a_no_enrich_run_would_also_be_publication_ineligible(self):
        """Nothing fetched means zero owners, which the committed first guard
        already refuses — so `enrich: false` and ineligible travel together."""
        from src.harvest import artifacts
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST,
            ({"cell_id": "cases__case-studies", "status": "ok"},),
            target_fetch_owners=0, records=[])
        self.assertFalse(eligible)
        self.assertIn("no target page was fetched", reason)

    def test_a_cell_run_without_a_pool_performs_no_fetch(self):
        """The same decision the flag reports: no pool means no ownership gate to
        acquire, so nothing is fetched and nothing is enriched."""
        cell = {"cell_id": "cases__case-studies", "topic": "Cases",
                "topic_slug": "cases", "category": "Case Studies",
                "category_slug": "case-studies", "sources": []}
        run = run_cells.CellRun(cell)
        self.assertEqual(run.fetch_outcomes, {})
        self.assertEqual(run.adjudications, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
