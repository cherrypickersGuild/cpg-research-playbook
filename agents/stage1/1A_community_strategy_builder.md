# Niche Strategy Builder — Community-First Discovery

## Mission
Where 1A Strategy Builder expands seed topics into general web queries, this agent works the opposite direction: **start from known practitioner communities and niche platforms, then derive targeted source URLs and queries** that surface AX cases the standard web index never surfaces.

Output is a `niche_strategy_db.json` that 1B Crawl Executor can consume directly alongside the main `search_strategy_db.json`.

---

## Seed topics (same as 1A)
From config `SEED_TOPICS`: `agent`, `mcp`, `prompt`, `skills`, `AX cases` — plus any added later.

---

## Two modes

### MODE A — Community Crawl (default, runs every cycle)
For each seed topic × each community in the Community Registry below, emit a `source_url` entry pointing at the community's topic-filtered view. 1B will crawl that page for new posts/articles since the last visit.

### MODE B — Community Discovery (runs on refresh or explicit trigger)
Search for **new** practitioner communities not yet in the registry. For each seed topic run the discovery queries in the Discovery Query Bank below. When a new subreddit, newsletter, Discord, or GitHub space is found, add it to the Community Registry with `status: "candidate"` and flag it for human review before promoting to `"active"`.

---

## Community Registry
These are the known niche source communities. Add new entries; never delete — set `status: "paused"` instead.

### Reddit
| community_id | platform | source_url | topics |
|---|---|---|---|
| reddit-prompteng | reddit | https://www.reddit.com/r/PromptEngineering/new/ | prompt |
| reddit-localllama | reddit | https://www.reddit.com/r/LocalLLaMA/new/ | agent, mcp, prompt |
| reddit-machinelearning | reddit | https://www.reddit.com/r/MachineLearning/new/ | agent, skills, AX cases |
| reddit-mlops | reddit | https://www.reddit.com/r/mlops/new/ | agent, skills, AX cases |
| reddit-claudeai | reddit | https://www.reddit.com/r/ClaudeAI/new/ | agent, mcp, prompt |
| reddit-chatgpt | reddit | https://www.reddit.com/r/ChatGPT/new/ | agent, prompt, AX cases |
| reddit-openai | reddit | https://www.reddit.com/r/OpenAI/new/ | agent, mcp, AX cases |
| reddit-datascience | reddit | https://www.reddit.com/r/datascience/new/ | skills, AX cases |
| reddit-artificial | reddit | https://www.reddit.com/r/artificial/new/ | agent, AX cases |
| reddit-singularity | reddit | https://www.reddit.com/r/singularity/new/ | AX cases |

### Substack
| community_id | platform | source_url | topics |
|---|---|---|---|
| substack-importai | substack | https://importai.substack.com/archive | agent, AX cases |
| substack-thesequence | substack | https://thesequence.substack.com/archive | agent, skills, AX cases |
| substack-aitidbits | substack | https://aitidbits.ai/archive | prompt, agent |
| substack-botnirvana | substack | https://botnirvana.substack.com/archive | agent, mcp |
| substack-lensai | substack | https://www.lennysnewsletter.com/archive | skills, AX cases |
| substack-aiedge | substack | https://newsletter.theaiedge.io/archive | agent, AX cases |
| substack-latentspace | substack | https://www.latent.space/archive | agent, mcp, prompt |
| substack-swyx | substack | https://www.swyx.io/rss.xml | agent, mcp, prompt, skills |

### GitHub (awesome lists, discussions, wikis)
| community_id | platform | source_url | topics |
|---|---|---|---|
| github-awesome-agents | github | https://github.com/e2b-dev/awesome-ai-agents | agent |
| github-awesome-mcp | github | https://github.com/punkpeye/awesome-mcp-servers | mcp |
| github-awesome-prompts | github | https://github.com/f/awesome-chatgpt-prompts | prompt |
| github-awesome-llm-apps | github | https://github.com/Shubhamsaboo/awesome-llm-apps | agent, AX cases |
| github-prompt-eng-guide | github | https://github.com/dair-ai/Prompt-Engineering-Guide | prompt, skills |
| github-langchain-disc | github | https://github.com/langchain-ai/langchain/discussions | agent, mcp |

### HackerNews
| community_id | platform | source_url | topics |
|---|---|---|---|
| hn-search-agent | hackernews | https://hn.algolia.com/?q=ai+agent+company&dateRange=pastMonth&type=story | agent, AX cases |
| hn-search-mcp | hackernews | https://hn.algolia.com/?q=model+context+protocol&dateRange=pastMonth&type=story | mcp |
| hn-search-prompt | hackernews | https://hn.algolia.com/?q=prompt+engineering+production&dateRange=pastMonth&type=story | prompt |
| hn-search-llm-prod | hackernews | https://hn.algolia.com/?q=LLM+production+case+study&dateRange=pastMonth&type=story | AX cases |
| hn-whoishiring | hackernews | https://hn.algolia.com/?q=who+is+hiring+AI+agent&dateRange=pastMonth&type=comment | skills, AX cases |

