#!/usr/bin/env python3
"""test_ledger.py — the per-cell rejection log and URL ledger (S5-3).

S5-1 already proved the writer is atomic and validate-before-write; that is
reused, not re-proved. What is new is the two data contracts:

  * EVERY REASON verify CAN EMIT MUST BE STORABLE. The reasons are enumerated
    from `verify.decide`'s own AST rather than typed here, so the day a new
    rejection reason is added this test fails instead of the artifact. This is
    the CF-2 reconciliation, pinned.
  * FIRST SEEN IS WRITTEN ONCE. Re-merging the same observations advances
    `last_seen_at` and `seen_count` and touches nothing else — not
    `first_seen_at`, not `outcome`, not the entry count.
  * A TERMINAL OUTCOME IS FINAL. `pending -> accepted|rejected|duplicate` once. A
    second observation claiming a different terminal outcome is a contradiction
    and raises; a later `pending` sighting never un-decides a decided URL.
  * A REJECTED URL STAYS REJECTED, so it is not re-fetched and re-rejected on
    every run.
  * LOSING A LEDGER IS EXPENSIVE. A corrupt or foreign ledger raises rather than
    being treated as empty, which would silently re-harvest the whole cell.

Offline and temp-rooted: no network, no fixtures, no cell execution, no
concurrency. Run via tests/test_taxonomy_ledger.sh.
"""
import ast
import dataclasses
import inspect
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, ledger, schema, verify as vf  # noqa: E402

CELL = "cases__domain-applications"
RUN = "20260730T120000Z-4242"
NOW = "2026-07-30T12:00:00Z"
LATER = "2026-07-31T09:30:00Z"


@dataclasses.dataclass(frozen=True)
class FakeExtracted:
    """Only the fields a rejection entry reads. Not a stand-in for extract.py."""
    identity_url: str
    target_url: str = "https://example.com/t/"
    title: str = "A title"
    source_ids: tuple = ("aws-ml-blog",)
    candidate_key: str = "k"


def verdict(reason="off_topic", *, accepted=False, detail="because",
            relevance=0.1, quality=0.4, audience_fit=1.0, freshness=None):
    scores = vf.Scores(relevance=relevance, quality=quality,
                       audience_fit=audience_fit, freshness=freshness)
    return vf.Verdict(candidate_key="k", accepted=accepted, scores=scores,
                      rejection_reason=None if accepted else reason, detail=detail)


def pair(url, reason="off_topic", **kw):
    return (FakeExtracted(identity_url=url), verdict(reason, **kw))


def log(pairs, **over):
    kwargs = dict(cell_id=CELL, harvest_run_id=RUN, generated_at=NOW)
    kwargs.update(over)
    return ledger.build_rejection_log(pairs, **kwargs)


def emitted_rejection_reasons():
    """The reasons `verify.decide` can actually produce, read from its AST.

    Typing them into the test would defeat the purpose: this must fail when
    verify.py grows a reason the rejection schema cannot store.
    """
    tree = ast.parse(inspect.getsource(vf.decide))
    reasons = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "verdict"):
            continue
        for arg in node.args[1:2]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    reasons.add(sub.value)
        for kw in node.keywords:
            if kw.arg == "reason":
                for sub in ast.walk(kw.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        reasons.add(sub.value)
    return reasons


class TempRootCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_ledger_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)


