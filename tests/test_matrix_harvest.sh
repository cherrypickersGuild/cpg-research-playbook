#!/usr/bin/env bash
# test_matrix_harvest.sh — deterministic, OFFLINE test of the (category x topic)
# matrix harvest: spec -> parallel per-cell query expansion -> parallel per-cell
# harvest -> fold.
#
# Everything runs under a temp STATE_DIR with a MOCK claude (CLAUDE_BIN): no live
# claude, no network, no production state/ write. The real scripts are driven end
# to end.
#
# Asserts:
#   A  matrix_spec.py builds the cross product, indices, and manifest correctly
#   B  bad input is refused, not silently normalised (dupes, empties, bad chars,
#      out-of-range pairs, --spec conflicts)
#   C  query expansion is per-cell, augments rather than clobbers, and REFUSES to
#      shrink an existing query set
#   D  a cell harvest writes only its own files, stamps category/topic from the
#      manifest, and never leaks into another cell
#   E  cell lane locks: same cell refused, different cells free
#   F  run_matrix.sh runs cells CONCURRENTLY, respects MAX_PARALLEL, and reports
#      honestly
#   G  merge_matrix.sh folds cells, keeps same-name entities from different cells
#      distinct, and is idempotent
#   H  production state/ is byte-identical before and after
#
#   Usage: bash tests/test_matrix_harvest.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/scripts/matrix_spec.py"
EXPAND="$ROOT/scripts/expand_queries_cell.sh"
CELL="$ROOT/scripts/harvest_matrix_cell.sh"
RUNM="$ROOT/scripts/run_matrix.sh"
FOLD="$ROOT/scripts/merge_matrix.sh"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_ne()       { if [ "$2" != "$3" ]; then ok "$1"; else bad "$1 (expected NOT [$2])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }

echo "== test_matrix_harvest.sh =="

snapshot() {
  if [ -d "$ROOT/state" ]; then
    find "$ROOT/state" -type f 2>/dev/null | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git -C "$ROOT" hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
}
STATE_BEFORE="$(snapshot)"

# --- the mock ---------------------------------------------------------------
# Identifies the cell from the per-cell file paths in the prompt (unambiguous),
# and the call type from --append-system-prompt (1G) vs its absence.
MOCK="$TMPROOT/mock_claude.sh"
cat > "$MOCK" <<'MOCK_EOF'
#!/usr/bin/env bash
set -u
args="$*"
emit() { printf '{"result": %s}\n' "$(printf '%s' "$1" | jq -Rs .)"; }

cid="$(printf '%s' "$args" | grep -oE 'category#[0-9]+_topic#[0-9]+' | head -1)"
[ -n "$cid" ] || cid="unknown"

# query expansion: prompt names the queries_ file and has no system prompt
case "$args" in
  *"Stage 1A query expansion"*)
    n="${MOCK_QUERIES:-3}"
    rows=""
    for k in $(seq 1 "$n"); do
      [ -n "$rows" ] && rows="$rows,"
      rows="$rows{\"query_id\":\"$cid-$k\",\"query\":\"q$k for $cid\",\"query_type\":\"workflow_metric\",\"target_platforms\":[\"web\"],\"seed_source_urls\":[],\"status\":\"active\",\"created_at\":\"2026-07-22\",\"run_count\":0,\"yield_count\":0}"
    done
    emit "{\"cell_id\":\"$cid\",\"generated_at\":\"2026-07-22\",\"queries\":[$rows]}"
    exit 0 ;;
esac

is_extract="no"; case "$args" in *"--append-system-prompt"*) is_extract="yes";; esac
sleep "${MOCK_LATENCY:-0}"

if [ "$is_extract" = "no" ]; then
  u="$RANDOM$RANDOM"
  emit "{\"hits\":[{\"source_url\":\"https://seed.example.com/$cid/$u\",\"target_url\":\"https://example.com/$cid/$u\",\"title\":\"t\",\"snippet\":\"s\",\"domain\":\"example.com\"}]}"
  exit 0
fi

