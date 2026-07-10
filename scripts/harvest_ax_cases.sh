#!/usr/bin/env bash
# harvest_ax_cases.sh — repeatedly builds candidate batches of AX case leads,
# runs the ax_case_harvest_extractor over them, and merges into
# state/ax_case_harvest_registry.json until the registry has >= target
# verified cases, or sources are exhausted.
#
# This is a deliberately separate, isolated sibling of scripts/harvest_entities.sh
# — same retry-hardening and JSONL-timing-log pattern, but for AX transformation
# case leads instead of agent/mcp/prompt/skill entities. See
# docs/ax_case_strategy.md for the full design and why the two paths are kept
# apart:
#   - never reads or writes state/entity_registry.json
#   - never reads or writes state/ax_case_db.json (the rich pipeline's output)
#   - never reads or writes state/visited_url_ledger.json — no ledger
#     seed/patch step exists in this script at all; dedup against re-selecting
#     a candidate is handled entirely via this run's own attempted-set plus
#     the existing registry's source_url values
#
# "Verified" means verification_status:"verified" — the case was pulled from
# its own source page, not just a search snippet.
#
#   Usage: bash scripts/harvest_ax_cases.sh [target=250] [--check]
#
# `target` is the FINAL total number of verified cases the canonical registry
# state/ax_case_harvest_registry.json should reach — NOT a number to add.
# Existing verified cases count toward it, so the loop only closes the gap
# (target - current). The canonical count is: cases in that registry with
# verification_status == "verified". Dedup is by case_key at merge time, so
# duplicate case_key values, rejects, and extraction attempts are never counted.
#
# `--check` prints one status line (current/target/remaining/status) and exits
# 0 WITHOUT any claude call or side effects — used by scripts/harvest_all.sh to
# skip an already-complete registry, and by the target tests. Needs only jq.
#
# Reaching a large target (e.g. 250) is done in bounded per-loop batches
# (BATCH_SIZE candidates each), merging after every batch; an interrupted run
# resumes from the merged registry count on re-invoke.
#   BATCH_SIZE (default 40)  candidate URLs requested per loop
#   MAX_LOOPS (default 40)   hard upper bound on loops
#   NO_PROGRESS_THRESHOLD (default 3)  consecutive no-progress loops before stop
# Test/isolation overrides (default to production behavior):
#   STATE_DIR   relocate all state/registry/log/batch paths (default: <repo>/state)
#   CLAUDE_BIN  the claude executable to invoke (default: claude)
#
# Exit 0: target reached; OR sources exhausted (NO_PROGRESS_THRESHOLD
#         consecutive no-progress loops); OR MAX_LOOPS reached — each printed
#         with the final tally. A clean exit does NOT imply the target was met;
#         read the printed status (or re-run with --check) to confirm.
# Exit 1: missing dependency, bad arguments, a claude/jq step failing, or a
#         persistent file (registry) found or left invalid JSON.
#
# Timing recovery: every run writes structured JSONL timing events to
# state/logs/ax_case_harvest_<run_id>.jsonl (gitignored, transient) — see
# docs/ax_case_harvest_workflow.md § Timing logs for the event schema.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"

TOPIC="ax_cases"   # single lane (no per-topic split); used as the log/label key

# ---------------------------------------------------------------------------
# Argument parsing FIRST — before ANY side effect — so `--check` is a pure,
# read-only status query: it must not mkdir, must not create STATE_DIR / a
# registry / attempted-set / batch / log file, and must not install the exit
# trap. The only positional arg is [target]; `--check` may appear in any
# position and is stripped here.
# ---------------------------------------------------------------------------
CHECK_MODE=false
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_MODE=true ;;
    *)       POSITIONAL+=("$arg") ;;
  esac
done
TARGET="${POSITIONAL[0]:-250}"
case "$TARGET" in
  ''|*[!0-9]*) echo "ERROR: target must be a positive integer (got '$TARGET')." >&2; exit 1 ;;
esac

# STATE_DIR override relocates every derived path in one shot (registry, logs,
# batch/attempted files). Production default is <repo>/state. Resolved here ONCE
# as a plain variable — NOT created, and never reassigned below — so --check can
# read the registry path with zero filesystem side effects.
STATE="${STATE_DIR:-$ROOT/state}"
REGISTRY="$STATE/ax_case_harvest_registry.json"

