# Addendum — Cherry Harvest Engine PRD

Depth that belongs downstream (architecture, solution design) or that earned a place but does not
fit the PRD's main narrative: rejected alternatives and why, mechanism-level decisions,
implementation notes. **The PRD states what the engine must do; this states why the alternatives
were not taken and how the mechanisms are expected to work.**

---

## 1. Rejected alternatives

### 1.1 Auto-reject every artifact with no detectable licence

**Rejected.** This was the research's own recommendation, and on its face it is compelling:
GitHub's data shows only ~20% of repositories carry a detectable licence, absence legally means
all rights reserved, and rejecting on absence therefore disposes of the majority of the corpus at
zero cost with a legally defensible rationale.

**Why it was not taken.** It conflates two different claims. *"We do not know whether this is
commercially usable"* and *"this should not be in our catalogue"* are separate propositions, and
the product's value proposition (§5 — reducing the cost of discovery and comparison) depends on
the corpus being broad. A visitor asking "what is widely used in this category?" is not served by
a catalogue that dropped 70–80% of the field on a licensing technicality.

**What was taken instead.** The four-gate separation in PRD §8.3. Corpus membership, public
listing, the commercial-usability filter, and our own asset reuse are four different decisions
with four different bars. Absence of a licence blocks the third and fourth but not the first two.
This keeps the corpus while making the strong claim only where it is earned.

**Cost of the choice.** A larger corpus with a large `indeterminate` tail, and a dependency on the
consumer displaying cautions prominently — which is why that obligation is written down as a
condition on the engine's guarantee in PRD §13 rather than assumed. The failure mode being traded
away — telling a visitor something is commercially usable when it was never established — is
materially worse than the one accepted.

### 1.2 Treat privacy opacity as a hard fail

**Rejected**, having initially been proposed as one.

Adjudicating a privacy policy automatically requires fetching and interpreting policy documents,
locating opt-out and deletion mechanisms, and deciding whether disclosure is adequate. It is
among the most expensive per-item operations in the pipeline and among the least reliable. At
corpus scale the false-positive cost — removing legitimate tools because their policy was
unfindable by a crawler — outweighs the benefit.

**What was taken instead.** The split in PRD §7.4: hard fail only on evidenced harm (deceptive
collection, refusal of deletion without basis, unconsented disclosure of sensitive data, an
unresolved breach, official sanction, or malicious design), and warning for everything merely
unclear. The governing sentence — *unclear is a warning, confirmed serious harm is a fail* — is
the general form of this trade and is applied elsewhere in the PRD too.

### 1.3 Rely on GitHub's licence field, or on OpenSSF Scorecard

**Rejected on evidence.**

GitHub's licence field is `licensee`: Sørensen–Dice matching at confidence threshold 98, over the
**root LICENSE file only**, against the ~13 licences `GET /licenses` serves by default, with
everything else collapsing to `NOASSERTION`. Its own documentation states it does not consider
dependency licences, README licence references, per-file headers, or compliance.

The failure is also asymmetric in the dangerous direction. An *appended* restriction — "commercial
use prohibited" bolted onto MIT — drops the match below threshold and correctly yields
NOASSERTION. A *stripped attribution clause* still scores ≥98% and is reported as clean MIT.
The mode that produces a **false permissive verdict** is the one that survives the threshold.

OpenSSF Scorecard's `License` check asks only whether a licence is declared; 6/10 for a
recognisable filename, +3 top-level, +1 if OSI/FSF-approved. A 10/10 is fully compatible with an
AGPL dependency tree, and expected behaviour on a BUSL-1.1 repository.

### 1.4 Buy a commercial SCA scanner and treat its verdict as authoritative

**Not rejected outright — rejected as an *authority*.**

FOSSA publishes a 99.8% accuracy claim; Black Duck publishes knowledge-base size; Snyk documents
that manifest-declared licences may differ from published ones and yield unknowns; Mend and
Revenera publish no numeric claims at all. **No vendor publishes a reproducible benchmark**, and
the Software Heritage License Dataset authors state plainly that no third-party scientific
benchmark comparing these tools exists — ScanCode's leadership is "generally assumed in the
industry."

A vendor may still be worth buying for coverage and convenience. What it cannot do is discharge
the human-review requirement, and no vendor's verdict should be stored as if it were ground
truth. Store it as one detector's opinion inside `license_evidence` (FR-27).

### 1.5 One `commercial_use` boolean

