#!/usr/bin/env python3
"""test_target_ownership.py — who fetches what, how often, within which bounds (S6-4).

The failures this suite exists to catch are the ones that cost either correctness
or politeness, and neither is visible from a green healthy-path run:

  * one canonical target fetched more than once. Two cells, or two topics, that
    surface the same URL must produce ONE request; a second would double-charge the
    budget, double the load on someone else's server, and make the owner count a
    fiction;
  * a rejected candidate being fetched. It was rejected on metadata by the
    committed gate, so the fetch can change nothing — and re-deciding afterwards is
    the re-judging Stage 6 forbids;
  * a fetch continuing after the budget is spent, where every further call
    re-charges an exhausted budget to learn the same thing;
  * a run turning publication-eligible merely because a target-fetch owner was
    acquired, while its records still say nobody checked them. That is the ordering
    defect this checkpoint surfaced, and the guard against it is asserted here;
  * ordering that depends on iteration accident rather than content, which would
    make which identity wins the fetch irreproducible.

Ownership is proved with TEST-LOCAL SYNTHETIC candidates and a real
`CandidatePool`: a shared identity is a property of what the feeds surfaced, and no
target-page fixture can create one (plan §14 E15). The committed Stage 4 dedupe
contract is not reopened — this asserts only the Stage 6 fact that one identity
buys one fetch whose outcome reaches every owner.

Offline throughout: the injected client is a stub that counts calls.
"""
import datetime
import glob
import json
import os
import tempfile
import unittest

from src.harvest import aliases as aliases_mod
from src.harvest import artifacts
from src.harvest import httpclient as hc
from src.harvest import pool as pool_mod
from src.harvest import run_cells
from src.harvest import targetfetch as targetfetch_mod
from src.harvest.budget import BudgetExhausted, RequestBudget

STAMP = "2026-07-30T12:00:00Z"


class StubClient:
    """Counts calls per URL. Cannot express a retry, a hop or a second answer."""

    def __init__(self, body=b"<html><head></head><body>x</body></html>",
                 fail_after=None):
        self.calls = []
        self.body = body
        self.fail_after = fail_after

    def get(self, url, budget=None, **kwargs):
        self.calls.append(url)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise BudgetExhausted("cell:probe", "requests", self.fail_after,
                                  len(self.calls))
        return StubResponse(url, self.body)

    @property
    def urls(self):
        return list(self.calls)


class StubResponse:
    def __init__(self, url, body, accounting=hc.ZERO_ACCOUNTING):
        self.status = 200
        self.url = url
        self.final_url = url
        self.body = body
        self.redirects = 0
        self.permanent_redirect = False
        self.content_hash = "hash-of-%s" % url
        self.content_type = "text/html; charset=utf-8"
        # S6-6A: the committed Response always carries one, so a stub standing in
        # for it must too. Zero by default — this suite counts CALLS, not attempts.
        self.accounting = accounting


class Candidate:
    """The fields `_fetch_targets` reads from an ExtractedCandidate."""

    def __init__(self, key, url, identity=None, canonical=None):
        self.candidate_key = key
        self.target_url = url
        self.identity_url = identity or url
        self.canonical_url = canonical or identity or url


class FakeVerdict:
    def __init__(self, accepted):
        self.accepted = accepted


def a_run(cell_id, candidates, accepted=True):
    """A CellRun carrying only what the fetch phase needs."""
    topic, category = cell_id.split("__", 1)
    run = run_cells.CellRun({"cell_id": cell_id, "topic_slug": topic,
                             "category_slug": category, "sources": []})
    run.extracted = tuple(candidates)
    run.verdicts = {c.candidate_key: FakeVerdict(
        accepted if not isinstance(accepted, dict)
        else accepted.get(c.candidate_key, True)) for c in candidates}
    return run


def fetch(run, client, *, pool=None, outcomes=None, budget=None, policy=None):
    return run_cells._fetch_targets(
        run,
        client=client,
        budget=budget if budget is not None else RequestBudget(),
        pool=pool if pool is not None else pool_mod.CandidatePool("probe-run"),
        outcomes=outcomes if outcomes is not None else {},
        clock=lambda: STAMP,
        canon_policy=policy if policy is not None
        else aliases_mod.load_canonicalization())


