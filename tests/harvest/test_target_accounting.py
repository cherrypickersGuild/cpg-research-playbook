#!/usr/bin/env python3
"""test_target_accounting.py — exact target request accounting (S6-6A).

S6-6 reported no target attempt count at all, and said so honestly: the committed
`TargetFetchOutcome` discarded the client's accounting, and `pool.accounting()`
sums `self.sources`, which only the source path ever populates. The number was
unreachable, so nothing was reported. This checkpoint makes it reachable, and the
failures worth pinning are the ones that would make the new number a lie:

  * A RECONSTRUCTED COUNT. The only honest number is the one `HttpClient`
    incremented at the moment each event happened. A formula ("attempts = owners"),
    a `client.stats` delta, or a re-derivation from redirect hops would all produce
    a plausible number that is wrong under exactly the conditions anyone would want
    it for — concurrency, retries, an interleaved robots fetch.
  * A DOUBLE COUNT. One canonical identity is fetched once per run and its outcome
    reaches every record owning it (S6-4). Summing per record instead of per owned
    identity would report two attempts for one request, and would quietly
    contradict the ownership guarantee the number is meant to describe.
  * THE TWO KEY SPACES MERGING. `http_attempts` has always meant source attempts.
    A target attempt added to it, or a combined total offered beside it, erases the
    boundary plan §2 exists to hold — and no reader could tell afterwards.
  * OMISSION AND ZERO BECOMING THE SAME ANSWER. "This run fetched no target page"
    and "this run does not report target accounting" are different facts, and a
    defaulted empty tuple would collapse them.
  * A ZERO STANDING IN FOR AN UNKNOWN. A budget-skipped target made no request, so
    its zeros are true. An error carrying no accounting is a different case, and
    the reason it reports zeros is that nothing observed it — recorded here so the
    distinction is visible rather than assumed.

Offline throughout: stub clients for the unit cases, the committed fixture opener
into an injected temp root for the one integrated run. No socket, no live request.
"""
import ast
import datetime
import glob
import inspect
import json
import os
import random
import subprocess
import tempfile
import unittest

from src.harvest import aliases as aliases_mod
from src.harvest import artifacts
from src.harvest import httpclient as hc
from src.harvest import pool as pool_mod
from src.harvest import run_cells
from src.harvest import schema
from src.harvest import targetfetch as tf
from src.harvest.budget import BudgetExhausted, RequestBudget

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = "https://tgt.harvest.test/page"
STAMP = "2026-07-30T12:00:00Z"
RUN_ID = "20260730T120000Z-1"


def code_only(source_text):
    """Executable code with docstrings removed — the committed static-scan idiom.

    Same helper as tests/harvest/test_run_cells.py and test_adapters.py. A boundary
    check must read what a module DOES, not what it says about itself.
    """
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
    return ast.unparse(tree)


def accounting(attempts=0, retries=0, redirect_hops=0, request_charges=0):
    return hc.FetchAccounting(attempts=attempts, retries=retries,
                              redirect_hops=redirect_hops,
                              request_charges=request_charges)


class StubResponse:
    """A response carrying accounting, as the committed Response always does."""

    def __init__(self, acct, url=URL):
        self.status = 200
        self.url = url
        self.final_url = url
        self.body = b"<html><head></head><body>x</body></html>"
        self.redirects = 0
        self.permanent_redirect = False
        self.content_hash = "hash-of-%s" % url
        self.content_type = "text/html"
        self.accounting = acct


class StubClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def get(self, url, budget=None, **kwargs):
        self.calls.append(url)
        if self._error is not None:
            raise self._error
        return self._response


def fetch(client, url=URL):
    return tf.fetch_target(url, client=client, clock=lambda: STAMP)


def outcome(acct):
    """A bare outcome carrying only the accounting under test."""
    return tf.TargetFetchOutcome(
        requested_url=URL, access_status=tf.OK, verification_status=tf.FETCHED,
        verification_evidence="probe", last_checked_at=STAMP, accounting=acct)


