# Proposal — multi-axis case facets and shared discovery

**Revision 4. Status: APPROVED DESIGN. Nothing implemented.** Stage 0–2 code is untouched and Stage
3 remains blocked. R1–R4 and V1–V4 are all decided; no design question remains open.

```text
revision:                    4
status:                      approved design — not implemented
approved_at_commit:          3b85a8102fb89ae0585ef0fc080f518238e4c1bc  (short: 3b85a81)
implementation_start_anchor: 8865c54e2cc8d879410576f247baac4aea149f34  (short: 8865c54)
implementation_plan:         docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md (proposed)
errata:                      see §16 — read it with §1.3, §5 and §13
```

**Revision-number correction.** The header of this file previously read "Revision 2. Status:
PROPOSAL … Awaiting approval", while the handoff called it revision 3 and `HANDOFF_CURRENT.md` /
`TODO.md` called it revision 4. The *content* has been consistent with the approved decisions
throughout; only the header was stale. **Revision 4 is the correct designation**, and the status is
approved, not awaiting approval.

Renamed from "domain facets": the field is `case_facets`, because it applies across the Cases topic
rather than to one category.

---

## 0 · Decision table

| # | Item | Status |
|---|---|---|
| 1 | Three independent axes (industry / business function / use-case type) | **Approved** |
| 2 | `Cases → Domain Applications` stays the publication category; 12 cells unchanged | **Approved** |
| 3 | Facets excluded from `record_id` / `content_id` / `identity_url` / publication path | **Approved** |
| 4 | Versioned per-dimension vocabularies with evidence-grounded assignment | **Approved** |
| 5 | Shared source discovery → shared candidate pool → dedup → classify → coverage → gap lanes | **Approved** |
| 6 | Discovery provenance never forces a label | **Approved** |
| 7 | Acceptance thresholds never lowered to satisfy coverage | **Approved** |
| — | | |
| C1 | `domain_facets` → **`case_facets`** | **Corrected** (§3) |
| C2 | Uniform `target_min` → **per-value coverage policy** (priority/standard/record_only) | **Corrected** (§2) |
| C3 | Coverage targets are **scheduler hints, never acceptance gates** | **Corrected** (§7) |
| C4 | Gap ranking uses 7 factors, not remaining-gap alone | **Corrected** (§7) |
| C5 | Add **`cross-industry`**; secondary = deployment context only, not conglomerate portfolio | **Corrected** (§1.1, §2) |
| C6 | `technology-software` = `record_only`; never inferred from publisher/vendor/platform | **Corrected** (§1.1, §5) |
| C7 | "fetched once per **round**" → once per **run**, keyed by `source_request_key` | **Corrected** (§8) |
| C8 | `fetch_count <= 1` → **logical-owner** invariants; HTTP attempts counted separately | **Corrected** (§9) |
| C9 | Lane terms *may* become evidence when independently found in the document | **Corrected** (§10) |
| C10 | Four distinct unresolved states, not blanket `other-unclear` | **Corrected** (§6) |
| C11 | Single source of truth for vocabulary; generated constraints with 5 guardrails | **Corrected** (§11) |
| C12 | New **Stage 2.5** checkpoint; full 199-assertion baseline rerun | **Corrected** (§12) |
| C13 | `other-unclear` alone must not satisfy the domain-applications requirement | **Corrected** (§4) |
| C14 | Mandatory smoke = round 1 only; optional `smoke-adaptive` | **Corrected** (§7.4) |
| — | | |
| R1 | Priority tier membership across all three axes | **Decided** (§2) |
| R2 | `case-studies` enrichment = `report_only` in v1, not a gate | **Decided** (§4) |
| R3 | **No** mid-run conditional revalidation; run-scoped immutable snapshot | **Decided** (§8.3) |
| R4 | `cross-industry` = `record_only`, `target_min` 0, never closes a concrete gap | **Decided** (§2.3) |
| — | | |
| V1 | 4 added values approved; counts become 18 / 19 / 22 | **Decided** (§15.1) |
| V2 | `legal-risk-compliance` approved; security function narrowed to `information-security` | **Decided** (§15.2) |
| V3 | No bare `operations`; both concrete operations functions are priority | **Decided** (§15.3) |
| V4 | `customer-interaction` added as a distinct priority value | **Decided** (§15.4) |

**No decisions remain open.**

---

## 1 · Controlled vocabularies

Three versioned files. Every entry carries: `slug`, `display_name`, `definition`, `positive_terms`,
`synonyms`, `exclusions`, `disambiguation`, `parent_group` (UI navigation only, never semantic),
`coverage_policy`, `status` (`active`|`deprecated`), `replaced_by`.

### 1.1 `config/harvest/facets/industries.v1.json` — *whose problem*

**18 entries** (17 previously proposed + `cross-industry`, added per correction C5).

