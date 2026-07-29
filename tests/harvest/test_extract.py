#!/usr/bin/env python3
"""test_extract.py — deterministic metadata normalization (S4-2).

The properties that carry the weight:

  * this is NOT body extraction. Nothing here fetches, parses a body, or touches
    `designated_target_fetch_owner_lane_id` / `designated_extraction_owner_lane_id`,
    whose committed meaning of null is "the operation has not occurred";
  * identity is S4-1's canonicalization result, consumed rather than recomputed,
    so there is exactly one identity path;
  * an unparseable date becomes null and SAYS SO — inventing a timestamp would
    make the freshness score a fiction, and swallowing the failure would hide it;
  * conflicting metadata is reported and fully retained, never resolved here.

Built on the real S4-1 pipeline, so the two contracts are proved to fit rather
than assumed to. Offline and in-memory: no network, no fixtures, no pool.
Run via tests/test_taxonomy_extract.sh.
"""
import ast
import dataclasses
import inspect
import itertools
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import dedupe as dd, extract as ex                   # noqa: E402
from src.harvest import records, urlkey                               # noqa: E402
from src.harvest.adapters.base import AdapterResult, RawCandidate     # noqa: E402

LANES = ("cell__cases__case-studies",
         "gap__business_function__marketing",
         "gap__industry__healthcare-life-sciences")

SOURCES = {
    "openai-news": {"source_id": "openai-news", "topic_slug": "cases",
                    "category_slug": "case-studies", "adapter": "feed",
                    "role": "discovery"},
    "anthropic-customers": {"source_id": "anthropic-customers", "topic_slug": "cases",
                            "category_slug": "case-studies", "adapter": "seed",
                            "role": "validation_seed"},
    "aws-ml-blog": {"source_id": "aws-ml-blog", "topic_slug": "cases",
                    "category_slug": "domain-applications", "adapter": "feed",
                    "role": "discovery"},
    "techcrunch-ai": {"source_id": "techcrunch-ai", "topic_slug": "discourse",
                      "category_slug": "market-and-investment", "adapter": "feed",
                      "role": "discovery"},
}

PAGE = "https://openai.com/index/acme-support-automation/"
OTHER = "https://openai.com/index/beta-logistics/"


def raw(url, position=0, source_id="openai-news", adapter="feed", **kw):
    return RawCandidate(target_url=url, source_id=source_id, adapter=adapter,
                        position=position, **kw)


def result(source_id, candidates, outcome="ok"):
    return AdapterResult(source_id=source_id, adapter=SOURCES[source_id]["adapter"],
                         result=outcome, candidates=tuple(candidates))


def extract(deliveries):
    return ex.normalize_all(dd.group(deliveries, sources=SOURCES))


def one(candidates, lane=LANES[0], source_id="openai-news"):
    return extract([dd.delivery(lane, result(source_id, candidates))]).candidates[0]


def serialize(res):
    return json.dumps({
        "unusable": [[u.source_id, u.position, u.target_url, u.reason]
                     for u in res.unusable],
        "issues": [[i.candidate_key, i.field, i.kind, i.detail] for i in res.issues],
        "candidates": [dataclasses.asdict(c) for c in res.candidates],
    }, sort_keys=True, default=list)


