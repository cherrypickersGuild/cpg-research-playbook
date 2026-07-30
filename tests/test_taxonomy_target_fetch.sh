#!/usr/bin/env bash
# test_taxonomy_target_fetch.sh — one target fetch and the error mapping (S6-2).
#
# S6-1 built the corpus. This is the first Stage 6 module that turns a fetch into
# a fact. Seven failures it is designed to catch, each of which would either put a
# false claim on a record or quietly relocate transport semantics:
#   * a failure mapped to the wrong access_status. "not_found" on a page that was
#     merely rate-limited is a false statement about a URL, and nothing downstream
#     could ever detect it;
#   * an unmapped HttpError subclass being handed the nearest plausible status.
#     The hierarchy is enumerated from httpclient.py's AST and each class is then
#     instantiated and exercised, so a tenth subclass fails HERE and not on a live
#     run;
#   * a second retry, redirect, timeout or response-size opinion growing in this
#     module and disagreeing with the client that actually owns them;
#   * more than one logical client call per fetch, which would make the budget
#     accounting and the Stage 6 ownership counts wrong;
#   * a system-clock read, which would make last_checked_at nondeterministic and
#     break the byte determinism of every artifact that carries it;
#   * a traceback, repr or object address reaching a persisted field;
#   * an interruption being swallowed by a broad except, so a Ctrl-C during a
#     fetch phase would be absorbed into a record instead of stopping the run.
#
# The injected client is a STUB, deliberately: raising a typed error from a stub is
# the whole of this module's failure surface, and routing it through a fixture
# would prove HttpClient's behaviour rather than this module's. Retry sequencing,
# robots decisions, redirect following, timeout mechanics, response-size mechanics
# and socket behaviour all belong to the committed HttpClient and are covered by
# tests/test_taxonomy_http.sh; not one of them is re-asserted here.
#
# Offline by construction: this module has no network path at all — a test asserts
# the token "socket" does not appear in it, and no HttpClient is ever constructed.
# Asserts production state/ and config/ are untouched AND that the repository's own
# runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_fetch.py' -v
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
