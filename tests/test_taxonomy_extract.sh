#!/usr/bin/env bash
# test_taxonomy_extract.sh — deterministic metadata normalization (S4-2).
#
# Three failures this is designed to catch, each of which would otherwise surface
# only as a confident-looking wrong value in a published record:
#   * an unparseable publisher date silently becoming a fabricated timestamp,
#     which turns the freshness score into a fiction;
#   * "metadata normalization" quietly acquiring body-extraction semantics and
#     claiming a target-fetch or extraction owner that never existed;
#   * a conflicting title or publisher resolved and then discarded, losing
#     evidence no later step can recover.
#
# Offline and in-memory: no network, no fixtures, no CandidatePool, no records
# built. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_extract.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
