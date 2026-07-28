# Case facet vocabulary — reference

**Status: implemented (Stage 2.5).** Source of truth: `config/harvest/facets/*.v1.json`.
This document explains the vocabulary; it does not define it. If the two disagree, the config files
win and this file is wrong.

```text
industries.v1.json         18 entries   7 priority ·  8 standard · 3 record_only
business-functions.v1.json 19 entries  10 priority ·  8 standard · 1 record_only
use-case-types.v1.json     22 entries  10 priority · 11 standard · 1 record_only
```

---

## 1 · Three axes, one question each

| Axis | Question | Cardinality |
|---|---|---|
| industry | **Whose** problem — the industry of the *adopting organisation* | one primary, ≤2 secondary |
| business function | **Whose work** inside that organisation changes | ≤4 values |
| use-case type | **What the AI does** | ≤4 values |

They are independent. A pharmaceutical company optimising a production line is
`healthcare-life-sciences` **+** `production-operations`, not `manufacturing-industrial`.

---

## 2 · The rules that keep the axes apart

| Term | Industry reading | Function / use-case reading | Rule |
|---|---|---|---|
| **finance** | `financial-services-insurance` — the org *is* a bank, insurer or fintech | `finance-accounting` — FP&A, invoicing, close, audit | Decided by *what the organisation is*, not what the task is. Both when each is independently evidenced |
| **legal** | `professional-services` — a law firm | `legal-risk-compliance` — contract review and compliance inside any org | In-house legal at a manufacturer = `manufacturing-industrial` + `legal-risk-compliance` |
| **retail** | `retail-cpg` | none | "Retail" never implies a function. Retail-media work = `retail-cpg` + `marketing` |
| **manufacturing** | `manufacturing-industrial` — the org makes things | `production-operations` — the production function, any industry | |
| **operations** | — | `supply-chain-operations` / `production-operations` | **No bare `operations` slug exists.** Generic "improving business operations" assigns neither; the term goes to `unresolved[]` |
| **education** | `education-research` — a school or university | `training-enablement` — employee upskilling | |
| **technology** | `technology-software` — the *adopting org* sells software | `software-engineering` / `it-infrastructure` | See §3 |
| **risk** | — | `legal-risk-compliance` (function) vs `risk-fraud-compliance` (use case) | **Different axes, not duplicates.** A bank's fraud model built by its compliance team carries both, and that pair is neither a duplicate nor a conflict |
| **security** | — | `information-security` (function) | Narrow: SOC and threat ops, vulnerability management, monitoring, incident response, identity. Enterprise non-security risk is `legal-risk-compliance` |
| **chat UI** | — | `customer-interaction` vs `conversational-assistant` | See §4 |

`other-unclear` is the **single** slug that appears on all three axes, and the only one exempt from
cross-axis disjointness. Everything else belongs to exactly one axis.

---

## 3 · `technology-software` is `record_only`

Assigned **only** when the adopting organisation is itself in technology or software. Never inferred
from the publisher, the AI vendor, the platform provider, or the fact that the piece appears on a
technology website.

**A customer case published by an AI vendor takes the customer's industry** — an OpenAI story about
a hospital is `healthcare-life-sciences`. Coverage policy is `record_only` so it is recorded
faithfully but never actively sought; otherwise it becomes the dumping ground for every vendor case
study. `check_facets.py` refuses industry evidence sourced from `field: "publisher"`, and refuses
`technology-software` evidenced from `publisher` or `target_url`.

`cross-industry` is also `record_only`, `target_min` 0: counted separately, never closing or reducing
a concrete industry's gap, and never launching a gap lane of its own.

---

## 4 · `customer-interaction` vs `conversational-assistant`

| | `customer-interaction` | `conversational-assistant` |
|---|---|---|
| Tier | **priority** | standard |
| Means | the AI interacts with **external** customers, users, patients, citizens, members, guests, clients | a **conversational interface** as the mode of interaction, **including internal employee copilots** |
| Coverage | can satisfy the Customer Interaction target | **never** satisfies it alone |