| # | slug | display name | parent_group | coverage | boundary |
|---|---|---|---|---|---|
| 1 | `financial-services-insurance` | Financial Services & Insurance | Regulated | **priority** | banks, insurers, capital markets, fintech. **Not** the finance department |
| 2 | `healthcare-life-sciences` | Healthcare & Life Sciences | Regulated | **priority** | providers, payers, pharma, biotech, medtech |
| 3 | `retail-cpg` | Retail & CPG | Consumer | **priority** | retailers, e-commerce, grocery, consumer brands |
| 4 | `manufacturing-industrial` | Manufacturing | Industrial | **priority** | discrete + process manufacturers |
| 5 | `professional-services` | Professional Services | Services | **priority** | **law firms**, consulting, accounting firms, agencies |
| 6 | `public-sector-government` | Public Sector | Regulated | **priority** | agencies, defence, civic services |
| 7 | `education-research` | Education | Regulated | **priority** | schools, universities, research institutes. **Not** corporate training |
| 8 | `energy-utilities-resources` | Energy, Utilities & Resources | Industrial | standard | power, oil & gas, mining, water |
| 9 | `transportation-logistics` | Transportation & Logistics | Industrial | standard | carriers, 3PL, freight, mobility |
| 10 | `agriculture-food` | Agriculture & Food | Industrial | standard | growers, food production |
| 11 | `real-estate-construction` | Real Estate & Construction | Industrial | standard | AEC, property |
| 12 | `travel-hospitality` | Travel & Hospitality | Consumer | standard | airlines, hotels, restaurants |
| 13 | `media-entertainment` | Media & Entertainment | Consumer | standard | publishers, studios, gaming, music |
| 14 | `telecommunications` | Telecommunications | Consumer | standard | carriers, network operators |
| 15 | `nonprofit-social-impact` | Nonprofit & Social Impact | Services | standard | NGOs, foundations |
| 16 | `technology-software` | Technology & Software | Services | **record_only** | the *adopting org* sells software. See §5.1 |
| 17 | `cross-industry` | Cross-Industry | — | **record_only** | deployment genuinely horizontal. See §2.3 |
| 18 | `other-unclear` | Other / Unclear | — | **record_only** | source does not support a more specific value |

**7 priority · 8 standard · 3 record_only = 18.**

### 1.2 `config/harvest/facets/business-functions.v1.json` — **19 entries**

Was 18. `knowledge-management` is **new** (V1) — the approved priority list names it and no existing
value covered it. `legal-compliance` is **renamed** `legal-risk-compliance` (V2).

| # | slug | display name | coverage |
|---|---|---|---|
| 1 | `customer-service-support` | Customer Service & Support | **priority** |
| 2 | `marketing` | Marketing | **priority** |
| 3 | `sales` | Sales | **priority** |
| 4 | `human-resources` | HR & People | **priority** |
| 5 | `finance-accounting` | Finance & Accounting | **priority** |
| 6 | `legal-risk-compliance` | Legal, Risk & Compliance | **priority** *(legal work, contracts, governance, audit, regulatory compliance, enterprise **non-security** risk)* |
| 7 | `supply-chain-operations` | Operations — Supply Chain | **priority** *(V3)* |
| 8 | `production-operations` | Operations — Production | **priority** *(V3)* |
| 9 | `knowledge-management` | Knowledge Management | **priority** *(new, V1)* |
| 10 | `executive-strategy` | Strategy & Management | **priority** |
| 11 | `procurement-sourcing` | Procurement & Sourcing | standard |
| 12 | `rnd-product-development` | R&D and Product Development | standard |
| 13 | `software-engineering` | Software Engineering | standard |
| 14 | `it-infrastructure` | IT & Infrastructure | standard |
| 15 | `information-security` | Information Security | standard *(V2 — renamed from `security-risk`; scope: SOC & threat ops, vulnerability management, security monitoring, incident response, access & identity security)* |
| 16 | `data-analytics` | Data & Analytics (function) | standard |
| 17 | `training-enablement` | Training & Enablement | standard |
| 18 | `facilities-workplace` | Facilities & Workplace | standard |
| 19 | `other-unclear` | Other / Unclear | **record_only** |

**10 priority · 8 standard · 1 record_only = 19.**

Names chosen so the axes cannot blur: `finance-accounting` not `finance`; `production-operations`
not `manufacturing`; `legal-risk-compliance` not `legal`; `training-enablement` not `education`.

### 1.3 `config/harvest/facets/use-case-types.v1.json` — **22 entries**

Was 18. Four values are **new**: `data-analysis-bi`, `risk-fraud-compliance`, `training-education`
(V1) and `customer-interaction` (V4).

| # | slug | display name | coverage |
|---|---|---|---|
| 1 | `search-retrieval` | Search & Knowledge Retrieval | **priority** |
| 2 | `document-processing` | Document Processing | **priority** |
| 3 | `data-analysis-bi` | Data Analysis & BI | **priority** *(new, V1)* |
| 4 | `workflow-automation` | Workflow Automation | **priority** |
| 5 | `agentic-orchestration` | Agentic Automation | **priority** |
| 6 | `customer-interaction` | Customer Interaction | **priority** *(new, V4)* |
| 7 | `decision-support` | Decision Support | **priority** |
| 8 | `recommendation-personalization` | Personalization & Recommendation | **priority** |
| 9 | `risk-fraud-compliance` | Risk, Fraud & Compliance | **priority** *(new, V1)* |
| 10 | `training-education` | Training & Education | **priority** *(new, V1)* |
| 11 | `conversational-assistant` | Conversational Assistant | standard *(V4 — demoted)* |
| 12 | `content-generation` | Content Generation | standard |
| 13 | `summarization-extraction` | Summarization & Extraction | standard |
| 14 | `classification-routing` | Classification & Routing | standard |
| 15 | `forecasting-prediction` | Forecasting & Prediction | standard |
| 16 | `anomaly-detection` | Anomaly Detection | standard |
| 17 | `code-generation` | Code Generation | standard |
| 18 | `translation-localization` | Translation & Localization | standard |
| 19 | `speech-audio` | Speech & Audio | standard |
| 20 | `vision-inspection` | Vision & Inspection | standard |
| 21 | `simulation-design` | Simulation & Design | standard |
| 22 | `other-unclear` | Other / Unclear | **record_only** |

