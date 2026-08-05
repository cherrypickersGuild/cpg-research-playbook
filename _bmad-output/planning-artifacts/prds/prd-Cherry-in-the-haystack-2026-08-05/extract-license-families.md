# Extract — Software license families, relicensing events, and classifier limits (Aug 2026)

Companion to `extract-license-landscape.md`. This one is about **which licenses permit what**,
and why an identifier alone cannot decide commercial usability. Received 2026-08-05.

---

## 1. OSI-approved families: what they cost commercially

**Permissive (MIT, BSD-2/3, Apache-2.0).** Unrestricted commercial use, modification,
redistribution, SaaS hosting, proprietary derivation; obligation is attribution/notice
retention. Apache-2.0 adds an express patent grant (§3) with defensive termination and a
NOTICE-file requirement (§4d). The only families with essentially zero downstream conditions.
**→ Auto-publishable.**

**Weak copyleft (MPL-2.0, LGPL-2.1/3.0).** Commercial use and proprietary combination fine;
copyleft scoped. MPL-2.0 is *file-level*: modified MPL files stay MPL, the rest does not. LGPL
requires users be able to relink a modified library — trivial with dynamic linking, painful for
static linking and locked-down binaries/containers. **No network trigger**, so SaaS use creates
no disclosure duty. **→ Publishable with a caveat flag.**

**Strong copyleft (GPL-2.0/3.0).** Distributing a derivative obliges releasing complete
corresponding source under the same license. **Pure internal use and unmodified SaaS operation
do not trigger distribution.** GPL-3.0 adds anti-Tivoization (§6) and patent retaliation.
**→ Risky to redistribute, safe to run.**

**AGPL-3.0.** §13 "Remote Network Interaction": modify the program and let users interact with
it *over a network* → you must offer those users the Corresponding Source. Closes the SaaS
loophole. Enterprise bans are usually broader than the license requires (unmodified network use
is arguably fine; contagion is limited to the derivative work), but policies are categorical
anyway. Google's public policy is canonical: *"Code licensed under the GNU Affero General Public
License (AGPL) MUST NOT be used at Google."* **→ Exclude-by-default, because the consumer's
policy — not the license text — governs.**

## 2. Source-available / non-OSI

- **BUSL-1.1** (MariaDB, 2017) is a *template*, not a license. Four parameters — Licensor,
  Licensed Work, **Additional Use Grant** (arbitrary carve-out), **Change Date** (max 4 years),
  after which the version falls back to a GPL-compatible **Change License**. Two BUSL projects
  can have opposite commercial terms. **A classifier reading only `BUSL-1.1` learns nothing
  actionable** — it must parse the Additional Use Grant and compute per-version change dates.
- **SSPL-1.0** (MongoDB, 16 Oct 2018): AGPL derivative; offering the program *as a service*
  requires releasing the entire service-management stack under SSPL. OSI-rejected; a poison pill
  for hosting.
- **Elastic License 2.0**: three limits — no hosted/managed service, no circumventing license
  keys, no removing notices. Internal commercial use permitted.
- **FSL-1.1-MIT / FSL-1.1-ALv2** (Sentry, Nov 2023): BUSL with variables removed — one fixed
  "Competing Use" restriction, fixed **2-year** conversion, future license MIT or Apache-2.0 only.
- **Fair Source (fair.io)** (Sentry, 2024): publicly readable + minimal business-protecting
  restrictions + **Delayed Open Source Publication**. Qualifying today: FSL, **Fair Core License
  (FCL)**, BUSL.
- **PolyForm** (Noncommercial, Small Business, Free Trial, Perimeter, Shield, Strict) and
  **Commons Clause** (a rider stripping the right to "Sell", applied atop an OSI license — the
  composite is not open source).

**SPDX status (list v3.28.0, released 2026-02-20):** `BUSL-1.1`, `SSPL-1.0`, `Elastic-2.0`,
`FSL-1.1-MIT`, `FSL-1.1-ALv2`, `PolyForm-Noncommercial-1.0.0`, `PolyForm-Small-Business-1.0.0`
all present, all flagged **not OSI-approved**. **Not on the list:** Commons Clause (submission
open; treat as `LicenseRef-`), FCL, RSALv2, n8n Sustainable Use License, and **every AI model
license** (Llama, Gemma, OpenRAIL). *Caveat: Commons-Clause absence is from a single list read;
verify before hard-coding.*

## 3. Relicensing events, 2023 → 2026

