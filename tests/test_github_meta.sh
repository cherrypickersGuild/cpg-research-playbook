#!/usr/bin/env bash
# test_github_meta.sh — wrapper so validate_task.sh (which runs bash tests) can
# execute the offline github_meta unit tests. All HTTP is mocked in the Python
# suite; NO real network call and NO real GitHub rate limit is consumed.
#   Usage: bash tests/test_github_meta.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python >/dev/null 2>&1 || { echo "  FAIL - python not found"; exit 1; }
# run isolated: no token in env, so the suite controls auth deterministically
env -u GITHUB_TOKEN -u GH_TOKEN python tests/test_github_meta.py
