# HANDOFF — current state

**Pointer file. Read this first.** Durable snapshot:
`docs/harvest/handoffs/HANDOFF_STAGE_2_FACETS_APPROVED_DESIGN_2026-07-28.md`

Last updated: **2026-07-28** · HEAD `8865c54e2cc8d879410576f247baac4aea149f34` · branch `main`

---

## Status

| | |
|---|---|
| **Stages 0–2** | **Implemented and tested** — 199 assertions, 7 suites, all green |
| **Stage 2.5** (case facets + shared discovery) | **Design approved, NOT implemented** |
| **Stage 3** onward | **Not started — blocked** |
| Live harvest / migration / refresh / link-check / promotion | **None performed** |
| Committed or pushed | **Nothing** |

The only tracked file modified in the whole effort so far is `.gitignore`, by exactly one line.

---

## Next action

Implement **Stage 2.5**, per `docs/harvest/DOMAIN_FACETS_PROPOSAL.md` (revision 4).
**The design is fully approved — R1–R4 and V1–V4 are all decided and no questions remain open.**

Vocabulary totals to build: **18 industries · 19 business functions · 22 use-case types**.

Stage 3 must not begin until both the existing 199 assertions **and** the new facet suites pass.

---

## Verify the state you inherited

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"

bash scripts/harvest/verify_protected_baseline.sh          # 18 protected files unchanged
git check-ignore -q state/taxonomy_harvest/probe           # runtime namespace ignored
git diff --stat -- .gitignore                              # must be exactly 1 insertion(+)

for t in protected_baseline config identity schema http domain_throttle budget; do
  bash "tests/test_taxonomy_${t}.sh"
done
```

---

## Map of what exists

```
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
                         DOMAIN_FACETS_PROPOSAL · HANDOFF_CURRENT · handoffs/
```

Not yet created: `src/harvest/adapters/`, `pool.py`, `coverage.py`, `scheduler.py`, `facets.py`,
`migrate/`, `data/harvested/`, and any `state/taxonomy_harvest/` run.

---

## Five invariants — do not break

1. 18 protected files stay byte-identical (`verify_protected_baseline.sh`).
2. `.gitignore` carries exactly one added line: `/state/taxonomy_harvest/`.
3. `APPROVED_CELLS` (12) in `check_config.py` is the specification, never derived from the config.
4. 508 pre-existing untracked files stay byte-identical; a clean `git status` is **not** required.
5. Stage 3 stays blocked until old and new suites both pass.

---

## Traps already paid for (see `INVENTORY_AND_REUSE_MAP.md` §5)

- Working tree is **mixed** CRLF/LF; the baseline pins `eol_form` per file for this reason.
- `urllib.robotparser` is **not** RFC 9309 — we ship our own matcher.
- `os.kill(pid, 0)` reports dead processes as **alive** on Windows.
- Git Bash `/tmp` paths are invisible to native Python; Python prints CRLF into `$(...)`.