# --check: pure read-only status. No trap, no mkdir, no file creation. A missing
# registry counts as 0 (it is NOT created). Needs only jq. Emits one
# machine-readable line for scripts/harvest_all.sh and the target tests, exit 0.
if [ "$CHECK_MODE" = true ]; then
  command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 1; }
  if [ -f "$REGISTRY" ]; then
    jq empty "$REGISTRY" 2>/dev/null || { echo "ERROR: $REGISTRY is not valid JSON." >&2; exit 1; }
    current="$(jq '[.cases[] | select(.verification_status=="verified")] | length' "$REGISTRY")"
  else
    current=0
  fi
  remaining=$(( TARGET - current ))
  if [ "$remaining" -lt 0 ]; then remaining=0; fi
  if [ "$current" -ge "$TARGET" ]; then status="complete"; else status="incomplete"; fi
  echo "[harvest][$TOPIC] check: current=$current target=$TARGET remaining=$remaining status=$status"
  exit 0
fi

# ---------------------------------------------------------------------------
# Structured JSONL timing log — set up first, before any exit-capable check,
# so even a missing-dependency failure gets captured. Same shape as
# harvest_entities.sh's log_event, with "topic" fixed to the constant
# "ax_cases" (there is only one lane here, unlike the four entity topics) so
# the same reconstruction tooling/queries work unchanged across both logs.
# ---------------------------------------------------------------------------
# STATE was resolved above (honoring STATE_DIR); create its log subdir now that
# we are past the read-only --check path (first side effect). STATE is NOT
# reassigned here.
mkdir -p "$STATE/logs"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LOG_FILE="$STATE/logs/ax_case_harvest_${RUN_ID}.jsonl"
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

EXIT_REASON=""
CURRENT_LOOP=""

# Fires on every script termination: normal exit, `set -e` auto-exit on a
# failing command, or a caught signal (SIGINT/SIGTERM). SIGKILL cannot be
# trapped by any process, ever — a run killed with -9 leaves no matching
# script_end/error event; that is an OS-level limitation, not something this
# script can work around.
on_exit() {
  local ec=$?
  trap - EXIT
  local total_duration=$(( $(date +%s) - SCRIPT_START_EPOCH ))
  local vafter=""
  if [ -f "${REGISTRY:-/nonexistent}" ]; then
    vafter="$(tally 2>/dev/null || echo "")"
  fi
  if [ "$ec" -eq 0 ]; then
    log_event topic_end topic="$TOPIC" loop="$CURRENT_LOOP" verified_after="$vafter" exit_code="0" detail="${EXIT_REASON:-normal_exit}"
  else
    log_event error topic="$TOPIC" loop="$CURRENT_LOOP" exit_code="$ec" detail="${EXIT_REASON:-unexpected_exit_or_signal}"
    log_event topic_end topic="$TOPIC" loop="$CURRENT_LOOP" verified_after="$vafter" exit_code="$ec" detail="ended_with_error"
  fi
  log_event script_end exit_code="$ec" duration_sec="$total_duration"
}
trap on_exit EXIT
# ---------------------------------------------------------------------------

# TARGET was parsed and validated at the top, before any side effect. Full-run
# dependency checks run here (with the trap active, so failures are logged):
# claude — via the overridable CLAUDE_BIN — is only needed for a real harvest,
# never for --check. CLAUDE_BIN defaults to "claude".
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || { EXIT_REASON="missing_dependency_claude"; echo "ERROR: CLAUDE_BIN '$CLAUDE_BIN' not on PATH." >&2; exit 1; }
command -v jq            >/dev/null 2>&1 || { EXIT_REASON="missing_dependency_jq"; echo "ERROR: 'jq' not found." >&2; exit 1; }

EXTRACTOR_SPEC="$ROOT/agents/stage1/ax_case_harvest_extractor.md"
AWESOME_LIST="$ROOT/reports/awesome-lists/awesome_ax-cases.md"
HITS_SHARD="$STATE/search_hits_ax.json"
# REGISTRY already set in the top block (used by --check); not reassigned here.
BATCH_HITS="$STATE/ax_case_harvest_hits.json"
BATCH_CASES="$STATE/ax_case_harvest_batch.json"
ATTEMPTED="$STATE/ax_case_harvest_attempted.json"
ERR_LOG="$STATE/ax_case_harvest.err"
# raw claude stdout for the most recent loop's two calls, captured unconditionally
# (overwritten each loop) so a parse failure downstream can actually be diagnosed
# instead of being lost inside a failed pipe — same reasoning as
# harvest_entities.sh's raw_candidates/raw_1g files.
RAW_CANDIDATES="$STATE/ax_case_harvest_raw_candidates.json"
RAW_EXTRACT="$STATE/ax_case_harvest_raw_extract.json"

