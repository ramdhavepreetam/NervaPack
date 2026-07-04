# nervapack.memory — Agent Memory Layer

`nervapack.memory` gives AI agents a structured, persistent memory that survives across sessions. It stores atomic facts, decisions, outcomes, and other knowledge in a local SQLite database with FTS5 full-text search and a bi-temporal data model. On recall it returns a scored, budget-capped Markdown block that fits inside your LLM's context window.

---

## The Problem It Solves

Standard RAG retrieves chunks of text — blobs that may be stale, duplicated, or irrelevant to the current task. Agent memory needs something different:

- **Cross-session persistence** — a decision made in session 1 must be recalled in session 5.
- **Atomic facts, not chunks** — "Chose JWT for stateless auth" is one node (~8 tokens), not a 400-token transcript segment.
- **Temporal correctness** — old decisions superseded by new ones must not surface as current truth.
- **Token discipline** — every recall is guaranteed to fit within a configurable budget.

---

## Data Model

### Node Kinds

| Kind | Prefix | Purpose |
|------|--------|---------|
| `session` | `s_` | Wraps a single agent task; scopes other nodes |
| `fact` | `f_` | Observed truth ("auth_service issues 15-min tokens") |
| `decision` | `d_` | Chosen option with optional rationale and rejected alternatives |
| `action` | `a_` | Something an agent did ("deployed v2 to staging") |
| `outcome` | `o_` | Result of an action or decision |
| `entity` | `e_` | Named service, component, or concept |
| `procedure` | `p_` | Repeatable steps ("how to roll a deploy") |
| `preference` | `pr_` | User or team preference ("always use snake_case") |

Node IDs are time-sortable: `{prefix}_{13-hex-timestamp}{16-hex-random}`.

### Edge Kinds

| Kind | Meaning |
|------|---------|
| `ABOUT` | Node is about an entity |
| `OCCURRED_IN` | Node belongs to a session |
| `SUPERSEDES` | New node replaces old (closes old `valid_until`) |
| `CONTRADICTS` | Node conflicts with another |
| `CAUSED` | Decision or action produced this outcome |
| `DERIVED_FROM` | Fact is inferred from another |
| `TOUCHES` | (Phase 3) Memory links to a live code node |

### Schema Overview

```sql
mem_nodes      -- all knowledge nodes (bi-temporal, namespaced)
mem_edges      -- typed directed edges
mem_aliases    -- entity name aliases (COLLATE NOCASE)
mem_review_queue -- Phase 2 consolidation queue (schema present, not yet active)
mem_fts        -- FTS5 external-content virtual table (synced via triggers)
```

The full DDL is in `src/nervapack/memory/schema.sql`.

---

## Bi-Temporal Model

Every node carries two time axes:

| Column | Axis | Meaning |
|--------|------|---------|
| `valid_from` | World time | When the fact became true in the world |
| `valid_until` | World time | When the fact stopped being true (`NULL` = still current) |
| `recorded_at` | Learn time | When the agent stored the node |

**Supersede, never delete.** When a fact changes, a new node is created and linked via a `SUPERSEDES` edge. The old node's `valid_until` is closed to the timestamp of supersession. Soft-delete (`tombstoned=1`) and hard-purge (`DELETE`) are supported for forgotten information; hard-purge is only sanctioned through `memory_forget(purge=True)` and the CLI `forget --purge` command.

### Example

```
d_aaa  "Chose session cookies for auth"   valid_from=2026-01-01  valid_until=2026-06-01
  │  ←[SUPERSEDES]
d_bbb  "Chose JWT for auth"              valid_from=2026-06-01  valid_until=NULL (current)
```

`memory_recall("auth mechanism")` returns only `d_bbb`.
`memory_recall("auth mechanism", as_of="2026-03-15")` returns only `d_aaa`.
`memory_timeline("auth")` returns both, with `d_aaa` marked `[superseded by d_bbb]`.

---

## Recall Pipeline

When you call `memory_recall(query, budget_tokens=500)` the following stages run in sequence:

