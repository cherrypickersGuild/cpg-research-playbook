#!/usr/bin/env bash
# harvest.sh — the taxonomy harvest command surface (Stage 9, checkpoint S9-1).
#
# Environment and dispatch only, on the committed `migrate.sh` pattern. This
# wrapper parses no option, makes no decision, creates no temporary file, makes
# no network call, runs no Git command and selects no state root. `"$@"` is
# forwarded verbatim, so a path containing spaces survives intact, and `exec`
# hands the Python process's real exit code straight back to the caller.
#
# Usage, help and the command list live in Python and ONLY in Python. Two usage
# documents drift; one does not. That includes the zero-argument case, which is
# forwarded rather than intercepted here.
#
# No harvest subcommand is implemented yet. Stage 9 registers each one in the
# checkpoint that implements it; `harvest.sh --help` says which.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

exec python -m src.harvest.cli "$@"
