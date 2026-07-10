#!/usr/bin/env bash
# test_permission_rules.sh — verify the project permission rules use the
# documented space-form syntax AND load in the INSTALLED claude (beyond mere
# JSON-schema parsing). Offline: local files + local `claude doctor`. No network.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="$ROOT/.claude/settings.local.json"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   - $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL - $1"; }

echo "[syntax] rules use space-form, not colon-style ':*'"
if jq -e '[.permissions | (.allow//[])+(.ask//[])+(.deny//[]) | .[] | select(test(":\\*"))] | length == 0' "$SETTINGS" >/dev/null 2>&1; then
  ok "no colon-style ':*' patterns present"
else
  bad "colon-style ':*' patterns found"
  jq -r '.permissions | (.allow//[])+(.ask//[])+(.deny//[]) | .[] | select(test(":\\*"))' "$SETTINGS" 2>/dev/null
fi

echo "[schema] settings.local.json valid JSON with the expected sections"
if jq -e '.permissions and .outputStyle and .hooks.PreToolUse' "$SETTINGS" >/dev/null 2>&1; then
  ok "permissions + outputStyle + hooks.PreToolUse present"
else
  bad "expected sections missing"
fi

echo "[installed] claude doctor loads project settings without complaint"
if command -v claude >/dev/null 2>&1; then
  out="$(mktemp)"
  if ( cd "$ROOT" && claude doctor >"$out" 2>&1 </dev/null ); then rc=0; else rc=$?; fi
  if [ "$rc" -eq 0 ] && ! grep -iE "invalid|malformed|failed to (parse|load)|ignored .*rule" "$out" >/dev/null 2>&1; then
    ok "claude doctor exit 0 and reported no settings/permission problems"
  else
    bad "claude doctor reported a problem (exit $rc)"
    grep -iE "invalid|malformed|error|rule|permission|settings" "$out" 2>/dev/null | head -20
  fi
  rm -f "$out"
else
  echo "  WARN - 'claude' not on PATH; installed-loader check skipped"
fi

echo; echo "=== $PASS passed, $FAIL failed ==="; [ "$FAIL" -eq 0 ]
