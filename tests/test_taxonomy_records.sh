#!/usr/bin/env bash
# test_taxonomy_records.sh — in-memory record construction and schema validation (S4-5B).
#
# Four failures this is designed to catch, each of which would put a malformed
# or misleading row into a published artifact:
#   * a cases__domain-applications full record built WITHOUT case_facets, or a
#     research-and-models / discourse record built WITH them — the schema's two
#     conditionals, which only bind inside the full-record branch;
#   * a cross_reference carrying a full-record field, which would let a
#     duplicate be counted as independent content in a second category;
#   * a facet payload moving record_id, content_id, identity_url or cell_id —
#     identity comes from urlkey, which never reads a facet;
#   * artifact order depending on the order cells finished in rather than on
#     (topic, primary_category, record_id).
#
# Offline and in-memory: no network, no fixtures, no CandidatePool, and nothing
# is written — no artifact, manifest, ledger or rejection file. Asserts state/
# and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_records_build.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
