# NervaPack - Project Knowledge Document

> **Last Updated:** 2026-06-16
> **Version:** 0.3.0
> **Status:** Active Development

---

## Project Mission

NervaPack is a **privacy-first, offline knowledge graph for codebases** that solves the fundamental problems with standard Vector RAG:

1. **Token Waste** - Chunk-based RAG retrieves entire files when only small sections are relevant, bloating LLM context windows
2. **Privacy Risk** - Cloud-based embedding APIs leak proprietary code to external services

NervaPack runs 100% locally using tree-sitter AST parsing, ChromaDB for embeddings, Ollama for LLM operations, and NetworkX for graph operations. It achieves **91.2% average token reduction** compared to naive file-dumping approaches ([verified benchmarks](docs/BENCHMARKS.md)).

---

## Current State (v0.3.0)

### Completed Features

- **Core Knowledge Graph System**
  - AST parsing for Python, JS/TS/TSX/JSX (bundled)
  - Optional language support: Go, Rust, Java, C, C++, Ruby, C#
  - NetworkX-based graph with DEFINES and EXPLAINS edges
  - ChromaDB vector storage with local embeddings
  - K-Hop BFS retrieval with token efficiency metrics

- **CLI Commands**
  - `ingest` - Build knowledge graph from source files
  - `query` - Retrieve focused context with token savings dashboard
  - `sync` - Incremental git-based updates (O(changed files))
  - `visualize` - Interactive HTML graph visualization (pyvis)
  - `status` - Graph health checks and sync status

- **MCP Server Integration** (v0.2.0+)
  - Exposes `query_codebase`, `graph_status`, `list_entities` tools
  - Compatible with Claude Code, Cursor, and other MCP clients
  - Automatic tool discovery via `.mcp.json`

- **Token Savings Dashboard** (v0.2.0+)
  - Exact token counting with tiktoken (optional)
  - Side-by-side comparison: NervaPack vs Naive RAG
  - Cost savings calculations for GPT-4o and Claude Sonnet
  - **Verified Performance:** 91.2% average reduction across real-world queries
  - See [BENCHMARKS.md](docs/BENCHMARKS.md) for detailed test results

- **Graph Visualization** (v0.2.0+)
  - Interactive HTML export with physics simulation
  - Color-coded nodes by type (file, function, class, import, markdown)
  - Edge styling (solid DEFINES, dashed EXPLAINS)
  - Hover tooltips with code previews

### Distribution Channels

1. **PyPI** - `pip install nervapack`
2. **Homebrew** - `brew install ramdhavepreetam/nervapack/nervapack`
3. **pipx** - `pipx install nervapack` (recommended for CLI tools)

---

## Technical Architecture

### High-Level Data Flow

```
Source Code + Docs
        ↓
    [Parser Layer]
    ├─ ASTParser (tree-sitter) → ParsedEntity[]
    └─ MDChunker (header-based) → Chunk[]
        ↓
    [Storage Layer]
    ├─ GraphBuilder (NetworkX) → .nervapack/graph.graphml
    └─ VectorStore (ChromaDB) → .nervapack/chroma_db/
        ↓
    [Semantic Layer]
    LLMSummarizer (Ollama) → EXPLAINS edges
        ↓
    [Retrieval Layer]
    GraphRetriever (K-Hop BFS) → Focused Context
        ↓
    [Presentation Layer]
    ├─ CLI (Rich formatted output)
    ├─ MCP Server (JSON-RPC tools)
    └─ Visualizer (Interactive HTML)
```

### Graph Schema

**Nodes:**
- `file:<path>` - Source files
- `function:<path>:<name>:<line>` - Function definitions
- `class:<path>:<name>:<line>` - Class definitions
- `import:<path>:import_<line>:<line>` - Import statements
- `md_<path>_<index>` - Markdown documentation chunks

**Edges:**
- `DEFINES` - Structural relationship (file → entity)
- `EXPLAINS` - Semantic relationship (markdown → code, LLM-drawn)

### Storage Layout

```
.nervapack/
├── graph.graphml       # NetworkX DiGraph (GraphML format)
├── graph.html          # Interactive visualization (regenerable)
└── chroma_db/          # ChromaDB persistent storage
    ├── chroma.sqlite3  # Metadata database
    └── [ONNX models]   # Local embedding models
```

### Module Organization