CNTDIR="${MOCK_COUNTER_DIR:-/tmp}"; mkdir -p "$CNTDIR"; CNT="$CNTDIR/$cid.cnt"
n=$(( $( [ -f "$CNT" ] && cat "$CNT" || echo 0 ) + 1 )); echo "$n" > "$CNT"
# Deliberately emit a WRONG topic/category so the cell identity stamp is tested.
emit "{\"entities\":[{\"topic\":\"WRONG-TOPIC\",\"category\":\"WRONG-CATEGORY\",\"entity_type\":\"tool\",\"name\":\"$cid-e$n\",\"description\":\"d\",\"description_source\":\"verified\",\"source_url\":\"https://seed.example.com/$cid/$n\",\"target_url\":\"https://example.com/$cid/$n\",\"github_stars\":null}],\"ledger_patch\":[{\"url\":\"https://seed.example.com/$cid/$n\",\"entity_extracted\":true,\"entity_ids\":[\"e-$n\"]}]}"
exit 0
MOCK_EOF
chmod +x "$MOCK"

# =========================================================================== A
echo "-- A: spec builds the cross product"
SA="$TMPROOT/A"; mkdir -p "$SA"
out="$(python "$SPEC" --categories "healthcare,finance" --topics "agent,rag,eval" --state "$SA" 2>&1)"; rc=$?
assert_eq "A1 spec exits 0" "0" "$rc"
assert_eq "A2 2 categories x 3 topics = 6 cells" "6" "$(printf '%s\n' "$out" | grep -c 'category#')"
assert_eq "A3 manifest cell_count" "6" "$(jq '.cell_count' "$SA/matrix/manifest.json")"
assert_eq "A4 indices are 1-based and ordered as typed" "finance" \
  "$(jq -r '.categories[] | select(.index==2) | .name' "$SA/matrix/manifest.json")"
assert_eq "A5 cell 2:3 is finance x eval" "finance|eval" \
  "$(jq -r '.cells[] | select(.i==2 and .j==3) | .category + "|" + .topic' "$SA/matrix/manifest.json")"
assert_eq "A6 filename matches category#i_topic#j.json" "category#2_topic#3.json" \
  "$(jq -r '.cells[] | select(.i==2 and .j==3) | .harvest_file' "$SA/matrix/manifest.json")"
assert_eq "A7 every cell_id is unique" "6" \
  "$(jq '[.cells[].cell_id] | unique | length' "$SA/matrix/manifest.json")"
# explicit pair subsetting
cat > "$SA/spec.json" <<'EOF'
{"categories":["healthcare","finance"],"topics":["agent","rag","eval"],"pairs":[[1,1],[2,3]]}
EOF
python "$SPEC" --spec "$SA/spec.json" --state "$SA" >/dev/null 2>&1
assert_eq "A8 pairs[] restricts to a subset" "2" "$(jq '.cell_count' "$SA/matrix/manifest.json")"

# =========================================================================== B
echo "-- B: bad input is refused, not normalised"
SB="$TMPROOT/B"; mkdir -p "$SB"
out="$(python "$SPEC" --categories "a,a" --topics "x" --state "$SB" 2>&1)"; rc=$?
assert_eq "B1 duplicate category refused" "1" "$rc"
assert_contains "B2 and explains the duplicate" "$out" "appears twice"
out="$(python "$SPEC" --categories "A,a" --topics "x" --state "$SB" 2>&1)"; rc=$?
assert_eq "B3 case-insensitive duplicate refused" "1" "$rc"
out="$(python "$SPEC" --categories "" --topics "x" --state "$SB" 2>&1)"; rc=$?
assert_eq "B4 empty category list refused" "1" "$rc"
out="$(python "$SPEC" --categories "a/b" --topics "x" --state "$SB" 2>&1)"; rc=$?
assert_eq "B5 path-reserved character refused" "1" "$rc"
cat > "$SB/bad.json" <<'EOF'
{"categories":["a"],"topics":["x"],"pairs":[[1,9]]}
EOF
out="$(python "$SPEC" --spec "$SB/bad.json" --state "$SB" 2>&1)"; rc=$?
assert_eq "B6 out-of-range pair refused" "1" "$rc"
out="$(python "$SPEC" --spec "$SB/bad.json" --categories "a" --state "$SB" 2>&1)"; rc=$?
assert_eq "B7 --spec + --categories refused" "1" "$rc"
if [ -f "$SB/matrix/manifest.json" ]; then bad "B8 a refused spec wrote a manifest"; else ok "B8 no manifest written by refused input"; fi

