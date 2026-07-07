#!/usr/bin/env bash
# harvest_entities.sh — repeatedly builds candidate batches for one topic,
# runs Stage 1G over them, and merges into state/entity_registry.json until
# the topic has >= target verified entities, or sources are exhausted.
#
# "Verified" means description_source:"verified" — the description was
# fetched from the entity's OWN primary page (repo, docs page, model card,
# package page, paper, or official product page). Awesome-list README URLs
# are seed material only and are never emitted as an entity's own url.
# See docs/entity_harvest_plan.md for the full design.
#
#   Usage: bash scripts/harvest_entities.sh <agent|mcp|prompt|skill> [target=100]
#
# Exit 0: target reached, a loop added 0 new verified entities (sources
#         exhausted), or MAX_LOOPS reached — all printed with the final tally.
# Exit 1: missing dependency, bad arguments, a claude/jq step failing, or a
#         persistent file (ledger/registry) found or left invalid JSON.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' not on PATH." >&2; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 1; }

TOPIC="${1:?Usage: bash scripts/harvest_entities.sh <agent|mcp|prompt|skill> [target=100]}"
TARGET="${2:-100}"
case "$TOPIC" in
  agent|mcp|prompt|skill) ;;
  *) echo "ERROR: topic must be one of agent, mcp, prompt, skill (got '$TOPIC')." >&2; exit 1 ;;
esac
case "$TARGET" in
  ''|*[!0-9]*) echo "ERROR: target must be a positive integer (got '$TARGET')." >&2; exit 1 ;;
esac

S1="$ROOT/agents/stage1"
STATE="$ROOT/state"
mkdir -p "$STATE"

HITS_TOPIC="$TOPIC"; [ "$TOPIC" = "skill" ] && HITS_TOPIC="skills"
HITS_SHARD="$STATE/search_hits_${HITS_TOPIC}.json"
AWESOME_LIST="$ROOT/reports/awesome-lists/awesome_${TOPIC}.md"
REGISTRY="$STATE/entity_registry.json"
LEDGER="$STATE/visited_url_ledger.json"
BATCH_HITS="$STATE/harvest_${TOPIC}_hits.json"
BATCH_ENTITIES="$STATE/harvest_${TOPIC}_entity_batch.json"
ATTEMPTED="$STATE/harvest_${TOPIC}_attempted.json"
ERR_LOG="$STATE/harvest_${TOPIC}.err"

[ -f "$REGISTRY" ] || echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$REGISTRY"
[ -f "$LEDGER" ]   || echo '{"ledger":[]}' > "$LEDGER"
# attempted-set is transient and scoped to this invocation — reset every run
echo '{"attempted_urls":[]}' > "$ATTEMPTED"

jq empty "$REGISTRY" 2>/dev/null || { echo "ERROR: $REGISTRY is not valid JSON — refusing to continue." >&2; exit 1; }
jq empty "$LEDGER"   2>/dev/null || { echo "ERROR: $LEDGER is not valid JSON — refusing to continue." >&2; exit 1; }

BATCH_SIZE="${BATCH_SIZE:-25}"
MAX_LOOPS="${MAX_LOOPS:-12}"

FLAGS=(--output-format json); [ -n "${MODEL:-}" ] && FLAGS+=(--model "$MODEL"); [ "${USE_BARE:-false}" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "${EXTRA_FLAGS:-}" ] && FLAGS+=($EXTRA_FLAGS)
clean(){ sed '/^```/d' | jq .; }

tally() {
  jq --arg t "$TOPIC" '[.entities[] | select(.topic==$t and .description_source=="verified")] | length' "$REGISTRY"
}

echo "[harvest][$TOPIC] starting. target=$TARGET verified entities. current: $(tally)/$TARGET"

