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
1. Walks the directory tree and automatically skips three categories of directories:
    - **Built-in skip list** — `dist/`, `build/`, `site/`, `node_modules/`, `venv/`, `.tox/`, `__pycache__/`, and dozens of other build/output directories.
    - **Intelligent vendor detection** — any directory whose name matches an installed Python package (cross-referenced against `pip list` at runtime) is skipped automatically. For example, if `pyvis/` or `chromadb/` ends up inside your project tree, NervaPack detects it and skips it without any manual config.
    - **Heuristic signals** — directories are also skipped if they contain an embedded `package.json`, `pyproject.toml`, or `setup.py` (indicating a self-contained library), or if ≥95% of their JS/TS files consist of very long lines (indicating minified bundles). This catches vendor directories that are not Python packages but behave like them.
2. Parses code files into AST entities (classes, functions, imports) using tree-sitter.
3. Skips minified files (`.min.js`, `.min.ts`, `.bundle.js`, etc.) and any file that produces more than 500 entities, both strong signals of non-user code.
4. Scans markdown documentation and chunks by header hierarchy.
5. Embeds entities into ChromaDB vector store using `upsert` — re-ingesting the same project is fully idempotent and does not duplicate data. Warm re-ingest (unchanged files) completes in under 1 second.
6. Uses LLM to bind docs to code (creates `EXPLAINS` edges). Falls back to free keyword-overlap matching when no `--llm` flag is given.
7. Saves graph to `.nervapack/graph.graphml`.

!!! tip "Exclude project-specific directories"
    Create a `.nervapackignore` file (gitignore syntax) in your project root to skip additional directories:
    ```
    generated/
    proto_out/
    __snapshots__/
    ```

!!! info "Vendor detection is automatic"
    You do not need to add third-party libraries to `.nervapackignore`. NervaPack detects them automatically by cross-referencing directory names against your installed Python environment and by inspecting the contents of each directory for embedded package manifests or minification signals.

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

Typical times for a Python project (ONNX embeddings, no LLM):

| Project size | Cold ingest | Warm re-ingest |
|---|---|---|
| Small (< 50 files) | 5–15 seconds | < 1 second |
| Medium (50–300 files) | 15–60 seconds | < 1 second |
| Large (300–1000 files) | 1–4 minutes | < 1 second |

**Warm re-ingest** is near-instant because NervaPack compares existing ChromaDB IDs against new content before embedding — only new or modified entities are sent to the ONNX model.

**LLM binding** (the `EXPLAINS` edge step) adds time proportional to the number of markdown chunks. Cloud APIs (Claude, OpenAI) are 5–10× faster than Ollama for this step. Skip it with `--no-llm` if you only need the structural graph.

---

## See Also

- [`sync`](sync.md) — Update graph after code changes
- [`status`](status.md) — Check graph health
- [`clean`](clean.md) — Wipe data and start fresh if ingest went wrong
- [`enrich`](enrich.md) — Add LLM semantic edges to an existing graph
