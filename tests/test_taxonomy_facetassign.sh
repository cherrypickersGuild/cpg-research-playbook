#!/usr/bin/env bash
# test_taxonomy_facetassign.sh — deterministic case_facets assignment (S4-5A).
#
# Three failures this is designed to catch, each of which would put an
# unearned label on a published record:
#   * an industry inferred from the PUBLISHER — a vendor-published customer
#     story must take the customer's industry, never the vendor's, and
#     technology-software must not be earned from the URL the page sits on;
#   * two equally-supported industries silently resolved to whichever sorts
#     first, manufacturing a finding out of a genuine ambiguity;
#   * a forbidden topic handed an empty payload instead of an explicit
#     not-applicable, which reporting_state would then count as `unresolved`
#     rather than `not_enriched`.
#
# Vocabulary-driven: terms are read from config/harvest/facets/ rather than
# typed into the tests, and a test asserts no slug or term is hard-coded in the
# assigner.
#
# Offline and in-memory: no network, no fixtures, no CandidatePool, no records
# built, no file writes. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_facetassign.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