# ------------------------------------------------------------- normalization
class TestNormalization(unittest.TestCase):
    def test_a_complete_item_normalizes_completely(self):
        candidate = one([raw(PAGE, title="Acme cuts handle time 38%",
                             summary="Acme deployed an assistant in support.",
                             publisher="OpenAI",
                             published_at="Mon, 06 Jul 2026 09:00:00 GMT")])
        self.assertEqual(candidate.title, "Acme cuts handle time 38%")
        self.assertEqual(candidate.summary,
                         "Acme deployed an assistant in support.")
        self.assertEqual(candidate.publisher, "OpenAI")
        self.assertEqual(candidate.published_at, "2026-07-06T09:00:00Z")
        self.assertEqual(candidate.issues, ())

    def test_missing_optional_fields_become_null_and_are_reported(self):
        candidate = one([raw(PAGE)])
        for field in ("title", "summary", "publisher", "published_at"):
            self.assertIsNone(getattr(candidate, field), field)
        kinds = {(i.field, i.kind) for i in candidate.issues}
        for field in ("title", "summary", "publisher", "published_at"):
            self.assertIn((field, ex.MISSING), kinds, field)

    def test_an_empty_summary_is_null_not_an_empty_string(self):
        candidate = one([raw(PAGE, title="Acme", summary="   ")])
        self.assertIsNone(candidate.summary)
        self.assertIn(("summary", ex.MISSING),
                      {(i.field, i.kind) for i in candidate.issues})

    def test_the_unknown_sentinel_becomes_null_and_is_distinguished(self):
        candidate = one([raw(PAGE, title="unknown", publisher="Unknown")])
        self.assertIsNone(candidate.title)
        self.assertIsNone(candidate.publisher)
        kinds = {(i.field, i.kind) for i in candidate.issues}
        self.assertIn(("title", ex.UNKNOWN_SENTINEL), kinds)
        self.assertIn(("publisher", ex.UNKNOWN_SENTINEL), kinds)
        self.assertNotIn(("title", ex.MISSING), kinds)

    def test_single_line_fields_collapse_injected_whitespace(self):
        candidate = one([raw(PAGE, title="Acme\n      cuts   handle time",
                             publisher="  OpenAI\tNews  ")])
        self.assertEqual(candidate.title, "Acme cuts handle time")
        self.assertEqual(candidate.publisher, "OpenAI News")

    def test_summary_structure_is_preserved(self):
        body = "First line.\n\nSecond paragraph."
        candidate = one([raw(PAGE, summary=body)])
        self.assertEqual(candidate.summary, body)

    def test_author_and_language_are_null_never_guessed(self):
        # No adapter supplies either; feed.py folds author into publisher.
        candidate = one([raw(PAGE, title="Acme", publisher="OpenAI")])
        self.assertIsNone(candidate.author)
        self.assertIsNone(candidate.language)

    def test_content_type_matches_the_committed_records_default(self):
        default = inspect.signature(records.make_full_record) \
            .parameters["content_type"].default
        self.assertEqual(ex.DEFAULT_CONTENT_TYPE, default)
        self.assertEqual(one([raw(PAGE)]).content_type, default)


# --------------------------------------------------------------------- dates
class TestDates(unittest.TestCase):
    def normalized(self, value):
        return one([raw(PAGE, published_at=value)]).published_at

    def test_rfc_822_as_used_by_rss(self):
        self.assertEqual(self.normalized("Mon, 06 Jul 2026 09:00:00 GMT"),
                         "2026-07-06T09:00:00Z")

    def test_iso_8601_with_z_as_used_by_atom(self):
        self.assertEqual(self.normalized("2026-07-06T09:00:00Z"),
                         "2026-07-06T09:00:00Z")

    def test_iso_8601_with_an_offset_converts_to_utc(self):
        self.assertEqual(self.normalized("2026-07-06T11:00:00+02:00"),
                         "2026-07-06T09:00:00Z")

    def test_a_bare_date_is_accepted_at_midnight_utc(self):
        self.assertEqual(self.normalized("2026-07-06"), "2026-07-06T00:00:00Z")

    def test_a_long_form_date_is_accepted(self):
        self.assertEqual(self.normalized("July 6, 2026"), "2026-07-06T00:00:00Z")

    def test_an_unparseable_date_is_null_and_reported(self):
        candidate = one([raw(PAGE, published_at="sometime last spring")])
        self.assertIsNone(candidate.published_at)
        issues = [i for i in candidate.issues if i.kind == ex.UNPARSEABLE_DATE]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].detail, "sometime last spring")

    def test_an_unparseable_date_does_not_remove_the_candidate(self):
        res = extract([dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0, title="Acme", published_at="not a date"),
            raw(OTHER, 1, title="Beta")]))])
        self.assertEqual(res.candidate_count, 2)
        self.assertIsNotNone(res.by_key(res.candidates[0].candidate_key))

    def test_a_missing_date_is_missing_not_unparseable(self):
        kinds = {i.kind for i in one([raw(PAGE)]).issues
                 if i.field == "published_at"}
        self.assertIn(ex.MISSING, kinds)
        self.assertNotIn(ex.UNPARSEABLE_DATE, kinds)

    def test_the_date_is_never_invented(self):
        for bad in ("", "   ", "yesterday", "0000", "not-a-date"):
            self.assertIsNone(self.normalized(bad), bad)


