# Quick Start

Get NervaPack running in under 5 minutes.

---

## Step 1: Install

```bash
pip install nervapack
```

For MCP integration with Claude Code or Cursor:
```bash
pip install "nervapack[mcp]"
```

Verify:
```bash
nervapack --help
```

---

## Step 2: (Optional) Set Up an LLM

NervaPack builds a structural graph with **zero LLM setup**. An LLM is only needed to add semantic doc-to-code edges (`EXPLAINS`). Skip this step if you just want to try it.

=== "Ollama (Privacy-First, Free)"
    ```bash
    brew install ollama       # or download from ollama.com
    ollama pull llama3
    ollama serve              # keep running in a separate terminal
    ```

=== "Claude API"
    ```bash
    pip install "nervapack[claude]"
    export ANTHROPIC_API_KEY=sk-ant-...
    ```

=== "OpenAI API"
    ```bash
    pip install "nervapack[openai]"
    export OPENAI_API_KEY=sk-...
    ```

=== "MCP / Claude Code"
    ```bash
    # Zero setup — auto-detected when running inside Claude Code
    pip install "nervapack[mcp]"
    ```

---

## Step 3: Ingest Your Project

```bash
cd your-project/
nervapack ingest .
```

**What this does (in order):**

1. Walks the directory tree — skips `dist/`, `build/`, `node_modules/`, `venv/`, `site/`, `.tox/`, and dozens of other non-code directories automatically.
2. Parses source files with tree-sitter → classes, functions, imports.
3. Chunks all `.md` files by header.
4. Embeds every entity into ChromaDB (local ONNX model, no cloud).
5. If an LLM is available, binds doc chunks to code nodes (`EXPLAINS` edges).
6. Saves the graph to `.nervapack/graph.graphml`.

**Expected time:**

| Project size | Time |
|---|---|
| < 50 files | 15–30 seconds |
| 50–500 files | 1–3 minutes |
| 500–2000 files | 3–10 minutes |

!!! tip "Re-ingest is safe"
    NervaPack uses `upsert` throughout — running `ingest` twice does not duplicate data. If you see large `.nervapack/chroma_db/` sizes from an older version, run `nervapack clean --vectors` first.

!!! tip "Exclude build directories"
    Create a `.nervapackignore` file (gitignore syntax) for any project-specific directories to skip:
    ```
    generated/
    proto_out/
    __snapshots__/
    ```

---

## Step 4: Run Your First Query

```bash
nervapack query "How does authentication work?"
```

**What you get:**
- A focused Markdown context block containing only the relevant classes, functions, and doc sections — ready to paste into an LLM prompt.
- A token efficiency panel showing how many tokens NervaPack used vs. naive "dump the whole file" RAG.

```
Query: "How does authentication work?"

Query Router: Intent: semantic, Direction: both
Vector Search: Found 3 seed nodes

Retrieved Context:
──────────────────────────────────────────────────────────
# NervaPack Context Retrieval
## File: `src/auth/middleware.py`
### CLASS: AuthMiddleware (L15-L42)
```python
class AuthMiddleware:
    def authenticate(self, token: str) -> User:
        ...
```

## File: `docs/authentication.md`
### MARKDOWN: Authentication Guide
JWT tokens are issued on login and expire after 15 minutes...
──────────────────────────────────────────────────────────

╭──────────────  NervaPack Token Efficiency  ──────────────╮
│  Strategy              Tokens   Reduction                 │
│  Naive RAG (3 files)   12,840   100% (base)              │
│  NervaPack              1,180     9.2%                    │
│ ─────────────────────────────────────────────────────────│
│  Tokens saved: 11,660   Reduction: 90.8%                 │
│  Cost saved (GPT-4o $2.50/1M): $0.0292 per query         │
╰───────────────────────────────────────────────────────────╯
```

### Impact analysis

Find what would break if you change a function:
```bash
nervapack query "what breaks if I change AuthMiddleware"
```

### Exact symbol lookup

Jump directly to a named entity, bypassing vector search:
```bash
nervapack query "VectorStore"
```

---

## Step 5: Visualize the Graph

```bash
nervapack visualize --enhanced --communities
```

Opens an interactive HTML file in your browser. Features:
- Real-time search (filter nodes by typing)
- Shortest path finder (click two nodes)
- Community detection with Louvain colour coding
- Drag, zoom, hover for code previews

Saved to `.nervapack/graph.html` — standalone, no internet required, shareable.

---

## Step 6: Check Status

```bash
nervapack status --detailed
```

Shows health score (0–100), language distribution, documentation coverage, and most-connected files. Use this to decide whether to run `nervapack enrich .` to improve semantic coverage.

---

## Step 7: Sync After Changes

After modifying files:
```bash
nervapack sync .
```

Only re-parses and re-embeds the changed files. Typically 2–5 seconds regardless of project size.

---

## Step 8: Use with Claude Code (MCP)

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph (v0.6.1)"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory (v0.6.1)"
    }
  }
}
```

Add to your `CLAUDE.md`:

```markdown
## NervaPack session protocol
At the start of every session:
1. Call `memory_start_session("<task name>")`.
2. Call `memory_recall("project context", budget_tokens=400)`.
3. Call `query("<topic>")` before answering any code question.

During the session: call `memory_store` for decisions, facts, and procedures.
At session end: call `memory_end_session("<summary>")`.
```

Reload Claude Code — NervaPack tools appear automatically.

---

## If Something Goes Wrong

### Graph is wrong or too large
```bash
nervapack clean --all    # wipes vectors + graph (keeps memory)
nervapack ingest .
```

### Duplicate vectors from multiple ingests (older versions)
```bash
nervapack clean --vectors
nervapack ingest .
```

### `doctor` for full diagnostics
```bash
nervapack doctor
```

Checks Python version, tree-sitter grammars, embedding backend, Ollama connectivity, and MCP config.

### "Not a git repository" error on `sync`
```bash
git init && git add . && git commit -m "init"
nervapack sync .
```

---

## Daily Workflow

```bash
# Morning: check graph is current
nervapack status

# Sync if files changed
nervapack sync .

# Query while coding
nervapack query "How does the caching layer work?"

# Before a review: explore changed module
nervapack explore src/auth/ --hops 2

# End of sprint: check hotspots
nervapack hotspots --since "2 weeks ago"
```

---

## Next Steps

- [Command Reference](../user-guide/commands/ingest.md) — detailed docs for every command
- [MCP Server](../integrations/mcp-server.md) — wire NervaPack into Claude Code / Cursor
- [Agent Memory](../memory/index.md) — cross-session memory for AI agents
- [Benchmarks](../BENCHMARKS.md) — verified performance numbers
