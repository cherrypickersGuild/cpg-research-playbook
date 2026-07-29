#!/usr/bin/env bash
# test_taxonomy_adapter_concurrency.sh — many lanes, one logical fetch.
#
# Failures this is designed to catch, none of which a single-threaded test can
# see:
#   * N lanes discovering one source issuing N real requests, turning one slow
#     or failing source into N of them;
#   * a failed source being re-fetched by the next lane in the same run;
#   * the single-fetch guarantee accidentally serializing unrelated sources,
#     which would make a 25-source run as slow as its slowest domain;
#   * a pool document that depends on which worker happened to finish first.
#
# Real threads released by a barrier, not sleeps. Offline: the opener is the
# fixture opener, and every other layer is the shipped code.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_adapter_concurrency.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