# ------------------------------------------------- the outcome carries the count
class TestTheOutcomeCarriesWhatTheClientFroze(unittest.TestCase):

    def test_a_success_copies_the_response_accounting_object(self):
        acct = accounting(attempts=3, retries=1, redirect_hops=1, request_charges=3)
        result = fetch(StubClient(StubResponse(acct)))
        # The very same immutable object: copied, not rebuilt from its parts.
        self.assertIs(result.accounting, acct)

    def test_a_typed_failure_copies_the_error_accounting(self):
        error = hc.ServerError("boom", url=URL, status=500)
        error.accounting = accounting(attempts=3, retries=2, request_charges=3)
        result = fetch(StubClient(error=error))
        self.assertIs(result.accounting, error.accounting)
        self.assertEqual(result.accounting.attempts, 3)
        self.assertEqual(result.accounting.retries, 2)

    def test_a_failed_fetch_is_accounted_exactly_like_a_successful_one(self):
        """A 404 that cost three attempts cost three attempts."""
        error = hc.ClientError("gone", url=URL, status=404)
        error.accounting = accounting(attempts=3, retries=2, request_charges=3)
        self.assertEqual(fetch(StubClient(error=error)).accounting.attempts, 3)

    def test_the_default_is_zero_not_none(self):
        """Every outcome answers the question; none of them answers with None."""
        built = tf.TargetFetchOutcome(
            requested_url=URL, access_status=tf.NOT_CHECKED,
            verification_status=tf.UNVERIFIED, verification_evidence="",
            last_checked_at=STAMP)
        self.assertEqual(built.accounting, hc.ZERO_ACCOUNTING)

    def test_an_error_with_no_accounting_reports_zeros(self):
        """`BudgetExhausted` has no class-level default, unlike `HttpError`.

        The committed client attaches accounting to both, so this is unreachable in
        production — but the `getattr` idiom is what keeps an unexpected object from
        crashing a whole cell, and zeros are then the honest answer: nothing
        observed the attempt, so nothing is claimed about it.
        """
        error = BudgetExhausted("cell:x", "requests", 60, 61)
        self.assertFalse(hasattr(error, "accounting"))
        self.assertEqual(fetch(StubClient(error=error)).accounting,
                         hc.ZERO_ACCOUNTING)

    def test_an_unexpected_exception_reports_zeros_rather_than_crashing(self):
        result = fetch(StubClient(error=ValueError("not an http error")))
        self.assertEqual(result.accounting, hc.ZERO_ACCOUNTING)
        self.assertEqual(result.error_class, "ValueError")

    def test_the_accounting_is_the_committed_frozen_type(self):
        result = fetch(StubClient(StubResponse(accounting(attempts=1))))
        self.assertIsInstance(result.accounting, hc.FetchAccounting)
        with self.assertRaises(Exception):
            result.accounting.attempts = 99

    def test_the_outcome_is_still_frozen_and_still_compares_by_value(self):
        acct = accounting(attempts=1, request_charges=1)
        first = fetch(StubClient(StubResponse(acct)))
        second = fetch(StubClient(StubResponse(acct)))
        self.assertEqual(first, second)
        with self.assertRaises(Exception):
            first.accounting = hc.ZERO_ACCOUNTING

    def test_two_fetches_costing_differently_are_not_equal(self):
        """Anti-vacuity: the field must actually participate."""
        cheap = fetch(StubClient(StubResponse(accounting(attempts=1))))
        dear = fetch(StubClient(StubResponse(accounting(attempts=4))))
        self.assertNotEqual(cheap, dear)

    def test_nothing_is_recomputed_from_the_shared_client_stats(self):
        """DV-8 exists to forbid diffing a client-lifetime aggregate.

        Scanned with docstrings stripped, the committed static-scan idiom: both
        modules now DOCUMENT why they do not touch `client.stats`, and a raw
        substring scan would be permanently red on the very sentence recording the
        guarantee.
        """
        for module in (tf, artifacts):
            source = code_only(inspect.getsource(module))
            with self.subTest(module.__name__):
                self.assertNotIn("stats", source)


