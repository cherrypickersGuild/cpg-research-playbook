#!/usr/bin/env bash
# run_pipeline.sh — runs the AX -> Samsung deck pipeline in order, with a hard
# validation gate, automatic per-stage logs, and structured, timestamped outputs.
#
#   Run it in a BASH shell (Git Bash or WSL), NOT in cmd/PowerShell, and NOT
#   inside the Claude chat. The script launches `claude -p` itself for each stage.
#
#   Usage:  bash run_pipeline.sh
#   Config: edit pipeline.config.sh first.
#
# Resume: set RESUME_RUN to a prior run folder name and FROM_STAGE to the stage
# you want to restart at. Earlier stages are reused from their saved files, so
# you never lose completed work and every stage stays aligned to the same config.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/pipeline.config.sh"

# --- preflight: fail early with a clear message ------------------------------
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' not on PATH. Install Claude Code and reopen the terminal."; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "ERROR: 'jq' not found. Install jq (winget install jqlang.jq  /  apt-get install jq)."; exit 1; }

# --- run folder: new, or resume an existing one ------------------------------
if [ -n "${RESUME_RUN:-}" ]; then
  RUN_ID="$RESUME_RUN"; RUN_DIR="$ROOT/runs/$RUN_ID"
  [ -d "$RUN_DIR" ] || { echo "ERROR: resume folder not found: $RUN_DIR"; exit 1; }
else
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"; RUN_DIR="$ROOT/runs/$RUN_ID"
fi
OUT="$RUN_DIR/outputs"; LOGS="$RUN_DIR/logs"
mkdir -p "$OUT" "$LOGS"
# symlink is convenience only; on Git Bash it may not be permitted, so never fail on it
ln -sfn "$RUN_DIR" "$ROOT/runs/latest" 2>/dev/null || true

# mirror all console output into the run log, timestamped
exec > >(while IFS= read -r line; do printf '%s %s\n' "$(date -u +%H:%M:%S)" "$line"; done | tee -a "$RUN_DIR/run.log") 2>&1

echo "=== AX pipeline run $RUN_ID  (from stage $FROM_STAGE) ==="

# --- shared run config: write once; reuse verbatim on resume (frozen result) -
[ "$TRANSFORMATION_END" = "TODAY" ] && TRANSFORMATION_END="$(date -u +%Y-%m-%d)"
[ "$PUBLICATION_END"   = "TODAY" ] && PUBLICATION_END="$(date -u +%Y-%m-%d)"
CONFIG_JSON="$RUN_DIR/run_config.json"
if [ ! -f "$CONFIG_JSON" ]; then
  cat > "$CONFIG_JSON" <<EOF
{
  "date_filter": {
    "transformation_date_range": { "start": "$TRANSFORMATION_START", "end": "$TRANSFORMATION_END" },
    "publication_date_range":    { "start": "$PUBLICATION_START",   "end": "$PUBLICATION_END" },
    "out_of_window_policy": "$OUT_OF_WINDOW_POLICY",
    "classic_cases_allowed_in": "$CLASSIC_CASES_ALLOWED_IN"
  },
  "selection_thresholds": {
    "main_deck_min_confidence": $MAIN_DECK_MIN_CONFIDENCE,
    "appendix_min_confidence": $APPENDIX_MIN_CONFIDENCE,
    "main_deck_count": { "min": $MAIN_DECK_MIN, "max": $MAIN_DECK_MAX },
    "appendix_count":  { "min": $APPENDIX_MIN, "max": $APPENDIX_MAX }
  },
  "audience": { "org": "$AUDIENCE_ORG", "level": "$AUDIENCE_LEVEL",
    "lecture_goal": "$LECTURE_GOAL", "time_limit_min": $TIME_LIMIT_MIN }
}
EOF
  echo "wrote run config -> run_config.json"
else
  echo "reusing existing run_config.json (dates/thresholds stay frozen for this run)"
fi

# --- claude flags ------------------------------------------------------------
COMMON_FLAGS=(--output-format json)
[ -n "$MODEL" ] && COMMON_FLAGS+=(--model "$MODEL")
[ "$USE_BARE" = "true" ] && COMMON_FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "$EXTRA_FLAGS" ] && COMMON_FLAGS+=($EXTRA_FLAGS)

clean_json() { sed '/^```/d' | jq .; }
require_output() { [ -s "$1" ] || { echo "ERROR: cannot resume — missing $(basename "$1"). Re-run with a lower FROM_STAGE."; exit 1; }; }

# run_stage <num> <label> <spec.md> <allowedTools> <task-prompt> <out-file>
run_stage() {
  local num="$1" label="$2" spec="$3" tools="$4" prompt="$5" outfile="$6"
  local raw="$LOGS/${num}_${label}.raw.json"
  echo "--- stage $num: $label ---"
  claude -p "$prompt" \
    --append-system-prompt "$(cat "$ROOT/agents/$spec")" \
    --allowedTools "$tools" \
    "${COMMON_FLAGS[@]}" \
    > "$raw" 2> "$LOGS/${num}_${label}.err"
  jq -r '.result' "$raw" | clean_json > "$outfile"
  echo "    cost: \$$(jq -r '.total_cost_usd // 0' "$raw")   ->  $(basename "$outfile")"
}

