#!/usr/bin/env bash
# test_parallel_harvest.sh — deterministic, OFFLINE proof that the harvest lanes
# can run CONCURRENTLY without losing or corrupting data.
#
# Everything runs under a temp STATE_DIR with a MOCK claude (CLAUDE_BIN), so no
# live claude, no network, and no production state/ write. The real loops of
# harvest_entities.sh are driven end to end.
#
# Asserts, in order:
#   A  split_entity_registry.py partitions the union exactly (no loss, no leak)
#   B  the split refuses to clobber a shard that has drifted ahead of the union
#   C  lockdir gives real mutual exclusion, releases, and breaks a stale lock
#   D  --check reads the shard, falls back to the union, and has NO side effects
#   E  two lanes on the SAME topic cannot both run; different topics never block
#   F  THE REGRESSION: four concurrent lanes each keep every entity they merged
#      — and the same workload against ONE shared file demonstrably loses rows
#      (the pre-fix behaviour this whole change exists to remove)
#   G  merge_building_blocks.sh folds shards -> union, is idempotent, preserves
#      union rows no shard carries, and folds the ledger shards
#   H  production state/ is byte-identical before and after this test
#
#   Usage: bash tests/test_parallel_harvest.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENT="$ROOT/scripts/harvest_entities.sh"
SPLIT="$ROOT/scripts/split_entity_registry.py"
FOLD="$ROOT/scripts/merge_building_blocks.sh"
MERGE1="$ROOT/scripts/merge_entity_registry.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_ne()       { if [ "$2" != "$3" ]; then ok "$1"; else bad "$1 (expected NOT [$2])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }

echo "== test_parallel_harvest.sh =="

# --- snapshot production state/ (assertion H) -------------------------------
snapshot() {
  if [ -d "$ROOT/state" ]; then
    find "$ROOT/state" -type f 2>/dev/null | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git -C "$ROOT" hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
}
STATE_BEFORE="$(snapshot)"

# --- fixture: a union registry with all four topics + one alien topic -------
mk_union() {
  local out="$1"
  python - "$out" <<'PY'
import json, sys
ents = []
n = 0
for topic, count in (("agent", 6), ("mcp", 5), ("prompt", 4), ("skill", 7)):
    for i in range(count):
        n += 1
        ents.append({
            "entity_id": "ent-t-%04d" % n,
            "topic": topic,
            "entity_type": "tool",
            "name": "%s-fixture-%d" % (topic, i),
            "description": "fixture",
            "description_source": "verified" if i % 3 else "snippet-only",
            "entity_key": "%s|%s-fixture-%d" % (topic, topic, i),
            "target_url": "https://example.com/%s/%d" % (topic, i),
            "source_url": "https://seed.example.com/%s" % topic,
            "github_stars": None,
            "corroboration_count": 1,
            "conflicting_evidence_log": [],
            "discovery": {"first_seen_at": "2026-01-01", "last_corroborated_at": "2026-01-01", "found_via": []},
        })
doc = {"schema_version": 2, "last_merged_at": "2026-01-01T00:00:00Z",
       "metadata": {"total_entities": len(ents)}, "entities": ents}
json.dump(doc, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
}

# =========================================================================== A
echo "-- A: split partitions the union exactly"
SA="$TMPROOT/A"; mkdir -p "$SA"
mk_union "$SA/entity_registry.json"
out="$(python "$SPLIT" --state "$SA" 2>&1)"; rc=$?
assert_eq "A1 split exits 0" "0" "$rc"
for f in BuildingBlocks_Agent.json BuildingBlocks_MCP.json BuildingBlocks_Prompt.json BuildingBlocks_Skill.json; do
  if [ -f "$SA/$f" ]; then ok "A2 $f created"; else bad "A2 $f missing"; fi
done
assert_eq "A3 agent shard count"  "6" "$(jq '.entities|length' "$SA/BuildingBlocks_Agent.json")"
assert_eq "A4 mcp shard count"    "5" "$(jq '.entities|length' "$SA/BuildingBlocks_MCP.json")"
assert_eq "A5 prompt shard count" "4" "$(jq '.entities|length' "$SA/BuildingBlocks_Prompt.json")"
assert_eq "A6 skill shard count"  "7" "$(jq '.entities|length' "$SA/BuildingBlocks_Skill.json")"
assert_eq "A7 shards sum to the union (no loss)" "22" \
  "$(jq -s '[.[].entities[]]|length' "$SA"/BuildingBlocks_*.json)"
assert_eq "A8 no cross-topic leakage into the mcp shard" "0" \
  "$(jq '[.entities[]|select(.topic!="mcp")]|length' "$SA/BuildingBlocks_MCP.json")"
assert_eq "A9 shard metadata recomputed, not copied from the union" "6" \
  "$(jq '.metadata.total_entities' "$SA/BuildingBlocks_Agent.json")"
# The shard must stay schema-compatible: the --check tally query must work on it.
assert_eq "A10 shard answers the verified-count query" "4" \
  "$(jq '[.entities[]|select(.topic=="agent" and .description_source=="verified")]|length' "$SA/BuildingBlocks_Agent.json")"

# an alien topic must be refused, not silently dropped
SA2="$TMPROOT/A2"; mkdir -p "$SA2"
jq '.entities[0].topic = "wildcard"' "$SA/entity_registry.json" > "$SA2/entity_registry.json"
out="$(python "$SPLIT" --state "$SA2" 2>&1)"; rc=$?
assert_eq "A11 unknown topic refuses the split" "1" "$rc"
assert_contains "A12 and says why" "$out" "outside"

# =========================================================================== B
echo "-- B: drift guard protects unmerged harvest work"
jq '.entities += [{"entity_key":"agent|only-in-shard","topic":"agent","entity_type":"tool",
    "name":"only-in-shard","description":"d","description_source":"verified",
    "target_url":"https://example.com/x","github_stars":null}]' \
  "$SA/BuildingBlocks_Agent.json" > "$SA/tmp.json" && mv "$SA/tmp.json" "$SA/BuildingBlocks_Agent.json"
