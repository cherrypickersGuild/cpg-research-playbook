#!/usr/bin/env bash
# test_taxonomy_source_cache.sh — the run-scoped source fetch cache.
#
# Three failures this is designed to catch, each of which would otherwise show up
# only as corrupt output after a real harvest:
#   * N lanes racing one source_request_key issuing N real HTTP requests, which
#     turns one slow or failing source into N of them;
#   * a failed fetch leaving a half-built CandidatePool source row, which
#     serializes to a schema-invalid artifact (five errors: source_id,
#     normalized_url, established_by and established_at all null);
#   * a waiter released before the complete pool row exists, so it reads a
#     snapshot that is not there yet.
#
# Threads and events, never sleeps-as-synchronization. Offline, no network, no
# production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_source_cache.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