# ----------------------------------------------------------- the budget skip
class TestABudgetSkipCostsNothingAndSaysSo(unittest.TestCase):

    def test_a_skipped_target_carries_genuine_zeros(self):
        skipped = run_cells._budget_skipped_outcome(URL, STAMP)
        self.assertEqual(skipped.accounting, hc.ZERO_ACCOUNTING)
        self.assertEqual(skipped.access_status, tf.NOT_CHECKED)

    def test_the_zeros_are_true_because_no_request_was_made(self):
        """Proved through the driver, not asserted about it: once the budget is
        spent the remaining targets are recorded without a client call at all."""
        candidates = [_Candidate("k%d" % i, "https://tgt.harvest.test/%d" % i)
                      for i in range(4)]
        run = _a_run(candidates)
        client = _CountingClient(fail_after=1)
        run_cells._fetch_targets(
            run, client=client, budget=RequestBudget(),
            pool=pool_mod.CandidatePool("probe-run"), outcomes={},
            clock=lambda: STAMP,
            canon_policy=aliases_mod.load_canonicalization())
        # One successful call, one that raised BudgetExhausted, and then nothing.
        self.assertEqual(len(client.calls), 2)
        skipped = [o for o in run.fetch_outcomes.values()
                   if o.access_status == tf.NOT_CHECKED]
        self.assertEqual(len(skipped), 3)
        for one in skipped:
            self.assertEqual(one.accounting, hc.ZERO_ACCOUNTING)


class _Candidate:
    def __init__(self, key, url):
        self.candidate_key = key
        self.target_url = url
        self.identity_url = url
        self.canonical_url = url


class _Verdict:
    accepted = True


class _CountingClient:
    def __init__(self, fail_after=None):
        self.calls = []
        self.fail_after = fail_after

    def get(self, url, budget=None, **kwargs):
        self.calls.append(url)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise BudgetExhausted("cell:probe", "requests", self.fail_after,
                                  len(self.calls))
        return StubResponse(accounting(attempts=1, request_charges=1), url=url)


def _a_run(candidates, cell_id="cases__case-studies"):
    topic, category = cell_id.split("__", 1)
    run = run_cells.CellRun({"cell_id": cell_id, "topic_slug": topic,
                             "category_slug": category, "sources": []})
    run.extracted = tuple(candidates)
    run.verdicts = {c.candidate_key: _Verdict() for c in candidates}
    return run


# ------------------------------------------------------------- the aggregation
class TestTheAggregation(unittest.TestCase):

    def test_it_sums_the_three_counters(self):
        totals = artifacts.target_request_accounting([
            outcome(accounting(attempts=3, retries=2, redirect_hops=0)),
            outcome(accounting(attempts=2, retries=0, redirect_hops=1)),
        ])
        self.assertEqual(totals, {"target_http_attempts": 5, "target_retries": 2,
                                  "target_redirect_hops": 1})

    def test_exactly_three_keys_are_produced(self):
        self.assertEqual(set(artifacts.target_request_accounting([])),
                         {"target_http_attempts", "target_retries",
                          "target_redirect_hops"})

    def test_an_empty_run_totals_zero_rather_than_producing_nothing(self):
        self.assertEqual(artifacts.target_request_accounting([]),
                         {"target_http_attempts": 0, "target_retries": 0,
                          "target_redirect_hops": 0})

    def test_request_charges_is_not_projected(self):
        """Available on every outcome; deliberately not reported here, because the
        block carries no `budget_charged` counterpart on the source side either."""
        totals = artifacts.target_request_accounting(
            [outcome(accounting(attempts=1, request_charges=1))])
        self.assertNotIn("target_budget_charged", totals)
        self.assertNotIn("target_request_charges", totals)

    def test_no_combined_total_is_produced(self):
        totals = artifacts.target_request_accounting(
            [outcome(accounting(attempts=1))])
        for combined in ("total_http_attempts", "http_attempts", "attempts"):
            with self.subTest(combined):
                self.assertNotIn(combined, totals)

    def test_the_sum_is_order_independent(self):
        rows = [outcome(accounting(attempts=i, retries=i % 2, redirect_hops=i % 3))
                for i in range(1, 9)]
        first = artifacts.target_request_accounting(rows)
        for seed in range(5):
            shuffled = list(rows)
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(artifacts.target_request_accounting(shuffled), first)

    def test_an_outcome_without_accounting_is_skipped_not_crashed_on(self):
        class Bare:
            accounting = None
        self.assertEqual(
            artifacts.target_request_accounting(
                [Bare(), outcome(accounting(attempts=2))])["target_http_attempts"],
            2)


