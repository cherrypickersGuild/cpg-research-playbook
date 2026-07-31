#!/usr/bin/env bash
# test_taxonomy_preflight.sh — the configured-source preflight (S9-2).
#
# S9-2 assembles rows over the committed `HttpClient.preflight()`, which is
# byte-unchanged. Six failures this suite is designed to catch:
#   * a shorter run than the caller thinks — unrestricted selection must resolve
#     exactly the 25 configured sources, each probed exactly once, and an
#     unknown, empty or duplicated id must be refused BEFORE any request, proved
#     by counting probes after the refusal;
#   * a dropped failure. A dead source is a ROW with its committed reason and
#     every other source is still probed, so "25 rows all ok" can never be
#     confused with "3 rows all ok";
#   * a row the schema would refuse — every row is validated against the
#     COMMITTED run_manifest.v1.json source_preflight[] item, read from the
#     schema file rather than retyped, `additionalProperties: false` included;
#   * a second HTTP or robots implementation. The real client is driven against
#     a test-owned loopback server, and httpclient.py is asserted byte-identical
#     to fddbbb7;
#   * retained state. No --state-root is accepted, and the one temporary lease
#     root the command owns is removed on success, on a reported source failure
#     and on an injected interruption;
#   * an outbound request. A socket-level guard refuses any non-loopback host and
#     is proved wired by tripping it deliberately.
#
# Loopback traffic this suite owns is allowed. OUTBOUND TRAFFIC IS NOT, and
# S9-2 has never contacted a configured source — that is S9-L1, still unapproved.
#
# Offline and temp-rooted: every byte lands under a directory this suite removes.
# Asserts state/ and config/ are untouched, that the repository's four runtime
# paths were never created, and that no retained external Stage 9 root is left.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_preflight.py' -v
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

# E9-5: the transient lease root is infrastructure scratch and is removed on
# every exit path. A retained external Stage 9 state root is a different thing
# entirely, and S9-2 selects none and creates none.
if [ -e "../stage9" ] || [ -e "./stage9" ]; then
  echo "FAIL - a retained external Stage 9 state root was created; S9-2 selects" >&2
  echo "       no such path and must create nothing." >&2
  exit 1
fi

exit "$EC"
