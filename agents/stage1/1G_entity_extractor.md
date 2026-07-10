# Stage 1G — Entity Extractor

## Mission
1C extracts **AX transformation cases** from hits (named company + workflow change + KPI). This agent
is 1C's sibling: it reads the **same hits**, independently, and where a hit describes a concrete,
nameable *thing* — a specific agent framework, MCP server, prompt technique/library, or skill — it
extracts a structured entity record instead. Note that the Hit schema (see `1B_crawl_executor.md`)
carries no `topic` field — a hit's originating query topic is not a reliable filter, and isn't needed:
exactly like 1C, this stage decides purely from the page's own content, not from which query surfaced
it. A single hit can yield a case (1C), an entity (1G), both, or neither — the two extractors run
independently over the same hits and never need to agree with each other.

## Inputs
- The same Hit list 1C reads: `state/hits.json` (or the in-flight batch passed by the orchestrator —
  `news_hits.json` from 1F, or 1B's fresh output).
- `state/visited_url_ledger.json` — tracks `entity_extracted`/`entity_ids` **separately** from 1C's
  `extracted`/`case_ids` on the same ledger row (a hit can be case-processed, entity-processed, both, or
  neither — these are independent passes over the same URL).
- `state/entity_registry.json` (read for context only; do not merge here — `merge_entity_registry.sh`
  owns the merge, exactly as `merge_case_db.sh` owns case merging).

## Procedure
1. For each hit with `entity_extracted: false` (or not yet in the ledger under that flag), read the
   content and decide: does this page describe **one specific, nameable thing** worth cataloging (a
   named agent framework, a named MCP server, a named prompt technique/library, a named skill) — as
   opposed to a general news article, opinion piece, or a page that only mentions such a thing in
   passing? Assign `topic` yourself from what the page actually is (`agent` / `mcp` / `prompt` /
   `skill`), not from any query metadata.
2. **If yes** → extract an entity record (schema below). Pull the description from the entity's OWN
   primary page (`target_url`, see step 6), not from the search snippet and not from the citing page
   (`source_url`); if `target_url` cannot be fetched or confidently resolved, fall back to the
   citing page's content and mark `description_source: "snippet-only"`.
3. **If no** → do not fabricate an entity. Still mark the ledger row `entity_extracted: true,
   entity_ids: []` so it's recorded as processed and never re-examined for entity extraction (1C's own
   `extracted`/`case_ids` fields on the same row are untouched by this step).
4. Assign `entity_type` from the topic's enum (below) based on what the page actually describes; use
   `"other"` if none fit rather than forcing a bad match.
5. Compute `entity_key` = `topic + "|" + normalized(name)` (lowercase, collapsed whitespace) — this is
   the identity `merge_entity_registry.sh` dedups on, mirroring how `merge_case_db.sh` uses `case_key`.
6. **Two URL fields, two independent fetches.** Every entity carries `source_url` (the URL that
   surfaced this entity — the citing/seed page, e.g., an awesome-list row, a search-hit page, a
   news article) and `target_url` (the entity's OWN official/primary page — its repo, docs page,
   model card, package page, paper, or official product page). These are independent fetches:
   - Fetch `source_url` to read the citing page when the hit content is what you need to decide
     whether this is an entity at all.
   - Separately fetch `target_url` to confirm it's really the entity's primary page and to pull the
     description from there. `description_source: "verified"` means the description came from
     `target_url` specifically — never from `source_url`, never from the snippet alone. If
     `target_url` cannot be fetched or confidently resolved, write `"unknown"` for `target_url` and
     set `description_source: "snippet-only"` (do not promote a citing-page description to
     `verified`).
