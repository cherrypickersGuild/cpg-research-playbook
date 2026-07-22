#!/usr/bin/env bash
# harvest_matrix_cell.sh — harvest ONE (category, topic) cell of the matrix.
#
# Same loop shape as scripts/harvest_entities.sh — candidate sourcing, GitHub
# metadata prefetch, Stage 1G extraction, merge, bounded progress accounting —
# with two deliberate differences:
#
#   1. The SEED is this cell's expanded query set (written by
#      expand_queries_cell.sh), not a curated awesome-list. Arbitrary
#      (category, topic) pairs have no hand-maintained list to read; queries are
#      what stands in for one.
#   2. Everything it writes is scoped to the cell, so every cell of the matrix
#      can run concurrently:
#
#        state/matrix/category#i_topic#j.json          harvested entities
#        state/matrix/.ledger_category#i_topic#j.json  visited-URL ledger
#        state/matrix/.attempted_…  .ghcache_…  .ghmeta_…  .hits_…  .batch_…
#        state/locks/harvest_category#i_topic#j.lock   lane lock
#
# Reuses the tested pieces rather than reimplementing them: lib/lockdir.sh,
# lib/clean_json.sh, merge_entity_registry.sh (which passes unknown fields
# through, so the `category` stamp survives the merge) and github_meta.py.
#
#   Usage: bash scripts/harvest_matrix_cell.sh <i> <j> [target=60] [--check]
#
# `target` is the FINAL number of verified entities this CELL should hold, not a
# number to add — same semantics as harvest_entities.sh, so an interrupted run
# resumes from the merged count.
#
# `--check` prints one status line, exits 0, and has NO claude call and NO side
# effects (no mkdir, no file creation, no lock).
#
# Env: BATCH_SIZE (12) · MAX_LOOPS (12) · NO_PROGRESS_THRESHOLD (3) ·
#      CANDIDATE_ATTEMPTS (3) · ONEG_ATTEMPTS (3) · CLAUDE_BIN · STATE_DIR · MODEL
#
# Exit 0: target reached, sources exhausted, or MAX_LOOPS — read the printed
#         status; a clean exit does NOT imply the target was met.
# Exit 1: bad args, missing manifest/queries, lock held, or a step failed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"
source "$ROOT/scripts/lib/lockdir.sh"

CHECK_MODE=false
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_MODE=true ;;
    *)       POSITIONAL+=("$arg") ;;
  esac
done
I="${POSITIONAL[0]:?Usage: bash scripts/harvest_matrix_cell.sh <i> <j> [target=60] [--check]}"
J="${POSITIONAL[1]:?Usage: bash scripts/harvest_matrix_cell.sh <i> <j> [target=60] [--check]}"
TARGET="${POSITIONAL[2]:-60}"
for v in "$I" "$J" "$TARGET"; do
  case "$v" in ''|*[!0-9]*) echo "ERROR: i, j and target must be positive integers (got '$v')." >&2; exit 1 ;; esac
done

command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 1; }

STATE="${STATE_DIR:-$ROOT/state}"
MDIR="$STATE/matrix"
MANIFEST="$MDIR/manifest.json"
[ -f "$MANIFEST" ] || { echo "ERROR: no manifest at $MANIFEST — run scripts/matrix_spec.py first." >&2; exit 1; }
jq empty "$MANIFEST" 2>/dev/null || { echo "ERROR: $MANIFEST is not valid JSON." >&2; exit 1; }

CELL_JSON="$(jq -c --argjson i "$I" --argjson j "$J" '.cells[] | select(.i==$i and .j==$j)' "$MANIFEST")"
[ -n "$CELL_JSON" ] || { echo "ERROR: no cell ($I,$J) in $MANIFEST." >&2; exit 1; }
CELL_ID="$(printf '%s' "$CELL_JSON" | jq -r '.cell_id')"
CATEGORY="$(printf '%s' "$CELL_JSON" | jq -r '.category')"
TOPIC="$(printf '%s' "$CELL_JSON" | jq -r '.topic')"
CELL_FILE="$MDIR/$(printf '%s' "$CELL_JSON" | jq -r '.harvest_file')"
QFILE="$MDIR/$(printf '%s' "$CELL_JSON" | jq -r '.queries_file')"