**10 priority · 11 standard · 1 record_only = 22.**

`content-generation` moves from priority to standard — it is absent from the approved priority list,
and following that list is the point.

**Definitions for the V4 split:**

- `customer-interaction` — the AI interacts with **external** customers, users, patients, citizens,
  members, guests or clients. Priority.
- `conversational-assistant` — a **conversational interface** as the mode of interaction, including
  **internal** employee copilots. Standard, so it can never satisfy the Customer Interaction
  coverage target on its own.

A chat interface alone is not evidence of customer interaction. An external assistant may carry
**both** values, but only when each definition is independently evidenced.

**Near-miss pairs added to the disjointness test:**
`training-enablement` (function — running employee upskilling) vs `training-education` (use case —
AI that teaches) · `legal-risk-compliance` (function) vs `risk-fraud-compliance` (use case) ·
`customer-interaction` vs `conversational-assistant` (same axis, different claim).

---

## 2 · Coverage policy (C2, C5)

`config/harvest/coverage_targets.v1.json`:

```jsonc
{
  "config_version": 1,
  "_about": "Scheduler HINTS. Never acceptance gates. Raising a target changes where the scheduler looks; it never changes what is accepted.",
  "tiers": {
    "priority":     { "target_min": 3 },
    "standard":     { "target_min": 2 },
    "record_only":  { "target_min": 0 }
  },
  "overrides": {}            // per-slug, after observing real yield
}
```

`other-unclear` is `target_min: 0` by construction — seeking more unclassifiable records is
meaningless. Targets are expected to be revised upward once real yield is observed; the file is
versioned so a change is auditable.

### 2.1 Tier assignment (R1 — decided)

| Axis | priority | standard | record_only | total |
|---|---:|---:|---:|---:|
| industries | 7 | 8 | 3 | **18** |
| business functions | 10 | 8 | 1 | **19** |
| use-case types | 10 | 11 | 1 | **22** |

Counts moved from the originally proposed 17 / 18 / 18. Values were **added because they were needed
to express the approved priority lists**, not trimmed to preserve an earlier total.

Defaults remain configurable and are **not publication quotas**. The scheduler may prioritise a gap
only when a credible source or query exists, global budget remains, and prior duplicate and
quality-rejection rates do not justify stopping. Acceptance criteria are never lowered to meet a
target.

### 2.2 Secondary industries (C5)

Cap stays **2**. The rule is *deployment context*, not corporate portfolio: a bank owned by a
conglomerate that also makes turbines is `financial-services-insurance` — the turbine business is
irrelevant to this deployment and generates no secondary label.

Test: a conglomerate fixture whose article mentions four unrelated business lines yields **zero**
secondary industries.

### 2.3 `cross-industry` (R4 — decided)

`record_only`, `target_min: 0`. Counted **separately** in reports; it can never satisfy or reduce the
gap of any concrete industry, and it never launches a gap-filling lane of its own.

Assigned only when the deployment itself is genuinely horizontal or documented across multiple
industries — **never** because a tool could theoretically be used broadly.

Tests: ten `cross-industry` records leave a `healthcare-life-sciences` gap and a
`manufacturing-industrial` gap **unchanged** · a generic reusable tool is not automatically
`cross-industry` · a documented multi-industry deployment may receive it · no
`gap__industry__cross-industry` lane is ever scheduled.

---

## 3 · `case_facets` schema (C1)

Added to `full_record.properties` as an optional key, so existing records stay valid:

```jsonc
"case_facets": {
  "type": ["object", "null"],
  "additionalProperties": false,
  "required": ["facets_version", "classification_state",
               "industry", "business_functions", "use_case_types"],
  "properties": {
    "facets_version": { "type": "integer", "const": 1 },
    "vocabulary_versions": {
      "type": "object", "additionalProperties": false,
      "properties": { "industries": {"type":"integer"},
                      "business_functions": {"type":"integer"},
                      "use_case_types": {"type":"integer"} }
    },
    "classification_state": { "enum": ["resolved", "unresolved"] },
    "industry":           { "$ref": "#/$defs/facet_axis_single" },
    "business_functions": { "type": "array", "maxItems": 4,
                            "items": { "$ref": "#/$defs/facet_axis_multi" } },
    "use_case_types":     { "type": "array", "maxItems": 4,
                            "items": { "$ref": "#/$defs/facet_axis_multi" } },
    "unresolved": { "type": "array", "items": { "$ref": "#/$defs/facet_unresolved" } }
  }
}
```

`$defs` additions:

