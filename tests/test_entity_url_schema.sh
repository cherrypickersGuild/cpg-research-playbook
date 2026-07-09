#!/usr/bin/env bash
# test_entity_url_schema.sh — deterministic functional test for the entity
# registry's source_url/target_url schema (see docs/entity_url_migration_note.md).
#
# Exercises scripts/merge_entity_registry.sh only, against fixtures built in a
# temp dir. No live `claude -p` calls, no full harvest, no writes to any real
# state/*.json file.
#
#   Usage: bash tests/test_entity_url_schema.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MERGE="$ROOT/scripts/merge_entity_registry.sh"
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
echo "[test 1] new entity: source_url and target_url both preserved, no url key"
MASTER="$TMPDIR/t1_master.json"
NEW="$TMPDIR/t1_new.json"
echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$MASTER"
cat > "$NEW" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0001","topic":"agent","entity_type":"framework","name":"TestAgent",
   "source_url":"https://blog.example.com/testagent-review","target_url":"https://github.com/test/agent",
   "description":"d","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW" "$MASTER" > /dev/null

assert_eq "source_url preserved" "https://blog.example.com/testagent-review" \
  "$(jq -r '.entities[0].source_url' "$MASTER")"
assert_eq "target_url stored separately" "https://github.com/test/agent" \
  "$(jq -r '.entities[0].target_url' "$MASTER")"
assert_eq "no ambiguous url key" "false" \
  "$(jq '.entities[0] | has("url")' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 2] corroborating batch never overwrites an existing source_url"
NEW2="$TMPDIR/t2_new.json"
cat > "$NEW2" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-9001","topic":"agent","entity_type":"framework","name":"TestAgent",
   "source_url":"https://another-site.example.com/mentions-testagent","target_url":"https://github.com/test/agent",
   "description":"d2","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW2" "$MASTER" > /dev/null

assert_eq "source_url unchanged after corroboration" "https://blog.example.com/testagent-review" \
  "$(jq -r '.entities[0].source_url' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 3] target_url is filled from unknown, but a genuine conflict is logged not overwritten"
MASTER3="$TMPDIR/t3_master.json"
cat > "$MASTER3" <<'EOF'
{"schema_version":1,"last_merged_at":null,"entities":[
  {"entity_id":"ent-t-0002","topic":"mcp","entity_type":"server","name":"UnknownTargetServer",
   "source_url":"https://hit.example.com/found-here","target_url":"unknown",
   "description":"d","description_source":"snippet-only","entity_key":"mcp|unknowntargetserver",
   "corroboration_count":1,
   "discovery":{"first_seen_at":"2026-07-01","last_corroborated_at":"2026-07-01","found_via":[{}]},
   "conflicting_evidence_log":[]}
]}
EOF
NEW3="$TMPDIR/t3_new.json"
cat > "$NEW3" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-9002","topic":"mcp","entity_type":"server","name":"UnknownTargetServer",
   "source_url":"https://hit2.example.com/also-found-here","target_url":"https://github.com/unknown/server",
   "description":"d3","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW3" "$MASTER3" > /dev/null
assert_eq "target_url filled from unknown" "https://github.com/unknown/server" \
  "$(jq -r '.entities[0].target_url' "$MASTER3")"

NEW3B="$TMPDIR/t3b_new.json"
cat > "$NEW3B" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-9003","topic":"mcp","entity_type":"server","name":"UnknownTargetServer",
   "source_url":"https://hit3.example.com/found-again","target_url":"https://official.example.com/different-page",
   "description":"d4","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW3B" "$MASTER3" > /dev/null
assert_eq "conflicting target_url NOT silently overwritten" "https://github.com/unknown/server" \
  "$(jq -r '.entities[0].target_url' "$MASTER3")"
assert_eq "conflict logged to conflicting_evidence_log" "target_url" \
  "$(jq -r '.entities[0].conflicting_evidence_log[0].field' "$MASTER3")"

# ---------------------------------------------------------------------------
echo "[test 4] a stray legacy url field on incoming data is dropped, never merged in"
MASTER4="$TMPDIR/t4_master.json"
echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$MASTER4"
NEW4="$TMPDIR/t4_new.json"
cat > "$NEW4" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0003","topic":"skill","entity_type":"skill","name":"LegacyFormatSkill",
   "url":"https://old-format.example.com/should-be-dropped",
   "source_url":"https://found.example.com/skill","target_url":"https://official.example.com/skill",
   "description":"d","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW4" "$MASTER4" > /dev/null
assert_eq "stray url key dropped on ingest" "false" \
  "$(jq '.entities[0] | has("url")' "$MASTER4")"

# ---------------------------------------------------------------------------
echo "[test 5] registry metadata counts match actual records"
MASTER5="$TMPDIR/t5_master.json"
echo '{"schema_version":1,"last_merged_at":null,"entities":[]}' > "$MASTER5"
NEW5="$TMPDIR/t5_new.json"
cat > "$NEW5" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-1","topic":"agent","entity_type":"framework","name":"A1","source_url":"https://a.example.com/1","target_url":"https://a1.example.com","description":"d","description_source":"verified"},
  {"entity_id":"ent-t-2","topic":"agent","entity_type":"product","name":"A2","source_url":"https://a.example.com/2","target_url":"unknown","description":"d","description_source":"snippet-only"},
  {"entity_id":"ent-t-3","topic":"mcp","entity_type":"server","name":"M1","source_url":"https://m.example.com/1","target_url":"https://m1.example.com","description":"d","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW5" "$MASTER5" > /dev/null

total_meta="$(jq '.metadata.total_entities' "$MASTER5")"
total_actual="$(jq '.entities | length' "$MASTER5")"
assert_eq "metadata.total_entities matches actual entity count" "$total_actual" "$total_meta"

agent_meta="$(jq '.metadata.entity_count_by_topic.agent' "$MASTER5")"
agent_actual="$(jq '[.entities[] | select(.topic=="agent")] | length' "$MASTER5")"
assert_eq "metadata.entity_count_by_topic.agent matches actual" "$agent_actual" "$agent_meta"

server_meta="$(jq '.metadata.entity_count_by_entity_type.server' "$MASTER5")"
server_actual="$(jq '[.entities[] | select(.entity_type=="server")] | length' "$MASTER5")"
assert_eq "metadata.entity_count_by_entity_type.server matches actual" "$server_actual" "$server_meta"

assert_eq "schema_version bumped to 2" "2" "$(jq '.schema_version' "$MASTER5")"

# ---------------------------------------------------------------------------
echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
