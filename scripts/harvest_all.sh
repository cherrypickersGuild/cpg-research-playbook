#!/usr/bin/env bash
# harvest_all.sh — sequential, resumable orchestrator that grows every entity
# topic (agent, mcp, prompt, skill) and then the AX-case registry to their FINAL
# verified-record targets, one stage at a time. Thin wrapper over the two
# per-lane harvesters (scripts/harvest_entities.sh, scripts/harvest_ax_cases.sh)
# — it owns ordering, skipping, and an honest pass/fail summary; it does NOT
# duplicate their loop/merge logic.
#
#   Usage:
#     bash scripts/harvest_all.sh                 # agent -> mcp -> prompt -> skill -> AX
#     bash scripts/harvest_all.sh --entities-only # the four entity topics only
#     bash scripts/harvest_all.sh --ax-only       # AX cases only
#
#   Targets (final totals, NOT amounts to add; existing records count):
#     ENTITY_TARGET (default 250, per entity topic)
#     AX_TARGET     (default 250, total AX verified cases)
#   Smoke example (isolated fixture): ENTITY_TARGET=5 AX_TARGET=3 STATE_DIR=/tmp/fix bash scripts/harvest_all.sh
#   Loop tuning + isolation knobs (BATCH_SIZE, MAX_LOOPS, NO_PROGRESS_THRESHOLD,
#   STATE_DIR, CLAUDE_BIN) are read by the child scripts and inherited from this
#   process's environment — set them as a prefix and they flow through.
#
# Sequential and bounded: each stage runs to completion before the next starts
# (no `&`, no parallelism); each child is itself bounded by MAX_LOOPS /
# NO_PROGRESS_THRESHOLD. Resumable: every stage first runs the child's --check,
# so an interrupted run resumes from the merged registry counts and never
# re-harvests a topic already at target.
#
# NO FALSE SUCCESS: a child harvester exits 0 even when it stops at MAX_LOOPS or
# NO_PROGRESS_THRESHOLD *below* target — so this orchestrator NEVER trusts a
# child's exit code as "reached target". After each child returns it re-runs
# --check; a stage counts as complete ONLY when --check reports status=complete.
# If any requested stage is still below target at the end, harvest_all.sh exits
# non-zero.
#
# Exit 0: every requested stage is at/above its target.
# Exit 1: at least one requested stage is still below target (bounded out or the
#         child errored) — the summary names which.
# Exit 2: bad arguments / non-integer target / missing dependency.

set -uo pipefail   # deliberately NOT -e: one stage failing must not abort the rest.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENT="$ROOT/scripts/harvest_entities.sh"
AX="$ROOT/scripts/harvest_ax_cases.sh"
[ -f "$ENT" ] || { echo "ERROR: not found: $ENT" >&2; exit 2; }
[ -f "$AX" ]  || { echo "ERROR: not found: $AX"  >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 2; }

ENTITY_TARGET="${ENTITY_TARGET:-250}"
AX_TARGET="${AX_TARGET:-250}"
case "$ENTITY_TARGET" in ''|*[!0-9]*) echo "ERROR: ENTITY_TARGET must be a positive integer (got '$ENTITY_TARGET')." >&2; exit 2 ;; esac
case "$AX_TARGET"     in ''|*[!0-9]*) echo "ERROR: AX_TARGET must be a positive integer (got '$AX_TARGET')." >&2; exit 2 ;; esac

MODE="all"
case "${1:-}" in
  ""|--all)        MODE="all" ;;
  --entities-only) MODE="entities" ;;
  --ax-only)       MODE="ax" ;;
  *) echo "Usage: bash scripts/harvest_all.sh [--all|--entities-only|--ax-only]" >&2; exit 2 ;;
esac

summary=()
incomplete=0

# is_complete <status-line> -> 0 if the line reports status=complete, else 1
is_complete() { case "$1" in *"status=complete"*) return 0 ;; *) return 1 ;; esac; }

# run_stage <label> <child-script> <args...> : pre-check (skip if complete),
# else run the child, then POST-check to decide completion honestly.
run_stage() {
  local label="$1"; shift
  local child="$1"; shift
  # $@ now holds the child's positional args (topic/target), WITHOUT --check
  echo ""
  echo "=== [$label] ==="

  local pre
  pre="$(bash "$child" "$@" --check)"
  echo "  pre : $pre"
  if is_complete "$pre"; then
    echo "  skip: already at/above target — no harvest launched."
    summary+=("$label  COMPLETE (skipped; already at target)")
    return 0
  fi

  echo "  run : bash $child $*"
  local child_ec=0
  bash "$child" "$@" || child_ec=$?

  local post
  post="$(bash "$child" "$@" --check)"
  echo "  post: $post"
  if is_complete "$post"; then
    summary+=("$label  COMPLETE")
    return 0
  fi

  incomplete=$((incomplete+1))
  if [ "$child_ec" -ne 0 ]; then
    summary+=("$label  INCOMPLETE (child exited $child_ec; still below target)")
  else
    summary+=("$label  INCOMPLETE (bounded by MAX_LOOPS/NO_PROGRESS; still below target)")
  fi
  return 1
}

echo "[harvest_all] mode=$MODE  ENTITY_TARGET=$ENTITY_TARGET  AX_TARGET=$AX_TARGET"

if [ "$MODE" = "all" ] || [ "$MODE" = "entities" ]; then
  for topic in agent mcp prompt skill; do
    run_stage "entity:$topic" "$ENT" "$topic" "$ENTITY_TARGET"
  done
fi
if [ "$MODE" = "all" ] || [ "$MODE" = "ax" ]; then
  run_stage "ax_cases" "$AX" "$AX_TARGET"
fi

echo ""
echo "=== harvest_all summary ==="
if [ "${#summary[@]}" -gt 0 ]; then
  for s in "${summary[@]}"; do echo "  $s"; done
fi
if [ "$incomplete" -gt 0 ]; then
  echo "RESULT: $incomplete stage(s) still below target — harvest INCOMPLETE."
  exit 1
fi
echo "RESULT: all requested stages at/above target — harvest COMPLETE."
exit 0
