#!/usr/bin/env python3
"""backfill_entity_target_url.py — evidence-based target_url backfill for
state/entity_registry.json, on top of the source_url/target_url schema split
already applied in commit 118fc0c ("Split entity url into source_url and
target_url"). That commit did a pure, conservative rename: every entity got
source_url = the pre-split ambiguous `url` value verbatim, target_url =
"unknown" always — no backfill attempted, since the per-row intent of the old
`url` field couldn't be determined mechanically at the time.

This script recovers what local evidence actually supports, and corrects one
thing the blanket rename got wrong: for entities originally surfaced through
an awesome-list report, the pre-split `url` was usually already the row's own
curated "Link" cell (the entity's own repo/site) — not the citing/seed page.
The 118fc0c rename put that value in source_url, which is backwards. This
script detects that case from local evidence and swaps it: the row's own link
becomes target_url, and the correct citing evidence (the awesome-list's own
seed README) becomes source_url instead.

Classification per entity, in priority order (matched against the entity's
CURRENT source_url, since that equals the pre-split `url` verbatim for every
row — see 118fc0c):

  (a) awesome-list confirmed — source_url exact/normalized-matches a curated
      "Link" cell in reports/awesome-lists/awesome_<topic>.md, AND that link
      is not itself another awesome-list/collection page (contains "awesome"
      in its path — a companion/curated-list row, not a single entity's own
      product page; excluded per the "don't treat a collection page as a
      target_url" rule). -> target_url = current source_url (the row's own
      link); source_url is CORRECTED to that report's own seed README url
      (extracted from its "List(s) reviewed" section) — the awesome-list page
      itself is source_url, never target_url.
  (b) shared-url conflict — source_url is shared by >=2 entities in the
      registry (evidence against "this is entity X's own official page",
      since two different entities essentially never share one homepage) ->
      target_url stays "unknown"; source_url untouched (already the best
      available guess).
  (c) search-hits confirmed — source_url exact/normalized-matches a literal
      hit url in state/search_hits_<topic>.json (topic-mapped; skill ->
      search_hits_skills.json) -> source_url untouched (confirmed as a real
      collected hit); target_url = source_url only if description_source ==
      "verified" (meaning the raw hit already landed directly on the
      entity's own page).
  (d) legacy fallback — no local evidence either way -> source_url untouched;
      target_url = source_url only if description_source == "verified", per
      the project's documented conservative fallback rule.

Never invents a target_url — cases (b)/(c)/(d) without verified confirmation
always land on "unknown". Read-only unless --apply is passed; --dry-run
(default) only ever prints/writes a report.

Usage:
  python scripts/backfill_entity_target_url.py --dry-run [--report out.json]
  python scripts/backfill_entity_target_url.py --apply [--report out.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "state" / "entity_registry.json"
AWESOME_DIR = ROOT / "reports" / "awesome-lists"
SEARCH_HITS_DIR = ROOT / "state"

TOPIC_TO_AWESOME = {
    "agent": AWESOME_DIR / "awesome_agent.md",
    "mcp": AWESOME_DIR / "awesome_mcp.md",
    "prompt": AWESOME_DIR / "awesome_prompt.md",
    "skill": AWESOME_DIR / "awesome_skill.md",
}
TOPIC_TO_HITS_SHARD = {
    "agent": SEARCH_HITS_DIR / "search_hits_agent.json",
    "mcp": SEARCH_HITS_DIR / "search_hits_mcp.json",
    "prompt": SEARCH_HITS_DIR / "search_hits_prompt.json",
    "skill": SEARCH_HITS_DIR / "search_hits_skills.json",
}

URL_RE = re.compile(r"https?://[^\s()\[\]|<>\"']+")
COLLECTION_RE = re.compile(r"awesome", re.IGNORECASE)


def normalize(url: str) -> str:
    """Conservative normalization: strip fragment, trailing slash, scheme, leading www.
    Never strips query strings or path segments — those can distinguish real pages."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")
    return urlunsplit(("", netloc, path, parts.query, ""))


def extract_urls(text: str):
    return [m.rstrip(".,;:") for m in URL_RE.findall(text)]


def load_awesome_list_corpus(topic: str):
    """Returns (link_urls: set[str], seed_urls: list[str]) for one topic's report.
    link_urls excludes any url that is itself an awesome-list/collection page
    (contains "awesome" in it) — those are never a legitimate target_url."""
    path = TOPIC_TO_AWESOME.get(topic)
    if not path or not path.exists():
        return set(), []
    text = path.read_text(encoding="utf-8")

    seed_urls = []
    m = re.search(r"List\(s\) reviewed:\*\*(.*?)\n---", text, re.S)
    if m:
        seed_urls = extract_urls(m.group(1))

    link_urls = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        for u in extract_urls(cells[1]):
            if COLLECTION_RE.search(u):
                continue  # companion/curated-list link, not a single entity's own page
            link_urls.add(u)

    return link_urls, seed_urls


def load_search_hits_corpus(topic: str):
    path = TOPIC_TO_HITS_SHARD.get(topic)
    if not path or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    urls = set()
    for result in data.get("results", []):
        for hit in result.get("hits", []):
            u = hit.get("url")
            if u:
                urls.add(u)
    return urls


