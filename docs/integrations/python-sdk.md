# Python SDK

Embed NervaPack's knowledge graph and memory capabilities directly in your Python code — no CLI required.

---

## Installation

```bash
pip install nervapack
```

---

## Quick Example

```python
from nervapack.parser.ast_parser import scan_directory
from nervapack.graph.builder import GraphBuilder
from nervapack.graph.vector_store import VectorStore
from nervapack.graph.retrieval import GraphRetriever

# 1. Parse a codebase into entities
entities = scan_directory("./my_project")

# 2. Build and save the graph
builder = GraphBuilder()
graph = builder.build_from_entities(entities)
builder.save_graph()

# 3. Embed entities into ChromaDB
vstore = VectorStore()
entity_dicts = [
    {"id": e.name, "content": e.content, "file_path": e.file_path}
    for e in entities
]
vstore.ingest_ast_entities(entity_dicts)

# 4. Query
results = vstore.search("authentication middleware", n_results=3)
seed_ids = results["ids"][0]

retriever = GraphRetriever(graph)
subgraph = retriever.retrieve_context(seed_ids, max_hops=1)
context = retriever.format_as_markdown(subgraph)
print(context)
```

---

## Module Reference

### `nervapack.parser.ast_parser`

Parse source files into structured AST entities.

#### `scan_directory(directory, parser=None) → List[ParsedEntity]`

Walk a directory tree, parse every supported source file, and return all entities. Build directories (`dist/`, `build/`, `node_modules/`, etc.) are pruned automatically. Respects `.nervapackignore` if present.

```python
from nervapack.parser.ast_parser import scan_directory, ASTParser

entities = scan_directory("./src")
print(f"Found {len(entities)} entities")
# → Found 378 entities
```

Pass an `ASTParser` instance to reuse the singleton parser (avoids reloading tree-sitter grammars):

```python
parser = ASTParser()
entities = scan_directory("./src", parser=parser)
```

#### `ASTParser`

Low-level file parser. Use `scan_directory` for most cases; use `ASTParser` directly when you need per-file control.

```python
from nervapack.parser.ast_parser import ASTParser

parser = ASTParser()
entities = parser.parse_file("src/auth/middleware.py")
for e in entities:
    print(e.kind, e.name, e.file_path, e.start_line, e.end_line)
```

#### `ParsedEntity`

Dataclass returned by the parser:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Entity name (class/function/import identifier) |
| `kind` | `str` | `"class"`, `"function"`, or `"import"` |
| `file_path` | `str` | Absolute path to the source file |
| `start_line` | `int` | First line of the entity |
| `end_line` | `int` | Last line of the entity |
| `content` | `str` | Full source text of the entity |
| `language` | `str` | Detected language (`"python"`, `"typescript"`, etc.) |

---

### `nervapack.parser.md_chunker`

Parse Markdown files into header-delimited chunks.

#### `scan_markdown_directory(directory) → List[Dict[str, str]]`

```python
from nervapack.parser.md_chunker import scan_markdown_directory

chunks = scan_markdown_directory("./docs")
for chunk in chunks:
    print(chunk["id"], chunk["content"][:60])
```

Each chunk dict has keys: `id`, `content`, `file_path`, `header`.

#### `MarkdownChunker`

Parse a single Markdown file:

```python
from nervapack.parser.md_chunker import MarkdownChunker

chunker = MarkdownChunker()
chunks = chunker.chunk_file("docs/authentication.md")
```

---

### `nervapack.graph.builder`

Build and persist the NetworkX knowledge graph.

#### `GraphBuilder`

```python
from nervapack.graph.builder import GraphBuilder

builder = GraphBuilder()
```

**`build_from_entities(entities) → nx.DiGraph`**

Build the graph from a list of `ParsedEntity` objects. Adds `DEFINES` edges (file → class → function) and heuristic `REFERENCES` edges (name-overlap between entities).

```python
from nervapack.parser.ast_parser import scan_directory
entities = scan_directory("./src")
graph = builder.build_from_entities(entities)
print(graph.number_of_nodes(), graph.number_of_edges())
```

**`save_graph(path=".nervapack/graph.graphml")`**

