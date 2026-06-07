# NervaPack

[![PyPI version](https://img.shields.io/pypi/v/nervapack.svg)](https://pypi.org/project/nervapack/)
[![Python Versions](https://img.shields.io/pypi/pyversions/nervapack.svg)](https://pypi.org/project/nervapack/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NervaPack** is a privacy-first, offline knowledge graph for your codebase. It solves two fundamental problems with standard Vector RAG:

- **Token waste** — chunk-based RAG retrieves blobs of text that may only tangentially relate to your query, bloating your context window.
- **Privacy risk** — sending code to cloud embedding APIs leaks your proprietary logic.

NervaPack runs 100% on your machine. It uses `tree-sitter` to parse your codebase into a deterministic Abstract Syntax Tree graph, then uses a local Ollama model to draw hard semantic edges between your documentation and your code. Queries traverse this graph with a K-Hop BFS, returning a hyper-targeted, token-efficient context window — no cloud required.

---

## Why NervaPack vs. standard Vector RAG

| | Standard Vector RAG | NervaPack |
|---|---|---|
| **Parsing** | Arbitrary text chunks | Deterministic AST nodes (class, function, import) |
| **Retrieval** | Nearest-neighbor blob | K-Hop BFS on a structural graph |
| **Doc ↔ Code links** | None | Hard `EXPLAINS` edges drawn by local LLM |
| **Privacy** | Cloud embeddings | 100% local (ChromaDB + Ollama) |
| **Incremental sync** | Re-index everything | Surgical per-file update via GitPython diff |

---

## Prerequisites

- **Python 3.10+**
- **Ollama** — install from [ollama.com](https://ollama.com/), then pull a model:
  ```bash
  ollama pull llama3
  ```
  NervaPack defaults to `llama3`. Any model that can follow instructions works.
- **Git** — your project must be a git repository (`git init` if not).

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

> On first run, `chromadb` downloads `onnxruntime` embedding models to your cache and `tree-sitter` compiles its language bindings. This is a one-time setup (~1–2 min).

---

## Quick Start

```bash
cd your-project/

# 1. Build the knowledge graph (run once)
nervapack ingest .

# 2. Query for context
nervapack query "How does authentication work?"

# 3. After modifying files, sync the graph incrementally
nervapack sync .

# 4. Check graph health
nervapack status
```

---

## Command Reference

### `nervapack ingest [PATH]`

Scans `PATH` (default: `.`) and builds the full knowledge graph.

What happens:
1. `tree-sitter` parses all `.py`, `.js`, `.jsx`, `.ts`, `.tsx` files into Classes, Functions, and Imports — exact AST nodes, not text chunks.
2. All `.md` files are chunked by header hierarchy.
3. Each Markdown chunk is sent to your local Ollama model. If the model identifies a code entity the prose explains, a hard `EXPLAINS` edge is written into the graph.
4. All nodes are embedded and stored in a local ChromaDB instance (`.nervapack/chroma_db`).

> The initial LLM binding pass is the slowest step. On a large repo with many docs, budget several minutes.

---

### `nervapack query PROMPT`

Retrieves context from the graph for a natural-language prompt.

What happens:
1. The prompt is embedded and ChromaDB returns the top-3 most semantically similar nodes.
2. Those nodes seed a K-Hop Breadth-First Search (default `max_hops=1`) through the NetworkX graph.
3. Adjacent nodes — including any Markdown docs linked via `EXPLAINS` edges — are collected into a compressed Markdown snippet and printed to your terminal.

The output is designed to be pasted directly into an LLM prompt as context.

---

### `nervapack sync [PATH]`

Incrementally updates the graph for files changed since the last ingest.

What happens:
1. `GitPython` diffs your working tree to find modified and deleted files.
2. For each changed file, old graph nodes and ChromaDB vectors are pruned.
3. Only the changed files are re-parsed and re-ingested.

A full `ingest` on a large codebase can take minutes. `sync` turns that into a 2–5 second surgical update.

---

### `nervapack status`

Prints the current state of the graph: node count, edge count, and any files that are out of sync with the graph.

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
       ├─ ASTParser (tree-sitter)
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
       └─ GraphRetriever.retrieve_context() → BFS subgraph → Markdown
```

**Storage layout** (inside your project root):
```
.nervapack/
├── graph.graphml       # NetworkX graph (deterministic structure)
└── chroma_db/          # ChromaDB (semantic embeddings)
```

**Source modules:**
| Module | Responsibility |
|---|---|
| `nervapack.parser.ast_parser` | Tree-sitter parsing → `ParsedEntity` objects |
| `nervapack.parser.md_chunker` | Markdown → header-delimited chunks |
| `nervapack.graph.builder` | Build and persist the NetworkX DiGraph |
| `nervapack.graph.vector_store` | ChromaDB ingest and semantic search |
| `nervapack.graph.retrieval` | K-Hop BFS context extraction |
| `nervapack.llm.summarizer` | Local Ollama interface for LLM binding |
| `nervapack.git.tracker` | GitPython diff for incremental sync |

---

## Privacy

NervaPack is 100% offline. No code, documentation, or query ever leaves your machine:

- Embeddings are generated by ChromaDB's built-in local model.
- LLM calls go exclusively to `localhost:11434` (your Ollama instance).
- All graph and vector data is stored in `.nervapack/` inside your project.

Add `.nervapack/` to your `.gitignore` to keep it out of version control.

---

## Contributing

1. Fork the repo and create a branch.
2. Make your changes with tests where applicable.
3. Open a pull request against `master`.

Bug reports and feature requests go to the [issue tracker](https://github.com/ramdhavepreetam/NervaPack/issues).

---

## License

MIT — see [LICENSE](LICENSE).
