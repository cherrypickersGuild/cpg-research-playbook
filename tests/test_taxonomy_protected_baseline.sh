#!/usr/bin/env bash
# test_taxonomy_protected_baseline.sh — the protected-file baseline must detect
# every way a protected file can change, including the one `git diff` hides.
#
# Runs entirely inside throwaway git repositories under $(mktemp -d), with the
# real repo's protected files never touched. Production state/ is asserted
# byte-identical afterwards, matching the convention in tests/test_*.sh.
#
# Cases proved:
#   A  an unchanged CRLF checkout passes
#   B  a content modification fails
#   C  an LF-only rewrite of a protected CRLF file fails
#      (this is the one that matters: `git diff` normalizes it away and reports
#       the file clean, so a git-diff-only check would pass it)
#   D  a tampered baseline fails
#   E  regeneration without --replace-baseline is refused
#
# Also asserted: the real repository's own baseline verifies, and a file whose
# on-disk form is LF (eol_form=blob) is handled correctly rather than being
# reported as drift.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }

BASELINE_PY="$ROOT/scripts/harvest/protected_baseline.py"

# Git Bash's /tmp/... is an MSYS virtual path. `[ -f ]` resolves it, but native
# Windows Python cannot open it. So every python invocation below first cd's
# into the repo under test and then uses RELATIVE paths only. (The baseline
# script itself is unaffected: it cd's before doing any file I/O.)
pyin() {  # pyin <dir> <python-args...>   — run python with cwd=<dir>
  local d="$1"; shift
  ( cd "$d" && python "$@" )
}

# --------------------------------------------------------------------------
# Build a throwaway repo whose checkout is CRLF (core.autocrlf=true), mirroring
# the real repository's configuration, and commit LF sources into it.
# --------------------------------------------------------------------------
make_repo() {
  local d="$1"
  mkdir -p "$d/scripts" "$d/fixtures"
  git -C "$d" init -q
  git -C "$d" config user.email t@example.com
  git -C "$d" config user.name  T
  git -C "$d" config core.autocrlf true

  printf 'line one\nline two\nline three\n' > "$d/scripts/protected_a.sh"
  printf 'alpha\nbeta\n'                    > "$d/scripts/protected_b.sh"
  printf '{"k":1}\n'                        > "$d/data.json"

  cat > "$d/fixtures/protected_paths.txt" <<'EOF'
scripts/protected_a.sh
scripts/protected_b.sh
data.json
EOF

  git -C "$d" add -A >/dev/null 2>&1
  git -C "$d" commit -q -m base >/dev/null 2>&1
  # Force a real checkout so autocrlf writes CRLF to disk, exactly like a fresh
  # clone would. Without this the files keep the LF bytes we just wrote.
  rm -f "$d/scripts/protected_a.sh" "$d/scripts/protected_b.sh" "$d/data.json"
  git -C "$d" checkout -q -- . >/dev/null 2>&1
  git -C "$d" rev-parse HEAD
}

run_baseline() {  # run_baseline <repo> <commit> <generate|verify> [args...]
  local d="$1" c="$2"; shift 2
  ( cd "$d" && PROTECTED_BASE_COMMIT="$c" \
      PROTECTED_PATHS_FILE="fixtures/protected_paths.txt" \
      PROTECTED_BASELINE="fixtures/protected_sha256.txt" \
      python "$BASELINE_PY" "$@" 2>&1 )
}

echo "=== A. unchanged CRLF checkout passes ==="
D1="$TMPROOT/a"; C1="$(make_repo "$D1")"
CRLF_COUNT="$(pyin "$D1" -c "print(open('scripts/protected_a.sh','rb').read().count(b'\r\n'))")"
assert_eq "checkout really is CRLF (3 CRLF in protected_a.sh)" "3" "$CRLF_COUNT"

OUT="$(run_baseline "$D1" "$C1" generate)"; EC=$?
assert_eq "generate succeeds on a clean tree" "0" "$EC"
assert_contains "generate reports the filtered form" "$OUT" "filtered=3"

OUT="$(run_baseline "$D1" "$C1" verify)"; EC=$?
assert_eq "verify passes on an unchanged CRLF checkout" "0" "$EC"
assert_contains "verify says OK" "$OUT" "byte-match"

echo
echo "=== B. a content modification fails ==="
D2="$TMPROOT/b"; C2="$(make_repo "$D2")"
run_baseline "$D2" "$C2" generate >/dev/null
printf 'line one\r\nCHANGED\r\nline three\r\n' > "$D2/scripts/protected_a.sh"
OUT="$(run_baseline "$D2" "$C2" verify)"; EC=$?
assert_eq "verify fails on a content change" "1" "$EC"
assert_contains "names the changed file" "$OUT" "scripts/protected_a.sh"

echo
echo "=== C. an LF-only rewrite of a protected CRLF file fails ==="
D3="$TMPROOT/c"; C3="$(make_repo "$D3")"
run_baseline "$D3" "$C3" generate >/dev/null
# Rewrite CRLF -> LF, changing nothing else. This is the case a git-diff-only
# check cannot see.
pyin "$D3" - scripts/protected_a.sh <<'PYEOF'
import sys
p = sys.argv[1]
b = open(p, "rb").read()
assert b.count(b"\r\n") > 0, "fixture should start as CRLF"
open(p, "wb").write(b.replace(b"\r\n", b"\n"))
PYEOF
GITDIFF="$(cd "$D3" && git diff --name-only -- scripts/protected_a.sh)"
assert_eq "git diff reports the LF-only rewrite as CLEAN (the blind spot)" "" "$GITDIFF"

