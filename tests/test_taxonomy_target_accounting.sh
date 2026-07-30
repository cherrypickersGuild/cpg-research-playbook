#!/usr/bin/env bash
# test_taxonomy_target_accounting.sh — exact target request accounting (S6-6A).
#
# S6-6 reported no target attempt count and said so honestly: the committed
# TargetFetchOutcome discarded the client's accounting, and pool.accounting() sums
# self.sources, which only the source path populates. This checkpoint makes the
# number reachable, and this suite defends the four ways it could become a lie:
#
#   * A RECONSTRUCTED COUNT. Only the counters HttpClient incremented at the moment
#     each event occurred are honest. A formula, a client.stats delta, or a
#     re-derivation from redirect hops all produce a plausible number that is wrong
#     under exactly the conditions anyone would want it for.
#   * A DOUBLE COUNT. One canonical identity is fetched once per run and its outcome
#     reaches every record owning it. The sum runs over the run-scoped MAP, so a URL
#     accepted in two cells or under two topics contributes once — and a test proves
#     that summing per record instead would report two.
#   * THE TWO KEY SPACES MERGING. http_attempts has always meant source attempts, it
#     still does, and no combined total exists — the schema refuses one.
#   * OMISSION AND ZERO COLLAPSING. "Fetched no target page" and "does not report
#     target accounting" are different facts; the None sentinel keeps them apart.
#
# Also asserted: pool.py and httpclient.py are byte-unchanged, which is the audit's
# central finding rather than an incidental property — every fact needed was already
# frozen onto the objects targetfetch holds.
#
# Offline: stub clients for the unit cases, the committed fixture opener into an
# injected temp root for the integrated run. No socket, no live request. Asserts
# production state/ and config/ are untouched AND that the repository's own runtime
# paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_accounting.py' -v
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
