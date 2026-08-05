---
title: "Cherry Harvest Engine — PRD"
status: draft
created: 2026-08-05
updated: 2026-08-05
project: Cherry-in-the-haystack
stakes: commercial-launch
working_mode: coaching (entry point — Vision + Features)
checkpoint: "branch point taken before Discovery Q1–Q4 were answered"
---

# Cherry Harvest Engine — PRD

> **DRAFT — CHECKPOINT.** This document was committed deliberately at a branch point, *before*
> the four open Discovery questions were answered. Everything under **Settled** is decided and
> evidenced. Everything under **Blocked on Q1–Q4** is intentionally empty — those sections
> cannot be written honestly until the product owner answers. Do not fill them by inference.

---

## 1. Scope (settled)

This PRD covers the **harvest and verification engine only**: discover candidate AI building
blocks, verify them, judge their commercial usability, and produce publishable data.

**In scope**

- Automated discovery of tools, workflows, agents, prompts, skills, and MCP servers
- Verification that a candidate is real, reachable, and described accurately
- Determination of **commercial usability** (license and terms)
- Quality judgement sufficient to justify publishing a recommendation
- Producing data in a shape a downstream website can consume

**Out of scope** (belongs to the platform PRD — see `docs/PRD/product-scope.md` in
`cherrypickersGuild/cherry-in-the-haystack`)

- Website UI, page layouts, navigation, search
- Free / paid / enterprise tiers and pricing
- Newsletter Studio, personalization engine, recommendation engine
- The Basics and Advanced knowledge sections and their Writer Agent
- KaaS (separate sub-project with its own PRD)

**Stakes: commercial launch.** Real paying users; a wrong recommendation carries legal and
reputational risk. Rigor is set accordingly — license risk, data-source rights, and NFRs
(freshness, accuracy) are first-class sections rather than footnotes.

## 2. Stated goal (product owner, verbatim intent)

> Automatically collect tools, workflows, and agents — for developers **and** non-developers —
> to populate the detailed content of cherryinthehaystack.com. Success is when
> **sufficiently verified, high-quality, commercially usable** material can be collected
> **automatically**.

Each of the four load-bearing words in that sentence — *automatically*, *verified*,
*high-quality*, *commercially usable* — is an open definition. Q2, Q3 and Q4 below exist to
close them.

## 3. Baseline — what exists today

Full extract: [`extract-repo-baseline.md`](extract-repo-baseline.md).

The repository already contains a working *collector*. It does not contain a *judge* or a
*publisher*.

| Success condition | Current state |
|---|---|
| **Automatically** collected | **No.** No scheduler, no CI. A human hand-launches `claude -p` lanes per session. Long or concurrent runs reliably hit the Claude session rate limit and all lanes fail together. |
| **Commercially usable** | **No.** No license field exists anywhere — not in the 16-field entity schema, not in `schemas/harvest/record.v1.json`, not in the five keys `scripts/github_meta.py` extracts. Greenfield. |
| **Sufficiently verified** | **Partial.** `description_source ∈ {verified, snippet-only}` records *how the description was obtained*, not whether the artifact was confirmed. The repo's own migration assessment states it "cannot supply `verification_status`". |
| **High quality** | **No.** For all 1,161 entities there is no score, no threshold, no ranking, and no human review. Stopping is governed by counts (`TARGET`, `MAX_LOOPS`, `NO_PROGRESS_THRESHOLD`), not by a quality bar. |
| **Non-developer audience** | **Inverted.** `audience_fit_score` exists but is a *negative* filter (binary 0.0/1.0, fired only by a `developer_only_audience` exclusion). In the only live corpus it saturated at 1.000 across all 19 records and rejected nothing. There is no skill-level, persona, or audience-type field. |
| **Published to the site** | **No.** Zero lines of promotion code. `promote`, `publication_manifest`, `promotion_journal`, `--publication-root` appear nowhere in `src/`, `scripts/`, `schemas/`, `config/`, `tests/`. |

**Inventory:** 1,161 entities — agent 293 · mcp 305 · prompt 204 · skill 359. 975 verified /
186 snippet-only. 1,132 URLs in the visited ledger. Harvest window 2026-07-06 → 2026-07-15.

**Known defects carried into this PRD**

