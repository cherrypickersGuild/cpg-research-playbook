#!/usr/bin/env bash
# test_taxonomy_dedupe.sh — deterministic candidate ingest and same-topic dedupe.
#
# Three failures this is designed to catch, each of which would otherwise surface
# only as wrong numbers in a finished artifact:
#   * three lanes sharing one cached source counted as three observations, which
#     triples every duplicate metric and misattributes provenance;
#   * output that depends on delivery, source, candidate or lane order, which
#     makes two runs over identical inputs disagree;
#   * a conflicting title or publisher silently discarded, which loses evidence
#     no later step can recover.
#
# Offline and in-memory: no network, no CandidatePool, no records, no fixtures.
# Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_dedupe.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