| Date | Event |
|---|---|
| Aug 2023 | HashiCorp → BUSL-1.1 (from MPL-2.0); OpenTF manifesto → **OpenTofu**, accepted by Linux Foundation 20 Sep 2023 |
| Mar 2024 | Redis → RSALv2 + SSPLv1; **Valkey** fork (LF; AWS/Google/Oracle/Alibaba) |
| Aug 2024 | Elastic adds **AGPLv3** as a third option (effective 8.16) — a partial return |
| 18 Nov 2024 | Cockroach Labs retires CockroachDB Core; single license, free under **$10M** annual revenue |
| Feb 2025 | IBM closes the **$6.4B** HashiCorp acquisition; Terraform stays BUSL-1.1 |
| 1 May 2025 | **Redis 8.0** ships tri-licensed RSALv2 / SSPLv1 / **AGPLv3** — the clearest reversal |
| Feb–Oct 2025 | **MinIO** strips the admin Web UI from Community Edition (26 Feb 2025); last community release 15 Oct 2025 |
| 30 Sep 2025 | **Liquibase 5.0** Community: Apache-2.0 → **FSL** (2-year reversion); broke downstream assumptions (Keycloak #43391) |
| Dec 2025 | Anthropic donates **MCP** to the Agentic AI Foundation under the Linux Foundation — the governance anchor for MCP-server licensing |
| 3 Dec 2025 → 25 Apr 2026 | MinIO declares maintenance mode; repo archived 25 Apr 2026 (license unchanged; *maintenance* ended, not openness) |
| 2 Apr 2026 | **Gemma 4** ships under **Apache-2.0** — first Gemmaverse release on an OSI license |

**No confirmed 2025–2026 relicensing of a major MCP-server or agent-framework project to
BUSL/SSPL/ELv2.** AI-tooling restrictions that exist are mostly *modified-permissive*: **Dify**
ships "Apache-2.0 plus two conditions" (no multi-tenant operation without written authorization;
no logo/copyright removal) — **an Apache-2.0 SPDX tag that is factually wrong**. **n8n** uses the
non-SPDX Sustainable Use License ("internal business purposes" only; consulting/support allowed,
hosting-for-fee prohibited). Flowise / Langflow / Qdrant / Supabase remain genuinely permissive.
RedMonk (Mar 2026): source-available licenses remain *statistically* negligible but
**strategically concentrated in high-value infra**.

OSI posture: OSAID **1.0** shipped 28 Oct 2024, approved by the 10-person board rather than the
membership; the unresolved fight is that it requires "data information," not training data. A
**1.1/2.0 update is targeted for Q4 2026**; OSI launched a two-year Open Source AI fellowship
(June 2026) explicitly aimed at open-washing. Bradley Kuhn (SFC) and multiple researchers remain
publicly opposed.

## 4. AI "community" licenses — none OSI-approved

- **Llama 2/3/4 Community License**: free commercial use *until* >700M MAU in the preceding
  calendar month, then a license must be requested from Meta at its sole discretion; mandatory
  "Built with Llama" attribution and `Llama-` name prefix for derivatives; binding AUP; Llama 3
  forbids using outputs to improve non-Llama models. **Llama 4 additionally excludes
  EU-domiciled individuals/companies from multimodal models.**
- **Gemma Terms of Use** (Gemma 1–3): Google reserves the right to *"restrict (remotely or
  otherwise) usage"* violating its Prohibited Use Policy; restrictions propagate to derivatives
  including models trained on Gemma synthetic data. Superseded for Gemma 4 (Apache-2.0), **not
  retroactively**.
- **Mistral**: split estate — many weights Apache-2.0, but the **Mistral AI Non-Production
  License (MNPL-0.1)** limits use to non-production (research, testing, QA, demo) and forbids
  supplying the model in commercial activity, paid or free, including SaaS; a separate Mistral
  Research License covers other releases. **Per-model check mandatory.**
- **Stability AI Community License**: commercial use free only under **$1M** annual revenue (any
  source); auto-terminates above that.
- **Cohere** research weights: **CC-BY-NC** + acceptable-use addendum — non-commercial, full stop.
- **Falcon (TII)**: 7B/40B → Apache-2.0 (2023); Falcon-180B uses a TII license requiring separate
  consent for hosted access.
- **Qwen**: mixed — much of the family Apache-2.0, but larger variants (e.g. Qwen2.5-VL-72B)
  carry a bespoke license with its own thresholds.
