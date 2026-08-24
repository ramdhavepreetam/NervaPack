# NervaPack — Claude Code Instructions

## Always use NervaPack MCP tools

**At the start of every session:**
1. Call `memory_start_session("<task name>")` to open a named session
2. Call `memory_recall("project context", budget_tokens=400)` to load prior decisions and facts
3. Call `query_codebase("<topic>")` before answering any question about how the code works

**During the session — call `memory_store` for:**
- Any decision made (`kind="decision"` with `rationale` and `alternatives_rejected`)
- Any fact discovered about system behaviour (`kind="fact"`)
- Any procedure or convention established (`kind="procedure"`)
- Any outcome from an action (`kind="outcome"`)

**At session end:**
- Call `memory_end_session("<one-paragraph summary of what was done>")`

**Never answer questions about this codebase from training data alone.**
Always call `query_codebase` first — it returns AST-precise, token-efficient context from the live graph.

## MCP servers available

| Server | Command | Purpose |
|--------|---------|---------|
| `nervapack` | `nervapack-mcp` | Code graph — `query_codebase`, `graph_status`, `list_entities` |
| `nervapack-memory` | `nervapack-memory-mcp` | Agent memory — 17 tools for storing and recalling decisions/facts |

## Project essentials

- **Version:** v0.8.0 (source of truth is `version` in `pyproject.toml`)
- **DB:** `.nervapack/memory.db` (SQLite, auto-resolved from cwd)
- **Graph:** `.nervapack/graph.graphml` (reingest with `nervapack ingest .` when source changes)
- **Tests:** `python3 -m pytest tests/memory/ -q` — must stay green before any commit
- **Docs:** `python3 -m mkdocs build --strict` — must build clean before any commit
- **Publish:** `python3 -m build && python3 -m twine upload dist/nervapack-<version>*`
  Never `twine upload dist/*` — `dist/` keeps every previously built version, and
  re-uploading one PyPI already has aborts the whole command. Always name the version.
- **MCP Registry:** `io.github.ramdhavepreetam/nervapack` (published, active)

### Release checklist

1. Bump `version` in `pyproject.toml`; add a `docs/changelog.md` entry.
2. Gates: `pytest tests/ -q`, `ruff check src/ tests/`, `mkdocs build --strict`.
3. `python3 -m build`, then install the wheel into a clean venv and run the
   packaged `nervapack` binary — this is what catches missing modules and
   broken entry points, which the source-tree tests cannot.
4. `python3 -m twine upload dist/nervapack-<version>*`.
5. Only after upload, update `Formula/nervapack.rb` — the sha256 does not exist
   until then. Take it from
   `curl -s https://pypi.org/pypi/nervapack/<version>/json` and verify it against
   the downloaded tarball; `brew audit` cannot run as root, so fall back to
   `ruby -c Formula/nervapack.rb`.
6. Bump the version strings in `.mcp.json`, and re-check the tool lists there
   against the package rather than editing the numbers alone.
7. **Push the formula to the tap repo** — `github.com/ramdhavepreetam/homebrew-nervapack`
   is what `brew install` actually reads; `Formula/nervapack.rb` in this repo is
   only a copy, and has silently drifted behind before (the tap sat on 0.7.6
   while PyPI was on 0.8.0). Copy the formula into the tap checkout at
   `/opt/homebrew/Library/Taps/ramdhavepreetam/homebrew-nervapack`, commit as
   `nervapack <version>`, and push.

   Auditing it: Homebrew refuses to run as root, so prefix with
   `sudo -u preetam`; and `brew audit <path>` is disabled, so audit by name
   against the tap — `brew audit --strict --online ramdhavepreetam/nervapack/nervapack`.
   `brew fetch <name>` is the real checksum test: it downloads the tarball and
   validates the sha256.

## Key architecture facts

- Two MCP servers ship in the same PyPI package: `nervapack-mcp` (code graph) and `nervapack-memory-mcp` (agent memory)
- Memory DB is SQLite + FTS5, bi-temporal (valid_from/valid_until), never hard-deletes by default
- Code graph is NetworkX DiGraph stored as GraphML + ChromaDB for vector search
- FastMCP tools that return lists must use `CallToolResult(content=[TextContent(type="text", text=json.dumps(the_list))])` — FastMCP serializes Python `list` returns as one TextContent per item, breaking single-item lists
- `_namespace_explicit` flag in `mcp_server.py` distinguishes intentional namespace switches from external test fixture resets
- Ingest wall time is ~99% ONNX embedding — parsing and graph building together are <0.1s even on large repos. Optimize the embedding path or nothing. CoreML is ~5x *slower* than CPU for this model, and bigger batches don't help (the tokenizer pads every input to a fixed 256 tokens); both were measured and rejected
- Vendor detection (`_is_vendor_dir`) takes a `scan_root` and must keep it — without it, a pip-installed project excludes its own source, since the dir name matches an installed dist. Same for any dir with its own `pyproject.toml`/`package.json`, which is every package in a monorepo
- Heuristic `REFERENCES` resolution tiers same-file → imported → globally-unique, and only then applies the `MAX_NAME_FANOUT` cap. The cap must stay last: applying it first silently disconnects polymorphic interfaces implemented across many files
