#!/usr/bin/env bash
# merge_matrix.sh — fold every matrix cell file into one readable view at
# state/matrix/matrix_union.json.
#
# The cell files are authoritative; this is a DERIVED convenience artifact, the
# same relationship BuildingBlocks shards have with entity_registry.json. Written
# by a single process under a lock, atomically, after the lanes are done.
#
# Identity across cells is (category, topic, name) — NOT the entity_key that
# merge_entity_registry.sh uses inside a cell, which is only `topic|name`. Two
# cells sharing a topic legitimately hold the same tool under the same
# entity_key; they are different findings ("this tool matters for healthcare
# agents" and "…for finance agents") and collapsing them on entity_key alone
# would silently delete one of the two.
#
#   Usage: bash scripts/merge_matrix.sh [--check]
#
# Exit 0: union written (or --check). Exit 1: missing manifest, an invalid cell
#         file, lock held, or invalid output (union left untouched).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/lockdir.sh"

CHECK_MODE=false
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_MODE=true ;;
    *) echo "Usage: bash scripts/merge_matrix.sh [--check]" >&2; exit 1 ;;
  esac
done
command -v jq >/dev/null 2>&1 || { echo "ERROR: 'jq' not found." >&2; exit 1; }

STATE="${STATE_DIR:-$ROOT/state}"
MDIR="$STATE/matrix"
MANIFEST="$MDIR/manifest.json"
UNION="$MDIR/matrix_union.json"
LOCK="$STATE/locks/matrix_union.lock"

[ -f "$MANIFEST" ] || { echo "ERROR: no manifest at $MANIFEST — nothing to fold." >&2; exit 1; }
jq empty "$MANIFEST" 2>/dev/null || { echo "ERROR: $MANIFEST is not valid JSON." >&2; exit 1; }

declare -a FILES=()
total=0; present=0; missing=0
# \r in IFS: this platform's jq emits CRLF, so `read` would otherwise leave a
# trailing carriage return in the last field. See the same note in run_matrix.sh.
while IFS=$'\t\r' read -r cid hf cat top; do
  [ -z "${cid:-}" ] && continue
  total=$((total+1))
  f="$MDIR/$hf"
  if [ ! -f "$f" ]; then
    # A cell that was never harvested is normal (skipped, or not requested yet).
    # It contributes nothing; it is not an error.
    missing=$((missing+1)); continue
  fi
  if ! jq empty "$f" 2>/dev/null; then
    echo "ERROR: cell file is not valid JSON: $f" >&2
    exit 1
  fi
  n="$(jq '[.entities[]?] | length' "$f")"
  v="$(jq '[.entities[]? | select(.description_source=="verified")] | length' "$f")"
  printf '[merge_mx] %-22s %-34s %4d entit(y/ies) (%d verified)\n' "$cid" "$cat x $top" "$n" "$v"
  FILES+=("$f"); present=$((present+1))
done < <(jq -r '.cells[] | [.cell_id,.harvest_file,.category,.topic] | @tsv' "$MANIFEST")

echo "[merge_mx] $present/$total cell file(s) present ($missing not harvested yet)"

if [ "$CHECK_MODE" = true ]; then
  echo "[merge_mx] --check: nothing written."
  exit 0
fi
if [ "${#FILES[@]}" -eq 0 ]; then
  echo "[merge_mx] no cell files to fold — union left untouched."
  exit 0
fi

if ! lock_acquire "$LOCK" "merge_matrix"; then
  echo "ERROR: could not acquire the matrix-union lock — another writer is active." >&2
  exit 1
fi
trap 'lock_release "$LOCK"' EXIT

TMP="$(mktemp "$MDIR/.tmp_mxunion_XXXXXX")"
if jq -s --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  def norm: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def mkey: ((.category // "unknown") | norm) + "|" + ((.topic // "unknown") | norm) + "|" + ((.name // "unknown") | norm);

  [ .[] | (.entities // [])[] ]
  | map(. + {matrix_key: mkey})
  | (INDEX(.matrix_key) | to_entries | map(.value)) as $final |
  {
    schema_version: 1,
    generated_at: $now,
    metadata: {
      total_entities: ($final | length),
      verified_entities: ([$final[] | select(.description_source=="verified")] | length),
      by_category: ($final | group_by(.category) | map({key: (.[0].category // "unknown"), value: length}) | from_entries),
      by_topic:    ($final | group_by(.topic)    | map({key: (.[0].topic    // "unknown"), value: length}) | from_entries)
    },
    entities: $final
  }
' "${FILES[@]}" > "$TMP" && jq empty "$TMP" 2>/dev/null; then
  n="$(jq '.entities | length' "$TMP")"
  v="$(jq '.metadata.verified_entities' "$TMP")"
  mv "$TMP" "$UNION"
  echo "[merge_mx] union written: $n entit(y/ies) ($v verified) -> $UNION"
else
  rm -f "$TMP"
  echo "ERROR: matrix fold produced invalid JSON; $UNION left unchanged." >&2
  exit 1
fi
exit 0