out="$(python "$SPLIT" --state "$SA" 2>&1)"; rc=$?
assert_eq "B1 refuses to clobber a drifted shard" "1" "$rc"
assert_contains "B2 names the recovery path" "$out" "merge_building_blocks.sh"
assert_eq "B3 the unmerged entity is still there" "7" "$(jq '.entities|length' "$SA/BuildingBlocks_Agent.json")"
out="$(python "$SPLIT" --state "$SA" --force 2>&1)"; rc=$?
assert_eq "B4 --force overrides" "0" "$rc"
assert_eq "B5 --force discarded the drifted row (as documented)" "6" \
  "$(jq '.entities|length' "$SA/BuildingBlocks_Agent.json")"

# =========================================================================== C
echo "-- C: lockdir mutual exclusion"
# shellcheck source=/dev/null
source "$ROOT/scripts/lib/lockdir.sh"
LK="$TMPROOT/C/test.lock"
if lock_acquire "$LK" "t1"; then ok "C1 first acquire succeeds"; else bad "C1 first acquire failed"; fi
# a second acquire from a DIFFERENT process must fail (same process would see its own pid)
if bash -c "source '$ROOT/scripts/lib/lockdir.sh'; lock_acquire '$LK' t2" 2>/dev/null; then
  bad "C2 second acquire wrongly succeeded"
else
  ok "C2 second acquire refused while held"
fi
lock_release "$LK"
if [ -d "$LK" ]; then bad "C3 lock dir still present after release"; else ok "C3 released"; fi
if bash -c "source '$ROOT/scripts/lib/lockdir.sh'; lock_acquire '$LK' t3" 2>/dev/null; then
  ok "C4 re-acquire after release succeeds"
else
  bad "C4 re-acquire after release failed"
fi
# stale lock (dead pid + old timestamp) must be breakable, or a crash wedges the repo
mkdir -p "$TMPROOT/C/stale.lock"
printf 'pid=999999 host=x label=dead started_at=2000-01-01T00:00:00Z epoch=100\n' > "$TMPROOT/C/stale.lock/owner"
if bash -c "source '$ROOT/scripts/lib/lockdir.sh'; lock_acquire '$TMPROOT/C/stale.lock' t4" 2>/dev/null; then
  ok "C5 stale lock is broken and re-acquired"
else
  bad "C5 stale lock wedged the lane"
fi
# ...but a FRESH lock owned by a live process must NOT be broken
mkdir -p "$TMPROOT/C/live.lock"
printf 'pid=%s host=x label=live started_at=now epoch=%s\n' "$$" "$(date +%s)" > "$TMPROOT/C/live.lock/owner"
if bash -c "source '$ROOT/scripts/lib/lockdir.sh'; lock_acquire '$TMPROOT/C/live.lock' t5" 2>/dev/null; then
  bad "C6 a live lock was wrongly broken"
