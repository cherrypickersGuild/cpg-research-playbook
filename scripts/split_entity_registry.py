#!/usr/bin/env python3
"""split_entity_registry.py — derive the per-topic BuildingBlocks shards from the
union registry.

Each entity topic gets a file it EXCLUSIVELY owns, so four harvest lanes can run
concurrently without a single shared mutable registry:

    state/entity_registry.json   (union, single-writer, derived)
        -> state/BuildingBlocks_Agent.json     topic == "agent"
        -> state/BuildingBlocks_MCP.json       topic == "mcp"
        -> state/BuildingBlocks_Prompt.json    topic == "prompt"
        -> state/BuildingBlocks_Skill.json     topic == "skill"

A shard is a strict SUBSET of the union in exactly the same schema (so
merge_entity_registry.sh, the --check tally, and every existing jq query work on
a shard unchanged). `metadata` is recomputed from the shard's own entity list —
never copied from the union — so a shard's counts can never describe rows it
does not contain. One extra top-level field, `topic`, records which slice this
is; nothing reads it as authority, it is a human/debug marker.

Entities whose topic is not one of the four known topics are reported and left
out of every shard (they stay in the union). This is loud on purpose: silently
dropping a row here would silently delete it on the next merge-back.

Idempotent and non-destructive: re-running rewrites the shards from the union.
By default it REFUSES to overwrite a shard that has drifted ahead of the union
(i.e. holds entity_keys the union does not), because that means a harvest lane
wrote to it and the union has not absorbed those rows yet — clobbering it would
lose real harvested work. Use --force to override, or run
merge_building_blocks.sh first to fold the shards back into the union.

  Usage:
    python scripts/split_entity_registry.py [--state DIR] [--force] [--dry-run]

  Exit 0: shards written (or --dry-run reported cleanly).
  Exit 1: bad/missing input, unknown topics found, or drift detected without
          --force.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

TOPICS = {
    "agent": "BuildingBlocks_Agent.json",
    "mcp": "BuildingBlocks_MCP.json",
    "prompt": "BuildingBlocks_Prompt.json",
    "skill": "BuildingBlocks_Skill.json",
}


def entity_key(e):
    """Same key merge_entity_registry.sh derives: entity_key, else topic|lower(name)."""
    k = e.get("entity_key")
    if k:
        return k
    name = (e.get("name") or "unknown").lower().strip()
    name = " ".join(name.split())
    return "%s|%s" % (e.get("topic") or "unknown", name)


def build_shard(topic, entities, now):
    """A shard in the union's exact schema, with metadata recomputed from `entities`."""
    by_type = {}
    for e in entities:
        t = e.get("entity_type")
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "schema_version": 2,
        "topic": topic,
        "last_merged_at": now,
        "metadata": {
            "topics": sorted({e.get("topic") for e in entities if e.get("topic")}),
            "entity_types": sorted(by_type),
            "total_entities": len(entities),
            "entity_count_by_topic": {topic: len(entities)} if entities else {},
            "entity_count_by_entity_type": dict(sorted(by_type.items())),
        },
        "entities": entities,
    }


def atomic_write_json(path, obj):
    """Write via a UNIQUE temp file in the target dir, then replace.

    A unique temp name (not a fixed `<path>.tmp`) matters here: fixed temp paths
    are exactly the concurrency defect this whole change exists to remove.
    """
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_split_", suffix=".json")
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
    p = argparse.ArgumentParser(description="Split entity_registry.json into per-topic BuildingBlocks shards.")
    p.add_argument("--state", default=None, help="state directory (default: <repo>/state)")
    p.add_argument("--force", action="store_true", help="overwrite shards even if they hold rows the union lacks")
    p.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = p.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state = args.state or os.environ.get("STATE_DIR") or os.path.join(root, "state")
    union_path = os.path.join(state, "entity_registry.json")

    if not os.path.isfile(union_path):
        print("ERROR: union registry not found: %s" % union_path, file=sys.stderr)
        return 1
    try:
        with open(union_path, "r", encoding="utf-8") as f:
            union = json.load(f)
    except (OSError, ValueError) as exc:
        print("ERROR: cannot read %s: %s" % (union_path, exc), file=sys.stderr)
        return 1

    entities = union.get("entities") or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    buckets = {t: [] for t in TOPICS}
    unknown = []
    for e in entities:
        t = e.get("topic")
        if t in buckets:
            buckets[t].append(e)
        else:
            unknown.append(e)

    if unknown:
        seen = sorted({str(e.get("topic")) for e in unknown})
        print("ERROR: %d entit(y/ies) carry a topic outside %s: %s"
              % (len(unknown), sorted(TOPICS), seen), file=sys.stderr)
        print("       Refusing to split — they would be dropped from every shard and "
              "then deleted on the next merge-back.", file=sys.stderr)
        return 1

    union_keys = {entity_key(e) for e in entities}

    # Drift guard: a shard holding keys the union does not means a lane harvested
    # into it and the union is stale. Overwriting would destroy that work.
    drifted = []
    for topic, fname in TOPICS.items():
        path = os.path.join(state, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                cur = json.load(f)
        except (OSError, ValueError):
            continue  # unreadable shard is not "ahead"; it will be rebuilt
        ahead = {entity_key(e) for e in (cur.get("entities") or [])} - union_keys
        if ahead:
            drifted.append((fname, len(ahead)))

    if drifted and not args.force:
        print("ERROR: %d shard(s) hold entities the union does not:" % len(drifted), file=sys.stderr)
        for fname, n in drifted:
            print("         %-28s %d unmerged entit(y/ies)" % (fname, n), file=sys.stderr)
        print("       Run: bash scripts/merge_building_blocks.sh   (fold shards -> union)",
              file=sys.stderr)
        print("       or re-run with --force to discard those rows.", file=sys.stderr)
        return 1

    print("union: %s  (%d entities)" % (union_path, len(entities)))
    for topic, fname in TOPICS.items():
        path = os.path.join(state, fname)
        rows = buckets[topic]
        verified = sum(1 for e in rows if e.get("description_source") == "verified")
        if args.dry_run:
            print("  would write %-28s %4d entities (%d verified)" % (fname, len(rows), verified))
            continue
        atomic_write_json(path, build_shard(topic, rows, now))
        print("  wrote %-28s %4d entities (%d verified)" % (fname, len(rows), verified))

    if args.dry_run:
        print("dry-run: nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
