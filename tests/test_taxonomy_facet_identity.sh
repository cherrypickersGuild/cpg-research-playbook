#!/usr/bin/env bash
# test_taxonomy_facet_identity.sh — facets must be invisible to identity.
#
# The failure this is designed to catch: a facet edit moving record_id,
# content_id, identity_url, cell_id or a published filename. A facet is an
# editorial judgement that gets revised; an identity is permanent. If revising a
# classification renamed an artifact, it would orphan that artifact's history.
#
# Proved twice: structurally (recompute across four kinds of facet edit) and
# statically (urlkey.py and slug.py must not mention facets at all).
#
# Offline, no network, no production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_facet_identity.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