# --------------------------------------------- one identity, counted exactly once
class TestOneIdentityIsCountedOnce(unittest.TestCase):
    """The whole reason the run-scoped MAP is the input, not the record set."""

    URL = "https://tgt.harvest.test/shared"

    def drive(self, cells):
        pool = pool_mod.CandidatePool("probe-run")
        outcomes = {}
        client = _CountingClient()
        runs = []
        for cell_id, candidates in cells:
            run = _a_run(candidates, cell_id=cell_id)
            run_cells._fetch_targets(
                run, client=client, budget=RequestBudget(), pool=pool,
                outcomes=outcomes, clock=lambda: STAMP,
                canon_policy=aliases_mod.load_canonicalization())
            runs.append(run)
        return pool, outcomes, runs, client

    def test_two_owners_in_one_cell_contribute_one_attempt(self):
        pool, outcomes, runs, client = self.drive([
            ("cases__case-studies", [_Candidate("k1", self.URL),
                                     _Candidate("k2", self.URL)])])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(pool.accounting()["target_fetch_owners"], 1)
        # Two records own it; the MAP has one entry, and so the count is 1.
        self.assertEqual(len(runs[0].fetch_outcomes), 2)
        totals = artifacts.target_request_accounting(
            [outcomes[key] for key in sorted(outcomes)])
        self.assertEqual(totals["target_http_attempts"], 1)

    def test_summing_per_record_would_double_count_it(self):
        """Anti-vacuity: the test above must be measuring something."""
        _pool, _outcomes, runs, _client = self.drive([
            ("cases__case-studies", [_Candidate("k1", self.URL),
                                     _Candidate("k2", self.URL)])])
        per_record = artifacts.target_request_accounting(
            list(runs[0].fetch_outcomes.values()))
        self.assertEqual(per_record["target_http_attempts"], 2)

    def test_one_identity_across_two_topics_still_counts_once(self):
        pool, outcomes, _runs, client = self.drive([
            ("cases__case-studies", [_Candidate("k1", self.URL)]),
            ("discourse__market-and-investment", [_Candidate("k2", self.URL)])])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(pool.accounting()["target_fetch_owners"], 1)
        self.assertEqual(
            artifacts.target_request_accounting(list(outcomes.values()))
            ["target_http_attempts"], 1)

    def test_distinct_identities_each_contribute_their_own_attempts(self):
        _pool, outcomes, _runs, client = self.drive([
            ("cases__case-studies", [_Candidate("k1", "https://tgt.harvest.test/a"),
                                     _Candidate("k2", "https://tgt.harvest.test/b")])])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            artifacts.target_request_accounting(list(outcomes.values()))
            ["target_http_attempts"], 2)


# ------------------------------------------------------------- the manifest API
def manifest(**kw):
    kw.setdefault("harvest_run_id", RUN_ID)
    kw.setdefault("started_at", STAMP)
    kw.setdefault("finished_at", STAMP)
    return artifacts.build_run_manifest(**kw)


SOURCE_ACCOUNTING = {"source_fetch_owners": 25, "target_fetch_owners": 4,
                     "extraction_owners": 0, "http_attempts": 25, "retries": 0,
                     "redirect_hops": 0, "conditional_revalidations": 0}


