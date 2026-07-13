#!/usr/bin/env bash
# validate_task.sh — single allowlisted, OFFLINE validation entry point.
# Focused checks for the files changed in the working tree:
#   bash -n (shell) · py_compile (python) · jq empty (json, read-only) ·
#   the tests/ regressions mapped to those files.
#
# Isolation is PROVEN, not assumed:
#   * external agents disabled (CLAUDE_BIN -> failing mock)
#   * STATE_DIR points at a throwaway temp dir (belt — NOT treated as proof)
#   * only tests on an AUDITED allowlist of isolation-safe tests are run; any
#     other (unaudited) test is skipped with a clear message, never trusted
#   * production state/ is content-hash-snapshotted before AND after; ANY change
#     fails the run non-zero and is reported (never auto-restored/overwritten)
# Real exit codes are preserved throughout; no meaningful command is piped
# through a filter.
#
#   Usage: bash scripts/validate_task.sh [--all] [file ...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/mock_claude.sh" <<'EOF'
#!/usr/bin/env bash
echo "validate_task.sh: live claude/agent invocation is disabled during validation" >&2
exit 97
EOF
chmod +x "$WORK/mock_claude.sh"
export CLAUDE_BIN="$WORK/mock_claude.sh"
export STATE_DIR="$WORK/state"; mkdir -p "$STATE_DIR"

# --- audited allowlist of isolation-safe tests -----------------------------
# Each was inspected and confirmed to run under a temp dir / temp STATE_DIR with
# a mock or `false` CLAUDE_BIN, contact no real remote, and never write the
# production state/ dir. Tests NOT listed here are skipped, not trusted.
ISOLATED=(
  test_ax_case_harvest_dates.sh test_clean_json.sh test_entity_github_stars.sh
  test_entity_url_schema.sh test_harvest_bounded.sh test_harvest_targets.sh
  test_harvest_1g_shape_guard.sh
  test_ledger_patch_merge.sh test_merge_entity_type_error.sh
  test_merge_error_propagation.sh test_pipeline_ledger_error.sh
  test_guard_command.sh test_safe_commit.sh test_safe_push_main.sh
  test_permission_rules.sh
)
is_isolated() {
  local b; b="$(basename "$1")"
  local t; for t in "${ISOLATED[@]}"; do [ "$t" = "$b" ] && return 0; done
  return 1
}

FAIL=0
run() { local label="$1"; shift
  if "$@"; then echo "  ok   - $label"
  else local rc=$?; echo "  FAIL - $label (exit $rc)"; FAIL=1; fi; }

MODE="changed"; declare -a FILES=()
[ "${1:-}" = "--all" ] && { MODE="all"; shift; }
if [ "$#" -gt 0 ]; then FILES=("$@"); MODE="explicit"
elif [ "$MODE" = "changed" ]; then
  while IFS= read -r f; do [ -n "$f" ] && FILES+=("$f"); done < <(
    { git diff --name-only --diff-filter=d HEAD 2>/dev/null
      git ls-files --others --exclude-standard; } | sort -u )
fi

echo "== validate_task.sh (mode: $MODE) =="
declare -a TESTS=()
add_test() { [ -f "$1" ] || return 0; case " ${TESTS[*]:-} " in *" $1 "*) ;; *) TESTS+=("$1");; esac; }

for f in "${FILES[@]:-}"; do
  [ -z "$f" ] && continue; [ -f "$f" ] || continue
  case "$f" in
    *.sh)   run "bash -n $f"    bash -n "$f" ;;
    *.py)   run "py_compile $f" python -m py_compile "$f" ;;
    *.json) run "jq empty $f"   jq empty "$f" ;;
  esac
  case "$f" in
    scripts/lib/clean_json.sh)                    add_test tests/test_clean_json.sh ;;
    scripts/merge_entity_registry.sh)             add_test tests/test_merge_entity_type_error.sh; add_test tests/test_entity_github_stars.sh ;;
    scripts/merge_ax_case_harvest_registry.sh|scripts/merge_case_db.sh) add_test tests/test_merge_error_propagation.sh ;;
    scripts/run_stage1.sh|scripts/discover.sh)    add_test tests/test_ledger_patch_merge.sh; add_test tests/test_pipeline_ledger_error.sh ;;
    scripts/backfill_entity_target_url.py)        add_test tests/test_entity_url_schema.sh ;;
    scripts/harvest_entities.sh)                  add_test tests/test_harvest_bounded.sh; add_test tests/test_harvest_targets.sh; add_test tests/test_harvest_1g_shape_guard.sh; add_test tests/test_entity_github_stars.sh; add_test tests/test_clean_json.sh ;;
    scripts/harvest_ax_cases.sh)                  add_test tests/test_ax_case_harvest_dates.sh; add_test tests/test_harvest_bounded.sh; add_test tests/test_clean_json.sh ;;
    .claude/hooks/guard_command.py)               add_test tests/test_guard_command.sh; add_test tests/test_permission_rules.sh ;;
    scripts/safe_commit.sh)                       add_test tests/test_safe_commit.sh; add_test tests/test_permission_rules.sh ;;
    scripts/safe_push_main.sh)                    add_test tests/test_safe_push_main.sh; add_test tests/test_permission_rules.sh ;;
  esac
done
[ "$MODE" = "all" ] && { for t in tests/*.sh; do add_test "$t"; done; }

# run only tests on the audited isolation allowlist
declare -a SAFE=()
for t in "${TESTS[@]:-}"; do
  [ -z "$t" ] && continue
  if is_isolated "$t"; then SAFE+=("$t")
  else echo "  WARN - skipping $t (not on the audited isolation allowlist)"; fi
done

# snapshot production state/ CONTENT (hashes) + porcelain before running anything
snapshot_state() {
  if [ -d state ]; then
    find state -type f | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
  echo "PORCELAIN:"; git status --porcelain -- state/
}
BEFORE="$(snapshot_state)"

for t in "${SAFE[@]:-}"; do [ -z "$t" ] && continue; run "offline $t" bash "$t"; done

AFTER="$(snapshot_state)"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "  FAIL - production state/ CHANGED during validation (NOT auto-restoring):"
  if ! diff <(printf '%s\n' "$BEFORE") <(printf '%s\n' "$AFTER"); then :; fi
  FAIL=1
else
  echo "  ok   - production state/ unchanged (content hashes + porcelain)"
fi

[ "${#FILES[@]}" -eq 0 ] && [ "$MODE" != "all" ] && echo "  (no changed files to validate)"
echo
[ "$FAIL" -eq 0 ] && echo "== validate_task.sh: PASS ==" || echo "== validate_task.sh: FAIL =="
exit "$FAIL"
