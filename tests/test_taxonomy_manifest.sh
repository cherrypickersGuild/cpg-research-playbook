#!/usr/bin/env bash
# test_taxonomy_manifest.sh — run manifest and LATEST_RUN_ID (S5-5).
#
# The pointer makes one promise: it names a run whose manifest exists and
# validates. Four failures this is designed to catch, each of which breaks it:
#   * the pointer advancing before the manifest is safely on disk, so a crash
#     leaves LATEST_RUN_ID naming a run with no manifest;
#   * an unfinished run (finished_at null) being published, or a finished run
#     being silently overwritten and its history rewritten;
#   * a configured cell omitted instead of recorded as not_run or zero_result,
#     letting a silently skipped cell hide behind a shorter list;
#   * publication_eligible asserted by a caller rather than derived. Stage 5
#     fetches no target page, so every record is unverified and the run is
#     honestly ineligible — a true statement, not a limitation to paper over.
#
# S5-1's atomic-writer internals are reused, not re-proved.
#
# Offline and temp-rooted: no network, no fixtures, no cell execution, no
# concurrency. Asserts state/ and config/ are untouched AND that the
# repository's own runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_manifest.py' -v
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