# --check: pure read-only status. Creates nothing, locks nothing.
if [ "$CHECK_MODE" = true ]; then
  if [ -f "$CELL_FILE" ] && jq empty "$CELL_FILE" 2>/dev/null; then
    current="$(jq '[.entities[]? | select(.description_source=="verified")] | length' "$CELL_FILE")"
  else
    current=0
  fi
  remaining=$(( TARGET - current )); [ "$remaining" -lt 0 ] && remaining=0
  if [ "$current" -ge "$TARGET" ]; then status="complete"; else status="incomplete"; fi
  echo "[cell][$CELL_ID] check: current=$current target=$TARGET remaining=$remaining status=$status category='$CATEGORY' topic='$TOPIC'"
  exit 0
fi

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || { echo "ERROR: CLAUDE_BIN '$CLAUDE_BIN' not on PATH." >&2; exit 1; }

mkdir -p "$MDIR"

LOCK="$STATE/locks/harvest_${CELL_ID}.lock"
if ! lock_acquire "$LOCK" "harvest_matrix:$CELL_ID"; then
  echo "ERROR: another harvest for $CELL_ID is already running (lock: $LOCK)." >&2
  echo "       Different cells run in parallel; the same cell does not." >&2
  exit 1
fi
trap 'lock_release "$LOCK"' EXIT

# The queries file IS the seed. Without it there is nothing to search, so this is
# a hard prerequisite rather than a warning — harvesting a cell with no expansion
# would fall back to the model inventing its own scope, which is exactly the
# uncontrolled sourcing the matrix design exists to avoid.
[ -f "$QFILE" ] && jq empty "$QFILE" 2>/dev/null \
  || { echo "ERROR: no valid query set for $CELL_ID at $QFILE — run: bash scripts/expand_queries_cell.sh $I $J" >&2; exit 1; }
NQ="$(jq '[.queries[]? | select((.status // "active")=="active")] | length' "$QFILE")"
[ "${NQ:-0}" -gt 0 ] || { echo "ERROR: $QFILE has no active queries for $CELL_ID." >&2; exit 1; }

LEDGER="$MDIR/.ledger_${CELL_ID}.json"
ATTEMPTED="$MDIR/.attempted_${CELL_ID}.json"
BATCH_HITS="$MDIR/.hits_${CELL_ID}.json"
BATCH_ENTITIES="$MDIR/.batch_${CELL_ID}.json"
RAW_CANDIDATES="$MDIR/.raw_cand_${CELL_ID}.json"
RAW_1G="$MDIR/.raw_1g_${CELL_ID}.json"
ERR_LOG="$MDIR/.err_${CELL_ID}.log"
GH_CACHE="$MDIR/.ghcache_${CELL_ID}.json"
GH_META="$MDIR/.ghmeta_${CELL_ID}.json"

[ -f "$CELL_FILE" ] || jq -n --arg c "$CATEGORY" --arg t "$TOPIC" --arg id "$CELL_ID" \
  '{schema_version:2, cell_id:$id, category:$c, topic:$t, last_merged_at:null, entities:[]}' > "$CELL_FILE"
[ -f "$LEDGER" ] || echo '{"ledger":[]}' > "$LEDGER"
echo '{"attempted_urls":[]}' > "$ATTEMPTED"   # transient, scoped to this invocation

jq empty "$CELL_FILE" 2>/dev/null || { echo "ERROR: $CELL_FILE is not valid JSON — refusing to continue." >&2; exit 1; }
jq empty "$LEDGER"    2>/dev/null || { echo "ERROR: $LEDGER is not valid JSON — refusing to continue." >&2; exit 1; }

BATCH_SIZE="${BATCH_SIZE:-12}"
MAX_LOOPS="${MAX_LOOPS:-12}"
NO_PROGRESS_THRESHOLD="${NO_PROGRESS_THRESHOLD:-3}"
CANDIDATE_ATTEMPTS="${CANDIDATE_ATTEMPTS:-3}"
ONEG_ATTEMPTS="${ONEG_ATTEMPTS:-3}"

FLAGS=(--output-format json); [ -n "${MODEL:-}" ] && FLAGS+=(--model "$MODEL"); [ "${USE_BARE:-false}" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "${EXTRA_FLAGS:-}" ] && FLAGS+=($EXTRA_FLAGS)
source "$ROOT/scripts/lib/clean_json.sh"
S1="$ROOT/agents/stage1"

valid_1g_batch() {
  jq -e '
    (type == "object")
    and has("entities")     and (.entities     | type == "array")
    and (.entities     | all(type == "object"))
    and has("ledger_patch") and (.ledger_patch | type == "array")
    and (.ledger_patch | all(type == "object" and has("url") and (.url | type == "string")))
  ' "$1" >/dev/null 2>&1
}