```
query
  │
  1. FTS5 search (BM25)
  │   ├─ exact phrase
  │   ├─ prefix per token (token*)    } tried in order until results found
  │   └─ OR fallback (tok1 OR tok2)  }
  │
  2. Graph expansion (up to 2 hops)
  │   └─ neighbours inherit 0.6× parent relevance per hop
  │
  3. Temporal mask
  │   ├─ as_of=None  → valid_until IS NULL AND not superseded AND not tombstoned
  │   └─ as_of=T     → valid_from ≤ T AND (valid_until IS NULL OR valid_until > T)
  │
  4. Scoring
  │   score = relevance × recency × frequency × connectivity
  │   ├─ relevance   = normalised BM25 rank (0–1)
  │   ├─ recency     = exp(−ln2 × age_days / 30)  [30-day half-life]
  │   ├─ frequency   = 1 + 0.1 × ln(1 + access_count)
  │   └─ connectivity= 1 + 0.1 × ln(1 + degree)
  │
  5. Budget packing
      ├─ Group by kind, render as Markdown lines
      ├─ Greedily fill to 90% of budget
      ├─ Reserve 10% for provenance footer
      └─ Hard invariant: result never exceeds budget_tokens
```

After packing, `access_count` and `last_accessed` are incremented on every returned node.

---

## Entity Resolution

Entity names are normalised so `AuthService`, `auth_service`, and `auth-service` all resolve to the same entity node. When `memory_store` receives `entities=["AuthService"]`:

1. Look up alias `AuthService` (case-insensitive via `COLLATE NOCASE`).
2. If not found, strip separators and try normalised form (`authservice`).
3. If not found, run FTS on entity content.
4. If still not found, create a new `entity` node and register three alias forms: original, `snake_case`, and normalised.

---

## Storage

The database is a single SQLite file. Location resolution order:

1. `NERVAPACK_MEMORY_DB` environment variable
2. Explicit `db_path` argument to `MemoryStore`
3. `.nervapack/memory.db` (walks up from `cwd`)
4. `~/.nervapack/memory.db` (global fallback, created automatically)

WAL mode is enabled so concurrent readers never block writes.

---

## Token Budget

The `TokenCounter` protocol (in `pack.py`) has two implementations:

| Implementation | Install | Formula |
|---|---|---|
| `CharTokenCounter` | Built-in (no deps) | `ceil(len(text) / 4)` |
| tiktoken-backed | `pip install nervapack[tokens]` | `cl100k_base` encoding |

`pack()` enforces the budget with a hard invariant — it drops items from the end until the total fits, then re-renders. The result is always `≤ budget_tokens`.

---

## Output Format

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

Sections appear only for kinds that have matching results. Provenance maps each node back to the session that created it.

---

## Design Decisions

### Standalone SQLite, not NetworkX/ChromaDB

The existing NervaPack graph (NetworkX GraphML + ChromaDB) is immutable between ingest cycles and provides no FTS5 or temporal semantics. A separate SQLite file with native FTS5 and a bi-temporal schema is the right substrate for mutable, session-scoped agent memory.

### Facts, Not Chunks

Recall returns atomic assertions — 8–30 tokens each — with explicit provenance. This is more useful to an LLM than a 400-token transcript segment because:
- The LLM receives structured, de-duplicated claims.
- Confidence and temporal validity are first-class metadata.
- Budget usage is predictable.

### No Network Calls at Runtime

All storage, retrieval, and scoring is local. No embeddings are generated at query time (FTS5 handles text search). This keeps latency low and the system fully offline.

### Phase 2 (Not Yet Active)

`NoopConsolidator` is a stub for a future consolidation worker that will use an LLM to merge session transcripts into durable facts. `mem_review_queue` is schema-present but not yet processed. The `EmbeddingResolver` stub exists for a future entity-resolution path that uses vector similarity. Neither generates LLM calls in the current (Phase 1) implementation.

---

## See Also

- [Memory MCP Server](../../integrations/memory-mcp.md) — 9 MCP tools exposed to Claude Code / Cursor
- [memory CLI](../commands/memory.md) — `init`, `stats`, `forget`, `export`
- [Architecture](architecture.md) — how memory relates to the code graph
