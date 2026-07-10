#!/usr/bin/env bash
# test_pipeline_ledger_error.sh — regression test that run_stage1.sh and
# discover.sh FAIL LOUDLY when one of their `jq -s '{ledger:...}' ... && mv`
# merges errors, instead of the old idiom that (under set -e) skipped the mv but
# ran on and exited 0 while silently leaving the ledger stale.
#
# Drives the REAL scripts with a mock CLAUDE_BIN (canned per-stage JSON) and a
# temp STATE_DIR. No live claude, no GitHub API, no writes to production state/.
#
# Failure fixture (per the corrected design): the canonical visited_url_ledger.json
# is kept VALID; the mock makes the hits stage's transient output carry a
# non-array `ledger_updates`, so the ledger merge `(.[0].ledger // []) +
# (.[1].ledger_updates // [])` does `array + string` and jq fails — targeting
# exactly the guarded `&& mv` merge.
#
#   Usage: bash tests/test_pipeline_ledger_error.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RS1="$ROOT/scripts/run_stage1.sh"
DISC="$ROOT/scripts/discover.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()      { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_nonzero() { if [ "$2" -ne 0 ]; then ok "$1 (exit $2)"; else bad "$1 (expected non-zero, got 0)"; fi; }
# grep -c already prints "0" on no match (and exits 1); with set +e/no chaining
# n captures that "0" cleanly. (The earlier `|| echo 0` appended a SECOND 0.)
assert_absent()  { local n; n="$(grep -cxF "$3" "$2" 2>/dev/null)"; n="${n:-0}"; if [ "$n" -eq 0 ]; then ok "$1"; else bad "$1 (stage '$3' ran)"; fi; }
assert_present() { local n; n="$(grep -cxF "$3" "$2" 2>/dev/null)"; n="${n:-0}"; if [ "$n" -gt 0 ]; then ok "$1"; else bad "$1 (stage '$3' did not run)"; fi; }

# --- mock claude: emits {"result":"<inner>"}; stage detected from the -p prompt.
MOCK="$TMPROOT/mock_claude.sh"
cat > "$MOCK" <<'MOCK_EOF'
#!/usr/bin/env bash
set -u
prompt=""; prev=""
for a in "$@"; do
  if [ "$prev" = "-p" ]; then prompt="$a"; break; fi
  prev="$a"
done
stage="unknown"
case "$prompt" in
  *"Search Strategy DB"*)   stage="1A" ;;
  *"Hit JSON"*)             stage="hits" ;;   # 1B (run_stage1) or 1F (discover)
  *"ax_case_db.json"*)      stage="1C" ;;
  *"entity batch JSON"*)    stage="1G" ;;
  *"candidate categories"*) stage="1E" ;;
esac
[ -n "${MOCK_LOG:-}" ] && echo "$stage" >> "$MOCK_LOG"

emit() { printf '{"result": %s}\n' "$(printf '%s' "$1" | jq -Rs .)"; }

case "$stage" in
  1A) emit '{"topics":[],"refresh_days":7,"strategies":[]}' ;;
  hits)
    if [ "${MOCK_BAD_STAGE:-}" = "hits" ]; then
      emit '{"hits":[],"ledger_updates":"BAD_NOT_AN_ARRAY","category_signals":[],"throttled_domains":[]}'
    else
      emit '{"hits":[{"url":"https://ex.com/h1","title":"t","snippet":"s","domain":"ex.com"}],"ledger_updates":[],"category_signals":[],"throttled_domains":[]}'
    fi ;;
  1C) emit '{"run_metadata":{},"coverage_summary":{},"cases":[],"pattern_index":{},"ledger_patch":[]}' ;;
  1G) emit '{"entities":[],"ledger_patch":[]}' ;;
  1E) emit '{"categories":[]}' ;;
  *)  emit '{}' ;;
esac
exit 0
MOCK_EOF
chmod +x "$MOCK"
export CLAUDE_BIN="$MOCK"

LEDGER_SEED='{"ledger":[{"url":"https://seed.example/keep","url_type":"news_url","platform":"custom","extracted":false,"case_ids":[],"entity_extracted":false,"entity_ids":[]}]}'
seed_state() {  # $1 = STATE_DIR fixture
  printf '%s' "$LEDGER_SEED" > "$1/visited_url_ledger.json"
  echo '{"sources":[]}' > "$1/source_registry.json"
}