```jsonc
"facet_slug": { "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$" },

"facet_evidence": {
  "type": "object", "additionalProperties": false,
  "required": ["field", "matched_term", "quote"],
  "properties": {
    "field": { "enum": ["title","summary","body","publisher","target_url","legacy_field"] },
    "matched_term": { "type": "string", "minLength": 2 },
    "quote": { "type": "string", "minLength": 3, "maxLength": 400 },
    "offset": { "type": ["integer","null"] }
  }
},

"facet_axis_single": {
  "type": "object", "additionalProperties": false,
  "required": ["primary","secondary","confidence","evidence"],
  "properties": {
    "primary":    { "oneOf": [{"$ref":"#/$defs/facet_slug"}, {"type":"null"}] },
    "secondary":  { "type":"array", "maxItems":2, "uniqueItems":true,
                    "items": {"$ref":"#/$defs/facet_slug"} },
    "confidence": { "type": ["number","null"], "minimum":0, "maximum":1 },
    "evidence":   { "type":"array", "items": {"$ref":"#/$defs/facet_evidence"} }
  },
  "if":   { "properties": {"primary": {"type":"string"}}, "required": ["primary"] },
  "then": { "properties": {"evidence": {"minItems":1}, "confidence": {"type":"number"}} }
},

"facet_axis_multi": {
  "type": "object", "additionalProperties": false,
  "required": ["slug","confidence","evidence"],
  "properties": {
    "slug":       { "$ref": "#/$defs/facet_slug" },
    "confidence": { "type":"number", "minimum":0, "maximum":1 },
    "evidence":   { "type":"array", "minItems":1, "items": {"$ref":"#/$defs/facet_evidence"} }
  }
},

"facet_unresolved": {
  "type":"object", "additionalProperties": false,
  "required": ["axis","state","detail"],
  "properties": {
    "axis":  { "enum": ["industry","business_function","use_case_type"] },
    "state": { "enum": ["other-unclear","unmapped_legacy_value",
                        "insufficient_evidence","not_applicable"] },
    "term":   { "type": ["string","null"] },
    "detail": { "type":"string", "minLength": 3 }
  }
}
```

**Identity exclusion is unchanged and absolute:** `case_facets` is never read by `urlkey.py`, never
part of `record_id`/`content_id`/`identity_url`/`cell_id`, and never part of the published filename.

---

## 4 · Applicability and the non-trivial requirement (C13)

| Topic / category | `case_facets` |
|---|---|
| `cases` / `domain-applications` | **required**, and must be non-trivially populated (below) |
| `cases` / `case-studies` | schema-optional; enrichment attempted where evidence permits; coverage **always reported, never gated** *(R2 — decided: `report_only` in v1)* |
| `cases` / `product-discovery` | optional, typically `use_case_types` only |
| any `cross_reference` row | **forbidden** — it is a pointer, and the closed union already rejects it |
| `research-and-models` / * · `discourse` / * | **forbidden** on full records |

**Non-trivial requirement for `domain-applications`** — `other-unclear` alone must not satisfy it.
A record is `classification_state: "resolved"` only when **both** hold:

1. `industry.primary` is a supported value that is **not** `other-unclear` (`cross-industry` counts); **and**
2. at least one supported `business_functions[]` **or** `use_case_types[]` entry exists.

Otherwise the record is `classification_state: "unresolved"`, must carry at least one
`unresolved[]` entry explaining why, and is **withheld from normal publication eligibility** — it is
retained, auditable, and excluded from the published set until reviewed. Expressed as a schema
conditional plus a semantic check (§11); the schema conditional does not touch the `required` array,
so Stage 1's "every required field is required" test is unaffected.

### 4.1 Coverage reporting states (R2)

Five states, counted and reported **separately** per category per run. Weak facets are never invented
to improve a number.

| State | Meaning |
|---|---|
| `facet_complete` | industry resolved **and** ≥1 function or use-case |
| `facet_partial` | some axis populated, but not enough for `resolved` |
| `unresolved` | attempted, evidence insufficient — carries `unresolved[]` |
| `not_enriched` | enrichment disabled or not attempted for this record |
| `unmapped_legacy_value` | legacy value present with no approved mapping |

Migrated AX cases remain **valid without facets** — migration is never blocked on facet quality.

A future version may introduce a Case Studies enrichment **gate**, but only after observing real
coverage and evidence quality from live runs. It is explicitly out of scope for v1.

---

## 5 · Ambiguity and exclusion rules

| Term | Industry reading | Function reading | Rule |
|---|---|---|---|
| **finance** | `financial-services-insurance` — the org *is* a bank/insurer/fintech | `finance-accounting` — FP&A, budgeting, invoicing, audit, close | Decided by *what the organisation is*, not what the task is. Both when each is independently evidenced. |
| **legal** | `professional-services` — law firm / legal-services provider | `legal-risk-compliance` — contract review, compliance inside any org | In-house legal at a manufacturer = `manufacturing-industrial` + `legal-risk-compliance`. *(Errata E2 — this row named the pre-V2 slug `legal-compliance`.)* |
| **retail** | `retail-cpg` — the org is a retailer/brand | none | Retail-media work = `retail-cpg` + `marketing`. "Retail" never implies a function. |
| **manufacturing** | `manufacturing-industrial` — the org makes things | `production-operations` — the production function, any industry | Pharma optimising a line = `healthcare-life-sciences` + `production-operations`. |
| **operations** | — | `supply-chain-operations` / `production-operations` | **Never inferred from generic prose.** "improving business operations" with no concrete workflow assigns nothing; the term goes to `unresolved[]`. |
| **education** | `education-research` — a school/university | `training-enablement` — employee upskilling | |
| **technology** | `technology-software` — the *adopting org* sells software | `software-engineering` / `it-infrastructure` | See exclusion below. |
| **risk** | — | `legal-risk-compliance` (function) vs `risk-fraud-compliance` (use case) | **Different axes, not duplicates.** The function is *who does the work*; the use case is *what the AI solves*. A bank's fraud-detection model built by its compliance team legitimately carries both. |
| **security** | — | `information-security` (function) | Narrow: SOC, threat ops, vulnerability management, monitoring, incident response, identity. Enterprise non-security risk belongs to `legal-risk-compliance`. |
| **chat UI** | — | `customer-interaction` vs `conversational-assistant` (both use cases) | A conversational interface alone proves nothing about *who* is on the other end. Internal copilot ⇒ `conversational-assistant` only. |