- **DeepSeek**: MIT on the headline reasoning models — genuinely permissive.
- **NVIDIA Open Model License**: permits commercial use and derivatives, NVIDIA claims no output
  ownership — but carries NVIDIA-defined guardrail conditions; not OSI-approved.
- **OpenRAIL / RAIL**: otherwise-permissive terms plus **behavioral use restrictions** in an
  attachment that must flow down to all derivatives and services. Use-field restrictions are per
  se non-open-source.

**Rule for the engine: model licenses are per-artifact, versioned, and frequently mislabeled on
Hugging Face. Treat the repo's `license:` tag as a hint, never as evidence.**

## 5. Dual licensing and CLAs — the classifier's blind spot

MySQL (GPL-2.0 + Oracle commercial), Qt (LGPL-3/GPL + commercial), Neo4j (GPLv3/AGPLv3 core +
commercial), Sidekiq (LGPL-3.0 + `COMM-LICENSE.txt`) all sell a proprietary alternative to the
same code — possible only because the vendor holds all rights via **copyright assignment or a
CLA/CAA**. That makes the public license a *floor*, not a ceiling.

**What a classifier CAN infer from `LICENSE: GPL-3.0`:** the terms on which you may use that
code, today, unilaterally. That grant is irrevocable for released versions.

**What it CANNOT infer:**

- (a) whether a paid alternative exists that most enterprises will be told to buy;
- (b) whether the *next* release keeps that license — a CLA is a standing relicensing
  capability, and Liquibase, Redis, HashiCorp and Cockroach all exercised it;
- (c) whether the repo is dual-licensed at all — the second license usually lives in a separate
  file, a website, or nowhere public;
- (d) whether enterprise features under `/ee` or `/enterprise` carry a different license than the
  repo root (Flowise, Grafana, GitLab pattern);
