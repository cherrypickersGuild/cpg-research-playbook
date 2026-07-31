#!/usr/bin/env bash
# test_taxonomy_compare.sh — run comparison and publication diff (S9-4).
#
# S9-4 adds the two commands that turn "two smokes exited 0" into "the two smokes
# agree", and the one that proves live work never touched the publication path.
# Both READ. Seven failures this suite is designed to catch:
#   * a comparator that forgives. There is no `--normalize` (E9-14): every
#     differing JSON path is enumerated and classified, and a field that belongs
#     to no committed schema class is an INVARIANT VIOLATION, not a silence;
#   * an identity that moved. record_id, content_id, identity_url, cell_id,
#     canonical_url, the classification and facet subtrees and every non-freshness
#     score must be identical for a record present in both runs;
#   * a clock reading mistaken for a change, or a change mistaken for a clock
#     reading. The permitted set is enumerated exactly and nothing else joins it;
#   * a count contradiction resolved the wrong way (E9-16). WITHIN a run, metadata
#     must agree with that run's records; BETWEEN runs, a changed count is content;
#   * a comparison that demands a pointer. Neither run need be LATEST_RUN_ID, and
#     `runvalidate` is not weakened to achieve that;
#   * a report whose bytes depend on record order or JSON key order;
#   * a `diff` that cannot tell "nothing is published" from "everything matches",
#     or that CREATES the publication root in order to look at it.
#
# The 24 shared ledger and rejection documents are never presented as historical
# A/B snapshots — they are updated in place and have no per-run form.
#
# Offline and temp-rooted: every byte lands under a directory this suite removes.
# No transport is constructed on any path. Asserts state/ and config/ are
# untouched and the repository's four runtime paths were never created — including
# data/harvested/, which `diff` names by default and must only ever look at.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_compare.py' -v
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
    echo "       stay under an injected temp root. 'diff' defaults to" >&2
    echo "       data/harvested/ and must LOOK at it, never create it." >&2
    exit 1
  fi
done

# S9-4 selects no external Stage 9 state root and creates none.
if [ -e "../stage9" ] || [ -e "./stage9" ]; then
  echo "FAIL - a retained external Stage 9 state root was created; S9-4 selects" >&2
  echo "       no such path and must create nothing outside its temp roots." >&2
  exit 1
fi

# This suite writes whole run trees into temp roots. A leaked one is a retained
# run tree by another name, and a setUpClass that failed partway is exactly how
# one escapes — which is why the suite uses addClassCleanup. Checked here too,
# because a guard the suite owns cannot catch the suite crashing.
LEAKED="$(python -c 'import os, tempfile
t = tempfile.gettempdir()
print(" ".join(n for n in os.listdir(t) if n.startswith("s94_")))' 2>/dev/null)"
if [ -n "$LEAKED" ]; then
  echo "FAIL - this test leaked temporary state roots: $LEAKED" >&2
  echo "       A stranded run tree is retained state; clean up on every path." >&2
  exit 1
fi

exit "$EC"
