#!/usr/bin/env bash
# run_matrix.sh — type a list of categories and topics; expand and harvest every
# (category, topic) cell CONCURRENTLY.
#
#   bash scripts/run_matrix.sh --categories "healthcare,finance" --topics "agent,rag"
#
# builds the 2x2 matrix and runs four independent lanes at once:
#
#     category#1_topic#1  healthcare x agent  ─┐
#     category#1_topic#2  healthcare x rag    ─┤  each lane: expand -> harvest
#     category#2_topic#1  finance    x agent  ─┤  each lane owns every file it writes
#     category#2_topic#2  finance    x rag    ─┘
#
# Each lane does its OWN query expansion and then its own harvest, so expansions
# run in parallel with each other and no lane waits at a phase barrier for the
# slowest expansion. Use --phased if you want every expansion finished and
# reviewable before any harvesting starts.
#
# CONCURRENCY IS CAPPED. A 4x5 matrix is 20 cells; launching 20 model lanes at
# once would exhaust the account session limit in minutes and fail all of them
# together — the opposite of what parallelism is for. MAX_PARALLEL (default 4)
# bounds how many lanes are in flight; the rest queue. Raise it only if you know
# you have the quota.
#
#   Usage:
#     bash scripts/run_matrix.sh --categories "a,b" --topics "x,y" [options]
#     bash scripts/run_matrix.sh --spec matrix.json [options]
#
#   Options:
#     --expand-only        run query expansion, no harvesting
#     --harvest-only       harvest using query sets that already exist
#     --phased             finish ALL expansions before ANY harvest starts
#     --cells "1:1,2:3"    restrict to specific i:j cells
#     --target N           verified entities per cell (default 60)
#     --queries N          active queries per cell (default 24)
#     --fold               also build state/matrix/matrix_union.json
#     --dry-run            print the plan and exit
#
#   Env: MAX_PARALLEL (4) · STAGGER_SEC (15) · CLAUDE_BIN · STATE_DIR · MODEL ·
#        plus the per-cell loop knobs (BATCH_SIZE, MAX_LOOPS, …).
#
# Per-lane output goes to state/logs/matrix_<run_id>/<cell_id>.log — interleaving
# a dozen lanes onto one terminal is unreadable.
#
# Exit 0: every requested cell reached its target (and the fold, if asked, worked).
# Exit 1: at least one cell is below target or a step failed — the summary names which.
# Exit 2: bad arguments or a missing dependency.
set -uo pipefail   # NOT -e: one lane failing must not abort the rest.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SPEC_PY="$ROOT/scripts/matrix_spec.py"
EXPAND="$ROOT/scripts/expand_queries_cell.sh"
HARVEST="$ROOT/scripts/harvest_matrix_cell.sh"
for f in "$SPEC_PY" "$EXPAND" "$HARVEST"; do
  [ -f "$f" ] || { echo "ERROR: not found: $f" >&2; exit 2; }
done
command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 2; }
command -v python >/dev/null 2>&1 || { echo "ERROR: 'python' not found." >&2; exit 2; }

CATEGORIES=""; TOPICS=""; SPEC=""; CELLS_FILTER=""
DO_EXPAND=true; DO_HARVEST=true; PHASED=false; DRY_RUN=false; DO_FOLD=false
TARGET=60; QUERIES=24
while [ "$#" -gt 0 ]; do
  case "$1" in
    --categories) shift; CATEGORIES="${1:-}" ;;
    --topics)     shift; TOPICS="${1:-}" ;;
    --spec)       shift; SPEC="${1:-}" ;;
    --cells)      shift; CELLS_FILTER="${1:-}" ;;
    --target)     shift; TARGET="${1:-}" ;;
    --queries)    shift; QUERIES="${1:-}" ;;
    --expand-only)  DO_HARVEST=false ;;
    --harvest-only) DO_EXPAND=false ;;
    --phased)       PHASED=true ;;
    --fold)         DO_FOLD=true ;;
    --dry-run)      DRY_RUN=true ;;
    *) echo "Usage: bash scripts/run_matrix.sh --categories \"a,b\" --topics \"x,y\" [--spec F] [--cells i:j,…] [--target N] [--queries N] [--expand-only|--harvest-only] [--phased] [--fold] [--dry-run]" >&2; exit 2 ;;
  esac
  shift
done
for v in TARGET QUERIES; do
  case "${!v}" in ''|*[!0-9]*) echo "ERROR: --${v,,} must be a positive integer (got '${!v}')." >&2; exit 2 ;; esac
done
MAX_PARALLEL="${MAX_PARALLEL:-4}"
STAGGER_SEC="${STAGGER_SEC:-15}"
case "$MAX_PARALLEL" in ''|*[!0-9]*|0) echo "ERROR: MAX_PARALLEL must be a positive integer (got '$MAX_PARALLEL')." >&2; exit 2 ;; esac

if [ "$DO_EXPAND" = false ] && [ "$DO_HARVEST" = false ]; then
  echo "ERROR: --expand-only and --harvest-only are mutually exclusive." >&2; exit 2
