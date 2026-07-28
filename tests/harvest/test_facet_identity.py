#!/usr/bin/env python3
"""test_facet_identity.py — facets must be invisible to identity.

The load-bearing property: a facet is an editorial judgement that can be revised,
while record_id / content_id / identity_url / cell_id / the published filename
are permanent. If a facet edit could move an id, revising a classification would
rename an artifact and orphan its history — so this is asserted structurally
(recompute everything across four kinds of facet edit) AND statically (the
identity modules must not even mention facets).

Run via tests/test_taxonomy_facet_identity.sh.
"""
import copy
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))

from src.harvest import facets, records, schema, slug, urlkey   # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"
IU = "https://example.com/case/hospital-triage"

IDENTITY_KEYS = ("record_id", "content_id", "identity_url", "canonical_url", "cell_id")


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
                                "evidence": [ev(term="support", quote="support triage")]}],
        "use_case_types": [{"slug": "search-retrieval", "confidence": 0.7,
                            "evidence": [ev(term="retrieval", quote="retrieval over notes")]}],
    }
    cf.update(over)
    return cf


def build(**kw):
    return records.make_full_record(
        record_id=urlkey.record_id("cases", IU),
        content_id=urlkey.content_id(IU),
        topic_slug="cases", category_slug="domain-applications",
        cell_id="cases__domain-applications",
        identity_url=IU, target_url=IU,
        harvest_run_id=RUN, source_id="openai-news", source_adapter="feed",
        title="A title", summary="A summary", curation_reason="Why it matters",
        discovered_at=NOW, **kw)


class TestBuilderCompatibility(unittest.TestCase):
    """DV-2: the added keyword must be invisible to every existing caller."""

    def test_omitting_and_passing_none_are_identical(self):
        a = build()
        b = build(case_facets=None)
        self.assertEqual(a, b)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotIn("case_facets", a)
        self.assertNotIn("case_facets", b)

    def test_an_empty_payload_omits_the_key(self):
        # {} is falsy, so "looked, found nothing" cannot be confused with
        # "never attempted" — the latter is the ABSENT key.
        self.assertNotIn("case_facets", build(case_facets={}))

    def test_the_parameter_is_keyword_only(self):
        import inspect
        sig = inspect.signature(records.make_full_record)
        p = sig.parameters["case_facets"]
        self.assertEqual(p.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(p.default)

    def test_cross_reference_builder_is_unchanged(self):
        import inspect
        self.assertNotIn("case_facets",
                         inspect.signature(records.make_cross_reference).parameters)

    def test_a_record_with_facets_still_validates(self):
        self.assertEqual(schema.validate(build(case_facets=good_facets()),
                                         "record.v1.json"), [])


class TestIdentityStability(unittest.TestCase):
    """Add, change, remove, null — none of it may move an identity."""

    def _identity(self, rec):
        return {k: rec.get(k) for k in IDENTITY_KEYS}

    def test_four_kinds_of_facet_edit_change_no_identity(self):
        base = build()
        baseline = self._identity(base)

        added = build(case_facets=good_facets())
        changed = build(case_facets=good_facets(
            industry={"primary": "manufacturing-industrial", "secondary": ["retail-cpg"],
                      "confidence": 0.4, "evidence": [ev(term="plant",
                                                         quote="the plant floor")]}))
        removed = copy.deepcopy(added)
        removed.pop("case_facets")
        nulled = copy.deepcopy(added)
        nulled["case_facets"] = None

        for label, rec in (("added", added), ("changed", changed),
                           ("removed", removed), ("nulled", nulled)):
            self.assertEqual(self._identity(rec), baseline, label)

    def test_ids_recomputed_from_the_record_are_unaffected(self):
        rec = build(case_facets=good_facets())
        self.assertEqual(urlkey.record_id(rec["topic"], rec["identity_url"]),
                         rec["record_id"])
        self.assertEqual(urlkey.content_id(rec["identity_url"]), rec["content_id"])

    def test_artifact_filename_is_unaffected(self):
        rec = build(case_facets=good_facets())
        self.assertEqual(slug.artifact_filename(rec["topic"], rec["primary_category"]),
                         "cases__domain-applications__harvest.json")
        self.assertEqual(slug.cell_id(rec["topic"], rec["primary_category"]),
                         rec["cell_id"])

    def test_sort_order_is_unaffected(self):
        a = build()
        b = build(case_facets=good_facets())
        self.assertEqual(records.sort_key(a), records.sort_key(b))


class TestIdentityModulesDoNotKnowAboutFacets(unittest.TestCase):
    """Static proof, so a future edit cannot quietly wire facets into identity."""

    def test_urlkey_and_slug_never_mention_facets(self):
        for name in ("urlkey.py", "slug.py"):
            path = os.path.join(ROOT, "src", "harvest", name)
            with open(path, encoding="utf-8") as f:
                text = f.read().lower()
            for needle in ("facet", "case_facets", "industry",
                           "business_function", "use_case"):
                self.assertNotIn(needle, text, "%s must not mention %r" % (name, needle))

    def test_identity_functions_take_only_url_and_topic(self):
        import inspect
        self.assertEqual(list(inspect.signature(urlkey.record_id).parameters),
                         ["topic_slug", "identity_url"])
        self.assertEqual(list(inspect.signature(urlkey.content_id).parameters),
                         ["identity_url"])


class TestTwelveCellSetUnchanged(unittest.TestCase):
    """Facets create no cells."""

    def test_approved_cells_is_still_exactly_twelve(self):
        import check_config
        self.assertEqual(len(check_config.APPROVED_CELLS), 12)
        self.assertIn("cases__domain-applications", check_config.APPROVED_CELLS)

    def test_check_config_does_not_read_facets(self):
        path = os.path.join(ROOT, "scripts", "harvest", "check_config.py")
        with open(path, encoding="utf-8") as f:
            text = f.read().lower()
        self.assertNotIn("facet", text,
                         "check_config.py stays byte-unchanged (DV-1): the 12-cell "
                         "specification and the facet vocabularies are separate gates")

    def test_config_check_still_reports_twelve_cells(self):
        import subprocess
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "scripts", "harvest", "check_config.py")],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cells=12", r.stdout)


class TestPublishedShape(unittest.TestCase):
    def test_facets_do_not_appear_in_any_identity_or_path_string(self):
        rec = build(case_facets=good_facets())
        blob = json.dumps({k: rec[k] for k in IDENTITY_KEYS})
        for token in ("healthcare", "facet", "industry", "customer-service"):
            self.assertNotIn(token, blob.lower())

    def test_record_schema_does_not_require_case_facets_globally(self):
        required = schema.load_schema("record.v1.json")["$defs"]["full_record"]["required"]
        self.assertNotIn("case_facets", required,
                         "adding it to `required` would break the Stage 1 assertion that "
                         "every required field is genuinely required")


if __name__ == "__main__":
    unittest.main(verbosity=2)
