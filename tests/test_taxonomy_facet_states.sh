#!/usr/bin/env bash
# test_taxonomy_facet_states.sh — the five reporting states and derived eligibility.
#
# Three failures this is designed to catch:
#   * a record counted in two reporting states, or in none, so the five counts
#     stop summing to the applicable full-record population;
#   * unmapped_legacy_value quietly folded into ordinary unresolved, hiding a
#     legacy value that a reviewer has to act on;
#   * publication eligibility drifting from "derived" into a persisted record flag.
#
# Also carries the D1 regression: a cases__domain-applications cross_reference row
# must stay VALID. A root-level applicability conditional would have required
# case_facets on a branch whose closed property set cannot carry it, making every
# such row unsatisfiable — a defect that would only surface at Stage 5.
#
# Offline, no network, no production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_facet_states.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
