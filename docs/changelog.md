# Changelog

All notable changes to NervaPack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