# =========================================================================== C
echo "-- C: per-cell query expansion augments and never shrinks"
SC="$TMPROOT/C"; mkdir -p "$SC"
python "$SPEC" --categories "healthcare" --topics "agent" --state "$SC" >/dev/null 2>&1
QF="$SC/matrix/queries_category#1_topic#1.json"
out="$(STATE_DIR="$SC" CLAUDE_BIN="$MOCK" MOCK_QUERIES=5 TARGET_QUERIES=5 bash "$EXPAND" 1 1 2>&1)"; rc=$?
assert_eq "C1 expansion exits 0" "0" "$rc"
assert_eq "C2 queries written" "5" "$(jq '.queries | length' "$QF")"
assert_eq "C3 category stamped from the manifest" "healthcare" "$(jq -r '.category' "$QF")"
assert_eq "C4 topic stamped from the manifest" "agent" "$(jq -r '.topic' "$QF")"
assert_eq "C5 cell_id stamped" "category#1_topic#1" "$(jq -r '.cell_id' "$QF")"
out="$(STATE_DIR="$SC" CLAUDE_BIN="$MOCK" TARGET_QUERIES=5 bash "$EXPAND" 1 1 --check 2>&1)"
assert_contains "C6 --check reports complete at target" "$out" "status=complete"
# a model returning FEWER queries must not destroy the existing set
out="$(STATE_DIR="$SC" CLAUDE_BIN="$MOCK" MOCK_QUERIES=2 TARGET_QUERIES=5 EXPAND_ATTEMPTS=1 bash "$EXPAND" 1 1 2>&1)"; rc=$?
assert_eq "C7 a shrinking expansion is refused" "1" "$rc"
assert_contains "C8 and says so" "$out" "refusing to shrink"
assert_eq "C9 the existing query set survived" "5" "$(jq '.queries | length' "$QF")"
# harvesting without a query set is a hard error
SC2="$TMPROOT/C2"; mkdir -p "$SC2"
python "$SPEC" --categories "healthcare" --topics "agent" --state "$SC2" >/dev/null 2>&1
out="$(STATE_DIR="$SC2" CLAUDE_BIN="$MOCK" bash "$CELL" 1 1 5 2>&1)"; rc=$?
assert_eq "C10 harvest without expansion is refused" "1" "$rc"
assert_contains "C11 and names the fix" "$out" "expand_queries_cell.sh"

# =========================================================================== D
echo "-- D: a cell harvest owns its files and stamps its own identity"
SD="$TMPROOT/D"; mkdir -p "$SD"
python "$SPEC" --categories "healthcare,finance" --topics "agent" --state "$SD" >/dev/null 2>&1
for ij in "1 1" "2 1"; do
  set -- $ij
  STATE_DIR="$SD" CLAUDE_BIN="$MOCK" MOCK_QUERIES=3 TARGET_QUERIES=3 bash "$EXPAND" "$1" "$2" >/dev/null 2>&1
done
STATE_DIR="$SD" CLAUDE_BIN="$MOCK" MOCK_COUNTER_DIR="$SD/cnt" BATCH_SIZE=1 MAX_LOOPS=4 \
  NO_PROGRESS_THRESHOLD=2 CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 bash "$CELL" 1 1 3 >/dev/null 2>&1
C11F="$SD/matrix/category#1_topic#1.json"
C21F="$SD/matrix/category#2_topic#1.json"
assert_eq "D1 the harvested cell file exists and has entities" "3" "$(jq '.entities | length' "$C11F")"
assert_eq "D2 topic overwritten from the manifest, not the model" "0" \
  "$(jq '[.entities[] | select(.topic != "agent")] | length' "$C11F")"
assert_eq "D3 category overwritten from the manifest, not the model" "0" \
  "$(jq '[.entities[] | select(.category != "healthcare")] | length' "$C11F")"
assert_eq "D4 the model's WRONG-TOPIC never reached the file" "0" \
  "$(jq '[.entities[] | select(.topic == "WRONG-TOPIC")] | length' "$C11F")"
assert_eq "D5 cell_id preserved through the merge" "category#1_topic#1" "$(jq -r '.cell_id' "$C11F")"
if [ -f "$C21F" ]; then bad "D6 harvesting cell 1:1 created cell 2:1's file"; else ok "D6 no leakage into the other cell's file"; fi
if [ -f "$SD/matrix/.ledger_category#1_topic#1.json" ]; then ok "D7 per-cell ledger created"; else bad "D7 no per-cell ledger"; fi
if [ -f "$SD/matrix/.ledger_category#2_topic#1.json" ]; then bad "D8 other cell's ledger touched"; else ok "D8 other cell's ledger untouched"; fi
assert_eq "D9 query run_count stamped back for the next expansion" "true" \
  "$(jq '[.queries[].run_count] | max > 0' "$SD/matrix/queries_category#1_topic#1.json")"

