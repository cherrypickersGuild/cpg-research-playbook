#!/usr/bin/env python3
"""test_classify.py — the ten committed precedence rules, evaluated (S4-3).

The properties that carry the weight:

  * ORDER. R6 beats R7 so an eval-bearing paper is a benchmark, not a paper; R4
    beats R9 so a model release is not commentary. Both are proved with inputs
    where BOTH rules' signals fire.
  * `none_of` REALLY EXCLUDES. A developer tool whose `is_end_user_product`
    signal fires is still kept out of Product Discovery, and falls back rather
    than being reclassified there.
  * NON-VACUITY. Every rule test has a paired negative: remove the evidence and
    the rule stops firing. A rule that fires on everything proves nothing.
  * NOTHING FROM THE LANE. A `lane_id`, a request key and an ownership
    designation are not evidence, are not readable from classify.py, and cannot
    change a result.

Driven by the real config and the real S4-1/S4-2 pipeline. Offline; no network,
no model, no facets, no scoring, no records. Run via tests/test_taxonomy_classify.sh.
"""
import ast
import inspect
import itertools
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import classify as cl, dedupe as dd, extract as ex        # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate          # noqa: E402

PRECEDENCE_PATH = os.path.join(ROOT, "config", "harvest", "precedence.v1.json")
RECORD_SCHEMA_PATH = os.path.join(ROOT, "schemas", "harvest", "record.v1.json")

LANES = ("cell__cases__case-studies",
         "gap__business_function__marketing",
         "gap__industry__healthcare-life-sciences")

SOURCES = {
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "techcrunch-ai": {"source_id": "techcrunch-ai", "topic_slug": "discourse",
                      "category_slug": "market-and-investment", "adapter": "feed",
                      "role": "discovery"},
    "anthropic-customers": {"source_id": "anthropic-customers", "topic_slug": "cases",
                            "category_slug": "case-studies", "adapter": "seed",
                            "role": "validation_seed"},
}


def candidate(title=None, summary=None, publisher=None,
              url="https://example.com/item/", source_id="openai-news",
              lane=LANES[0]):
    """One ExtractedCandidate through the real S4-1 -> S4-2 pipeline."""
    item = RawCandidate(target_url=url, source_id=source_id,
                        adapter=SOURCES[source_id]["adapter"], position=0,
                        title=title, summary=summary, publisher=publisher)
    result = AdapterResult(source_id=source_id,
                           adapter=SOURCES[source_id]["adapter"],
                           result="ok", candidates=(item,))
    deduped = dd.group([dd.delivery(lane, result)], sources=SOURCES)
    return ex.normalize_all(deduped).candidates[0]


def cell(classification):
    return (classification.topic_slug, classification.category_slug)


def serialize(classifications):
    return json.dumps([{
        "candidate_key": c.candidate_key,
        "cell": list(cell(c)),
        "rule_id": c.rule_id,
        "rationale": c.rationale,
        "payload": c.payload(),
        "matched_rule_ids": list(c.matched_rule_ids),
        "contexts": [list(x) for x in c.contexts],
    } for c in classifications], sort_keys=True)


# ---- inputs designed one per rule, verified against the committed config ----
R1 = dict(title="How Acme Corp cut resolution time by 38%",
          summary="Deployed in production across support.")
R2 = dict(title="Best practice for healthcare intake workflows",
          summary="A playbook teams can adopt.")
R3 = dict(title="Meet Lumen, a scheduling app for small teams",
          summary="Sign up today.")
R3_TOOL = dict(title="Forge, a developer tool product launch",
               summary="For teams shipping software.")
R4 = dict(title="Introducing Atlas 3, our new model", summary="Better reasoning.")
R5 = dict(title="Northwind raised a Series B", summary="Investors backed the round.")
R6 = dict(title="We release a new benchmark for retrieval",
          summary="Scores across tasks.")
R6_OVER_R7 = dict(title="Abstract: we propose a new benchmark suite",
                  summary="Experiments show gains.")
R7 = dict(title="Abstract: we propose a sparse attention method",
          summary="Our method improves long documents.")
R8 = dict(title="How we built our streaming ingestion architecture",
          summary="Latency and throughput under the hood.")
R8_BLOCKED = dict(title="Scaling internals at Acme reduced latency by 30%",
                  summary="Numbers from the rollout window.")