[ -f "$REGISTRY" ] || echo '{"schema_version":1,"last_merged_at":null,"cases":[]}' > "$REGISTRY"
# attempted-set is transient and scoped to this invocation — reset every run
echo '{"attempted_urls":[]}' > "$ATTEMPTED"

jq empty "$REGISTRY" 2>/dev/null || { EXIT_REASON="registry_invalid_json"; echo "ERROR: $REGISTRY is not valid JSON — refusing to continue." >&2; exit 1; }

# Loop tuning — all env-overridable, kept DISTINCT from TARGET (the final count):
#   BATCH_SIZE            candidate URLs requested per loop (bounded; never the
#                         whole remaining gap in one oversized call)
#   MAX_LOOPS             hard upper bound on loops
#   NO_PROGRESS_THRESHOLD consecutive no-progress loops (0 candidates OR 0 new
#                         verified after merge) tolerated before declaring the
#                         sources exhausted and stopping safely
# Defaults are sized for a 250 target with attrition from duplicates, rejected
# candidates, and failed verification; a single unlucky batch no longer halts
# the run (the counter must reach the threshold), but the run always terminates.
BATCH_SIZE="${BATCH_SIZE:-40}"
MAX_LOOPS="${MAX_LOOPS:-40}"
NO_PROGRESS_THRESHOLD="${NO_PROGRESS_THRESHOLD:-3}"

FLAGS=(--output-format json); [ -n "${MODEL:-}" ] && FLAGS+=(--model "$MODEL"); [ "${USE_BARE:-false}" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "${EXTRA_FLAGS:-}" ] && FLAGS+=($EXTRA_FLAGS)
# clean() — robust JSON recovery from a (possibly prose- or fence-wrapped)
# nested `claude -p` result; strips fences, recovers a single top-level JSON
# object/array via a string/escape-aware scan, validates with jq, and fails
# loudly on none/ambiguous/invalid. See scripts/lib/clean_json.sh.
source "$ROOT/scripts/lib/clean_json.sh"

tally() {
  jq '[.cases[] | select(.verification_status=="verified")] | length' "$REGISTRY"
}

log_event script_start topic="$TOPIC" target="$TARGET" command_label="harvest_ax_cases" detail="batch_size=${BATCH_SIZE};max_loops=${MAX_LOOPS}"
log_event topic_start topic="$TOPIC" target="$TARGET" verified_before="$(tally)"

echo "[harvest][ax_cases] starting. target=$TARGET verified cases. current: $(tally)/$TARGET"

