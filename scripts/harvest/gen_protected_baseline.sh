#!/usr/bin/env bash
# gen_protected_baseline.sh — record the protected-file baseline, ONCE.
#
# Run before implementation; the output is committed. Normal acceptance runs
# call verify_protected_baseline.sh instead, so a rerun can never silently
# bless an accidental modification.
#
# The authority is Git's own rendering of the implementation-start commit, not
# whatever happens to be on disk. See scripts/harvest/protected_baseline.py for
# why both the filtered (checkout) and blob (stored) renderings are accepted and
# why the observed one is pinned per file.
#
#   Usage: bash scripts/harvest/gen_protected_baseline.sh [--replace-baseline]
#
# Exit 0: baseline written. Exit 1: drift, missing commit/path, or an existing
#         baseline without --replace-baseline.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec python scripts/harvest/protected_baseline.py generate "$@"
