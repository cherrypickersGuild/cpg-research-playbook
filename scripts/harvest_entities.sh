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
#
# Timing recovery: every run writes structured JSONL timing events to
# state/logs/harvest_<run_id>.jsonl (gitignored, transient) — see
# docs/entity_harvest_workflow.md § Timing logs for the event schema and how
# to reconstruct run/topic/loop/subprocess/merge durations from it.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"

# ---------------------------------------------------------------------------
# Structured JSONL timing log — set up first, before any exit-capable check,
# so even a missing-dependency failure gets captured. One event per line,
# UTC ISO-8601 timestamps. Never logs prompts, secrets, or full command
# bodies — command_label/detail are short fixed strings only.
#
# log_event never fails the script: every write ends in `|| true`, so a
# logging problem (disk full, unwritable state/logs/) can never turn an
# otherwise-successful run into a failure. The one true limitation: log_event
# itself shells out to jq to build valid JSON, so if jq is missing entirely
# (the very first dependency check below), no event can be written at all —
# there's nothing to serialize with. That single gap is inherent, not a bug.
# ---------------------------------------------------------------------------
STATE="$ROOT/state"
mkdir -p "$STATE/logs"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LOG_FILE="$STATE/logs/harvest_${RUN_ID}.jsonl"
SCRIPT_START_EPOCH="$(date +%s)"

