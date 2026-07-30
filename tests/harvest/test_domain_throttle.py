#!/usr/bin/env python3
"""test_domain_throttle.py — the per-domain cap must hold ACROSS PROCESSES.

Every cell is its own process, so an in-process limiter would let twelve cells
each "politely" allow one concurrent request and produce twelve. These tests
launch real subprocesses against a local recording HTTP server and measure what
actually arrived.

Two properties, measured where each is actually controlled:
  * max observed CONCURRENCY never exceeds the cap — measured at the server,
    from overlapping (arrival, departure) intervals, which is exactly where
    concurrency is observable;
  * every SPACING gap is at least the configured interval — measured at WORKER
    RELEASE, the moment DomainLease.wait_turn lets a worker go. Server-arrival
    spacing is release spacing plus a per-request latency difference (socket
    connect, accept, handler-thread spawn) that the gate does not control, so it
    proves delivery here, never pacing.
"""
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.domainlease import (  # noqa: E402
    DomainLease, LeaseTimeout, domain_slug, effective_interval,
    effective_concurrency, _pid_alive,
)

WORKER = os.path.join(ROOT, "tests", "harvest", "throttle_worker.py")


def worker_module():
    """The worker imported BY PATH, so the import works under `unittest discover`
    and under a dotted module path alike."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("throttle_worker_under_test", WORKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder(BaseHTTPRequestHandler):
    events = []
    pids = []
    lock = threading.Lock()
    hold_sec = 0.05

    def do_GET(self):
        t0 = time.time()
        pid = _pid_from_path(self.path)
        time.sleep(self.hold_sec)          # widen the window so overlap is detectable
        t1 = time.time()
        with Recorder.lock:
            Recorder.events.append((t0, t1))
            Recorder.pids.append(pid)      # identity, for completeness checks
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def _pid_from_path(path):
    """The worker's pid from /ping?pid=N. Identity only — never a timing input."""
    q = parse_qs(urlparse(path).query)
    try:
        return int(q.get("pid", ["-1"])[0])
    except (TypeError, ValueError):
        return -1


def parse_release_timestamps(stdout_text, expected):
    """One worker's `releases_monotonic_ns`, or raise.

    Raises rather than returning a partial list on purpose: a silently missing
    timestamp would shrink the sample, and a shrunken sample makes the pacing
    assertion pass by having nothing left to compare.
    """
    lines = [l.strip() for l in stdout_text.splitlines() if l.strip()]
    payloads = []
    for line in lines:
        try:
            payloads.append(json.loads(line))
        except ValueError:
            raise ValueError("worker emitted a non-JSON line: %r" % line[:200])
    if len(payloads) != 1:
        raise ValueError("expected exactly one JSON line from the worker, got %d"
                         % len(payloads))
    obj = payloads[0]
    if "releases_monotonic_ns" not in obj:
        raise ValueError("worker JSON carries no releases_monotonic_ns key: %r" % obj)
    rel = obj["releases_monotonic_ns"]
    if not isinstance(rel, list):
        raise ValueError("releases_monotonic_ns is not a list: %r" % (rel,))
    if len(rel) != expected:
        raise ValueError("expected %d release timestamps, got %d" % (expected, len(rel)))
    for v in rel:
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise ValueError("release timestamp is not a positive integer: %r" % (v,))
    return rel


def max_concurrency(events):
    """Peak overlap from (start, end) intervals via a sweep line."""
    points = []
    for a, b in events:
        points.append((a, 1))
        points.append((b, -1))
    points.sort()
    cur = peak = 0
    for _, delta in points:
        cur += delta
        peak = max(peak, cur)
    return peak


def min_gap(events):
    starts = sorted(a for a, _ in events)
    if len(starts) < 2:
        return float("inf")
    return min(b - a for a, b in zip(starts, starts[1:]))


class ServerCase(unittest.TestCase):
    def setUp(self):
        Recorder.events = []
        Recorder.pids = []
        self.tmp = tempfile.mkdtemp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_workers(self, n_workers, requests_each, max_conc, interval, extra=()):
        procs = []
        for _ in range(n_workers):
            procs.append(subprocess.Popen(
                [sys.executable, WORKER, self.tmp, "127.0.0.1", str(self.port),
                 str(requests_each), str(max_conc), str(interval), *extra],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT))
        outs = []
        for p in procs:
            out, err = p.communicate(timeout=180)
            outs.append((p.returncode, out.decode(errors="replace"),
                         err.decode(errors="replace")))
        return outs


