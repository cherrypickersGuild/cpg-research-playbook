#!/usr/bin/env python3
"""matrix_spec.py — turn a typed list of categories and topics into a cell manifest.

The matrix harvest works on CELLS. A cell is one (category, topic) pair, and it
owns every file written for it, which is what lets all cells run concurrently:

    categories: healthcare, finance        topics: agent, rag
        -> category#1_topic#1  (healthcare x agent)
           category#1_topic#2  (healthcare x rag)
           category#2_topic#1  (finance    x agent)
           category#2_topic#2  (finance    x rag)

`i` and `j` are 1-based indices into the categories and topics lists AS GIVEN.
That is the whole contract behind the `category#i_topic#j.json` filenames, and it
means the order you type the lists in is significant: reordering them renames
every cell. The manifest exists so nothing has to guess — it records which name
each index refers to, and every cell file repeats its own category/topic inside.

  Usage:
    python scripts/matrix_spec.py --categories "healthcare,finance" \
                                  --topics "agent,rag" [--state DIR] [--out-json]
    python scripts/matrix_spec.py --spec matrix.json [--state DIR]

  A --spec file is {"categories":[...], "topics":[...], "pairs":[[i,j],...]}
  where `pairs` is optional and restricts the run to a subset of cells (the full
  cross product is the default).

  Writes <state>/matrix/manifest.json and prints one TAB-separated line per cell:
      i <TAB> j <TAB> category <TAB> topic <TAB> cell_id

  Exit 0: manifest written. Exit 1: bad or ambiguous input.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

# Names go into filenames only as indices, but they also go into prompts and JSON,
# so keep them printable, trimmed, and free of the characters that would break a
# shell word or a path if someone later derives a filename from a name.
BAD_NAME = re.compile(r'[\x00-\x1f/\\<>:"|?*]')


def parse_list(raw):
    """Split a comma-separated list, trim, drop empties, preserve order."""
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def validate_names(kind, names):
    """Reject what would silently corrupt a cell identity later."""
    if not names:
        return ["no %s given — the matrix would have zero cells" % kind]
    errs = []
    for n in names:
        if BAD_NAME.search(n):
            errs.append("%s %r contains a control or path-reserved character" % (kind, n))
        if len(n) > 120:
            errs.append("%s %r is longer than 120 characters" % (kind, n))
    # Duplicates are fatal, not deduped: two identical categories would produce two
    # cells with different indices harvesting the same thing into different files,
    # and the duplicate work would look like real coverage in the summary.
    seen = {}
    for idx, n in enumerate(names, 1):
        k = n.casefold()
        if k in seen:
            errs.append("%s %r appears twice (positions %d and %d) — "
                        "that would harvest the same thing into two cells"
                        % (kind, n, seen[k], idx))
        seen[k] = idx
    return errs


def build(categories, topics, pairs=None):
    cells = []
    wanted = None
    if pairs is not None:
        wanted = {(int(a), int(b)) for a, b in pairs}
    for i, cat in enumerate(categories, 1):
        for j, top in enumerate(topics, 1):
            if wanted is not None and (i, j) not in wanted:
                continue
            cid = "category#%d_topic#%d" % (i, j)
            cells.append({
                "i": i, "j": j, "category": cat, "topic": top, "cell_id": cid,
                "harvest_file": "%s.json" % cid,
                "queries_file": "queries_%s.json" % cid,
            })
    return cells


def atomic_write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_matrix_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description="Build a (category x topic) cell manifest.")
    p.add_argument("--categories", help="comma-separated category list, in order")
    p.add_argument("--topics", help="comma-separated topic list, in order")
    p.add_argument("--spec", help='JSON file: {"categories":[...],"topics":[...],"pairs":[[i,j],...]}')
    p.add_argument("--state", default=None, help="state directory (default: <repo>/state)")
    p.add_argument("--out-json", action="store_true", help="print the manifest as JSON instead of TSV")
    args = p.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state = args.state or os.environ.get("STATE_DIR") or os.path.join(root, "state")

    pairs = None
    if args.spec:
        if args.categories or args.topics:
            print("ERROR: --spec cannot be combined with --categories/--topics.", file=sys.stderr)
            return 1
        try:
            with open(args.spec, "r", encoding="utf-8") as f:
                spec = json.load(f)
        except (OSError, ValueError) as exc:
            print("ERROR: cannot read spec %s: %s" % (args.spec, exc), file=sys.stderr)
            return 1
        categories = list(spec.get("categories") or [])
        topics = list(spec.get("topics") or [])
        pairs = spec.get("pairs")
    else:
        categories = parse_list(args.categories)
        topics = parse_list(args.topics)

    errs = validate_names("category", categories) + validate_names("topic", topics)
    if errs:
        for e in errs:
            print("ERROR: %s" % e, file=sys.stderr)
        return 1

    if pairs is not None:
        for pr in pairs:
            if (not isinstance(pr, (list, tuple)) or len(pr) != 2):
                print("ERROR: each entry of `pairs` must be [i, j]; got %r" % (pr,), file=sys.stderr)
                return 1
            i, j = pr
            if not (1 <= int(i) <= len(categories)) or not (1 <= int(j) <= len(topics)):
                print("ERROR: pair [%s, %s] is out of range (categories 1..%d, topics 1..%d)"
                      % (i, j, len(categories), len(topics)), file=sys.stderr)
                return 1

    cells = build(categories, topics, pairs)
    if not cells:
        print("ERROR: the spec selected zero cells.", file=sys.stderr)
        return 1

    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": [{"index": i, "name": c} for i, c in enumerate(categories, 1)],
        "topics": [{"index": j, "name": t} for j, t in enumerate(topics, 1)],
        "cell_count": len(cells),
        "cells": cells,
    }
    atomic_write_json(os.path.join(state, "matrix", "manifest.json"), manifest)

    if args.out_json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        for c in cells:
            print("%d\t%d\t%s\t%s\t%s" % (c["i"], c["j"], c["category"], c["topic"], c["cell_id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
