#!/usr/bin/env bash
# test_taxonomy_http.sh — robots (RFC 9309 longest-match), redirects, timeouts,
# retries, Retry-After and byte caps. Fully mocked opener; no request leaves the
# machine and no test sleeps for real.
# tests/*.sh from its audited allowlist) can run the python suite, matching the
# existing tests/test_github_meta.sh pattern.
#
# Offline, no network, no state. Asserts production state/ is untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_http.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
