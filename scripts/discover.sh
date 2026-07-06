#!/usr/bin/env bash
# discover.sh — runs the two seeding-strategy extensions on their own cadences
# (see SEEDING_STRATEGY.md): 1F News Monitor (fast lane, tier:"news" sources
# only) and 1E Category Discovery (slow lane, proposes new seed topics).
# Safe to schedule often, like refresh.sh — 1F still respects the ledger and
# freshness window, and 1E only proposes candidates, never activates them.
#
#   Usage: bash discover.sh [--news-only | --category-only]   (default: both)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' not on PATH."; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "ERROR: 'jq' not found."; exit 1; }

S1="$ROOT/agents/stage1"; STATE="$ROOT/state"
mkdir -p "$STATE"
[ -f "$STATE/category_registry.json" ] || echo '{"categories":[]}' > "$STATE/category_registry.json"
[ -f "$STATE/entity_registry.json" ]   || echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$STATE/entity_registry.json"
[ -f "$STATE/visited_url_ledger.json" ] || echo '{"ledger":[]}' > "$STATE/visited_url_ledger.json"
[ -f "$STATE/source_registry.json" ]    || cp "$ROOT/config/source_registry_template.json" "$STATE/source_registry.json"

MODE="${1:-both}"
NEWS_FRESHNESS_WINDOW_DAYS="${NEWS_FRESHNESS_WINDOW_DAYS:-7}"

FLAGS=(--output-format json); [ -n "$MODEL" ] && FLAGS+=(--model "$MODEL"); [ "$USE_BARE" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "$EXTRA_FLAGS" ] && FLAGS+=($EXTRA_FLAGS)
clean(){ sed '/^```/d' | jq .; }

