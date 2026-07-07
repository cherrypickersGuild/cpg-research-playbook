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
# raw claude stdout for the most recent loop's two calls, captured unconditionally (overwritten
# each loop) so a parse failure downstream (bad/non-JSON output) can actually be diagnosed instead
# of being lost inside a failed pipe — this is what harvest_skill.err could NOT show, since that
# only captures claude's stderr, not the malformed stdout that broke jq.
RAW_CANDIDATES="$STATE/harvest_${TOPIC}_raw_candidates.json"
RAW_1G="$STATE/harvest_${TOPIC}_raw_1g.json"

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
  # The model occasionally prefixes its JSON with a stray sentence despite the "no prose"
  # instruction (observed ~1-in-2 across live runs) — that breaks the fence-stripping clean()
  # step and jq fails on the leftover prose. This is a transient formatting slip, not a script
  # defect, so retry a few times before treating it as a real failure.
  CANDIDATE_ATTEMPTS="${CANDIDATE_ATTEMPTS:-3}"
  candidate_ok=false
  for attempt in $(seq 1 "$CANDIDATE_ATTEMPTS"); do
    if claude -p "You are sourcing CANDIDATE urls for Stage 1G (entity extraction) — you do not extract or verify entities yourself here. Topic: $TOPIC. Seed sources, in priority order: (a) $AWESOME_LIST plus the source awesome-list raw README(s) it cites near its top (fetch those for entries beyond the report's own ~40-row cap), (b) $HITS_SHARD. For EVERY candidate you propose, resolve it to the PROJECT'S OWN primary URL — its own repo, docs page, model card, package page, paper, or official product page. Never emit an awesome-list README URL itself as a candidate's url. Drop any entry whose own primary URL cannot be determined rather than guessing. EXCLUDE any URL that is: already entity_extracted:true in the ledger at $LEDGER, already listed in attempted_urls[] in $ATTEMPTED, or already a url of an existing entity in $REGISTRY. Return at most $BATCH_SIZE candidates. Output ONLY JSON of the shape {\"hits\":[{\"url\":\"...\",\"title\":\"...\",\"snippet\":\"...\",\"domain\":\"...\"}]}. No prose, no fences." \
         --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_CANDIDATES" | jq -r '.result' | clean > "$BATCH_HITS" \
       && jq empty "$BATCH_HITS" 2>/dev/null; then
      candidate_ok=true
      break
    fi
    echo "[harvest][$TOPIC] loop $loop: candidate-batch attempt $attempt/$CANDIDATE_ATTEMPTS produced invalid output (raw: $RAW_CANDIDATES) — retrying" >&2
  done
  if [ "$candidate_ok" != true ]; then
    echo "ERROR: candidate-batch step failed for topic '$TOPIC' after $CANDIDATE_ATTEMPTS attempts (raw output: $RAW_CANDIDATES, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  n_candidates=$(jq '.hits | length' "$BATCH_HITS")
  if [ "${n_candidates:-0}" -eq 0 ]; then
    echo "[harvest][$TOPIC] loop $loop: 0 candidates found — sources exhausted at $current/$TARGET verified."
    exit 0
  fi
  echo "[harvest][$TOPIC] loop $loop: $n_candidates candidate(s)"

  # record every URL sent this loop as attempted, before we know 1G's verdict —
  # this is what stops a later loop from re-selecting a dropped/rejected candidate.
  if ! jq -s '{attempted_urls: ((.[0].attempted_urls // []) + [.[1].hits[]?.url]) | unique}' \
       "$ATTEMPTED" "$BATCH_HITS" > "$ATTEMPTED.tmp"; then
    rm -f "$ATTEMPTED.tmp"
    echo "ERROR: attempted-set merge (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$ATTEMPTED.tmp" 2>/dev/null || { rm -f "$ATTEMPTED.tmp"; echo "ERROR: attempted-set merge produced invalid JSON — aborting." >&2; exit 1; }
  mv "$ATTEMPTED.tmp" "$ATTEMPTED"

  # seed a ledger row for every candidate URL that doesn't already have one — these URLs came
  # straight from the candidate-batch step, not through 1B's own ledger-append, so without this
  # the entity_extracted/entity_ids patch below would have no existing row to match against and
  # would silently no-op (existing rows always win via unique_by's first-occurrence semantics).
  if ! jq -s --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
      (.[1].hits // []) as $hits
      | { ledger: ( (.[0].ledger // []) + ($hits | map({
            url: .url, url_type: "news_url", platform: (.platform // "custom"),
            first_crawled_at: $now, last_crawled_at: $now, crawl_count: 1,
            http_status_last: null, content_hash: null,
            extracted: false, case_ids: [], entity_extracted: false, entity_ids: []
          })) ) | unique_by(.url) }' \
       "$LEDGER" "$BATCH_HITS" > "$LEDGER.tmp"; then
    rm -f "$LEDGER.tmp"
    echo "ERROR: ledger seed (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$LEDGER.tmp" 2>/dev/null || { rm -f "$LEDGER.tmp"; echo "ERROR: ledger seed produced invalid JSON — aborting." >&2; exit 1; }
  mv "$LEDGER.tmp" "$LEDGER"

  echo "[harvest][$TOPIC] loop $loop: running 1G (fetch + verify each candidate)"
  # Same transient stray-prose failure mode as the candidate-batch step above (confirmed by
  # live runs — it hits either claude -p call, not just the first one) — retry here too rather
  # than hard-failing the whole loop over a formatting slip.
  ONEG_ATTEMPTS="${ONEG_ATTEMPTS:-3}"
  oneg_ok=false
  for attempt in $(seq 1 "$ONEG_ATTEMPTS"); do
    if claude -p "Follow your system instructions. Hits: $BATCH_HITS. Visited-URL ledger: $LEDGER (use its entity_extracted/entity_ids fields, separate from 1C's extracted/case_ids on the same rows). Fetch each candidate's own page before extracting; only set description_source:\"verified\" when the description came from that fetch, never from the snippet alone — if the page can't be fetched, use description_source:\"snippet-only\" per your existing rules rather than marking it verified. Output ONLY the entity batch JSON (entities, ledger_patch). No prose, no fences." \
         --append-system-prompt "$(cat "$S1/1G_entity_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_1G" | jq -r '.result' | clean > "$BATCH_ENTITIES" \
       && jq empty "$BATCH_ENTITIES" 2>/dev/null; then
      oneg_ok=true
      break
    fi
    echo "[harvest][$TOPIC] loop $loop: 1G attempt $attempt/$ONEG_ATTEMPTS produced invalid output (raw: $RAW_1G) — retrying" >&2
  done
  if [ "$oneg_ok" != true ]; then
    echo "ERROR: 1G extraction step failed for topic '$TOPIC' after $ONEG_ATTEMPTS attempts (raw output: $RAW_1G, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  # fold this loop's ledger_patch into the persistent ledger (entity_extracted/entity_ids).
  # $e must stay bound across the $u computation, so the whole tail is inside one `. as $e | ...`
  # (an earlier version scoped $e only inside the inner parens, which is a jq compile error that
  # `&&`-chaining silently swallowed under `set -e` — checked explicitly here instead).
  if ! jq -s '(.[1].ledger_patch // []) as $p
         | {ledger: [ .[0].ledger[] | . as $e | (($p[] | select(.url==$e.url)) // {}) as $u | $e + $u ]}' \
       "$LEDGER" "$BATCH_ENTITIES" > "$LEDGER.tmp"; then
    rm -f "$LEDGER.tmp"
    echo "ERROR: ledger merge (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$LEDGER.tmp" 2>/dev/null || { rm -f "$LEDGER.tmp"; echo "ERROR: ledger merge produced invalid JSON — aborting." >&2; exit 1; }
  mv "$LEDGER.tmp" "$LEDGER"

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
