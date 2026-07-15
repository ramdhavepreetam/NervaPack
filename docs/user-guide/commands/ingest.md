# `nervapack ingest`

Build the knowledge graph from your codebase.

---

## Synopsis

```bash
nervapack ingest [PATH] [OPTIONS]
```

---

## Description

The `ingest` command scans your repository and builds the complete knowledge graph. This is typically run once per project, then updated with `sync`.

**What it does:**
1. Walks the directory tree — automatically skips `dist/`, `build/`, `site/`, `node_modules/`, `venv/`, `.tox/`, `__pycache__/`, and dozens of other build/output directories, so generated artefacts are never ingested.
2. Parses code files into AST entities (classes, functions, imports) using tree-sitter.
3. Scans markdown documentation and chunks by header hierarchy.
4. Embeds entities into ChromaDB vector store using `upsert` — re-ingesting the same project is fully idempotent and does not duplicate data.
5. Uses LLM to bind docs to code (creates `EXPLAINS` edges). Falls back to free keyword-overlap matching when no `--llm` flag is given.
6. Saves graph to `.nervapack/graph.graphml`.

!!! tip "Exclude project-specific directories"
    Create a `.nervapackignore` file (gitignore syntax) in your project root to skip additional directories:
    ```
    generated/
    proto_out/
    __snapshots__/
    ```

---

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `PATH` | Directory to scan | `.` (current) |
| `--llm` | LLM provider (ollama, claude, openai, mcp) | Auto-detect |
| `--model` | Model name (provider-specific) | Provider default |
| `--api-key` | API key for cloud providers | From env vars |
| `--embeddings` | Embedding backend (`onnx`, `ollama`) | `onnx` |

---

## Examples

### Basic usage
```bash
cd your-project/
nervapack ingest .
```

### With specific LLM
```bash
nervapack ingest . --llm claude
nervapack ingest . --llm openai --model gpt-4o
```

### Different directory
```bash
nervapack ingest /path/to/repo
```

---

## Expected Output

```
Ingesting repository at .

Scanning directory for code entities...
Found 378 AST entities.

Building deterministic Structural Graph...
Graph saved with 378 nodes and 353 edges.

Ingesting AST nodes into Vector Store...
AST Vector ingestion complete.

Scanning directory for Markdown docs...
Found 12 Markdown chunks.

Setting up LLM provider...
Using LLM provider: ollama

Binding documentation to AST...
Semantic binding complete.

Ingestion complete.
```

---

## Performance

Typical times for a Python project:
- Small (< 100 files): 1-2 minutes
- Medium (100-1000 files): 5-10 minutes
- Large (1000+ files): 15-30 minutes

**Note:** LLM binding is the slowest step. Cloud APIs (Claude, OpenAI) are 5x faster than Ollama.

---

## See Also

- [`sync`](sync.md) — Update graph after code changes
- [`status`](status.md) — Check graph health
- [`clean`](clean.md) — Wipe data and start fresh if ingest went wrong
- [`enrich`](enrich.md) — Add LLM semantic edges to an existing graph
