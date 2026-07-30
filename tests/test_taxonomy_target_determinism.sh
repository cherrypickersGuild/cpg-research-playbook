#!/usr/bin/env bash
# test_taxonomy_target_determinism.sh — determinism, failure modes, partial runs (S6-7).
#
# Stage 6 added the first thing in this pipeline that reads a page. This suite asks
# the only questions that matter once it does, and each one names a failure that a
# green healthy-path run cannot show you:
#
#   * BYTES THAT MOVE ON THEIR OWN. Two equivalent runs must be byte-identical
#     across all 43 files, and two runs at different instants must differ at an
#     ENUMERATED set of leaves. Enumeration rather than normalization, because a
#     normalizer forgives every field it was not told about.
#   * ORDER LEAKING INTO OUTPUT. Cell, source and candidate order are each shuffled
#     non-vacuously; if any of them can change a byte, the artifacts are a function
#     of scheduling rather than of content.
#   * A FAILURE MODE THAT CORRUPTS THE RUN AROUND IT. 404, 410, 403, a terminal
#     500, an empty body, a non-HTML body, permanent and temporary redirects and
#     three contradictory canonicals each produce a complete, valid, honest record.
#   * A HALF-WRITTEN TREE. An interruption during the fetch phase publishes nothing
#     at all; the retry is an ordinary fresh run, because there is no resume.
#   * A CLAIM THE RUN CANNOT SUPPORT. One identity is counted once, a budget-skipped
#     target costs zero, observed failures keep a run eligible, and a target nobody
#     checked does not.
#
# Scenario corpora are COPIES of the committed fixture tree with target-fixture
# content substituted in the copy. No committed fixture, source fixture, topic
# configuration or production module is touched, and a test asserts the repository
# corpus is unchanged afterwards.
#
# DELIBERATELY NOT HERE:
#   * transport simulation — timeout sequencing, a 500 -> 200 retry transition and
#     an over-cap body belong to the committed HttpClient and are tested in
#     tests/test_taxonomy_http.sh (plan §5.0, §14 E15). No retry count is asserted,
#     only the DV-8 accounting identity that holds whatever the client did;
#   * a run-level robots_denied. All four accepted targets and the source feed that
#     surfaces them share github.com, so denying that host stops discovery before a
#     record exists. RobotsDenied -> robots_denied stays owned by
#     tests/test_taxonomy_target_fetch.sh and by fixture #20, whose contract is that
#     it is never opened at all.
#
# Offline: the committed FixtureOpener over temp trees, into injected temp roots.
# Asserts production state/ and config/ are untouched AND that the repository's own
# runtime paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_target_determinism.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/ tests/fixtures/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/, config/ or the fixture corpus was modified:" >&2
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
