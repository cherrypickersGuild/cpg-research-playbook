#!/usr/bin/env bash
# test_taxonomy_coverage_report.sh — coverage report wiring (S5-4).
#
# Four failures this is designed to catch, each of which would make a coverage
# number less trustworthy than no number at all:
#   * a states block disagreeing with facets.count_states over the same records,
#     or the five states not summing to applicable_full_records;
#   * not_enriched ("never tried") folded into unresolved ("looked, found
#     nothing"), or unmapped_legacy_value hidden inside either — the one fact a
#     reviewer has to act on;
#   * a cross_reference counted as an independent record, double-counting the
#     record it points at;
#   * an empty industry.secondary presented as a gap or a withheld record. CF-11
#     leaves it empty BY DESIGN, and a report that made it look like a defect
#     would create pressure to manufacture the findings CF-11 prevents.
#
# This checkpoint is wiring: coverage.py and facets.py must stay byte-unchanged,
# and a test asserts that with git. S5-1's atomicity is reused, not re-proved.
#
# Offline and temp-rooted: no network, no fixtures, no cell execution, no
# concurrency. Asserts state/ and config/ are untouched AND that the
# repository's own runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_coverage_report.py' -v
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
