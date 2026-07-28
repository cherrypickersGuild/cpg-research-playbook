#!/usr/bin/env python3
"""test_schema.py — the record schema's discriminated union must be airtight.

The property that matters: a cross_reference is a POINTER, not a record. If the
union were loose, a cross_reference could be counted as an independent record in
a second category — which is exactly the duplication the taxonomy forbids — or a
half-built full record could be published as if complete.

Run via tests/test_taxonomy_schema.sh.
"""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import schema, records, urlkey  # noqa: E402

RUN = "20260728T120000Z-4242"
NOW = "2026-07-28T12:00:00Z"
IU = "https://example.com/article"


def full_record(**over):
    rec = records.make_full_record(
        record_id=urlkey.record_id("cases", IU),
        content_id=urlkey.content_id(IU),
        topic_slug="cases", category_slug="case-studies",
        cell_id="cases__case-studies",
        identity_url=IU, target_url=IU,
        harvest_run_id=RUN, source_id="openai-news", source_adapter="feed",
        title="A title", summary="A summary", curation_reason="Why it matters",
        discovered_at=NOW)
    rec.update(over)
    return rec


def cross_ref(**over):
    row = records.make_cross_reference(
        record_id=urlkey.record_id("discourse", IU),
        content_id=urlkey.content_id(IU),
        identity_url=IU, topic_slug="discourse",
        category_slug="insights-and-opinions",
        duplicate_of=urlkey.record_id("cases", IU),
        owner_topic="cases", reason="owned by cases/case-studies",
        harvest_run_id=RUN, discovered_at=NOW)
    row.update(over)
    return row


class TestEnvironment(unittest.TestCase):
    def test_pinned_validator_present(self):
        info = schema.check_environment()
        self.assertEqual(info["jsonschema_version"], schema.REQUIRED_JSONSCHEMA)
        self.assertFalse(info["dependency_drift"])
        self.assertFalse(info["python_unverified"])


