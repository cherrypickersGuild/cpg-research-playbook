# Handoff — Stage 2 complete, Stage 2.5 design approved, not implemented

**Date:** 2026-07-28
**Repo:** `C:\Users\SJ\Documents\ClaudeWorkspace\axCaseResearch4`
**Branch:** `main` · **HEAD:** `8865c54e2cc8d879410576f247baac4aea149f34` (6 ahead of `origin/main`)
**Implementation-start commit (protected baseline anchor):** the same `8865c54e…`

This is a point-in-time snapshot for a new session. Read `docs/harvest/HANDOFF_CURRENT.md` first;
this file is the durable copy.

---

## 1 · State in one line

Stages 0–2 are **implemented and tested** (199 assertions, all green). Stage 2.5 is **designed and
approved but NOT implemented**. Stage 3 has **not started**. **No live harvest, migration, refresh,
link-check or promotion has been performed.**

---

## 2 · What is implemented and tested

| Stage | Deliverables | Tests |
|---|---|---|
| **0** — scaffold, baselines | `.gitignore` (+1 line), `hash_tree.py`, `protected_baseline.py` + 2 wrappers, `protected_paths.txt` (18), `protected_sha256.txt`, `untracked_baseline.txt` (508 files), 3 docs | `test_taxonomy_protected_baseline.sh` — **24** |
| **1** — config, schemas, identity | `requirements.txt`/`constraints.txt`, 7 config files (12 cells / 25 sources), 7 JSON schemas, `slug.py`, `urlkey.py`, `records.py`, `schema.py`, `check_config.py` | `config` **18** · `identity` **42** · `schema` **35** |
| **2** — HTTP, leases, budgets | `budget.py`, `domainlease.py`, `httpclient.py` (incl. own RFC 9309 `RobotsRules`) | `http` **48** · `domain_throttle` **16** · `budget` **16** |

**Total: 199 assertions across 7 suites.**

Run them all:

```bash
cd "C:/Users/SJ/Documents/ClaudeWorkspace/axCaseResearch4"
for t in protected_baseline config identity schema http domain_throttle budget; do
  bash "tests/test_taxonomy_${t}.sh"
done
bash scripts/harvest/verify_protected_baseline.sh
```

---

## 3 · Four defects found and fixed (do not reintroduce)

1. **Baseline derivation.** Hashing the working tree against `git show <commit>:<path>` reported 8
   protected files as drifted while `git diff` said clean. Cause: `core.autocrlf=true`, no
   `.gitattributes`. The tree is **legitimately mixed** — 10 of 18 protected files are LF on disk
   (written by tooling), 8 are CRLF (written by a checkout). The baseline now compares against
   `git cat-file --filters` and **pins the observed `eol_form` per file**, which is what catches an
   LF-only rewrite that `git diff` normalises away.
2. **`urllib.robotparser` is not RFC 9309.** Stdlib uses first-match-in-order; the RFC requires
   longest-match-wins, and the difference errs *unsafely* (`Allow: /` then `Disallow: /private`
   permits `/private/x`). Replaced with `httpclient.RobotsRules`.
3. **`os.kill(pid, 0)` is not a liveness probe on Windows.** For a definitively exited process it
   returned normally, reporting ALIVE — so a crashed worker's domain slot could only be reclaimed by
   the 120 s age rule. Replaced with `OpenProcess` + `GetExitCodeProcess`. (An earlier hypothesis
   that it *terminates* live processes was tested and **disproved** — do not repeat that claim.)
4. **Windows/Git Bash test traps.** `mktemp -d` returns an MSYS path native Python cannot open
   (`[ -f ]` succeeds, `open()` raises). Python prints CRLF, so `$(...)` leaves interior `\r` and
   breaks multi-line comparison. Both documented in `INVENTORY_AND_REUSE_MAP.md` §5.

---

## 4 · Stage 2.5 — approved design, NOT implemented

Full spec: `docs/harvest/DOMAIN_FACETS_PROPOSAL.md` (revision 3).