fi

STATE="${STATE_DIR:-$ROOT/state}"
MDIR="$STATE/matrix"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LOGDIR="$STATE/logs/matrix_$RUN_ID"

# --- build (or reuse) the manifest ------------------------------------------
# --harvest-only with no list given reuses the existing manifest, so a follow-up
# run does not have to retype the lists and cannot accidentally renumber the
# cells (which would point every i:j at a different intersection).
if [ -n "$SPEC" ]; then
  python "$SPEC_PY" --spec "$SPEC" --state "$STATE" >/dev/null || exit 2
elif [ -n "$CATEGORIES" ] || [ -n "$TOPICS" ]; then
  python "$SPEC_PY" --categories "$CATEGORIES" --topics "$TOPICS" --state "$STATE" >/dev/null || exit 2
elif [ -f "$MDIR/manifest.json" ]; then
  echo "[matrix] no lists given — reusing the existing manifest at $MDIR/manifest.json"
else
  echo "ERROR: give --categories and --topics (or --spec), or run once before using --harvest-only." >&2
  exit 2
fi

MANIFEST="$MDIR/manifest.json"
jq empty "$MANIFEST" 2>/dev/null || { echo "ERROR: $MANIFEST is not valid JSON." >&2; exit 2; }

# --- select cells ------------------------------------------------------------
# IFS includes \r, not just \t: the jq build on this platform writes CRLF, and
# `read` strips only the \n — which would leave a trailing carriage return in the
# LAST field (cid) and nowhere else. That CR is invisible in output yet ends up
# in log filenames and lock keys. Command substitution "$(jq …)" strips it, which
# is why only these @tsv read loops need the guard.
declare -a CELL_I=() CELL_J=() CELL_ID=() CELL_LABEL=()
while IFS=$'\t\r' read -r i j cat top cid; do
  [ -z "${i:-}" ] && continue
  if [ -n "$CELLS_FILTER" ]; then
    case ",$CELLS_FILTER," in *",$i:$j,"*) ;; *) continue ;; esac
  fi
  CELL_I+=("$i"); CELL_J+=("$j"); CELL_ID+=("$cid"); CELL_LABEL+=("$cat x $top")
done < <(jq -r '.cells[] | [.i,.j,.category,.topic,.cell_id] | @tsv' "$MANIFEST")

if [ "${#CELL_I[@]}" -eq 0 ]; then
  echo "ERROR: no cells selected (check --cells)." >&2; exit 2
fi

echo "[matrix] run_id=$RUN_ID"
echo "[matrix] cells=${#CELL_I[@]}  expand=$DO_EXPAND harvest=$DO_HARVEST phased=$PHASED"
echo "[matrix] target=$TARGET verified/cell  queries=$QUERIES/cell  max_parallel=$MAX_PARALLEL  stagger=${STAGGER_SEC}s"
echo "[matrix] per-cell logs: $LOGDIR/"
for k in "${!CELL_I[@]}"; do
  printf '[matrix]   %-22s %s\n' "${CELL_ID[$k]}" "${CELL_LABEL[$k]}"
done

if [ "$DRY_RUN" = true ]; then
  echo "[matrix] dry-run — nothing launched."
  exit 0
fi
mkdir -p "$LOGDIR"

# --- bounded-concurrency launcher -------------------------------------------
# Bash has no worker pool, and the obvious implementations are both wrong here:
#   * `kill -0 $pid` cannot detect a finished lane — a background child that has
#     exited is a ZOMBIE until it is waited on, and the process entry still
#     exists, so `kill -0` keeps reporting it alive forever.
#   * `wait -n` unblocks on the first exit but does not say WHICH child it was,
#     and it REAPS that child, so a later `wait $pid` for it returns "no such
#     job" instead of the real exit code.
# `jobs -rp` lists only still-RUNNING children, so a pid that has dropped off
# that list is finished and can be waited on for its true status exactly once.
POLL_SEC="${POLL_SEC:-2}"
declare -A LANE_EC=()
declare -a RUNNING_PID=() RUNNING_KEY=()

reap_one() {   # block until at least one lane finishes; record its exit code
  local running_now idx pid reaped
  while :; do
    running_now=" $(jobs -rp | tr '\n' ' ') "
    local -a np=() nk=()
    reaped=0
    for idx in "${!RUNNING_PID[@]}"; do
      pid="${RUNNING_PID[$idx]}"
      case "$running_now" in
        *" $pid "*) np+=("$pid"); nk+=("${RUNNING_KEY[$idx]}") ;;
        *) wait "$pid" 2>/dev/null; LANE_EC["${RUNNING_KEY[$idx]}"]=$?
           echo "[matrix] done   ${RUNNING_KEY[$idx]} (exit ${LANE_EC[${RUNNING_KEY[$idx]}]})"
           reaped=1 ;;
      esac
    done
    RUNNING_PID=(); RUNNING_KEY=()
    [ "${#np[@]}" -gt 0 ] && RUNNING_PID=("${np[@]}")
    [ "${#nk[@]}" -gt 0 ] && RUNNING_KEY=("${nk[@]}")
    [ "$reaped" -eq 1 ] && return 0
    sleep "$POLL_SEC"
  done
}

