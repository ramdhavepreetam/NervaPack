# MCP Server Integration

Use NervaPack directly in Claude Code and Cursor.

---

## Quick Setup

```bash
# 1. Install MCP support
pip install "nervapack[mcp]"

# 2. Build your graph
nervapack ingest .

# 3. Create .mcp.json
cat > .mcp.json << 'MCPEOF'
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph"
    }
  }
}
MCPEOF

# 4. Reload your editor
```

---

## Available Tools

- `query_codebase(prompt, max_hops)` — Query the graph
- `graph_status()` — Check graph health
- `list_entities(type, file_path)` — Browse entities

See the [README](https://github.com/ramdhavepreetam/NervaPack#using-nervapack-in-llm-developer-tools) for details.
