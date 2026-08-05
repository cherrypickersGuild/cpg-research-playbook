# Extract — License-detection tooling and its measured accuracy ceiling (Aug 2026)

Third companion extract. This one answers the NFR question: **how accurate can automated
license determination actually be?** Received 2026-08-05.

---

## 1. ScanCode Toolkit (AboutCode/nexB) — the de facto reference implementation

**Data-driven, not regex-driven**: ships ~**2,100 license full texts** and **~32,000 license
notices, mentions and variants** compiled into a search index. Latest release **v32.5.0 (Jan
2026)**, tracking **SPDX License List 3.28**. Claims "best-in-class and reference tool" status
and **30,000+ automated tests**.

Scoring mechanics are widely misread:

- `rule_relevance` is a **rule-authoring** property — 0–100; a rule of **>20 words is 100%
  relevant, a single-word rule 5%**, +5% per additional word.
- `match_coverage` = matched words ÷ match magnitude.
- `score` derives from matched tokens, query tokens in the matched range (including
  unknown/unmatched), and rule relevance.
- **A score of 100 means "this text matches this rule fully" — NOT "this is the project's
  license."**

The 2023+ rework introduced `LicenseDetection` objects with a `detection_log`, plus
**`license_clues`** — matches deliberately demoted because "the matched license rule data is not
sufficient to create a LicenseDetection" — and the **unknown license categories**, notably
`unknown-license-reference` (text *about* licensing that matched only an unknown-keyed rule).
These are honest uncertainty signals and they are common.

