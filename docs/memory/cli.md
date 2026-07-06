# `nervapack-memory` CLI

Inspect and manage the NervaPack agent memory store from the command line.

---

## Synopsis

```bash
python -m nervapack.memory <command> [OPTIONS]
# or, after pip install:
nervapack-memory <command> [OPTIONS]
```

---

## Commands

### `init`

Create the memory database schema if it does not already exist.

```bash
python -m nervapack.memory init
python -m nervapack.memory init --db /path/to/memory.db
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--db PATH` | Path to the SQLite file | Auto-resolved (see [Storage](concepts.md#storage)) |

**Output:**

```
✓ Memory store initialised at .nervapack/memory.db
```

Calling `init` on an existing database is safe — it uses `CREATE TABLE IF NOT EXISTS` throughout.

---

### `stats`

Print node counts, database size, and top entities.

```bash
python -m nervapack.memory stats
python -m nervapack.memory stats --db ~/.nervapack/memory.db
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--db PATH` | Path to the SQLite file | Auto-resolved |

**Output:**

```
          Memory Stats
┌──────────┬───────┐
│ Kind     │ Count │
├──────────┼───────┤
│ fact     │    14 │
│ decision │     5 │
│ entity   │     3 │
│ session  │     4 │
│ outcome  │     4 │
└──────────┴───────┘

DB size: 48.0 KB  |  Namespaces: default

Top entities by degree:
  [e_0019f2...] auth_service (degree 6)
  [e_0019f3...] payment_service (degree 2)
```

---

### `forget`

Tombstone (soft-delete) or hard-purge memory nodes.

```bash
# Tombstone a specific node (recoverable — sets tombstoned=1)
python -m nervapack.memory forget --node-id f_0019f2...

# Tombstone all nodes linked to an entity
python -m nervapack.memory forget --entity auth_service

# Tombstone all nodes older than a date
python -m nervapack.memory forget --before 2026-01-01T00:00:00

# Hard-delete a node (irreversible — removes row and FTS entry)
python -m nervapack.memory forget --node-id f_0019f2... --purge
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--node-id ID` | `-n` | Single node to forget |
| `--entity NAME` | `-e` | Forget all nodes linked to this entity via ABOUT edges |
| `--before TIMESTAMP` | `-b` | Forget all nodes recorded before this ISO-8601 timestamp |
| `--purge` | | Hard-delete instead of tombstone (irreversible) |
| `--db PATH` | | Path to the SQLite file |

**Notes:**

- Multiple selectors (`--node-id`, `--entity`, `--before`) are combined with union (OR).
- Tombstoned nodes are excluded from `memory_recall` and `memory_about` but remain in the database and are visible in `memory_timeline`.
- Hard-purge removes the row from `mem_nodes`, deletes dependent edges and aliases, and fires the FTS5 DELETE trigger to remove the entry from `mem_fts`.

---

### `export`

Dump all non-tombstoned nodes and edges as JSON.

```bash
# Print to stdout
python -m nervapack.memory export

# Write to file
python -m nervapack.memory export --out memory_dump.json
python -m nervapack.memory export --out dump.json --db /path/to/memory.db
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--out FILE` | `-o` | Output path (default: stdout) |
| `--db PATH` | | Path to the SQLite file |

**Output format:**

```json
{
  "nodes": [
    {
      "id": "d_0019f2...",
      "kind": "decision",
      "content": "Chose JWT over session cookies for auth_service",
      "data": "{\"rationale\": \"...\", \"alternatives_rejected\": [...]}",
      "confidence": 0.9,
      "valid_from": "2026-07-03T10:00:00+00:00",
      "valid_until": null,
      "recorded_at": "2026-07-03T10:00:00+00:00",
      "session_id": "s_0019f2...",
      "namespace": "default",
      "tombstoned": 0,
      "access_count": 3,
      "last_accessed": "2026-07-03T11:00:00+00:00"
    }
  ],
  "edges": [
    {
      "id": "edge_...",
      "src": "d_0019f2...",
      "dst": "e_0019f2...",
      "kind": "ABOUT",
      "recorded_at": "2026-07-03T10:00:00+00:00",
      "data": null
    }
  ]
}
```

---

## Environment Variables

| Variable | Effect |
|----------|--------|
| `NERVAPACK_MEMORY_DB` | Override the database path for all commands |

```bash
export NERVAPACK_MEMORY_DB=/shared/team/memory.db
python -m nervapack.memory stats
```

---

## See Also

- [Concepts & data model](concepts.md) — data model, recall pipeline, bi-temporal semantics
- [MCP Tools](mcp-tools.md) — use memory from Claude Code / Cursor
- [Python API](python-api.md) — use memory directly in Python
