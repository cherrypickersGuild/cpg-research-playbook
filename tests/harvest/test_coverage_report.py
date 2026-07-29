#!/usr/bin/env python3
"""test_coverage_report.py — coverage report construction and persistence (S5-4).

This checkpoint is wiring: `coverage.py` and `facets.py` do the counting and stay
byte-unchanged. What these tests protect is the wiring's honesty.

  * THE COUNTS ARE THE SAME COUNTS. Every `by_category.states` block must agree
    with `facets.count_states` over the same scoped set, and the five states must
    sum EXACTLY to `applicable_full_records`. A coverage number that disagrees
    with the records is worse than no number.
  * FIVE STATES, COUNTED SEPARATELY, ALWAYS. `not_enriched` ("never tried") is not
    `unresolved` ("looked, found nothing"), and `unmapped_legacy_value` outranks
    both — it is the fact a reviewer has to act on.
  * A POINTER IS NOT A RECORD. `cross_reference` rows are excluded from every
    count; counting one would double-count the record it points at.
  * CF-11 IS PROTECTED. An empty `industry.secondary` is deliberate — the
    committed definition means deployment context, never corporate portfolio — so
    it must never surface as a gap, a deficiency, or a withheld record. If the
    report made an empty `secondary` look like a defect, it would create pressure
    to manufacture exactly the findings CF-11 exists to prevent.
  * ORDER IS A FUNCTION OF CONTENT. The committed builder sorts `by_category` but
    projects per-record rows in input order, so the wiring sorts first. Shuffled
    input must yield byte-identical bytes.

S5-1's atomicity is reused, not re-proved. Offline and temp-rooted; no network,
no cell execution. Run via tests/test_taxonomy_coverage_report.sh.
"""
import copy
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, coverage, facets, records, schema, urlkey  # noqa: E402

RUN = "20260730T120000Z-4242"
NOW = "2026-07-30T12:00:00Z"
GATED = ("cases", "domain-applications")

VOCAB = {"industries": 1, "business_functions": 1, "use_case_types": 1}


def facet_payload(state, *, industry=None, secondary=None, functions=(),
                  unresolved=()):
    """A schema-valid case_facets payload in a chosen classification state."""
    return {
        "facets_version": 1,
        "vocabulary_versions": dict(VOCAB),
        "classification_state": state,
        "industry": {
            "primary": industry,
            "secondary": list(secondary or []),
            "confidence": 0.5 if industry else None,
            "evidence": ([{"field": "summary", "matched_term": "hospital",
                           "quote": "a hospital team"}] if industry else []),
        },
        "business_functions": [
            {"slug": slug, "confidence": 0.5,
             "evidence": [{"field": "summary", "matched_term": slug,
                           "quote": "a %s mention" % slug}]}
            for slug in functions],
        "use_case_types": [],
        "unresolved": list(unresolved),
    }


RESOLVED = facet_payload("resolved", industry="healthcare-life-sciences",
                         functions=("customer-service-support",))
PARTIAL = facet_payload("unresolved", industry="healthcare-life-sciences")
EMPTY = facet_payload("unresolved")
LEGACY = facet_payload("unresolved", unresolved=[
    {"axis": "industry", "state": "unmapped_legacy_value",
     "detail": "legacy value 'Hospitals' has no reviewed mapping"}])


def full_record(url, *, topic="cases", category="domain-applications",
                case_facets=None):
    return records.make_full_record(
        record_id=urlkey.record_id(topic, url),
        content_id=urlkey.content_id(url),
        topic_slug=topic, category_slug=category,
        cell_id="%s__%s" % (topic, category),
        identity_url=url, target_url=url,
        harvest_run_id=RUN, source_id="aws-ml-blog", source_adapter="feed",
        title="A title", summary="A summary", discovered_at=NOW,
        case_facets=copy.deepcopy(case_facets) if case_facets else None)


def cross_ref(url, *, topic="cases", category="domain-applications"):
    return records.make_cross_reference(
        record_id=urlkey.record_id(topic, url),
        content_id=urlkey.content_id(url),
        identity_url=url, topic_slug=topic, category_slug=category,
        duplicate_of=urlkey.record_id("research-and-models", url),
        owner_topic="research-and-models", reason="owned elsewhere",
        harvest_run_id=RUN, discovered_at=NOW)


def report(recs, **over):
    kwargs = dict(harvest_run_id=RUN, generated_at=NOW)
    kwargs.update(over)
    return artifacts.build_coverage_report(recs, **kwargs)