Documented false positives: obvious MIT text reported as `unknown-license-reference` (#4481);
spurious unknown-reference before x11-lucent text (#3079); misleading *declared license* rollups
(#4551).

**ScanCode.io** wraps this in scripted pipelines with PurlDB package matching and a "license
clarity score" compliance gate — i.e. **the ecosystem's own answer to detection uncertainty is
triage, not automation.**

## 2. licensee (Ruby) — this is what GitHub's license badge actually is

Three stages: exact match → exact match after stripping whitespace and copyright lines →
**Sørensen–Dice coefficient** similarity. **Default `confidence_threshold` is 98.** Looks only at
root `LICENSE`/`LICENCE`/`COPYING`/`COPYRIGHT`/`UNLICENSE` variants plus a REUSE-style
`LICENSES/` directory.

Its own docs are candid about scope — licensee does **not** consider: dependency licensing,
README license references ("can't reliably parse natural language"), every possible license
("just the most popular ones"), per-file source headers, package-manager metadata (optional
plugins only), and explicitly not **compliance** — *"multiple tools and human review are
needed."* Conflicting matches are returned as a set, not resolved.

> **Load-bearing for this PRD: GitHub's `license` field is a single-file, root-only,
> most-popular-licenses-only heuristic.**

## 3. askalono (Amazon/jpeddicord) — legacy

Bigrams + Sørensen–Dice against known license texts, max score. No hand-maintained regexes;
aggressive normalization. README disclaimer: *"You are not entitled to rely on the accuracy of
the output of this tool."* **The project is archived — no longer maintained.**

## 4. Commercial vendors — claims, not measurements

| Vendor | Public claim | Reality |
|---|---|---|
| **FOSSA** | **99.8%** license scanning accuracy, 17+ languages / 20+ build systems | No methodology, corpus, or ground truth published |
| **Black Duck** (spun out of Synopsys 2024–25) | KB of **>9M unique components** from >50,000 sites; elsewhere "10M+ projects"; >260,000 tracked vulns | KB size is a **coverage** claim, not accuracy |
| **Snyk Open Source** | Scans **manifest files** against known-licenses set | Own docs concede: declared-vs-published license mismatch, and *"if the developer did not define the licenses in the package manager, this could result in unknown values"* |
| **Mend** (ex-WhiteSource), **Revenera FlexNet Code Insight** | — | **No numeric accuracy claims found** |

**No vendor publishes a reproducible benchmark. Every number above is marketing.**

## 5. SBOM standards and license-field quality

**SPDX**: ISO/IEC 5962:2021 codifies only **SPDX 2.2.1**; the live spec is **3.0.1** with 3.1 in
development — "ISO-standard SBOM" and "current SPDX" are not the same artifact. Fields:
`licenseConcluded`, `licenseDeclared`, `licenseInfoInFiles`, plus `LicenseRef-` custom refs.

**CycloneDX 1.7** shipped **21 Oct 2025**, adopted as **ECMA-424, 2nd edition, Dec 2025**;
carries `licenses[]` with SPDX id/expression/name and `evidence.licenses` for
detected-vs-declared.

Quality is poor and measured:

- Component license was **NOT** in the 2021 NTIA minimum elements. **CISA's 2026 Minimum
  Elements (July 2026)** newly **adds component license as a required field** — an admission the
  field was systematically absent.
- **Only 7% of analyzed SBOMs report all NTIA minimum fields; 12% don't comply with their own
  declared standard** (Nocera et al. 2025).
- Torres-Arias et al. (2023): four tools over **1,000 Docker images** — **none** produced full
  coverage of package IDs and licenses.
- A large-scale adherence study reports license fields show **near-zero consistency across most
  tool pairs** (arXiv 2601.05622).

## 6. OpenSSF Scorecard — presence only, not usability

~20 checks. The **License** check is **risk: Low** and scores **6/10** for a recognizable
`LICENSE`/`COPYRIGHT`/`COPYING` filename or `LICENSES/` entry, **+3** if top-level, **+1** if the
license is FSF/OSI-approved.

It does **not** evaluate license compatibility, copyleft obligations, commercial usability,
dependency licenses, or whether the file's content matches the declared license.
**A 10/10 License score is compatible with an AGPL dependency tree.**

## 7. GitHub dependency graph / SBOM export

`GET /repos/{owner}/{repo}/dependency-graph/sbom` returns SPDX JSON with
`licenseConcluded`/`licenseDeclared` per package. Limits: values are **registry-metadata
derived** (declared, not verified); the graph covers **manifest-declared dependencies** only, not
vendored or copy-pasted code; and **GitHub Enterprise Server does not retrieve license
information for dependencies at all**.

## 8. The accuracy ceiling — what is actually measured

| Study | Method | Result |
|---|---|---|
| **Ninka** (German, Di Penta, Davies, ASE 2010) | sentence matching on source-file **headers** | **precision 96.6%, recall 82.3%** over ~0.8M files (Debian 5.0.2). Still the most-cited hard number — and it is header-only and 16 years old |
| **LiDetector** (TOSEM 32(1):22, 2022) | PCFG + sentiment over license **terms** | **93.28% precision / 75.70% recall** on term identification; **91.09%** on rights/obligations inference; **83.58% F1**. On 200 GitHub projects flagged 169 incompatible at **10.06% FP / 2.56% FN** |
| **Wolter 2019 (FAU)** tool comparison | ScanCode vs FOSSology | ScanCode detected most (~1,094 licenses/project avg vs ~903) but **in conflict situations ScanCode's positive predictive value was 37.5% vs FOSSology's 66.66%** — ScanCode's recall advantage is bought with false positives |

**Evidence thinness is explicit.** The Software Heritage License Dataset authors (EMSE; **6.9M
unique license files**, ground truth from **8,102 manually analyzed documents**) state they are
*"not aware of third-party scientific benchmarks comparing these and other tools"* and that
ScanCode's leadership is *"generally assumed in the industry."*
**There is no accepted public benchmark for end-to-end license determination.**

**Missing licenses**: GitHub/Balter 2015 (~20% of public repos licensed) and a 2020 Open Weaver
analysis of the top 1M starred repos (**46% no license, +7% "other"**) bracket the problem. Both
non-peer-reviewed and population-dependent; **no rigorous 2023–2026 replication surfaced — a real
gap.**

**Manifest vs LICENSE disagreement**: Riehle et al. found **roughly half** of studied
repositories show inconsistencies between declared and in-code licenses. For PyPI, **97.98%** of
the top-8,000 packages' license files are standard SPDX texts and only **2.02%** are substantive
variants (0.30% modified SPDX, 1.12% custom, 0.55% dual) — yet **median Winnowing similarity to
canonical text is 0.90**, meaning *textual* drift is near-universal while *legal* drift is rare.
**That gap is exactly what a 98%-threshold matcher gets wrong in both directions.**

## 9. Transitive inheritance — the MIT-wrapper-over-AGPL trap

An MIT-declared package's own manifest is legally uninformative about its dependency closure.

- **7.27% of PyPI releases have license incompatibilities; 61.3% of them caused by transitive
  dependencies** (arXiv 2308.05942).
- Across registries: npm shows **257,593** absolute incompatibilities; **~5.2% of dependency
  links** connect incompatibly-licensed packages; per-ecosystem rates run **0.6% (npm) to 13.9%
  (RubyGems)** (Pfeiffer, arXiv 2203.01634).
- In the PyPI variant study, 54 packages with substantial license variants propagated
  incompatibility to **10.7% of 2,177 downstream dependents (9.0% of 34,004 releases)**.

Manifest-only scanners (Snyk, GitHub dep graph) see the declared string and stop. File-level
scanners (ScanCode, Black Duck snippet matching) see the text but have no notion of obligation
propagation. Only term-level analyzers (LiDetector/LiResolver class, **still research-grade**)
reason about compatibility — at **~76% recall**.

## Bottom line for the PRD

Fully automated license **determination** has no demonstrated ceiling above roughly
**95–97% precision at ~75–85% recall** on the *narrow* subtask of identifying a license text, and
is materially worse on the real question — *what obligations does this artifact impose*.

Vendor "99.8%" claims are unaudited and measure a different, easier thing. Every serious tool's
own documentation — licensee, askalono, ScanCode — says human review is required.

> **Design for a triage pipeline with explicit unknown/clue states, not a verdict API.**

## Sources

- [ScanCode license detection](https://scancode-toolkit.readthedocs.io/en/latest/explanation/scancode-license-detection.html) · [FAQ (rule counts)](https://scancode-toolkit.readthedocs.io/en/stable/getting-started/faq.html) · [adding rules](https://scancode-toolkit.readthedocs.io/en/stable/how-to-guides/add_new_license_detection_rule.html) · [repo](https://github.com/aboutcode-org/scancode-toolkit) · [releases](https://github.com/aboutcode-org/scancode-toolkit/releases)
- ScanCode issues: [#979 score/relevance](https://github.com/nexB/scancode-toolkit/issues/979) · [#1675 unknown-license RFC](https://github.com/aboutcode-org/scancode-toolkit/issues/1675) · [#4481 MIT→unknown](https://github.com/aboutcode-org/scancode-toolkit/issues/4481) · [#3079](https://github.com/aboutcode-org/scancode-toolkit/issues/3079) · [#4551 misleading declared license](https://github.com/aboutcode-org/scancode-toolkit/issues/4551)
- [ScanCode.io](https://github.com/aboutcode-org/scancode.io) · [built-in pipelines](https://scancodeio.readthedocs.io/en/latest/built-in-pipelines.html)
- [licensee repo](https://github.com/licensee/licensee) · [what we look at](https://licensee.github.io/licensee/what-we-look-at/) · [confidence threshold](https://licensee.github.io/licensee/customizing/) · [CLI usage](https://github.com/licensee/licensee/blob/main/docs/command-line-usage.md)
- [askalono (archived)](https://github.com/jpeddicord/askalono) · [askalono crate](https://lib.rs/crates/askalono)
- [FOSSA (99.8% claim)](https://fossa.com/solutions/oss-license-compliance/) · [FOSSA snippets](https://fossa.com/products/snippets/) · [Black Duck KnowledgeBase](https://www.blackduck.com/software-composition-analysis-tools/knowledgebase.html) · [Snyk license compliance docs](https://docs.snyk.io/scan-with-snyk/snyk-open-source/scan-open-source-libraries-and-licenses/open-source-license-compliance) · [Revenera FlexNet Code Insight](https://www.revenera.com/software-composition-analysis/products/flexnet-code-insight)
- [CycloneDX v1.7](https://cyclonedx.org/news/cyclonedx-v1.7-released/) · [ECMA-424](https://ecma-international.org/publications-and-standards/standards/ecma-424/) · [CISA 2026 SBOM Minimum Elements](https://www.cisa.gov/resources-tools/resources/2026-minimum-elements-software-bill-materials-sbom) · [CISA 2025 draft](https://www.cisa.gov/sites/default/files/2025-08/2025_CISA_SBOM_Minimum_Elements.pdf)
- SBOM quality: [BOM practices survey](https://arxiv.org/html/2601.11678v1) · [adherence gap](https://arxiv.org/pdf/2601.05622) · [where we stand](https://arxiv.org/pdf/2301.05362) · [JBomAudit (NDSS 2025)](https://www.ndss-symposium.org/wp-content/uploads/2025-322-paper.pdf) · [SBOM adoption in OSS (JSS 2025)](https://www.sciencedirect.com/science/article/pii/S0164121225002092)
- [OpenSSF Scorecard checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md) · [scorecard.dev](https://scorecard.dev/)
- [GitHub SBOM REST endpoint](https://docs.github.com/en/rest/dependency-graph/sboms) · [About the dependency graph](https://docs.github.com/code-security/supply-chain-security/understanding-your-software-supply-chain/about-the-dependency-graph)
- Academic: [LiDetector (TOSEM 2022)](https://arxiv.org/abs/2204.10502) · [LiResolver](https://arxiv.org/pdf/2306.14675) · [Ninka](https://github.com/dmgerman/ninka) · [Software Heritage License Dataset](https://arxiv.org/abs/2308.11258) · [License Inconsistencies on GitHub (Riehle)](https://dirkriehle.com/wp-content/uploads/2022/10/License_Inconsistencies_on_Github.pdf) · [License usage and changes (EMSE 2016)](https://www.cs.wm.edu/~denys/pubs/EMSE'16-Licensing.pdf) · [Large-scale license usage study (MSR 2024)](https://xing-hu.github.io/assets/papers/msr2024.pdf) · [Small Changes, Big Trouble (PyPI variants)](https://arxiv.org/html/2507.14594) · [PyPI license incompatibilities](https://arxiv.org/pdf/2308.05942) · [License Incompatibilities in Software Ecosystems (Pfeiffer)](https://arxiv.org/pdf/2203.01634) · [Open Source, Hidden Costs (SLR)](https://arxiv.org/pdf/2507.05270) · [Catch the Butterfly (SPDX terms and conflicts)](https://arxiv.org/pdf/2401.10636)
- Tool comparisons: [Wolter 2019 (FAU)](https://osr.cs.fau.de/wp-content/uploads/2019/08/wolter_2019.pdf) · [Comparison of OSS License Scanning Tools (DiVA)](https://www.diva-portal.org/smash/get/diva2:1463853/FULLTEXT01.pdf) · [LicenseScannerComparison](https://github.com/maxhbr/LicenseScannerComparison)