### 5.1 `technology-software` exclusions (C6)

Assign **only** when the adopting organisation or the deployment context is itself in
technology/software. Explicitly **never** inferred from:

- the **publisher** of the article;
- the **AI vendor** whose model is used;
- the **platform provider** (cloud, framework, hosting);
- the fact that the piece appears on a technology website.

**A customer case published by an AI vendor takes the customer's industry, not the vendor's.** An
OpenAI-published story about a hospital is `healthcare-life-sciences`. Coverage policy is
`record_only` so it is recorded faithfully but never actively sought — otherwise it becomes the
dumping ground for every vendor case study.

---

## 6 · Unresolved and not-applicable semantics (C10)

Four distinct states, never collapsed:

| state | Means | Use when |
|---|---|---|
| `other-unclear` | The source *does* discuss the axis but supports no vocabulary value | An article about "AI in the public services sector" that resists placement |
| `unmapped_legacy_value` | A legacy record carries a value the new vocabulary has no approved mapping for | AX migration meets `industry: "Adtech"` with no mapping |
| `insufficient_evidence` | Content cannot support any classification on this axis | Enrichment disabled; only a title is available |
| `not_applicable` | The axis does not apply to this record | A horizontal dev tool with no employer |

For `unmapped_legacy_value` specifically: preserve the **exact original value** in
`provenance.raw`, emit an `unresolved[]` entry carrying the term, **do not guess a slug**, and **do
not present the legacy value as grounded classification evidence**. A reviewed entry in
`legacy_industry_map.v1.json` may later assign a real slug with `field: "legacy_field"` provenance.

---

## 7 · Adaptive coverage scheduler (C3, C4, C14)

Round 1 is broad — the 12 configured cells, exactly as today. Then per round:

1. compute coverage per axis value against its **tier target** (§2);
2. **rank gaps** by a weighted score over seven factors, not remaining gap alone:
   remaining gap · configured priority · historical acceptance yield · duplicate rate ·
   quality-rejection rate · credible-source availability · remaining global budget;
3. open bounded gap lanes only where a credible source exists; otherwise record
   `stop_reason: "no_credible_source"` and report the gap honestly;
4. run, merge, recompute.

**Coverage targets are scheduler hints, never acceptance gates.** `min_relevance`, `min_quality` and
`accept_composite` are read once per run and are never touched by the scheduler. It changes *where*
it looks, never *what it accepts*. An unmet target is reported as an unmet target.

Stop conditions (any): `max_rounds` (default 3) · new-accepted below `no_progress_min` ·
`duplicate_rate` above threshold · global or lane budget exhausted · all targets met.

### 7.4 Smoke posture

- **Mandatory smoke: round 1 only.** No gap lanes. It stays an infrastructure and integration test.
- Adaptive scheduling is covered by **deterministic fixture tests** with an injected clock and
  scripted source results.
- Optional, non-mandatory `harvest.sh smoke-adaptive --lanes <1-2> --max-rounds 2` with a very small
  budget, for exercising the scheduler live once the deterministic gates pass.

---

## 8 · `source_request_key` and cache reuse (C7)

"Fetched once per round" was wrong. The correct unit is a **normalized request, once per run,
reused across every round and lane**.

```
source_request_key = sha256(
    source_id | normalized_url | method | canonical_query | body_hash |
    significant_headers | adapter_mode
)[:16]
```

- `normalized_url` uses the Stage 1 canonicalizer (tracking params stripped, order preserved).
- `canonical_query` is the request-significant query, sorted **only** for API adapters where order
  is provably insignificant; feed/seed URLs keep their order.
- `significant_headers` is an allowlist (`Accept`, `Accept-Language`) — never `User-Agent`, never
  auth material.
- `adapter_mode` distinguishes e.g. seed `index` from seed `record` against the same URL.

**Consequences.** One logical source definition may legitimately produce several request keys — an
API source queried by a broad lane and by `gap__industry__healthcare` has two distinct keys and two
fetches, correctly. A feed shared by three lanes has **one** key and is fetched **once per run**,
reused in rounds 2 and 3 from `pool/sources/<request_key>.json`.

### 8.3 Run-scoped immutable snapshot (R3 — decided: **no mid-run revalidation**)

For each `source_request_key`:

1. the **first** logical fetch in a run may use cached `ETag` / `Last-Modified` metadata carried over
   from a previous run;
