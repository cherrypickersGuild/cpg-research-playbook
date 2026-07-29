#!/usr/bin/env python3
"""test_cell_artifact.py — cell and topic artifact contents (S5-2).

S5-1 already proved the shared writer is atomic, deterministic and
validate-before-write; those guarantees are reused here, not re-proved. What is
new is what goes INSIDE the two artifacts:

  * ORDER IS A FUNCTION OF CONTENT. Records are sorted by the committed
    `records.sort_key`, so shuffled input yields byte-identical artifacts and two
    runs can be compared by hash.
  * A POINTER IS NOT CONTENT. A `cross_reference` may sit in a cell artifact but
    is counted separately from `full_records` and never contributes to a
    category's coverage.
  * COUNTS CANNOT LIE. Every count is derived from the records in the artifact,
    and a caller that tries to supply one is refused — two sources of truth for
    "how many records are here" is how an artifact starts describing a set it
    does not contain.
  * A BAD RECORD SURFACES AS ITSELF. Records are validated against
    `record.v1.json` BEFORE assembly, so a `cases__domain-applications` record
    missing its facets is refused by name rather than swallowed.
  * D2 HAS ONE HOME. The `{signal, matched}` projection lives in `artifacts.py`;
    forwarding `classify.Evidence` wholesale is refused by the schema.

Offline and temp-rooted: no network, no fixtures, no pool, no cell execution.
Run via tests/test_taxonomy_cell_artifact.sh.
"""
import copy
import glob
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, classify as cl, records, schema, urlkey  # noqa: E402

RUN = "20260730T120000Z-4242"
NOW = "2026-07-30T12:00:00Z"

FACETS = {
    "facets_version": 1,
    "vocabulary_versions": {"industries": 1, "business_functions": 1,
                            "use_case_types": 1},
    "classification_state": "unresolved",
    "industry": {"primary": None, "secondary": [], "confidence": None,
                 "evidence": []},
    "business_functions": [],
    "use_case_types": [],
    "unresolved": [],
}


def full_record(url, topic="cases", category="domain-applications", **over):
    rec = records.make_full_record(
        record_id=urlkey.record_id(topic, url),
        content_id=urlkey.content_id(url),
        topic_slug=topic, category_slug=category,
        cell_id="%s__%s" % (topic, category),
        identity_url=url, target_url=url,
        harvest_run_id=RUN, source_id="aws-ml-blog", source_adapter="feed",
        title="A title", summary="A summary", discovered_at=NOW,
        case_facets=copy.deepcopy(FACETS) if category == "domain-applications" else None)
    rec.update(over)
    return rec


def cross_ref(url, topic="cases", category="domain-applications"):
    return records.make_cross_reference(
        record_id=urlkey.record_id(topic, url),
        content_id=urlkey.content_id(url),
        identity_url=url, topic_slug=topic, category_slug=category,
        duplicate_of=urlkey.record_id("research-and-models", url),
        owner_topic="research-and-models", reason="owned elsewhere",
        harvest_run_id=RUN, discovered_at=NOW)


def cell(recs, cell_id="cases__domain-applications",
         category="Domain Applications", category_slug="domain-applications",
         **over):
    kwargs = dict(topic="Cases", topic_slug="cases", category=category,
                  category_slug=category_slug, cell_id=cell_id,
                  harvest_run_id=RUN, generated_at=NOW)
    kwargs.update(over)
    return artifacts.build_cell_artifact(recs, **kwargs)


def topic(cells, **over):
    kwargs = dict(topic="Cases", topic_slug="cases", harvest_run_id=RUN,
                  generated_at=NOW)
    kwargs.update(over)
    return artifacts.build_topic_artifact(cells, **kwargs)


class TempRootCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_cell_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)