# ============================ STAGE 1 — Case Finder ==========================
CASE_DB="$OUT/01_case_db.json"
if [ "$FROM_STAGE" -le 1 ]; then
  if [ "${STAGE1_MODE:-monolith}" = "discovery" ]; then
    echo "--- stage 1: discovery sub-pipeline (1A->1B->1C) ---"
    bash "$ROOT/run_stage1.sh" "$CASE_DB" "$CONFIG_JSON"
  else
    run_stage 01 case_finder 01_case_finder.md "Read,WebSearch,WebFetch" \
      "Follow your system instructions. Read the run config at $CONFIG_JSON and obey its date_filter. Find verified AX cases and output ONLY the corpus JSON (run_metadata, coverage_summary, cases[], pattern_index) to stdout. No prose, no code fences." \
      "$CASE_DB"
  fi
elif [ ! -s "$CASE_DB" ]; then
  [ -n "$EXISTING_CASE_DB" ] || { echo "ERROR: FROM_STAGE>1 but no $CASE_DB and EXISTING_CASE_DB is empty."; exit 1; }
  cp "$EXISTING_CASE_DB" "$CASE_DB"; echo "stage 1 skipped; seeded from $EXISTING_CASE_DB"
else
  echo "stage 1 skipped; reusing existing 01_case_db.json"
fi

# ============================ STAGE 2 — Validator ===========================
VALIDATED="$OUT/02_validated.json"
if [ "$FROM_STAGE" -le 2 ]; then
  run_stage 02 validator 02_validator.md "Read,WebSearch,WebFetch" \
    "Follow your system instructions. Read the case corpus at $CASE_DB and the run config at $CONFIG_JSON. Validate every case (fabrication, URL accessibility, source tier, KPI traceability, dates vs the config ranges, contradictory evidence, deck-readiness). Output ONLY the validation JSON to stdout. No prose, no code fences." \
    "$VALIDATED"
else
  require_output "$VALIDATED"; echo "stage 2 skipped; reusing 02_validated.json"
fi

# ----- HARD GATE: only gate_passed cases continue ----------------------------
GATE="$OUT/02b_gate_passed.json"
if [ "$FROM_STAGE" -le 2 ] || [ ! -s "$GATE" ]; then
  jq '{ gate_passed_ids: [ .results[] | select(.gate_passed == true) | .case_id ],
        validation: [ .results[] | select(.gate_passed == true) ] }' \
    "$VALIDATED" > "$GATE"
fi
echo "gate: $(jq '.gate_passed_ids | length' "$GATE") of $(jq '.results | length' "$VALIDATED") cases passed"

# ============================ STAGE 3 — Selector ============================
SELECTED="$OUT/03_selected.json"
if [ "$FROM_STAGE" -le 3 ]; then
  run_stage 03 selector 03_selector.md "Read" \
    "Follow your system instructions. Read the full case records at $CASE_DB, the gate-passed validation at $GATE, and the run config at $CONFIG_JSON. Consider ONLY case_ids present in $GATE. Join them to their full records by case_id, score Samsung relevance, and curate main + appendix per the thresholds. Output ONLY the selection JSON to stdout. No prose, no code fences." \
    "$SELECTED"
else
  require_output "$SELECTED"; echo "stage 3 skipped; reusing 03_selected.json"
fi

# ============================ STAGE 4 — Slide Builder =======================
DECK="$OUT/04_deck_plan.json"
if [ "$FROM_STAGE" -le 4 ]; then
  run_stage 04 slide_builder 04_slide_builder.md "Read" \
    "Follow your system instructions. Read the selection at $SELECTED, the full case records at $CASE_DB, the validation at $VALIDATED, and the run config at $CONFIG_JSON. Build the executive deck plan (narrative + slides + applicability matrix + appendix) using only validator-verified numbers in slide bodies. Output ONLY the deck_plan JSON to stdout. No prose, no code fences." \
    "$DECK"
else
  require_output "$DECK"; echo "stage 4 skipped; reusing 04_deck_plan.json"
fi

# ============================ manifest =======================================
TOTAL_COST="$(jq -s '[.[].total_cost_usd // 0] | add' "$LOGS"/*.raw.json 2>/dev/null || echo 0)"
jq -n --arg run "$RUN_ID" --arg cost "$TOTAL_COST" \
  --argjson cases "$(jq '.cases | length' "$CASE_DB" 2>/dev/null || echo 0)" \
  --argjson passed "$(jq '.gate_passed_ids | length' "$GATE" 2>/dev/null || echo 0)" \
  --argjson main "$(jq '.main_deck | length' "$SELECTED" 2>/dev/null || echo 0)" \
  --argjson appendix "$(jq '.appendix | length' "$SELECTED" 2>/dev/null || echo 0)" \
  '{run_id:$run, total_cost_usd:($cost|tonumber), counts:{cases:$cases, gate_passed:$passed, main_deck:$main, appendix:$appendix},
    outputs:["outputs/01_case_db.json","outputs/02_validated.json","outputs/02b_gate_passed.json","outputs/03_selected.json","outputs/04_deck_plan.json"]}' \
  > "$RUN_DIR/manifest.json"

echo "=== done. total cost: \$$TOTAL_COST ==="
echo "results: $RUN_DIR/outputs/"
