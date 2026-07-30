#!/usr/bin/env bash
# test_taxonomy_recovery.sh — recovery and re-run semantics (S5-7).
#
# S5-6 proved a healthy run. This proves the unhealthy ones, by actually breaking
# `os.replace`, `os.unlink` and the pointer write rather than by reading the code.
# Five failures this is designed to catch, each of which makes the artifact tree
# untrustworthy in a way a green healthy-path suite would never notice:
#   * a half-written artifact becoming readable. Interrupt anywhere — before a
#     rename, part-way through, with an OSError or a KeyboardInterrupt — and every
#     file on disk must still be a complete, schema-valid artifact;
#   * the pointer outliving its manifest. LATEST_RUN_ID names a run whose manifest
#     exists and validates, or it names nothing. A run that dies after its
#     manifest but before the pointer leaves the pointer on the PREVIOUS run;
#   * a sweeper that deletes by pattern. Ownership is proved by having watched the
#     write, so a foreign .tmp_* is left alone — globbing and deleting would
#     destroy another writer's in-flight file;
#   * a finished run being repeated. A run_id that already has a manifest is
#     refused BEFORE the first byte, so the refusal cannot double-count the
#     cross-run ledger or replace a rejection log;
#   * a second run silently re-judging. Over unchanged inputs it must reproduce
#     every identity, classification and score; only the run id and the
#     clock-derived fields may move, and the suite enumerates that difference set
#     rather than normalizing it away.
#
# The interruption injection is scoped to renames under the artifact root on
# purpose: HttpClient's domain leases are written atomically too, and an unscoped
# counter would spend its budget on lease files and kill the run before it ever
# wrote an artifact — passing while proving nothing.
#
# S5-1's atomicity internals and S5-6's healthy-path drive are reused, not
# re-proved. Offline and temp-rooted: no network, no concurrency. Asserts state/
# and config/ are untouched AND that the repository's own runtime artifact paths
# were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_recovery.py' -v
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
