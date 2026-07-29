#!/usr/bin/env bash
# test_taxonomy_ledger.sh — per-cell rejection log and URL ledger (S5-3).
#
# Four failures this is designed to catch, each of which quietly destroys work:
#   * verify.py growing a rejection reason that rejection.v1.json cannot store,
#     which would fail at write time on a live run rather than here (the reasons
#     are enumerated from verify.decide's AST, not typed into the test);
#   * first_seen_at being rewritten on a re-merge, which would erase how long a
#     URL has actually been known;
#   * a decided URL being un-decided — a terminal outcome overwritten by a
#     different one, or a rejected entry dropped so every run re-fetches and
#     re-rejects it;
#   * a corrupt ledger being treated as empty, which looks like success and
#     silently re-harvests the whole cell.
#
# S5-1 already proves the writer is atomic and validate-before-write; those
# guarantees are reused here rather than re-proved.
#
# Offline and temp-rooted: no network, no fixtures, no cell execution, no
# concurrency. Asserts state/ and config/ are untouched AND that the
# repository's own runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_ledger.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

for LEAK in state/taxonomy_harvest data/harvested runs; do
  if [ -e "$LEAK" ]; then
    echo "FAIL - this test created the real runtime path '$LEAK'; writes must" >&2
    echo "       stay under an injected temp root." >&2
    exit 1
  fi
done

exit "$EC"