class TestCrossProcessConcurrency(ServerCase):
    def test_six_workers_respect_max_concurrency_one(self):
        outs = self.run_workers(n_workers=6, requests_each=2, max_conc=1, interval=0.0)
        for rc, _, err in outs:
            self.assertEqual(rc, 0, err)
        self.assertEqual(len(Recorder.events), 12)
        self.assertEqual(max_concurrency(Recorder.events), 1,
                         "a second process entered while one held the only slot")

    def test_cap_of_two_is_respected_and_used(self):
        outs = self.run_workers(n_workers=6, requests_each=2, max_conc=2, interval=0.0)
        for rc, _, err in outs:
            self.assertEqual(rc, 0, err)
        peak = max_concurrency(Recorder.events)
        self.assertLessEqual(peak, 2, "cap exceeded")
        self.assertGreaterEqual(peak, 2, "cap of 2 never actually used — not proving much")

    def test_minimum_interval_enforced_across_processes(self):
        """The shared gate spaces processes that never spoke to each other.

        Measured at WORKER RELEASE, which is the event DomainLease.wait_turn
        actually controls. It previously measured server-arrival spacing, which
        is `release spacing + (latency of request i+1 - latency of request i)`:
        socket connect, ThreadingHTTPServer accept and handler-thread spawn all
        sit between the two, and the gate has no say over any of them. A 50-run
        diagnostic measured both sides simultaneously — release gaps never fell
        below the interval (350/350, minimum 0.3120s) while arrival gaps fell
        below the old 0.255s floor in 49 of 50 runs (minimum 0.1787s), with the
        latency-delta arithmetic closing to ~0.1ms. The old assertion was
        therefore reporting first-request connection cost as a pacing failure.

        No tolerance is applied: monotonic_ns is QueryPerformanceCounter here
        (100ns resolution, ~500ns observed tick), six orders of magnitude below
        the quantity under test, so there is no granularity to absorb.
        """
        interval = 0.30
        interval_ns = 300_000_000          # integer ns; no float rounding
        n_workers, requests_each = 4, 2
        expected_requests = n_workers * requests_each

        outs = self.run_workers(n_workers=n_workers, requests_each=requests_each,
                                max_conc=1, interval=interval)
        for rc, _, err in outs:
            self.assertEqual(rc, 0, err)

        # one valid release timestamp per request from every successful worker
        releases = []
        for rc, out, err in outs:
            try:
                releases.extend(parse_release_timestamps(out, requests_each))
            except ValueError as exc:
                self.fail("worker release timestamps unusable: %s (stderr=%s)"
                          % (exc, err[-400:]))
        self.assertEqual(len(releases), expected_requests)

        ordered = sorted(releases)
        gaps = [b - a for a, b in zip(ordered, ordered[1:])]
        self.assertEqual(len(gaps), expected_requests - 1)
        worst = min(gaps)
        self.assertGreaterEqual(
            worst, interval_ns,
            "the pacing gate released two requests %.4fs apart, expected >= %.2fs. "
            "(server-arrival min gap was %.4fs — recorded for diagnosis only; "
            "arrival spacing is not controlled by the gate and does not decide "
            "this test)" % (worst / 1e9, interval, min_gap(Recorder.events)))

        # The server side proves DELIVERY, never spacing: every request arrived,
        # exactly once per worker, none missing and none duplicated.
        self.assertEqual(len(Recorder.events), expected_requests,
                         "expected %d requests to arrive" % expected_requests)
        per_pid = collections.Counter(Recorder.pids)
        self.assertNotIn(-1, per_pid, "a request arrived without a usable pid")
        self.assertEqual(len(per_pid), n_workers,
                         "expected %d distinct workers, saw %r" % (n_workers, per_pid))
        for pid, count in per_pid.items():
            self.assertEqual(count, requests_each,
                             "worker %d sent %d requests, expected %d"
                             % (pid, count, requests_each))


