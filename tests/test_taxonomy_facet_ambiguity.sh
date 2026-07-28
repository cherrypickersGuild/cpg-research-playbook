#!/usr/bin/env bash
# test_taxonomy_facet_ambiguity.sh — the three axes must not blur into each other.
#
# The vocabulary exists because a handful of words mean different things on
# different axes: "finance" is an industry or a function, "legal" is a firm or a
# department, "risk" is who does the work or what the AI solves. Each boundary is
# asserted here so a future vocabulary edit cannot quietly reintroduce the
# ambiguity.
#
# Two traps this deliberately avoids passing vacuously:
#   * disjointness excludes ONLY the named other-unclear sentinel, and the
#     cross-axis rejection test uses a REAL cross-axis slug;
#   * "a conglomerate yields no secondary industry" is proved by requiring each
#     secondary to be lexically supported by quoted evidence, not by asserting an
#     empty list nobody populated.
#
# Offline, no network, no production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_facet_ambiguity.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
