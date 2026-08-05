# Extract — AI-artifact licensing & commercial-usability determination (landscape, Aug 2026)

Bearing on the PRD's central claim: "commercially usable." Received 2026-08-05.

---

## 1. Model weights: probably not copyrightable — so the "license" is a contract

The US position on weights is unsettled; the Copyright Office has never squarely ruled.
USCO **Part 2 (Copyrightability, Jan 29 2025)** addresses AI *outputs*, not weights. **Part 3
(Generative AI Training, pre-publication May 9 2025)** argues that where outputs closely
resemble training inputs there is a "strong argument" the **weights themselves** infringe
reproduction/derivative rights, analogizing weights to compressed copies. Part 3's authority is
compromised — Librarian Carla Hayden fired the day before release, Register Shira Perlmutter the
day after; it remains formally "pre-publication."

Scholarly consensus runs the other way on *ownership*: weights are numeric, functionally
dictated, produced by autonomous optimization — failing both originality and human-authorship
tests. In the EU, copyright is likewise doubtful, but the **sui generis database right**
(Directive 96/9) is a live alternative: 15-year term, potentially renewed by
retraining/fine-tuning, EU-based makers only, extraction of substantial parts only.

**Consequence for a catalog: a weights "license" is a contract/ToS, not a copyright license.**
Klyman, *The Mirage of AI Terms of Use Restrictions* argues such restrictions collapse in
practice — no copyright hook, formation and privity problems, nothing binding a third-party
redistributor. Treat Llama/Gemma/OpenRAIL-style terms as contractual conditions requiring
evidence of acceptance, not as SPDX-comparable grants. HF now carries
`openmdw-1.0`/`openmdw-1.1` precisely because normal OSS licenses do not fit.

*Bartz v. Anthropic* (Alsup, June 2025) held training was fair use but pirated **acquisition**
was not — settled Sept 2025 for **$1.5B, ~500,000 works, ~$3,000/work**. Liability attached to
data provenance, not license text.

## 2. Prompts: an MIT license on a prompt library is close to a no-op

Part 2's finding — "prompts do not alone provide sufficient control for the resulting work to be
authored by a human" — is about **outputs**, and is routinely misquoted as being about prompts.
Whether the prompt string is itself protectable is ordinary doctrine: 37 CFR §202.1(a) excludes
short phrases; functional instructions with few expressive alternatives fall to **merger**; genre
conventions ("act as a senior engineer, be concise") are **scenes-à-faire**. Long, structured
prompt collections may earn thin compilation copyright in *selection and arrangement*, not in
individual prompts.

**Evidence is thin.** No US litigation over prompt-library license breach, no reported
enforcement. Marketplaces route around copyright via ToS + trade secret, which fails on privity
once a buyer republishes.

→ For the engine: a prompt repo's `LICENSE: MIT` is best read as a *non-assertion signal*
(useful, weakly evidentiary), not a grant. Absence of a license on a prompt repo is far less
blocking than on code.

## 3. Datasets: the three-layer problem, with hard miscategorization numbers

Code license ≠ data license ≠ model/weights license, and repos routinely carry one and imply
all three.

**Data Provenance Initiative** (MIT et al.; arXiv:2310.16787, *Nature Machine Intelligence* 2024)
audited **1,800+ finetuning datasets**: **license omission over 70%**, **error rates over 50%**
on popular hosting sites. **66% of analyzed Hugging Face licenses fell into a different use
category than the author intended — usually labeled *more permissive* than intended.**
Re-annotation cut "unspecified" from ~72% to ~30%.

Concrete traps: `cc-by-nc-*` bars commercial use outright; `cc-by-sa-4.0` imposes ShareAlike; EU
database rights persist independently of the CC layer; Books3 (196,640 pirated books) sat inside
The Pile; Common Crawl's ToS is not a content license for the crawled pages.

## 4. Hugging Face license metadata quality: ~70% of models have no license at all

