---
title: "Cherry Harvest Engine — PRD"
status: draft
created: 2026-08-05
updated: 2026-08-05
project: Cherry-in-the-haystack
stakes: commercial-launch
working_mode: coaching (entry point — Vision + Features)
revision: "post-review bounded edit checkpoint"
---

# Cherry Harvest Engine — PRD

> **DRAFT — revised after a full review gate; not finalized.** Eight reviewers (quality rubric,
> adversarial, edge-case sweep, four input reconciliations, memlog audit) produced ~250 raw
> findings, deduplicated to 10 blockers / 15 majors / 8 minors / 3 accepted risks. This revision
> closes the blockers and the product decisions attached to them. Remaining majors are listed in
> §18 with their disposition. Checkpoint `7a9dc65` on branch `prd/cherry-harvest-engine`
> preserves the pre-answer state.

---

## 1. Scope

This PRD covers the **harvest and verification engine only**: discover candidate AI building
blocks, verify them, judge their commercial usability, and produce publishable data.

**In scope**

- Automated discovery of tools, workflows, agents, prompts, skills, and MCP servers
- Verification that a candidate is real, reachable, maintained, and described accurately
- Determination of **commercial usability**, in both directions (§9)
- Audience classification, including positive assessment of non-developer suitability
- Quality assessment, defined independently of popularity (§10)
- Security and privacy risk screening
- Producing data in a shape a downstream website can consume, under an explicit contract (§13)

**Out of scope** — belongs to the platform PRD (`docs/PRD/product-scope.md` in
`cherrypickersGuild/cherry-in-the-haystack`)

- Website UI, page layouts, navigation, search
- Free / paid / enterprise tiers and pricing
- Newsletter Studio, personalization engine, recommendation engine
- The Basics and Advanced knowledge sections and their Writer Agent
- KaaS (separate sub-project with its own PRD)

**Boundary discipline.** This engine emits data and states the guarantees attached to it. Where
a guarantee only holds if the consuming site behaves in a particular way, that obligation is
recorded in **§13 Downstream Consumer Contract** as a condition on the engine's guarantee — not
as a requirement this PRD imposes on the website. The engine never asserts authority over UI.

**Stakes: commercial launch.** Real paying users; a wrong recommendation carries legal and
reputational risk. Rigor is set accordingly — licence risk, data-source rights and NFRs are
first-class sections rather than footnotes.

## 2. Stated goal

> Automatically collect tools, workflows, and agents — for developers **and** non-developers —
> to populate the detailed content of cherryinthehaystack.com. Success is when
> **sufficiently verified, high-quality, commercially usable** material can be collected
> **automatically**.

Where each load-bearing word is defined:

| Word | Defined in |
|---|---|
| *verified* | §7 Verification model, §8 State, disposition and gate model |
| *high-quality* | §10 Quality model |
| *commercially usable* | §9 Licence and commercial usability |
| *automatically* | §14 FG-L, and the auto-disposition rate target in §16 |
| developer / non-developer | §6 Audience model |

## 3. Baseline — what exists today

Full extract: [`extract-repo-baseline.md`](extract-repo-baseline.md). Figures below were
re-verified against the live repository during the review gate; three errors in the previous
revision are corrected and marked.

The repository already contains a working *collector*. It does not contain a *judge* or a
*publisher*.

| Success condition | Current state |
|---|---|
| **Automatically** collected | **No.** No scheduler, no CI. A human hand-launches `claude -p` lanes per session. Long or concurrent runs reliably hit the Claude session rate limit and all lanes fail together. |
| **Commercially usable** | **No.** No licence field exists anywhere — not in the 16-field entity schema, not in `schemas/harvest/record.v1.json`, not in the five keys `scripts/github_meta.py` extracts. Greenfield. |
| **Sufficiently verified** | **Partial.** `description_source ∈ {verified, snippet-only}` records *how the description was obtained*, not whether the artifact was confirmed. The repo's own migration assessment states it "cannot supply `verification_status`". |
| **High quality** | **No.** For all 1,161 entities there is no score, no threshold, no ranking, and no human review. Stopping is governed by counts (`TARGET`, `MAX_LOOPS`, `NO_PROGRESS_THRESHOLD`), not by a quality bar. |
| **Non-developer audience** | **Inverted.** `audience_fit_score` exists but is a *negative* filter (binary 0.0/1.0, fired only by a `developer_only_audience` exclusion). In the only live corpus it saturated at 1.000 across all 19 records and rejected nothing. No skill-level, persona, or audience-type field. |
| **Security / privacy screening** | **Absent.** No vulnerability data source, no policy assessment, no risk flags. |
| **Published to the site** | **No producer.** *(corrected)* The publication **layout contract exists and is committed** — `publication_manifest` and `--publication-root` occur 5 and 8 times across `cli.py`, `compare.py` and `test_compare.py`. What does not exist is the **producer** that writes it, and `promote` / `promotion_journal`. Zero records have been published. |

**Inventory:** 1,161 entities — agent 293 · mcp 305 · prompt 204 · skill 359. 975 verified /
186 snippet-only. 1,132 URLs in the visited ledger. Harvest window 2026-07-06 → 2026-07-15.

**Known defects carried into this PRD**