run_1f() {
  echo "[1F] news monitor (freshness window ${NEWS_FRESHNESS_WINDOW_DAYS} days, today=$(date -u +%Y-%m-%d))"
  claude -p "Follow your system instructions. Today is $(date -u +%Y-%m-%d). NEWS_FRESHNESS_WINDOW_DAYS=$NEWS_FRESHNESS_WINDOW_DAYS. Source registry: $STATE/source_registry.json. Community registry: $STATE/community_strategy_db.json (may not exist yet; treat as empty communities[] if absent). Visited-URL ledger: $STATE/visited_url_ledger.json (NEVER refetch a news_url already in it). SEED_TOPICS: $SEED_TOPICS. Active categories: $STATE/category_registry.json. Consider only registry rows with tier == \"news\". Output ONLY the Hit JSON (hits, ledger_updates, category_signals, freshness_window_days, throttled_domains). No prose, no fences." \
    --append-system-prompt "$(cat "$S1/1F_news_monitor.md")" --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
    2> "$STATE/1F.err" | jq -r '.result' | clean > "$STATE/news_hits.json"

  # merge ledger_updates into the persistent ledger — same technique run_stage1.sh uses for 1B.
  jq -s '{ledger: ((.[0].ledger // []) + (.[1].ledger_updates // [])) | unique_by(.url)}' \
    "$STATE/visited_url_ledger.json" "$STATE/news_hits.json" > "$STATE/ledger.tmp" \
    && mv "$STATE/ledger.tmp" "$STATE/visited_url_ledger.json"

  local n_hits n_signals
  n_hits=$(jq '.hits | length' "$STATE/news_hits.json" 2>/dev/null || echo 0)
  n_signals=$(jq '.category_signals | length' "$STATE/news_hits.json" 2>/dev/null || echo 0)
  echo "[1F] new news hits: ${n_hits:-0}  |  category signals surfaced: ${n_signals:-0} (feed these to 1E, not category_registry.json directly)"

  if [ "${n_hits:-0}" -gt 0 ]; then
    echo "[1C] case extractor (news hits)"
    claude -p "Follow your system instructions. New hits: $STATE/news_hits.json. Registry: $STATE/source_registry.json. Run config (date_filter): $STATE/run_config.json (use defaults if absent). Extract AX cases from new news_urls into the case schema with discovery provenance. Output ONLY the ax_case_db.json (run_metadata, coverage_summary, cases[], pattern_index) plus a top-level ledger_patch[]. No prose, no fences." \
      --append-system-prompt "$(cat "$S1/1C_case_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
      2> "$STATE/1C_news.err" | jq -r '.result' | clean > "$STATE/news_case_db_with_patch.json"

    local ts newdb
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    newdb="$STATE/news_case_db_${ts}.json"
    jq 'del(.ledger_patch)' "$STATE/news_case_db_with_patch.json" > "$newdb"
    jq -s '(.[1].ledger_patch // []) as $p
           | {ledger: [ .[0].ledger[] | (. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u | $e + $u ]}' \
       "$STATE/visited_url_ledger.json" "$STATE/news_case_db_with_patch.json" > "$STATE/ledger.tmp" \
       && mv "$STATE/ledger.tmp" "$STATE/visited_url_ledger.json"

    echo "[1F] new cases extracted: $(jq '.cases | length' "$newdb" 2>/dev/null || echo 0) -> $newdb"
    echo "[merge] folding into master state/ax_case_db.json"
    bash "$ROOT/scripts/merge_case_db.sh" "$newdb" "$STATE/ax_case_db.json"

    echo "[1G] entity extractor (news hits)"
    claude -p "Follow your system instructions. Hits: $STATE/news_hits.json. Visited-URL ledger: $STATE/visited_url_ledger.json (use its entity_extracted/entity_ids fields, separate from 1C's extracted/case_ids on the same rows). Output ONLY the entity batch JSON (entities, ledger_patch). No prose, no fences." \
      --append-system-prompt "$(cat "$S1/1G_entity_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
      2> "$STATE/1G_news.err" | jq -r '.result' | clean > "$STATE/news_entity_batch.json"
    jq -s '(.[1].ledger_patch // []) as $p
           | {ledger: [ .[0].ledger[] | (. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u | $e + $u ]}' \
       "$STATE/visited_url_ledger.json" "$STATE/news_entity_batch.json" > "$STATE/ledger.tmp" \
       && mv "$STATE/ledger.tmp" "$STATE/visited_url_ledger.json"
    echo "[1F] new entities extracted: $(jq '.entities | length' "$STATE/news_entity_batch.json" 2>/dev/null || echo 0)"
    echo "[merge] folding into master state/entity_registry.json"
    bash "$ROOT/scripts/merge_entity_registry.sh" "$STATE/news_entity_batch.json" "$STATE/entity_registry.json"
  else
    echo "[1F] no new news hits — nothing to extract or merge."
  fi
}

run_1e() {
  echo "[1E] category discovery"
  claude -p "Follow your system instructions. Today is $(date -u +%Y-%m-%d). Read state/search_hits.json (and its per-topic shards), state/community_strategy_db.json's discovery_candidates[] if present, and state/category_registry.json (augment, do not clobber). Current SEED_TOPICS: $SEED_TOPICS. Propose new candidate categories with >=3 evidence points; never set status to active yourself. Output ONLY the full updated category_registry.json. No prose, no fences." \
    --append-system-prompt "$(cat "$S1/1E_category_discovery.md")" --allowedTools "Read,WebSearch" "${FLAGS[@]}" \
    2> "$STATE/1E.err" | jq -r '.result' | clean > "$STATE/category_registry.json.tmp" \
    && mv "$STATE/category_registry.json.tmp" "$STATE/category_registry.json"

  local n_candidates n_active
  n_candidates=$(jq '[.categories[] | select(.status=="candidate")] | length' "$STATE/category_registry.json" 2>/dev/null || echo 0)
  n_active=$(jq '[.categories[] | select(.status=="active")] | length' "$STATE/category_registry.json" 2>/dev/null || echo 0)
  echo "[1E] categories: ${n_active:-0} active, ${n_candidates:-0} awaiting human review in $STATE/category_registry.json"
  if [ "${n_candidates:-0}" -gt 0 ]; then
    echo "[1E] ACTION NEEDED: review candidates, then flip approved ones to status:\"active\" and add their category_id to SEED_TOPICS in pipeline.config.sh."
  fi
}

case "$MODE" in
  --news-only)     run_1f ;;
  --category-only) run_1e ;;
  both|"")         run_1f; run_1e ;;
  *) echo "ERROR: unknown mode '$MODE'. Use --news-only, --category-only, or no argument for both."; exit 1 ;;
esac

echo "[discover] done."
