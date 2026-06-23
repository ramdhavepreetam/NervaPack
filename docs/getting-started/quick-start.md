# Quick Start

Get NervaPack running in 5 minutes. This tutorial walks you through building your first knowledge graph and running your first query.

---

## Step 1: Install NervaPack

If you haven't already, install NervaPack:

=== "Homebrew (macOS/Linux)"
    ```bash
    brew tap ramdhavepreetam/nervapack
    brew install nervapack
    ```

=== "pipx (Recommended)"
    ```bash
    pipx install nervapack
    ```

=== "pip"
    ```bash
    pip install nervapack
    ```

Verify installation:
```bash
nervapack --help
```

---

## Step 2: Set Up LLM Provider

NervaPack needs an LLM to bind documentation to code. Choose one:

=== "Ollama (Privacy-First, Free)"
    ```bash
    # Install Ollama
    brew install ollama  # or download from ollama.com

    # Pull a model
    ollama pull llama3

    # Start Ollama (in separate terminal)
    ollama serve
    ```

=== "Claude API (Cloud)"
    ```bash
    # Get API key from https://console.anthropic.com
    export ANTHROPIC_API_KEY=sk-ant-...

    # Install Claude support
    pip install "nervapack[claude]"
    ```

=== "OpenAI API (Cloud)"
    ```bash
    # Get API key from https://platform.openai.com/api-keys
    export OPENAI_API_KEY=sk-...

    # Install OpenAI support
    pip install "nervapack[openai]"
    ```

=== "MCP (Claude Code/Cursor)"
    ```bash
    # No setup needed!
    # If using NervaPack through Claude Code, it auto-detects
    pip install "nervapack[mcp]"
    ```

!!! tip "First time users"
    We recommend **Ollama** for maximum privacy and zero recurring costs.

---

## Step 3: Navigate to Your Project

```bash
cd your-project/
```

!!! warning "Git required"
    Your project must be a git repository:
    ```bash
    # If not already a git repo:
    git init
    git add .
    git commit -m "Initial commit"
    ```

---

## Step 4: Build the Knowledge Graph

Run the ingest command to build your graph:

=== "With Ollama (Default)"
    ```bash
    nervapack ingest .
    ```

=== "With Claude API"
    ```bash
    nervapack ingest . --llm claude
    ```

=== "With OpenAI API"
    ```bash
    nervapack ingest . --llm openai
    ```

**What happens:**

1. **Scans directory** for code files (`.py`, `.js`, `.ts`, etc.)
2. **Parses AST** using tree-sitter (classes, functions, imports)
3. **Scans markdown docs** (`.md` files)
4. **Embeds entities** into ChromaDB vector store
5. **Binds docs to code** using LLM (creates `EXPLAINS` edges)
6. **Saves graph** to `.nervapack/graph.graphml`

**Expected time:**
- Small project (< 100 files): 1-2 minutes
- Medium project (100-1000 files): 5-10 minutes
- Large project (1000+ files): 15-30 minutes

!!! tip "Progress tracking"
    NervaPack shows real-time progress with rich console output.

---

## Step 5: Run Your First Query

Ask NervaPack about your codebase:

```bash
nervapack query "How does authentication work?"
```

**Output:**

```
Query: "How does authentication work?"

Vector Search: Found 3 seed nodes

┌───────────────────────────────────────────────────────┐
│ #  │ Node Type │ Name/File                            │
├───────────────────────────────────────────────────────┤
│ 1  │ function  │ authenticate_user                    │
│ 2  │ class     │ AuthMiddleware                       │
│ 3  │ markdown  │ Authentication Guide                 │
└───────────────────────────────────────────────────────┘

Graph Traversal: Expanding with max_hops=1

  Seed nodes: 3
  Expanded nodes: 7
  Total retrieved: 10
  Edges followed: 12
  Traversal depth: 1

Retrieved Context:
──────────────────────────────────────────────────────────

# NervaPack Context Retrieval
## File: src/auth/middleware.py
### CLASS: AuthMiddleware (L15-L42)
...

## File: docs/authentication.md
### MARKDOWN: Authentication Guide
...

──────────────────────────────────────────────────────────

╭──────────────  NervaPack Token Efficiency  ──────────────╮
│  Strategy              Tokens   Visual            Relative │
│  Naive RAG (3 files)   12,840   ████████████████  100%    │
│  NervaPack              1,180   █░░░░░░░░░░░░░░░    9.2%  │
│ ──────────────────────────────────────────────────────────│
│  Tokens saved: 11,660   Reduction: 90.8%                  │
│  Cost saved (GPT-4o  $2.50/1M): $0.0292 per query         │
│  Cost saved (Claude Sonnet $3/1M): $0.0350 per query      │
╰───────────────────────────────────────────────────────────╯
```