else
  ok "C6 a live lock is never broken"
fi

# =========================================================================== D
echo "-- D: --check is sharded and side-effect free"
SD="$TMPROOT/D"; mkdir -p "$SD"
mk_union "$SD/entity_registry.json"
# no shard yet -> must fall back to the union, and must NOT create the shard
out="$(STATE_DIR="$SD" bash "$ENT" agent 250 --check 2>&1)"
assert_contains "D1 falls back to the union when no shard exists" "$out" "current=4"
if [ -f "$SD/BuildingBlocks_Agent.json" ]; then bad "D2 --check created a shard (side effect)"; else ok "D2 --check created nothing"; fi
if [ -d "$SD/locks" ]; then bad "D3 --check took a lock (side effect)"; else ok "D3 --check took no lock"; fi
python "$SPLIT" --state "$SD" >/dev/null 2>&1
# now that a shard exists, --check must read the SHARD, not the union
jq '.entities += [{"entity_key":"agent|shard-only","topic":"agent","entity_type":"tool","name":"shard-only",
    "description":"d","description_source":"verified","target_url":"https://example.com/s","github_stars":null}]' \
  "$SD/BuildingBlocks_Agent.json" > "$SD/t.json" && mv "$SD/t.json" "$SD/BuildingBlocks_Agent.json"
out="$(STATE_DIR="$SD" bash "$ENT" agent 250 --check 2>&1)"
assert_contains "D4 reads the shard once it exists" "$out" "current=5"

# =========================================================================== E
echo "-- E: lane locks — same topic serialised, different topics free"
SE="$TMPROOT/E"; mkdir -p "$SE/locks"
mk_union "$SE/entity_registry.json"
# a mock claude that just blocks, so the lane holds its lock while we probe
BLOCKER="$TMPROOT/blocker.sh"
cat > "$BLOCKER" <<'EOF'
#!/usr/bin/env bash
sleep 30
EOF
chmod +x "$BLOCKER"
STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$ENT" agent 9999 >"$TMPROOT/E_agent.log" 2>&1 &
LANE_PID=$!
# wait for the lock to appear rather than sleeping a fixed guess
for _ in $(seq 1 100); do [ -d "$SE/locks/harvest_agent.lock" ] && break; sleep 0.1; done
if [ -d "$SE/locks/harvest_agent.lock" ]; then ok "E1 lane took its topic lock"; else bad "E1 lane never took a lock"; fi

out="$(STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$ENT" agent 9999 2>&1)"; rc=$?
assert_eq "E2 a second SAME-topic lane refuses to start" "1" "$rc"
assert_contains "E3 and explains why" "$out" "already running"

# a DIFFERENT topic must not be blocked — this is the whole point of the change
timeout 10 env STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$ENT" mcp 9999 >"$TMPROOT/E_mcp.log" 2>&1
rc=$?
if [ "$rc" -eq 124 ]; then
  ok "E4 a different topic starts freely (ran until timeout, not refused)"
else
  case "$(cat "$TMPROOT/E_mcp.log")" in
    *"already running"*) bad "E4 a different topic was wrongly blocked" ;;
    *) ok "E4 a different topic was not blocked (exit $rc)" ;;
  esac
fi
kill "$LANE_PID" 2>/dev/null; wait "$LANE_PID" 2>/dev/null
# the killed lane must not leave its lock behind (EXIT trap releases it)
for _ in $(seq 1 30); do [ -d "$SE/locks/harvest_agent.lock" ] || break; sleep 0.1; done
if [ -d "$SE/locks/harvest_agent.lock" ]; then
  bad "E5 lock survived lane termination"
else
  ok "E5 lock released when the lane died"
fi

# =========================================================================== F
echo "-- F: REGRESSION — concurrent merges lose nothing when sharded"
SF="$TMPROOT/F"; mkdir -p "$SF"
# Each lane merges ROWS_PER_LANE distinct entities into its own shard, all four
# at the same time. Every row must survive.
ROWS=12
for topic in agent mcp prompt skill; do
  case "$topic" in
    agent) shard="BuildingBlocks_Agent.json" ;;  mcp) shard="BuildingBlocks_MCP.json" ;;
    prompt) shard="BuildingBlocks_Prompt.json" ;; skill) shard="BuildingBlocks_Skill.json" ;;
  esac
  echo '{"schema_version":2,"last_merged_at":null,"entities":[]}' > "$SF/$shard"
  ( for i in $(seq 1 "$ROWS"); do
      jq -n --arg t "$topic" --arg n "conc-$i" \
        '{entities:[{topic:$t,entity_type:"tool",name:$n,description:"d",
                     description_source:"verified",target_url:("https://example.com/"+$t+"/"+$n),
                     source_url:"https://seed.example.com",github_stars:null}],ledger_patch:[]}' \
        > "$SF/batch_${topic}_$i.json"
      bash "$MERGE1" "$SF/batch_${topic}_$i.json" "$SF/$shard" >/dev/null 2>&1
    done ) &
