#!/usr/bin/env bash
# test_taxonomy_target_fixtures.sh — the S6-1 target fixture corpus (Stage 6).
#
# Stage 5 closed with every record honestly unverified, because no target page
# could be fetched: there were no target fixtures. This is that corpus, plus the
# loader that serves it and the checker that keeps it honest. Six failures this is
# designed to catch, each of which would let a later Stage 6 suite pass while
# proving nothing:
#   * a fixture silently shadowing another because sources and targets were kept
#     in two URL indexes that could disagree about who owns a URL;
#   * a malformed or dishonestly-labelled fixture loading anyway and being served
#     as some default, so the test above it exercises a page nobody authored;
#   * an undeclared file in targets/ being treated as authorized — precisely what
#     a directory-glob authorization allowed before it was replaced by a literal
#     declared set in the checker;
#   * a transport-simulation directive (`raise`, `responses`, `delay`, a generated
#     oversized body) creeping into the fixture format, which would move retry,
#     timeout and body-cap semantics out of HttpClient, where they are actually
#     tested, and into a second HTTP implementation;
#   * the manifest drifting from the bytes on disk, making "verified fixtures" a
#     claim about nothing;
#   * a robots-denied URL being fetched anyway, with the denial recorded after the
#     request instead of before it.
#
# Deliberately NOT here, because they belong to later checkpoints or to already
# committed contracts: HttpError-to-access_status mapping (S6-2), canonical and
# alias adjudication (S6-3), fetch ownership (S6-4), target-derived record
# evidence (S6-5), publication eligibility (S6-6), and retry sequencing, timeout
# enforcement and the body cap, all of which are HttpClient's and are covered by
# tests/test_taxonomy_http.sh. HttpClient appears here only as a compatibility
# harness proving a target fixture is indistinguishable from a source fixture to
# everything above the opener.
#
# Offline and temp-rooted: no network, no concurrency, no artifact. Asserts
# production state/ and config/ are untouched AND that the repository's own
# runtime paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_fixtures.py' -v
EC=$?

python scripts/harvest/check_fixtures.py || EC=1

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
