#!/usr/bin/env python3
"""test_facet_states.py — the five reporting states and derived eligibility.

The properties that matter:

  * five MUTUALLY EXCLUSIVE, EXHAUSTIVE states, so the counts always sum to the
    applicable population and no record is ever counted twice;
  * unmapped_legacy_value is FIRST in precedence and never collapses into
    unresolved — a legacy value with no reviewed mapping is a fact a reviewer
    must act on, not a shrug;
  * publication eligibility is DERIVED from the complete record and is never a
    persisted record flag;
  * a cases__domain-applications cross_reference row is still valid (the D1
    regression: a root-level conditional would have made it unsatisfiable).

Run via tests/test_taxonomy_facet_states.sh.
"""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))

from src.harvest import coverage, facets, records, schema, urlkey   # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"
IU = "https://example.com/case/x"
UNMAPPED = "superapp (mobility, delivery, fintech)"


def ev(field="body", term="hospital", quote="the hospital deployed it"):
    return {"field": field, "matched_term": term, "quote": quote, "offset": None}


def facets_payload(state="resolved", industry="healthcare-life-sciences",
                   functions=("customer-service-support",), use_cases=(), unresolved=None):
    return {
        "facets_version": 1,
        "vocabulary_versions": facets.vocabulary_versions(),
        "classification_state": state,
        "industry": ({"primary": industry, "secondary": [], "confidence": 0.9,
                      "evidence": [ev()]} if industry else
                     {"primary": None, "secondary": [], "confidence": None, "evidence": []}),
        "business_functions": [{"slug": s, "confidence": 0.7,
                                "evidence": [ev(term=s, quote="evidence for " + s)]}
                               for s in functions],
        "use_case_types": [{"slug": s, "confidence": 0.7,
                            "evidence": [ev(term=s, quote="evidence for " + s)]}
                           for s in use_cases],
        **({"unresolved": unresolved} if unresolved else {}),
    }


def rec(topic="cases", category="domain-applications", case_facets=None,
        rid=None, migrated_legacy=None):
    url = IU + (rid or "")
    r = records.make_full_record(
        record_id=urlkey.record_id(topic, url), content_id=urlkey.content_id(url),
        topic_slug=topic, category_slug=category, cell_id="%s__%s" % (topic, category),
        identity_url=url, target_url=url, harvest_run_id=RUN,
        source_id="s", source_adapter="feed", discovered_at=NOW,
        case_facets=case_facets)
    if migrated_legacy is not None:
        r["provenance"]["migration"] = {"adapter": "ax_cases", "migrated_at": NOW,
                                        "assumptions": []}
        r["provenance"]["raw"] = {"industry": migrated_legacy}
    return r


def cross_ref(category="domain-applications"):
    return records.make_cross_reference(
        record_id=urlkey.record_id("cases", IU), content_id=urlkey.content_id(IU),
        identity_url=IU, topic_slug="cases", category_slug=category,
        duplicate_of=urlkey.record_id("discourse", IU), owner_topic="discourse",
        reason="owned by discourse", harvest_run_id=RUN, discovered_at=NOW)


# One record in each of the five states, for the partition assertions.
def five_records():
    complete = rec(rid="1", case_facets=facets_payload())
    partial = rec(rid="2", case_facets=facets_payload(
        state="unresolved", industry="retail-cpg", functions=(),
        unresolved=[{"axis": "use_case_type", "state": "insufficient_evidence",
                     "detail": "only a title was available"}]))
    unresolved = rec(rid="3", case_facets=facets_payload(
        state="unresolved", industry=None, functions=(),
        unresolved=[{"axis": "industry", "state": "other-unclear",
                     "detail": "the sector resists placement"}]))
    not_enriched = rec(rid="4")
    unmapped = rec(rid="5", migrated_legacy=UNMAPPED, case_facets=facets_payload(
        state="unresolved", industry=None, functions=(),
        unresolved=[{"axis": "industry", "state": "unmapped_legacy_value",
                     "term": UNMAPPED, "detail": "no reviewed mapping exists"}]))
    return [complete, partial, unresolved, not_enriched, unmapped]


class TestFourUnresolvedStatesAreDistinct(unittest.TestCase):
    def test_the_enum_carries_all_four(self):
        self.assertEqual(set(facets.UNRESOLVED_STATES),
                         {"other-unclear", "unmapped_legacy_value",
                          "insufficient_evidence", "not_applicable"})

    def test_each_validates_and_is_kept_separate(self):
        for state in facets.UNRESOLVED_STATES:
            cf = facets_payload(state="unresolved", industry=None, functions=(),
                                unresolved=[{"axis": "industry", "state": state,
                                             "term": None, "detail": "a reason"}])
            r = rec(case_facets=cf)
            self.assertEqual(schema.validate(r, "record.v1.json"), [], state)


