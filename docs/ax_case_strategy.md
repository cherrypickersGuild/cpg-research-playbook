# AX case strategy — two separate paths, not merged

This records the decision from the 2026-07-08 audit/design session: **keep the existing rich
case pipeline and a new harvest-style case catalog as two structurally separate paths.** Neither
writes into the other's output file. See `docs/entity_harvest_plan.md` for the sibling document
this mirrors (entities instead of cases).

## 1. Existing rich pipeline (unchanged, not run as part of this work)

- **Output:** `state/ax_case_db.json`
- **Purpose:** the full-fidelity AX case database — company, workflow, KPI with baseline/after/delta,
  source tiers, dates, contradictory-evidence checks. This is the schema Stage 2 (`agents/02_validator.md`)
  hard-requires before a case can reach the Stage 3/4 deck pipeline. Defined in `agents/01_case_finder.md`,
  extracted per-hit by `agents/stage1/1C_case_extractor.md`, persisted by `scripts/merge_case_db.sh`.
- **Current issue #1 — no case-only runner.** No script isolates 1C from the rest of Stage 1.
  `scripts/run_stage1.sh` is the only thing that populates `state/ax_case_db.json`, and it always
  runs the full `1A → 1B → 1C → merge_case_db.sh → 1G → merge_entity_registry.sh` chain — 1C and 1G
  are bundled, never separable.
- **Current issue #2 — touches `entity_registry.json` as a side effect.** Because 1G rides along in
  the same script, any run of `run_stage1.sh` also merges into `state/entity_registry.json`. Case
  *data* never leaks into it (1C and 1G write to structurally separate merge targets), but the file
  grows regardless — an unwanted side effect if the goal is only to collect cases.
- **Do not run this path until `merge_case_db.sh`'s schema drift is fixed.** It has the same defect
  pattern we already found and fixed in `merge_entity_registry.sh` (commit `b6ee7a7`): the new-case
  branch spreads the incoming case object wholesale, so a raw `found_via` persists redundantly
  alongside `discovery.found_via[]`, and `conflicting_evidence_log` is only added on the
  corroboration-match branch, not on first sight. Fix that drift the same way before trusting a real
  `run_stage1.sh` run to produce a clean `ax_case_db.json`.

## 2. New harvest-style AX case path (built)

- **Output / canonical registry:** `state/ax_case_harvest_registry.json` — the single canonical
  AX-case harvest registry: a separate, persistent (tracked, not gitignored) file. Never write case
  data into `entity_registry.json`. The completion metric is the count of cases in this file with
  `verification_status:"verified"`; the target is **≥250** total (final registry total, existing cases
  count toward it — not a number to add). Driven by `scripts/harvest_ax_cases.sh [target=250]` (see
  [`ax_case_harvest_workflow.md`](ax_case_harvest_workflow.md)) or the `scripts/harvest_all.sh`
  orchestrator's final stage.
- **Purpose:** a standalone, lightweight AX case catalog — same role relative to the rich pipeline
  that `entity_registry.json` already plays relative to the rest of Stage 1: a fast, independently
  useful corpus that is explicitly *not* wired into the Stage 2–4 deck pipeline.
- **Isolation rules:**
  - Must not write to `state/entity_registry.json`, ever.
  - Must not modify `state/visited_url_ledger.json` unless a future revision explicitly designs
    that integration — the default is to leave the shared ledger alone, avoiding both the mixing
    risk and any read/write contention with `harvest_entities.sh` or `run_stage1.sh`.
  - Uses its own scratch/log files, named distinctly from the entity-harvest ones (e.g.
    `state/ax_case_harvest_*` for transient batches, mirroring `state/harvest_*`'s gitignore pattern
    rather than reusing it literally).
  - Uses the same JSONL timing-log convention already built for entities: structured events under
    `state/logs/`, e.g. `state/logs/ax_case_harvest_<run_id>.jsonl` (local, transient, gitignored —
    same `state/logs/` rule already in `.gitignore`).

## 3. Proposed case schema

Per case, in `state/ax_case_harvest_registry.json`:

