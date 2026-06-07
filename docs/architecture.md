# NervaPack Architecture

## Overview

NervaPack is structured around three pipelines that share a common graph and vector store:

1. **Ingest** — parse the codebase and build the knowledge graph from scratch
2. **Sync** — incrementally update the graph for files changed in git
3. **Query** — retrieve a token-efficient context window for a natural-language prompt

```
Source Files
    │
    ├── .py / .js / .ts / .tsx  ──► ASTParser ──► ParsedEntity[]
    │                                                    │
    └── .md ──────────────────── ► MDChunker ──► Chunk[]
                                                         │
                                    ┌────────────────────┤
                                    ▼                    ▼
                              GraphBuilder          VectorStore
                           (NetworkX DiGraph)      (ChromaDB)
                                    │
                              LLMSummarizer
                           (EXPLAINS edges)
```

---

## Data Model

### Graph (NetworkX DiGraph)

Persisted at `.nervapack/graph.graphml`.

**Node types:**

| Type | ID format | Key attributes |
|---|---|---|
| `file` | `file:<abs_path>` | `path` |
| `function` | `function:<path>:<name>:<line>` | `name`, `file_path`, `start_line`, `end_line`, `content` |
| `class` | `class:<path>:<name>:<line>` | same as function |
| `import` | `import:<path>:import_<line>:<line>` | same as function |
| `markdown` | `md_<path>_<chunk_index>` | `header`, `content`, `file_path` |

**Edge types:**

| Relation | From → To | Meaning |
|---|---|---|
| `DEFINES` | `file` → `function/class/import` | The file declares this entity |
| `EXPLAINS` | `markdown` → `function/class` | Docs semantically describe this entity (LLM-drawn) |

### Vector Store (ChromaDB)

Persisted at `.nervapack/chroma_db/`. Uses ChromaDB's default local embedding model.

Two collections:
- **`ast_entities`** — one document per AST node (function, class, import), text is `"This is a <type> named <name> in <path>. Code:\n<content>"`
- **`markdown_chunks`** — one document per Markdown chunk, text is the raw chunk prose

---

## Module Responsibilities

### `nervapack.parser.ast_parser`

Uses `tree-sitter` to walk a source file's syntax tree and extract `ParsedEntity` dataclass objects for every class definition, function definition, and import statement. Supported languages: Python, JavaScript, TypeScript, TSX.

`scan_directory(path)` walks the directory tree, skipping `.git`, `node_modules`, `venv`, and `__pycache__`.

### `nervapack.parser.md_chunker`

Reads Markdown files and splits them into chunks by header hierarchy (`#`, `##`, `###`). Each chunk carries its header text, body content, and source file path.

### `nervapack.graph.builder` — `GraphBuilder`

Constructs and persists a `networkx.DiGraph`. Key methods:

- `build_from_entities(entities)` — creates file and entity nodes, draws `DEFINES` edges
- `save_graph(path)` — writes GraphML to `.nervapack/graph.graphml`
- `load_graph(path)` — reads GraphML back into memory
- `remove_nodes_for_file(file_path)` — prunes all nodes associated with a file (used by `sync`)

### `nervapack.graph.vector_store` — `VectorStore`

Wraps a ChromaDB client. Key methods:

- `ingest_ast_entities(docs)` — upserts AST node summaries
- `ingest_chunks(chunks)` — upserts Markdown chunks
- `search(query, n_results)` — returns top-N matching node IDs
- `delete_by_file(file_path)` — removes all vectors associated with a file (used by `sync`)

### `nervapack.graph.retrieval` — `GraphRetriever`

Given a list of seed node IDs, performs a K-Hop BFS through the NetworkX graph and collects the resulting subgraph. `format_as_markdown(subgraph)` serializes the subgraph into a compact Markdown block ready for LLM consumption.

### `nervapack.llm.summarizer` — `LLMSummarizer`

Sends Markdown chunks to a local Ollama model and asks it to identify which (if any) AST entity IDs the prose explains. Returns the matching node IDs. Used during `ingest` and `sync` to draw `EXPLAINS` edges.

Default model: `llama3`. Override via the `model` attribute.

### `nervapack.git.tracker` — `GitTracker`

Uses `GitPython` to diff the working tree against HEAD and return the list of modified or deleted file paths. Used by `nervapack sync` to determine which files need re-ingestion.

---

## Sync Algorithm

```
changed_files = GitTracker.get_changed_files()

for file in changed_files:
    GraphBuilder.remove_nodes_for_file(file)
    VectorStore.delete_by_file(file)

    if file exists:
        if file is code (.py/.js/.ts):
            entities = ASTParser.parse_file(file)
            GraphBuilder.add_nodes(entities)
            VectorStore.ingest_ast_entities(entities)
        elif file is .md:
            chunks = MDChunker.chunk_file(file)
            VectorStore.ingest_chunks(chunks)
            LLMSummarizer.bind_docs_to_ast(chunks) → EXPLAINS edges

GraphBuilder.save_graph()
```

The sync skips unchanged files entirely, making it O(changed files) rather than O(repo size).

---

## Query Algorithm

```
seed_ids = VectorStore.search(prompt, n_results=3)
subgraph  = GraphRetriever.retrieve_context(seed_ids, max_hops=1)
context   = GraphRetriever.format_as_markdown(subgraph)
print(context)
```

`max_hops=1` means the retriever collects the seed nodes plus all their direct neighbors. This is enough to pull in, for example, a matched function node plus the Markdown doc linked to it via an `EXPLAINS` edge, and the file node that defines it.