Persist the graph to disk as GraphML.

```python
builder.save_graph()
builder.save_graph(path="/tmp/mygraph.graphml")
```

**`load_graph(path=".nervapack/graph.graphml") → nx.DiGraph`**

Load a previously saved graph. Returns a NetworkX DiGraph.

```python
graph = builder.load_graph()
```

**`remove_nodes_for_file(file_path)`**

Remove all nodes and edges belonging to a file — used during incremental sync.

```python
builder.remove_nodes_for_file("src/old_module.py")
```

---

### `nervapack.graph.vector_store`

ChromaDB-backed semantic search.

#### `VectorStore(db_path=".nervapack/chroma_db", embedding_function=None)`

```python
from nervapack.graph.vector_store import VectorStore

vstore = VectorStore()
# Custom ChromaDB path:
vstore = VectorStore(db_path="/data/my_chroma_db")
```

**`ingest_ast_entities(entities: List[Dict])`**

Embed code entities into ChromaDB. Uses `upsert` — safe to call multiple times on the same data.

```python
entity_dicts = [
    {
        "id": f"{e.kind}:{e.file_path}:{e.name}",
        "content": e.content,
        "file_path": e.file_path,
        "name": e.name,
        "kind": e.kind,
    }
    for e in entities
]
vstore.ingest_ast_entities(entity_dicts)
```

**`ingest_chunks(chunks: List[Dict])`**

Embed Markdown chunks into ChromaDB. Uses `upsert`.

```python
chunks = scan_markdown_directory("./docs")
vstore.ingest_chunks(chunks)
```

**`search(query, n_results=5) → dict`**

Vector similarity search. Returns a ChromaDB result dict with keys `ids`, `documents`, `metadatas`, `distances`.

```python
results = vstore.search("JWT authentication", n_results=3)
seed_ids = results["ids"][0]       # list of node IDs
distances = results["distances"][0]  # similarity scores
```

**`delete_by_file(file_path)`**

Remove all vectors for a given file path — used during sync.

```python
vstore.delete_by_file("src/old_module.py")
```

---

### `nervapack.graph.retrieval`

K-Hop BFS context extraction from the graph.

#### `GraphRetriever(graph: nx.DiGraph)`

```python
from nervapack.graph.retrieval import GraphRetriever

graph = GraphBuilder().load_graph()
retriever = GraphRetriever(graph)
```

**`retrieve_context(start_node_ids, max_hops=2, direction="both") → nx.DiGraph`**

Run BFS from the given seed nodes and return the induced subgraph.

- `direction="forward"` — follow outgoing edges only
- `direction="reverse"` — follow incoming edges only (impact analysis)
- `direction="both"` — traverse all edges (default)

```python
results = vstore.search("payment processing", n_results=3)
seed_ids = results["ids"][0]

# Standard context retrieval
subgraph = retriever.retrieve_context(seed_ids, max_hops=1)

# Impact analysis — what depends on these nodes?
impact = retriever.retrieve_context(seed_ids, max_hops=2, direction="reverse")
```

**`format_as_markdown(subgraph) → str`**

Convert a retrieved subgraph into a Markdown string ready to inject into an LLM prompt.

```python
context = retriever.format_as_markdown(subgraph)
# Pass to your LLM:
response = llm.chat(system=context, user="How does payment processing work?")
```

**`get_source_files(subgraph) → List[str]`**

Return the unique file paths in a subgraph — used by the token meter to compute naive RAG baseline.

```python
files = retriever.get_source_files(subgraph)
```

---

### `nervapack.graph.analytics`

Graph health metrics and statistics.

#### `GraphAnalytics(graph: nx.DiGraph)`

```python
from nervapack.graph.analytics import GraphAnalytics

graph = GraphBuilder().load_graph()
analytics = GraphAnalytics(graph)
```

**Key methods:**