2. a `200` **or** `304` establishes the **immutable run-scoped source snapshot**;
3. every lane and every adaptive round in that run reuses that snapshot;
4. no later round may revalidate or replace it.

A changed source requires a **new harvest run**, or an explicit `refresh` / `linkcheck` command.

This is distinct from retries and redirects, which belong to the *same* logical fetch and are counted
separately as HTTP attempts (§9).

*Why this matters:* allowing revalidation mid-run would make output depend on when a round happened
to execute, so two runs over identical inputs could diverge — destroying the determinism the fixture
suite asserts.

Tests: a conditional `304` result is reused across all rounds · an adaptive round issues **no** second
conditional request for the same key · a **new** run may revalidate and observe a newer source
version · output is identical under shuffled worker and round timing.

---

## 9 · Logical owners vs HTTP attempts (C8)

`fetch_count <= 1` at the HTTP level was wrong — retries, redirect hops, and conditional
revalidation are legitimate multiple attempts.

**Asserted invariants (logical):**

| Invariant | Meaning |
|---|---|
| one **source-fetch owner** per `source_request_key` per run | three lanes sharing a feed ⇒ one owner |
| one **target-fetch owner** per canonical candidate per run | a page found by four lanes is fetched once |
| one **extraction owner** per accepted response body | no double parsing |
| one **record** per `(topic, identity_url)` | unchanged |

**Separately observable (physical):** `http_attempts`, `retries`, `redirect_hops`,
`conditional_revalidations` — all charged to the shared `RequestBudget` exactly as Stage 2 already
does, and all reported per lane and per run.

Test: three lanes referencing one feed produce **1** logical owner and **1** HTTP attempt; the same
feed behind a 301 plus one 503 retry produces **1** logical owner and **3** HTTP attempts, with the
budget charged 3.

---

## 10 · Discovery/classification separation (C9)

Lane membership is **provenance only** and carries zero direct classification weight — a record found
via `gap__function__marketing` gets no marketing label for that reason.

**But** the lane's *query terms* may legitimately become evidence **when independently found in the
extracted target document**. The classifier is grounded in the document; the lane merely suggested
where to look. Concretely: `gap__industry__healthcare` finds a page, and the word "hospital" appears
in the fetched body — that body quote is valid evidence. The lane ID itself never is.

Per-lane quality metrics, reported and never fed back into classification:
lane-to-final-label **agreement** · **mismatch** rate · acceptance yield · duplicate rate ·
quality-rejection rate.

---

## 11 · Vocabulary source of truth (C11)

**Option A — generated constraint file.** `gen_facet_schema.py` emits
`schemas/harvest/facets.generated.v1.json` containing real enums.
*Pro:* a published artifact validates standalone with any off-the-shelf JSON Schema validator, no
repo access needed. *Con:* a generation step and drift risk.

**Option B — shape-only schema + semantic validator.** Schema checks slug shape; `check_facets.py`
checks membership.
*Pro:* exactly one source of truth, no generation. *Con:* a standalone consumer validating a
published artifact would **accept an invalid slug** — the schema alone cannot catch it.

**Recommendation: Option A, with both.** Artifacts are published to `cherryinthehaystack.com` and may
be validated by consumers who have no access to this repo, so standalone validatability is a real
requirement. The generated file gets five guardrails: never hand-edited (stated in its header);
deterministic generation; a header recording each source vocabulary's version **and SHA-256**; a test
that regenerates and fails on any drift; and runtime verification that
`case_facets.vocabulary_versions` matches the loaded vocabularies. The semantic validator is retained
as well, for the checks a schema cannot express (§4's non-trivial requirement, axis-disjointness,
deprecation).

---

## 12 · Stage 2.5 boundary (C12)

Stage 1 can no longer be called unchanged, so this gets its own honest checkpoint:

```
Stage 2.5 — case facets and shared-discovery design
```

Contents: the three vocabularies + coverage targets + legacy map · `record.v1.json` changes and the
three new schemas · `gen_facet_schema.py` + `check_facets.py` semantic validator · classification and
ownership contracts · new test suites · **rerun of every Stage 0–2 suite**.

Stage 2 remains functionally complete; the **199-assertion baseline is rerun after Stage 2.5** and
must still pass. **Stage 3 stays blocked until both the existing suites and the new facet suites
pass.**

---

## 13 · Affected files and exact new tests

**New config** — `config/harvest/facets/{industries,business-functions,use-case-types}.v1.json` ·
`config/harvest/facets/legacy_industry_map.v1.json` · `config/harvest/coverage_targets.v1.json`

**New schemas** — `facets.generated.v1.json` *(generated)* · `candidate_pool.v1.json` ·
`discovery_lane.v1.json` · `coverage_report.v1.json`

**Modified schemas** — `record.v1.json` (add `case_facets`, 5 `$defs`, one `allOf`; extend
`rejection_reason` with `not_a_case_trend_piece`, `not_a_case_product_announcement`,
`not_a_case_tutorial`, `not_a_case_hypothetical`, `keyword_only_match`) ·
`run_manifest.v1.json` (add `rounds[]`, `coverage[]`, `lane_quality[]`)

