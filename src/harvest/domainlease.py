#!/usr/bin/env python3
"""domainlease.py — per-domain concurrency and spacing, ACROSS processes.

Every cell runs in its own process, so an in-process limiter cannot enforce a
pipeline-wide per-domain cap: twelve cells each politely allowing "1 concurrent
request to arxiv.org" is twelve concurrent requests to arxiv.org. The
coordination therefore has to live somewhere both processes can see, which here
means the filesystem.

Built on `mkdir` atomicity, the same primitive scripts/lib/lockdir.sh uses and
for the same reason: Git Bash has no flock, and `os.mkdir` is atomic
create-or-fail on both Windows and POSIX.

    state/taxonomy_harvest/domains/<domain_slug>/
        slots/slot_1.lease ... slot_N.lease   dir; holds `owner` (pid/host/time)
        pace.lock                             short-held mutex over next_allowed_at
        next_allowed_at                       unix epoch float; the shared gate

Two independent mechanisms:

  concurrency  N slot directories. Acquiring one is `mkdir`; the first process
               to succeed owns it. All N held means wait.
  spacing      A single shared `next_allowed_at`. Before each request a worker
               sleeps until that time, then pushes it forward by the effective
               interval. Because it is shared, one worker's Retry-After delays
               EVERY worker on that domain — which is the entire reason this is
               on disk rather than in memory.

Stale recovery matters as much as acquisition. A worker killed mid-request must
not wedge the domain forever, but a slow worker must not have its slot stolen
either. The policy mirrors lockdir.sh: break a lease only when its pid is
PROVABLY gone, or when it is older than lease_stale_sec. An unparseable owner
file or an undeterminable pid counts as ALIVE — fail safe, because wrongly
stealing a live slot causes the exact over-concurrency this module exists to
prevent.
"""
import errno
import os
import random
import re
import socket
import time

DEFAULT_MAX_CONCURRENCY = 1
DEFAULT_MIN_INTERVAL_SEC = 2.0
DEFAULT_LEASE_STALE_SEC = 120.0

_SAFE = re.compile(r"[^a-z0-9.-]+")


class LeaseTimeout(Exception):
    """No slot became free within the allowed wait."""

    reason = "lease_timeout"


def domain_slug(host):
    """Filesystem-safe directory name for a host.

    Keeps dots so the directory is readable ('arxiv.org'), replaces anything
    else, and bounds the length for path-limit safety on Windows.
    """
    h = (host or "").strip().lower().strip(".")
    if not h:
        h = "unknown-host"
    h = _SAFE.sub("-", h)
    return h[:100]


def _pid_alive_windows(pid):
    """Liveness via the Win32 API.

    os.kill(pid, 0) is NOT a liveness probe on Windows. Measured on this
    platform (CPython 3.13, win32): for a process that had definitively exited,
    os.kill(pid, 0) returned normally — i.e. reported the dead process as ALIVE.
    Relying on it would mean a crashed worker's slot was never reclaimed by the
    pid rule and the domain stayed blocked until lease_stale_sec expired, which
    is exactly the wedge that rule exists to prevent.

    OpenProcess + GetExitCodeProcess answers the question directly.

    Known conservative edge: a process that exits with code 259 (STILL_ACTIVE)
    is indistinguishable from a running one and reads as alive. That errs toward
    waiting, which is the safe direction, and the age rule still reclaims it.
    """
    import ctypes
    import ctypes.wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_INVALID_PARAMETER = 87
    ERROR_ACCESS_DENIED = 5

    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except Exception:
        return True

    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        err = ctypes.get_last_error()
        if err == ERROR_INVALID_PARAMETER:
            return False            # no such process — provably gone
        if err == ERROR_ACCESS_DENIED:
            return True             # exists, we just cannot look at it
        return True                 # undeterminable -> fail safe
    try:
        code = ctypes.wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == STILL_ACTIVE
    except Exception:
        return True
    finally:
        try:
            k32.CloseHandle(handle)
        except Exception:
            pass