- (e) whether a `LICENSE` file is actually the license it claims (Dify's "Apache-2.0").

Minimum viable scanning: multi-file (`LICENSE*`, `COMM-LICENSE*`, `licenses/`, per-directory
files, `SECURITY`/`NOTICE`, README license sections) plus SPDX-expression parsing of `OR`/`AND`
compound tags. Where a dual license is detected, the correct output is *"publishable under X,
commercial alternative exists"* — **not a boolean**.

## 6. Recommended classifier policy (candidate FR material)

| Bucket | Licenses | Engine action |
|---|---|---|
| Allow automatically | MIT, BSD-2/3, Apache-2.0, ISC, Zlib, Unlicense, CC0 | publish |
| Allow with advisory | MPL-2.0, LGPL-2.1/3.0 | publish + caveat flag |
| Quarantine | GPL-2.0/3.0 | publish only in non-redistribution mode |
| Hard-exclude | AGPL-3.0, SSPL-1.0, all non-SPDX / `LicenseRef-` | do not publish |
| **Human review required** | BUSL (Additional Use Grant), FSL (change date), any revenue/MAU threshold, any behavioral-use attachment | queue for a person |

**Store the license as an SPDX expression *plus* the raw text hash**, because the identifier
alone provably under-determines commercial usability.

## Sources

- [Google AGPL policy (quotes §13)](https://opensource.google/documentation/reference/using/agpl-policy)
- [SPDX License List v3.28.0 (2026-02-20)](https://spdx.org/licenses/) · [FSL-1.1-MIT](https://spdx.org/licenses/FSL-1.1-MIT.html) · [FSL-1.1-ALv2](https://spdx.org/licenses/FSL-1.1-ALv2.html) · [Commons-Clause request #902](https://github.com/spdx/license-list-XML/issues/902)
- [Fair Source — definition](https://fair.io/about/) · [qualifying licenses](https://fair.io/licenses/)
- [Sentry: Introducing the Functional Source License](https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding/) · [fsl.software](https://fsl.software/)
- [Wikipedia: Business Source License](https://en.wikipedia.org/wiki/Business_Source_License) · [Server Side Public License](https://en.wikipedia.org/wiki/Server_Side_Public_License)
- [HashiCorp licence change (Aug 2023)](https://discuss.hashicorp.com/t/hashicorp-projects-changing-license-to-business-source-license-v1-1/57106) · [OpenTofu](https://en.wikipedia.org/wiki/OpenTofu)
- [Redis under AGPLv3 (May 2025)](https://redis.io/blog/agplv3/) · [Redis licenses](https://redis.io/legal/licenses/)
- [Liquibase → FSL](https://www.liquibase.com/blog/liquibase-community-for-the-future-fsl) · [Liquibase FSL page](https://www.liquibase.com/liquibase-functional-source-license) · [Liquibase 5.0 announcement](https://www.businesswire.com/news/home/20250930639100/en/Liquibase-Unveils-Liquibase-Secure-and-Liquibase-5.0-A-New-Era-for-Mission-Critical-Database-Change) · [Keycloak #43391](https://github.com/keycloak/keycloak/issues/43391)
- [Cockroach licensing FAQs](https://www.cockroachlabs.com/docs/stable/licensing-faqs) · [SD Times: CockroachDB retires Core](https://sdtimes.com/os/cockroachdb-retires-self-hosted-core-offering-makes-enterprise-version-free-for-companies-under-10m-in-annual-revenue/)
- [Akka: why we are changing the license](https://akka.io/blog/why-we-are-changing-the-license-for-akka) · [Akka BSL FAQ](https://akka.io/bsl-license-faq)
- [MinIO removes admin UI (Blocks & Files)](https://blocksandfiles.com/2025/06/19/minio-removes-management-features-from-basic-community-edition-object-storage-code/) · [minio #21714 Maintenance Mode](https://github.com/minio/minio/issues/21714) · [MinIO archived — 2026 status](https://stormdevelopments.ca/blog/minio-s-community-edition-is-archived-what-still-runs-in-2026/)
- [RedMonk: The State of Open Source Licensing in 2026](https://redmonk.com/sogrady/2026/03/25/open-source-licensing-2026/)
- [Goodwin: Moving Away From Open Source](https://www.goodwinlaw.com/en/insights/publications/2024/09/insights-practices-moving-away-from-open-source-trends-in-licensing)
- [n8n Sustainable Use License](https://docs.n8n.io/sustainable-use-license/) · [n8n LICENSE.md](https://github.com/n8n-io/n8n/blob/master/LICENSE.md)
- [Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE) · [Dify license problem #17109](https://github.com/langgenius/dify/issues/17109)
- [Flowise LICENSE.md](https://github.com/FlowiseAI/Flowise/blob/main/LICENSE.md) · [Flowise #5164](https://github.com/FlowiseAI/Flowise/issues/5164)
- [AAIF: MCP is growing up (LF donation, Dec 2025)](https://aaif.io/blog/mcp-is-growing-up)
- [OSI: Open Source AI](https://opensource.org/ai) · [LWN on OSAID](https://lwn.net/Articles/995159/) · [The New Stack: The Case Against OSAID](https://thenewstack.io/the-case-against-osis-open-source-ai-definition/) · [OSI Open Source AI Fellowship (June 2026)](https://www.opensourceforu.com/2026/06/open-source-initiative-launches-open-source-ai-fellowship/)
- [TechCrunch: 'Open' AI model licenses often carry concerning restrictions](https://techcrunch.com/2025/03/14/open-ai-model-licenses-often-carry-concerning-restrictions/) · [Tech Policy Press: 'Open-Washing' Is Everywhere in AI](https://www.techpolicy.press/open-washing-is-everywhere-in-ai-four-criteria-cut-through-it/)
- [Llama 4 Community License](https://www.llama.com/llama4/license/) · [llama-models LICENSE](https://github.com/meta-llama/llama-models/blob/main/models/llama4/LICENSE)
- [Gemma 4 under Apache 2.0 (Google OSS Blog)](https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html) · [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Mistral MNPL-0.1](https://mistral.ai/licenses/MNPL-0.1.md) · [Mistral MNPL announcement](https://mistral.ai/news/mistral-ai-non-production-license-mnpl/)
- [Stability AI License](https://stability.ai/license) · [Stability Community License update](https://stability.ai/news-updates/license-update)
- [NVIDIA Open Model License (PDF)](https://developer.download.nvidia.com/licenses/nvidia-open-model-license-agreement-june-2024.pdf) · [NVIDIA OML risk analysis (Dec 2025)](https://shujisado.org/2025/12/19/nvidia-open-model-license-a-corporate-risk-analysis/)
- [tiiuae/falcon-40b](https://huggingface.co/tiiuae/falcon-40b) · [Wikipedia: Qwen](https://en.wikipedia.org/wiki/Qwen)
- [Sidekiq LICENSE.txt](https://github.com/sidekiq/sidekiq/blob/main/LICENSE.txt) · [Sidekiq COMM-LICENSE.txt](https://github.com/sidekiq/sidekiq/blob/main/COMM-LICENSE.txt) · [Sidekiq Commercial FAQ](https://github.com/sidekiq/sidekiq/wiki/Commercial-FAQ)
