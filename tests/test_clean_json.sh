#!/usr/bin/env bash
# test_clean_json.sh — offline regression tests for clean() (scripts/lib/clean_json.sh),
# the robust JSON recovery used by harvest_entities.sh / harvest_ax_cases.sh to
# turn a possibly prose-wrapped nested `claude -p` .result into clean JSON.
#
# No live claude, no GitHub API, no writes to production state/ (the one
# script-level case uses a mock CLAUDE_BIN + temp STATE_DIR).
#
#   Usage: bash tests/test_clean_json.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/clean_json.sh"
ENT="$ROOT/scripts/harvest_entities.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()      { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_nonzero() { if [ "$2" -ne 0 ]; then ok "$1 (exit $2)"; else bad "$1 (expected non-zero, got 0)"; fi; }

# run_clean <input> -> sets OUT and EC
run_clean() { OUT="$(printf '%s' "$1" | clean 2>/dev/null)"; EC=$?; }

echo "[clean] accepts plain valid JSON unchanged (semantically)"
run_clean '{"hits":[1,2,3]}'
assert_eq "plain JSON exit 0" "0" "$EC"
assert_eq "plain JSON .hits length" "3" "$(printf '%s' "$OUT" | jq -c '.hits | length')"

echo "[clean] strips Markdown fences"
run_clean "$(printf '```json\n{"a":1}\n```')"
assert_eq "fenced exit 0" "0" "$EC"
assert_eq "fenced .a" "1" "$(printf '%s' "$OUT" | jq -c '.a')"

echo "[clean] recovers JSON with a prose PREFIX"
run_clean 'I have what I need. Here it is: {"a":1,"b":[2,3]}'
assert_eq "prose-prefix exit 0" "0" "$EC"
assert_eq "prose-prefix .b" "[2,3]" "$(printf '%s' "$OUT" | jq -c '.b')"

echo "[clean] recovers JSON with a prose SUFFIX"
run_clean '{"a":1} -- hope that helps!'
assert_eq "prose-suffix exit 0" "0" "$EC"
assert_eq "prose-suffix .a" "1" "$(printf '%s' "$OUT" | jq -c '.a')"

echo "[clean] recovers a top-level ARRAY wrapped in prose"
run_clean 'result: [1,2,3] end'
assert_eq "array exit 0" "0" "$EC"
assert_eq "array value" "[1,2,3]" "$(printf '%s' "$OUT" | jq -c '.')"

echo "[clean] braces/brackets INSIDE strings do not split the value"
run_clean '{"note":"has } and { and ] and [ inside","ok":true}'
assert_eq "braces-in-string exit 0" "0" "$EC"
assert_eq "braces-in-string .note preserved" "has } and { and ] and [ inside" "$(printf '%s' "$OUT" | jq -r '.note')"

echo "[clean] escaped quotes/braces inside strings are honored"
run_clean '{"s":"he said \"{x}\" then left"}'
assert_eq "escaped-quotes exit 0" "0" "$EC"
assert_eq "escaped-quotes .s preserved" 'he said "{x}" then left' "$(printf '%s' "$OUT" | jq -r '.s')"

echo "[clean] rejects malformed output"
run_clean '{"a": 1'
assert_nonzero "unbalanced -> reject" "$EC"
run_clean 'totally not json at all'
assert_nonzero "prose-only -> reject" "$EC"
run_clean '{ "a" 1 }'
assert_nonzero "balanced-but-invalid -> reject (jq validation)" "$EC"

echo "[clean] rejects MULTIPLE ambiguous JSON payloads"
run_clean "$(printf '{"a":1}\n{"b":2}')"
assert_nonzero "two valid objects -> ambiguous reject" "$EC"
run_clean 'first {"a":1} then also {"b":2} here'
assert_nonzero "two valid objects in prose -> ambiguous reject" "$EC"

echo "[clean] a stray EMPTY [] / {} in prose does not trip the ambiguity guard"
# Regression: the model's prose preamble mentioned "attempted_urls[]", so the
# scanner lifted a bare [] alongside the real {"hits":...} object and clean()
# wrongly rejected the whole batch as ambiguous. An empty container is never a
# real payload — the real object must still be recovered.
run_clean 'All resolved — checked against attempted_urls[] and registry source_urls. {"hits":[{"url":"u"}]}'
assert_eq "empty-[] + object exit 0" "0" "$EC"
assert_eq "empty-[] + object .hits[0].url" "u" "$(printf '%s' "$OUT" | jq -r '.hits[0].url')"
run_clean 'note: config was {} initially. {"cases":[{"company":"Acme"}]}'
assert_eq "empty-{} + object exit 0" "0" "$EC"
assert_eq "empty-{} + object .cases[0].company" "Acme" "$(printf '%s' "$OUT" | jq -r '.cases[0].company')"

echo "[clean] the real pipe: jq -r .result | clean recovers a prose-wrapped envelope"
env_json='{"type":"result","subtype":"success","is_error":false,"result":"Sure — here you go: {\"hits\":[{\"source_url\":\"u\"}]} done"}'
OUT="$(printf '%s' "$env_json" | jq -r '.result' | clean 2>/dev/null)"; EC=$?
assert_eq "envelope-path exit 0" "0" "$EC"
assert_eq "envelope-path .hits[0].source_url" "u" "$(printf '%s' "$OUT" | jq -r '.hits[0].source_url')"

# ---------------------------------------------------------------------------
echo "[script] a candidate reply with NO recoverable JSON -> harvest fails, canonical registry UNCHANGED"
# snapshot production state (must be untouched)
REAL="state/entity_registry.json"
REAL_HASH_BEFORE="$(git -C "$ROOT" hash-object "$REAL" 2>/dev/null || echo MISSING)"
PORCELAIN_BEFORE="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

MOCK="$TMPROOT/mock_claude.sh"
cat > "$MOCK" <<'MOCK_EOF'
#!/usr/bin/env bash
# Always returns a VALID envelope whose .result is prose with NO JSON at all,
# so clean() finds nothing to recover and every attempt fails.
printf '{"result": %s}\n' "$(printf '%s' "I have what I need, but this reply contains no json object whatsoever." | jq -Rs .)"
MOCK_EOF
chmod +x "$MOCK"

d="$TMPROOT/state"; mkdir -p "$d"
echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[
 {"topic":"agent","entity_type":"framework","description_source":"verified","entity_key":"agent|keep","name":"Keep",
  "source_url":"https://ex/keep","target_url":"https://github.com/x/keep","github_stars":null}
]}' > "$d/entity_registry.json"
echo '{"ledger":[]}' > "$d/visited_url_ledger.json"
before="$(cat "$d/entity_registry.json")"
STATE_DIR="$d" CLAUDE_BIN="$MOCK" CANDIDATE_ATTEMPTS=1 BATCH_SIZE=3 MAX_LOOPS=3 \
  bash "$ENT" agent 5 >/dev/null 2>&1; ec=$?
after="$(cat "$d/entity_registry.json")"
assert_nonzero "harvest exits non-zero when no JSON recoverable" "$ec"
assert_eq "fixture registry byte-for-byte unchanged" "$before" "$after"
if jq empty "$d/entity_registry.json" 2>/dev/null; then ok "fixture registry still valid JSON"; else bad "fixture registry corrupted"; fi

echo "[script] production state/ untouched by the whole test"
assert_eq "production entity_registry.json unchanged" "$REAL_HASH_BEFORE" "$(git -C "$ROOT" hash-object "$REAL" 2>/dev/null || echo MISSING)"
assert_eq "git status --porcelain state/ unchanged" "$PORCELAIN_BEFORE" "$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
