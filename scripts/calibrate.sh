#!/usr/bin/env bash
# calibrate.sh — reads a finished (or partial) run and prints the numbers you
# need to set the knobs in pipeline.config.sh: validation outcomes, the gate
# pass-rate, a confidence histogram of the gate-passed set, headroom vs your
# current thresholds, suggested thresholds for ~1.75x headroom, and pattern /
# failure coverage.
#
#   Usage:  bash calibrate.sh [runs/<id>]      (defaults to the newest run)
#
# Needs only stages 1-2 to have run (02_validated.json, ideally 01_case_db.json).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/pipeline.config.sh"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found. Install jq first."; exit 1; }

# --- resolve the run folder --------------------------------------------------
if [ -n "${1:-}" ]; then RUN_DIR="$1"
elif [ -e "$ROOT/runs/latest" ]; then RUN_DIR="$(readlink -f "$ROOT/runs/latest" 2>/dev/null || echo "$ROOT/runs/latest")"
else RUN_DIR="$(ls -1dt "$ROOT"/runs/*/ 2>/dev/null | head -1)"; fi
RUN_DIR="${RUN_DIR%/}"
[ -n "$RUN_DIR" ] && [ -d "$RUN_DIR" ] || { echo "No run folder found. Pass one: bash calibrate.sh runs/<id>"; exit 1; }

VAL="$RUN_DIR/outputs/02_validated.json"
DB="$RUN_DIR/outputs/01_case_db.json"
[ -s "$VAL" ] || { echo "Missing $VAL — run at least stages 1-2 first."; exit 1; }

echo "================ AX pipeline calibration ================"
echo "run: $RUN_DIR"
echo "current config: MAIN>=$MAIN_DECK_MIN_CONFIDENCE (cap $MAIN_DECK_MAX)   APPENDIX>=$APPENDIX_MIN_CONFIDENCE (cap $APPENDIX_MAX)"
echo

# --- 1. validation outcomes / gate pass-rate ---------------------------------
echo "--- 1. validation outcomes ---"
jq -r '
  .results as $r | ($r|length) as $t |
  def c(s): [$r[]|select(.validation_status==s)]|length;
  "  total validated    : \($t)",
  "  pass               : \(c("pass"))",
  "  pass_with_caveat   : \(c("pass_with_caveat"))",
  "  manual_review      : \(c("manual_review"))",
  "  reject             : \(c("reject"))",
  "  gate passed -> sel : \([$r[]|select(.gate_passed==true)]|length) / \($t)"
' "$VAL"
echo

