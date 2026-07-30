#!/usr/bin/env python3
"""test_target_fetch.py — one target fetch, and the whole error mapping (S6-2).

The contracts worth pinning here are the ones whose violation would put a FALSE
CLAIM on a record, or would quietly move transport semantics out of the module
that is actually tested on them:

  * a failure mapped to the wrong access_status — "not_found" on a page that was
    merely rate-limited is a false statement about a URL, and nothing downstream
    could detect it;
  * an unmapped HttpError subclass silently receiving the nearest plausible
    status. The mapping is enumerated from the committed hierarchy through the
    AST, so a tenth subclass added later fails HERE rather than on a live run;
  * a second retry, redirect, timeout or size-cap opinion growing in this module,
    which would then disagree with HttpClient's;
  * more than one logical client call, which would make budget accounting and
    ownership counts wrong;
  * a system-clock read, which would make last_checked_at nondeterministic and
    break every artifact hash that contains it;
  * a traceback, repr or address reaching a persisted field;
  * an interruption being swallowed by a broad except.

The injected client here is a STUB. That is deliberate and is the plan's §5.0
boundary: raising a typed error from a stub is the whole of Stage 6's failure
surface, and routing it through fixtures would prove HttpClient's behaviour
instead of this module's. Retry sequencing, robots decisions, redirect following,
timeout mechanics, size mechanics and socket behaviour are HttpClient's and are
covered by tests/test_taxonomy_http.sh; none is re-asserted here.
"""
import ast
import dataclasses
import inspect
import os
import unittest

from src.harvest import httpclient as hc
from src.harvest import targetfetch as tf
from src.harvest.budget import BudgetExhausted

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTTPCLIENT_PATH = os.path.join(ROOT, "src", "harvest", "httpclient.py")

STAMP = "2026-07-30T12:00:00Z"
URL = "https://tgt.harvest.test/ok-plain"
BODY = b"<!doctype html>\n<html><body><p>page</p></body></html>\n"


def clock(stamp=STAMP):
    return lambda: stamp


class StubClient:
    """The injected client. Records its calls; answers with one canned result.

    Note what it CANNOT express: an attempt count, a retry, a partial body or a
    second answer for the same URL. fetch_target must not need any of them.
    """

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def get(self, url, budget=None, **kwargs):
        self.calls.append((url, budget, kwargs))
        if self._error is not None:
            raise self._error
        return self._response


class StubResponse:
    """Only the fields fetch_target is allowed to read.

    `accounting` joined the read set at S6-6A. It is listed here rather than
    defaulted away deliberately: this class IS the declaration of what the module
    may look at, so a field appearing here is the visible cost of a new read.
    """

    def __init__(self, status=200, final_url=URL, body=BODY, redirects=0,
                 permanent_redirect=False, content_hash="hash", content_type="text/html",
                 accounting=hc.ZERO_ACCOUNTING):
        self.status = status
        self.final_url = final_url
        self.body = body
        self.redirects = redirects
        self.permanent_redirect = permanent_redirect
        self.content_hash = content_hash
        self.content_type = content_type
        self.accounting = accounting


def fetch(client, *, url=URL, budget=None, stamp=STAMP):
    return tf.fetch_target(url, client=client, budget=budget, clock=clock(stamp))


