#!/usr/bin/env bash
# test_taxonomy_config.sh — the taxonomy configuration must be complete and exact.
#
# Two failures this is designed to catch, both of which would otherwise surface
# only during a live run:
#   * a source object missing one of its nine required fields, or inheriting a
#     value implicitly from its category (the config is read per-source, so an
#     inherited value is an unstated assumption);
#   * a configured cell set that is not EXACTLY the 12 approved categories —
#     missing, extra, renamed or misspelled.
#
# Runs offline against the real config files (they are inputs, never mutated),
# plus throwaway malformed copies under $(mktemp -d) to prove the checks fire.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TMPROOT="$(mktemp -d)"
trap '[ -n "${TMPROOT:-}" ] && rm -rf "$TMPROOT"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   - $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
assert_eq()       { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected [$2], got [$3])"; fi; }
assert_contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (output missing: $3)" ;; esac; }

CHECK="scripts/harvest/check_config.py"

# Python on Windows writes CRLF. Command substitution strips the TRAILING
# newline but leaves every interior \r in place, which silently breaks
# multi-line string comparison (the two sides print identically and differ).
# Every capture below goes through this.
pyout() { python "$@" | tr -d '\r'; }

echo "=== A. the real configuration passes every check ==="
OUT="$(python "$CHECK" 2>&1)"; EC=$?
assert_eq "check_config exits 0 on the real config" "0" "$EC"
assert_contains "reports 12 cells" "$OUT" "cells=12"
assert_contains "reports 25 sources" "$OUT" "sources=25"

echo
echo "=== B. every source carries all nine required fields ==="
MISSING="$(pyout - <<'PYEOF'
import json, glob
REQ = ["source_id","topic_slug","category_slug","adapter","url","role",
       "max_candidates","max_requests","fixture_id"]
bad = []
for f in sorted(glob.glob("config/harvest/topics/*.v1.json")):
    d = json.load(open(f, encoding="utf-8"))
    for c in d["categories"]:
        for s in c["sources"]:
            for k in REQ:
                if k not in s or s[k] in (None, "", []):
                    bad.append("%s:%s" % (s.get("source_id","?"), k))
print(",".join(bad))
PYEOF
)"
assert_eq "no source is missing a required field" "" "$MISSING"

echo
echo "=== C. the cell set is exactly the 12 approved categories ==="
CELLS="$(pyout - <<'PYEOF'
import json, glob
out = []
for f in sorted(glob.glob("config/harvest/topics/*.v1.json")):
    d = json.load(open(f, encoding="utf-8"))
    for c in d["categories"]:
        out.append("%s__%s" % (d["topic_slug"], c["category_slug"]))
print("\n".join(sorted(out)))
PYEOF
)"
EXPECTED="cases__case-studies
cases__domain-applications
cases__product-discovery
discourse__big-tech-trends
discourse__community
discourse__insights-and-opinions
discourse__market-and-investment
discourse__regulations-policy-compliance
discourse__technical-deep-dives
research-and-models__benchmark-and-datasets
research-and-models__model-updates
research-and-models__papers"
assert_eq "cell set matches the approved taxonomy exactly" "$EXPECTED" "$CELLS"

echo
echo "=== D. slugs round-trip through the slugifier ==="
SLUGBAD="$(pyout - <<'PYEOF'
import json, glob, sys
sys.path.insert(0, ".")
from src.harvest.slug import slugify
bad = []
for f in sorted(glob.glob("config/harvest/topics/*.v1.json")):
    d = json.load(open(f, encoding="utf-8"))
    if slugify(d["topic"]) != d["topic_slug"]:
        bad.append("%s->%s" % (d["topic"], d["topic_slug"]))
    for c in d["categories"]:
        if slugify(c["category"]) != c["category_slug"]:
            bad.append("%s->%s" % (c["category"], c["category_slug"]))
print(",".join(bad))
PYEOF
)"
assert_eq "every display name slugifies to its declared slug" "" "$SLUGBAD"

echo
echo "=== E. no duplicate source_id or fixture_id ==="
DUPS="$(pyout - <<'PYEOF'
import json, glob, collections
ids, fx = [], []
for f in sorted(glob.glob("config/harvest/topics/*.v1.json")):
    d = json.load(open(f, encoding="utf-8"))
    for c in d["categories"]:
        for s in c["sources"]:
            ids.append(s["source_id"]); fx.append(s["fixture_id"])
