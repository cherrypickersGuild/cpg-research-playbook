# Stage 1E — Category Discovery

## Mission
Find topics worth tracking that `SEED_TOPICS` doesn't cover yet, and propose them — never activate
them yourself. This is the mechanism for growing the pipeline beyond its initial five topics
(`agent`, `mcp`, `prompt`, `skill`, `AX cases`) over time, without letting scope creep in unreviewed.

## Inputs
- `state/search_hits.json` (and its per-topic shards) — recurring terms in real hit titles/snippets.
- `state/community_strategy_db.json` / `niche_strategy_db.json`'s `discovery_candidates[]` — community
  discovery already surfaces adjacent themes as a side effect; this agent mines that array too.
- `state/category_registry.json` (read and augment; create with `{"categories": []}` if absent).
- The current `SEED_TOPICS` list (so you don't re-propose an already-active category).
- Optional: a small batch of broad discovery searches (see Query Bank below) when the existing corpus
  doesn't have enough signal on its own.

## Procedure
1. **Mine existing signal first** (cheap, no new crawling): scan hit titles/snippets and
   `discovery_candidates[].topics` for terms that recur across **at least 3 independent hits or
   candidates** and are not a synonym of an existing active category (e.g. don't propose "AI agents"
   as distinct from `agent`).
2. **Run the Query Bank** (below) for a small supplementary search pass — this catches genuinely new
   terms that haven't shown up in existing hits yet, especially fast-moving product/framework names.
3. For each candidate term, write a `category_registry.json` entry with `status: "candidate"`,
   `evidence[]` citing the specific hit_ids/candidate_ids/queries that surfaced it, and a one-line
   `label`. Never fabricate evidence — if you can't point to at least 3 concrete occurrences, don't
   propose it.
4. **Never set `status: "active"` yourself.** That happens only when a human reviews the entry and
   changes it — at which point 1A/1A-community pick the new `category_id` up as a topic on their next
   run (append it to `SEED_TOPICS`).
5. If a term was previously `rejected`, do not re-propose it unless new evidence volume is
   substantially higher than at rejection time (note the comparison in `reviewer_notes` if you do).

## Query Bank
```
"emerging" AI agent trend 2026 -site:reddit.com
new AI agent framework OR protocol OR standard 2026
"what's next for" AI agents OR LLM tooling 2026
AI agent category "hasn't been covered" OR "underrated" 2026
```
Use sparingly — this stage should mostly run off signal already collected by 1B/1F, not fresh crawling.

## Output — `category_registry.json` (full file, you augment it)
```json
{
  "categories": [
    {
      "category_id": "agent-memory",
      "label": "Agent memory / long-context systems",
      "status": "candidate",
      "first_observed_at": "2026-07-06",
      "promoted_at": null,
      "evidence": [
        { "type": "recurring_term", "source": "search_hits.json", "count": 4, "sample_hit_ids": ["hit-2026-0210", "hit-2026-0233"] }
      ],
      "reviewer_notes": "",
      "rejected_reason": null
    }
  ]
}
```

## Rules
- Never promote a candidate to `active` — that is a human decision, always.
- Never delete a `rejected` entry — keeping it prevents re-proposing the same declined idea every cycle.
- A candidate needs ≥3 independent evidence points; if you only have 1-2, keep gathering rather than
  proposing a thin category.
- Return JSON only (the full updated `category_registry.json`). No prose, no fences.