# ------------------------------------------------------------------ ownership
class TestOneFetchPerCanonicalIdentity(unittest.TestCase):

    URL = "https://tgt.harvest.test/shared"

    def test_two_owners_in_one_cell_cause_exactly_one_client_call(self):
        run = a_run("cases__case-studies",
                    [Candidate("k1", self.URL), Candidate("k2", self.URL)])
        client = StubClient()
        fetch(run, client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.urls, [self.URL])

    def test_both_owners_receive_the_very_same_outcome_object(self):
        run = a_run("cases__case-studies",
                    [Candidate("k1", self.URL), Candidate("k2", self.URL)])
        fetch(run, StubClient())
        self.assertIs(run.fetch_outcomes["k1"], run.fetch_outcomes["k2"])

    def test_owners_in_different_topics_share_one_fetch_across_cells(self):
        """The run-scoped pool and outcome map are what make this hold."""
        pool = pool_mod.CandidatePool("probe-run")
        outcomes = {}
        client = StubClient()
        first = a_run("cases__case-studies", [Candidate("k1", self.URL)])
        second = a_run("research-and-models__papers", [Candidate("k2", self.URL)])
        fetch(first, client, pool=pool, outcomes=outcomes)
        fetch(second, client, pool=pool, outcomes=outcomes)
        self.assertEqual(len(client.calls), 1)
        self.assertIs(first.fetch_outcomes["k1"], second.fetch_outcomes["k2"])

    def test_the_second_owner_gets_the_result_rather_than_nothing(self):
        pool = pool_mod.CandidatePool("probe-run")
        outcomes = {}
        client = StubClient()
        first = a_run("cases__case-studies", [Candidate("k1", self.URL)])
        second = a_run("discourse__community", [Candidate("k2", self.URL)])
        fetch(first, client, pool=pool, outcomes=outcomes)
        fetch(second, client, pool=pool, outcomes=outcomes)
        outcome = second.fetch_outcomes["k2"]
        self.assertEqual(outcome.access_status, targetfetch_mod.OK)
        self.assertEqual(outcome.verification_status, targetfetch_mod.FETCHED)

    def test_tracking_parameter_variants_are_one_identity_and_one_fetch(self):
        """Canonical identity, not raw URL string — the committed canonicalizer."""
        run = a_run("cases__case-studies", [
            Candidate("k1", self.URL),
            Candidate("k2", self.URL + "?utm_source=x")])
        client = StubClient()
        fetch(run, client)
        self.assertEqual(len(client.calls), 1)

    def test_distinct_identities_are_each_fetched_exactly_once(self):
        run = a_run("cases__case-studies", [
            Candidate("k1", "https://tgt.harvest.test/a"),
            Candidate("k2", "https://tgt.harvest.test/b"),
            Candidate("k3", "https://tgt.harvest.test/c")])
        client = StubClient()
        fetch(run, client)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(sorted(client.urls), [
            "https://tgt.harvest.test/a", "https://tgt.harvest.test/b",
            "https://tgt.harvest.test/c"])

    def test_the_pool_records_one_target_fetch_owner_per_identity(self):
        pool = pool_mod.CandidatePool("probe-run")
        run = a_run("cases__case-studies", [
            Candidate("k1", self.URL), Candidate("k2", self.URL),
            Candidate("k3", "https://tgt.harvest.test/other")])
        fetch(run, StubClient(), pool=pool)
        self.assertEqual(pool.accounting()["target_fetch_owners"], 2)

    def test_source_fetch_owners_is_untouched_by_target_fetching(self):
        """The two key spaces must stay separate, or the accounting lies."""
        pool = pool_mod.CandidatePool("probe-run")
        before = pool.accounting()["source_fetch_owners"]
        run = a_run("cases__case-studies", [Candidate("k1", self.URL)])
        fetch(run, StubClient(), pool=pool)
        self.assertEqual(pool.accounting()["source_fetch_owners"], before)


class TestRejectedCandidatesAreNeverFetched(unittest.TestCase):

    def test_a_rejected_candidate_is_not_fetched(self):
        run = a_run("cases__case-studies",
                    [Candidate("k1", "https://tgt.harvest.test/rejected")],
                    accepted=False)
        client = StubClient()
        fetch(run, client)
        self.assertEqual(client.calls, [])
        self.assertEqual(run.fetch_outcomes, {})

    def test_only_the_accepted_half_of_a_mixed_cell_is_fetched(self):
        run = a_run("cases__case-studies", [
            Candidate("keep", "https://tgt.harvest.test/keep"),
            Candidate("drop", "https://tgt.harvest.test/drop")],
            accepted={"keep": True, "drop": False})
        client = StubClient()
        fetch(run, client)
        self.assertEqual(client.urls, ["https://tgt.harvest.test/keep"])
        self.assertEqual(set(run.fetch_outcomes), {"keep"})


