#!/usr/bin/env python3
"""test_customer_interaction.py — decision V4, the external/internal split.

The failure this prevents: counting every chatbot as customer interaction. A
conversational interface is a MODE; it proves nothing about who is on the other
end. So customer-interaction (priority, strictly external) is a separate value
from conversational-assistant (standard, explicitly including internal employee
copilots) — and because the latter is standard, it can never satisfy the
Customer Interaction coverage target on its own.

Run via tests/test_taxonomy_customer_interaction.sh.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))

from src.harvest import coverage, facets, records, urlkey    # noqa: E402
from check_facets import validate_record_facets              # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"

EXTERNAL = ("Patients ask the assistant about their appointments before they "
            "arrive at the clinic")
INTERNAL = ("Employees ask the internal copilot about HR policy in a chat "
            "window inside the intranet")


def ev(term, quote, field="body"):
    return {"field": field, "matched_term": term, "quote": quote, "offset": None}


def payload(use_cases, industry="healthcare-life-sciences",
            industry_quote="the hospital rolled it out"):
    doc = {
        "facets_version": 1,
        "vocabulary_versions": facets.vocabulary_versions(),
        "classification_state": "resolved",
        "industry": {"primary": industry, "secondary": [], "confidence": 0.9,
                     "evidence": [ev("hospital", industry_quote)]},
        "business_functions": [{"slug": "customer-service-support", "confidence": 0.7,
                                "evidence": [ev("support ticket",
                                                "support tickets are deflected")]}],
        "use_case_types": [{"slug": s, "confidence": 0.7, "evidence": [ev(t, q)]}
                           for s, t, q in use_cases],
    }
    doc["classification_state"] = facets.decide_classification_state(doc)
    return doc


def rec(doc, i=0):
    url = "https://example.com/case/ci-%d" % i
    return records.make_full_record(
        record_id=urlkey.record_id("cases", url), content_id=urlkey.content_id(url),
        topic_slug="cases", category_slug="domain-applications",
        cell_id="cases__domain-applications", identity_url=url, target_url=url,
        harvest_run_id=RUN, source_id="s", source_adapter="feed",
        discovered_at=NOW, case_facets=doc)


class TestTheTwoValuesAreSeparate(unittest.TestCase):
    def test_both_exist_on_the_use_case_axis(self):
        s = facets.slugs("use_case_type")
        self.assertIn("customer-interaction", s)
        self.assertIn("conversational-assistant", s)

    def test_tiers_are_priority_and_standard(self):
        self.assertEqual(facets.coverage_policy("use_case_type",
                                                "customer-interaction"), "priority")
        self.assertEqual(facets.coverage_policy("use_case_type",
                                                "conversational-assistant"), "standard")

    def test_customer_interaction_is_defined_as_strictly_external(self):
        e = facets.entry("use_case_type", "customer-interaction")
        self.assertIn("external", e["definition"].lower())
        excl = " ".join(e["exclusions"]).lower()
        self.assertIn("internal", excl)

    def test_conversational_assistant_explicitly_includes_internal_copilots(self):
        e = facets.entry("use_case_type", "conversational-assistant")
        self.assertIn("internal", e["definition"].lower())


class TestExternalVersusInternal(unittest.TestCase):
    def test_an_external_customer_assistant_may_receive_customer_interaction(self):
        doc = payload([("customer-interaction", "patients interact with", EXTERNAL)])
        self.assertEqual(validate_record_facets(rec(doc)), [])

    def test_an_internal_employee_copilot_does_not(self):
        doc = payload([("customer-interaction", "copilot", INTERNAL)])
        problems = validate_record_facets(rec(doc, 1))
        self.assertTrue(any("EXTERNAL" in p for p in problems), problems)

    def test_an_internal_copilot_receives_conversational_assistant_only(self):
        doc = payload([("conversational-assistant", "internal copilot", INTERNAL)])
        self.assertEqual(validate_record_facets(rec(doc, 2)), [])
        slugs = [u["slug"] for u in doc["use_case_types"]]
        self.assertEqual(slugs, ["conversational-assistant"])
        self.assertNotIn("customer-interaction", slugs)

    def test_a_conversational_ui_alone_does_not_prove_customer_interaction(self):
        doc = payload([("customer-interaction", "chat window",
                        "users type into a chat window")])
        problems = validate_record_facets(rec(doc, 3))
        self.assertTrue(problems,
                        "a chat interface alone proves nothing about who is on the "
                        "other end")

    def test_both_values_only_when_each_is_independently_evidenced(self):
        good = payload([
            ("customer-interaction", "patients interact with", EXTERNAL),
            ("conversational-assistant", "chatbot",
             "the chatbot answers in natural language"),
        ])
        self.assertEqual(validate_record_facets(rec(good, 4)), [])

        bad = payload([
            ("customer-interaction", "chatbot", "the chatbot answers questions"),
            ("conversational-assistant", "chatbot", "the chatbot answers questions"),
        ])
        self.assertTrue(validate_record_facets(rec(bad, 5)),
                        "one shared conversational quote cannot evidence both values")


class TestCoverageTarget(unittest.TestCase):
    def test_conversational_assistant_alone_never_satisfies_the_target(self):
        recs = [rec(payload([("conversational-assistant", "internal copilot", INTERNAL)]), i)
                for i in range(5)]
        rows = coverage.axis_targets(recs)
        ci = next(r for r in rows if r["slug"] == "customer-interaction")
        ca = next(r for r in rows if r["slug"] == "conversational-assistant")

        self.assertEqual(ca["observed"], 5)
        self.assertEqual(ci["observed"], 0)
        self.assertEqual(ci["target_min"], 3)
        self.assertEqual(ci["gap"], 3, "five internal copilots leave the Customer "
                                       "Interaction target completely unmet")

    def test_external_records_do_close_the_customer_interaction_gap(self):
        recs = [rec(payload([("customer-interaction", "patients interact with", EXTERNAL)]), i)
                for i in range(3)]
        rows = coverage.axis_targets(recs)
        ci = next(r for r in rows if r["slug"] == "customer-interaction")
        self.assertEqual(ci["observed"], 3)
        self.assertEqual(ci["gap"], 0)

    def test_the_two_values_have_independent_targets(self):
        self.assertEqual(facets.target_min("use_case_type", "customer-interaction"), 3)
        self.assertEqual(facets.target_min("use_case_type", "conversational-assistant"), 2)

    def test_a_customer_interaction_gap_lane_may_be_scheduled(self):
        from src.harvest import scheduler
        s = scheduler.Scheduler(clock=lambda: 0.0)
        lanes, _ = s.plan_round(2, credible_sources={"customer-interaction": ["src"]},
                                max_lanes=99)
        self.assertIn("gap__use_case_type__customer-interaction",
                      [l["lane_id"] for l in lanes])


if __name__ == "__main__":
    unittest.main(verbosity=2)