R9 = dict(title="The case for smaller models",
          summary="My take: this will change how teams buy.")
R4_OVER_R9 = dict(title="The case for our new model, and what this means",
                  summary="A shift.")
R10 = dict(title="Notes from the field", summary="A short update.",
           url="https://example.com/notes/")
R1_AND_R3 = dict(title="How Acme Corp cut resolution time by 38% with our app",
                 summary="Deployed in production.")


# ------------------------------------------------------------------ each rule
class TestEveryRuleFires(unittest.TestCase):
    def assert_rule(self, spec, rule_id, expected_cell):
        got = cl.classify(candidate(**spec))
        self.assertEqual(got.rule_id, rule_id)
        self.assertEqual(cell(got), expected_cell)
        return got

    def test_r1_named_org_with_implementation_and_results(self):
        got = self.assert_rule(R1, "R1_org_implementation_with_results",
                               ("cases", "case-studies"))
        signals = {e.signal for e in got.evidence}
        self.assertEqual(signals, {"has_named_organization",
                                   "has_concrete_implementation",
                                   "has_measurable_outcome"})

    def test_r2_industry_pattern(self):
        self.assert_rule(R2, "R2_industry_pattern",
                         ("cases", "domain-applications"))

    def test_r3_end_user_product(self):
        self.assert_rule(R3, "R3_end_user_product",
                         ("cases", "product-discovery"))

    def test_r4_model_release(self):
        self.assert_rule(R4, "R4_model_release",
                         ("research-and-models", "model-updates"))

    def test_r5_funding_event(self):
        self.assert_rule(R5, "R5_funding_event",
                         ("discourse", "market-and-investment"))

    def test_r6_eval_resource(self):
        self.assert_rule(R6, "R6_eval_resource",
                         ("research-and-models", "benchmark-and-datasets"))

    def test_r7_academic_primary(self):
        self.assert_rule(R7, "R7_academic_primary",
                         ("research-and-models", "papers"))

    def test_r8_engineering_analysis(self):
        self.assert_rule(R8, "R8_engineering_analysis",
                         ("discourse", "technical-deep-dives"))

    def test_r9_opinion_thesis(self):
        self.assert_rule(R9, "R9_opinion_thesis",
                         ("discourse", "insights-and-opinions"))

    def test_r10_falls_back_to_the_discovery_cell(self):
        got = cl.classify(candidate(source_id="techcrunch-ai", **R10))
        self.assertEqual(got.rule_id, cl.FALLBACK_RULE_ID)
        self.assertEqual(cell(got), ("discourse", "market-and-investment"))
        self.assertTrue(got.used_fallback)
        self.assertEqual(got.evidence, ())

    def test_all_ten_committed_rules_are_reachable(self):
        document = cl.load_precedence()
        self.assertEqual(len(document["rules"]), 10)
        reached = {cl.classify(candidate(**spec)).rule_id for spec in
                   (R1, R2, R3, R4, R5, R6, R7, R8, R9, R10)}
        self.assertEqual(reached, {r["rule_id"] for r in document["rules"]})


