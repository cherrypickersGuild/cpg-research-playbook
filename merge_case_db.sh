#!/usr/bin/env bash
# merge_case_db.sh — folds a batch of newly-extracted cases (1C's per-run
# output) into the persistent master corpus at state/ax_case_db.json.
#
# Dedup key: case_key if the input already carries one, else derived as
#   lowercase(company) | lowercase(ax_pattern) | transformation_date[0:7]
# (company x pattern x year-month) — the same identity 1C's own rule already
# uses ("one case per company x workflow x period"); this just applies it
# ACROSS runs instead of only within one.
#
# On a match: merge sources[] (dedup by url), increment corroboration_count,
# keep the higher confidence, stamp discovery.last_corroborated_at. A
# conflicting transformation_date is NEVER silently overwritten — it's logged
# to conflicting_evidence_log[] for a human to resolve.
#
#   Usage: bash merge_case_db.sh <new_case_db.json> [master_db.json]
#   (master_db.json defaults to state/ax_case_db.json; created if absent)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEW="${1:?Usage: bash merge_case_db.sh <new_case_db.json> [master_db.json]}"
MASTER="${2:-$ROOT/state/ax_case_db.json}"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found."; exit 1; }
[ -s "$NEW" ] || { echo "ERROR: $NEW not found or empty."; exit 1; }

mkdir -p "$(dirname "$MASTER")"
[ -f "$MASTER" ] || echo '{"schema_version":1,"last_merged_at":null,"cases":[]}' > "$MASTER"

TODAY="$(date -u +%Y-%m-%d)"
TMP="$(mktemp)"

jq -s --arg today "$TODAY" '
  def norm_company: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def case_key: .case_key // (
    (.company | norm_company) + "|" +
    ((.ax_pattern // "unknown") | ascii_downcase) + "|" +
    ((.transformation_date // "unknown") | tostring | .[0:7])
  );

  .[0] as $master | .[1] as $incoming |

  (($master.cases // []) | map(. + {case_key: case_key}) | INDEX(.case_key)) as $by_key |
  (($incoming.cases // []) | map(. + {case_key: case_key})) as $new |

  (reduce $new[] as $c ($by_key;
    if has($c.case_key) then
      (.[$c.case_key]) as $ex |
      (($ex.sources // []) + ($c.sources // []) | unique_by(.url)) as $mergedsrc |
      (($ex.corroboration_count // 1) + 1) as $corrob |
      ( ($ex.transformation_date // null) != null and ($c.transformation_date // null) != null
        and ($ex.transformation_date // null) != ($c.transformation_date // null)
      ) as $date_conflict |
      (($ex.conflicting_evidence_log // []) +
        (if $date_conflict then
          [{"noted_at": $today, "field": "transformation_date",
            "existing": $ex.transformation_date, "incoming": $c.transformation_date}]
         else [] end)
      ) as $conflict_log |
      .[$c.case_key] = ($ex + {
        sources: $mergedsrc,
        corroboration_count: $corrob,
        confidence: ([($ex.confidence // 0), ($c.confidence // 0)] | max),
        conflicting_evidence_log: $conflict_log,
        discovery: {
          first_seen_at: ($ex.discovery.first_seen_at // $today),
          last_corroborated_at: $today,
          found_via: (($ex.discovery.found_via // []) + ($c.discovery.found_via // [{}]))
        }
      })
    else
      .[$c.case_key] = ($c + {
        corroboration_count: ($c.corroboration_count // 1),
        discovery: {
          first_seen_at: $today,
          last_corroborated_at: $today,
          found_via: ($c.discovery.found_via // [{}])
        }
      })
    end
  )) as $merged_by_key |

  {
    schema_version: 1,
    last_merged_at: $today,
    cases: ($merged_by_key | to_entries | map(.value))
  }
' "$MASTER" "$NEW" > "$TMP" && mv "$TMP" "$MASTER"

N_NEW=$(jq '.cases | length' "$NEW")
N_MASTER=$(jq '.cases | length' "$MASTER")
N_CONFLICTS=$(jq '[.cases[] | select((.conflicting_evidence_log // []) | length > 0)] | length' "$MASTER")
echo "[merge] folded $N_NEW case(s) from $NEW -> master now has $N_MASTER case(s) in $MASTER"
[ "${N_CONFLICTS:-0}" -gt 0 ] && echo "[merge] WARNING: $N_CONFLICTS case(s) have unresolved conflicting_evidence_log entries — review before using in a deck."
exit 0