**New code** — `src/harvest/facets.py` · `pool.py` · `coverage.py` · `scheduler.py` ·
`request_key.py` · `scripts/harvest/gen_facet_schema.py` · `scripts/harvest/check_facets.py`

**Modified code** — `scripts/harvest/check_config.py` only.
**Untouched:** `src/harvest/{urlkey,slug,records,schema,budget,domainlease,httpclient}.py`.

**New tests**

| Suite | Proves |
|---|---|
| `test_taxonomy_facets.sh` | vocabulary shape · generated-schema drift · `vocabulary_versions` runtime match · deprecation still validates historically |
| `test_taxonomy_facet_ambiguity.sh` | pairwise-disjoint slug sets (all near-miss pairs named) · cross-axis slug rejected on each axis · finance/legal/retail/manufacturing/operations/education fixtures · conglomerate yields no secondary · vendor-published customer case takes the **customer's** industry · `technology-software` not inferred from publisher/vendor/platform · **`legal-risk-compliance` + `risk-fraud-compliance` co-occur without being flagged duplicate or conflicting** · `information-security` not assigned for contract/audit work · **"improving business operations" assigns neither operations function** |
| `test_taxonomy_customer_interaction.sh` | an external customer-support assistant may receive `customer-interaction` · an **internal employee copilot does not** · conversational UI alone does not prove customer interaction · one external assistant may carry **both** values only when each is independently evidenced · `conversational-assistant` alone never satisfies the Customer Interaction coverage target |
| `test_taxonomy_facet_identity.sh` | add/change/remove/null `case_facets` ⇒ `record_id`, `content_id`, `identity_url`, `cell_id`, artifact filename all unchanged · static grep proving `urlkey.py`/`slug.py` never mention facets |
| `test_taxonomy_facet_states.sh` | the four unresolved states are distinct · `other-unclear` alone fails the domain-applications requirement · unresolved records are withheld from publication eligibility · `unmapped_legacy_value` never becomes evidence |
| `test_taxonomy_pool.sh` | `source_request_key` stability and sensitivity · one logical owner across 3 lanes · **304 snapshot reused across all rounds** · **no second conditional request within a run** · a new run may revalidate · redirect+retry ⇒ 1 owner / 3 attempts / budget 3 · every contributing `lane_id` preserved · output identical under shuffled round timing |
| `test_taxonomy_coverage.sh` | tier targets (7/8/3 · 10/8/1 · **10/11/1** — Errata E1) · 7-factor gap ranking · `no_credible_source` reported not invented · **thresholds provably constant across rounds** · all stop conditions · **10 `cross-industry` records do not close a healthcare or manufacturing gap** · no `cross-industry` gap lane is ever scheduled · the 5 coverage-reporting states counted separately |

**Docs** — this file · `docs/harvest/FACET_VOCABULARY.md` · TODO/plan updates for Stage 2.5.

---

## 14 · Compatibility and migration

**Existing assertions:** `APPROVED_CELLS` (12) unchanged — facets create no cells.
`test_taxonomy_config.sh` (18) reads topic configs only. `test_taxonomy_schema.sh` (35) unaffected —
`case_facets` is added to `properties`, not `required`. `test_taxonomy_identity.sh` (42) untouched.
Stage 2 (80) untouched. **No existing test requires modification.**

**AX migration (231 cases):** they land in `case-studies`, where facets are schema-optional, so
migration is not blocked on facet quality. Legacy `industry` maps only via the reviewed table;
anything unmapped becomes `unmapped_legacy_value` in `unresolved[]` with the exact original preserved
in `provenance.raw` — never guessed, never presented as evidence. Business functions and use cases
are populated only where `workflow_after`/`ai_system_or_tool` yield a quotable phrase; otherwise `[]`
("looked, found nothing"), which is distinct from `null`. **Count stays 231; no ID changes.**

---

## 15 · Vocabulary decisions (V1–V4 — all resolved)

### 15.1 V1 — four added values, **approved**

| Slug | Axis | Why no existing value worked |
|---|---|---|
| `knowledge-management` | business function | Nothing covered internal knowledge capture/retrieval as a *function*; `data-analytics` is about numbers, `search-retrieval` is a use-case type |
| `data-analysis-bi` | use-case type | `decision-support` is the downstream act; analysis/BI is the capability itself |
| `risk-fraud-compliance` | use-case type | Was split across `anomaly-detection` and `classification-routing`, losing the domain meaning |
| `training-education` | use-case type | No value described AI that teaches |

Counts are recorded explicitly rather than forced back to the originals:
**17 → 18 industries · 18 → 19 business functions · 18 → 22 use-case types** (the last includes
`customer-interaction` from V4). No useful value was removed to preserve an earlier count.

### 15.2 V2 — `legal-risk-compliance` approved, security narrowed

- **`legal-risk-compliance`** (priority) — legal work, contracts, governance, audit, regulatory
  compliance, enterprise **non-security** risk.
- **`information-security`** (standard) — renamed from `security-risk`, scope narrowed to SOC and
  threat operations, vulnerability management, security monitoring, incident response, and access
  and identity security.

The rename is a direct consequence of the decision: leaving "risk" in both slug names would
reintroduce the axis blur the vocabulary exists to prevent.