loop=0
while :; do
  loop=$((loop+1))
  current="$(tally)"

  if [ "$current" -ge "$TARGET" ]; then
    echo "[harvest][$TOPIC] target reached: $current/$TARGET verified. done."
    exit 0
  fi
  if [ "$loop" -gt "$MAX_LOOPS" ]; then
    echo "[harvest][$TOPIC] MAX_LOOPS ($MAX_LOOPS) reached at $current/$TARGET verified. stopping."
    exit 0
  fi

  echo "[harvest][$TOPIC] loop $loop: building candidate batch (batch size <= $BATCH_SIZE)"
  claude -p "You are sourcing CANDIDATE urls for Stage 1G (entity extraction) — you do not extract or verify entities yourself here. Topic: $TOPIC. Seed sources, in priority order: (a) $AWESOME_LIST plus the source awesome-list raw README(s) it cites near its top (fetch those for entries beyond the report's own ~40-row cap), (b) $HITS_SHARD. For EVERY candidate you propose, resolve it to the PROJECT'S OWN primary URL — its own repo, docs page, model card, package page, paper, or official product page. Never emit an awesome-list README URL itself as a candidate's url. Drop any entry whose own primary URL cannot be determined rather than guessing. EXCLUDE any URL that is: already entity_extracted:true in the ledger at $LEDGER, already listed in attempted_urls[] in $ATTEMPTED, or already a url of an existing entity in $REGISTRY. Return at most $BATCH_SIZE candidates. Output ONLY JSON of the shape {\"hits\":[{\"url\":\"...\",\"title\":\"...\",\"snippet\":\"...\",\"domain\":\"...\"}]}. No prose, no fences." \
    --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
    2> "$ERR_LOG" | jq -r '.result' | clean > "$BATCH_HITS" \
    || { echo "ERROR: candidate-batch step failed for topic '$TOPIC' (see $ERR_LOG)." >&2; exit 1; }
  jq empty "$BATCH_HITS" 2>/dev/null || { echo "ERROR: candidate batch is not valid JSON (see $BATCH_HITS)." >&2; exit 1; }

  n_candidates=$(jq '.hits | length' "$BATCH_HITS")
  if [ "${n_candidates:-0}" -eq 0 ]; then
    echo "[harvest][$TOPIC] loop $loop: 0 candidates found — sources exhausted at $current/$TARGET verified."
    exit 0
  fi
  echo "[harvest][$TOPIC] loop $loop: $n_candidates candidate(s)"

  # record every URL sent this loop as attempted, before we know 1G's verdict —
  # this is what stops a later loop from re-selecting a dropped/rejected candidate.
  jq -s '{attempted_urls: ((.[0].attempted_urls // []) + [.[1].hits[]?.url]) | unique}' \
    "$ATTEMPTED" "$BATCH_HITS" > "$ATTEMPTED.tmp" && mv "$ATTEMPTED.tmp" "$ATTEMPTED"

  echo "[harvest][$TOPIC] loop $loop: running 1G (fetch + verify each candidate)"
  claude -p "Follow your system instructions. Hits: $BATCH_HITS. Visited-URL ledger: $LEDGER (use its entity_extracted/entity_ids fields, separate from 1C's extracted/case_ids on the same rows). Fetch each candidate's own page before extracting; only set description_source:\"verified\" when the description came from that fetch, never from the snippet alone — if the page can't be fetched, use description_source:\"snippet-only\" per your existing rules rather than marking it verified. Output ONLY the entity batch JSON (entities, ledger_patch). No prose, no fences." \
    --append-system-prompt "$(cat "$S1/1G_entity_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
    2> "$ERR_LOG" | jq -r '.result' | clean > "$BATCH_ENTITIES" \
    || { echo "ERROR: 1G extraction step failed for topic '$TOPIC' (see $ERR_LOG)." >&2; exit 1; }
  jq empty "$BATCH_ENTITIES" 2>/dev/null || { echo "ERROR: 1G output is not valid JSON (see $BATCH_ENTITIES)." >&2; exit 1; }

  # fold this loop's ledger_patch into the persistent ledger (entity_extracted/entity_ids),
  # same technique run_stage1.sh/discover.sh already use for 1G.
  jq -s '(.[1].ledger_patch // []) as $p
         | {ledger: [ .[0].ledger[] | (. as $e | ($p[] | select(.url==$e.url)) // {} ) as $u | $e + $u ]}' \
     "$LEDGER" "$BATCH_ENTITIES" > "$LEDGER.tmp" && mv "$LEDGER.tmp" "$LEDGER"
  jq empty "$LEDGER" 2>/dev/null || { echo "ERROR: ledger became invalid JSON after merge — aborting." >&2; exit 1; }

  before="$(tally)"
  bash "$ROOT/scripts/merge_entity_registry.sh" "$BATCH_ENTITIES" "$REGISTRY" \
    || { echo "ERROR: merge_entity_registry.sh failed for topic '$TOPIC'." >&2; exit 1; }
  jq empty "$REGISTRY" 2>/dev/null || { echo "ERROR: $REGISTRY became invalid JSON after merge — aborting." >&2; exit 1; }
  after="$(tally)"
  added=$((after - before))

  echo "[harvest][$TOPIC] loop $loop: +$added new verified -> $after/$TARGET verified"

  if [ "$added" -le 0 ]; then
    echo "[harvest][$TOPIC] loop $loop added 0 new verified entities — sources exhausted at $after/$TARGET verified."
    exit 0
  fi
done