7. **Echo `source_url` in `ledger_patch[].url`** so the merge step can match the ledger row that was
   seeded from the candidate batch (the ledger's own key is the visited/fetched URL, which for the
   harvest path is the candidate's `source_url`). For the 1B/1F Hit shape used by `discover.sh`,
   where the hit has `news_url`/`source_url` fields of its own, `source_url` on the entity is the
   hit's `news_url` (the specific article that was crawled) — same rule, "the URL that was actually
   fetched to find this entity."
8. **`github_stars` — only from a confirmed GitHub repo, never inferred.** After resolving
   `target_url` (step 6), check whether it points at a GitHub repository root
   (`https://github.com/<owner>/<repo>`, not a gist, an org page, an issue, a file path, or any
   other GitHub URL shape). If, and only if, it does:
   - Fetch `https://api.github.com/repos/<owner>/<repo>` and read `stargazers_count` — prefer the
     API over scraping the rendered repo page, since the API gives an exact integer instead of an
     abbreviated/rounded display string (`"12.4k"`).
   - Set `github_stars` to that integer, the count **as of this fetch** — it is a live number, not
     a one-time fact; a later corroborating run is expected to report a different (typically
     higher) value, and that is a fresh, correct measurement, not a conflict.
   - If the API call fails or the count can't be confidently read, set `github_stars: null`.
   If `target_url` is not a GitHub repo root — including `"unknown"`, a non-GitHub domain, or any
   other GitHub URL shape — set `github_stars: null` and do not attempt to estimate a count from
   anywhere else (a mention like "10k+ GitHub stars" on the entity's own product page or in a
   citing article is not a measurement; leave it out of `github_stars` and, if you want to keep it
   at all, it belongs in `freshness_signal` as prose, same as today).

## `entity_type` enum by topic
| topic | entity_type values |
|---|---|
| `agent` | `framework` \| `platform` \| `product` \| `benchmark` \| `dataset` \| `other` |
| `mcp` | `server` \| `client_sdk` \| `framework` \| `registry` \| `other` |
| `prompt` | `technique` \| `library` \| `tool` \| `guide` \| `dataset` \| `other` |
| `skill` | `skill` \| `marketplace` \| `guide` \| `spec` \| `other` |

## Output — entity batch (consumed by `merge_entity_registry.sh`, same shape as 1C's ledger_patch pairing)
```json
{
  "entities": [
    {
      "entity_id": "ent-2026-0001",
      "topic": "mcp",
      "entity_type": "server",
      "name": "example-mcp-server",
      "source_url": "https://raw.githubusercontent.com/github/awesome-mcp-servers/main/README.md",
      "target_url": "https://github.com/example/example-mcp-server",
      "description": "Verified from the repo README: an MCP server exposing X to Y via Z.",
      "description_source": "verified",
      "maintainer_or_vendor": "Example Org",
      "freshness_signal": "last commit 2026-06-30",
      "github_stars": 4213,
      "related_topics": ["agent"],
      "found_via": { "hit_id": "hit-2026-0210", "platform": "web" }
    }
  ],
  "ledger_patch": [
    { "url": "https://raw.githubusercontent.com/github/awesome-mcp-servers/main/README.md", "entity_extracted": true, "entity_ids": ["ent-2026-0001"] }
  ]
}
```

## Rules
- Do not extract cases here — that's still 1C's job; if a hit is really an AX transformation story
  rather than a description of a specific tool, leave it to 1C and don't force an entity out of it.
- Never invent a description, maintainer, freshness signal, or `target_url`; unknown -> `"unknown"`.
  In particular, never default `target_url` to `source_url` to fill the field — a citing page (an
  awesome-list row, a search-hit page, a news article) is NOT the entity's own primary page.
- `github_stars` is `null`, never `"unknown"` — it is a number-or-nothing field, not a string field
  with the rest of the schema's `"unknown"` sentinel. Never invent or estimate it; never populate it
  from anything other than a direct fetch of the GitHub API for a confirmed repo-root `target_url`.
- One entity per (topic x name) — if a hit describes something already extracted this run, merge into
  the same in-batch entity rather than emitting a duplicate (cross-run dedup is `merge_entity_registry.sh`'s
  job, but avoid obvious in-run duplicates yourself).
- `entity_extracted`/`entity_ids` are this stage's ledger fields; never write to `extracted`/`case_ids`
  (those belong to 1C) and never read them to decide whether to skip a hit.
- Return JSON only. No prose, no fences.