**`risk-fraud-compliance` (use-case type) coexists deliberately.** It describes the *problem being
solved*, not the organisational function. A bank's fraud-detection model built by its compliance team
legitimately carries `business_function: legal-risk-compliance` **and**
`use_case_type: risk-fraud-compliance`; a fixture in `test_taxonomy_facet_ambiguity.sh` asserts this
pair is **not** treated as duplicate or conflicting.

### 15.3 V3 — no bare `operations`

Both concrete functions are **priority**: `supply-chain-operations` and `production-operations`.

Generic phrasing such as "improving business operations" assigns **neither** without evidence of a
concrete supply-chain or production workflow; the term goes to `unresolved[]`. **No third generic
operations value is created in v1** — one would need a clearly bounded, non-overlapping definition
and supporting examples, and no such boundary has been identified.

### 15.4 V4 — `customer-interaction` added as a distinct value

- **`customer-interaction`** (**priority**) — the AI interacts with **external** customers, users,
  patients, citizens, members, guests or clients.
- **`conversational-assistant`** (**standard**) — a conversational interface as the mode of
  interaction, explicitly including **internal** employee copilots. Because it is standard, it can
  never satisfy the Customer Interaction coverage target on its own.

An internal employee assistant does **not** receive `customer-interaction` merely for having a chat
interface. An external assistant may carry both values, but only when each definition is
independently evidenced. Covered by `test_taxonomy_customer_interaction.sh` (§13).

### 15.5 Nothing remains open

R1–R4 and V1–V4 are all decided. No question in this proposal awaits a decision.

---

## 16 · Errata — documentation corrections

Found while checking this design against the Stage 0–2 code as written. **None of these changes an
approved decision**; each corrects an internal inconsistency in this document. The full analysis and
the corresponding implementation decisions are in `docs/harvest/STAGE_2_5_IMPLEMENTATION_PLAN.md`
(defects D1–D10).

| # | Where | Was | Is | Why |
|---|---|---|---|---|
| **E1** | §13 (`test_taxonomy_coverage.sh` row) and the handoff's §4 summary | use-case tiers "10/10/1" | **10 priority / 11 standard / 1 record_only** | "10/10/1" sums to 21 and cannot describe the 22 approved use-case values. §1.3 and §2.1 already say 10/11/1, and `TODO.md` agrees. The 22-value total is the binding decision |
| **E2** | §5, the "legal" row (two occurrences) | `legal-compliance` | **`legal-risk-compliance`** | Decision V2 renamed the slug. §1.2 was updated; the ambiguity table was not. Corrected inline below |
| **E3** | Document header | "Revision 2 · PROPOSAL · Awaiting approval" | **Revision 4 · approved design** | The header lagged behind the handoff and `TODO.md`; the content was already at revision 4 |
| **E4** | §13, "Modified schemas — `record.v1.json` … one `allOf`" | location unstated | the `allOf` belongs **inside `#/$defs/full_record`** | At the document root it would make every `cases__domain-applications` **cross_reference** row unsatisfiable, since that branch is `additionalProperties:false` and cannot carry `case_facets`. See plan D1 / DV-5 |
| **E5** | §3, `case_facets.required` | omits `vocabulary_versions` | `vocabulary_versions` is **required** inside `case_facets`, all three sub-keys required | §11 guardrail 5 requires a runtime version match, which is unenforceable when the key may be absent. See plan D5 / DV-6 |
| **E6** | §13, "pairwise-disjoint slug sets" | stated without exception | disjoint **except for the explicitly shared sentinel `other-unclear`** | `other-unclear` is in all three vocabularies by design (§1.1, §1.2, §1.3), so the rule as written contradicts them. See plan D3 |
| **E7** | §4 / §4.1, "withheld from normal publication eligibility"; five reporting states listed without precedence | no representation given, and `unmapped_legacy_value` left ambiguous against `unresolved` | a **derived predicate** plus coverage-report output — **no new persisted record field** — over **five mutually exclusive, exhaustive** states with a total precedence order in which `unmapped_legacy_value` ranks **first** and is counted separately; state and predicate are derived from the **complete record** (`record_type`, `topic`, `primary_category`, `case_facets`, legacy provenance), not `case_facets` alone | `publication_eligible` is run-level; `rejection_reason` is the wrong home, because an unresolved record is retained and auditable, not rejected. Without a total order the same record could be counted twice, and an unmapped legacy value could vanish into the generic `unresolved` bucket. Eligibility (Domain Applications: `facet_complete` only) is separate from reporting; Case Studies stay report-only in v1. See plan D7 §8.3 and the six assertions in §10 |
| **E8** | §14, "Legacy `industry` maps only via the reviewed table" | implies a complete table | a **reviewed seed**; the long tail becomes `unmapped_legacy_value` | Measured: the 231 AX cases carry **173 distinct free-text `industry` values**. A complete one-to-one table is not achievable, and pretending otherwise invites guessing. See plan D10 |

Two further constraints, recorded here because they affect §8 and §2 but were not stated there:

- **`source_request_key` must pin `canonicalization_version`.** It is built on the Stage 1
  canonicalizer, whose behaviour is driven by `config/harvest/canonicalization.v1.json`; without the
  version in the key material, a config bump silently changes keys across runs.
- **A `coverage_targets` override may not raise a `record_only` value above 0.** Allowing it for
  `cross-industry`, `technology-software` or `other-unclear` would contradict decisions R4 and C6.