# --------------------------------------------------------------- all signals
class TestEverySignal(unittest.TestCase):
    SPECS = {
        "has_named_organization": R1,
        "has_concrete_implementation": R1,
        "has_measurable_outcome": R1,
        "has_measurable_outcome_for_named_org": R8_BLOCKED,
        "has_industry_scope": R2,
        "is_generally_applicable": R2,
        "is_end_user_product": R3,
        "is_developer_tool": R3_TOOL,
        "is_model_or_api_change": R4,
        "is_funding_or_ma_event": R5,
        "is_eval_resource": R6,
        "is_academic_primary": R7,
        "is_engineering_analysis": R8,
        "is_opinion_or_prediction": R9,
    }

    def test_the_config_declares_exactly_fourteen_signals(self):
        self.assertEqual(len(cl.load_precedence()["signals"]), 14)
        self.assertEqual(set(self.SPECS), set(cl.load_precedence()["signals"]))

    def test_every_configured_signal_fires_on_a_designed_input(self):
        for name, spec in sorted(self.SPECS.items()):
            fired, _ = cl.signals_for(candidate(**spec))
            self.assertTrue(fired[name], "%s did not fire" % name)

    def test_every_fired_signal_quotes_its_match(self):
        for name, spec in sorted(self.SPECS.items()):
            fired, evidence = cl.signals_for(candidate(**spec))
            self.assertTrue(evidence[name], "%s fired with no evidence" % name)
            for item in evidence[name]:
                self.assertEqual(item.signal, name)
                self.assertTrue(item.matched.strip(), name)

    def test_no_signal_fires_on_empty_metadata(self):
        fired, _ = cl.signals_for(candidate(url="https://example.com/notes/"))
        self.assertEqual([n for n, v in fired.items() if v], [])

    def test_the_composite_signal_requires_both_components(self):
        both, _ = cl.signals_for(candidate(**R8_BLOCKED))
        self.assertTrue(both["has_measurable_outcome_for_named_org"])
        # remove the named organisation and the composite must stop firing
        alone, _ = cl.signals_for(candidate(
            title="Scaling internals reduced latency by 30%",
            summary="Numbers from the rollout window."))
        self.assertTrue(alone["has_measurable_outcome"])
        self.assertFalse(alone["has_named_organization"])
        self.assertFalse(alone["has_measurable_outcome_for_named_org"])

    def test_patterns_are_case_sensitive_so_a_capital_means_a_proper_noun(self):
        upper, _ = cl.signals_for(candidate(title="Rolled out at Acme"))
        lower, _ = cl.signals_for(candidate(title="rolled out at acme"))
        self.assertTrue(upper["has_named_organization"])
        self.assertFalse(lower["has_named_organization"])