class TestTheManifestApi(unittest.TestCase):

    def test_omitting_the_argument_omits_the_three_keys(self):
        """Every committed pre-S6-6A caller stays byte-identical."""
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING))
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops"):
            with self.subTest(key):
                self.assertNotIn(key, doc["request_accounting"])

    def test_omitting_both_still_omits_the_block_entirely(self):
        self.assertNotIn("request_accounting", manifest())

    def test_an_explicitly_empty_iterable_reports_three_zeros(self):
        """Supplied-but-empty is a fact about the run, not an absence of one."""
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                       target_outcomes=[])
        block = doc["request_accounting"]
        self.assertEqual(block["target_http_attempts"], 0)
        self.assertEqual(block["target_retries"], 0)
        self.assertEqual(block["target_redirect_hops"], 0)

    def test_an_empty_iterable_and_an_omission_are_different_documents(self):
        self.assertNotEqual(manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                                     target_outcomes=[]),
                            manifest(request_accounting=dict(SOURCE_ACCOUNTING)))

    def test_the_values_are_the_sum_of_the_outcomes(self):
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                       target_outcomes=[outcome(accounting(attempts=2, retries=1)),
                                        outcome(accounting(attempts=3,
                                                           redirect_hops=2))])
        block = doc["request_accounting"]
        self.assertEqual(block["target_http_attempts"], 5)
        self.assertEqual(block["target_retries"], 1)
        self.assertEqual(block["target_redirect_hops"], 2)

    def test_the_block_appears_even_with_no_source_accounting(self):
        doc = manifest(target_outcomes=[outcome(accounting(attempts=1))])
        self.assertEqual(doc["request_accounting"]["target_http_attempts"], 1)
        self.assertNotIn("http_attempts", doc["request_accounting"])

    def test_the_source_counters_are_left_exactly_as_supplied(self):
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                       target_outcomes=[outcome(accounting(attempts=9, retries=4,
                                                           redirect_hops=3))])
        block = doc["request_accounting"]
        for key, value in SOURCE_ACCOUNTING.items():
            with self.subTest(key):
                self.assertEqual(block[key], value)

    def test_the_derived_value_overrides_a_caller_supplied_one(self):
        """The count is derived from the outcomes, never asserted beside them."""
        supplied = dict(SOURCE_ACCOUNTING, target_http_attempts=999)
        doc = manifest(request_accounting=supplied,
                       target_outcomes=[outcome(accounting(attempts=2))])
        self.assertEqual(doc["request_accounting"]["target_http_attempts"], 2)

    def test_the_callers_dict_is_never_mutated(self):
        supplied = dict(SOURCE_ACCOUNTING)
        manifest(request_accounting=supplied,
                 target_outcomes=[outcome(accounting(attempts=2))])
        self.assertEqual(supplied, SOURCE_ACCOUNTING)

    def test_a_reported_manifest_validates(self):
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                       target_outcomes=[outcome(accounting(attempts=4, retries=1,
                                                           redirect_hops=1))])
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_the_schema_refuses_a_combined_total(self):
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING,
                                               total_http_attempts=29))
        self.assertNotEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_the_schema_refuses_a_negative_target_count(self):
        doc = manifest(request_accounting=dict(SOURCE_ACCOUNTING,
                                               target_http_attempts=-1))
        self.assertNotEqual(schema.validate(doc, "run_manifest.v1.json"), [])

    def test_eligibility_is_untouched_by_any_of_this(self):
        """Accounting reports; it does not decide. Nothing here may move §8."""
        with_counts = manifest(request_accounting=dict(SOURCE_ACCOUNTING),
                               target_outcomes=[outcome(accounting(attempts=4))])
        without = manifest(request_accounting=dict(SOURCE_ACCOUNTING))
        self.assertEqual(with_counts["publication_eligible"],
                         without["publication_eligible"])
        self.assertEqual(with_counts["publication_ineligible_reason"],
                         without["publication_ineligible_reason"])


