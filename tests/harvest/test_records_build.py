#!/usr/bin/env python3
"""test_records_build.py — in-memory record construction and schema validation (S4-5B).

This is the seam where every earlier stage's output becomes a record. Nothing is
written: candidates are deduped, normalized, classified, scored and faceted in
memory, handed to the UNMODIFIED `records.make_full_record` /
`make_cross_reference`, and validated against `record.v1.json`.

The properties that carry the weight:

  * THE TWO `case_facets` CONDITIONALS ARE REAL. A `cases__domain-applications`
    full record MUST carry facets, and a `research-and-models` or `discourse`
    full record may not carry them at all. Both are asserted from the schema's
    own behaviour — a record that breaks either is refused, not merely warned
    about. The conditionals live inside the full-record branch precisely so a
    `cases__domain-applications` CROSS_REFERENCE row stays satisfiable.
  * A CROSS_REFERENCE IS A POINTER. Its property set is closed, so it cannot
    carry a title, a score, or `case_facets`. That is what stops a duplicate
    being counted as independent content in a second category.
  * FACETS ARE INERT FOR IDENTITY. Adding, changing or removing `case_facets`
    must not move `record_id`, `content_id`, `identity_url` or `cell_id` —
    identity comes from `urlkey`, which never reads a facet.
  * ORDER IS A FUNCTION OF CONTENT. Artifact order is
    `(topic, primary_category, record_id)`, so shuffled input yields a
    byte-identical artifact.
  * THE TWO EVIDENCE SYSTEMS STAY APART. `classification.evidence` is the
    category's, `case_facets[...].evidence` is the vocabulary's. A facet term
    must never appear in the classification's evidence.

Offline and in-memory: no network, no fixtures, no CandidatePool, no file
writes. Run via tests/test_taxonomy_records.sh.
"""
import copy
import dataclasses
import inspect
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import classify as cl, dedupe as dd, extract as ex           # noqa: E402
from src.harvest import facetassign as fa, facets, records, schema            # noqa: E402
from src.harvest import urlkey, verify as vf                                  # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate             # noqa: E402

RUN = "20260730T120000Z-4242"
NOW = "2026-07-30T12:00:00Z"

# Two discovery sources in different cells. `aws-ml-blog` is the vendor whose
# publisher name must never ground an industry.
SOURCES = {
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
}
CASE_LANE = "cell__cases__domain-applications"

# A document that grounds all three axes from the committed vocabularies.
CASE_DOC = dict(
    title="A hospital network deployed an assistant for patient intake",
    summary="The clinical team automated scheduling and billing for the finance "
            "department, improving customer support response times across the "
            "contact centre.")


def cell_id(topic, category):
    return "%s__%s" % (topic, category)


def extracted_for(source_id="aws-ml-blog", lane=CASE_LANE,
                  url="https://example.com/item/", **payload):
    item = RawCandidate(target_url=url, source_id=source_id, adapter="feed",
                        position=0, **payload)
    result = AdapterResult(source_id=source_id, adapter="feed", result="ok",
                           candidates=(item,))
    deduped = dd.group([dd.delivery(lane, result)], sources=SOURCES)
    return ex.normalize_all(deduped).candidates[0]


def pipeline(topic="cases", category="domain-applications",
             source_id="aws-ml-blog", url="https://example.com/item/", **spec):
    """dedupe -> extract -> classify -> verify -> facetassign, in memory."""
    extracted = extracted_for(source_id=source_id, url=url, **spec)
    classification = dataclasses.replace(cl.classify(extracted),
                                         topic_slug=topic, category_slug=category)
    verdict = vf.verify(extracted, classification)
    assignment = fa.assign(extracted, classification)
    return extracted, classification, verdict, assignment


