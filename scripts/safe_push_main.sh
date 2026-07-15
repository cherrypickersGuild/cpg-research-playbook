#!/usr/bin/env bash
# safe_push_main.sh — gated push of the current repo's main branch to origin.
#   --check    run every safety check and REPORT; never pushes (exit 0 = safe)
#   --execute  run every check, then push origin main (kept ask-gated by perms)
#
# Checks: branch must be main; fetch origin main (unpiped); origin/main must be
# an ancestor of main (no divergence); working diff clean (no whitespace/conflict
# markers) between origin/main..main; then list the commits that would be pushed.
set -euo pipefail
MODE="${1:-}"
case "$MODE" in --check|--execute) ;; *) echo "usage: safe_push_main.sh --check|--execute" >&2; exit 2 ;; esac

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || { echo "safe_push_main.sh: on '$BRANCH', not 'main' — refusing." >&2; exit 3; }

echo "== fetch origin main =="
git fetch origin main

echo "== ancestry (origin/main must be ancestor of main) =="
if ! git merge-base --is-ancestor origin/main main; then
  echo "safe_push_main.sh: origin/main is NOT an ancestor of main (diverged/behind) — stop." >&2
  exit 4
fi

echo "== whitespace/conflict check origin/main..main =="
# Preserved raw harvest artifacts (state/artifacts/*/_raw_*) are captured
# VERBATIM from upstream sources (e.g. an awesome-list README) and may contain
# source-significant trailing whitespace. They are therefore EXEMPT from the
# trailing-whitespace portion of this check ONLY — via a tightly scoped
# pathspec, never a repo-wide file-type exception. Every ordinary file (source,
# scripts, registries, docs, and NON-raw artifacts) is still fully checked by
# the git diff --check below, and the exempted raw artifacts are still scanned
# for leftover merge-conflict markers immediately after, so real corruption can
# never slip through.
RAW_ARTIFACT_PATHSPEC=':(exclude,glob)state/artifacts/*/_raw_*'
git diff --check origin/main..main -- . "$RAW_ARTIFACT_PATHSPEC"
if git diff origin/main..main -- ':(glob)state/artifacts/*/_raw_*' \
     | grep -nE '^\+(<{7}|>{7})' >/dev/null; then
  echo "safe_push_main.sh: leftover merge-conflict marker in a preserved raw artifact — stop." >&2
  exit 5
fi

echo "== commits to push (origin/main..main) =="
git log --oneline origin/main..main
echo "($(git rev-list --count origin/main..main) commit(s) ahead of origin/main)"

if [ "$MODE" = "--check" ]; then
  echo "== --check only: NOT pushing =="
  exit 0
fi

echo "== push origin main =="
git push origin main
echo "== pushed =="
