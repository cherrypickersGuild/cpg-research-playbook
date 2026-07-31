#!/usr/bin/env bash
# test_taxonomy_cli.sh — the live execution seam and CLI foundation (S9-1).
#
# S9-1 makes a live run CONSTRUCTIBLE without making one HAPPEN. Six failures
# this suite is designed to catch, each of which would either break a committed
# contract or quietly claim work that never occurred:
#   * an omitted seam changing behaviour. `transport`, `mode`, `enrich` and
#     `source_preflight` all default to the behaviour committed at 720f114c; the
#     old call shape and the new all-None shape are compared file by file over a
#     real 43-path tree, because a tree hash passes on two empty directories;
#   * a half-live API. `Transport` is frozen and atomic, so a live opener can
#     never inherit the fixture's suppressed pacing; a test asserts that separate
#     opener/sleep/lease_root parameters do not exist;
#   * deleting a lease root that belongs to the caller, or leaking the temporary
#     one run() creates for itself;
#   * a dishonest manifest: `mode="smoke"` must be ineligible through the
#     COMMITTED derivation with no new predicate, and `enrich=False` must leave
#     the three target_* accounting keys ABSENT rather than zero — "the lane did
#     not run" and "the lane ran and found nothing" are different answers;
#   * a request leaving the machine. Proved with a sentinel at the transport
#     boundary AND proved non-vacuously: the same sentinel, supplied as a
#     transport opener, is reached;
#   * judgement leaking into the CLI layer. An AST scan of cli.py proves it owns
#     no vocabulary and defines no matcher, canonicalizer, serializer, scorer or
#     classifier.
#
# S5-7's recovery semantics, S5-5's pointer ordering, S6-6's eligibility proof and
# S6-7's determinism proof are reused, not re-proved: their own wrappers own them.
#
# Offline and temp-rooted: every byte lands under a directory this suite removes.
# No local recording server, no socket. Asserts state/ and config/ are untouched,
# that the repository's four runtime paths were never created, and that no
# retained external Stage 9 state root was left behind — S9-1 selects none.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_cli.py' -v
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

# S9-1 selects no external retained state root and creates none. A `locks/` tree
# beside the repository would mean live_transport built one during construction,
# which its own test forbids.
if [ -e "../stage9" ] || [ -e "./stage9" ]; then
  echo "FAIL - a retained external Stage 9 state root was created; S9-1 selects" >&2
  echo "       no such path and must create nothing." >&2
  exit 1
fi

exit "$EC"