def match(url: str, corpus_exact: set, corpus_norm_map: dict):
    if url in corpus_exact:
        return "exact"
    if normalize(url) in corpus_norm_map:
        return "normalized"
    return None


def classify(entities):
    awesome_corpus = {}
    awesome_seed = {}
    hits_corpus = {}
    for topic in TOPIC_TO_AWESOME:
        links, seeds = load_awesome_list_corpus(topic)
        awesome_corpus[topic] = (links, {normalize(u): u for u in links})
        awesome_seed[topic] = seeds
    for topic in TOPIC_TO_HITS_SHARD:
        urls = load_search_hits_corpus(topic)
        hits_corpus[topic] = (urls, {normalize(u): u for u in urls})

    url_counts = {}
    for e in entities:
        u = e.get("source_url")
        if u and u != "unknown":
            url_counts[u] = url_counts.get(u, 0) + 1

    results = []
    for e in entities:
        source_url = e.get("source_url", "")
        topic = e.get("topic", "unknown")
        shared = url_counts.get(source_url, 0) > 1
        desc_source = e.get("description_source")

        rec = {
            "entity_id": e.get("entity_id"),
            "entity_key": e.get("entity_key"),
            "topic": topic,
            "name": e.get("name"),
            "old_source_url": source_url,
            "description_source": desc_source,
            "shared_url": shared,
            "shared_url_count": url_counts.get(source_url, 0),
            "case": None,
            "evidence": None,
            "new_source_url": source_url,
            "new_target_url": "unknown",
        }

        a_exact, a_norm = awesome_corpus.get(topic, (set(), {}))
        h_exact, h_norm = hits_corpus.get(topic, (set(), {}))

        awesome_match = match(source_url, a_exact, a_norm)
        hits_match = match(source_url, h_exact, h_norm)

        if awesome_match and not shared:
            seeds = awesome_seed.get(topic, [])
            rec["case"] = "a_awesome_list_confirmed"
            rec["evidence"] = {
                "source_kind": "awesome_list",
                "matched_file": TOPIC_TO_AWESOME[topic].relative_to(ROOT).as_posix(),
                "match_method": awesome_match,
            }
            rec["new_target_url"] = source_url  # the row's own link, previously mislabeled as source_url
            rec["new_source_url"] = seeds[0] if seeds else TOPIC_TO_AWESOME[topic].relative_to(ROOT).as_posix()
        elif shared:
            rec["case"] = "b_shared_url_conflict"
            rec["evidence"] = {"source_kind": "shared_url", "matched_file": None, "match_method": None}
            rec["new_target_url"] = "unknown"
            rec["new_source_url"] = source_url  # untouched, already best-available
        elif hits_match:
            rec["case"] = "c_search_hits_confirmed"
            rec["evidence"] = {
                "source_kind": "search_hits",
                "matched_file": TOPIC_TO_HITS_SHARD[topic].relative_to(ROOT).as_posix(),
                "match_method": hits_match,
            }
            rec["new_source_url"] = source_url  # untouched, confirmed correct
            rec["new_target_url"] = source_url if desc_source == "verified" else "unknown"
        else:
            rec["case"] = "d_legacy_fallback"
            rec["evidence"] = {"source_kind": "legacy_fallback", "matched_file": None, "match_method": None}
            rec["new_source_url"] = source_url  # untouched, best available
            rec["new_target_url"] = source_url if desc_source == "verified" else "unknown"

        results.append(rec)

    return results


def build_report(results):
    total = len(results)
    by_case = {}
    for r in results:
        by_case.setdefault(r["case"], []).append(r)

    def sample(case, n=3):
        return by_case.get(case, [])[:n]

    target_filled = sum(1 for r in results if r["new_target_url"] != "unknown")
    target_unknown = total - target_filled
    source_corrected = sum(1 for r in results if r["new_source_url"] != r["old_source_url"])

    report = {
        "total_entities": total,
        "count_by_case": {k: len(v) for k, v in by_case.items()},
        "count_recovered_from_awesome_list": len(by_case.get("a_awesome_list_confirmed", [])),
        "count_recovered_from_search_hits": len(by_case.get("c_search_hits_confirmed", [])),
        "count_shared_url_conflict": len(by_case.get("b_shared_url_conflict", [])),
        "count_legacy_fallback": len(by_case.get("d_legacy_fallback", [])),
        "count_target_url_filled": target_filled,
        "count_target_url_unknown": target_unknown,
        "count_source_url_corrected": source_corrected,
        "samples": {case: sample(case) for case in by_case},
    }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", default=None, help="write the JSON report to this path")
    args = ap.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entities = registry.get("entities", [])
    results = classify(entities)
    report = build_report(results)

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not args.apply:
        print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
        print(f"\nFull report with samples written to: {args.report}" if args.report else "\n(pass --report <path> to save full samples)")
        return

    by_key = {r["entity_key"]: r for r in results}
    for e in entities:
        r = by_key[e["entity_key"]]
        e["source_url"] = r["new_source_url"]
        e["target_url"] = r["new_target_url"]

    REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"Applied backfill to {REGISTRY} ({len(entities)} entities).")


if __name__ == "__main__":
    sys.exit(main())
