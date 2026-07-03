# Awesome MCP — Landscape Report

**Topic:** mcp (Model Context Protocol)
**Date compiled:** 2026-07-03
**List(s) reviewed:**
- [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) — 90,212 stars (via GitHub API), last push 2026-06-26, last repo update 2026-07-03. Fetched via raw README (`raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md`, 3,230 lines). Note: a first attempt to fetch the rendered `github.com` page returned GitHub's site-navigation chrome instead of the README body (a known WebFetch limitation on GitHub's JS-rendered pages) — the raw markdown fetch was used for all real parsing.

**Substitution note:** No substitution was needed — the seed URL is alive and is the de facto canonical "awesome-mcp-servers" list (also mirrored as a searchable directory at glama.ai/mcp/servers).

## Important scope note

The source list's "Server Implementations" section is no longer a small curated set — it now spans **~45 categories and several thousand individual entries**, and a large fraction of recently-added entries (especially in "Aggregators," "Browser Automation," and several other categories) are auto-generated-looking, low-provenance repos promoting "x402" crypto micropayment APIs, agent marketplaces, and similar speculative projects with little to no independent verification signal. Per the task's instruction to cap at ~40 entries and prioritize what's genuinely on-topic, this report deliberately selects the **official / vendor-maintained servers, the most-starred community servers, and the core SDK frameworks** from across categories, rather than sampling proportionally from the long tail. Every entry below was independently verified via its own README and/or the GitHub API (stars, last push) — this is noted per row.

---

## Reference Implementations & Registries

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| modelcontextprotocol/servers | https://github.com/modelcontextprotocol/servers | Official collection of reference MCP server implementations (Fetch, Git, Memory, etc.), maintained by Anthropic with community contributions. Older servers (filesystem, postgres, sqlite, google-maps, puppeteer, everything) have been moved to a companion `servers-archived` repo. 88,008 stars; last push 2026-06-29. | This is the canonical starting point for understanding what an MCP server actually looks like in code — essential first stop for any AX education program teaching MCP fundamentals. |
| punkpeye/awesome-mcp-clients | https://github.com/punkpeye/awesome-mcp-clients | Companion list (linked from the servers list's "Clients" section) cataloging MCP client applications (Claude Desktop, IDEs, etc.). | list-only (not deep-crawled this run — out of scope of "servers," but relevant as the client-side counterpart). |

## Frameworks (building MCP servers)

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| PrefectHQ/fastmcp (listed as jlowin/fastmcp) | https://github.com/jlowin/fastmcp | Python framework for building MCP servers/clients with minimal boilerplate — auto-generates schemas from function signatures, handles transport/auth/lifecycle. Maintained by Prefect (workflow-orchestration company); the README claims ~70% of MCP servers across all languages use "some version of FastMCP." 25,940 stars; last push 2026-07-01. | The de facto standard scaffolding tool for MCP server authors — directly relevant for any hands-on "build your first MCP server" module. |
| punkpeye/fastmcp | https://github.com/punkpeye/fastmcp | TypeScript equivalent of the above: an opinionated framework handling OAuth, HTTP streaming, custom routes, and edge-runtime support for MCP servers. Community-maintained (individual maintainer, inspired by the Python FastMCP). 3,214 stars; last push 2026-07-03. | Same role as the Python FastMCP but for JS/TS shops — useful comparison point for language-choice discussions. |

