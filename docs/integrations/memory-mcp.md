# Memory MCP Server

`nervapack-memory-mcp` is an MCP server that exposes 9 tools for storing and recalling structured agent memory. Any MCP-compatible client — Claude Code, Cursor, or a custom agent — can use it to persist facts, decisions, and outcomes across sessions.

---

## Setup

**1. Install**

```bash
pip install "nervapack[memory]"
```

**2. Initialise the store**

```bash
python -m nervapack.memory init
# ✓ Memory store initialised at .nervapack/memory.db
```

**3. Register in `.mcp.json`**

Add alongside the knowledge-graph server:

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph — query_codebase, graph_status, list_entities"
    },
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "NervaPack agent memory — store, recall, and reason over facts across sessions"
    }
  }
}
```

**4. Reload your editor** — both servers appear automatically.

---

## Tool Reference

### `memory_store`

Persist a memory node and link it to entities.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The assertion, decision, or fact to store |
| `kind` | string | Yes | One of: `fact`, `decision`, `action`, `outcome`, `procedure`, `preference` |
| `entities` | list[string] | No | Entity names to link via ABOUT edges. Created if not found. |
| `confidence` | float | No | 0.0–1.0. Default `1.0` |
| `valid_from` | string | No | ISO-8601 timestamp when this became true. Default: now |
| `supersedes` | string | No | Node ID to supersede (closes its `valid_until`, adds SUPERSEDES edge) |
| `session_id` | string | No | Attach to a specific session. Default: auto-created session |

**Returns:**

```json
{
  "node_id": "d_0019f2...",
  "linked_entity_ids": ["e_0019f2..."],
  "created_entity_ids": []
}
```

**Examples:**

```python
# Store a decision
memory_store(
    "Chose JWT over session cookies for auth_service — stateless horizontal scaling",
    kind="decision",
    entities=["auth_service"],
    confidence=0.9,
)

# Store a fact with temporal anchor
memory_store(
    "auth_service issues 15-minute access tokens with rotating refresh tokens",
    kind="fact",
    entities=["auth_service"],
    valid_from="2026-07-01T00:00:00",
)

# Supersede an old decision
memory_store(
    "Switched auth_service from JWT to Paseto v4 for stronger type safety",
    kind="decision",
    entities=["auth_service"],
    supersedes="d_0019f2...",
)
```

!!! note "Rich decision metadata"
    To store `rationale` and `alternatives_rejected` on a decision, use the Python library API:
    ```python
    from nervapack.memory import MemoryStore
    store = MemoryStore()
    store.add_node(
        kind="decision",
        content="Chose JWT for auth_service",
        data={
            "rationale": "Stateless tokens enable horizontal scaling without shared session store.",
            "alternatives_rejected": ["server-side sessions", "PASETO"],
        },
        confidence=0.9,
    )
    ```
    These fields are then surfaced by `memory_why`. The MCP `memory_store` tool does not expose a `data` parameter by design — it keeps the tool surface minimal.

---

### `memory_recall`

Retrieve the most relevant memories for a query, packed into a token budget.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Natural language search phrase |
| `budget_tokens` | int | No | Maximum tokens in result. Default `500` |
| `kinds` | list[string] | No | Filter to specific node kinds |
| `as_of` | string | No | ISO-8601 timestamp for point-in-time recall |
| `hops` | int | No | Graph expansion depth. Default `1`, max `2` |

**Returns:** Markdown string, always `≤ budget_tokens`.

**Pipeline:**

1. FTS5 BM25 search (tries exact → prefix → OR variants for partial matches)
2. Graph expansion: neighbours inherit 0.6× parent relevance per hop
3. Temporal mask: exclude superseded and tombstoned nodes
4. Scoring: `relevance × recency × frequency × connectivity`
5. Budget packing: greedy fill to 90% budget, 10% reserved for provenance

**Examples:**

```python
# Basic recall
memory_recall("why JWT for auth")

# Budget-limited to 200 tokens
memory_recall("deployment procedure", budget_tokens=200)

# Only facts, point-in-time
memory_recall("auth_service", kinds=["fact"], as_of="2026-01-15T00:00:00")