done
wait
sharded_total=0
for shard in "$SF"/BuildingBlocks_*.json; do
  if ! jq empty "$shard" 2>/dev/null; then bad "F0 $shard became invalid JSON"; fi
  sharded_total=$(( sharded_total + $(jq '.entities|length' "$shard") ))
done
assert_eq "F1 sharded concurrency keeps every row (4 lanes x $ROWS)" "$((ROWS*4))" "$sharded_total"

# Contrast: the SAME workload against one shared file. This is the pre-fix
# layout; it is expected to lose rows to the read-modify-write race. The test
# asserts the sharded run is at least as complete as the shared run — it never
# asserts that the shared run MUST lose data, because a race that happens not to
# collide on a fast machine would make that a flaky test.
SHARED="$SF/shared_registry.json"
echo '{"schema_version":2,"last_merged_at":null,"entities":[]}' > "$SHARED"
for topic in agent mcp prompt skill; do
  ( for i in $(seq 1 "$ROWS"); do
      bash "$MERGE1" "$SF/batch_${topic}_$i.json" "$SHARED" >/dev/null 2>&1
    done ) &
done
wait
if jq empty "$SHARED" 2>/dev/null; then
  shared_total="$(jq '.entities|length' "$SHARED")"
else
  shared_total="0 (file corrupted)"
fi
echo "     [evidence] shared single-file result: $shared_total / $((ROWS*4)) rows survived"
echo "     [evidence] sharded result:            $sharded_total / $((ROWS*4)) rows survived"
if [ "$sharded_total" -ge "${shared_total%% *}" ] 2>/dev/null; then
  ok "F2 sharding is never worse than the shared file"
else
  bad "F2 sharding lost more rows than the shared file"
fi

# =========================================================================== F2
echo "-- FT: topic guard keeps a lane's shard single-topic"
# A live end-to-end run surfaced this: 1G returned entities labelled with a topic
# other than the lane's, they merged into the shard, and the fold then refused
# EVERY shard — one stray row blocked the union rebuild for all four topics.
# The lane must drop foreign-topic rows before merging.
SFT="$TMPROOT/FT"; mkdir -p "$SFT"
echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[]}' > "$SFT/entity_registry.json"
echo '{"ledger":[]}' > "$SFT/visited_url_ledger.json"
FTMOCK="$TMPROOT/ft_mock.sh"
cat > "$FTMOCK" <<'FTEOF'
#!/usr/bin/env bash
set -u
args="$*"
emit() { printf '{"result": %s}\n' "$(printf '%s' "$1" | jq -Rs .)"; }
case "$args" in
  *"--append-system-prompt"*)
    # one correct-topic row + one foreign-topic row in the same batch
    emit '{"entities":[
      {"topic":"agent","entity_type":"tool","name":"good-one","entity_key":"agent|good-one",
       "description":"d","description_source":"verified","source_url":"https://seed.example.com/1",
       "target_url":"https://example.com/1","github_stars":null},
      {"topic":"mcp","entity_type":"tool","name":"wrong-lane","entity_key":"mcp|wrong-lane",
       "description":"d","description_source":"verified","source_url":"https://seed.example.com/2",
       "target_url":"https://example.com/2","github_stars":null}],
      "ledger_patch":[{"url":"https://seed.example.com/1","entity_extracted":true,"entity_ids":["e1"]}]}' ;;
  *)
    emit '{"hits":[{"source_url":"https://seed.example.com/1","target_url":"https://example.com/1","title":"t","snippet":"s","domain":"example.com"}]}' ;;
esac
exit 0
FTEOF
chmod +x "$FTMOCK"
out="$(STATE_DIR="$SFT" CLAUDE_BIN="$FTMOCK" BATCH_SIZE=1 MAX_LOOPS=2 NO_PROGRESS_THRESHOLD=1 \
       CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 bash "$ENT" agent 1 2>&1)"
