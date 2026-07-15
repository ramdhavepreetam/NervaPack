# NervaPack

[![PyPI version](https://img.shields.io/pypi/v/nervapack.svg)](https://pypi.org/project/nervapack/)
[![Python Versions](https://img.shields.io/pypi/pyversions/nervapack.svg)](https://pypi.org/project/nervapack/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Token Reduction](https://img.shields.io/badge/Token_Reduction-91.2%25-brightgreen.svg)](docs/BENCHMARKS.md)
[![Verified](https://img.shields.io/badge/Performance-Verified-blue.svg)](docs/BENCHMARKS.md)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-listed-blue.svg)](https://registry.modelcontextprotocol.io)

<!-- mcp-name: io.github.ramdhavepreetam/nervapack -->

**NervaPack** is a privacy-first, offline knowledge graph for your codebase. It solves two fundamental problems with standard Vector RAG:

- **Token waste** — chunk-based RAG retrieves blobs of text that may only tangentially relate to your query, bloating your context window.
- **Privacy risk** — sending code to cloud embedding APIs leaks your proprietary logic.

NervaPack runs 100% on your machine. It uses `tree-sitter` to parse your codebase into a deterministic Abstract Syntax Tree graph, then uses a local Ollama model to draw hard semantic edges between your documentation and your code. Queries traverse this graph with a K-Hop BFS, returning a hyper-targeted, token-efficient context window — no cloud required.

---

## Verified Performance

**91.2% Average Token Reduction** — independently verified on real-world codebases.

| Test Type | Tokens (Naive) | Tokens (NervaPack) | Reduction |
|-----------|----------------|-------------------|-----------|
| Simple Query | 10,926 | 101 | **99.1%** |
| Medium Query | 13,092 | 164 | **98.7%** |
| Complex Query | 3,290 | 1,102 | **66.5%** |
| **Average** | **52,037** | **2,459** | **91.2%** |

**Cost Savings:** $181–$724 per developer per year (GPT-4o to Claude Sonnet)

📊 **[View Full Benchmarks](docs/BENCHMARKS.md)** · 🧪 **[Messy Code Performance](docs/MESSY_CODE_PERFORMANCE.md)**

> **Code quality impact:** 90–99% reduction on clean code, 50–75% on legacy/messy code. Even poorly structured codebases benefit significantly.

---

## Why NervaPack vs. standard Vector RAG

| | Standard Vector RAG | NervaPack |
|---|---|---|
| **Parsing** | Arbitrary text chunks | Deterministic AST nodes (class, function, import) |
| **Retrieval** | Nearest-neighbour blob | K-Hop BFS on a structural graph |
| **Doc ↔ Code links** | None | Hard `EXPLAINS` edges drawn by local LLM |
| **Privacy** | Cloud embeddings | 100% local (ChromaDB + ONNX + optional Ollama) |
| **Incremental sync** | Re-index everything | Surgical per-file update via GitPython diff |
| **Token savings** | No measurement | Built-in dashboard shows exact reduction per query |
| **Graph visibility** | Black box | Interactive HTML visualization of every node and edge |
| **Duplicate-safe** | Repeated ingest = duplicate data | `upsert` — re-ingest is idempotent |
| **Agent memory** | None | 17-tool MCP server for cross-session memory |

---

## Prerequisites

- **Python 3.10+**
- **Git** — your project must be a git repository (`git init` if not)

*(Optional for semantic code-doc binding)* — an LLM provider. Structural graph indexing and basic queries work out-of-the-box with zero configuration and no cloud connection.

| Provider | Setup | Cost | Privacy |
|----------|-------|------|---------|
| **Ollama** (default) | `brew install ollama && ollama pull llama3` | Free | 100% local |
| **Claude API** | `pip install "nervapack[claude]"` + `ANTHROPIC_API_KEY` | ~$0.25/1k calls | Cloud |
| **OpenAI API** | `pip install "nervapack[openai]"` + `OPENAI_API_KEY` | ~$0.15/1k calls | Cloud |
| **MCP (Claude Code)** | Zero config | Included in subscription | Cloud |

---

## Installation

```bash
# Recommended
pip install nervapack

# With optional features
pip install "nervapack[mcp]"          # MCP server for Claude Code / Cursor
pip install "nervapack[memory]"       # agent memory MCP server
pip install "nervapack[metrics]"      # exact token counts (tiktoken)
pip install "nervapack[dashboard]"    # web dashboard (streamlit + plotly)
pip install "nervapack[claude]"       # Claude API support
pip install "nervapack[openai]"       # OpenAI API support
pip install "nervapack[all]"          # everything
```

> On first run, ChromaDB downloads an ONNX embedding model (~30 MB) to `~/.cache/chroma/`. This is a one-time download.

---

## Quick Start

```bash
cd your-project/

# 1. Build the knowledge graph (runs locally, no LLM required for basic use)
nervapack ingest .

# 2. Query for context — get focused results + token savings dashboard
nervapack query "How does authentication work?"

# 3. Add semantic doc-to-code edges (requires an LLM)
nervapack enrich .

# 4. Visualize the full graph
nervapack visualize --enhanced --communities

# 5. After changing files, sync incrementally (fast — only changed files)
nervapack sync .

# 6. If you ingested wrong data or need a fresh start
nervapack clean --all
nervapack ingest .

# 7. Check system health
nervapack doctor
```

---

## Command Reference

### `nervapack ingest [PATH]` — Build the graph

Scans `PATH` (default: `.`) and builds the full knowledge graph.

**What happens:**
1. Walks the directory tree with tree-sitter, skipping `dist/`, `build/`, `node_modules/`, `venv/`, `site/`, `.tox/`, and dozens of other build directories automatically.
2. Parses source files into exact AST nodes: classes, functions, imports.
3. Chunks all `.md` files by header hierarchy.
4. Embeds every entity into a local ChromaDB vector store (ONNX by default, Ollama optional).
5. Optionally binds doc chunks to code nodes via an LLM, adding `EXPLAINS` edges.
6. Saves the graph once to `.nervapack/graph.graphml`.

**Re-ingesting is safe** — `upsert` is used throughout, so running `ingest` twice does not duplicate data.

```bash
nervapack ingest .                           # auto-detect LLM
nervapack ingest . --llm ollama              # force Ollama
nervapack ingest . --llm claude              # use Claude API
nervapack ingest . --llm openai --model gpt-4o-mini
nervapack ingest . --embeddings ollama       # use Ollama for embeddings too
```

**Supported languages (bundled):** Python, JavaScript, JSX, TypeScript, TSX

**Additional languages:**
```bash
pip install "nervapack[go]"            # Go
pip install "nervapack[rust]"          # Rust
pip install "nervapack[java]"          # Java
pip install "nervapack[c]"             # C / C headers
pip install "nervapack[cpp]"           # C++
pip install "nervapack[ruby]"          # Ruby
pip install "nervapack[csharp]"        # C#
pip install "nervapack[all-languages]" # all of the above
```

**Exclude directories** — create `.nervapackignore` in your project root (gitignore syntax):
```
dist/
build/
site/
generated/
*.egg-info/
```

---

### `nervapack query PROMPT` — Query the graph

Retrieves focused context for a natural-language prompt and prints a token savings dashboard.

**What happens:**
1. Intent detection — "what breaks if I change X" routes to impact analysis (reverse BFS); exact symbol names bypass vector search.
2. ChromaDB returns the top-3 most semantically similar nodes.
3. Those nodes seed a K-Hop BFS through the NetworkX graph (default: 1 hop, both directions).
4. Adjacent nodes — including any markdown docs via `EXPLAINS` edges and memory notes via `TOUCHES` edges — are collected.
5. A focused Markdown context block is printed, ready to paste into an LLM prompt.
6. Token efficiency panel shows savings vs. naive "dump the whole file" RAG.

```bash
nervapack query "How does authentication work?"
nervapack query "What calls VectorStore?"
nervapack query "what breaks if I change GraphBuilder"  # impact analysis
```

**Example output:**
```
Query: "How does authentication work?"

Query Router: Intent: semantic, Direction: both
Vector Search: Found 3 seed nodes

Retrieved Context:
──────────────────────────────────────────────────────────
# NervaPack Context Retrieval
## File: `src/auth/middleware.py`
### CLASS: AuthMiddleware (L15-L42)
...
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

---

### `nervapack sync [PATH]` — Incremental update

Updates only the files that changed since the last ingest. Uses `GitPython` to diff the working tree.

```bash
nervapack sync .
```

A full ingest on a large project can take minutes. `sync` turns that into a 2–5 second surgical update per file. Re-parses changed files, batch-upserts new vectors, and saves the graph once at the end.

---

### `nervapack clean [OPTIONS]` — Remove ingested data

Wipe graph data and start fresh. Use this when you have duplicate vectors, ingested the wrong directory, or need to reduce disk usage.

```bash
nervapack clean --vectors          # wipe ChromaDB only (chroma_db/)
nervapack clean --graph            # delete graph.graphml only
nervapack clean --history          # clear query + graph history logs
nervapack clean --all              # everything above (keeps memory.db)
nervapack clean --all --yes        # skip confirmation (CI / scripts)
```

**Never deleted by `clean`:** `memory.db` — your agent memory is always safe.

**Typical workflow after a bad ingest:**
```bash
nervapack clean --all
nervapack ingest .
```

---

### `nervapack enrich [PATH]` — Add semantic edges

Runs LLM doc-to-code binding on an already-ingested graph. Use this if you:
- Ran `ingest` without an LLM and want to add `EXPLAINS` edges now.
- Added new documentation and want to bind it without a full re-ingest.

```bash
nervapack enrich .                           # auto-detect LLM
nervapack enrich . --llm ollama --model llama3
nervapack enrich . --llm claude              # shows cost estimate before proceeding
```

---

### `nervapack status [--detailed]` — Graph health

```bash
nervapack status            # node/edge counts + unsynced files
nervapack status --detailed # full analytics: health score, language distribution, coverage
```

Health score (0–100) factors in documentation coverage, node connectivity, graph density, and edge diversity. A structural-only graph typically scores 30–40; after `enrich` it rises to 70–90.

---

### `nervapack visualize [OPTIONS]` — Interactive HTML graph

```bash
nervapack visualize                           # basic visualization
nervapack visualize --enhanced                # + real-time search + path finder
nervapack visualize --enhanced --communities  # + community detection (Louvain)
nervapack visualize --output ~/my-graph.html  # custom output path
nervapack visualize --no-browser              # generate without opening
```

Produces a standalone HTML file with no external dependencies — drag, zoom, search, find shortest paths between nodes.

---

### `nervapack explore TARGET [--hops N]` — Focused subgraph

Extract and visualize the N-hop neighbourhood of a specific file, class, or function.

```bash
nervapack explore GraphBuilder --hops 2
nervapack explore src/auth/middleware.py --hops 1
nervapack explore "function:parse"
```

---

### `nervapack dependencies [FILE]` — Import dependency analysis

Analyze file-level import chains, detect circular dependencies, and visualize the dependency graph.

```bash
nervapack dependencies                        # full project analysis
nervapack dependencies src/graph/builder.py   # single file
nervapack dependencies --no-cycles            # skip cycle detection
```

---

### `nervapack hotspots [OPTIONS]` — Change frequency analysis

Show which files change most often in git history — prime targets for documentation and review.

```bash
nervapack hotspots                            # top 20 by commit count
nervapack hotspots --since "6 months ago"    # recent history only
nervapack hotspots --ext .py --churn         # Python files, sort by lines changed
```

---

### `nervapack history [OPTIONS]` — Query history

```bash
nervapack history              # last 10 queries with token savings
nervapack history --limit 50   # last 50
nervapack history --stats      # aggregate: total savings, cost avoided, top topics
nervapack history --clear      # delete history
```

---

### `nervapack serve [--port N]` — Web dashboard

```bash
nervapack serve                # http://localhost:8501
nervapack serve --port 8080    # custom port
```

Requires `nervapack[dashboard]`. Shows graph overview, language distribution, analytics, query history trends, and an interactive graph explorer.

---

### `nervapack doctor` — Environment check

```bash
nervapack doctor
```

Verifies Python version, tree-sitter grammars, embedding backend, Ollama connectivity, and MCP config. Run this after installation or when troubleshooting.

---

## Storage Layout

Everything lives in `.nervapack/` inside your project root:

```
.nervapack/
├── graph.graphml          # NetworkX DiGraph (AST + EXPLAINS edges)
├── chroma_db/             # ChromaDB vector store (ONNX embeddings)
├── memory.db              # Agent memory (SQLite + FTS5, bi-temporal)
├── query_history.jsonl    # Per-query token savings log
└── graph_history.jsonl    # Ingest/sync event log
```

Add `.nervapack/` to `.gitignore` to keep it out of version control.

**Disk usage guide:**
- `chroma_db/` — typically 10–100 MB depending on project size. Run `nervapack clean --vectors && nervapack ingest .` if it grows unexpectedly.
- `graph.graphml` — typically 0.5–5 MB.
- `memory.db` — grows with agent usage; rarely exceeds a few MB.

---

## MCP Integration (Claude Code, Cursor, Windsurf)

NervaPack ships two MCP servers in the same package. Drop this `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph (v0.6.1) — query, graph_status, explore, impact"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory (v0.6.1) — store, recall, and reason over facts across sessions"
    }
  }
}
```

### Knowledge Graph MCP tools (`nervapack-mcp`)

| Tool | What it does |
|------|-------------|
| `query` | Vector search → K-Hop BFS → focused Markdown context + token savings |
| `graph_status` | Node/edge counts, language breakdown, unsynced file warnings |
| `explore` | Browse all indexed classes, functions, imports, markdown docs |
| `impact` | Reverse dependency analysis — find what depends on a given entity |

### Agent Memory MCP tools (`nervapack-memory-mcp`) — 17 tools

| Tool | Purpose |
|------|---------|
| `memory_start_session` | Open a named session |
| `memory_store` | Persist a fact, decision, outcome, procedure, preference, or action |
| `memory_recall` | FTS5 search → graph expansion → scored, budget-capped recall |
| `memory_about` | Entity dossier: all facts/decisions linked to one entity |
| `memory_why` | Explain a decision: rationale, rejected alternatives, outcomes |
| `memory_timeline` | Chronological trace including superseded versions |
| `memory_end_session` | Close session with an outcome summary |
| `memory_forget` | Tombstone or hard-purge nodes |
| `memory_verify` | Confirm (confidence +0.1) or refute (close + confidence ×0.5) |
| `memory_stats` | Node counts, DB size, top entities, all namespaces |
| `memory_list_sessions` | List all sessions with node counts |
| `memory_clear_session` | Delete a session and all its nodes |
| `memory_for_code` | Memories that TOUCH a source file or specific line |
| `memory_to_code` | Code locations a memory node TOUCHES |
| `memory_import` | Bulk-seed memory from a JSON array |
| `memory_switch_namespace` | Switch the active namespace |
| `memory_verify_staleness` | Flag memories whose source file changed since stored |

### CLAUDE.md template

Add to your `CLAUDE.md` to wire NervaPack into every Claude Code session:

```markdown
## Always use NervaPack MCP tools

At the start of every session:
1. Call `memory_start_session("<task name>")` to open a named session.
2. Call `memory_recall("project context", budget_tokens=400)` to load prior decisions.
3. Call `query("<topic>")` before answering any question about how the code works.

During the session — call `memory_store` for:
- Any decision made (kind="decision" with rationale and alternatives_rejected)
- Any fact discovered about system behaviour (kind="fact")
- Any procedure or convention established (kind="procedure")

At session end — call `memory_end_session("<one-paragraph summary>")`.
```

---

## Architecture

```
nervapack ingest .
       │
       ├─ ASTParser (tree-sitter)               16 extensions, 10 languages
       │    └─ ParsedEntity[]: class, function, import
       │
       ├─ GraphBuilder (NetworkX DiGraph)
       │    ├─ Nodes: file, class, function, import, markdown
       │    ├─ Edges: DEFINES (AST, confidence=1.0)
       │    ├─ Edges: REFERENCES (heuristic name overlap, confidence=0.7)
       │    └─ Edges: EXPLAINS (LLM or keyword binding, confidence=0.5–0.9)
       │
       ├─ VectorStore (ChromaDB)
       │    ├─ Embedding: ONNX (default) or Ollama
       │    └─ upsert — re-ingest is idempotent
       │
       └─ GraphHistory  — snapshot recorded after each ingest/sync

nervapack query "..."
       │
       ├─ Intent detection (impact / exact / semantic)
       ├─ VectorStore.search() → seed node IDs
       ├─ GraphRetriever.retrieve_context()
       │    └─ deque BFS, direction: forward / reverse / both
       ├─ MemoryStore.get_touches_for_file() → memory context injection
       └─ TokenMeter → savings vs. naive RAG

nervapack clean --all
       └─ Deletes chroma_db/, graph.graphml, history logs
          Never touches memory.db
```

**Key source modules:**

| Module | Responsibility |
|--------|---------------|
| `nervapack.parser.ast_parser` | tree-sitter parsing → `ParsedEntity`; shared singleton parser instance |
| `nervapack.parser.md_chunker` | Markdown → header-delimited chunks; prunes build dirs from os.walk |
| `nervapack.graph.builder` | NetworkX DiGraph; O(1) file-index for sync; compiled regex for REFERENCES |
| `nervapack.graph.vector_store` | ChromaDB upsert (idempotent); pluggable embedding function |
| `nervapack.graph.retrieval` | K-Hop BFS with `deque` (O(n) not O(n²)) |
| `nervapack.graph.token_meter` | tiktoken singleton; token savings panel |
| `nervapack.graph.query_history` | Tail-read JSONL — O(limit) not O(total) |
| `nervapack.graph.analytics` | Bulk `graph.degree()` — single call not per-node loop |
| `nervapack.llm.base` | `bind_docs_to_ast` with keyword pre-filter (top-12 candidates) |
| `nervapack.llm.providers.ollama` | `ollama.list()` cached 60 s |
| `nervapack.memory.store` | SQLite + FTS5; bi-temporal; `batch_neighbors` for O(1) hop expansion |
| `nervapack.memory.recall` | Batched hop expansion; audit trail on recall |
| `nervapack.mcp_server` | FastMCP — `query`, `graph_status`, `explore`, `impact` |
| `nervapack.memory.mcp_server` | FastMCP — 17 memory tools |

---

## nervapack.memory — Agent Memory

Stop re-pasting project context into every new chat.

```python
# Store a decision
memory_store(
    "Chose JWT over session cookies for auth_service — stateless horizontal scaling",
    kind="decision",
    entities=["auth_service"],
    confidence=0.9,
    rationale="Stateless tokens enable horizontal scaling without shared session store.",
    alternatives_rejected=["server-side sessions", "PASETO"],
)

# Recall in any future session
memory_recall("project context", budget_tokens=400)
```

```
## Memory recall: "project context" (6 items · 171/400 tokens)

### Decisions
- [d_0019f2] 2026-06-05 · conf 0.90 — Chose JWT for auth_service

### Facts
- [f_0019f3] 2026-06-05 · conf 1.00 — auth_service issues 15-min access tokens

### Procedures
- [p_0019f5] 2026-06-12 · conf 1.00 — Deploy: GitHub Actions → staging → prod manual
```

**Token efficiency:**

| Approach | Tokens per session | After 20 sessions |
|----------|--------------------|-------------------|
| Manual paste (architecture doc) | ~2,400 | ~48,000 |
| `memory_recall` | **~171** | **~3,420** |
| **Savings** | | **93% fewer tokens** |

**CLI:**
```bash
nervapack-memory init                          # create schema
nervapack-memory stats                         # counts + top entities
nervapack-memory search "JWT auth"             # FTS search
nervapack-memory timeline "auth service"       # chronological trace
nervapack-memory audit d_0019f2abc             # access audit trail
nervapack-memory rebind old/path.py new/path.py  # update file links after rename
nervapack-memory export --out dump.json        # JSON dump
```

**Data model:** 8 node kinds, 7 edge kinds, bi-temporal (`valid_from`/`valid_until`), never hard-deletes by default.

---

## Privacy

NervaPack is 100% offline by default:

- Embeddings use ChromaDB's built-in ONNX model (runs on CPU, no cloud).
- LLM calls (when using Ollama) go to `localhost:11434` only.
- All graph and vector data lives in `.nervapack/` inside your project.
- No telemetry, no analytics, no network calls at runtime.

Only if you explicitly pass `--llm claude` or `--llm openai` does any code leave your machine.

---

## Contributing

1. Fork the repo and create a branch.
2. Run tests: `python3 -m pytest tests/memory/ -q`
3. Run docs check: `python3 -m mkdocs build --strict`
4. Open a pull request against `master`.

Bug reports and feature requests: [issue tracker](https://github.com/ramdhavepreetam/NervaPack/issues).

---

## License

MIT — see [LICENSE](LICENSE).
