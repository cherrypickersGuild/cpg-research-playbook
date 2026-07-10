#!/usr/bin/env bash
# test_harvest_targets.sh — deterministic, OFFLINE tests for the 250-target
# remaining-count / skip logic of the harvest pipeline. Exercises the harvest
# scripts' `--check` mode and the merge scripts only — NO live claude, NO GitHub
# API, NO writes to any real state/*.json (everything runs under a temp STATE_DIR).
#
#   Usage: bash tests/test_harvest_targets.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENT="$ROOT/scripts/harvest_entities.sh"
AX="$ROOT/scripts/harvest_ax_cases.sh"
ALL="$ROOT/scripts/harvest_all.sh"
MERGE_ENT="$ROOT/scripts/merge_entity_registry.sh"
MERGE_AX="$ROOT/scripts/merge_ax_case_harvest_registry.sh"
TMPROOT="$(mktemp -d)"
# Cleanup is scoped strictly to the mktemp dir (never a broad path); guard so an
# unset/empty var can never widen it.
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

# Airtight safety net: force EVERY child harvest invocation (real or --check) to
# use `false` as its "claude", so no code path in this test can ever reach a real
# claude call. --check never invokes claude anyway; the at-target real runs exit
# before their claude call. `command -v false` succeeds, so dependency checks pass.
export CLAUDE_BIN=false

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }

# field <check-line> <key>  ->  value after key=
field() { printf '%s\n' "$1" | grep -oE "$2=[^ ]+" | head -1 | cut -d= -f2; }

# mk_entity_reg <file> <topic> <count> [<topic> <count> ...]  (all "verified")
mk_entity_reg() {
  local file="$1"; shift
  local pairs="[]"
  while [ "$#" -ge 2 ]; do
    pairs="$(jq -c --arg t "$1" --argjson c "$2" '. + [{topic:$t,count:$c}]' <<<"$pairs")"
    shift 2
  done
  # entity_type is included so the merge's metadata block (group_by(.entity_type)
  # | from_entries) never sees a null key — real 1G output always carries it.
  jq -n --argjson pairs "$pairs" '
    { schema_version:2, last_merged_at:null,
      entities: [ $pairs[] as $p | range(0;$p.count)
        | { topic:$p.topic, entity_type:"framework", description_source:"verified",
            name:($p.topic+"-"+(.|tostring)), entity_key:($p.topic+"|e"+(.|tostring)) } ] }' > "$file"
}
# mk_ax_reg <file> <verified_count>
mk_ax_reg() {
  jq -n --argjson n "$2" '
    { schema_version:1, last_merged_at:null,
      cases: [ range(0;$n)
        | { case_key:("c"+(.|tostring)+"|bot|automated"), verification_status:"verified",
            company:("Co"+(.|tostring)) } ] }' > "$1"
}
new_state() { local d="$TMPROOT/state_$1"; mkdir -p "$d"; echo "$d"; }

# ---------------------------------------------------------------------------
echo "[entity] below-target produces a positive remaining count"
d="$(new_state e_below)"; mk_entity_reg "$d/entity_registry.json" agent 100
line="$(STATE_DIR="$d" bash "$ENT" agent 250 --check)"
assert_eq "current=100" "100" "$(field "$line" current)"
assert_eq "remaining=150" "150" "$(field "$line" remaining)"
assert_eq "status incomplete" "incomplete" "$(field "$line" status)"

echo "[entity] 249 still requests more harvesting"
d="$(new_state e_249)"; mk_entity_reg "$d/entity_registry.json" agent 249
line="$(STATE_DIR="$d" bash "$ENT" agent 250 --check)"
assert_eq "remaining=1" "1" "$(field "$line" remaining)"
assert_eq "status incomplete" "incomplete" "$(field "$line" status)"

echo "[entity] 250 skips harvesting (complete)"
d="$(new_state e_250)"; mk_entity_reg "$d/entity_registry.json" agent 250
line="$(STATE_DIR="$d" bash "$ENT" agent 250 --check)"
assert_eq "remaining=0" "0" "$(field "$line" remaining)"
assert_eq "status complete" "complete" "$(field "$line" status)"

echo "[entity] above-250 is complete AND registry is not truncated / no claude launched"
d="$(new_state e_251)"; mk_entity_reg "$d/entity_registry.json" agent 251
before_n="$(jq '.entities|length' "$d/entity_registry.json")"
# real run (not --check) at a target below the current count: must hit target_reached
# on loop 1, never invoke CLAUDE_BIN, and never modify the registry.
STATE_DIR="$d" CLAUDE_BIN=false bash "$ENT" agent 250 >/dev/null 2>&1; ec=$?
after_n="$(jq '.entities|length' "$d/entity_registry.json")"
assert_eq "harvest exited 0 at target" "0" "$ec"
assert_eq "registry not truncated (251 kept)" "$before_n" "$after_n"
assert_eq "251 kept literally" "251" "$after_n"