class TestPrecedenceIsTotal(unittest.TestCase):
    def test_the_five_states_in_order(self):
        complete, partial, unresolved, not_enriched, unmapped = five_records()
        self.assertEqual(coverage.reporting_state(complete), "facet_complete")
        self.assertEqual(coverage.reporting_state(partial), "facet_partial")
        self.assertEqual(coverage.reporting_state(unresolved), "unresolved")
        self.assertEqual(coverage.reporting_state(not_enriched), "not_enriched")
        self.assertEqual(coverage.reporting_state(unmapped), "unmapped_legacy_value")

    def test_null_case_facets_is_not_enriched(self):
        r = rec()
        r["case_facets"] = None
        self.assertEqual(coverage.reporting_state(r), "not_enriched")

    def test_unmapped_outranks_partial(self):
        # T2: a record whose functions ARE populated but whose industry came from
        # an unmapped legacy string must still report unmapped_legacy_value.
        cf = facets_payload(state="unresolved", industry=None,
                            functions=("marketing",),
                            unresolved=[{"axis": "industry",
                                         "state": "unmapped_legacy_value",
                                         "term": UNMAPPED, "detail": "no mapping"}])
        r = rec(migrated_legacy=UNMAPPED, case_facets=cf)
        self.assertTrue(facets.any_axis_populated(cf))
        self.assertEqual(coverage.reporting_state(r), "unmapped_legacy_value")

    def test_unmapped_outranks_not_enriched_is_impossible_and_that_is_the_point(self):
        # A migrated record cannot hide an unmapped value by omitting case_facets:
        # check_facets refuses it. Without facets present the state IS
        # not_enriched, which is exactly why that refusal exists.
        from check_facets import validate_record_facets
        r = rec(migrated_legacy=UNMAPPED)
        self.assertEqual(coverage.reporting_state(r), "not_enriched")
        self.assertTrue(validate_record_facets(r))

    def test_every_applicable_record_gets_exactly_one_state(self):
        for r in five_records():
            state = coverage.reporting_state(r)
            self.assertIn(state, facets.REPORTING_STATES)
            self.assertIsNotNone(state)

    def test_state_is_deterministic(self):
        r = five_records()[4]
        self.assertEqual({coverage.reporting_state(copy.deepcopy(r)) for _ in range(20)},
                         {"unmapped_legacy_value"})


class TestPartitionAndExclusion(unittest.TestCase):
    def test_t5_counts_sum_exactly_to_applicable_full_records(self):
        recs = five_records()
        tally = facets.count_states(recs)
        self.assertEqual(tally["applicable_full_records"], 5)
        self.assertEqual(sum(tally["counts"].values()), 5)
        self.assertEqual(tally["counts"],
                         {"facet_complete": 1, "facet_partial": 1, "unresolved": 1,
                          "not_enriched": 1, "unmapped_legacy_value": 1})

    def test_t6_cross_references_are_excluded_from_every_count(self):
        recs = five_records()
        before = facets.count_states(recs)
        with_refs = recs + [cross_ref() for _ in range(4)]
        after = facets.count_states(with_refs)
        self.assertEqual(before, after)
        for row in with_refs[len(recs):]:
            self.assertIsNone(coverage.reporting_state(row))

    def test_t1_and_t2_unmapped_is_counted_only_once_and_not_as_unresolved(self):
        base = five_records()[:4]                       # no unmapped record yet
        baseline = facets.count_states(base)["counts"]
        unmapped = five_records()[4]
        after = facets.count_states(base + [unmapped])["counts"]

        self.assertEqual(after["unmapped_legacy_value"],
                         baseline["unmapped_legacy_value"] + 1)
        self.assertEqual(after["unresolved"], baseline["unresolved"])
        self.assertEqual(after["facet_partial"], baseline["facet_partial"])
        self.assertEqual(after["not_enriched"], baseline["not_enriched"])
        self.assertEqual(after["facet_complete"], baseline["facet_complete"])

    def test_partition_holds_over_a_large_mixed_population(self):
        recs = []
        for i in range(37):
            recs.extend(r for r in five_records())
            recs.append(cross_ref())
        tally = facets.count_states(recs)
        self.assertEqual(tally["applicable_full_records"], 37 * 5)
        self.assertEqual(sum(tally["counts"].values()), 37 * 5)