# --------------------------------------------------------------------- bounds
class TestBudgetAndBounds(unittest.TestCase):

    def test_budget_exhaustion_stops_further_client_calls(self):
        run = a_run("cases__case-studies", [
            Candidate("k%d" % i, "https://tgt.harvest.test/%d" % i)
            for i in range(6)])
        client = StubClient(fail_after=2)
        fetch(run, client)
        # Two succeeded, the third raised BudgetExhausted, and nothing after it
        # was attempted.
        self.assertEqual(len(client.calls), 3)

    def test_every_target_after_exhaustion_is_recorded_not_checked(self):
        run = a_run("cases__case-studies", [
            Candidate("k%d" % i, "https://tgt.harvest.test/%d" % i)
            for i in range(6)])
        fetch(run, StubClient(fail_after=2))
        statuses = [run.fetch_outcomes["k%d" % i].access_status for i in range(6)]
        self.assertEqual(statuses.count(targetfetch_mod.OK), 2)
        self.assertEqual(statuses.count(targetfetch_mod.NOT_CHECKED), 4)

    def test_a_skipped_target_says_no_request_was_made(self):
        run = a_run("cases__case-studies", [
            Candidate("k%d" % i, "https://tgt.harvest.test/%d" % i)
            for i in range(4)])
        fetch(run, StubClient(fail_after=1))
        skipped = run.fetch_outcomes["k3"]
        self.assertEqual(skipped.access_status, targetfetch_mod.NOT_CHECKED)
        self.assertEqual(skipped.verification_status, targetfetch_mod.UNVERIFIED)
        self.assertIsNone(skipped.http_status)
        self.assertIsNone(skipped.content_hash)

    def test_a_skipped_target_uses_the_committed_outcome_type(self):
        run = a_run("cases__case-studies", [
            Candidate("k%d" % i, "https://tgt.harvest.test/%d" % i)
            for i in range(3)])
        fetch(run, StubClient(fail_after=1))
        self.assertIsInstance(run.fetch_outcomes["k2"],
                              targetfetch_mod.TargetFetchOutcome)

    def test_the_per_cell_cap_is_declared_and_bounded(self):
        self.assertIsInstance(run_cells.MAX_TARGET_FETCHES_PER_CELL, int)
        self.assertGreater(run_cells.MAX_TARGET_FETCHES_PER_CELL, 0)

    def test_the_per_cell_cap_stops_fetching(self):
        cap = run_cells.MAX_TARGET_FETCHES_PER_CELL
        run = a_run("cases__case-studies", [
            Candidate("k%03d" % i, "https://tgt.harvest.test/%d" % i)
            for i in range(cap + 5)])
        client = StubClient()
        fetch(run, client)
        self.assertEqual(len(client.calls), cap)
        self.assertEqual(len(run.fetch_outcomes), cap + 5)


class TestDeterminism(unittest.TestCase):

    def test_fetch_order_is_the_committed_candidate_key_order(self):
        candidates = [Candidate("k3", "https://tgt.harvest.test/c"),
                      Candidate("k1", "https://tgt.harvest.test/a"),
                      Candidate("k2", "https://tgt.harvest.test/b")]
        client = StubClient()
        fetch(a_run("cases__case-studies", candidates), client)
        self.assertEqual(client.urls, ["https://tgt.harvest.test/a",
                                       "https://tgt.harvest.test/b",
                                       "https://tgt.harvest.test/c"])

    def test_a_shuffled_input_produces_the_same_call_order(self):
        urls = ["https://tgt.harvest.test/%s" % s for s in ("a", "b", "c")]
        first, second = StubClient(), StubClient()
        fetch(a_run("cases__case-studies",
                    [Candidate("k1", urls[0]), Candidate("k2", urls[1]),
                     Candidate("k3", urls[2])]), first)
        fetch(a_run("cases__case-studies",
                    [Candidate("k3", urls[2]), Candidate("k2", urls[1]),
                     Candidate("k1", urls[0])]), second)
        self.assertEqual(first.urls, second.urls)

    def test_adjudication_runs_per_owner_and_is_deterministic(self):
        url = "https://tgt.harvest.test/shared"
        run = a_run("cases__case-studies",
                    [Candidate("k1", url), Candidate("k2", url)])
        fetch(run, StubClient())
        self.assertEqual(set(run.adjudications), {"k1", "k2"})
        self.assertEqual(run.adjudications["k1"], run.adjudications["k2"])

    def test_adjudication_leaves_the_canonical_url_alone_without_evidence(self):
        url = "https://tgt.harvest.test/plain"
        run = a_run("cases__case-studies", [Candidate("k1", url)])
        fetch(run, StubClient())
        canonical, alias_rows, conflicts = run.adjudications["k1"]
        self.assertEqual(canonical, url)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())


