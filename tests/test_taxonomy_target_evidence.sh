#!/usr/bin/env bash
# test_taxonomy_target_evidence.sh — observed evidence on full records (S6-5).
#
# This is the checkpoint where a Stage 6 mistake becomes PERSISTED. Up to here a
# wrong answer lived in memory; from here it is written into a record that later
# stages read and `promote` may publish. Six failures this suite is designed to
# catch, each of which writes a false claim that nothing downstream can detect:
#   * a record claiming `fetched` when the fetch failed, or `not_checked` when it
#     succeeded. Either makes access_status worthless as evidence — and it is the
#     field the whole publication gate is built on;
#   * a fetch changing something it has no business changing. If a score, a
#     category, a facet payload or an identity moves between a fetch and a no-fetch
#     run, the fetch re-judged the item, which Stage 6 forbids outright. The suite
#     enumerates the difference set and requires it to be EXACTLY the six evidence
#     fields;
#   * a cross_reference row growing its own target evidence. It is a pointer at a
#     full record in another cell, so giving it an independent access_status invents
#     a second opinion about one page;
#   * a malformed alias reaching a written artifact. An alias asserts that two URLs
#     are the same resource, so a bad one is a destructive claim; it must be refused
#     BEFORE the record is assembled, not caught by the schema afterwards;
#   * alias order or duplication varying between runs, which puts a moving field
#     into an artifact whose bytes are compared;
#   * `updated_at` being promoted from a Last-Modified header (CF-17), which would
#     assert a content update nobody observed and disagree with a freshness score
#     computed before the fetch.
#
# `make_full_record` remains the SOLE owner of the persistent record shape: the
# D6-A `url_aliases` parameter is validated, projected, deduplicated and ordered
# there, and `run_cells.py` passes aliases in rather than mutating a completed
# record dict. Omitting the argument still yields `"url_aliases": []`, so every
# committed caller is unaffected.
#
# Deliberately NOT here: alias-conflict artifacts and their schema,
# `alias_conflicts_count` reporting, target HTTP-attempt accounting, `config.enrich`
# and the positive eligibility-completion proof — all S6-6. Robots evidence stays
# unwired (`canonical_robots_allowed=None`), so no canonical_tag alias forms; a test
# pins that, so the day it is wired the change is visible rather than silent.
#
# Offline: the projection tests use stub outcomes, and the one integrated run uses
# the committed fixture opener into an injected temp root. Asserts production state/
# and config/ are untouched AND that the repository's own runtime paths were never
# created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_evidence.py' -v
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