# 2-hop expansion to pull in connected context
memory_recall("payment flow", hops=2)
```

**Output:**

```markdown
## Memory recall: "why JWT for auth" (as of 2026-07-03 · 3 items · 171/500 tokens)

### Decisions
- [d_0019f2...] 2026-07-03 · conf 0.90 — Chose JWT over session cookies for auth_service

### Facts
- [f_0019f2...] 2026-07-03 · conf 1.00 — auth_service issues 15-minute access tokens

### Entities
- [e_0019f2...] 2026-07-03 · conf 1.00 — auth_service

### Provenance
d_0019f2... ← session s_0019f2... · f_0019f2... ← session s_0019f2...
```

---

### `memory_about`

Entity dossier: all currently valid nodes linked to one entity, newest first.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity` | string | Yes | Entity name or ID. Case-insensitive, alias-aware. |
| `budget_tokens` | int | No | Default `500` |

**Returns:** Markdown block (same format as `memory_recall`).

**Example:**

```python
memory_about("auth_service")
memory_about("AuthService")       # same result — alias-normalised
memory_about("e_0019f2...")       # by node ID
```

---

### `memory_why`

Explain a decision: content, rationale, rejected alternatives, caused outcomes, and supersession chain.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision_ref` | string | Yes | Node ID (e.g. `d_0019f2...`) or a search phrase (best FTS match among decision nodes) |

**Returns:** Markdown string.

**Example:**

```python
memory_why("d_0019f2...")              # by ID
memory_why("JWT auth decision")        # by phrase — FTS best match among decisions
```

**Output:**

```markdown
## Decision: d_0019f2...
**Chose JWT over session cookies for auth_service**
Date: 2026-07-03T10:00:00+00:00  ·  Confidence: 0.90

**Rationale:** JWT is stateless and enables horizontal scaling without shared session store.
**Rejected alternatives:** server-side sessions, PASETO

**Outcomes:**
- [o_0019f3...] Auth service latency dropped 12ms after removing session DB calls

**Supersedes:**
- [d_0019f1...] Chose session cookies for auth_service
```

---

### `memory_timeline`

Chronological trace of all memories matching a topic, including superseded nodes.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | string | Yes | Search phrase |
| `since` | string | No | ISO-8601 lower bound on `recorded_at` |

**Returns:** Markdown timeline, oldest first.

**Example:**

```python
memory_timeline("auth_service")
memory_timeline("JWT", since="2026-01-01T00:00:00")
```

**Output:**

```markdown
## Memory timeline: 'auth_service'

- [d_0019f1...] 2026-01-01 · conf 1.00 [superseded by d_0019f2...] — Chose session cookies for auth_service
- [d_0019f2...] 2026-07-03 · conf 0.90 — Chose JWT over session cookies for auth_service
```

---

### `memory_end_session`

Close the current session and store an outcome summary.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `summary` | string | Yes | What was accomplished or decided in this session |

**Returns:**

```json
{
  "closed_session_id": "s_0019f2...",
  "outcome_id": "o_0019f3..."
}
```

**What it does:**

1. Sets `valid_until = now` on the current session node.
2. Creates an `outcome` node with the summary text, linked via `OCCURRED_IN`.
3. Queues consolidation (Phase 2, currently a no-op).
4. Resets the in-process session so the next tool call opens a fresh one.

**Example:**

```python
memory_end_session(
    "Implemented JWT auth for auth_service; chose refresh-token rotation over opaque tokens."
)
```

---

### `memory_forget`

Tombstone (soft-delete) or hard-purge nodes.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node_id` | string | No | Specific node to forget |
| `entity` | string | No | Forget all nodes linked to this entity via ABOUT edges |
| `before` | string | No | Forget all nodes recorded before this ISO-8601 timestamp |
| `purge` | bool | No | `True` = hard-delete (irreversible). Default `False` |

At least one of `node_id`, `entity`, or `before` must be provided. Multiple selectors are combined with OR.

**Returns:**

```json
{
  "count": 3,
  "mode": "tombstone",
  "ids": ["f_0019f2...", "f_0019f3...", "f_0019f4..."]
}
```

**Tombstone vs purge:**

| | Tombstone | Purge |
|--|--|--|
| Row deleted | No | Yes |
| FTS entry removed | No | Yes (DELETE trigger) |
| Visible in timeline | Yes | No |
| Reversible | Yes (update `tombstoned=0`) | No |
| Sanctioned use | Routine forgetting | GDPR / hard removal |

