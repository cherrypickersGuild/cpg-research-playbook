#!/usr/bin/env bash
# test_taxonomy_linkcheck.sh — bounded link-health re-checking (S9-6).
#
# S9-6 adds the last command of the Stage 9 surface, and the only one that reads a
# finished run and writes a new one from it. Seven failures this suite is designed
# to catch:
#   * a MUTATED BASE RUN. The base directory is hashed before and after and must
#     be byte-identical — a linkcheck that edited its input would destroy the very
#     M2/M3 dataset it was measuring;
#   * a DELETED or DOWNGRADED record. Availability is not truth: a 404 today does
#     not unmake a case that existed, so `link_history` is append-only, the record
#     count never falls, and no prior entry is rewritten;
#   * a SAMPLE THAT DEPENDS ON ITERATION ORDER. Selection is the first N in the
#     committed `records.sort_key` order; shuffling the base records must not
#     change which are chosen;
#   * a VACUOUS CHECK. The committed corpus's accepted targets are all reachable,
#     so synthetic base runs point at the committed 404/410/301 target fixtures —
#     and a stub reporting every target `ok` is PROVED to defeat that guard;
#   * a SILENTLY WIDENED BOUND. `--sample` above the committed target-fetch bound
#     is refused, never clamped;
#   * LOST LINEAGE. `base_run_id` is written, differs from the new run, and names
#     a run directory that exists;
#   * a run that claims to have checked something it did not. Cell status is `ok`
#     only where a record was checked in THIS run, and a link-health RESULT never
#     sets a cell status.
#
# Offline and temp-rooted: every byte lands under a directory this suite removes,
# the transport is the committed FIXTURE transport, and a socket-level guard
# refuses every non-loopback host and is proved wired by tripping it. Asserts
# state/ and config/ are untouched, that the repository's four runtime paths were
# never created, and that the frozen owners and the fixture corpus did not move.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_linkcheck.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

for LEAK in state/taxonomy_harvest data/harvested runs LATEST_RUN_ID; do
  if [ -e "$LEAK" ]; then
    echo "FAIL - this test created the real runtime path '$LEAK'; a linkcheck" >&2
    echo "       writes only under an injected --state-root." >&2
    exit 1
  fi
done

# S9-6 selects no external Stage 9 state root and creates none. The retained
# Stage 9 evidence root is never named, read or written by this suite.
if [ -e "../stage9" ] || [ -e "./stage9" ]; then
  echo "FAIL - a retained external Stage 9 state root was created; S9-6 selects" >&2
  echo "       no such path and must create nothing outside its temp roots." >&2
  exit 1
fi

# This suite writes whole run trees into temp roots, twice per case (a base run
# and a linkcheck run). A leaked one is a retained run tree by another name, and
# a setUp that failed partway is exactly how one escapes.
LEAKED="$(python -c 'import os, tempfile
t = tempfile.gettempdir()
print(" ".join(n for n in os.listdir(t) if n.startswith("s96_")))' 2>/dev/null)"
if [ -n "$LEAKED" ]; then
  echo "FAIL - this test leaked temporary state roots: $LEAKED" >&2
  echo "       A stranded run tree is retained state; clean up on every path." >&2
  exit 1
fi

exit "$EC"
