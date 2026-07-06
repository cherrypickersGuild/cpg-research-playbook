# SETUP — running the AX pipeline in Claude Code

This bundle runs four agents in a fixed order, gates out weak cases, logs every step, and saves results in timestamped folders. You don't need to know Claude Code's internals; follow the steps below.

## 1. What's in the bundle
```
ax_pipeline/
├─ scripts/
│   ├─ run_pipeline.sh     # the orchestrator — runs all stages in order
│   └─ calibrate.sh        # prints the numbers for setting the config knobs
├─ pipeline.config.sh      # the ONLY file you normally edit (dates, thresholds, audience)
├─ CLAUDE.md               # project memory (for interactive sessions)
├─ agents/                 # the four agent specs, used as system prompts
│   ├─ 00_pipeline_overview.md
│   ├─ 01_case_finder.md
│   ├─ 02_validator.md
│   ├─ 03_selector.md
│   └─ 04_slide_builder.md
├─ config/
│   └─ ax_case_output_template.json   # reference schema for the case corpus
├─ .claude/
│   ├─ settings.json       # tool permissions, so headless runs don't stall
│   └─ agents/ax-validator.md   # example subagent (interactive alternative)
└─ runs/                   # created automatically; one folder per run
```

## 2. One-time install
Claude Code needs Node.js 18+. Then:
```bash
npm install -g @anthropic-ai/claude-code
claude            # first run logs you in (browser) — do this once
```
Also install `jq` (the script uses it to handle JSON): `brew install jq` / `apt-get install jq`.

## 3. Configure the run
Open `pipeline.config.sh` and set the date window, thresholds, and audience. The important switch:
- `FROM_STAGE=1` also runs the case finder (long — hundreds of searches).
- `FROM_STAGE=2` skips it and starts from a case DB you already have; set `EXISTING_CASE_DB` to that file's path.

Start with `FROM_STAGE=2` and a small hand-made case file to watch the pipeline work end-to-end before committing to a full 200-case finder run.

## 4. Run it
```bash
cd ax_pipeline
bash scripts/run_pipeline.sh
```
That's the whole pipeline. The script will print each stage, its cost, and where the output went.

## 5. Where everything lands (ordered + structured)
Each run gets its own timestamped folder; nothing is ever overwritten:
```
runs/20260626T120000Z/
├─ run.log                 # full timestamped console log
├─ run_config.json         # the exact config this run used (reproducibility)
├─ manifest.json           # summary: counts + total cost + output paths
├─ outputs/
│   ├─ 01_case_db.json
│   ├─ 02_validated.json
│   ├─ 02b_gate_passed.json   # only cases that cleared validation
│   ├─ 03_selected.json
│   └─ 04_deck_plan.json
└─ logs/
    ├─ 02_validator.raw.json  # full headless metadata (cost, session_id, duration)
    └─ 02_validator.err       # stderr if a stage misbehaves
```
`runs/latest` always points at the newest run, so `runs/latest/outputs/04_deck_plan.json` is your deck plan.

## 6. How the hard gate works
Between stage 2 and stage 3 the script runs one line of `jq` that keeps only cases where the validator set `gate_passed = true`, writing `02b_gate_passed.json`. Stage 3 is told to consider only those case_ids. This is *why* it's a script and not loose delegation: the gate is enforced by code, not by a model's discretion. Rejected and manual-review cases stay in `02_validated.json` for your audit but never reach the deck.

## 7. Logging and cost — automatic
Every stage runs with `--output-format json`, whose payload includes `total_cost_usd`, `session_id`, and `duration_ms`; the script saves that to `logs/<stage>.raw.json` and sums the cost into `manifest.json`. The human-readable narrative of the run is in `run.log`. You don't have to add any logging yourself.

## 8. Permissions and auth (so it doesn't hang)
Headless runs stall if a tool needs an approval no one is there to give. Two safeguards are already set:
- `.claude/settings.json` allows exactly the read/search/fetch tools the agents use and denies Bash/Write/Edit (the orchestrator does all file-writing itself, in bash).
- For fully unattended/overnight runs in an **isolated** VM, set `EXTRA_FLAGS="--dangerously-skip-permissions"` in the config. Only do this in a sandbox.

Auth: by default the script uses your interactive login. For CI, set `USE_BARE="true"` and export `ANTHROPIC_API_KEY` (bare mode skips the keychain and bills the API key).

## 9. Calibrating the config knobs
Don't guess the thresholds and counts. Run stages 1–2 once, then:
```bash
bash scripts/calibrate.sh    # reads the newest run (or pass runs/<id>)
```
It prints validation outcomes, the gate pass-rate, a confidence histogram of the gate-passed cases, headroom vs your current `MAIN_DECK_MIN_CONFIDENCE` / `APPENDIX_MIN_CONFIDENCE`, suggested thresholds for ~1.75× headroom, pattern + failure coverage, and industry coverage (with an over-concentration warning). Set counts from your time budget (≈ one case slide per 3–4 min of the talk), set thresholds so ~1.5–2× your deck caps clear them, then re-tune cheaply: change `pipeline.config.sh`, set `RESUME_RUN=<run folder>` and `FROM_STAGE=3`, and re-run selection only.

## 10. Turning the deck plan into a .pptx
Stage 4 outputs structured JSON on purpose — keep the agent out of brittle binary-file work. Render separately with `python-pptx`:
```bash
pip install python-pptx
python render_pptx.py runs/latest/outputs/04_deck_plan.json   # maps each slide to a layout
```
(Ask me to generate `render_pptx.py` against a clean executive template and I'll build it.)

## 11. The interactive alternative (subagents)
If you'd rather drive it by hand instead of via the script, the subagents in `.claude/agents/` let you do that. Open Claude Code in this folder and say, e.g., *"Use the ax-validator subagent on config/ax_case_output_template.json."* Caveat: the model decides when to delegate, so you don't get the enforced gate or the clean per-stage logs the script gives you. Note that **subagent files are loaded at session start — if you edit one on disk, restart the session** (edits made through the `/agents` menu apply immediately). Use the script for repeatable production runs; use subagents for poking at a single stage.

## 12. Troubleshooting
- *A stage's output file is empty or `jq` errors:* the agent likely added prose. Check `logs/<stage>.raw.json` → `.result`; tighten the "JSON only" wording in that agent's spec and re-run.
- *Run hangs:* a tool wasn't permitted — see section 8.
- *Stage 1 never finishes / is huge:* run the finder in batches (by pattern or industry) and concatenate the `cases[]` arrays into one `ax_case_db.json`, then run with `FROM_STAGE=2`.
- *Costs higher than expected:* set a cheaper `MODEL` in the config for the search-heavy stages.