# ------------------------------------------------------------ cell artifact
class TestCellArtifact(unittest.TestCase):
    def test_it_validates(self):
        art = cell([full_record("https://example.com/a/")])
        self.assertEqual(schema.validate(art, "cell_artifact.v1.json"), [])

    def test_every_required_key_is_present(self):
        art = cell([full_record("https://example.com/a/")])
        required = schema.load_schema("cell_artifact.v1.json")["required"]
        for key in required:
            self.assertIn(key, art, key)

    def test_the_artifact_type_is_pinned(self):
        self.assertEqual(cell([])["artifact_type"], "cell")

    def test_an_empty_cell_is_valid_not_an_error(self):
        art = cell([])
        self.assertEqual(schema.validate(art, "cell_artifact.v1.json"), [])
        self.assertEqual(art["metadata"]["total_records"], 0)

    def test_records_are_sorted_by_the_committed_key(self):
        urls = ["https://example.com/%d/" % i for i in range(6)]
        art = cell([full_record(u) for u in urls])
        keys = [records.sort_key(r) for r in art["records"]]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_input_yields_identical_bytes(self):
        recs = [full_record("https://example.com/%d/" % i) for i in range(8)]
        expected = artifacts.serialize(cell(recs))
        rng = random.Random(20260730)
        for _ in range(5):
            shuffled = list(recs)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(cell(shuffled)), expected)

    def test_an_invented_top_level_field_is_refused(self):
        art = cell([])
        art["extra_field"] = "nope"
        self.assertNotEqual(schema.validate(art, "cell_artifact.v1.json"), [])

    def test_the_builder_does_not_alias_its_input(self):
        recs = [full_record("https://example.com/a/")]
        art = cell(recs)
        art["records"][0]["title"] = "MUTATED"
        self.assertNotEqual(recs[0]["title"], "MUTATED")


# ----------------------------------------------------------- counts and pointers
class TestCounts(unittest.TestCase):
    def test_a_cross_reference_is_counted_separately_from_full_records(self):
        art = cell([full_record("https://example.com/a/"),
                    full_record("https://example.com/b/"),
                    cross_ref("https://example.com/c/")])
        meta = art["metadata"]
        self.assertEqual(meta["full_records"], 2)
        self.assertEqual(meta["cross_references"], 1)
        self.assertEqual(meta["total_records"], 3)

    def test_total_is_full_plus_cross_references(self):
        art = cell([full_record("https://example.com/a/"),
                    cross_ref("https://example.com/c/")])
        meta = art["metadata"]
        self.assertEqual(meta["total_records"],
                         meta["full_records"] + meta["cross_references"])

    def test_counts_match_the_records_actually_carried(self):
        art = cell([full_record("https://example.com/%d/" % i) for i in range(4)])
        self.assertEqual(art["metadata"]["total_records"], len(art["records"]))

    def test_a_caller_may_not_supply_a_derived_count(self):
        for bad in ("total_records", "full_records", "cross_references"):
            with self.assertRaises(artifacts.ArtifactError) as caught:
                cell([], metadata={"sources": [], bad: 999})
            self.assertIn(bad, str(caught.exception))

    def test_caller_metadata_that_is_not_derivable_survives(self):
        sources = [{"source_id": "aws-ml-blog", "adapter": "feed",
                    "result": "zero_result", "reason": "no_items_in_window"}]
        art = cell([], metadata={"sources": sources, "rejected": 3})
        self.assertEqual(art["metadata"]["sources"], sources)
        self.assertEqual(art["metadata"]["rejected"], 3)
        self.assertEqual(schema.validate(art, "cell_artifact.v1.json"), [])


# ------------------------------------------------- validate records before assembly
class TestRecordValidation(unittest.TestCase):
    def test_a_domain_applications_record_without_facets_is_refused(self):
        bad = full_record("https://example.com/a/")
        del bad["case_facets"]
        with self.assertRaises(artifacts.ArtifactError) as caught:
            cell([bad])
        self.assertIn(bad["record_id"], str(caught.exception))

    def test_a_research_record_with_facets_is_refused(self):
        bad = full_record("https://example.com/a/", topic="research-and-models",
                          category="papers")
        bad["case_facets"] = copy.deepcopy(FACETS)
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.build_cell_artifact(
                [bad], topic="Research & Models", topic_slug="research-and-models",
                category="Papers", category_slug="papers",
                cell_id="research-and-models__papers", harvest_run_id=RUN,
                generated_at=NOW)

    def test_the_refusal_names_the_offending_record(self):
        bad = full_record("https://example.com/a/")
        bad["record_type"] = "nonsense"
        with self.assertRaises(artifacts.ArtifactError) as caught:
            cell([bad])
        self.assertIn("record.v1.json", str(caught.exception))

    def test_a_valid_mixed_set_is_accepted(self):
        art = cell([full_record("https://example.com/a/"),
                    cross_ref("https://example.com/b/")])
        self.assertEqual(schema.validate(art, "cell_artifact.v1.json"), [])