# --- 2. confidence histogram of gate-passed ----------------------------------
echo "--- 2. confidence of gate-passed cases ---"
bar(){ local n="$1" max="$2" w=0; [ "$max" -gt 0 ] && w=$(( n*40/max )); printf '%*s' "$w" '' | tr ' ' '#'; }
ROWS=$(jq -r '
  [.results[]|select(.gate_passed==true)|.confidence_after_validation] as $c |
  ( ["0.90-1.00", ([$c[]|select(.>=0.90)]|length)]
  , ["0.80-0.89", ([$c[]|select(.>=0.80 and .<0.90)]|length)]
  , ["0.70-0.79", ([$c[]|select(.>=0.70 and .<0.80)]|length)]
  , ["0.65-0.69", ([$c[]|select(.>=0.65 and .<0.70)]|length)]
  , ["0.50-0.64", ([$c[]|select(.>=0.50 and .<0.65)]|length)]
  , ["< 0.50",    ([$c[]|select(.<0.50)]|length)]
  ) | "\(.[0])\t\(.[1])"' "$VAL")
maxc=0
while IFS=$'\t' read -r lbl n; do [ "${n:-0}" -gt "$maxc" ] && maxc="$n"; done <<< "$ROWS"
while IFS=$'\t' read -r lbl n; do printf '  %-10s %3d  %s\n' "$lbl" "$n" "$(bar "$n" "$maxc")"; done <<< "$ROWS"
echo

# --- 3. headroom vs current thresholds ---------------------------------------
echo "--- 3. headroom vs current thresholds ---"
read -r GE_MAIN GE_APP TOTGP < <(jq -r \
  --argjson m "$MAIN_DECK_MIN_CONFIDENCE" --argjson a "$APPENDIX_MIN_CONFIDENCE" '
  [.results[]|select(.gate_passed==true)|.confidence_after_validation] as $c |
  "\([$c[]|select(.>=$m)]|length) \([$c[]|select(.>=$a)]|length) \($c|length)"' "$VAL")
hr_main=$(awk -v n="$GE_MAIN" -v d="$MAIN_DECK_MAX" 'BEGIN{ if(d>0) printf "%.2f", n/d; else print "0.00" }')
hr_app=$(awk -v n="$GE_APP"  -v d="$APPENDIX_MAX"  'BEGIN{ if(d>0) printf "%.2f", n/d; else print "0.00" }')
verdict(){ awk -v h="$1" 'BEGIN{ if(h+0>=1.5) print "OK"; else if(h+0>=1.0) print "TIGHT"; else print "LOW (raise sourcing or lower threshold)" }'; }
echo "  main:     $GE_MAIN cases >= $MAIN_DECK_MIN_CONFIDENCE   (cap $MAIN_DECK_MAX)   -> ${hr_main}x  [$(verdict "$hr_main")]"
echo "  appendix: $GE_APP cases >= $APPENDIX_MIN_CONFIDENCE   (cap $APPENDIX_MAX)   -> ${hr_app}x  [$(verdict "$hr_app")]"
echo "  (aim for ~1.5-2x so SELECTION, not confidence, drives the final set)"
echo

# --- 4. suggested thresholds for ~1.75x headroom -----------------------------
echo "--- 4. suggested thresholds for ~1.75x headroom ---"
kmain=$(( (175*MAIN_DECK_MAX + 99)/100 ))
kapp=$(( (175*APPENDIX_MAX + 99)/100 ))
rec(){ jq -r --argjson k "$1" '
  ([.results[]|select(.gate_passed==true)|.confidence_after_validation]|sort|reverse) as $s |
  if ($s|length) >= $k then (($s[$k-1]*100|round)/100|tostring)
  else "n/a (only \($s|length) gate-passed; need \($k))" end' "$VAL"; }
echo "  MAIN_DECK_MIN_CONFIDENCE ~ $(rec "$kmain")   (targets ~$kmain cases vs cap $MAIN_DECK_MAX)"
echo "  APPENDIX_MIN_CONFIDENCE  ~ $(rec "$kapp")    (targets ~$kapp cases vs cap $APPENDIX_MAX)"
echo

# --- 5. pattern + failure coverage of gate-passed ----------------------------
echo "--- 5. coverage of gate-passed set ---"
if [ -s "$DB" ]; then
  jq -r --slurpfile db "$DB" '
    ([.results[]|select(.gate_passed==true)|.case_id]) as $ids |
    (($db[0].cases) // []) as $cases |
    [ $cases[] | select(.case_id as $id | ($ids|index($id))) ] as $g |
    ($g|group_by(.ax_pattern)) as $byp |
    "  distinct patterns : \($byp|length)",
    ($byp[] | "    \(.[0].ax_pattern): \(length)"),
    "  failure cases     : \([$g[]|select(.failure_case==true)]|length)",
    "  gate-passed total : \($g|length)"
  ' "$VAL"
  read -r DP FC < <(jq -r --slurpfile db "$DB" '
    ([.results[]|select(.gate_passed==true)|.case_id]) as $ids |
    (($db[0].cases)//[]) as $cases |
    [ $cases[] | select(.case_id as $id | ($ids|index($id))) ] as $g |
    "\($g|group_by(.ax_pattern)|length) \([$g[]|select(.failure_case==true)]|length)"' "$VAL")
  echo "  verdict: patterns $([ "${DP:-0}" -ge 4 ] && echo OK || echo "WARN (<4)") ; failure cases $([ "${FC:-0}" -ge 1 ] && echo OK || echo "WARN (need >=1)")"
  echo
  echo "--- 6. industry coverage of gate-passed set ---"
  jq -r --slurpfile db "$DB" '
    ([.results[]|select(.gate_passed==true)|.case_id]) as $ids |
    (($db[0].cases) // []) as $cases |
    [ $cases[] | select(.case_id as $id | ($ids|index($id))) ] as $g |
    ($g|length) as $tot |
    if $tot==0 then "  (no gate-passed cases)" else
      ($g | group_by(.industry) | map({ind:(.[0].industry // "unknown"), n:length}) | sort_by(.n) | reverse) as $byi |
      ( "  distinct industries: \($byi|length)"
      , ($byi[] | "    \(.ind): \(.n)  (\( ((.n*100)/$tot)|floor )%)")
      , "  top industry share : \( (($byi[0].n*100)/$tot)|floor )%"
      )
    end
  ' "$VAL"
  read -r DI TS < <(jq -r --slurpfile db "$DB" '
    ([.results[]|select(.gate_passed==true)|.case_id]) as $ids |
    (($db[0].cases)//[]) as $cases |
    [ $cases[] | select(.case_id as $id | ($ids|index($id))) ] as $g |
    ($g|length) as $tot |
    if $tot==0 then "0 0" else
      ($g|group_by(.industry)) as $byi |
      "\($byi|length) \( (((($byi|map(length))|max)*100)/$tot)|floor )"
    end' "$VAL")
  echo "  verdict: industries $([ "${DI:-0}" -ge 6 ] && echo OK || echo "WARN (<6 distinct)") ; concentration $([ "${TS:-0}" -le 35 ] && echo OK || echo "WARN (top ${TS}% > 35%)")"
else
  echo "  (skipped: 01_case_db.json not in this run — pattern/industry coverage needs it)"
fi
echo
echo "Tip: change knobs in pipeline.config.sh, then set RESUME_RUN=$(basename "$RUN_DIR") and FROM_STAGE=3 to re-run selection only."
