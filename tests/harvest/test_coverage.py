#!/usr/bin/env python3
"""test_coverage.py — coverage targets, gap ranking, and the adaptive scheduler.

The property that matters most: coverage targets are HINTS. The scheduler changes
WHERE it looks, never WHAT is accepted — so the acceptance thresholds are
asserted identical in every round, and an unmet target is asserted to be reported
rather than met by lowering a bar or inventing a facet.

Second: cross-industry is counted and reported but never closes a concrete gap
and never opens a lane of its own. Ten cross-industry records must leave a
healthcare gap and a manufacturing gap exactly where they were.

Run via tests/test_taxonomy_coverage.sh.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import coverage, facets, records, schema, scheduler, urlkey  # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"


def ev(term="hospital", quote="the hospital deployed it"):
    return {"field": "body", "matched_term": term, "quote": quote, "offset": None}


def rec(industry, i, functions=("customer-service-support",),
        use_cases=("search-retrieval",), category="domain-applications",
        secondary=()):
    url = "https://example.com/case/%s-%d" % (industry, i)
    cf = {
        "facets_version": 1,
        "vocabulary_versions": facets.vocabulary_versions(),
        "classification_state": "resolved",
        "industry": {"primary": industry, "secondary": list(secondary),
                     "confidence": 0.9, "evidence": [ev()]},
        "business_functions": [{"slug": s, "confidence": 0.7, "evidence": [ev(term=s)]}
                               for s in functions],
        "use_case_types": [{"slug": s, "confidence": 0.7, "evidence": [ev(term=s)]}
                           for s in use_cases],
    }
    return records.make_full_record(
        record_id=urlkey.record_id("cases", url), content_id=urlkey.content_id(url),
        topic_slug="cases", category_slug=category,
        cell_id="cases__" + category, identity_url=url, target_url=url,
        harvest_run_id=RUN, source_id="s", source_adapter="feed",
        discovered_at=NOW, case_facets=cf)


def gap_for(rows, axis, slug):
    return next(r for r in rows if r["axis"] == axis and r["slug"] == slug)


class TestTierTargets(unittest.TestCase):
    def test_priority_standard_record_only(self):
        self.assertEqual(facets.target_min("industry", "healthcare-life-sciences"), 3)
        self.assertEqual(facets.target_min("industry", "media-entertainment"), 2)
        self.assertEqual(facets.target_min("industry", "cross-industry"), 0)
        self.assertEqual(facets.target_min("business_function", "knowledge-management"), 3)
        self.assertEqual(facets.target_min("use_case_type", "customer-interaction"), 3)
        self.assertEqual(facets.target_min("use_case_type", "conversational-assistant"), 2)

    def test_axis_target_rows_cover_every_value(self):
        rows = coverage.axis_targets([])
        self.assertEqual(len(rows), 18 + 19 + 22)
        for axis, n in (("industry", 18), ("business_function", 19), ("use_case_type", 22)):
            self.assertEqual(sum(1 for r in rows if r["axis"] == axis), n)

    def test_observed_counts_include_secondary_industries(self):
        recs = [rec("manufacturing-industrial", 1, secondary=["retail-cpg"])]
        obs = coverage.observed_counts(recs)
        self.assertEqual(obs["industry"]["manufacturing-industrial"], 1)
        self.assertEqual(obs["industry"]["retail-cpg"], 1)


class TestCrossIndustryNeverClosesAGap(unittest.TestCase):
    def test_ten_cross_industry_records_leave_both_gaps_unchanged(self):
        before = coverage.axis_targets([])
        h0 = gap_for(before, "industry", "healthcare-life-sciences")["gap"]
        m0 = gap_for(before, "industry", "manufacturing-industrial")["gap"]
        self.assertEqual((h0, m0), (3, 3))

        recs = [rec("cross-industry", i) for i in range(10)]
        after = coverage.axis_targets(recs)
        self.assertEqual(gap_for(after, "industry", "healthcare-life-sciences")["gap"], h0)
        self.assertEqual(gap_for(after, "industry", "manufacturing-industrial")["gap"], m0)

    def test_cross_industry_is_still_counted_and_reported(self):
        recs = [rec("cross-industry", i) for i in range(10)]
        row = gap_for(coverage.axis_targets(recs), "industry", "cross-industry")
        self.assertEqual(row["observed"], 10)
        self.assertEqual(row["target_min"], 0)
        self.assertFalse(row["counts_toward_gap"])

    def test_no_cross_industry_or_sentinel_gap_lane_is_ever_scheduled(self):
        s = scheduler.Scheduler()
        credible = {slug: ["some-source"] for slug in facets.slugs("industry")}
        lanes, _ = s.plan_round(2, credible_sources=credible, max_lanes=99)
        ids = [l["lane_id"] for l in lanes]
        self.assertNotIn("gap__industry__cross-industry", ids)
        self.assertNotIn("gap__industry__other-unclear", ids)
        for lid in ids:
            self.assertNotIn("cross-industry", lid)
            self.assertNotIn("other-unclear", lid)

    def test_record_only_values_are_excluded_from_ranking(self):
        rows = coverage.axis_targets([])
        ranked = coverage.rank_gaps(rows, credible_sources={"technology-software": ["s"]})
        self.assertFalse(any(r["slug"] == "technology-software" for r in ranked))


class TestSevenFactorRanking(unittest.TestCase):
    def _rank(self, **stats):
        rows = coverage.axis_targets([])
        credible = {r["slug"]: ["s"] for r in rows}
        return coverage.rank_gaps(rows, lane_stats=stats, credible_sources=credible)

    def test_all_seven_factors_are_present(self):
        ranked = self._rank()
        self.assertTrue(ranked)
        self.assertEqual(set(ranked[0]["factors"]), set(coverage.GAP_FACTORS))

    def test_priority_outranks_standard_all_else_equal(self):
        ranked = self._rank()
        by_slug = {r["slug"]: r["rank_score"] for r in ranked}
        self.assertGreater(by_slug["healthcare-life-sciences"],
                           by_slug["media-entertainment"])

    def test_duplicates_and_quality_rejections_are_penalties(self):
        clean = self._rank()
        dirty = self._rank(**{"healthcare-life-sciences":
                              {"duplicate_rate": 1.0, "quality_rejection_rate": 1.0}})
        self.assertGreater(
            next(r for r in clean if r["slug"] == "healthcare-life-sciences")["rank_score"],
            next(r for r in dirty if r["slug"] == "healthcare-life-sciences")["rank_score"],
            "ranking on remaining gap alone would chase an unproductive value forever")

    def test_no_credible_source_is_reported_not_invented(self):
        rows = coverage.axis_targets([])
        ranked = coverage.rank_gaps(rows, credible_sources={})
        self.assertTrue(ranked)
        self.assertTrue(all(r["not_opened_reason"] == "no_credible_source" for r in ranked))

    def test_a_met_target_produces_no_gap(self):
        recs = [rec("healthcare-life-sciences", i) for i in range(3)]
        rows = coverage.axis_targets(recs)
        self.assertEqual(gap_for(rows, "industry", "healthcare-life-sciences")["gap"], 0)
        ranked = coverage.rank_gaps(rows, credible_sources={"healthcare-life-sciences": ["s"]})
        self.assertFalse(any(r["slug"] == "healthcare-life-sciences" for r in ranked))


class TestThresholdsNeverMove(unittest.TestCase):
    def test_thresholds_are_identical_in_every_round(self):
        s = scheduler.Scheduler(clock=lambda: 0.0)
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [rec("healthcare-life-sciences", n)],
                                "new_accepted": 1, "duplicate_rate": 0.1},
              credible_sources=credible)
        seen = [r["thresholds"] for r in s.rounds]
        self.assertGreater(len(seen), 1)
        for t in seen:
            self.assertEqual(t, seen[0])
        self.assertEqual(seen[0], scheduler.load_thresholds())

    def test_the_scheduler_never_writes_a_threshold(self):
        import inspect
        text = inspect.getsource(scheduler)
        for forbidden in ("min_relevance =", "min_quality =", "accept_composite =",
                          'thresholds["min_relevance"]', "accept_composite\"] ="):
            self.assertNotIn(forbidden, text)

    def test_an_unmet_target_is_reported_as_unmet(self):
        recs = [rec("healthcare-life-sciences", 1)]           # 1 of 3
        row = gap_for(coverage.axis_targets(recs), "industry", "healthcare-life-sciences")
        self.assertEqual(row["observed"], 1)
        self.assertEqual(row["gap"], 2)


class TestStopConditions(unittest.TestCase):
    def _sched(self):
        return scheduler.Scheduler(clock=lambda: 0.0)

    def test_round_one_is_the_configured_cells_only(self):
        s = self._sched()
        lanes, skipped = s.plan_round(1)
        self.assertEqual(len(lanes), 12)
        self.assertTrue(all(l["kind"] == "configured_cell" for l in lanes))
        self.assertFalse(any(l["lane_id"].startswith("gap__") for l in lanes))
        self.assertEqual(skipped, [])

    def test_max_rounds(self):
        s = self._sched()
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5, "duplicate_rate": 0.0},
              credible_sources=credible)
        self.assertEqual(s.rounds[-1]["stop_reason"], "max_rounds")
        self.assertEqual(len(s.rounds), s.max_rounds)

    def test_no_progress(self):
        s = self._sched()
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [], "new_accepted": 0, "duplicate_rate": 0.0},
              credible_sources=credible)
        self.assertEqual(s.rounds[-1]["stop_reason"], "no_progress")
        self.assertEqual(len(s.rounds), 2)

    def test_duplicate_rate(self):
        s = self._sched()
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5, "duplicate_rate": 0.95},
              credible_sources=credible)
        self.assertEqual(s.rounds[-1]["stop_reason"], "duplicate_rate")

    def test_budget_exhausted(self):
        s = self._sched()
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5,
                                "duplicate_rate": 0.0, "budget_exhausted": n >= 2},
              credible_sources=credible)
        self.assertEqual(s.rounds[-1]["stop_reason"], "budget_exhausted")

    def test_no_credible_source_stops_and_is_named(self):
        s = self._sched()
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5, "duplicate_rate": 0.0},
              credible_sources={})
        self.assertEqual(s.rounds[-1]["stop_reason"], "no_credible_source")
        self.assertTrue(s.rounds[-1]["_skipped"])
        self.assertTrue(all(x["not_opened_reason"] == "no_credible_source"
                            for x in s.rounds[-1]["_skipped"]))

    def test_all_targets_met(self):
        s = self._sched()
        s.never_gap = set(facets.slugs("industry")) | set(
            facets.slugs("business_function")) | set(facets.slugs("use_case_type"))
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5, "duplicate_rate": 0.0},
              credible_sources={})
        self.assertEqual(s.rounds[-1]["stop_reason"], "all_targets_met")

    def test_every_stop_reason_is_in_the_manifest_enum(self):
        allowed = set(scheduler.STOP_REASONS)
        manifest = schema.load_schema("run_manifest.v1.json")
        enum = set(manifest["properties"]["rounds"]["items"]["properties"]
                   ["stop_reason"]["enum"]) - {None}
        self.assertEqual(allowed, enum)


class TestManifestAndReportShapes(unittest.TestCase):
    def test_rounds_validate_inside_a_run_manifest(self):
        s = scheduler.Scheduler(clock=lambda: 0.0)
        credible = {slug: ["s"] for slug in facets.slugs("industry")}
        s.run(lambda n, lanes: {"records": [], "new_accepted": 5, "duplicate_rate": 0.1},
              credible_sources=credible)
        man = {
            "schema_version": 1, "harvest_run_id": RUN, "mode": "harvest",
            "started_at": NOW, "finished_at": NOW,
            "environment": {"python_version": "3.13.9", "jsonschema_version": "4.26.0",
                            "platform": "win32"},
            "config": {}, "source_preflight": [], "cells": [],
            "classification_decisions": [], "publication_eligible": True,
            "rounds": s.manifest_rounds(),
            "coverage": [coverage.category_coverage([], "cases", "domain-applications",
                                                    with_axis_targets=False)],
            "lane_quality": [{"lane_id": "gap__industry__retail-cpg",
                              "axis": "industry", "slug": "retail-cpg",
                              "candidates": 5, "accepted": 2}],
            "request_accounting": {"source_fetch_owners": 1, "http_attempts": 3},
        }
        self.assertEqual(schema.validate(man, "run_manifest.v1.json"), [])

    def test_the_five_states_are_counted_separately_in_the_report(self):
        recs = [rec("healthcare-life-sciences", i) for i in range(2)]
        doc = coverage.build_coverage_report(recs, RUN, NOW, thresholds_constant=True)
        self.assertEqual(schema.validate(doc, "coverage_report.v1.json"), [])
        states = doc["by_category"][0]["states"]
        self.assertEqual(set(states), {"facet_complete", "facet_partial", "unresolved",
                                       "not_enriched", "unmapped_legacy_value"})
        self.assertEqual(sum(states.values()),
                         doc["by_category"][0]["applicable_full_records"])

    def test_case_studies_coverage_is_reported_but_not_gated(self):
        recs = [rec("retail-cpg", i, category="case-studies") for i in range(2)]
        doc = coverage.build_coverage_report(recs, RUN, NOW)
        row = doc["by_category"][0]
        self.assertEqual(row["category_slug"], "case-studies")
        self.assertFalse(row["gated"])
        self.assertEqual(row["states"]["facet_complete"], 2)
        self.assertEqual(row["publication_withheld_records"], 0)

    def test_a_manifest_without_the_new_keys_is_still_valid(self):
        man = {
            "schema_version": 1, "harvest_run_id": RUN, "mode": "smoke",
            "started_at": NOW, "finished_at": NOW,
            "environment": {"python_version": "3.13.9", "jsonschema_version": "4.26.0",
                            "platform": "win32"},
            "config": {}, "source_preflight": [], "cells": [],
            "classification_decisions": [], "publication_eligible": False,
        }
        self.assertEqual(schema.validate(man, "run_manifest.v1.json"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
