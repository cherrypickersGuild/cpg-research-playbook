#!/usr/bin/env bash
# merge_entity_registry.sh — folds a batch of newly-extracted entities (1G's
# per-run output) into the persistent master registry at
# state/entity_registry.json. Sibling to merge_case_db.sh, same technique.
#
# Dedup key: entity_key if the input already carries one, else derived as
#   topic | lowercase(name)
#
# On a match: increment corroboration_count, keep the richer description
# (verified beats snippet-only; never downgrade an already-verified
# description back to snippet-only), union related_topics, stamp
# discovery.last_corroborated_at. A conflicting entity_type is NEVER
# silently overwritten — it's logged to conflicting_evidence_log[] for a
# human to resolve, same as merge_case_db.sh does for transformation_date.
#
#   Usage: bash merge_entity_registry.sh <new_entity_batch.json> [master_registry.json]
#   (master_registry.json defaults to state/entity_registry.json; created if absent)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEW="${1:?Usage: bash merge_entity_registry.sh <new_entity_batch.json> [master_registry.json]}"
MASTER="${2:-$ROOT/state/entity_registry.json}"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found."; exit 1; }
[ -s "$NEW" ] || { echo "ERROR: $NEW not found or empty."; exit 1; }

mkdir -p "$(dirname "$MASTER")"
[ -f "$MASTER" ] || echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$MASTER"

TODAY="$(date -u +%Y-%m-%d)"
TMP="$(mktemp)"

jq -s --arg today "$TODAY" '
  def norm_name: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def entity_key: .entity_key // ( (.topic // "unknown") + "|" + (.name | norm_name) );
  def desc_rank(d): if d == "verified" then 2 elif d == "snippet-only" then 1 else 0 end;

  .[0] as $master | .[1] as $incoming |

  (($master.entities // []) | map(. + {entity_key: entity_key}) | INDEX(.entity_key)) as $by_key |
  (($incoming.entities // []) | map(. + {entity_key: entity_key})) as $new |

  (reduce $new[] as $e ($by_key;
    if has($e.entity_key) then
      (.[$e.entity_key]) as $ex |
      (($ex.corroboration_count // 1) + 1) as $corrob |
      ( (($ex.related_topics // []) + ($e.related_topics // [])) | unique ) as $topics |
      ( if desc_rank($e.description_source // "unknown") > desc_rank($ex.description_source // "unknown")
        then { description: $e.description, description_source: $e.description_source }
        else { description: $ex.description, description_source: $ex.description_source }
        end
        + {
            maintainer_or_vendor: (
              if ($ex.maintainer_or_vendor // "unknown") != "unknown" then $ex.maintainer_or_vendor
              else ($e.maintainer_or_vendor // "unknown") end
            ),
            freshness_signal: (
              if ($ex.freshness_signal // "unknown") != "unknown" then $ex.freshness_signal
              else ($e.freshness_signal // "unknown") end
            )
          }
      ) as $best_desc |
      ( ($ex.entity_type // null) != null and ($e.entity_type // null) != null
        and ($ex.entity_type // null) != ($e.entity_type // null)
      ) as $type_conflict |
      (($ex.conflicting_evidence_log // []) +
        (if $type_conflict then
          [{"noted_at": $today, "field": "entity_type",
            "existing": $ex.entity_type, "incoming": $e.entity_type}]
         else [] end)
      ) as $conflict_log |
      .[$e.entity_key] = ($ex + $best_desc + {
        corroboration_count: $corrob,
        related_topics: $topics,
        conflicting_evidence_log: $conflict_log,
        discovery: {
          first_seen_at: ($ex.discovery.first_seen_at // $today),
          last_corroborated_at: $today,
          found_via: (($ex.discovery.found_via // []) + [($e.found_via // {})])
        }
      })
    else
      .[$e.entity_key] = ($e + {
        corroboration_count: ($e.corroboration_count // 1),
        discovery: {
          first_seen_at: $today,
          last_corroborated_at: $today,
          found_via: [($e.found_via // {})]
        }
      })
    end
  )) as $merged_by_key |

  {
    schema_version: 1,
    last_merged_at: $today,
    entities: ($merged_by_key | to_entries | map(.value))
  }
' "$MASTER" "$NEW" > "$TMP" && mv "$TMP" "$MASTER"

N_NEW=$(jq '.entities | length' "$NEW")
N_MASTER=$(jq '.entities | length' "$MASTER")
N_CONFLICTS=$(jq '[.entities[] | select((.conflicting_evidence_log // []) | length > 0)] | length' "$MASTER")
echo "[merge] folded $N_NEW entit(y/ies) from $NEW -> master now has $N_MASTER entit(y/ies) in $MASTER"
[ "${N_CONFLICTS:-0}" -gt 0 ] && echo "[merge] WARNING: $N_CONFLICTS entit(y/ies) have unresolved conflicting_evidence_log entries — review before relying on entity_type."
exit 0
