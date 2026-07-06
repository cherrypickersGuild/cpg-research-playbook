#!/usr/bin/env bash
# refresh.sh — the closed cycle (1D). Re-searches only STALE keywords, then runs
# the discovery pass for them. Safe to schedule (cron / Task Scheduler) often;
# it does nothing until a strategy crosses REFRESH_DAYS.
#   Usage: bash refresh.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' not on PATH."; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "ERROR: 'jq' not found."; exit 1; }
S1="$ROOT/agents/stage1"; STATE="$ROOT/state"
FLAGS=(--output-format json); [ -n "$MODEL" ] && FLAGS+=(--model "$MODEL"); [ "$USE_BARE" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "$EXTRA_FLAGS" ] && FLAGS+=($EXTRA_FLAGS)
clean(){ sed '/^```/d' | jq .; }

echo "[1D] refresh scheduler (REFRESH_DAYS=$REFRESH_DAYS, today=$(date -u +%Y-%m-%d))"
claude -p "Follow your system instructions. Today is $(date -u +%Y-%m-%d). REFRESH_DAYS=$REFRESH_DAYS. Read $STATE/search_strategy_db.json, select strategies where age(last_updated_at) >= REFRESH_DAYS or next_refresh_due <= today, pause run_count>=3 with yield_count=0, and output ONLY the refresh-run JSON (refreshed_strategy_ids, paused_strategy_ids, next_due). No prose, no fences." \
  --append-system-prompt "$(cat "$S1/1D_refresh_scheduler.md")" --allowedTools "Read" "${FLAGS[@]}" \
  2> "$STATE/1D.err" | jq -r '.result' | clean > "$STATE/refresh_run.json"

N=$(jq '.refreshed_strategy_ids | length' "$STATE/refresh_run.json" 2>/dev/null || echo 0)
echo "[1D] stale strategies to refresh: $N"
if [ "${N:-0}" -gt 0 ]; then
  # closed loop: re-run the discovery pass (1A refresh -> 1B -> 1C) and merge new cases
  OUTDB="$STATE/refresh_case_db_$(date -u +%Y%m%dT%H%M%SZ).json"
  bash "$ROOT/scripts/run_stage1.sh" "$OUTDB" "$STATE/run_config.json"
  echo "[1D] closed cycle done; new cases in $OUTDB (merge into your corpus / re-run Stages 2-4)"
else
  echo "[1D] nothing stale — corpus is fresh. No crawling performed."
fi