def corpus():
    """One record in each of the five states, plus a pointer."""
    return [
        full_record("https://example.com/complete/", case_facets=RESOLVED),
        full_record("https://example.com/partial/", case_facets=PARTIAL),
        full_record("https://example.com/empty/", case_facets=EMPTY),
        full_record("https://example.com/legacy/", case_facets=LEGACY),
        full_record("https://example.com/never/", topic="research-and-models",
                    category="papers"),
        cross_ref("https://example.com/pointer/"),
    ]


def row_for(doc, topic_slug, category_slug):
    for row in doc["by_category"]:
        if (row["topic_slug"], row["category_slug"]) == (topic_slug, category_slug):
            return row
    return None


class TempRootCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_coverage_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)


# ------------------------------------------------------------------- document
class TestReportDocument(unittest.TestCase):
    def test_it_validates(self):
        self.assertEqual(schema.validate(report(corpus()),
                                         "coverage_report.v1.json"), [])

    def test_every_required_key_is_present(self):
        doc = report(corpus())
        for key in schema.load_schema("coverage_report.v1.json")["required"]:
            self.assertIn(key, doc, key)

    def test_an_empty_record_set_still_validates(self):
        doc = report([])
        self.assertEqual(schema.validate(doc, "coverage_report.v1.json"), [])
        self.assertEqual(doc["by_category"], [])

    def test_the_vocabulary_versions_come_from_facets(self):
        self.assertEqual(report(corpus())["vocabulary_versions"],
                         facets.vocabulary_versions())

    def test_thresholds_constant_is_reported_not_derived(self):
        # S5-4 must not recalibrate or reinterpret S4-4's provisional numbers.
        for value in (True, False, None):
            self.assertEqual(report(corpus(), thresholds_constant=value)
                             ["thresholds_constant"], value)

    def test_by_category_is_sorted(self):
        keys = [(r["topic_slug"], r["category_slug"])
                for r in report(corpus())["by_category"]]
        self.assertEqual(keys, sorted(keys))

    def test_a_malformed_record_is_refused_before_counting(self):
        bad = full_record("https://example.com/a/", case_facets=RESOLVED)
        del bad["case_facets"]
        with self.assertRaises(artifacts.ArtifactError) as caught:
            report([bad])
        self.assertIn(bad["record_id"], str(caught.exception))

    def test_the_records_projection_can_be_omitted(self):
        doc = report(corpus(), include_records=False)
        self.assertNotIn("records", doc)
        self.assertEqual(schema.validate(doc, "coverage_report.v1.json"), [])


# --------------------------------------------------------------------- counts
class TestCounts(unittest.TestCase):
    def test_states_agree_with_facets_count_states(self):
        recs = corpus()
        doc = report(recs)
        for row in doc["by_category"]:
            scoped = [r for r in recs
                      if facets.is_applicable(r)
                      and r.get("topic") == row["topic_slug"]
                      and r.get("primary_category") == row["category_slug"]]
            tally = facets.count_states(scoped)
            self.assertEqual(row["states"], tally["counts"])
            self.assertEqual(row["applicable_full_records"],
                             tally["applicable_full_records"])

    def test_the_five_states_sum_exactly_to_the_applicable_population(self):
        for row in report(corpus())["by_category"]:
            self.assertEqual(sum(row["states"].values()),
                             row["applicable_full_records"])

    def test_a_cross_reference_is_excluded_from_every_count(self):
        with_pointer = report(corpus())
        without = report([r for r in corpus()
                          if r.get("record_type") != "cross_reference"])
        self.assertEqual(with_pointer["by_category"], without["by_category"])

    def test_a_pointer_never_appears_in_the_records_projection(self):
        doc = report(corpus())
        ids = {r["record_id"] for r in doc["records"]}
        pointer = cross_ref("https://example.com/pointer/")
        self.assertNotIn(pointer["record_id"], ids)

    def test_eligible_plus_withheld_equals_the_applicable_population(self):
        for row in report(corpus())["by_category"]:
            self.assertEqual(row["publication_eligible_records"]
                             + row["publication_withheld_records"],
                             row["applicable_full_records"])

    def test_only_the_committed_cell_is_gated(self):
        for row in report(corpus())["by_category"]:
            expected = (row["topic_slug"], row["category_slug"]) in facets.FACET_GATED_CELLS
            self.assertEqual(row["gated"], expected)
        self.assertIn(GATED, facets.FACET_GATED_CELLS)