def build_full(topic="cases", category="domain-applications",
               source_id="aws-ml-blog", url="https://example.com/item/",
               with_facets=True, **spec):
    """The S4-5B builder: pipeline output -> records.make_full_record."""
    extracted, classification, verdict, assignment = pipeline(
        topic=topic, category=category, source_id=source_id, url=url, **spec)
    payload = assignment.case_facets if (with_facets and assignment.applicable) else None
    rec = records.make_full_record(
        record_id=urlkey.record_id(topic, extracted.identity_url),
        content_id=extracted.content_id,
        topic_slug=topic, category_slug=category,
        cell_id=cell_id(topic, category),
        identity_url=extracted.identity_url,
        target_url=extracted.target_url,
        canonical_url=extracted.canonical_url,
        harvest_run_id=RUN, source_id=source_id, source_adapter="feed",
        title=extracted.title, summary=extracted.summary,
        publisher=extracted.publisher, author=extracted.author,
        published_at=extracted.published_at, language=extracted.language,
        content_type=extracted.content_type,
        discovered_at=NOW,
        access_status=verdict.access_status,
        http_status=verdict.http_status,
        verification_status=verdict.verification_status,
        verification_evidence=verdict.verification_evidence,
        relevance_score=verdict.scores.relevance,
        quality_score=verdict.scores.quality,
        audience_fit_score=verdict.scores.audience_fit,
        freshness_score=verdict.scores.freshness,
        content_hash=verdict.content_hash,
        classification={
            "rule_id": classification.rule_id,
            "rationale": classification.rationale,
            # The record schema admits {signal, matched} only — `field` lives on
            # classify.Evidence but is deliberately not carried onto a record.
            "evidence": [{"signal": e.signal, "matched": e.matched}
                         for e in classification.evidence],
            "competing_categories": [
                {"topic": c.topic, "category": c.category, "rule_id": c.rule_id}
                for c in classification.competing_categories],
        },
        raw=extracted.provenance_raw,
        case_facets=payload)
    return rec, assignment, classification


def build_cross_reference(topic="discourse", category="insights-and-opinions",
                          url="https://example.com/item/"):
    return records.make_cross_reference(
        record_id=urlkey.record_id(topic, url),
        content_id=urlkey.content_id(url),
        identity_url=url, topic_slug=topic, category_slug=category,
        duplicate_of=urlkey.record_id("cases", url),
        owner_topic="cases", reason="owned by cases/domain-applications",
        harvest_run_id=RUN, discovered_at=NOW,
        cell_id=cell_id(topic, category))


def errors(record):
    return schema.validate(record, "record.v1.json")


# --------------------------------------------------------------- construction
class TestFullRecordConstruction(unittest.TestCase):
    def test_a_case_record_is_built_and_validates(self):
        rec, _, _ = build_full(**CASE_DOC)
        self.assertEqual(errors(rec), [])
        self.assertEqual(rec["record_type"], "full")
        self.assertEqual(rec["schema_version"], records.SCHEMA_VERSION)

    def test_the_builder_is_the_committed_unmodified_one(self):
        # S4-5B adds no production module: it calls records.py as shipped.
        self.assertTrue(inspect.isfunction(records.make_full_record))
        self.assertTrue(inspect.isfunction(records.make_cross_reference))
        params = inspect.signature(records.make_full_record).parameters
        self.assertIn("case_facets", params)
        self.assertIsNone(params["case_facets"].default)

    def test_every_schema_required_key_is_present(self):
        rec, _, _ = build_full(**CASE_DOC)
        required = schema.load_schema("record.v1.json")["$defs"]["full_record"]["required"]
        for key in required:
            self.assertIn(key, rec, key)

    def test_scores_reach_the_record_from_verify(self):
        rec, _, _ = build_full(**CASE_DOC)
        _, _, verdict, _ = pipeline(**CASE_DOC)
        self.assertEqual(rec["relevance_score"], verdict.scores.relevance)
        self.assertEqual(rec["quality_score"], verdict.scores.quality)
        self.assertEqual(rec["audience_fit_score"], verdict.scores.audience_fit)

    def test_an_unfetched_record_is_honest_about_it(self):
        rec, _, _ = build_full(**CASE_DOC)
        self.assertEqual(rec["access_status"], "not_checked")
        self.assertEqual(rec["verification_status"], "unverified")

    def test_nothing_is_written(self):
        before = {p: os.path.getmtime(p) for p in
                  ("config/harvest/facets", "schemas/harvest", "src/harvest")}
        build_full(**CASE_DOC)
        build_cross_reference()
        after = {p: os.path.getmtime(p) for p in before}
        self.assertEqual(before, after)
        self.assertFalse(os.path.exists("state/taxonomy_harvest"))
        self.assertFalse(os.path.exists("data/harvested"))