- **Seed exhaustion** — `agent`, `prompt`, and `ax-cases` seeds are consumed; sourcing returns
  ~0 new. `skill` is *not* exhausted (400+ uncatalogued entries remain in the raw VoltAgent
  README, beyond the report's 40-row cap).
- **GitHub stars ordering bug** — prefetch runs at `harvest_entities.sh:536`, *before* Stage 1G
  resolves `target_url` at :550. 916 of 1,161 rows have `github_stars: null`. A token does not
  fix this; a backfill pass would.
- **`entity_id` collisions** — 721 distinct ids across 1,161 rows; only `entity_key` is unique.
- **137 rows carry the `"unknown"` URL sentinel**; 36 URLs are shared by 77 rows.
- **G9 / G10** — human review has no artifact, schema, process, acceptance criteria or owner;
  website integration is unowned and lives outside this repo.

**Two pipelines coexist.** The legacy bash entity harvest holds the 1,161 tool records. The
Python taxonomy pipeline (Stages 0–10, scoring, facets, atomic artifacts) is engineered for
*articles*, has 3 live runs, 19 accepted records, and 0 published files. Its record schema is
far richer and is a **reference asset** for this PRD — not the subject of it.

## 4. Commercial-usability constraints (settled, evidence-backed)

Three research extracts underpin this section:
[`extract-license-landscape.md`](extract-license-landscape.md) ·
[`extract-license-families.md`](extract-license-families.md) ·
[`extract-license-tooling-accuracy.md`](extract-license-tooling-accuracy.md).

These are **constraints, not preferences.** They bound what the engine can promise.

### C1 — A single `license` field is insufficient

License must be modelled in **three slots** — code / data / weights-or-artifact — and `absent`,
`unknown`, and `other` must be **three distinct states**. Absent means *all rights reserved*,
not *free*.

### C2 — Declared license metadata is unreliable

- The official MCP registry's `server.json` (schema 2025-12-11) **has no license field at all**;
  license must be resolved at the linked repository.
- ~**70%** of Hugging Face models carry **no license** (RedMonk, ~2.9M models scanned).
- **35.5%** of model-to-application transitions **strip restrictive clauses** by relicensing
  under permissive terms (arXiv:2509.09873, over 1.6M models / 140k GitHub projects).
- **66%** of analysed HF dataset licenses fall into a different use category than the author
  intended — **usually labelled more permissive than intended** (Data Provenance Initiative).

### C3 — The identifier under-determines the answer

`BUSL-1.1` is a *template*: its Additional Use Grant and per-version Change Date must be parsed
before any verdict. **Dify** ships an SPDX tag of `Apache-2.0` that is factually wrong (it adds
a multi-tenant prohibition and a logo-removal prohibition). **n8n**'s Sustainable Use License is
non-SPDX and limits use to internal business purposes. Both read as permissive to a naive
scanner. AI community licenses add thresholds no identifier expresses — Llama (>700M MAU, plus
an EU exclusion on Llama 4 multimodal), Stability (<$1M revenue), Mistral MNPL (non-production
only), Cohere research weights (CC-BY-NC).

A classifier also provably **cannot** infer: whether a paid dual-license alternative exists;
whether the next release keeps the license (a CLA is a standing relicensing capability —
Liquibase, Redis, HashiCorp and Cockroach all exercised it); whether `/ee` subdirectories carry
different terms; or whether a `LICENSE` file is the license it claims to be.

### C4 — Existing trust signals do not mean what they appear to mean

- **GitHub's license badge** is `licensee`: Sørensen–Dice at confidence threshold 98, **root
  LICENSE file only**, popular licenses only, explicitly *not* compliance.
- **OpenSSF Scorecard**'s License check is **presence-only** — a 10/10 score is compatible with
  an AGPL dependency tree.
- Vendor accuracy claims (FOSSA's 99.8%) are **unaudited marketing** with no published
  methodology, corpus, or ground truth.

### C5 — Transitive obligations are invisible to manifest-level scanning

**7.27%** of PyPI releases have license incompatibilities, **61.3% of them caused by transitive
dependencies**. Across registries, ~**5.2%** of dependency links connect incompatibly-licensed
packages (0.6% npm → 13.9% RubyGems). Manifest-only scanners (Snyk, GitHub dependency graph)
see the declared string and stop.

### C6 — The accuracy ceiling, and what follows from it

Automated license *determination* has **no demonstrated ceiling above ~95–97% precision at
~75–85% recall** — and that is on the *narrow* subtask of identifying a license text, not on the
real question of what obligations the artifact imposes. Ninka: 96.6 / 82.3 (2010, file headers
only). LiDetector: 93.28 / 75.70 (2022). **No accepted public benchmark for end-to-end license
determination exists.** Every serious tool's own documentation — `licensee`, `askalono`,
ScanCode — states that human review is required.

> **Adopted stance:** build a **triage pipeline with explicit unknown/clue states, not a verdict
> API.** At commercial-launch stakes, human review is not optional. Store the license as an SPDX
> expression **plus the raw text hash**, because the identifier alone provably under-determines
> commercial usability.

### C7 — The base rate decides the product

Revised on primary sources —
[`extract-license-determination-revised.md`](extract-license-determination-revised.md).

GitHub's own published analysis (using Licensee) finds only **~20% of repositories carry a
detectable license** (~30% counting forks), and **15.68%** of that licensed minority is
"Other/Non-standard." GitHub states plainly that absence means **all rights reserved**.

> **The default disposition of a randomly harvested artifact is: not commercially usable.**

This inverts the design. Rejecting on absence is the highest-value automated rule available and
disposes of the majority of the corpus for free — but it also means the engine's realistic
output is a **small, hard-won set**, not a large catalogue. Q4 is therefore not a policy
preference; it is the single decision that sets corpus size.

Two detector facts constrain any implementation: GitHub's `GET /licenses` serves only **13
licenses**, collapsing everything else to `NOASSERTION`; and Licensee's threshold-98
Sørensen–Dice is **asymmetric** — an *appended* restriction ("commercial use prohibited") falls
below threshold and correctly yields NOASSERTION, while a *stripped attribution clause* can
still score ≥98% and be reported as **clean MIT**.

### C8 — Candidate classifier policy

Recorded as a starting point for the requirements section, not yet ratified. The operative key
is **ScanCode LicenseDB's `category`** (Permissive · Copyleft · Copyleft Limited · Commercial ·
Proprietary Free · Non-Commercial · Free Restricted · Source-available) — **that taxonomy, not
the SPDX identifier, maps to commercial usability**, and it is the best off-the-shelf component
available.

| Bucket | Rule | Engine action |
|---|---|---|
| Auto-allow | ≥98%-confidence exact SPDX match on MIT, Apache-2.0, BSD-2/3, ISC, 0BSD, Unlicense, CC0-1.0, MPL-2.0 — **only when** LICENSE, manifest and headers agree and no vendored directory contradicts them | publish |
| Auto-reject | ScanCode categories Commercial / Proprietary Free / Non-Commercial / Source-available / Free Restricted; denylist BUSL-\*, SSPL-\*, Elastic-2.0, FSL-\*, Llama/Gemma community, CC-BY-NC\*, CC-BY-ND\*, RAIL/OpenRAIL, JSON License; **and null / NOASSERTION / "other"** | do not publish |
| Human required | NOASSERTION on high-value artifacts · any LICENSE-vs-manifest-vs-header disagreement · `OR` expressions (electing a license is a legal act) · BUSL Additional Use Grant prose · AGPL anywhere in the transitive closure of a hosted service · modified text of a known license · share-alike inbound · anything crossing Hugging Face | queue for a person |

**Revised ceiling: ~80–85% auto-dispositionable, 15–20% human-review-or-reject.** No published
benchmark exists for this task; the estimate is compositional.

Two engineering mandates follow:

1. **`license_evidence` is a structured record**, never a bare string — detected ID, detector,
   confidence, source path + line range, manifest value, disagreement flags, ScanCode category,
   reviewer + date. `commercial_use` defaults to `"unknown"` and requires an affirmative
   transition.
2. **Re-scan on a cadence against a pinned commit SHA.** HashiCorp→BUSL, Redis→RSALv2/SSPL→AGPL,
   Elastic→ELv2→AGPL: **a 2024 clearance is not a 2026 clearance.**

### C9 — The share-alike trap is already in our seed corpus

`sindresorhus/awesome` is **CC0-1.0** (safe). **`awesome-selfhosted/awesome-selfhosted` is
CC-BY-SA-3.0** — ingesting its curatorial selection *and its descriptions* can force the
published catalog under BY-SA.

> **Rule: harvest the facts (repo URL, name), never the prose.**

This bears directly on the current pipeline, which seeds from curated awesome-list reports and
copies descriptions into `description`.

### C10 — Asserting "commercially usable" assumes liability the incumbents decline

GitHub — with more data and more lawyers — states it is "not a law firm." A product that makes
**"commercially usable" a headline claim** takes on liability the incumbents explicitly refuse.
This needs **counsel-reviewed disclaimer language before launch, not after.**

Related: do **not** build a "prompts are probably not copyrightable" exception into the engine.
Copyright is not the binding constraint — the repo license as contract, platform ToS, EU *sui
generis* database rights over the collection, and trademark all bind regardless.

## 5. Blocked on Q1–Q4

These sections are **deliberately unwritten**. The answers change the requirements materially,
so inferring them would produce a confident and wrong PRD.

### Q1 — Vision *(blocked)*

**Question:** When the engine works, what does a visitor to cherryinthehaystack.com actually
*get*? Not the screen — the thing they walk away with.

*Depends on this:* Vision statement · what "publishable data" must contain · whether the unit of
output is an entry, a comparison, or a recommendation.

### Q2 — The quality bar *(blocked)*

**Question:** What counts as a **disqualifier**? (e.g. many stars but no commit in 6 months; a
solo toy with excellent docs; a vendor product with no independent usage evidence; works fine
but GPL; free but requires an API key.)

*Depends on this:* the entire scoring/gating model — the single largest hole in the current
system, where 1,161 records have no quality judgement of any kind.

### Q3 — Whose commercial use? *(blocked)*

**Question:** (a) may **we** publish this data commercially — our data-collection rights; or
(b) may a **visitor** use this tool in their own company — the tool's license; or (c) both.

*Depends on this:* whether the engine needs a source-rights model in addition to an artifact
license model. (a) and (b) are different systems.

### Q4 — Disposition of unclear licenses *(blocked)*

**Question:** exclude / publish-with-a-warning / route to human review. Given C2, a large share
of candidates land here.

*Depends on this:* corpus size, publication volume, and ongoing human review cost — this single
answer sets the operating budget.

## 6. Open items

- `docs/README.md` in the `cherry-in-the-haystack` repo returned **404** on `raw.../main/`; the
  main-product ↔ sub-project boundary document was not obtained. Path may differ.
- A landscape survey of competing registries and directories was commissioned; **only its
  revised license section was delivered** (folded into C7–C10). The **registry comparison table,
  the quality-signal analysis, the white-space assessment and the full risk list were not
  delivered** and remain outstanding. Without them, this PRD currently has **no evidenced view of
  who else does this or how they gate quality** — a real gap at commercial-launch stakes.
- No measurement exists — anywhere — of what fraction of `awesome-mcp-servers` entries have a
  resolvable license. If that number is needed, it must be measured directly.
- Non-developer demand evidence is **unassessed**; the current pipeline can only reject
  developer-only material, never positively identify non-developer suitability.

## 7. Provenance

Sources extracted for this draft:

| Source | Artifact |
|---|---|
| This repository (`axCaseResearch4`) | [`extract-repo-baseline.md`](extract-repo-baseline.md) |
| AI-artifact licensing (weights, prompts, datasets, HF metadata, MCP registry) | [`extract-license-landscape.md`](extract-license-landscape.md) |
| License families, relicensing events 2023–2026, dual licensing and CLAs | [`extract-license-families.md`](extract-license-families.md) |
| Detection tooling and its measured accuracy ceiling | [`extract-license-tooling-accuracy.md`](extract-license-tooling-accuracy.md) |
| License determination revised on primary sources (base rates, ScanCode categories, transitive laundering) — **supersedes** the license conclusions in the landscape extract | [`extract-license-determination-revised.md`](extract-license-determination-revised.md) |
| `docs/PRD/product-scope.md` (upstream platform scope) | read directly; used to fix the scope boundary in §1 |

Decision trail: [`.memlog.md`](.memlog.md).