**What happened:**

1. **Vector search** found 3 most relevant nodes
2. **Graph traversal** expanded 1-hop to find related code
3. **Context extracted** as focused Markdown
4. **Token savings calculated** vs naive approach

!!! success "Copy-paste ready"
    The context output is designed to be pasted directly into an LLM prompt!

---

## Step 6: Visualize the Graph

See your knowledge graph in an interactive HTML visualization:

```bash
nervapack visualize --enhanced --communities
```

**Opens in browser:**

- **Node shapes:** Files (diamonds), Classes (dots), Functions (dots)
- **Colors:** Community-detected modules (Louvain algorithm)
- **Search box:** Real-time filtering
- **Interactive:** Drag, zoom, click nodes for details
- **Path finder:** Click two nodes to find shortest path

**Saved to:** `.nervapack/graph.html`

!!! tip "Share visualizations"
    The HTML file is standalone—no external dependencies. Share it with your team!

---

## Step 7: Check Graph Status

See comprehensive analytics:

```bash
nervapack status --detailed
```

**Output:**

```
╭──────────────  NervaPack Status  ──────────────╮
│ Graph Health Score: 34/100 ●●●○○○○○○○          │
│                                                │
│ 📊 Overview                                    │
│   Nodes:      378                              │
│   Edges:      353                              │
│   Files:       25                              │
│   Functions:  138                              │
│   Classes:     20                              │
│                                                │
│ 📚 Language Distribution                       │
│   Python      ████████████████ 100.0%  (25)   │
│                                                │
│ 📖 Documentation Coverage                      │
│   ░░░░░░░░░░░░░░░░ 0.0% (0/158 entities)       │
│                                                │
│ 🔗 Most Connected Files                        │
│   1. cli.py                    (75 edges)      │
│   2. app.py                    (28 edges)      │
│                                                │
│ 🔄 Git Sync Status                             │
│   ✓ Graph is in sync                           │
╰────────────────────────────────────────────────╯
```

---

## Step 8: Sync After Changes

After modifying files, update your graph incrementally:

```bash
# Make some changes to your code
vim src/auth/middleware.py

# Sync only changed files (fast!)
nervapack sync .
```

**Output:**

```
Syncing changed files with NervaPack graph...
Found 1 changed files.
Updated AST for auth/middleware.py
Sync complete.
```

!!! tip "Incremental updates"
    `sync` only re-indexes changed files—much faster than re-running `ingest`!

---

## Common Workflows

### Daily Development
```bash
# Morning: Check if graph is up to date
nervapack status

# Sync if needed
nervapack sync .

# Query as you code
nervapack query "How does the caching layer work?"
```

### Code Review
```bash
# Explore a specific module
nervapack explore src/auth/ --hops 2

# Check dependencies
nervapack dependencies src/auth/middleware.py

# Visualize for the reviewer
nervapack visualize --enhanced --communities
```

### Documentation
```bash
# Query for context
nervapack query "authentication flow" > context.md

# Use context to write docs with LLM assistance
```

---

## Next Steps

You've successfully built your first knowledge graph! Here's what to explore next:

<div class="grid" markdown>

**[LLM Provider Setup](llm-providers.md)**
Learn about all provider options (Ollama, Claude, OpenAI, MCP)

**[Command Reference](../user-guide/commands/ingest.md)**
Detailed docs for all 10 CLI commands

**[MCP Server Integration](../integrations/mcp-server.md)**
Use NervaPack directly in Claude Code/Cursor

**[Python SDK](../integrations/python-sdk.md)**
Build custom tools with the NervaPack API

</div>

---

## Troubleshooting Quick Start

### "Ollama not running" error
```bash
# Make sure Ollama is running
ollama serve

# In another terminal, verify:
ollama list
```

### "Not a git repository" error
```bash
# Initialize git in your project
git init
git add .
git commit -m "Initial commit"
```

### "No relevant nodes found" after query
- **Graph might be empty.** Check: `nervapack status`
- **Query might be too specific.** Try broader terms.
- **Re-run ingest** if you recently added docs.

### Graph out of sync
```bash
# Full rebuild (if sync doesn't work)
rm -rf .nervapack/
nervapack ingest .
```

---

**You're all set!** 🎉

NervaPack is now integrated into your development workflow. Happy querying!