# ----------------------------------------------------- the case_facets conditional
class TestCaseFacetsConditional(unittest.TestCase):
    def test_a_domain_applications_record_carries_facets(self):
        rec, assignment, _ = build_full(**CASE_DOC)
        self.assertTrue(assignment.applicable)
        self.assertIn("case_facets", rec)
        self.assertEqual(errors(rec), [])

    def test_a_domain_applications_record_without_facets_is_refused(self):
        rec, _, _ = build_full(with_facets=False, **CASE_DOC)
        self.assertNotIn("case_facets", rec)
        self.assertNotEqual(errors(rec), [])

    def test_the_conditional_is_satisfied_from_committed_vocabularies_alone(self):
        # The S4-5B stop condition: if this fails, no committed vocabulary can
        # satisfy the schema's own requirement and the checkpoint must halt.
        rec, _, _ = build_full(**CASE_DOC)
        self.assertIsInstance(rec["case_facets"], dict)
        self.assertEqual(errors(rec), [])

    def test_a_research_record_with_facets_is_refused(self):
        rec, _, _ = build_full(topic="research-and-models", category="papers",
                               **CASE_DOC)
        rec["case_facets"] = {"facets_version": facets.FACETS_VERSION}
        self.assertNotEqual(errors(rec), [])

    def test_a_discourse_record_with_facets_is_refused(self):
        rec, _, _ = build_full(topic="discourse", category="insights-and-opinions",
                               **CASE_DOC)
        rec["case_facets"] = {"facets_version": facets.FACETS_VERSION}
        self.assertNotEqual(errors(rec), [])

    def test_a_forbidden_topic_omits_facets_and_validates(self):
        for topic, category in (("research-and-models", "papers"),
                                ("discourse", "insights-and-opinions")):
            rec, assignment, _ = build_full(topic=topic, category=category, **CASE_DOC)
            self.assertFalse(assignment.applicable, topic)
            self.assertNotIn("case_facets", rec)
            self.assertEqual(errors(rec), [], topic)

    def test_an_explicit_null_is_also_accepted_for_a_forbidden_topic(self):
        rec, _, _ = build_full(topic="discourse", category="insights-and-opinions",
                               **CASE_DOC)
        rec["case_facets"] = None
        self.assertEqual(errors(rec), [])

    def test_the_forbidden_topics_are_the_committed_ones(self):
        rule = schema.load_schema("record.v1.json")["$defs"]["full_record"]["allOf"][1]
        self.assertEqual(set(rule["if"]["properties"]["topic"]["enum"]),
                         set(facets.FACET_FORBIDDEN_TOPICS))


