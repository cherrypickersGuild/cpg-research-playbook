#!/usr/bin/env python3
"""test_facetassign.py — deterministic `case_facets` assignment (S4-5A).

The properties that carry the weight:

  * THE PUBLISHER IS NOT THE CUSTOMER. A vendor-published customer story must
    take the customer's industry, so `publisher` can never ground an industry and
    `target_url` can never ground `technology-software`. Both are asserted with
    the term present ONLY in the forbidden field.
  * A TIE IS AN AMBIGUITY. Two equally-supported industries resolve to the
    committed `other-unclear` sentinel with both names recorded — never to
    whichever sorts first.
  * NOT-APPLICABLE IS NOT EMPTY. `research-and-models` and `discourse` return an
    explicit not-applicable result, because an empty payload would be counted as
    `unresolved` rather than `not_enriched`.
  * NOTHING IS ASSERTED WITHOUT A QUOTE. Every asserted value carries evidence
    from an authorized field, and `facets.evidence_supports` gates every one.

Vocabulary-driven throughout: terms are pulled from the committed files rather
than typed here, so the tests cannot drift from the config. Offline; no network,
no pool, no records. Run via tests/test_taxonomy_facetassign.sh.
"""
import ast
import copy
import dataclasses
import inspect
import itertools
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import classify as cl, dedupe as dd, extract as ex        # noqa: E402
from src.harvest import facetassign as fa, facets, schema, verify as vf    # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate          # noqa: E402

RECORD_SCHEMA_PATH = os.path.join(ROOT, "schemas", "harvest", "record.v1.json")
LANES = ("cell__cases__domain-applications", "gap__industry__healthcare-life-sciences")

SOURCES = {
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
}

HEALTHCARE = dict(
    title="A hospital network deployed an assistant for patient intake",
    summary="The clinical team automated scheduling and billing for the finance "
            "department, improving customer support response times across the "
            "contact centre.")


def first_term(axis, slug):
    """A real term for a real slug, read from the committed vocabulary."""
    entry = facets.entry(axis, slug)
    terms = list(entry.get("positive_terms") or []) + list(entry.get("synonyms") or [])
    return terms[0]


def candidate(source_id="aws-ml-blog", lane=LANES[0],
              url="https://example.com/item/", **payload):
    item = RawCandidate(target_url=url, source_id=source_id,
                        adapter="feed", position=0, **payload)
    result = AdapterResult(source_id=source_id, adapter="feed", result="ok",
                           candidates=(item,))
    deduped = dd.group([dd.delivery(lane, result)], sources=SOURCES)
    return ex.normalize_all(deduped).candidates[0]


def assigned(topic="cases", category="domain-applications", **spec):
    extracted = candidate(**spec)
    classification = dataclasses.replace(cl.classify(extracted),
                                         topic_slug=topic, category_slug=category)
    return extracted, classification, fa.assign(extracted, classification)


def slugs(payload, axis_plural):
    return [v["slug"] for v in payload[axis_plural]]


def serialize(assignments):
    return json.dumps([{
        "candidate_key": a.candidate_key, "applicable": a.applicable,
        "gated": a.gated, "report_only": a.report_only,
        "case_facets": a.case_facets,
    } for a in assignments], sort_keys=True)


