# `nervapack clean`

Remove ingested graph data and start fresh.

---

## Synopsis

```bash
nervapack clean [OPTIONS]
```

---

## Description

`clean` deletes the files NervaPack writes into `.nervapack/` so you can re-ingest from scratch. Use it when:

- You ran `nervapack ingest .` multiple times and have **duplicate embeddings** in ChromaDB
- You ingested the **wrong directory** and want to start over
- The graph or vector store is **corrupt or stale**
- You want to **reduce disk space** used by `.nervapack/`

`clean` never touches `memory.db` (your agent memory store) — decisions, facts, and sessions are always preserved.

---

## Options

| Option | Description |
|--------|-------------|
| `--vectors` | Wipe the ChromaDB vector store only (`chroma_db/`) |
| `--graph` | Delete `graph.graphml` only |
| `--history` | Clear `query_history.jsonl` and `graph_history.jsonl` |
| `--all` | Everything above — full wipe, keeps `memory.db` |
| `--yes` / `-y` | Skip the confirmation prompt (useful in scripts/CI) |
| `--path PATH` | Project root where `.nervapack/` lives (default: `.`) |

---

## Examples

### Fix duplicate embeddings after multiple ingests
```bash
nervapack clean --vectors
nervapack ingest .
```

### Delete everything and re-ingest from scratch
```bash
nervapack clean --all
nervapack ingest .
```

### Non-interactive full wipe (CI / scripting)
```bash
nervapack clean --all --yes
nervapack ingest .
```

### Clean a different project's graph
```bash
nervapack clean --all --path /path/to/project
```

---

## What gets deleted

| Flag | Files removed |
|------|---------------|
| `--vectors` | `.nervapack/chroma_db/` (the entire ChromaDB directory) |
| `--graph` | `.nervapack/graph.graphml` |
| `--history` | `.nervapack/query_history.jsonl`, `.nervapack/graph_history.jsonl` |
| `--all` | All of the above |

**Never deleted:** `.nervapack/memory.db` (agent memory — bi-temporal SQLite store).

---

## Output

```
The following will be permanently deleted:

  What                    Path                        Size
 ──────────────────────────────────────────────────────────
  ChromaDB vector store   ./.nervapack/chroma_db   38.1 MB
  Graph (graph.graphml)   ./.nervapack/graph.graphml 1.4 MB

Note: memory.db (agent memory) is never touched by clean.

Proceed? [y/n]: y
✓ Deleted: ChromaDB vector store
✓ Deleted: Graph (graph.graphml)

Clean complete. Run nervapack ingest . to rebuild.
```

---

## Typical workflow after a bad ingest

```bash
# 1. See what's there
nervapack status

# 2. Wipe vectors and graph (keep memory)
nervapack clean --all

# 3. Optionally add a .nervapackignore to exclude build dirs
cat > .nervapackignore << 'EOF'
dist/
build/
site/
*.egg-info/
EOF

# 4. Re-ingest cleanly
nervapack ingest .
```

---

## See Also

- [`ingest`](ingest.md) — build the knowledge graph
- [`status`](status.md) — check graph health before and after
- [`doctor`](doctor.md) — diagnose environment issues
