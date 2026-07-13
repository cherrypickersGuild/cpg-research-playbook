#!/usr/bin/env bash
# test_harvest_1g_shape_guard.sh — deterministic, OFFLINE test for the 1G output
# SHAPE guard in harvest_entities.sh. clean() guarantees valid JSON but not the
# right shape: a rate-limit prose deferral can collapse to a bare `[]` (from an
# "entity_ids:[]" fragment), which passes `jq empty` but then crashes the ledger
# merge (`.[1].ledger_patch` on an array) and aborts the whole run. valid_1g_batch
# must reject such outputs so the attempt FAILS and takes the existing retry path,
# never reaching the ledger or registry merge.
#
# Drives the REAL loop of harvest_entities.sh with a MOCK claude (CLAUDE_BIN) that
# emits a chosen bad/good 1G shape, under a temp STATE_DIR. Asserts, per malformed
# shape (`[]`, missing .ledger_patch, missing .entities, non-object ledger_patch
# element):
#   * the extraction attempt fails and retries, then the run exits NON-ZERO;
#   * NO partial merge — temp registry stays empty and no ledger row gets
#     entity_ids stamped (the ledger_patch merge never ran);
# plus a positive control (a well-formed batch still merges), and the standard
# real-state protection: the real state/*.json are byte-identical before/after.
#
#   Usage: bash tests/test_harvest_1g_shape_guard.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENT="$ROOT/scripts/harvest_entities.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_ne()       { if [ "$2" != "$3" ]; then ok "$1"; else bad "$1 (expected != [$2], got [$3])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }

# --- mock claude -----------------------------------------------------------
# candidate-batch call (no --append-system-prompt) -> valid hits, so the loop
# always reaches the 1G step. 1G call (has --append-system-prompt) -> a shape
# chosen by MOCK_1G_MODE. Emitted values are the CLEANED shapes directly (this
# test targets the shape guard, not clean()'s prose recovery, which has its own
# test); `[]` reproduces the real prose->`[]` collapse post-clean.
MOCK="$TMPROOT/mock_claude.sh"
cat > "$MOCK" <<'MOCK_EOF'
#!/usr/bin/env bash
set -u
args="$*"
emit() { printf '{"result": %s}\n' "$(printf '%s' "$1" | jq -Rs .)"; }
is_extract="no"; case "$args" in *"--append-system-prompt"*) is_extract="yes" ;; esac

if [ "$is_extract" = "no" ]; then
  emit '{"hits":[{"source_url":"https://example.com/c","target_url":"https://example.com/t","title":"t","snippet":"s","domain":"example.com"}]}'
  exit 0
fi

good_entity='{"topic":"mcp","entity_type":"server","name":"x","entity_key":"mcp|x","source_url":"https://example.com/c","target_url":"https://example.com/t","description":"d","description_source":"verified","github_stars":null}'
good_patch='{"url":"https://example.com/c","entity_extracted":true,"entity_ids":["x"]}'
case "${MOCK_1G_MODE:-empty_array}" in
  empty_array)      emit '[]' ;;
  missing_ledger)   emit "{\"entities\":[$good_entity]}" ;;
  missing_entities) emit "{\"ledger_patch\":[$good_patch]}" ;;
  bad_ledger_elem)  emit "{\"entities\":[],\"ledger_patch\":[\"not-an-object\"]}" ;;
  valid)            emit "{\"entities\":[$good_entity],\"ledger_patch\":[$good_patch]}" ;;
  *)                emit '[]' ;;
esac
exit 0
MOCK_EOF
chmod +x "$MOCK"

# deterministic mock -> keep attempts small; >1 so the retry path is exercised.
export CLAUDE_BIN="$MOCK" BATCH_SIZE=5 CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=2

new_state() {
  local d="$TMPROOT/$1"; mkdir -p "$d"
  echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[]}' > "$d/entity_registry.json"
  echo '{"ledger":[]}' > "$d/visited_url_ledger.json"
  echo "$d"
}
reg_entities()  { jq '.entities | length' "$1/entity_registry.json"; }
ledger_stamped(){ jq '[.ledger[] | select((.entity_ids // []) | length > 0)] | length' "$1/visited_url_ledger.json"; }

# --- real-state protection: snapshot BEFORE --------------------------------
REAL_FILES=(state/entity_registry.json state/visited_url_ledger.json)
declare -A HASH_BEFORE
for f in "${REAL_FILES[@]}"; do HASH_BEFORE["$f"]="$(git -C "$ROOT" hash-object "$f" 2>/dev/null || echo MISSING)"; done
PORCELAIN_BEFORE="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

# --- malformed shapes: must fail the attempt, retry, exit non-zero, NOT merge
for mode in empty_array missing_ledger missing_entities bad_ledger_elem; do
  echo "[shape-guard] malformed 1G output ($mode) -> retry, non-zero exit, no merge"
  d="$(new_state "bad_$mode")"
  OUT="$(STATE_DIR="$d" MOCK_1G_MODE="$mode" MAX_LOOPS=3 NO_PROGRESS_THRESHOLD=3 \
         bash "$ENT" mcp 5 2>&1)"; EC=$?
  assert_ne       "$mode: run exits non-zero"                 "0" "$EC"
  assert_contains "$mode: attempt logged invalid + retried"   "$OUT" "produced invalid output"
  assert_contains "$mode: failed after all attempts"          "$OUT" "1G extraction step failed"
  assert_eq       "$mode: NO registry merge (0 entities)"     "0" "$(reg_entities "$d")"
  assert_eq       "$mode: NO ledger_patch merge (0 stamped)"  "0" "$(ledger_stamped "$d")"
done

# --- positive control: a well-formed batch is accepted and merges ----------
echo "[shape-guard] well-formed 1G output -> accepted, merges, exit 0"
d="$(new_state good)"
OUT="$(STATE_DIR="$d" MOCK_1G_MODE=valid MAX_LOOPS=3 NO_PROGRESS_THRESHOLD=3 \
       bash "$ENT" mcp 1 2>&1)"; EC=$?
assert_eq "valid: clean bounded exit 0"          "0" "$EC"
assert_eq "valid: entity merged (1 in registry)" "1" "$(reg_entities "$d")"
assert_eq "valid: ledger row stamped (1)"        "1" "$(ledger_stamped "$d")"

# --- real-state protection: assert AFTER == BEFORE -------------------------
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
