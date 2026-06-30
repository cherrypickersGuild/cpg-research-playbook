# AX → Samsung Executive Deck — Pipeline Overview

Four agents run in sequence. Each consumes the prior agent's JSON and emits its own. Validation is a **hard gate**: no case reaches selection until it passes.

```
Stage 1  Case Discovery        → ax_case_db.json          (the ≥200-case corpus)
   │     sub-pipeline: 1A Strategy Builder → 1B Crawl Executor → 1C Case Extractor;
   │     1D Refresh Scheduler closes the loop (re-search stale keywords);
   │     persistent stores in state/. See agents/stage1/00_discovery_overview.md
   │
Stage 2  Case Integrity Validator → validated_cases.json   (pass / caveat / review / reject)
   │     ── VALIDATION GATE: only pass + pass_with_caveat continue ──
Stage 3  AX Case Selector       → selected_cases.json       (Samsung-scored; main + appendix)
   │
Stage 4  Executive Slide Builder → deck_plan.json → .pptx   (narrative + slides + source appendix)
```

Why this shape, and where I split or merged your spec:

- **Validator is its own agent and a gate, not a step.** Selecting before validating lets impressive-but-weak cases through, exactly as you noted. The gate lives at the validator's output: `reject` and `manual_review` cases are held back; only `pass` / `pass_with_caveat` flow on.
- **Relevance Selector + Executive Case Curator → one Selector agent.** Scoring relevance and choosing the 6–10 main / 10–20 appendix cases are the same decision; splitting them just hands a ranked list across a boundary and re-reads it. The Selector scores *and* curates.
- **Narrative Planner + Slide Builder + Source Appendix Builder → one Slide Builder agent.** The narrative is the deck's spine and the slides realize it from shared state; the appendix is derived from already-validated sources. Splitting these multiplies lossy handoffs. The Slide Builder plans the storyline first, then emits a slide-by-slide JSON (incl. appendix) that `python-pptx` renders. If you later want parallelism, the narrative step is the clean seam to cut.

## Shared run configuration
All agents read one config so thresholds and dates can't drift between stages.

```yaml
date_filter:                      # inherited from the Case Finder run; the Validator re-checks against it
  transformation_date_range: { start: "2023-01-01", end: "TODAY" }
  publication_date_range:    { start: "2024-01-01", end: "TODAY" }
  out_of_window_policy: "reject"        # reject | flag_low_confidence | include_as_context
  classic_cases_allowed_in: "appendix"  # where pre-2023 predictive-ML cases may still appear

selection_thresholds:
  main_deck_min_confidence: 0.80        # after validation
  appendix_min_confidence:  0.65
  main_deck_count:   { min: 6,  max: 10 }
  appendix_count:    { min: 10, max: 20 }

audience:
  org: "Samsung Electronics"
  level: "executives"
  lecture_goal: ""                      # fill per engagement
  time_limit_min: 60
  themes: ["semiconductor/manufacturing", "R&D", "software dev", "supply chain",
           "enterprise knowledge work", "device support", "governance/failure"]
```

## Data contract between stages
- Stage 2 adds a `validation` block to each case but **never rewrites case facts** — it annotates, flags, and scores `confidence_after_validation`. Provenance from Stage 1 is preserved.
- Stage 3 reads only gate-passed cases, adds `samsung_relevance` scoring and a `selection` verdict (`main` / `appendix` / `not_selected`).
- Stage 4 reads selected cases + their validated sources and emits `deck_plan.json`. Every slide references the `case_id`s and `source.id`s it rests on, so the appendix and citations are generated, not retyped.

## Non-negotiables carried through every stage
Named company · concrete before/after workflow · measurable KPI traceable to a source · separate transformation vs publication dates · vendor-only claims labeled unverified · contradictory-evidence check · unknown fields written as `"unknown"`, never invented.