# ------------------------------------------------------------- D2 projection
class TestClassificationEvidenceProjection(unittest.TestCase):
    def test_it_narrows_to_the_schema_admitted_keys(self):
        got = artifacts.project_classification_evidence(
            [cl.Evidence(signal="is_case_study", matched="deployed", field="title")])
        self.assertEqual(got, [{"signal": "is_case_study", "matched": "deployed"}])

    def test_the_dropped_key_is_the_one_the_schema_refuses(self):
        item = (schema.load_schema("record.v1.json")["$defs"]["classification"]
                ["properties"]["evidence"]["items"])
        self.assertEqual(set(item["properties"]),
                         set(artifacts.CLASSIFICATION_EVIDENCE_KEYS))
        self.assertFalse(item["additionalProperties"])

    def test_it_accepts_dicts_as_well_as_the_dataclass(self):
        self.assertEqual(
            artifacts.project_classification_evidence(
                [{"signal": "s", "matched": "m", "field": "title"}]),
            [{"signal": "s", "matched": "m"}])

    def test_empty_and_none_are_both_empty(self):
        self.assertEqual(artifacts.project_classification_evidence([]), [])
        self.assertEqual(artifacts.project_classification_evidence(None), [])

    def test_an_unprojected_record_cannot_reach_an_artifact(self):
        # The projection and the record schema are linked, not merely adjacent.
        bad = full_record("https://example.com/a/")
        bad["classification"]["evidence"] = [
            {"signal": "s", "matched": "m", "field": "title"}]
        with self.assertRaises(artifacts.ArtifactError):
            cell([bad])
        bad["classification"]["evidence"] = artifacts.project_classification_evidence(
            [{"signal": "s", "matched": "m", "field": "title"}])
        self.assertEqual(schema.validate(cell([bad]), "cell_artifact.v1.json"), [])


# ----------------------------------------------------------- topic artifact
class TestTopicArtifact(unittest.TestCase):
    def two_cells(self):
        a = cell([full_record("https://example.com/a/"),
                  full_record("https://example.com/b/")])
        b = cell([full_record("https://example.com/c/", category="case-studies")],
                 cell_id="cases__case-studies", category="Case Studies",
                 category_slug="case-studies")
        return [a, b]

    def test_it_validates(self):
        self.assertEqual(schema.validate(topic(self.two_cells()),
                                         "topic_artifact.v1.json"), [])

    def test_the_artifact_type_is_pinned(self):
        self.assertEqual(topic([])["artifact_type"], "topic")

    def test_it_merges_every_cell_record(self):
        art = topic(self.two_cells())
        self.assertEqual(art["metadata"]["total_records"], 3)
        self.assertEqual(len(art["records"]), 3)

    def test_it_deduplicates_by_record_id(self):
        # The same identity in two categories of one topic is ONE record:
        # record_id is derived from (topic, identity_url).
        shared = "https://example.com/shared/"
        a = cell([full_record(shared)])
        b = cell([full_record(shared, category="case-studies")],
                 cell_id="cases__case-studies", category="Case Studies",
                 category_slug="case-studies")
        art = topic([a, b])
        self.assertEqual(len(art["records"]), 1)
        self.assertEqual(art["metadata"]["total_records"], 1)

    def test_deduplication_is_deterministic_under_cell_order(self):
        shared = "https://example.com/shared/"
        a = cell([full_record(shared)])
        b = cell([full_record(shared, category="case-studies")],
                 cell_id="cases__case-studies", category="Case Studies",
                 category_slug="case-studies")
        self.assertEqual(artifacts.serialize(topic([a, b])),
                         artifacts.serialize(topic([b, a])))

    def test_records_are_re_sorted_across_cells(self):
        art = topic(list(reversed(self.two_cells())))
        keys = [records.sort_key(r) for r in art["records"]]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_cell_order_yields_identical_bytes(self):
        cells = self.two_cells()
        expected = artifacts.serialize(topic(cells))
        rng = random.Random(4242)
        for _ in range(5):
            shuffled = list(cells)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(topic(shuffled)), expected)

    def test_by_category_counts_full_records_only(self):
        a = cell([full_record("https://example.com/a/"),
                  cross_ref("https://example.com/x/")])
        art = topic([a])
        self.assertEqual(art["metadata"]["by_category"], {"domain-applications": 1})
        self.assertEqual(art["metadata"]["cross_references"], 1)

    def test_by_category_sums_to_full_records(self):
        art = topic(self.two_cells())
        self.assertEqual(sum(art["metadata"]["by_category"].values()),
                         art["metadata"]["full_records"])

    def test_the_cells_block_names_every_contributing_cell(self):
        art = topic(self.two_cells())
        rows = art["metadata"]["cells"]
        self.assertEqual([r["cell_id"] for r in rows],
                         ["cases__case-studies", "cases__domain-applications"])
        self.assertTrue(all(r["present"] for r in rows))
        self.assertEqual(sum(r["records"] for r in rows), 3)

    def test_an_invented_top_level_field_is_refused(self):
        art = topic([])
        art["extra_field"] = "nope"
        self.assertNotEqual(schema.validate(art, "topic_artifact.v1.json"), [])

    def test_a_caller_may_not_supply_a_derived_count(self):
        with self.assertRaises(artifacts.ArtifactError):
            topic([], metadata={"by_category": {"x": 1}})


