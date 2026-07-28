#!/usr/bin/env python3
"""check_config.py — validate the taxonomy configuration before anything runs.

Fails loudly when:
  * a source object omits any of its nine required fields (the config is read
    per-source, so an implicitly inherited value is an unstated assumption);
  * a source's topic_slug/category_slug disagree with the category it sits in;
  * a source_id or fixture_id is duplicated;
  * a url is not absolute;
  * a display name does not round-trip through the slugifier;
  * the configured cell set is not EXACTLY the 12 approved categories;
  * a topic file does not validate against schemas/harvest/taxonomy.v1.json.

  Usage:
    python scripts/harvest/check_config.py [--topics-dir DIR] [--quiet]

Exit 0: configuration is complete and exact. Exit 1: any problem (all reported).
"""
import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest.slug import slugify, SlugError  # noqa: E402
from src.harvest import schema as schema_mod      # noqa: E402

REQUIRED_SOURCE_FIELDS = [
    "source_id", "topic_slug", "category_slug", "adapter", "url",
    "role", "max_candidates", "max_requests", "fixture_id",
]

# The approved taxonomy. Hard-coded on purpose: this is the specification the
# configuration is checked AGAINST, so deriving it from the configuration would
# make the check vacuous.
APPROVED_CELLS = {
    "cases__domain-applications",
    "cases__case-studies",
    "cases__product-discovery",
    "research-and-models__model-updates",
    "research-and-models__papers",
    "research-and-models__benchmark-and-datasets",
    "discourse__regulations-policy-compliance",
    "discourse__community",
    "discourse__big-tech-trends",
    "discourse__market-and-investment",
    "discourse__technical-deep-dives",
    "discourse__insights-and-opinions",
}


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate the taxonomy configuration.")
    p.add_argument("--topics-dir", default=os.path.join(ROOT, "config", "harvest", "topics"))
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    problems = []
    cells = []
    source_ids = {}
    fixture_ids = {}
    n_sources = 0

    files = sorted(glob.glob(os.path.join(args.topics_dir, "*.v1.json")))
    if not files:
        print("ERROR: no topic config files under %s" % args.topics_dir, file=sys.stderr)
        return 1

    for f in files:
        rel = os.path.relpath(f, ROOT)
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except ValueError as exc:
            problems.append("%s: not valid JSON (%s)" % (rel, exc))
            continue

        for err in schema_mod.validate(doc, "taxonomy.v1.json", label=rel):
            problems.append(err)

        topic = doc.get("topic", "")
        tslug = doc.get("topic_slug", "")
        try:
            if slugify(topic) != tslug:
                problems.append("%s: topic %r slugifies to %r, but topic_slug is %r"
                                % (rel, topic, slugify(topic), tslug))
        except SlugError as exc:
            problems.append("%s: topic %r is not slug-able (%s)" % (rel, topic, exc))

        for cat in doc.get("categories", []):
            cname = cat.get("category", "")
            cslug = cat.get("category_slug", "")
            try:
                if slugify(cname) != cslug:
                    problems.append("%s: category %r slugifies to %r, but category_slug is %r"
                                    % (rel, cname, slugify(cname), cslug))
            except SlugError as exc:
                problems.append("%s: category %r is not slug-able (%s)" % (rel, cname, exc))

            cell = "%s__%s" % (tslug, cslug)
            cells.append(cell)

            for s in cat.get("sources", []):
                n_sources += 1
                sid = s.get("source_id", "<no source_id>")

                for k in REQUIRED_SOURCE_FIELDS:
                    if k not in s or s[k] in (None, "", []):
                        problems.append("%s: source %s is missing required field %r"
                                        % (rel, sid, k))

                if s.get("topic_slug") != tslug:
                    problems.append("%s: source %s has topic_slug %r but sits under %r"
                                    % (rel, sid, s.get("topic_slug"), tslug))
                if s.get("category_slug") != cslug:
                    problems.append("%s: source %s has category_slug %r but sits under %r"
                                    % (rel, sid, s.get("category_slug"), cslug))

                url = s.get("url", "")
                if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                    problems.append("%s: source %s url is not absolute: %r" % (rel, sid, url))

                if sid in source_ids:
                    problems.append("%s: duplicate source_id %r (also in %s)"
                                    % (rel, sid, source_ids[sid]))
                else:
                    source_ids[sid] = rel

                fx = s.get("fixture_id")
                if fx:
                    if fx in fixture_ids:
                        problems.append("%s: duplicate fixture_id %r (also in %s)"
                                        % (rel, fx, fixture_ids[fx]))
                    else:
                        fixture_ids[fx] = rel

                if s.get("adapter") == "seed":
                    seed = s.get("seed") or {}
                    if seed.get("mode") == "index" and not seed.get("path_prefix_allowlist"):
                        problems.append(
                            "%s: source %s is a seed index with an empty path_prefix_allowlist. "
                            "That fails closed (no child qualifies) — if intended, say so, but it "
                            "is almost always a mistake." % (rel, sid))

    # exact cell-set comparison
    got = set(cells)
    if len(cells) != len(got):
        dupes = sorted({c for c in cells if cells.count(c) > 1})
        problems.append("duplicate cells configured: %s" % ", ".join(dupes))
    for missing in sorted(APPROVED_CELLS - got):
        problems.append("MISSING approved cell: %s" % missing)
    for extra in sorted(got - APPROVED_CELLS):
        problems.append("UNEXPECTED cell not in the approved taxonomy: %s" % extra)

    if problems:
        for p_ in problems:
            print("ERROR: %s" % p_, file=sys.stderr)
        print("ERROR: configuration check FAILED (%d problem(s))." % len(problems), file=sys.stderr)
        return 1

    if not args.quiet:
        print("[config] OK — cells=%d sources=%d topics=%d (matches the approved taxonomy exactly)"
              % (len(got), n_sources, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
