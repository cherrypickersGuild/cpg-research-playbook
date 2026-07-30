#!/usr/bin/env bash
# test_taxonomy_run_cells.sh — the cell driver (S5-6).
#
# This is the checkpoint that makes Stage 5 a stage rather than a library: the
# committed Stage 4 pipeline is driven over the fixture corpus, cell by cell, and
# one run's worth of artifacts lands on disk. Five failures this is designed to
# catch, each of which would make the artifact tree untrustworthy:
#   * an artifact that does not validate, or a path that should not exist —
#     the file set is asserted EXACTLY, so an extra file fails as loudly as a
#     missing one;
#   * bytes that depend on order rather than content: two runs with a pinned
#     clock, and a run with shuffled cell order, must produce identical trees;
#   * one cell's failure taking down the run, or corrupting another cell's
#     artifact — a broken cell is reported as adapter_error and still gets a
#     complete, valid artifact;
#   * concurrency creeping in. Stage 5 is sequential BY DESIGN (plan §9.1); that
#     is what keeps CF-1's unlocked pool paths at zero concurrent callers, and a
#     static scan fails if a lock, thread, process or async call appears;
#   * a live request. The opener is fixtures.FixtureOpener and a test proves no
#     socket is opened.
#
# S5-1's atomicity, S5-2's artifact assembly, S5-3's ledger semantics, S5-4's
# coverage counting and S5-5's pointer ordering are reused, not re-proved.
#
# Offline and temp-rooted: every byte lands under an injected temp root. Asserts
# state/ and config/ are untouched AND that the repository's own runtime artifact
# paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_run_cells.py' -v
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

exit "$EC"
