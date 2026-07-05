# NervaPack

[![PyPI version](https://img.shields.io/pypi/v/nervapack.svg)](https://pypi.org/project/nervapack/)
[![Python Versions](https://img.shields.io/pypi/pyversions/nervapack.svg)](https://pypi.org/project/nervapack/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Token Reduction](https://img.shields.io/badge/Token_Reduction-91.2%25-brightgreen.svg)](docs/BENCHMARKS.md)
[![Verified](https://img.shields.io/badge/Performance-Verified-blue.svg)](docs/BENCHMARKS.md)

**NervaPack** is a privacy-first, offline knowledge graph for your codebase. It solves two fundamental problems with standard Vector RAG:

- **Token waste** — chunk-based RAG retrieves blobs of text that may only tangentially relate to your query, bloating your context window.
- **Privacy risk** — sending code to cloud embedding APIs leaks your proprietary logic.

NervaPack runs 100% on your machine. It uses `tree-sitter` to parse your codebase into a deterministic Abstract Syntax Tree graph, then uses a local Ollama model to draw hard semantic edges between your documentation and your code. Queries traverse this graph with a K-Hop BFS, returning a hyper-targeted, token-efficient context window — no cloud required.

---

## ⚡ Verified Performance

**91.2% Average Token Reduction** — independently verified on real-world codebases.

| Test Type | Tokens (Naive) | Tokens (NervaPack) | Reduction |
|-----------|----------------|-------------------|-----------|
| Simple Query | 10,926 | 101 | **99.1%** |
| Medium Query | 13,092 | 164 | **98.7%** |
| Complex Query | 3,290 | 1,102 | **66.5%** |
| **Average** | **52,037** | **2,459** | **91.2%** |

**Cost Savings:** $181-$724 per developer per year (GPT-4o to GPT-4 Turbo)

📊 **[View Full Benchmarks](docs/BENCHMARKS.md)** · 🧪 **[Messy Code Performance](docs/MESSY_CODE_PERFORMANCE.md)**

> **Code Quality Impact:** 90-99% reduction on clean code, 50-75% on legacy/messy code. Even poorly structured codebases benefit significantly.

---

## Why NervaPack vs. standard Vector RAG

| | Standard Vector RAG | NervaPack |
|---|---|---|
| **Parsing** | Arbitrary text chunks | Deterministic AST nodes (class, function, import) |
| **Retrieval** | Nearest-neighbor blob | K-Hop BFS on a structural graph |
| **Doc ↔ Code links** | None | Hard `EXPLAINS` edges drawn by local LLM |
| **Privacy** | Cloud embeddings | 100% local (ChromaDB + Ollama) |
| **Incremental sync** | Re-index everything | Surgical per-file update via GitPython diff |
| **Token savings** | No measurement | Built-in dashboard shows exact reduction per query |
| **Graph visibility** | Black box | Interactive HTML visualization of every node and edge |

---

## Prerequisites

- **Python 3.10+**
- **Git** — your project must be a git repository (`git init` if not)
- **LLM Provider** (choose one):
  - **Ollama** (local, privacy-first) — install from [ollama.com](https://ollama.com/), then pull a model:
    ```bash
    ollama pull llama3
    ```
  - **Claude API** (cloud, no local setup) — get API key from [console.anthropic.com](https://console.anthropic.com/)
  - **OpenAI API** (cloud, widely available) — get API key from [platform.openai.com](https://platform.openai.com/api-keys)
  - **Claude Code/Cursor** (MCP integration) — uses your existing Claude session, zero config!

---

## Installation

**Option A — Homebrew (Mac/Linux, recommended)**
```bash
brew tap ramdhavepreetam/nervapack
brew install nervapack
```

**Option B — pipx (any platform, cleanest Python install)**
```bash
pipx install nervapack
```

**Option C — pip**
```bash
pip install nervapack
```

**With optional features:**
```bash
pip install "nervapack[metrics]"    # exact token counting (tiktoken)
pip install "nervapack[dashboard]"  # web dashboard (streamlit + plotly)
pip install "nervapack[mcp]"        # MCP server for Claude Code/Cursor
pip install "nervapack[claude]"     # Claude API support (cloud LLM)
pip install "nervapack[openai]"     # OpenAI API support (cloud LLM)
pip install "nervapack[cloud-llm]"  # Both Claude + OpenAI
pip install "nervapack[all]"        # All features
```

> On first run, `chromadb` downloads `onnxruntime` embedding models to your cache and `tree-sitter` compiles its language bindings. This is a one-time setup (~1–2 min).

---

## LLM Provider Options

NervaPack supports multiple LLM providers for document-to-code binding. Choose based on your priorities:

### Option 1: Ollama (Default — Privacy-First, Free)

**Best for:** Privacy-conscious users, offline work, no recurring costs

```bash
# One-time setup
brew install ollama
ollama pull llama3
ollama serve

# Use NervaPack (auto-detects Ollama)
nervapack ingest .
```

**Pros:** ✅ Free, ✅ 100% private, ✅ Works offline
**Cons:** ❌ ~4GB download, ❌ Uses local resources

---

### Option 2: Claude API (Cloud — Fast, High Quality)

**Best for:** Users who want best results without local setup

```bash
# Install Claude support
pip install "nervapack[claude]"

# Get API key from https://console.anthropic.com
export ANTHROPIC_API_KEY=sk-ant-...

# Use NervaPack with Claude
nervapack ingest . --llm claude
```

**Cost estimate:** ~$0.25 per 1000 binding calls (Haiku model)
**Pros:** ✅ No local install, ✅ High quality, ✅ Fast
**Cons:** ❌ Sends code to cloud, ❌ Costs money

**Available models:**
- `claude-3-haiku-20240307` (fastest, cheapest — default)
- `claude-3-5-sonnet-20241022` (best quality, higher cost)

---

### Option 3: OpenAI API (Cloud — Widely Available)

**Best for:** Users with existing OpenAI accounts

```bash
# Install OpenAI support
pip install "nervapack[openai]"

# Get API key from https://platform.openai.com/api-keys
export OPENAI_API_KEY=sk-...

# Use NervaPack with OpenAI
nervapack ingest . --llm openai
```

**Cost estimate:** ~$0.15 per 1000 binding calls (GPT-4o-mini)
**Pros:** ✅ Widely available, ✅ Good quality
**Cons:** ❌ Sends code to cloud, ❌ Costs money

**Available models:**
- `gpt-4o-mini` (cheapest, good quality — default)
- `gpt-4o` (best quality, higher cost)

---

### Option 4: MCP Delegation (Claude Code/Cursor)

**Best for:** Users already in Claude Code or Cursor

```bash
# Zero setup needed!
# If using NervaPack through Claude Code:
nervapack ingest .
# → Auto-detects MCP context
# → Uses your existing Claude session
# → No separate API key needed
```

**Pros:** ✅ Zero config, ✅ Uses existing auth, ✅ No extra cost
**Cons:** ⚠️ Only works in MCP-compatible tools

---

### Privacy & Cost Comparison

| Provider | Privacy | Setup | Cost (1000 calls) | Use Case |
|----------|---------|-------|-------------------|----------|
| **Ollama** | 🔒 100% Local | Medium | Free | Privacy-first |
| **Claude API** | ☁️ Cloud | Easy | ~$0.25 | Quality + convenience |
| **OpenAI API** | ☁️ Cloud | Easy | ~$0.15 | Existing OpenAI users |
| **MCP Delegation** | ☁️ Cloud* | Zero | Included | Claude Code users |

*Uses Claude through your existing subscription

---

## Quick Start

```bash
cd your-project/

# 1. Build the knowledge graph (run once)
nervapack ingest .

# 2. Query for context — see focused results + token savings dashboard
nervapack query "How does authentication work?"

# 3. Visualize the graph with search and community detection
nervapack visualize --enhanced --communities

# 4. Launch interactive web dashboard
nervapack serve

# 5. After modifying files, sync the graph incrementally
nervapack sync .

# 6. Check detailed graph health and analytics
nervapack status --detailed
```

---

## Command Reference

### `nervapack ingest [PATH]`

Scans `PATH` (default: `.`) and builds the full knowledge graph.

What happens:
1. `tree-sitter` parses source files into Classes, Functions, and Imports — exact AST nodes, not text chunks.
2. All `.md` files are chunked by header hierarchy.
3. Each Markdown chunk is sent to your local Ollama model. If the model identifies a code entity the prose explains, a hard `EXPLAINS` edge is written into the graph.
4. All nodes are embedded and stored in a local ChromaDB instance (`.nervapack/chroma_db`).

> The initial LLM binding pass is the slowest step. On a large repo with many docs, budget several minutes.

**Supported languages** (bundled): Python, JavaScript, JSX, TypeScript, TSX

**Additional languages** (optional extras):
```bash
pip install "nervapack[go]"           # Go
pip install "nervapack[rust]"         # Rust
pip install "nervapack[java]"         # Java
pip install "nervapack[c]"            # C / C headers
pip install "nervapack[cpp]"          # C++
pip install "nervapack[ruby]"         # Ruby
pip install "nervapack[csharp]"       # C#
pip install "nervapack[all-languages]" # everything above
```

---

### `nervapack query PROMPT`

Retrieves context from the graph for a natural-language prompt, then prints a **token savings dashboard** comparing NervaPack against naive RAG.

What happens:
1. The prompt is embedded and ChromaDB returns the top-3 most semantically similar nodes.
2. Those nodes seed a K-Hop Breadth-First Search (`max_hops=1`) through the NetworkX graph.
3. Adjacent nodes — including any Markdown docs linked via `EXPLAINS` edges — are collected into a compressed Markdown snippet.
4. The token efficiency panel is printed showing how many tokens were saved vs. sending the raw files.

**Example output:**

```
Running query: How does the CLI work?
Found 3 seed nodes. Traversing graph...

--- Retrieved Context ---
# NervaPack Context Retrieval
## File: src/nervapack/cli.py
### FUNCTION: query (L200-L242)
...
--- End Context ---

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

**"Naive RAG"** is defined as the full content of every source file that contains a matched node — the maximum a standard "find relevant files, dump them whole" approach would send to an LLM. The comparison is honest and conservative.

Install `nervapack[metrics]` for exact token counts via `tiktoken`. Without it, a character-based estimate is used and marked with `~`.

The context output is designed to be pasted directly into an LLM prompt.

> **📊 Verified Performance:** The 90% reduction claim is verified through real-world testing. See [BENCHMARKS.md](docs/BENCHMARKS.md) for detailed test results (91.2% average across 5 queries on NervaPack's own codebase). Performance varies based on code quality: 90-99% on clean code, 50-75% on legacy/messy code. [Learn more →](docs/MESSY_CODE_PERFORMANCE.md)

---

### `nervapack visualize [--enhanced] [--communities]`

Renders the knowledge graph as an **interactive HTML file** and opens it in your browser.

**Basic usage:**
```bash
nervapack visualize                          # saves to .nervapack/graph.html
nervapack visualize --output ~/my-graph.html # custom output path
nervapack visualize --no-browser             # generate without opening
```

**Enhanced mode (recommended):**
```bash
nervapack visualize --enhanced               # adds real-time search
nervapack visualize --enhanced --communities # + community detection
```

**Enhanced features:**
- **Real-time search** — Filter nodes by typing (instant, client-side)
- **Path finder** — Click two nodes to find and highlight shortest path
- **Community detection** — Color-coded modules using Louvain algorithm
- **Visual highlighting** — Matched nodes enlarged, non-matched dimmed

What the visualization shows:
- **Node shapes:** diamonds = files, dots = all other entities
- **Node colors:** blue = file, green = function, amber = class, gray = import, lavender = markdown (or community colors)
- **Edge styles:** solid = `DEFINES`, dashed = `EXPLAINS`
- **Hover tooltips:** type, name, file, line range, and a code preview
- **Interactive:** drag, zoom, click — spring-force physics layout

The graph is a static HTML file with no external dependencies — share it, open it offline, or embed it in docs.

---

### `nervapack explore <target> [--hops N]`

Extract and visualize a focused subgraph around a specific file, class, or function. Perfect for understanding a specific part of your codebase without the noise of the full graph.

```bash
nervapack explore GraphBuilder --hops 2     # explore 2-hop neighborhood
nervapack explore src/cli.py --hops 1       # file-based exploration
nervapack explore "function:parse"          # partial name matching
```

**How it works:**
1. Searches for nodes matching the target (by file path, name, or node ID)
2. Performs multi-source BFS to extract N-hop neighborhood
3. Generates enhanced visualization with search enabled

**Use cases:**
- Understanding class relationships
- Finding related code quickly
- Impact analysis before refactoring
- Onboarding to specific modules

---

### `nervapack dependencies [file]`

Analyze file-level import dependencies, detect circular dependencies, and visualize the dependency graph.

**Overall analysis:**
```bash
nervapack dependencies
```

Shows:
- Total files and dependency edges
- Circular dependency detection with cycle visualization
- Most depended-on files (top 10)
- Files with most dependencies (top 10)
- Orphan files (no dependencies)
- Interactive hierarchical visualization

**Specific file:**
```bash
nervapack dependencies src/graph/builder.py
```

Shows:
- Files this file imports
- Files that import this file

**Visualization features:**
- **Color coding:**
  - 🔴 Red: Part of circular dependency
  - 🔵 Cyan: Heavily depended on (>5 dependents)
  - 🟡 Yellow: Many dependencies (>5 imports)
  - 🟢 Green: Normal file
  - ⚫ Gray: Orphan (isolated)
- **Hierarchical layout** — Topological sort when DAG
- **Search box** — Filter files by name
- **Size scaling** — Proportional to total degree

**Example output:**
```
╭──────────  Dependency Metrics  ──────────╮
│ Total Files              │  127          │
│ Total Dependencies       │  456          │
│ Max Dependency Depth     │  8            │
│ Orphan Files             │  3            │
╰──────────────────────────────────────────╯

⚠ Circular Dependencies Detected: 2 cycle(s)

Cycle 1:
  auth.py
  → user.py
  → session.py
  → auth.py (back to start)
```

---

### `nervapack serve [--port N]`

Launch an interactive **web dashboard** with real-time analytics, visualizations, and graph exploration. Requires `nervapack[dashboard]`.

```bash
nervapack serve                  # launches on http://localhost:8501
nervapack serve --port 8080      # custom port
nervapack serve --no-browser     # don't auto-open browser
```

**Dashboard features:**
- **Overview tab** — Health score, language distribution, top files
- **Analytics tab** — Node/edge type breakdown, degree distribution
- **Query History tab** — Trends, cost savings, keyword frequency
- **Graph Explorer tab** — Real-time search, statistics

**Performance:**
- Initial load: <2 seconds
- Subsequent loads: <200ms (cached)
- Real-time filtering and charts

---

### `nervapack sync [PATH]`

Incrementally updates the graph for files changed since the last ingest.

What happens:
1. `GitPython` diffs your working tree to find modified and deleted files.
2. For each changed file, old graph nodes and ChromaDB vectors are pruned.
3. Only the changed files are re-parsed and re-ingested.

A full `ingest` on a large codebase can take minutes. `sync` turns that into a 2–5 second surgical update.

---

### `nervapack status [--detailed]`

Prints the current state of the graph: node count, edge count, and any files that are out of sync with the graph.

**Enhanced with `--detailed` flag:**
```bash
nervapack status --detailed
```

Shows comprehensive analytics:
- **Health score** (0-100) based on documentation coverage, connectivity, and graph density
- **Language distribution** with visual bars
- **Most connected files** (top 10 by degree)
- **Documentation coverage** percentage
- **Git sync status** with warnings for unsynced files

**Example output:**
```
╭──────────── NervaPack Status ────────────────╮
│ Graph Health Score: 85/100 ●●●●●●●●○○        │
│                                              │
│ 📊 Overview                                  │
│   Nodes:      1,247                          │
│   Edges:      3,821                          │
│   Files:        156                          │
│   Functions:    892                          │
│                                              │
│ 📚 Language Distribution                     │
│   Python      ████████████░░░░  62.5%  (98)  │
│   TypeScript  ██████░░░░░░░░░░  35.2%  (55)  │
│                                              │
│ 📖 Documentation Coverage                    │
│   ████████████░░░░░  67.8% (845/1247)        │
╰──────────────────────────────────────────────╯
```

---

### `nervapack history [--stats] [--limit N] [--clear]`

View query history and analytics. All queries are automatically saved to `.nervapack/query_history.jsonl`.

```bash
nervapack history              # show last 10 queries
nervapack history --limit 20   # show last 20
nervapack history --stats      # aggregate statistics
nervapack history --clear      # clear all history
```

**Statistics include:**
- Total queries run
- Average token savings percentage
- Total tokens saved across all queries
- Cost savings (GPT-4o and Claude Sonnet pricing)
- Most frequently queried topics (word frequency analysis)

---

## Configuration

NervaPack reads the Ollama model from the `LLMSummarizer` class (`src/nervapack/llm/summarizer.py`). To use a different model, set `model` to any model you have pulled locally:

```python
# src/nervapack/llm/summarizer.py
self.model = "phi3"   # or "mistral", "codellama", etc.
```

Ollama is expected at `http://localhost:11434` (its default). To use a remote Ollama instance, set `OLLAMA_HOST`:

```bash
OLLAMA_HOST=http://my-server:11434 nervapack ingest .
```

---

## Architecture

```
nervapack ingest .
       │
       ├─ ASTParser (tree-sitter)          16 extensions, 9 languages
       │    └─ ParsedEntity[]: class, function, import
       │
       ├─ GraphBuilder (NetworkX DiGraph)
       │    ├─ Nodes: file, class, function, import, markdown
       │    └─ Edges: DEFINES, EXPLAINS
       │
       ├─ LLMSummarizer (Ollama)
       │    └─ Draws EXPLAINS edges: markdown → code entity
       │
       └─ VectorStore (ChromaDB)
            └─ Embeds node summaries for semantic search

nervapack query "..."
       │
       ├─ VectorStore.search() → seed node IDs
       ├─ GraphRetriever.retrieve_context() → BFS subgraph → Markdown
       └─ TokenMeter → savings vs. naive RAG (tokens, %, cost)

nervapack visualize
       │
       └─ Visualizer (pyvis) → .nervapack/graph.html
```

**Storage layout** (inside your project root):
```
.nervapack/
├── graph.graphml       # NetworkX graph (deterministic structure)
├── graph.html          # Interactive visualization (generated by visualize)
└── chroma_db/          # ChromaDB (semantic embeddings)
```

**Source modules:**
| Module | Responsibility |
|---|---|
| `nervapack.parser.language_registry` | Declarative registry of 16 file extensions and their tree-sitter grammars |
| `nervapack.parser.ast_parser` | Tree-sitter parsing → `ParsedEntity` objects |
| `nervapack.parser.md_chunker` | Markdown → header-delimited chunks |
| `nervapack.graph.builder` | Build and persist the NetworkX DiGraph |
| `nervapack.graph.vector_store` | ChromaDB ingest and semantic search |
| `nervapack.graph.retrieval` | K-Hop BFS context extraction |
| `nervapack.graph.visualizer` | pyvis interactive HTML export |
| `nervapack.graph.visualizer_v2` | Enhanced visualizer with search, communities, path finding |
| `nervapack.graph.dependency_analyzer` | File-level dependency analysis and cycle detection |
| `nervapack.graph.analytics` | Health scoring, language distribution, coverage metrics |
| `nervapack.graph.query_history` | Query tracking and aggregate analytics |
| `nervapack.graph.token_meter` | Token counting and savings panel |
| `nervapack.dashboard.app` | Streamlit web dashboard with interactive charts |
| `nervapack.llm.summarizer` | Local Ollama interface for LLM binding |
| `nervapack.git.tracker` | GitPython diff for incremental sync |
| `nervapack.mcp_server` | MCP server for Claude Code/Cursor integration |

---

## Privacy

NervaPack is 100% offline. No code, documentation, or query ever leaves your machine:

- Embeddings are generated by ChromaDB's built-in local model.
- LLM calls go exclusively to `localhost:11434` (your Ollama instance).
- All graph and vector data is stored in `.nervapack/` inside your project.

Add `.nervapack/` to your `.gitignore` to keep it out of version control.

---

## Using NervaPack in LLM Developer Tools

NervaPack ships a built-in MCP server, so any MCP-compatible tool (Claude Code, Cursor, etc.) can use it as a native context provider — no custom code required.

### Setup (one-time per project)

**1. Install the MCP extra:**
```bash
pip install "nervapack[mcp]"
```

**2. Build the graph:**
```bash
nervapack ingest .
```

**3. Add `.mcp.json` to your project root:**
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

That's it. Reload your MCP-compatible tool and NervaPack's tools appear automatically.

### Tools exposed

| Tool | What it does |
|---|---|
| `query_codebase(prompt, max_hops?)` | Vector search → K-Hop BFS → focused Markdown context + token savings summary |
| `graph_status()` | Node/edge counts by type, language breakdown, unsynced file warnings |
| `list_entities(entity_type?, file_path?)` | Browse all indexed classes, functions, imports, markdown docs |

### How Claude Code uses it

Once `.mcp.json` is in place, Claude Code automatically calls `query_codebase` before answering questions about the codebase. Instead of reading whole files, it gets a surgical subgraph of only the relevant code — the same token savings you see in the CLI dashboard, applied to every single response.

```
You:     "How does the sync command decide which files to re-ingest?"
Claude:  → calls query_codebase("sync command file re-ingest logic")
         → gets 1,180 tokens of focused context (vs 12,840 tokens naive)
         → answers precisely, citing exact line numbers
```

### Keeping the graph fresh

```bash
# After modifying files
nervapack sync .

# Check if Claude's context is stale
# (graph_status tool reports this automatically)
```

### Python SDK (for building your own tool)

```python
from nervapack.graph.builder import GraphBuilder
from nervapack.graph.vector_store import VectorStore
from nervapack.graph.retrieval import GraphRetriever

graph = GraphBuilder().load_graph()
retriever = GraphRetriever(graph)
results = VectorStore().search("your query", n_results=3)
start_nodes = results["ids"][0]
subgraph = retriever.retrieve_context(start_nodes, max_hops=1)
context = retriever.format_as_markdown(subgraph)
# Inject context into your LLM system prompt
```

---

## nervapack.memory — Conversation Context Extender

Stop re-pasting project context into every new chat.

Every developer using an AI assistant on an ongoing project hits the same wall: Monday you explain the architecture and decisions. Wednesday, new tab, blank slate — you explain them again. `nervapack.memory` fixes this. It accumulates structured context across sessions and delivers a complete project briefing — 30 days of decisions and conventions — in under 200 tokens.

```
Session 1:  "Chose JWT for auth — stateless scaling"                → 8 tokens stored
Session 2:  "auth_service issues 15-min tokens"                     → 7 tokens stored
Session 3:  "Deploy: GitHub Actions → staging → manual prod"        → 9 tokens stored
            ...4 weeks later...

memory_recall("project context", budget_tokens=400)
→ 6 items · 171/400 tokens    ← full project briefing, guaranteed ≤ 400 tokens
```

The bi-temporal model keeps only **current truth**: old decisions superseded by new ones don't surface. Budget enforcement is a hard invariant — recall never bloats your context window.

### Quickstart (5 minutes)

**1. Install**

```bash
pip install "nervapack[memory]"
nervapack-memory init
# ✓ Memory store initialised at .nervapack/memory.db
```

**2. Add to `.mcp.json`**

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp"
    }
  }
}
```

**3. Recommended session protocol (add to CLAUDE.md or system prompt)**

```markdown
At the start of every session:
1. Call memory_start_session("task name").
2. Call memory_recall("project context", budget_tokens=400) — this is your briefing.
3. Call memory_recall on any specific topic before working on it.

During the session, store decisions, facts, conventions, and outcomes.
At session end, call memory_end_session("summary").
```

**4. Store a decision with full context**

```python
memory_store(
    "Chose JWT over session cookies for auth_service — stateless horizontal scaling",
    kind="decision",
    entities=["auth_service"],
    confidence=0.9,
    rationale="Stateless tokens enable horizontal scaling without shared session store.",
    alternatives_rejected=["server-side sessions", "PASETO"],
)
```

**5. Recall in any future session**

```python
memory_recall("project context", budget_tokens=400)
```

Output:
```
## Memory recall: "project context" (as of 2026-07-05 · 6 items · 171/400 tokens)

### Decisions
- [d_0019f2] 2026-06-05 · conf 0.90 — Chose JWT for auth_service — stateless horizontal scaling
- [d_0019f4] 2026-06-12 · conf 0.95 — CockroachDB replaces Postgres for geo-distributed writes

### Facts
- [f_0019f3] 2026-06-05 · conf 1.00 — auth_service issues 15-min access tokens with rotating refresh
- [f_0019f7] 2026-06-19 · conf 1.00 — payment_service ~8k txn/day at p99 < 200ms

### Procedures
- [p_0019f5] 2026-06-12 · conf 1.00 — Deploy: GitHub Actions → staging auto → prod manual approval

### Preferences
- [pr_0019f6] 2026-06-12 · conf 1.00 — All new services must expose /health and /metrics endpoints
```

### Token Efficiency: Memory vs. Paste

| Approach | Tokens per session | After 20 sessions |
|----------|-------------------|-------------------|
| Manual paste (architecture doc) | ~2,400 | ~48,000 |
| Manual paste (recent notes) | ~800 | ~16,000 |
| `memory_recall` | **~171** | **~3,420** |
| **Savings** | — | **93% fewer tokens** |

### Seeding From Existing Notes

Load your decision log or conventions in one pass:

```python
from nervapack.memory import MemoryStore

store = MemoryStore()
decisions = [
    ("Chose JWT for auth_service — stateless scaling", "decision", ["auth_service"]),
    ("CockroachDB replaces Postgres for geo-distributed writes", "decision", ["database"]),
    ("All new services must expose /health and /metrics", "preference", []),
    ("Deploy via GitHub Actions → staging → manual prod approval", "procedure", []),
]
for content, kind, entities in decisions:
    nid = store.add_node(kind=kind, content=content, confidence=1.0)
    print(f"Seeded [{nid}] {content[:50]}")
```

### Data Model

**8 node kinds:** `fact`, `decision`, `action`, `outcome`, `entity`, `procedure`, `preference`, `session`

**7 edge kinds:** `ABOUT`, `OCCURRED_IN`, `SUPERSEDES`, `CONTRADICTS`, `CAUSED`, `DERIVED_FROM`, `TOUCHES`

**Bi-temporal:** every node has `valid_from`/`valid_until` (world-time) and `recorded_at` (learn-time). Supersede closes the old window; rows are never deleted in normal operation.

```
d_aaa  "session cookies"  valid_from=2026-01-01  valid_until=2026-06-01
  └─[SUPERSEDES]
d_bbb  "JWT"              valid_from=2026-06-01  valid_until=NULL (current)

memory_recall("auth")              → returns d_bbb only (current truth)
memory_recall("auth", as_of=...)  → returns d_aaa only (point-in-time)
memory_timeline("auth")           → returns both (d_aaa marked [superseded])
```

### MCP Tools (15 total)

| Tool | Purpose |
|------|---------|
| `memory_start_session` | Open a named session (e.g. "JWT refactor") |
| `memory_store` | Persist a fact, decision, outcome, procedure, preference, or action |
| `memory_recall` | FTS5 search → graph expansion → scored, budget-capped recall |
| `memory_about` | Entity dossier: all current facts/decisions linked to one entity |
| `memory_why` | Explain a decision: rationale, rejected alternatives, caused outcomes |
| `memory_timeline` | Chronological trace including superseded versions |
| `memory_end_session` | Close session with an outcome summary + queues consolidation |
| `memory_forget` | Tombstone (soft) or hard-purge nodes |
| `memory_verify` | `confirm` → confidence +0.1; `refute` → close + confidence ×0.5 |
| `memory_list_sessions` | List all sessions with node counts |
| `memory_clear_session` | Delete a session and all its nodes |
| `memory_stats` | Node counts, DB size, top entities by degree |
| `memory_for_code` | Memories that TOUCH a source file (optionally at a line) |
| `memory_to_code` | Code locations a memory node TOUCHES (file, line range, type) |
| `memory_import` | Bulk-seed memory from a JSON array of node specs |

### Recall Pipeline

```
query
  ├─ 1. FTS5 BM25 search (exact → prefix* → OR fallback)
  ├─ 2. Graph expansion (0.6× relevance decay per hop, up to 2 hops)
  ├─ 3. Temporal mask (exclude superseded, tombstoned, out-of-window)
  ├─ 4. Confidence filter (min_confidence threshold, default 0.0)
  ├─ 5. Score: relevance × recency × frequency × connectivity
  └─ 6. Budget pack (greedy fill, hard invariant: result ≤ budget_tokens)
```

### CLI

```bash
nervapack-memory init                             # create schema
nervapack-memory start-session "Task name"        # open a named session
nervapack-memory stats                            # counts + top entities
nervapack-memory sessions                         # list all sessions
nervapack-memory search "JWT auth"               # FTS search
nervapack-memory show f_0019f2...                 # inspect a node
nervapack-memory forget --node-id f_0019f2...    # tombstone
nervapack-memory forget --entity old_svc --purge # hard-delete
nervapack-memory export --out dump.json           # JSON dump
nervapack-memory import seed.json                 # bulk seed from JSON file
nervapack-memory consolidate                      # deduplicate pending session facts
nervapack-memory consolidate --dry-run            # preview without changes
```

### Storage

| Path | When used |
|------|-----------|
| `.nervapack/memory.db` | Default when `.nervapack/` dir exists |
| `~/.nervapack/memory.db` | Global fallback (created automatically) |
| `$NERVAPACK_MEMORY_DB` | Override via environment variable |

### Combined With the Code Graph

Used together, the two NervaPack servers cover the full context problem:

```
nervapack-mcp (code graph)          nervapack-memory-mcp (agent memory)
────────────────────────────        ──────────────────────────────────────
"How does auth_service work?"  +    "Why was JWT chosen for auth_service?"
"Which functions call login()?"     "What did we decide last sprint?"
"What does this class import?"      "What's the deploy procedure?"
↓                                   ↓
AST-precise, 91% token reduction    Decision-precise, budget-capped recall
```

### Design

- **Standalone SQLite + FTS5** — the code graph (NetworkX + ChromaDB) is immutable between ingest cycles and has no temporal semantics. A separate SQLite file is the right substrate for mutable, session-scoped memory.
- **Facts, not chunks** — recall returns atomic assertions (8–30 tokens each) with provenance, not transcript segments.
- **Bi-temporal, never delete** — supersede closes the old `valid_until`; only `memory_forget(purge=True)` hard-deletes.
- **No network at runtime** — all storage, search, and scoring is local. No embeddings at query time.
- **Hard token invariant** — `pack()` guarantees the result always fits in `budget_tokens`. No surprises.

---

## Contributing

1. Fork the repo and create a branch.
2. Make your changes with tests where applicable.
3. Open a pull request against `master`.

Bug reports and feature requests go to the [issue tracker](https://github.com/ramdhavepreetam/NervaPack/issues).

---

## License

MIT — see [LICENSE](LICENSE).
