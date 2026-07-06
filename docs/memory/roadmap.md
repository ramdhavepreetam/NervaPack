# Roadmap

## Shipped

### v0.4.5 — Foundation
- SQLite memory store with bi-temporal schema and FTS5
- 12 MCP tools: `memory_store`, `memory_recall`, `memory_about`, `memory_why`, `memory_timeline`, `memory_end_session`, `memory_forget`, `memory_verify`, `memory_stats`, `memory_start_session`, `memory_list_sessions`, `memory_clear_session`
- Named sessions, entity resolution with CamelCase normalisation, confidence filter on recall
- CLI: `init`, `stats`, `forget`, `export`, `search`, `show`, `start-session`, `sessions`, `delete-session`
- Token budget invariant (CharTokenCounter built-in, tiktoken optional)

### v0.5.0 — Integrations
- **Rule-based consolidation** — `memory_end_session` queues a job; `nervapack-memory consolidate` deduplicates near-identical facts (Jaccard > 0.9)
- **TOUCHES bridge** — `memory_store` with entity names matching code graph nodes creates TOUCHES edges with `file_path`, `start_line`, `end_line`
- **Reverse code lookup** — `memory_for_code(file_path)` and `memory_to_code(memory_id)` MCP tools
- **Bulk import** — `memory_import` MCP tool and `nervapack-memory import <file.json>` CLI command

### v0.5.1 — Multi-project & staleness (current)
- **Namespace isolation** — `memory_switch_namespace()` MCP tool; `namespace=` param on `memory_store`, `memory_recall`, `memory_stats`, `memory_start_session`
- **Staleness detection** — `memory_verify_staleness()` MCP tool: scans TOUCHES edges, compares file mtimes vs `recorded_at`, queues stale nodes for review
- **`get_pending_jobs(kind=...)` filter** — consolidation and staleness jobs no longer conflict
- 17 MCP tools total, 90 tests

---

## What's next

### Semantic / vector recall (future)
Today recall uses FTS5 keyword search. A query for `"auth service"` won't match a node that says `"JWT validation layer"` unless those words appear. Vector recall would use sentence embeddings to match by meaning.

**Planned implementation:** `sqlite-vec` extension + `sentence-transformers` (offline model). The `nervapack[vec]` extra is already stubbed in `pyproject.toml`. FTS5 and vector recall would run in parallel; results would be merged and re-scored.

**Why not yet:** adds a ~500MB model download and ~100ms latency per query. For the primary use cases (coding agent, chatbot with structured facts), FTS5 is sufficient because you control what you store — you write concise, keyword-rich nodes rather than embedding arbitrary prose.

### LLM-based consolidation (future)
Today consolidation uses Jaccard word-overlap (threshold > 0.9) to detect near-duplicates. This catches `"Chose JWT for auth"` vs `"Chose JWT for authentication"` but misses semantic equivalence like `"JWT is stateless"` vs `"tokens eliminate the need for a session store"`.

**Planned implementation:** plug-in `LLMConsolidator` that calls an LLM to cluster session facts and tombstone semantic duplicates. The `Consolidator` protocol is already designed for this — `NoopConsolidator` → `RuleBasedConsolidator` → `LLMConsolidator`.

**Why not yet:** LLM consolidation adds latency and cost at session close. For most use cases, rule-based deduplication is sufficient. LLM consolidation will be opt-in.

### Agent-to-agent collaboration primitives (future)
Shared namespace is today's mechanism for agent collaboration. Future work may include structured handoff nodes (a typed "handoff" kind), read-only namespace access controls, and a subscription mechanism so Agent B is notified when Agent A writes to the shared channel.

---

## Implementation stubs in the codebase

| Stub | File | What it blocks |
|------|------|---------------|
| `vec = []` extra | `pyproject.toml:51` | sqlite-vec + sentence-transformers install |
| `NoopConsolidator` | `consolidate.py:19` | Placeholder for LLMConsolidator |
| `Consolidator` protocol | `consolidate.py:10` | Interface for future LLM-based consolidation |

---

## See Also

- [Concepts & data model](concepts.md) — current architecture
- [GitHub Issues](https://github.com/ramdhavepreetam/NervaPack/issues) — request features or report bugs
