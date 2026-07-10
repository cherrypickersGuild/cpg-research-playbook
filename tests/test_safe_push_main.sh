#!/usr/bin/env bash
# test_safe_push_main.sh — offline tests for scripts/safe_push_main.sh using a
# LOCAL bare remote only. No network, no real remote. Production state/ asserted
# unchanged (content hashes + porcelain), never restored.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SP="$ROOT/scripts/safe_push_main.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   - $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL - $1"; }

prod_snap(){
  git -C "$ROOT" status --porcelain -- state/ 2>/dev/null
  if [ -d "$ROOT/state" ]; then
    find "$ROOT/state" -type f | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git -C "$ROOT" hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
}
PROD_BEFORE="$(prod_snap)"

setup_pair(){   # sets BARE (local bare remote) + WORK (clone on main at c1, pushed)
  BARE="$TMPROOT/bare$RANDOM.git"; WORK="$TMPROOT/work$RANDOM"
  git init -q --bare "$BARE"
  git init -q -b main "$WORK"
  git -C "$WORK" config user.email t@t; git -C "$WORK" config user.name t
  echo c1 > "$WORK/f.txt"; git -C "$WORK" add f.txt; git -C "$WORK" commit -q -m c1
  git -C "$WORK" remote add origin "$BARE"
  git -C "$WORK" push -q -u origin main
}
bare_tip(){ git -C "$BARE" rev-parse main 2>/dev/null; }

echo "[success] --check does not push; --execute pushes"
setup_pair
echo c2 > "$WORK/f.txt"; git -C "$WORK" commit -q -am c2      # local ahead by 1
tip_before="$(bare_tip)"
( cd "$WORK" && bash "$SP" --check >/dev/null 2>&1 ); rc=$?
[ "$rc" -eq 0 ] && ok "--check exit 0 (fast-forwardable)" || bad "--check exit $rc"
[ "$(bare_tip)" = "$tip_before" ] && ok "--check did NOT push (remote tip unchanged)" || bad "--check pushed"
( cd "$WORK" && bash "$SP" --execute >/dev/null 2>&1 ); rc=$?
[ "$rc" -eq 0 ] && ok "--execute exit 0" || bad "--execute exit $rc"
[ "$(bare_tip)" = "$(git -C "$WORK" rev-parse main)" ] && ok "--execute advanced remote to local main" || bad "--execute did not push"
ourl="$(git -C "$WORK" remote get-url origin)"
case "$ourl" in
  http://*|https://*|git@*|ssh://*|git://*) bad "origin is a network remote: $ourl" ;;
  *"$(basename "$BARE")")                   ok "origin is the local bare remote, no network ($ourl)" ;;
  *)                                         bad "origin unexpected: $ourl" ;;
esac

echo "[divergence] origin ahead -> --check stops non-zero, no push"
setup_pair
OTHER="$TMPROOT/other$RANDOM"; git clone -q "$BARE" "$OTHER"
git -C "$OTHER" config user.email t@t; git -C "$OTHER" config user.name t
echo c2other > "$OTHER/f.txt"; git -C "$OTHER" commit -q -am c2other; git -C "$OTHER" push -q origin main
echo c2work > "$WORK/f.txt"; git -C "$WORK" commit -q -am c2work      # WORK diverges
tip_before="$(bare_tip)"
( cd "$WORK" && bash "$SP" --check >/dev/null 2>&1 ); rc=$?
[ "$rc" -ne 0 ] && ok "--check exits non-zero on divergence (exit $rc)" || bad "--check should stop on divergence"
[ "$(bare_tip)" = "$tip_before" ] && ok "no push happened on divergence" || bad "remote changed on divergence"

echo "[branch] refuses when not on main"
setup_pair
git -C "$WORK" checkout -q -b feature
( cd "$WORK" && bash "$SP" --check >/dev/null 2>&1 ); rc=$?
[ "$rc" -eq 3 ] && ok "non-main branch refused (exit 3)" || bad "expected exit 3, got $rc"

cd "$ROOT"
echo "[production] state/ untouched (content hashes + porcelain), not restored"
[ "$(prod_snap)" = "$PROD_BEFORE" ] && ok "production state/ unchanged" || bad "production changed"
echo; echo "=== $PASS passed, $FAIL failed ==="; [ "$FAIL" -eq 0 ]
