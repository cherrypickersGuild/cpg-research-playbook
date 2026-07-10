#!/usr/bin/env bash
# test_guard_command.sh — offline tests for the PreToolUse Bash guard.
# exit 2 (never 1) + stderr on block, exit 0 on allow. No network, no production
# writes, no git mutation.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/.claude/hooks/guard_command.py"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   - $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
run_guard(){ local p; p="$(jq -nc --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}')"
  ERR="$(printf '%s' "$p" | python "$GUARD" 2>&1 >/dev/null)"; EC=$?; }
blk(){ run_guard "$1"; if [ "$EC" -eq 2 ]; then ok "BLOCK: $1"; else bad "expected 2 got $EC: $1"; fi; }
alw(){ run_guard "$1"; if [ "$EC" -eq 0 ]; then ok "ALLOW: $1"; else bad "expected 0 got $EC ($ERR): $1"; fi; }

echo "[block] failure-masking + protected-pipe + dangerous commands"
blk 'echo hi || true'
blk 'make test || :'
blk 'bash scripts/validate_task.sh | tee out.log'
blk 'git fetch origin main | tail -1'
blk 'git fetch origin main 2>&1 | head -40'
blk 'bash tests/test_x.sh | grep PASS'
blk 'git push --force origin main'
blk 'git push -f origin main'
blk 'git push --force-with-lease'
blk 'git reset --hard HEAD~1'
blk 'git clean -fd'
blk 'git clean -fdx'
blk 'rm -rf build/'
blk 'rm -fr /tmp/x'
blk 'rm -r -f node_modules'
blk 'rm -r /'
blk 'echo x > state/entity_registry.json'
blk 'jq . a.json > state/ax_case_db.json'
blk 'mv /tmp/x.json state/category_registry.json'
blk 'sed -i s/a/b/ state/visited_url_ledger.json'
blk 'rm -f state/entity_registry.json'
blk 'STATE_DIR=state bash tests/test_clean_json.sh'

echo "[allow] read-only inspection + safe temp-file forms"
alw 'git status'
alw 'git diff HEAD'
alw 'git log --oneline -5'
alw 'git log --oneline | head -20'
alw 'jq empty state/entity_registry.json'
alw 'cat state/entity_registry.json'
alw 'bash scripts/validate_task.sh'
alw 'bash -n scripts/harvest_entities.sh'
alw 'grep -n foo scripts/discover.sh'
alw 'git clean -n'
alw 'rm -f /tmp/backup.json'
alw 'git fetch origin main >/tmp/f.log 2>&1; tail -1 /tmp/f.log'
alw 'bash tests/test_x.sh >/tmp/t.log 2>&1; grep PASS /tmp/t.log'
alw 'STATE_DIR=/tmp/x bash tests/test_clean_json.sh'

echo "[fail-closed] malformed stdin still blocks a recognized danger"
ERR="$(printf 'not json: git push --force' | python "$GUARD" 2>&1 >/dev/null)"; EC=$?
if [ "$EC" -eq 2 ]; then ok "malformed payload + force-push -> exit 2"; else bad "expected 2 got $EC"; fi

echo; echo "=== $PASS passed, $FAIL failed ==="; [ "$FAIL" -eq 0 ]
