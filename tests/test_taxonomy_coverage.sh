#!/usr/bin/env bash
# test_taxonomy_coverage.sh — coverage targets, gap ranking, adaptive scheduling.
#
# Three failures this is designed to catch:
#   * an acceptance threshold moving between rounds. Coverage targets are HINTS:
#     the scheduler changes WHERE it looks, never WHAT is accepted. The test
#     asserts min_relevance / min_quality / accept_composite are identical in
#     every round AND that the scheduler source never assigns one;
#   * cross-industry closing a concrete gap, or opening a lane of its own. Ten
#     cross-industry records must leave the healthcare and manufacturing gaps
#     exactly where they were;
#   * an unmet target being "met" by lowering a bar or inventing a weak facet
#     instead of being reported as unmet, with no_credible_source named.
#
# Fully offline and deterministic: round results are injected through a callable
# and the clock is injectable, so adaptive behaviour is provable before any
# Stage 3 adapter exists.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_coverage.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