# ------------------------------------------------------------- facet integrity
class TestFacetIntegrity(unittest.TestCase):
    def test_the_industry_comes_from_the_customer_not_the_publisher(self):
        rec, _, _ = build_full(**CASE_DOC)
        industry = rec["case_facets"]["industry"]
        self.assertEqual(industry["primary"], "healthcare-life-sciences")
        for ev in industry["evidence"]:
            self.assertNotEqual(ev["field"], "publisher")

    def test_an_industry_named_only_by_the_publisher_is_refused(self):
        rec, _, _ = build_full(title="An update", summary="A short note.",
                               publisher="Hospital Health Systems")
        # Non-vacuous: the payload IS built, the industry is simply ungrounded.
        self.assertIn("case_facets", rec)
        self.assertIsNone(rec["case_facets"]["industry"]["primary"])
        # Positive control — the same term in an authorized field does ground it.
        grounded, _, _ = build_full(title="An update",
                                    summary="The hospital clinical team ran intake.")
        self.assertEqual(grounded["case_facets"]["industry"]["primary"],
                         "healthcare-life-sciences")

    def test_technology_software_is_never_earned_from_the_target_url(self):
        rec, _, _ = build_full(url="https://software.example.com/saas-platform/",
                               title="An update", summary="A short note.")
        self.assertIn("case_facets", rec)
        self.assertIsNone(rec["case_facets"]["industry"]["primary"])
        self.assertIn("software", rec["target_url"])

    def test_every_facet_evidence_entry_has_the_committed_shape(self):
        rec, _, _ = build_full(**CASE_DOC)
        payload = rec["case_facets"]
        seen = list(payload["industry"]["evidence"])
        for plural in ("business_functions", "use_case_types"):
            for value in payload[plural]:
                seen.extend(value["evidence"])
        self.assertTrue(seen)
        for ev in seen:
            self.assertEqual(set(ev) - {"offset"}, {"field", "matched_term", "quote"})
            self.assertIn(ev["field"], ("title", "summary", "publisher", "target_url"))
            self.assertGreaterEqual(len(ev["matched_term"]), 2)
            self.assertTrue(3 <= len(ev["quote"]) <= 400)

    def test_every_quote_is_taken_from_the_document(self):
        rec, _, classification = build_full(**CASE_DOC)
        _, _, _, assignment = pipeline(**CASE_DOC)
        extracted = extracted_for(**CASE_DOC)
        fields = {"title": extracted.title, "summary": extracted.summary,
                  "publisher": extracted.publisher, "target_url": extracted.target_url}
        payload = rec["case_facets"]
        seen = list(payload["industry"]["evidence"])
        for plural in ("business_functions", "use_case_types"):
            for value in payload[plural]:
                seen.extend(value["evidence"])
        for ev in seen:
            source = fields.get(ev["field"]) or ""
            self.assertIn(ev["quote"], source, ev)

    def test_lexical_support_required_values_carry_their_own_term(self):
        rec, _, _ = build_full(**CASE_DOC)
        payload = rec["case_facets"]
        for axis, plural in facets.AXIS_PLURAL.items():
            if axis == "industry":
                values = [(payload["industry"]["primary"], payload["industry"]["evidence"])]
            else:
                values = [(v["slug"], v["evidence"]) for v in payload[plural]]
            for slug, evidence in values:
                if slug and (axis, slug) in facets.LEXICAL_SUPPORT_REQUIRED:
                    self.assertTrue(facets.evidence_supports(axis, slug, evidence),
                                    "%s/%s" % (axis, slug))

    def test_classification_state_comes_from_facets(self):
        rec, _, _ = build_full(**CASE_DOC)
        payload = rec["case_facets"]
        self.assertEqual(payload["classification_state"],
                         facets.decide_classification_state(payload))

    def test_vocabulary_versions_come_from_facets(self):
        rec, _, _ = build_full(**CASE_DOC)
        self.assertEqual(rec["case_facets"]["vocabulary_versions"],
                         facets.vocabulary_versions())

    def test_a_resolved_record_is_distinguishable_from_an_unresolved_one(self):
        resolved, _, _ = build_full(**CASE_DOC)
        unresolved, _, _ = build_full(title="Notes from the field",
                                      summary="A short update.")
        self.assertEqual(resolved["case_facets"]["classification_state"], "resolved")
        self.assertEqual(unresolved["case_facets"]["classification_state"], "unresolved")
        self.assertEqual(errors(resolved), [])
        self.assertEqual(errors(unresolved), [])

    def test_the_sentinel_and_the_four_unresolved_states_are_the_committed_ones(self):
        self.assertEqual(facets.SENTINEL, "other-unclear")
        self.assertEqual(len(facets.UNRESOLVED_STATES), 4)
        for state in ("other-unclear", "unmapped_legacy_value",
                      "insufficient_evidence", "not_applicable"):
            self.assertIn(state, facets.UNRESOLVED_STATES)

    def test_a_tie_reaches_the_record_as_the_sentinel(self):
        rec, _, _ = build_full(title="A bank and a hospital",
                               summary="banking and healthcare together.")
        industry = rec["case_facets"]["industry"]
        if industry["primary"] == facets.SENTINEL:
            competing = [u for u in rec["case_facets"]["unresolved"]
                         if u["axis"] == "industry"]
            self.assertTrue(competing)
        self.assertEqual(errors(rec), [])

    def test_an_unresolved_record_still_validates(self):
        rec, _, _ = build_full(title="Notes from the field",
                               summary="A short update.")
        states = {u["state"] for u in rec["case_facets"]["unresolved"]}
        self.assertTrue(states <= set(facets.UNRESOLVED_STATES))
        self.assertEqual(errors(rec), [])