class TestFullRecord(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(schema.validate(full_record(), "record.v1.json"), [])

    def test_every_required_field_is_actually_required(self):
        base = full_record()
        required = schema.load_schema("record.v1.json")["$defs"]["full_record"]["required"]
        for key in required:
            bad = copy.deepcopy(base)
            del bad[key]
            self.assertTrue(schema.validate(bad, "record.v1.json"),
                            "removing %r should invalidate the record" % key)

    def test_unknown_field_rejected(self):
        self.assertTrue(schema.validate(full_record(surprise="x"), "record.v1.json"))

    def test_topic_and_category_are_enumerated(self):
        self.assertTrue(schema.validate(full_record(topic="dev-tools"), "record.v1.json"))
        self.assertTrue(schema.validate(full_record(primary_category="misc"), "record.v1.json"))

    def test_timestamps_must_be_utc_z(self):
        for bad in ["2026-07-28", "2026-07-28T12:00:00+09:00", "2026-07-28 12:00:00Z"]:
            self.assertTrue(schema.validate(full_record(discovered_at=bad), "record.v1.json"), bad)

    def test_nullable_timestamps_accept_null(self):
        self.assertEqual(schema.validate(full_record(published_at=None, last_checked_at=None),
                                         "record.v1.json"), [])

    def test_urls_must_be_absolute(self):
        self.assertTrue(schema.validate(full_record(target_url="/relative"), "record.v1.json"))
        self.assertTrue(schema.validate(full_record(identity_url="example.com"), "record.v1.json"))

    def test_source_url_may_be_null(self):
        # Migrated AX cases have no separate surfacing URL; null is the honest value.
        self.assertEqual(schema.validate(full_record(source_url=None), "record.v1.json"), [])

    def test_scores_bounded_0_to_1(self):
        self.assertEqual(schema.validate(full_record(relevance_score=0.5), "record.v1.json"), [])
        self.assertTrue(schema.validate(full_record(relevance_score=1.5), "record.v1.json"))
        self.assertTrue(schema.validate(full_record(relevance_score=-0.1), "record.v1.json"))

    def test_scores_may_be_null(self):
        self.assertEqual(schema.validate(full_record(relevance_score=None), "record.v1.json"), [])

    def test_id_shape_enforced(self):
        self.assertTrue(schema.validate(full_record(record_id="tooshort"), "record.v1.json"))
        self.assertTrue(schema.validate(full_record(content_id="NOTHEX0123456789"), "record.v1.json"))

    def test_status_enums(self):
        self.assertTrue(schema.validate(full_record(access_status="fine"), "record.v1.json"))
        self.assertTrue(schema.validate(full_record(verification_status="verified"), "record.v1.json"),
                        "'verified' is deliberately NOT a valid value: the legacy AX field of that "
                        "name meant only 'the fetch succeeded' and was routinely misread")
        self.assertEqual(schema.validate(full_record(verification_status="fetched"),
                                         "record.v1.json"), [])

    def test_rejection_reason_enumerated_and_nullable(self):
        self.assertEqual(schema.validate(full_record(rejection_reason=None), "record.v1.json"), [])
        self.assertEqual(schema.validate(full_record(rejection_reason="seo_spam"),
                                         "record.v1.json"), [])
        self.assertTrue(schema.validate(full_record(rejection_reason="i didn't like it"),
                                        "record.v1.json"))

    def test_classification_requires_rationale(self):
        bad = full_record()
        bad["classification"] = {"rule_id": "R1", "evidence": [], "competing_categories": []}
        self.assertTrue(schema.validate(bad, "record.v1.json"))

    def test_content_hash_must_be_full_sha256_or_null(self):
        self.assertEqual(schema.validate(full_record(content_hash=None), "record.v1.json"), [])
        self.assertEqual(schema.validate(full_record(content_hash="a" * 64), "record.v1.json"), [])
        self.assertTrue(schema.validate(full_record(content_hash="a" * 16), "record.v1.json"))


class TestCrossReferenceUnion(unittest.TestCase):
    """The load-bearing property: the two branches cannot be confused."""

    def test_valid(self):
        self.assertEqual(schema.validate(cross_ref(), "record.v1.json"), [])

    def test_cross_reference_cannot_carry_full_record_fields(self):
        for field, value in [("title", "x"), ("summary", "x"), ("relevance_score", 0.9),
                             ("target_url", IU), ("canonical_url", IU),
                             ("classification", {}), ("provenance", {}),
                             ("access_status", "ok")]:
            self.assertTrue(schema.validate(cross_ref(**{field: value}), "record.v1.json"),
                            "a cross_reference carrying %r must be rejected" % field)

    def test_cross_reference_requires_something_to_point_at(self):
        bad = cross_ref()
        del bad["duplicate_of"]
        self.assertTrue(schema.validate(bad, "record.v1.json"))

    def test_cross_reference_requires_a_reason(self):
        bad = cross_ref()
        del bad["cross_reference_reason"]
        self.assertTrue(schema.validate(bad, "record.v1.json"))
        self.assertTrue(schema.validate(cross_ref(cross_reference_reason=""), "record.v1.json"))

    def test_partial_full_record_is_not_accepted_as_cross_reference(self):
        rec = full_record()
        partial = {k: rec[k] for k in ("schema_version", "record_id", "content_id",
                                       "identity_url", "topic", "primary_category",
                                       "harvest_run_id", "discovered_at")}
        partial["record_type"] = "cross_reference"
        # no duplicate_of / cross_reference_reason -> invalid
        self.assertTrue(schema.validate(partial, "record.v1.json"))

    def test_full_record_stripped_to_cross_reference_fields_is_rejected_as_full(self):
        rec = full_record()
        partial = {k: rec[k] for k in ("schema_version", "record_type", "record_id",
                                       "content_id", "identity_url", "topic",
                                       "primary_category", "harvest_run_id", "discovered_at")}
        self.assertTrue(schema.validate(partial, "record.v1.json"))

    def test_unknown_record_type_rejected(self):
        self.assertTrue(schema.validate(full_record(record_type="stub"), "record.v1.json"))

    def test_exactly_one_branch_matches(self):
        import jsonschema
        v = jsonschema.Draft202012Validator(schema.load_schema("record.v1.json"),
                                            registry=schema._build_registry())
        # oneOf means a document matching BOTH branches would also be invalid;
        # assert the valid documents each match exactly one.
        self.assertEqual(list(v.iter_errors(full_record())), [])
        self.assertEqual(list(v.iter_errors(cross_ref())), [])


class TestArtifactSchemas(unittest.TestCase):
    def _cell(self, recs):
        return {
            "schema_version": 1, "artifact_type": "cell",
            "topic": "Cases", "topic_slug": "cases",
            "category": "Case Studies", "category_slug": "case-studies",
            "cell_id": "cases__case-studies",
            "generated_at": NOW, "harvest_run_id": RUN,
            "metadata": {
                "total_records": len(recs),
                "full_records": sum(1 for r in recs if r["record_type"] == "full"),
                "cross_references": sum(1 for r in recs if r["record_type"] == "cross_reference"),
                "sources": [{"source_id": "openai-news", "adapter": "feed", "result": "ok"}],
            },
            "records": recs,
        }

    def test_cell_artifact_valid(self):
        self.assertEqual(schema.validate(self._cell([full_record()]), "cell_artifact.v1.json"), [])

    def test_cell_artifact_accepts_mixed_records(self):
        self.assertEqual(
            schema.validate(self._cell([full_record(), cross_ref()]), "cell_artifact.v1.json"), [])

    def test_cell_artifact_rejects_a_malformed_record(self):
        bad = self._cell([full_record(record_id="short")])
        self.assertTrue(schema.validate(bad, "cell_artifact.v1.json"))

    def test_zero_result_source_is_valid_not_an_error(self):
        art = self._cell([])
        art["metadata"]["sources"] = [{
            "source_id": "producthunt", "adapter": "feed",
            "result": "zero_result", "reason": "category_exclusion_applied",
            "candidates": 12, "accepted": 0}]
        self.assertEqual(schema.validate(art, "cell_artifact.v1.json"), [])

    def test_source_result_is_enumerated(self):
        art = self._cell([])
        art["metadata"]["sources"] = [{"source_id": "x", "adapter": "feed", "result": "weird"}]
        self.assertTrue(schema.validate(art, "cell_artifact.v1.json"))

    def test_topic_artifact_valid(self):
        art = {
            "schema_version": 1, "artifact_type": "topic",
            "topic": "Cases", "topic_slug": "cases",
            "generated_at": NOW, "harvest_run_id": RUN,
            "metadata": {"total_records": 1, "full_records": 1, "cross_references": 0,
                         "by_category": {"case-studies": 1},
                         "cells": [{"cell_id": "cases__case-studies", "present": True, "records": 1}]},
            "records": [full_record()],
        }
        self.assertEqual(schema.validate(art, "topic_artifact.v1.json"), [])

    def test_run_manifest_valid(self):
        man = {
            "schema_version": 1, "harvest_run_id": RUN, "mode": "smoke",
            "started_at": NOW, "finished_at": NOW,
            "environment": {"python_version": "3.13.9", "jsonschema_version": "4.26.0",
                            "platform": "win32"},
            "config": {"cross_topic_policy": "cross_reference", "enrich": False},
            "source_preflight": [{"source_id": "openai-news", "result": "ok"}],
            "cells": [{"cell_id": "cases__case-studies", "topic_slug": "cases",
                       "category_slug": "case-studies", "status": "zero_result",
                       "zero_result_reason": "no_items_in_window"}],
            "classification_decisions": [],
            "publication_eligible": False,
            "publication_ineligible_reason": "bounded smoke: enrichment disabled",
        }
        self.assertEqual(schema.validate(man, "run_manifest.v1.json"), [])

    def test_run_manifest_rejects_unknown_zero_result_reason(self):
        man = {
            "schema_version": 1, "harvest_run_id": RUN, "mode": "smoke",
            "started_at": NOW, "finished_at": NOW,
            "environment": {"python_version": "3.13.9", "jsonschema_version": "4.26.0",
                            "platform": "win32"},
            "config": {}, "source_preflight": [],
            "cells": [{"cell_id": "c__d", "topic_slug": "c", "category_slug": "d",
                       "status": "zero_result", "zero_result_reason": "felt like it"}],
            "classification_decisions": [], "publication_eligible": False,
        }
        self.assertTrue(schema.validate(man, "run_manifest.v1.json"))

    def test_run_id_shape_enforced(self):
        man = {
            "schema_version": 1, "harvest_run_id": "not-a-run-id", "mode": "smoke",
            "started_at": NOW, "finished_at": NOW,
            "environment": {"python_version": "3.13.9", "jsonschema_version": "4.26.0",
                            "platform": "win32"},
            "config": {}, "source_preflight": [], "cells": [],
            "classification_decisions": [], "publication_eligible": False,
        }
        self.assertTrue(schema.validate(man, "run_manifest.v1.json"))

    def test_ledger_and_rejection_schemas(self):
        led = {"schema_version": 1, "cell_id": "cases__case-studies", "updated_at": NOW,
               "entries": [{"identity_url": IU, "first_seen_at": NOW, "last_seen_at": NOW,
                            "seen_count": 1, "outcome": "accepted"}]}
        self.assertEqual(schema.validate(led, "ledger.v1.json"), [])

        rej = {"schema_version": 1, "cell_id": "cases__case-studies",
               "harvest_run_id": RUN, "generated_at": NOW,
               "rejections": [{"identity_url": IU, "source_id": "openai-news",
                               "rejection_reason": "developer_only_audience",
                               "rejected_at": NOW}]}
        self.assertEqual(schema.validate(rej, "rejection.v1.json"), [])

        rej["rejections"][0]["rejection_reason"] = "vibes"
        self.assertTrue(schema.validate(rej, "rejection.v1.json"))


class TestDeterministicOrdering(unittest.TestCase):
    def test_sort_is_stable_and_independent_of_input_order(self):
        a = full_record()
        b = cross_ref()
        self.assertEqual([r["record_id"] for r in records.sort_records([a, b])],
                         [r["record_id"] for r in records.sort_records([b, a])])


if __name__ == "__main__":
    unittest.main(verbosity=2)
