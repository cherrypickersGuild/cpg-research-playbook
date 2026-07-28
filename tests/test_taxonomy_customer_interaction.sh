#!/usr/bin/env bash
# test_taxonomy_customer_interaction.sh — decision V4, the external/internal split.
#
# The failure this prevents: counting every chatbot as customer interaction. A
# conversational interface is a MODE of interaction and proves nothing about who
# is on the other end, so customer-interaction (priority, strictly external) is a
# separate value from conversational-assistant (standard, explicitly including
# internal employee copilots).
#
# The coverage consequence is asserted directly: five internal copilots leave the
# Customer Interaction target completely unmet, because a standard value can
# never satisfy a priority value's target on its own.
#
# Offline, no network, no production state. Asserts state/ and config/ untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m unittest discover -s tests/harvest -p 'test_customer_interaction.py' -v
EC=$?

DIRTY="$(git status --porcelain --untracked-files=no -- state/ config/)"
if [ -n "$DIRTY" ]; then
  echo "FAIL - production state/ or config/ was modified by this test:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

exit "$EC"