class TestPublicationEligibility(unittest.TestCase):
    def test_only_facet_complete_is_eligible_in_domain_applications(self):
        complete, partial, unresolved, not_enriched, unmapped = five_records()
        self.assertTrue(coverage.is_publication_eligible(complete))
        for r in (partial, unresolved, not_enriched, unmapped):
            self.assertFalse(coverage.is_publication_eligible(r),
                             coverage.reporting_state(r))

    def test_t3_an_unmapped_legacy_value_cannot_make_a_record_eligible(self):
        cf = facets_payload(state="unresolved", industry=None, functions=("marketing",),
                            unresolved=[{"axis": "industry",
                                         "state": "unmapped_legacy_value",
                                         "term": UNMAPPED, "detail": "no mapping"}])
        r = rec(migrated_legacy=UNMAPPED, case_facets=cf)
        self.assertFalse(coverage.is_publication_eligible(r))
        self.assertEqual(coverage.withheld_reason(r), "unmapped_legacy_value")

    def test_withheld_is_not_rejected(self):
        r = five_records()[1]
        self.assertFalse(coverage.is_publication_eligible(r))
        self.assertIsNone(r["rejection_reason"])
        self.assertEqual(len(r["record_id"]), 16)
        self.assertEqual(schema.validate(r, "record.v1.json"), [])

    def test_t4_case_studies_are_report_only_and_never_withheld(self):
        for state_kwargs in ({}, {"case_facets": facets_payload(
                state="unresolved", industry=None, functions=(),
                unresolved=[{"axis": "industry", "state": "unmapped_legacy_value",
                             "term": UNMAPPED, "detail": "no mapping"}])}):
            r = rec(category="case-studies", **state_kwargs)
            self.assertTrue(coverage.is_publication_eligible(r))
            self.assertIsNone(coverage.withheld_reason(r))
            self.assertEqual(schema.validate(r, "record.v1.json"), [])

    def test_t4_migration_count_is_unaffected(self):
        # 231 migrated case-studies records, all in the worst facet state, all
        # still valid and all still present: facets never block migration.
        recs = [rec(category="case-studies", rid=str(i), migrated_legacy=UNMAPPED,
                    case_facets=facets_payload(
                        state="unresolved", industry=None, functions=(),
                        unresolved=[{"axis": "industry",
                                     "state": "unmapped_legacy_value",
                                     "term": UNMAPPED, "detail": "no mapping"}]))
                for i in range(231)]
        self.assertEqual(len(recs), 231)
        self.assertTrue(all(coverage.is_publication_eligible(r) for r in recs))
        tally = facets.count_states(recs)
        self.assertEqual(tally["counts"]["unmapped_legacy_value"], 231)
        self.assertEqual(sum(tally["counts"].values()), 231)

    def test_eligibility_is_not_a_persisted_field(self):
        props = schema.load_schema("record.v1.json")["$defs"]["full_record"]["properties"]
        for forbidden in ("publication_eligible", "publication_withheld",
                          "reporting_state", "facet_state"):
            self.assertNotIn(forbidden, props)

    def test_cross_references_are_never_withheld_by_facets(self):
        row = cross_ref()
        self.assertTrue(coverage.is_publication_eligible(row))
        self.assertIsNone(coverage.withheld_reason(row))


def full_branch_errors(record):
    """Validate against #/$defs/full_record directly.

    The document root is a oneOf, so a rejection there reports only "not valid
    under any of the given schemas" and hides WHY. Checking the branch directly
    is what proves the record was rejected for the intended reason rather than
    incidentally.
    """
    import jsonschema
    doc = schema.load_schema("record.v1.json")
    sub = dict(doc["$defs"]["full_record"])
    sub["$defs"] = doc["$defs"]
    v = jsonschema.Draft202012Validator(sub, registry=schema._build_registry())
    return [e.message for e in v.iter_errors(record)]


