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
6. Binds docs to code (creates `EXPLAINS` edges) using the [binding mode](#binding-modes) you choose — fast keyword matching by default, or an LLM with `--mode llm`.
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
| `--mode`, `-m` | Doc binding mode: `fast` or `llm` (see below) | `fast`, or `NERVAPACK_INGEST_MODE` |
| `--llm` | LLM provider for `--mode llm` (`ollama`, `claude`, `openai`). Passing it implies `--mode llm` | `ollama` |
| `--model` | Model name (provider-specific) | Provider default |
| `--api-key` | API key for cloud providers | From env vars |
| `--embeddings` | Embedding backend (`onnx`, `ollama`) | `onnx` |

`--no-bind` still works as a deprecated alias for `--mode fast`.

---

## Binding Modes

Ingest always embeds every code entity and doc chunk locally (ONNX). The mode only decides how each markdown chunk gets linked to the code it describes.

| | `fast` (default) | `llm` |
|---|---|---|
| How | Links a chunk to the functions/classes it names *as code* — in backticks, as a call (`name(`), or as a compound identifier like `build_keyword_index` | An LLM picks, from the ~15 nearest entities, the ones the chunk actually explains |
| Needs | Nothing — fully offline | Ollama running, or an Anthropic / OpenAI API key |
| Speed | Seconds, whatever the doc count | Roughly one LLM call per doc chunk — minutes to hours on large doc sets |
| Edge tag | `source="keyword"`, confidence 0.5 | `source="semantic-llm"`, confidence 0.9 |

Fast mode favours precision. A section that only describes code in prose, without naming it, gets no edge. Matching is case-sensitive and ignores import statements, file paths, CLI flags (`--model`) and keyword arguments. A name defined in more than three places, such as `__init__` or a common `load`, only matches when the chunk also names its file. Use `--mode llm` when your docs mostly describe code in prose.

An LLM is **never** used unless you ask for one. Earlier versions quietly switched to LLM binding whenever Ollama was running, and when the requested model was missing they used whatever model was installed first, which could be a large chat model at 8+ seconds per chunk.

With `--mode llm`, a provider that isn't reachable or configured stops the ingest with an error before any work starts. NervaPack doesn't fall back to keyword binding silently. Set `NERVAPACK_INGEST_MODE=llm` to make LLM mode the default for `ingest` and `sync`.

!!! tip "Pick a small, fast model for local LLM mode"
    The binding prompt is a short classification task. A 7B model such as `qwen2.5:7b` handles it well; a 24B chat model is many times slower without being more accurate. NervaPack warns you when the requested Ollama model isn't installed and another one is substituted.

---

## Examples

### Basic usage (fast mode)
```bash
cd your-project/
nervapack ingest .
```

### LLM mode
```bash
nervapack ingest . --mode llm                          # local Ollama
nervapack ingest . --mode llm --model qwen2.5:7b       # pick the Ollama model
nervapack ingest . --llm claude                        # Claude API (implies --mode llm)
nervapack ingest . --llm openai --model gpt-4o-mini
```

### Different directory
```bash
nervapack ingest /path/to/repo
```

---

## Expected Output

```
Ingesting repository at .
Doc binding: fast (keyword matching, no LLM). Use --mode llm for LLM binding.

Scanning directory for code entities...
Found 378 AST entities.

Building deterministic Structural Graph...
Graph saved with 378 nodes and 353 edges.

Ingesting AST nodes into Vector Store...
AST Vector ingestion complete.

Scanning directory for Markdown docs...
Found 12 Markdown chunks.

Binding documentation to AST with keyword matching...
Doc binding complete (fast).

Ingestion complete.
```

---

## What Gets Scanned

NervaPack indexes your project's own source and skips third-party code.

**Always skipped:** `node_modules/`, `.venv/` / `venv/`, `vendor/`, `third_party/`,
`site-packages/`, build outputs (`dist/`, `build/`, `site/`, `target/`), caches,
and minified bundles (`*.min.js`, `*.bundle.js`, or directories where nearly
every JS/TS file is one long line). This holds wherever they appear, including
nested inside a source directory.

**Never skipped:** anything under your project's own source roots — the
directory you point `ingest` at, plus conventional `src/`, `app/`, `apps/`,
`packages/`, and `source/` folders directly beneath it. Packages in a monorepo
keep their own `pyproject.toml` or `package.json` without being mistaken for
dependencies, and a package you have pip-installed in editable mode is still
indexed from source.

Add project-specific exclusions in a `.nervapackignore` file, using
`.gitignore` syntax.

---

## Performance

Typical times for a Python project (ONNX embeddings, no LLM):

| Project size | Cold ingest | Warm re-ingest |
|---|---|---|
| Small (< 50 files) | 5–15 seconds | < 1 second |
| Medium (50–300 files) | 15–60 seconds | < 1 second |
| Large (300–1000 files) | 1–4 minutes | < 1 second |

**Warm re-ingest** is near-instant because NervaPack compares existing ChromaDB IDs against new content before embedding — only new or modified entities are sent to the ONNX model. Editing a file re-embeds that file's content and nothing else; on a 1,144-chunk corpus that is roughly a third of a second.

Embedding dominates ingest time — parsing and graph construction together account for well under a second even on large repositories. NervaPack uses every CPU core for it by default; see [Tuning Ingest Performance](../../getting-started/installation.md#tuning-ingest-performance) to change that.

**`--mode llm`** adds roughly one LLM call per markdown chunk, and a progress bar shows how far along it is. Cloud APIs (Claude, OpenAI) are 5–10× faster than a local Ollama for this step, and model size matters a lot locally. As a reference point, on the NervaPack repo's 1,264 doc chunks, fast mode finishes the whole ingest in ~20s, while a 24B Ollama model takes ~8s *per chunk*.

---

## See Also

- [`sync`](sync.md) — Update graph after code changes
- [`status`](status.md) — Check graph health
- [`clean`](clean.md) — Wipe data and start fresh if ingest went wrong
- [`enrich`](enrich.md) — Add LLM semantic edges to an existing graph