# ------------------------------------------------------------------- success
class TestSuccessfulFetch(unittest.TestCase):

    def test_a_plain_200_becomes_ok_and_fetched(self):
        outcome = fetch(StubClient(StubResponse()))
        self.assertEqual(outcome.access_status, tf.OK)
        self.assertEqual(outcome.verification_status, tf.FETCHED)

    def test_it_never_claims_verified(self):
        """The schema's own note: 'fetched' is not an editorial judgement."""
        outcome = fetch(StubClient(StubResponse()))
        self.assertNotEqual(outcome.verification_status, "verified")

    def test_it_carries_the_observed_status_and_final_url(self):
        outcome = fetch(StubClient(StubResponse(status=200, final_url=URL)))
        self.assertEqual(outcome.http_status, 200)
        self.assertEqual(outcome.final_url, URL)

    def test_it_carries_the_clients_content_hash_unchanged(self):
        outcome = fetch(StubClient(StubResponse(content_hash="abc123")))
        self.assertEqual(outcome.content_hash, "abc123")

    def test_it_does_not_recompute_the_content_hash(self):
        """Response already hashed the exact bytes with the committed function."""
        outcome = fetch(StubClient(StubResponse(body=b"xyz", content_hash="sentinel")))
        self.assertEqual(outcome.content_hash, "sentinel")

    def test_it_carries_the_body_and_content_type_outward_unparsed(self):
        outcome = fetch(StubClient(StubResponse(body=BODY, content_type="text/html")))
        self.assertEqual(outcome.body, BODY)
        self.assertEqual(outcome.content_type, "text/html")

    def test_a_permanent_redirect_chain_becomes_redirected(self):
        outcome = fetch(StubClient(StubResponse(
            redirects=2, permanent_redirect=True,
            final_url="https://tgt.harvest.test/redirect-permanent-c")))
        self.assertEqual(outcome.access_status, tf.REDIRECTED)
        self.assertTrue(outcome.permanent_redirect)

    def test_a_chain_containing_a_temporary_hop_stays_ok(self):
        outcome = fetch(StubClient(StubResponse(
            redirects=2, permanent_redirect=False,
            final_url="https://tgt.harvest.test/redirect-temporary-c")))
        self.assertEqual(outcome.access_status, tf.OK)
        self.assertFalse(outcome.permanent_redirect)

    def test_permanence_is_the_clients_classification_not_this_modules(self):
        """redirects>0 alone must not make it permanent."""
        outcome = fetch(StubClient(StubResponse(redirects=3, permanent_redirect=False)))
        self.assertEqual(outcome.access_status, tf.OK)

    def test_the_succeeded_predicate_agrees_with_the_status(self):
        self.assertTrue(fetch(StubClient(StubResponse())).succeeded)
        self.assertTrue(fetch(StubClient(StubResponse(
            redirects=1, permanent_redirect=True))).succeeded)
        self.assertFalse(fetch(StubClient(error=hc.ClientError("x", status=404))).succeeded)

    def test_the_evidence_names_the_status_and_byte_length(self):
        outcome = fetch(StubClient(StubResponse(body=b"1234567890")))
        self.assertIn("http 200", outcome.verification_evidence)
        self.assertIn("10 bytes", outcome.verification_evidence)

    def test_an_empty_but_present_body_reports_zero_bytes(self):
        outcome = fetch(StubClient(StubResponse(body=b"")))
        self.assertIn("0 bytes", outcome.verification_evidence)

    def test_a_none_body_does_not_crash_the_evidence(self):
        outcome = fetch(StubClient(StubResponse(body=None)))
        self.assertIn("0 bytes", outcome.verification_evidence)
        self.assertIsNone(outcome.body)

    def test_no_error_class_is_recorded_on_success(self):
        self.assertIsNone(fetch(StubClient(StubResponse())).error_class)


