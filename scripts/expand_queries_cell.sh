#!/usr/bin/env bash
# expand_queries_cell.sh — Stage 1A query expansion for ONE (category, topic) cell.
#
# The existing 1A step (scripts/run_stage1.sh) expands every seed topic in a
# SINGLE claude call and writes one state/search_strategy_db.json. That is the
# same shape of problem the entity harvest had: one monolithic call, one shared
# mutable file, no way to run topics concurrently. This script is the per-cell
# version — it expands exactly one (category, topic) pair into a file only that
# cell writes, so every cell's expansion can run at the same time.
#
#   Usage: bash scripts/expand_queries_cell.sh <i> <j> [--check]
#
# <i> <j> are 1-based indices into state/matrix/manifest.json, written by
# scripts/matrix_spec.py. The manifest is the only place the index-to-name
# mapping lives; this script never re-derives it.
#
# Output: state/matrix/queries_category#<i>_topic#<j>.json
#   {category, topic, cell_id, generated_at, queries:[{query_id, query,
#    query_type, target_platforms, seed_source_urls, status, created_at,
#    run_count, yield_count}]}
#
# AUGMENTS, never clobbers: an existing queries file is passed to the model as
# the de-dup baseline, and the result is only installed if it is valid JSON of
# the right shape AND has at least as many queries as it started with. A model
# that "helpfully" returns three queries where forty existed would otherwise
# silently destroy prior expansion work.
#
# `--check` prints one status line and exits 0 with NO claude call and NO side
# effects — used by the orchestrator to skip cells that are already expanded.
#
# Env: TARGET_QUERIES (default 24) · CLAUDE_BIN · STATE_DIR · MODEL ·
#      EXPAND_ATTEMPTS (default 3)
#
# Exit 0: queries written (or --check). Exit 1: bad args, missing manifest,
#         lock held, or the model failed after EXPAND_ATTEMPTS.
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
I="${POSITIONAL[0]:?Usage: bash scripts/expand_queries_cell.sh <i> <j> [--check]}"
J="${POSITIONAL[1]:?Usage: bash scripts/expand_queries_cell.sh <i> <j> [--check]}"
case "$I" in ''|*[!0-9]*) echo "ERROR: i must be a positive integer (got '$I')." >&2; exit 1 ;; esac
case "$J" in ''|*[!0-9]*) echo "ERROR: j must be a positive integer (got '$J')." >&2; exit 1 ;; esac

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
QFILE="$MDIR/$(printf '%s' "$CELL_JSON" | jq -r '.queries_file')"

TARGET_QUERIES="${TARGET_QUERIES:-24}"

# --check: pure read-only. Must not create the file, the dir, or a lock.
if [ "$CHECK_MODE" = true ]; then
  if [ -f "$QFILE" ] && jq empty "$QFILE" 2>/dev/null; then
    n="$(jq '[.queries[]? | select((.status // "active") == "active")] | length' "$QFILE")"
  else
    n=0
  fi
  if [ "${n:-0}" -ge "$TARGET_QUERIES" ]; then st="complete"; else st="incomplete"; fi
  echo "[expand][$CELL_ID] check: queries=$n target=$TARGET_QUERIES status=$st category='$CATEGORY' topic='$TOPIC'"
  exit 0
fi

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || { echo "ERROR: CLAUDE_BIN '$CLAUDE_BIN' not on PATH." >&2; exit 1; }

mkdir -p "$MDIR"

# One expander per cell. Different cells never block each other — that is the
# point — but two runs of the SAME cell would both rewrite $QFILE.
LOCK="$STATE/locks/expand_${CELL_ID}.lock"
if ! lock_acquire "$LOCK" "expand:$CELL_ID"; then
  echo "ERROR: another expansion for $CELL_ID is already running (lock: $LOCK)." >&2
  exit 1
fi
trap 'lock_release "$LOCK"' EXIT

[ -f "$QFILE" ] && jq empty "$QFILE" 2>/dev/null || printf '{"category":%s,"topic":%s,"cell_id":%s,"generated_at":null,"queries":[]}\n' \
  "$(jq -Rn --arg v "$CATEGORY" '$v')" "$(jq -Rn --arg v "$TOPIC" '$v')" "$(jq -Rn --arg v "$CELL_ID" '$v')" > "$QFILE"

BEFORE="$(jq '.queries | length' "$QFILE")"

FLAGS=(--output-format json); [ -n "${MODEL:-}" ] && FLAGS+=(--model "$MODEL"); [ "${USE_BARE:-false}" = "true" ] && FLAGS+=(--bare)
# shellcheck disable=SC2206
[ -n "${EXTRA_FLAGS:-}" ] && FLAGS+=($EXTRA_FLAGS)
source "$ROOT/scripts/lib/clean_json.sh"

