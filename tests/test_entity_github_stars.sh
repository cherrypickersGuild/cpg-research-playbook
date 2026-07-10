#!/usr/bin/env bash
# test_entity_github_stars.sh — deterministic functional test for the
# entity registry's github_stars field (see agents/stage1/1G_entity_extractor.md
# and scripts/merge_entity_registry.sh).
#
# Exercises scripts/merge_entity_registry.sh only, against fixtures built in a
# temp dir. No live `claude -p` calls, no GitHub API calls, no writes to any
# real state/*.json file.
#
#   Usage: bash tests/test_entity_github_stars.sh

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
echo "[test 1] new GitHub-repo entity gets github_stars populated"
MASTER="$TMPDIR/t1_master.json"
NEW="$TMPDIR/t1_new.json"
echo '{"schema_version":2,"last_merged_at":null,"entities":[]}' > "$MASTER"
cat > "$NEW" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0001","topic":"mcp","entity_type":"server","name":"RepoA",
   "source_url":"https://example.com/found-a","target_url":"https://github.com/foo/repo-a",
   "description":"d","description_source":"verified","github_stars":100}
]}
EOF
bash "$MERGE" "$NEW" "$MASTER" > /dev/null
assert_eq "github_stars populated on new GitHub entity" "100" \
  "$(jq -r '.entities[0].github_stars' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 2] a fresher non-null measurement overwrites the stored value (not a conflict)"
NEW2="$TMPDIR/t2_new.json"
cat > "$NEW2" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-9001","topic":"mcp","entity_type":"server","name":"RepoA",
   "source_url":"https://another.example.com/mention","target_url":"https://github.com/foo/repo-a",
   "description":"d2","description_source":"verified","github_stars":142}
]}
EOF
bash "$MERGE" "$NEW2" "$MASTER" > /dev/null
assert_eq "github_stars overwritten by newer measurement" "142" \
  "$(jq -r '.entities[0].github_stars' "$MASTER")"
assert_eq "no conflicting_evidence_log entry from a stars update" "0" \
  "$(jq '.entities[0].conflicting_evidence_log | length' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 3] a batch that doesn't re-measure stars keeps the existing value (no blank-out)"
NEW3="$TMPDIR/t3_new.json"
cat > "$NEW3" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-9002","topic":"mcp","entity_type":"server","name":"RepoA",
   "source_url":"https://third.example.com/mention","target_url":"https://github.com/foo/repo-a",
   "description":"d3","description_source":"verified"}
]}
EOF
bash "$MERGE" "$NEW3" "$MASTER" > /dev/null
assert_eq "github_stars kept when incoming batch has no measurement" "142" \
  "$(jq -r '.entities[0].github_stars' "$MASTER")"

# ---------------------------------------------------------------------------
echo "[test 4] non-GitHub target_url forces github_stars to null regardless of incoming value"
MASTER4="$TMPDIR/t4_master.json"
echo '{"schema_version":2,"last_merged_at":null,"entities":[]}' > "$MASTER4"
NEW4="$TMPDIR/t4_new.json"
cat > "$NEW4" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0002","topic":"agent","entity_type":"product","name":"NotARepo",
   "source_url":"https://example.com/found-b","target_url":"https://example.com/product-page",
   "description":"d","description_source":"verified","github_stars":9999}
]}
EOF
bash "$MERGE" "$NEW4" "$MASTER4" > /dev/null
assert_eq "github_stars forced null for non-GitHub target_url" "null" \
  "$(jq -r '.entities[0].github_stars' "$MASTER4")"

# ---------------------------------------------------------------------------
echo "[test 5] target_url:\"unknown\" also forces github_stars null"
NEW5="$TMPDIR/t5_new.json"
cat > "$NEW5" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0003","topic":"skill","entity_type":"skill","name":"UnresolvedTarget",
   "source_url":"https://example.com/found-c","target_url":"unknown",
   "description":"d","description_source":"snippet-only","github_stars":55}
]}
EOF
bash "$MERGE" "$NEW5" "$MASTER4" > /dev/null
assert_eq "github_stars forced null when target_url is unknown" "null" \
  "$(jq -r '.entities[] | select(.name=="UnresolvedTarget") | .github_stars' "$MASTER4")"

# ---------------------------------------------------------------------------
echo "[test 6] a GitHub URL that is NOT a repo root (e.g. an org page) is not treated as a repo"
NEW6="$TMPDIR/t6_new.json"
cat > "$NEW6" <<'EOF'
{"entities":[
  {"entity_id":"ent-t-0004","topic":"agent","entity_type":"framework","name":"JustAnOrgPage",
   "source_url":"https://example.com/found-d","target_url":"https://github.com/some-org",
   "description":"d","description_source":"verified","github_stars":321}
]}
EOF
bash "$MERGE" "$NEW6" "$MASTER4" > /dev/null
assert_eq "github_stars forced null for a github.com org page (not owner/repo)" "null" \
  "$(jq -r '.entities[] | select(.name=="JustAnOrgPage") | .github_stars' "$MASTER4")"

# ---------------------------------------------------------------------------
echo "[test 7] an entity untouched by this run's batch still ends up with an explicit github_stars key"
MASTER7="$TMPDIR/t7_master.json"
cat > "$MASTER7" <<'EOF'
{"schema_version":2,"last_merged_at":null,"entities":[
  {"entity_id":"ent-t-0005","topic":"prompt","entity_type":"tool","name":"PreexistingNoStars",
   "source_url":"https://example.com/found-e","target_url":"https://example.com/pre-existing",
   "description":"d","description_source":"verified","entity_key":"prompt|preexistingnostars",
   "corroboration_count":1,
   "discovery":{"first_seen_at":"2026-07-01","last_corroborated_at":"2026-07-01","found_via":[{}]},
   "conflicting_evidence_log":[]}
]}
EOF
EMPTY="$TMPDIR/empty.json"
echo '{"entities":[]}' > "$EMPTY"
bash "$MERGE" "$EMPTY" "$MASTER7" > /dev/null
assert_eq "untouched pre-existing entity gets github_stars:null via normalization" "null" \
  "$(jq -r '.entities[0].github_stars' "$MASTER7")"
assert_eq "untouched pre-existing entity has the key present (not just falsy)" "true" \
  "$(jq '.entities[0] | has("github_stars")' "$MASTER7")"

# ---------------------------------------------------------------------------
echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
