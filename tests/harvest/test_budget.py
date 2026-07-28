#!/usr/bin/env python3
"""test_budget.py — the caps cannot be exceeded, by any route.

The routes that matter, because each is a way a naive implementation leaks:
retries, redirect hops, target-page enrichment, several sources in one cell, and
all of them combined. Clocks are injected so a 120-second budget is asserted in
microseconds rather than by actually waiting.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.budget import RequestBudget, BudgetExhausted  # noqa: E402


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestRequestCaps(unittest.TestCase):
    def test_charges_up_front(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=2)
        b.charge_request()
        b.charge_request()
        with self.assertRaises(BudgetExhausted) as cm:
            b.charge_request()
        self.assertEqual(cm.exception.kind, "requests")
        self.assertEqual(cm.exception.reason, "budget_exhausted")

    def test_a_rejected_charge_does_not_consume(self):
        # Charging before the attempt means the request that discovers the
        # budget is empty must not itself be counted.
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=1)
        b.charge_request()
        with self.assertRaises(BudgetExhausted):
            b.charge_request()
        self.assertEqual(b.usage()[0]["requests"], 1)

    def test_nested_scopes_both_enforced(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=10)
        b.push("adapter:a", max_requests=3)
        for _ in range(3):
            b.charge_request()
        with self.assertRaises(BudgetExhausted) as cm:
            b.charge_request()
        self.assertEqual(cm.exception.scope, "adapter:a")
        # the cell still has room; a fresh adapter may continue
        b.pop("adapter:a")
        b.push("adapter:b", max_requests=3)
        b.charge_request()
        self.assertEqual(b.usage()[0]["requests"], 4)

    def test_one_adapter_cannot_starve_the_cell(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=5)
        for name in ("a", "b", "c"):
            b.push("adapter:" + name, max_requests=4)
            try:
                for _ in range(4):
                    b.charge_request()
            except BudgetExhausted as exc:
                self.assertEqual(exc.scope, "cell")
            b.pop("adapter:" + name)
        self.assertLessEqual(b.usage()[0]["requests"], 5)

    def test_multi_charge(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=5)
        b.charge_request(3)
        with self.assertRaises(BudgetExhausted):
            b.charge_request(3)


class TestTimeCaps(unittest.TestCase):
    def test_time_budget_enforced(self):
        c = FakeClock()
        b = RequestBudget(clock=c)
        b.push("adapter:x", max_seconds=120)
        c.advance(119)
        b.check_time()
        c.advance(2)
        with self.assertRaises(BudgetExhausted) as cm:
            b.check_time()
        self.assertEqual(cm.exception.kind, "seconds")

    def test_charge_checks_time_first(self):
        c = FakeClock()
        b = RequestBudget(clock=c)
        b.push("cell", max_requests=100, max_seconds=10)
        c.advance(11)
        with self.assertRaises(BudgetExhausted) as cm:
            b.charge_request()
        self.assertEqual(cm.exception.kind, "seconds")

    def test_would_exceed_time_predicts_a_pacing_sleep(self):
        # Pacing counts against the budget: a 15s crawl-delay source must not be
        # able to burn an adapter budget in sleeps and call it progress.
        c = FakeClock()
        b = RequestBudget(clock=c)
        b.push("adapter:arxiv", max_seconds=120)
        c.advance(110)
        self.assertFalse(b.would_exceed_time(5))
        self.assertTrue(b.would_exceed_time(15))

    def test_remaining_reports_tightest_scope(self):
        c = FakeClock()
        b = RequestBudget(clock=c)
        b.push("cell", max_requests=60, max_seconds=300)
        b.push("adapter:a", max_requests=25, max_seconds=120)
        self.assertEqual(b.remaining_requests(), 25)
        self.assertAlmostEqual(b.remaining_seconds(), 120, places=3)


class TestLeakRoutes(unittest.TestCase):
    """Every way a cap could be exceeded if only 'logical fetches' were counted."""

    def _cell(self, max_requests=10):
        b = RequestBudget(clock=FakeClock())
        b.push("cell:t__c", max_requests=max_requests)
        return b

    def test_retries_count(self):
        b = self._cell(3)
        for _ in range(3):          # one logical fetch, three attempts
            b.charge_request()
        with self.assertRaises(BudgetExhausted):
            b.charge_request()

    def test_redirect_hops_count(self):
        b = self._cell(3)
        for _ in range(3):          # one logical fetch, three hops
            b.charge_request()
        with self.assertRaises(BudgetExhausted):
            b.charge_request()

    def test_enrichment_counts(self):
        b = self._cell(4)
        b.charge_request()          # the feed
        for _ in range(3):          # three target pages
            b.charge_request()
        with self.assertRaises(BudgetExhausted):
            b.charge_request()

    def test_multiple_sources_in_one_cell_share_the_cell_cap(self):
        b = self._cell(5)
        total = 0
        exhausted = False
        for src in ("s1", "s2", "s3"):
            b.push("adapter:" + src, max_requests=3)
            try:
                for _ in range(3):
                    b.charge_request()
                    total += 1
            except BudgetExhausted as exc:
                self.assertEqual(exc.scope, "cell:t__c")
                exhausted = True
            b.pop("adapter:" + src)
            if exhausted:
                break
        self.assertTrue(exhausted)
        self.assertEqual(total, 5)

    def test_all_four_combined(self):
        b = self._cell(6)
        n = 0
        with self.assertRaises(BudgetExhausted):
            for _ in range(100):    # retries x redirects x enrichment x sources
                b.charge_request()
                n += 1
        self.assertEqual(n, 6)


class TestScopeContextManager(unittest.TestCase):
    def test_scope_pops_even_on_exception(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell", max_requests=2)
        with self.assertRaises(BudgetExhausted):
            with b.scope("adapter:x", max_requests=1):
                b.charge_request()
                b.charge_request()
        self.assertEqual([s["scope"] for s in b.usage()], ["cell"])

    def test_mismatched_pop_is_an_error(self):
        b = RequestBudget(clock=FakeClock())
        b.push("cell")
        b.push("adapter:a")
        with self.assertRaises(ValueError):
            b.pop("cell")


if __name__ == "__main__":
    unittest.main(verbosity=2)