# --------------------------------------------------------- matching (S4-3A)
class TestMatchingSemantics(unittest.TestCase):
    """Whole-token matching, with `*` as the one declared prefix mechanism.

    These replace the S4-3 assertions that pinned arbitrary substring matching,
    under which `product` fired inside "production" and `ide` inside "guide"."""

    def fires(self, signal, **spec):
        fired, _ = cl.signals_for(candidate(**spec))
        return fired[signal]

    def test_ide_matches_ide_but_not_guide(self):
        self.assertTrue(self.fires("is_developer_tool", title="Our IDE plugin"))
        self.assertFalse(self.fires("is_developer_tool",
                                    title="A guide to getting started"))

    def test_product_matches_product_but_not_production(self):
        self.assertTrue(self.fires("is_end_user_product", title="Our new product"))
        self.assertFalse(self.fires("is_end_user_product",
                                    title="Rolled out in production"))

    def test_exact_token_matching_is_case_insensitive(self):
        for form in ("product", "Product", "PRODUCT", "PrOdUcT"):
            self.assertTrue(self.fires("is_end_user_product",
                                       title="Our new %s" % form), form)

    def test_a_term_never_matches_inside_a_longer_token(self):
        for text in ("apparatus", "application", "appendix"):
            self.assertFalse(self.fires("is_end_user_product", title=text), text)
        self.assertTrue(self.fires("is_end_user_product", title="our app"))

    def test_a_phrase_respects_token_boundaries_at_both_ends(self):
        self.assertTrue(self.fires("has_concrete_implementation",
                                   title="Now in production"))
        # a longer token at either end must not satisfy the phrase
        self.assertFalse(self.fires("has_concrete_implementation",
                                    title="Bin productionise"))
        self.assertFalse(self.fires("has_concrete_implementation",
                                    title="Wein production"))

    def test_a_phrase_is_not_satisfied_by_unrelated_adjacent_fragments(self):
        # "we built" must be two whole tokens in order, not fragments of others.
        self.assertTrue(self.fires("has_concrete_implementation",
                                   title="How we built it"))
        self.assertFalse(self.fires("has_concrete_implementation",
                                    title="However builtin helpers"))

    def test_phrase_tokens_must_be_contiguous(self):
        self.assertTrue(self.fires("is_opinion_or_prediction",
                                   title="The case for smaller models"))
        self.assertFalse(self.fires("is_opinion_or_prediction",
                                    title="The strongest case made for it"))

    def test_punctuation_between_phrase_tokens_is_normalized_away(self):
        # ci/cd is a two-token phrase; the separator does not have to be a space.
        for text in ("using ci/cd pipelines", "using ci cd pipelines",
                     "using CI/CD pipelines"):
            self.assertTrue(self.fires("is_developer_tool", title=text), text)

    def test_the_declared_stem_matches_its_intended_word_forms(self):
        for form in ("deprecate", "deprecated", "deprecation", "DEPRECATED",
                     "deprecating"):
            self.assertTrue(self.fires("is_model_or_api_change",
                                       title="Atlas 1 is %s" % form), form)

    def test_a_stem_still_may_not_begin_inside_another_token(self):
        for text in ("undeprecated flag", "predeprecation notice"):
            self.assertFalse(self.fires("is_model_or_api_change", title=text), text)

    def test_a_plain_term_does_not_behave_as_a_stem(self):
        # `benchmark` carries no marker, so it is exact and must not stem.
        self.assertTrue(self.fires("is_eval_resource", title="A new benchmark"))
        self.assertFalse(self.fires("is_eval_resource", title="Benchmarking runs"))

    def test_exactly_one_configured_term_declares_a_stem(self):
        stems = [(name, term)
                 for name, spec in cl.load_precedence()["signals"].items()
                 for term in (spec.get("any_of_keywords") or ())
                 if term.endswith(cl.STEM_MARKER)]
        self.assertEqual(stems, [("is_model_or_api_change", "deprecat*")])

    def test_every_configured_term_is_english_and_separator_delimited(self):
        # S4-3A removed a lone Japanese term that had been carried since 0edbf50.
        # Token matching needs word separators, so a script without them cannot
        # work here without segmentation this pipeline deliberately does not have;
        # keeping such a term would be an inert claim of multilingual coverage.
        offenders = [(name, term)
                     for name, spec in cl.load_precedence()["signals"].items()
                     for term in (spec.get("any_of_keywords") or ())
                     if any(ord(char) > 127 for char in term)]
        self.assertEqual(offenders, [])

    def test_no_script_aware_segmentation_was_introduced(self):
        source = inspect.getsource(cl)
        for forbidden in ("unicodedata", "jieba", "mecab", "janome",
                          "Hiragana", "Katakana", "CJK", "Han"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_a_misplaced_stem_marker_is_refused(self):
        for bad in ("dep*recat", "*deprecat", "*", "   "):
            with self.assertRaises(cl.ClassifyError, msg=bad):
                cl.compile_term(bad)

    def test_the_evaluator_holds_no_per_word_or_per_signal_exception(self):
        # Checked on STRING LITERALS IN CODE, not on raw text: the module's own
        # docstring legitimately quotes "guide" and "production" to explain the
        # semantics, and a substring scan would either fail on the prose or have
        # to be weakened until it proved nothing.
        tree = ast.parse(inspect.getsource(cl))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        literals = {node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str)} - docstrings
        for term in (t for spec in cl.load_precedence()["signals"].values()
                     for t in (spec.get("any_of_keywords") or ())):
            self.assertNotIn(term, literals, "%r is hard-coded" % term)
        for name in cl.load_precedence()["signals"]:
            self.assertNotIn(name, literals, "signal %r is hard-coded" % name)

    def test_evidence_is_quoted_from_the_original_text(self):
        _, evidence = cl.signals_for(candidate(title="Our IDE plugin"))
        matched = [e.matched for e in evidence["is_developer_tool"]]
        self.assertEqual(matched, ["IDE"])


