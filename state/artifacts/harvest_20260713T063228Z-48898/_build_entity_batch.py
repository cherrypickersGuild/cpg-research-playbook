import json, io

base = "https://github.com/punkpeye/awesome-mcp-servers"
# (name, anchor, target_url, entity_type, desc, maintainer, stars, pushed, related)
rows = [
("serena", "#coding-agents", "https://github.com/oraios/serena", "server",
 "A powerful MCP toolkit for coding, providing semantic retrieval and editing capabilities - the IDE for your agent.", "oraios", 26379, "2026-07-12", ["agent"]),
("DesktopCommanderMCP", "#coding-agents", "https://github.com/wonderwhy-er/DesktopCommanderMCP", "server",
 "MCP server for Claude that gives it terminal control, file system search, and diff-based file editing capabilities.", "wonderwhy-er", 8059, "2026-07-12", ["agent"]),
("codemcp", "#coding-agents", "https://github.com/ezyang/codemcp", "server",
 "Coding-assistant MCP for Claude Desktop.", "ezyang", 1610, "2025-12-25", []),
("iterm-mcp", "#coding-agents", "https://github.com/ferrislucas/iterm-mcp", "server",
 "A Model Context Protocol server that executes commands in the current iTerm session - useful for REPL and CLI assistance.", "ferrislucas", 566, "2025-09-20", []),
("mcp-server-commands", "#coding-agents", "https://github.com/g0t4/mcp-server-commands", "server",
 "Model Context Protocol server to run shell commands (exposes a runProcess tool).", "g0t4", 229, "2026-06-15", []),
("mcp-shell-server", "#coding-agents", "https://github.com/tumf/mcp-shell-server", "server",
 "Secure MCP server for whitelisted shell command execution with stdin, argv pipelines, timeouts, and structured audit logging.", "tumf", 181, "2026-07-02", []),
("Agent-MCP", "#coding-agents", "https://github.com/rinadelph/Agent-MCP", "framework",
 "A framework for creating multi-agent systems that enables coordinated, efficient AI collaboration through the Model Context Protocol (MCP).", "rinadelph", 1266, "2026-03-28", ["agent"]),
("cli-mcp-server", "#coding-agents", "https://github.com/MladenSU/cli-mcp-server", "server",
 "Command-line interface for MCP clients with secure execution and customizable security policies.", "MladenSU", 173, "2025-07-04", []),
("CodeGraphContext", "#coding-agents", "https://github.com/CodeGraphContext/CodeGraphContext", "server",
 "An MCP server plus CLI tool that indexes local code into a graph database to provide structural code context to AI assistants.", "CodeGraphContext", 3915, "2026-07-04", []),
("vscode-mcp-server", "#coding-agents", "https://github.com/juehang/vscode-mcp-server", "server",
 "MCP server to expose VS Code editing features to an LLM for AI coding.", "juehang", 380, "2026-01-07", []),
("canvas-mcp", "#education", "https://github.com/admin978/canvas-mcp", "server",
 "Local-first Canvas LMS MCP server (stdio transport, ~125 lines of Python).", "admin978", 2, "2026-05-27", []),
("brightspace-mcp-server", "#education", "https://github.com/RohanMuppa/brightspace-mcp-server", "server",
 "MCP server for the Brightspace (D2L) LMS - check grades, due dates, assignments, announcements, rosters, syllabus and course content from any MCP client.", "RohanMuppa", 25, "2026-05-01", []),
("mcp-server-pronunciation", "#education", "https://github.com/JuhongPark/mcp-server-pronunciation", "server",
 "Local MCP voice coach with English pronunciation, grammar, and fluency feedback.", "JuhongPark", 3, "2026-05-24", []),
("imagesorcery-mcp", "#multimedia-process", "https://github.com/sunriseapps/imagesorcery-mcp", "server",
 "An MCP server providing tools for local image-processing operations.", "sunriseapps", 326, "2026-05-19", []),
("topaz-mcp", "#multimedia-process", "https://github.com/TopazLabs/topaz-mcp", "server",
 "Topaz Labs MCP server - AI image enhancement via the Model Context Protocol.", "Topaz Labs", 5, "2026-02-16", []),
("Pixelle-MCP", "#multimedia-process", "https://github.com/ATH-MaaS/Pixelle-MCP", "framework",
 "An open-source multimodal AIGC solution based on ComfyUI + MCP + LLM.", "ATH-MaaS", 1079, "2025-12-17", []),
("mcp-server-pexels", "#multimedia-process", "https://github.com/afshinator/mcp-server-pexels", "server",
 "MCP server for Pexels stock photos and videos.", "afshinator", 2, "2026-05-27", []),
("exif-mcp", "#multimedia-process", "https://github.com/stass/exif-mcp", "server",
 "MCP server to extract image metadata (EXIF, XMP, etc.).", "stass", 38, "2025-11-14", []),
("strava-mcp", "#sports", "https://github.com/r-huijts/strava-mcp", "server",
 "A Model Context Protocol (MCP) server that connects to the Strava API, providing tools to access Strava data through LLMs.", "r-huijts", 452, "2026-06-13", []),
("mlb-api-mcp", "#sports", "https://github.com/guillochon/mlb-api-mcp", "server",
 "A Model Context Protocol (MCP) server that provides comprehensive access to MLB statistics and baseball data through a FastMCP-based interface.", "guillochon", 55, "2026-06-19", []),
("balldontlie-mcp", "#sports", "https://github.com/mikechao/balldontlie-mcp", "server",
 "An MCP server that integrates the balldontlie API to provide information about players, teams and games for the NBA, NFL and MLB.", "mikechao", 25, "2026-03-30", []),
("whoop-mcp-server", "#sports", "https://github.com/rajdeepmondaldotcom/whoop-mcp-server", "server",
 "MCP server to ask your AI anything about your WHOOP data.", "rajdeepmondaldotcom", 1, "2026-06-12", []),
("firstcycling-mcp", "#sports", "https://github.com/r-huijts/firstcycling-mcp", "server",
 "A Model Context Protocol (MCP) server that provides professional cycling data from FirstCycling - cyclists, race results, and more.", "r-huijts", 19, "2025-08-26", []),
("mcp-unity", "#gaming", "https://github.com/CoderGamester/mcp-unity", "server",
 "Model Context Protocol plugin to connect with the Unity Editor - designed for Cursor, Claude Code, Codex, Windsurf and other IDEs.", "CoderGamester", 1827, "2026-07-04", []),
("godot-mcp", "#gaming", "https://github.com/Coding-Solo/godot-mcp", "server",
 "MCP server for interfacing with the Godot game engine - launch the editor, run projects, and capture debug output.", "Coding-Solo", 4676, "2026-04-16", []),
("Unity-MCP", "#gaming", "https://github.com/IvanMurzak/Unity-MCP", "server",
 "AI skills, MCP tools, and CLI for the Unity Engine, enabling a full AI develop-and-test loop with efficient token usage.", "IvanMurzak", 3518, "2026-07-12", []),
("chess-mcp", "#gaming", "https://github.com/pab1it0/chess-mcp", "server",
 "A Model Context Protocol server for Chess.com's Published Data API, exposing player data, game records, and other public information to AI assistants.", "pab1it0", 78, "2026-06-26", []),
("opgg-mcp", "#gaming", "https://github.com/opgginc/opgg-mcp", "server",
 "A Model Context Protocol implementation that provides AI agents with access to OP.GG game data for League of Legends, Teamfight Tactics, and Valorant.", "OP.GG", 94, "2026-05-23", []),
("bgg-mcp", "#gaming", "https://github.com/kkjdaniel/bgg-mcp", "server",
 "MCP server that provides access to BoardGameGeek and a variety of board-game-related data through the Model Context Protocol.", "kkjdaniel", 50, "2026-04-19", []),
("mcp-kodi", "#home-automation", "https://github.com/laszlopere/mcp-kodi", "server",
 "An MCP server for controlling Kodi over JSON-RPC.", "laszlopere", 1, "2026-06-19", []),
("fritzbox-mcp-server", "#home-automation", "https://github.com/kambriso/fritzbox-mcp-server", "server",
 "FRITZ!Box MCP server for LLM/AI integration - home automation from your AI agent.", "kambriso", 14, "2026-06-15", []),
("deep-research-mcp", "#research", "https://github.com/pminervini/deep-research-mcp", "server",
 "MCP server for OpenAI's Deep Research APIs, Gemini Deep Research Agent, Allen AI's DR-Tulu, and Hugging Face's Open Deep Research.", "pminervini", 91, "2026-06-10", []),
("legiscan-mcp", "#research", "https://github.com/sh-patterson/legiscan-mcp", "server",
 "MCP server for the LegiScan API - access legislative data from all 50 US states and Congress: search bills, get full text, track votes, look up legislators, and monitor changes.", "sh-patterson", 6, "2026-05-21", []),
("scholar-sidekick-mcp", "#research", "https://github.com/mlava/scholar-sidekick-mcp", "server",
 "MCP server that resolves any scholarly identifier (DOI, PMID, PMCID, ISBN, arXiv, ISSN, ADS, WHO IRIS) into 10,000+ CSL styles or nine export formats, single or batch.", "mlava", 5, "2026-07-11", []),
("modbus-mcp", "#embedded-system", "https://github.com/kukapay/modbus-mcp", "server",
 "An MCP server that standardizes and contextualizes industrial Modbus data.", "kukapay", 25, "2025-05-12", []),
("opcua-mcp", "#embedded-system", "https://github.com/kukapay/opcua-mcp", "server",
 "An MCP server that connects to OPC UA-enabled industrial systems.", "kukapay", 28, "2025-10-29", []),
("esp-mcp", "#embedded-system", "https://github.com/horw/esp-mcp", "server",
 "MCP server that centralizes ESP32-related commands to simplify getting started with LLM-driven interaction.", "horw", 154, "2025-12-27", []),
("patent-search-mcp-server", "#legal", "https://github.com/smythmyke/patent-search-mcp-server", "server",
 "MCP server for an AI patent-search generator - patent dossiers, prosecution history, citation graphs, and Google Patents search.", "smythmyke", 2, "2026-06-08", []),
("us-legal-mcp", "#legal", "https://github.com/JamesANZ/us-legal-mcp", "server",
 "An MCP server that provides comprehensive access to US legislation.", "JamesANZ", 34, "2026-04-20", []),
("vectara-mcp", "#RAG", "https://github.com/vectara/vectara-mcp", "server",
 "Open-source MCP server for Vectara.", "Vectara", 27, "2026-04-30", []),
]

assert len(rows) == 40, len(rows)
entities = []
patch = {}
for i, (name, anchor, turl, etype, desc, maint, stars, pushed, related) in enumerate(rows):
    eid = "ent-2026-%04d" % (3031 + i)
    surl = base + anchor
    entities.append({
        "entity_id": eid, "topic": "mcp", "entity_type": etype, "name": name,
        "source_url": surl, "target_url": turl, "description": desc,
        "description_source": "verified", "maintainer_or_vendor": maint,
        "freshness_signal": "last commit " + pushed, "github_stars": stars,
        "related_topics": related, "found_via": None,
    })
    patch.setdefault(surl, []).append(eid)

ledger_patch = [{"url": u, "entity_extracted": True, "entity_ids": ids} for u, ids in patch.items()]
out = {"entities": entities, "ledger_patch": ledger_patch}
s = json.dumps(out, ensure_ascii=False, indent=2)
io.open("state/_entity_batch_mcp_out.json", "w", encoding="utf-8").write(s)
assert len(patch) == 10, len(patch)
assert sum(len(v) for v in patch.values()) == 40
assert json.loads(s)
print("OK entities=%d ledger_rows=%d ids=%d" % (len(entities), len(ledger_patch), sum(len(v) for v in patch.values())))
