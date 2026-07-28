#!/usr/bin/env bash
# test_taxonomy_facets.sh — the facet vocabularies and their generated constraints.
#
# Two failures this is designed to catch, both of which would otherwise surface
# only after a published artifact was already wrong:
#   * the generated constraint schema drifting from the vocabularies that are
#     supposed to be its single source of truth (including a hand edit);
#   * a malformed file in schemas/harvest/, which src/harvest/schema.py loads
#     WHOLESALE into one cached registry — so it would break every suite, not
#     just this one.
#
# Offline, no network, no production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_facets.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