# =========================================================================== E
echo "-- E: cell lane locks"
SE="$TMPROOT/E"; mkdir -p "$SE"
python "$SPEC" --categories "healthcare,finance" --topics "agent" --state "$SE" >/dev/null 2>&1
for ij in "1 1" "2 1"; do
  set -- $ij
  STATE_DIR="$SE" CLAUDE_BIN="$MOCK" MOCK_QUERIES=3 TARGET_QUERIES=3 bash "$EXPAND" "$1" "$2" >/dev/null 2>&1
done
BLOCKER="$TMPROOT/blocker.sh"; printf '#!/usr/bin/env bash\nsleep 30\n' > "$BLOCKER"; chmod +x "$BLOCKER"
STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$CELL" 1 1 999 >"$TMPROOT/E11.log" 2>&1 &
LANE_PID=$!
for _ in $(seq 1 100); do [ -d "$SE/locks/harvest_category#1_topic#1.lock" ] && break; sleep 0.1; done
if [ -d "$SE/locks/harvest_category#1_topic#1.lock" ]; then ok "E1 cell took its lane lock"; else bad "E1 no lane lock taken"; fi
out="$(STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$CELL" 1 1 999 2>&1)"; rc=$?
assert_eq "E2 the SAME cell is refused while running" "1" "$rc"
assert_contains "E3 and explains why" "$out" "already running"
timeout 8 env STATE_DIR="$SE" CLAUDE_BIN="$BLOCKER" bash "$CELL" 2 1 999 >"$TMPROOT/E21.log" 2>&1
rc=$?
case "$(cat "$TMPROOT/E21.log")" in
  *"already running"*) bad "E4 a different cell was wrongly blocked" ;;
  *) ok "E4 a different cell is not blocked (exit $rc)" ;;
esac
kill "$LANE_PID" 2>/dev/null; wait "$LANE_PID" 2>/dev/null
for _ in $(seq 1 30); do [ -d "$SE/locks/harvest_category#1_topic#1.lock" ] || break; sleep 0.1; done
if [ -d "$SE/locks/harvest_category#1_topic#1.lock" ]; then bad "E5 lock survived lane termination"; else ok "E5 lock released when the lane died"; fi

# =========================================================================== F
echo "-- F: run_matrix.sh runs cells concurrently and caps parallelism"
SF="$TMPROOT/F"; mkdir -p "$SF"
out="$(STATE_DIR="$SF" bash "$RUNM" --categories "healthcare,finance" --topics "agent,rag" --dry-run 2>&1)"; rc=$?
assert_eq "F1 dry-run exits 0" "0" "$rc"
assert_eq "F2 dry-run plans 4 cells" "4" "$(printf '%s\n' "$out" | grep -cE 'category#[0-9]+_topic#[0-9]+')"
assert_contains "F3 dry-run launches nothing" "$out" "nothing launched"
# Regression: this platform's jq writes CRLF, so `read` on @tsv left a trailing
# carriage return in the LAST field only — invisible in normal output, but it
# ended up in the per-cell log filename and the summary. Assert the plan lines
# carry no CR at all.
if printf '%s\n' "$out" | grep -q $'\r'; then
  bad "F2b dry-run output contains a stray carriage return (jq CRLF leaked through read)"
else
  ok "F2b no stray carriage return in the cell plan"
fi

START=$(date +%s)
out="$(STATE_DIR="$SF" CLAUDE_BIN="$MOCK" MOCK_COUNTER_DIR="$SF/cnt" MOCK_QUERIES=3 MOCK_LATENCY=1 \
       MAX_PARALLEL=4 STAGGER_SEC=0 POLL_SEC=1 BATCH_SIZE=1 MAX_LOOPS=4 NO_PROGRESS_THRESHOLD=2 \
       CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 \
       bash "$RUNM" --categories "healthcare,finance" --topics "agent,rag" --target 3 --queries 3 --fold 2>&1)"
RC4=$?
ELAPSED4=$(( $(date +%s) - START ))
assert_eq "F4 all four cells reached target -> exit 0" "0" "$RC4"
assert_contains "F5 summary says COMPLETE" "$out" "matrix run COMPLETE"
for c in "category#1_topic#1" "category#1_topic#2" "category#2_topic#1" "category#2_topic#2"; do
  assert_eq "F6 $c harvested to target" "3" "$(jq '[.entities[]|select(.description_source=="verified")]|length' "$SF/matrix/$c.json" 2>/dev/null || echo MISSING)"
