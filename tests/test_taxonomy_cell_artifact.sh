#!/usr/bin/env bash
# test_taxonomy_cell_artifact.sh — cell and topic artifact contents (S5-2).
#
# Four failures this is designed to catch, each of which would put a misleading
# artifact in front of a reader who cannot see the records that built it:
#   * record order depending on arrival rather than on (topic, primary_category,
#     record_id), which would make two runs over the same input differ;
#   * a metadata count disagreeing with the records beside it, because a caller
#     was allowed to supply a number the artifact should have derived;
#   * a cross_reference counted as independent content, inflating a category's
#     coverage with a pointer;
#   * the same identity appearing twice in one topic artifact, or a record the
#     record schema rejects being swallowed into an artifact instead of refused.
#
# S5-1 already proves the writer is atomic and validate-before-write; those
# guarantees are reused here rather than re-proved.
#
# Offline and temp-rooted: no network, no fixtures, no CandidatePool, no cell
# execution. Asserts state/ and config/ are untouched AND that the repository's
# own runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_cell_artifact.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

for LEAK in state/taxonomy_harvest data/harvested runs; do
  if [ -e "$LEAK" ]; then
    echo "FAIL - this test created the real runtime path '$LEAK'; writes must" >&2
    echo "       stay under an injected temp root." >&2
    exit 1
  fi
done

exit "$EC"
