# CLAUDE.md — AX → Samsung executive deck pipeline

This project turns a corpus of AI-transformation ("AX") cases into a vetted executive slide deck through four ordered stages. **Validation is a hard gate: never select or present a case that has not passed validation.**

Pipeline order and where each spec lives:
1. Case Finder — `agents/01_case_finder.md` → `ax_case_db.json`
2. Case Integrity Validator — `agents/02_validator.md` → adds `gate_passed`
3. AX Case Selector — `agents/03_selector.md` → main + appendix (gate-passed only)
4. Executive Slide Builder — `agents/04_slide_builder.md` → `deck_plan.json`

Shared rules carried through every stage: named company · concrete before/after workflow · measurable KPI traceable to a source · transformation date kept separate from publication date · vendor-only claims labeled unverified · contradictory-evidence check · unknown fields written as `"unknown"`, never invented.

To run the whole thing non-interactively: `bash scripts/run_pipeline.sh` (edit `pipeline.config.sh` first). Outputs land in `runs/<timestamp>/outputs/`, logs in `runs/<timestamp>/logs/`, newest run symlinked at `runs/latest/`.

## Entity harvest: sharded storage, parallel lanes

Each entity topic owns one file; `state/entity_registry.json` is a **derived union**, never harvested
into directly. This is what makes the four lanes safe to run concurrently — no two writers share a file.

- `agent`→`state/BuildingBlocks_Agent.json` · `mcp`→`BuildingBlocks_MCP.json` · `prompt`→`BuildingBlocks_Prompt.json` · `skill`→`BuildingBlocks_Skill.json` (same schema as the union)
- Ledger and GitHub-metadata cache are sharded per topic too (`visited_url_ledger_<topic>.json`, `github_meta_cache_<topic>.json`).
- Run concurrently: `bash scripts/harvest_parallel.sh` — or one `harvest_entities.sh <topic>` per session.
- Fold to the union when lanes finish: `bash scripts/merge_building_blocks.sh` (single-writer, idempotent, also folds the ledger shards). Both orchestrators do this automatically.
- Advisory locks live in `state/locks/`. Same topic twice = refused; different topics never block.
- Never add a new shared mutable file to the harvest path. If something must be shared, it gets a lock and an atomic write-then-rename via a **unique** temp name — a fixed `<file>.tmp` is a shared name and will interleave.

When asked to run a single stage interactively, use the matching subagent in `.claude/agents/` (e.g. `ax-validator`) and pass the input file path explicitly.

## Autonomous coding safety & repair policy

Gated autonomous coding is configured via `.claude/settings.local.json` and
`.claude/hooks/guard_command.py`. When working autonomously:

- Implement the **smallest** task-related change; keep unrelated code untouched.
- Validate with `bash scripts/validate_task.sh` — the single allowlisted, offline
  validation entry point (isolated temp state, mocked agents, no production writes).
- If validation fails, diagnose and fix defects **directly related** to the task, then
  rerun. Do not pause merely because a directly-related pre-existing defect is exposed.
- Never claim success unless the **latest** `validate_task.sh` run exits 0.
- Commit (only when asked) via `bash scripts/safe_commit.sh -m "…" <explicit files>`;
  never `-A` / `.` / globs. Direct `git add` / `git commit` still prompt.
- Push checks run via `bash scripts/safe_push_main.sh --check`. The actual push
  (`--execute`) and every `git push` always require explicit human approval.
- **Stop and ask** before: pushing, deploying, any external side effect, production
  `state/` writes, anything needing credentials, destructive/irreversible loss of
  unrelated work, or genuinely unrelated scope expansion.