dup = [k for k, v in collections.Counter(ids).items() if v > 1]
dup += [k for k, v in collections.Counter(fx).items() if v > 1]
print(",".join(sorted(dup)))
PYEOF
)"
assert_eq "no duplicate ids" "" "$DUPS"

echo
echo "=== F. config validates against schemas/harvest/taxonomy.v1.json ==="
SCHEMA_ERRS="$(pyout - <<'PYEOF'
import glob, sys
sys.path.insert(0, ".")
from src.harvest import schema
errs = []
for f in sorted(glob.glob("config/harvest/topics/*.v1.json")):
    errs += schema.validate_file(f, "taxonomy.v1.json")
print("\n".join(errs))
PYEOF
)"
assert_eq "all topic configs are schema-valid" "" "$SCHEMA_ERRS"

echo
echo "=== G. the checks actually fire on broken config ==="
mkdir -p "$TMPROOT/broken/config/harvest/topics"
cp config/harvest/topics/*.v1.json "$TMPROOT/broken/config/harvest/topics/"

# G1 — drop a required field from one source
python - "$TMPROOT/broken/config/harvest/topics/cases.v1.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
del d["categories"][0]["sources"][0]["max_requests"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
OUT="$(python "$CHECK" --topics-dir "$TMPROOT/broken/config/harvest/topics" 2>&1)"; EC=$?
assert_eq "missing required field is rejected" "1" "$EC"
assert_contains "names the missing field" "$OUT" "max_requests"

# G2 — remove a whole category so the cell set is no longer the approved 12
cp config/harvest/topics/*.v1.json "$TMPROOT/broken/config/harvest/topics/"
python - "$TMPROOT/broken/config/harvest/topics/discourse.v1.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["categories"] = [c for c in d["categories"] if c["category_slug"] != "community"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
OUT="$(python "$CHECK" --topics-dir "$TMPROOT/broken/config/harvest/topics" 2>&1)"; EC=$?
assert_eq "a missing category is rejected" "1" "$EC"
assert_contains "names the missing cell" "$OUT" "discourse__community"

# G3 — an extra category that is not in the approved taxonomy
cp config/harvest/topics/*.v1.json "$TMPROOT/broken/config/harvest/topics/"
python - "$TMPROOT/broken/config/harvest/topics/discourse.v1.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
extra = json.loads(json.dumps(d["categories"][0]))
extra["category"] = "Dev Tools"
extra["category_slug"] = "dev-tools"
for s in extra["sources"]:
    s["category_slug"] = "dev-tools"
    s["source_id"] = s["source_id"] + "-devtools"
    s["fixture_id"] = s["fixture_id"] + "_devtools"
d["categories"].append(extra)
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
OUT="$(python "$CHECK" --topics-dir "$TMPROOT/broken/config/harvest/topics" 2>&1)"; EC=$?
assert_eq "an unapproved extra category is rejected" "1" "$EC"
assert_contains "names the unexpected cell" "$OUT" "dev-tools"

# G4 — a duplicated source_id
cp config/harvest/topics/*.v1.json "$TMPROOT/broken/config/harvest/topics/"
python - "$TMPROOT/broken/config/harvest/topics/cases.v1.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["categories"][1]["sources"][0]["source_id"] = d["categories"][0]["sources"][0]["source_id"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
OUT="$(python "$CHECK" --topics-dir "$TMPROOT/broken/config/harvest/topics" 2>&1)"; EC=$?
assert_eq "a duplicate source_id is rejected" "1" "$EC"
assert_contains "says duplicate" "$OUT" "duplicate"

# G5 — a slug that no longer matches its display name
cp config/harvest/topics/*.v1.json "$TMPROOT/broken/config/harvest/topics/"
python - "$TMPROOT/broken/config/harvest/topics/cases.v1.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["categories"][0]["category_slug"] = "domain-apps"
for s in d["categories"][0]["sources"]:
    s["category_slug"] = "domain-apps"
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
OUT="$(python "$CHECK" --topics-dir "$TMPROOT/broken/config/harvest/topics" 2>&1)"; EC=$?
assert_eq "a slug that does not round-trip is rejected" "1" "$EC"

echo
echo "=== H. the real config files were not modified by this test ==="
DIRTY="$(git status --porcelain --untracked-files=no -- config/)"
assert_eq "config/ has no tracked modification" "" "$DIRTY"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
