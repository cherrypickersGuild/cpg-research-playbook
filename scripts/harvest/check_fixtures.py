#!/usr/bin/env python3
"""check_fixtures.py — the offline fixture corpus is complete and honest.

Deliberately NOT part of check_config.py, which stays byte-unchanged (DV-1) and
whose job is the configuration's own shape. This checks a different thing: that
every configured source and every configured host has a fixture, that the
manifest's bytes and hashes match what is on disk, and that no fixture claims a
provenance it does not have.

Fails when:
  * a configured source has no fixture, or a fixture names no configured source;
  * a fixture's url or source_id disagrees with the configuration;
  * a configured host has no robots fixture keyed by that EXACT host
    (arxiv.org does not cover rss.arxiv.org — robots policy is per origin);
  * a fixture_id or robots host is duplicated;
  * a manifest byte count or SHA-256 does not match the file;
  * a file on disk is missing from the manifest, or vice versa;
  * a synthetic fixture claims `captured_at`, or a recorded one omits it;
  * any manifest path escapes the fixture tree;
  * a target fixture is malformed, duplicated, undeclared, or claims a
    `source_id` or a transport-simulation key (S6-1).

Target fixtures are a DECLARED SET: `TARGET_FIXTURE_IDS` below is the literal
corpus, and both an unexpected file and a missing one fail. A directory is not an
authorization — that is the whole point of listing them here.

Exit 0 and print a one-line summary when everything holds.
"""
import glob
import hashlib
import json
import os
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Imported, never re-listed: the loader that refuses these keys and the checker
# that reports them must mean exactly the same set, and a second copy could only
# drift from the first.
from src.harvest.fixtures import FORBIDDEN_TARGET_KEYS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_ROOT = os.path.join(ROOT, "tests", "fixtures", "harvest")
TOPICS_DIR = os.path.join(ROOT, "config", "harvest", "topics")

# The literal S6-1 target corpus. Each entry maps one-to-one onto a contract case
# in STAGE_6_IMPLEMENTATION_PLAN.md section 11; adding a file without adding it
# here fails, and so does listing one that is not on disk.
TARGET_FIXTURE_IDS = (
    "tgt_accepted_1",
    "tgt_accepted_2",
    "tgt_accepted_3",
    "tgt_accepted_4",
    "tgt_canonical_circular_1",
    "tgt_canonical_circular_2",
    "tgt_canonical_conflicting",
    "tgt_canonical_cross_host",
    "tgt_canonical_same_host",
    "tgt_empty_body",
    "tgt_forbidden",
    "tgt_gone",
    "tgt_non_html_json",
    "tgt_non_html_pdf",
    "tgt_not_found",
    "tgt_ok_plain",
    "tgt_redirect_permanent_1",
    "tgt_redirect_permanent_2",
    "tgt_redirect_permanent_3",
    "tgt_redirect_temporary_1",
    "tgt_redirect_temporary_2",
    "tgt_redirect_temporary_3",
    "tgt_robots_denied",
    "tgt_server_error",
)

# The two robots hosts S6-1 adds. Existing robots fixtures are untouched, so this
# is only the new set, and it is checked for presence rather than exclusivity —
# earlier stages legitimately added hosts of their own.
TARGET_ROBOTS_HOSTS = ("tgt-robots-denied.harvest.test", "tgt.harvest.test")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def configured_sources(topics_dir=None):
    out = []
    for path in sorted(glob.glob(os.path.join(topics_dir or TOPICS_DIR, "*.json"))):
        doc = _load(path)
        for category in doc.get("categories", []):
            out.extend(category.get("sources", []))
    return out


