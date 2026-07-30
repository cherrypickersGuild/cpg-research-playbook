#!/usr/bin/env bash
# migrate.sh — the Stage 7 migration command surface (S7-4).
#
# Environment and dispatch only: every option is parsed, and every decision made,
# in Python. This wrapper creates no temporary file, makes no network call, runs
# no Git command, and never re-parses or interpolates an argument — `"$@"` is
# forwarded verbatim, so a path containing spaces survives intact.
#
#   migrate.sh ax-cases [options]      map the AX registry in memory and report.
#                                      DRY-RUN ONLY: it writes nothing at all.
#   migrate.sh entity-assess [options] assess the entity registry. Migrates zero
#                                      entities; writes only to --output.
#   migrate.sh --help                  this text.
#
# `ax-cases --apply` is recognised and REFUSED: applying a migration bundle is
# checkpoint S7-5, which is neither implemented nor approved. It is refused in
# Python, before anything is read or written.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

usage() {
  cat >&2 <<'USAGE'
usage: migrate.sh <command> [options]

commands:
  ax-cases        map the protected AX case registry in memory and print a
                  deterministic JSON dry-run report to stdout. Writes nothing.
                  --registry PATH --overrides PATH --facets-dir PATH
                  --expect-count N --allow-unmappable
                  --run-id ID --migrated-at YYYY-MM-DDTHH:MM:SSZ
  entity-assess   render the entity-registry assessment. Migrates nothing.
                  --registry PATH --output PATH
  --help, -h      show this text

`ax-cases --apply` is refused: apply is checkpoint S7-5 and is not implemented.
USAGE
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

COMMAND="$1"
shift

case "$COMMAND" in
  ax-cases)
    exec python -m src.harvest.migrate.ax_cases "$@"
    ;;
  entity-assess)
    exec python -m src.harvest.migrate.entity_assess "$@"
    ;;
  --help|-h|help)
    usage
    exit 0
    ;;
  *)
    echo "migrate.sh: unknown command '$COMMAND'" >&2
    usage
    exit 2
    ;;
esac
