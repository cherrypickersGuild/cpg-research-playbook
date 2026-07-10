#!/usr/bin/env bash
# test_merge_error_propagation.sh — regression test that merge_case_db.sh and
# merge_ax_case_harvest_registry.sh FAIL LOUDLY when their jq step errors,
# instead of the old `jq ... && mv` idiom that (under set -e) skipped the mv but
# still exited 0, falsely reporting success while the master was left unchanged.
# Sibling of tests/test_merge_entity_type_error.sh (entity merge).
#
# Failure trigger: a non-empty but INVALID-JSON batch. The merge scripts only
# check `-s` (non-empty), not `jq empty`, so invalid JSON reaches the main
# `jq -s` transform and forces it to fail — exactly the path the fix guards.
#
# OFFLINE: merge scripts + fixtures only, temp dir, no claude, no git writes,
# no production state/.
#
#   Usage: bash tests/test_merge_error_propagation.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap '[ -n "${TMPDIR:-}" ] && rm -rf "$TMPDIR"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()      { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_nonzero() { if [ "$2" -ne 0 ]; then ok "$1 (exit $2)"; else bad "$1 (expected non-zero, got 0)"; fi; }

# check_merge <label> <merge-script> <root-key> <master-json> <good-batch-json> <count-after-good>
# Runs a positive control (valid batch merges, exit 0, master updated & valid)
# then the regression (invalid-JSON batch -> non-zero, master byte-unchanged & valid).
check_merge() {
  local label="$1" merge="$2" key="$3" master_json="$4" good_json="$5" want_count="$6"
  local d="$TMPDIR/$label"; mkdir -p "$d"
  local master="$d/master.json" good="$d/good.json" bad="$d/bad.json"
  printf '%s' "$master_json" > "$master"
  printf '%s' "$good_json"   > "$good"
  printf '%s' '{"'"$key"'": [ { "case_key": "x|y|z",'  > "$bad"   # deliberately truncated -> invalid JSON

  echo "[$label] positive control: valid batch merges, exit 0"
  local before_ok; before_ok="$(cat "$master")"
  bash "$merge" "$good" "$master" >/dev/null 2>&1; local ec=$?
  assert_eq "$label positive exits 0" "0" "$ec"
  assert_eq "$label master now has $want_count $key" "$want_count" "$(jq --arg k "$key" '.[$k] | length' "$master")"
  if jq empty "$master" 2>/dev/null; then ok "$label master valid JSON"; else bad "$label master invalid JSON"; fi
  if [ "$before_ok" != "$(cat "$master")" ]; then ok "$label master actually updated"; else bad "$label master unchanged after good merge"; fi

  echo "[$label] regression: invalid-JSON batch -> merge FAILS loudly, master untouched"
  local before_bad; before_bad="$(cat "$master")"
  local err; err="$(bash "$merge" "$bad" "$master" 2>&1 >/dev/null)"; ec=$?
  local after_bad; after_bad="$(cat "$master")"
  assert_nonzero "$label merge exits non-zero on jq failure" "$ec"
  assert_eq "$label master byte-for-byte unchanged" "$before_bad" "$after_bad"
  if jq empty "$master" 2>/dev/null; then ok "$label master still valid JSON (no partial write)"; else bad "$label master corrupted"; fi
  case "$err" in *"failed"*|*"ERROR"*) ok "$label surfaces an error to stderr" ;; *) bad "$label no stderr error (got: $err)" ;; esac
}

# ---------------------------------------------------------------------------
check_merge "merge_case_db" "$ROOT/scripts/merge_case_db.sh" "cases" \
  '{"schema_version":1,"last_merged_at":null,"cases":[{"case_key":"a|coding|2026-01","company":"A"}]}' \
  '{"cases":[{"case_key":"b|coding|2026-01","company":"B"}]}' \
  "2"

check_merge "merge_ax_harvest" "$ROOT/scripts/merge_ax_case_harvest_registry.sh" "cases" \
  '{"schema_version":1,"last_merged_at":null,"cases":[{"case_key":"a|bot|auto","company":"A","verification_status":"verified"}]}' \
  '{"cases":[{"case_key":"b|bot|auto","company":"B","verification_status":"verified"}]}' \
  "2"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
