#!/usr/bin/env bash
# test_taxonomy_eligibility.sh — alias conflicts and the §8 eligibility proof (S6-6).
#
# Two claims get defended here, and a reader trusts both without re-deriving them:
#   * THE CONFLICT ARTIFACT is the record of merges that were REFUSED. A conflict
#     says two URLs were not treated as one resource, and why. Six ways that record
#     could become untrustworthy are pinned: a count that disagrees with its own
#     rows; ordering that wanders between runs; a positional conflict_id, so the
#     same contradiction gets a different id each run; a malformed row reaching
#     disk; an uncommitted reason slipping past the schema; and an empty set being
#     OMITTED rather than written, which would make "this run found none"
#     indistinguishable from "nobody looked".
#   * ELIGIBILITY decides whether a run may ever be published, so §8's predicate is
#     proved in BOTH directions: true only when all four clauses hold, and false for
#     each clause failing on its own, with the committed priority between them. It
#     is derived from run facts alone — a cross_reference pointer cannot manufacture
#     a missing-evidence finding, and neither the existence nor the size of the
#     conflict artifact can move it either way.
#
# S6-6 adds NO eligibility predicate. It proves the one S6-4 brought forward, routes
# conflicts S6-3 already adjudicated, and reports a count read back from the
# validated artifact rather than carried beside it — so the manifest and the
# artifact cannot drift.
#
# Deliberately NOT here: alias adjudication itself (every §4 row belongs to
# tests/test_taxonomy_aliases.sh) and the exact target HTTP-attempt values, which
# belong to S6-6A and tests/test_taxonomy_target_accounting.sh. S6-6 could not
# derive them at all — the committed TargetFetchOutcome carried no accounting and
# pool.accounting() structurally cannot see a target fetch — so what this suite
# keeps is the BOUNDARY: `http_attempts` still means source attempts and only
# source attempts, the target counters are their own separate keys, and no
# combined total is reported, because folding the two key spaces together is what
# plan §2 forbids.
#
# Offline: no network path is involved, and the one integrated run uses the
# committed fixture opener into an injected temp root. Asserts production state/ and
# config/ are untouched AND that the repository's own runtime paths were never
# created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_eligibility.py' -v
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