# ----------------------------------------------------------------- conflicts
class TestConflicts(unittest.TestCase):
    def conflicting(self):
        return [
            dd.delivery(LANES[1], result("openai-news", [raw(
                PAGE, title="OpenAI headline", publisher="OpenAI",
                summary="One summary.", published_at="2026-07-06T09:00:00Z")])),
            dd.delivery(LANES[0], result("anthropic-customers", [raw(
                PAGE, source_id="anthropic-customers", adapter="seed",
                title="Anthropic customer story", publisher="Anthropic",
                summary="A different summary.",
                published_at="2026-07-07T09:00:00Z")])),
        ]

    def test_display_follows_s4_1_authority(self):
        candidate = extract(self.conflicting()).candidates[0]
        self.assertEqual(candidate.title, "Anthropic customer story")
        self.assertEqual(candidate.publisher, "Anthropic")
        self.assertEqual(candidate.published_at, "2026-07-07T09:00:00Z")

    def test_authority_does_not_depend_on_delivery_order(self):
        forward = self.conflicting()
        a = serialize(extract(forward))
        b = serialize(extract(list(reversed(forward))))
        self.assertEqual(a, b)

    def test_every_conflict_is_reported(self):
        candidate = extract(self.conflicting()).candidates[0]
        conflicted = {i.field for i in candidate.issues
                      if i.kind == ex.CONFLICTING_VALUES}
        for field in ("title", "publisher", "summary", "published_at"):
            self.assertIn(field, conflicted, field)

    def test_no_alternative_value_is_discarded(self):
        candidate = extract(self.conflicting()).candidates[0]
        titles = [value for value, _ in candidate.variants("title")]
        self.assertIn("OpenAI headline", titles)
        self.assertIn("Anthropic customer story", titles)
        publishers = dict(candidate.variants("publisher"))
        self.assertEqual(publishers["OpenAI"], ("openai-news",))
        self.assertEqual(publishers["Anthropic"], ("anthropic-customers",))

    def test_the_losing_date_survives_verbatim_in_provenance(self):
        candidate = extract(self.conflicting()).candidates[0]
        dates = [value for value, _ in candidate.variants("published_at")]
        self.assertIn("2026-07-06T09:00:00Z", dates)
        self.assertIn("2026-07-07T09:00:00Z", dates)

    def test_all_observations_are_retained(self):
        candidate = extract(self.conflicting()).candidates[0]
        self.assertEqual(candidate.observation_count, 2)
        self.assertEqual(
            sorted(o["source_id"] for o in candidate.provenance_raw["observations"]),
            ["anthropic-customers", "openai-news"])

    def test_a_blank_winner_falls_through_without_losing_evidence(self):
        candidate = extract([
            dd.delivery(LANES[0], result("anthropic-customers", [raw(
                PAGE, source_id="anthropic-customers", adapter="seed",
                title="   ", publisher="Anthropic")])),
            dd.delivery(LANES[0], result("openai-news",
                                         [raw(PAGE, title="Acme story")])),
        ]).candidates[0]
        self.assertEqual(candidate.title, "Acme story")
        self.assertEqual(candidate.publisher, "Anthropic")