- **Seed exhaustion** — `agent`, `prompt`, and `ax-cases` seeds are consumed; sourcing returns
  ~0 new. `skill` is *not* exhausted (400+ uncatalogued entries remain in the raw VoltAgent
  README, beyond the report's 40-row cap).
- **GitHub stars ordering bug** — prefetch runs at `harvest_entities.sh:536`, *before* Stage 1G
  resolves `target_url` at :550. *(corrected)* The defect affects **436 of the 678 rows that
  have a GitHub `target_url`** — not 916 of 1,161; the larger figure counts rows that have no
  GitHub URL at all and were never in scope for star collection. A token does not fix the
  ordering; a backfill pass would.
- **`entity_id` collisions** — 721 distinct ids across 1,161 rows; only `entity_key` is unique.
- **137 rows carry the `"unknown"` URL sentinel**; 36 URLs are shared by 77 rows.
- **G9 / G10** — human review had no artifact, schema, process, acceptance criteria or owner
  *within this repository*; §14 FG-J and §8 now supply them, and §18 records that the upstream
  platform already operates a review process this engine must connect to rather than duplicate.
- **G14 — a hard implementation constraint.** 33 of 39 taxonomy wrappers assert `config/` is
  unmodified, so no checkpoint that edits `config/` can pass `validate_task.sh`. Several
  requirements in §14 are configuration changes by nature. See §17.

**Two pipelines coexist.** The legacy bash entity harvest holds the 1,161 tool records. The
Python taxonomy pipeline (Stages 0–10, scoring, facets, atomic artifacts, a committed
publication layout) is engineered for *articles*. Neither is wholesale adopted nor wholesale
discarded — §12.2 sets the contract-driven replacement policy.

**`docs/README.md` — never written.** *(corrected)* The previous revision recorded a 404 as
though the path were wrong. The review gate confirmed via the GitHub contents API and HTML tree
that `docs/` contains no README at all, while `product-scope.md` itself cites "See
`docs/README.md` for the full boundary definition." The upstream document carries a dangling
reference to its own boundary document, and **no document anywhere places this engine inside the
platform.** Recorded as an open item in §18.

## 4. Evidence-backed constraints

Four research extracts underpin this section:
[`landscape`](extract-license-landscape.md) ·
[`families`](extract-license-families.md) ·
[`tooling accuracy`](extract-license-tooling-accuracy.md) ·
[`determination revised`](extract-license-determination-revised.md) — the last **supersedes** the
licence conclusions of the first.

These are **constraints, not preferences.** They bound what the engine can promise.

**C1 — A single `license` field is insufficient.** Licence must be modelled in **three slots** —
code / data / model-artifact — each carrying its own class and evidence, and the model must be
able to represent **conflicting** evidence. *Implemented by FR-26 and §9.1.*

**C2 — Declared licence metadata is unreliable.** The official MCP registry's `server.json`
(schema 2025-12-11) **has no licence field at all**. ~**70%** of Hugging Face models carry **no
licence** (RedMonk, ~2.9M scanned). **35.5%** of model-to-application transitions **strip
restrictive clauses** by relicensing permissively (arXiv:2509.09873). **66%** of analysed HF
dataset licences fall into a different use category than the author intended — **usually more
permissive than intended**.

**C3 — The identifier under-determines the answer.** `BUSL-1.1` is a *template*: its Additional
Use Grant is free-form vendor prose and is **irreducibly human**; its Change Date converts a
version on a schedule, with no repository change at all. **Dify** ships an SPDX tag of
`Apache-2.0` that is factually wrong. **n8n**'s Sustainable Use License is non-SPDX. Both read as
permissive to a naive scanner. AI community licences add thresholds no identifier expresses —
Llama (>700M MAU, plus an EU exclusion on Llama 4 multimodal), Stability (<$1M revenue), Mistral
MNPL (non-production only), Cohere research weights (CC-BY-NC). A classifier also provably
**cannot** infer whether a paid dual-licence alternative exists, whether the next release keeps
the licence (a CLA is a standing relicensing capability — Liquibase, Redis, HashiCorp and
Cockroach all exercised it), whether `/ee` subdirectories carry different terms, or whether a
`LICENSE` file is the licence it claims. *Consequence: FR-87 forbids deriving a disposition from
an identifier alone.*

**C4 — Existing trust signals do not mean what they appear to mean.** GitHub's licence badge is
`licensee`: Sørensen–Dice at confidence threshold 98, **root LICENSE file only**, popular
licences only, explicitly *not* compliance. OpenSSF Scorecard's Licence check is
**presence-only** — a 10/10 is compatible with an AGPL dependency tree. Vendor accuracy claims
(FOSSA's 99.8%) are **unaudited marketing** with no published methodology.

**C5 — Transitive obligations are invisible to manifest-level scanning.** **7.27%** of PyPI
releases have licence incompatibilities, **61.3% of them caused by transitive dependencies**.
"Don't Trust the Label" traces 232,270 dataset→model→app chains: **62.3% pass through at least
one unlicensed artifact.** **A permissive label on a downstream AI repo is empirically the most
likely place for a laundered restriction to hide.** Only **14.2%** of detected conflicts are
fundamentally unresolvable — the labels are wrong, not the artifacts.

**C6 — The accuracy ceiling.** Automated licence *determination* has **no demonstrated ceiling
above ~95–97% precision at ~75–85% recall** — on the *narrow* subtask of identifying a licence
text, not on what obligations it imposes. Ninka 96.6/82.3 (2010, headers only); LiDetector
93.28/75.70 (2022). **No accepted public benchmark exists.** Every serious tool's own
documentation — `licensee`, `askalono`, ScanCode — states human review is required.
→ **Build a triage pipeline with explicit evidence states, not a verdict API.**

**C7 — The base rate.** GitHub's own analysis finds only **~20% of repositories carry a
detectable licence** (~30% with forks); **15.68%** of the licensed minority is
"Other/Non-standard"; absence means **all rights reserved**. `GET /licenses` serves only **13
licences**, collapsing the rest to `NOASSERTION`. Licensee's threshold-98 matching is
**asymmetric** — an *appended* restriction correctly yields NOASSERTION, while a *stripped
attribution clause* can still score ≥98% and be reported as **clean MIT**. That asymmetry is the
dangerous error class, and FR-63 queues it explicitly.
*Sizing caveat: the ~20% figure is non-peer-reviewed and 2015-era, bracketed against a 2020
figure of 46% unlicensed with no 2023–2026 replication. §9.4's trade-off is sized off it and
should be re-measured against our own corpus — see §16 SM-1.*

**C8 — ScanCode's `category` is the operative key.** LicenseDB tags each licence with a category
beyond the SPDX ID — Permissive · Copyleft · Copyleft Limited · Commercial · Proprietary Free ·
Non-Commercial · Free Restricted · Source-available. **That taxonomy, not the SPDX identifier,
is the primary input to disposition.** Caution: ScanCode's Licence Clarity Score measures
documentation quality, not permission — a BUSL repo can score perfectly, so it must never be
wired to a gate.

**C9 — The share-alike trap is already in our seed corpus.** `sindresorhus/awesome` is CC0-1.0
(safe). **`awesome-selfhosted/awesome-selfhosted` is CC-BY-SA-3.0** — ingesting its curatorial
selection *and its descriptions* can force the published catalog under BY-SA.
→ **Harvest the facts (repo URL, name), never the prose.** The existing corpus already violates
this, which is one reason §12.1 freezes it rather than migrating it.

**C10 — Asserting "commercially usable" assumes liability the incumbents decline.** GitHub — with
more data and more lawyers — states it is "not a law firm." This needs **counsel-reviewed
disclaimer language before launch, not after**, and the disclaimer must name the limits this PRD
knowingly accepts: no transitive-dependency analysis, artifact-scoped claims only, and
point-in-time validity. Related: do **not** build a "prompts are probably not copyrightable"
exception into the engine — the repo licence as contract, platform ToS, EU *sui generis*
database rights, and trademark all bind regardless.

## 5. Vision

A visitor gets **curated information that lets them rapidly explore and compare the tools
actually in use in a given category.**

The core value is **not a list of tools.** It is **reducing the cost of discovery, comparison and
initial vetting** by putting what you need in one place.

Each entry carries, as far as it can be established: name and icon · a summary of what it does ·
category and purpose · links (official site, GitHub repository, documentation, product page) ·
publicly verifiable interest signals such as GitHub stars · **licence and commercial usability** ·
whether it has been updated recently · **verification status and cautions**.

A visitor must be able to answer these five questions quickly:

1. What is widely used in this category right now?
2. What problem does each tool solve?
3. Is it still maintained and operating?
4. Can I use it in a personal or company project?
5. Are there licence, security or privacy issues I need to look into further?

## 6. Audience model

**Both developers and non-developers are in scope.** That does **not** mean showing both groups
the same tools and the same information. The product supports both, states each tool's target
user and required capability, and varies the explore/compare criteria by group.

### 6.1 Audience is a positive field, never a negative filter

```json
{
  "audience": {
    "primary": ["developer"],
    "also_suitable_for": ["technical_non_developer"],
    "skill_level": "intermediate",
    "code_required": true,
    "local_install_required": true,
    "hosted_option_available": false
  }
}
```

Vocabulary: `developer` · `technical_non_developer` · `business_user` · `creator` ·
`researcher` · `general_user`.

### 6.2 Non-developer suitability needs its own criteria

For a non-developer, stars and SPDX identifiers matter far less than: usable straight from a
browser · local install required · coding or CLI required · core function reachable through
natural language or a GUI alone · signup-to-first-result not convoluted · free trial or free plan
· pricing published · use cases and official guides comprehensible to a non-developer · clear
security and privacy options when entering company data.

```json
{
  "non_developer_usability": {
    "status": "suitable_with_learning",
    "code_required": false,
    "cli_required": false,
    "browser_based": true,
    "setup_complexity": "low",
    "pricing_visible": true,
    "evidence_urls": []
  }
}
```

### 6.3 Source policy for v1 — official, primary, public, or permitted only

Current sourcing (awesome-lists, GitHub) is structurally biased toward developer tools.
Non-developer coverage expands through a distinct source family, subject to one hard rule:

> **v1 uses only official, primary, public, or expressly permitted sources.** A paid commercial
> data agreement (G2, Capterra, TrustRadius and equivalents) **must not be a launch
> precondition.** If such an agreement is later obtained it is an expansion, not a dependency.

Admissible v1 families: vendor official sites and product pages · official product documentation
and pricing pages · public open-data sources with permissive terms · official platform and
marketplace listings where terms permit · no-code and low-code marketplaces, whose listing
structure is itself machine-checkable evidence for `code_required: false`.

**Coverage honesty is a requirement, not a nicety.** The engine publishes, per audience segment,
both its coverage and its **`unknown` rate** (FR-71). Items with absent or weak audience evidence
stay unresolved; non-developer suitability is **never assumed**.

> Non-developers are **in scope with staged data coverage**, not deferred.

## 7. Verification model

**"Verified" does not warrant safety or quality.** It means that, *as of the time of
collection*, the tool's existence, accessibility, maintenance state, usage evidence and absence
of serious risk were checked. This framing is deliberate and bounds the claim being made (C10).

Verification produces **evidence records**, not verdicts. How evidence becomes a disposition and
a gate outcome is §8. This section defines **what is checked and what counts as a failure**.

### 7.1 Existence and safety — confirmed failures

Each of the following is a **confirmed failure with a reason code**, never an absence of
information. The distinction is load-bearing: these are things we checked and found wrong.

| Reason code | Condition |
|---|---|
| `EXIST_UNREACHABLE` | official site, repository or documentation links cannot be reached across the configured window |
| `EXIST_DISCONTINUED` | the project or service is discontinued, deleted, archived, or no longer offered |
| `EXIST_UNIDENTIFIABLE` | the tool's existence or official source cannot be corroborated by any independent source |
| `SAFE_MALICIOUS` | evidence of spam, impersonation, or malware distribution |
| `SEC_VULN_UNRESOLVED` | a confirmed, unresolved serious vulnerability or breach |
| `LIC_INFRINGEMENT` | adjudicated or officially reported licence violation, copyright infringement, or unauthorized redistribution |
| `PRIV_*` | the privacy conditions in §7.4 |

`EXIST_UNIDENTIFIABLE` and `LIC_INFRINGEMENT` both require **corroborating evidence from an
identifiable source**; neither may be asserted on inference alone (§18 records the residual
exposure).

### 7.2 Cautions — recorded, not disqualifying

Long dormant with unclear maintenance · thin usage evidence · missing or unusable documentation ·
early-stage or explicitly experimental · a recent security issue whose resolution is unconfirmed ·
repeated outages or unstable operation · unclear privacy or data-retention policy.

These produce caution flags carried with the record. The visitor-facing vocabulary is
`needs-review` · `caution` · `possibly-inactive`, bound to the `caution_flags[]` field (FR-56).
These are display labels and are deliberately distinct from the machine states in §8.

### 7.3 Age is not a disqualifier, and stars are not currency

An old tool is **not** excluded merely for being old. **GitHub stars are a popularity signal,
never standalone evidence of current usability** — a dead repository keeps its stars. Currency is
judged on multiple signals: recent commits, recent releases, whether the official service is
actually operating, and issue/community activity (FR-20).

### 7.4 Privacy — unclear is a caution, confirmed serious harm is a failure

**Confirmed failure** — only where reliably evidenced: `PRIV_DECEPTIVE_COLLECTION` ·
`PRIV_DELETION_REFUSED` (explicit refusal with no legal or contractual basis) ·
`PRIV_SENSITIVE_DISCLOSURE` (third-party disclosure without consent) · `PRIV_BREACH_UNRESOLVED` ·
`PRIV_SANCTIONED` (official sanction or credible evidence of repeated violation in practice) ·
`PRIV_MALICIOUS_DESIGN` (built for malware, credential theft, or exfiltration).

**Caution** — no findable privacy policy · unclear retention · unclear training-data use ·
opt-out or deletion path hard to confirm · undocumented enterprise options · stale or
self-contradictory policy documents.

```json
{
  "privacy": {
    "status": "indeterminate",
    "policy_url": null,
    "training_opt_out": "unresolved",
    "data_deletion_available": "unresolved",
    "retention_disclosed": "unresolved",
    "risk_flags": [],
    "evidence_urls": []
  }
}
```

### 7.5 Security verification is a new capability

Screening for unresolved serious vulnerabilities requires a vulnerability data source (OSV,
GitHub Advisory, CVE) that **does not exist in the current pipeline**. Until it exists the
security evidence state is `unchecked`, which under §8.3 **prevents `commercially_usable` from
being asserted** and does **not** silently pass. It also does not queue review (§8.5) and does
not remove the entity from the corpus.

## 8. State, disposition and gate model

This section replaces the previous scattered treatment of statuses and gates. It exists because
the review gate found the not-known state spelled six different ways, `unknown` absent from its
own enumeration, and the single rule guarding the product's headline claim failing **open**.

**Three axes, kept strictly separate.**

### 8.1 Axis 1 — Evidence state (what we observed)

Attached to every individual assertion, never to the record as a whole.

| State | Meaning |
|---|---|
| `confirmed` | checked; the evidence is definite |
| `conflicting` | checked; independent sources disagree |
| `absent` | checked; the thing genuinely is not there (e.g. no licence file anywhere) |
| `unreadable` | checked; found but could not be interpreted (e.g. bespoke licence prose) |
| `unchecked` | not yet assessed |
| `unavailable` | could not be assessed because a dependency failed (outage, rate limit, block) |

`absent`, `unchecked` and `unavailable` are **three different facts** and are never collapsed.
Every evidence record carries `{state, reason_code, evidence_urls[], method, detector,
confidence, checked_at}` (FR-83).

### 8.2 Axis 2 — Disposition state (what we decided)

Derived per domain: existence · currency · licence · commercial use · catalog rights · audience ·
quality · privacy · security · visual asset.

| State | Meaning |
|---|---|
| `cleared` | affirmatively acceptable |
| `cleared_with_conditions` | acceptable subject to recorded conditions |
| `blocked` | affirmatively unacceptable — always carries a reason code from §7.1 or §7.4 |
| `indeterminate` | evidence insufficient to decide; the resting state, not an error |
| `review_required` | undecided **and** the decision would materially change a gate (§8.5) |

`blocked` is reserved for **confirmed failures**. A thing we did not check is `indeterminate`,
never `blocked`. A thing we checked and found wrong is `blocked`, never `indeterminate`.

### 8.3 Axis 3 — Gate outcomes (computed, never stored as truth)

Four booleans, each recomputed from dispositions on every assessment, each explainable (FR-61).

**`corpus_included`** — TRUE unless existence is `blocked` **or** privacy/security is `blocked`
for a `SAFE_*` or `PRIV_MALICIOUS_DESIGN` reason.
*`indeterminate` never blocks corpus membership.* This is the rule that keeps the corpus broad.

**`publicly_listed`** — TRUE when all hold:
- `corpus_included` is TRUE
- existence disposition is `cleared` or `cleared_with_conditions`
- no domain is `blocked`
- catalog rights are `cleared` or `cleared_with_conditions`

*Licence `indeterminate` does not block listing.* An unclear-licence tool is listed, carrying its
cautions.

**`commercially_usable`** — TRUE only when all hold:
- `publicly_listed` is TRUE
- licence disposition is `cleared` or `cleared_with_conditions`
- `end_user_use` for the requested usage context is `allowed` or `allowed_with_conditions` (§9.3)
- privacy disposition is not `blocked` and not `indeterminate`
- security disposition is not `blocked` and not `indeterminate`

**`asset_reusable`** — TRUE only when the visual-asset disposition is `cleared` (§11).

### 8.4 The governing rule (replaces the previous §11)

> **Gates that require confirmed evidence are satisfied only by an explicit affirmative
> disposition. `indeterminate`, `unchecked` and `unavailable` never satisfy them.**
> **Corpus membership is the one gate that does not require confirmed evidence — it is
> refused only by a confirmed failure.**

This is stated as an **allowlist**, not as a denylist of one value. The previous phrasing
("`unknown` shall never satisfy any gate") failed open against every other spelling of not-known,
and simultaneously emptied the corpus when applied to `corpus_included`. Both defects are closed
by separating the two rules above.

The rule is directional and deliberately asymmetric: **unconfirmed evidence may remain in the
corpus; it may not pass a gate that requires confirmation.**

### 8.5 Review is triggered by consequence, not by uncertainty

An item enters the human review queue **only** when an unresolved judgement could materially
change one of:

1. `publicly_listed`
2. `commercially_usable`
3. an already-published high-risk claim

**Explicitly not queued:** every `indeterminate` or `unchecked` value · visual assets whose
rights are unresolved (they render the neutral placeholder and cost nothing to leave unresolved) ·
external data-source outages (`unavailable` is a system condition, not a judgement).

This narrowing is the difference between a queue one operator can sustain and one that cannot be
staffed at any size — see §16 and §18.

## 9. Licence and commercial usability

### 9.1 Three slots, three classes (implements C1)

Licence is modelled per artifact slot. Every slot carries its own class, evidence and conditions.

```json
{
  "license": {
    "slots": {
      "code":           { "class": "standard", "spdx_expression": "Apache-2.0", "text_hash": "…", "scancode_category": "Permissive", "evidence": { "state": "confirmed", "…": "…" } },
      "data":           { "class": "absent_or_unconfirmed", "evidence": { "state": "unchecked" } },
      "model_artifact": { "class": "not_applicable" }
    },
    "conflicts": [],
    "conditions": [],
    "restrictions": [],
    "disposition": "cleared",
    "checked_at": "2026-08-05"
  }
}
```

**Slot classes**

| Class | Meaning |
|---|---|
| `standard` | a recognised licence identified with confirmed evidence |
| `absent_or_unconfirmed` | no licence found, or found but not confirmable — **all rights reserved by default** |
| `nonstandard_or_conditional` | present but bespoke, modified, rider-bearing, or otherwise not reducible to an identifier |
| `not_applicable` | the slot does not exist for this artifact |

**Conflicting evidence is first-class.** Where sources disagree, the slot's evidence state is
`conflicting`, `conflicts[]` records each source and its claim, and the disposition is
`review_required` if it would change a gate (§8.5), otherwise `indeterminate`.

### 9.2 Disposition policy — five buckets (restores the dropped policy)

The licence disposition is a function of **(ScanCode category, riders detected, thresholds
detected, evidence state, usage context)**. **It is never a function of the SPDX identifier
alone** (C3, FR-87).

| Bucket | Input pattern | Disposition |
|---|---|---|
| **auto-allow** | category `Permissive`, evidence `confirmed`, no riders, no thresholds, LICENSE / manifest / headers agree | `cleared` |
| **allow-with-conditions** | category `Copyleft Limited` (MPL, LGPL); or permissive with attribution/notice obligations | `cleared_with_conditions`, obligations recorded in `conditions[]` |
| **quarantine** | category `Copyleft` (GPL family) | `cleared_with_conditions` for internal-use context only; `restricted` for redistribution and hosted-service contexts (§9.3) |
| **auto-block** | categories `Non-Commercial`, `Proprietary Free`, `Free Restricted`; network-copyleft (AGPL, SSPL) for hosted-service context; `absent_or_unconfirmed` for the commercial claim | `blocked` for the affected contexts |
| **human-review** | rider-bearing or modified licence text · `OR` expressions · BUSL Additional Use Grant · FSL or other time-converting terms · revenue/MAU/company-size thresholds · behavioural-use attachments · share-alike inbound to our catalog · `conflicting` evidence · AGPL anywhere in the transitive closure of a hosted service · artifacts sourced through Hugging Face | `review_required` |

Note that `auto-block` here blocks the **commercial-usability claim** for the affected context.
It does not remove the entity from the corpus (§8.3).

### 9.3 `end_user_use` is contextual, not a scalar

May a visitor use the tool for company work, paid products, client projects, or
revenue-generating work? The answer depends on **how** they intend to use it, so the field is
resolved **per usage context** and derived from four inputs (FR-88):

- **conditions** — obligations imposed (attribution, notice retention, source availability)
- **restrictions** — uses prohibited (hosting, resale, competing service, non-production only)
- **usage context** — `internal_use` · `redistribution` · `hosted_service` · `model_training`
- **evidence source** — repository licence · official ToS · pricing page · official product docs

```json
{
  "commercial_use": {
    "catalog_use": "allowed",
    "end_user_use": {
      "internal_use":   "allowed",
      "redistribution": "allowed_with_conditions",
      "hosted_service": "restricted",
      "model_training": "indeterminate"
    }
  }
}
```

Values: `allowed` · `allowed_with_conditions` · `restricted` · `indeterminate`.
`commercially_usable` (§8.3) is evaluated against the **requested** context; where no context is
specified, `internal_use` is the default and the record states so.

Also recorded: ownership and commercial terms of **generated output** (where obtainable),
free-tier versus paid-tier commercial terms, and whether an enterprise licence or additional
contract is required.

### 9.4 `catalog_use` — may *we* publish this?

Whether our service may collect, store, process and display this tool's metadata, name, icon,
description, links and public metrics.

**Assessed on a separate path from licence determination.** It is mostly not a licence question —
it is `robots.txt`, API policy, terms of service, collection method, and asset rights, each
managed on its own (FR-37..FR-42). Values: `allowed` · `allowed_with_conditions` · `restricted` ·
`indeterminate`.

### 9.5 Non-repository evidence path

Many entities — SaaS products, hosted services, marketplace listings, and most non-developer
tools — have **no repository**. Resolving licence "at the repository" would make them permanently
unresolvable and would cancel the audience segment §6 requires.

For these, the evidence path is (FR-89): **official terms of service · pricing page · privacy
policy · published commercial-use terms · official product documentation.** The code slot is
`not_applicable`; the disposition is derived from the terms found. A SaaS product whose ToS
permits business use on a paid plan reaches `cleared_with_conditions`, not `indeterminate`.

### 9.6 Unclear licence does not remove a tool

If existence, accessibility and relevance hold, an entity with an unresolved licence stays in the
corpus and may be listed publicly with its cautions. It is **excluded from the
commercially-usable filter** by §8.3, and its assets are not reused (§11). The four gates carry
four different bars — that separation is what preserves corpus size without ever telling a
visitor something is commercially usable when it was not established.

## 10. Quality model

"High-quality" is one of the four success words in §2 and previously had no definition. It is
defined here **independently of popularity**, and every criterion must be independently
verifiable from evidence the engine already collects or can collect.

| Criterion | Verifiable as |
|---|---|
| **Documentation adequacy** | official docs exist and cover installation/access, configuration, and at least one worked example |
| **Getting-started integrity** | the documented first-run path resolves — referenced links, packages or endpoints exist |
| **Maintenance responsiveness** | issues or support requests receive maintainer responses within the assessment window |
| **Release discipline** | versioned releases exist, with a changelog or release notes |
| **Operational stability** | no repeated confirmed outages or service interruptions in the window |
| **Provenance clarity** | an identifiable maintainer, vendor or organisation is stated and corroborated |
| **Description integrity** | the tool's own description matches what the documentation and interface actually offer |

**Explicitly excluded from quality:** stars, download counts, follower counts, and any social or
popularity metric. Those are collected and displayed as *interest signals* (FR-21) and are never
inputs to the quality disposition.

Quality resolves to a disposition per §8.2. `indeterminate` quality does not block
`publicly_listed`; it is displayed as a caution.

## 11. Visual assets

**Rights-confirmed icons only; everything else gets a neutral placeholder.**

- An open-source **code** licence is **never** treated as granting logo or trademark rights.
- A logo or icon may be stored, copied or processed **only** with an official brand guide, media
  kit, or explicit permission.
- Never scrape or self-host third-party images (FR-59).
- A favicon existing on the official site does **not** establish reuse rights.
- Icon rights are a **separate field** from the tool's licence.

```json
{
  "visual_asset": {
    "disposition": "indeterminate",
    "asset_type": "logo",
    "source_url": null,
    "usage_basis": null,
    "stored_locally": false
  }
}
```

`asset_reusable` requires `cleared`. Every other disposition renders the neutral placeholder, and
**unresolved visual assets are never queued for human review** (§8.5) — leaving them unresolved
is free.

## 12. Existing assets

### 12.1 The 1,161 records are frozen as a legacy seed manifest

They are **not** migrated to verified records.

**Preserved** — discovery facts only: URLs, prior identifiers (`entity_id`, `entity_key`), the
topic label, and first-seen timestamps.

**Not inherited** — no prior verification, licence, quality, privacy, security or
commercial-usability claim carries over. `description_source: verified` on 975 rows is
explicitly **not** a verification state (§3).

**Not publishable** until re-collected and passed through the gates in §8.3.

Rationale: every field the new model needs requires a fresh fetch regardless, so in-place
backfill buys nothing while paying remediation for 491 colliding identifiers, 137 URL sentinels
and 36 URLs shared by 77 rows. Freezing also drops the C9 prose-liability inherited from
awesome-list descriptions, and converts a blocked migration into an ordinary ingest whose
durable value is the ~1,024 usable URLs.

### 12.2 Pipeline replacement is contract-driven, not wholesale

Neither existing pipeline is adopted wholesale or discarded wholesale.

- **This PRD is the authoritative specification.**
- An existing component is reused **only** where it passes the new schema contract and the new
  behavioural contract defined here.
- Components that pass are reused as-is; components that do not are replaced incrementally
  behind the same contract.
- The committed publication layout (§3) is a candidate for reuse under this rule; the missing
  producer is new work either way.

## 13. Downstream Consumer Contract

The engine emits data and states what is guaranteed about it. Several guarantees hold **only if**
the consuming site behaves in a defined way. Those conditions live here, as conditions on the
engine's guarantee — not as requirements this PRD imposes on the website.

| The engine emits | The consumer must | If not |
|---|---|---|
| Records with `caution_flags[]` and licence cautions | display cautions alongside the record | the engine's C10 liability position does not hold; the guarantee is void |
| `commercially_usable` as a per-context boolean | filter on the same context the visitor intends | the claim is misapplied and the engine's precision figure does not transfer |
| `visual_asset.disposition` | render a neutral placeholder for anything not `cleared` | trademark exposure passes to the consumer |
| Per-segment coverage and `unknown` rate (FR-71) | not present coverage as broader than published | NFR-10's honesty guarantee is void |
| A retraction signal (FR-72) | remove or re-render the affected record | a withdrawn claim stays public |

**Consumer identification is an open item.** §18 records that no upstream document places this
engine inside the platform and that FR-67's artifact has no named consumer.

## 14. Feature groups and functional requirements

Requirement numbering is continuous with the pre-review revision. Modified requirements keep
their number; new numbers are used only for independently testable new behaviour.

### FG-A — Source management and discovery

- **FR-1** The engine SHALL maintain a source registry recording, per source: identifier,
  adapter type, the audience segment(s) it serves, the licence and terms of the source itself,
  its crawl policy, and whether it qualifies as official / primary / public / permitted under
  §6.3.
- **FR-2** Sources SHALL be tagged by audience segment so coverage can be measured per segment.
- **FR-3** The engine SHALL support at minimum: curated lists, official product directories,
  SaaS catalogues admissible under §6.3, vendor product and pricing pages, package/registry APIs,
  no-code and low-code marketplaces, and search expansion.
- **FR-4** From share-alike or otherwise restrictively-licensed sources the engine SHALL extract
  **only factual identifiers** (name, URL) and SHALL NOT ingest descriptive prose (C9). This
  applies to every ingest, including re-collection of legacy seed entries (§12.1).
- **FR-5** The engine SHALL record per source the last successful harvest and the count of new
  entities yielded.
- **FR-6** *(modified)* A source yielding no new entities across a configured threshold —
  **default three consecutive runs** — SHALL be flagged exhausted, reported, and removed from
  the active rotation until replenished. Exhaustion SHALL raise a **replenishment task**
  identifying the affected audience segment, so a known-exhausted lane is not silently starved.
- **FR-7** Adding a source SHALL NOT require code changes to the harvest loop. *(Configuration
  dependency — see §17.)*

### FG-B — Candidate extraction and identity

- **FR-8** Every entity SHALL carry a stable, globally unique identifier that survives
  re-harvest and is never re-issued by a later run.
- **FR-9** *(modified)* Identity SHALL be resolved on the canonical target URL **together with a
  continuity check**: where a URL's ownership, namespace or maintainer changes, the engine SHALL
  treat it as a **new identity**, invalidate inherited assertions, and SHALL NOT carry forward
  prior human review decisions (FR-65).
- **FR-10** The engine SHALL NOT emit a sentinel string such as `"unknown"` in a URL field; an
  absent URL SHALL be null with a recorded reason code.
- **FR-11** *(modified)* The same entity discovered through multiple sources SHALL merge into one
  record carrying a multi-source provenance list. Merge SHALL be refused where the candidates
  disagree on canonical identity, and SHALL NOT merge two entities that share a URL without
  sharing an identity.
- **FR-12** *(modified)* Conflicting field values from different sources SHALL set the affected
  assertion's evidence state to `conflicting` (§8.1) and record each source's claim. They SHALL
  NOT be silently overwritten, and SHALL NOT be auto-resolved in favour of any single source
  type.
- **FR-13** Descriptions SHALL be attributed to how they were obtained, and SHALL be
  independently re-writable without losing the evidence link. `description_source` SHALL NOT be
  used to derive any verification or disposition state.

### FG-C — Existence and accessibility verification

- **FR-14** For each official URL the engine SHALL record HTTP status, fetch timestamp and
  content hash.
- **FR-15** *(modified)* Unreachable official links SHALL produce reason code
  `EXIST_UNREACHABLE` and a `blocked` existence disposition — **only after** FR-16's window is
  exhausted, and **only where** the failure is attributable to the target rather than to our own
  fetch being refused (FR-42).
- **FR-16** *(modified)* The engine SHALL distinguish transient failure from persistent
  unavailability, requiring a configured number of failures across a configured window —
  **default three failures across fourteen days** — before declaring discontinuation.
- **FR-17** The engine SHALL detect explicit end-of-life signals — repository archived flags,
  sunset notices, deprecation banners — producing `EXIST_DISCONTINUED`.
- **FR-18** *(modified)* The engine SHALL corroborate that a claimed official source belongs to
  the tool, using at least two of: vendor domain correspondence, repository owner correspondence,
  cross-reference from an independent official source, or package-registry ownership metadata.
  `EXIST_UNIDENTIFIABLE` SHALL be asserted only when corroboration fails **and** the failure is
  itself evidenced — never on absence of a signal alone.

### FG-D — Maintenance and currency

- **FR-19** The engine SHALL collect multiple currency signals: last commit, last release,
  release cadence, issue and PR activity, and whether the hosted service responds.
- **FR-20** *(modified)* A currency verdict SHALL be derived from at least two independent
  signals **available for that entity type** — for entities with no repository, the applicable
  signals are service responsiveness, documentation/changelog updates, and published release or
  status notices. Where signals disagree, the currency disposition SHALL be `indeterminate` and
  the disagreement recorded. Stars alone SHALL NOT establish currency.
- **FR-21** Popularity metrics SHALL be collected and labelled **as interest signals**, distinct
  from currency and excluded from quality (§10).
- **FR-22** GitHub metadata SHALL be fetched **after** target-URL resolution, correcting the
  ordering defect in §3.
- **FR-23** The engine SHALL support backfilling popularity metadata for existing records
  without a full re-harvest.

### FG-E — Licence and commercial usability

- **FR-24** *(modified)* Licence SHALL be resolved from **primary sources for the artifact
  type** — the repository for code artifacts, and the §9.5 evidence path for artifacts with no
  repository. It SHALL never be taken from a registry or directory listing (C2).
- **FR-25** Licence detection SHALL scan multiple locations: `LICENSE*`, `COMM-LICENSE*`,
  `licenses/`, per-directory licence files, `NOTICE`, package manifests, README licence
  sections, and `/ee` or `/enterprise` subdirectories. Where subdirectory terms differ from the
  root, both SHALL be recorded and the stricter SHALL govern the disposition.
- **FR-26** *(modified)* Licence SHALL be stored in the **three-slot model of §9.1** — code,
  data, model-artifact — each slot carrying its class, SPDX expression where applicable, raw
  licence-text hash, ScanCode category, and its own evidence record. Conflicting evidence SHALL
  be representable via `conflicts[]`.
- **FR-27** `license_evidence` SHALL be a structured record — detected identifier, detector,
  confidence, source path and line range, manifest value, disagreement flags, category, reviewer
  and date. Never a bare string.
- **FR-28** *(modified)* Licence disposition SHALL take a value from §8.2 (`cleared`,
  `cleared_with_conditions`, `blocked`, `indeterminate`, `review_required`) and SHALL be derived
  by the five-bucket policy in §9.2. The previous five-value `license_status` vocabulary is
  replaced; its distinctions are preserved as slot class (§9.1) plus evidence state (§8.1).
- **FR-29** Disagreement between LICENSE file, manifest and headers SHALL set the evidence state
  to `conflicting` and route to human review. It SHALL NOT be auto-resolved in the manifest's
  favour (C7).
- **FR-30** SPDX `OR` expressions SHALL route to human review — electing a licence is a legal
  act.
- **FR-31** Rider-bearing licences and modified texts of known licences SHALL route to human
  review (C3).
- **FR-32** *(modified)* Thresholds and conditions expressed in licence prose SHALL be captured
  as structured `conditions[]` and `restrictions[]` entries carrying type, comparator, value,
  unit and scope — expressive enough to represent MAU counts, revenue limits, company size,
  territorial exclusions, field-of-use restrictions, and naming or attribution obligations.
- **FR-33** *(modified)* The engine SHALL record the ownership and commercial terms of
  **generated output** where the entity publishes them, and SHALL set that component to
  `indeterminate` with reason code `LIC_OUTPUT_TERMS_ABSENT` where it does not. Absence SHALL
  NOT block `commercially_usable` **for usage contexts that do not involve generated output**,
  and SHALL block it for contexts that do.
- **FR-34** The engine SHALL record whether an enterprise licence or additional contract is
  required.
- **FR-35** *(modified)* Free-tier versus paid-tier commercial terms SHALL be recorded separately
  from any open-source licence, sourced from the §9.5 evidence path, and SHALL be
  `indeterminate` where the vendor does not publish them.
- **FR-36** Licence determination SHALL be pinned to a specific commit SHA or product version.
- **FR-87** *(new)* The licence disposition SHALL be computed from ScanCode category, detected
  riders, detected thresholds, evidence state and usage context. **A disposition SHALL NOT be
  derived from an SPDX identifier alone**, and no allow/deny decision may be implemented as a
  lookup keyed only on an identifier.
- **FR-88** *(new)* `end_user_use` SHALL be resolved **per usage context** (`internal_use`,
  `redistribution`, `hosted_service`, `model_training`) from conditions, restrictions, usage
  context and evidence source, per §9.3. A single scalar commercial-use verdict SHALL NOT be
  emitted.
- **FR-89** *(new)* For entities with no repository the engine SHALL resolve licence and
  commercial terms from official terms of service, pricing pages, privacy policy, published
  commercial-use terms, and official product documentation, recording which of these supplied
  each assertion.

### FG-F — Catalog rights (`catalog_use`)

- **FR-37** `catalog_use` SHALL be assessed independently of FG-E (§9.4).
- **FR-38** *(modified)* The engine SHALL check `robots.txt` and record the specific directive
  applying to its own user agent. Where no directive is found, `catalog_use` for crawling SHALL
  be `allowed` by default and recorded as such — absence of a directive is a permissive fact, not
  an unknown.
- **FR-39** *(modified)* The engine SHALL check terms of service and API terms for restrictions
  on reuse or redistribution of metadata **where such terms are published and machine-reachable**,
  and SHALL set `indeterminate` with a reason code where they are not. This requirement SHALL NOT
  be read as requiring legal interpretation of every entity's ToS.
- **FR-40** *(modified)* Attribution requirements SHALL be recorded per entity where stated by
  the source, and SHALL default to `indeterminate` where not stated.
- **FR-41** `catalog_use` SHALL take one of: `allowed`, `allowed_with_conditions`, `restricted`,
  `indeterminate`.
- **FR-42** *(modified)* Crawl restrictions SHALL be respected at fetch time. A fetch refused by
  our own compliance SHALL be recorded with evidence state `unavailable` and SHALL NOT produce
  `EXIST_UNREACHABLE` (FR-15).

### FG-G — Audience and non-developer usability

- **FR-43** Every entity SHALL carry the `audience` object defined in §6.1.
- **FR-44** *(modified)* Every entity SHALL carry the `non_developer_usability` object defined in
  §6.2, populated from primary evidence — the product's own site, documentation, pricing page, or
  a marketplace listing whose structure is itself evidence.
- **FR-45** Audience suitability SHALL be expressed positively. A negative-only
  `developer_only`-style flag SHALL NOT be used.
- **FR-46** Where evidence is absent or weak, audience fields SHALL remain `indeterminate`.
  Non-developer suitability SHALL NEVER be assumed.
- **FR-47** *(modified)* Every non-developer suitability determination SHALL carry
  `evidence_urls` pointing to **primary or official sources**. Third-party directory or affiliate
  listings SHALL NOT satisfy this requirement on their own.
- **FR-48** *(modified)* The engine SHALL report corpus coverage **per audience segment**,
  including the proportion of entities whose audience disposition is `indeterminate`.

### FG-H — Security and privacy screening

- **FR-49** The engine SHALL query a vulnerability data source (OSV, GitHub Advisory, CVE) —
  a **new capability** not present today.
- **FR-50** *(modified)* Until FR-49 is implemented, the security evidence state SHALL be
  `unchecked`. Under §8.3 this prevents `commercially_usable`, does not affect
  `corpus_included`, and does not queue review. The engine SHALL NOT claim security verification
  is complete.
- **FR-51** *(modified)* A confirmed unresolved serious vulnerability SHALL set the security
  disposition to `blocked` with reason code `SEC_VULN_UNRESOLVED`. Where an entity has no
  package coordinates and cannot be queried, the state is `unchecked`, not `cleared`.
- **FR-52** A recent security issue whose resolution is unconfirmed SHALL produce a caution
  (§7.2), not a `blocked` disposition.
- **FR-53** Every entity SHALL carry the `privacy` object defined in §7.4.
- **FR-54** *(modified)* The privacy disposition SHALL be `blocked` only for the evidenced
  conditions in §7.4, each carrying its reason code and corroborating evidence. Opacity SHALL
  produce a caution and an `indeterminate` disposition.
- **FR-55** Detected spam, impersonation or malware distribution SHALL set the safety disposition
  to `blocked` with reason code `SAFE_MALICIOUS`, which also removes `corpus_included` (§8.3).

### FG-I — State, disposition and gating

- **FR-56** *(modified)* Every record SHALL carry per-domain dispositions (§8.2), the reason
  codes producing any `blocked` state, and the display `caution_flags[]` drawn from
  `needs-review` · `caution` · `possibly-inactive` (§7.2).
- **FR-57** *(modified)* The engine SHALL compute the four gates of §8.3 —`corpus_included`,
  `publicly_listed`, `commercially_usable`, `asset_reusable` — as **derived properties**,
  recomputed from current dispositions on every assessment and never stored as independent truth.
- **FR-58** *(modified)* `commercially_usable` SHALL require **all** of: `publicly_listed`;
  licence disposition `cleared` or `cleared_with_conditions`; `end_user_use` for the requested
  context `allowed` or `allowed_with_conditions`; privacy disposition neither `blocked` nor
  `indeterminate`; security disposition neither `blocked` nor `indeterminate`.
- **FR-59** `asset_reusable` SHALL require a `cleared` visual-asset disposition (§11).
- **FR-60** *(modified)* Gates requiring confirmed evidence SHALL be satisfied **only** by an
  explicit affirmative disposition (`cleared` or `cleared_with_conditions`), evaluated as an
  allowlist. `indeterminate`, `unchecked` and `unavailable` SHALL NOT satisfy them.
  `corpus_included` is exempt: it is refused only by a confirmed failure (§8.4).
- **FR-61** Every gate decision SHALL be explainable — storing the rule applied, the dispositions
  relied on, and the evidence behind each.
- **FR-83** *(new)* Every assertion SHALL carry an evidence record with `{state, reason_code,
  evidence_urls[], method, detector, confidence, checked_at}`, where `state` is one of the six
  values in §8.1. `absent`, `unchecked` and `unavailable` SHALL be distinguishable and SHALL NOT
  be collapsed into a single value at any layer, including the published artifact.
- **FR-84** *(new)* Each domain SHALL resolve to exactly one disposition from §8.2. A `blocked`
  disposition SHALL always carry a reason code; a disposition SHALL NOT be `blocked` on the basis
  of missing evidence alone.
- **FR-85** *(new)* `corpus_included` SHALL be TRUE unless the existence disposition is `blocked`,
  or the safety or privacy disposition is `blocked` for a `SAFE_*` or `PRIV_MALICIOUS_DESIGN`
  reason code. `indeterminate` SHALL NOT reduce corpus membership.
- **FR-86** *(new)* `publicly_listed` SHALL be TRUE when `corpus_included` is TRUE, the existence
  disposition is `cleared` or `cleared_with_conditions`, no domain is `blocked`, and catalog
  rights are `cleared` or `cleared_with_conditions`. A licence disposition of `indeterminate`
  SHALL NOT prevent public listing.

### FG-J — Human review

- **FR-62** *(modified)* The engine SHALL provide a human review queue with a defined artifact
  schema. **Accountability sits with the existing Knowledge Team.** The role performing
  individual reviews is the **Catalog Review Operator**, defined as a role and **not** requiring
  a new standing team; it may be discharged by existing staff, rotation, or contracted
  specialists. The role's competency requirement — licence election is a legal act (FR-30) — is
  stated so staffing can be matched to it.
- **FR-63** *(modified)* An item SHALL enter the queue **only** when an unresolved judgement
  could materially change `publicly_listed`, `commercially_usable`, or an already-published
  high-risk claim (§8.5). Qualifying triggers are the human-review row of §9.2, plus
  **high-confidence permissive detections whose licence text hash does not match the canonical
  text of the detected identifier** — the C7 stripped-clause asymmetry. Items SHALL NOT be queued
  merely for being `indeterminate`, for visual assets whose rights are unresolved, or for
  `unavailable` caused by an external outage.
- **FR-64** Reviewer decisions SHALL record reviewer identity, date, rationale and the evidence
  consulted.
- **FR-65** *(modified)* Reviewer decisions SHALL survive re-harvest and SHALL NOT be overwritten
  by automated re-assessment without flagging the change — **except** where FR-9's continuity
  check or FR-82's change detection invalidates the basis of the decision, in which case the
  decision SHALL be invalidated and re-queued.
- **FR-66** *(modified)* Queue depth, queue age, decision throughput and time-to-decision SHALL
  be reportable.
- **FR-92** *(new)* The queue SHALL have a declared **capacity** and a **processing SLA** by
  priority class, and SHALL define **over-capacity behaviour**: when open items exceed capacity,
  the engine SHALL throttle intake of review-generating assessments — not collection — and SHALL
  leave the affected strong claims unmade rather than approximated. Over-capacity events SHALL be
  reported.

### FG-K — Publication output

- **FR-67** The engine SHALL produce a versioned publication artifact against an explicit,
  documented schema contract.
- **FR-68** *(modified)* Only records satisfying `publicly_listed` SHALL be emitted. The artifact
  SHALL carry each record's dispositions, reason codes and cautions, not only its positives.
- **FR-69** *(modified)* Each emitted record SHALL carry the caution and disposition data the
  consumer needs to satisfy §13. The engine SHALL NOT specify how the consumer renders it.
- **FR-70** Publication SHALL be atomic and idempotent and SHALL produce a manifest.
- **FR-71** *(modified)* The artifact SHALL carry a **coverage statement per audience segment,
  including the `indeterminate` rate per assessed domain**, so a consumer cannot present coverage
  as broader than the data supports.
- **FR-72** The engine SHALL provide a retraction path that removes a previously published record
  and records why.

### FG-L — Automation and operations

- **FR-73** The engine SHALL run unattended on a schedule, without a human launching a session.
- **FR-74** The engine SHALL detect and back off on rate limiting (HTTP 429 and provider session
  limits).
- **FR-75** Concurrency SHALL be capped and configurable. *(Configuration dependency — §17.)*
- **FR-76** Each run SHALL emit a manifest with counts by evidence state, disposition and gate.
- **FR-77** *(modified)* Failure of one lane SHALL NOT fail the whole run **where the failure is
  lane-local**. Shared-quota exhaustion SHALL be recognised as a run-level condition, SHALL
  suspend the run, and SHALL leave completed work resumable rather than discarded.
- **FR-78** A child process exiting 0 SHALL NOT be treated as evidence the target was met;
  completion SHALL be re-derived from the data.

### FG-M — Re-verification, freshness and change response

- **FR-79** Every assertion SHALL carry its own `checked_at`, not one timestamp per record.
- **FR-80** Re-verification cadence SHALL be configurable **per assertion class** — licence,
  currency, availability, privacy, security, audience, quality. *(Configuration dependency —
  §17.)*
- **FR-81** *(modified)* Assertions older than their cadence SHALL move to evidence state
  `unchecked`, which under §8.3 withdraws the gates requiring confirmation while leaving corpus
  membership intact. Decay SHALL NOT by itself enqueue human review (§8.5).
- **FR-82** *(modified)* On detecting a relicensing or terms change — via the pinned SHA/version
  of FR-36, a licence text-hash change, or a published terms update — the engine SHALL execute
  the transition: **(1)** invalidate the affected assertions and any human decision resting on
  them; **(2)** recompute all four gates; **(3)** enqueue human review where the change is
  materially ambiguous under §8.5; **(4)** retract any published record whose claim no longer
  holds (FR-72); **(5)** re-publish only after re-verification. Time-triggered conversions —
  BUSL Change Dates, FSL two-year reversion — SHALL be scheduled from recorded dates and SHALL
  NOT depend on a repository change to fire.

### FG-N — Quality assessment *(new group)*

- **FR-90** *(new)* The engine SHALL assess quality against the criteria in §10 —
  documentation adequacy, getting-started integrity, maintenance responsiveness, release
  discipline, operational stability, provenance clarity, description integrity — each recorded as
  its own assertion with evidence, and SHALL resolve a quality disposition per §8.2. Popularity
  and social metrics SHALL NOT be inputs.

### FG-O — Legacy corpus and component reuse *(new group)*

- **FR-91** *(new)* The existing 1,161 records SHALL be frozen as a **legacy seed manifest**
  preserving discovery facts only (§12.1). No prior verification, licence, quality, privacy,
  security or commercial-usability claim SHALL be inherited, and no legacy record SHALL be
  published until re-collected and passed through §8.3.
- **FR-96** *(new)* An existing pipeline component SHALL be reused only where it passes the
  schema contract and behavioural contract defined in this PRD; components that do not SHALL be
  replaced incrementally behind the same contract (§12.2).

### FG-P — Measurement and evaluation *(new group)*

- **FR-93** *(new)* The engine SHALL maintain a **gold set** of entities with human-adjudicated
  licence, commercial-usability and quality verdicts, spanning permissive, copyleft,
  network-copyleft, source-available, rider-bearing, absent-licence and non-repository cases.
  Each release SHALL be evaluated against it and SHALL report precision and recall per
  disposition bucket.
- **FR-94** *(new)* The engine SHALL draw a periodic random **audit sample** from published
  records asserting `commercially_usable`, have it adjudicated by a Catalog Review Operator, and
  report the observed false-permissive rate. NFR-1 is measured by this sample; without it the
  claim is unverifiable.
- **FR-95** *(new)* The engine SHALL emit the success metrics and counter-metrics of §16 as run
  outputs, and SHALL make a release's metric deltas available before publication.

### FG-Q — Configuration and implementation constraints *(new group)*

- **FR-97** *(new)* Requirements that depend on changing committed configuration — source
  registry (FR-1, FR-3, FR-7), vocabularies and thresholds (FR-6, FR-16, FR-28, FR-41),
  concurrency (FR-75), cadences (FR-80), audience axes (FR-43) — SHALL be implementable without
  violating the repository's validation gate. Because 33 of 39 wrappers currently assert `config/`
  is unmodified (§3, §17), the implementation SHALL either amend those assertions or relocate
  mutable configuration to a path the gate permits. This constraint SHALL be resolved before
  implementation begins and SHALL NOT be left silently impossible.

## 15. Non-functional requirements

- **NFR-1** *(modified)* **Claim safety.** No record may present as commercially usable without
  an affirmative licence disposition and an affirmative `end_user_use` for the requested context.
  This is enforced structurally by FR-58 and FR-60, and **measured** by FR-94's audit sample.
  False positives on this claim are the product's most serious defect class; the target is
  ≥99% precision on the audit sample (§16 SM-2 / CM-1).
- **NFR-2** *(modified)* **Review capacity.** The human review load target is **15–20% of
  assessed items — an initial measurement target, not a guarantee.** The system SHALL declare a
  queue capacity and a processing SLA (FR-92), SHALL define over-capacity behaviour, and SHALL
  report actual load against target. If measured load materially exceeds target, the response is
  to narrow triggers (§8.5) or to add capacity — never to relax FR-58.
- **NFR-3** **Auditability.** Every published assertion SHALL be traceable to an evidence URL, a
  timestamp, a detector and the rule that produced it. A reviewer SHALL be able to reconstruct
  any verdict without re-running the pipeline.
- **NFR-4** **Freshness.** Availability and currency assertions SHALL be re-verified on a cadence
  short enough that a discontinued tool does not remain listed as live. Licence assertions SHALL
  be re-verified on a cadence appropriate to observed relicensing frequency.
- **NFR-5** *(modified)* **Legal readiness.** Counsel-reviewed disclaimer language SHALL be in
  place **before** launch, covering the commercial-usability claim, the verification claim, and
  their stated limits — specifically: artifact-scoped only (no transitive-dependency analysis,
  addendum §2.3), point-in-time validity, and per-usage-context applicability.
- **NFR-6** **Collection etiquette.** The engine SHALL identify itself by user agent, honour
  `robots.txt`, and respect published rate limits. Restrictions are enforced, not merely logged.
- **NFR-7** *(modified)* **Reproducibility.** Given the same inputs and pinned versions, a run
  SHALL produce the same dispositions and gate outcomes. Model-driven steps SHALL record their
  inputs and outputs so a verdict can be explained and replayed after the fact.
- **NFR-8** **Data integrity.** Writes SHALL be atomic; a partial run SHALL NOT produce a partial
  publication; concurrent lanes SHALL NOT share a mutable file.
- **NFR-9** **Cost control.** Model invocations per run SHALL be bounded and reportable. Privacy,
  audience and quality assessment are the expensive paths and SHALL be budgeted explicitly, with
  assessment gated on prior existence and accessibility checks and cached against a content hash.
- **NFR-10** **Coverage honesty.** The published data SHALL carry its own coverage limits and
  `indeterminate` rates (FR-71). The engine's guarantee is conditioned on §13.
- **NFR-11** *(modified)* **Degradation.** When an external dependency is unavailable, affected
  assertions SHALL be recorded as `unavailable` — distinct from `absent` and `unchecked`.
  Previously confirmed assertions SHALL retain their state until their cadence lapses, so a
  dependency outage SHALL NOT cause mass withdrawal of existing claims.
- **NFR-12** *(new)* **Automation rate.** The engine SHALL target **80–85% of assessed items
  auto-dispositioned without human review** — an initial measurement target derived from the
  research, to be re-measured against our own corpus. Actual rate SHALL be reported per run
  (§16 SM-1).
- **NFR-13** *(new)* **Detectability.** Every NFR making a numeric claim SHALL have a
  corresponding measurement in §16 and a harness that can observe a violation. An NFR with no
  instrument SHALL NOT be stated as a guarantee.

## 16. Success metrics and counter-metrics

Every metric is paired with a counter-metric that makes the opposite failure visible. The thesis
being measured is **reduced discovery and comparison cost at a defensible claim quality** — so
breadth and precision are measured against each other, deliberately.

| ID | Success metric | Counter-metric | Source |
|---|---|---|---|
| **SM-1** | **Auto-disposition rate** — share of assessed items resolved without human review. Target 80–85% (NFR-12). | **CM-1: false-permissive rate** in the auto-allow bucket, from FR-94's audit sample. Guards against hitting SM-1 by loosening the classifier. | FR-95, FR-94 |
| **SM-2** | **Commercial-usability precision** — share of published `commercially_usable` records the audit sample confirms. Target ≥99% (NFR-1). | **CM-2: unclaimed-but-usable rate** — share of the corpus where `commercially_usable` is false solely because of `indeterminate` evidence. Guards against hitting SM-2 by never claiming anything. | FR-94, FR-95 |
| **SM-3** | **Coverage per audience segment** — entities published per segment, non-developer tracked separately. | **CM-3: evidence-backed audience share** — proportion of audience labels backed by primary evidence rather than left `indeterminate`. Guards against coverage inflated by unevidenced labels. | FR-48, FR-71 |
| **SM-4** | **Freshness** — share of published records whose assertions are within cadence. | **CM-4: retraction rate** (FR-72). Guards against freshness achieved by dropping anything hard to re-verify. | FR-79, FR-81 |
| **SM-5** | **Time-to-decision** — median and p90 age of resolved review items against the FR-92 SLA. | **CM-5: reversal rate** — reviewer decisions later overturned. Guards against speed bought with correctness. | FR-66, FR-92 |
| **SM-6** | **Gold-set performance** — precision and recall per disposition bucket, per release. | **CM-6: gold-set drift** — share of gold-set entities whose ground truth changed since adjudication, indicating the set is stale rather than the engine improved. | FR-93 |

Baselines are set from the first full run; targets before that point are the research-derived
figures in NFR-2 and NFR-12 and are explicitly provisional.

## 17. Implementation constraints

**The validation gate currently forbids what several requirements need.** 33 of 39 taxonomy
wrappers assert `config/` is unmodified, so no checkpoint editing `config/` can pass
`validate_task.sh`. The requirements that are configuration changes by nature are FR-1, FR-3,
FR-6, FR-7, FR-16, FR-28, FR-41, FR-43, FR-75 and FR-80.

Two admissible resolutions, both requiring a decision before implementation:

1. **Amend the wrapper assertions** so that declared-mutable configuration paths are excluded
   from the immutability check, keeping the check for everything else.
2. **Relocate mutable configuration** to a path the gate permits, leaving `config/` as
   genuinely immutable policy.

FR-97 requires one of these to be chosen. It is recorded here rather than left as an
implementation surprise.

## 18. Open items

**Carried, with disposition:**

- **Downstream consumer is unidentified.** FR-67's artifact has no named consumer, and no
  upstream document places this engine inside the platform — `docs/README.md` was never written
  and `product-scope.md` cites it anyway (§3). §13 states the contract; the counterparty is
  still unnamed. *Blocking for FR-67's schema design.*
- **Upstream review process overlap.** The platform already operates a Knowledge Team weekly
  review in Notion with its own status model. FR-62 assigns accountability there, but the
  integration — whether the Catalog Review Operator works inside that process or alongside it —
  is unresolved, as are the competency, capacity and cadence mismatches the review gate
  identified (licence election vs. summarisation; continuous vs. weekly batch).
- **Upstream tag vocabulary does not cover `skill`.** The platform's `building-blocks` sub-tags
  are `building-blocks-mixed` / `agents` / `mcp` / `prompt`. `skill` is this engine's largest
  topic (359 of 1,161) and its only unexhausted seed.
- **Non-developer audience has no upstream consumer.** The upstream document is titled "Cherry
  for AI Engineers" and contains no non-developer concept. §6 makes non-developer assessment
  mandatory and the addendum names it the most expensive path. The consumer for that field is
  unconfirmed.
- **Competitor landscape is unevidenced.** The commissioned survey delivered only its licence
  section. No evidenced view of who else does this or how they gate quality.
- **`EXIST_UNIDENTIFIABLE` and `LIC_INFRINGEMENT` carry residual exposure.** Both are
  publishable adverse assertions about a named third party. FR-18 and §7.1 require corroborating
  evidence, but the standard of proof is a legal question for NFR-5's counsel review.
- **C7's base rate is 2015-era and non-peer-reviewed.** §9's trade-off is sized off it. SM-1
  re-measures it against our own corpus; until then the sizing is provisional.
- **Seed replenishment is a task, not a plan.** FR-6 raises replenishment tasks; which sources
  fill the exhausted `agent` and `prompt` lanes is undecided.

**Accepted risks:**

- **No transitive-dependency licence analysis** (addendum §2.3). Documented, disclaimed under
  NFR-5, and revisited if a production-grade term-level analyser appears.
- **Artifact-scoped, point-in-time claims only.** The engine never asserts anything about a
  dependency closure or about future releases.
- **`unavailable` is not reviewed.** An external outage leaves claims withdrawn by cadence rather
  than escalated; this trades some freshness for a queue that stays staffable.

## 19. Provenance

| Source | Artifact |
|---|---|
| This repository (`axCaseResearch4`) | [`extract-repo-baseline.md`](extract-repo-baseline.md) |
| AI-artifact licensing (weights, prompts, datasets, HF metadata, MCP registry) | [`extract-license-landscape.md`](extract-license-landscape.md) |
| Licence families, relicensing 2023–2026, dual licensing and CLAs | [`extract-license-families.md`](extract-license-families.md) |
| Detection tooling and its measured accuracy ceiling | [`extract-license-tooling-accuracy.md`](extract-license-tooling-accuracy.md) |
| Licence determination revised on primary sources — **supersedes** the licence conclusions in the landscape extract | [`extract-license-determination-revised.md`](extract-license-determination-revised.md) |
| `docs/PRD/product-scope.md` (upstream platform scope) | read directly; used to fix the scope boundary in §1 and the overlaps in §18 |

Decision trail: [`.memlog.md`](.memlog.md).
