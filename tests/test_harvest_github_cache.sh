#!/usr/bin/env bash
# test_harvest_github_cache.sh — offline integration test: the harvest prefetches
# GitHub metadata deterministically (scripts/github_meta.py) and feeds the
# sanitized local file to 1G, so the 1G agent no longer calls api.github.com per
# repo. Uses a MOCK claude + temp STATE_DIR, and PRE-SEEDS a fresh GitHub cache so
# the prefetch is a pure cache read (ZERO network, no real rate limit consumed).
# Asserts: GH_META is produced from cache and passed to 1G; the 1G prompt no
# longer instructs fetching api.github.com; no token leaks into cache/meta/args/
# logs; and the real production state/*.json are byte-identical before/after.
#   Usage: bash tests/test_harvest_github_cache.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENT="$ROOT/scripts/harvest_entities.sh"
TMP="$(mktemp -d)"; trap '[ -n "${TMP:-}" ] && rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   - $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
asrt(){ if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2] got [$3])"; fi; }

REPO_URL="https://github.com/exampletestorg/exampletestrepo"
KEY="exampletestorg/exampletestrepo"
CAPTURE="$TMP/extract_args.txt"

# --- mock claude: candidate emits a github target_url; extract captures its args
MOCK="$TMP/mock_claude.sh"
cat > "$MOCK" <<MOCK_EOF
#!/usr/bin/env bash
set -u
args="\$*"
emit(){ printf '{"result": %s}\n' "\$(printf '%s' "\$1" | jq -Rs .)"; }
is_extract="no"; case "\$args" in *"--append-system-prompt"*) is_extract="yes" ;; esac
if [ "\$is_extract" = "no" ]; then
  emit '{"hits":[{"source_url":"https://example.com/c","target_url":"$REPO_URL","title":"t","snippet":"s","domain":"github.com"}]}'
  exit 0
fi
printf '%s' "\$args" > "$CAPTURE"
emit '{"entities":[{"topic":"prompt","entity_type":"library","name":"exampletestrepo","entity_key":"prompt|exampletestrepo","source_url":"https://example.com/c","target_url":"$REPO_URL","description":"d","description_source":"verified","github_stars":null}],"ledger_patch":[{"url":"https://example.com/c","entity_extracted":true,"entity_ids":["x"]}]}'
exit 0
MOCK_EOF
chmod +x "$MOCK"

STATE="$TMP/state"; mkdir -p "$STATE"
echo '{"schema_version":2,"last_merged_at":null,"metadata":{},"entities":[]}' > "$STATE/entity_registry.json"
echo '{"ledger":[]}' > "$STATE/visited_url_ledger.json"
# pre-seed a FRESH cache entry -> prefetch is a pure cache read (0 network calls)
NOW="$(python -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
cat > "$STATE/github_meta_cache.json" <<CACHE
{"repos":{"$KEY":{"status":"ok","stars":4242,"canonical_url":"$REPO_URL","archived":false,"pushed_at":"2026-07-01T00:00:00Z","fetched_at":"$NOW"}}}
CACHE

# real-state protection: snapshot BEFORE
declare -A HB
for f in entity_registry.json visited_url_ledger.json; do HB[$f]="$(git -C "$ROOT" hash-object "state/$f" 2>/dev/null || echo MISSING)"; done
PB="$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

# run one bounded loop, unauthenticated (env token vars stripped)
STATE_DIR="$STATE" CLAUDE_BIN="$MOCK" BATCH_SIZE=5 CANDIDATE_ATTEMPTS=1 ONEG_ATTEMPTS=1 \
  MAX_LOOPS=2 NO_PROGRESS_THRESHOLD=1 \
  env -u GITHUB_TOKEN -u GH_TOKEN bash "$ENT" prompt 1 >/dev/null 2>&1 || true

GM="$STATE/harvest_prompt_github_meta.json"
echo "[integration] deterministic prefetch -> GH_META -> 1G (no api.github.com)"
[ -f "$GM" ] && ok "GH_META file created" || bad "GH_META file missing"
if jq empty "$GM" 2>/dev/null; then ok "GH_META valid JSON"; else bad "GH_META invalid JSON"; fi
asrt "GH_META carries the seeded stars from cache (zero network)" "4242" "$(jq -r --arg k "$KEY" '.repos[$k].stars // "MISSING"' "$GM" 2>/dev/null)"
if grep -qF "$GM" "$CAPTURE" 2>/dev/null; then ok "1G call received the GH_META path"; else bad "1G call did NOT receive GH_META path"; fi
if grep -qE 'fetch https?://api\.github\.com' "$CAPTURE" 2>/dev/null; then bad "1G prompt still instructs fetching api.github.com"; else ok "1G prompt no longer instructs fetching api.github.com"; fi

# no token / bearer header anywhere it could leak
LEAK=0
for f in "$STATE/github_meta_cache.json" "$GM" "$CAPTURE" "$STATE/harvest_prompt.err"; do
  [ -f "$f" ] && grep -qiE 'ghp_[A-Za-z0-9]|gho_[A-Za-z0-9]|github_pat_|authorization:|bearer ' "$f" && LEAK=1
done
asrt "no token/authorization header in cache/meta/args/logs" "0" "$LEAK"

echo "[safety] production state/*.json + git status unchanged"
for f in entity_registry.json visited_url_ledger.json; do
  asrt "unchanged: state/$f" "${HB[$f]}" "$(git -C "$ROOT" hash-object "state/$f" 2>/dev/null || echo MISSING)"
done
asrt "git status --porcelain state/ unchanged" "$PB" "$(git -C "$ROOT" status --porcelain state/ 2>/dev/null)"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