# --------------------------------------------------------------------- states
class TestReportingStates(unittest.TestCase):
    def state_of(self, doc, url, topic="cases"):
        target = urlkey.record_id(topic, url)
        for row in doc["records"]:
            if row["record_id"] == target:
                return row["reporting_state"]
        return None

    def test_each_state_is_reported_from_facets_not_recomputed(self):
        recs = corpus()
        doc = report(recs)
        by_id = {r["record_id"]: r for r in recs}
        for row in doc["records"]:
            self.assertEqual(row["reporting_state"],
                             facets.reporting_state(by_id[row["record_id"]]))

    def test_a_resolved_record_is_facet_complete(self):
        doc = report(corpus())
        self.assertEqual(self.state_of(doc, "https://example.com/complete/"),
                         "facet_complete")

    def test_a_partially_populated_record_is_facet_partial(self):
        doc = report(corpus())
        self.assertEqual(self.state_of(doc, "https://example.com/partial/"),
                         "facet_partial")

    def test_an_empty_payload_is_unresolved(self):
        doc = report(corpus())
        self.assertEqual(self.state_of(doc, "https://example.com/empty/"),
                         "unresolved")

    def test_not_enriched_is_distinct_from_unresolved(self):
        # "never tried" and "looked, found nothing" are different facts.
        doc = report(corpus())
        self.assertEqual(self.state_of(doc, "https://example.com/never/",
                                       topic="research-and-models"),
                         "not_enriched")
        self.assertEqual(self.state_of(doc, "https://example.com/empty/"),
                         "unresolved")
        gated_row = row_for(doc, *GATED)
        self.assertEqual(gated_row["states"]["unresolved"], 1)
        self.assertEqual(gated_row["states"]["not_enriched"], 0)

    def test_an_unmapped_legacy_value_outranks_facet_partial(self):
        doc = report(corpus())
        self.assertEqual(self.state_of(doc, "https://example.com/legacy/"),
                         "unmapped_legacy_value")

    def test_a_not_applicable_record_has_no_state_row(self):
        self.assertIsNone(facets.reporting_state(
            cross_ref("https://example.com/pointer/")))

    def test_only_facet_complete_is_eligible_in_the_gated_cell(self):
        doc = report(corpus())
        for row in doc["records"]:
            if (row["topic_slug"], row["category_slug"]) != GATED:
                continue
            self.assertEqual(row["publication_eligible"],
                             row["reporting_state"] == "facet_complete")

    def test_a_report_only_cell_is_never_withheld_by_facets(self):
        recs = [full_record("https://example.com/cs/", category="case-studies",
                            case_facets=EMPTY)]
        doc = report(recs)
        row = row_for(doc, "cases", "case-studies")
        self.assertFalse(row["gated"])
        self.assertEqual(row["publication_withheld_records"], 0)

    def test_withheld_is_not_rejected(self):
        doc = report(corpus())
        for row in doc["records"]:
            if row["publication_eligible"]:
                continue
            self.assertIsNotNone(row["withheld_reason"])
            self.assertIn(row["withheld_reason"], facets.REPORTING_STATES)


# ------------------------------------------------------------- CF-11 protection
class TestCF11SecondaryIndustries(unittest.TestCase):
    def test_every_record_in_the_corpus_has_an_empty_secondary(self):
        # The premise of the rest of this class.
        for rec in corpus():
            cf = rec.get("case_facets")
            if isinstance(cf, dict):
                self.assertEqual(cf["industry"]["secondary"], [])

    def test_an_empty_secondary_produces_no_gap_row_of_its_own(self):
        # Gaps are per axis VALUE, never per "secondary is empty". Nothing in the
        # report may name secondary as a deficiency.
        doc = report(corpus())
        blob = json.dumps(doc)
        self.assertNotIn("secondary", blob)

    def test_an_empty_secondary_does_not_change_any_count(self):
        base = report(corpus())
        # Adding a secondary would ADD observations; removing the (already empty)
        # list must change nothing. Proven by equality with an explicit empty.
        recs = corpus()
        for rec in recs:
            cf = rec.get("case_facets")
            if isinstance(cf, dict):
                cf["industry"]["secondary"] = []
        self.assertEqual(report(recs)["by_category"], base["by_category"])

    def test_an_empty_secondary_never_withholds_a_record(self):
        doc = report(corpus())
        for row in doc["records"]:
            if row["reporting_state"] == "facet_complete":
                self.assertTrue(row["publication_eligible"],
                                "an empty secondary must not withhold a record")

    def test_a_facet_complete_record_with_no_secondary_is_still_complete(self):
        doc = report([full_record("https://example.com/c/", case_facets=RESOLVED)])
        row = row_for(doc, *GATED)
        self.assertEqual(row["states"]["facet_complete"], 1)
        self.assertEqual(row["publication_eligible_records"], 1)
        self.assertEqual(row["publication_withheld_records"], 0)

    def test_a_populated_secondary_would_be_counted_if_it_ever_existed(self):
        # CF-11 leaves secondary empty by DESIGN, not because the counter is
        # broken. This pins that the machinery is live, so the design decision
        # stays visible rather than becoming an accident.
        payload = facet_payload("resolved", industry="healthcare-life-sciences",
                                secondary=["financial-services-insurance"],
                                functions=("customer-service-support",))
        doc = report([full_record("https://example.com/s/", case_facets=payload)])
        row = row_for(doc, *GATED)
        observed = {(a["axis"], a["slug"]): a["observed"] for a in row["axis_targets"]}
        self.assertEqual(observed[("industry", "financial-services-insurance")], 1)
        self.assertEqual(observed[("industry", "healthcare-life-sciences")], 1)


