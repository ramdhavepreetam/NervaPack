# `nervapack sync`

Incrementally update the graph after code changes — without re-ingesting the whole project.

---

## Synopsis

```bash
nervapack sync [PATH]
```

---

## Description

`sync` diffs your git working tree against the last commit, finds the files that changed, and surgically updates only those files in the graph and vector store.

- **Removes** old nodes and ChromaDB vectors for each changed file.
- **Re-parses** the updated file with tree-sitter.
- **Re-embeds** the new entities into ChromaDB (batched in one call per file).
- **Re-binds** any markdown docs linked to the changed file.
- **Saves** the updated graph once at the end.

A full `ingest` on a large project can take minutes. `sync` turns that into a 2–5 second surgical update per file.

!!! warning "Requires git"
    `sync` uses `GitPython` to detect changed files. Your project must be a git repository.

---

## Options

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Path to the repository root | `.` (current directory) |

---

## Examples

```bash
# Sync after editing files
nervapack sync .

# Sync a different project
nervapack sync /path/to/project
```

---

## Expected Output

```
Syncing changed files with NervaPack graph...
Found 3 changed files.
Updated AST for src/graph/builder.py
Updated AST for src/graph/retrieval.py
Removed old_module.py
Sync complete.
```

---

## When to Use `sync` vs `ingest`

| Situation | Command |
|-----------|---------|
| First-time setup | `nervapack ingest .` |
| After editing 1–20 files | `nervapack sync .` |
| After a large refactor (many renames) | `nervapack ingest .` |
| After adding a new language/directory | `nervapack ingest .` |
| Graph corrupt or wrong data ingested | `nervapack clean --all && nervapack ingest .` |

---

## What Gets Updated

For each changed source file (`.py`, `.js`, `.ts`, etc.):

1. Old graph nodes for that file are removed (O(1) — file index lookup).
2. Old ChromaDB vectors for that file are deleted (`delete_by_file`).
3. The file is re-parsed by tree-sitter into new entities.
4. All new entities are batch-upserted into ChromaDB in one call.
5. New graph nodes and `DEFINES` edges are added.

For each changed markdown file (`.md`):

1. Old graph nodes removed.
2. Old vectors deleted.
3. File re-chunked by header.
4. Chunks upserted into ChromaDB.
5. LLM binding re-runs for the chunks (via `LLMSummarizer`).

---

## See Also

- [`ingest`](ingest.md) — full rebuild from scratch
- [`clean`](clean.md) — wipe data before re-ingesting
- [`status`](status.md) — check which files are out of sync
