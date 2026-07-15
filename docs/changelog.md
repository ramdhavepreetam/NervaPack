# Changelog

All notable changes to NervaPack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.3] - 2026-07-15

### Fixed
- **Vendored/bundled libraries scanned as user code** — added `vendor`, `vendors`, `lib`, `libs`, `third_party`, `extern`, `_vendor`, `rusted-host`, `site-packages` to `_SKIP_DIRS` in both `ast_parser` and `md_chunker`. Projects with pip packages or JS libraries living inside the repo tree (e.g. `rusted-host/pyvis/`) no longer produce hundreds of thousands of spurious entities.
- **Minified JS/TS files parsed** — added `_SKIP_SUFFIXES` check; `.min.js`, `.min.ts`, `.min.cjs`, `.bundle.js`, `.bundle.ts` are now skipped entirely.
- **Duplicate vector IDs from minified files** — added a 500-entity-per-file cap; files generating more than 500 entities are silently skipped (they are minified bundles, not readable source).

### Upgrade Notes
If you previously ingested a project and got unexpectedly large entity counts, clean and re-ingest:
```bash
nervapack clean --all
nervapack ingest .
```

---

## [0.6.2] - 2026-07-15

### Performance
- **Re-ingest now near-instant** — `VectorStore` checks which IDs already exist with identical content before embedding; re-running `nervapack ingest .` on an unchanged project drops from ~85s to <1s for markdown and is instant for AST entities. Only new or modified documents are sent to ONNX.
- **Smaller chunk count** — `MarkdownChunker` now merges chunks shorter than 120 characters forward, reducing total chunk count by ~33% (1796 → 1190 on NervaPack's own docs). Proportionally faster first ingest and lower ChromaDB storage.

---

## [0.6.1] - 2026-07-15

### Fixed
- **ChromaDB duplicate embeddings** — replaced `collection.add()` with `collection.upsert()` in `VectorStore.ingest_chunks()` and `VectorStore.ingest_ast_entities()`. Running `nervapack ingest .` multiple times no longer multiplies storage; re-ingesting a previously indexed project is now fully idempotent.
- **Over-broad directory scan** — expanded `_SKIP_DIRS` in `ast_parser.py` to exclude common build/output directories (`dist`, `build`, `site`, `target`, `out`, `output`, `.tox`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `htmlcov`, `coverage`, `.next`, `.nuxt`, `.svelte-kit`, `.turbo`, `bin`, `.gradle`, `.idea`, `.vscode`, `.venv`, `env`) and any directory ending with `.egg-info` or `.dist-info`. This prevents NervaPack from ingesting generated artefacts, which was the primary cause of multi-GB graph sizes on typical Python/JS projects.

### Upgrade Notes
If you previously ran `nervapack ingest .` and saw unexpectedly large `.nervapack/chroma_db/` sizes, clear and re-ingest:
```bash
rm -rf .nervapack/chroma_db
nervapack ingest .
```

---

## [0.6.0] - 2026-07-14

### Added
- **`nervapack enrich` command** — add semantic doc-to-code edges to an existing graph without full re-ingestion. Uses LLM binding with cost confirmation for cloud providers.
- **`nervapack doctor` command** — system check for Python version, Tree-sitter grammars, embedding backend, Ollama reachability, and MCP config.
- **`nervapack memory rebind` command** — update `file_path` in TOUCHES edges to survive file renames/refactoring.
- **`nervapack memory timeline --as-of`** — point-in-time timeline queries; accepts ISO timestamp or git commit hash.
- **`nervapack memory audit`** — full access audit trail for a memory node (who recalled it, with what query and score).
- **`nervapack memory search --as-of`** — bi-temporal search: query the memory state as it was at a past commit or timestamp.
- **MCP `impact` tool** — reverse dependency analysis; finds what depends on a given entity by traversing the graph backwards.
- **Pluggable embedding backend** — `nervapack ingest --embeddings ollama` or `NERVAPACK_EMBEDDINGS=ollama` to swap ChromaDB's embedding function. Defaults to ONNX.
- **Heuristic cross-file `REFERENCES` edges** — `GraphBuilder` now adds name-overlap edges between entities across files (confidence=0.7).
- **Directional BFS in `GraphRetriever`** — `retrieve_context(direction="forward"|"reverse"|"both")` for forward/reverse/bidirectional traversal.
- **Query router in `nervapack query`** — intent detection for impact queries (`what breaks if I change X`), exact symbol match, and vector search fallback.
- **`mem_audit` table** — new schema table tracking every recall access with timestamp, query, and score.
- **Ollama model auto-resolve** — `OllamaProvider` falls back to first installed model if the requested model isn't available.
- **LLM `bind_docs_to_ast` pre-filter** — keyword-overlap pre-filter keeps candidate list ≤12, preventing local model hallucination on large prompts.
- **Ingestion timer** — `nervapack ingest` reports total elapsed time on completion.

### Changed
- **MCP tool renames (breaking):** `query_codebase` → `query`, `list_entities` → `explore`. Update `.mcp.json` accordingly.
- **Default Claude model** updated to `claude-haiku-4-5-20251001`.
- **`nervapack query` output** — Rich markup escaped in node names and doc headers to prevent rendering errors; `[seed]` tag escaped correctly.
- **`ingest` LLM errors** — non-fatal: prints a notice and continues with keyword-only binding instead of exiting.
- **`dependencies` command** — `--cycles/--no-cycles` and `--layers/--no-layers` flags simplified to `--cycles` / `--layers`.
- **`recall`** now records an audit trail entry in `mem_audit` for every node returned.
- **EXPLAINS edges** now carry `source` (`semantic-llm` or `keyword`) and `confidence` (0.9 or 0.5) attributes.

---

## [0.5.8] - 2026-07-07

### Added
- **MCP Registry submission** — `server.json` added to project root for the official MCP Registry (`io.github.ramdhavepreetam/nervapack`). Lists all 20 tools across both MCP servers.
- **PyPI ownership proof** — `<!-- mcp-name: io.github.ramdhavepreetam/nervapack -->` added to `README.md` as required by the registry's PyPI verification flow.

---

## [0.5.7] - 2026-07-07

### Fixed
- **Memory MCP server broken** — Phase D consolidation had reduced `mcp_server.py` to 3 tools (`remember`/`recall`/`audit`) while the test suite, README, and `.mcp.json` all expected the original 17-tool interface. All MCP integration tests failed with `Unknown tool: memory_store`. Restored the full 17-tool server.
- **`add_touches_edges` missing from `MemoryStore`** — the store method referenced by the MCP server was never implemented; added it.
- **Namespace state leaked across MCP sessions** — `memory_switch_namespace` left `_namespace` set globally; subsequent fresh sessions inherited the wrong namespace. Fixed with an `_namespace_explicit` flag so external resets (test fixture, process restart) revert to `"default"`.
- **`memory_list_sessions` / `memory_to_code` returned wrong type** — FastMCP serializes Python `list` returns as one `TextContent` per item; single-item lists were parsed as a dict by callers. Both tools now return `CallToolResult` with a single JSON-array text payload.
- Tests: 90/90 passing (was 32 failing).

---

## [0.5.6] - 2026-07-05

### Fixed
- **EXPLAINS edges were never created** — `ingest` discarded the already-configured LLM provider and re-instantiated `LLMSummarizer` via the deprecated wrapper, which silently fell back to Ollama and failed. Fixed by using the provider object directly.
- **Default Claude model was deprecated** — factory defaulted to `claude-3-haiku-20240307` (404). Updated to `claude-haiku-4-5-20251001`.
- **Keyword-only binding added** — running `nervapack ingest .` without `--llm` now uses free, instant keyword-overlap matching instead of making LLM API calls. LLM binding only triggers when `--llm` is explicitly passed. This produces EXPLAINS edges in seconds at zero cost.

### Result
- Health score: 8/100 → 47/100
- EXPLAINS edges: 0 → 3,253
- Doc coverage: 0.0% → 46.2%

---

## [0.5.5] - 2026-07-05

### Fixed
- **`.nervapackignore` was never read** — `scan_directory()` only consulted a hardcoded `_SKIP_DIRS` set, so `site/`, `lib/`, `dist/` and their minified JavaScript were all ingested as real code. This inflated node counts from ~630 to 1,791 and produced a misleading health score. `scan_directory()` now reads `.nervapackignore` at walk time using gitignore-style fnmatch patterns.
- Added `site/` (MkDocs build output) to `.nervapackignore`.
- Fixed `st.page_link("app.py")` crash in the Streamlit dashboard — this call is only valid in multipage Streamlit apps; removed it from the single-file dashboard.

---

## [0.5.4] - 2026-07-05

### Fixed
- Dashboard startup error: `st.page_link("app.py", icon="🏠")` raises in single-file Streamlit apps. Removed the decorative sidebar navigation link.

---

## [0.5.3] - 2026-07-05

### Added — Phase 4: Advanced Analytics

- **`nervapack hotspots`** — new CLI command that reads `git log --numstat` to rank files by commit frequency or total churn. Supports `--since`, `--ext`, `--limit`, `--churn` flags. No new dependencies (uses GitPython already bundled).
- **Graph evolution history** (`src/nervapack/graph/graph_history.py`) — `GraphHistory` appends a JSONL snapshot of graph stats (node/edge counts, health score, doc coverage) after every `ingest` and `sync`. Snapshots accumulate going-forward; no historical backfill.
- **Dashboard: Hotspots tab** — interactive bar chart + table with time-window dropdown (All time / 1 year / 6 months / 3 months / 1 month) and sort toggle (commit count vs churn).
- **Dashboard: Graph Evolution tab** — node/edge count over time, health score trend, doc coverage trend, and sync log table.
- 14 new tests; full suite: 104 passing.

---

## [0.5.2] - 2026-07-05

### Changed
- Version bump; docs URL pointed to readthedocs.io.

---

## [0.5.1] - 2026-07-05

### Added — Phase 3: Multi-Agent Scaling (nervapack.memory)

- **Namespace isolation** — all memory nodes tagged with a `namespace` column (default `"default"`). `memory_switch_namespace()` MCP tool sets the active namespace and resets the session to prevent cross-namespace leaks. `namespace` parameter added to `memory_store`, `memory_recall`, `memory_stats`, `memory_start_session`.
- **Staleness detection** — `memory_verify_staleness()` MCP tool: checks TOUCHES edge file mtimes vs `recorded_at`, queues stale nodes for review.

---

## [0.5.0] - 2026-07-05

### Added — Phase 2: Activate Stubs (nervapack.memory)

- **Rule-based consolidation** — `RuleBasedConsolidator` deduplicates memory nodes via Jaccard word-overlap (threshold > 0.9). `nervapack-memory consolidate [--dry-run]` CLI command.
- **TOUCHES edge creation** — `match_code_entity()` in `resolve.py` links memory nodes to code graph nodes. Lazy graph load with sentinel; TOUCHES edges carry `file_path`, `start_line`, `end_line`.
- **Reverse lookup MCP tools** — `memory_for_code(file_path, line=None)` and `memory_to_code(memory_id)`.
- **Import/seed** — `memory_import` MCP tool and `nervapack-memory import <file.json>` CLI command.

---

## [0.4.6] - 2026-07-05

### Added
- `__version__` exposed at package root (`from nervapack import __version__`).
- Automatic update notifications: checks PyPI on startup, prints a notice if a newer version is available (cached for 24 h, non-blocking background thread).

---

## [0.4.5] - 2026-07-05

### Added — Phase 1: Gap Closure (nervapack.memory)

- Tests for `list_sessions`, `delete_session`, `memory_list_sessions`, `memory_clear_session` MCP tools.
- `memory_verify` refute path: refuted facts excluded from future recalls.
- `memory_about` normalised alias (`AuthService` → `auth_service`).
- `timeline` `since` parameter.
- `memory_store` `rationale` and `alternatives_rejected` optional params — merged into node data JSON.
- `memory_start_session(name)` MCP tool and `nervapack-memory start-session` CLI command.
- `min_confidence` filter on `memory_recall` (0.0–1.0).
- CamelCase→snake_case entity alias fix in `resolve.py`.
- `pack_timeline` budget cap (default 1000 tokens, drops oldest entries).
- `nervapack-memory show <node_id>` and `nervapack-memory search <query>` CLI commands.

---

## [0.4.3] - 2026-07-04

### Added
- `nervapack-memory delete-session` CLI command.
- `nervapack-memory list-sessions` CLI command.

---

## [0.4.2] - 2026-07-03

### Added — `nervapack.memory` (Phase 1)

- **`nervapack.memory`** — a new structured agent memory layer, fully independent of the code-graph stack.
- **SQLite store** (`src/nervapack/memory/store.py`) with FTS5 full-text search (BM25), bi-temporal schema (`valid_from` / `valid_until` world-time + `recorded_at` learn-time), 8 node kinds, 7 edge kinds, external-content FTS5 table synced via INSERT/UPDATE/DELETE triggers.
- **Recall pipeline** (`src/nervapack/memory/recall.py`): FTS5 BM25 entry search → graph expansion (up to 2 hops, 0.6× relevance decay) → temporal mask → 4-factor scoring (relevance × recency × frequency × connectivity) → budget packing.
- **Token budget enforcement** (`src/nervapack/memory/pack.py`): `CharTokenCounter` (built-in, `ceil(len/4)`) and optional tiktoken; `pack()` guarantees result is always `≤ budget_tokens`.
- **Entity resolution** (`src/nervapack/memory/resolve.py`): case-insensitive alias lookup + normalised separator-stripped matching (`AuthService` ↔ `auth_service` ↔ `auth-service`).
- **MCP server** (`nervapack-memory-mcp`) exposing 9 tools: `memory_store`, `memory_recall`, `memory_about`, `memory_why`, `memory_timeline`, `memory_end_session`, `memory_forget`, `memory_verify`, `memory_stats`.
- **CLI** (`nervapack-memory`) with 4 commands: `init`, `stats`, `forget`, `export`.
- **Phase 2 stubs**: `NoopConsolidator` queues consolidation without making LLM calls; `mem_review_queue` table present for future entity merge workflow.
- **Cross-process demo** (`examples/seed_demo.py`): session A stores a decision, session B recalls it in a fresh process within 500-token budget.
- **56 tests** covering CRUD, FTS sync, bi-temporal supersede, budget invariant, entity resolution, all 9 MCP tools, cross-session persistence.
- **mypy clean** across all 8 source files in `nervapack.memory`.

### Changed

- `.mcp.json` — added `nervapack-memory` server entry alongside existing `nervapack` server.
- `pyproject.toml` — added `memory = ["mcp[cli]>=1.0.0"]` and `tokens = ["tiktoken>=0.5.0"]` extras; added two new entry points (`nervapack-memory-mcp`, `nervapack-memory`).
- Documentation — added memory concept guide, CLI reference, full MCP tool reference; updated architecture doc, MCP integration page, and README.

### Design constraints (enforced by implementation)

- No network calls at runtime — fully local, offline-first, zero telemetry.
- No hard deletes in normal operation — supersede closes `valid_until`; `memory_forget(purge=True)` is the only sanctioned hard delete.
- No Phase 2/3 functionality (no LLM calls, no embeddings) in this release.
- Facts, not chunks — every recalled item is an atomic assertion with provenance.

---

## [0.4.1] - 2026-06-18

### Fixed
- Resolved network initialization race condition in visualizer
- Fixed MCP server configuration paths

### Changed
- Added `.nervapackignore` for better file filtering
- Updated MCP config with proper paths

---

## [0.4.0] - 2026-06-16

### Added
- **Multi-LLM provider support**
    - Ollama (local, privacy-first)
    - Claude API (cloud, high quality)
    - OpenAI API (cloud, widely available)
    - MCP Delegation (zero-config for Claude Code/Cursor)
- `--llm` and `--model` CLI flags for provider selection
- Smart provider auto-detection (MCP → env vars → Ollama)
- Cost estimation for cloud providers (shown before binding)
- User confirmation prompts for cloud LLM usage
- Provider validation and helpful error messages

### Changed
- Refactored LLM architecture to factory pattern
- Split `LLMSummarizer` into provider-specific modules
- Updated documentation with provider comparison tables
- Enhanced CLI help text with provider examples

### Documentation
- Added comprehensive LLM provider guide
- Created `MULTI_LLM_IMPLEMENTATION.md` with architecture details
- Updated README with provider comparison and setup instructions

---

## [0.3.1] - 2026-06-15

### Fixed
- Build and deployment configuration issues
- Version bump for PyPI release

---

## [0.3.0] - 2026-06-14

### Added - Phase 3: Web Dashboard
- **Streamlit-based interactive web dashboard**
    - `nervapack serve` command to launch on localhost
    - 4 dashboard tabs: Overview, Analytics, Query History, Graph Explorer
    - 8+ interactive Plotly charts (pie, bar, trends)
    - Caching strategy for fast subsequent loads (<200ms)
    - Real-time metrics with health score visualization

### Added - Phase 2: Advanced Graph Visualization
- **Enhanced visualizer (v2) module**
    - Real-time client-side search (instant filtering on 5000+ nodes)
    - Community detection using Louvain algorithm (10-color palette)
    - `nervapack explore` command for focused N-hop subgraph extraction
    - Interactive path finder with BFS shortest path algorithm
- **Dependency analysis module**
    - `nervapack dependencies` command for file-level import analysis
    - Circular dependency detection
    - Hierarchical visualization with color-coded dependency types

### Added - Phase 1: Enhanced CLI Visualizations
- **Graph analytics module**
    - Health scoring algorithm (0-100 scale)
    - Language distribution metrics
    - Documentation coverage analysis
    - Connectivity and degree distribution stats
- **Query history module**
    - Automatic query tracking to `.nervapack/query_history.jsonl`
    - `nervapack history` command with aggregate statistics
    - Cost savings dashboard across all queries
    - Most-queried topics analysis (word frequency)
- **Enhanced status command**
    - `--detailed` flag for comprehensive analytics
    - Visual bars for language distribution
    - Top-10 most connected files
    - Git sync warnings

### Changed
- Updated `query` command with tree visualization of BFS traversal
- Enhanced token savings panel with cost estimates
- Improved visual presentation across all CLI commands

### Documentation
- Added `VISUALIZATION_PLAN.md` (5-phase roadmap)
- Added phase completion docs (PHASE1_COMPLETE.md, PHASE2_COMPLETE.md, PHASE3_COMPLETE.md)
- Added `OVERALL_PROGRESS.md` with cross-phase metrics
- Updated `KNOWLEDGE.md` with comprehensive project overview

---

## [0.2.0] - 2024-12-XX

### Added
- MCP server for Claude Code/Cursor integration
- `nervapack-mcp` command-line tool
- Three MCP tools: `query_codebase`, `graph_status`, `list_entities`
- `.mcp.json` configuration support

### Changed
- Improved graph persistence and loading
- Enhanced error messages

---

## [0.1.0] - 2024-11-XX

### Added
- Initial release
- Core commands: `ingest`, `query`, `visualize`, `sync`, `status`
- Tree-sitter based AST parsing
- NetworkX graph storage
- ChromaDB vector store
- Ollama LLM integration
- GitPython incremental sync
- PyVis interactive visualization
- Token efficiency metrics

### Supported Languages (Bundled)
- Python
- JavaScript
- TypeScript
- JSX
- TSX

---

## [Unreleased]

### Planned Features
- Additional language parsers (Go, Rust, Java)
- Performance benchmarks
- CI/CD examples
- VS Code extension
- Plugin system for custom parsers
- Advanced query operators
- Graph diff visualization

---

## Version Numbering

NervaPack follows Semantic Versioning (SemVer):

- **MAJOR** version (X.0.0): Incompatible API changes
- **MINOR** version (0.X.0): New features (backward compatible)
- **PATCH** version (0.0.X): Bug fixes (backward compatible)

### Current Status
- **v0.4.x**: Beta — Feature-complete, production-ready for early adopters
- **v1.0.0**: Planned when test coverage >70% and docs are complete

---

## Migration Guides

### Upgrading to 0.4.0

**Breaking changes:** None

**New features:**
- Multi-LLM provider support (no action required if using Ollama)
- To use cloud providers:
  ```bash
  pip install "nervapack[claude]"  # For Claude API
  pip install "nervapack[openai]"  # For OpenAI API
  ```

**CLI changes:**
- New flags: `--llm`, `--model`, `--api-key`
- Auto-detection works as before (no changes needed)

### Upgrading to 0.3.0

**Breaking changes:** None

**New features:**
- Web dashboard (requires optional install):
  ```bash
  pip install "nervapack[dashboard]"
  ```
- Enhanced visualizations work out of the box

---

## Contributing

See [Contributing Guide](contributing.md) for development workflow and how to propose changes.

Report bugs and request features on [GitHub Issues](https://github.com/ramdhavepreetam/NervaPack/issues).
