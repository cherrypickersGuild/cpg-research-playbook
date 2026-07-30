#!/usr/bin/env bash
# test_taxonomy_migration.sh — Stage 7 migration: the entity assessment (S7-1),
# the suspicious-URL guard (S7-2) and the in-memory AX mapping (S7-3).
# 133 assertions, 43 + 28 + 62.
#
# --- S7-3, the AX mapping ----------------------------------------------------
# This is where a legacy row becomes a record a later stage may publish, so the
# failures worth pinning are the ones that would persist a FALSE CLAIM:
#   * a record claiming evidence nobody gathered. Migration issues no request, so
#     every record is asserted `not_checked` with null http_status, content_hash
#     and last_checked_at, `canonical_url == identity_url`, empty aliases, and
#     `snippet_only` — never `fetched`, whatever the legacy row called itself;
#   * an invented identity. Identity is URL-derived through the committed urlkey
#     helpers; the corpus's 126 distinct `case_id`s over 231 rows are proved NOT
#     to collapse anything, and two rows sharing a URL fail loudly rather than
#     being merged away;
#   * a clock. `harvest_run_id` and `migrated_at` are required inputs and
#     `discovered_at` is always supplied, so `make_full_record` can never reach
#     its fallback; an AST test proves the module calls no clock at all;
#   * a facet inferred from prose. Business function and use-case arrays stay
#     empty with explicit insufficiency entries, and the corpus's reporting
#     states are pinned at exactly 112 facet_partial / 118 unmapped_legacy_value
#     / 1 unresolved — the E27 case records its reviewed mapping instead of
#     asserting it;
#   * a mutation crossing the boundary. Mapping cannot change the registry,
#     changing the registry afterwards cannot change a finished record, and
#     changing one record cannot reach another;
#   * a moving field. Two mappings differing only in run id and migration instant
#     are diffed recursively, and exactly two leaves may move.
# Every accepted record is validated against `record.v1.json` inside the mapper
# and against the committed `check_facets.py` here.
#
# --- S7-2, the guard ---------------------------------------------------------
# The guard decides whether a legacy case page is refused, so the failures that
# matter are the ones that would refuse a legitimate page or admit an index one:
#   * substring matching creeping back in. Read as substrings, the master plan's
#     wording refuses five real pages in the protected corpus — four
#     `cloud.google.com` posts caught by `google.`, and one LinkedIn article
#     whose path merely contains a `/search/` segment (erratum E24). Both are
#     pinned as negative controls, with `research.example.com`, `/feeds/`,
#     `/tags/`, `?faq=` and a query VALUE containing a search token beside them;
#   * a rule that cannot fire. Each of the four has several positive examples, so
#     "0 of 231" is a finding about the corpus rather than a guard that never
#     worked — and the 231-case test runs fabricated positives through the same
#     loop to prove exactly that;
#   * unstable precedence. A URL matching two rules is always reported under the
#     first in the committed order, pinned in both directions;
#   * a malformed input filed under a suspicious rule. "Not a URL" and "a search
#     page" are different findings: the first raises, and the guard never
#     prepends a scheme or otherwise repairs the input;
#   * a rewritten URL. `GuardMatch` has no field that could carry one, and the
#     detail text is asserted to contain no URL at all.
# Purity is structural, from the module's own AST: `base.py` imports exactly
# `dataclasses` and `urllib.parse`, executes nothing at import beyond
# definitions, and defines no second canonicalizer or registrable-domain parser.
#
# --- S7-1, the entity assessment ---------------------------------------------
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
# whatever `tests/harvest/test_migration.py` currently holds, so S7-3 onwards add
# tests without touching the runner — S7-2 changed only this description.
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