loop=0
no_progress=0   # consecutive loops that added no new verified records
while :; do
  loop=$((loop+1))
  CURRENT_LOOP="$loop"
  current="$(tally)"
  remaining=$(( TARGET - current )); if [ "$remaining" -lt 0 ]; then remaining=0; fi
  log_event loop_start topic="$TOPIC" loop="$loop" target="$TARGET" verified_before="$current"

  if [ "$current" -ge "$TARGET" ]; then
    EXIT_REASON="target_reached"
    echo "[harvest][ax_cases] target reached: $current/$TARGET verified. done."
    exit 0
  fi
  if [ "$loop" -gt "$MAX_LOOPS" ]; then
    EXIT_REASON="max_loops_reached"
    echo "[harvest][ax_cases] MAX_LOOPS ($MAX_LOOPS) reached at $current/$TARGET verified (remaining $remaining). stopping — target NOT met."
    exit 0
  fi
  echo "[harvest][ax_cases] loop $loop/$MAX_LOOPS: current=$current target=$TARGET remaining=$remaining no_progress=$no_progress/$NO_PROGRESS_THRESHOLD"

  echo "[harvest][ax_cases] loop $loop: building candidate batch (batch size <= $BATCH_SIZE)"
  # The model occasionally prefixes its JSON with a stray sentence despite the "no prose"
  # instruction — same transient failure mode observed repeatedly in harvest_entities.sh's
  # live runs. Retry a few times before treating it as a real failure.
  CANDIDATE_ATTEMPTS="${CANDIDATE_ATTEMPTS:-3}"
  candidate_ok=false
  for attempt in $(seq 1 "$CANDIDATE_ATTEMPTS"); do
    CLAUDE_CALL_START_EPOCH="$(date +%s)"
    log_event claude_call_start topic="$TOPIC" loop="$loop" command_label="candidate_batch" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS}"
    if "$CLAUDE_BIN" -p "You are sourcing CANDIDATE urls for an AX transformation case harvest — you do not extract or verify cases yourself here. Seed sources, in priority order: (a) $AWESOME_LIST plus the source awesome-list raw page(s) it cites near its top (for entries beyond the report's own cap), (b) $HITS_SHARD. For EVERY candidate you propose, resolve it to the page that actually describes the transformation story (a news article, case study, or company blog post — not an index/listicle page). Never emit an index/awesome-list page itself as a candidate's url. Drop any entry whose own source URL can't be determined rather than guessing. EXCLUDE any URL that is: already listed in attempted_urls[] in $ATTEMPTED, or already a source_url of an existing case in $REGISTRY. Return at most $BATCH_SIZE candidates. Output ONLY JSON of the shape {\"hits\":[{\"url\":\"...\",\"title\":\"...\",\"snippet\":\"...\",\"domain\":\"...\"}]}. No prose, no fences." \
         --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_CANDIDATES" | jq -r '.result' | clean > "$BATCH_HITS" \
       && jq empty "$BATCH_HITS" 2>/dev/null; then
      log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="candidate_batch" exit_code="0" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS};ok"
      candidate_ok=true
      break
    fi
    log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="candidate_batch" exit_code="1" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${CANDIDATE_ATTEMPTS};invalid_output"
    echo "[harvest][ax_cases] loop $loop: candidate-batch attempt $attempt/$CANDIDATE_ATTEMPTS produced invalid output (raw: $RAW_CANDIDATES) — retrying" >&2
  done
  if [ "$candidate_ok" != true ]; then
    EXIT_REASON="candidate_batch_failed_after_retries"
    echo "ERROR: candidate-batch step failed after $CANDIDATE_ATTEMPTS attempts (raw output: $RAW_CANDIDATES, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  n_candidates=$(jq '.hits | length' "$BATCH_HITS")
  if [ "${n_candidates:-0}" -eq 0 ]; then
    # 0 candidates is a no-progress event, not an immediate stop: a single empty
    # batch may be transient, and the next loop re-sources with the same
    # exclusions. Fold it into the SAME consecutive counter as a 0-added merge so
    # one bounded threshold governs all exhaustion, then move on.
    no_progress=$((no_progress+1))
    echo "[harvest][ax_cases] loop $loop: 0 candidates (no_progress=$no_progress/$NO_PROGRESS_THRESHOLD)"
    if [ "$no_progress" -ge "$NO_PROGRESS_THRESHOLD" ]; then
      EXIT_REASON="sources_exhausted_no_candidates"
      echo "[harvest][ax_cases] $no_progress consecutive no-progress loops — sources exhausted at $current/$TARGET verified (remaining $remaining). stopping — target NOT met."
      exit 0
    fi
    continue
  fi
  echo "[harvest][ax_cases] loop $loop: $n_candidates candidate(s)"

  # record every URL sent this loop as attempted, before we know the extractor's verdict —
  # this is what stops a later loop from re-selecting a dropped/rejected candidate. This is
  # the ONLY dedup mechanism in this script — there is no shared ledger to seed or patch.
  if ! jq -s '{attempted_urls: ((.[0].attempted_urls // []) + [.[1].hits[]?.url]) | unique}' \
       "$ATTEMPTED" "$BATCH_HITS" > "$ATTEMPTED.tmp"; then
    rm -f "$ATTEMPTED.tmp"
    EXIT_REASON="attempted_set_merge_failed"
    echo "ERROR: attempted-set merge (jq) failed — aborting." >&2
    exit 1
  fi
  jq empty "$ATTEMPTED.tmp" 2>/dev/null || { rm -f "$ATTEMPTED.tmp"; EXIT_REASON="attempted_set_invalid_json"; echo "ERROR: attempted-set merge produced invalid JSON — aborting." >&2; exit 1; }
  mv "$ATTEMPTED.tmp" "$ATTEMPTED"

  echo "[harvest][ax_cases] loop $loop: running extractor (fetch + verify each candidate)"
  EXTRACT_ATTEMPTS="${EXTRACT_ATTEMPTS:-3}"
  extract_ok=false
  for attempt in $(seq 1 "$EXTRACT_ATTEMPTS"); do
    CLAUDE_CALL_START_EPOCH="$(date +%s)"
    log_event claude_call_start topic="$TOPIC" loop="$loop" command_label="case_extraction" detail="attempt=${attempt}/${EXTRACT_ATTEMPTS}"
    if "$CLAUDE_BIN" -p "Follow your system instructions. Hits: $BATCH_HITS. Fetch each candidate's own page before extracting; only set verification_status:\"verified\" when the description came from that fetch, never from the snippet alone — if the page can't be fetched, use verification_status:\"snippet-only\" per your existing rules rather than marking it verified. Record transformation_date and publication_date as two separate fields, each \"unknown\" independently if the page does not state it — never infer one from the other. Output ONLY the case batch JSON (cases). No prose, no fences." \
         --append-system-prompt "$(cat "$EXTRACTOR_SPEC")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_EXTRACT" | jq -r '.result' | clean > "$BATCH_CASES" \
       && jq empty "$BATCH_CASES" 2>/dev/null; then
      log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="case_extraction" exit_code="0" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${EXTRACT_ATTEMPTS};ok"
      extract_ok=true
      break
    fi
    log_event claude_call_end topic="$TOPIC" loop="$loop" command_label="case_extraction" exit_code="1" duration_sec="$(( $(date +%s) - CLAUDE_CALL_START_EPOCH ))" detail="attempt=${attempt}/${EXTRACT_ATTEMPTS};invalid_output"
    echo "[harvest][ax_cases] loop $loop: extractor attempt $attempt/$EXTRACT_ATTEMPTS produced invalid output (raw: $RAW_EXTRACT) — retrying" >&2
  done
  if [ "$extract_ok" != true ]; then
    EXIT_REASON="extract_failed_after_retries"
    echo "ERROR: case extraction step failed after $EXTRACT_ATTEMPTS attempts (raw output: $RAW_EXTRACT, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  before="$(tally)"
  MERGE_START_EPOCH="$(date +%s)"
  log_event merge_start topic="$TOPIC" loop="$loop" verified_before="$before" command_label="merge_ax_case_harvest_registry"
  if bash "$ROOT/scripts/merge_ax_case_harvest_registry.sh" "$BATCH_CASES" "$REGISTRY"; then
    MERGE_EC=0
  else
    MERGE_EC=$?
  fi
  if [ "$MERGE_EC" -ne 0 ]; then
    log_event merge_end topic="$TOPIC" loop="$loop" exit_code="$MERGE_EC" duration_sec="$(( $(date +%s) - MERGE_START_EPOCH ))" detail="merge_ax_case_harvest_registry_failed"
    EXIT_REASON="merge_ax_case_harvest_registry_failed"
    echo "ERROR: merge_ax_case_harvest_registry.sh failed." >&2
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

  remaining=$(( TARGET - after )); if [ "$remaining" -lt 0 ]; then remaining=0; fi
  dropped=$(( n_candidates - added )); if [ "$dropped" -lt 0 ]; then dropped=0; fi
  # rejection/duplicate impact: of n_candidates URLs sent, only `added` became new
  # verified cases; the rest were duplicate case_keys, rejected by the extractor,
  # or fetched but unverifiable.
  echo "[harvest][ax_cases] loop $loop/$MAX_LOOPS: current=$after target=$TARGET remaining=$remaining | candidates=$n_candidates, +$added new verified ($dropped dropped: dup/rejected/unverified)"

  if [ "$added" -le 0 ]; then
    # No new verified this loop. Do NOT stop on the first occurrence — one batch
    # of all-duplicate/all-rejected candidates can be followed by a productive
    # one (the attempted-set grew, so the next loop sources different URLs). Only
    # after NO_PROGRESS_THRESHOLD CONSECUTIVE no-progress loops do we conclude the
    # sources are exhausted and stop safely.
    no_progress=$((no_progress+1))
    echo "[harvest][ax_cases] loop $loop added 0 new verified (no_progress=$no_progress/$NO_PROGRESS_THRESHOLD)"
    if [ "$no_progress" -ge "$NO_PROGRESS_THRESHOLD" ]; then
      EXIT_REASON="sources_exhausted_no_new_verified"
      echo "[harvest][ax_cases] $no_progress consecutive no-progress loops — sources exhausted at $after/$TARGET verified (remaining $remaining). stopping — target NOT met."
      exit 0
    fi
  else
    no_progress=0   # progress resets the consecutive counter
  fi
done