OUT="$(run_baseline "$D3" "$C3" verify)"; EC=$?
assert_eq "verify STILL fails on the LF-only rewrite" "1" "$EC"
assert_contains "names the rewritten file" "$OUT" "scripts/protected_a.sh"
assert_contains "diagnoses it as an EOL-only rewrite" "$OUT" "EOL-only rewrite"
assert_contains "explains git diff hides it" "$OUT" "normalizes it away"

echo
echo "=== D. a tampered baseline fails ==="
D4="$TMPROOT/d"; C4="$(make_repo "$D4")"
run_baseline "$D4" "$C4" generate >/dev/null
# Change the file AND rewrite the baseline row to match, i.e. try to bless it.
printf 'line one\r\nTAMPERED\r\nline three\r\n' > "$D4/scripts/protected_a.sh"
pyin "$D4" - <<'PYEOF'
import hashlib
bl = "fixtures/protected_sha256.txt"
new = hashlib.sha256(open("scripts/protected_a.sh", "rb").read()).hexdigest()
out = []
for line in open(bl, encoding="utf-8"):
    if line.startswith("#") or "scripts/protected_a.sh" not in line:
        out.append(line); continue
    parts = [p for p in line.rstrip("\n").split("  ") if p]
    parts[0] = new                      # forge the digest
    out.append("  ".join(parts) + "\n")
open(bl, "w", encoding="utf-8", newline="\n").writelines(out)
PYEOF
OUT="$(run_baseline "$D4" "$C4" verify)"; EC=$?
assert_eq "verify fails even though the baseline was forged to match" "1" "$EC"
assert_contains "reports baseline tampering" "$OUT" "tampered or stale"

echo
echo "=== E. regeneration without --replace-baseline is refused ==="
D5="$TMPROOT/e"; C5="$(make_repo "$D5")"
run_baseline "$D5" "$C5" generate >/dev/null
OUT="$(run_baseline "$D5" "$C5" generate)"; EC=$?
assert_eq "second generate is refused" "1" "$EC"
assert_contains "explains why" "$OUT" "bless itself"
OUT="$(run_baseline "$D5" "$C5" generate --replace-baseline)"; EC=$?
assert_eq "explicit --replace-baseline is allowed" "0" "$EC"

echo
echo "=== F. drift that matches neither rendering is refused at generate ==="
D6="$TMPROOT/f"; C6="$(make_repo "$D6")"
printf 'totally different\r\n' > "$D6/scripts/protected_a.sh"
OUT="$(run_baseline "$D6" "$C6" generate)"; EC=$?
assert_eq "generate refuses a drifted tree" "1" "$EC"
assert_contains "says it matches neither rendering" "$OUT" "NEITHER"

echo
echo "=== G. the real repository's baseline verifies ==="
OUT="$(cd "$ROOT" && bash scripts/harvest/verify_protected_baseline.sh 2>&1)"; EC=$?
assert_eq "real protected baseline verifies" "0" "$EC"
# 10 of the 18 real protected files are LF on disk (eol_form=blob) because they
# were written by tooling rather than by a checkout. That is a pre-existing
# condition, not drift, and must not be reported as drift.
NBLOB="$(awk '$0 !~ /^#/ && NF==4 && $2=="blob"     {n++} END{print n+0}' "$ROOT/tests/fixtures/taxonomy/protected_sha256.txt")"
NFILT="$(awk '$0 !~ /^#/ && NF==4 && $2=="filtered" {n++} END{print n+0}' "$ROOT/tests/fixtures/taxonomy/protected_sha256.txt")"
assert_eq "real baseline records 10 LF-on-disk files"   "10" "$NBLOB"
assert_eq "real baseline records 8 CRLF-on-disk files"  "8"  "$NFILT"

echo
echo "=== H. production state/ untouched by this test ==="
# Tracked changes only. A bare `git status --porcelain -- state/` also lists the
# 56 pre-existing untracked state/_* scratch files that were present at session
# start; those are out of scope and must NOT be treated as drift. Untracked
# paths are covered separately, against tests/fixtures/taxonomy/untracked_baseline.txt.
STATE_DIRTY="$(cd "$ROOT" && git status --porcelain --untracked-files=no -- state/)"
assert_eq "production state/ has no tracked modification" "" "$STATE_DIRTY"

# And no NEW untracked path appeared under state/ either.
NEW_UNTRACKED="$(cd "$ROOT" && python - <<'PYEOF'
import subprocess
now = set(p.decode() for p in subprocess.run(
    ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "state/"],
    capture_output=True, check=True).stdout.split(b"\0") if p)
base = set()
for line in open("tests/fixtures/taxonomy/untracked_baseline.txt", encoding="utf-8"):
    if line.startswith("#") or not line.strip():
        continue
    p = line.rstrip("\n").split("  ", 2)[2]
    if p.startswith("state/"):
        base.add(p)
print("\n".join(sorted(now - base)))
PYEOF
)"
assert_eq "no new untracked path under state/" "" "$NEW_UNTRACKED"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