# ------------------------------------------------------------------ ordering
class TestOrdering(unittest.TestCase):
    def test_rules_are_evaluated_in_committed_order(self):
        orders = [r["order"] for r in cl.load_precedence()["rules"]]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(orders, list(range(1, 11)))

    def test_r6_beats_r7_on_an_eval_bearing_paper(self):
        got = cl.classify(candidate(**R6_OVER_R7))
        fired, _ = cl.signals_for(candidate(**R6_OVER_R7))
        self.assertTrue(fired["is_eval_resource"])
        self.assertTrue(fired["is_academic_primary"])
        self.assertEqual(got.rule_id, "R6_eval_resource")
        # R7's none_of excludes it entirely, so it is not even a competitor.
        self.assertNotIn("R7_academic_primary", got.matched_rule_ids)

    def test_r4_beats_r9_and_r9_is_recorded_as_competing(self):
        got = cl.classify(candidate(**R4_OVER_R9))
        self.assertEqual(got.rule_id, "R4_model_release")
        self.assertEqual(cell(got), ("research-and-models", "model-updates"))
        competing = {c.rule_id for c in got.competing_categories}
        self.assertIn("R9_opinion_thesis", competing)
        self.assertTrue(got.ambiguous)

    def test_r1_beats_r3_when_both_fire(self):
        # S4-3A: this used to rely on "production" containing "product". It now
        # needs a real product token, which is the point of the correction.
        fired, _ = cl.signals_for(candidate(**R1_AND_R3))
        self.assertTrue(fired["is_end_user_product"])
        got = cl.classify(candidate(**R1_AND_R3))
        self.assertEqual(got.rule_id, "R1_org_implementation_with_results")
        self.assertIn("R3_end_user_product",
                      {c.rule_id for c in got.competing_categories})

    def test_r1_alone_no_longer_drags_in_r3_via_a_word_fragment(self):
        got = cl.classify(candidate(**R1))
        self.assertEqual(got.rule_id, "R1_org_implementation_with_results")
        self.assertNotIn("R3_end_user_product",
                         {c.rule_id for c in got.competing_categories})

    def test_reordering_the_rule_list_cannot_change_the_outcome(self):
        document = cl.load_precedence()
        shuffled = dict(document, rules=list(reversed(document["rules"])))
        for spec in (R1, R4_OVER_R9, R6_OVER_R7, R8, R9):
            a = cl.classify(candidate(**spec))
            b = cl.classify(candidate(**spec), precedence=shuffled)
            self.assertEqual(a.rule_id, b.rule_id)
            self.assertEqual(cell(a), cell(b))

    def test_the_fallback_never_competes_with_a_concrete_rule(self):
        got = cl.classify(candidate(**R4))
        self.assertIn(cl.FALLBACK_RULE_ID, got.matched_rule_ids)
        self.assertNotIn(cl.FALLBACK_RULE_ID,
                         {c.rule_id for c in got.competing_categories})


# ------------------------------------------------------------------ none_of
class TestExclusions(unittest.TestCase):
    def test_a_developer_tool_is_not_classified_as_a_product(self):
        fired, _ = cl.signals_for(candidate(**R3_TOOL))
        self.assertTrue(fired["is_end_user_product"])
        self.assertTrue(fired["is_developer_tool"])
        got = cl.classify(candidate(**R3_TOOL))
        self.assertNotEqual(cell(got), ("cases", "product-discovery"))
        self.assertEqual(got.rule_id, cl.FALLBACK_RULE_ID)

    def test_removing_the_tool_signal_admits_the_same_item_to_r3(self):
        got = cl.classify(candidate(title="Forge, a product launch",
                                    summary="For teams shipping schedules."))
        self.assertEqual(got.rule_id, "R3_end_user_product")

    def test_r8_is_blocked_by_a_measured_named_organisation(self):
        fired, _ = cl.signals_for(candidate(**R8_BLOCKED))
        self.assertTrue(fired["is_engineering_analysis"])
        self.assertTrue(fired["has_measurable_outcome_for_named_org"])
        got = cl.classify(candidate(**R8_BLOCKED))
        self.assertNotEqual(cell(got), ("discourse", "technical-deep-dives"))
        self.assertEqual(got.rule_id, cl.FALLBACK_RULE_ID)

    def test_r8_fires_once_the_measured_organisation_is_gone(self):
        got = cl.classify(candidate(**R8))
        self.assertEqual(got.rule_id, "R8_engineering_analysis")

    def test_r2_is_blocked_by_a_measurable_outcome(self):
        got = cl.classify(candidate(
            title="Best practice for healthcare intake workflows",
            summary="A playbook that cut handling time by 22%."))
        self.assertNotEqual(got.rule_id, "R2_industry_pattern")