# --- automated real-state protection: snapshot BEFORE ----------------------
REAL_FILES=(state/visited_url_ledger.json state/ax_case_db.json state/entity_registry.json state/ax_case_harvest_registry.json)
declare -A HASH_BEFORE
for f in "${REAL_FILES[@]}"; do HASH_BEFORE["$f"]="$(git -C "$ROOT" hash-object "$f" 2>/dev/null || echo MISSING)"; done
PORCELAIN_BEFORE="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

# ===========================================================================
echo "[run_stage1] positive control: valid mocked outputs -> exit 0, ledger valid"
d="$TMPROOT/rs1_pos"; mkdir -p "$d"; seed_state "$d"; log="$TMPROOT/rs1_pos.log"; : > "$log"
STATE_DIR="$d" MOCK_LOG="$log" bash "$RS1" "$d/out.json" "$d/cfg.json" >/dev/null 2>&1; ec=$?
assert_eq "run_stage1 positive exits 0" "0" "$ec"
if jq empty "$d/visited_url_ledger.json" 2>/dev/null; then ok "ledger valid after success"; else bad "ledger invalid after success"; fi
assert_present "1A ran" "$log" "1A"
assert_present "hits (1B) ran" "$log" "hits"
assert_present "1C ran" "$log" "1C"
assert_present "1G ran" "$log" "1G"

echo "[run_stage1] regression: 1B ledger merge fails -> non-zero, ledger untouched, later stages skipped"
d="$TMPROOT/rs1_reg"; mkdir -p "$d"; seed_state "$d"; log="$TMPROOT/rs1_reg.log"; : > "$log"
before="$(cat "$d/visited_url_ledger.json")"
STATE_DIR="$d" MOCK_LOG="$log" MOCK_BAD_STAGE=hits bash "$RS1" "$d/out.json" "$d/cfg.json" >/dev/null 2>&1; ec=$?
after="$(cat "$d/visited_url_ledger.json")"
assert_nonzero "run_stage1 regression exits non-zero" "$ec"
assert_eq "canonical ledger byte-for-byte unchanged" "$before" "$after"
if jq empty "$d/visited_url_ledger.json" 2>/dev/null; then ok "canonical ledger still valid JSON"; else bad "ledger corrupted"; fi
assert_present "hits (1B) attempted" "$log" "hits"
assert_absent "1C did NOT run after failure" "$log" "1C"
assert_absent "1G did NOT run after failure" "$log" "1G"

# ===========================================================================
echo "[discover] positive control: valid mocked outputs -> exit 0, ledger valid"
d="$TMPROOT/disc_pos"; mkdir -p "$d"; seed_state "$d"; log="$TMPROOT/disc_pos.log"; : > "$log"
STATE_DIR="$d" MOCK_LOG="$log" bash "$DISC" both >/dev/null 2>&1; ec=$?
assert_eq "discover positive exits 0" "0" "$ec"
if jq empty "$d/visited_url_ledger.json" 2>/dev/null; then ok "ledger valid after success"; else bad "ledger invalid after success"; fi
assert_present "hits (1F) ran" "$log" "hits"
assert_present "1E ran" "$log" "1E"

echo "[discover] regression: 1F ledger merge fails -> non-zero, ledger untouched, later stages skipped"
d="$TMPROOT/disc_reg"; mkdir -p "$d"; seed_state "$d"; log="$TMPROOT/disc_reg.log"; : > "$log"
before="$(cat "$d/visited_url_ledger.json")"
STATE_DIR="$d" MOCK_LOG="$log" MOCK_BAD_STAGE=hits bash "$DISC" both >/dev/null 2>&1; ec=$?
after="$(cat "$d/visited_url_ledger.json")"
assert_nonzero "discover regression exits non-zero" "$ec"
assert_eq "canonical ledger byte-for-byte unchanged" "$before" "$after"
if jq empty "$d/visited_url_ledger.json" 2>/dev/null; then ok "canonical ledger still valid JSON"; else bad "ledger corrupted"; fi
assert_present "hits (1F) attempted" "$log" "hits"
assert_absent "1C did NOT run after failure" "$log" "1C"
assert_absent "1G did NOT run after failure" "$log" "1G"
assert_absent "1E did NOT run after failure" "$log" "1E"

# --- real-state protection: assert AFTER == BEFORE -------------------------
echo "[safety] production state/*.json content + git status unchanged by the whole run"
for f in "${REAL_FILES[@]}"; do
  after_h="$(git -C "$ROOT" hash-object "$f" 2>/dev/null || echo MISSING)"
  assert_eq "unchanged: $f" "${HASH_BEFORE[$f]}" "$after_h"
done
PORCELAIN_AFTER="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"
assert_eq "git status --porcelain state/ unchanged" "$PORCELAIN_BEFORE" "$PORCELAIN_AFTER"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
