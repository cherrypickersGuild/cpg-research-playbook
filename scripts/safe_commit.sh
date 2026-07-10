#!/usr/bin/env bash
# safe_commit.sh — stage ONLY explicitly named files, then commit.
#
# Safety properties:
#   * refuses -A/-a/--all, '.', globs, unknown flags, directories, empty list
#   * FAILS CLOSED if the index already holds staged changes — it never alters
#     or unstages pre-existing staged work
#   * transactional staging: it only runs on an empty index, so if any
#     post-staging check fails it rolls the index back to that empty state
#     (working tree left untouched) before exiting non-zero
#   * verifies the staged set EXACTLY equals the requested set before committing
#   * supports explicitly named tracked files that were deleted from the tree
#   * does not amend unless --amend is passed
#
#   Usage: bash scripts/safe_commit.sh -m "message" [--amend] <path> [path ...]
set -euo pipefail

MSG=""; AMEND=0; declare -a FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -m|--message) shift; MSG="${1:-}" ;;
    --amend) AMEND=1 ;;
    -A|-a|--all)        echo "safe_commit.sh: refusing '$1' — name files explicitly." >&2; exit 2 ;;
    .|./|--|-p|--patch) echo "safe_commit.sh: refusing broad/ambiguous arg '$1'." >&2; exit 2 ;;
    -*)                 echo "safe_commit.sh: refusing unknown/unsafe flag '$1'." >&2; exit 2 ;;
    *)                  FILES+=("$1") ;;
  esac
  shift
done
[ -n "$MSG" ] || { echo "safe_commit.sh: commit message required (-m \"...\")." >&2; exit 2; }
[ "${#FILES[@]}" -gt 0 ] || { echo "safe_commit.sh: no files named — refusing empty commit set." >&2; exit 2; }

# fail closed: never run (or touch the index) if staged changes already exist
if ! git diff --cached --quiet; then
  echo "safe_commit.sh: index already has staged changes — refusing; nothing was altered." >&2
  echo "                commit/unstage them first, or include them by name and retry." >&2
  exit 5
fi

# validate each named path: reject globs & directories; allow paths that either
# exist OR are tracked-but-deleted (so a deletion can be committed by name)
for f in "${FILES[@]}"; do
  case "$f" in *'*'*|*'?'*|*'['*|*']'*) echo "safe_commit.sh: refusing wildcard '$f'." >&2; exit 2 ;; esac
  if [ -d "$f" ]; then echo "safe_commit.sh: '$f' is a directory — name files, not directories." >&2; exit 2; fi
  if [ ! -e "$f" ] && ! git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    echo "safe_commit.sh: '$f' does not exist and is not a tracked file." >&2; exit 2
  fi
done

# from here the index was verified empty; roll back to that empty state on any
# post-staging failure (working tree is never touched)
rollback_and_exit() {
  git reset -q
  echo "safe_commit.sh: staging rolled back; index restored to empty, working tree untouched." >&2
  exit "$1"
}

if ! git add -- "${FILES[@]}"; then rollback_and_exit 4; fi

# verify the staged set EXACTLY equals the requested set (no more, no less)
REQ="$(printf '%s\n' "${FILES[@]}" | sed 's#^\./##' | LC_ALL=C sort -u)"
STAGED="$(git -c core.quotepath=false diff --cached --name-only | LC_ALL=C sort -u)"
if [ "$REQ" != "$STAGED" ]; then
  echo "safe_commit.sh: staged set != requested set — refusing." >&2
  echo "--- requested ---" >&2; printf '%s\n' "$REQ" >&2
  echo "--- staged ---"    >&2; printf '%s\n' "$STAGED" >&2
  echo "(a named file may have had no changes, or expanded to multiple paths)" >&2
  rollback_and_exit 6
fi

echo "== staged files =="; git diff --cached --name-only
echo "== staged stat ==";  git diff --cached --stat
echo "== whitespace/conflict check =="
if ! git diff --cached --check; then
  echo "safe_commit.sh: whitespace/conflict-marker check failed." >&2
  rollback_and_exit 7
fi

if [ "$AMEND" -eq 1 ]; then
  git commit --amend -m "$MSG" || rollback_and_exit 8
else
  git commit -m "$MSG" || rollback_and_exit 8
fi
echo "== committed =="; git log -1 --oneline
