# Memory

`nervapack.memory` is a persistent, structured memory layer for any LLM application — chatbots, AI coding agents, multi-agent pipelines, decision logs. It stores atomic facts, decisions, preferences, and outcomes in a local SQLite database. On recall it scores and packs results into a token budget and returns them as a Markdown block ready to inject into a prompt.

It runs 100% offline. No embeddings, no cloud calls, no vector database. A fresh recall on a 100-node store completes in under 5ms.

---

## What it does

```
your app
  │
  ├─ store("Chose JWT for auth", kind="decision", entities=["auth_service"])
  │       ↓
  │   SQLite + FTS5 + bi-temporal graph
  │       ↑
  └─ recall("why JWT?", budget_tokens=200)
       → "## Memory recall … Chose JWT … conf 0.90 … 171/200 tokens"
```

- **Persist anything** — facts, decisions, preferences, procedures, outcomes, entities
- **Recall with a budget** — get the most relevant memories in ≤ N tokens, guaranteed
- **Cross-session** — memories written in session 1 are available in session 1000
- **Temporal correctness** — superseded decisions never surface as current truth
- **Namespace isolation** — multiple projects or agents share one database file without collision
- **Code-linked** — when used with a NervaPack code graph, memories link to the exact file and line they describe (`memory_for_code`, `memory_to_code`, `memory_verify_staleness`)

---

## Install

```bash
pip install "nervapack[memory]"
```

Initialise the store (creates `.nervapack/memory.db` in the current directory):

```bash
nervapack-memory init
```

---

## Choose your interface

| Interface | Best for | Docs |
|-----------|----------|------|
| **Python library** | Chatbots, custom apps, scripts | [Python API](python-api.md) |
| **MCP tools** | Claude Code, Cursor, any MCP client | [MCP Tools](mcp-tools.md) |
| **CLI** | Admin, inspection, seeding, export | [CLI](cli.md) |

---

## Use cases

<div class="grid cards" markdown>

-   :material-chat: **Chatbot memory**

    ---

    Chatbot that remembers user preferences, prior topics, and past answers across conversations. No embeddings, no vector DB, pure Python.

    [:octicons-arrow-right-24: Chatbot guide](use-cases/chatbot.md)

-   :material-robot: **AI coding agent**

    ---

    Claude Code / Cursor agent that recalls project decisions and conventions at the start of every session. The MCP workflow with TOUCHES bridge to the code graph.

    [:octicons-arrow-right-24: Coding agent guide](use-cases/coding-agent.md)

-   :material-graph: **Multi-agent systems**

    ---

    Two or more agents sharing one memory database using namespace isolation. Agent A writes, Agent B reads. No cross-namespace leaks.

    [:octicons-arrow-right-24: Multi-agent guide](use-cases/multi-agent.md)

-   :material-file-document-edit: **Decision log / ADR store**

    ---

    Architecture Decision Record store — import existing ADRs, query why decisions were made, trace supersession history, and surface stale decisions when code changes.

    [:octicons-arrow-right-24: Decision log guide](use-cases/adr-store.md)

</div>

---

## 60-second example

```python
from nervapack.memory import MemoryStore, recall

store = MemoryStore()  # auto-creates .nervapack/memory.db

# Store — session is created automatically on first write
store.add_node("decision", "Chose JWT for auth — stateless horizontal scaling",
               confidence=0.9,
               data={"rationale": "No session store needed",
                     "alternatives_rejected": ["session cookies", "opaque tokens"]})

store.add_node("fact", "JWT tokens expire after 15 minutes")
store.add_node("preference", "All APIs return ISO-8601 timestamps in UTC")

# Recall — scored, budget-capped, ready to inject into any prompt
context = recall(store, "authentication design", budget_tokens=300)
print(context)
```

**Output:**

```
## Memory recall: "authentication design" (as of 2026-07-05 · 2 items · 171/300 tokens)

### Decisions
- [d_0019f2...] 2026-07-05 · conf 0.90 — Chose JWT for auth — stateless horizontal scaling

### Facts
- [f_0019f2...] 2026-07-05 · conf 1.00 — JWT tokens expire after 15 minutes

### Provenance
d_0019f2... ← session s_0019f2... · f_0019f2... ← session s_0019f2...
```

---

## Key design properties

**Token budget invariant.** `recall()` never returns more than `budget_tokens` tokens. It packs the highest-scoring nodes greedily, dropping from the end until the result fits. You can safely inject the output directly into your prompt without measuring it first.

**Supersede, never delete.** When a fact changes, create a new node and pass `supersedes="old_node_id"`. The old node's validity window is closed; it disappears from recall but remains in `memory_timeline`. Soft-delete (`tombstone`) and hard-purge are available for GDPR/explicit removal.

**No network calls.** All storage, retrieval, and scoring runs locally. FTS5 handles text search — no embeddings at query time. Latency is SQLite I/O, not network I/O.

**One file, multiple namespaces.** All data lives in a single SQLite file. Use `memory_switch_namespace("project_b")` to isolate memory for separate projects or agents. `memory_stats()` reports all namespaces.

---

## See also

- [Concepts & data model](concepts.md) — bi-temporal schema, recall pipeline, entity resolution, scoring formula
- [Roadmap](roadmap.md) — what's shipped, what's next
