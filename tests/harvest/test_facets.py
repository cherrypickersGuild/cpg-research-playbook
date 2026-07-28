#!/usr/bin/env python3
"""test_facets.py — the facet vocabularies and their generated constraints.

Two properties carry the weight here:

  * the vocabularies are the single source of truth, and the generated schema is
    a pure function of them — so drift must be impossible to miss;
  * schemas/harvest/ is loaded WHOLESALE into one cached registry by schema.py,
    so a malformed generated file must fail loudly rather than silently shadow
    another schema or break unrelated suites.

Run via tests/test_taxonomy_facets.sh.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))

from src.harvest import facets, schema            # noqa: E402
from src.harvest.slug import slugify              # noqa: E402
import gen_facet_schema                           # noqa: E402

CHECK = os.path.join(ROOT, "scripts", "harvest", "check_facets.py")
GEN = os.path.join(ROOT, "scripts", "harvest", "gen_facet_schema.py")
SCHEMA_DIR = os.path.join(ROOT, "schemas", "harvest")


def run(*args):
    return subprocess.run([sys.executable] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def ev(field="body", term="hospital", quote="the hospital deployed the assistant"):
    return {"field": field, "matched_term": term, "quote": quote, "offset": None}


def good_facets(**over):
    cf = {
        "facets_version": 1,
        "vocabulary_versions": facets.vocabulary_versions(),
        "classification_state": "resolved",
        "industry": {"primary": "healthcare-life-sciences", "secondary": [],
                     "confidence": 0.9, "evidence": [ev()]},
        "business_functions": [{"slug": "customer-service-support", "confidence": 0.8,
                                "evidence": [ev(term="support tickets",
                                                quote="support tickets are triaged")]}],
        "use_case_types": [{"slug": "search-retrieval", "confidence": 0.7,
                            "evidence": [ev(term="retrieval",
                                            quote="retrieval over clinical notes")]}],
    }
    cf.update(over)
    return cf


def full_record(**over):
    rec = {
        "record_type": "full", "record_id": "a" * 16,
        "topic": "cases", "primary_category": "domain-applications",
        "provenance": {"source_id": "x", "source_adapter": "feed"},
        "case_facets": good_facets(),
    }
    rec.update(over)
    return rec


class TestVocabularyShape(unittest.TestCase):
    def test_each_vocabulary_validates_against_its_schema(self):
        for axis in facets.AXES:
            path = os.path.join(facets.FACETS_DIR, facets.AXIS_FILE[axis])
            self.assertEqual(schema.validate_file(path, "facet_vocabulary.v1.json"), [], axis)

    def test_totals_are_18_19_22(self):
        self.assertEqual(len(facets.entries("industry")), 18)
        self.assertEqual(len(facets.entries("business_function")), 19)
        self.assertEqual(len(facets.entries("use_case_type")), 22)

    def test_tier_splits_are_7_8_3__10_8_1__10_11_1(self):
        # Derived from the files, never hardcoded twice. The "10/10/1" that
        # appeared in earlier drafts sums to 21 and cannot describe 22 values.
        self.assertEqual(facets.tier_counts("industry"),
                         {"priority": 7, "standard": 8, "record_only": 3})
        self.assertEqual(facets.tier_counts("business_function"),
                         {"priority": 10, "standard": 8, "record_only": 1})
        self.assertEqual(facets.tier_counts("use_case_type"),
                         {"priority": 10, "standard": 11, "record_only": 1})

    def test_tier_counts_sum_to_totals(self):
        for axis in facets.AXES:
            self.assertEqual(sum(facets.tier_counts(axis).values()),
                             len(facets.entries(axis)), axis)

    def test_every_slug_is_already_a_slug_and_unique(self):
        for axis in facets.AXES:
            ss = [e["slug"] for e in facets.entries(axis)]
            self.assertEqual(len(ss), len(set(ss)), axis)
            for s in ss:
                self.assertEqual(slugify(s), s, "%s: %r" % (axis, s))

    def test_axes_are_disjoint_except_the_named_sentinel(self):
        a = facets.slugs("industry")
        b = facets.slugs("business_function")
        c = facets.slugs("use_case_type")
        for x, y in ((a, b), (a, c), (b, c)):
            self.assertEqual(x & y, {facets.SENTINEL})
        for s in (a, b, c):
            self.assertIn(facets.SENTINEL, s)

    def test_no_bare_operations_slug_anywhere(self):
        for axis in facets.AXES:
            for bad in ("operations", "business-operations", "ops"):
                self.assertNotIn(bad, facets.slugs(axis), "%s/%s" % (axis, bad))
        self.assertEqual(facets.coverage_policy("business_function",
                                                "supply-chain-operations"), "priority")
        self.assertEqual(facets.coverage_policy("business_function",
                                                "production-operations"), "priority")

    def test_record_only_industries(self):
        for s in ("technology-software", "cross-industry", "other-unclear"):
            self.assertEqual(facets.coverage_policy("industry", s), "record_only")

    def test_customer_interaction_is_priority_and_assistant_is_standard(self):
        self.assertEqual(facets.coverage_policy("use_case_type",
                                                "customer-interaction"), "priority")
        self.assertEqual(facets.coverage_policy("use_case_type",
                                                "conversational-assistant"), "standard")

    def test_legal_and_security_functions_are_separate(self):
        fs = facets.slugs("business_function")
        self.assertIn("legal-risk-compliance", fs)
        self.assertIn("information-security", fs)
        self.assertNotIn("legal-compliance", fs)
        self.assertNotIn("security-risk", fs)


class TestGeneratedSchema(unittest.TestCase):
    def test_no_drift_against_the_vocabularies(self):
        r = run(GEN, "--check")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_regeneration_into_a_temp_dir_is_byte_identical(self):
        tmp = tempfile.mkdtemp(prefix="facetgen_")
        try:
            r = run(GEN, "--out-dir", tmp, "--quiet")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(tmp, gen_facet_schema.OUT_NAME), "rb") as f:
                fresh = f.read()
            with open(os.path.join(SCHEMA_DIR, gen_facet_schema.OUT_NAME), "rb") as f:
                live = f.read()
            self.assertEqual(fresh, live)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_generated_file_declares_itself_generated_with_source_hashes(self):
        doc = schema.load_schema(gen_facet_schema.OUT_NAME)
        meta = doc["_generated"]
        self.assertIn("DO NOT HAND-EDIT", meta["never_hand_edit"])
        self.assertEqual(len(meta["sources"]), 3)
        for s in meta["sources"]:
            self.assertEqual(len(s["sha256"]), 64)
            self.assertIn("vocabulary_version", s)

    def test_generated_enums_carry_every_slug(self):
        doc = schema.load_schema(gen_facet_schema.OUT_NAME)
        self.assertEqual(set(doc["$defs"]["industry_slug"]["enum"]), facets.slugs("industry"))
        self.assertEqual(set(doc["$defs"]["business_function_slug"]["enum"]),
                         facets.slugs("business_function"))
        self.assertEqual(set(doc["$defs"]["use_case_type_slug"]["enum"]),
                         facets.slugs("use_case_type"))

    def test_generated_schema_compiles_and_rejects_an_invalid_slug(self):
        import jsonschema
        doc = schema.load_schema(gen_facet_schema.OUT_NAME)
        jsonschema.Draft202012Validator.check_schema(doc)
        v = jsonschema.Draft202012Validator(doc)
        self.assertEqual(list(v.iter_errors({"case_facets": good_facets()})), [])
        bad = good_facets()
        bad["industry"] = dict(bad["industry"], primary="banking-sector")
        self.assertTrue(list(v.iter_errors({"case_facets": bad})),
                        "a well-shaped but non-vocabulary slug must be rejected by the "
                        "generated schema — that is the whole reason it exists")

    def test_a_malformed_generated_file_fails_loudly(self):
        # schemas/harvest/ is loaded wholesale into one cached registry, so a
        # broken file here would otherwise break every suite with a confusing
        # error. Prove check_facets reports it, and says why it matters.
        tmp = tempfile.mkdtemp(prefix="facetbad_")
        try:
            for name in os.listdir(SCHEMA_DIR):
                if name.endswith(".json"):
                    shutil.copy(os.path.join(SCHEMA_DIR, name), os.path.join(tmp, name))
            with open(os.path.join(tmp, gen_facet_schema.OUT_NAME), "w",
                      encoding="utf-8") as f:
                f.write('{"$id": "broken", ')       # truncated on purpose
            r = run(CHECK, "--schema-dir", tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not valid JSON", r.stderr)
            self.assertIn("cached registry", r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_hand_edited_generated_file_is_reported_as_drift(self):
        tmp = tempfile.mkdtemp(prefix="facetdrift_")
        try:
            for name in os.listdir(SCHEMA_DIR):
                if name.endswith(".json"):
                    shutil.copy(os.path.join(SCHEMA_DIR, name), os.path.join(tmp, name))
            path = os.path.join(tmp, gen_facet_schema.OUT_NAME)
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            doc["$defs"]["industry_slug"]["enum"].append("hand-added-industry")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, sort_keys=True)
            r = run(CHECK, "--schema-dir", tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("DRIFTED", r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCoverageTargets(unittest.TestCase):
    def test_real_config_passes(self):
        r = run(CHECK)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_tier_targets(self):
        self.assertEqual(facets.target_min("industry", "healthcare-life-sciences"), 3)
        self.assertEqual(facets.target_min("industry", "telecommunications"), 2)
        self.assertEqual(facets.target_min("industry", "cross-industry"), 0)
        self.assertEqual(facets.target_min("industry", "technology-software"), 0)
        self.assertEqual(facets.target_min("use_case_type", "other-unclear"), 0)

    def test_an_override_raising_a_record_only_value_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="facettgt_")
        try:
            src = os.path.join(facets.CONFIG_DIR, "coverage_targets.v1.json")
            doc = json.load(open(src, encoding="utf-8"))
            doc["overrides"]["cross-industry"] = {"target_min": 3}
            with open(os.path.join(tmp, "coverage_targets.v1.json"), "w",
                      encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
            r = run(CHECK, "--config-dir", tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("record_only", r.stderr)
            self.assertIn("cross-industry", r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cross_industry_and_sentinel_never_get_a_gap_lane(self):
        t = facets.load_coverage_targets()
        never = set(t["scheduler"]["never_schedule_gap_lane_for"])
        self.assertIn("cross-industry", never)
        self.assertIn(facets.SENTINEL, never)


class TestVocabularyVersions(unittest.TestCase):
    def test_runtime_match(self):
        self.assertEqual(facets.vocabulary_versions(),
                         {"industries": 1, "business_functions": 1, "use_case_types": 1})
        self.assertEqual(
            __import__("scripts.harvest.check_facets", fromlist=["x"]).validate_record_facets(
                full_record()), [])

    def test_a_mismatched_vocabulary_version_is_rejected(self):
        from check_facets import validate_record_facets
        cf = good_facets(vocabulary_versions={"industries": 99, "business_functions": 1,
                                              "use_case_types": 1})
        problems = validate_record_facets(full_record(case_facets=cf))
        self.assertTrue(any("vocabulary_versions" in p for p in problems), problems)


class TestDeprecation(unittest.TestCase):
    def _temp_vocab_with_deprecated(self):
        tmp = tempfile.mkdtemp(prefix="facetdep_")
        for name in os.listdir(facets.FACETS_DIR):
            shutil.copy(os.path.join(facets.FACETS_DIR, name), os.path.join(tmp, name))
        path = os.path.join(tmp, facets.AXIS_FILE["use_case_type"])
        doc = json.load(open(path, encoding="utf-8"))
        for e in doc["entries"]:
            if e["slug"] == "speech-audio":
                e["status"] = "deprecated"
                e["replaced_by"] = "vision-inspection"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        facets.clear_caches()
        return tmp

    def tearDown(self):
        facets.clear_caches()

    def test_deprecated_validates_historically_but_is_refused_for_new_assignment(self):
        from check_facets import validate_record_facets
        tmp = self._temp_vocab_with_deprecated()
        try:
            self.assertIn("speech-audio", facets.slugs("use_case_type", tmp))
            self.assertNotIn("speech-audio", facets.active_slugs("use_case_type", tmp))

            cf = good_facets()
            cf["use_case_types"] = [{"slug": "speech-audio", "confidence": 0.6,
                                     "evidence": [ev(term="transcription",
                                                     quote="calls are transcribed")]}]
            cf["vocabulary_versions"] = facets.vocabulary_versions(tmp)
            rec = full_record(case_facets=cf)

            historical = validate_record_facets(rec, tmp, new_assignment=False)
            self.assertEqual(historical, [], historical)

            fresh = validate_record_facets(rec, tmp, new_assignment=True)
            self.assertTrue(any("deprecated" in p for p in fresh), fresh)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLegacyMapSeed(unittest.TestCase):
    def test_normalization_is_minimal_and_documented(self):
        self.assertEqual(facets.normalize_legacy_value("  Banking /  Financial   Services "),
                         "banking / financial services")
        self.assertEqual(facets.normalize_legacy_value(None), "")

    def test_lookup_returns_none_rather_than_guessing(self):
        self.assertEqual(facets.lookup_legacy_industry("Banking"),
                         "financial-services-insurance")
        self.assertIsNone(facets.lookup_legacy_industry(
            "superapp (mobility, delivery, fintech)"))
        self.assertIsNone(facets.lookup_legacy_industry("a thing nobody reviewed"))

    def test_it_is_a_seed_not_a_complete_table(self):
        # Grounded in the real corpus: 231 cases, 173 distinct free-text values.
        # A complete table is not achievable, and the long tail must stay visible.
        with open(os.path.join(ROOT, "state", "ax_case_harvest_registry.json"),
                  encoding="utf-8") as f:
            reg = json.load(f)
        cases = reg["cases"]
        self.assertEqual(len(cases), 231)
        distinct = {facets.normalize_legacy_value(c["industry"]) for c in cases
                    if isinstance(c.get("industry"), str) and c["industry"].strip()}
        self.assertEqual(len(distinct), 173)

        mapped = sum(1 for c in cases if facets.lookup_legacy_industry(c.get("industry")))
        unmapped = len(cases) - mapped
        self.assertGreater(mapped, 0)
        self.assertGreater(unmapped, 0,
                           "if every value mapped, the seed would be pretending to be a "
                           "complete table for 173 free-text strings")
        self.assertEqual(mapped + unmapped, 231)

    def test_no_entry_maps_to_the_sentinel(self):
        for slug in facets.load_legacy_industry_map().values():
            self.assertNotEqual(slug, facets.SENTINEL)


class TestUnmappedLegacySemantics(unittest.TestCase):
    def _migrated(self, legacy_value, case_facets):
        return {
            "record_type": "full", "record_id": "b" * 16,
            "topic": "cases", "primary_category": "case-studies",
            "provenance": {"source_id": "ax", "source_adapter": "migration",
                           "migration": {"adapter": "ax_cases"},
                           "raw": {"industry": legacy_value}},
            "case_facets": case_facets,
        }

    def test_a_migrated_record_may_not_hide_an_unmapped_value_by_omitting_facets(self):
        from check_facets import validate_record_facets
        rec = self._migrated("superapp (mobility, delivery, fintech)", None)
        problems = validate_record_facets(rec)
        self.assertTrue(any("unmapped_legacy_value" in p for p in problems), problems)
        self.assertTrue(any("not_enriched" in p for p in problems), problems)

    def test_a_mapped_legacy_value_needs_no_unresolved_entry(self):
        from check_facets import validate_record_facets
        cf = good_facets()
        cf["industry"] = {"primary": "financial-services-insurance", "secondary": [],
                          "confidence": 0.8,
                          "evidence": [{"field": "legacy_field", "matched_term": "Banking",
                                        "quote": "Banking", "offset": None}]}
        self.assertEqual(validate_record_facets(self._migrated("Banking", cf)), [])

    def test_an_unmapped_value_may_never_be_classification_evidence(self):
        from check_facets import validate_record_facets
        term = "superapp (mobility, delivery, fintech)"
        cf = good_facets(classification_state="resolved")
        cf["industry"] = {"primary": "transportation-logistics", "secondary": [],
                          "confidence": 0.5,
                          "evidence": [{"field": "legacy_field", "matched_term": term,
                                        "quote": term, "offset": None}]}
        cf["unresolved"] = [{"axis": "industry", "state": "unmapped_legacy_value",
                             "term": term, "detail": "no reviewed mapping exists"}]
        problems = validate_record_facets(self._migrated(term, cf))
        self.assertTrue(any("classification evidence" in p for p in problems), problems)


class TestEvidenceSourceRules(unittest.TestCase):
    def test_industry_is_never_evidenced_from_the_publisher(self):
        from check_facets import validate_record_facets
        cf = good_facets()
        cf["industry"] = dict(cf["industry"],
                              evidence=[ev(field="publisher", term="Healthcare Weekly",
                                           quote="Healthcare Weekly")])
        problems = validate_record_facets(full_record(case_facets=cf))
        self.assertTrue(any("publisher" in p for p in problems), problems)

    def test_technology_software_is_never_evidenced_from_publisher_or_host(self):
        from check_facets import validate_record_facets
        for field in ("publisher", "target_url"):
            cf = good_facets()
            cf["industry"] = {"primary": "technology-software", "secondary": [],
                              "confidence": 0.5,
                              "evidence": [ev(field=field, term="openai.com",
                                              quote="openai.com/customer-stories")]}
            problems = validate_record_facets(full_record(case_facets=cf))
            self.assertTrue(any("technology-software" in p or "publisher" in p
                                for p in problems), (field, problems))

    def test_a_value_asserted_without_evidence_is_refused(self):
        from check_facets import validate_record_facets
        cf = good_facets()
        cf["business_functions"] = [{"slug": "marketing", "confidence": 0.5, "evidence": []}]
        problems = validate_record_facets(full_record(case_facets=cf))
        self.assertTrue(any("no evidence" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main(verbosity=2)
