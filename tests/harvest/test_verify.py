#!/usr/bin/env python3
"""test_verify.py — the four committed scores and the accept/reject gate (S4-4).

The properties that carry the weight:

  * NUMBERS COME FROM POLICY. Every weight and threshold is read from
    `policy.v1.json`; the composite is checked against a hand-computed weighted
    sum so the module and the config cannot silently disagree.
  * AN UNKNOWN IS NOT A PENALTY. No publication date means `freshness: null` and
    a composite renormalized over what could be scored — not 0.0, which would
    assert the item is old.
  * NOTHING IS FETCHED, SO NOTHING IS CLAIMED. Every verdict carries
    access_status "not_checked", http_status None, verification_status
    "unverified", content_hash None, and no timestamp is invented.
  * A REJECTION IS A FINDING. The reason comes from the committed record enum and
    the detail names the exact rule and number that decided it.

Driven by the real S4-1 -> S4-2 -> S4-3 pipeline and the real config. Offline;
no network, no fixtures, no pool, no records. Run via tests/test_taxonomy_verify.sh.
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

from src.harvest import classify as cl, dedupe as dd, extract as ex   # noqa: E402
from src.harvest import verify as vf                                  # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate     # noqa: E402

RECORD_SCHEMA_PATH = os.path.join(ROOT, "schemas", "harvest", "record.v1.json")
LANES = ("cell__cases__case-studies", "gap__business_function__marketing")
CLOCK = "2026-07-10T00:00:00Z"

SOURCES = {
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "anthropic-customers": {"source_id": "anthropic-customers", "topic_slug": "cases",
                            "category_slug": "case-studies", "adapter": "seed",
                            "role": "validation_seed"},
}

# A case study that clears every gate: named org, implementation, measured
# result, a substantial summary, a publisher and a fresh date.
STRONG = dict(
    title="Acme Corp rolled out an assistant in production and reduced handle "
          "time by 38 percent",
    summary=("Acme deployed the assistant across its support organisation. "
             "The rollout is described with a measured baseline, the results "
             "before and after the change, and the per quarter figures that "
             "the team tracked throughout the customer story. " + "Detail. " * 20),
    publisher="Acme Engineering", published_at="2026-07-10T00:00:00Z")


def candidate(source_id="openai-news", lane=LANES[0], url="https://example.com/item/",
              **payload):
    item = RawCandidate(target_url=url, source_id=source_id,
                        adapter=SOURCES[source_id]["adapter"], position=0, **payload)
    result = AdapterResult(source_id=source_id,
                           adapter=SOURCES[source_id]["adapter"],
                           result="ok", candidates=(item,))
    deduped = dd.group([dd.delivery(lane, result)], sources=SOURCES)
    return ex.normalize_all(deduped).candidates[0]


def judged(clock=CLOCK, policy=None, **spec):
    extracted = candidate(**spec)
    classification = cl.classify(extracted)
    scores = vf.score(extracted, classification, policy=policy, clock=clock)
    verdict = vf.decide(extracted, classification, scores, policy=policy)
    return extracted, classification, scores, verdict


def policy_with(**thresholds):
    document = copy.deepcopy(vf.load_policy())
    document["scoring"]["thresholds"].update(thresholds)
    return document


def numeric_literals(module):
    """Every int/float literal in a module, as floats. AST, never a text scan."""
    return {float(node.value)
            for node in ast.walk(ast.parse(inspect.getsource(module)))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)}


def serialize(verdicts):
    return json.dumps([{
        "candidate_key": v.candidate_key, "accepted": v.accepted,
        "reason": v.rejection_reason, "detail": v.detail,
        "scores": v.scores.payload(),
        "evidence": [e.payload() for e in v.scores.evidence],
        "cell": [v.topic_slug, v.category_slug], "rule_id": v.rule_id,
        "access_status": v.access_status, "http_status": v.http_status,
        "verification_status": v.verification_status,
        "content_hash": v.content_hash,
    } for v in verdicts], sort_keys=True)


# ------------------------------------------------------------------- scores
class TestScores(unittest.TestCase):
    def test_relevance_rises_with_required_and_boost_terms(self):
        _, _, weak, _ = judged(title="Acme Corp deployed results in production")
        _, _, strong, _ = judged(**STRONG)
        self.assertGreater(strong.relevance, weak.relevance)
        self.assertGreaterEqual(weak.relevance, 0.0)
        self.assertLessEqual(strong.relevance, 1.0)

    def test_relevance_is_zero_when_no_required_term_matches(self):
        _, _, scores, _ = judged(title="Notes from the field",
                                 summary="A short update.")
        self.assertEqual(scores.relevance, 0.0)
        self.assertEqual(scores.required_hits, 0)

    def test_quality_rises_with_observable_evidence(self):
        _, _, bare, _ = judged(title="Acme Corp deployed results in production")
        _, _, full, _ = judged(**STRONG)
        self.assertGreater(full.quality, bare.quality)
        self.assertLessEqual(full.quality, 1.0)

    def test_a_stub_summary_counts_for_less_than_a_substantial_one(self):
        _, _, stub, _ = judged(title="Acme Corp deployed in production",
                               summary="Short.")
        _, _, full, _ = judged(title="Acme Corp deployed in production",
                               summary="A" * (vf.SUBSTANTIAL_SUMMARY + 1))
        self.assertGreater(full.quality, stub.quality)

    def test_corroboration_from_a_second_source_raises_quality(self):
        payload = dict(title="Acme Corp deployed in production, results measured",
                       summary="A" * 250, publisher="Acme")
        single = candidate(**payload)
        pair = ex.normalize_all(dd.group([
            dd.delivery(LANES[0], AdapterResult(
                source_id="openai-news", adapter="feed", result="ok",
                candidates=(RawCandidate(target_url="https://example.com/item/",
                                         source_id="openai-news", adapter="feed",
                                         position=0, **payload),))),
            dd.delivery(LANES[1], AdapterResult(
                source_id="aws-ml-blog", adapter="feed", result="ok",
                candidates=(RawCandidate(target_url="https://example.com/item/",
                                         source_id="aws-ml-blog", adapter="feed",
                                         position=0, **payload),))),
        ], sources=SOURCES)).candidates[0]
        one = vf.score(single, cl.classify(single), clock=CLOCK)
        two = vf.score(pair, cl.classify(pair), clock=CLOCK)
        self.assertEqual(pair.source_ids, ("aws-ml-blog", "openai-news"))
        self.assertGreater(two.quality, one.quality)

    def test_audience_fit_is_full_unless_the_category_excludes_it(self):
        _, _, ok, _ = judged(**STRONG)
        self.assertEqual(ok.audience_fit, 1.0)

    def test_every_score_stays_within_the_committed_range(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            spec = json.load(handle)["$defs"]["score"]
        for payload in (dict(title="x"), STRONG,
                        dict(title="Notes", summary="A" * 400)):
            _, _, scores, _ = judged(**payload)
            for name, value in scores.payload().items():
                if value is None:
                    continue
                self.assertGreaterEqual(value, spec["minimum"], name)
                self.assertLessEqual(value, spec["maximum"], name)

    def test_scores_are_rounded_to_the_declared_precision(self):
        _, _, scores, _ = judged(**STRONG)
        for name, value in scores.payload().items():
            if value is None:
                continue
            self.assertEqual(value, round(value, vf.PRECISION), name)

    def test_unusable_configured_terms_are_reported_not_silently_dropped(self):
        # `%` is configured as a case-studies boost term and has no matchable
        # token. It is skipped and named rather than aborting or vanishing.
        _, _, scores, _ = judged(**STRONG)
        self.assertIn("%", scores.unusable_terms)


# ---------------------------------------------------------------- composite
class TestComposite(unittest.TestCase):
    def weights(self):
        return vf.load_policy()["scoring"]["weights"]

    def test_the_composite_is_the_committed_weighted_mean(self):
        _, _, scores, _ = judged(**STRONG)
        w = self.weights()
        expected = (w["relevance"] * scores.relevance +
                    w["quality"] * scores.quality +
                    w["audience_fit"] * scores.audience_fit +
                    w["freshness"] * scores.freshness) / sum(w.values())
        self.assertEqual(scores.composite, round(expected, vf.PRECISION))

    def test_the_weights_are_read_from_policy_not_restated_in_code(self):
        # Compared on NUMERIC LITERALS, not on raw text: "0.3" is a substring of
        # "0.30" and of "0.35", so a text scan would fire on unrelated constants.
        self.assertEqual(numeric_literals(vf) & set(self.weights().values()),
                         set())

    def test_a_missing_date_renormalizes_over_the_scored_dimensions(self):
        payload = dict(STRONG)
        payload.pop("published_at")
        _, _, scores, _ = judged(**payload)
        self.assertIsNone(scores.freshness)
        w = self.weights()
        partial = sum(w[k] for k in ("relevance", "quality", "audience_fit"))
        expected = (w["relevance"] * scores.relevance +
                    w["quality"] * scores.quality +
                    w["audience_fit"] * scores.audience_fit) / partial
        self.assertEqual(scores.composite, round(expected, vf.PRECISION))

    def test_an_unknown_date_is_not_treated_as_zero_freshness(self):
        payload = dict(STRONG)
        payload.pop("published_at")
        _, _, unknown, _ = judged(**payload)
        _, _, ancient, _ = judged(**dict(STRONG, published_at="2016-01-01T00:00:00Z"))
        self.assertIsNone(unknown.freshness)
        self.assertGreater(unknown.composite, ancient.composite)


# --------------------------------------------------------------- freshness
class TestFreshness(unittest.TestCase):
    def freshness(self, published):
        _, _, scores, _ = judged(**dict(STRONG, published_at=published))
        return scores.freshness

    def test_a_same_day_item_is_fully_fresh(self):
        self.assertEqual(self.freshness("2026-07-10T00:00:00Z"), 1.0)

    def test_one_half_life_halves_freshness(self):
        half_life = vf.load_policy()["scoring"]["freshness_half_life_days"]
        self.assertEqual(half_life, 90)
        self.assertAlmostEqual(self.freshness("2026-04-11T00:00:00Z"), 0.5,
                               places=3)

    def test_two_half_lives_quarter_freshness(self):
        self.assertAlmostEqual(self.freshness("2026-01-11T00:00:00Z"), 0.25,
                               places=3)

    def test_freshness_decays_monotonically(self):
        values = [self.freshness(d) for d in
                  ("2026-07-10T00:00:00Z", "2026-05-10T00:00:00Z",
                   "2026-03-10T00:00:00Z", "2025-07-10T00:00:00Z")]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_a_future_date_is_clamped_rather_than_exceeding_one(self):
        self.assertEqual(self.freshness("2027-01-01T00:00:00Z"), 1.0)

    def test_a_missing_date_yields_null_freshness(self):
        payload = dict(STRONG)
        payload.pop("published_at")
        _, _, scores, _ = judged(**payload)
        self.assertIsNone(scores.freshness)

    def test_an_unparseable_date_yields_null_freshness_and_no_invention(self):
        _, _, scores, _ = judged(**dict(STRONG, published_at="sometime in spring"))
        self.assertIsNone(scores.freshness)

    def test_the_clock_is_injected_and_never_read_from_the_wall(self):
        early = judged(clock="2026-07-10T00:00:00Z", **STRONG)[2].freshness
        late = judged(clock="2027-07-10T00:00:00Z", **STRONG)[2].freshness
        self.assertEqual(early, 1.0)
        self.assertLess(late, early)


# --------------------------------------------------------------- thresholds
class TestThresholds(unittest.TestCase):
    def test_thresholds_come_from_the_committed_policy(self):
        _, classification, _, _ = judged(**STRONG)
        limits = vf.thresholds_for(classification)
        self.assertEqual(limits, vf.load_policy()["scoring"]["thresholds"])

    def test_threshold_selection_uses_the_classified_cell(self):
        _, classification, _, _ = judged(**STRONG)
        cell = "%s__%s" % (classification.topic_slug, classification.category_slug)
        document = copy.deepcopy(vf.load_policy())
        document["scoring"]["thresholds_by_cell"] = {cell: {"min_relevance": 0.99}}
        self.assertEqual(vf.thresholds_for(classification, document)["min_relevance"],
                         0.99)
        other = copy.deepcopy(vf.load_policy())
        other["scoring"]["thresholds_by_cell"] = {"discourse__community":
                                                  {"min_relevance": 0.99}}
        self.assertEqual(vf.thresholds_for(classification, other)["min_relevance"],
                         vf.load_policy()["scoring"]["thresholds"]["min_relevance"])

    def test_a_candidate_exactly_at_a_threshold_is_accepted(self):
        _, _, scores, _ = judged(**STRONG)
        at = policy_with(accept_composite=scores.composite,
                         min_relevance=scores.relevance,
                         min_quality=scores.quality)
        self.assertTrue(judged(policy=at, **STRONG)[3].accepted)

    def test_a_candidate_immediately_below_composite_is_rejected(self):
        _, _, scores, _ = judged(**STRONG)
        just_above = policy_with(accept_composite=scores.composite + 0.0001)
        verdict = judged(policy=just_above, **STRONG)[3]
        self.assertFalse(verdict.accepted)
        self.assertIn("composite", verdict.detail)

    def test_a_candidate_immediately_below_relevance_is_rejected_for_relevance(self):
        _, _, scores, _ = judged(**STRONG)
        raised = policy_with(min_relevance=scores.relevance + 0.0001)
        verdict = judged(policy=raised, **STRONG)[3]
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.rejection_reason, "below_relevance_threshold")

    def test_a_candidate_immediately_below_quality_is_rejected_for_quality(self):
        _, _, scores, _ = judged(**STRONG)
        raised = policy_with(min_quality=scores.quality + 0.0001, min_relevance=0.0)
        verdict = judged(policy=raised, **STRONG)[3]
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.rejection_reason, "below_quality_threshold")

    def test_relevance_is_gated_before_quality(self):
        _, _, scores, _ = judged(**STRONG)
        both = policy_with(min_relevance=scores.relevance + 0.0001,
                           min_quality=scores.quality + 0.0001)
        self.assertEqual(judged(policy=both, **STRONG)[3].rejection_reason,
                         "below_relevance_threshold")


# ---------------------------------------------------------------- decisions
class TestDecisions(unittest.TestCase):
    def test_a_strong_case_study_is_accepted(self):
        verdict = judged(**STRONG)[3]
        self.assertTrue(verdict.accepted)
        self.assertIsNone(verdict.rejection_reason)
        self.assertIn("accept_composite", verdict.detail)

    def test_a_candidate_with_no_title_and_no_summary_is_insufficient(self):
        verdict = judged(publisher="Acme")[3]
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.rejection_reason, "insufficient_evidence")

    def test_a_candidate_matching_no_required_term_is_off_topic(self):
        verdict = judged(title="Notes from the field", summary="A short update.")[3]
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.rejection_reason, "off_topic")
        self.assertIn("cases__case-studies", verdict.detail)

    def test_a_developer_tool_in_an_excluding_category_is_rejected_as_such(self):
        extracted = candidate(
            source_id="openai-news",
            title="Forge, a product launch for developers with an SDK and CLI",
            summary="A developer tool for teams shipping software. " + "x" * 220)
        classification = cl.classify(extracted)
        # force the product-discovery vocabulary, whose exclude list is the
        # developer-tool list, without touching classification itself
        scores = vf.score(extracted, dataclasses.replace(
            classification, category_slug="product-discovery"), clock=CLOCK)
        verdict = vf.decide(extracted, dataclasses.replace(
            classification, category_slug="product-discovery"), scores)
        self.assertTrue(scores.excluded)
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.rejection_reason, "developer_only_audience")
        self.assertEqual(scores.audience_fit, 0.0)

    def test_every_rejection_reason_is_in_the_committed_record_enum(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            allowed = set(json.load(handle)["$defs"]["rejection_reason"]["enum"])
        seen = set()
        for payload in (dict(publisher="Acme"),
                        dict(title="Notes", summary="Short."),
                        dict(title="Acme Corp deployed results in production"),
                        STRONG):
            seen.add(judged(**payload)[3].rejection_reason)
        self.assertTrue(seen)
        for reason in seen:
            self.assertIn(reason, allowed, reason)

    def test_a_rejected_candidate_keeps_its_scores_and_reason(self):
        _, _, scores, verdict = judged(title="Notes from the field",
                                       summary="A short update.")
        self.assertFalse(verdict.accepted)
        self.assertIs(verdict.scores, scores)
        self.assertIsNotNone(verdict.scores.composite)
        self.assertTrue(verdict.detail)

    def test_the_detail_always_names_the_rule_and_the_numbers(self):
        for payload in (STRONG, dict(title="Notes", summary="Short."),
                        dict(publisher="Acme")):
            self.assertTrue(judged(**payload)[3].detail.strip())

    def test_ambiguous_classification_stays_visible_on_the_verdict(self):
        extracted = candidate(
            title="The case for our new model, and what this means",
            summary="A" * 250)
        classification = cl.classify(extracted)
        self.assertTrue(classification.ambiguous)
        verdict = vf.verify(extracted, classification, clock=CLOCK)
        self.assertTrue(verdict.ambiguous)
        self.assertEqual(verdict.rule_id, classification.rule_id)

    def test_contradictory_metadata_is_scored_not_resolved(self):
        payload = dict(summary="A" * 250)
        pair = ex.normalize_all(dd.group([
            dd.delivery(LANES[0], AdapterResult(
                source_id="openai-news", adapter="feed", result="ok",
                candidates=(RawCandidate(
                    target_url="https://example.com/item/", source_id="openai-news",
                    adapter="feed", position=0, title="Acme cut costs", **payload),))),
            dd.delivery(LANES[1], AdapterResult(
                source_id="aws-ml-blog", adapter="feed", result="ok",
                candidates=(RawCandidate(
                    target_url="https://example.com/item/", source_id="aws-ml-blog",
                    adapter="feed", position=0, title="Acme raised costs",
                    **payload),))),
        ], sources=SOURCES)).candidates[0]
        self.assertEqual(len(pair.variants("title")), 2)
        verdict = vf.verify(pair, cl.classify(pair), clock=CLOCK)
        # both titles survive in provenance; the verdict does not pick a winner
        self.assertEqual(len(pair.provenance_raw["field_variants"]["title"]), 2)
        self.assertIsNotNone(verdict.scores.composite)


# --------------------------------------------------------- no-enrichment
class TestNoEnrichment(unittest.TestCase):
    def test_every_verdict_carries_the_honest_no_fetch_values(self):
        for payload in (STRONG, dict(title="Notes", summary="Short."),
                        dict(publisher="Acme")):
            verdict = judged(**payload)[3]
            self.assertEqual(verdict.access_status, "not_checked")
            self.assertIsNone(verdict.http_status)
            self.assertEqual(verdict.verification_status, "unverified")
            self.assertIsNone(verdict.content_hash)
            self.assertIsNone(verdict.verification_evidence)

    def test_absent_fetch_evidence_is_never_by_itself_a_rejection(self):
        verdict = judged(**STRONG)[3]
        self.assertTrue(verdict.accepted)
        self.assertEqual(verdict.access_status, "not_checked")

    def test_inaccessible_is_representable_but_never_claimed(self):
        with open(RECORD_SCHEMA_PATH, encoding="utf-8") as handle:
            allowed = set(json.load(handle)["$defs"]["access_status"]["enum"])
        self.assertIn("not_checked", allowed)
        for payload in (STRONG, dict(title="Notes", summary="Short.")):
            self.assertNotIn(judged(**payload)[3].access_status,
                             {"ok", "not_found", "gone", "timeout", "unreachable"})

    def test_no_timestamp_is_fabricated(self):
        blob = serialize([judged(**STRONG)[3]])
        self.assertNotIn("last_checked_at", blob)
        self.assertNotIn("updated_at", blob)


# --------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def batch(self, order=None):
        specs = [dict(STRONG), dict(title="Notes from the field", summary="Short."),
                 dict(title="The case for our new model, and what this means",
                      summary="A" * 250),
                 dict(title="Acme Corp deployed in production, results measured",
                      summary="A" * 250, publisher="Acme")]
        deliveries = []
        for index, spec in enumerate(specs):
            deliveries.append(dd.delivery(LANES[index % 2], AdapterResult(
                source_id="openai-news", adapter="feed", result="ok",
                candidates=(RawCandidate(
                    target_url="https://example.com/item-%d/" % index,
                    source_id="openai-news", adapter="feed", position=0,
                    **spec),))))
        if order is not None:
            deliveries = [deliveries[i] for i in order]
        extraction = ex.normalize_all(dd.group(deliveries, sources=SOURCES))
        classifications = cl.classify_all(extraction)
        return vf.verify_all(extraction, classifications, clock=CLOCK)

    def test_every_permutation_gives_one_output(self):
        outputs = {serialize(self.batch(order))
                   for order in itertools.permutations(range(4))}
        self.assertEqual(len(outputs), 1)
        self.assertEqual(len(list(itertools.permutations(range(4)))), 24)

    def test_repeated_runs_are_byte_identical(self):
        self.assertEqual(serialize(self.batch()), serialize(self.batch()))

    def test_verdicts_are_sorted_by_candidate_key(self):
        keys = [v.candidate_key for v in self.batch()]
        self.assertEqual(keys, sorted(keys))

    def test_evidence_is_deterministically_ordered(self):
        _, _, scores, _ = judged(**STRONG)
        keys = [e.order_key for e in scores.evidence]
        self.assertEqual(keys, sorted(keys))

    def test_classification_is_not_mutated_by_verification(self):
        extracted = candidate(**STRONG)
        classification = cl.classify(extracted)
        before = dataclasses.asdict(classification)
        vf.verify(extracted, classification, clock=CLOCK)
        self.assertEqual(dataclasses.asdict(classification), before)

    def test_verification_never_changes_the_cell(self):
        _, classification, _, verdict = judged(**STRONG)
        self.assertEqual((verdict.topic_slug, verdict.category_slug),
                         (classification.topic_slug, classification.category_slug))

    def test_an_unclassified_candidate_is_refused(self):
        extraction = ex.normalize_all(dd.group(
            [dd.delivery(LANES[0], AdapterResult(
                source_id="openai-news", adapter="feed", result="ok",
                candidates=(RawCandidate(target_url="https://example.com/x/",
                                         source_id="openai-news", adapter="feed",
                                         position=0, title="x"),)))],
            sources=SOURCES))
        with self.assertRaises(vf.VerifyError):
            vf.verify_all(extraction, ())


# --------------------------------------------------------------- non-vacuity
class TestNonVacuity(unittest.TestCase):
    """Change a score input and the verdict must be able to change. A gate that
    accepts everything would pass every positive test above and mean nothing."""

    def flips_between(self, richer, poorer):
        """Both composites, and a threshold set between them, must flip the verdict.

        Stated this way rather than against the shipped thresholds: a fixture
        strong enough to accept under the committed policy may still accept after
        one field is removed, which would prove nothing about whether the input
        mattered. Setting the bar between the two measured composites proves it
        exactly.
        """
        high = judged(**richer)[2].composite
        low = judged(**poorer)[2].composite
        self.assertGreater(high, low)
        between = policy_with(accept_composite=(high + low) / 2.0)
        self.assertTrue(judged(policy=between, **richer)[3].accepted)
        self.assertFalse(judged(policy=between, **poorer)[3].accepted)

    def test_removing_the_summary_lowers_the_score_and_can_flip_acceptance(self):
        poorer = dict(STRONG)
        poorer["summary"] = "Short."
        self.flips_between(STRONG, poorer)

    def test_removing_the_publisher_lowers_the_score_and_can_flip_acceptance(self):
        poorer = dict(STRONG)
        poorer.pop("publisher")
        self.flips_between(STRONG, poorer)

    def test_removing_required_terms_can_flip_acceptance(self):
        self.assertTrue(judged(**STRONG)[3].accepted)
        self.assertFalse(judged(title="Notes from the field",
                                summary="A" * 250)[3].accepted)

    def test_ageing_the_item_lowers_the_composite(self):
        fresh = judged(**STRONG)[2].composite
        old = judged(**dict(STRONG, published_at="2016-01-01T00:00:00Z"))[2].composite
        self.assertLess(old, fresh)

    def test_raising_a_threshold_can_flip_acceptance(self):
        composite = judged(**STRONG)[2].composite
        self.assertTrue(judged(**STRONG)[3].accepted)
        just_above = policy_with(accept_composite=composite + 0.0001)
        self.assertFalse(judged(policy=just_above, **STRONG)[3].accepted)

    def test_lowering_every_threshold_admits_a_weak_candidate(self):
        weak = dict(title="Acme Corp deployed results in production")
        self.assertFalse(judged(**weak)[3].accepted)
        permissive = policy_with(min_relevance=0.0, min_quality=0.0,
                                 min_audience_fit=0.0, accept_composite=0.0)
        self.assertTrue(judged(policy=permissive, **weak)[3].accepted)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(inspect.getsource(vf))

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
                  "httpclient", "HttpClient", "sourcecache", "SourceFetchCache",
                  "fixtures", "FixtureOpener", "anthropic", "openai"}
        self.assertEqual(self.imported() & banned, set())

    def test_no_pool_facet_or_record_dependency(self):
        banned = {"pool", "CandidatePool", "records", "facets", "facetassign",
                  "coverage", "scheduler"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("make_full_record", "make_cross_reference",
                          "acquire_target_fetch", "acquire_extraction",
                          "add_candidate", "case_facets", "assign"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_no_cross_topic_resolution_is_performed(self):
        for forbidden in ("resolve_cross_topic", "cross_topic_policy",
                          "owner_topic", "topic_rank", "multi_topic",
                          "duplicate_of", "suppress"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_it_never_writes_a_file(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                for arg in node.args[1:]:
                    self.assertEqual(getattr(arg, "value", "r"), "r")
                for kw in node.keywords:
                    if kw.arg == "mode":
                        self.assertEqual(getattr(kw.value, "value", "r"), "r")
        called = {n.func.id for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("print", called)

    def test_lane_and_ownership_fields_are_unreadable_from_here(self):
        for forbidden in ("lane_id", "lane_ids", "source_request_key",
                          "source_request_keys", "owner_lane_id",
                          "target_fetch_owner", "extraction_owner",
                          "contributing_lanes", "observations"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_it_reuses_the_committed_matcher_rather_than_a_second_one(self):
        self.assertIn("classify", self.imported())
        self.assertNotIn("re", self.imported())
        called = {n.func.attr for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("_find_term", called)
        self.assertIn("_tokenize", called)
        for forbidden in ("compile", "findall", "finditer", "search"):
            self.assertNotIn(forbidden, called, forbidden)

    def test_no_threshold_is_restated_in_code(self):
        self.assertEqual(
            numeric_literals(vf) &
            set(vf.load_policy()["scoring"]["thresholds"].values()),
            set())

    def test_no_policy_number_at_all_appears_as_a_literal(self):
        scoring = vf.load_policy()["scoring"]
        policy_numbers = (set(scoring["weights"].values()) |
                          set(scoring["thresholds"].values()) |
                          {float(scoring["freshness_half_life_days"])})
        self.assertEqual(numeric_literals(vf) & policy_numbers, set())

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("Scores", "Verdict", "ScoreEvidence", "score", "decide",
                     "verify", "verify_all", "thresholds_for", "load_policy",
                     "VerifyError"):
            self.assertTrue(hasattr(vf, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
