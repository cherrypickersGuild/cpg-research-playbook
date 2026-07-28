# HANDOFF — current state

**Pointer file. Read this first.** Durable snapshot:
`docs/harvest/handoffs/HANDOFF_STAGE_2_FACETS_APPROVED_DESIGN_2026-07-28.md`
Next-stage plan: `docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md`

Last updated: **2026-07-28**, in the session that verified the checkpoint below and wrote the Stage
2.5 plan. Branch `main`.

```text
verified_code_checkpoint:    3b85a8102fb89ae0585ef0fc080f518238e4c1bc  (short: 3b85a81)
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34  (short: 8865c54)
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e  (short: 0edbf50)
approved_facet_design:       3b85a8102fb89ae0585ef0fc080f518238e4c1bc  (short: 3b85a81)
push_state:                  local only — nothing pushed to origin/main
document_status:             updated before Stage 2.5 implementation
```

`verified_code_checkpoint` is the commit whose **code** was verified, not a claim about what `HEAD`
will be after this document is itself committed. Committing documentation advances `HEAD`; it does
not advance the code checkpoint. When that happens, the code checkpoint stays `3b85a81` until Stage
2.5 code lands.

---

## Status

| | |
|---|---|
| **Stages 0–2** | **Implemented and tested** at `0edbf50` — 199 assertions, 7 suites, all green |
| **Stage 2.5** (case facets + shared discovery) | **Design approved** at `3b85a81`; **implementation plan approved** (DV-1 … DV-6, D1–D10). **NOT implemented** |
| **Stage 3** onward | **Not started — blocked** |
| Live harvest / migration / refresh / link-check / promotion | **None performed** |
| Committed | **Yes** — `0edbf50` (Stage 0–2 code) and `3b85a81` (approved facet design) |
| Pushed | **No** — the branch is 8 commits ahead of `origin/main`; nothing has been pushed |

The only tracked file modified relative to the implementation-start anchor `8865c54` is
`.gitignore`, by exactly one line.

---

## Next action

**Implement Stage 2.5** per `docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md` (**approved**) and
`docs/harvest/DOMAIN_FACETS_PROPOSAL.md` (**revision 4**, plus its §16 Errata).

**Everything is approved and nothing remains open.** The facet design: R1–R4 and V1–V4. The
implementation plan: deviations DV-1 … DV-6, and the D1–D10 design corrections — including D7, whose
approved form keeps **all five** reporting states explicit, mutually exclusive and separately
counted, with `unmapped_legacy_value` first in precedence, and publication eligibility as a derived
predicate over the **complete record** rather than a persisted flag (plan §8.3, six assertions in
§10).

Vocabulary totals to build: **18 industries · 19 business functions · 22 use-case types**.
Tier splits: **7-8-3 industries · 10-8-1 functions · 10-11-1 use cases**
(the "10/10/1" that appeared in earlier drafts was a typo — see the proposal's Errata).

Stage 3 must not begin until both the existing 199 assertions **and** the new facet suites pass.

---

## Verify the state you inherited

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"

git rev-parse HEAD                                         # code checkpoint: 3b85a81 (+ any doc commits)
git log --oneline -3                                       # 3b85a81 · 0edbf50 · 8865c54
git status --short --untracked-files=all                   # 508 lines, all '??'
git log --oneline origin/main..HEAD                        # unpushed — nothing has been pushed

bash scripts/harvest/verify_protected_baseline.sh          # 18 protected files unchanged
git check-ignore -q state/taxonomy_harvest/probe           # runtime namespace ignored
git diff --stat 8865c54 HEAD -- .gitignore                 # must be exactly 1 insertion(+)

for t in protected_baseline config identity schema http domain_throttle budget; do
  bash "tests/test_taxonomy_${t}.sh"
done
```

---

## Map of what exists

```text
config/harvest/          topics/{cases,research-and-models,discourse}.v1.json  (12 cells, 25 sources)
                         policy · precedence · canonicalization · watchlists · migration_overrides
schemas/harvest/         record · cell_artifact · topic_artifact · run_manifest
                         ledger · rejection · taxonomy   (all .v1.json)
src/harvest/             slug · urlkey · records · schema · budget · domainlease · httpclient
scripts/harvest/         hash_tree · protected_baseline (+2 wrappers) · check_config
tests/                   test_taxonomy_*.sh  (7 wrappers)
tests/harvest/           test_identity · test_schema · test_http · test_budget
                         test_domain_throttle · throttle_worker
tests/fixtures/taxonomy/ protected_paths · protected_sha256 · untracked_baseline
docs/harvest/            IMPLEMENTATION_PLAN · TODO · INVENTORY_AND_REUSE_MAP
                         DOMAIN_FACETS_PROPOSAL · STAGE_2_5_IMPLEMENTATION_PLAN
                         HANDOFF_CURRENT · handoffs/
```

Not yet created: `src/harvest/adapters/`, `pool.py`, `coverage.py`, `scheduler.py`, `facets.py`,
`request_key.py`, `config/harvest/facets/`, `migrate/`, `data/harvested/`, and any
`state/taxonomy_harvest/` run.

---

## Five invariants — do not break

1. 18 protected files stay byte-identical (`verify_protected_baseline.sh`).
2. `.gitignore` carries exactly one added line vs `8865c54`: `/state/taxonomy_harvest/`.
3. `APPROVED_CELLS` (12) in `check_config.py` is the specification, never derived from the config.
4. 508 pre-existing untracked files stay byte-identical; a clean `git status` is **not** required.
5. Stage 3 stays blocked until old and new suites both pass.

---

## Traps already paid for (see `INVENTORY_AND_REUSE_MAP.md` §5)

- Working tree is **mixed** CRLF/LF; the baseline pins `eol_form` per file for this reason.
- `urllib.robotparser` is **not** RFC 9309 — we ship our own matcher.
- `os.kill(pid, 0)` reports dead processes as **alive** on Windows.
- Git Bash `/tmp` paths are invisible to native Python; Python prints CRLF into `$(...)`.
- `schema.py::_build_registry()` loads **every** `*.json` in `schemas/harvest/` into one cached
  registry — a malformed or duplicate-`$id` file there breaks all seven suites, not just its own.
