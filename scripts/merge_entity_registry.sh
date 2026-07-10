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
# discovery.last_corroborated_at. A conflicting entity_type OR a conflicting
# target_url is NEVER silently overwritten — both are logged to
# conflicting_evidence_log[] for a human to resolve, same as merge_case_db.sh
# does for transformation_date. A changed official site (target_url mismatch)
# is meaningful signal, not noise. source_url is always pass-through: a
# different citing page for the same entity is expected (corroboration), not a
# conflict.
#
# The registry's top-level metadata block (topics, entity_types,
# total_entities, entity_count_by_topic, entity_count_by_entity_type) is
# fully recomputed from the final entities list on every merge, so it can
# never drift from the actual records. schema_version is 2 (source_url/
# target_url schema); last_merged_at is a full UTC timestamp.
#
# github_stars is a live number, not identity data like target_url — it's
# expected to change (usually grow) between runs, so a newer measurement is
# never a "conflict": the incoming value simply wins whenever it is non-null,
# else the existing value (possibly itself null) is kept. This script also
# enforces the "no stars from non-GitHub pages" rule structurally, not just
# by trusting 1G's instruction-following: any incoming entity whose
# target_url is not a github.com/<owner>/<repo> root has github_stars forced
# to null before merging, regardless of what the batch supplied.
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
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP="$(mktemp)"

# The whole transform runs under `if` so a jq failure propagates instead of
# being swallowed: the old `jq ... > "$TMP" && mv` idiom left jq as the LHS of
# `&&`, which `set -e` does not treat as fatal — so a failed merge (e.g. a
# metadata `from_entries` on an entity missing entity_type) skipped the `mv`
# but the script still ran on and exited 0, falsely reporting success while the
# master was silently left unchanged. Now: jq fails -> master untouched, exit 1.
if jq -s --arg today "$TODAY" --arg now "$NOW" '
  def norm_name: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def entity_key: .entity_key // ( (.topic // "unknown") + "|" + (.name | norm_name) );
  def desc_rank(d): if d == "verified" then 2 elif d == "snippet-only" then 1 else 0 end;
  def is_github_repo_root: (.target_url // "") | test("^https?://(www\\.)?github\\.com/[^/]+/[^/]+/?$"; "i");
  def normalize_stars: if is_github_repo_root then (.github_stars // null) else null end;

  .[0] as $master | .[1] as $incoming |

  (($master.entities // []) | map(. + {entity_key: entity_key}) | INDEX(.entity_key)) as $by_key |
  (($incoming.entities // []) | map(. + {entity_key: entity_key} + {github_stars: normalize_stars})) as $new |

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
      # target_url resolution: if existing is "unknown"/missing and incoming carries a real
      # (non-"unknown") target_url, backfill from incoming — same one-way backfill rule as
      # maintainer_or_vendor. Skipped when $target_conflict (handled below) since a real-vs-real
      # mismatch is logged, not silently picked. Without this backfill the record could end up
      # in the impossible state of description_source:"verified" paired with target_url:"unknown"
      # — the 1G contract is that verified requires target_url to have been fetched.
      ( if ($ex.target_url // "unknown") == "unknown" and ($e.target_url // "unknown") != "unknown"
        then { target_url: $e.target_url }
        else {} end
      ) as $target_backfill |
      ( ($ex.entity_type // null) != null and ($e.entity_type // null) != null
        and ($ex.entity_type // null) != ($e.entity_type // null)
      ) as $type_conflict |
      ( ($ex.target_url // null) != null and ($ex.target_url // null) != "unknown"
        and ($e.target_url // null) != null and ($e.target_url // null) != "unknown"
        and ($ex.target_url // null) != ($e.target_url // null)
      ) as $target_conflict |
      # github_stars: latest non-null measurement always wins — not identity data, so unlike
      # target_url this is never a "conflict" to log, just a freshness update (or a no-op if this
      # batch did not re-measure it, in which case the existing value — possibly itself null — is
      # kept rather than being blanked out).
      ( if ($e.github_stars // null) != null then $e.github_stars else ($ex.github_stars // null) end
      ) as $stars_update |
      (($ex.conflicting_evidence_log // []) +
        (if $type_conflict then
          [{"noted_at": $today, "field": "entity_type",
            "existing": $ex.entity_type, "incoming": $e.entity_type}]
         else [] end) +
        (if $target_conflict then
          [{"noted_at": $today, "field": "target_url",
            "existing": $ex.target_url, "incoming": $e.target_url}]
         else [] end)
      ) as $conflict_log |
      .[$e.entity_key] = ($ex + $best_desc + $target_backfill + {
        github_stars: $stars_update,
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
      .[$e.entity_key] = (($e | del(.found_via)) + {
        github_stars: ($e.github_stars // null),
        corroboration_count: ($e.corroboration_count // 1),
        conflicting_evidence_log: [],
        discovery: {
          first_seen_at: $today,
          last_corroborated_at: $today,
          found_via: [($e.found_via // {})]
        }
      })
    end
  )) as $merged_by_key |

  # del(.url) is defensive cleanup for any stray legacy field; the github_stars normalization
  # covers every entity in the registry, not just ones touched by the incoming batch this run —
  # otherwise an entity untouched by $new (a pure pass-through from $by_key) could be missing the
  # key entirely rather than carrying an explicit null, breaking "always present" schema
  # consistency for older rows that predate this field.
  ( $merged_by_key | to_entries | map(.value | del(.url) | if has("github_stars") then . else . + {github_stars: null} end) ) as $final_entities |

  {
    schema_version: 2,
    last_merged_at: $now,
    metadata: {
      topics: ($final_entities | map(.topic) | unique | sort),
      entity_types: ($final_entities | map(.entity_type) | unique | sort),
      total_entities: ($final_entities | length),
      entity_count_by_topic: ($final_entities | group_by(.topic) | map({key: .[0].topic, value: length}) | from_entries),
      entity_count_by_entity_type: ($final_entities | group_by(.entity_type) | map({key: .[0].entity_type, value: length}) | from_entries)
    },
    entities: $final_entities
  }
' "$MASTER" "$NEW" > "$TMP"; then
  mv "$TMP" "$MASTER"
else
  rm -f "$TMP"
  echo "ERROR: merge_entity_registry jq step failed; $MASTER left unchanged (not overwritten)." >&2
  exit 1
fi

N_NEW=$(jq '.entities | length' "$NEW")
N_MASTER=$(jq '.entities | length' "$MASTER")
N_CONFLICTS=$(jq '[.entities[] | select((.conflicting_evidence_log // []) | length > 0)] | length' "$MASTER")
echo "[merge] folded $N_NEW entit(y/ies) from $NEW -> master now has $N_MASTER entit(y/ies) in $MASTER"
[ "${N_CONFLICTS:-0}" -gt 0 ] && echo "[merge] WARNING: $N_CONFLICTS entit(y/ies) have unresolved conflicting_evidence_log entries — review before relying on entity_type."
exit 0