A chat interface alone is not evidence of customer interaction — it proves nothing about who is on
the other end. An external assistant may carry **both** values, but only when each definition is
independently evidenced. Five internal copilots leave the Customer Interaction target completely
unmet, and `test_taxonomy_customer_interaction.sh` asserts exactly that.

---

## 5 · Coverage policy

`config/harvest/coverage_targets.v1.json`: `priority → 3`, `standard → 2`, `record_only → 0`, plus
per-slug overrides.

**These are scheduler hints, never acceptance gates.** `min_relevance`, `min_quality` and
`accept_composite` live in `policy.v1.json`, are read once per run, and are never touched by the
scheduler. It changes *where* it looks, never *what* it accepts. An unmet target is reported as an
unmet target. An override may not raise a `record_only` value above 0 — `check_facets.py` refuses it.

---

## 6 · The five reporting states

Mutually exclusive and exhaustive over applicable records (`record_type == "full"`).
**`cross_reference` rows are excluded from all five.** First match wins:

| # | State | Condition |
|---:|---|---|
| 1 | `unmapped_legacy_value` | any `unresolved[]` entry has that state |
| 2 | `not_enriched` | `case_facets` absent or `null` |
| 3 | `facet_complete` | `classification_state == "resolved"` |
| 4 | `facet_partial` | unresolved, ≥1 axis populated |
| 5 | `unresolved` | unresolved, nothing populated |

The counts always sum to `applicable_full_records`. `unmapped_legacy_value` ranks **first** so it can
never be folded into `unresolved` or `facet_partial` — a legacy value with no reviewed mapping is a
fact a reviewer must act on.

**Publication eligibility is derived, never persisted.** A `cases`/`domain-applications`/`full`
record is eligible only in state `facet_complete`; the other four are withheld — *withheld, not
rejected*: the record keeps its `record_id`, carries no `rejection_reason`, and stays auditable.
Case Studies and Product Discovery are report-only in v1.

---

## 7 · Four unresolved states, never collapsed

| State | Use when |
|---|---|
| `other-unclear` | the source discusses the axis but supports no vocabulary value |
| `unmapped_legacy_value` | a legacy record carries a non-empty value the vocabulary has no reviewed mapping for |
| `insufficient_evidence` | the content cannot support any classification on this axis |
| `not_applicable` | the axis does not apply to this record |

For `unmapped_legacy_value`: the exact original is preserved in `provenance.raw` **and** carried as
the entry's `term`; **no slug is guessed**; and the value is **never** presented as classification
evidence. A migrated record may not hide one by omitting `case_facets` — `check_facets.py` refuses
that, because it would report as `not_enriched`.

Measured reality: the 231 AX cases carry **173 distinct free-text industry values**.
`legacy_industry_map.v1.json` is a reviewed **seed**, not a table; the long tail stays visible as
`unmapped_legacy_value`.

---

## 8 · Facets never touch identity

`case_facets` is never read by `urlkey.py` or `slug.py`, and is never part of `record_id`,
`content_id`, `identity_url`, `cell_id` or a published filename. Adding, changing, removing or
nulling it changes none of them — asserted structurally and by static grep in
`test_taxonomy_facet_identity.sh`. The approved 12-cell set is unchanged: facets create no cells.

---

## 9 · Changing the vocabulary

1. Edit the relevant `config/harvest/facets/*.v1.json` and bump its `vocabulary_version`.
2. Regenerate: `python scripts/harvest/gen_facet_schema.py`.
   **Never hand-edit `schemas/harvest/facets.generated.v1.json`** — it is generated, drift-tested,
   and lives in a directory `schema.py` loads wholesale into one cached registry.
3. Validate: `python scripts/harvest/check_facets.py`.
4. Run `bash tests/test_taxonomy_facets.sh` and `bash tests/test_taxonomy_facet_ambiguity.sh`.
5. Retiring a value means `status: "deprecated"` + `replaced_by`. It keeps validating on historical
   records and may not be newly assigned — never delete an entry.