**Core idea.** `Cases → Domain Applications` stays the publication category and the 12-cell structure
is unchanged. Industry / business function / use-case type become three independent, versioned,
evidence-grounded facets on a `case_facets` record field. Facets are **never** part of `record_id`,
`content_id`, `identity_url`, `cell_id` or the published filename.

**Decided:** three axes · `case_facets` naming · coverage tiers as scheduler *hints* only
(7/8/3 industries, 10/8/1 functions, 10/10/1 use cases) · `case-studies` enrichment `report_only` ·
**no mid-run revalidation** (run-scoped immutable source snapshot) · `cross-industry` `record_only`
and it never closes a concrete gap · `technology-software` `record_only`, never inferred from
publisher/vendor/platform · mandatory smoke stays round 1 only.

**Vocabulary decisions V1–V4 — all resolved (§15 of the proposal):**

- **V1** — five values added: `knowledge-management` (function), `data-analysis-bi`,
  `risk-fraud-compliance`, `training-education`, `customer-interaction` (use cases).
  Counts: **17→18 industries · 18→19 functions · 18→22 use-case types**, recorded explicitly rather
  than trimmed back.
- **V2** — `legal-compliance` → `legal-risk-compliance` (priority); `security-risk` →
  `information-security` (standard), narrowed to SOC/threat ops, vulnerability management,
  monitoring, incident response, identity. `risk-fraud-compliance` coexists **by design** — it is a
  use-case type describing the problem, not the function.
- **V3** — **no bare `operations` slug.** `supply-chain-operations` and `production-operations` are
  both priority; generic "business operations" prose assigns neither.
- **V4** — `customer-interaction` (priority, strictly external) is **separate** from
  `conversational-assistant` (standard, includes internal copilots). A chat interface alone never
  proves customer interaction, and `conversational-assistant` cannot satisfy the Customer Interaction
  coverage target.

**No decisions remain open.**

**Scope when implemented:** 3 vocabulary files + coverage targets + legacy map · `record.v1.json`
`case_facets` changes + 3 new schemas · `gen_facet_schema.py` + `check_facets.py` · `source_request_key`
and logical-owner contracts · 6 new test suites · **rerun of the full 199-assertion baseline**.

---

## 5 · Explicitly NOT done

- ✗ Stage 3 adapters, fixtures, classification implementation
- ✗ AX migration (the 231 cases are untouched)
- ✗ Source preflight against live sources
- ✗ Any live harvest, refresh, link-check or promotion
- ✗ `data/harvested/` does not exist; nothing published
- ✗ `state/taxonomy_harvest/` contains no production run
- ✗ Nothing committed or pushed

---

## 6 · Invariants a new session must preserve

1. **18 protected files** must stay byte-identical — verify with
   `bash scripts/harvest/verify_protected_baseline.sh` before and after any work.
2. **`.gitignore` may contain exactly one added line** (`/state/taxonomy_harvest/`).
   `git diff --stat -- .gitignore` must read `1 insertion(+)`.
3. **The 12-cell `APPROVED_CELLS` set** in `scripts/harvest/check_config.py` is the specification;
   never derive it from the config it validates.
4. **508 pre-existing untracked files** (`.scratch_ax/` etc.) must remain byte-identical and are out
   of scope. A clean `git status` is *not* required and never asserted.
5. **Stage 3 stays blocked** until both the existing suites and the new facet suites pass.

---

## 7 · Environment facts

CPython **3.13.9** win32 (`python`, not `python3` — the latter is a Store stub) · `jsonschema` 4.26.0
pinned exactly · jq 1.8.2 (emits CRLF) · `core.autocrlf=true`, no `.gitattributes` · network egress
verified; all 25 configured sources returned 200 at plan time and robots was checked per host ·
`export.arxiv.org` is `Disallow: /` so the arXiv **API is unusable** and RSS is used instead ·
`arxiv.org` Crawl-delay 15, `blogs.microsoft.com` Crawl-delay 10.
