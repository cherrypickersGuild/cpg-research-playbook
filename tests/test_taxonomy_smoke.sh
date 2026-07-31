#!/usr/bin/env bash
# test_taxonomy_smoke.sh — bounded smoke and read-only run validation (S9-3).
#
# S9-3 adds the two commands that make a live run possible to PERFORM and
# possible to TRUST, and adds them entirely offline. Seven failures this suite is
# designed to catch:
#   * a cap that does not bind, or binds dishonestly. The candidate cap slices
#     BEFORE any judgement, so an excluded candidate gets no classification, no
#     facets, no record and no rejection row — unprocessed is not rejected; the
#     accepted cap keeps the deterministic prefix ending at the Nth accepted
#     candidate and relabels nothing;
#   * a budget that forgives itself. The smoke budget is command-wide: preflight
#     time is subtracted, the scope is checked at every cell boundary, and an
#     expiry aborts BEFORE the artifact-writing phase, publishing no manifest and
#     leaving the previous pointer untouched;
#   * a run that claims more than it did. config.bounds carries the three smoke
#     caps only when they were enforced; omitted bounds reproduce the committed
#     config bytes exactly;
#   * a validator that repairs. The whole tree is hashed before and after
#     validation — including a BROKEN tree — and must be byte-identical;
#   * miscounted paths across runs (E9-11). 42 JSON = 18 selected-run + 24
#     shared; a second run adds 18 and updates the same 24, it does not make 84;
#   * a pointer that disagrees. `validate --run-id` answers "is the run this root
#     currently points at sound?", so a historical non-latest id is invalid by
#     contract;
#   * an outbound request. A socket-level guard refuses every non-loopback host
#     and is proved wired by tripping it.
#
# Every smoke here runs on a FIXTURE transport. NO CONFIGURED SOURCE HAS BEEN
# CONTACTED — that is S9-L1 and S9-L2, both unapproved.
#
# Offline and temp-rooted: every byte lands under a directory this suite removes,
# including the external state roots it creates for the CLI. Asserts state/ and
# config/ are untouched, the repository's four runtime paths were never created,
# and no external Stage 9 root or lease root is left behind.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_smoke.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

for LEAK in state/taxonomy_harvest data/harvested runs LATEST_RUN_ID; do
  if [ -e "$LEAK" ]; then
    echo "FAIL - this test created the real runtime path '$LEAK'; writes must" >&2
    echo "       stay under an injected temp root." >&2
    exit 1
  fi
done

# The external state roots this suite drives the CLI against are `mktemp -d`
# directories it removes itself. A retained Stage 9 root beside the repository
# would mean one escaped; S9-3 selects no such path and creates none.
if [ -e "../stage9" ] || [ -e "./stage9" ]; then
  echo "FAIL - a retained external Stage 9 state root was created; S9-3 selects" >&2
  echo "       no such path and must create nothing outside its temp roots." >&2
  exit 1
fi

# This suite drives the CLI against external state roots, so its temp trees hold
# whole 43-path runs. A leaked one is a retained run tree by another name — and a
# setUpClass that failed partway is exactly how one escapes, which is why the
# suite registers cleanup with addClassCleanup rather than tearDownClass. Checked
# here as well, because a guard the suite owns cannot catch the suite crashing.
LEAKED="$(python -c 'import os, tempfile
t = tempfile.gettempdir()
print(" ".join(n for n in os.listdir(t) if n.startswith("s93_")))' 2>/dev/null)"
if [ -n "$LEAKED" ]; then
  echo "FAIL - this test leaked temporary state/lease roots: $LEAKED" >&2
  echo "       A stranded run tree is retained state; clean up on every path." >&2
  exit 1
fi

exit "$EC"