# ----------------------------------------------------- the eligibility guard
class TestEligibilityRequiresRealEvidence(unittest.TestCase):
    """The ordering defect S6-4 surfaced, and the guard brought forward for it."""

    CELLS = ({"cell_id": "cases__case-studies", "status": "ok"},)

    def full(self, access_status):
        return {"record_type": "full", "access_status": access_status}

    def test_owners_alone_cannot_make_a_run_eligible(self):
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=4,
            records=[self.full("not_checked")] * 4)
        self.assertFalse(eligible)
        self.assertIn("no target evidence", reason)
        self.assertIn("4 of 4", reason)

    def test_one_unchecked_record_among_many_is_enough(self):
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=4,
            records=[self.full("ok"), self.full("ok"), self.full("ok"),
                     self.full("not_checked")])
        self.assertFalse(eligible)
        self.assertIn("1 of 4", reason)

    def test_a_budget_skipped_record_keeps_the_run_ineligible(self):
        eligible, _ = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=2,
            records=[self.full("ok"), self.full("not_checked")])
        self.assertFalse(eligible)

    def test_a_failed_fetch_still_counts_as_checked(self):
        """robots_denied and 404 are real observed statuses, not missing evidence."""
        for status in ("ok", "redirected", "not_found", "gone", "robots_denied",
                       "auth_required", "server_error", "timeout", "unreachable",
                       "paywalled"):
            with self.subTest(status):
                eligible, reason = artifacts.derive_publication_eligibility(
                    artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=1,
                    records=[self.full(status)])
                self.assertTrue(eligible, reason)

    def test_a_cross_reference_row_never_creates_a_missing_evidence_count(self):
        records = [self.full("ok"),
                   {"record_type": "cross_reference"},
                   {"record_type": "cross_reference"}]
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=1,
            records=records)
        self.assertTrue(eligible, reason)
        self.assertEqual(artifacts.unchecked_full_records(records), (0, 1))

    def test_zero_owners_still_takes_priority(self):
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST, self.CELLS, target_fetch_owners=0,
            records=[self.full("ok")])
        self.assertFalse(eligible)
        self.assertIn("no target page was fetched", reason)

    def test_a_failed_cell_still_takes_priority_over_the_new_guard(self):
        eligible, reason = artifacts.derive_publication_eligibility(
            artifacts.MODE_HARVEST,
            ({"cell_id": "cases__case-studies", "status": "adapter_error"},),
            target_fetch_owners=1, records=[self.full("not_checked")])
        self.assertFalse(eligible)
        self.assertIn("cell(s) failed", reason)

    def test_eligibility_is_still_not_a_parameter_of_the_builder(self):
        import inspect
        parameters = inspect.signature(artifacts.build_run_manifest).parameters
        self.assertNotIn("publication_eligible", parameters)
        self.assertNotIn("publication_ineligible_reason", parameters)


class TestIntegratedRunStaysHonest(unittest.TestCase):
    """The whole driver, over the committed fixture corpus, into a temp root."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s6_4_run_")
        moment = datetime.datetime(2026, 7, 30, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        cls.result = run_cells.run(cls.root, clock=lambda: moment)
        cls.manifest = json.load(open(
            glob.glob(os.path.join(cls.root, "runs", "*", "manifest.json"))[0],
            encoding="utf-8"))

    def test_target_fetch_owners_became_non_zero(self):
        self.assertGreater(
            self.manifest["request_accounting"]["target_fetch_owners"], 0)

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(leaked))


if __name__ == "__main__":
    unittest.main(verbosity=2)