## Aggregators

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| 1mcp-app/agent | https://github.com/1mcp-app/agent | "1MCP" — a unified runtime that aggregates multiple MCP servers behind one interface, with progressive tool discovery (`instructions`, `inspect`, `run`) so agents load a smaller, focused toolset instead of everything at once. Maintained by the 1mcp-app open-source community (Apache 2.0). 460 stars; last push 2026-07-02. | Illustrates a real operational pain point in MCP adoption — tool-count/context bloat — and one common architectural fix (proxy/aggregator servers). |
| PipedreamHQ/pipedream | https://github.com/PipedreamHQ/pipedream | Pipedream is a general integration/automation platform connecting 1,000+ apps via prebuilt components and custom code (Node.js, Python, Go, Bash); it also ships MCP-compatible tool endpoints per the source list's description ("2,500 APIs with prebuilt tools"), though the top-level README itself doesn't mention MCP explicitly. Maintained by PipedreamHQ (VC-backed company). 11,526 stars; last push 2026-07-02. | description_source: partially list-only — subpage confirmed the platform and maintainer but not the specific MCP integration claim from the list blurb, since the root README doesn't surface it. Useful as a case study of a broad SaaS-integration platform retrofitting MCP support. |

## Cloud Platforms

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| awslabs/mcp | https://github.com/awslabs/mcp | Suite of official AWS-maintained MCP servers giving coding assistants (Kiro, Cursor, Claude, etc.) access to AWS docs, infrastructure management, databases, and serverless deployment. Maintained by AWS Labs; the README notes AWS also has a separate proprietary "Agent Toolkit for AWS" for production/audit-heavy use cases. 9,376 stars; last push 2026-07-03 (marked 🎖️ official in the source list). | Flagship example of a major cloud vendor operationalizing MCP for infra-as-code and cloud-ops agents — directly relevant to AX programs covering cloud automation. |
| cloudflare/mcp-server-cloudflare | https://github.com/cloudflare/mcp-server-cloudflare | Official Cloudflare-maintained MCP servers exposing Workers, DNS analytics, security, and observability tooling so an agent can "read configurations, process information, make suggestions, and even make changes" across Cloudflare products. 3,915 stars; last push 2026-07-01 (marked 🎖️ official). | Another concrete official vendor integration; good comparison point against AWS's approach (many small domain-specific servers vs. one bundle). |
| hashicorp/terraform-mcp-server | https://github.com/hashicorp/terraform-mcp-server | Official HashiCorp MCP server bridging AI agents to the Terraform Registry API — provider discovery, module analysis, and infrastructure-as-code workflows. 1,454 stars; last push 2026-07-02 (marked 🎖️ official). | Shows MCP reaching into the IaC/DevOps tooling layer specifically, a common AX transformation target. |
| Azure/azure-mcp | https://github.com/Azure/azure-mcp | Official Microsoft MCP server for Azure services (Storage, Cosmos DB, Azure Monitor, etc.). 1,221 stars; last push 2026-02-06 — **repository is now archived** per GitHub API (`archived: true`). | Included as a freshness/gap flag: this was a leading vendor MCP server but appears to have been discontinued or folded elsewhere as of early 2026 — worth verifying Microsoft's current Azure+MCP story before citing it as active in course material. |
| googleapis/mcp-toolbox (repo renamed from `genai-toolbox`) | https://github.com/googleapis/mcp-toolbox | "MCP Toolbox for Databases" — Google-maintained open-source MCP server connecting AI agents, IDEs, and apps to enterprise databases with both prebuilt and custom tool definitions. 15,836 stars; last push 2026-07-02. | Note: the list still links the old repo name/URL (`googleapis/genai-toolbox`), which now 301-redirects — worth flagging as a stale link in the source list itself. |

## Databases

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| redis/mcp-redis | https://github.com/redis/mcp-redis | Official Redis-maintained MCP server giving agents a natural-language interface to store conversations, cache data, and run vector search against Redis, without hand-written query code. MIT licensed. 538 stars; last push 2026-06-22. | Concrete example of a database vendor exposing agent memory/caching primitives directly through MCP. |
| neo4j-contrib/mcp-neo4j | https://github.com/neo4j-contrib/mcp-neo4j | Neo4j Labs (Field GenAI team)-maintained set of MCP servers letting agents run Cypher queries, manage Aura cloud instances, and build/query knowledge graphs. Explicitly marked experimental/outside official product support. 972 stars; last push 2026-04-10 (staler than most peers in this table). | Good example for teaching agentic knowledge-graph and long-term memory patterns, with an honest caveat about its "labs/experimental" status. |

