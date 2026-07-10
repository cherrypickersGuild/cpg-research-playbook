#!/usr/bin/env bash
# test_safe_commit.sh — offline tests for scripts/safe_commit.sh.
# Throwaway local repos only. No network, no real remote, no production writes.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SC="$ROOT/scripts/safe_commit.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   - $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL - $1"; }

# production snapshot = content hashes of every state/ file + porcelain (not just HEAD)
prod_snap(){
  git -C "$ROOT" status --porcelain -- state/ 2>/dev/null
  if [ -d "$ROOT/state" ]; then
    find "$ROOT/state" -type f | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git -C "$ROOT" hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
}
PROD_BEFORE="$(prod_snap)"

newrepo(){
  local d="$TMPROOT/r$RANDOM$RANDOM"; mkdir -p "$d"; cd "$d"
  git init -q -b main; git config user.email t@t; git config user.name t
  echo base > tracked.txt; echo base > other.txt
  git add tracked.txt other.txt; git commit -q -m init
}

echo "[reject] unsafe invocations never commit"
newrepo; h="$(git rev-parse HEAD)"; echo more >> tracked.txt
if bash "$SC" -m m            >/dev/null 2>&1; then bad "empty list";  else ok "empty file list refused"; fi
if bash "$SC" -m m -A         >/dev/null 2>&1; then bad "-A";          else ok "-A refused"; fi
if bash "$SC" -m m .          >/dev/null 2>&1; then bad "'.'";         else ok "'.' refused"; fi
if bash "$SC" -m m '*.txt'    >/dev/null 2>&1; then bad "glob";        else ok "glob refused"; fi
if bash "$SC" -m m nope.txt   >/dev/null 2>&1; then bad "missing";     else ok "missing/untracked refused"; fi
[ "$(git rev-parse HEAD)" = "$h" ] && ok "no commit created by refusals" || bad "a refusal committed"

echo "[fail-closed] pre-existing staged work stays byte- and entry-identical"
newrepo
echo staged >> tracked.txt; git add tracked.txt      # pre-existing staged change
echo unstaged >> other.txt
IDX="$(git ls-files --stage)"; CACHED="$(git diff --cached)"
if bash "$SC" -m m other.txt >/dev/null 2>&1; then bad "should refuse dirty index"; else ok "refused: index already staged"; fi
[ "$(git ls-files --stage)" = "$IDX" ]    && ok "index entries unchanged" || bad "index entries changed"
[ "$(git diff --cached)"    = "$CACHED" ] && ok "staged diff byte-for-byte unchanged" || bad "staged diff changed"

echo "[transactional] a post-staging failure rolls the index back to empty"
newrepo
printf '<<<<<<< HEAD\nboom\n' > conflict.txt          # trips git diff --cached --check
if bash "$SC" -m "add conflict" conflict.txt >/dev/null 2>&1; then bad "should fail on conflict-marker check"; else ok "failed on post-staging check"; fi
if git diff --cached --quiet; then ok "index rolled back to empty after failure"; else bad "index left with staged changes"; fi
[ -f conflict.txt ] && ok "working-tree file left untouched" || bad "working tree altered"

echo "[accept] explicitly named file: staged set must equal requested set"
newrepo; echo change >> tracked.txt
if bash "$SC" -m "edit tracked" tracked.txt >/dev/null 2>&1; then ok "committed named file"; else bad "named commit failed"; fi
files="$(git show --name-only --pretty=format: HEAD | sed '/^$/d')"
[ "$files" = "tracked.txt" ] && ok "commit contains exactly tracked.txt" || bad "commit scope wrong ($files)"

echo "[accept] explicitly named DELETED tracked file commits the deletion"
newrepo; rm tracked.txt                               # working-tree deletion, unstaged
if bash "$SC" -m "remove tracked" tracked.txt >/dev/null 2>&1; then ok "committed deletion by name"; else bad "deletion commit failed"; fi
if git cat-file -e HEAD:tracked.txt 2>/dev/null; then bad "tracked.txt still in HEAD"; else ok "tracked.txt removed in HEAD"; fi

echo "[amend] amends only when --amend is passed"
newrepo; echo a >> other.txt; bash "$SC" -m first other.txt >/dev/null 2>&1
n1="$(git rev-list --count HEAD)"; echo b >> tracked.txt
bash "$SC" -m amended --amend tracked.txt >/dev/null 2>&1
[ "$(git rev-list --count HEAD)" = "$n1" ] && ok "--amend kept commit count" || bad "--amend changed count"

cd "$ROOT"
echo "[production] state/ untouched (content hashes + porcelain), not restored"
[ "$(prod_snap)" = "$PROD_BEFORE" ] && ok "production state/ unchanged" || bad "production changed"
echo; echo "=== $PASS passed, $FAIL failed ==="; [ "$FAIL" -eq 0 ]