**Examples:**

```python
# Soft-forget a node
memory_forget(node_id="f_0019f2...")

# Soft-forget everything about an entity
memory_forget(entity="old_payment_service")

# Forget all nodes before a date
memory_forget(before="2026-01-01T00:00:00")

# Hard-purge a specific node (irreversible)
memory_forget(node_id="f_0019f2...", purge=True)
```

---

### `memory_verify`

Confirm or refute a memory node, updating its confidence.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node_id` | string | Yes | Node to verify |
| `status` | string | Yes | `"confirm"` or `"refute"` |

**Semantics:**

| Status | Effect |
|--------|--------|
| `confirm` | `confidence = min(1.0, confidence + 0.1)` |
| `refute` | `confidence = confidence × 0.5`, `valid_until = now` (closes the node) |

**Returns:**

```json
{
  "node_id": "f_0019f2...",
  "confidence": 0.95,
  "status": "confirmed"
}
```

**Example:**

```python
# Agent tests a fact and it holds
memory_verify("f_0019f2...", "confirm")

# Agent discovers a fact is wrong — close it
memory_verify("f_0019f2...", "refute")
```

---

### `memory_stats`

Summary statistics for the memory store.

**Parameters:** None.

**Returns:**

```json
{
  "kind_counts": {"fact": 14, "decision": 5, "entity": 3, "session": 4, "outcome": 4},
  "db_size_bytes": 49152,
  "top_entities": [
    {"id": "e_0019f2...", "content": "auth_service", "degree": 6},
    {"id": "e_0019f3...", "content": "payment_service", "degree": 2}
  ],
  "namespaces": ["default"]
}
```

**Example:**

```python
memory_stats()
```

---

## Recommended Agent Workflow

```
Session start
  └─ memory_recall("task context", budget_tokens=300)   # load prior context
       │
       │  ... agent works ...
       │
  ├─ memory_store("decision", kind="decision", entities=[...])
  ├─ memory_store("fact discovered", kind="fact")
  │
  └─ memory_end_session("Summary of what was done")      # session end
```

**When to call each tool:**

| Tool | When |
|------|------|
| `memory_recall` | At session start — before answering questions that depend on history |
| `memory_store` | Any decision, fact, or outcome worth preserving |
| `memory_about` | When asked about a specific service or component |
| `memory_why` | When asked to justify or explain a past decision |
| `memory_timeline` | When the user asks about the history of something |
| `memory_verify` | When a prior fact is confirmed or contradicted by new evidence |
| `memory_forget` | When explicitly asked to forget something |
| `memory_end_session` | When a task or conversation ends |
| `memory_stats` | Diagnostic/administrative use |

---

## Running the Server Directly

```bash
# stdio (default, for MCP clients)
nervapack-memory-mcp

# Custom database
NERVAPACK_MEMORY_DB=/path/to/memory.db nervapack-memory-mcp
```

---

## Cross-Process Demo

Verify that session A's memory is recalled by session B in a separate process:

```bash
# Session A — store
NERVAPACK_MEMORY_DB=/tmp/demo.db python examples/seed_demo.py session_a

# Session B — recall (fresh process)
NERVAPACK_MEMORY_DB=/tmp/demo.db python examples/seed_demo.py session_b
```

Expected output from session B:

```
## Memory recall: "why JWT for auth" (as of 2026-07-03 · 3 items · 171/500 tokens)

### Decisions
- [d_...] 2026-07-03 · conf 0.90 — Chose JWT over session cookies for auth_service

### Facts
- [f_...] 2026-07-03 · conf 1.00 — auth_service issues 15-minute access tokens with rotating refresh tokens

### Entities
- [e_...] 2026-07-03 · conf 1.00 — auth_service

Token count: 171/500  ✓
```

---

## See Also

- [Memory concept guide](../user-guide/concepts/memory.md) — data model, recall pipeline, bi-temporal semantics
- [memory CLI](../user-guide/commands/memory.md) — `init`, `stats`, `forget`, `export`
- [Knowledge Graph MCP Server](mcp-server.md) — code graph tools: `query_codebase`, `graph_status`, `list_entities`
