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

### `rebind`

Update `file_path` in TOUCHES edges to survive file renames and refactoring.

```bash
nervapack-memory rebind old/path/auth.py new/path/auth_service.py
nervapack-memory rebind src/utils.py src/helpers/utils.py --db .nervapack/memory.db
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `OLD_PATH` | File path currently stored in TOUCHES edges |
| `NEW_PATH` | New file path to replace it with |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--db PATH` | Path to the SQLite file | Auto-resolved |

**Output:**

```
Rebound 12 TOUCHES edges from `src/utils.py` to `src/helpers/utils.py`.
```

Use this after renaming or moving a file so that memory nodes linked to the old path remain reachable via the new path.

---

### `search`

Run a full-text search and print results as a table.

```bash
nervapack-memory search "JWT auth"
nervapack-memory search "auth" --kind decision --limit 5
nervapack-memory search "auth" --as-of 2026-06-01T00:00:00
nervapack-memory search "auth" --as-of abc1234   # git commit hash
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `QUERY` | FTS5 search query |

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--kind KIND` | `-k` | Filter by node kind (`fact`, `decision`, etc.) | All kinds |
| `--limit N` | `-l` | Max results to return | `10` |
| `--as-of TIMESTAMP` | | Point-in-time search (ISO timestamp or git commit hash) | Current |
| `--db PATH` | | Path to the SQLite file | Auto-resolved |

The `--as-of` option enables **bi-temporal search**: if you pass a git commit hash, NervaPack resolves it to the commit's ISO timestamp and returns memory nodes as they existed at that point in time.

---

### `timeline`

Print a chronological trace of memories related to a topic, including superseded versions.

```bash
nervapack-memory timeline "auth service"
nervapack-memory timeline "vector store" --since 2026-06-01T00:00:00
nervapack-memory timeline "graph builder" --as-of abc1234
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TOPIC` | Topic to trace |

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--since TIMESTAMP` | `-s` | Only show nodes recorded after this timestamp or commit hash | All time |
| `--as-of TIMESTAMP` | | Show state of memories as of this timestamp or commit hash | Current |
| `--db PATH` | | Path to the SQLite file | Auto-resolved |

**Output:**

```
Timeline: "auth service"

[2026-06-10T09:00:00]  decision  Chose JWT over session cookies
[2026-06-15T14:30:00]  fact      JWT secret rotated to new key
[2026-07-01T11:00:00]  outcome   Auth latency improved 40% after rotation
  ↑ supersedes: [2026-06-10T09:00:00] original JWT decision
```

---

### `audit`

Show the complete access audit trail for a memory node.

```bash
nervapack-memory audit d_0019f2abc
nervapack-memory audit d_0019f2abc --db .nervapack/memory.db
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `MEMORY_ID` | ID of the memory node to audit |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--db PATH` | Path to the SQLite file | Auto-resolved |

**Output:**

```
Memory Audit: d_0019f2abc
Recorded:     2026-06-10T09:00:00
Access Count: 5
Content:      Chose JWT over session cookies for auth_service

┌────────────────────┬───────┬──────────────────────────────────┐
│ Accessed At        │ Score │ Query                            │
├────────────────────┼───────┼──────────────────────────────────┤
│ 2026-07-10 10:01   │  0.91 │ JWT auth decision                │
│ 2026-07-11 14:23   │  0.87 │ auth service architecture        │
│ 2026-07-12 09:05   │  0.83 │ why session cookies rejected     │
└────────────────────┴───────┴──────────────────────────────────┘
```

Each row corresponds to one `memory_recall` call that returned this node. The score is the relevance score at recall time.

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
