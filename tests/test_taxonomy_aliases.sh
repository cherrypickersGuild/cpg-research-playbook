#!/usr/bin/env bash
# test_taxonomy_aliases.sh — redirect and rel=canonical adjudication (S6-3).
#
# This is the Stage 6 module where a bug is IRREVERSIBLE. A wrongly trusted
# canonical merges two records that were genuinely different, and no later step
# can un-merge them; the committed canonicalization policy says so outright, which
# is why its governing principle is to prefer a false negative. Eight failures
# this suite is designed to catch:
#   * an identity moving. identity_url, record_id and content_id must be
#     byte-identical after every row of the section 4 table, INCLUDING every
#     conflict row. Proved with test-local sentinels, because importing record
#     construction to test this module would couple S6-3 to a builder it must
#     never touch;
#   * a chain containing a temporary redirect creating a permanent alias, which
#     would rewrite a preferred URL on evidence the committed client classified as
#     temporary;
#   * permanence inferred from a redirect COUNT rather than from the client's own
#     permanent_redirect flag — three 301s and 301->302->200 both have hops, and
#     only the first may alias;
#   * a cross-registrable-domain canonical being auto-accepted, which is the
#     destructive merge the whole trust tier exists to prevent;
#   * two subdomains of ONE registrable domain being treated as cross-domain. That
#     is the mistake erratum E16 corrected: a second host comparison disagreeing
#     with the committed urlkey.registrable_host, which is the only host authority
#     in this repo;
#   * contradictory evidence crashing instead of being recorded as a conflict, or
#     being silently resolved by picking one of two claims;
#   * a scan cap that reads past its own bound, making extraction cost depend on
#     page weight rather than on the cap;
#   * nondeterministic alias ordering or conflict evidence, which would put a
#     moving field into a persisted record.
#
# Deliberately NOT here: redirect execution, retry attempts, robots mechanics,
# throttling, timeouts and body-size enforcement all belong to the committed
# HttpClient (tests/test_taxonomy_http.sh), and typed-error-to-access_status
# mapping belongs to S6-2 (tests/test_taxonomy_target_fetch.sh). Robots reaches
# this module as an injected VERDICT, never as a check it performs.
#
# Pure and offline by construction: adjudicate() and extract_rel_canonical() take
# explicit inputs only — no network, no socket, no filesystem, no runtime state,
# no HttpClient, no pool, no record construction. The one impure function is the
# cached policy loader, which sits outside both. Asserts production state/ and
# config/ are untouched AND that the repository's own runtime paths were never
# created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_aliases.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

for LEAK in state/taxonomy_harvest data/harvested runs LATEST_RUN_ID; do
  if [ -e "$LEAK" ]; then
    echo "FAIL - this test created the real runtime path '$LEAK'; writes must" >&2
    echo "       stay under an injected temp root." >&2
    exit 1
  fi
done

exit "$EC"