assert_contains "FT1 the foreign-topic row is reported" "$out" "topic other than 'agent'"
assert_eq "FT2 only the correct-topic row was merged" "1" \
  "$(jq '.entities|length' "$SFT/BuildingBlocks_Agent.json")"
assert_eq "FT3 the shard stays single-topic" "0" \
  "$(jq '[.entities[]|select(.topic!="agent")]|length' "$SFT/BuildingBlocks_Agent.json")"
assert_eq "FT4 the dropped row did not leak into another shard" "0" \
  "$(jq '[.entities[]?|select(.name=="wrong-lane")]|length' "$SFT/BuildingBlocks_MCP.json" 2>/dev/null || echo 0)"
# and because the shard stayed pure, the fold still works
STATE_DIR="$SFT" bash "$FOLD" >/dev/null 2>&1; rc=$?
assert_eq "FT5 the fold is not blocked by the dropped row" "0" "$rc"

# =========================================================================== G
echo "-- G: fold shards -> union"
SG="$TMPROOT/G"; mkdir -p "$SG"
mk_union "$SG/entity_registry.json"
python "$SPLIT" --state "$SG" >/dev/null 2>&1
# simulate two lanes having harvested new rows into their own shards
for pair in "agent:BuildingBlocks_Agent.json" "skill:BuildingBlocks_Skill.json"; do
  t="${pair%%:*}"; f="${pair#*:}"
  jq --arg t "$t" '.entities += [{"entity_key":($t+"|newly-harvested"),"topic":$t,"entity_type":"tool",
      "name":"newly-harvested","description":"d","description_source":"verified",
      "target_url":("https://example.com/"+$t+"/new"),"github_stars":null}]' \
    "$SG/$f" > "$SG/t.json" && mv "$SG/t.json" "$SG/$f"
done
# and a ledger shard per lane, with overlapping + distinct rows
cat > "$SG/visited_url_ledger.json" <<'EOF'
{"ledger":[{"url":"https://a.example.com","crawl_count":1,"first_crawled_at":"2026-01-01T00:00:00Z","last_crawled_at":"2026-01-01T00:00:00Z","extracted":false,"case_ids":[],"entity_extracted":false,"entity_ids":[]}]}
EOF
cat > "$SG/visited_url_ledger_agent.json" <<'EOF'
{"ledger":[{"url":"https://a.example.com","crawl_count":2,"first_crawled_at":"2026-01-01T00:00:00Z","last_crawled_at":"2026-02-01T00:00:00Z","extracted":false,"case_ids":[],"entity_extracted":true,"entity_ids":["ent-a"]},
           {"url":"https://agent-only.example.com","crawl_count":1,"first_crawled_at":"2026-02-01T00:00:00Z","last_crawled_at":"2026-02-01T00:00:00Z","extracted":false,"case_ids":[],"entity_extracted":true,"entity_ids":["ent-b"]}]}
EOF
cat > "$SG/visited_url_ledger_skill.json" <<'EOF'
{"ledger":[{"url":"https://skill-only.example.com","crawl_count":1,"first_crawled_at":"2026-02-02T00:00:00Z","last_crawled_at":"2026-02-02T00:00:00Z","extracted":false,"case_ids":[],"entity_extracted":true,"entity_ids":["ent-c"]}]}
EOF
out="$(STATE_DIR="$SG" bash "$FOLD" 2>&1)"; rc=$?
assert_eq "G1 fold exits 0" "0" "$rc"
assert_eq "G2 union now holds both new rows" "24" "$(jq '.entities|length' "$SG/entity_registry.json")"
assert_eq "G3 union metadata recomputed" "24" "$(jq '.metadata.total_entities' "$SG/entity_registry.json")"
assert_eq "G4 no duplicate entity_keys in the union" "24" \
  "$(jq '[.entities[]|(.entity_key // (.topic+"|"+(.name|ascii_downcase)))]|unique|length' "$SG/entity_registry.json")"
# ledger fold: 3 distinct urls, flags latched, ids unioned, counts maxed
assert_eq "G5 ledger union has every distinct url" "3" "$(jq '.ledger|length' "$SG/visited_url_ledger.json")"
assert_eq "G6 entity_extracted latches true" "true" \
  "$(jq -r '.ledger[]|select(.url=="https://a.example.com")|.entity_extracted' "$SG/visited_url_ledger.json")"
