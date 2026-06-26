#!/usr/bin/env bash
# run_stage1.sh — one discovery pass: 1A (strategies) -> 1B (crawl) -> 1C (extract).
# Reads/writes the persistent stores in state/, writes this run's case DB to $1.
#   Usage: bash run_stage1.sh <output_case_db.json> [run_config.json]
# Called by run_pipeline.sh for stage 1; can also be run standalone.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/pipeline.config.sh"
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' not on PATH."; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "ERROR: 'jq' not found."; exit 1; }

OUT_DB="${1:-$ROOT/state/ax_case_db.json}"
CFG="${2:-$ROOT/state/run_config.json}"
S1="$ROOT/agents/stage1"
STATE="$ROOT/state"
mkdir -p "$STATE"
[ -f "$STATE/search_strategy_db.json" ] || echo '{"topics":[],"refresh_days":'"$REFRESH_DAYS"',"strategies":[]}' > "$STATE/search_strategy_db.json"
[ -f "$STATE/visited_url_ledger.json" ] || echo '{"ledger":[]}' > "$STATE/visited_url_ledger.json"
[ -f "$STATE/source_registry.json" ]    || cp "$ROOT/config/source_registry_template.json" "$STATE/source_registry.json"

FLAGS=(--output-format json); [ -n "$MODEL" ] && FLAGS+=(--model "$MODEL"); [ "$USE_BARE" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "$EXTRA_FLAGS" ] && FLAGS+=($EXTRA_FLAGS)
clean(){ sed '/^```/d' | jq .; }

echo "[1A] strategy builder"
claude -p "Follow your system instructions. Seed topics: $SEED_TOPICS. REFRESH_DAYS=$REFRESH_DAYS. Read and augment the Search Strategy DB at $STATE/search_strategy_db.json (do not clobber existing rows). Output ONLY the full updated Search Strategy DB JSON. No prose, no fences." \
  --append-system-prompt "$(cat "$S1/1A_strategy_builder.md")" --allowedTools "Read,WebSearch" "${FLAGS[@]}" \
  2> "$STATE/1A.err" | jq -r '.result' | clean > "$STATE/search_strategy_db.json.tmp" && mv "$STATE/search_strategy_db.json.tmp" "$STATE/search_strategy_db.json"

echo "[1B] crawl executor (dedup via ledger)"
claude -p "Follow your system instructions. Strategies: $STATE/search_strategy_db.json. Registry: $STATE/source_registry.json. Visited-URL ledger: $STATE/visited_url_ledger.json (NEVER refetch a news_url already in it). Output ONLY the Hit JSON (hits, ledger_updates, throttled_domains). No prose, no fences." \
  --append-system-prompt "$(cat "$S1/1B_crawl_executor.md")" --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
  2> "$STATE/1B.err" | jq -r '.result' | clean > "$STATE/hits.json"
# merge ledger_updates into the persistent ledger (append new, keep existing)
jq -s '{ledger: ((.[0].ledger // []) + (.[1].ledger_updates // []))
        | unique_by(.url)}' "$STATE/visited_url_ledger.json" "$STATE/hits.json" > "$STATE/ledger.tmp" \
  && mv "$STATE/ledger.tmp" "$STATE/visited_url_ledger.json"

echo "[1C] case extractor"
claude -p "Follow your system instructions. New hits: $STATE/hits.json. Registry: $STATE/source_registry.json. Run config (date_filter): $CFG. Extract AX cases from new news_urls into the case schema with discovery provenance. Output ONLY the ax_case_db.json (run_metadata, coverage_summary, cases[], pattern_index) plus a top-level ledger_patch[]. No prose, no fences." \
  --append-system-prompt "$(cat "$S1/1C_case_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
  2> "$STATE/1C.err" | jq -r '.result' | clean > "$STATE/case_db_with_patch.json"
# split: case DB out to caller, and apply ledger_patch (extracted/case_ids)
jq 'del(.ledger_patch)' "$STATE/case_db_with_patch.json" > "$OUT_DB"
jq -s '(.[1].ledger_patch // []) as $p
       | {ledger: [ .[0].ledger[] | (. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u | $e + $u ]}' \
   "$STATE/visited_url_ledger.json" "$STATE/case_db_with_patch.json" > "$STATE/ledger.tmp" \
   && mv "$STATE/ledger.tmp" "$STATE/visited_url_ledger.json"

echo "[stage1] cases: $(jq '.cases|length' "$OUT_DB" 2>/dev/null || echo 0) -> $OUT_DB"