**Rejected.** "Can this be used commercially" has two different subjects with different evidence,
different failure modes and different consequences: whether *we* may publish the metadata, and
whether a *visitor* may use the tool. They are not correlated — a tool can be freely usable by
anyone while its logo and marketing copy are firmly protected, and a tool with restrictive
end-user terms may place no restriction at all on describing it factually. PRD §9 keeps them as
`catalog_use` and `end_user_use`.

### 1.6 A single `verified` boolean

**Rejected.** Verification is an assertion about several independent things — existence,
accessibility, maintenance, usage evidence, security, privacy, licence — assessed at different
times, by different mechanisms, with different confidence. Collapsing them loses exactly the
information a visitor needs to decide whether *their* concern is covered. Hence per-assertion
`checked_at` (FR-79) and per-assertion decay (FR-81).

### 1.7 A single status vocabulary shared by evidence and judgement

**Rejected during the review gate**, which found the not-known state spelled six different ways
(`needs_review`, `not_found`, `unverified`, `not_assessed`, `unknown`, `null`), `unknown` absent
from its own enumeration, and the single rule guarding the headline claim failing **open** —
a literal `!= "unknown"` check passes `not_assessed` security and `unverified` assets.

The root cause was not sloppy naming. It was that one vocabulary was being asked to express two
different things: *what we observed* and *what we decided*. Those have different value sets and
different consumers. "We did not check" and "we decided this is unacceptable" are not points on
one scale.

**What was taken instead.** PRD §8's three axes — evidence state, disposition state, gate
outcome. The cost is more machinery: three vocabularies instead of one, and a derivation step
between each. The benefit is that fail-open becomes structurally difficult, because gates are
written as allowlists over affirmative dispositions rather than as denylists over one bad value.

The rule that makes it work is directional: **unconfirmed evidence may stay in the corpus; it may
not pass a gate that requires confirmation.** Corpus membership is refused only by a *confirmed
failure*. Every other gate is granted only by a *confirmed success*.

### 1.8 Queue every unresolved judgement for human review

**Rejected.** It is the obvious reading of "human review is not optional" and it is unstaffable.

The review gate's arithmetic: with five assertion classes decaying on cadence, a literal
decay-triggers-review reading generates roughly thirty review events per entity per year, and one
operator sustains about **2,300 entities** — less than twice the corpus that already exists.
Narrow the triggers to consequence-bearing judgements and the same operator sustains around
**58,000**. The binding constraint was never volume; it was trigger scope.

**What was taken instead.** PRD §8.5 queues an item only when the unresolved judgement could
materially change public listing, commercial usability, or an already-published high-risk claim.
Three things are explicitly *not* queued: every `indeterminate` value, unverified visual assets
(the neutral placeholder costs nothing), and `unavailable` caused by an external outage (a system
condition, not a judgement).

**Cost of the choice.** A large tail of permanently unresolved records. That is the intended
outcome — they remain listed, carrying cautions, and simply never earn the strong claim.

### 1.9 Migrate the 1,161 existing records into the new model

**Rejected.** Backfill-in-place looked cheaper than re-collection and is not.

Every field the new model needs — licence slots, dispositions, audience evidence, privacy,
security, quality — requires a fresh fetch regardless. So "backfill" *is* a re-harvest, plus the
remediation cost of 491 colliding identifiers, 137 URL sentinels and 36 URLs shared by 77 rows,
plus one hazard that is easy to miss: those records already contain descriptions copied from
awesome-lists, so migrating them **inherits the CC-BY-SA exposure C9 exists to prevent, on day
one**.

**What was taken instead.** PRD §12.1 freezes them as a legacy seed manifest. The durable value
of that corpus is the ~1,024 usable URLs, not the records wrapped around them. This converts a
blocked migration with four documented contract failures into an ordinary ingest.

### 1.10 Wholesale reuse — or wholesale replacement — of the existing pipelines

**Both rejected.** The memlog carried an unconfirmed assumption for the entire drafting period
("supersedes/unifies them — TO CONFIRM"), and an earlier revision quietly answered it a third way
by calling the Python pipeline "a reference asset, not the subject of it." None of the three was
a decision anyone made.

Wholesale reuse fails because the existing schemas cannot express the three-slot licence model,
the evidence/disposition split, or per-context commercial use. Wholesale replacement discards
tested machinery — atomic writes, advisory locks, the four-score verification path, and a
**committed publication layout contract** that the review gate confirmed does exist (the previous
revision wrongly recorded it as absent; only the producer is missing).

**What was taken instead.** PRD §12.2: contract-driven incremental replacement. A component is
reused only where it passes the new schema and behavioural contract; the PRD is authoritative.
This keeps the decision per-component and evidence-based rather than ideological.

