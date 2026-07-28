# HANDOFF — current state

**Pointer file. Read this first.** Durable snapshot:
`docs/harvest/handoffs/HANDOFF_STAGE_2_5_COMPLETE_2026-07-28.md`

Last updated: **2026-07-28**, in the session that implemented and verified Stage 2.5. Branch `main`.

```text
verified_code_checkpoint:    46ab67cde36acf4b2b403d17d4bc589eff3d5cb7   Stage 2.5 implementation
documentation_approval:      79389e1460a13492fcdc42ab8c96af5313ad9bca   approved plan
stage_0_2_implementation:    0edbf50a0d9d7283cf6f1e6cd823ea55d04c8e5e
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34   protected-baseline anchor
push_state:                  local only — nothing pushed to origin/main
document_status:             updated after the Stage 2.5 implementation commit
```

`verified_code_checkpoint` is the commit whose **code** was verified, not a claim about what `HEAD`
will be after this document is itself committed. Committing documentation advances `HEAD`; it does
not advance the code checkpoint.

---

## Status

| | |
|---|---|
| **Stages 0–2** | **Implemented and tested** at `0edbf50` — 199 assertions, 7 suites |
| **Stage 2.5** (case facets + shared discovery) | **COMPLETE** at `46ab67c` — 188 new assertions, 7 new suites |
| **Total** | **387 assertions across 14 suites, all green** |
| Protected baseline | **passing** — 18 files byte-match Git's rendering of `8865c54e…` |
| Exact 12-cell taxonomy | **unchanged** — facets create no cells |
| Tracked modifications after `46ab67c` | **zero** |
| Untracked files | exactly the original **508**, all byte-unchanged |
| **Stage 3** onward | **NOT STARTED — blocked.** Not approved for implementation |
| Live harvest / migration / refresh / link-check / promotion | **None performed** |
| Pushed | **No** — nothing has been pushed |

---

## Next action

**Produce and get approval for a Stage 3 implementation plan.** Stage 3 is *not* approved for
implementation; the entry conditions are §18 of the durable handoff. In short, a new session must
independently verify this state, rerun the trust-establishing checks, review the Stage 3 scope
against the actual Stage 2.5 interfaces, present a plan, and receive explicit approval before editing
any file.

Design and approval artifacts are **frozen** and must not be rewritten to restate history:
`docs/harvest/DOMAIN_FACETS_PROPOSAL.md` (revision 4 + §16 Errata) ·
`docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md`. They were implemented by `46ab67c` with **no plan
deviations**, except the separately approved request-key correction (durable handoff §9).

---

## Verify the state you inherited

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"

git rev-parse HEAD                                   # code checkpoint 46ab67c (+ any doc commits)
git log --oneline -5                                 # 46ab67c · 79389e1 · 3b85a81 · 0edbf50 · 8865c54
git status --short --untracked-files=all             # 508 lines, all '??'
git log --oneline origin/main..HEAD                  # unpushed — nothing has been pushed

bash scripts/harvest/verify_protected_baseline.sh    # 18 protected files unchanged
git diff --stat 8865c54 HEAD -- .gitignore           # must be exactly 1 insertion(+)

for t in protected_baseline config identity schema http domain_throttle budget \
         facets facet_ambiguity facet_identity facet_states customer_interaction pool coverage; do
  bash "tests/test_taxonomy_${t}.sh"
done
python scripts/harvest/check_facets.py
python scripts/harvest/gen_facet_schema.py --check
python scripts/harvest/check_config.py               # prints cells=12 sources=25
```

---

## Map of what exists

```text
config/harvest/          topics/{cases,research-and-models,discourse}.v1.json  (12 cells, 25 sources)
                         policy · precedence · canonicalization · watchlists · migration_overrides
                         coverage_targets.v1.json
config/harvest/facets/   industries (18) · business-functions (19) · use-case-types (22)
                         legacy_industry_map.v1.json  (reviewed seed, 80 entries)
schemas/harvest/         record · cell_artifact · topic_artifact · run_manifest
                         ledger · rejection · taxonomy · facet_vocabulary
                         facets.generated (GENERATED) · candidate_pool · discovery_lane
                         coverage_report                                    (all .v1.json)
src/harvest/             slug · urlkey · records · schema · budget · domainlease · httpclient
                         facets · pool · coverage · scheduler · request_key
scripts/harvest/         hash_tree · protected_baseline (+2 wrappers) · check_config
                         gen_facet_schema · check_facets
tests/                   test_taxonomy_*.sh  (14 wrappers)
tests/harvest/           test_identity · test_schema · test_http · test_budget · test_domain_throttle
                         test_facets · test_facet_ambiguity · test_facet_identity · test_facet_states
                         test_customer_interaction · test_pool · test_coverage · throttle_worker
docs/harvest/            IMPLEMENTATION_PLAN · TODO · INVENTORY_AND_REUSE_MAP
                         DOMAIN_FACETS_PROPOSAL · STAGE_2_5_IMPLEMENTATION_PLAN
                         FACET_VOCABULARY · HANDOFF_CURRENT · handoffs/
```

Not yet created: `src/harvest/adapters/`, `src/harvest/migrate/`, `scripts/harvest/harvest.sh`,
`tests/fixtures/harvest/`, `data/harvested/`, and any `state/taxonomy_harvest/` run.

---

## Seven invariants — do not break

1. 18 protected files stay byte-identical (`verify_protected_baseline.sh`).
2. `.gitignore` carries exactly one added line vs `8865c54`: `/state/taxonomy_harvest/`.
3. `APPROVED_CELLS` (12) in `check_config.py` is the specification, never derived from the config —
   and `check_config.py` itself stays **byte-unchanged** (DV-1).
4. 508 pre-existing untracked files stay byte-identical; a clean `git status` is **not** required.
5. `case_facets` never touches `record_id`, `content_id`, `identity_url`, `cell_id` or a published
   filename. `urlkey.py` and `slug.py` must not even mention facets.
6. Query normalization is **opt-in per request** (`query_order_policy`, default `preserve`). Adapter
   class never enables sorting; repeated-key value order and multiplicity stay significant.
7. Stage 3 stays blocked until a new session verifies this state, presents a plan, and receives
   explicit approval.

---

## Traps already paid for (see `INVENTORY_AND_REUSE_MAP.md` §5 and the durable handoff §15)

- Working tree is **mixed** CRLF/LF; the baseline pins `eol_form` per file for this reason. Expect
  `LF will be replaced by CRLF` warnings on `git add` — noise, not a problem.
- `urllib.robotparser` is **not** RFC 9309 — we ship our own matcher.
- `os.kill(pid, 0)` reports dead processes as **alive** on Windows.
- Git Bash `/tmp` paths are invisible to native Python; Python prints CRLF into `$(...)`.
- `schema.py::_build_registry()` loads **every** `*.json` in `schemas/harvest/` into one cached
  registry — a malformed or duplicate-`$id` file there breaks all 14 suites, not just its own.
- The guard hook blocks piping a protected command into `head`/`grep`/`sed`/`awk`/`tee`, and blocks
  broad recursive `rm`. Write to a temp file, then inspect it.
- `safe_commit.sh` fails closed on a non-empty index and verifies the staged set exactly equals the
  requested set. Name files explicitly.
