#!/usr/bin/env bash
# harvest_parallel.sh — run the harvest lanes CONCURRENTLY and then fold the
# per-topic shards into the union registry.
#
# Parallel sibling of scripts/harvest_all.sh, which remains the sequential
# orchestrator. Same contract, same honesty rules, same targets — the only
# difference is that the lanes overlap in time instead of queueing:
#
#     harvest_all.sh       agent -> mcp -> prompt -> skill -> ax     (serial)
#     harvest_parallel.sh  agent | mcp | prompt | skill | ax         (concurrent)
#                                        |
#                                        v
#                          merge_building_blocks.sh  -> entity_registry.json
#
# WHY THIS IS SAFE. Each lane writes only files it exclusively owns: its
# BuildingBlocks shard, its ledger shard, its GitHub-metadata cache shard, and
# its already-per-topic scratch files. No two lanes read-modify-write the same
# path, so there is no lost update and no shared temp file to interleave into.
# The union registry is written by exactly ONE process — the merge step below —
# after every lane has finished, under the union lock. Each lane additionally
# holds a per-topic lane lock for its whole run, so launching this script twice
# does not produce two writers per shard; the second invocation's lanes refuse
# to start and are reported as such.
#
# WHAT IS DELIBERATELY *NOT* PARALLELISED. The fold at the end is single-writer
# by design. Four concurrent merges into one union is the exact defect this
# whole change removes; doing it once, at the end, costs ~2 s.
#
# FAILURE ISOLATION. `wait` is per-PID, so one lane dying (rate limit, network,
# bad batch) never aborts the others — its exit code is captured and reported,
# and the fold still runs so the surviving lanes' work reaches the union.
#
# STAGGERED START. Lanes are launched STAGGER_SEC apart (default 20). Four cold
# `claude -p` calls fired in the same instant is the shape most likely to trip
# the session rate limit, which fails all lanes at once — the opposite of the
# isolation this design is for.
#
#   Usage:
#     bash scripts/harvest_parallel.sh                  # 4 entity lanes + AX
#     bash scripts/harvest_parallel.sh --entities-only  # 4 entity lanes
#     bash scripts/harvest_parallel.sh --topics agent,mcp
#     bash scripts/harvest_parallel.sh --no-merge       # skip the union fold
#     bash scripts/harvest_parallel.sh --dry-run        # show the plan, run nothing
#
#   Env: ENTITY_TARGET (250) · AX_TARGET (250) · STAGGER_SEC (20) ·
#        plus everything the children read (BATCH_SIZE, MAX_LOOPS,
#        NO_PROGRESS_THRESHOLD, STATE_DIR, CLAUDE_BIN, MODEL).
#
# Per-lane console output goes to state/logs/parallel_<run_id>/<lane>.log —
# interleaving five lanes onto one terminal would make every log unreadable.
#
# Exit 0: every requested lane is at/above target AND the fold succeeded.
# Exit 1: at least one lane below target, or the fold failed — the summary names
#         which. As in harvest_all.sh, a child's exit code is NEVER trusted as
#         "reached target"; completion is decided by re-running the child's
#         --check afterwards.
# Exit 2: bad arguments or a missing dependency.
set -uo pipefail   # deliberately NOT -e: one lane failing must not abort the rest.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENT="$ROOT/scripts/harvest_entities.sh"
AX="$ROOT/scripts/harvest_ax_cases.sh"
FOLD="$ROOT/scripts/merge_building_blocks.sh"
for f in "$ENT" "$AX" "$FOLD"; do
  [ -f "$f" ] || { echo "ERROR: not found: $f" >&2; exit 2; }
done
command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 2; }

ENTITY_TARGET="${ENTITY_TARGET:-250}"
AX_TARGET="${AX_TARGET:-250}"
STAGGER_SEC="${STAGGER_SEC:-20}"
for v in ENTITY_TARGET AX_TARGET STAGGER_SEC; do
  case "${!v}" in ''|*[!0-9]*) echo "ERROR: $v must be a non-negative integer (got '${!v}')." >&2; exit 2 ;; esac
done

TOPICS="agent mcp prompt skill"
RUN_AX=true
DO_MERGE=true
DRY_RUN=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    ""|--all)        ;;
    --entities-only) RUN_AX=false ;;
    --ax-only)       TOPICS="" ;;
    --no-merge)      DO_MERGE=false ;;
    --dry-run)       DRY_RUN=true ;;
    --topics)
      shift
      [ "$#" -gt 0 ] || { echo "ERROR: --topics needs a comma-separated list." >&2; exit 2; }
      TOPICS="$(printf '%s' "$1" | tr ',' ' ')"
      RUN_AX=false
      for t in $TOPICS; do
        case "$t" in agent|mcp|prompt|skill) ;;
          *) echo "ERROR: unknown topic '$t' (expected agent|mcp|prompt|skill)." >&2; exit 2 ;;
        esac
      done ;;
    *) echo "Usage: bash scripts/harvest_parallel.sh [--all|--entities-only|--ax-only] [--topics a,b] [--no-merge] [--dry-run]" >&2; exit 2 ;;
  esac
  shift
done

STATE="${STATE_DIR:-$ROOT/state}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LOGDIR="$STATE/logs/parallel_$RUN_ID"

echo "[parallel] run_id=$RUN_ID"
echo "[parallel] topics='$TOPICS' ax=$RUN_AX  ENTITY_TARGET=$ENTITY_TARGET AX_TARGET=$AX_TARGET stagger=${STAGGER_SEC}s"
echo "[parallel] per-lane logs: $LOGDIR/"