# ---------------------------------------------------------------- the whole run
class TestTheIntegratedRun(unittest.TestCase):
    """The committed corpus, through the committed driver, into a temp root."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s6_6a_run_")
        moment = datetime.datetime(2026, 7, 30, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        cls.result = run_cells.run(cls.root, clock=lambda: moment)
        with open(glob.glob(os.path.join(cls.root, "runs", "*",
                                         "manifest.json"))[0],
                  encoding="utf-8") as handle:
            cls.manifest = json.load(handle)
        cls.accounting = cls.manifest["request_accounting"]

    def test_the_three_keys_are_reported(self):
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops"):
            with self.subTest(key):
                self.assertIn(key, self.accounting)

    def test_something_was_actually_counted(self):
        self.assertGreater(self.accounting["target_http_attempts"], 0)

    def test_the_run_checked_every_record_so_no_target_was_skipped(self):
        """The premise the identity below depends on, asserted rather than assumed:
        a budget-skipped target is an owner that made no request."""
        self.assertTrue(self.manifest["publication_eligible"])

    def test_attempts_equals_owners_plus_retries_plus_hops(self):
        """The DV-8 identity, over a run where every owned identity was fetched:
        one attempt to begin with, one more per retry, one more per followed
        redirect. It ties the reported number to the ownership count without
        deriving either from the other."""
        self.assertEqual(
            self.accounting["target_http_attempts"],
            self.accounting["target_fetch_owners"]
            + self.accounting["target_retries"]
            + self.accounting["target_redirect_hops"])

    def test_the_source_counters_did_not_move(self):
        """25 sources, 25 source attempts — exactly as before S6-6A."""
        self.assertEqual(self.accounting["source_fetch_owners"], 25)
        self.assertEqual(self.accounting["http_attempts"], 25)
        self.assertEqual(self.accounting["retries"], 0)
        self.assertEqual(self.accounting["redirect_hops"], 0)

    def test_the_source_attempts_do_not_include_the_target_attempts(self):
        """The one number this checkpoint could most easily have corrupted."""
        self.assertNotEqual(
            self.accounting["http_attempts"],
            25 + self.accounting["target_http_attempts"])

    def test_no_combined_total_reached_the_manifest(self):
        for combined in ("total_http_attempts", "total_attempts"):
            with self.subTest(combined):
                self.assertNotIn(combined, self.accounting)

    def test_the_manifest_validates(self):
        self.assertEqual(schema.validate(self.manifest, "run_manifest.v1.json"), [])

    def test_the_count_is_reproducible(self):
        """A second run over the same corpus with a pinned clock costs the same."""
        root = tempfile.mkdtemp(prefix="s6_6a_run2_")
        self.addCleanup(_rmtree, root)
        moment = datetime.datetime(2026, 7, 30, 12, 0, 0,
                                   tzinfo=datetime.timezone.utc)
        run_cells.run(root, clock=lambda: moment)
        with open(glob.glob(os.path.join(root, "runs", "*", "manifest.json"))[0],
                  encoding="utf-8") as handle:
            second = json.load(handle)
        self.assertEqual(second["request_accounting"], self.accounting)

    @classmethod
    def tearDownClass(cls):
        _rmtree(cls.root)


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):

    def test_the_pool_and_the_client_are_byte_unchanged(self):
        """The audit's central finding, asserted rather than remembered: every fact
        needed was already frozen onto the objects `targetfetch` holds, so neither
        the pool nor the client had to learn anything new. `pool.py` stays inside
        the Stage 4 byte-freeze and no guard was retired for it."""
        for path in ("src/harvest/pool.py", "src/harvest/httpclient.py"):
            with self.subTest(path):
                rc = subprocess.call(["git", "diff", "--exit-code", "--quiet",
                                      "HEAD", "--", path], cwd=ROOT)
                self.assertEqual(rc, 0, path)

    def test_the_pool_still_reports_source_attempts_only(self):
        """`pool.accounting()` gained nothing: it sums source snapshots, and a
        target fetch adds none. The under-reporting S6-4 observed is not fixed
        here — it is reported apart, which is the point."""
        pool = pool_mod.CandidatePool("probe-run")
        pool.add_candidate(URL, "cell__probe")
        key = next(iter(pool.candidates))
        pool.acquire_target_fetch(key, "cell__probe")
        totals = pool.accounting()
        self.assertEqual(totals["target_fetch_owners"], 1)
        self.assertEqual(totals["http_attempts"], 0)
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops"):
            with self.subTest(key):
                self.assertNotIn(key, totals)

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(os.path.join(ROOT, leaked)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