# ------------------------------------------------------------------ identity
class TestIdentity(unittest.TestCase):
    def test_identity_url_is_consumed_not_recomputed(self):
        group = dd.group([dd.delivery(LANES[0], result("openai-news",
                                                       [raw(PAGE)]))],
                         sources=SOURCES).groups[0]
        candidate = ex.normalize(group)
        self.assertEqual(candidate.identity_url, group.identity_url)
        self.assertEqual(candidate.identity_url, urlkey.canonicalize_string(PAGE))

    def test_canonical_url_equals_identity_url(self):
        candidate = one([raw(PAGE)])
        self.assertEqual(candidate.canonical_url, candidate.identity_url)

    def test_content_id_is_the_committed_function_of_identity_url(self):
        candidate = one([raw(PAGE)])
        self.assertEqual(candidate.content_id,
                         urlkey.content_id(candidate.identity_url))

    def test_identity_is_stable_across_metadata_changes(self):
        a = one([raw(PAGE, title="one", publisher="A")])
        b = one([raw(PAGE, title="two", publisher="B",
                     published_at="2026-07-06")])
        self.assertEqual(a.identity_url, b.identity_url)
        self.assertEqual(a.content_id, b.content_id)
        self.assertEqual(a.candidate_key, b.candidate_key)

    def test_a_tracking_variant_keeps_one_identity(self):
        res = extract([dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0, title="a"),
            raw(PAGE + "?utm_source=x", 1, title="b")]))])
        self.assertEqual(res.candidate_count, 1)
        self.assertEqual(res.candidates[0].identity_url,
                         urlkey.canonicalize_string(PAGE))

    def test_no_alias_is_ever_produced(self):
        fields = {f.name for f in dataclasses.fields(ex.ExtractedCandidate)}
        self.assertNotIn("url_aliases", fields)
        self.assertNotIn("aliases", fields)
        self.assertNotIn("redirects", fields)
        self.assertNotIn("url_aliases", serialize(extract(
            [dd.delivery(LANES[0], result("openai-news", [raw(PAGE)]))])))

    def test_fetch_dependent_fields_are_absent(self):
        fields = {f.name for f in dataclasses.fields(ex.ExtractedCandidate)}
        for absent in ("access_status", "http_status", "content_hash",
                       "updated_at", "last_checked_at", "verification_status",
                       "verification_evidence", "link_history"):
            self.assertNotIn(absent, fields, absent)


# ------------------------------------------------------------------ contexts
class TestContextsAndProvenance(unittest.TestCase):
    def three_cells(self):
        return [
            dd.delivery(LANES[0], result("openai-news", [raw(PAGE)])),
            dd.delivery(LANES[1], result("aws-ml-blog",
                                         [raw(PAGE, source_id="aws-ml-blog")])),
            dd.delivery(LANES[2], result("techcrunch-ai",
                                         [raw(PAGE, source_id="techcrunch-ai")])),
        ]

    def test_every_discovery_context_reaches_the_classifier(self):
        candidate = extract(self.three_cells()).candidates[0]
        self.assertEqual(len(candidate.contexts), 3)
        self.assertIn(("cases", "case-studies"), candidate.contexts)
        self.assertIn(("cases", "domain-applications"), candidate.contexts)
        self.assertIn(("discourse", "market-and-investment"), candidate.contexts)

    def test_source_contribution_metadata_is_carried(self):
        candidate = extract(self.three_cells()).candidates[0]
        self.assertEqual(candidate.source_ids,
                         ("aws-ml-blog", "openai-news", "techcrunch-ai"))
        self.assertEqual(candidate.lane_ids, tuple(sorted(LANES)))

    def test_request_keys_are_carried_sorted(self):
        shared = result("openai-news", [raw(PAGE)])
        res = extract([dd.delivery(LANES[0], shared, "ffff000011112222"),
                       dd.delivery(LANES[1], shared, "0000aaaabbbbcccc")])
        self.assertEqual(res.candidates[0].source_request_keys,
                         ("0000aaaabbbbcccc", "ffff000011112222"))

    def test_provenance_payload_is_the_untouched_s4_1_retention(self):
        group = dd.group(self.three_cells(), sources=SOURCES).groups[0]
        self.assertEqual(ex.normalize(group).provenance_raw,
                         group.retention_payload())

    def test_provenance_payload_is_plain_json_data(self):
        candidate = extract(self.three_cells()).candidates[0]
        json.dumps(candidate.provenance_raw)
        self.assertNotIn("record_id", candidate.provenance_raw)
        self.assertNotIn("schema_version", candidate.provenance_raw)