log_event() {
  local event="$1"; shift
  local ts topic="" loop="" target="" verified_before="" verified_after="" command_label="" exit_code="" duration_sec="" detail=""
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local kv
  for kv in "$@"; do
    case "$kv" in
      topic=*)           topic="${kv#topic=}" ;;
      loop=*)            loop="${kv#loop=}" ;;
      target=*)          target="${kv#target=}" ;;
      verified_before=*) verified_before="${kv#verified_before=}" ;;
      verified_after=*)  verified_after="${kv#verified_after=}" ;;
      command_label=*)   command_label="${kv#command_label=}" ;;
      exit_code=*)       exit_code="${kv#exit_code=}" ;;
      duration_sec=*)    duration_sec="${kv#duration_sec=}" ;;
      detail=*)          detail="${kv#detail=}" ;;
    esac
  done
  jq -cn \
    --arg ts "$ts" --arg run_id "$RUN_ID" --arg event "$event" \
    --arg topic "$topic" --arg loop "$loop" --arg target "$target" \
    --arg verified_before "$verified_before" --arg verified_after "$verified_after" \
    --arg command_label "$command_label" --arg exit_code "$exit_code" \
    --arg duration_sec "$duration_sec" --arg detail "$detail" \
    '{ts:$ts, run_id:$run_id, event:$event}
     + (if $topic=="" then {} else {topic:$topic} end)
     + (if $loop=="" then {} else {loop:($loop|tonumber? // $loop)} end)
     + (if $target=="" then {} else {target:($target|tonumber? // $target)} end)
     + (if $verified_before=="" then {} else {verified_before:($verified_before|tonumber? // $verified_before)} end)
     + (if $verified_after=="" then {} else {verified_after:($verified_after|tonumber? // $verified_after)} end)
     + (if $command_label=="" then {} else {command_label:$command_label} end)
     + (if $exit_code=="" then {} else {exit_code:($exit_code|tonumber? // $exit_code)} end)
     + (if $duration_sec=="" then {} else {duration_sec:($duration_sec|tonumber? // $duration_sec)} end)
     + (if $detail=="" then {} else {detail:$detail} end)
    ' >> "$LOG_FILE" 2>/dev/null || true
}

# Best-available context for the exit trap. TOPIC/loop aren't known yet this
# early — CURRENT_TOPIC/CURRENT_LOOP get set as the script actually learns
# them, so a failure before that point just logs with those fields omitted.
EXIT_REASON=""
CURRENT_TOPIC=""
CURRENT_LOOP=""

# Fires on every script termination: normal exit, `set -e` auto-exit on a
# failing command, or a caught signal (SIGINT/SIGTERM — bash runs the EXIT
# trap for these same as any other exit). SIGKILL cannot be trapped by any
# process, ever — a run killed with -9 leaves no matching script_end/error
# event; that is an OS-level limitation, not something this script can work
# around. Whatever kills the run via SIGTERM (the harness's normal
# background-task stop) IS caught here.
on_exit() {
  local ec=$?
  trap - EXIT
  local total_duration=$(( $(date +%s) - SCRIPT_START_EPOCH ))
  local vafter=""
  if [ -n "$CURRENT_TOPIC" ] && [ -f "${REGISTRY:-/nonexistent}" ]; then
    vafter="$(tally 2>/dev/null || echo "")"
  fi
  if [ "$ec" -eq 0 ]; then
    log_event topic_end topic="$CURRENT_TOPIC" loop="$CURRENT_LOOP" verified_after="$vafter" exit_code="0" detail="${EXIT_REASON:-normal_exit}"
  else
    log_event error topic="$CURRENT_TOPIC" loop="$CURRENT_LOOP" exit_code="$ec" detail="${EXIT_REASON:-unexpected_exit_or_signal}"
    log_event topic_end topic="$CURRENT_TOPIC" loop="$CURRENT_LOOP" verified_after="$vafter" exit_code="$ec" detail="ended_with_error"
  fi
  log_event script_end exit_code="$ec" duration_sec="$total_duration"
}
trap on_exit EXIT
# ---------------------------------------------------------------------------

command -v claude >/dev/null 2>&1 || { EXIT_REASON="missing_dependency_claude"; echo "ERROR: 'claude' not on PATH." >&2; exit 1; }
command -v jq     >/dev/null 2>&1 || { EXIT_REASON="missing_dependency_jq"; echo "ERROR: 'jq' not found." >&2; exit 1; }

TOPIC="${1:?Usage: bash scripts/harvest_entities.sh <agent|mcp|prompt|skill> [target=100]}"
TARGET="${2:-100}"
case "$TOPIC" in
  agent|mcp|prompt|skill) ;;
  *) EXIT_REASON="bad_topic_arg"; echo "ERROR: topic must be one of agent, mcp, prompt, skill (got '$TOPIC')." >&2; exit 1 ;;
esac
case "$TARGET" in
  ''|*[!0-9]*) EXIT_REASON="bad_target_arg"; echo "ERROR: target must be a positive integer (got '$TARGET')." >&2; exit 1 ;;
esac
CURRENT_TOPIC="$TOPIC"

S1="$ROOT/agents/stage1"

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

jq empty "$REGISTRY" 2>/dev/null || { EXIT_REASON="registry_invalid_json"; echo "ERROR: $REGISTRY is not valid JSON — refusing to continue." >&2; exit 1; }
jq empty "$LEDGER"   2>/dev/null || { EXIT_REASON="ledger_invalid_json"; echo "ERROR: $LEDGER is not valid JSON — refusing to continue." >&2; exit 1; }

BATCH_SIZE="${BATCH_SIZE:-25}"
MAX_LOOPS="${MAX_LOOPS:-12}"

FLAGS=(--output-format json); [ -n "${MODEL:-}" ] && FLAGS+=(--model "$MODEL"); [ "${USE_BARE:-false}" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "${EXTRA_FLAGS:-}" ] && FLAGS+=($EXTRA_FLAGS)
clean(){ sed '/^```/d' | jq .; }

tally() {
  jq --arg t "$TOPIC" '[.entities[] | select(.topic==$t and .description_source=="verified")] | length' "$REGISTRY"
}

log_event script_start topic="$TOPIC" target="$TARGET" command_label="harvest_entities" detail="batch_size=${BATCH_SIZE};max_loops=${MAX_LOOPS}"
log_event topic_start topic="$TOPIC" target="$TARGET" verified_before="$(tally)"

echo "[harvest][$TOPIC] starting. target=$TARGET verified entities. current: $(tally)/$TARGET"

loop=0
while :; do
  loop=$((loop+1))
  CURRENT_LOOP="$loop"
  current="$(tally)"
  log_event loop_start topic="$TOPIC" loop="$loop" target="$TARGET" verified_before="$current"

  if [ "$current" -ge "$TARGET" ]; then
    EXIT_REASON="target_reached"
    echo "[harvest][$TOPIC] target reached: $current/$TARGET verified. done."
    exit 0
  fi
  if [ "$loop" -gt "$MAX_LOOPS" ]; then
    EXIT_REASON="max_loops_reached"
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
    CLAUDE_CALL_START_EPOCH="$(date +%s)"
    log_event claude_call_start topic="$TOPIC" loop="$loop" command_label="candidate_batch" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS}"
    if claude -p "You are sourcing CANDIDATE urls for Stage 1G (entity extraction) — you do not extract or verify entities yourself here. Topic: $TOPIC. Seed sources, in priority order: (a) $AWESOME_LIST plus the source awesome-list raw README(s) it cites near its top (fetch those for entries beyond the report's own ~40-row cap), (b) $HITS_SHARD. For EVERY candidate you propose, resolve it to the PROJECT'S OWN primary URL — its own repo, docs page, model card, package page, paper, or official product page. Never emit an awesome-list README URL itself as a candidate's url. Drop any entry whose own primary URL cannot be determined rather than guessing. EXCLUDE any URL that is: already entity_extracted:true in the ledger at $LEDGER, already listed in attempted_urls[] in $ATTEMPTED, or already a url of an existing entity in $REGISTRY. Return at most $BATCH_SIZE candidates. Output ONLY JSON of the shape {\"hits\":[{\"url\":\"...\",\"title\":\"...\",\"snippet\":\"...\",\"domain\":\"...\"}]}. No prose, no fences." \
         --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_CANDIDATES" | jq -r '.result' | clean > "$BATCH_HITS" \
       && jq empty "$BATCH_HITS" 2>/dev/null; then
      log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="candidate_batch" exit_code="0" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS};ok"
      candidate_ok=true
      break
    fi
    log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="candidate_batch" exit_code="1" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS};invalid_output"
    echo "[harvest][$TOPIC] loop $loop: candidate-batch attempt $attempt/$CANDIDATE_ATTEMPTS produced invalid output (raw: $RAW_CANDIDATES) — retrying" >&2
  done
  if [ "$candidate_ok" != true ]; then
    EXIT_REASON="candidate_batch_failed_after_retries"
    echo "ERROR: candidate-batch step failed for topic '$TOPIC' after $CANDIDATE_ATTEMPTS attempts (raw output: $RAW_CANDIDATES, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  n_candidates=$(jq '.hits | length' "$BATCH_HITS")
  if [ "${n_candidates:-0}" -eq 0 ]; then
    EXIT_REASON="sources_exhausted_no_candidates"
    echo "[harvest][$TOPIC] loop $loop: 0 candidates found — sources exhausted at $current/$TARGET verified."
    exit 0
  fi
  echo "[harvest][$TOPIC] loop $loop: $n_candidates candidate(s)"

  # record every URL sent this loop as attempted, before we know 1G's verdict —
  # this is what stops a later loop from re-selecting a dropped/rejected candidate.
  if ! jq -s '{attempted_urls: ((.[0].attempted_urls // []) + [.[1].hits[]?.url]) | unique}' \
       "$ATTEMPTED" "$BATCH_HITS" > "$ATTEMPTED.tmp"; then
    rm -f "$ATTEMPTED.tmp"
    EXIT_REASON="attempted_set_merge_failed"
    echo "ERROR: attempted-set merge (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$ATTEMPTED.tmp" 2>/dev/null || { rm -f "$ATTEMPTED.tmp"; EXIT_REASON="attempted_set_invalid_json"; echo "ERROR: attempted-set merge produced invalid JSON — aborting." >&2; exit 1; }
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
    EXIT_REASON="ledger_seed_failed"
    echo "ERROR: ledger seed (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$LEDGER.tmp" 2>/dev/null || { rm -f "$LEDGER.tmp"; EXIT_REASON="ledger_seed_invalid_json"; echo "ERROR: ledger seed produced invalid JSON — aborting." >&2; exit 1; }
  mv "$LEDGER.tmp" "$LEDGER"

  echo "[harvest][$TOPIC] loop $loop: running 1G (fetch + verify each candidate)"
  # Same transient stray-prose failure mode as the candidate-batch step above (confirmed by
  # live runs — it hits either claude -p call, not just the first one) — retry here too rather
  # than hard-failing the whole loop over a formatting slip.
  ONEG_ATTEMPTS="${ONEG_ATTEMPTS:-3}"
  oneg_ok=false
  for attempt in $(seq 1 "$ONEG_ATTEMPTS"); do
    CLAUDE_CALL_START_EPOCH="$(date +%s)"
    log_event claude_call_start topic="$TOPIC" loop="$loop" command_label="1g_extraction" detail="attempt=${attempt}/${ONEG_ATTEMPTS}"
    if claude -p "Follow your system instructions. Hits: $BATCH_HITS. Visited-URL ledger: $LEDGER (use its entity_extracted/entity_ids fields, separate from 1C's extracted/case_ids on the same rows). Fetch each candidate's own page before extracting; only set description_source:\"verified\" when the description came from that fetch, never from the snippet alone — if the page can't be fetched, use description_source:\"snippet-only\" per your existing rules rather than marking it verified. Output ONLY the entity batch JSON (entities, ledger_patch). No prose, no fences." \
         --append-system-prompt "$(cat "$S1/1G_entity_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_1G" | jq -r '.result' | clean > "$BATCH_ENTITIES" \
       && jq empty "$BATCH_ENTITIES" 2>/dev/null; then
      log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="1g_extraction" exit_code="0" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${ONEG_ATTEMPTS};ok"
      oneg_ok=true
      break
    fi
    log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="1g_extraction" exit_code="1" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${ONEG_ATTEMPTS};invalid_output"
    echo "[harvest][$TOPIC] loop $loop: 1G attempt $attempt/$ONEG_ATTEMPTS produced invalid output (raw: $RAW_1G) — retrying" >&2
  done
  if [ "$oneg_ok" != true ]; then
    EXIT_REASON="oneg_extraction_failed_after_retries"
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
    EXIT_REASON="ledger_patch_merge_failed"
    echo "ERROR: ledger merge (jq) failed for topic '$TOPIC' — aborting." >&2
    exit 1
  fi
  jq empty "$LEDGER.tmp" 2>/dev/null || { rm -f "$LEDGER.tmp"; EXIT_REASON="ledger_patch_invalid_json"; echo "ERROR: ledger merge produced invalid JSON — aborting." >&2; exit 1; }
  mv "$LEDGER.tmp" "$LEDGER"

  before="$(tally)"
  MERGE_START_EPOCH="$(date +%s)"
  log_event merge_start topic="$TOPIC" loop="$loop" verified_before="$before" command_label="merge_entity_registry"
  if bash "$ROOT/scripts/merge_entity_registry.sh" "$BATCH_ENTITIES" "$REGISTRY"; then
    MERGE_EC=0
  else
    MERGE_EC=$?
  fi
  if [ "$MERGE_EC" -ne 0 ]; then
    log_event merge_end topic="$TOPIC" loop="$loop" exit_code="$MERGE_EC" duration_sec="$(( $(date +%s) - MERGE_START_EPOCH ))" detail="merge_entity_registry_failed"
    EXIT_REASON="merge_entity_registry_failed"
    echo "ERROR: merge_entity_registry.sh failed for topic '$TOPIC'." >&2
    exit 1
  fi
  if ! jq empty "$REGISTRY" 2>/dev/null; then
    log_event merge_end topic="$TOPIC" loop="$loop" exit_code="1" duration_sec="$(( $(date +%s) - MERGE_START_EPOCH ))" detail="registry_invalid_json_after_merge"
    EXIT_REASON="registry_invalid_after_merge"
    echo "ERROR: $REGISTRY became invalid JSON after merge — aborting." >&2
    exit 1
  fi
  after="$(tally)"
  added=$((after - before))
  log_event merge_end topic="$TOPIC" loop="$loop" verified_before="$before" verified_after="$after" exit_code="0" duration_sec="$(( $(date +%s) - MERGE_START_EPOCH ))" detail="added=${added}"

  echo "[harvest][$TOPIC] loop $loop: +$added new verified -> $after/$TARGET verified"

  if [ "$added" -le 0 ]; then
    EXIT_REASON="sources_exhausted_no_new_verified"
    echo "[harvest][$TOPIC] loop $loop added 0 new verified entities — sources exhausted at $after/$TARGET verified."
    exit 0
  fi
done