```
src/nervapack/
├── cli.py                  # Main CLI entry point (Typer)
├── mcp_server.py           # MCP server (JSON-RPC tools)
├── parser/
│   ├── language_registry.py   # Declarative language configs
│   ├── ast_parser.py          # Tree-sitter AST extraction
│   └── md_chunker.py          # Markdown header-based chunking
├── graph/
│   ├── builder.py             # NetworkX graph construction
│   ├── vector_store.py        # ChromaDB wrapper
│   ├── retrieval.py           # K-Hop BFS context extraction
│   ├── token_meter.py         # Token counting & savings metrics
│   └── visualizer.py          # pyvis HTML export
├── llm/
│   └── summarizer.py          # Ollama integration for EXPLAINS edges
└── git/
    └── tracker.py             # GitPython change detection
```

---

## Key Algorithms

### 1. Ingest Pipeline

```python
# High-level pseudocode
entities = ASTParser.scan_directory(path)  # Parse all code files
chunks = MDChunker.scan_directory(path)    # Parse all .md files

graph = GraphBuilder()
graph.build_from_entities(entities)        # Create nodes + DEFINES edges

vector_store = VectorStore()
vector_store.ingest_ast_entities(entities) # Embed code nodes
vector_store.ingest_chunks(chunks)         # Embed markdown chunks

# Semantic binding (slowest step)
for chunk in chunks:
    matched_entities = LLMSummarizer.bind_docs_to_ast(chunk, entities)
    for entity_id in matched_entities:
        graph.add_edge(chunk.id, entity_id, relation="EXPLAINS")

graph.save_graph(".nervapack/graph.graphml")
```

**Time Complexity:** O(files × LLM_latency) for initial ingest
**Space Complexity:** O(AST nodes + doc chunks)

### 2. Sync Pipeline

```python
# Git-based incremental update
changed_files = GitTracker.get_changed_files()

for file in changed_files:
    # Prune old data
    graph.remove_nodes_for_file(file)
    vector_store.delete_by_file(file)

    # Re-ingest only changed files
    if file.endswith(('.py', '.js', '.ts', '.tsx')):
        entities = ASTParser.parse_file(file)
        graph.add_entities(entities)
        vector_store.ingest_ast_entities(entities)
    elif file.endswith('.md'):
        chunks = MDChunker.chunk_file(file)
        vector_store.ingest_chunks(chunks)
        # Re-run LLM binding for this doc
        LLMSummarizer.bind_docs_to_ast(chunks, graph.get_all_entities())

graph.save_graph()
```

**Time Complexity:** O(changed_files × LLM_latency)
**Key Optimization:** Only processes git-modified files, not entire repo

### 3. Query Pipeline

```python
# K-Hop BFS retrieval
seed_ids = vector_store.search(query, n_results=3)  # Top-3 semantic matches
subgraph = graph_retriever.retrieve_context(seed_ids, max_hops=1)
context_markdown = graph_retriever.format_as_markdown(subgraph)

# Token efficiency calculation
naive_tokens = sum(file.total_tokens for file in subgraph.source_files)
nervapack_tokens = count_tokens(context_markdown)
savings = (naive_tokens - nervapack_tokens) / naive_tokens
```

**Key Parameters:**
- `n_results=3` - Number of seed nodes from vector search
- `max_hops=1` - BFS depth (0=seeds only, 1=seeds+neighbors, 2=2-hop, etc.)

---

## Development Guidelines

### Code Quality Standards

1. **Type Hints** - Use Python type hints for all public APIs
2. **Docstrings** - Document all modules, classes, and public functions
3. **Error Handling** - Graceful degradation (e.g., fallback to character-based token counting if tiktoken unavailable)
4. **Path Handling** - Always use absolute paths internally
5. **Lazy Loading** - Tree-sitter parsers loaded on-demand to reduce startup time

### Testing Strategy

- Unit tests for core algorithms (AST parsing, graph building, retrieval)
- Integration tests for full pipelines (ingest → query)
- Test fixtures for multiple languages
- Mock Ollama responses to avoid LLM latency in tests

### Performance Optimization

1. **Incremental Sync** - Git-based change detection reduces re-indexing from O(repo) to O(changed)
2. **Lazy Parser Loading** - Tree-sitter grammars loaded only for languages encountered
3. **Batched Embeddings** - ChromaDB handles batching internally
4. **GraphML Persistence** - NetworkX serialization is fast and deterministic

### Security Considerations

- **Privacy First** - No cloud API calls, all processing local
- **Data Isolation** - `.nervapack/` directory contains all artifacts, can be gitignored
- **No Credentials** - No API keys or tokens required
- **Local Ollama** - LLM runs on localhost:11434, user-controlled

---

## Known Limitations & Future Work

### Current Limitations

1. **LLM Binding Latency** - Initial ingest is slow due to LLM calls for EXPLAINS edges
   - Mitigation: Only runs once; sync is much faster

2. **Language Support** - Core languages bundled, others require extras
   - Future: Auto-detect and suggest missing language extras

