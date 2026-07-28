#!/usr/bin/env bash
# test_taxonomy_budget.sh — request-count and wall-clock caps cannot be exceeded
# via retries, redirect hops, enrichment, multiple sources, or all combined.
# Injected clocks, so a 120s budget is asserted in microseconds.
# tests/*.sh from its audited allowlist) can run the python suite, matching the
# existing tests/test_github_meta.sh pattern.
#
# Offline, no network, no state. Asserts production state/ is untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_budget.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
