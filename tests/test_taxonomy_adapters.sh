#!/usr/bin/env bash
# test_taxonomy_adapters.sh — feed, jsonapi and seed over the offline fixtures.
#
# Failures this is designed to catch, each of which would otherwise surface only
# after a real harvest had already produced wrong output:
#   * a parser failure reported as an empty source, so an outage looks like a
#     quiet week (or the reverse);
#   * the seed adapter following a child link and quietly becoming a crawler;
#   * a per-source branch creeping into a parser, so adding the 26th source
#     needs code rather than configuration;
#   * an adapter reaching the network, or establishing a pool snapshot itself
#     instead of going through SourceFetchCache.
#
# Entirely offline: the only injected component is the opener. Robots, the RFC
# 9309 matcher, retries, redirects, content-type and byte caps and DV-8
# accounting are all the shipped code. An unfixtured URL or host raises.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/harvest/check_fixtures.py || exit 1
python -m unittest discover -s tests/harvest -p 'test_adapters.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
