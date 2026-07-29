#!/usr/bin/env bash
# test_taxonomy_verify.sh — the four committed scores and the accept/reject gate.
#
# Three failures this is designed to catch, each of which would put a confident
# number on a record that has not earned it:
#   * a missing publication date scored as 0.0 freshness, which silently
#     penalises every item whose feed omits a date instead of reporting null;
#   * a weight or threshold restated in Python, so tuning policy.v1.json stops
#     changing what is accepted;
#   * a verdict claiming fetch evidence — access_status "ok", an http_status, a
#     content_hash — when Stage 4 fetches nothing at all.
#
# Every number comes from config/harvest/policy.v1.json; the composite is checked
# against a hand-computed weighted mean so module and config cannot disagree.
#
# Offline and in-memory: no network, no fixtures, no CandidatePool, no facets,
# no records, no file writes. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_verify.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
