#!/usr/bin/env bash
# test_ax_case_harvest_dates.sh — deterministic functional test for the
# ax_case_harvest_registry.json's transformation_date/publication_date fields
# (see agents/stage1/ax_case_harvest_extractor.md and
# scripts/merge_ax_case_harvest_registry.sh).
#
# Exercises scripts/merge_ax_case_harvest_registry.sh only, against fixtures
# built in a temp dir. No live `claude -p` calls, no writes to any real
# state/*.json file.
#
#   Usage: bash tests/test_ax_case_harvest_dates.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MERGE="$ROOT/scripts/merge_ax_case_harvest_registry.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

PASS=0
FAIL=0

ok() { PASS=$((PASS+1)); echo "  ok - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then ok "$desc"; else bad "$desc (expected [$expected], got [$actual])"; fi
}

# ---------------------------------------------------------------------------
echo "[test 1] new case gets both date fields from the incoming batch"
MASTER="$TMPDIR/t1_master.json"
NEW="$TMPDIR/t1_new.json"
echo '{"schema_version":1,"last_merged_at":null,"cases":[]}' > "$MASTER"
cat > "$NEW" <<'EOF'
{"cases":[
  {"case_id":"case-t-0001","company":"Acme Corp","industry":"insurance",
   "workflow_before":"manual","workflow_after":"automated","ai_system_or_tool":"CopilotForClaims",
   "measurable_kpi":"turnaround time","kpi_value":"3 days -> same-day","evidence_quote":"q",
   "source_url":"https://example.com/acme","source_title":"t","source_domain":"example.com",
   "transformation_date":"2026-02","publication_date":"2026-03-15",
   "confidence":0.7,"verification_status":"verified"}
]}
EOF
bash "$MERGE" "$NEW" "$MASTER" > /dev/null
assert_eq "transformation_date set on new case" "2026-02" \
  "$(jq -r '.cases[0].transformation_date' "$MASTER")"
assert_eq "publication_date set on new case" "2026-03-15" \
  "$(jq -r '.cases[0].publication_date' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 2] an existing real transformation_date is never overwritten by a corroborating batch"
NEW2="$TMPDIR/t2_new.json"
cat > "$NEW2" <<'EOF'
{"cases":[
  {"case_id":"case-t-9001","company":"Acme Corp","industry":"insurance",
   "workflow_before":"manual","workflow_after":"automated","ai_system_or_tool":"CopilotForClaims",
   "measurable_kpi":"turnaround time","kpi_value":"3 days -> same-day","evidence_quote":"q2",
   "source_url":"https://example.com/acme-2","source_title":"t2","source_domain":"example.com",
   "transformation_date":"2099-99","publication_date":"2026-04-01",
   "confidence":0.6,"verification_status":"snippet-only"}
]}
EOF
bash "$MERGE" "$NEW2" "$MASTER" > /dev/null
assert_eq "transformation_date unchanged (real value wins over incoming)" "2026-02" \
  "$(jq -r '.cases[0].transformation_date' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 3] an existing unknown publication_date is backfilled from a corroborating batch"
MASTER3="$TMPDIR/t3_master.json"
cat > "$MASTER3" <<'EOF'
{"schema_version":1,"last_merged_at":null,"cases":[
  {"case_id":"case-t-0002","company":"Beta Inc","industry":"retail",
   "workflow_before":"manual","workflow_after":"automated","ai_system_or_tool":"BetaBot",
   "measurable_kpi":"cost","kpi_value":"-20%","evidence_quote":"q",
   "source_url":"https://example.com/beta","source_title":"t","source_domain":"example.com",
   "transformation_date":"2026-05","publication_date":"unknown",
   "confidence":0.8,"verification_status":"verified",
   "case_key":"beta inc|betabot|automated","corroboration_count":1,
   "discovery":{"first_seen_at":"2026-07-01","last_corroborated_at":"2026-07-01","found_via":[{}]},
   "conflicting_evidence_log":[]}
]}
EOF
NEW3="$TMPDIR/t3_new.json"
cat > "$NEW3" <<'EOF'
{"cases":[
  {"case_id":"case-t-9002","company":"Beta Inc","industry":"retail",
   "workflow_before":"manual","workflow_after":"automated","ai_system_or_tool":"BetaBot",
   "measurable_kpi":"cost","kpi_value":"-20%","evidence_quote":"q2",
   "source_url":"https://example.com/beta-2","source_title":"t2","source_domain":"example.com",
   "transformation_date":"2026-05","publication_date":"2026-06-01",
   "confidence":0.75,"verification_status":"verified"}
]}
EOF
bash "$MERGE" "$NEW3" "$MASTER3" > /dev/null
assert_eq "publication_date backfilled from unknown" "2026-06-01" \
  "$(jq -r '.cases[0].publication_date' "$MASTER3")"

# ---------------------------------------------------------------------------
echo "[test 4] a case untouched by this run's batch still ends up with both date keys present"
MASTER4="$TMPDIR/t4_master.json"
cat > "$MASTER4" <<'EOF'
{"schema_version":1,"last_merged_at":null,"cases":[
  {"case_id":"case-t-0003","company":"Gamma LLC","industry":"logistics",
   "workflow_before":"manual","workflow_after":"automated","ai_system_or_tool":"GammaOpt",
   "measurable_kpi":"cost","kpi_value":"-10%","evidence_quote":"q",
   "source_url":"https://example.com/gamma","source_title":"t","source_domain":"example.com",
   "confidence":0.5,"verification_status":"snippet-only",
   "case_key":"gamma llc|gammaopt|automated","corroboration_count":1,
   "discovery":{"first_seen_at":"2026-07-01","last_corroborated_at":"2026-07-01","found_via":[{}]},
   "conflicting_evidence_log":[]}
]}
EOF
EMPTY="$TMPDIR/empty.json"
echo '{"cases":[]}' > "$EMPTY"
bash "$MERGE" "$EMPTY" "$MASTER4" > /dev/null
assert_eq "untouched case gets transformation_date:unknown via normalization" "unknown" \
  "$(jq -r '.cases[0].transformation_date' "$MASTER4")"
assert_eq "untouched case gets publication_date:unknown via normalization" "unknown" \
  "$(jq -r '.cases[0].publication_date' "$MASTER4")"
assert_eq "untouched case has both keys present" "true" \
  "$(jq '.cases[0] | (has("transformation_date") and has("publication_date"))' "$MASTER4")"

# ---------------------------------------------------------------------------
echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