3. **Graph Scalability** - NetworkX in-memory graph may struggle with 100K+ node repos
   - Future: Consider graph database (Neo4j, DuckDB) for very large codebases

4. **Embedding Model** - ChromaDB's default model may not be optimal for code
   - Future: Allow custom embedding models

5. **No Cross-Repo Analysis** - Each repo is isolated
   - Future: Multi-repo knowledge graphs with cross-repo IMPORTS edges

### Roadmap Ideas

#### Short-term (v0.4.0)
- [ ] Improve LLM binding prompt for better EXPLAINS edge quality
- [ ] Add `--model` CLI flag to override default Ollama model
- [ ] Support for additional file types (YAML, JSON, TOML config files)
- [ ] Parallel LLM binding for faster ingest
- [ ] Better error messages and user guidance

#### Medium-term (v0.5.0)
- [ ] Custom embedding model support (e.g., CodeBERT, StarCoder)
- [ ] Query optimization: cache frequent queries
- [ ] Graph diffing: visualize changes between commits
- [ ] Export formats: JSON, CSV, GraphQL API
- [ ] VS Code extension using MCP server

#### Long-term (v1.0.0)
- [ ] Multi-repo knowledge graphs
- [ ] Call graph analysis (CALLS edges)
- [ ] Dependency graph analysis (IMPORTS edges)
- [ ] Temporal analysis: "How did this function evolve?"
- [ ] AI-powered refactoring suggestions
- [ ] Integration with GitHub/GitLab for PR context

---

## MCP Server Integration

### Setup for Claude Code / Cursor

1. Install with MCP support:
   ```bash
   pip install "nervapack[mcp]"
   ```

2. Build the knowledge graph:
   ```bash
   cd your-project/
   nervapack ingest .
   ```

3. Add `.mcp.json` to project root:
   ```json
   {
     "mcpServers": {
       "nervapack": {
         "command": "nervapack-mcp",
         "description": "NervaPack knowledge graph - query_codebase, graph_status, list_entities"
       }
     }
   }
   ```

4. Reload your MCP-compatible tool (Claude Code, Cursor)

### Exposed Tools

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `query_codebase` | `prompt: str, max_hops?: int` | Semantic search → K-Hop BFS → focused context + token savings |
| `graph_status` | None | Node/edge counts, language breakdown, unsynced files warning |
| `list_entities` | `entity_type?: str, file_path?: str` | Browse all indexed classes, functions, imports, markdown |

### Workflow Integration

```
User: "How does the sync command work?"
    ↓
Claude Code automatically calls: query_codebase("sync command implementation")
    ↓
NervaPack returns:
- Focused context (1,180 tokens)
- Token savings summary (90.8% reduction vs 12,840 naive tokens)
    ↓
Claude Code answers with exact file:line citations
```

---

## Token Efficiency Metrics

### Real-World Performance

Based on typical NervaPack queries on medium-sized repos (1K-10K LOC):

| Metric | Naive RAG | NervaPack | Savings |
|--------|-----------|-----------|---------|
| **Tokens per query** | 8,000-15,000 | 800-1,500 | 85-92% |
| **Context precision** | Low (whole files) | High (focused snippets) | N/A |
| **Cost per 1000 queries (GPT-4o)** | $20-37.50 | $2-3.75 | $18-34 |
| **Cost per 1000 queries (Claude Sonnet)** | $24-45 | $2.40-4.50 | $21.60-40.50 |

### Token Counting Methods

1. **Exact** (with `tiktoken`):
   ```python
   import tiktoken
   enc = tiktoken.encoding_for_model("gpt-4")
   tokens = len(enc.encode(text))
   ```

2. **Estimated** (fallback):
   ```python
   tokens = len(text) / 4  # Conservative character-based estimate
   ```

Install exact counting: `pip install "nervapack[metrics]"`

---

## Configuration & Customization

### Ollama Model Selection

Default model is `llama3`. To change:

```python
# src/nervapack/llm/summarizer.py
class LLMSummarizer:
    def __init__(self):
        self.model = "phi3"  # or "mistral", "codellama", etc.
```

Or set via environment variable (future feature):
```bash
NERVAPACK_MODEL=phi3 nervapack ingest .
```

### Ollama Host

Default: `http://localhost:11434`

Override with environment variable:
```bash
OLLAMA_HOST=http://my-server:11434 nervapack query "..."
```

### Custom Exclusions

Currently hardcoded in `ast_parser.py`:
```python
SKIP_DIRS = {'.git', 'node_modules', 'venv', '__pycache__', '.nervapack'}
```

Future: Support `.nervapackignore` file

---

## Troubleshooting

### Common Issues

1. **"Ollama not found"**
   - Install Ollama: https://ollama.com/
   - Start Ollama service: `ollama serve`
   - Pull a model: `ollama pull llama3`

