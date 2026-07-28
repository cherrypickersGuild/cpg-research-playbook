#!/usr/bin/env python3
"""test_facet_ambiguity.py — the axes must not blur into each other.

The vocabulary exists because a handful of words mean different things on
different axes: "finance" is an industry or a function, "legal" is a firm or a
department, "risk" is who does the work or what the AI solves. Every rule here
is one of those boundaries, asserted so a future vocabulary edit cannot quietly
reintroduce the ambiguity.

Run via tests/test_taxonomy_facet_ambiguity.sh.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))

from src.harvest import facets, records, schema, urlkey     # noqa: E402
from check_facets import validate_record_facets             # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"


def ev(term, quote=None, field="body"):
    return {"field": field, "matched_term": term,
            "quote": quote or ("... %s ..." % term), "offset": None}


def cf(industry=None, secondary=(), functions=(), use_cases=(),
       industry_evidence=None, state=None, unresolved=None):
    payload = {
        "facets_version": 1,
        "vocabulary_versions": facets.vocabulary_versions(),
        "classification_state": "resolved",
        "industry": {"primary": industry, "secondary": list(secondary),
                     "confidence": 0.8 if industry else None,
                     "evidence": industry_evidence or ([ev(industry)] if industry else [])},
        "business_functions": [{"slug": s, "confidence": 0.7, "evidence": [ev(e)]}
                               for s, e in functions],
        "use_case_types": [{"slug": s, "confidence": 0.7, "evidence": [ev(e)]}
                           for s, e in use_cases],
    }
    if unresolved:
        payload["unresolved"] = unresolved
    payload["classification_state"] = state or facets.decide_classification_state(payload)
    return payload


def rec(payload, category="domain-applications", i=0):
    url = "https://example.com/case/amb-%d" % i
    return records.make_full_record(
        record_id=urlkey.record_id("cases", url), content_id=urlkey.content_id(url),
        topic_slug="cases", category_slug=category, cell_id="cases__" + category,
        identity_url=url, target_url=url, harvest_run_id=RUN,
        source_id="s", source_adapter="feed", discovered_at=NOW, case_facets=payload)


class TestDisjointness(unittest.TestCase):
    def test_slug_sets_are_disjoint_except_the_named_sentinel(self):
        a, b, c = (facets.slugs(x) for x in facets.AXES)
        self.assertEqual(a & b, {facets.SENTINEL})
        self.assertEqual(a & c, {facets.SENTINEL})
        self.assertEqual(b & c, {facets.SENTINEL})

    def test_a_real_cross_axis_slug_is_rejected_on_each_other_axis(self):
        # NOT the sentinel — using other-unclear here would pass vacuously.
        cross = [("business_function", "data-analytics", "use_case_type"),
                 ("use_case_type", "code-generation", "business_function"),
                 ("industry", "retail-cpg", "business_function"),
                 ("business_function", "marketing", "industry")]
        for home_axis, slug, foreign_axis in cross:
            self.assertIn(slug, facets.slugs(home_axis))
            self.assertNotIn(slug, facets.slugs(foreign_axis),
                             "%r must belong to %s only" % (slug, home_axis))

    def test_a_function_slug_offered_as_a_use_case_is_refused(self):
        payload = cf(industry="retail-cpg",
                     use_cases=[("data-analytics", "data team")])
        problems = validate_record_facets(rec(payload))
        self.assertTrue(any("not a use_case_type slug" in p for p in problems), problems)

    def test_every_near_miss_pair_exists_and_is_distinct(self):
        pairs = [(("business_function", "training-enablement"),
                  ("use_case_type", "training-education")),
                 (("business_function", "legal-risk-compliance"),
                  ("use_case_type", "risk-fraud-compliance")),
                 (("business_function", "data-analytics"),
                  ("use_case_type", "data-analysis-bi")),
                 (("use_case_type", "customer-interaction"),
                  ("use_case_type", "conversational-assistant"))]
        for (ax_a, sl_a), (ax_b, sl_b) in pairs:
            self.assertIn(sl_a, facets.slugs(ax_a))
            self.assertIn(sl_b, facets.slugs(ax_b))
            self.assertNotEqual(sl_a, sl_b)


class TestAxisBoundaries(unittest.TestCase):
    """finance / legal / retail / manufacturing / operations / education."""

    def test_finance_the_industry_is_not_finance_the_function(self):
        # A retailer automating invoice matching: retail industry, finance function.
        payload = cf(industry="retail-cpg",
                     functions=[("finance-accounting", "invoice")])
        self.assertEqual(validate_record_facets(rec(payload)), [])
        self.assertEqual(payload["industry"]["primary"], "retail-cpg")
        self.assertNotIn("financial-services-insurance",
                         [payload["industry"]["primary"]])

    def test_a_bank_may_carry_both_readings_when_each_is_evidenced(self):
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", "the bank's retail division")],
                     functions=[("finance-accounting", "month-end close")])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_legal_in_house_takes_the_employers_industry(self):
        payload = cf(industry="manufacturing-industrial",
                     industry_evidence=[ev("factory", "the factory's legal team")],
                     functions=[("legal-risk-compliance", "contract review")])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_a_law_firm_is_professional_services(self):
        payload = cf(industry="professional-services",
                     industry_evidence=[ev("law firm", "the law firm rolled it out")],
                     functions=[("legal-risk-compliance", "contract review")])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_retail_never_implies_a_function(self):
        d = facets.entry("industry", "retail-cpg")["disambiguation"].lower()
        self.assertIn("never implies a business function", d)
        # Retail-media work is the industry plus an explicit marketing function,
        # not an industry that silently drags a function along with it.
        payload = cf(industry="retail-cpg",
                     industry_evidence=[ev("retailer", "the retailer's media arm")],
                     functions=[("marketing", "campaign")])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_pharma_production_line_is_healthcare_plus_production_operations(self):
        payload = cf(industry="healthcare-life-sciences",
                     industry_evidence=[ev("pharma", "the pharma plant")],
                     functions=[("production-operations", "line throughput")])
        self.assertEqual(validate_record_facets(rec(payload)), [])
        self.assertNotEqual(payload["industry"]["primary"], "manufacturing-industrial")

    def test_education_the_industry_is_not_training_the_function(self):
        school = cf(industry="education-research",
                    industry_evidence=[ev("university", "the university")],
                    use_cases=[("training-education", "tutor")])
        bank = cf(industry="financial-services-insurance",
                  industry_evidence=[ev("bank", "the bank")],
                  functions=[("training-enablement", "employee training")])
        self.assertEqual(validate_record_facets(rec(school)), [])
        self.assertEqual(validate_record_facets(rec(bank, i=1)), [])


class TestNoBareOperations(unittest.TestCase):
    def test_no_generic_operations_slug_exists(self):
        for axis in facets.AXES:
            for bad in ("operations", "business-operations", "ops", "operations-general"):
                self.assertNotIn(bad, facets.slugs(axis))

    def test_generic_business_operations_prose_assigns_neither(self):
        # "improving business operations" with no concrete workflow: the term
        # goes to unresolved[], and NO operations function is assigned.
        payload = cf(industry="retail-cpg",
                     industry_evidence=[ev("retailer", "the retailer")],
                     use_cases=[("workflow-automation", "process automation")],
                     unresolved=[{"axis": "business_function",
                                  "state": "insufficient_evidence",
                                  "term": "improving business operations",
                                  "detail": "no concrete supply-chain or production workflow"}])
        self.assertEqual(validate_record_facets(rec(payload)), [])
        assigned = [f["slug"] for f in payload["business_functions"]]
        self.assertNotIn("supply-chain-operations", assigned)
        self.assertNotIn("production-operations", assigned)

    def test_both_concrete_operations_functions_are_priority(self):
        for s in ("supply-chain-operations", "production-operations"):
            self.assertEqual(facets.coverage_policy("business_function", s), "priority")


class TestRiskVersusSecurity(unittest.TestCase):
    def test_the_function_and_the_use_case_co_occur_without_conflict(self):
        # A bank's fraud model built by its compliance team carries BOTH, and
        # that pair is not a duplicate and not a conflict.
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", "the bank's compliance team")],
                     functions=[("legal-risk-compliance", "compliance team")],
                     use_cases=[("risk-fraud-compliance", "fraud detection")])
        self.assertEqual(validate_record_facets(rec(payload)), [])
        self.assertEqual(payload["classification_state"], "resolved")

    def test_information_security_is_not_for_contract_or_audit_work(self):
        e = facets.entry("business_function", "information-security")
        excl = " ".join(e["exclusions"]).lower()
        self.assertIn("contract", excl)
        self.assertIn("audit", excl)
        self.assertIn("legal-risk-compliance", excl)

    def test_the_security_function_was_renamed_and_narrowed(self):
        fs = facets.slugs("business_function")
        self.assertNotIn("security-risk", fs)
        self.assertIn("information-security", fs)
        d = facets.entry("business_function", "information-security")["definition"].lower()
        for scope in ("soc", "vulnerability", "incident response", "identity"):
            self.assertIn(scope, d)


class TestVendorPublishedCases(unittest.TestCase):
    def test_a_vendor_published_customer_case_takes_the_customers_industry(self):
        payload = cf(industry="healthcare-life-sciences",
                     industry_evidence=[ev("hospital", "the hospital's triage nurses")],
                     use_cases=[("decision-support", "triage recommendation")])
        r = rec(payload)
        r["publisher"] = "OpenAI"
        r["target_url"] = "https://openai.com/index/customer-story"
        self.assertEqual(validate_record_facets(r), [])
        self.assertEqual(payload["industry"]["primary"], "healthcare-life-sciences")

    def test_technology_software_is_not_inferred_from_publisher_vendor_or_platform(self):
        for field in ("publisher", "target_url"):
            payload = cf(industry="technology-software",
                         industry_evidence=[ev("openai.com", "openai.com", field=field)])
            problems = validate_record_facets(rec(payload))
            self.assertTrue(problems, field)

    def test_technology_software_needs_the_adopter_to_be_a_software_company(self):
        ok = cf(industry="technology-software",
                industry_evidence=[ev("software company",
                                      "the software company retrained its own team")],
                functions=[("software-engineering", "pull request")])
        self.assertEqual(validate_record_facets(rec(ok)), [])

        weak = cf(industry="technology-software",
                  industry_evidence=[ev("hospital", "the hospital deployed it")],
                  functions=[("software-engineering", "pull request")])
        self.assertTrue(validate_record_facets(rec(weak, i=1)))

    def test_technology_software_is_record_only(self):
        self.assertEqual(facets.coverage_policy("industry", "technology-software"),
                         "record_only")
        self.assertEqual(facets.target_min("industry", "technology-software"), 0)


class TestSecondaryIndustries(unittest.TestCase):
    def test_the_cap_is_two(self):
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", "the bank")],
                     secondary=["retail-cpg", "telecommunications", "media-entertainment"])
        self.assertTrue(schema.validate(rec(payload), "record.v1.json"))

    def test_a_conglomerate_article_yields_zero_secondary_industries(self):
        # The article mentions four unrelated business lines. Deployment context
        # is the bank; the turbine business is irrelevant and generates no label.
        quote = ("the group also builds turbines, runs hotels and operates a "
                 "telecoms arm, but the deployment was in the bank")
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", quote)],
                     functions=[("customer-service-support", "support ticket")])
        self.assertEqual(payload["industry"]["secondary"], [])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_a_secondary_with_no_supporting_evidence_is_refused(self):
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", "the bank deployed it")],
                     secondary=["manufacturing-industrial"])
        problems = validate_record_facets(rec(payload))
        self.assertTrue(any("secondary industry" in p for p in problems), problems)
        self.assertTrue(any("corporate portfolio" in p for p in problems), problems)

    def test_a_genuinely_evidenced_secondary_is_accepted(self):
        quote = "rolled out across the bank and its factory maintenance crews"
        payload = cf(industry="financial-services-insurance",
                     industry_evidence=[ev("bank", quote), ev("factory", quote)],
                     secondary=["manufacturing-industrial"],
                     functions=[("production-operations", "predictive maintenance")])
        self.assertEqual(validate_record_facets(rec(payload)), [])


class TestCrossIndustryAssignment(unittest.TestCase):
    def test_a_generic_reusable_tool_is_not_automatically_cross_industry(self):
        payload = cf(industry="cross-industry",
                     industry_evidence=[ev("useful", "a generally useful tool")])
        problems = validate_record_facets(rec(payload))
        self.assertTrue(any("cross-industry" in p for p in problems), problems)

    def test_a_documented_multi_industry_deployment_may_receive_it(self):
        payload = cf(industry="cross-industry",
                     industry_evidence=[ev("deployed across",
                                           "deployed across customers in banking, "
                                           "retail and healthcare")],
                     use_cases=[("workflow-automation", "process automation")])
        self.assertEqual(validate_record_facets(rec(payload)), [])

    def test_cross_industry_counts_as_resolved_but_is_record_only(self):
        payload = cf(industry="cross-industry",
                     industry_evidence=[ev("horizontal deployment",
                                           "a horizontal deployment across sectors")],
                     use_cases=[("workflow-automation", "process automation")])
        self.assertEqual(facets.decide_classification_state(payload), "resolved")
        self.assertEqual(facets.coverage_policy("industry", "cross-industry"), "record_only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
