#!/usr/bin/env bash
# clean_json.sh — defines clean(): robustly turn a nested `claude -p` result
# string on stdin into a single clean JSON object/array on stdout, or fail
# (non-zero) so the caller's retry / fail-loud machinery kicks in.
#
# Why this exists: `claude --output-format json` returns a valid envelope, but
# its .result text sometimes wraps the intended JSON in a prose preamble/suffix
# (or Markdown fences) despite "Output ONLY JSON, no prose, no fences". The old
# `sed '/^```/d' | jq .` only stripped fences, so any stray prose made jq fail
# and the whole batch was rejected (observed: candidate-batch failing all 3
# retries, registry left untouched — see the agent smoke run).
#
# clean() reads ALL of stdin and:
#   1. strips Markdown fence lines (``` and ```json);
#   2. extracts every TOP-LEVEL {...} / [...] value with a string/escape-aware
#      scanner, so braces/brackets INSIDE JSON strings never split a value and
#      the naive "first { to last }" pitfall is avoided;
#   3. validates each extracted candidate with `jq empty`, keeping only valid
#      JSON values;
#   4. emits the single valid value (pretty-printed by jq) ONLY if EXACTLY one
#      was found. Zero valid values (no/only-malformed JSON) or two-or-more
#      (ambiguous) -> return non-zero, emit nothing.
#
# It never touches any registry/ledger: callers pipe clean() -> a temp batch
# file and merge only on success, so a parse failure is fail-loud and leaves
# canonical state byte-for-byte unchanged.
#
# Requires: jq, awk (GNU or POSIX), bash 4.4+ (for read -d '').
clean() {
  local input cand n=0 out=""
  input="$(cat)"
  # strip Markdown fence lines (opening ```json / plain ``` and closing ```)
  input="$(printf '%s' "$input" | sed '/^[[:space:]]*```/d')"
  # String/escape-aware scan: emit each complete top-level {...}/[...] value,
  # NUL-separated. Braces inside strings are ignored (depth only moves outside
  # of string context); backslash escapes inside strings are honored.
  while IFS= read -r -d '' cand; do
    [ -n "$cand" ] || continue
    printf '%s' "$cand" | jq empty 2>/dev/null || continue
    # Ignore trivial EMPTY containers ([] / {}). These are almost always stray
    # fragments the scanner lifts out of the model's prose preamble — e.g. the
    # literal "attempted_urls[]" that both harvest prompts mention — never the
    # intended payload (every caller expects a NON-empty object: {"hits":...},
    # {entities,ledger_patch}, {cases}). Counting them would collide with the
    # real object and trip the exactly-one ambiguity guard below, failing a
    # perfectly good batch. A genuine two-real-payloads case still has two
    # NON-empty values and is still rejected as ambiguous.
    printf '%s' "$cand" | jq -e '(type=="array" or type=="object") and (length==0)' >/dev/null 2>&1 && continue
    n=$((n + 1))
    out="$cand"
  done < <(printf '%s' "$input" | awk '
    BEGIN { depth=0; instr=0; esc=0; cap=0; buf="" }
    {
      line=$0; L=length(line)
      for (i=1;i<=L;i++) {
        c=substr(line,i,1)
        if (esc)   { esc=0; if (cap) buf=buf c; continue }
        if (instr) {
          if (c=="\\") esc=1; else if (c=="\"") instr=0
          if (cap) buf=buf c; continue
        }
        if (c=="\"") { instr=1; if (cap) buf=buf c; continue }
        if (c=="{" || c=="[") {
          if (depth==0 && !cap) { cap=1; buf="" }
          depth++
          if (cap) buf=buf c
          continue
        }
        if (c=="}" || c=="]") {
          if (depth>0) {
            if (cap) buf=buf c
            depth--
            if (depth==0 && cap) { printf "%s%c", buf, 0; cap=0; buf="" }
          }
          continue
        }
        if (cap) buf=buf c
      }
      if (cap) buf=buf "\n"   # preserve newlines inside a multi-line value
    }
  ')
  [ "$n" -eq 1 ] || return 1
  printf '%s' "$out" | jq .
}