# ------------------------------------------------------------- rejection log
class TestRejectionLog(unittest.TestCase):
    def test_it_validates(self):
        doc = log([pair("https://example.com/a/")])
        self.assertEqual(schema.validate(doc, "rejection.v1.json"), [])

    def test_every_required_key_is_present(self):
        doc = log([pair("https://example.com/a/")])
        for key in schema.load_schema("rejection.v1.json")["required"]:
            self.assertIn(key, doc, key)

    def test_an_empty_log_is_valid(self):
        doc = log([])
        self.assertEqual(schema.validate(doc, "rejection.v1.json"), [])
        self.assertEqual(doc["rejections"], [])

    def test_accepted_verdicts_are_not_logged(self):
        doc = log([pair("https://example.com/a/"),
                   (FakeExtracted("https://example.com/ok/"), verdict(accepted=True))])
        urls = [r["identity_url"] for r in doc["rejections"]]
        self.assertEqual(urls, ["https://example.com/a/"])

    def test_the_reason_comes_from_the_verdict(self):
        doc = log([pair("https://example.com/a/", "below_quality_threshold")])
        self.assertEqual(doc["rejections"][0]["rejection_reason"],
                         "below_quality_threshold")

    def test_the_scores_come_from_the_verdict(self):
        doc = log([pair("https://example.com/a/", relevance=0.25, quality=0.5)])
        scores = doc["rejections"][0]["scores"]
        self.assertEqual(scores["relevance"], 0.25)
        self.assertEqual(scores["quality"], 0.5)
        self.assertIsNone(scores["freshness"])

    def test_the_detail_survives_verbatim(self):
        doc = log([pair("https://example.com/a/",
                        detail="composite 0.3100 < accept_composite 0.4000")])
        self.assertEqual(doc["rejections"][0]["detail"],
                         "composite 0.3100 < accept_composite 0.4000")

    def test_a_refusal_without_a_reason_is_itself_refused(self):
        bad = vf.Verdict(candidate_key="k", accepted=False, scores=vf.Scores(),
                         rejection_reason=None)
        with self.assertRaises(ledger.LedgerError):
            log([(FakeExtracted("https://example.com/a/"), bad)])

    def test_a_candidate_with_no_source_is_refused(self):
        with self.assertRaises(ledger.LedgerError):
            log([(FakeExtracted("https://example.com/a/", source_ids=()), verdict())])

    def test_rejections_are_sorted_by_reason_then_url(self):
        doc = log([pair("https://example.com/z/", "off_topic"),
                   pair("https://example.com/a/", "off_topic"),
                   pair("https://example.com/m/", "below_quality_threshold")])
        keys = [(r["rejection_reason"], r["identity_url"]) for r in doc["rejections"]]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_input_yields_identical_bytes(self):
        pairs = [pair("https://example.com/%d/" % i,
                      ["off_topic", "below_quality_threshold",
                       "insufficient_evidence"][i % 3]) for i in range(9)]
        expected = artifacts.serialize(log(pairs))
        rng = random.Random(20260730)
        for _ in range(5):
            shuffled = list(pairs)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(log(shuffled)), expected)

    def test_an_invented_field_is_refused_by_the_schema(self):
        doc = log([])
        doc["extra_field"] = "nope"
        self.assertNotEqual(schema.validate(doc, "rejection.v1.json"), [])


# ------------------------------------------------- CF-2: the reason vocabulary
class TestReasonVocabulary(unittest.TestCase):
    def test_verify_emits_at_least_the_gate_ladder(self):
        emitted = emitted_rejection_reasons()
        self.assertGreaterEqual(len(emitted), 6, emitted)
        for expected in ("off_topic", "insufficient_evidence",
                         "below_relevance_threshold", "below_quality_threshold",
                         "category_exclusion_applied", "developer_only_audience"):
            self.assertIn(expected, emitted)

    def test_every_reason_verify_emits_is_storable(self):
        # CF-2, pinned: this is what makes the finding non-blocking rather than
        # merely believed to be non-blocking.
        allowed = set(schema.load_schema("rejection.v1.json")["properties"]
                      ["rejections"]["items"]["properties"]["rejection_reason"]["enum"])
        unstorable = sorted(emitted_rejection_reasons() - allowed)
        self.assertEqual(unstorable, [], "verify emits reasons the log cannot store")

    def test_each_emitted_reason_really_validates_in_a_log(self):
        for reason in sorted(emitted_rejection_reasons()):
            doc = log([pair("https://example.com/a/", reason)])
            self.assertEqual(schema.validate(doc, "rejection.v1.json"), [], reason)

    def test_a_reason_outside_the_committed_enum_is_refused(self):
        doc = log([pair("https://example.com/a/", "below_composite_threshold")])
        self.assertNotEqual(schema.validate(doc, "rejection.v1.json"), [],
                            "the schema must reject an uncommitted reason")


