#!/usr/bin/env bash
# test_ledger_patch_merge.sh — regression test for the ledger-patch merge jq
# expression shared by run_stage1.sh and discover.sh.
#
# The expression applies each ledger_patch entry onto the matching visited-URL
# ledger row (by url). An earlier form scoped `. as $e` INSIDE `(... ) as $u`,
# so `$e` was undefined at `$e + $u` — a jq COMPILE error. Under the
# `jq ... && mv` idiom (set -e) that compile error was swallowed, so the patch
# merge silently did nothing: extracted/case_ids/entity_extracted/entity_ids
# were never applied. The corrected form (already proven in harvest_entities.sh)
# keeps `. as $e |` at the top level of the pipe.
#
# OFFLINE: jq + temp fixtures only. No claude, no scripts driven, no git writes,
# no production state/.
#
#   Usage: bash tests/test_ledger_patch_merge.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap '[ -n "${TMPDIR:-}" ] && rm -rf "$TMPDIR"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()      { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_nonzero() { if [ "$2" -ne 0 ]; then ok "$1 (exit $2)"; else bad "$1 (expected non-zero, got 0)"; fi; }

# The corrected expression (must match run_stage1.sh / discover.sh).
CORRECT='(.[1].ledger_patch // []) as $p
  | {ledger: [ .[0].ledger[] | . as $e | (($p[] | select(.url==$e.url)) // {}) as $u | $e + $u ]}'
# The old buggy expression (kept only to prove it fails to compile).
BUGGY='(.[1].ledger_patch // []) as $p
  | {ledger: [ .[0].ledger[] | (. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u | $e + $u ]}'

LEDGER="$TMPDIR/ledger.json"
cat > "$LEDGER" <<'EOF'
{"ledger":[
  {"url":"https://ex.com/u1","url_type":"news_url","extracted":false,"case_ids":[],"entity_extracted":false,"entity_ids":[]},
  {"url":"https://ex.com/u2","url_type":"news_url","extracted":false,"case_ids":[],"entity_extracted":false,"entity_ids":[]}
]}
EOF
cat > "$TMPDIR/patch_1c.json" <<'EOF'
{"cases":[],"ledger_patch":[{"url":"https://ex.com/u1","extracted":true,"case_ids":["case-1"]}]}
EOF
cat > "$TMPDIR/patch_1g.json" <<'EOF'
{"entities":[],"ledger_patch":[{"url":"https://ex.com/u1","entity_extracted":true,"entity_ids":["ent-1"]}]}
EOF
cat > "$TMPDIR/patch_bad.json" <<'EOF'
{"ledger_patch":[123]}
EOF

# ---------------------------------------------------------------------------
echo "[compile] the buggy form fails to compile; the corrected form runs"
jq -s "$BUGGY" "$LEDGER" "$TMPDIR/patch_1c.json" >/dev/null 2>&1; assert_nonzero "buggy expr is a jq compile error" "$?"
jq -s "$CORRECT" "$LEDGER" "$TMPDIR/patch_1c.json" >/dev/null 2>&1; assert_eq "corrected expr runs (exit 0)" "0" "$?"

# ---------------------------------------------------------------------------
echo "[1C patch] extracted + case_ids are actually applied to the matching row"
out="$(jq -s "$CORRECT" "$LEDGER" "$TMPDIR/patch_1c.json")"
assert_eq "u1.extracted -> true"          "true"   "$(printf '%s' "$out" | jq -c '.ledger[0].extracted')"
assert_eq "u1.case_ids -> [case-1]"       '["case-1"]' "$(printf '%s' "$out" | jq -c '.ledger[0].case_ids')"
assert_eq "u2 (unmatched) extracted stays false" "false" "$(printf '%s' "$out" | jq -c '.ledger[1].extracted')"

echo "[1G patch] entity_extracted + entity_ids are actually applied to the matching row"
out="$(jq -s "$CORRECT" "$LEDGER" "$TMPDIR/patch_1g.json")"
assert_eq "u1.entity_extracted -> true"   "true"   "$(printf '%s' "$out" | jq -c '.ledger[0].entity_extracted')"
assert_eq "u1.entity_ids -> [ent-1]"      '["ent-1"]' "$(printf '%s' "$out" | jq -c '.ledger[0].entity_ids')"

# ---------------------------------------------------------------------------
echo "[failure] a malformed patch makes the merge fail, canonical ledger untouched"
before="$(cat "$LEDGER")"
jq -s "$CORRECT" "$LEDGER" "$TMPDIR/patch_bad.json" > "$TMPDIR/out.tmp" 2>/dev/null; ec=$?
after="$(cat "$LEDGER")"
assert_nonzero "corrected expr fails on a non-object patch entry" "$ec"
assert_eq "canonical ledger byte-for-byte unchanged" "$before" "$after"
if jq empty "$LEDGER" 2>/dev/null; then ok "canonical ledger still valid JSON"; else bad "ledger corrupted"; fi

# ---------------------------------------------------------------------------
echo "[scripts] run_stage1.sh and discover.sh use the corrected form, not the buggy one"
for f in scripts/run_stage1.sh scripts/discover.sh; do
  good="$(grep -cF '. as $e | (($p[] | select(.url==$e.url)) // {}) as $u | $e + $u' "$ROOT/$f")"
  buggy="$(grep -cF '(. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u' "$ROOT/$f")"
  assert_eq "$f uses corrected form (2x)" "2" "$good"
  assert_eq "$f has no buggy form (0x)"   "0" "$buggy"
done

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