def check(fixture_root=None, topics_dir=None):
    root = fixture_root or FIXTURE_ROOT
    problems = []
    sources_dir = os.path.join(root, "sources")
    robots_dir = os.path.join(root, "robots")
    targets_dir = os.path.join(root, "targets")
    manifest_path = os.path.join(root, "MANIFEST.json")

    for needed in (sources_dir, robots_dir, targets_dir, manifest_path):
        if not os.path.exists(needed):
            return ["missing %s" % os.path.relpath(needed, ROOT)], {}

    sources = configured_sources(topics_dir)
    by_fixture_id = {}
    for source in sources:
        by_fixture_id.setdefault(source["fixture_id"], []).append(source)
    for fixture_id, group in by_fixture_id.items():
        if len(group) > 1:
            problems.append("config: fixture_id %r is claimed by %d sources"
                            % (fixture_id, len(group)))

    # ------------------------------------------------------------- sources
    on_disk, seen_ids = {}, {}
    for path in sorted(glob.glob(os.path.join(sources_dir, "*.json"))):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        fixture = _load(path)
        fixture_id = fixture.get("fixture_id")
        if not fixture_id:
            problems.append("%s: no fixture_id" % rel)
            continue
        if fixture_id in seen_ids:
            problems.append("%s: duplicate fixture_id %r (also %s)"
                            % (rel, fixture_id, seen_ids[fixture_id]))
            continue
        seen_ids[fixture_id] = rel
        on_disk[fixture_id] = (rel, fixture)

    for fixture_id, group in sorted(by_fixture_id.items()):
        source = group[0]
        if fixture_id not in on_disk:
            problems.append("source %r: no fixture %s"
                            % (source["source_id"], "sources/%s.json" % fixture_id))
            continue
        rel, fixture = on_disk[fixture_id]
        if fixture.get("source_id") != source["source_id"]:
            problems.append("%s: source_id %r does not match config %r"
                            % (rel, fixture.get("source_id"), source["source_id"]))
        if fixture.get("url") != source["url"]:
            problems.append("%s: url does not match the configured url" % rel)
        if not fixture.get("body_b64") and not fixture.get("body"):
            problems.append("%s: empty body — a fixture must exercise its adapter" % rel)

    for fixture_id, (rel, _) in sorted(on_disk.items()):
        if fixture_id not in by_fixture_id:
            problems.append("%s: fixture_id %r matches no configured source"
                            % (rel, fixture_id))

    # -------------------------------------------------------------- robots
    robots, seen_hosts = {}, {}
    for path in sorted(glob.glob(os.path.join(robots_dir, "*.json"))):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        fixture = _load(path)
        host = fixture.get("host")
        if not host:
            problems.append("%s: no host" % rel)
            continue
        if host in seen_hosts:
            problems.append("%s: duplicate robots host %r (also %s)"
                            % (rel, host, seen_hosts[host]))
            continue
        seen_hosts[host] = rel
        robots[host] = (rel, fixture)

    configured_hosts = sorted({urlsplit(s["url"]).hostname for s in sources})
    for host in configured_hosts:
        if host not in robots:
            problems.append(
                "configured host %r has no robots fixture. Robots policy is "
                "per origin: a fixture for a parent domain does not cover it." % host)

    for host in TARGET_ROBOTS_HOSTS:
        if host not in robots:
            problems.append("S6-1 robots host %r has no fixture at robots/%s.json"
                            % (host, host))

    # -------------------------------------------------------------- targets
    # A declared set, checked in both directions: a file nobody declared is as
    # much a failure as a declared file that is missing.
    targets, target_urls = {}, {}
    for path in sorted(glob.glob(os.path.join(targets_dir, "*"))):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        name = os.path.basename(path)
        if not name.endswith(".json"):
            problems.append("%s: targets/ holds only declared .json fixtures" % rel)
            continue
        fixture = _load(path)
        fixture_id = fixture.get("fixture_id")
        stem = name[:-len(".json")]
        if fixture_id != stem:
            problems.append("%s: fixture_id %r does not match its filename" % (rel, fixture_id))
            continue
        if stem not in TARGET_FIXTURE_IDS:
            problems.append("%s: undeclared target fixture — add it to "
                            "TARGET_FIXTURE_IDS with its contract, or remove it" % rel)
            continue
        if stem in targets:
            problems.append("%s: duplicate target fixture_id %r" % (rel, stem))
            continue
        targets[stem] = (rel, fixture)

        url = fixture.get("url")
        if not url:
            problems.append("%s: no url" % rel)
        elif url in target_urls:
            problems.append("%s: url %r is already claimed by %s"
                            % (rel, url, target_urls[url]))
        else:
            target_urls[url] = rel
            if url in {s["url"] for s in sources}:
                problems.append("%s: url %r is also a configured source url — one "
                                "URL cannot be both an index and an item page" % (rel, url))
        if "source_id" in fixture:
            problems.append("%s: a target fixture must not claim a source_id" % rel)
        if not isinstance(fixture.get("status"), int) or isinstance(fixture.get("status"), bool):
            problems.append("%s: status must be an integer" % rel)
        if ("body" in fixture) == ("body_b64" in fixture):
            problems.append("%s: exactly one of body or body_b64 must be present" % rel)
        if not fixture.get("contract_intent"):
            problems.append("%s: no contract_intent — a permanent fixture states what "
                            "contract it exists to hold" % rel)
        for key in FORBIDDEN_TARGET_KEYS:
            if key in fixture:
                problems.append(
                    "%s: forbidden transport-simulation key %r. Retries, timeouts and "
                    "the body cap belong to HttpClient and are tested there." % (rel, key))

    for fixture_id in TARGET_FIXTURE_IDS:
        if fixture_id not in targets:
            problems.append("declared target fixture %r is missing at targets/%s.json"
                            % (fixture_id, fixture_id))

    # ---------------------------------------------------------- provenance
    all_fixtures = [(rel, f) for rel, f in on_disk.values()]
    all_fixtures += [(rel, f) for rel, f in robots.values()]
    all_fixtures += [(rel, f) for rel, f in targets.values()]
    for rel, fixture in sorted(all_fixtures):
        provenance = fixture.get("provenance")
        if provenance not in ("synthetic", "recorded"):
            problems.append("%s: provenance must be 'synthetic' or 'recorded', got %r"
                            % (rel, provenance))
            continue
        if provenance == "synthetic":
            if "captured_at" in fixture:
                problems.append("%s: synthetic fixture must not claim captured_at" % rel)
            if not fixture.get("authored_at") or not fixture.get("authored_against"):
                problems.append("%s: synthetic fixture needs authored_at and "
                                "authored_against" % rel)
        else:
            if not fixture.get("captured_at"):
                problems.append("%s: recorded fixture must carry captured_at" % rel)
            if not fixture.get("captured_from"):
                problems.append("%s: recorded fixture must carry captured_from" % rel)

    # ------------------------------------------------------------ manifest
    manifest = _load(manifest_path)
    entries = {e.get("path"): e for e in manifest.get("entries", [])}
    for rel in sorted(entries):
        if rel is None or rel.startswith(("/", "\\")) or ".." in rel.split("/"):
            problems.append("manifest: path %r escapes the fixture tree" % rel)
            continue
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path):
            problems.append("manifest: %s is listed but missing on disk" % rel)
            continue
        # Closed explicitly: harmless when this ran once as a script and exited,
        # but check() is now also called in-process by its own suite, where leaked
        # handles bury a real failure under hundreds of ResourceWarnings.
        with open(path, "rb") as fp:
            raw = fp.read()
        entry = entries[rel]
        if entry.get("bytes") != len(raw):
            problems.append("manifest: %s bytes %r != %d on disk"
                            % (rel, entry.get("bytes"), len(raw)))
        digest = hashlib.sha256(raw).hexdigest()
        if entry.get("sha256") != digest:
            problems.append("manifest: %s sha256 mismatch" % rel)

    for path in sorted(glob.glob(os.path.join(sources_dir, "*.json")) +
                       glob.glob(os.path.join(robots_dir, "*.json")) +
                       glob.glob(os.path.join(targets_dir, "*.json"))):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if rel not in entries:
            problems.append("manifest: %s exists on disk but is not listed" % rel)

    summary = {
        "sources_configured": len(sources),
        "source_fixtures": len(on_disk),
        "configured_hosts": len(configured_hosts),
        "robots_fixtures": len(robots),
        "target_fixtures": len(targets),
        "targets_declared": len(TARGET_FIXTURE_IDS),
        "manifest_entries": len(entries),
    }
    return problems, summary


def main():
    problems, summary = check()
    if problems:
        print("[fixtures] FAILED — %d problem(s):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1
    print("[fixtures] OK — %d/%d configured sources have a fixture; "
          "%d/%d configured hosts have a robots fixture; "
          "%d/%d declared target fixtures present; "
          "%d manifest entries all byte- and hash-matched"
          % (summary["source_fixtures"], summary["sources_configured"],
             summary["configured_hosts"], summary["configured_hosts"],
             summary["target_fixtures"], summary["targets_declared"],
             summary["manifest_entries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
