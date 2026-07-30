#!/usr/bin/env bash
# test_taxonomy_migration.sh — Stage 7 migration. At S7-1: the entity assessment.
#
# The entity registry is NOT migrated, and this suite is what keeps that a fact
# rather than a promise. Six failures it is designed to catch, each of which
# would put a wrong number in front of the person making the product decision:
#   * a malformed row being skipped. Every count in the document would be wrong
#     by an unknown amount and nothing would say so — so a bad top level, a bad
#     row, an unrecognised field or a bad `discovery` block all RAISE, and the
#     suite proves each one does;
#   * a subtotal that does not reconcile. Topic, entity type, topic x type and
#     description source each sum to the population AND are compared against the
#     registry's own `metadata`, with a dropped row and a moved row proved to
#     break the reconciliation rather than pass it;
#   * bytes that depend on input order. Row order in a merged registry is an
#     artefact of merging, so reversal and three seeded shuffles must all render
#     the identical document; each reordering is asserted to be non-vacuous;
#   * a committed document that has drifted from the code that generates it. The
#     document is generated, never hand-edited, and the suite compares the
#     committed bytes with a fresh render;
#   * a claim that entities were migrated. Zero is structural: the module carries
#     no record builder, no artifact writer and no network import, and the suite
#     asserts that from the source rather than trusting the prose;
#   * the protected source being touched. `state/entity_registry.json` is one of
#     the 18 protected files; its SHA-256 is compared before and after.
#
# Identity is the finding this checkpoint exists to measure, so the duplicate and
# repeated-identifier maths is recomputed a second, differently-written way in
# the test — a shared helper cannot make both agree on the same mistake — and is
# checked again against a synthetic corpus with hand-known answers.
#
# Later Stage 7 checkpoints EXTEND this wrapper; it is not replaced. It runs
# whatever `tests/harvest/test_migration.py` currently holds, so S7-2 onwards add
# tests without touching the runner.
#
# Offline: no socket, no clock, no network. The only write goes to an injected
# temporary directory. Asserts production state/ and config/ are untouched AND
# that the repository's own runtime artifact paths were never created.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_migration.py' -v
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