echo "[entity] counts are independent across the four topics"
d="$(new_state e_indep)"; mk_entity_reg "$d/entity_registry.json" agent 250 mcp 100 prompt 0 skill 300
assert_eq "agent complete"   "complete"   "$(field "$(STATE_DIR="$d" bash "$ENT" agent 250 --check)" status)"
assert_eq "mcp incomplete"   "incomplete" "$(field "$(STATE_DIR="$d" bash "$ENT" mcp 250 --check)" status)"
assert_eq "prompt remaining=250" "250"    "$(field "$(STATE_DIR="$d" bash "$ENT" prompt 250 --check)" remaining)"
assert_eq "skill complete (above)" "complete" "$(field "$(STATE_DIR="$d" bash "$ENT" skill 250 --check)" status)"

echo "[entity] explicit small target override still works"
d="$(new_state e_small)"; mk_entity_reg "$d/entity_registry.json" agent 4
assert_eq "target 3 -> complete" "complete"   "$(field "$(STATE_DIR="$d" bash "$ENT" agent 3 --check)" status)"
assert_eq "target 5 -> incomplete" "incomplete" "$(field "$(STATE_DIR="$d" bash "$ENT" agent 5 --check)" status)"

echo "[entity] duplicate candidates do NOT falsely satisfy the target"
d="$(new_state e_dup)"; mk_entity_reg "$d/entity_registry.json" agent 3
# a batch whose entities all duplicate existing entity_keys — must not raise the unique count
jq -n '{entities:[ range(0;3) | {topic:"agent", entity_type:"framework", description_source:"verified",
        name:("agent-"+(.|tostring)), entity_key:("agent|e"+(.|tostring)),
        target_url:"https://example.com/x"} ]}' > "$d/dup_batch.json"
bash "$MERGE_ENT" "$d/dup_batch.json" "$d/entity_registry.json" >/dev/null
line="$(STATE_DIR="$d" bash "$ENT" agent 10 --check)"
assert_eq "still 3 after merging duplicates" "3" "$(field "$line" current)"
assert_eq "remaining still 7" "7" "$(field "$line" remaining)"

# ---------------------------------------------------------------------------
echo "[ax] empty registry (0) -> remaining = target"
d="$(new_state ax_0)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 0
line="$(STATE_DIR="$d" bash "$AX" 250 --check)"
assert_eq "current=0" "0" "$(field "$line" current)"
assert_eq "remaining=250" "250" "$(field "$line" remaining)"
assert_eq "incomplete" "incomplete" "$(field "$line" status)"

echo "[ax] 249 incomplete, 250 complete, 251 complete (existing cases reduce remaining)"
d="$(new_state ax_249)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 249
assert_eq "249 remaining=1"  "1"          "$(field "$(STATE_DIR="$d" bash "$AX" 250 --check)" remaining)"
d="$(new_state ax_250)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 250
assert_eq "250 complete"     "complete"   "$(field "$(STATE_DIR="$d" bash "$AX" 250 --check)" status)"
d="$(new_state ax_251)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 251
assert_eq "251 complete"     "complete"   "$(field "$(STATE_DIR="$d" bash "$AX" 250 --check)" status)"
assert_eq "251 remaining=0"  "0"          "$(field "$(STATE_DIR="$d" bash "$AX" 250 --check)" remaining)"

echo "[ax] existing merged cases reduce the remaining target"
d="$(new_state ax_partial)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 40
assert_eq "40 -> remaining 210" "210" "$(field "$(STATE_DIR="$d" bash "$AX" 250 --check)" remaining)"

echo "[ax] explicit small target override still works"
d="$(new_state ax_small)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 2
assert_eq "target 3 -> incomplete" "incomplete" "$(field "$(STATE_DIR="$d" bash "$AX" 3 --check)" status)"
assert_eq "target 2 -> complete"   "complete"   "$(field "$(STATE_DIR="$d" bash "$AX" 2 --check)" status)"

echo "[ax] duplicate case_key values do NOT count as progress"
d="$(new_state ax_dup)"; mk_ax_reg "$d/ax_case_harvest_registry.json" 3
# batch of cases duplicating existing case_keys — unique verified count must stay 3
jq -n '{cases:[ range(0;3) | {case_key:("c"+(.|tostring)+"|bot|automated"),
        verification_status:"verified", company:("Co"+(.|tostring))} ]}' > "$d/dup_cases.json"
bash "$MERGE_AX" "$d/dup_cases.json" "$d/ax_case_harvest_registry.json" >/dev/null
line="$(STATE_DIR="$d" bash "$AX" 10 --check)"
assert_eq "still 3 verified after dup merge" "3" "$(field "$line" current)"
assert_eq "remaining still 7" "7" "$(field "$line" remaining)"

# ---------------------------------------------------------------------------
echo "[orchestrator] all stages already at target -> skip all, exit 0, no claude"
d="$(new_state all_done)"
mk_entity_reg "$d/entity_registry.json" agent 2 mcp 2 prompt 2 skill 2
mk_ax_reg "$d/ax_case_harvest_registry.json" 1
STATE_DIR="$d" ENTITY_TARGET=2 AX_TARGET=1 CLAUDE_BIN=false bash "$ALL" --all >/dev/null 2>&1; ec=$?
assert_eq "harvest_all exits 0 when all complete" "0" "$ec"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