tally() { jq '[.entities[]? | select(.description_source=="verified")] | length' "$CELL_FILE"; }

echo "[cell][$CELL_ID] category='$CATEGORY' topic='$TOPIC' target=$TARGET verified. current: $(tally)/$TARGET ($NQ active queries)"

loop=0
no_progress=0
while :; do
  loop=$((loop+1))
  current="$(tally)"
  remaining=$(( TARGET - current )); [ "$remaining" -lt 0 ] && remaining=0

  if [ "$current" -ge "$TARGET" ]; then
    echo "[cell][$CELL_ID] target reached: $current/$TARGET verified. done."
    exit 0
  fi
  if [ "$loop" -gt "$MAX_LOOPS" ]; then
    echo "[cell][$CELL_ID] MAX_LOOPS ($MAX_LOOPS) reached at $current/$TARGET (remaining $remaining). stopping — target NOT met."
    exit 0
  fi
  echo "[cell][$CELL_ID] loop $loop/$MAX_LOOPS: current=$current target=$TARGET remaining=$remaining no_progress=$no_progress/$NO_PROGRESS_THRESHOLD"

  # ---- candidate sourcing, seeded by this cell's queries ---------------------
  candidate_ok=false
  for attempt in $(seq 1 "$CANDIDATE_ATTEMPTS"); do
    if "$CLAUDE_BIN" -p "You are sourcing CANDIDATE urls for Stage 1G entity extraction — you do not extract or verify entities here. This is ONE cell of a harvest matrix: category=\"$CATEGORY\", topic=\"$TOPIC\". A candidate only belongs in this cell if it is relevant to the topic AS APPLIED TO that category; a generic $TOPIC tool with no $CATEGORY connection does NOT belong here, and neither does a $CATEGORY resource unrelated to $TOPIC. Your search worklist is $QFILE — run its active queries with WebSearch (prefer ones with the lowest run_count) and follow their seed_source_urls. For EVERY candidate return BOTH urls: source_url = the page where you found it (search result page, index, or citing article — never omit), and target_url = a best-effort resolved primary url for the entity itself (its own repo, docs page, model card, package page, paper, or official product page). If you cannot confidently resolve target_url, emit the literal string \"unknown\" rather than guessing — 1G will try to resolve it. Never copy source_url into target_url to fill the field. EXCLUDE any candidate whose source_url is already entity_extracted:true in $LEDGER or listed in attempted_urls[] in $ATTEMPTED, and any whose target_url (when not \"unknown\") is already a target_url in $CELL_FILE. Return at most $BATCH_SIZE candidates. Output ONLY JSON of the shape {\"hits\":[{\"source_url\":\"...\",\"target_url\":\"...\",\"title\":\"...\",\"snippet\":\"...\",\"domain\":\"...\"}]}. No prose, no fences." \
         --allowedTools "Read,WebSearch,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_CANDIDATES" | jq -r '.result' | clean > "$BATCH_HITS" \
       && jq empty "$BATCH_HITS" 2>/dev/null; then
      candidate_ok=true; break
    fi
    echo "[cell][$CELL_ID] loop $loop: candidate attempt $attempt/$CANDIDATE_ATTEMPTS produced invalid output (raw: $RAW_CANDIDATES) — retrying" >&2
  done
  if [ "$candidate_ok" != true ]; then
    echo "ERROR: candidate step failed for $CELL_ID after $CANDIDATE_ATTEMPTS attempts (raw: $RAW_CANDIDATES, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  n_candidates=$(jq '.hits | length' "$BATCH_HITS")
  if [ "${n_candidates:-0}" -eq 0 ]; then
    no_progress=$((no_progress+1))
    echo "[cell][$CELL_ID] loop $loop: 0 candidates (no_progress=$no_progress/$NO_PROGRESS_THRESHOLD)"
    if [ "$no_progress" -ge "$NO_PROGRESS_THRESHOLD" ]; then
      echo "[cell][$CELL_ID] $no_progress consecutive no-progress loops — sources exhausted at $current/$TARGET. stopping — target NOT met."
      exit 0
    fi
    continue
  fi
  echo "[cell][$CELL_ID] loop $loop: $n_candidates candidate(s)"

  # ---- attempted-set + ledger seed (unique temps; never a fixed .tmp) --------
  ATT_TMP="$(mktemp "$MDIR/.tmp_att_XXXXXX")"
  if ! jq -s '{attempted_urls: ((.[0].attempted_urls // []) + [.[1].hits[]?.source_url]) | unique}' \
       "$ATTEMPTED" "$BATCH_HITS" > "$ATT_TMP" || ! jq empty "$ATT_TMP" 2>/dev/null; then
    rm -f "$ATT_TMP"; echo "ERROR: attempted-set merge failed for $CELL_ID — aborting." >&2; exit 1
  fi
  mv "$ATT_TMP" "$ATTEMPTED"

  LED_TMP="$(mktemp "$MDIR/.tmp_led_XXXXXX")"
  if ! jq -s --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
      (.[1].hits // []) as $hits
      | { ledger: ( (.[0].ledger // []) + ($hits | map({
            url: .source_url, url_type: "news_url", platform: (.platform // "custom"),
            first_crawled_at: $now, last_crawled_at: $now, crawl_count: 1,
            http_status_last: null, content_hash: null,
            extracted: false, case_ids: [], entity_extracted: false, entity_ids: []
          })) ) | unique_by(.url) }' \
       "$LEDGER" "$BATCH_HITS" > "$LED_TMP" || ! jq empty "$LED_TMP" 2>/dev/null; then
    rm -f "$LED_TMP"; echo "ERROR: ledger seed failed for $CELL_ID — aborting." >&2; exit 1
  fi
  mv "$LED_TMP" "$LEDGER"

  # ---- deterministic GitHub metadata (outside the model, non-fatal) ---------
  if ! python "$ROOT/scripts/github_meta.py" prefetch --hits "$BATCH_HITS" --cache "$GH_CACHE" --out "$GH_META" >>"$ERR_LOG" 2>&1; then
    echo "[cell][$CELL_ID] loop $loop: GitHub metadata prefetch failed — continuing with empty metadata (github_stars null)" >&2
  fi
  jq empty "$GH_META" 2>/dev/null || echo '{"repos":{}}' > "$GH_META"

  # ---- 1G extraction --------------------------------------------------------
  echo "[cell][$CELL_ID] loop $loop: running 1G (fetch + verify each candidate)"
  oneg_ok=false
  for attempt in $(seq 1 "$ONEG_ATTEMPTS"); do
    if "$CLAUDE_BIN" -p "Follow your system instructions. Hits (shape: {hits:[{source_url,target_url,title,snippet,domain}]}): $BATCH_HITS. Visited-URL ledger: $LEDGER (keyed by source_url — use its entity_extracted/entity_ids fields). This batch belongs to matrix cell category=\"$CATEGORY\", topic=\"$TOPIC\": set every emitted entity's topic to exactly \"$TOPIC\" and add a \"category\" field set to exactly \"$CATEGORY\". Emit source_url verbatim from the hit; for target_url, verify-or-resolve it yourself via WebFetch (the candidate step may have set it to \"unknown\"), and pull the description from target_url specifically — description_source:\"verified\" means the description came from target_url, never from source_url and never from the snippet alone. If target_url cannot be confidently resolved or fetched, write target_url:\"unknown\" and description_source:\"snippet-only\". GitHub star counts are provided LOCALLY in $GH_META (a JSON file with a .repos object keyed by lowercase \"owner/repo\") — DO NOT call api.github.com and DO NOT WebFetch api.github.com. If target_url is a GitHub repo root, look up its lowercase owner/repo in $GH_META's .repos: if that entry's status is \"ok\", set github_stars to its integer .stars and prefer its .canonical_url as target_url; otherwise set github_stars:null — never estimate it from a page. In your ledger_patch[], echo source_url in the url field so it matches the seeded row. Output ONLY the entity batch JSON (entities, ledger_patch). No prose, no fences." \
         --append-system-prompt "$(cat "$S1/1G_entity_extractor.md")" --allowedTools "Read,WebFetch" "${FLAGS[@]}" \
         2> "$ERR_LOG" | tee "$RAW_1G" | jq -r '.result' | clean > "$BATCH_ENTITIES" \
       && jq empty "$BATCH_ENTITIES" 2>/dev/null \
       && valid_1g_batch "$BATCH_ENTITIES"; then
      oneg_ok=true; break
    fi
    echo "[cell][$CELL_ID] loop $loop: 1G attempt $attempt/$ONEG_ATTEMPTS produced invalid output (raw: $RAW_1G) — retrying" >&2
  done
  if [ "$oneg_ok" != true ]; then
    echo "ERROR: 1G step failed for $CELL_ID after $ONEG_ATTEMPTS attempts (raw: $RAW_1G, stderr: $ERR_LOG)." >&2
    exit 1
  fi

  # ---- ledger patch ---------------------------------------------------------
  LEDP_TMP="$(mktemp "$MDIR/.tmp_ledp_XXXXXX")"
  if ! jq -s '(.[1].ledger_patch // []) as $p
         | {ledger: [ .[0].ledger[] | . as $e | (($p[] | select(.url==$e.url)) // {}) as $u | $e + $u ]}' \
       "$LEDGER" "$BATCH_ENTITIES" > "$LEDP_TMP" || ! jq empty "$LEDP_TMP" 2>/dev/null; then
    rm -f "$LEDP_TMP"; echo "ERROR: ledger patch merge failed for $CELL_ID — aborting." >&2; exit 1
  fi
  mv "$LEDP_TMP" "$LEDGER"

  # ---- cell guard: stamp identity from the MANIFEST, not from the model ------
  # The same lesson as the entity harvest's topic guard, applied one level up: a
  # cell file must contain only this cell's rows, because that is what makes the
  # cells disjoint and therefore safe to write concurrently. Rather than drop
  # mislabelled rows here, overwrite topic/category from the manifest — unlike
  # the four fixed topics, `category` is a label this pipeline assigns to a cell,
  # not a property the model discovers, so the manifest is authoritative by
  # definition and there is no judgement to defer.
  GUARD_TMP="$(mktemp "$MDIR/.tmp_guard_XXXXXX")"
  if ! jq --arg c "$CATEGORY" --arg t "$TOPIC" \
       '.entities |= map(. + {topic:$t, category:$c})' "$BATCH_ENTITIES" > "$GUARD_TMP" \
     || ! jq empty "$GUARD_TMP" 2>/dev/null; then
    rm -f "$GUARD_TMP"; echo "ERROR: cell identity stamp failed for $CELL_ID — refusing to merge." >&2; exit 1
  fi
  mv "$GUARD_TMP" "$BATCH_ENTITIES"

  # ---- merge into the cell file --------------------------------------------
  before="$(tally)"
  if ! bash "$ROOT/scripts/merge_entity_registry.sh" "$BATCH_ENTITIES" "$CELL_FILE"; then
    echo "ERROR: merge_entity_registry.sh failed for $CELL_ID." >&2; exit 1
  fi
  jq empty "$CELL_FILE" 2>/dev/null || { echo "ERROR: $CELL_FILE became invalid JSON after merge — aborting." >&2; exit 1; }
  # merge_entity_registry.sh rewrites the whole document and knows nothing about
  # cells, so re-stamp the cell identity it dropped.
  ID_TMP="$(mktemp "$MDIR/.tmp_id_XXXXXX")"
  if jq --arg c "$CATEGORY" --arg t "$TOPIC" --arg id "$CELL_ID" \
       '. + {cell_id:$id, category:$c, topic:$t}' "$CELL_FILE" > "$ID_TMP" && jq empty "$ID_TMP" 2>/dev/null; then
    mv "$ID_TMP" "$CELL_FILE"
  else
    rm -f "$ID_TMP"
  fi

  after="$(tally)"
  added=$((after - before))
  remaining=$(( TARGET - after )); [ "$remaining" -lt 0 ] && remaining=0
  dropped=$(( n_candidates - added )); [ "$dropped" -lt 0 ] && dropped=0
  echo "[cell][$CELL_ID] loop $loop/$MAX_LOOPS: current=$after target=$TARGET remaining=$remaining | candidates=$n_candidates, +$added new verified ($dropped dropped: dup/rejected/unverified)"

  # ---- stamp query run counts so the next expansion can see what yielded ----
  Q_TMP="$(mktemp "$MDIR/.tmp_q_XXXXXX")"
  if jq --argjson added "$added" \
       '.queries |= map(if (.status // "active")=="active"
                        then . + {run_count: ((.run_count // 0) + 1),
                                  yield_count: ((.yield_count // 0) + $added)}
                        else . end)' "$QFILE" > "$Q_TMP" && jq empty "$Q_TMP" 2>/dev/null; then
    mv "$Q_TMP" "$QFILE"
  else
    rm -f "$Q_TMP"
  fi

  if [ "$added" -le 0 ]; then
    no_progress=$((no_progress+1))
    echo "[cell][$CELL_ID] loop $loop added 0 new verified (no_progress=$no_progress/$NO_PROGRESS_THRESHOLD)"
    if [ "$no_progress" -ge "$NO_PROGRESS_THRESHOLD" ]; then
      echo "[cell][$CELL_ID] $no_progress consecutive no-progress loops — sources exhausted at $after/$TARGET. stopping — target NOT met."
      exit 0
    fi
  else
    no_progress=0
  fi
done
