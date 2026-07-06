# Concepts & Data Model

`nervapack.memory` stores knowledge as a typed, directed graph in SQLite — not as vector embeddings or raw text. This page explains the data model, the bi-temporal schema, how recall works, and the design decisions behind it.

!!! tip "Just want to use it?"
    Start with the [Overview](index.md) for a 60-second example, or jump to a [use case guide](use-cases/chatbot.md).

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
| `TOUCHES` | Memory node is about a named entity that maps to a code graph node |

### Schema Overview

```sql
mem_nodes        -- all knowledge nodes (bi-temporal, namespaced)
mem_edges        -- typed directed edges
mem_aliases      -- entity name aliases (COLLATE NOCASE)
mem_review_queue -- consolidation queue (populated on session close, processed by `consolidate` CLI)
mem_fts          -- FTS5 external-content virtual table (synced via triggers)
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
2. Convert CamelCase to snake_case and try that alias (`AuthService` → `auth_service`).
3. Strip all separators and try normalised form (`authservice`).
4. Run FTS on entity content.
5. If still not found, create a new `entity` node and register four alias forms: original, basic slug, CamelCase→snake_case, and separator-stripped.

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

### Rule-Based Consolidation (v0.5.0)

When a session closes via `memory_end_session`, a consolidation job is written to `mem_review_queue`. The `nervapack-memory consolidate` CLI command processes pending jobs: it deduplicates near-identical facts within each session using Jaccard word-overlap (threshold > 0.9) and tombstones the older duplicate. Future versions may use an LLM for semantic-level deduplication — the `Consolidator` protocol is designed for this.

### TOUCHES Bridge (v0.5.0)

When `memory_store` is called with entity names that match nodes in the code graph (`.nervapack/graph.graphml`), a `TOUCHES` edge is created from the memory node to the entity. The entity's `data` JSON is updated with `file_path`, `start_line`, `end_line`, and `graph_node_id`. This enables:

- `memory_for_code(file_path)` — "What decisions were made about this file?"
- `memory_to_code(memory_id)` — "Where in the code is this decision anchored?"
- `memory_verify_staleness()` — "Which of my memories about code are outdated?"

The code graph is loaded lazily when the first matching entity is stored. If the graph is not present, TOUCHES edges are silently skipped (memory works without the code graph).

### Namespace Isolation (v0.5.1)

Every node is tagged with a `namespace` (default `"default"`). All queries filter by namespace. Use `memory_switch_namespace("project_b")` or pass `namespace=` to `memory_store`, `memory_recall`, `memory_start_session`, or `memory_stats` to work in a different namespace. Switching resets the active session so cross-namespace OCCURRED_IN leaks can't happen. All namespaces share one SQLite file.

---

## See Also

- [Coding agent guide](use-cases/coding-agent.md) — full MCP workflow including the context-extender pattern
- [MCP Tools reference](mcp-tools.md) — all 17 MCP tools
- [CLI reference](cli.md) — `init`, `stats`, `search`, `show`, `forget`, `export`, `consolidate`, `import`
- [Python API](python-api.md) — direct Python usage without MCP