# ------------------------------------------------------------- ledger merge
class TestLedgerMerge(unittest.TestCase):
    def test_a_first_observation_creates_the_entry(self):
        doc = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                  now=NOW, cell_id=CELL)
        self.assertEqual(schema.validate(doc, "ledger.v1.json"), [])
        entry = doc["entries"][0]
        self.assertEqual(entry["first_seen_at"], NOW)
        self.assertEqual(entry["last_seen_at"], NOW)
        self.assertEqual(entry["seen_count"], 1)
        self.assertEqual(entry["outcome"], "pending")

    def test_a_second_observation_advances_only_the_counters(self):
        first = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                    now=NOW, cell_id=CELL)
        second = ledger.merge_ledger(first, [{"identity_url": "https://example.com/a/"}],
                                     now=LATER)
        entry = second["entries"][0]
        self.assertEqual(entry["first_seen_at"], NOW, "first_seen_at was rewritten")
        self.assertEqual(entry["last_seen_at"], LATER)
        self.assertEqual(entry["seen_count"], 2)
        self.assertEqual(len(second["entries"]), 1)

    def test_a_double_merge_changes_nothing_else(self):
        obs = [{"identity_url": "https://example.com/a/", "outcome": "accepted",
                "record_id": "r1"},
               {"identity_url": "https://example.com/b/", "outcome": "rejected",
                "rejection_reason": "off_topic"}]
        once = ledger.merge_ledger(None, obs, now=NOW, cell_id=CELL)
        twice = ledger.merge_ledger(once, obs, now=LATER)
        self.assertEqual(len(twice["entries"]), len(once["entries"]))
        for before, after in zip(once["entries"], twice["entries"]):
            self.assertEqual(before["first_seen_at"], after["first_seen_at"])
            self.assertEqual(before["outcome"], after["outcome"])
            self.assertEqual(after["seen_count"], before["seen_count"] + 1)
            self.assertEqual(after["last_seen_at"], LATER)

    def test_pending_may_become_terminal(self):
        first = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                    now=NOW, cell_id=CELL)
        for terminal in ledger.TERMINAL_OUTCOMES:
            got = ledger.merge_ledger(first, [{"identity_url": "https://example.com/a/",
                                               "outcome": terminal}], now=LATER)
            self.assertEqual(got["entries"][0]["outcome"], terminal)

    def test_a_terminal_outcome_is_final(self):
        done = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                           "outcome": "accepted"}],
                                   now=NOW, cell_id=CELL)
        with self.assertRaises(ledger.LedgerError) as caught:
            ledger.merge_ledger(done, [{"identity_url": "https://example.com/a/",
                                        "outcome": "rejected"}], now=LATER)
        self.assertIn("accepted", str(caught.exception))

    def test_a_later_pending_sighting_does_not_undecide(self):
        done = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                           "outcome": "rejected"}],
                                   now=NOW, cell_id=CELL)
        got = ledger.merge_ledger(done, [{"identity_url": "https://example.com/a/"}],
                                  now=LATER)
        self.assertEqual(got["entries"][0]["outcome"], "rejected")

    def test_a_rejected_url_is_retained(self):
        # Drop it and every run re-fetches and re-rejects the same URL.
        doc = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                          "outcome": "rejected",
                                          "rejection_reason": "off_topic"}],
                                  now=NOW, cell_id=CELL)
        entry = doc["entries"][0]
        self.assertEqual(entry["outcome"], "rejected")
        self.assertEqual(entry["rejection_reason"], "off_topic")

    def test_entries_are_sorted_by_identity_url(self):
        urls = ["https://example.com/%s/" % s for s in "zqamb"]
        doc = ledger.merge_ledger(None, [{"identity_url": u} for u in urls],
                                  now=NOW, cell_id=CELL)
        got = [e["identity_url"] for e in doc["entries"]]
        self.assertEqual(got, sorted(got))

    def test_observation_order_does_not_change_the_bytes(self):
        obs = [{"identity_url": "https://example.com/%d/" % i} for i in range(8)]
        expected = artifacts.serialize(
            ledger.merge_ledger(None, obs, now=NOW, cell_id=CELL))
        rng = random.Random(7)
        for _ in range(5):
            shuffled = list(obs)
            rng.shuffle(shuffled)
            self.assertEqual(artifacts.serialize(
                ledger.merge_ledger(None, shuffled, now=NOW, cell_id=CELL)), expected)

    def test_an_observation_may_not_set_a_merge_owned_field(self):
        for field in ledger.MERGE_OWNED_FIELDS:
            with self.assertRaises(ledger.LedgerError) as caught:
                ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                            field: "x"}], now=NOW, cell_id=CELL)
            self.assertIn(field, str(caught.exception))

    def test_an_observation_without_an_identity_is_refused(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.merge_ledger(None, [{"source_id": "aws-ml-blog"}],
                                now=NOW, cell_id=CELL)

    def test_an_unknown_observation_field_is_refused(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                        "invented": 1}], now=NOW, cell_id=CELL)

    def test_an_unknown_outcome_is_refused(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/",
                                        "outcome": "maybe"}], now=NOW, cell_id=CELL)

    def test_merging_into_a_new_ledger_needs_a_cell_id(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.merge_ledger(None, [], now=NOW)

    def test_the_existing_ledger_is_not_mutated(self):
        first = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                    now=NOW, cell_id=CELL)
        snapshot = json.loads(json.dumps(first))
        ledger.merge_ledger(first, [{"identity_url": "https://example.com/a/"}],
                            now=LATER)
        self.assertEqual(first, snapshot)


