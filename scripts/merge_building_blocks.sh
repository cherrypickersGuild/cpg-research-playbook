#!/usr/bin/env bash
# merge_building_blocks.sh — fold the four per-topic BuildingBlocks shards back
# into the single union registry at state/entity_registry.json.
#
# Direction of truth, once the parallel harvest is in play:
#
#     BuildingBlocks_{Agent,MCP,Prompt,Skill}.json   AUTHORITATIVE per topic
#                     (each written by exactly one harvest lane)
#                              |  merge_building_blocks.sh   (this script)
#                              v
#     entity_registry.json                          DERIVED union, single writer
#
# The shards partition the corpus by topic, so the union is a concatenation, not
# a conflict resolution: no two shards can contain the same entity_key, because
# entity_key is `topic|name` and each shard holds exactly one topic. That is what
# makes parallel harvesting safe — the lanes are not racing over shared records,
# they are appending to disjoint sets.
#
# WITHIN a shard, dedup/corroboration/conflict-logging already happened at
# merge_entity_registry.sh time. This script deliberately does NOT re-run that
# logic: re-merging a whole shard as if it were a fresh batch would inflate
# corroboration_count and re-stamp last_corroborated_at on every run, turning an
# idempotent bookkeeping step into a data-drift generator. Running this script
# twice with unchanged shards produces a byte-identical union apart from
# last_merged_at.
#
# Union rows whose topic has no shard, or which a shard no longer carries, are
# PRESERVED and reported. Nothing in this pipeline deletes entities, so a row
# that vanished from a shard means the shard is incomplete (a truncated file, a
# half-restored backup) — not an instruction to delete. Preserving is the
# recoverable choice; deleting is not.
#
# Writing is single-writer and atomic: it takes the union lock, writes a unique
# temp, validates it, and only then renames over the union.
#
#   Usage:
#     bash scripts/merge_building_blocks.sh            # fold shards -> union
#     bash scripts/merge_building_blocks.sh --check    # report drift, write nothing
#     bash scripts/merge_building_blocks.sh --strict   # require every shard to exist
#
# Exit 0: union written (or --check completed).
# Exit 1: missing dependency, invalid shard, lock held, a missing shard under
#         --strict, or the merge produced invalid JSON (union left untouched in
#         every failure case).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/lockdir.sh"

CHECK_MODE=false
STRICT=false
for arg in "$@"; do
  case "$arg" in
    --check)  CHECK_MODE=true ;;
    --strict) STRICT=true ;;
    *) echo "Usage: bash scripts/merge_building_blocks.sh [--check] [--strict]" >&2; exit 1 ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 1; }

STATE="${STATE_DIR:-$ROOT/state}"
UNION="$STATE/entity_registry.json"
LOCK="$STATE/locks/entity_registry.lock"

SHARDS=(
  "agent:$STATE/BuildingBlocks_Agent.json"
  "mcp:$STATE/BuildingBlocks_MCP.json"
  "prompt:$STATE/BuildingBlocks_Prompt.json"
  "skill:$STATE/BuildingBlocks_Skill.json"
)

[ -f "$UNION" ] || echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[]}' > "$UNION"
jq empty "$UNION" 2>/dev/null || { echo "ERROR: $UNION is not valid JSON — refusing to continue." >&2; exit 1; }

