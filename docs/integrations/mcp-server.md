# MCP Server Integration

NervaPack ships two MCP servers. Use both together for the full picture: the knowledge-graph server answers structural questions about your code; the memory server recalls decisions and facts from previous sessions.

**MCP Registry:** `io.github.ramdhavepreetam/nervapack` — listed on the [official MCP Registry](https://registry.modelcontextprotocol.io).

Supported editors: **Claude Code**, **Cursor**, **Windsurf** — all use the same `.mcp.json` config file.

---

## Editor Setup

### Claude Code

Claude Code auto-discovers `.mcp.json` in the project root. No additional configuration needed.

```bash
pip install "nervapack[mcp]"
nervapack ingest .
```

Add `.mcp.json` to your project root (config shown below), then reload Claude Code.

### Cursor

Cursor reads `.mcp.json` from the project root identically to Claude Code.

```bash
pip install "nervapack[mcp]"
nervapack ingest .
```

Add `.mcp.json` (see the config below), then open the Cursor MCP panel (Settings → MCP) and click **Reload**.

### Windsurf

Windsurf (Codeium) supports MCP via a global config file at `~/.codeium/windsurf/mcp_config.json`. You can also use a project-local `.mcp.json` — check your Windsurf version's docs for project-level support.

**Global config (works in all Windsurf projects):**

```bash
mkdir -p ~/.codeium/windsurf
```

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph — query_codebase, graph_status, list_entities"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory — store, recall, and reason over facts across sessions"
    }
  }
}
```

Save to `~/.codeium/windsurf/mcp_config.json`, then restart Windsurf. The NervaPack tools appear in the Cascade panel automatically.

> **Tip:** You still need to run `nervapack ingest .` per-project. The MCP server reads from the project's `.nervapack/` directory.

---

## Full mcp.json

Drop this in your project root for all editors:

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph — query_codebase, graph_status, list_entities"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory — store, recall, and reason over facts across sessions"
    }
  }
}
```

---

## Knowledge Graph Server (`nervapack-mcp`)

Exposes the code knowledge graph to Claude Code and Cursor.

### Quick Setup

```bash
# 1. Install MCP support
pip install "nervapack[mcp]"

# 2. Build the graph
nervapack ingest .

# 3. Add to .mcp.json
```

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph — query_codebase, graph_status, list_entities"
    }
  }
}
```

```bash
# 4. Reload your editor
```

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `query_codebase` | `prompt: str`, `max_hops?: int` | Vector search → K-Hop BFS → focused Markdown context with token savings summary |
| `graph_status` | — | Node/edge counts by type, language breakdown, unsynced file warnings |
| `list_entities` | `entity_type?: str`, `file_path?: str` | Browse all indexed classes, functions, imports, and markdown docs |

### Example Interaction

```
You:     "How does the sync command decide which files to re-ingest?"
Claude:  → calls query_codebase("sync command file re-ingest logic")
         → gets 1,180 tokens of focused context (vs 12,840 tokens naive)
         → answers precisely, citing exact line numbers
```

---

## Memory Server (`nervapack-memory-mcp`)

Persists and recalls structured facts, decisions, and outcomes across agent sessions.

### Quick Setup

```bash
# 1. Install memory support
pip install "nervapack[memory]"

# 2. Initialise
python -m nervapack.memory init

# 3. Add to .mcp.json alongside the knowledge-graph server
```

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph — query_codebase, graph_status, list_entities"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory — store, recall, and reason over facts across sessions"
    }
  }
}
```

### Tools

| Tool | Description |
|------|-------------|
| `memory_start_session` | Open a named session — call this first every session |
| `memory_store` | Persist a fact, decision, outcome, procedure, preference, or action |
| `memory_recall` | FTS5 search → graph expansion → scored, budget-capped recall |
| `memory_about` | Dossier on one entity: all linked facts/decisions newest first |
| `memory_why` | Explain a decision: rationale, rejected alternatives, outcomes |
| `memory_timeline` | Chronological trace including superseded versions |
| `memory_end_session` | Close the session with an outcome summary |
| `memory_forget` | Tombstone or hard-purge nodes |
| `memory_verify` | Confirm (confidence +0.1) or refute (close + confidence ×0.5) |
| `memory_stats` | Node counts, DB size, top entities, all namespaces |
| `memory_list_sessions` | List all sessions with node counts, newest first |
| `memory_clear_session` | Tombstone or hard-purge all nodes in a session |
| `memory_for_code` | Memories that TOUCH a source file or specific line |
| `memory_to_code` | Code locations a memory node TOUCHES (file, line range) |
| `memory_import` | Bulk-seed memory from a JSON array of node specs |
| `memory_switch_namespace` | Switch the active namespace, resetting the active session |
| `memory_verify_staleness` | Scan TOUCHES edges; flag memories whose source file changed |

Full tool reference: [Memory MCP Server](memory-mcp.md).

---

## Using Both Servers Together

With both servers registered, Claude Code has:

- **Structural knowledge** (via `nervapack`) — current code, live function signatures, import graph, coverage.
- **Historical knowledge** (via `nervapack-memory`) — past decisions, architectural rationale, outcomes from prior sessions.

```
You:     "Why did we choose JWT over session cookies, and is the auth module still structured that way?"

Claude:  → calls memory_recall("JWT auth decision")       ← history
         → calls query_codebase("auth module structure")  ← current code
         → synthesises both into a coherent answer
```

---

## Storage

| Server | Data | Location |
|--------|------|----------|
| `nervapack-mcp` | NetworkX graph (graphml) + ChromaDB | `.nervapack/graph.graphml`, `.nervapack/chroma_db/` |
| `nervapack-memory-mcp` | SQLite (FTS5 + bi-temporal) | `.nervapack/memory.db` or `~/.nervapack/memory.db` |

Add `.nervapack/` to `.gitignore` to keep both out of version control.

---

## See Also

- [Memory MCP Server — full tool reference](memory-mcp.md)
- [Python SDK](python-sdk.md) — use NervaPack programmatically
- [Memory CLI](../user-guide/commands/memory.md) — `init`, `stats`, `forget`, `export`