# ------------------------------------------------------- the two evidence systems
class TestEvidenceSeparation(unittest.TestCase):
    def test_facet_terms_never_leak_into_classification_evidence(self):
        rec, _, _ = build_full(**CASE_DOC)
        payload = rec["case_facets"]
        facet_terms = {ev["matched_term"].lower()
                       for ev in payload["industry"]["evidence"]}
        for plural in ("business_functions", "use_case_types"):
            for value in payload[plural]:
                facet_terms |= {ev["matched_term"].lower() for ev in value["evidence"]}
        classification_terms = {e["matched"].lower()
                                for e in rec["classification"]["evidence"]}
        self.assertEqual(facet_terms & classification_terms, set())

    def test_facetassign_and_classify_share_no_evidence_constructor(self):
        fa_src = inspect.getsource(fa)
        self.assertNotIn("cl.Evidence", fa_src)
        self.assertNotIn("classify.Evidence", fa_src)
        # facetassign builds plain dicts for facet evidence; classify's Evidence
        # dataclass is the category system's and must not appear in a payload.
        rec, _, _ = build_full(**CASE_DOC)
        for ev in rec["case_facets"]["industry"]["evidence"]:
            self.assertIsInstance(ev, dict)
            self.assertNotIn("signal", ev)

    def test_the_two_systems_use_different_keys(self):
        rec, _, _ = build_full(**CASE_DOC)
        if rec["classification"]["evidence"]:
            self.assertEqual(set(rec["classification"]["evidence"][0]),
                             {"signal", "matched"})
        self.assertEqual(set(rec["case_facets"]["industry"]["evidence"][0])
                         - {"offset"},
                         {"field", "matched_term", "quote"})

    def test_the_record_schema_narrows_classification_evidence(self):
        # classify.Evidence carries `field`; the record schema deliberately does
        # not admit it, so a builder that forwards the dataclass wholesale is
        # refused rather than silently widening the record.
        item = (schema.load_schema("record.v1.json")["$defs"]["classification"]
                ["properties"]["evidence"]["items"])
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(set(item["properties"]), {"signal", "matched"})
        self.assertIn("field", {f.name for f in dataclasses.fields(cl.Evidence)})
        rec, _, _ = build_full(topic="research-and-models", category="papers",
                               source_id="openai-news",
                               title="A benchmark paper",
                               summary="We evaluate a model.")
        self.assertTrue(rec["classification"]["evidence"])
        widened = copy.deepcopy(rec)
        widened["classification"]["evidence"][0]["field"] = "title"
        self.assertNotEqual(errors(widened), [])


# ------------------------------------------------------------------- identity
class TestIdentityIsInertToFacets(unittest.TestCase):
    def test_facets_do_not_move_any_identity_field(self):
        with_f, _, _ = build_full(**CASE_DOC)
        without, _, _ = build_full(with_facets=False, **CASE_DOC)
        for key in ("record_id", "content_id", "identity_url", "cell_id",
                    "canonical_url", "target_url"):
            self.assertEqual(with_f[key], without[key], key)

    def test_identity_comes_from_urlkey_not_from_a_facet(self):
        rec, _, _ = build_full(**CASE_DOC)
        self.assertEqual(rec["record_id"],
                         urlkey.record_id("cases", rec["identity_url"]))
        self.assertEqual(rec["content_id"], urlkey.content_id(rec["identity_url"]))

    def test_urlkey_never_reads_a_facet(self):
        src = inspect.getsource(urlkey)
        self.assertNotIn("case_facets", src)
        self.assertNotIn("facets", src)

    def test_mutating_facets_changes_no_id(self):
        rec, _, _ = build_full(**CASE_DOC)
        before = (rec["record_id"], rec["content_id"], rec["cell_id"])
        rec["case_facets"]["business_functions"] = []
        after = (rec["record_id"], rec["content_id"], rec["cell_id"])
        self.assertEqual(before, after)


# ------------------------------------------------------------ cross_reference
class TestCrossReference(unittest.TestCase):
    def test_a_cross_reference_is_built_and_validates(self):
        row = build_cross_reference()
        self.assertEqual(errors(row), [])
        self.assertEqual(row["record_type"], "cross_reference")

    def test_it_cannot_carry_a_full_record_field(self):
        for field, value in (("title", "A title"),
                             ("summary", "A summary"),
                             ("relevance_score", 0.9),
                             ("classification", {"rule_id": "R10"}),
                             ("case_facets", {"facets_version": 1})):
            row = build_cross_reference()
            row[field] = value
            self.assertNotEqual(errors(row), [], field)

    def test_a_case_cross_reference_row_stays_satisfiable(self):
        # The conditional lives inside the full-record branch precisely so this
        # row is not made impossible for one of the twelve cells.
        row = build_cross_reference(topic="cases", category="domain-applications")
        self.assertEqual(errors(row), [])
        self.assertNotIn("case_facets", row)

    def test_it_points_at_the_owner(self):
        row = build_cross_reference()
        self.assertEqual(row["owner_topic"], "cases")
        self.assertTrue(row["duplicate_of"])
        self.assertNotEqual(row["record_id"], row["duplicate_of"])


