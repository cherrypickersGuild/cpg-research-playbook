#!/usr/bin/env bash
# test_taxonomy_target_ownership.sh — target-fetch ownership and bounds (S6-4).
#
# S6-2 could fetch one page; S6-3 could adjudicate one outcome. This is the
# checkpoint that decides WHO fetches WHAT, HOW OFTEN, and within which bounds —
# and every failure it guards against is invisible from a green healthy-path run:
#   * one canonical target fetched more than once. Two cells, or two topics, that
#     surface the same URL must produce ONE request. A second double-charges the
#     committed budget, doubles the load on somebody else's server, and turns the
#     target_fetch_owners count into a fiction;
#   * a rejected candidate being fetched. The committed gate already rejected it on
#     metadata, so the fetch can change nothing — and re-deciding afterwards is the
#     re-judging Stage 6 forbids outright;
#   * fetching continuing after the budget is spent, where each further call
#     re-charges an exhausted budget to discover the same thing;
#   * a run becoming publication-eligible merely because ONE target-fetch owner was
#     acquired, while every record still says nobody checked it. That is the
#     ordering defect this checkpoint surfaced: the owner count goes non-zero here,
#     but the guard that made it insufficient was two checkpoints away. The guard
#     was brought forward, and it is asserted here in both directions;
#   * fetch order depending on iteration accident rather than content, which would
#     make which identity wins the fetch irreproducible.
#
# Ownership is proved with TEST-LOCAL SYNTHETIC candidates over a real
# CandidatePool. A shared identity is a property of what the feeds surfaced, and no
# target-page fixture can manufacture one — so no source fixture and no topic config
# is read, added or modified. The committed Stage 4 dedupe contract is NOT reopened:
# this asserts only the Stage 6 fact that one identity buys one fetch whose outcome
# reaches every owner.
#
# Sequential by construction — no thread, process, lock or async anywhere in the
# fetch phase — so pool.acquire_target_fetch keeps exactly one caller and CF-1
# stays untriggered. Offline: the injected client is a call-counting stub, and the
# one integrated run uses the committed fixture opener into a temp root. Asserts
# production state/ and config/ are untouched AND that the repository's own runtime
# paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_ownership.py' -v
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
