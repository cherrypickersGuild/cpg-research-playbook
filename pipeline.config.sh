#!/usr/bin/env bash
# pipeline.config.sh — edit before each run, then: bash run_pipeline.sh
# Everything the orchestrator needs lives here so the script itself stays untouched.

# ---- Model (optional). Leave empty to use your default. Cheaper model = lower cost. ----
MODEL=""                      # e.g. "claude-sonnet-4-6" or "" for account default

# ---- Date filter (passed to every stage as config; agents must obey it) ----
TRANSFORMATION_START="2023-01-01"   # widen to e.g. 2017-01-01 to allow classic ML cases
TRANSFORMATION_END="TODAY"
PUBLICATION_START="2024-01-01"
PUBLICATION_END="TODAY"
OUT_OF_WINDOW_POLICY="reject"        # reject | flag_low_confidence | include_as_context
CLASSIC_CASES_ALLOWED_IN="appendix"

# ---- Selection thresholds ----
MAIN_DECK_MIN_CONFIDENCE="0.80"
APPENDIX_MIN_CONFIDENCE="0.65"
MAIN_DECK_MIN=6
MAIN_DECK_MAX=10
APPENDIX_MIN=10
APPENDIX_MAX=20

# ---- Audience ----
AUDIENCE_ORG="Samsung Electronics"
AUDIENCE_LEVEL="executives"
LECTURE_GOAL="Show credible, transferable AI-transformation patterns and the decisions they imply."
TIME_LIMIT_MIN=60

# ---- Pipeline control ----
FROM_STAGE=2                  # which stage to start at: 1 case finder · 2 validator · 3 selector · 4 slide builder
STAGE1_MODE="discovery"       # "discovery" = the 1A-1D sub-pipeline (run_stage1.sh) · "monolith" = single case finder
SEED_TOPICS="agent, mcp, prompt, skills, AX cases"   # comma-separated seed topics for query expansion (1A)
REFRESH_DAYS=90               # closed-cycle threshold: re-search a keyword this many days after its last update (1D)
NEWS_FRESHNESS_WINDOW_DAYS=7   # 1F News Monitor: only emit hits published within this many days (see discover.sh, SEEDING_STRATEGY.md)
EXISTING_CASE_DB=""           # if starting at stage 2 with no prior run, path to a prebuilt ax_case_db.json
RESUME_RUN=""                 # to resume a crashed/stopped run, set this to the run folder name under runs/
                              # (e.g. "20260626T120000Z") and set FROM_STAGE to the stage to restart at.
                              # Earlier stages are reused from their saved files; config stays frozen.

# ---- Auth / permissions ----
USE_BARE="false"              # "true" for CI/unattended (requires ANTHROPIC_API_KEY); "false" uses your login
EXTRA_FLAGS=""                # set to "--dangerously-skip-permissions" ONLY inside an isolated sandbox/VM