# ---------------------------------------------------------------- positives
class TestPositiveAssignment(unittest.TestCase):
    def test_the_industry_axis_is_assigned_from_the_vocabulary(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(a.case_facets["industry"]["primary"],
                         "healthcare-life-sciences")
        self.assertTrue(a.case_facets["industry"]["evidence"])

    def test_the_business_function_axis_is_assigned(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertTrue(slugs(a.case_facets, "business_functions"))

    def test_the_use_case_type_axis_is_assigned(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertTrue(slugs(a.case_facets, "use_case_types"))

    def test_every_axis_can_be_assigned_from_a_committed_term(self):
        for axis, plural in facets.AXIS_PLURAL.items():
            slug = sorted(s for s in facets.active_slugs(axis)
                          if s != facets.SENTINEL
                          and (axis, s) not in facets.LEXICAL_SUPPORT_REQUIRED)[0]
            term = first_term(axis, slug)
            _, _, a = assigned(title="A case study",
                               summary="This work involves %s in production." % term)
            payload = a.case_facets
            got = ([payload["industry"]["primary"]] if axis == "industry"
                   else slugs(payload, plural))
            self.assertIn(slug, got, "%s/%s via %r" % (axis, slug, term))

    def test_a_synonym_grounds_a_value_just_as_a_positive_term_does(self):
        entry = facets.entry("industry", "financial-services-insurance")
        synonym = (entry.get("synonyms") or [])[0]
        _, _, a = assigned(title="A case study",
                           summary="The organisation works in %s." % synonym)
        self.assertEqual(a.case_facets["industry"]["primary"],
                         "financial-services-insurance")
        self.assertEqual(a.case_facets["industry"]["evidence"][0]["matched_term"],
                         synonym)

    def test_every_asserted_value_carries_evidence_and_a_confidence(self):
        _, _, a = assigned(**HEALTHCARE)
        payload = a.case_facets
        self.assertTrue(payload["industry"]["evidence"])
        self.assertIsInstance(payload["industry"]["confidence"], float)
        for plural in ("business_functions", "use_case_types"):
            for value in payload[plural]:
                self.assertTrue(value["evidence"], value["slug"])
                self.assertGreater(value["confidence"], 0.0)

    def test_evidence_quotes_come_from_an_authorized_field(self):
        _, _, a = assigned(**HEALTHCARE)
        payload = a.case_facets
        everything = [payload["industry"]] + payload["business_functions"] + \
            payload["use_case_types"]
        for value in everything:
            for item in value["evidence"]:
                self.assertIn(item["field"], fa.EVIDENCE_FIELDS)
                self.assertGreaterEqual(len(item["matched_term"]), 2)
                self.assertGreaterEqual(len(item["quote"]), 3)
                self.assertLessEqual(len(item["quote"]), 400)


# ------------------------------------------------------- forbidden evidence
class TestForbiddenEvidence(unittest.TestCase):
    def test_the_publisher_can_never_ground_an_industry(self):
        term = first_term("industry", "financial-services-insurance")
        # the term exists ONLY in the publisher field
        _, _, a = assigned(title="An update", summary="A general note about work.",
                           publisher="Acme %s Group" % term)
        self.assertIsNone(a.case_facets["industry"]["primary"])
        self.assertEqual(a.case_facets["industry"]["evidence"], [])

    def test_the_same_term_in_the_summary_does_ground_it(self):
        term = first_term("industry", "financial-services-insurance")
        _, _, a = assigned(title="An update",
                           summary="The adopting organisation is a %s." % term)
        self.assertEqual(a.case_facets["industry"]["primary"],
                         "financial-services-insurance")

    def test_target_url_can_never_ground_technology_software(self):
        _, _, a = assigned(title="An update", summary="A general note.",
                           url="https://example.com/software/saas/platform/")
        self.assertNotEqual(a.case_facets["industry"]["primary"],
                            "technology-software")

    def test_the_committed_prohibitions_are_the_ones_applied(self):
        self.assertEqual(fa._allowed_fields("industry", "healthcare-life-sciences"),
                         ("title", "summary", "target_url"))
        self.assertEqual(fa._allowed_fields("industry", "technology-software"),
                         ("title", "summary"))
        self.assertEqual(fa._allowed_fields("business_function", "finance-accounting"),
                         fa.EVIDENCE_FIELDS)

    def test_a_business_function_may_still_use_the_publisher(self):
        # Only INDUSTRY carries the publisher prohibition.
        self.assertIn("publisher",
                      fa._allowed_fields("business_function", "finance-accounting"))


# ------------------------------------------------------- lexical support
class TestLexicalSupport(unittest.TestCase):
    def test_the_committed_set_is_what_is_enforced(self):
        self.assertEqual(sorted(facets.LEXICAL_SUPPORT_REQUIRED),
                         [("industry", "cross-industry"),
                          ("industry", "technology-software"),
                          ("use_case_type", "customer-interaction")])

    def test_a_support_required_value_is_refused_without_its_own_term(self):
        for axis, slug in sorted(facets.LEXICAL_SUPPORT_REQUIRED):
            _, _, a = assigned(title="A case study",
                               summary="A general description with no such term.")
            payload = a.case_facets
            got = ([payload["industry"]["primary"]] if axis == "industry"
                   else slugs(payload, facets.AXIS_PLURAL[axis]))
            self.assertNotIn(slug, got, "%s/%s" % (axis, slug))

    def test_every_asserted_value_passes_the_committed_support_gate(self):
        _, _, a = assigned(**HEALTHCARE)
        payload = a.case_facets
        primary = payload["industry"]["primary"]
        if primary and primary != facets.SENTINEL:
            self.assertTrue(facets.evidence_supports(
                "industry", primary, payload["industry"]["evidence"]))
        for axis, plural in (("business_function", "business_functions"),
                             ("use_case_type", "use_case_types")):
            for value in payload[plural]:
                self.assertTrue(facets.evidence_supports(
                    axis, value["slug"], value["evidence"]), value["slug"])


# ------------------------------------------------------------- ambiguity
class TestAmbiguity(unittest.TestCase):
    def tie(self):
        return assigned(title="A bank and a hospital",
                        summary="banking and healthcare together.")

    def test_a_tie_resolves_to_the_committed_sentinel(self):
        _, _, a = self.tie()
        self.assertEqual(a.case_facets["industry"]["primary"], facets.SENTINEL)

    def test_a_tie_records_every_competing_value(self):
        _, _, a = self.tie()
        entries = [u for u in a.case_facets["unresolved"]
                   if u["axis"] == "industry"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["state"], facets.SENTINEL)
        self.assertIn("financial-services-insurance", entries[0]["detail"])
        self.assertIn("healthcare-life-sciences", entries[0]["detail"])

    def test_a_tie_is_never_broken_by_slug_order(self):
        _, _, a = self.tie()
        self.assertNotEqual(a.case_facets["industry"]["primary"],
                            "financial-services-insurance")

    def test_a_clear_winner_is_not_treated_as_ambiguous(self):
        _, _, a = assigned(title="A hospital network",
                           summary="The clinical team at the hospital ran patient intake.")
        self.assertEqual(a.case_facets["industry"]["primary"],
                         "healthcare-life-sciences")

    def test_the_sentinel_is_never_matched_as_a_vocabulary_value(self):
        _, _, a = assigned(title="other unclear", summary="other-unclear content.")
        entries = [u for u in a.case_facets.get("unresolved", [])
                   if u["axis"] == "industry"]
        self.assertEqual(entries[0]["state"], "insufficient_evidence")


# ------------------------------------------------------ insufficient / states
class TestStates(unittest.TestCase):
    def test_no_evidence_yields_insufficient_evidence_on_every_axis(self):
        _, _, a = assigned(title="Notes from the field", summary="A short update.")
        states = {(u["axis"], u["state"]) for u in a.case_facets["unresolved"]}
        for axis in facets.AXES:
            self.assertIn((axis, "insufficient_evidence"), states, axis)

    def test_no_evidence_yields_an_unresolved_classification_state(self):
        _, _, a = assigned(title="Notes from the field", summary="A short update.")
        self.assertEqual(a.classification_state, "unresolved")

    def test_a_complete_assignment_is_resolved(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(a.classification_state, "resolved")

    def test_the_state_comes_from_facets_and_is_not_recomputed(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(a.classification_state,
                         facets.decide_classification_state(a.case_facets))

    def test_an_industry_alone_is_not_resolved(self):
        _, _, a = assigned(title="A hospital network",
                           summary="The clinical team at the hospital.")
        payload = a.case_facets
        if not payload["business_functions"] and not payload["use_case_types"]:
            self.assertEqual(a.classification_state, "unresolved")

    def test_a_short_vocabulary_term_can_match_an_unrelated_english_word(self):
        # Pinned, not papered over: `it-infrastructure` lists the term "IT",
        # which is a whole token in "ran it". Token matching is working exactly
        # as S4-3A specifies; the sharp edge is in the committed vocabulary, and
        # tuning it belongs to the stage that revisits the facet lists (CF-12).
        _, _, a = assigned(title="A hospital network",
                           summary="The hospital team ran it.")
        self.assertIn("it-infrastructure", slugs(a.case_facets,
                                                 "business_functions"))
        _, _, without = assigned(title="A hospital network",
                                 summary="A hospital.")
        self.assertEqual(slugs(without.case_facets, "business_functions"), [])

    def test_unresolved_entries_are_deterministically_ordered(self):
        _, _, a = assigned(title="Notes", summary="A short update.")
        keys = [(u["axis"], u["state"], u["detail"])
                for u in a.case_facets["unresolved"]]
        self.assertEqual(keys, sorted(keys))


# ------------------------------------------------------------ applicability
class TestApplicability(unittest.TestCase):
    def test_a_forbidden_topic_returns_explicit_not_applicable(self):
        for topic in sorted(facets.FACET_FORBIDDEN_TOPICS):
            _, _, a = assigned(topic=topic, category="community", **HEALTHCARE)
            self.assertFalse(a.applicable)
            self.assertIsNone(a.case_facets)
            self.assertIn(topic, a.reason)

    def test_not_applicable_is_not_an_empty_payload(self):
        # An empty payload would be counted `unresolved`; absent means
        # `not_enriched`. The two are different reviewer signals.
        _, _, a = assigned(topic="discourse", category="community", **HEALTHCARE)
        self.assertIsNone(a.case_facets)
        self.assertNotEqual(a.case_facets, {})

    def test_the_gated_cell_is_the_committed_one(self):
        _, _, a = assigned(topic="cases", category="domain-applications", **HEALTHCARE)
        self.assertTrue(a.gated)
        self.assertFalse(a.report_only)
        self.assertEqual(facets.FACET_GATED_CELLS,
                         frozenset({("cases", "domain-applications")}))

    def test_report_only_cells_are_assigned_but_not_gated(self):
        for category in ("case-studies", "product-discovery"):
            _, _, a = assigned(topic="cases", category=category, **HEALTHCARE)
            self.assertTrue(a.applicable)
            self.assertFalse(a.gated)
            self.assertTrue(a.report_only)
            self.assertIsInstance(a.case_facets, dict)

    def test_the_schema_requires_facets_exactly_where_this_module_assigns(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            branch = json.load(handle)["$defs"]["full_record"]
        required_rule, null_rule = branch["allOf"][0], branch["allOf"][1]
        self.assertEqual(required_rule["if"]["properties"]["topic"]["const"], "cases")
        self.assertEqual(
            required_rule["if"]["properties"]["primary_category"]["const"],
            "domain-applications")
        self.assertEqual(set(null_rule["if"]["properties"]["topic"]["enum"]),
                         set(facets.FACET_FORBIDDEN_TOPICS))


# ---------------------------------------------------------------- schema fit
class TestSchemaFit(unittest.TestCase):
    def validate(self, payload):
        return schema.validate({"case_facets": payload},
                               "facets.generated.v1.json")

    def test_a_complete_payload_validates(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(self.validate(a.case_facets), [])

    def test_an_empty_evidence_payload_validates(self):
        _, _, a = assigned(title="Notes", summary="A short update.")
        self.assertEqual(self.validate(a.case_facets), [])

    def test_a_tie_payload_validates(self):
        _, _, a = assigned(title="A bank and a hospital",
                           summary="banking and healthcare together.")
        self.assertEqual(self.validate(a.case_facets), [])

    def test_the_payload_carries_the_committed_required_keys(self):
        _, _, a = assigned(**HEALTHCARE)
        for key in ("facets_version", "vocabulary_versions",
                    "classification_state", "industry", "business_functions",
                    "use_case_types"):
            self.assertIn(key, a.case_facets, key)

    def test_vocabulary_versions_come_from_facets(self):
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(a.case_facets["vocabulary_versions"],
                         facets.vocabulary_versions())

    def test_multi_axes_respect_the_schema_cap(self):
        _, _, a = assigned(**HEALTHCARE)
        for plural in ("business_functions", "use_case_types"):
            self.assertLessEqual(len(a.case_facets[plural]), fa.MAX_MULTI_VALUES)

    def test_secondary_industries_are_left_empty_by_design(self):
        # `secondary` means DEPLOYMENT CONTEXT, a judgement lexical evidence
        # cannot make. Empty is honest; see CF-11.
        _, _, a = assigned(**HEALTHCARE)
        self.assertEqual(a.case_facets["industry"]["secondary"], [])


# --------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def batch(self, order=None):
        specs = [dict(HEALTHCARE),
                 dict(title="A bank automated underwriting",
                      summary="The insurer reduced fraud in its risk team."),
                 dict(title="Notes from the field", summary="A short update."),
                 dict(title="A bank and a hospital",
                      summary="banking and healthcare together.")]
        deliveries = []
        for index, spec in enumerate(specs):
            deliveries.append(dd.delivery(LANES[index % 2], AdapterResult(
                source_id="aws-ml-blog", adapter="feed", result="ok",
                candidates=(RawCandidate(
                    target_url="https://example.com/item-%d/" % index,
                    source_id="aws-ml-blog", adapter="feed", position=0,
                    **spec),))))
        if order is not None:
            deliveries = [deliveries[i] for i in order]
        extraction = ex.normalize_all(dd.group(deliveries, sources=SOURCES))
        classifications = cl.classify_all(extraction)
        return fa.assign_all(extraction, classifications)

    def test_every_permutation_gives_one_output(self):
        outputs = {serialize(self.batch(order))
                   for order in itertools.permutations(range(4))}
        self.assertEqual(len(outputs), 1)
        self.assertEqual(len(list(itertools.permutations(range(4)))), 24)

    def test_repeated_runs_are_byte_identical(self):
        self.assertEqual(serialize(self.batch()), serialize(self.batch()))

    def test_results_are_sorted_by_candidate_key(self):
        keys = [a.candidate_key for a in self.batch()]
        self.assertEqual(keys, sorted(keys))

    def test_evidence_order_is_stable_across_runs(self):
        first = assigned(**HEALTHCARE)[2].case_facets
        second = assigned(**HEALTHCARE)[2].case_facets
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_multi_axis_values_are_ordered_by_strength_then_slug(self):
        _, _, a = assigned(**HEALTHCARE)
        for plural in ("business_functions", "use_case_types"):
            keys = [(-len(v["evidence"]), v["slug"]) for v in a.case_facets[plural]]
            self.assertEqual(keys, sorted(keys), plural)

    def test_the_lane_cannot_influence_the_result(self):
        one = assigned(**HEALTHCARE)[2].case_facets
        other = fa.assign(
            candidate(lane=LANES[1], **HEALTHCARE),
            dataclasses.replace(cl.classify(candidate(lane=LANES[1], **HEALTHCARE)),
                                topic_slug="cases",
                                category_slug="domain-applications")).case_facets
        self.assertEqual(json.dumps(one, sort_keys=True),
                         json.dumps(other, sort_keys=True))

    def test_a_gap_lane_term_never_becomes_a_facet(self):
        # The lane names a healthcare gap; the document says nothing about it.
        _, _, a = assigned(lane=LANES[1], title="An update",
                           summary="A general note about work.")
        self.assertIsNone(a.case_facets["industry"]["primary"])


# ------------------------------------------------------------- no mutation
class TestNoMutation(unittest.TestCase):
    def test_classification_is_not_mutated(self):
        extracted = candidate(**HEALTHCARE)
        classification = dataclasses.replace(
            cl.classify(extracted), topic_slug="cases",
            category_slug="domain-applications")
        before = dataclasses.asdict(classification)
        fa.assign(extracted, classification)
        self.assertEqual(dataclasses.asdict(classification), before)

    def test_the_extracted_candidate_is_not_mutated(self):
        extracted = candidate(**HEALTHCARE)
        before = dataclasses.asdict(extracted)
        fa.assign(extracted, dataclasses.replace(
            cl.classify(extracted), topic_slug="cases",
            category_slug="domain-applications"))
        self.assertEqual(dataclasses.asdict(extracted), before)

    def test_verification_output_is_not_touched(self):
        extracted = candidate(**HEALTHCARE)
        classification = cl.classify(extracted)
        verdict = vf.verify(extracted, classification, clock="2026-07-30T00:00:00Z")
        before = (verdict.accepted, verdict.rejection_reason,
                  verdict.scores.payload())
        fa.assign(extracted, dataclasses.replace(
            classification, topic_slug="cases",
            category_slug="domain-applications"))
        self.assertEqual((verdict.accepted, verdict.rejection_reason,
                          verdict.scores.payload()), before)

    def test_the_vocabularies_are_not_mutated(self):
        before = copy.deepcopy(facets.load_all())
        assigned(**HEALTHCARE)
        self.assertEqual(facets.load_all(), before)

    def test_an_unclassified_candidate_is_refused(self):
        extraction = ex.normalize_all(dd.group(
            [dd.delivery(LANES[0], AdapterResult(
                source_id="aws-ml-blog", adapter="feed", result="ok",
                candidates=(RawCandidate(target_url="https://example.com/x/",
                                         source_id="aws-ml-blog", adapter="feed",
                                         position=0, title="x"),)))],
            sources=SOURCES))
        with self.assertRaises(fa.FacetAssignError):
            fa.assign_all(extraction, ())


# --------------------------------------------------------------- non-vacuity
class TestNonVacuity(unittest.TestCase):
    """Remove the supporting evidence and the facet must change. A matcher that
    assigns regardless would pass every positive test above and mean nothing."""

    def test_removing_the_industry_term_removes_the_industry(self):
        term = first_term("industry", "healthcare-life-sciences")
        with_term = assigned(title="A case study",
                             summary="The %s team ran the rollout." % term)[2]
        without = assigned(title="A case study",
                           summary="The team ran the rollout.")[2]
        self.assertEqual(with_term.case_facets["industry"]["primary"],
                         "healthcare-life-sciences")
        self.assertIsNone(without.case_facets["industry"]["primary"])

    def test_removing_a_function_term_removes_that_function(self):
        _, _, rich = assigned(**HEALTHCARE)
        poor = dict(HEALTHCARE)
        poor["summary"] = "The team ran the rollout."
        _, _, thin = assigned(**poor)
        self.assertTrue(slugs(rich.case_facets, "business_functions"))
        self.assertEqual(slugs(thin.case_facets, "business_functions"), [])

    def test_losing_the_supporting_axis_flips_the_classification_state(self):
        _, _, rich = assigned(**HEALTHCARE)
        # BOTH fields must lose their supporting terms: HEALTHCARE's title alone
        # grounds conversational-assistant, which is enough to stay resolved.
        _, _, thin = assigned(title="A hospital network", summary="A hospital.")
        self.assertEqual(rich.classification_state, "resolved")
        # an industry with no supported function or use case is NOT resolved
        self.assertEqual(thin.case_facets["industry"]["primary"],
                         "healthcare-life-sciences")
        self.assertEqual(slugs(thin.case_facets, "business_functions"), [])
        self.assertEqual(thin.classification_state, "unresolved")

    def test_moving_a_term_into_the_publisher_removes_the_industry(self):
        term = first_term("industry", "financial-services-insurance")
        grounded = assigned(title="A case", summary="A %s ran it." % term)[2]
        moved = assigned(title="A case", summary="An organisation ran it.",
                         publisher="Acme %s" % term)[2]
        self.assertEqual(grounded.case_facets["industry"]["primary"],
                         "financial-services-insurance")
        self.assertIsNone(moved.case_facets["industry"]["primary"])


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(inspect.getsource(fa))

    def imported(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.split(".")[0])
                names.update(a.name for a in node.names)
        return names

    def referenced(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return names

    def test_no_network_fetch_or_fixture_dependency(self):
        banned = {"urllib", "requests", "httpx", "aiohttp", "socket", "http",
                  "ssl", "subprocess", "asyncio", "xml", "html", "bs4", "lxml",
                  "httpclient", "HttpClient", "sourcecache", "fixtures",
                  "anthropic", "openai", "os", "io", "json"}
        self.assertEqual(self.imported() & banned, set())

    def test_no_pool_record_or_later_stage_dependency(self):
        banned = {"pool", "CandidatePool", "records", "coverage", "scheduler"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("make_full_record", "make_cross_reference",
                          "acquire_target_fetch", "acquire_extraction",
                          "add_candidate", "record_id", "content_id",
                          "schema_version", "resolve_cross_topic"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_it_does_not_score_or_verify(self):
        banned = {"verify", "VerifyError", "Scores", "Verdict"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("relevance", "quality", "audience_fit", "composite",
                          "accepted", "rejection_reason"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_lane_and_ownership_fields_are_unreadable_from_here(self):
        for forbidden in ("lane_id", "lane_ids", "source_request_key",
                          "source_request_keys", "owner_lane_id",
                          "target_fetch_owner", "extraction_owner",
                          "contributing_lanes", "observations"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_it_reuses_the_committed_matcher_and_vocabularies(self):
        imported = self.imported()
        self.assertIn("classify", imported)
        self.assertIn("facets", imported)
        self.assertNotIn("re", imported)
        called = {n.func.attr for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("_find_term", called)
        self.assertIn("_tokenize", called)
        self.assertIn("evidence_supports", called)
        self.assertIn("decide_classification_state", called)

    def test_no_slug_or_vocabulary_term_is_hard_coded(self):
        literals = {node.value for node in ast.walk(self.tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str)}
        docstrings = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        literals -= docstrings
        # One slug is unavoidably named: the committed prohibition is
        # slug-specific and facets.py encodes the slug in the constant's NAME
        # rather than exposing it as data. Pinned so it cannot drift.
        allowed_slug = "technology-software"
        self.assertIn(allowed_slug.upper().replace("-", "_"),
                      "TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS")
        self.assertIn(allowed_slug, facets.slugs("industry"))
        for axis in facets.AXES:
            for slug in facets.slugs(axis):
                if slug in (facets.SENTINEL, allowed_slug):
                    continue          # referenced via facets.SENTINEL, or above
                self.assertNotIn(slug, literals, slug)
                for term in (facets.entry(axis, slug).get("positive_terms") or []):
                    # A term that happens to equal an evidence field name
                    # ("publisher" is a media-entertainment term, "summary" a
                    # summarization one) collides with a legitimate literal.
                    if term in fa.EVIDENCE_FIELDS:
                        continue
                    self.assertNotIn(term, literals, term)

    def test_it_never_writes_a_file(self):
        called = {n.func.id for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("open", called)
        self.assertNotIn("print", called)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("FacetAssignment", "assign", "assign_all", "applicability",
                     "FacetAssignError"):
            self.assertTrue(hasattr(fa, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