# --- validate every shard BEFORE touching anything --------------------------
# Missing shard: DERIVED from the union rather than treated as an error. A shard
# can legitimately be absent — a repo that predates sharding, or a run where every
# lane was skipped because it was already at target and so no lane bootstrapped
# one. Deriving is provably lossless: the shard is filled with exactly the union's
# rows for that topic, so folding it back is a no-op for that topic. It can never
# delete anything, which is why it is the safe default. Pass --strict to demand
# that every shard already exist.
#
# A shard that EXISTS but is malformed or carries a foreign topic is always an
# error, in both modes: those cannot be repaired without guessing, and guessing
# here would corrupt the union.
declare -a SHARD_FILES=()
missing=0
for pair in "${SHARDS[@]}"; do
  topic="${pair%%:*}"; file="${pair#*:}"
  if [ ! -f "$file" ]; then
    if [ "$STRICT" = true ]; then
      echo "ERROR: shard missing for topic '$topic': $file" >&2
      echo "       Create the shards first: python scripts/split_entity_registry.py" >&2
      missing=1; continue
    fi
    echo "[merge_bb] shard for '$topic' absent — deriving it from the union (lossless)"
    dtmp="$(mktemp "$STATE/.tmp_derive_XXXXXX")"
    if jq --arg t "$topic" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
          [.entities[]? | select(.topic==$t)] as $e
          | {schema_version:2, topic:$t, last_merged_at:$now,
             metadata:{topics:($e|map(.topic)|unique|sort),
                       entity_types:($e|map(.entity_type)|unique|sort),
                       total_entities:($e|length),
                       entity_count_by_topic:($e|group_by(.topic)|map({key:.[0].topic,value:length})|from_entries),
                       entity_count_by_entity_type:($e|group_by(.entity_type)|map({key:.[0].entity_type,value:length})|from_entries)},
             entities:$e}' "$UNION" > "$dtmp" && jq empty "$dtmp" 2>/dev/null; then
      mv "$dtmp" "$file"
    else
      rm -f "$dtmp"
      echo "ERROR: could not derive the '$topic' shard from $UNION." >&2
      missing=1; continue
    fi
  fi
  if ! jq empty "$file" 2>/dev/null; then
    echo "ERROR: shard for topic '$topic' is not valid JSON: $file" >&2
    missing=1; continue
  fi
  # A shard must contain only its own topic — otherwise entity_keys could collide
  # across shards and the "disjoint sets" guarantee this script relies on is void.
  stray="$(jq --arg t "$topic" '[.entities[]? | select(.topic != $t)] | length' "$file")"
  if [ "${stray:-0}" -ne 0 ]; then
    echo "ERROR: shard $file contains $stray entit(y/ies) whose topic != '$topic':" >&2
    jq -r --arg t "$topic" '.entities[]? | select(.topic != $t) | "         topic=\(.topic // "null") name=\(.name // "?") key=\(.entity_key // "?")"' "$file" >&2
    echo "       This breaks the disjoint-shard invariant the parallel harvest relies on." >&2
    echo "       harvest_entities.sh drops foreign-topic rows at the lane boundary, so a shard" >&2
    echo "       carrying them was written by an older build or edited by hand." >&2
    echo "       Inspect the rows above, then remove them from the shard and re-run this fold." >&2
    missing=1; continue
  fi
  SHARD_FILES+=("$file")
done
[ "$missing" -eq 0 ] || exit 1

# --- report what the fold would change --------------------------------------
union_n="$(jq '.entities | length' "$UNION")"
shard_n="$(jq -s '[.[].entities[]?] | length' "${SHARD_FILES[@]}")"
echo "[merge_bb] union: $union_n entit(y/ies)   shards: $shard_n entit(y/ies)"
for pair in "${SHARDS[@]}"; do
  topic="${pair%%:*}"; file="${pair#*:}"
  n="$(jq '.entities | length' "$file")"
  v="$(jq '[.entities[]? | select(.description_source=="verified")] | length' "$file")"
  u="$(jq --arg t "$topic" '[.entities[]? | select(.topic==$t)] | length' "$UNION")"
  printf '[merge_bb]   %-7s shard=%4d (verified %4d)  union_has=%4d  delta=%+d\n' \
    "$topic" "$n" "$v" "$u" "$((n - u))"
done

if [ "$CHECK_MODE" = true ]; then
  echo "[merge_bb] --check: nothing written."
  exit 0
fi

# --- single-writer critical section ------------------------------------------
if ! lock_acquire "$LOCK" "merge_building_blocks"; then
  echo "ERROR: could not acquire the union-registry lock — another writer is active." >&2
  exit 1
fi
trap 'lock_release "$LOCK"' EXIT

TMP="$(mktemp "$STATE/.tmp_union_XXXXXX")"

