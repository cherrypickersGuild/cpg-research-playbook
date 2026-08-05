# Extract — License determination, revised on primary sources (Aug 2026)

**Delivery caveat.** This was commissioned as a four-part landscape survey (registry landscape
table · quality signals · license vetting · non-developer demand). **Only the revised license
section was returned.** The registry comparison table, the quality-signal analysis, the
white-space assessment and the risk list were **not delivered** and remain open — see
`prd.md` §6.

This extract **supersedes** the license-vetting conclusions in
[`extract-license-landscape.md`](extract-license-landscape.md) where the two disagree.

---

## The base rate is worse than previously stated — and it settles the design

GitHub's own published analysis (using Licensee): only **~20% of repositories carry a detectable
license** (~30% counting forks), stable across GitHub's history. Of the licensed minority,
**15.68% land in "Other/Non-standard."**

GitHub is explicit that absence means **all rights reserved** — "no one may reproduce,
distribute, or create derivative works."

> **The default disposition of a randomly harvested artifact is: not commercially usable.**
> Rejecting on absence is the highest-value automated rule available, and it disposes of the
> majority of the corpus for free.

## What the detectors actually return

- `GET /licenses` serves only **13 licenses** by default; everything else in the SPDX universe
  collapses to `key: "other"`, `spdx_id: "NOASSERTION"`.
- Licensee hard-codes `CONFIDENCE_THRESHOLD = 98` (Sørensen–Dice against normalized text) and
  documents that it does **not** examine dependency licenses, README license references, most
  licenses, or source-file headers. On unresolvable multiple matches it **returns no project
  license**. It does not parse SPDX expressions (`-or-later`, `AND`/`OR`/`WITH`).

**Asymmetry worth designing around:** an *appended* restriction ("commercial use prohibited")
drops below 98% and correctly yields NOASSERTION; a *stripped attribution clause* can still
score ≥98% and be reported as **clean MIT**.

## The actionable component: ScanCode's `category` field

ScanCode carries ~2,500 licenses, 35,000+ detection rules and 40,000+ license-detection tests —
but the operative asset is that its **LicenseDB tags each license with a category** beyond the
SPDX ID:

`Permissive` · `Copyleft` · `Copyleft Limited` · `Commercial` · `Proprietary Free` ·
`Non-Commercial` · `Free Restricted` · `Source-available`

**That taxonomy, not the SPDX identifier, is what maps to commercial usability**, and it is the
single best off-the-shelf component for this product.

Two cautions:

- ScanCode's **License Clarity Score measures documentation quality, not permission** — a BUSL
  repo can score perfectly.
- **No vendor publishes audited precision/recall.** Treat accuracy claims as *unavailable*, not
  *high*.
- **OpenSSF Scorecard is irrelevant here**: of 19 checks, `License` asks only "does the project
  declare a license?" — 10/10 on a BUSL-1.1 repo is expected behavior.

## Open-washing, with the mechanics that need encoding

SPDX List v3.28.0 (2026-02-20) carries independent **"OSI Approved?"** and **"FSF Free/Libre?"**
columns; **BUSL-1.1, SSPL-1.0 and Elastic-2.0 are all listed with neither marked** — SPDX is an
identifier registry, **not an approval**.

- **BUSL-1.1** grants only non-production use, with the **Additional Use Grant** living as
  free-form vendor prose in a header field. Some grants *do* permit your use — **this is
  irreducibly human.**
- **FSL** converts to MIT/Apache-2.0 after two years *per version*.
- **Llama**'s threshold is **700M MAU in the preceding calendar month, measured on the version
  release date**, plus mandatory "Built with Llama" attribution, a derivative-naming rule, an
  incorporated AUP, and litigation-termination. OSI's OSAID evaluation lists **Llama 2, Grok,
  Phi-2 and Mixtral as failing**.

## The share-alike trap is in the seed corpus itself

- `sindresorhus/awesome` is **CC0-1.0** — safe.
- `awesome-selfhosted/awesome-selfhosted` is **CC-BY-SA-3.0** — ingesting its curatorial
  selection and descriptions **can force the published catalog under BY-SA.**

> **Rule: harvest the facts (repo URL, name), never the prose.**

This bears directly on the current pipeline, which seeds from curated awesome-list reports and
copies descriptions.

## Transitive inheritance — where automation collapses, now quantified

None of the three detectors traverse dependencies; Licensee says so explicitly. Three studies
converge:

- **"Don't Trust the Label"** (arXiv:2607.20300) traces **232,270** dataset→model→app chains:
  **62.3% pass through at least one unlicensed artifact**; obligation-bearing licenses survive
  end-to-end at **<7%** vs **95.1%** for permissive.