2. **"No module named 'tree_sitter_python'"**
   - First run downloads and compiles tree-sitter grammars
   - Takes 1-2 minutes
   - Requires internet connection once

3. **"Graph not found"**
   - Run `nervapack ingest .` before querying
   - Check `.nervapack/graph.graphml` exists

4. **Slow ingest**
   - LLM binding is the bottleneck (hundreds of Ollama calls)
   - Use faster models: `phi3`, `tinyllama`
   - Future: Parallel LLM calls

5. **Out of sync warnings**
   - Run `nervapack sync .` after modifying files
   - Or re-run `nervapack ingest .` (slower)

---

## Contributing

### Development Setup

```bash
# Clone repo
git clone https://github.com/ramdhavepreetam/NervaPack.git
cd NervaPack

# Install in editable mode with all extras
pip install -e ".[dev,metrics,mcp,all-languages]"

# Run tests (future)
pytest tests/

# Build and test locally
nervapack ingest .
nervapack query "How does the parser work?"
```

### Pull Request Checklist

- [ ] Code follows existing style (type hints, docstrings)
- [ ] Tests added for new features
- [ ] Documentation updated (README.md, KNOWLEDGE.md, architecture.md)
- [ ] Version bumped in `pyproject.toml` if necessary
- [ ] Changelog entry added

### Areas for Contribution

1. **Language Support** - Add new tree-sitter grammars
2. **Performance** - Optimize LLM binding, graph traversal
3. **Visualization** - Enhance graph rendering (3D? Timeline?)
4. **Integrations** - VS Code, JetBrains IDEs, GitHub Actions
5. **Testing** - Expand test coverage
6. **Documentation** - Tutorials, case studies, blog posts

---

## Project Context & History

### Version History

- **v0.1.0** (Initial Release)
  - Core AST parsing for Python, JS/TS
  - Basic graph building and vector storage
  - CLI commands: ingest, query

- **v0.2.0** (Visualization & Token Metrics)
  - Interactive graph visualization (pyvis)
  - Token savings dashboard with cost calculations
  - Improved Markdown chunking

- **v0.3.0** (MCP Integration - Current)
  - MCP server for Claude Code / Cursor integration
  - Tools: `query_codebase`, `graph_status`, `list_entities`
  - Packaging improvements (Homebrew tap, pipx support)

### Design Philosophy

1. **Privacy First** - No cloud dependencies, 100% local processing
2. **Deterministic Parsing** - AST-based, not heuristic text chunking
3. **Incremental Everything** - Sync, not full re-indexing
4. **Token Efficiency** - Measure and optimize for LLM context costs
5. **Graph-Native** - Structural relationships matter, not just embeddings
6. **Developer Experience** - Beautiful CLI output, interactive visualizations

### Inspiration & Related Work

- **Vector RAG** - Standard approach, but wasteful and privacy-leaking
- **Tree-sitter** - Fast, incremental parsers for every language
- **NetworkX** - Python graph library, perfect for code analysis
- **ChromaDB** - Local-first vector database
- **Ollama** - Local LLM inference, privacy-preserving
- **MCP** - Model Context Protocol by Anthropic, enables tool integrations

---

## Questions & Answers

### Why not just use vector embeddings?

Embeddings alone can't capture structural relationships (e.g., "this function is defined in this file"). Graph edges encode these relationships explicitly, and K-Hop BFS ensures we retrieve structurally adjacent nodes, not just semantically similar ones.

### Why local LLM instead of GPT-4?

Privacy. Many developers work on proprietary codebases that can't be sent to cloud APIs. Ollama runs entirely on your machine, so your code never leaves.

### Why NetworkX instead of a graph database?

Simplicity and portability. NetworkX graphs serialize to GraphML, a standard format. For repos with <100K nodes, in-memory graphs are fast enough. For larger repos, we may add Neo4j/DuckDB support in the future.

### Why tree-sitter instead of regex/AST modules?

Tree-sitter is fast, incremental, and supports 40+ languages with a unified API. Python's `ast` module only works for Python, and regex-based parsing is fragile.

### Can I use NervaPack on private repos?

Yes! That's the entire point. Everything runs locally. Just add `.nervapack/` to your `.gitignore` to keep the knowledge graph out of version control.

---

## Contact & Resources

- **GitHub:** https://github.com/ramdhavepreetam/NervaPack
- **PyPI:** https://pypi.org/project/nervapack/
- **Issues:** https://github.com/ramdhavepreetam/NervaPack/issues
- **Discussions:** https://github.com/ramdhavepreetam/NervaPack/discussions

---

**Last Updated:** 2026-06-16
**Maintained by:** Preetam Ramdhas
**License:** MIT