# ------------------------------------------------------------------ ordering
class TestDeterminism(unittest.TestCase):
    def corpus(self):
        specs = [
            ("cases", "domain-applications", "https://example.com/a/", CASE_DOC),
            ("cases", "case-studies", "https://example.com/b/",
             dict(title="A retailer rolled out forecasting",
                  summary="The supply chain team improved demand forecasting.")),
            ("research-and-models", "papers", "https://example.com/c/",
             dict(title="A benchmark paper", summary="We evaluate a model.")),
            ("discourse", "insights-and-opinions", "https://example.com/d/",
             dict(title="An opinion", summary="A short essay on adoption.")),
        ]
        out = []
        for topic, category, url, doc in specs:
            source = "aws-ml-blog" if topic == "cases" else "openai-news"
            rec, _, _ = build_full(topic=topic, category=category,
                                   source_id=source, url=url, **doc)
            out.append(rec)
        return out

    def test_the_whole_corpus_validates(self):
        for rec in self.corpus():
            self.assertEqual(errors(rec), [], rec["record_id"])

    def test_the_sort_key_is_the_committed_triple(self):
        rec = self.corpus()[0]
        self.assertEqual(records.sort_key(rec),
                         (rec["topic"], rec["primary_category"], rec["record_id"]))

    def test_records_are_sorted_by_that_triple(self):
        ordered = records.sort_records(self.corpus())
        keys = [records.sort_key(r) for r in ordered]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_input_yields_identical_output(self):
        base = records.sort_records(self.corpus())
        expected = json.dumps(base, sort_keys=True)
        rng = random.Random(20260730)
        for _ in range(5):
            shuffled = self.corpus()
            rng.shuffle(shuffled)
            got = json.dumps(records.sort_records(shuffled), sort_keys=True)
            self.assertEqual(got, expected)

    def test_repeated_construction_is_byte_identical(self):
        first = json.dumps(records.sort_records(self.corpus()), sort_keys=True)
        second = json.dumps(records.sort_records(self.corpus()), sort_keys=True)
        self.assertEqual(first, second)

    def test_a_mixed_artifact_of_records_and_pointers_validates_and_orders(self):
        items = self.corpus() + [build_cross_reference()]
        for item in items:
            self.assertEqual(errors(item), [], item["record_id"])
        keys = [records.sort_key(r) for r in records.sort_records(items)]
        self.assertEqual(keys, sorted(keys))


# --------------------------------------------------------------- no mutation
class TestNoMutation(unittest.TestCase):
    def test_building_a_record_does_not_mutate_the_assignment(self):
        _, _, _, assignment = pipeline(**CASE_DOC)
        before = copy.deepcopy(assignment.case_facets)
        records.make_full_record(
            record_id="r", content_id="c", topic_slug="cases",
            category_slug="domain-applications", cell_id="cases__domain-applications",
            identity_url="https://example.com/x/", target_url="https://example.com/x/",
            harvest_run_id=RUN, source_id="aws-ml-blog", source_adapter="feed",
            discovered_at=NOW, case_facets=assignment.case_facets)
        self.assertEqual(assignment.case_facets, before)

    def test_the_vocabularies_are_not_mutated(self):
        before = copy.deepcopy(facets.load_all())
        build_full(**CASE_DOC)
        self.assertEqual(facets.load_all(), before)

    def test_two_records_do_not_share_a_facet_payload(self):
        a, _, _ = build_full(url="https://example.com/one/", **CASE_DOC)
        b, _, _ = build_full(url="https://example.com/two/", **CASE_DOC)
        self.assertIsNot(a["case_facets"], b["case_facets"])
        a["case_facets"]["business_functions"] = []
        self.assertNotEqual(a["case_facets"]["business_functions"],
                            b["case_facets"]["business_functions"])


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def test_s4_5b_adds_no_production_module(self):
        # The checkpoint is test-only: records.py and facetassign.py are the
        # committed ones, and no new module sits between them.
        self.assertFalse(os.path.exists(os.path.join(ROOT, "src", "harvest",
                                                     "recordbuild.py")))

    def test_no_artifact_directory_is_created(self):
        build_full(**CASE_DOC)
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_the_record_schema_is_the_committed_one(self):
        doc = schema.load_schema("record.v1.json")
        self.assertEqual(len(doc["oneOf"]), 2)
        self.assertEqual(len(doc["$defs"]["full_record"]["allOf"]), 2)

    def test_no_network_or_pool_dependency(self):
        src = inspect.getsource(records)
        for forbidden in ("requests", "urllib.request", "httpclient", "CandidatePool"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
