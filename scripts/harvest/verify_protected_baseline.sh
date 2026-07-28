#!/usr/bin/env bash
# verify_protected_baseline.sh — prove no protected file has changed.
#
# Four checks, in order of strength:
#
#   1. PRIMARY — the exact working-tree bytes byte-match Git's rendering of the
#      implementation-start commit for that path, in the eol_form pinned when
#      the baseline was made. The expected digest is recomputed from the commit
#      on every run, never read as a number from the baseline file.
#   2. the baseline's own recorded digest also agrees with that rendering, so a
#      tampered baseline cannot hide a change.
#   3. the recorded blob_id matches the commit's blob for that path.
#   4. `git diff --exit-code` against the commit — Git's own eol-normalized view.
#
# Checks 1 and 4 are complementary, not redundant. An LF-only rewrite of a file
# that was CRLF on disk is invisible to 4 (git normalizes it away and calls the
# file clean) and caught by 1 (the bytes changed, and the eol_form flipped).
#
#   Usage: bash scripts/harvest/verify_protected_baseline.sh [--quiet]
#
# Exit 0: everything matches. Exit 1: any drift, tampering, or missing input.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec python scripts/harvest/protected_baseline.py verify "$@"
