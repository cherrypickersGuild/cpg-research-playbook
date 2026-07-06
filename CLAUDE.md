# CLAUDE.md — AX → Samsung executive deck pipeline

This project turns a corpus of AI-transformation ("AX") cases into a vetted executive slide deck through four ordered stages. **Validation is a hard gate: never select or present a case that has not passed validation.**

Pipeline order and where each spec lives:
1. Case Finder — `agents/01_case_finder.md` → `ax_case_db.json`
2. Case Integrity Validator — `agents/02_validator.md` → adds `gate_passed`
3. AX Case Selector — `agents/03_selector.md` → main + appendix (gate-passed only)
4. Executive Slide Builder — `agents/04_slide_builder.md` → `deck_plan.json`

Shared rules carried through every stage: named company · concrete before/after workflow · measurable KPI traceable to a source · transformation date kept separate from publication date · vendor-only claims labeled unverified · contradictory-evidence check · unknown fields written as `"unknown"`, never invented.

To run the whole thing non-interactively: `bash scripts/run_pipeline.sh` (edit `pipeline.config.sh` first). Outputs land in `runs/<timestamp>/outputs/`, logs in `runs/<timestamp>/logs/`, newest run symlinked at `runs/latest/`.

When asked to run a single stage interactively, use the matching subagent in `.claude/agents/` (e.g. `ax-validator`) and pass the input file path explicitly.
