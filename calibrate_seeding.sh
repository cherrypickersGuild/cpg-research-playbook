#!/usr/bin/env bash
# calibrate_seeding.sh — health metrics for the SEEDING side of the pipeline
# (see SEEDING_STRATEGY.md §7), as distinct from calibrate.sh which tunes a
# single run's validation/selection thresholds. This one reads the persistent
# state/ stores directly, since seeding health is a cross-run, ongoing concern.
#
#   Usage: bash calibrate_seeding.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/pipeline.config.sh"
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found."; exit 1; }

STATE="$ROOT/state"
SSD="$STATE/search_strategy_db.json"
CSD="$STATE/community_strategy_db.json"
CATREG="$STATE/category_registry.json"
CASEDB="$STATE/ax_case_db.json"
ENTREG="$STATE/entity_registry.json"
TODAY="$(date -u +%Y-%m-%d)"

bar(){ local n="$1" max="$2" w=0; [ "$max" -gt 0 ] 2>/dev/null && w=$(( n*40/max )); printf '%*s' "$w" '' | tr ' ' '#'; }

echo "================ Seeding health ================"
echo "as of: $TODAY   REFRESH_DAYS=$REFRESH_DAYS   NEWS_FRESHNESS_WINDOW_DAYS=${NEWS_FRESHNESS_WINDOW_DAYS:-7}"
echo

# --- 1. yield by seed topic (web queries + community strategies combined) ---
echo "--- 1. yield by seed topic ---"
if [ -s "$SSD" ] || [ -s "$CSD" ]; then
  ROWS=$(jq -s -r '
    ( (.[0].strategies // []) + (.[1].strategies // []) ) as $all |
    ($all | group_by(.topic) | map({topic: .[0].topic, yield: (map(.yield_count // 0) | add), runs: (map(.run_count // 0) | add)})) as $byt |
    $byt[] | "\(.topic)\t\(.yield)\t\(.runs)"
  ' "${SSD:-/dev/null}" "${CSD:-/dev/null}" 2>/dev/null || echo "")
  if [ -n "$ROWS" ]; then
    maxy=0
    while IFS=$'\t' read -r topic yield runs; do [ "${yield:-0}" -gt "$maxy" ] && maxy="$yield"; done <<< "$ROWS"
    while IFS=$'\t' read -r topic yield runs; do
      printf '  %-14s yield=%-4s runs=%-4s %s\n' "$topic" "$yield" "$runs" "$(bar "${yield:-0}" "$maxy")"
    done <<< "$ROWS"
  else
    echo "  (no strategies with yield yet)"
  fi
else
  echo "  (neither search_strategy_db.json nor community_strategy_db.json found)"
fi
echo

# --- 2. corroboration_count distribution in the master case DB --------------
echo "--- 2. corroboration across the master case DB ---"
if [ -s "$CASEDB" ]; then
  jq -r '
    (.cases // []) as $cases |
    ($cases | length) as $t |
    ($cases | map(.corroboration_count // 1)) as $c |
    "  total cases         : \($t)",
    "  corroborated (>=2)  : \([$c[]|select(.>=2)]|length)",
    "  single-source (=1)  : \([$c[]|select(.==1)]|length)",
    "  max corroboration   : \(if $t>0 then ($c|max) else 0 end)"
  ' "$CASEDB"
  N_CONFLICTS=$(jq '[.cases[]? | select((.conflicting_evidence_log // []) | length > 0)] | length' "$CASEDB")
  echo "  unresolved conflicts: ${N_CONFLICTS:-0} $([ "${N_CONFLICTS:-0}" -gt 0 ] && echo '<- review these before using in a deck')"
else
  echo "  (state/ax_case_db.json not found yet — run run_stage1.sh, refresh.sh, or discover.sh at least once)"
fi
echo

# --- 3. category discovery funnel --------------------------------------------
echo "--- 3. category discovery funnel ---"
if [ -s "$CATREG" ]; then
  jq -r '
    (.categories // []) as $c |
    def c(s): [$c[]|select(.status==s)]|length;
    "  active     : \(c("active"))",
    "  candidate  : \(c("candidate"))  (awaiting human review)",
    "  paused     : \(c("paused"))",
    "  rejected   : \(c("rejected"))"
  ' "$CATREG"
  N_PENDING=$(jq '[.categories[]? | select(.status=="candidate")] | length' "$CATREG")
  [ "${N_PENDING:-0}" -gt 0 ] && echo "  ACTION NEEDED: $N_PENDING candidate(s) waiting in $CATREG"
else
  echo "  (state/category_registry.json not found yet — run discover.sh)"
fi
echo

# --- 4. news-tier vs evergreen-tier yield (community sources only) ----------
echo "--- 4. news-tier vs evergreen-tier yield ---"
if [ -s "$CSD" ]; then
  jq -r '
    (.communities // []) as $comms |
    (.strategies // [] | map(select(.community_id != null))) as $strats |
    ($comms | map({(.community_id): (.tier // "evergreen")}) | add // {}) as $tier_of |
    ( ["news","evergreen"][] as $t |
      ( [$strats[] | select(($tier_of[.community_id] // "evergreen") == $t)] ) as $rows |
      "  \($t): yield=\([$rows[].yield_count // 0]|add // 0)  strategies=\($rows|length)"
    )
  ' "$CSD"
else
  echo "  (state/community_strategy_db.json not found — no community/tier data yet)"
fi
echo

# --- 5. entity registry (agent/mcp/prompt/skill things, from 1G) ------------
echo "--- 5. entity registry (1G output) ---"
if [ -s "$ENTREG" ]; then
  jq -r '
    (.entities // []) as $ents |
    ($ents | length) as $t |
    "  total entities       : \($t)",
    ($ents | group_by(.topic) | map({topic: .[0].topic, n: length}) | sort_by(-.n)[] | "    \(.topic): \(.n)"),
    "  corroborated (>=2)   : \([$ents[] | select((.corroboration_count // 1) >= 2)] | length)",
    "  verified description : \([$ents[] | select((.description_source // "unknown") == "verified")] | length) of \($t)"
  ' "$ENTREG"
  N_ECONFLICTS=$(jq '[.entities[]? | select((.conflicting_evidence_log // []) | length > 0)] | length' "$ENTREG")
  echo "  unresolved conflicts : ${N_ECONFLICTS:-0} $([ "${N_ECONFLICTS:-0}" -gt 0 ] && echo '<- review entity_type disagreements')"
else
  echo "  (state/entity_registry.json not found yet — run run_stage1.sh or discover.sh at least once)"
fi
echo

# --- 6. staleness snapshot -----------------------------------------------------
echo "--- 6. staleness (strategies due for refresh) ---"
if [ -s "$SSD" ] || [ -s "$CSD" ]; then
  jq -s -r --arg today "$TODAY" '
    ( (.[0].strategies // []) + (.[1].strategies // []) ) as $all |
    ($all | length) as $t |
    ([$all[] | select(.status=="active" and ((.next_refresh_due // "9999-12-31") <= $today))] | length) as $stale |
    "  active strategies : \([$all[]|select(.status=="active")]|length) of \($t) total",
    "  stale (due now)    : \($stale)"
  ' "${SSD:-/dev/null}" "${CSD:-/dev/null}"
else
  echo "  (no strategy DBs found)"
fi
echo
echo "Tip: run 'bash refresh.sh' to clear stale evergreen strategies, 'bash discover.sh' for news + category passes."