`license:` is YAML front-matter in the card `README.md`, from a fixed list of ~90 identifiers
(Apache/MIT/BSD/GPL family, full CC matrix incl. all NC and ND variants, OpenRAIL family,
`llama2`–`llama4`, `gemma`, `grok2-community`, `openmdw-*`, plus `unknown` and `other`).
`license: other` requires a LICENSE file and free-text `license_name` — **an unbounded escape
hatch, not machine-resolvable, not validated**. Nothing checks the tag against repo contents.

- **RedMonk (May 2026)** scanned **~2.9M models**: **~1M licensed — nearly 70% carry no license
  at all.** Apache leads MIT ~2.5×; ~2/3 of licensed models OSI-approved; OpenRAIL the largest
  non-OSI category.
- **arXiv:2502.04484** mined 760,460 models (July 2024) on documentation/licensing gaps.
- **Most useful here — *From Hugging Face to GitHub: Tracing License Drift* (arXiv:2509.09873)**
  audited **364k datasets, 1.6M models, 140k GitHub projects**: **35.5% of model-to-application
  transitions strip restrictive clauses by relicensing under permissive terms.** Their
  SPDX+model-clause rule engine (~200 clauses) resolves 86.4% of detected conflicts.
  **Downstream declarations are unreliable by default.**

## 5. MCP and agent frameworks: the registry records no license at all

**"MCP is MIT" is outdated.** `modelcontextprotocol/servers`' LICENSE states the project "is
undergoing a licensing transition from the MIT License to the Apache License, Version 2.0" — new
code Apache-2.0, non-spec docs CC-BY-4.0, unconsented prior contributions **still MIT**. A
genuinely mixed repo.

**Decisive for a harvesting engine:** the official MCP registry's `server.json` schema
(2025-12-11) **has no license field**. Required properties are only `name`, `description`,
`version`; `repository`, `packages`, `remotes`, `icons`, `websiteUrl`, `_meta` carry no legal
metadata. **License must be resolved from the linked repository, not the registry.**

Third-party directories partly fill the gap: **Glama** publishes a per-server license badge
alongside quality/maintenance letter grades (~37k servers tracked mid-2026) — the only directory
with a first-class license attribute. **Smithery** (~7k servers) and **PulseMCP** surface
official/community flags and popularity, not license.

Frameworks: LangChain, LlamaIndex, AutoGen, CrewAI are MIT. The traps:

- **n8n — Sustainable Use License**: "fair-code," source-available, use limited to **internal
  business purposes / personal / non-commercial**, explicitly not OSI open source.
- **Dify — Apache-2.0 *plus riders***: no operating a **multi-tenant environment** without
  written authorization; no removing the Dify logo/copyright from the frontend.

Both are detected by naive scanners as permissive.

## 6. Marketplaces: no usable license metadata anywhere

OpenAI's GPT Store gives creators ownership of instructions/config while granting OpenAI a
nonexclusive, worldwide, irrevocable, royalty-free license — but exposes **no license field for
third-party reuse**. Anthropic's Skills Marketplace (launched May 2026, ~600 skills, 15% revenue
share) assigns output rights to users but does not standardize a per-skill artifact license.
Awesome-lists carry name + URL + blurb; no license column exists.

**Explicit gap:** no published measurement exists of what fraction of `awesome-mcp-servers`
entries have a resolvable license. If that number is needed, it must be measured directly —
resolve each entry to a repo, read the LICENSE blob via the GitHub API, and record `none`
separately from `other`. Given ~70% unlicensed on HF and GitHub's historically similar rate,
expect a large unlicensed tail.

## Design implications for the PRD

1. Model a **three-slot license record** (code / data / weights-or-artifact), never one field.
2. Treat `other`, `unknown`, and **absent** as three distinct states — absent means **"all rights
   reserved,"** not "free."
3. Verify at the **repo LICENSE blob**, not the declared tag; expect ~35% drift.
4. Flag **rider-bearing** licenses (Dify, n8n, Commons Clause, OpenRAIL use restrictions) as
   *conditional*, not permissive.