```json
{
  "case_id": "case-2026-0001",
  "case_key": "acme corp|copilot for claims|automated claims triage",
  "company": "Acme Corp",
  "industry": "insurance",
  "workflow_before": "Manual claims triage by a 12-person team, ~3 day turnaround",
  "workflow_after": "Automated claims triage with human review on exceptions only, same-day turnaround",
  "ai_system_or_tool": "Copilot for Claims (in-house, built on Claude)",
  "measurable_kpi": "claims turnaround time",
  "kpi_value": "3 days -> same-day (unknown% reduction, no baseline count disclosed)",
  "evidence_quote": "verbatim quote from the source substantiating the claim",
  "source_url": "https://...",
  "source_title": "How Acme Corp cut claims turnaround with AI",
  "source_domain": "example.com",
  "transformation_date": "2026-02",
  "publication_date": "2026-03-15",
  "confidence": 0.7,
  "verification_status": "verified",
  "discovery": {
    "first_seen_at": "2026-07-08",
    "last_corroborated_at": "2026-07-08",
    "found_via": [{"hit_id": "hit-...", "platform": "custom"}]
  },
  "conflicting_evidence_log": []
}
```

This is deliberately leaner than the rich pipeline's schema — no `kpi[]` baseline/after/delta
objects, no source-tier classification, no contradictory-evidence search per case. That's the
tradeoff for speed/volume; see §5 for how a case can graduate to the rich schema later if needed.

`conflicting_evidence_log` defaults to `[]` and is present on every case from creation — built in
correctly from the start this time, not retrofitted the way `merge_entity_registry.sh` needed to be.

## 4. Dedup key recommendation

```
case_key = normalized(company) + "|" + normalized(ai_system_or_tool) + "|" + normalized(workflow_after)
```

where `normalized(x)` = lowercase, collapsed whitespace, trimmed — the same normalization
`merge_entity_registry.sh` and `merge_case_db.sh` already use for their own keys. This differs from
the rich pipeline's `case_key` (`company|ax_pattern|transformation_date[0:7]`) because the harvest
schema still has no `ax_pattern` — `workflow_after` is the closest analogue to "what changed," and
`ai_system_or_tool` distinguishes two different AI adoptions at the same company doing
similar-sounding work. The lean schema does now carry `transformation_date` (added alongside
`publication_date` so the harvest path follows the same date-separation rule as every other stage),
but `case_key` deliberately does not incorporate it — changing the dedup key formula is a bigger,
separate decision from just adding the field, and is out of scope here. Not yet validated against
real extracted data; revisit if it produces obviously wrong merges (e.g. two distinct case studies
at the same company collapsing into one, or corroborating mentions of the same case failing to
merge).

## 5. Future bridge to the rich schema

Harvested lightweight cases are not automatically eligible for the Stage 2–4 deck pipeline. If a
harvested case turns out to be strong enough to promote:

1. A human (or a dedicated promotion step) re-verifies it against the rich pipeline's inclusion bar
   (named company, concrete workflow, measurable KPI with baseline — see `agents/01_case_finder.md`).
2. Map the lean fields across: `workflow_before`/`workflow_after` → `old_workflow`/`new_ai_workflow`,
   `measurable_kpi`/`kpi_value` → a single `kpi[]` entry (baseline/after/delta filled in only if
   actually verifiable, not inferred), `source_url`/`source_title`/`source_domain` → one `source[]`
   entry with a manually-assigned `tier`.
3. Missing rich-schema fields (`ax_pattern`, `deployment_status`, `evidence_strength`,
   `date_inferred`, etc.) must be filled in for real, or left `"unknown"` — never copied/guessed
   from the lean record. `transformation_date`/`publication_date` carry over directly since both
   schemas already track them the same way (kept separate, `"unknown"` if unstated).
4. The promoted case then enters `state/ax_case_db.json` through the normal `merge_case_db.sh` path,
   with its own fresh `case_key` under that schema's key formula.

This keeps the harvest catalog honest about being a *lead-generation* corpus, not a shortcut into
the validated, deck-ready one.
