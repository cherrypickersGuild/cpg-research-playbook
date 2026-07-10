#!/usr/bin/env bash
# test_harvest_bounded.sh — deterministic, OFFLINE test that the harvest loops
# TERMINATE within their bounds. It drives the REAL loop of harvest_entities.sh /
# harvest_ax_cases.sh with a MOCK claude (CLAUDE_BIN) that emits canned JSON, so
# no live claude / GitHub API is ever called, and everything runs under a temp
# STATE_DIR. Asserts:
#   * a non-progressing (all-duplicate) source stops after NO_PROGRESS_THRESHOLD
#     CONSECUTIVE no-progress loops — NOT on the first, and NOT never.
#   * a progressing source with a high target stops exactly at MAX_LOOPS.
#   * harvest_all.sh reports INCOMPLETE and exits non-zero when a stage cannot
#     reach its target (no false success).
# Plus an automated real-state protection assertion: the real state/*.json files
# and their git tracked-status are byte-identical before and after the run.
#
#   Usage: bash tests/test_harvest_bounded.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENT="$ROOT/scripts/harvest_entities.sh"
AX="$ROOT/scripts/harvest_ax_cases.sh"
ALL="$ROOT/scripts/harvest_all.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }
assert_absent()   { case "$2" in *"$3"*) bad "$1 (output unexpectedly contains: $3)" ;; *) ok "$1" ;; esac; }

# --- write the mock claude -------------------------------------------------
# It reads its args ("$*") to decide (a) lane: entity vs ax, and (b) call type:
# candidate (no --append-system-prompt) vs extract (has it). Behavior is driven
# by MOCK_BEHAVIOR: "dup" emits the SAME record every extract (0 net progress
# after the first merge); "unique" emits a fresh record each extract (progress
# every loop). Output is the {"result":"<inner-json>"} envelope the loop expects.
MOCK="$TMPROOT/mock_claude.sh"
cat > "$MOCK" <<'MOCK_EOF'
#!/usr/bin/env bash
set -u
args="$*"
case "$args" in
  *"AX transformation case harvest"*|*"case batch JSON"*) lane="ax" ;;
  *) lane="entity" ;;
esac
is_extract="no"; case "$args" in *"--append-system-prompt"*) is_extract="yes" ;; esac

emit() { printf '{"result": %s}\n' "$(printf '%s' "$1" | jq -Rs .)"; }

if [ "$is_extract" = "no" ]; then
  if [ "$lane" = "ax" ]; then
    emit '{"hits":[{"url":"https://example.com/c","title":"t","snippet":"s","domain":"example.com"}]}'
  else
    emit '{"hits":[{"source_url":"https://example.com/c","target_url":"https://example.com/t","title":"t","snippet":"s","domain":"example.com"}]}'
  fi
  exit 0
fi

key="fixed"
if [ "${MOCK_BEHAVIOR:-dup}" = "unique" ]; then
  n=0; [ -f "${MOCK_COUNTER_FILE:-}" ] && n="$(cat "$MOCK_COUNTER_FILE" 2>/dev/null || echo 0)"
  n=$((n+1)); echo "$n" > "$MOCK_COUNTER_FILE"; key="$n"
fi

if [ "$lane" = "ax" ]; then
  emit "{\"cases\":[{\"company\":\"Co$key\",\"ai_system_or_tool\":\"bot\",\"workflow_after\":\"automated $key\",\"workflow_before\":\"manual\",\"industry\":\"x\",\"measurable_kpi\":\"k\",\"kpi_value\":\"v\",\"evidence_quote\":\"q\",\"source_url\":\"https://example.com/$key\",\"source_title\":\"t\",\"source_domain\":\"example.com\",\"verification_status\":\"verified\",\"confidence\":0.8,\"transformation_date\":\"2026-01\",\"publication_date\":\"2026-02\"}]}"
else
  emit "{\"entities\":[{\"topic\":\"agent\",\"entity_type\":\"framework\",\"name\":\"m$key\",\"entity_key\":\"agent|m$key\",\"source_url\":\"https://example.com/$key\",\"target_url\":\"https://example.com/t$key\",\"description\":\"d\",\"description_source\":\"verified\",\"github_stars\":null}],\"ledger_patch\":[{\"url\":\"https://example.com/c\",\"entity_extracted\":true,\"entity_ids\":[\"m$key\"]}]}"
fi
exit 0
MOCK_EOF
chmod +x "$MOCK"

# Constants for every run (mock is deterministic -> 1 attempt; tiny batch).
# Exported so child harvests — including those harvest_all spawns — inherit them.
# (Env assignments from an array expansion are NOT recognized by bash as
# assignments, so we export rather than prefix with "${arr[@]}".)
export CLAUDE_BIN="$MOCK" BATCH_SIZE=5 CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 EXTRACT_ATTEMPTS=1

new_state() {
  local d="$TMPROOT/$1"; mkdir -p "$d"
  echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[]}' > "$d/entity_registry.json"
  echo '{"schema_version":1,"last_merged_at":null,"cases":[]}' > "$d/ax_case_harvest_registry.json"
  echo '{"ledger":[]}' > "$d/visited_url_ledger.json"
  echo "$d"
}
cur_entity() { STATE_DIR="$1" bash "$ENT" agent "$2" --check | grep -oE 'current=[0-9]+' | cut -d= -f2; }
cur_ax()     { STATE_DIR="$1" bash "$AX" "$2" --check       | grep -oE 'current=[0-9]+' | cut -d= -f2; }