# --------------------------------------------------------------- pass-through
class TestUnusablePassThrough(unittest.TestCase):
    def mixed(self):
        return [dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0, title="Acme"),
            raw("ftp://openai.com/x", 1, title="not http"),
            raw("not-a-url", 2, title="not absolute")]))]

    def test_rejected_candidates_stay_separately_visible(self):
        res = extract(self.mixed())
        self.assertEqual(len(res.unusable), 2)
        self.assertEqual({u.reason for u in res.unusable},
                         {"uncanonicalizable_target_url"})

    def test_rejected_candidates_are_not_normalized(self):
        res = extract(self.mixed())
        self.assertEqual(res.candidate_count, 1)
        urls = {c.target_url for c in res.candidates}
        self.assertNotIn("ftp://openai.com/x", urls)
        self.assertNotIn("not-a-url", urls)

    def test_the_unusable_collection_is_passed_through_unmodified(self):
        deduped = dd.group(self.mixed(), sources=SOURCES)
        self.assertEqual(ex.normalize_all(deduped).unusable, deduped.unusable)

    def test_one_candidate_per_valid_group(self):
        res = extract([dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0), raw(OTHER, 1),
            raw("https://openai.com/c/", 2)]))])
        self.assertEqual(res.candidate_count, 3)
        self.assertEqual(len({c.candidate_key for c in res.candidates}), 3)


# --------------------------------------------------------------- determinism
class TestDeterminism(unittest.TestCase):
    def scenario(self):
        return [
            dd.delivery(LANES[0], result("openai-news", [
                raw(PAGE, 0, title="Acme cuts handle time",
                    published_at="Mon, 06 Jul 2026 09:00:00 GMT"),
                raw(OTHER, 1, title="Beta logistics", publisher="OpenAI")]),
                "1111111111111111"),
            dd.delivery(LANES[1], result("openai-news", [
                raw(PAGE, 0, title="Acme cuts handle time",
                    published_at="Mon, 06 Jul 2026 09:00:00 GMT"),
                raw(OTHER, 1, title="Beta logistics", publisher="OpenAI")]),
                "1111111111111111"),
            dd.delivery(LANES[2], result("aws-ml-blog", [
                raw(PAGE, 0, source_id="aws-ml-blog", title="AWS on Acme",
                    published_at="2026-07-05T00:00:00Z")]), "2222222222222222"),
            dd.delivery(LANES[0], result("anthropic-customers", [
                raw(PAGE, 0, source_id="anthropic-customers", adapter="seed",
                    title="Anthropic customer story", publisher="Anthropic")]),
                "3333333333333333"),
            dd.delivery(LANES[1], result("techcrunch-ai", [
                raw(OTHER, 0, source_id="techcrunch-ai", title="TC on Beta",
                    published_at="garbled")]), "4444444444444444"),
        ]

    def test_every_permutation_gives_one_output(self):
        base = self.scenario()
        outputs = {serialize(extract(list(order)))
                   for order in itertools.permutations(base)}
        self.assertEqual(len(outputs), 1, "input order changed the output")
        self.assertEqual(len(list(itertools.permutations(base))), 120)

    def test_shuffled_source_map_order_gives_one_output(self):
        base = self.scenario()
        rng = random.Random(7)
        outputs = set()
        for _ in range(12):
            keys = list(SOURCES)
            rng.shuffle(keys)
            deduped = dd.group(base, sources={k: SOURCES[k] for k in keys})
            outputs.add(serialize(ex.normalize_all(deduped)))
        self.assertEqual(len(outputs), 1)

    def test_candidates_are_sorted_by_candidate_key(self):
        res = extract(self.scenario())
        keys = [c.candidate_key for c in res.candidates]
        self.assertEqual(keys, sorted(keys))

    def test_issues_are_deterministically_ordered(self):
        base = self.scenario()
        first = [(i.candidate_key, i.field, i.kind) for i in extract(base).issues]
        second = [(i.candidate_key, i.field, i.kind)
                  for i in extract(list(reversed(base))).issues]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_repeated_runs_are_byte_identical(self):
        base = self.scenario()
        self.assertEqual(serialize(extract(base)), serialize(extract(base)))


