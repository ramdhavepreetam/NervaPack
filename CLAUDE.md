# NervaPack — Claude Code Instructions

## Always use NervaPack MCP tools

**At the start of every session:**
1. Call `memory_start_session("<task name>")` to open a named session
2. Call `memory_recall("project context", budget_tokens=400)` to load prior decisions and facts
3. Call `query_codebase("<topic>")` before answering any question about how the code works

**During the session — call `memory_store` for:**
- Any decision made (`kind="decision"` with `rationale` and `alternatives_rejected`)
- Any fact discovered about system behaviour (`kind="fact"`)
- Any procedure or convention established (`kind="procedure"`)
- Any outcome from an action (`kind="outcome"`)

**At session end:**
- Call `memory_end_session("<one-paragraph summary of what was done>")`

**Never answer questions about this codebase from training data alone.**
Always call `query_codebase` first — it returns AST-precise, token-efficient context from the live graph.

## MCP servers available

| Server | Command | Purpose |
|--------|---------|---------|
| `nervapack` | `nervapack-mcp` | Code graph — `query_codebase`, `graph_status`, `list_entities` |
| `nervapack-memory` | `nervapack-memory-mcp` | Agent memory — 17 tools for storing and recalling decisions/facts |

## Project essentials

- **Version:** v0.7.4
- **DB:** `.nervapack/memory.db` (SQLite, auto-resolved from cwd)
- **Graph:** `.nervapack/graph.graphml` (reingest with `nervapack ingest .` when source changes)
- **Tests:** `python3 -m pytest tests/memory/ -q` — must stay green before any commit
- **Docs:** `python3 -m mkdocs build --strict` — must build clean before any commit
- **Publish:** `python3 -m build && python3 -m twine upload dist/*`
- **MCP Registry:** `io.github.ramdhavepreetam/nervapack` (published, active)

## Key architecture facts

- Two MCP servers ship in the same PyPI package: `nervapack-mcp` (code graph) and `nervapack-memory-mcp` (agent memory)
- Memory DB is SQLite + FTS5, bi-temporal (valid_from/valid_until), never hard-deletes by default
- Code graph is NetworkX DiGraph stored as GraphML + ChromaDB for vector search
- FastMCP tools that return lists must use `CallToolResult(content=[TextContent(type="text", text=json.dumps(the_list))])` — FastMCP serializes Python `list` returns as one TextContent per item, breaking single-item lists
- `_namespace_explicit` flag in `mcp_server.py` distinguishes intentional namespace switches from external test fixture resets