# ---------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def test_shuffled_records_yield_identical_bytes(self):
        recs = corpus()
        expected = artifacts.serialize(report(recs))
        rng = random.Random(20260730)
        for _ in range(5):
            shuffled = list(recs)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(report(shuffled)), expected)

    def test_repeated_construction_is_byte_identical(self):
        self.assertEqual(artifacts.serialize(report(corpus())),
                         artifacts.serialize(report(corpus())))

    def test_the_records_projection_is_ordered_by_the_committed_key(self):
        doc = report(corpus())
        ordered = records.sort_records(
            [r for r in corpus() if facets.is_applicable(r)])
        self.assertEqual([r["record_id"] for r in doc["records"]],
                         [r["record_id"] for r in ordered])

    def test_axis_target_rows_are_stable(self):
        first = report(corpus())["by_category"][0]["axis_targets"]
        second = report(list(reversed(corpus())))["by_category"][0]["axis_targets"]
        self.assertEqual(first, second)


# --------------------------------------------------------------- persistence
class TestPersistence(TempRootCase):
    def test_the_path_follows_the_committed_layout(self):
        self.assertEqual(artifacts.coverage_report_path(self.root, RUN),
                         os.path.join(self.root, "runs", RUN, "coverage.json"))

    def test_it_round_trips_through_the_shared_writer(self):
        doc = report(corpus())
        path = artifacts.coverage_report_path(self.root, RUN)
        artifacts.write_coverage_report(path, doc)
        with open(path, "rb") as fh:
            written = json.loads(fh.read().decode("utf-8"))
        self.assertEqual(written, doc)
        self.assertEqual(schema.validate(written, "coverage_report.v1.json"), [])

    def test_an_invalid_report_writes_no_file(self):
        doc = report(corpus())
        doc["extra_field"] = "nope"
        path = artifacts.coverage_report_path(self.root, RUN)
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_coverage_report(path, doc)
        self.assertFalse(os.path.exists(path))

    def test_two_writes_are_byte_identical(self):
        doc = report(corpus())
        one = os.path.join(self.root, "one.json")
        two = os.path.join(self.root, "two.json")
        artifacts.write_coverage_report(one, doc)
        artifacts.write_coverage_report(two, doc)
        with open(one, "rb") as a, open(two, "rb") as b:
            self.assertEqual(a.read(), b.read())


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_coverage_and_facets_are_byte_unchanged(self):
        # This checkpoint is wiring. If either module moved, it is not wiring.
        result = subprocess.run(
            ["git", "diff", "--exit-code", "--",
             "src/harvest/coverage.py", "src/harvest/facets.py"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         "coverage.py or facets.py was modified:\n" + result.stdout)

    def test_the_counting_is_delegated_not_reimplemented(self):
        doc = report(corpus())
        direct = coverage.build_coverage_report(
            records.sort_records([r for r in corpus()]), RUN, NOW)
        self.assertEqual(doc, direct)

    def test_no_threshold_or_score_is_computed_here(self):
        import inspect
        src = inspect.getsource(artifacts.build_coverage_report)
        for owned_elsewhere in ("min_relevance", "accept_composite", "min_quality",
                                "load_policy", "SATURATION"):
            self.assertNotIn(owned_elsewhere, src)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("build_coverage_report", "write_coverage_report",
                     "coverage_report_path"):
            self.assertTrue(hasattr(artifacts, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