class TestSchemaApplicability(unittest.TestCase):
    def test_domain_applications_requires_facets(self):
        r = rec()
        self.assertTrue(schema.validate(r, "record.v1.json"))
        branch = full_branch_errors(r)
        self.assertTrue(any("case_facets" in e for e in branch), branch)

    def test_domain_applications_rejects_an_explicit_null(self):
        r = rec()
        r["case_facets"] = None
        self.assertTrue(schema.validate(r, "record.v1.json"))
        self.assertTrue(full_branch_errors(r))

    def test_research_and_discourse_rejection_names_the_facet_key(self):
        bad = rec(topic="discourse", category="community", case_facets=facets_payload())
        branch = full_branch_errors(bad)
        self.assertTrue(branch)
        self.assertTrue(any("null" in e or "case_facets" in e for e in branch), branch)

    def test_d1_regression_a_domain_applications_cross_reference_is_still_valid(self):
        # A root-level conditional would have demanded case_facets on a branch
        # whose closed property set cannot carry it — making this unsatisfiable.
        self.assertEqual(schema.validate(cross_ref(), "record.v1.json"), [])

    def test_a_cross_reference_may_never_carry_facets(self):
        row = cross_ref()
        row["case_facets"] = facets_payload()
        self.assertTrue(schema.validate(row, "record.v1.json"))

    def test_case_studies_and_product_discovery_are_optional(self):
        for cat in ("case-studies", "product-discovery"):
            self.assertEqual(schema.validate(rec(category=cat), "record.v1.json"), [], cat)
            self.assertEqual(schema.validate(rec(category=cat, case_facets=facets_payload()),
                                             "record.v1.json"), [], cat)

    def test_research_and_discourse_may_not_carry_facets(self):
        for topic, cat in (("research-and-models", "papers"), ("discourse", "community")):
            ok = rec(topic=topic, category=cat)
            self.assertEqual(schema.validate(ok, "record.v1.json"), [], topic)
            ok["case_facets"] = None
            self.assertEqual(schema.validate(ok, "record.v1.json"), [], topic)
            bad = rec(topic=topic, category=cat, case_facets=facets_payload())
            self.assertTrue(schema.validate(bad, "record.v1.json"), topic)

    def test_other_unclear_alone_does_not_satisfy_the_requirement(self):
        cf = facets_payload(state="unresolved", industry="other-unclear", functions=(),
                            unresolved=[{"axis": "industry", "state": "other-unclear",
                                         "detail": "resists placement"}])
        self.assertEqual(facets.decide_classification_state(cf), "unresolved")
        r = rec(case_facets=cf)
        self.assertEqual(coverage.reporting_state(r), "facet_partial")
        self.assertFalse(coverage.is_publication_eligible(r))

    def test_cross_industry_does_satisfy_the_requirement(self):
        cf = facets_payload(industry="cross-industry")
        self.assertEqual(facets.decide_classification_state(cf), "resolved")
        self.assertTrue(coverage.is_publication_eligible(rec(case_facets=cf)))

    def test_an_unresolved_record_must_say_why(self):
        from check_facets import validate_record_facets
        cf = facets_payload(state="unresolved", industry=None, functions=())
        problems = validate_record_facets(rec(case_facets=cf))
        self.assertTrue(any("unresolved[] entry" in p for p in problems), problems)


class TestCoverageReport(unittest.TestCase):
    def test_report_states_sum_and_exclude_cross_references(self):
        recs = five_records() + [cross_ref()]
        doc = coverage.build_coverage_report(recs, RUN, NOW, thresholds_constant=True)
        self.assertEqual(schema.validate(doc, "coverage_report.v1.json"), [])
        row = next(r for r in doc["by_category"]
                   if r["category_slug"] == "domain-applications")
        self.assertEqual(sum(row["states"].values()), row["applicable_full_records"])
        self.assertEqual(row["applicable_full_records"], 5)
        self.assertTrue(row["gated"])
        self.assertEqual(row["publication_eligible_records"], 1)
        self.assertEqual(row["publication_withheld_records"], 4)
        self.assertEqual(len(doc["records"]), 5)

    def test_report_lets_a_consumer_read_state_without_re_deriving_it(self):
        doc = coverage.build_coverage_report(five_records(), RUN, NOW)
        by_state = {r["reporting_state"] for r in doc["records"]}
        self.assertEqual(by_state, set(facets.REPORTING_STATES))
        for row in doc["records"]:
            self.assertEqual(row["publication_eligible"],
                             row["reporting_state"] == "facet_complete")

    def test_case_studies_row_is_not_gated(self):
        recs = [rec(category="case-studies", rid=str(i)) for i in range(3)]
        doc = coverage.build_coverage_report(recs, RUN, NOW)
        row = doc["by_category"][0]
        self.assertFalse(row["gated"])
        self.assertEqual(row["publication_withheld_records"], 0)
        self.assertEqual(row["states"]["not_enriched"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