- **License Drift** (arXiv:2509.09873v2; 1.6M models, 136k repos): **35.5% of model→repository
  transitions eliminate restrictive clauses**; ML-license retention **0.4%**; dominant violation
  pattern **ML→Permissive (109,214 cases, 84.9%)**; legacy compatibility matrices miss **81.5%**
  of proprietary-API conflicts.
- Only **14.2% of conflicts are fundamentally unresolvable** — **the labels are wrong, not the
  artifacts.**

> Read together: **a permissive label on a downstream AI repo is empirically the most likely
> place for a laundered restriction to hide.**

## Prompts: weak copyright is not permission

The USCO Part 2 report (Jan 29, 2025) addresses AI *outputs* and does not resolve whether a
prompt is itself protectable. Ordinary doctrine suggests a one-line prompt is not (short
phrases; merger on functional instructions; scènes à faire), while a long structured system
prompt plausibly is.

**But copyright is not the binding constraint** — the repo license as contract, platform ToS, EU
*sui generis* database rights over the collection, and trademark all bind regardless.

> **Do not build a "probably not copyrightable" exception into the engine.**

*Caveat carried from the source pass: the USCO PDF's text layer was not extractable, so it is
cited for date and scope only — the merger-doctrine analysis is general doctrine, not a
quotation.*

## Revised ceiling: ~80–85% auto-dispositionable, 15–20% human-review-or-reject

(Up from an earlier 10–15% estimate. No published benchmark exists for this task; the estimate
is compositional.)

**Auto-allow** — ≥98%-confidence exact SPDX match on a short allowlist (MIT, Apache-2.0,
BSD-2/3, ISC, 0BSD, Unlicense, CC0-1.0, MPL-2.0) **only when** LICENSE, manifest and headers
agree and no vendored directory contradicts them.

**Auto-reject** — ScanCode categories `Commercial` / `Proprietary Free` / `Non-Commercial` /
`Source-available` / `Free Restricted`, plus a denylist (BUSL-\*, SSPL-\*, Elastic-2.0, FSL-\*,
Llama/Gemma community, CC-BY-NC\*, CC-BY-ND\*, RAIL/OpenRAIL, JSON License) — **and null /
NOASSERTION / "other."**

**Human required** —

- NOASSERTION on otherwise-high-value artifacts
- any LICENSE-vs-manifest-vs-header disagreement (Licensee resolves to the LICENSE file —
  `package.json: "MIT"` over an AGPL LICENSE is **AGPL**)
- `OR` expressions (**electing a license is a legal act**)
- BUSL Additional Use Grant prose
- AGPL anywhere in the transitive closure of a hosted service
- modified text of a known license
- share-alike inbound to the catalog
- anything crossing Hugging Face

## Two engineering mandates this implies

1. **Store `license_evidence` as a structured record** — detected ID, detector, confidence,
   source path + line range, manifest value, disagreement flags, ScanCode category, reviewer +
   date. **Never a bare string.** Default `commercial_use` to `"unknown"` and require an
   affirmative transition.
2. **Re-scan on a cadence against a pinned commit SHA.** HashiCorp→BUSL, Redis→RSALv2/SSPL→AGPL,
   Elastic→ELv2→AGPL all mean **a 2024 clearance is not a 2026 clearance.**

## Risks (partial — the full risk list was not delivered)

- **Human-review load is 15–20%**, not 10–15%.
- **Manifest-trust risk** — auto-resolving a LICENSE/manifest mismatch in the manifest's favor
  produces confidently wrong permissive verdicts: the exact failure the laundering data predicts.
- **Own-disclaimer risk** — GitHub, with more data and more lawyers, states it is "not a law
  firm." A product asserting **"commercially usable" as a headline claim** assumes liability the
  incumbents explicitly decline, and needs **counsel-reviewed disclaimer language before launch,
  not after.**

## Sources

[GitHub license usage data](https://github.blog/open-source/open-source-license-usage-on-github-com/) ·
[licensee what-we-look-at](https://github.com/licensee/licensee/blob/master/docs/what-we-look-at.md) ·
[ScanCode LicenseDB categories](https://scancode-licensedb.aboutcode.org/) ·
[Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md) ·
[SPDX BUSL-1.1](https://spdx.org/licenses/BUSL-1.1.html) ·
[Llama 4 LICENSE (raw)](https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/LICENSE) ·
[OSI Open Source AI](https://opensource.org/ai) ·
[awesome-selfhosted CC-BY-SA-3.0](https://raw.githubusercontent.com/awesome-selfhosted/awesome-selfhosted/master/LICENSE) ·
[Don't Trust the Label (arXiv:2607.20300)](https://arxiv.org/abs/2607.20300) ·
[License Drift (arXiv:2509.09873v2)](https://arxiv.org/html/2509.09873v2) ·
[USCO AI Part 2](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf)
