#!/usr/bin/env bash
# test_taxonomy_artifacts.sh — deterministic atomic artifact writing (S5-1).
#
# Four failures this is designed to catch, each of which would make the Stage 5
# artifact tree untrustworthy:
#   * bytes that depend on dict insertion order rather than content, which would
#     make every downstream determinism proof decoration;
#   * a crash between write and rename damaging or truncating the artifact that
#     was already there — the reader must see the old file or the new one, never
#     a partial one;
#   * a temp file outliving its write, whether from an error or a Ctrl-C, or a
#     fixed `<file>.tmp` name that two writers would interleave through;
#   * an invalid document reaching disk because it was validated after writing
#     instead of before.
#
# Offline and temp-rooted: no network, no fixtures, no CandidatePool, no records.
# Every write lands in a per-test temp directory. Asserts state/ and config/ are
# untouched AND that the repository's own runtime artifact paths were never
# created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_artifacts.py' -v
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