# ------------------------------------------------------- the mapping, exhaustively
def concrete_http_error_classes():
    """Every concrete class in the committed HttpError hierarchy, from the AST.

    Reads only class names and their declared bases — no line numbers, no
    declaration order, no import spelling. Each name is then resolved to the ACTUAL
    class on the module and exercised, so this proves a mapping for the real
    hierarchy rather than for a parsed shadow of it.
    """
    with open(HTTPCLIENT_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    bases = {node.name: [b.id for b in node.bases if isinstance(b, ast.Name)]
             for node in tree.body if isinstance(node, ast.ClassDef)}

    def descends(name, seen=()):
        if name == "HttpError":
            return True
        return any(descends(base, seen + (name,))
                   for base in bases.get(name, []) if base not in seen)

    found = []
    for name in bases:
        if not descends(name):
            continue
        klass = getattr(hc, name, None)
        if inspect.isclass(klass) and issubclass(klass, hc.HttpError):
            found.append(klass)
    return sorted(found, key=lambda k: k.__name__)


# The mapping this suite expects, written out rather than derived from the module
# under test: deriving it would make the test agree with any implementation.
EXPECTED = {
    "HttpError": tf.UNREACHABLE,
    "RobotsDenied": tf.ROBOTS_DENIED,
    "HttpTimeout": tf.TIMEOUT,
    "DnsFailure": tf.UNREACHABLE,
    "ServerError": tf.SERVER_ERROR,
    "LeaseUnavailable": tf.UNREACHABLE,
    "ResponseTooLarge": tf.UNREACHABLE,
    "UnexpectedContentType": tf.UNREACHABLE,
    "EmptyResponse": tf.UNREACHABLE,
    "ClientError": tf.UNREACHABLE,      # with no status; per-status cases below
}

COMMITTED_ACCESS_STATUSES = frozenset({
    tf.NOT_CHECKED, tf.OK, tf.REDIRECTED, tf.NOT_FOUND, tf.GONE, tf.AUTH_REQUIRED,
    tf.PAYWALLED, tf.SERVER_ERROR, tf.TIMEOUT, tf.ROBOTS_DENIED, tf.UNREACHABLE,
})


class TestEveryCommittedErrorClassIsMapped(unittest.TestCase):

    def setUp(self):
        self.classes = concrete_http_error_classes()

    def test_the_hierarchy_is_discovered_at_all(self):
        """A discovery bug that found nothing would make this class vacuous."""
        self.assertGreaterEqual(len(self.classes), 10)
        self.assertIn(hc.HttpError, self.classes)
        self.assertIn(hc.ClientError, self.classes)

    def test_every_discovered_class_has_exactly_one_mapping(self):
        for klass in self.classes:
            with self.subTest(klass.__name__):
                status = tf.access_status_for(klass("probe"))
                self.assertIn(status, COMMITTED_ACCESS_STATUSES)
                self.assertEqual(status, EXPECTED[klass.__name__])

    def test_the_expectation_covers_the_hierarchy_with_nothing_left_over(self):
        self.assertEqual({k.__name__ for k in self.classes}, set(EXPECTED))

    def test_every_discovered_class_actually_produces_an_outcome(self):
        """Instantiate and exercise the real class, not just look it up."""
        for klass in self.classes:
            with self.subTest(klass.__name__):
                outcome = fetch(StubClient(error=klass("probe")))
                self.assertEqual(outcome.access_status, EXPECTED[klass.__name__])
                self.assertEqual(outcome.error_class, klass.__name__)
                self.assertEqual(outcome.verification_status, tf.UNVERIFIED)

    def test_a_subclass_nobody_mapped_fails_loudly(self):
        class FutureHttpError(hc.HttpError):
            pass

        with self.assertRaises(tf.TargetFetchError):
            tf.access_status_for(FutureHttpError("probe"))

    def test_an_unmapped_subclass_raises_through_fetch_target_too(self):
        class AnotherFutureError(hc.HttpError):
            pass

        with self.assertRaises(tf.TargetFetchError):
            fetch(StubClient(error=AnotherFutureError("probe")))

    def test_a_subclass_of_a_mapped_class_inherits_its_mapping(self):
        class StricterTimeout(hc.HttpTimeout):
            pass

        self.assertEqual(tf.access_status_for(StricterTimeout("probe")), tf.TIMEOUT)

    def test_the_mapping_is_keyed_by_class_not_by_name(self):
        for key in tf.ACCESS_STATUS_FOR_ERROR:
            with self.subTest(key):
                self.assertTrue(inspect.isclass(key))

    def test_no_mapped_value_is_outside_the_committed_vocabulary(self):
        for klass, status in tf.ACCESS_STATUS_FOR_ERROR.items():
            if status is tf.BY_CLIENT_STATUS:
                continue
            with self.subTest(klass.__name__):
                self.assertIn(status, COMMITTED_ACCESS_STATUSES)


class TestClientErrorIsMappedByStatus(unittest.TestCase):
    """4xx is not one fact, and the committed vocabulary distinguishes five."""

    CASES = ((404, tf.NOT_FOUND), (410, tf.GONE), (401, tf.AUTH_REQUIRED),
             (403, tf.AUTH_REQUIRED), (402, tf.PAYWALLED))

    def test_each_distinguishable_status_maps_to_its_own_value(self):
        for status, expected in self.CASES:
            with self.subTest(status=status):
                outcome = fetch(StubClient(error=hc.ClientError("x", status=status)))
                self.assertEqual(outcome.access_status, expected)
                self.assertEqual(outcome.http_status, status)

    def test_another_4xx_is_honestly_unreachable(self):
        for status in (400, 405, 418, 429, 451):
            with self.subTest(status=status):
                outcome = fetch(StubClient(error=hc.ClientError("x", status=status)))
                self.assertEqual(outcome.access_status, tf.UNREACHABLE)

    def test_a_client_error_without_a_status_falls_back_rather_than_crashing(self):
        outcome = fetch(StubClient(error=hc.ClientError("no status")))
        self.assertEqual(outcome.access_status, tf.UNREACHABLE)
        self.assertIsNone(outcome.http_status)

    def test_the_status_is_recorded_in_the_evidence(self):
        outcome = fetch(StubClient(error=hc.ClientError("x", status=404)))
        self.assertIn("404", outcome.verification_evidence)


class TestBudgetExhaustion(unittest.TestCase):
    """A budget stop is the absence of a check, not a failed one."""

    def error(self):
        return BudgetExhausted("cell:x", "requests", 60, 61)

    def test_it_reports_not_checked(self):
        outcome = fetch(StubClient(error=self.error()))
        self.assertEqual(outcome.access_status, tf.NOT_CHECKED)

    def test_it_is_not_reported_as_a_failed_fetch(self):
        outcome = fetch(StubClient(error=self.error()))
        self.assertNotIn(outcome.access_status,
                         (tf.UNREACHABLE, tf.SERVER_ERROR, tf.TIMEOUT))

    def test_it_stays_unverified_and_claims_no_status(self):
        outcome = fetch(StubClient(error=self.error()))
        self.assertEqual(outcome.verification_status, tf.UNVERIFIED)
        self.assertIsNone(outcome.http_status)
        self.assertIsNone(outcome.content_hash)

    def test_it_does_not_raise(self):
        self.assertIsInstance(fetch(StubClient(error=self.error())),
                              tf.TargetFetchOutcome)

    def test_the_evidence_names_the_budget_class(self):
        outcome = fetch(StubClient(error=self.error()))
        self.assertIn("BudgetExhausted", outcome.verification_evidence)


# ------------------------------------------------------------------ isolation
class TestDependencyIsolation(unittest.TestCase):

    def test_exactly_one_logical_client_call_is_made_on_success(self):
        client = StubClient(StubResponse())
        fetch(client)
        self.assertEqual(len(client.calls), 1)

    def test_exactly_one_logical_client_call_is_made_on_failure(self):
        client = StubClient(error=hc.ClientError("x", status=404))
        fetch(client)
        self.assertEqual(len(client.calls), 1)

    def test_it_does_not_retry_a_failure_itself(self):
        """Retries are HttpClient's, and a second call here would double-charge."""
        client = StubClient(error=hc.ServerError("boom", status=500))
        fetch(client)
        self.assertEqual(len(client.calls), 1)

    def test_the_injected_budget_is_passed_through_untouched(self):
        sentinel = object()
        client = StubClient(StubResponse())
        fetch(client, budget=sentinel)
        self.assertIs(client.calls[0][1], sentinel)

    def test_the_requested_url_is_passed_through_unmodified(self):
        client = StubClient(StubResponse())
        fetch(client, url="https://tgt.harvest.test/paper.pdf")
        self.assertEqual(client.calls[0][0], "https://tgt.harvest.test/paper.pdf")

    def test_the_outcome_records_the_url_that_was_requested(self):
        outcome = fetch(StubClient(StubResponse()), url="https://tgt.harvest.test/gone")
        self.assertEqual(outcome.requested_url, "https://tgt.harvest.test/gone")

    def test_a_stub_that_is_no_http_client_at_all_suffices(self):
        """It never needs the real class, so it cannot be constructing one."""
        client = StubClient(StubResponse())
        self.assertNotIsInstance(client, hc.HttpClient)
        self.assertIsInstance(fetch(client), tf.TargetFetchOutcome)

    def test_the_outcome_surface_is_exactly_the_declared_field_set(self):
        """Surface, not implementation: an alias, pool or record field appearing
        here is the visible symptom of this module taking on a later job."""
        self.assertEqual(
            {f.name for f in dataclasses.fields(tf.TargetFetchOutcome)},
            {"requested_url", "access_status", "verification_status",
             "verification_evidence", "last_checked_at", "http_status", "final_url",
             "permanent_redirect", "content_hash", "content_type", "body",
             "error_class",
             # S6-6A: the client's own frozen per-fetch counters, carried outward
             # unread. Still not an alias, a pool or a record field.
             "accounting"})

    def test_the_body_is_carried_outward_byte_identical_and_unparsed(self):
        markup = b'<html><head><link rel="canonical" href="https://x.test/a"></head></html>'
        outcome = fetch(StubClient(StubResponse(body=markup)))
        self.assertEqual(outcome.body, markup)

    def test_the_dependencies_are_injected_keyword_only(self):
        parameters = inspect.signature(tf.fetch_target).parameters
        for name in ("client", "budget", "clock"):
            with self.subTest(name):
                self.assertEqual(parameters[name].kind,
                                 inspect.Parameter.KEYWORD_ONLY)


# ------------------------------------------------------------------- the clock
class TestDeterministicClock(unittest.TestCase):

    def test_last_checked_at_comes_from_the_injected_clock(self):
        outcome = fetch(StubClient(StubResponse()), stamp="2026-01-02T03:04:05Z")
        self.assertEqual(outcome.last_checked_at, "2026-01-02T03:04:05Z")

    def test_a_failure_is_stamped_from_the_same_injected_clock(self):
        outcome = fetch(StubClient(error=hc.ClientError("x", status=404)),
                        stamp="2026-01-02T03:04:05Z")
        self.assertEqual(outcome.last_checked_at, "2026-01-02T03:04:05Z")

    def test_a_plain_string_clock_is_accepted(self):
        outcome = tf.fetch_target(URL, client=StubClient(StubResponse()),
                                  clock="2026-05-06T07:08:09Z")
        self.assertEqual(outcome.last_checked_at, "2026-05-06T07:08:09Z")

    def test_a_datetime_clock_is_normalized_by_the_committed_helper(self):
        import datetime
        moment = datetime.datetime(2026, 5, 6, 7, 8, 9, tzinfo=datetime.timezone.utc)
        outcome = tf.fetch_target(URL, client=StubClient(StubResponse()),
                                  clock=lambda: moment)
        self.assertEqual(outcome.last_checked_at, "2026-05-06T07:08:09Z")

    def test_a_missing_clock_is_refused_rather_than_defaulted(self):
        with self.assertRaises(tf.TargetFetchError):
            tf.fetch_target(URL, client=StubClient(StubResponse()), clock=None)

    def test_an_unusable_clock_is_refused_rather_than_invented(self):
        with self.assertRaises(tf.TargetFetchError):
            tf.fetch_target(URL, client=StubClient(StubResponse()),
                            clock=lambda: "not a timestamp")

    def test_the_clock_is_refused_before_the_client_is_called(self):
        """A refused clock must not spend a request."""
        client = StubClient(StubResponse())
        with self.assertRaises(tf.TargetFetchError):
            tf.fetch_target(URL, client=client, clock=None)
        self.assertEqual(client.calls, [])

    def test_two_fetches_with_one_clock_and_one_result_are_identical(self):
        first = fetch(StubClient(StubResponse()))
        second = fetch(StubClient(StubResponse()))
        self.assertEqual(first, second)

    def test_the_outcome_is_frozen(self):
        outcome = fetch(StubClient(StubResponse()))
        with self.assertRaises(Exception):
            outcome.access_status = tf.GONE


# ------------------------------------------------------- deterministic evidence
class TestEvidenceIsDeterministic(unittest.TestCase):

    def test_no_object_address_reaches_the_evidence(self):
        outcome = fetch(StubClient(error=hc.ClientError("x", status=404)))
        self.assertNotIn("0x", outcome.verification_evidence)

    def test_no_traceback_text_reaches_the_evidence(self):
        outcome = fetch(StubClient(error=hc.ServerError("boom", status=500)))
        for marker in ("Traceback", "File \"", "line "):
            with self.subTest(marker):
                self.assertNotIn(marker, outcome.verification_evidence)

    def test_the_error_class_is_named_by_class_not_by_repr(self):
        outcome = fetch(StubClient(error=hc.HttpTimeout("slow")))
        self.assertEqual(outcome.error_class, "HttpTimeout")
        self.assertNotIn("HttpTimeout(", outcome.verification_evidence)

    def test_two_identical_failures_produce_identical_evidence(self):
        first = fetch(StubClient(error=hc.ClientError("gone for good", status=410)))
        second = fetch(StubClient(error=hc.ClientError("gone for good", status=410)))
        self.assertEqual(first.verification_evidence, second.verification_evidence)
        self.assertEqual(first, second)

    def test_an_exception_with_an_empty_message_still_yields_evidence(self):
        outcome = fetch(StubClient(error=hc.DnsFailure("")))
        self.assertIn("DnsFailure", outcome.verification_evidence)


# --------------------------------------------------- ordinary and control flow
class TestOrdinaryAndControlExceptions(unittest.TestCase):

    def test_an_unexpected_ordinary_exception_becomes_an_outcome(self):
        outcome = fetch(StubClient(error=ValueError("something odd")))
        self.assertEqual(outcome.access_status, tf.UNREACHABLE)
        self.assertEqual(outcome.error_class, "ValueError")
        self.assertEqual(outcome.verification_status, tf.UNVERIFIED)

    def test_an_unexpected_exception_does_not_take_the_cell_down(self):
        self.assertIsInstance(fetch(StubClient(error=RuntimeError("odd"))),
                              tf.TargetFetchOutcome)

    def test_keyboard_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            fetch(StubClient(error=KeyboardInterrupt()))

    def test_system_exit_is_not_swallowed(self):
        with self.assertRaises(SystemExit):
            fetch(StubClient(error=SystemExit(1)))

    def test_generator_exit_is_not_swallowed(self):
        with self.assertRaises(GeneratorExit):
            fetch(StubClient(error=GeneratorExit()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