# --- automated real-state protection: snapshot BEFORE ----------------------
REAL_FILES=(state/entity_registry.json state/ax_case_harvest_registry.json state/visited_url_ledger.json)
declare -A HASH_BEFORE
for f in "${REAL_FILES[@]}"; do HASH_BEFORE["$f"]="$(git -C "$ROOT" hash-object "$f" 2>/dev/null || echo MISSING)"; done
PORCELAIN_BEFORE="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

# ---------------------------------------------------------------------------
echo "[entity] no-progress: all-duplicate source stops after N consecutive no-progress loops"
d="$(new_state e_noprog)"
OUT="$(STATE_DIR="$d" MOCK_BEHAVIOR=dup MOCK_COUNTER_FILE="$d/ctr" \
       MAX_LOOPS=20 NO_PROGRESS_THRESHOLD=2 \
       bash "$ENT" agent 999 2>&1)"; EC=$?
assert_eq "entity no-progress exits 0 (clean, bounded)" "0" "$EC"
assert_contains "stopped via no-progress" "$OUT" "consecutive no-progress loops"
assert_absent  "did NOT stop via MAX_LOOPS" "$OUT" "MAX_LOOPS (20) reached"
assert_eq "only the 1 unique dup record merged" "1" "$(cur_entity "$d" 999)"

echo "[entity] max-loops: progressing source stops exactly at MAX_LOOPS"
d="$(new_state e_maxloop)"
OUT="$(STATE_DIR="$d" MOCK_BEHAVIOR=unique MOCK_COUNTER_FILE="$d/ctr" \
       MAX_LOOPS=3 NO_PROGRESS_THRESHOLD=5 \
       bash "$ENT" agent 999 2>&1)"; EC=$?
assert_eq "entity max-loops exits 0 (clean, bounded)" "0" "$EC"
assert_contains "stopped via MAX_LOOPS" "$OUT" "MAX_LOOPS (3) reached"
assert_absent  "did NOT stop via no-progress" "$OUT" "consecutive no-progress loops"
assert_eq "3 loops each added 1 -> current=3" "3" "$(cur_entity "$d" 999)"

echo "[ax] no-progress: all-duplicate source stops after N consecutive no-progress loops"
d="$(new_state ax_noprog)"
OUT="$(STATE_DIR="$d" MOCK_BEHAVIOR=dup MOCK_COUNTER_FILE="$d/ctr" \
       MAX_LOOPS=20 NO_PROGRESS_THRESHOLD=2 \
       bash "$AX" 999 2>&1)"; EC=$?
assert_eq "ax no-progress exits 0 (clean, bounded)" "0" "$EC"
assert_contains "stopped via no-progress" "$OUT" "consecutive no-progress loops"
assert_absent  "did NOT stop via MAX_LOOPS" "$OUT" "MAX_LOOPS (20) reached"
assert_eq "only the 1 unique dup case merged" "1" "$(cur_ax "$d" 999)"

echo "[ax] max-loops: progressing source stops exactly at MAX_LOOPS"
d="$(new_state ax_maxloop)"
OUT="$(STATE_DIR="$d" MOCK_BEHAVIOR=unique MOCK_COUNTER_FILE="$d/ctr" \
       MAX_LOOPS=3 NO_PROGRESS_THRESHOLD=5 \
       bash "$AX" 999 2>&1)"; EC=$?
assert_eq "ax max-loops exits 0 (clean, bounded)" "0" "$EC"
assert_contains "stopped via MAX_LOOPS" "$OUT" "MAX_LOOPS (3) reached"
assert_eq "3 loops each added 1 -> current=3" "3" "$(cur_ax "$d" 999)"

echo "[orchestrator] no false success: a stage that cannot reach target -> INCOMPLETE, exit 1"
d="$(new_state all_incomplete)"
OUT="$(STATE_DIR="$d" ENTITY_TARGET=5 AX_TARGET=5 MOCK_BEHAVIOR=dup MOCK_COUNTER_FILE="$d/ctr" \
       MAX_LOOPS=6 NO_PROGRESS_THRESHOLD=2 \
       bash "$ALL" --all 2>&1)"; EC=$?
assert_eq "harvest_all exits non-zero when below target" "1" "$EC"
assert_contains "summary reports INCOMPLETE" "$OUT" "harvest INCOMPLETE"
assert_absent  "does not falsely claim COMPLETE" "$OUT" "all requested stages at/above target"

# --- automated real-state protection: assert AFTER == BEFORE ----------------
echo "[safety] real state/*.json content + git status unchanged by the whole run"
for f in "${REAL_FILES[@]}"; do
  after="$(git -C "$ROOT" hash-object "$f" 2>/dev/null || echo MISSING)"
  assert_eq "unchanged: $f" "${HASH_BEFORE[$f]}" "$after"
done
PORCELAIN_AFTER="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"
assert_eq "git status --porcelain state/ unchanged" "$PORCELAIN_BEFORE" "$PORCELAIN_AFTER"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