assert_eq "G7 crawl_count takes the max" "2" \
  "$(jq '.ledger[]|select(.url=="https://a.example.com")|.crawl_count' "$SG/visited_url_ledger.json")"
assert_eq "G8 last_crawled_at takes the later value" "2026-02-01T00:00:00Z" \
  "$(jq -r '.ledger[]|select(.url=="https://a.example.com")|.last_crawled_at' "$SG/visited_url_ledger.json")"

# idempotence: folding again changes nothing but the timestamp
before="$(jq -S 'del(.last_merged_at)' "$SG/entity_registry.json")"
led_before="$(jq -S . "$SG/visited_url_ledger.json")"
STATE_DIR="$SG" bash "$FOLD" >/dev/null 2>&1
after="$(jq -S 'del(.last_merged_at)' "$SG/entity_registry.json")"
led_after="$(jq -S . "$SG/visited_url_ledger.json")"
assert_eq "G9 entity fold is idempotent" "$before" "$after"
assert_eq "G10 ledger fold is idempotent" "$led_before" "$led_after"

# a union row no shard carries must be PRESERVED, never deleted
jq '.entities += [{"entity_key":"legacy|orphan","topic":"legacy","entity_type":"tool","name":"orphan",
    "description":"d","description_source":"verified","target_url":"https://example.com/o","github_stars":null}]' \
  "$SG/entity_registry.json" > "$SG/t.json" && mv "$SG/t.json" "$SG/entity_registry.json"
STATE_DIR="$SG" bash "$FOLD" >/dev/null 2>&1
assert_eq "G11 an orphan union row is preserved, not deleted" "1" \
  "$(jq '[.entities[]|select(.entity_key=="legacy|orphan")]|length' "$SG/entity_registry.json")"

# a missing shard is DERIVED from the union by default (lossless self-heal) —
# a harvest_all run where every lane was skipped never bootstraps a shard, and
# that must not make the fold fail
SG2="$TMPROOT/G2"; mkdir -p "$SG2"
mk_union "$SG2/entity_registry.json"
python "$SPLIT" --state "$SG2" >/dev/null 2>&1
rm -f "$SG2/BuildingBlocks_Prompt.json"
out="$(STATE_DIR="$SG2" bash "$FOLD" 2>&1)"; rc=$?
assert_eq "G12 a missing shard is derived, not fatal" "0" "$rc"
assert_contains "G13 and says it derived it" "$out" "deriving it from the union"
assert_eq "G14 the derived shard has the union's prompt rows" "4" \
  "$(jq '.entities|length' "$SG2/BuildingBlocks_Prompt.json")"
assert_eq "G15 no entity lost by the self-heal" "22" "$(jq '.entities|length' "$SG2/entity_registry.json")"

# ...but --strict still demands every shard exist (CI / deliberate checks)
SG2b="$TMPROOT/G2b"; mkdir -p "$SG2b"
mk_union "$SG2b/entity_registry.json"
python "$SPLIT" --state "$SG2b" >/dev/null 2>&1
rm -f "$SG2b/BuildingBlocks_Prompt.json"
out="$(STATE_DIR="$SG2b" bash "$FOLD" --strict 2>&1)"; rc=$?
assert_eq "G16 --strict aborts on a missing shard" "1" "$rc"
assert_contains "G17 and names the missing topic" "$out" "prompt"
assert_eq "G18 union untouched by the aborted strict fold" "22" \
  "$(jq '.entities|length' "$SG2b/entity_registry.json")"

# a shard containing a foreign topic must abort too (entity_key collision risk)
SG3="$TMPROOT/G3"; mkdir -p "$SG3"
mk_union "$SG3/entity_registry.json"
python "$SPLIT" --state "$SG3" >/dev/null 2>&1
jq '.entities[0].topic = "skill"' "$SG3/BuildingBlocks_Agent.json" > "$SG3/t.json" && mv "$SG3/t.json" "$SG3/BuildingBlocks_Agent.json"
out="$(STATE_DIR="$SG3" bash "$FOLD" 2>&1)"; rc=$?
assert_eq "G19 a cross-topic shard aborts the fold (even without --strict)" "1" "$rc"

# =========================================================================== H
echo "-- H: production state/ untouched"
STATE_AFTER="$(snapshot)"
assert_eq "H1 production state/ byte-identical before and after" "$STATE_BEFORE" "$STATE_AFTER"

echo ""
echo "== test_parallel_harvest.sh: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ] || exit 1
exit 0