```python
# Node counts by type
analytics.get_node_counts_by_type()
# → {"file": 78, "function": 551, "class": 65, "import": 628, "markdown": 20}

# Edge counts by relation
analytics.get_edge_counts_by_relation()
# → {"DEFINES": 1244, "EXPLAINS": 416, "REFERENCES": 20173}

# Language distribution
analytics.get_language_distribution()
# → {"python": 78}

# Most connected nodes (top N)
analytics.get_most_connected_nodes(n=5)
# → [("file:src/cli.py", 75), ("file:src/graph/builder.py", 48), ...]

# Documentation coverage
analytics.get_documentation_coverage()
# → {"covered": 416, "total": 616, "percentage": 67.5}

# Orphaned nodes (no edges)
analytics.get_orphaned_nodes()
# → ["import:src/old.py:unused_import", ...]

# Overall health score (0–100)
analytics.get_health_score()
# → 85

# Full summary dict
analytics.get_summary_stats()
```

---

### `nervapack.graph.token_meter`

Token counting and savings panel.

```python
from nervapack.graph.token_meter import count_tokens, naive_rag_text, render_savings_panel

# Count tokens in a string (uses tiktoken if installed, else char estimate)
n_tokens, exact = count_tokens("def authenticate(self, token: str) -> User: ...")
print(n_tokens, "tokens", "(exact)" if exact else "(estimated)")

# Build a naive RAG baseline from source files
naive_text = naive_rag_text(["src/auth/middleware.py", "src/auth/utils.py"])
naive_tokens, _ = count_tokens(naive_text)

# Render the savings panel to stdout
render_savings_panel(
    nervapack_tokens=1180,
    naive_tokens=naive_tokens,
    source_files=["src/auth/middleware.py", "src/auth/utils.py"],
)
```

Install `nervapack[metrics]` for exact tiktoken counts. Without it, a character-based estimate is used.

---

### `nervapack.graph.query_history`

Record and retrieve per-query analytics.

```python
from nervapack.graph.query_history import QueryHistory

history = QueryHistory()  # uses .nervapack/query_history.jsonl

# Record a query
history.add_query(
    query="How does auth work?",
    nodes_retrieved=12,
    nervapack_tokens=1180,
    naive_tokens=12840,
    execution_time_ms=230,
)

# Retrieve recent queries (tail-read — O(limit), not O(file size))
recent = history.get_recent_queries(limit=10)
for r in recent:
    print(r.query, r.token_savings_pct)

# Aggregate statistics
stats = history.get_statistics()
print(stats["avg_savings_pct"], stats["total_tokens_saved"])

# Clear history
history.clear_history()
```

---

### `nervapack.memory.store`

Low-level access to the bi-temporal agent memory store.

```python
from nervapack.memory.store import MemoryStore

store = MemoryStore()                          # uses .nervapack/memory.db
store = MemoryStore(namespace="my_project")    # namespace isolation
```

**`add_node(kind, content, confidence, entities, rationale, alternatives_rejected, ...) → str`**

Store a structured memory node. Returns the generated node ID.

```python
node_id = store.add_node(
    kind="decision",
    content="Chose JWT over session cookies for auth_service",
    confidence=0.9,
    entities=["auth_service"],
    rationale="Stateless tokens enable horizontal scaling.",
    alternatives_rejected=["server-side sessions", "PASETO"],
)
```

**`fts_search(query, limit, min_confidence, ...) → List[dict]`**

Full-text search over memory nodes using SQLite FTS5. Returns current (non-superseded, non-tombstoned) nodes only.

```python
results = store.fts_search("authentication JWT", limit=10)
for r in results:
    print(r["id"], r["kind"], r["content"])
```

**`supersede(new_id, old_id)`**

Mark an old decision as superseded by a new one. Closes the old node's `valid_until` timestamp.

```python
new_id = store.add_node(kind="decision", content="Switched to PASETO for auth_service", ...)
store.supersede(new_id, old_decision_id)
```

**`timeline(entity, include_superseded=True) → List[dict]`**

Chronological trace for an entity, including superseded versions.

```python
history = store.timeline("auth_service")
for node in history:
    print(node["valid_from"], node["content"], node.get("superseded_by"))
```

**`batch_neighbors(node_ids, edge_kinds=None) → Dict[str, List[dict]]`**

Retrieve neighbors for multiple nodes in a single SQL query — efficient for graph expansion.