# --------------------------------------------------------------- non-vacuity
class TestNonVacuity(unittest.TestCase):
    """Remove the evidence, lose the rule. Otherwise a rule that fires on
    anything would pass every positive test above and mean nothing."""

    def test_r1_needs_all_three_of_its_signals(self):
        self.assertEqual(cl.classify(candidate(**R1)).rule_id,
                         "R1_org_implementation_with_results")
        for weakened in (
            dict(title="How Acme Corp cut resolution time",       # no outcome
                 summary="Deployed in production across support."),
            dict(title="How Acme Corp cut resolution time by 38%",  # no impl
                 summary="A summary with no implementation verb."),
            dict(title="Resolution time fell by 38 %",             # no org
                 summary="Deployed in production across teams."),
        ):
            self.assertNotEqual(cl.classify(candidate(**weakened)).rule_id,
                                "R1_org_implementation_with_results", weakened)

    def test_each_single_signal_rule_stops_firing_without_its_term(self):
        pairs = [
            ("R4_model_release", dict(title="Introducing Atlas 3, our new model"),
             dict(title="Introducing Atlas 3")),
            ("R5_funding_event", dict(title="Northwind raised a Series B"),
             dict(title="Northwind hired a new team")),
            ("R6_eval_resource", dict(title="We release a new benchmark"),
             dict(title="We release notes")),
            ("R9_opinion_thesis", dict(title="The case for smaller models"),
             dict(title="Smaller models")),
        ]
        for rule_id, present, absent in pairs:
            self.assertEqual(cl.classify(candidate(**present)).rule_id, rule_id)
            self.assertNotEqual(cl.classify(candidate(**absent)).rule_id, rule_id)

    def test_an_empty_candidate_reaches_only_the_fallback(self):
        got = cl.classify(candidate(url="https://example.com/notes/"))
        self.assertEqual(got.matched_rule_ids, (cl.FALLBACK_RULE_ID,))


# ----------------------------------------------------------------- contexts
class TestDiscoveryContexts(unittest.TestCase):
    def multi_context(self, **spec):
        item = lambda sid: AdapterResult(                      # noqa: E731
            source_id=sid, adapter=SOURCES[sid]["adapter"], result="ok",
            candidates=(RawCandidate(target_url="https://example.com/item/",
                                     source_id=sid,
                                     adapter=SOURCES[sid]["adapter"],
                                     position=0, **spec),))
        deliveries = [dd.delivery(LANES[i], item(sid)) for i, sid in enumerate(
            ("openai-news", "aws-ml-blog", "techcrunch-ai"))]
        deduped = dd.group(deliveries, sources=SOURCES)
        return ex.normalize_all(deduped).candidates[0]

    def test_every_discovery_context_reaches_the_classifier(self):
        got = cl.classify(self.multi_context(title="Notes from the field"))
        self.assertEqual(len(got.contexts), 3)

    def test_the_fallback_uses_the_first_context_and_records_the_rest(self):
        got = cl.classify(self.multi_context(title="Notes from the field"))
        self.assertEqual(got.rule_id, cl.FALLBACK_RULE_ID)
        self.assertEqual(cell(got), got.contexts[0])
        self.assertEqual(len(got.competing_categories), 2)
        self.assertEqual({c.rule_id for c in got.competing_categories},
                         {cl.FALLBACK_RULE_ID})
        self.assertTrue(got.ambiguous)

    def test_context_is_not_reduced_to_the_primary_observation(self):
        got = cl.classify(self.multi_context(title="Notes from the field"))
        recorded = {(c.topic, c.category) for c in got.competing_categories}
        recorded.add(cell(got))
        self.assertEqual(recorded, set(got.contexts))

    def test_a_concrete_rule_ignores_the_discovery_cell(self):
        got = cl.classify(self.multi_context(**R4))
        self.assertEqual(cell(got), ("research-and-models", "model-updates"))
        self.assertNotIn(cell(got), got.contexts)
        self.assertTrue(got.differs_from_discovery)

    def test_cross_topic_ownership_is_recorded_not_resolved(self):
        got = cl.classify(self.multi_context(**R4))
        # The condition is visible; nothing here suppresses, merges or assigns
        # an owner topic. That is Stage 5's single-writer phase.
        self.assertTrue(got.differs_from_discovery)
        payload = got.payload()
        for absent in ("owner_topic", "duplicate_of", "cross_reference_reason",
                       "multi_topic"):
            self.assertNotIn(absent, payload)

    def test_a_candidate_without_context_is_refused(self):
        class NoContext:
            candidate_key = "0" * 16
            title = summary = publisher = None
            target_url = "https://example.com/x/"
            contexts = ()
        with self.assertRaises(cl.ClassifyError):
            cl.classify(NoContext())