# --------------------------------------------------------- load / write / paths
class TestLoadAndWrite(TempRootCase):
    def test_the_paths_are_cross_run_and_cell_owned(self):
        self.assertEqual(artifacts.ledger_path(self.root, CELL),
                         os.path.join(self.root, "ledgers", CELL + ".json"))
        self.assertEqual(artifacts.rejection_log_path(self.root, CELL),
                         os.path.join(self.root, "rejections", CELL + ".json"))
        for path in (artifacts.ledger_path(self.root, CELL),
                     artifacts.rejection_log_path(self.root, CELL)):
            self.assertNotIn(os.sep + "runs" + os.sep, path)

    def test_a_missing_ledger_is_a_first_run_not_a_fault(self):
        self.assertIsNone(ledger.load_ledger(self.root, CELL))

    def test_a_ledger_round_trips(self):
        doc = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                  now=NOW, cell_id=CELL)
        ledger.write_ledger(self.root, CELL, doc)
        self.assertEqual(ledger.load_ledger(self.root, CELL), doc)

    def test_a_rejection_log_round_trips(self):
        doc = log([pair("https://example.com/a/")])
        path = ledger.write_rejection_log(self.root, CELL, doc)
        with open(path, "rb") as fh:
            self.assertEqual(json.loads(fh.read().decode("utf-8")), doc)

    def test_a_corrupt_ledger_raises_rather_than_resetting(self):
        path = artifacts.ledger_path(self.root, CELL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"{ this is not json")
        with self.assertRaises(ledger.LedgerError) as caught:
            ledger.load_ledger(self.root, CELL)
        self.assertIn("re-harvest", str(caught.exception))

    def test_a_schema_invalid_ledger_raises(self):
        path = artifacts.ledger_path(self.root, CELL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        artifacts.write_atomic(path, artifacts.serialize({"schema_version": 1}))
        with self.assertRaises(ledger.LedgerError):
            ledger.load_ledger(self.root, CELL)

    def test_a_ledger_from_another_cell_raises(self):
        doc = ledger.merge_ledger(None, [], now=NOW, cell_id="cases__case-studies")
        artifacts.write_atomic(artifacts.ledger_path(self.root, CELL),
                               artifacts.serialize(doc))
        with self.assertRaises(ledger.LedgerError) as caught:
            ledger.load_ledger(self.root, CELL)
        self.assertIn("cases__case-studies", str(caught.exception))

    def test_an_invalid_ledger_write_leaves_the_previous_one_intact(self):
        good = ledger.merge_ledger(None, [{"identity_url": "https://example.com/a/"}],
                                   now=NOW, cell_id=CELL)
        ledger.write_ledger(self.root, CELL, good)
        with self.assertRaises(artifacts.ArtifactError):
            ledger.write_ledger(self.root, CELL, dict(good, extra_field=1))
        self.assertEqual(ledger.load_ledger(self.root, CELL), good)

    def test_the_accumulated_ledger_survives_two_runs(self):
        ledger.write_ledger(self.root, CELL, ledger.merge_ledger(
            None, [{"identity_url": "https://example.com/a/", "outcome": "rejected",
                    "rejection_reason": "off_topic"}], now=NOW, cell_id=CELL))
        run_two = ledger.merge_ledger(
            ledger.load_ledger(self.root, CELL),
            [{"identity_url": "https://example.com/a/"},
             {"identity_url": "https://example.com/b/", "outcome": "accepted"}],
            now=LATER)
        ledger.write_ledger(self.root, CELL, run_two)
        final = ledger.load_ledger(self.root, CELL)
        by_url = {e["identity_url"]: e for e in final["entries"]}
        self.assertEqual(len(by_url), 2)
        self.assertEqual(by_url["https://example.com/a/"]["first_seen_at"], NOW)
        self.assertEqual(by_url["https://example.com/a/"]["seen_count"], 2)
        self.assertEqual(by_url["https://example.com/a/"]["outcome"], "rejected")
        self.assertEqual(by_url["https://example.com/b/"]["first_seen_at"], LATER)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_it_uses_the_shared_writer(self):
        src = inspect.getsource(ledger)
        self.assertIn("artifacts.write_document", src)

    def test_it_adds_no_locking_or_concurrency(self):
        src = inspect.getsource(ledger)
        for deferred in ("threading", "multiprocessing", "Lock", "flock", "sqlite"):
            self.assertNotIn(deferred, src)

    def test_it_does_not_decide_what_to_reject(self):
        # Reasons come from the Verdict. This module must not score or gate.
        src = inspect.getsource(ledger)
        for owned_by_verify in ("min_relevance", "accept_composite", "load_policy",
                               "thresholds_for"):
            self.assertNotIn(owned_by_verify, src)

    def test_it_does_not_reach_into_later_checkpoints(self):
        # A boundary check on THIS module's surface, not on which files happen to
        # exist yet: a future-file absence assertion only measures checkpoint
        # progress and breaks the day that checkpoint is approved.
        tokens = {n for n in dir(ledger) if not n.startswith("_")}
        for later in ("build_coverage_report", "build_run_manifest", "LATEST_RUN_ID"):
            self.assertNotIn(later, tokens)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("build_rejection_log", "load_ledger", "merge_ledger",
                     "write_ledger", "LedgerError"):
            self.assertTrue(hasattr(ledger, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