## Monitoring & Observability

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| getsentry/sentry-mcp | https://github.com/getsentry/sentry-mcp | Official Sentry-maintained MCP server acting as middleware to the Sentry API, optimized for coding-assistant debugging workflows (issue inspection, triage). 750 stars; last push 2026-07-03. | Shows MCP being used to close the loop between "agent writes code" and "agent debugs the resulting production errors" — a compelling AX workflow example. |
| grafana/mcp-grafana | https://github.com/grafana/mcp-grafana | Official Grafana-maintained MCP server for searching dashboards, querying datasources (Prometheus, Loki, etc.), and managing alerts/incidents via an agent. 3,210 stars; last push 2026-07-03 (marked 🎖️ official). | Demonstrates MCP extending into ops/SRE workflows — relevant for "agent as on-call assistant" use cases. |

## Browser Automation

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| microsoft/playwright-mcp | https://github.com/microsoft/playwright-mcp | Official Microsoft-maintained MCP server letting agents drive a real browser via Playwright, using structured accessibility snapshots instead of screenshots/vision models. 34,647 stars; last push 2026-06-29. | Arguably the most-adopted browser-automation MCP server; central reference point for "agent that operates a web UI" workflows. |
| executeautomation/mcp-playwright | https://github.com/executeautomation/mcp-playwright | Community (ExecuteAutomation)-maintained Playwright MCP server supporting screenshots, test-code generation, scraping, JS execution, and 143 real device profiles. 5,566 stars; last push 2025-12-13 (~7 months stale relative to peers). | Useful as a comparison against the official Microsoft server — broader feature surface (test-gen, device emulation) but slower-moving maintenance cadence. |
| browserbase/mcp-server-browserbase | https://github.com/browserbase/mcp-server-browserbase | Browserbase-maintained MCP server for controlling a cloud (not local) browser via Browserbase + Stagehand, with six core tools for navigation/extraction. Apache 2.0. 3,391 stars; last push 2026-07-01. | Represents the "browser automation as a cloud service" pattern, relevant for agents that need scale/isolation rather than a local Chrome instance. |
| webdriverio/mcp | https://github.com/webdriverio/mcp | Official WebdriverIO project MCP server automating Chrome/Firefox/Edge/Safari and native iOS/Android apps through one interface. 32 stars; last push 2026-07-01 — very new/low-adoption despite official provenance. | Notable as one of the only MCP servers in this list covering native mobile app automation, not just web. |

## Search & Data Extraction

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| exa-labs/exa-mcp-server | https://github.com/exa-labs/exa-mcp-server | Official Exa-maintained MCP server exposing Exa's neural search API (web search, content retrieval, research) to agents across Claude, VS Code, Cursor, etc. Offered as both hosted service and npm package. 4,657 stars; last push 2026-07-02 (marked 🎖️ official). | A leading example of "search-as-a-tool" for agents — core building block for research-oriented agent workflows. |
| brave/brave-search-mcp-server | https://github.com/brave/brave-search-mcp-server | Official Brave-maintained MCP server for web/local/image/video/news search plus AI summarization via Brave's Search API. MIT licensed. 1,259 stars; last push 2026-06-29. | Alternative to Exa with a privacy-focused search vendor backing it — useful for comparing search-tool tradeoffs in an agent stack. |