# jq inputs: union first, then the four shards.
#   $shard_keys  = every entity_key present in a shard (shards win on conflict)
#   preserved    = union rows no shard carries (unknown topic, or shard shrank)
# entity_key is derived exactly as merge_entity_registry.sh derives it, so the
# two scripts can never disagree about identity.
if jq -s --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  def norm_name: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def ekey: .entity_key // ( (.topic // "unknown") + "|" + (.name | norm_name) );

  .[0] as $union |
  ( .[1:] | map(.entities // []) | add // [] ) as $shard_rows |
  ( $shard_rows | map(ekey) | unique ) as $shard_keys |
  ( ($union.entities // []) | map(select( (ekey) as $k | ($shard_keys | index($k)) == null )) ) as $preserved |
  ( $shard_rows + $preserved ) as $final |

  {
    schema_version: 2,
    last_merged_at: $now,
    metadata: {
      topics: ($final | map(.topic) | unique | sort),
      entity_types: ($final | map(.entity_type) | unique | sort),
      total_entities: ($final | length),
      entity_count_by_topic: ($final | group_by(.topic) | map({key: .[0].topic, value: length}) | from_entries),
      entity_count_by_entity_type: ($final | group_by(.entity_type) | map({key: .[0].entity_type, value: length}) | from_entries)
    },
    entities: $final
  }
' "$UNION" "${SHARD_FILES[@]}" > "$TMP"; then
  :
else
  rm -f "$TMP"
  echo "ERROR: merge_building_blocks jq step failed; $UNION left unchanged." >&2
  exit 1
fi

# Never install output we have not validated — the whole point of the temp file.
if ! jq empty "$TMP" 2>/dev/null; then
  rm -f "$TMP"
  echo "ERROR: merge produced invalid JSON; $UNION left unchanged." >&2
  exit 1
fi

final_n="$(jq '.entities | length' "$TMP")"
preserved_n=$(( final_n - shard_n ))
mv "$TMP" "$UNION"

echo "[merge_bb] union rebuilt: $final_n entit(y/ies) ($shard_n from shards, $preserved_n preserved from the previous union)"
if [ "$preserved_n" -gt 0 ]; then
  echo "[merge_bb] NOTE: $preserved_n union row(s) were not present in any shard and were kept, not deleted."
  jq -r '[.entities[] | select(.topic as $t | ["agent","mcp","prompt","skill"] | index($t) | not)] | length as $n
         | if $n > 0 then "[merge_bb] of those, \($n) carry a topic outside the four shard topics." else empty end' "$UNION"
fi

# ---------------------------------------------------------------------------
# Fold the per-topic ledger shards back into the union visited-URL ledger.
#
# Without this the shards are the only record of what each lane crawled, and
# they are transient/gitignored — so the crawl history of a whole run would be
# lost the moment a shard is cleaned up, and the next run would re-fetch
# hundreds of already-visited pages. The union ledger stays the committed,
# persistent truth; the shards are working copies seeded from it.
#
# Merge rule per URL: union all rows, then for each url keep the STRONGEST
# knowledge — extraction flags are latched true (a page that was extracted can
# never become un-extracted), id lists are unioned, crawl_count takes the max,
# and last_crawled_at takes the later timestamp. This is order-independent and
# idempotent, which matters because lanes finish in an arbitrary order.
# ---------------------------------------------------------------------------
declare -a LEDGER_SHARDS=()
for pair in "${SHARDS[@]}"; do
  topic="${pair%%:*}"
  ls_path="$STATE/visited_url_ledger_${topic}.json"
  if [ -f "$ls_path" ]; then
    if jq empty "$ls_path" 2>/dev/null; then
      LEDGER_SHARDS+=("$ls_path")
    else
      echo "[merge_bb] WARNING: ledger shard for '$topic' is not valid JSON — skipped, NOT folded: $ls_path" >&2
    fi
  fi
done

if [ "${#LEDGER_SHARDS[@]}" -eq 0 ]; then
  echo "[merge_bb] no ledger shards present — union ledger left unchanged."
  exit 0
fi

UNION_LEDGER="$STATE/visited_url_ledger.json"
[ -f "$UNION_LEDGER" ] || echo '{"ledger":[]}' > "$UNION_LEDGER"
if ! jq empty "$UNION_LEDGER" 2>/dev/null; then
  echo "ERROR: $UNION_LEDGER is not valid JSON — ledger fold skipped (entity union already written)." >&2
  exit 1
fi

led_before="$(jq '.ledger | length' "$UNION_LEDGER")"
LTMP="$(mktemp "$STATE/.tmp_ledger_union_XXXXXX")"
if jq -s '
  def latest(a; b): if (a // "") >= (b // "") then a else b end;
  [ .[].ledger[]? ]
  | group_by(.url)
  | map(
      reduce .[] as $r ({};
        . + $r + {
          url: $r.url,
          crawl_count:      ( [ (.crawl_count // 0), ($r.crawl_count // 0) ] | max ),
          first_crawled_at: ( if (.first_crawled_at // null) == null then $r.first_crawled_at
                              elif ($r.first_crawled_at // null) == null then .first_crawled_at
                              elif .first_crawled_at <= $r.first_crawled_at then .first_crawled_at
                              else $r.first_crawled_at end ),
          last_crawled_at:  latest(.last_crawled_at; $r.last_crawled_at),
          extracted:        ( (.extracted // false)        or ($r.extracted // false) ),
          entity_extracted: ( (.entity_extracted // false) or ($r.entity_extracted // false) ),
          case_ids:         ( ((.case_ids   // []) + ($r.case_ids   // [])) | unique ),
          entity_ids:       ( ((.entity_ids // []) + ($r.entity_ids // [])) | unique )
        })
    )
  | {ledger: .}
' "$UNION_LEDGER" "${LEDGER_SHARDS[@]}" > "$LTMP" && jq empty "$LTMP" 2>/dev/null; then
  led_after="$(jq '.ledger | length' "$LTMP")"
  mv "$LTMP" "$UNION_LEDGER"
  echo "[merge_bb] ledger union rebuilt from ${#LEDGER_SHARDS[@]} shard(s): $led_before -> $led_after row(s)"
else
  rm -f "$LTMP"
  echo "ERROR: ledger fold failed; $UNION_LEDGER left unchanged (the entity union WAS written)." >&2
  exit 1
fi
exit 0