RAW="$MDIR/.raw_expand_${CELL_ID}.json"
ERR="$MDIR/.err_expand_${CELL_ID}.log"
TODAY="$(date -u +%Y-%m-%d)"

# valid_queries <file> — clean() guarantees valid JSON, not the right SHAPE.
valid_queries() {
  jq -e '
    (type == "object") and has("queries") and (.queries | type == "array")
    and (.queries | all(type == "object" and has("query") and (.query | type == "string") and (.query | length > 0)))
  ' "$1" >/dev/null 2>&1
}

echo "[expand][$CELL_ID] category='$CATEGORY' topic='$TOPIC' — expanding to >= $TARGET_QUERIES queries (have $BEFORE)"

EXPAND_ATTEMPTS="${EXPAND_ATTEMPTS:-3}"
TMP="$(mktemp "$MDIR/.tmp_q_${CELL_ID}_XXXXXX")"
ok=false
for attempt in $(seq 1 "$EXPAND_ATTEMPTS"); do
  if "$CLAUDE_BIN" -p "You are doing Stage 1A query expansion for exactly ONE cell of a harvest matrix. Category: \"$CATEGORY\". Topic: \"$TOPIC\". Expand this SPECIFIC intersection — every query must be about the topic AS IT APPLIES TO that category, not the topic in general and not the category in general. Today is $TODAY. Existing queries for this cell are in $QFILE — read it and treat every query already there as taken: return the full list (existing rows preserved verbatim, including their created_at/run_count/yield_count) PLUS enough genuinely new ones to reach at least $TARGET_QUERIES active queries total. Never delete a row; to retire one set its status to \"paused\". Expand along these axes so coverage is broad but precise: workflow+metric phrasings, named entity/vendor/product phrasings, platform-scoped queries (site:github.com, site:reddit.com, site:substack.com and similar), failure/skeptical phrasings, and broad seed pages (indexes, newsletters, channels that regularly cover this intersection) which go in seed_source_urls. Keep each query short and specific — a few words of signal plus operators. Output ONLY JSON of the shape {\"category\":\"$CATEGORY\",\"topic\":\"$TOPIC\",\"cell_id\":\"$CELL_ID\",\"generated_at\":\"$TODAY\",\"queries\":[{\"query_id\":\"${CELL_ID}-001\",\"query\":\"...\",\"query_type\":\"workflow_metric|entity|platform_scoped|failure|broad_seed\",\"target_platforms\":[\"web\"],\"seed_source_urls\":[],\"status\":\"active\",\"created_at\":\"$TODAY\",\"run_count\":0,\"yield_count\":0}]}. No prose, no fences." \
       --allowedTools "Read,WebSearch" "${FLAGS[@]}" \
       2> "$ERR" | tee "$RAW" | jq -r '.result' | clean > "$TMP" \
     && jq empty "$TMP" 2>/dev/null \
     && valid_queries "$TMP"; then
    ok=true
    break
  fi
  echo "[expand][$CELL_ID] attempt $attempt/$EXPAND_ATTEMPTS produced invalid output (raw: $RAW) — retrying" >&2
done

if [ "$ok" != true ]; then
  rm -f "$TMP"
  echo "ERROR: query expansion failed for $CELL_ID after $EXPAND_ATTEMPTS attempts (raw: $RAW, stderr: $ERR)." >&2
  exit 1
fi

# Never shrink. The prompt says "preserve existing rows", but a prompt is not a
# guarantee — enforce it here so a model that returns a fresh short list cannot
# destroy expansion work that has already been paid for.
AFTER="$(jq '.queries | length' "$TMP")"
if [ "$AFTER" -lt "$BEFORE" ]; then
  rm -f "$TMP"
  echo "ERROR: expansion returned $AFTER queries but $BEFORE already existed for $CELL_ID — refusing to shrink the set; $QFILE left unchanged." >&2
  exit 1
fi

# Stamp identity from the manifest, not from whatever the model echoed back.
jq --arg c "$CATEGORY" --arg t "$TOPIC" --arg id "$CELL_ID" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   '. + {category:$c, topic:$t, cell_id:$id, generated_at:$now}' "$TMP" > "$TMP.stamped" \
  && jq empty "$TMP.stamped" 2>/dev/null \
  || { rm -f "$TMP" "$TMP.stamped"; echo "ERROR: could not stamp cell identity onto $CELL_ID queries." >&2; exit 1; }
rm -f "$TMP"
mv "$TMP.stamped" "$QFILE"

ACTIVE="$(jq '[.queries[] | select((.status // "active")=="active")] | length' "$QFILE")"
echo "[expand][$CELL_ID] wrote $AFTER quer(y/ies) ($ACTIVE active, was $BEFORE) -> $QFILE"
exit 0