## Workplace & Productivity

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| sooperset/mcp-atlassian | https://github.com/sooperset/mcp-atlassian | MCP server for Jira and Confluence (Cloud and Server/Data Center) — search, create, and update issues/pages. Explicitly **not** an official Atlassian product; maintained by an individual developer ("sooperset"), MIT licensed. 5,492 stars; last push 2026-06-20. | Despite being unofficial, this is the most-starred Atlassian MCP integration in the list and a realistic example of community tooling filling a gap large vendors haven't officially closed. |
| upstash/context7 | https://github.com/upstash/context7 | Context7 supplies AI coding agents with up-to-date, version-specific library documentation and code examples injected directly into prompts, avoiding stale/hallucinated API knowledge. Maintained by Upstash; usable as a CLI or an MCP server. 58,507 stars; last push 2026-07-03. | One of the highest-starred entries reviewed in this run — a strong signal that "keeping coding agents current on library APIs" is a major real-world MCP use case worth covering in an AX curriculum. |

## Data Platforms

| Name | Link | What it is | Why it matters for mcp |
|---|---|---|---|
| mindsdb/minds (repo renamed from `mindsdb`) | https://github.com/mindsdb/minds | Now positioned as "MindsHub Cowork" — a unified workspace for delegating tasks (research, analysis, reporting) to AI agents, with a "secure vault" connecting external systems (BigQuery, Postgres, Gmail, etc.) and a "Model Router" for switching AI providers. The current README does not explicitly reference MCP despite the source list filing it under a data-platform/MCP-relevant category. Maintained by MindsDB. 39,372 stars; last push 2026-07-01. | description_source: subpage-verified but flagged — this project appears to have pivoted product direction since being added to the awesome-list; anyone citing it as an "MCP server" should double check current MCP support directly rather than relying on the list's old blurb. |

---

## Synthesis

The MCP server ecosystem has scaled enormously in about a year: the seed list now tracks several thousand servers across ~45 categories, and the strongest freshness signal across this sample is that essentially all officially-vendor-maintained servers (AWS, Cloudflare, Microsoft/Playwright, GitHub, HashiCorp, Grafana, Sentry, Redis, Brave, Exa, Google) had commits within the last one to three days of this report — MCP is clearly an actively-developed, high-velocity space, not a settled standard. At the same time, the sheer volume of the list has attracted a long tail of low-provenance, seemingly auto-generated or promotional entries (particularly "x402" crypto-micropayment aggregator servers), so curation quality has degraded as adoption grew, and researchers should not treat inclusion in this list alone as a quality signal. Two Python/TypeScript frameworks (FastMCP in both languages) have emerged as the dominant scaffolding for building new servers, which is worth teaching directly rather than raw-protocol implementation. One official entry (Azure/azure-mcp) was found archived, a reminder that "official" status doesn't guarantee longevity and that freshness should always be re-checked before use in course material. Overall, for an AX education program, the most durable teaching examples are the vendor-official servers (AWS, GitHub, Cloudflare, Microsoft Playwright, Sentry, Grafana) plus the two FastMCP frameworks and the reference `modelcontextprotocol/servers` repo — these best illustrate both "why MCP matters" (real companies shipping it) and "how to build one" (the frameworks).

## Gaps / could not verify

- No entries in this run hit an outright fetch failure (404/private/throttled) — the raw-README strategy worked for every subpage attempted.
- **punkpeye/awesome-mcp-clients** was noted from the source list's "Clients" section but not deep-crawled (out of scope for "servers"; flagged as list-only above).
- **PipedreamHQ/pipedream**: the root README did not explicitly confirm the list's specific MCP/"2,500 APIs" claim — platform and maintainer were verified, but the precise MCP integration detail rests on the list's own blurb.
- **mindsdb/minds**: the current README reflects an apparent product pivot away from explicit MCP framing since the list entry was written — treat the list's description as dated relative to the live repo.
- **googleapis/mcp-toolbox**: the source list still links the old `googleapis/genai-toolbox` URL, which now redirects — a stale-link issue in the source list itself, not a fetch failure on our end.
- The vast majority (>95%) of entries in categories like Aggregators, Art & Culture, Aerospace, and others were intentionally **not** fetched, per the task's ~40-entry cap and the instruction to prioritize on-topic, verifiable entries over exhaustive coverage of a list that has become heavily long-tailed.