# ----------------------------------------------------------------- integrity
class TestIntegrity(unittest.TestCase):
    def test_a_non_group_is_refused(self):
        with self.assertRaises(ex.ExtractError):
            ex.normalize({"candidate_key": "0" * 16})

    def test_a_non_result_is_refused(self):
        with self.assertRaises(ex.ExtractError):
            ex.normalize_all([])

    def test_an_empty_group_is_refused(self):
        empty = dd.CandidateGroup(candidate_key="0" * 16,
                                  identity_url="https://openai.com/a",
                                  observations=())
        with self.assertRaises(ex.ExtractError):
            ex.normalize(empty)

    def test_extracted_candidates_are_immutable(self):
        candidate = one([raw(PAGE, title="Acme")])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            candidate.title = "rewritten"

    def test_a_malformed_optional_field_never_removes_a_candidate(self):
        res = extract([dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0, title="unknown", summary="  ",
                publisher="unknown", published_at="nonsense")]))])
        self.assertEqual(res.candidate_count, 1)
        self.assertEqual(res.candidates[0].identity_url,
                         urlkey.canonicalize_string(PAGE))
        self.assertGreaterEqual(len(res.candidates[0].issues), 4)

    def test_result_level_issues_match_the_per_candidate_issues(self):
        res = extract([dd.delivery(LANES[0], result("openai-news", [
            raw(PAGE, 0), raw(OTHER, 1, title="Beta")]))])
        flattened = [i for c in res.candidates for i in c.issues]
        self.assertEqual(len(res.issues), len(flattened))
        for candidate in res.candidates:
            self.assertEqual(res.issues_for(candidate.candidate_key),
                             candidate.issues)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    """Metadata normalization is not body extraction. Proved on the import and
    call graphs, not on a text scan: this module's prose legitimately discusses
    fetching, bodies and ownership, and a substring search would either fail
    spuriously or be weakened until it proved nothing."""

    def setUp(self):
        self.tree = ast.parse(inspect.getsource(ex))

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
                  "fixtures", "FixtureOpener", "os", "io", "json"}
        self.assertEqual(self.imported() & banned, set())

    def test_no_pool_or_ownership_dependency(self):
        banned = {"pool", "CandidatePool"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("acquire_target_fetch", "acquire_extraction",
                          "target_fetch_owner", "extraction_owner",
                          "designated_target_fetch_owner_lane_id",
                          "designated_extraction_owner_lane_id",
                          "add_candidate", "record_established_source",
                          "reuse_snapshot", "get_or_fetch"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_no_later_stage_dependency(self):
        banned = {"classify", "verify", "facetassign", "facets", "coverage",
                  "scheduler", "schema", "precedence"}
        self.assertEqual(self.imported() & banned, set())
        for forbidden in ("make_full_record", "make_cross_reference",
                          "relevance_score", "quality_score", "case_facets",
                          "classification", "rejection_reason", "primary_category"):
            self.assertNotIn(forbidden, self.referenced(), forbidden)

    def test_it_consumes_the_committed_helpers(self):
        imported = self.imported()
        self.assertIn("dedupe", imported)
        self.assertIn("records", imported)
        self.assertIn("urlkey", imported)
        called = {n.func.attr for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("to_iso8601_utc", called)
        self.assertIn("null_if_unknown", called)

    def test_no_second_date_url_or_identity_implementation(self):
        called = {n.func.attr for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for forbidden in ("strptime", "fromisoformat", "parsedate_to_datetime",
                          "urlsplit", "urlunsplit", "urljoin", "sha256",
                          "canonicalize_string", "candidate_key",
                          "source_request_key", "record_id", "slugify"):
            self.assertNotIn(forbidden, called, forbidden)
        self.assertNotIn("datetime", self.imported())
        self.assertNotIn("hashlib", self.imported())

    def test_stage_4_writes_nothing(self):
        called = {n.func.id for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("open", called)
        self.assertNotIn("print", called)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("ExtractedCandidate", "ExtractionResult",
                     "NormalizationIssue", "normalize", "normalize_all",
                     "ExtractError"):
            self.assertTrue(hasattr(ex, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