```python
neighbors = store.batch_neighbors(["d_abc123", "f_def456"])
for node_id, nbrs in neighbors.items():
    print(node_id, "→", [n["id"] for n in nbrs])
```

**`stats() → dict`**

Node counts, DB size, top entities by degree.

```python
s = store.stats()
print(s["total_nodes"], s["db_size_bytes"])
```

---

## End-to-End: Custom LLM Context Pipeline

Build a RAG pipeline that uses NervaPack for retrieval instead of naive chunking:

```python
from nervapack.parser.ast_parser import scan_directory
from nervapack.parser.md_chunker import scan_markdown_directory
from nervapack.graph.builder import GraphBuilder
from nervapack.graph.vector_store import VectorStore
from nervapack.graph.retrieval import GraphRetriever
from nervapack.graph.token_meter import count_tokens, render_savings_panel


def build_index(project_path: str):
    """One-time setup: parse, embed, and save."""
    entities = scan_directory(project_path)
    doc_chunks = scan_markdown_directory(project_path)

    builder = GraphBuilder()
    builder.build_from_entities(entities)
    builder.save_graph()

    vstore = VectorStore()
    entity_dicts = [
        {"id": f"{e.kind}:{e.file_path}:{e.name}", "content": e.content,
         "file_path": e.file_path, "name": e.name, "kind": e.kind}
        for e in entities
    ]
    vstore.ingest_ast_entities(entity_dicts)
    vstore.ingest_chunks(doc_chunks)
    print(f"Indexed {len(entities)} entities + {len(doc_chunks)} doc chunks")


def retrieve(query: str, max_hops: int = 1) -> str:
    """Query-time: vector search → BFS → Markdown context."""
    graph = GraphBuilder().load_graph()
    vstore = VectorStore()
    retriever = GraphRetriever(graph)

    results = vstore.search(query, n_results=3)
    seed_ids = results["ids"][0]

    subgraph = retriever.retrieve_context(seed_ids, max_hops=max_hops)
    context = retriever.format_as_markdown(subgraph)

    # Print token savings panel
    source_files = retriever.get_source_files(subgraph)
    nervapack_tokens, _ = count_tokens(context)
    render_savings_panel(nervapack_tokens, source_files=source_files)

    return context


# Usage
build_index("./my_project")  # run once
context = retrieve("How does the payment service handle retries?")
# Inject context into your LLM call:
# response = anthropic.messages.create(system=context, ...)
```

---

## End-to-End: Persistent Agent Memory

Give any agent cross-session memory:

```python
from nervapack.memory.store import MemoryStore
from nervapack.memory.recall import recall

store = MemoryStore(namespace="my_agent")

# Store a decision
store.add_node(
    kind="decision",
    content="Use async queues for order processing — sync calls timeout under load",
    confidence=0.95,
    entities=["order_service"],
    rationale="p99 latency exceeded 2s under peak load in load test.",
)

# In a future session, recall it
context = recall(store, "order processing", budget_tokens=200)
print(context)
# → ## Memory recall: "order processing" (1 item · 28/200 tokens)
# → ### Decisions
# → - Use async queues for order processing — sync calls timeout under load
```

---

## Supported Languages

The parser supports these file extensions out of the box:

| Extension | Language |
|-----------|---------|
| `.py` | Python |
| `.js`, `.jsx` | JavaScript |
| `.ts`, `.tsx` | TypeScript |

Additional languages via optional extras:

```bash
pip install "nervapack[go]"      # .go
pip install "nervapack[rust]"    # .rs
pip install "nervapack[java]"    # .java
pip install "nervapack[c]"       # .c, .h
pip install "nervapack[cpp]"     # .cpp, .cc, .cxx, .hpp
pip install "nervapack[ruby]"    # .rb
pip install "nervapack[csharp]"  # .cs
```

---

## See Also

- [MCP Server](mcp-server.md) — use NervaPack tools from Claude Code / Cursor without writing Python
- [Agent Memory MCP tools](../memory/mcp-tools.md) — 17 memory tools over MCP
- [API Reference](../api/graph.md) — auto-generated module docs