# ------------------------------------------------------------ paths and writing
class TestPathsAndWriting(TempRootCase):
    def test_the_cell_path_follows_the_committed_layout(self):
        got = artifacts.cell_artifact_path(self.root, RUN, "cases__domain-applications")
        self.assertEqual(got, os.path.join(self.root, "runs", RUN, "cells",
                                           "cases__domain-applications.json"))

    def test_the_topic_path_follows_the_committed_layout(self):
        got = artifacts.topic_artifact_path(self.root, RUN, "cases")
        self.assertEqual(got, os.path.join(self.root, "runs", RUN, "topics",
                                           "cases.json"))

    def test_a_cell_artifact_round_trips_through_the_writer(self):
        art = cell([full_record("https://example.com/a/")])
        path = artifacts.cell_artifact_path(self.root, RUN, art["cell_id"])
        artifacts.write_cell_artifact(path, art)
        with open(path, "rb") as fh:
            written = json.loads(fh.read().decode("utf-8"))
        self.assertEqual(written, art)
        self.assertEqual(schema.validate(written, "cell_artifact.v1.json"), [])

    def test_a_topic_artifact_round_trips_through_the_writer(self):
        art = topic([cell([full_record("https://example.com/a/")])])
        path = artifacts.topic_artifact_path(self.root, RUN, "cases")
        artifacts.write_topic_artifact(path, art)
        with open(path, "rb") as fh:
            self.assertEqual(json.loads(fh.read().decode("utf-8")), art)

    def test_an_invalid_artifact_writes_no_file(self):
        art = cell([])
        art["extra_field"] = "nope"
        path = artifacts.cell_artifact_path(self.root, RUN, "cases__domain-applications")
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_cell_artifact(path, art)
        self.assertFalse(os.path.exists(path))

    def test_two_writes_of_the_same_artifact_are_byte_identical(self):
        art = cell([full_record("https://example.com/a/")])
        one = os.path.join(self.root, "one.json")
        two = os.path.join(self.root, "two.json")
        artifacts.write_cell_artifact(one, art)
        artifacts.write_cell_artifact(two, art)
        with open(one, "rb") as a, open(two, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_writing_leaves_no_temp_debris(self):
        art = cell([full_record("https://example.com/a/")])
        path = artifacts.cell_artifact_path(self.root, RUN, art["cell_id"])
        artifacts.write_cell_artifact(path, art)
        directory = os.path.dirname(path)
        self.assertEqual(glob.glob(os.path.join(directory,
                                                artifacts.TEMP_PREFIX + "*")), [])


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_s5_2_adds_no_later_checkpoint_module(self):
        for later in ("ledger.py", "run_cells.py"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, "src", "harvest", later)),
                             later)

    def test_it_reuses_the_committed_sort_key(self):
        art = cell([full_record("https://example.com/%d/" % i) for i in range(5)])
        self.assertEqual(art["records"],
                         records.sort_records(list(art["records"])))

    def test_it_does_not_reimplement_record_construction(self):
        tokens = {n for n in dir(artifacts) if not n.startswith("_")}
        for later in ("make_full_record", "make_cross_reference"):
            self.assertNotIn(later, tokens)


if __name__ == "__main__":
    unittest.main(verbosity=2)