---

## 2. Mechanism notes

### 2.1 ScanCode as the licence-classification component

The operative asset is not ScanCode's detection breadth (~2,100–2,500 licence texts, ~32,000–
35,000 rules) but its **LicenseDB `category` field**: Permissive · Copyleft · Copyleft Limited ·
Commercial · Proprietary Free · Non-Commercial · Free Restricted · Source-available. That
taxonomy maps to commercial usability; the SPDX identifier does not. SPDX is an identifier
registry — v3.28.0 lists BUSL-1.1, SSPL-1.0 and Elastic-2.0 with **neither** "OSI Approved" nor
"FSF Free/Libre" marked, which is a labelling fact, not a permission.

Two cautions for whoever implements this:

- **ScanCode's License Clarity Score measures documentation quality, not permission.** A BUSL
  repository can score perfectly. Do not wire it to a gate.
- ScanCode's recall advantage is bought with false positives. The one published comparison
  (Wolter, FAU 2019) found ScanCode detected more licences per project than FOSSology (~1,094 vs
  ~903) but with a **positive predictive value of 37.5% vs 66.66% in conflict situations**. Small
  and dated, but it is the only published comparison found.

### 2.2 Why licence determination is pinned to a SHA

Relicensing is not hypothetical and not rare in the infrastructure tier: HashiCorp → BUSL (Aug
2023), Redis → RSALv2/SSPL (Mar 2024) → AGPLv3 (May 2025), Elastic → ELv2 → AGPLv3 (Aug 2024),
Liquibase Community → FSL (Sep 2025), Cockroach Core retired (Nov 2024). The direction is not
uniform — Redis and Elastic partially reversed, Gemma 4 shipped Apache-2.0 in Apr 2026 — which is
precisely why a stored verdict without a version anchor is meaningless. FR-36 and FR-82 exist for
this.

The mechanism is also the cheap way to detect drift: re-resolving the licence only when the
pinned SHA changes avoids re-scanning the whole corpus on every cycle.

### 2.3 Transitive licence obligations — deliberately deferred

PRD §14 does not require dependency-closure licence analysis, and that is a conscious limitation
rather than an oversight.

The evidence says it matters: 7.27% of PyPI releases carry licence incompatibilities, 61.3% of
those caused by transitive dependencies; ~5.2% of dependency links across registries connect
incompatibly-licensed packages; "Don't Trust the Label" finds 62.3% of 232,270
dataset→model→app chains pass through at least one unlicensed artifact.

The evidence also says it is not currently solvable at acceptable cost: manifest-level scanners
do not traverse; file-level scanners have no notion of obligation propagation; only term-level
analysers (LiDetector / LiResolver class) reason about compatibility, and they are research-grade
at ~76% recall.

**Practical stance.** The engine assesses the artifact, not its dependency closure, and the
published claim must be scoped accordingly — this is one of the limits NFR-5's disclaimer
language has to cover. Revisit if a production-grade term-level analyser appears.

### 2.4 `catalog_use` is an entirely different checking path

Worth stating plainly for implementers: `end_user_use` is answered by reading licence texts;
`catalog_use` is answered by reading `robots.txt`, API terms of service, and brand guidelines.
They share a record and share nothing else — different fetchers, different parsers, different
review triggers. Building `catalog_use` as a branch of the licence classifier would be a
structural mistake.

### 2.5 Icons: why this is a trademark question, not a licence question

An MIT licence grants rights in *code*. Logos and product names are trademarks, and trademark law
protects source identification, not expression — permission to copy the software carries no
permission to reproduce the mark. Many projects publish an explicit brand guide or media kit
precisely because the code licence does not cover it.

Hot-linking a favicon does not escape this: it is still reproduction in our interface, and it
additionally creates a dependency on someone else's server. Hence FR-59 and PRD §11 — store
nothing without an explicit basis, and render the neutral placeholder in every other case.

### 2.6 Non-developer assessment is the expensive path

The §6.2 criteria — browser-usable, no CLI, GUI-reachable core function, signup-to-first-result,
pricing published, guides comprehensible — are not derivable from repository metadata. They
require fetching and reading product pages, pricing pages and documentation, which is a
model-driven operation per entity.

This is the main driver behind NFR-9. Two mitigations worth designing in: assess audience only
for entities that have already passed existence and accessibility checks, and cache the
assessment against a content hash of the product page so unchanged pages are not re-assessed.

---

## 3. Notes for downstream documents