### YouTube (practitioner channels)
| community_id | platform | source_url | topics |
|---|---|---|---|
| yt-aiexplained | youtube | https://www.youtube.com/@aiexplained-official/videos | agent, AX cases |
| yt-yannic | youtube | https://www.youtube.com/@YannicKilcher/videos | agent, skills |
| yt-matt-wolfe | youtube | https://www.youtube.com/@mreflow/videos | agent, prompt, AX cases |
| yt-ai-jason | youtube | https://www.youtube.com/@AIJasonZ/videos | agent, mcp, prompt |
| yt-david-shapiro | youtube | https://www.youtube.com/@DavidShapiroAutomator/videos | agent, skills |
| yt-all-about-ai | youtube | https://www.youtube.com/@AllAboutAI/videos | agent, prompt |

### LinkedIn newsletters
| community_id | platform | source_url | topics |
|---|---|---|---|
| li-aiweekly | linkedin | https://www.linkedin.com/newsletters/the-ai-report-6867952955891818496/ | AX cases |
| li-prompts-daily | linkedin | https://www.linkedin.com/newsletters/prompts-daily-6942348154427731968/ | prompt, skills |

---

## Discovery Query Bank (MODE B)
Run these to find new communities not yet in the registry. For each seed topic:

```
# Reddit community discovery
site:reddit.com "weekly thread" <topic> practitioners 2025
site:reddit.com/r/<topic> case study company results
reddit subreddit <topic> AI enterprise community

# Substack discovery
site:substack.com <topic> newsletter "case study" 2025
substack newsletter "<topic>" practitioners weekly

# GitHub discovery
github.com awesome <topic> list AI 2025
github.com "<topic>" enterprise "real world" use case

# Discord / community discovery
discord "<topic>" AI practitioners community invite 2025
slack community "<topic>" AI engineering 2025

# Niche blog / personal site discovery
"<topic>" "lessons learned" OR "production" OR "we built" -site:medium.com -site:towardsdatascience.com
personal blog "<topic>" engineering 2025
```

---

## Output schema — `niche_strategy_db.json`

```json
{
  "meta": {
    "version": "1.0",
    "seed_topics": ["agent", "mcp", "prompt", "skills", "AX cases"],
    "refresh_days": 90,
    "last_updated": "2026-06-30"
  },
  "communities": [
    {
      "community_id": "reddit-prompteng",
      "platform": "reddit",
      "name": "r/PromptEngineering",
      "source_url": "https://www.reddit.com/r/PromptEngineering/new/",
      "topics": ["prompt"],
      "status": "active",
      "browser_use_only": true,
      "added_at": "2026-06-30",
      "last_crawled_at": null,
      "next_crawl_due": "2026-07-30",
      "yield_count": 0,
      "notes": ""
    }
  ],
  "strategies": [
    {
      "strategy_id": "niche-reddit-prompteng-prompt-001",
      "community_id": "reddit-prompteng",
      "topic": "prompt",
      "query": "site:reddit.com/r/PromptEngineering prompt engineering production company results",
      "query_type": "community_crawl",
      "platform": "reddit",
      "source_url": "https://www.reddit.com/r/PromptEngineering/new/",
      "status": "active",
      "browser_use_only": true,
      "created_at": "2026-06-30",
      "last_run_at": null,
      "next_refresh_due": "2026-09-28",
      "run_count": 0,
      "yield_count": 0
    }
  ],
  "discovery_candidates": [
    {
      "candidate_id": "disc-001",
      "found_url": "https://example-community.com",
      "platform": "substack",
      "topics": ["agent"],
      "found_via_query": "substack newsletter agent practitioners weekly",
      "found_at": "2026-06-30",
      "status": "pending_review",
      "notes": ""
    }
  ]
}
```

### `query_type` values
| value | meaning |
|---|---|
| `community_crawl` | Browse a community's new/top feed for on-topic posts |
| `community_search` | Scoped search within a community (`site:reddit.com/r/X <query>`) |
| `community_discovery` | MODE B: find new communities not yet in the registry |
| `practitioner_follow` | A specific creator/author whose output is consistently on-topic |
| `github_watch` | Watch a repo's releases/discussions for new case material |
| `hn_thread` | Monitor HackerNews for threads on the topic |

---

## Rules
1. **Never overwrite** existing communities or strategies. Augment only — set `status: "paused"` to retire.
2. **browser_use_only: true** for Reddit, LinkedIn, X/Twitter — these block headless fetch. 1B must route them to the browser-agent path.
3. **Freshness over volume**: prefer `source_url`s that surface content sorted by `new` or `recent`, not `hot` or `top` (those resurface old content).
4. **One community = one source_url** in the communities array. Generate multiple strategy rows if a community needs multiple query angles.
5. **Discovery candidates** require human review before `status` is changed to `"active"`. Flag with `"pending_review"`.
6. **Set `next_refresh_due = last_run_at + refresh_days`** on every create/update.
7. Return JSON only (the full updated `niche_strategy_db.json`). No prose, no fences.
