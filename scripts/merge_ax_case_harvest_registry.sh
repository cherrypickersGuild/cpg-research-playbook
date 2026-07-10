#!/usr/bin/env bash
# merge_ax_case_harvest_registry.sh — folds a batch of newly-extracted AX cases
# (ax_case_harvest_extractor.md's per-run output) into the persistent master
# registry at state/ax_case_harvest_registry.json. Sibling to
# merge_entity_registry.sh, same technique — built with that script's
# found_via/conflicting_evidence_log lessons already applied from the start
# (see docs/ax_case_strategy.md and commit b6ee7a7 for the drift this avoids):
# no raw found_via is ever persisted at the top level, and
# conflicting_evidence_log is always present, defaulting to [].
#
# Dedup key: case_key = normalized(company) + "|" + normalized(ai_system_or_tool)
#   + "|" + normalized(workflow_after) — see docs/ax_case_strategy.md §4.
#   company/ai_system_or_tool/workflow_after are therefore identical (modulo
#   normalization) between two records that share a case_key by construction;
#   only the remaining fields can meaningfully differ between corroborating
#   sources.
#
# On a match: increment corroboration_count, swap in the richer evidence
# bundle (verification_status + evidence_quote + source_url/title/domain)
# when the incoming case is more verified than the existing one — verified
# beats snippet-only, never the reverse — backfill industry/workflow_before/
# measurable_kpi/transformation_date/publication_date only when the existing
# value was "unknown", and keep the higher confidence. A conflicting
# kpi_value is NEVER silently overwritten — it's logged to
# conflicting_evidence_log[] for a human to resolve, the same pattern
# merge_case_db.sh uses for transformation_date and merge_entity_registry.sh
# uses for entity_type. transformation_date and publication_date are always
# distinct keys, even backfilled independently of each other — never infer
# one from the other.
#
# Isolated from the rest of the project: never touches state/entity_registry.json,
# state/ax_case_db.json, or state/visited_url_ledger.json.
#
#   Usage: bash merge_ax_case_harvest_registry.sh <new_case_batch.json> [master_registry.json]
#   (master_registry.json defaults to state/ax_case_harvest_registry.json; created if absent)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEW="${1:?Usage: bash merge_ax_case_harvest_registry.sh <new_case_batch.json> [master_registry.json]}"
MASTER="${2:-$ROOT/state/ax_case_harvest_registry.json}"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found."; exit 1; }
[ -s "$NEW" ] || { echo "ERROR: $NEW not found or empty."; exit 1; }

mkdir -p "$(dirname "$MASTER")"
[ -f "$MASTER" ] || echo '{"schema_version":1,"last_merged_at":null,"cases":[]}' > "$MASTER"

TODAY="$(date -u +%Y-%m-%d)"
TMP="$(mktemp)"