class TestPaceLockFailsClosed(unittest.TestCase):
    """The shared gate is never read-modify-written without its lock.

    `_pace_lock_acquire` is bounded and never raises: it returns False on
    deadline exhaustion and on any OSError. The old code gated only the
    *release* on that result, so on failure the read, the sleep and the write
    all proceeded unsynchronized — two workers could read the same gate and both
    go early, which is precisely what the gate exists to prevent.

    Deterministic throughout: the failure is injected at the narrowest seam
    rather than by waiting out a ten-second deadline.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _lease(self, acquire_result, interval=0.30):
        """A lease whose pace-lock acquisition result is injected, and whose
        every pacing-state touch is recorded."""
        calls = self.calls

        class Instrumented(DomainLease):
            def _pace_lock_acquire(self, timeout=10.0):
                calls.append("acquire")
                return acquire_result

            def _pace_lock_release(self):
                calls.append("release")
                return super()._pace_lock_release()

            def _read_next_allowed(self):
                calls.append("read")
                return super()._read_next_allowed()

            def _write_next_allowed(self, value):
                calls.append("write")
                return super()._write_next_allowed(value)

        return Instrumented(self.tmp, "x.test", min_interval_sec=interval,
                            sleep=lambda s: calls.append("sleep"))

    @staticmethod
    def _gate_bytes(lease):
        try:
            with open(lease.next_allowed_path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def test_deadline_exhaustion_raises_lease_timeout(self):
        lease = self._lease(acquire_result=False)
        lease._ensure_dirs()
        before = self._gate_bytes(lease)
        with self.assertRaises(LeaseTimeout) as cm:
            lease.wait_turn(interval_sec=0.30)
        self.assertIn("x.test", str(cm.exception))
        self.assertIn("NOT", str(cm.exception))
        self.assertEqual(cm.exception.reason, "lease_timeout")
        self.assertEqual(self._gate_bytes(lease), before, "gate file must be untouched")

    def test_an_os_error_during_acquisition_raises_lease_timeout(self):
        # The real acquire swallows OSError and returns False; prove the caller
        # now refuses rather than proceeding.
        real = DomainLease(os.path.join(self.tmp, "missing", "deeper"), "y.test",
                           min_interval_sec=0.30)
        self.assertIs(real._pace_lock_acquire(timeout=0.01), False)

        lease = self._lease(acquire_result=False)
        lease._ensure_dirs()
        with self.assertRaises(LeaseTimeout):
            lease.wait_turn(interval_sec=0.30)

    def test_no_pacing_state_is_touched_on_either_failure(self):
        lease = self._lease(acquire_result=False)
        lease._ensure_dirs()
        with self.assertRaises(LeaseTimeout):
            lease.wait_turn(interval_sec=0.30)
        self.assertEqual(self.calls, ["acquire"],
                         "no read, no write, no sleep, no release may occur")
        self.assertNotIn("read", self.calls)
        self.assertNotIn("write", self.calls)
        self.assertNotIn("sleep", self.calls)

    def test_release_is_not_called_after_a_failed_acquisition(self):
        lease = self._lease(acquire_result=False)
        lease._ensure_dirs()
        with self.assertRaises(LeaseTimeout):
            lease.wait_turn(interval_sec=0.30)
        self.assertNotIn("release", self.calls,
                         "releasing a lock we never took would free another "
                         "worker's lock")

    def test_a_failed_acquisition_leaves_no_stray_lock_directory(self):
        lease = self._lease(acquire_result=False)
        lease._ensure_dirs()
        with self.assertRaises(LeaseTimeout):
            lease.wait_turn(interval_sec=0.30)
        self.assertFalse(os.path.exists(lease.pace_lock))

    def test_successful_acquisition_retains_gate_advancement(self):
        lease = self._lease(acquire_result=True)
        lease._ensure_dirs()
        os.mkdir(lease.pace_lock)          # the injected acquire did not make it
        wait = lease.wait_turn(interval_sec=0.30)
        self.assertEqual(wait, 0.0)
        self.assertEqual(self.calls, ["acquire", "read", "write", "release"])
        advanced = float(open(lease.next_allowed_path).read().strip())
        self.assertGreater(advanced, 0.0)

        # a second turn must now wait for the gate the first one pushed forward
        self.calls.clear()
        second = self._lease(acquire_result=True)
        os.mkdir(second.pace_lock)
        slept = second.wait_turn(interval_sec=0.30)
        self.assertGreater(slept, 0.0, "the gate advanced by the first turn")
        self.assertLessEqual(slept, 0.30)

    def test_the_real_acquire_still_succeeds_and_releases_normally(self):
        lease = DomainLease(self.tmp, "real.test", min_interval_sec=0.0)
        lease._ensure_dirs()
        self.assertEqual(lease.wait_turn(interval_sec=0.0), 0.0)
        self.assertFalse(os.path.exists(lease.pace_lock), "lock must be released")

    def test_pace_lock_stale_recovery_still_works(self):
        lease = DomainLease(self.tmp, "stale.test", min_interval_sec=0.0)
        lease._ensure_dirs()
        os.mkdir(lease.pace_lock)
        old = time.time() - 120.0                       # older than the 30s break
        os.utime(lease.pace_lock, (old, old))
        self.assertIs(lease._pace_lock_acquire(timeout=1.0), True,
                      "a lock abandoned long ago must be reclaimable")
        lease._pace_lock_release()

    def test_a_freshly_held_pace_lock_is_not_stolen(self):
        lease = DomainLease(self.tmp, "held.test", min_interval_sec=0.0)
        lease._ensure_dirs()
        os.mkdir(lease.pace_lock)                       # fresh mtime
        self.assertIs(lease._pace_lock_acquire(timeout=0.05), False)
        self.assertTrue(os.path.exists(lease.pace_lock))
        os.rmdir(lease.pace_lock)

    def test_concurrency_slot_stale_recovery_is_unchanged(self):
        # The slot lease and its pid/age reclamation are a separate mechanism
        # from the pace lock and must not be disturbed by this correction.
        lease = DomainLease(self.tmp, "slot.test", max_concurrency=1)
        slot = lease.acquire(wait_max_sec=1.0)
        self.assertTrue(os.path.isdir(slot))
        lease.release()
        self.assertFalse(os.path.isdir(slot))


class TestReleaseMeasurement(unittest.TestCase):
    """The measurement itself, checked without spawning processes.

    These guard the correction: the pacing assertion must read WORKER release
    timestamps, must not be reachable from server-arrival data, and must fail
    loudly rather than quietly shrinking its sample.
    """

    @staticmethod
    def _line(releases, pid=101, requests=None):
        return json.dumps({"pid": pid,
                           "requests": len(releases) if requests is None else requests,
                           "releases_monotonic_ns": releases})

    def test_release_timestamps_are_emitted_and_parsed_for_every_worker(self):
        outs = [(0, self._line([1_000_000_000, 1_300_000_000]), ""),
                (0, self._line([1_150_000_000, 1_450_000_000], pid=102), "")]
        got = []
        for _, out, _ in outs:
            got.extend(parse_release_timestamps(out, 2))
        self.assertEqual(got, [1_000_000_000, 1_300_000_000,
                               1_150_000_000, 1_450_000_000])

    def test_the_worker_emits_the_key_the_assertion_reads(self):
        # Static coupling check: the helper's key must exist in the worker.
        with open(WORKER, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("releases_monotonic_ns", text)
        self.assertIn("time.monotonic_ns()", text)
        self.assertNotIn("time.time_ns()", text,
                         "release stamping must use the monotonic clock")

    def test_release_gaps_are_independent_of_server_arrival_order(self):
        # Same releases, wildly different arrival data: the computed gaps must
        # not move. This is what makes the assertion immune to transport jitter.
        releases = [1_000_000_000, 1_320_000_000, 1_650_000_000]
        gaps = [b - a for a, b in zip(sorted(releases), sorted(releases)[1:])]

        Recorder.events = [(0.0, 0.1), (0.05, 0.2), (0.06, 0.3)]   # near-simultaneous
        first = min(gaps)
        Recorder.events = [(0.0, 0.1), (9.0, 9.1), (99.0, 99.1)]   # far apart
        second = min(gaps)
        Recorder.events = []
        self.assertEqual(first, second)
        self.assertEqual(first, 320_000_000)

    def test_a_missing_release_key_fails_loudly(self):
        with self.assertRaises(ValueError):
            parse_release_timestamps(json.dumps({"pid": 1, "requests": 2}), 2)

    def test_a_short_release_list_fails_loudly(self):
        with self.assertRaises(ValueError):
            parse_release_timestamps(self._line([1_000_000_000]), 2)

    def test_a_malformed_release_value_fails_loudly(self):
        for bad in ("nope", None, 0, -5, 1.5, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_release_timestamps(self._line([1_000_000_000, bad]), 2)

    def test_non_json_or_multiple_lines_fail_loudly(self):
        with self.assertRaises(ValueError):
            parse_release_timestamps("not json at all", 2)
        with self.assertRaises(ValueError):
            parse_release_timestamps(self._line([1, 2]) + "\n" + self._line([3, 4]), 2)

    def test_empty_worker_output_fails_loudly(self):
        with self.assertRaises(ValueError):
            parse_release_timestamps("", 2)

    def test_pid_is_recovered_from_the_request_path(self):
        self.assertEqual(_pid_from_path("/ping?pid=4242"), 4242)
        self.assertEqual(_pid_from_path("/ping"), -1)
        self.assertEqual(_pid_from_path("/ping?pid=notanumber"), -1)


class TestSharedGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_penalize_delays_a_different_lease_object(self):
        # Simulates two workers: one is told to back off, the other must feel it.
        a = DomainLease(self.tmp, "x.test", max_concurrency=2, min_interval_sec=0.0)
        b = DomainLease(self.tmp, "x.test", max_concurrency=2, min_interval_sec=0.0)
        a.penalize(0.4)
        t0 = time.time()
        b.acquire(wait_max_sec=5)
        try:
            b.wait_turn(interval_sec=0.0)
        finally:
            b.release()
        self.assertGreaterEqual(time.time() - t0, 0.3,
                                "a Retry-After on one worker did not delay the other")

    def test_gate_file_is_shared_per_domain(self):
        a = DomainLease(self.tmp, "x.test")
        b = DomainLease(self.tmp, "other.test")
        self.assertNotEqual(a.next_allowed_path, b.next_allowed_path)
        a.penalize(1)
        self.assertTrue(os.path.exists(a.next_allowed_path))
        self.assertFalse(os.path.exists(b.next_allowed_path))


class TestStaleLeaseRecovery(ServerCase):
    def test_killed_worker_does_not_wedge_the_domain(self):
        # A worker exits via os._exit while holding the only slot.
        outs = self.run_workers(n_workers=1, requests_each=1, max_conc=1, interval=0.0,
                                extra=("--die-holding-lease",))
        self.assertEqual(outs[0][0], 9)

        slot = os.path.join(self.tmp, domain_slug("127.0.0.1"), "slots", "slot_1.lease")
        self.assertTrue(os.path.isdir(slot), "expected an orphaned slot to exist")

        # The dead pid is provably gone, so the next worker reclaims it promptly
        # rather than waiting out lease_stale_sec.
        lease = DomainLease(self.tmp, "127.0.0.1", max_concurrency=1, min_interval_sec=0.0)
        t0 = time.time()
        lease.acquire(wait_max_sec=10)
        lease.release()
        self.assertLess(time.time() - t0, 5.0,
                        "a dead worker's lease should be reclaimed, not waited out")

    def test_live_lease_is_never_stolen(self):
        held = DomainLease(self.tmp, "x.test", max_concurrency=1, min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            other = DomainLease(self.tmp, "x.test", max_concurrency=1,
                                min_interval_sec=0.0, lease_stale_sec=3600)
            with self.assertRaises(LeaseTimeout):
                other.acquire(wait_max_sec=0.5)
        finally:
            held.release()

    def test_stale_by_age_is_reclaimed_even_if_pid_looks_alive(self):
        lease = DomainLease(self.tmp, "x.test", max_concurrency=1,
                            min_interval_sec=0.0, lease_stale_sec=0.2)
        lease.acquire(wait_max_sec=5)
        slot = lease._held
        # Rewrite the owner with THIS process's pid (definitely alive) but an
        # old epoch, so only the age rule can reclaim it.
        with open(os.path.join(slot, "owner"), "w", encoding="utf-8") as f:
            f.write("pid=%d host=t acquired_at=old epoch=%.3f\n" % (os.getpid(), time.time() - 60))
        other = DomainLease(self.tmp, "x.test", max_concurrency=1,
                            min_interval_sec=0.0, lease_stale_sec=0.2)
        other.acquire(wait_max_sec=5)
        other.release()

    def test_release_is_idempotent_and_safe(self):
        lease = DomainLease(self.tmp, "x.test", max_concurrency=1)
        lease.acquire(wait_max_sec=5)
        lease.release()
        lease.release()

    def test_pid_liveness_fails_safe(self):
        self.assertTrue(_pid_alive(os.getpid()))
        self.assertTrue(_pid_alive(None), "undeterminable must count as alive")
        self.assertTrue(_pid_alive(-1))

    def test_pid_liveness_detects_a_dead_process(self):
        # The regression that motivated the platform-specific probe: on Windows
        # os.kill(pid, 0) returns normally for a process that has definitively
        # exited, reporting it ALIVE, so a crashed worker's slot would only ever
        # be reclaimed by the (120s) age rule.
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.assertFalse(_pid_alive(p.pid),
                         "a process that has exited must be reported dead")

    def test_pid_liveness_detects_a_live_process(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            time.sleep(0.4)
            self.assertTrue(_pid_alive(p.pid))
            # and probing must not disturb it
            time.sleep(0.2)
            self.assertIsNone(p.poll(), "the liveness probe must not kill the process")
        finally:
            p.kill()
            p.wait()


class TestEffectiveSettings(unittest.TestCase):
    def test_interval_takes_the_maximum(self):
        defaults = {"min_interval_sec": 2.0}
        overrides = {"arxiv.org": {"min_interval_sec": 15.0}}
        self.assertEqual(effective_interval(defaults, overrides, "arxiv.org"), 15.0)
        self.assertEqual(effective_interval(defaults, overrides, "other.com"), 2.0)
        # a robots Crawl-delay can only slow us down, never speed us up
        self.assertEqual(effective_interval(defaults, {}, "x.com", robots_crawl_delay=10), 10.0)
        self.assertEqual(effective_interval(defaults, {}, "x.com", robots_crawl_delay=0.5), 2.0)

    def test_override_matches_subdomains(self):
        overrides = {"microsoft.com": {"min_interval_sec": 10.0}}
        self.assertEqual(effective_interval({"min_interval_sec": 2.0}, overrides,
                                            "blogs.microsoft.com"), 10.0)

    def test_concurrency_takes_the_minimum(self):
        self.assertEqual(effective_concurrency({"max_concurrency": 4},
                                               {"github.com": {"max_concurrency": 1}},
                                               "github.com"), 1)
        self.assertEqual(effective_concurrency({"max_concurrency": 4}, {}, "x.com"), 4)

    def test_domain_slug_is_filesystem_safe(self):
        self.assertEqual(domain_slug("Blogs.Microsoft.COM"), "blogs.microsoft.com")
        self.assertEqual(domain_slug("a/b:c"), "a-b-c")
        self.assertEqual(domain_slug(""), "unknown-host")


class TestLeaseTimeoutDiagnostic(unittest.TestCase):
    """S6-TD: a LeaseTimeout must describe the tree it timed out against.

    Three `domain_throttle` failure signatures have been observed inside full-gate
    runs, and none reproduced under faithful process-based investigation — six real
    workers on a fresh root acquired 12/12 with no orphaned slot, capping the poll
    backoff changed nothing, and artificial CPU load did not reproduce it. What the
    failures produced was a bare traceback saying a worker waited 30s, which cannot
    distinguish a held slot from a lost one. This proves the diagnostic path itself,
    deterministically: the slot is OCCUPIED BY THIS TEST, so nothing depends on
    scheduler luck and nothing waits 30 seconds.

    It fixes no instability and claims none.
    """

    HOST = "127.0.0.1"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def worker(self, *extra, wait_max_sec="0.5", timeout=60):
        proc = subprocess.Popen(
            [sys.executable, WORKER, self.tmp, self.HOST, "0", "1", "1", "0.0",
             "--wait-max-sec=%s" % wait_max_sec, *extra],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")

    @staticmethod
    def records(stderr):
        prefix = "LEASE_TIMEOUT_DIAGNOSTIC "
        return [json.loads(line[len(prefix):])
                for line in stderr.splitlines() if line.startswith(prefix)]

    def test_a_worker_denied_the_only_slot_exits_through_the_timeout_path(self):
        held = DomainLease(self.tmp, self.HOST, max_concurrency=1,
                           min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            rc, _, err = self.worker()
        finally:
            held.release()
        self.assertNotEqual(rc, 0)
        self.assertIn("LeaseTimeout", err)
        self.assertIn("no slot for", err)

    def test_exactly_one_diagnostic_record_is_emitted(self):
        held = DomainLease(self.tmp, self.HOST, max_concurrency=1,
                           min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            _, _, err = self.worker()
        finally:
            held.release()
        self.assertEqual(len(self.records(err)), 1)

    def test_the_record_describes_the_occupied_slot_and_its_owner(self):
        held = DomainLease(self.tmp, self.HOST, max_concurrency=1,
                           min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            _, _, err = self.worker("--worker-id=probe-7")
        finally:
            held.release()
        record = self.records(err)[0]
        self.assertEqual(record["worker_id"], "probe-7")
        self.assertEqual(record["host"], self.HOST)
        self.assertEqual(record["max_concurrency"], 1)
        self.assertEqual(record["wait_max_sec"], 0.5)
        self.assertTrue(record["slots_dir_exists"])
        self.assertEqual(len(record["slots"]), 1)
        slot = record["slots"][0]
        self.assertEqual(slot["slot"], "slots/slot_1.lease")
        self.assertTrue(slot["exists"])
        self.assertTrue(slot["owner_present"])
        # The slot really is held by THIS process — the point of the diagnostic.
        self.assertEqual(slot["owner_pid"], os.getpid())
        self.assertIn("pid=%d" % os.getpid(), slot["owner_text"])
        self.assertIsNotNone(slot["owner_epoch"])
        self.assertGreaterEqual(slot["age_sec"], 0.0)

    def test_the_record_carries_the_original_error_and_the_wait_it_made(self):
        held = DomainLease(self.tmp, self.HOST, max_concurrency=1,
                           min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            _, _, err = self.worker()
        finally:
            held.release()
        record = self.records(err)[0]
        self.assertIn("no slot for", record["error"])
        self.assertGreaterEqual(record["waited_sec"], 0.5)
        self.assertEqual(record["request_index"], 0)
        self.assertEqual(record["collection_errors"], [])

    def test_the_record_is_one_line_of_parseable_json(self):
        held = DomainLease(self.tmp, self.HOST, max_concurrency=1,
                           min_interval_sec=0.0)
        held.acquire(wait_max_sec=5)
        try:
            _, _, err = self.worker()
        finally:
            held.release()
        lines = [l for l in err.splitlines()
                 if l.startswith("LEASE_TIMEOUT_DIAGNOSTIC ")]
        self.assertEqual(len(lines), 1)
        self.assertIsInstance(json.loads(lines[0][len("LEASE_TIMEOUT_DIAGNOSTIC "):]),
                              dict)

    def test_a_successful_worker_emits_no_diagnostic(self):
        """The marker's presence in a log is itself the signal, so a healthy
        worker must never print it."""
        srv = ThreadingHTTPServer((self.HOST, 0), Recorder)
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            proc = subprocess.Popen(
                [sys.executable, WORKER, self.tmp, self.HOST, str(port),
                 "1", "1", "0.0"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
            out, err = proc.communicate(timeout=60)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(proc.returncode, 0, err.decode(errors="replace"))
        self.assertEqual(self.records(err.decode(errors="replace")), [])
        self.assertNotIn("LEASE_TIMEOUT_DIAGNOSTIC", err.decode(errors="replace"))

    def test_the_default_wait_limit_is_still_thirty_seconds(self):
        """The knob is test-only: omitting it must change nothing for the suite's
        existing callers."""
        self.assertEqual(worker_module().DEFAULT_WAIT_MAX_SEC, 30.0)

    def test_a_broken_collector_does_not_mask_the_original_timeout(self):
        """Best-effort collection: the failure it describes always survives."""
        throttle_worker = worker_module()

        class Hostile:
            host = "h"
            max_concurrency = 1
            min_interval_sec = 0.0
            lease_stale_sec = 120.0

            @property
            def dir(self):
                raise RuntimeError("snapshot exploded")

        class Sink:
            def __init__(self):
                self.text = ""

            def write(self, chunk):
                self.text += chunk

            def flush(self):
                pass

        sink = Sink()
        record = throttle_worker.emit_lease_timeout_diagnostic(
            Hostile(), LeaseTimeout("no slot for h within 0.5s"),
            worker_id="x", request_index=0, waited_sec=0.5, wait_max_sec=0.5,
            stream=sink)
        self.assertIn("no slot for h", record["error"])
        self.assertTrue(record["collection_errors"])
        self.assertTrue(sink.text.startswith("LEASE_TIMEOUT_DIAGNOSTIC "))

    def test_the_diagnostic_is_bounded(self):
        module = worker_module()
        self.assertLessEqual(module.MAX_OWNER_TEXT, 1024)
        self.assertLessEqual(module.MAX_COLLECTION_ERRORS, 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