**For architecture.** The four gates in PRD §8.3 are computed properties, not stored state — they
must be re-derivable from the underlying assertions on every assessment (FR-57), or they will
drift out of agreement with the evidence. Related: FR-65 makes reviewer verdicts *inputs* to gate
computation, not overrides applied afterwards — with two invalidation paths (FR-9 identity
discontinuity, FR-82 change detection) that must be able to revoke a human decision.

**For architecture.** The three-axis model (PRD §8) is the load-bearing structure. Evidence
records attach to assertions, dispositions attach to domains, gates attach to the record. Any
implementation that flattens these — a single status column, or a stored gate boolean — reopens
the fail-open defect the review gate found. The six evidence states must remain distinguishable
all the way into the published artifact (FR-83).

**For architecture.** FR-11 (multi-source merge) and FR-12 (conflict recording) together imply
the record is an accumulation of source-attributed assertions rather than a flat document. The
existing `conflicting_evidence_log` in the current schema is the right instinct at the wrong
granularity. Note FR-11's added refusal condition: two entities sharing a URL is not evidence
they share an identity — the existing corpus has 36 URLs across 77 rows precisely because that
was assumed.

**For architecture.** FR-97 and PRD §17 are a pre-implementation blocker, not a note. The
validation gate forbids editing `config/`, and ten requirements are configuration changes by
nature. Choose one of the two resolutions before building anything that touches vocabularies,
thresholds, cadences or the source registry.

**For UX.** PRD §13 is the contract to read first. The engine's guarantees are *conditional* on
consumer behaviour — cautions displayed, per-context filtering, neutral placeholders, coverage
not overstated, retractions honoured. Each row of that table names what breaks if the condition
is not met. The engine does not specify rendering; it specifies what must survive rendering.

**For UX.** The neutral placeholder (§11) will be visible on a large fraction of entries at
launch, and the unclear-licence caution is a legal position (C10), not a minor annotation.

**For UX.** §6 requires the same catalogue to serve developers and non-developers with different
comparison criteria. The data model supports it; the interface question — one view that adapts,
or two entry paths — is not settled here. §18 records that the non-developer field has no
confirmed upstream consumer.

**For operations.** Accountability for review sits with the existing Knowledge Team; the
executing role is the **Catalog Review Operator** (FR-62), deliberately defined as a role rather
than a new standing team so it can be discharged by rotation or contract. Two things must be
sized before launch: the queue capacity and SLA of FR-92, and the competency match — FR-30 calls
licence election a legal act, which is not the same skill as the summarisation and scoring the
Knowledge Team performs today.

**For operations.** NFR-2's 15–20% and NFR-12's 80–85% are **initial measurement targets derived
from external research, not guarantees**. SM-1 and CM-1 exist to replace them with figures
measured on our own corpus. Treat the first full run as the baseline-setting run.

---

## 4. Terminology

| Term | Meaning here |
|---|---|
| **Entity** / **building block** | One harvested thing: a tool, workflow, agent, prompt, skill, or MCP server |
| **Assertion** | One checked claim about an entity, carrying its own evidence record and `checked_at` |
| **Evidence state** | Axis 1 (PRD §8.1) — what we observed: `confirmed` · `conflicting` · `absent` · `unreadable` · `unchecked` · `unavailable` |
| **Disposition** | Axis 2 (PRD §8.2) — what we decided for a domain: `cleared` · `cleared_with_conditions` · `blocked` · `indeterminate` · `review_required` |
| **Gate** | Axis 3 (PRD §8.3) — one of four computed admission decisions: `corpus_included` · `publicly_listed` · `commercially_usable` · `asset_reusable` |
| **Confirmed failure** | A `blocked` disposition carrying a reason code — something checked and found wrong, never something merely unchecked |
| **Caution** | A display-level flag (`needs-review` · `caution` · `possibly-inactive`) carried with a record; distinct from the machine states above |
| **Reason code** | The identifier attached to every `blocked` disposition (`EXIST_*`, `SAFE_*`, `SEC_*`, `LIC_*`, `PRIV_*`) |
| **Usage context** | The intended use a commercial verdict is resolved against: `internal_use` · `redistribution` · `hosted_service` · `model_training` |
| **`catalog_use`** | Whether *we* may collect and display the entity's metadata and assets |
| **`end_user_use`** | Whether a *visitor* may use the tool commercially — resolved per usage context, never as a scalar |
| **Legacy seed manifest** | The frozen 1,161 records, preserved as discovery facts only (PRD §12.1) |
| **Catalog Review Operator** | The role performing individual human reviews; accountability sits with the Knowledge Team (FR-62) |