# ----------------------------------------------------------------- rationale
class TestRationaleAndPayload(unittest.TestCase):
    def test_rationale_names_the_rule_and_quotes_the_evidence(self):
        got = cl.classify(candidate(**R1))
        self.assertTrue(got.rationale.startswith(
            "R1_org_implementation_with_results:"))
        for item in got.evidence:
            self.assertIn(item.signal, got.rationale)
            self.assertIn(item.matched, got.rationale)

    def test_the_fallback_rationale_names_the_discovery_cell(self):
        got = cl.classify(candidate(source_id="techcrunch-ai", **R10))
        self.assertIn(cl.FALLBACK_RULE_ID, got.rationale)
        self.assertIn("discourse__market-and-investment", got.rationale)

    def test_rationale_is_never_generic_boilerplate(self):
        rationales = {cl.classify(candidate(**spec)).rationale
                      for spec in (R1, R2, R4, R5, R6, R7, R8, R9)}
        self.assertEqual(len(rationales), 8)
        for text in rationales:
            self.assertTrue(text.strip())

    def test_the_payload_matches_the_committed_classification_schema(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            schema = json.load(handle)
        spec = schema["$defs"]["classification"]
        payload = cl.classify(candidate(**R1)).payload()
        self.assertEqual(set(payload), set(spec["required"]))
        self.assertEqual(set(payload) - set(spec["properties"]), set())

    def test_evidence_entries_are_closed_to_signal_and_matched(self):
        for item in cl.classify(candidate(**R1)).payload()["evidence"]:
            self.assertEqual(set(item), {"signal", "matched"})

    def test_competing_entries_are_closed_to_topic_category_rule(self):
        for item in cl.classify(candidate(**R4_OVER_R9)).payload()[
                "competing_categories"]:
            self.assertEqual(set(item), {"topic", "category", "rule_id"})

    def test_assigned_cells_are_all_committed_cells(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            schema = json.load(handle)
        topics = set(schema["$defs"]["topic_slug"]["enum"])
        categories = set(schema["$defs"]["category_slug"]["enum"])
        for rule in cl.load_precedence()["rules"]:
            assign = rule["assign"]
            if assign.get("use_discovery_cell"):
                continue
            self.assertIn(assign["topic_slug"], topics)
            self.assertIn(assign["category_slug"], categories)


# --------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def batch(self, order=None):
        specs = [("openai-news", R1), ("aws-ml-blog", R4_OVER_R9),
                 ("techcrunch-ai", R9), ("openai-news", R10),
                 ("aws-ml-blog", R6_OVER_R7)]
        deliveries = []
        for index, (source_id, spec) in enumerate(specs):
            payload = dict(spec)
            url = payload.pop("url", "https://example.com/item-%d/" % index)
            item = RawCandidate(target_url=url, source_id=source_id,
                                adapter=SOURCES[source_id]["adapter"],
                                position=0, **payload)
            deliveries.append(dd.delivery(
                LANES[index % len(LANES)],
                AdapterResult(source_id=source_id,
                              adapter=SOURCES[source_id]["adapter"],
                              result="ok", candidates=(item,))))
        if order is not None:
            deliveries = [deliveries[i] for i in order]
        deduped = dd.group(deliveries, sources=SOURCES)
        return cl.classify_all(ex.normalize_all(deduped))

    def test_every_permutation_of_the_batch_gives_one_output(self):
        outputs = {serialize(self.batch(order))
                   for order in itertools.permutations(range(5))}
        self.assertEqual(len(outputs), 1, "input order changed the output")
        self.assertEqual(len(list(itertools.permutations(range(5)))), 120)

    def test_results_are_sorted_by_candidate_key(self):
        keys = [c.candidate_key for c in self.batch()]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_observations_do_not_change_a_classification(self):
        rng = random.Random(11)
        outputs = set()
        for _ in range(12):
            sources_shuffled = list(SOURCES)
            rng.shuffle(sources_shuffled)
            outputs.add(serialize(self.batch()))
        self.assertEqual(len(outputs), 1)

    def test_repeated_runs_are_byte_identical(self):
        self.assertEqual(serialize(self.batch()), serialize(self.batch()))

    def test_lane_identity_cannot_change_a_result(self):
        results = {serialize((cl.classify(candidate(lane=lane, **R1)),))
                   for lane in LANES}
        self.assertEqual(len(results), 1)

    def test_a_gap_lane_term_never_becomes_evidence(self):
        # The lane names a healthcare gap; the document says nothing about it.
        got = cl.classify(candidate(lane=LANES[2], **R4))
        self.assertNotIn("healthcare", got.rationale)
        for item in got.evidence:
            self.assertNotIn("healthcare", item.matched.casefold())
        self.assertNotEqual(cell(got), ("cases", "domain-applications"))

    def test_competing_categories_are_deterministically_ordered(self):
        got = cl.classify(candidate(**R1))
        keys = [c.order_key for c in got.competing_categories]
        self.assertEqual(keys, sorted(keys))


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    """Classification is a pure function over normalized metadata. Proved on the
    import and call graphs, not on a text scan: the prose legitimately discusses
    fetching, models and ownership."""

    def setUp(self):
        self.tree = ast.parse(inspect.getsource(cl))

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

    def test_no_network_fetch_model_or_fixture_dependency(self):
        banned = {"urllib", "requests", "httpx", "aiohttp", "socket", "http",
                  "ssl", "subprocess", "asyncio", "xml", "html", "bs4", "lxml",
                  "httpclient", "HttpClient", "sourcecache", "SourceFetchCache",
                  "fixtures", "FixtureOpener", "anthropic", "openai"}
        self.assertEqual(self.imported() & banned, set())

    def test_no_pool_scoring_facet_or_record_dependency(self):
        banned = {"pool", "CandidatePool", "records", "facets", "facetassign",
                  "verify", "coverage", "scheduler", "budget", "domainlease"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("make_full_record", "make_cross_reference",
                          "acquire_target_fetch", "acquire_extraction",
                          "add_candidate", "case_facets", "relevance_score",
                          "quality_score", "audience_fit_score",
                          "accept_composite", "rejection_reason",
                          "verification_status", "access_status"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_lane_and_ownership_fields_are_unreadable_from_here(self):
        for forbidden in ("lane_id", "lane_ids", "source_request_key",
                          "source_request_keys", "owner_lane_id",
                          "target_fetch_owner", "extraction_owner",
                          "designated_target_fetch_owner_lane_id",
                          "designated_extraction_owner_lane_id",
                          "contributing_lanes", "observations",
                          "provenance_raw"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_no_cross_topic_resolution_is_performed(self):
        for forbidden in ("resolve_cross_topic", "cross_topic_policy",
                          "owner_topic", "topic_rank", "multi_topic",
                          "duplicate_of", "suppress"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_the_rules_are_read_from_the_committed_config_not_hard_coded(self):
        source = inspect.getsource(cl)
        with open(PRECEDENCE_PATH, encoding="utf-8") as handle:
            document = json.load(handle)
        # No rule_id is transcribed into code except the fallback's, which is
        # exported as a constant for callers. Nothing DISPATCHES on it — the
        # next test proves the fallback is located structurally.
        named = [r["rule_id"] for r in document["rules"]
                 if r["rule_id"] in source and r["rule_id"] != cl.FALLBACK_RULE_ID]
        self.assertEqual(named, [])
        for signal in document["signals"]:
            self.assertNotIn(signal, source, "signal %r is hard-coded" % signal)
        self.assertIn("precedence.v1.json", source)

    def test_the_fallback_is_found_by_its_flag_not_by_its_name(self):
        # Rename the fallback rule: a name-matching implementation would lose it.
        document = cl.load_precedence()
        renamed = dict(document, rules=[
            dict(rule, rule_id="RX_renamed_fallback")
            if (rule.get("assign") or {}).get("use_discovery_cell") else rule
            for rule in document["rules"]])
        got = cl.classify(candidate(**R10), precedence=renamed)
        self.assertEqual(got.rule_id, "RX_renamed_fallback")
        self.assertTrue(got.used_fallback)
        self.assertEqual(cell(got), got.contexts[0])

    def test_no_rule_is_evaluated_by_string_comparison(self):
        source = inspect.getsource(cl)
        for rule in cl.load_precedence()["rules"]:
            self.assertNotIn('== "%s"' % rule["rule_id"], source)
            self.assertNotIn("== '%s'" % rule["rule_id"], source)

    def test_stage_4_writes_nothing(self):
        called = {n.func.id for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("print", called)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                mode = [a for a in node.args[1:]] + [k for k in node.keywords
                                                     if k.arg == "mode"]
                self.assertTrue(all(getattr(m, "value", "r") == "r"
                                    for m in mode if hasattr(m, "value")))

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("Classification", "Evidence", "CompetingCategory",
                     "classify", "classify_all", "signals_for",
                     "load_precedence", "ClassifyError"):
            self.assertTrue(hasattr(cl, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