done
assert_eq "F7 each cell carries its own category" "healthcare" "$(jq -r '.category' "$SF/matrix/category#1_topic#2.json")"
assert_eq "F8 each cell carries its own topic" "rag" "$(jq -r '.topic' "$SF/matrix/category#1_topic#2.json")"
# Per-cell logs must be named for the cell, with no CR smuggled into the filename.
LOGDIR_F="$(find "$SF/logs" -maxdepth 1 -type d -name 'matrix_*' 2>/dev/null | head -1)"
assert_eq "F8b one clean log file per cell" "4" \
  "$(find "$LOGDIR_F" -maxdepth 1 -type f -name 'category#*_topic#*.log' 2>/dev/null | wc -l | tr -d ' ')"

# MAX_PARALLEL=1 must take materially longer than MAX_PARALLEL=4 on the same work
SF2="$TMPROOT/F2"; mkdir -p "$SF2"
START=$(date +%s)
STATE_DIR="$SF2" CLAUDE_BIN="$MOCK" MOCK_COUNTER_DIR="$SF2/cnt" MOCK_QUERIES=3 MOCK_LATENCY=1 \
  MAX_PARALLEL=1 STAGGER_SEC=0 POLL_SEC=1 BATCH_SIZE=1 MAX_LOOPS=4 NO_PROGRESS_THRESHOLD=2 \
  CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 \
  bash "$RUNM" --categories "healthcare,finance" --topics "agent,rag" --target 3 --queries 3 >/dev/null 2>&1
ELAPSED1=$(( $(date +%s) - START ))
echo "     [evidence] MAX_PARALLEL=4: ${ELAPSED4}s   MAX_PARALLEL=1: ${ELAPSED1}s"
if [ "$ELAPSED4" -lt "$ELAPSED1" ]; then
  ok "F9 concurrency is real (4 lanes finished faster than 1 at a time)"
else
  bad "F9 MAX_PARALLEL=4 was not faster than MAX_PARALLEL=1 (${ELAPSED4}s vs ${ELAPSED1}s)"
fi

# =========================================================================== G
echo "-- G: fold cells into the matrix union"
UN="$SF/matrix/matrix_union.json"
if [ -f "$UN" ]; then ok "G1 --fold produced the union"; else bad "G1 no union written"; fi
assert_eq "G2 union holds every cell's entities" "12" "$(jq '.entities | length' "$UN")"
assert_eq "G3 by_category counts" "6" "$(jq '.metadata.by_category.healthcare' "$UN")"
assert_eq "G4 by_topic counts" "6" "$(jq '.metadata.by_topic.rag' "$UN")"
# same-named entity in two different cells must stay TWO rows, not collapse to one
SG="$TMPROOT/G"; mkdir -p "$SG/matrix"
python "$SPEC" --categories "healthcare,finance" --topics "agent" --state "$SG" >/dev/null 2>&1
for pair in "1:healthcare" "2:finance"; do
  idx="${pair%%:*}"; cat="${pair#*:}"
  jq -n --arg c "$cat" --arg id "category#${idx}_topic#1" \
    '{schema_version:2, cell_id:$id, category:$c, topic:"agent", entities:[
       {topic:"agent", category:$c, entity_type:"tool", name:"SharedTool",
        entity_key:"agent|sharedtool", description:"d", description_source:"verified",
        target_url:"https://example.com/shared", github_stars:null}]}' \
    > "$SG/matrix/category#${idx}_topic#1.json"
done
STATE_DIR="$SG" bash "$FOLD" >/dev/null 2>&1
assert_eq "G5 same name in two cells stays two rows" "2" "$(jq '.entities | length' "$SG/matrix/matrix_union.json")"
assert_eq "G6 and they are distinguished by category" "2" \
  "$(jq '[.entities[].category] | unique | length' "$SG/matrix/matrix_union.json")"
before="$(jq -S 'del(.generated_at)' "$SG/matrix/matrix_union.json")"
STATE_DIR="$SG" bash "$FOLD" >/dev/null 2>&1
after="$(jq -S 'del(.generated_at)' "$SG/matrix/matrix_union.json")"
assert_eq "G7 fold is idempotent" "$before" "$after"
# an invalid cell file must abort the fold, not be skipped
echo 'not json' > "$SG/matrix/category#2_topic#1.json"
out="$(STATE_DIR="$SG" bash "$FOLD" 2>&1)"; rc=$?
assert_eq "G8 an invalid cell file aborts the fold" "1" "$rc"

# =========================================================================== H
echo "-- H: production state/ untouched"
assert_eq "H1 production state/ byte-identical before and after" "$STATE_BEFORE" "$(snapshot)"

echo ""
echo "== test_matrix_harvest.sh: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ] || exit 1
exit 0