launch() {
  local key="$1"; shift
  while [ "${#RUNNING_PID[@]}" -ge "$MAX_PARALLEL" ]; do reap_one; done
  if [ "${#RUNNING_PID[@]}" -gt 0 ] && [ "$STAGGER_SEC" -gt 0 ]; then sleep "$STAGGER_SEC"; fi
  echo "[matrix] launch $key"
  "$@" &
  RUNNING_PID+=("$!"); RUNNING_KEY+=("$key")
}

drain() { while [ "${#RUNNING_PID[@]}" -gt 0 ]; do reap_one; done; }

# One lane = expand then harvest for a single cell, in one background process.
# Chaining inside the lane is what makes it "each by each": cell 3 starts
# harvesting the moment ITS OWN expansion is done, without waiting for cell 7's.
cell_lane() {
  local i="$1" j="$2" log="$3"
  {
    if [ "$DO_EXPAND" = true ]; then
      TARGET_QUERIES="$QUERIES" bash "$EXPAND" "$i" "$j" || exit $?
    fi
    if [ "$DO_HARVEST" = true ]; then
      bash "$HARVEST" "$i" "$j" "$TARGET" || exit $?
    fi
  } >"$log" 2>&1
}

expand_lane() {
  local i="$1" j="$2" log="$3"
  TARGET_QUERIES="$QUERIES" bash "$EXPAND" "$i" "$j" >"$log" 2>&1
}

harvest_lane() {
  local i="$1" j="$2" log="$3"
  bash "$HARVEST" "$i" "$j" "$TARGET" >>"$log" 2>&1
}

if [ "$PHASED" = true ] && [ "$DO_EXPAND" = true ] && [ "$DO_HARVEST" = true ]; then
  echo ""; echo "=== phase 1: query expansion, ${#CELL_I[@]} cell(s), capped at $MAX_PARALLEL ==="
  for k in "${!CELL_I[@]}"; do
    launch "${CELL_ID[$k]}" expand_lane "${CELL_I[$k]}" "${CELL_J[$k]}" "$LOGDIR/${CELL_ID[$k]}.log"
  done
  drain
  echo ""; echo "=== phase 2: harvest, ${#CELL_I[@]} cell(s), capped at $MAX_PARALLEL ==="
  for k in "${!CELL_I[@]}"; do
    launch "${CELL_ID[$k]}" harvest_lane "${CELL_I[$k]}" "${CELL_J[$k]}" "$LOGDIR/${CELL_ID[$k]}.log"
  done
  drain
else
  echo ""; echo "=== running ${#CELL_I[@]} cell lane(s), capped at $MAX_PARALLEL concurrent ==="
  for k in "${!CELL_I[@]}"; do
    launch "${CELL_ID[$k]}" cell_lane "${CELL_I[$k]}" "${CELL_J[$k]}" "$LOGDIR/${CELL_ID[$k]}.log"
  done
  drain
fi

# --- optional fold -----------------------------------------------------------
FOLD_EC=0
if [ "$DO_FOLD" = true ]; then
  echo ""; echo "=== [fold] cells -> matrix_union.json ==="
  bash "$ROOT/scripts/merge_matrix.sh" || FOLD_EC=$?
fi

# --- honest post-check -------------------------------------------------------
echo ""
echo "=== run_matrix summary (run_id=$RUN_ID) ==="
incomplete=0
for k in "${!CELL_I[@]}"; do
  cid="${CELL_ID[$k]}"
  if [ "$DO_HARVEST" = true ]; then
    post="$(bash "$HARVEST" "${CELL_I[$k]}" "${CELL_J[$k]}" "$TARGET" --check 2>&1)"
  else
    post="$(TARGET_QUERIES="$QUERIES" bash "$EXPAND" "${CELL_I[$k]}" "${CELL_J[$k]}" --check 2>&1)"
  fi
  ec="${LANE_EC[$cid]:-0}"
  case "$post" in
    *"status=complete"*) printf '  %-22s COMPLETE   %s\n' "$cid" "$post" ;;
    *)
      incomplete=$((incomplete+1))
      printf '  %-22s INCOMPLETE %s\n' "$cid" "$post"
      [ "$ec" -ne 0 ] && printf '  %-22s            lane exited %s — log: %s\n' "" "$ec" "$LOGDIR/$cid.log"
      ;;
  esac
done

if [ "$FOLD_EC" -ne 0 ]; then
  echo "RESULT: cell fold FAILED (exit $FOLD_EC) — the cell files still hold every harvested entity."
  exit 1
fi
if [ "$incomplete" -gt 0 ]; then
  echo "RESULT: $incomplete cell(s) still below target — matrix run INCOMPLETE."
  exit 1
fi
echo "RESULT: all ${#CELL_I[@]} cell(s) at/above target — matrix run COMPLETE."
exit 0
