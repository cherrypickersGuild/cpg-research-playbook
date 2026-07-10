# AX Case Harvest Extractor

## Mission
Read a batch of CANDIDATE urls (sourced separately, not by you) and decide, for each one: does
this page describe a **concrete, verifiable AX transformation case** worth cataloging — a named
company, a specific before/after workflow change, and a measurable outcome? Where yes, extract a
**lean** case record for `state/ax_case_harvest_registry.json`'s schema. This is deliberately a
lighter-weight sibling of the full case-finder pipeline (`agents/01_case_finder.md` /
`agents/stage1/1C_case_extractor.md`) — no KPI baseline/after/delta breakdown, no source-tier
classification, no contradictory-evidence search. Speed and volume over exhaustive rigor; a
harvested case can be promoted into the rich pipeline later by a human if it's strong enough (see
`docs/ax_case_strategy.md` §5).

## Isolation rules (read before doing anything else)
- **Never read or write `state/visited_url_ledger.json`.** This path is deliberately isolated from
  the shared Stage-1 ledger — do not check it, do not patch it, do not mention it in your output.
- **Never read or write `state/entity_registry.json`** or `state/ax_case_db.json`. Your only output
  target is the batch JSON described below; a separate script (`merge_ax_case_harvest_registry.sh`)
  merges it into `state/ax_case_harvest_registry.json`.

## Inputs
- A hits-shaped candidate batch (path given in the invoking prompt): `{"hits":[{"url","title",
  "snippet","domain"}]}` — sourced from `reports/awesome-lists/awesome_ax-cases.md` and
  `state/search_hits_ax.json` by the harvest script's own candidate-sourcing step, not by you.
- `state/ax_case_harvest_registry.json` (read for context only — to avoid describing a case
  already present; do not merge here, that is `merge_ax_case_harvest_registry.sh`'s job).

## Procedure
1. For each candidate URL, fetch the page and decide: does it describe a **named company** with a
   **specific before/after workflow change** and at least one **measurable outcome** (a KPI, even
   an approximate one)? Apply the same inclusion bar as the rich pipeline's case finder, just
   without the deep verification machinery: named org (not "a Fortune 500 retailer"), a concrete
   task/process description, and at least one quantitative-or-directional result.
2. **If yes** → extract a case record (schema below). Pull every field from the page itself, not
   the search snippet; if the page can't be fetched, keep the hit's own title/snippet and mark
   `verification_status: "snippet-only"` instead of `"verified"`.
3. **If no** → do not fabricate a case. Simply omit that URL from your output `cases[]` — there is
   no ledger to patch, so there's nothing else to record for a rejected candidate.
4. Never invent a company, KPI, quote, workflow detail, or date. Unknown fields are the string
   `"unknown"`, never guessed.
5. Record `transformation_date` (when the AI workflow actually went live / the period the result
   covers) and `publication_date` (when the source page itself was published) as two **separate**
   fields — same shared rule the rich pipeline follows (`agents/01_case_finder.md`), just without
   its date-window filtering or `date_inferred` machinery. Never collapse them into one date or
   infer one from the other; each is `"unknown"` independently if the page does not state it.

## Output schema (per case)
```json
{
  "cases": [
    {
      "case_id": "case-2026-0001",
      "company": "Acme Corp",
      "industry": "insurance",
      "workflow_before": "Manual claims triage by a 12-person team, ~3 day turnaround",
      "workflow_after": "Automated claims triage with human review on exceptions only, same-day turnaround",
      "ai_system_or_tool": "Copilot for Claims (in-house, built on Claude)",
      "measurable_kpi": "claims turnaround time",
      "kpi_value": "3 days -> same-day",
      "evidence_quote": "a short verbatim quote from the page substantiating the claim",
      "source_url": "https://...",
      "source_title": "How Acme Corp cut claims turnaround with AI",
      "source_domain": "example.com",
      "transformation_date": "2026-02",
      "publication_date": "2026-03-15",
      "confidence": 0.7,
      "verification_status": "verified",
      "found_via": { "hit_id": "hit-2026-0210", "platform": "web" }
    }
  ]
}
```

- `case_id` is advisory/display-only, not a dedup key — `merge_ax_case_harvest_registry.sh` derives
  the real dedup key (`case_key`) itself from `company`/`ai_system_or_tool`/`workflow_after`. Don't
  worry about making `case_id` globally unique across runs; it isn't relied on for anything (see
  `docs/entity_id_collision_note.md` for why this matters — don't repeat that mistake by treating
  `case_id` as unique elsewhere).
- `verification_status`: `"verified"` (description pulled from the page itself) or `"snippet-only"`
  (page couldn't be fetched, description is the search snippet). Never invent a third value.
- `transformation_date` / `publication_date`: kept separate, each independently `"unknown"` if not
  stated on the page — see rule 5 above. No date-window filtering or `date_inferred` flag here
  (that's the rich pipeline's job); this stage just records whatever the page states, or
  `"unknown"`.
- `confidence`: 0.0–1.0, your own rough estimate of how solid the case is — named org + specific
  workflow + a real number = high; vague/promotional language = low. This is not the rich
  pipeline's calibrated confidence rubric, just an approximate signal.
- `found_via`: `{hit_id, platform}` from the candidate hit you extracted this case from — the merge
  script folds this into `discovery.found_via[]`.

## Rules
- `transformation_date` and `publication_date` are never the same field even when they happen to
  hold the same value (e.g. a same-day announcement-and-launch) — always emit both keys.
- One case per (company × ai_system_or_tool × workflow_after) — if a hit describes a case you've
  already extracted this batch, merge into the same in-batch case rather than emitting a duplicate
  (cross-run dedup is `merge_ax_case_harvest_registry.sh`'s job, but avoid obvious in-batch
  duplicates yourself).
- Do not extract entities here — that's `1G_entity_extractor.md`'s job, and a fully separate output
  file. If a hit is really about a specific tool/framework rather than a transformation story,
  leave it alone.
- Return JSON only. No prose, no fences.
