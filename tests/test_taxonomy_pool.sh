#!/usr/bin/env bash
# test_taxonomy_pool.sh — request keys, shared snapshots, ownership accounting.
#
# Three failures this is designed to catch:
#   * a source_request_key that is unstable across runs, or blind to something
#     that genuinely changes the request — the canonicalization config version in
#     particular, without which a config bump silently changes every key;
#   * a source revalidated MID-RUN, which would make output depend on when a
#     round happened to execute, so two runs over identical inputs could diverge;
#   * logical ownership conflated with HTTP attempts — a redirect hop plus a
#     retry is three attempts of ONE logical fetch, not three fetches.
#
# Fully offline: results are injected, there is no adapter and no network. That
# is what lets determinism under shuffled lane ordering be proved before Stage 3
# exists.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_pool.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