5. Record weights/model terms as **contract-acceptance evidence**, not as a copyright grant.

## Sources

- [USCO Part 2: Copyrightability (Jan 2025, PDF)](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf)
- [Copyright Office on AI Training and Fair Use — Part 3 analysis (Skadden)](https://www.skadden.com/insights/publications/2025/05/copyright-office-report)
- [USCO Part 2 client alert (Crowell & Moring)](https://www.crowell.com/en/insights/client-alerts/us-copyright-office-releases-part-2-of-artificial-intelligence-report-clarifying-copyrightability-of-generative-ai-outputs)
- [The Mirage of AI Terms of Use Restrictions (arXiv:2412.07066)](https://arxiv.org/pdf/2412.07066)
- [Are AI models' weights protected databases? (Kluwer Copyright Blog)](https://legalblogs.wolterskluwer.com/copyright-blog/are-ai-models-weights-protected-databases/)
- [Training Foundation Models as Data Compression (arXiv:2407.13493)](https://arxiv.org/pdf/2407.13493)
- [The Bartz v. Anthropic Settlement (Kluwer Copyright Blog)](https://legalblogs.wolterskluwer.com/copyright-blog/the-bartz-v-anthropic-settlement-understanding-americas-largest-copyright-settlement/)
- [Anthropic to pay authors $1.5 billion in settlement (NPR)](https://www.npr.org/2025/09/05/g-s1-87367/anthropic-authors-settlement-pirated-chatbot-training-material)
- [EU AI Act: GPAI Model Obligations in Force (Latham & Watkins)](https://www.lw.com/en/insights/eu-ai-act-gpai-model-obligations-in-force-and-final-gpai-code-of-practice-in-place)
- [European Commission Mandatory Template for Training-Data Disclosure (WilmerHale)](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/european-commission-releases-mandatory-template-for-public-disclosure-of-ai-training-data)
- [Copyright compliance under the EU AI Act for GPAI providers (Clifford Chance)](https://www.cliffordchance.com/insights/resources/blogs/ip-insights/2025/10/copyright-compliance-under-the-eu-ai-act-for-gpai-model-providers.html)
- [The Data Provenance Initiative (arXiv:2310.16787)](https://arxiv.org/abs/2310.16787)
- [A large-scale audit of dataset licensing and attribution in AI (Nature MI)](https://www.nature.com/articles/s42256-024-00878-8)
- [From Hugging Face to GitHub: Tracing License Drift (arXiv:2509.09873)](https://arxiv.org/abs/2509.09873)
- [An Empirical Analysis of ML Model and Dataset Documentation, Supply Chain, and Licensing Challenges on Hugging Face (arXiv:2502.04484)](https://arxiv.org/html/2502.04484v2)
- [License Distribution on Hugging Face (RedMonk, May 2026)](https://redmonk.com/sogrady/2026/05/12/hugging-face-licensing/)
- [Hugging Face Hub — Licenses documentation](https://huggingface.co/docs/hub/en/repositories-licenses)
- [MCP registry server.json schema (2025-12-11)](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json)
- [server.json Format Specification](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md)
- [modelcontextprotocol/servers LICENSE](https://github.com/modelcontextprotocol/servers/blob/main/LICENSE)
- [Glama MCP server directory](https://glama.ai/mcp/servers)
- [n8n Sustainable Use License](https://docs.n8n.io/sustainable-use-license/)
- [Announcing the new Sustainable Use License (n8n blog)](https://blog.n8n.io/announcing-new-sustainable-use-license/)
- [Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)
- [Dify open-source license policy](https://docs.dify.ai/en/policies/open-source)
- [OpenAI Service Terms](https://openai.com/policies/service-terms/)
- [AI Agent Marketplace: Legal Risks for Custom GPTs and AI Agents](https://techandmedialaw.com/ai-agent-marketplace-legal/)