# --- pre-check every lane (cheap, read-only) --------------------------------
# Same skip rule as harvest_all.sh: a lane already at target is never launched.
declare -a LANES=() SKIPPED=()
for t in $TOPICS; do
  pre="$(bash "$ENT" "$t" "$ENTITY_TARGET" --check 2>&1)"
  echo "  pre  entity:$t : $pre"
  case "$pre" in
    *"status=complete"*) SKIPPED+=("entity:$t") ;;
    *) LANES+=("entity:$t") ;;
  esac
done
if [ "$RUN_AX" = true ]; then
  pre="$(bash "$AX" "$AX_TARGET" --check 2>&1)"
  echo "  pre  ax_cases  : $pre"
  case "$pre" in
    *"status=complete"*) SKIPPED+=("ax_cases") ;;
    *) LANES+=("ax_cases") ;;
  esac
fi

if [ "$DRY_RUN" = true ]; then
  echo "[parallel] dry-run — would launch: ${LANES[*]:-<none>}"
  echo "[parallel] dry-run — would skip  : ${SKIPPED[*]:-<none>}"
  [ "$DO_MERGE" = true ] && echo "[parallel] dry-run — would then fold shards -> union via $(basename "$FOLD")"
  exit 0
fi

if [ "${#LANES[@]}" -eq 0 ]; then
  echo "[parallel] nothing to do — every requested lane is already at target."
  [ "$DO_MERGE" = true ] && { echo ""; bash "$FOLD" || exit 1; }
  exit 0
fi

mkdir -p "$LOGDIR"

# --- launch ------------------------------------------------------------------
# Bash arrays keep PID -> lane association; `wait <pid>` then yields that lane's
# real exit code. (`wait` with no argument returns only the LAST job's status,
# which would silently hide every other lane's failure.)
declare -a PIDS=() PIDLANE=()
launched=0
for lane in "${LANES[@]}"; do
  if [ "$launched" -gt 0 ] && [ "$STAGGER_SEC" -gt 0 ]; then sleep "$STAGGER_SEC"; fi
  log="$LOGDIR/${lane//:/_}.log"
  case "$lane" in
    entity:*)
      topic="${lane#entity:}"
      echo "[parallel] launch $lane  -> $log"
      bash "$ENT" "$topic" "$ENTITY_TARGET" >"$log" 2>&1 &
      ;;
    ax_cases)
      echo "[parallel] launch $lane  -> $log"
      bash "$AX" "$AX_TARGET" >"$log" 2>&1 &
      ;;
  esac
  PIDS+=("$!"); PIDLANE+=("$lane")
  launched=$((launched+1))
done
echo "[parallel] $launched lane(s) running concurrently; waiting…"

# --- wait, per lane ----------------------------------------------------------
declare -a LANE_EC=()
for i in "${!PIDS[@]}"; do
  wait "${PIDS[$i]}"; ec=$?
  LANE_EC+=("$ec")
  echo "[parallel] lane ${PIDLANE[$i]} exited $ec"
done

# --- fold shards -> union (single writer, after all lanes are done) ----------
FOLD_EC=0
if [ "$DO_MERGE" = true ]; then
  echo ""
  echo "=== [fold] shards -> entity_registry.json ==="
  bash "$FOLD" || FOLD_EC=$?
  [ "$FOLD_EC" -ne 0 ] && echo "[parallel] WARNING: union fold failed (exit $FOLD_EC) — the shards still hold every harvested entity; re-run: bash scripts/merge_building_blocks.sh" >&2
else
  echo "[parallel] --no-merge: shards NOT folded into the union. Run scripts/merge_building_blocks.sh when ready."
fi

# --- honest post-check -------------------------------------------------------
echo ""
echo "=== harvest_parallel summary (run_id=$RUN_ID) ==="
incomplete=0
for s in "${SKIPPED[@]:-}"; do [ -n "$s" ] && echo "  $s  COMPLETE (skipped; already at target)"; done
for i in "${!PIDLANE[@]}"; do
  lane="${PIDLANE[$i]}"; ec="${LANE_EC[$i]}"
  case "$lane" in
    entity:*) post="$(bash "$ENT" "${lane#entity:}" "$ENTITY_TARGET" --check 2>&1)" ;;
    ax_cases) post="$(bash "$AX" "$AX_TARGET" --check 2>&1)" ;;
  esac
  case "$post" in
    *"status=complete"*) echo "  $lane  COMPLETE   ($post)" ;;
    *)
      incomplete=$((incomplete+1))
      if [ "$ec" -ne 0 ]; then
        echo "  $lane  INCOMPLETE (lane exited $ec; still below target) ($post)"
        echo "                 log: $LOGDIR/${lane//:/_}.log"
      else
        echo "  $lane  INCOMPLETE (bounded by MAX_LOOPS/NO_PROGRESS) ($post)"
      fi ;;
  esac
done

if [ "$FOLD_EC" -ne 0 ]; then
  echo "RESULT: union fold FAILED — harvest INCOMPLETE."
  exit 1
fi
if [ "$incomplete" -gt 0 ]; then
  echo "RESULT: $incomplete lane(s) still below target — harvest INCOMPLETE."
  exit 1
fi
echo "RESULT: all requested lanes at/above target and folded into the union — harvest COMPLETE."
exit 0
