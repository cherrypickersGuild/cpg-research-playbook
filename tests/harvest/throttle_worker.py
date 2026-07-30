#!/usr/bin/env python3
"""throttle_worker.py — one worker process for the domain-throttle test.

Deliberately a SEPARATE PROCESS. The property under test is that the per-domain
cap holds across processes; running the workers as threads would let them share
in-process state and prove nothing.

  Usage:
    python tests/harvest/throttle_worker.py <lease_root> <host> <port>
                                            <requests> <max_conc> <interval>
                                            [--die-holding-lease]
                                            [--wait-max-sec=SECONDS]
                                            [--worker-id=LABEL]

Prints one JSON line summarising what it did.

On a LeaseTimeout it additionally writes ONE bounded diagnostic record to stderr
(see `emit_lease_timeout_diagnostic`) and then re-raises, so the failure behaviour
the suite already asserts is unchanged. Three `domain_throttle` failure signatures
have been observed inside full-gate runs and none reproduced under faithful
process-based investigation (see STAGE_6_IMPLEMENTATION_PLAN.md, S6-T/S6-TD): a
bare traceback said only that a worker waited 30s, never what the lease tree
looked like while it waited. This turns the next occurrence into evidence.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.domainlease import DomainLease, LeaseTimeout  # noqa: E402

# Stable, greppable marker: the suite and the gate logs both find the record by
# this prefix, so a diagnostic can never be confused with ordinary worker output.
DIAGNOSTIC_PREFIX = "LEASE_TIMEOUT_DIAGNOSTIC "

# Bounds, so a diagnostic can never become an unbounded log. The slot count is
# already bounded by max_concurrency; these cap the free-form parts.
MAX_OWNER_TEXT = 400
MAX_COLLECTION_ERRORS = 8
DEFAULT_WAIT_MAX_SEC = 30.0


def _slot_snapshot(lease, slot_path, errors):
    """One slot directory, described as observed. Never raises."""
    row = {"slot": os.path.relpath(slot_path, lease.dir).replace(os.sep, "/")}
    try:
        row["exists"] = os.path.isdir(slot_path)
    except OSError as exc:
        row["exists"] = None
        errors.append("isdir(%s): %s" % (row["slot"], exc))
        return row
    if not row["exists"]:
        return row

    try:
        mtime = os.path.getmtime(slot_path)
        row["mtime"] = round(mtime, 3)
        row["age_sec"] = round(time.time() - mtime, 3)
    except OSError as exc:
        # Vanishing mid-collection is itself a finding, not a collection bug:
        # it means the slot was released while this worker was timing out.
        row["vanished_during_collection"] = True
        errors.append("getmtime(%s): %s" % (row["slot"], exc))

    owner_path = os.path.join(slot_path, "owner")
    try:
        row["owner_present"] = os.path.exists(owner_path)
    except OSError as exc:
        row["owner_present"] = None
        errors.append("exists(owner): %s" % exc)
    if row.get("owner_present"):
        try:
            with open(owner_path, "r", encoding="utf-8") as handle:
                row["owner_text"] = handle.read(MAX_OWNER_TEXT).strip()
        except OSError as exc:
            row["owner_vanished_during_collection"] = True
            errors.append("read(owner): %s" % exc)
    # Parsed through the committed reader, so the diagnostic agrees with what the
    # lease itself would conclude about this owner rather than re-parsing it.
    try:
        pid, epoch = lease._read_owner(slot_path)
        row["owner_pid"] = pid
        row["owner_epoch"] = None if epoch is None else round(epoch, 3)
    except Exception as exc:                                      # noqa: BLE001
        errors.append("_read_owner(%s): %s" % (row["slot"], exc))
    return row


def emit_lease_timeout_diagnostic(lease, exc, *, worker_id, request_index,
                                  waited_sec, wait_max_sec, stream=None):
    """Write one bounded diagnostic record to stderr. Best-effort, never raises.

    Deliberately emitted ONLY on the LeaseTimeout path: a successful worker prints
    nothing here, so the marker's presence in a log is itself the signal.
    """
    stream = stream if stream is not None else sys.stderr
    errors = []
    record = {
        "pid": os.getpid(),
        "worker_id": worker_id,
        "host": getattr(lease, "host", None),
        "max_concurrency": getattr(lease, "max_concurrency", None),
        "wait_max_sec": wait_max_sec,
        "min_interval_sec": getattr(lease, "min_interval_sec", None),
        "lease_stale_sec": getattr(lease, "lease_stale_sec", None),
        "request_index": request_index,
        "waited_sec": round(waited_sec, 3),
        "error": str(exc),
    }
    try:
        record["lease_dir_exists"] = os.path.isdir(lease.dir)
        record["slots_dir_exists"] = os.path.isdir(lease.slots_dir)
        record["pace_lock_exists"] = os.path.exists(lease.pace_lock)
        try:
            with open(lease.next_allowed_path, "r", encoding="utf-8") as handle:
                record["next_allowed_at"] = handle.read(64).strip()
        except OSError:
            record["next_allowed_at"] = None

        # Only the slots this lease could have taken — never a recursive dump of
        # unrelated temporary files.
        slots = []
        for index in range(1, int(getattr(lease, "max_concurrency", 1)) + 1):
            slots.append(_slot_snapshot(
                lease, os.path.join(lease.slots_dir, "slot_%d.lease" % index),
                errors))
        record["slots"] = slots
    except Exception as exc2:                                     # noqa: BLE001
        # A broken collector must never replace the failure it was describing.
        errors.append("snapshot: %s: %s" % (type(exc2).__name__, exc2))
    record["collection_errors"] = errors[:MAX_COLLECTION_ERRORS]

    try:
        stream.write(DIAGNOSTIC_PREFIX + json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
    except Exception:                                             # noqa: BLE001
        pass
    return record


def _flag(prefix, default):
    """A `--name=value` option, scanned from argv. Positional args are unchanged."""
    for arg in sys.argv[1:]:
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return default


def main():
    lease_root = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    n = int(sys.argv[4])
    max_conc = int(sys.argv[5])
    interval = float(sys.argv[6])
    die = "--die-holding-lease" in sys.argv
    # Test-only knob. The DEFAULT IS UNCHANGED at 30s, so every existing caller
    # behaves byte-identically; only a regression that deliberately occupies the
    # slot passes a short limit, so it need not wait 30 seconds to prove the path.
    wait_max_sec = float(_flag("--wait-max-sec=", DEFAULT_WAIT_MAX_SEC))
    worker_id = _flag("--worker-id=", "")

    import urllib.request

    done = []
    releases_monotonic_ns = []
    for request_index in range(n):
        lease = DomainLease(lease_root, host, max_concurrency=max_conc,
                            min_interval_sec=interval)
        started = time.monotonic()
        try:
            lease.acquire(wait_max_sec=wait_max_sec)
        except LeaseTimeout as exc:
            # Describe the tree, then fail exactly as before: same exception, same
            # exit path, same non-zero status the suite already asserts on.
            emit_lease_timeout_diagnostic(
                lease, exc, worker_id=worker_id, request_index=request_index,
                waited_sec=time.monotonic() - started, wait_max_sec=wait_max_sec)
            raise
        try:
            lease.wait_turn(interval_sec=interval)
            # The moment the pacing gate released this worker. Stamped here,
            # before the request is initiated, because THIS is the event
            # DomainLease.wait_turn controls. Everything after it — socket
            # connect, ThreadingHTTPServer accept, handler-thread spawn — is
            # transport and scheduling the gate has no say over, and measuring
            # spacing on the far side of it measures that instead.
            #
            # monotonic_ns, not time_ns: immune to wall-clock adjustment, and on
            # this platform it is QueryPerformanceCounter (100ns resolution,
            # ~500ns observed tick) counting from boot, so values from separate
            # processes on one machine are directly comparable.
            releases_monotonic_ns.append(time.monotonic_ns())
            if die:
                # Exit hard while still holding the slot: no release, no atexit,
                # no finally. This is the crash the stale-lease policy exists for.
                os._exit(9)
            url = "http://127.0.0.1:%d/ping?pid=%d" % (port, os.getpid())
            with urllib.request.urlopen(url, timeout=10) as r:
                r.read()
            done.append(time.time())
        finally:
            lease.release()

    print(json.dumps({"pid": os.getpid(), "requests": len(done),
                      "releases_monotonic_ns": releases_monotonic_ns}))


if __name__ == "__main__":
    main()