def _pid_alive_posix(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False            # no such process — provably gone
        if exc.errno == errno.EPERM:
            return True             # exists, owned by someone else
        return True
    except Exception:
        return True


def _pid_alive(pid):
    """True unless the process is PROVABLY gone.

    Undeterminable means alive. Wrongly declaring a live worker dead would let a
    second worker take its slot, producing exactly the over-concurrency this
    module exists to prevent; wrongly declaring a dead worker alive only costs a
    wait, bounded by lease_stale_sec.
    """
    if pid is None or pid <= 0:
        return True
    if os.name == "nt":
        return _pid_alive_windows(pid)
    return _pid_alive_posix(pid)


class DomainLease:
    """Cross-process concurrency slot + spacing gate for one domain."""

    def __init__(self, root, host, max_concurrency=DEFAULT_MAX_CONCURRENCY,
                 min_interval_sec=DEFAULT_MIN_INTERVAL_SEC,
                 lease_stale_sec=DEFAULT_LEASE_STALE_SEC,
                 clock=time.time, sleep=time.sleep):
        self.host = host
        self.slug = domain_slug(host)
        self.dir = os.path.join(root, self.slug)
        self.slots_dir = os.path.join(self.dir, "slots")
        self.pace_lock = os.path.join(self.dir, "pace.lock")
        self.next_allowed_path = os.path.join(self.dir, "next_allowed_at")
        self.max_concurrency = max(1, int(max_concurrency))
        self.min_interval_sec = float(min_interval_sec)
        self.lease_stale_sec = float(lease_stale_sec)
        self._clock = clock
        self._sleep = sleep
        self._held = None

    # ------------------------------------------------------------------ setup
    def _ensure_dirs(self):
        os.makedirs(self.slots_dir, exist_ok=True)

    # ------------------------------------------------------------- concurrency
    def _write_owner(self, slot_dir):
        try:
            with open(os.path.join(slot_dir, "owner"), "w", encoding="utf-8", newline="\n") as f:
                f.write("pid=%d host=%s acquired_at=%s epoch=%.3f\n"
                        % (os.getpid(), socket.gethostname(),
                           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), self._clock()))
        except OSError:
            pass  # owner metadata is diagnostic; the mkdir is the lock

    def _read_owner(self, slot_dir):
        try:
            with open(os.path.join(slot_dir, "owner"), "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return None, None
        pid = epoch = None
        m = re.search(r"pid=(\d+)", text)
        if m:
            pid = int(m.group(1))
        m = re.search(r"epoch=([0-9.]+)", text)
        if m:
            try:
                epoch = float(m.group(1))
            except ValueError:
                epoch = None
        return pid, epoch

    def _try_break_stale(self, slot_dir):
        """Reclaim a slot only when it is provably safe to do so."""
        pid, epoch = self._read_owner(slot_dir)
        if pid is None and epoch is None:
            # No readable owner. Could be a slot mid-creation, so age it out
            # rather than stealing it immediately.
            try:
                age = self._clock() - os.path.getmtime(slot_dir)
            except OSError:
                return False
            if age < self.lease_stale_sec:
                return False
        else:
            if _pid_alive(pid):
                if epoch is None or (self._clock() - epoch) < self.lease_stale_sec:
                    return False
            # pid provably gone, or lease older than the stale threshold

        try:
            owner = os.path.join(slot_dir, "owner")
            if os.path.exists(owner):
                os.unlink(owner)
            os.rmdir(slot_dir)
            return True
        except OSError:
            return False

    def acquire(self, wait_max_sec=60.0, budget=None):
        """Take a concurrency slot. Raises LeaseTimeout rather than blocking forever."""
        self._ensure_dirs()
        deadline = self._clock() + float(wait_max_sec)
        attempt = 0

        while True:
            for i in range(1, self.max_concurrency + 1):
                slot = os.path.join(self.slots_dir, "slot_%d.lease" % i)
                try:
                    os.mkdir(slot)
                except FileExistsError:
                    if self._try_break_stale(slot):
                        try:
                            os.mkdir(slot)
                        except OSError:
                            continue
                    else:
                        continue
                except OSError:
                    continue
                self._write_owner(slot)
                self._held = slot
                return slot

            if self._clock() >= deadline:
                raise LeaseTimeout(
                    "no slot for %s within %.1fs (max_concurrency=%d)"
                    % (self.host, wait_max_sec, self.max_concurrency))
            if budget is not None:
                budget.check_time()

            attempt += 1
            # Jittered backoff so N blocked workers do not retry in lockstep and
            # hand the slot to whichever happens to poll first every time.
            base = min(0.05 * (2 ** min(attempt, 5)), 1.0)
            self._sleep(base * (0.5 + random.random()))

    def release(self):
        """Give the slot back. Safe to call twice; never releases another's slot."""
        slot = self._held
        self._held = None
        if not slot:
            return
        try:
            owner = os.path.join(slot, "owner")
            pid, _ = self._read_owner(slot)
            if pid is not None and pid != os.getpid():
                return          # not ours — someone reclaimed it; leave it alone
            if os.path.exists(owner):
                os.unlink(owner)
            os.rmdir(slot)
        except OSError:
            pass

    # ----------------------------------------------------------------- spacing
    def _pace_lock_acquire(self, timeout=10.0):
        deadline = self._clock() + timeout
        while True:
            try:
                os.mkdir(self.pace_lock)
                return True
            except FileExistsError:
                try:
                    age = self._clock() - os.path.getmtime(self.pace_lock)
                    if age > 30.0:      # only ever held for a moment
                        os.rmdir(self.pace_lock)
                        continue
                except OSError:
                    pass
                if self._clock() >= deadline:
                    return False
                self._sleep(0.01 + random.random() * 0.02)
            except OSError:
                return False

    def _pace_lock_release(self):
        try:
            os.rmdir(self.pace_lock)
        except OSError:
            pass

    def _read_next_allowed(self):
        try:
            with open(self.next_allowed_path, "r", encoding="utf-8") as f:
                return float(f.read().strip())
        except (OSError, ValueError):
            return 0.0

    def _write_next_allowed(self, value):
        tmp = self.next_allowed_path + ".tmp.%d" % os.getpid()
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write("%.6f\n" % value)
            os.replace(tmp, self.next_allowed_path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def wait_turn(self, interval_sec=None, budget=None):
        """Sleep until this domain's shared gate opens, then push it forward.

        Returns the number of seconds actually slept, so callers can record how
        much of a budget went to politeness rather than work.

        FAILS CLOSED. `next_allowed_at` is a read-modify-write across processes,
        so it is only ever touched while holding the pace lock. This previously
        gated the *release* on acquisition but not the critical section: when
        `_pace_lock_acquire()` returned False — deadline exhausted, or any OS
        error — the read, the sleep and the write all went ahead unsynchronized,
        and two workers could read the same gate and both proceed early. That is
        the one thing this gate exists to prevent, so failing to acquire is now
        an error rather than a licence to continue.
        """
        self._ensure_dirs()
        interval = self.min_interval_sec if interval_sec is None else float(interval_sec)

        # Nothing below this line runs on the failure path: no clock read, no
        # gate read, no sleep, no gate write, and no release of a lock we never
        # took. `_pace_lock_acquire` is bounded and never raises; it returns
        # False on deadline exhaustion and on any OSError.
        if not self._pace_lock_acquire():
            raise LeaseTimeout(
                "pace lock for %s unavailable; the shared pacing gate was NOT "
                "updated. Refusing to read-modify-write next_allowed_at without "
                "the lock, because two workers doing that concurrently would "
                "both read the same gate and both proceed early." % self.host)

        try:
            now = self._clock()
            nxt = self._read_next_allowed()
            wait = max(0.0, nxt - now)

            if budget is not None and wait > 0 and budget.would_exceed_time(wait):
                # Fail fast rather than sleep into a timeout we can already see
                # coming. The gate is left untouched so other workers are
                # unaffected by this one giving up.
                _raise_budget(budget, wait)

            if wait > 0:
                self._sleep(wait)
            self._write_next_allowed(max(self._clock(), nxt) + interval)
        finally:
            # Unconditional: this point is reachable only after a successful
            # acquisition, so there is no longer a lock-we-do-not-hold to guard.
            self._pace_lock_release()
        return wait

    def penalize(self, seconds):
        """Push the shared gate out by `seconds` (Retry-After, 429, 503).

        Shared on purpose: one worker being told to back off must slow every
        other worker on that domain, not just itself.
        """
        self._ensure_dirs()
        got = self._pace_lock_acquire()
        try:
            target = self._clock() + float(seconds)
            if target > self._read_next_allowed():
                self._write_next_allowed(target)
        finally:
            if got:
                self._pace_lock_release()

    # ------------------------------------------------------------------ ctx
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def _raise_budget(budget, wait):
    from .budget import BudgetExhausted
    raise BudgetExhausted("pacing", "seconds", budget.remaining_seconds(), round(wait, 3))


def effective_interval(policy_defaults, overrides, host, robots_crawl_delay=None):
    """max(configured floor, per-domain override, robots Crawl-delay).

    Taking the max means a publisher's stated Crawl-delay can only ever slow us
    down, never speed us up past our own floor.
    """
    base = float(policy_defaults.get("min_interval_sec", DEFAULT_MIN_INTERVAL_SEC))
    ov = _match_override(overrides, host)
    if ov and ov.get("min_interval_sec") is not None:
        base = max(base, float(ov["min_interval_sec"]))
    if robots_crawl_delay is not None:
        try:
            base = max(base, float(robots_crawl_delay))
        except (TypeError, ValueError):
            pass
    return base


def effective_concurrency(policy_defaults, overrides, host):
    n = int(policy_defaults.get("max_concurrency", DEFAULT_MAX_CONCURRENCY))
    ov = _match_override(overrides, host)
    if ov and ov.get("max_concurrency") is not None:
        n = min(n, int(ov["max_concurrency"]))
    return max(1, n)


def _match_override(overrides, host):
    """Exact host match first, then any parent-domain suffix.

    So an override on 'microsoft.com' also governs 'blogs.microsoft.com', which
    is what makes a single entry cover a publisher's whole estate.
    """
    if not overrides:
        return None
    h = (host or "").lower()
    if h in overrides:
        return overrides[h]
    for key, val in overrides.items():
        k = key.lower()
        if h == k or h.endswith("." + k):
            return val
    return None
