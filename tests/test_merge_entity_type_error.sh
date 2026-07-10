#!/usr/bin/env bash
# test_merge_entity_type_error.sh — regression test for merge_entity_registry.sh's
# error propagation. Before the fix, a jq failure inside the merge (e.g. the
# metadata `from_entries` choking on an entity missing `entity_type`) was
# swallowed: the `jq ... && mv` idiom skipped the mv under `set -e` but the
# script still exited 0, falsely reporting success while the master was left
# unchanged. The merge must instead FAIL LOUDLY (non-zero) and leave the master
# untouched. OFFLINE: merge script + fixtures only, temp dir, no claude, no git
# writes, no production state/.
#
#   Usage: bash tests/test_merge_entity_type_error.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MERGE="$ROOT/scripts/merge_entity_registry.sh"
TMPDIR="$(mktemp -d)"
trap '[ -n "${TMPDIR:-}" ] && rm -rf "$TMPDIR"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()      { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_nonzero() { if [ "$2" -ne 0 ]; then ok "$1 (exit $2)"; else bad "$1 (expected non-zero, got 0)"; fi; }

# ---------------------------------------------------------------------------
echo "[positive control] a well-formed batch (entity_type present) merges cleanly, exit 0"
MASTER="$TMPDIR/master_ok.json"
NEW="$TMPDIR/new_ok.json"
cat > "$MASTER" <<'EOF'
{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[
  {"topic":"agent","entity_type":"framework","name":"A1","entity_key":"agent|a1",
   "source_url":"https://ex.com/a1","target_url":"https://github.com/x/a1",
   "description":"d","description_source":"verified","github_stars":null}
]}
EOF
cat > "$NEW" <<'EOF'
{"entities":[
  {"topic":"agent","entity_type":"framework","name":"A2","entity_key":"agent|a2",
   "source_url":"https://ex.com/a2","target_url":"https://github.com/x/a2",
   "description":"d","description_source":"verified"}
]}
EOF
before_ok="$(cat "$MASTER")"
bash "$MERGE" "$NEW" "$MASTER" >/dev/null 2>&1; ec=$?
assert_eq "positive control exits 0" "0" "$ec"
assert_eq "master grew to 2 entities" "2" "$(jq '.entities | length' "$MASTER")"
if jq empty "$MASTER" 2>/dev/null; then ok "master still valid JSON"; else bad "master invalid JSON after merge"; fi
if [ "$before_ok" != "$(cat "$MASTER")" ]; then ok "master was actually updated"; else bad "master unchanged (merge did nothing)"; fi

# ---------------------------------------------------------------------------
echo "[regression] a batch entity MISSING entity_type -> merge FAILS loudly, master untouched"
MASTER2="$TMPDIR/master_bad.json"
NEW2="$TMPDIR/new_bad.json"
cat > "$MASTER2" <<'EOF'
{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[
  {"topic":"agent","entity_type":"framework","name":"A1","entity_key":"agent|a1",
   "source_url":"https://ex.com/a1","target_url":"https://github.com/x/a1",
   "description":"d","description_source":"verified","github_stars":null}
]}
EOF
# NOTE: this incoming entity deliberately omits "entity_type" — the metadata
# group_by(.entity_type)|from_entries would then build a null object key.
cat > "$NEW2" <<'EOF'
{"entities":[
  {"topic":"agent","name":"NoType","entity_key":"agent|notype",
   "source_url":"https://ex.com/nt","target_url":"https://github.com/x/nt",
   "description":"d","description_source":"verified"}
]}
EOF
before_bad="$(cat "$MASTER2")"
err="$(bash "$MERGE" "$NEW2" "$MASTER2" 2>&1 >/dev/null)"; ec=$?
after_bad="$(cat "$MASTER2")"
assert_nonzero "merge exits non-zero on the jq failure (not a false success)" "$ec"
assert_eq "master left byte-for-byte unchanged" "$before_bad" "$after_bad"
if jq empty "$MASTER2" 2>/dev/null; then ok "master remains valid JSON (no partial/truncated write)"; else bad "master corrupted"; fi
case "$err" in *"failed"*|*"ERROR"*) ok "surfaces an error message to stderr" ;; *) bad "no error message on stderr (got: $err)" ;; esac

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
