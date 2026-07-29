#!/usr/bin/env python3
"""throttle_worker.py — one worker process for the domain-throttle test.

Deliberately a SEPARATE PROCESS. The property under test is that the per-domain
cap holds across processes; running the workers as threads would let them share
in-process state and prove nothing.

  Usage:
    python tests/harvest/throttle_worker.py <lease_root> <host> <port>
                                            <requests> <max_conc> <interval>
                                            [--die-holding-lease]

Prints one JSON line summarising what it did.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.domainlease import DomainLease  # noqa: E402


def main():
    lease_root = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    n = int(sys.argv[4])
    max_conc = int(sys.argv[5])
    interval = float(sys.argv[6])
    die = "--die-holding-lease" in sys.argv

    import urllib.request

    done = []
    releases_monotonic_ns = []
    for _ in range(n):
        lease = DomainLease(lease_root, host, max_concurrency=max_conc,
                            min_interval_sec=interval)
        lease.acquire(wait_max_sec=30)
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