# Run the transform under `if` so a jq failure propagates instead of being
# swallowed: the old `jq ... > "$TMP" && mv` idiom left jq as the LHS of `&&`,
# which `set -e` does not treat as fatal — a failed merge skipped the `mv` but
# the script ran on and exited 0, falsely reporting success while the master
# was silently left unchanged. Now: jq fails -> master untouched, exit 1.
if jq -s --arg today "$TODAY" '
  def norm: (. // "unknown") | ascii_downcase | gsub("[[:space:]]+";" ") | sub("^ +";"") | sub(" +$";"");
  def case_key: .case_key // ( (.company | norm) + "|" + (.ai_system_or_tool | norm) + "|" + (.workflow_after | norm) );
  def status_rank(s): if s == "verified" then 2 elif s == "snippet-only" then 1 else 0 end;

  .[0] as $master | .[1] as $incoming |

  (($master.cases // []) | map(. + {case_key: case_key}) | INDEX(.case_key)) as $by_key |
  (($incoming.cases // []) | map(. + {case_key: case_key})) as $new |

  (reduce $new[] as $c ($by_key;
    if has($c.case_key) then
      (.[$c.case_key]) as $ex |
      (($ex.corroboration_count // 1) + 1) as $corrob |
      ( if status_rank($c.verification_status // "unknown") > status_rank($ex.verification_status // "unknown")
        then {
          verification_status: $c.verification_status,
          evidence_quote: $c.evidence_quote,
          source_url: $c.source_url,
          source_title: ($c.source_title // "unknown"),
          source_domain: ($c.source_domain // "unknown")
        }
        else {
          verification_status: $ex.verification_status,
          evidence_quote: $ex.evidence_quote,
          source_url: $ex.source_url,
          source_title: $ex.source_title,
          source_domain: $ex.source_domain
        }
        end
      ) as $best_evidence |
      ( {
          industry: (
            if ($ex.industry // "unknown") != "unknown" then $ex.industry
            else ($c.industry // "unknown") end
          ),
          workflow_before: (
            if ($ex.workflow_before // "unknown") != "unknown" then $ex.workflow_before
            else ($c.workflow_before // "unknown") end
          ),
          measurable_kpi: (
            if ($ex.measurable_kpi // "unknown") != "unknown" then $ex.measurable_kpi
            else ($c.measurable_kpi // "unknown") end
          ),
          transformation_date: (
            if ($ex.transformation_date // "unknown") != "unknown" then $ex.transformation_date
            else ($c.transformation_date // "unknown") end
          ),
          publication_date: (
            if ($ex.publication_date // "unknown") != "unknown" then $ex.publication_date
            else ($c.publication_date // "unknown") end
          )
        }
      ) as $backfill |
      ( ($ex.kpi_value // null) != null and ($c.kpi_value // null) != null
        and ($ex.kpi_value // null) != ($c.kpi_value // null)
      ) as $kpi_conflict |
      (($ex.conflicting_evidence_log // []) +
        (if $kpi_conflict then
          [{"noted_at": $today, "field": "kpi_value",
            "existing": $ex.kpi_value, "incoming": $c.kpi_value}]
         else [] end)
      ) as $conflict_log |
      .[$c.case_key] = ($ex + $best_evidence + $backfill + {
        kpi_value: $ex.kpi_value,
        confidence: ([($ex.confidence // 0), ($c.confidence // 0)] | max),
        corroboration_count: $corrob,
        conflicting_evidence_log: $conflict_log,
        discovery: {
          first_seen_at: ($ex.discovery.first_seen_at // $today),
          last_corroborated_at: $today,
          found_via: (($ex.discovery.found_via // []) + [($c.found_via // {})])
        }
      })
    else
      .[$c.case_key] = (($c | del(.found_via)) + {
        transformation_date: ($c.transformation_date // "unknown"),
        publication_date: ($c.publication_date // "unknown"),
        corroboration_count: ($c.corroboration_count // 1),
        conflicting_evidence_log: [],
        discovery: {
          first_seen_at: $today,
          last_corroborated_at: $today,
          found_via: [($c.found_via // {})]
        }
      })
    end
  )) as $merged_by_key |

  # Normalize transformation_date/publication_date onto every case in the registry, not just ones
  # touched by the incoming batch this run — otherwise a case that predates this schema addition
  # and is never re-corroborated would be missing the keys entirely instead of carrying an
  # explicit "unknown", breaking "always present" schema consistency for older rows.
  ( $merged_by_key | to_entries | map(.value
      | if has("transformation_date") then . else . + {transformation_date: "unknown"} end
      | if has("publication_date") then . else . + {publication_date: "unknown"} end
    ) ) as $final_cases |

  {
    schema_version: 1,
    last_merged_at: $today,
    cases: $final_cases
  }
' "$MASTER" "$NEW" > "$TMP"; then
  mv "$TMP" "$MASTER"
else
  rm -f "$TMP"
  echo "ERROR: merge_ax_case_harvest_registry jq step failed; $MASTER left unchanged (not overwritten)." >&2
  exit 1
fi

N_NEW=$(jq '.cases | length' "$NEW")
N_MASTER=$(jq '.cases | length' "$MASTER")
N_CONFLICTS=$(jq '[.cases[] | select((.conflicting_evidence_log // []) | length > 0)] | length' "$MASTER")
echo "[merge] folded $N_NEW case(s) from $NEW -> master now has $N_MASTER case(s) in $MASTER"
[ "${N_CONFLICTS:-0}" -gt 0 ] && echo "[merge] WARNING: $N_CONFLICTS case(s) have unresolved conflicting_evidence_log entries — review before relying on kpi_value."
exit 0
