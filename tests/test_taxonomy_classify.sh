#!/usr/bin/env bash
# test_taxonomy_classify.sh — the ten committed precedence rules (S4-3).
#
# Three failures this is designed to catch, each of which would put a record in
# the wrong published category with a confident-looking rationale:
#   * rule ORDER drifting, so an eval-bearing paper lands in Papers instead of
#     Benchmark & Datasets, or a model release is filed as commentary;
#   * a `none_of` exclusion quietly weakening, so a developer tool is
#     reclassified into Product Discovery instead of being kept out of it;
#   * a lane name, a source request key or an ownership designation becoming
#     evidence — a gap lane looking for healthcare cases must not label a
#     document healthcare because the lane was named that.
#
# The rules are read from config/harvest/precedence.v1.json as DATA; a test
# asserts no rule_id and no signal name is hard-coded in the evaluator.
#
# Offline: no network, no model call, no fixtures, no CandidatePool, no scoring,
# no facets, no records. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_classify.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
