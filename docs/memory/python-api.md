# Python API

`nervapack.memory` is a plain Python library — no server, no MCP, no agent framework required. Import `MemoryStore` and `recall` and you have a persistent memory layer in three lines.

```bash
pip install "nervapack[memory]"
```

---

## Core imports

```python
from nervapack.memory import (
    MemoryStore,      # The database — store, retrieve, manage nodes
    recall,           # Scored, budget-capped recall returning Markdown
    recall_timeline,  # Chronological trace of a topic
)
```

---

## MemoryStore

`MemoryStore` is the low-level interface. It manages the SQLite database, schema, nodes, edges, sessions, and namespaces.

### Initialisation

```python
from nervapack.memory import MemoryStore

# Auto-resolves to .nervapack/memory.db (walks up from cwd, then ~/.nervapack/)
store = MemoryStore()

# Explicit path
store = MemoryStore(db_path="/path/to/memory.db")

# Named namespace (isolates all reads and writes)
store = MemoryStore(namespace="project_b")

# Override via environment variable (useful in production / testing)
# export NERVAPACK_MEMORY_DB=/shared/memory.db
store = MemoryStore()
```

### add_node — store a memory

```python
node_id = store.add_node(
    kind="decision",          # fact | decision | action | outcome | entity | procedure | preference
    content="Chose JWT for auth — stateless horizontal scaling",
    confidence=0.9,           # 0.0–1.0, default 1.0
    session_id=sid,           # link to a session node (optional)
    valid_from=None,          # ISO-8601 or None (defaults to now)
    data={                    # arbitrary JSON metadata
        "rationale": "No session store needed",
        "alternatives_rejected": ["session cookies", "opaque tokens"],
    },
)
# Returns e.g. "d_0019f2b3c4d5e6f7a8b9c0d1e2f3a4b5"
```

**Node kind prefixes:**

| Kind | Prefix | Use for |
|------|--------|---------|
| `session` | `s_` | A unit of work (task, conversation, request) |
| `fact` | `f_` | Observed truth |
| `decision` | `d_` | A choice made, with optional rationale |
| `action` | `a_` | Something that was done |
| `outcome` | `o_` | Result of an action or decision |
| `entity` | `e_` | Named service, component, user, or concept |
| `procedure` | `p_` | Repeatable steps |
| `preference` | `pr_` | A standing preference or convention |

### get_node

```python
node = store.get_node("d_0019f2...")
# Returns a sqlite3.Row (dict-like) or None
print(node["content"])
print(node["confidence"])
print(node["recorded_at"])
```

### add_edge — link nodes

```python
store.add_edge(
    src="d_0019f2...",   # source node id
    dst="e_0019f3...",   # destination node id
    kind="ABOUT",        # ABOUT | OCCURRED_IN | SUPERSEDES | CONTRADICTS | CAUSED | DERIVED_FROM | TOUCHES
)
```

### tombstone / purge

```python
# Soft-delete (recoverable — sets tombstoned=1, excluded from recall)
count = store.tombstone(["f_0019f2...", "f_0019f3..."])

# Hard-delete (irreversible — removes row, FTS entry, edges)
count = store.purge(["f_0019f2..."])
```

### Sessions

```python
from nervapack.memory.store import _now_iso

# Open a session
sid = store.add_node("session", "JWT auth refactor",
                     data={"started_at": _now_iso(), "agent_id": "my_bot"})

# List all sessions
sessions = store.list_sessions(limit=20)
for s in sessions:
    print(s["id"], s["content"], s["node_count"])

# Close a session (set valid_until)
store.close_session(sid)

# Delete a session and all its nodes
result = store.delete_session(sid, purge=False)  # purge=True for hard delete
```

### Namespaces

```python
# All nodes written to store are tagged with store.namespace
store = MemoryStore(namespace="chatbot_user_42")
store.add_node("fact", "User prefers concise answers")

# Switch namespace (all subsequent reads/writes use the new namespace)
store.namespace = "chatbot_user_99"

# List all namespaces in the database
s = store.stats()
print(s["namespaces"])   # ["default", "chatbot_user_42", "chatbot_user_99"]
```

### stats

```python
s = store.stats()
print(s["kind_counts"])    # {"fact": 14, "decision": 5, ...}
print(s["db_size_bytes"])  # 49152
print(s["namespaces"])     # ["default"]
print(s["top_entities"])   # [{"id": "e_...", "content": "auth_service", "degree": 6}]
```

### FTS search

```python
results = store.fts_search("JWT authentication", limit=10, kinds=["decision", "fact"])
for r in results:
    print(r["id"], r["content"])
```

---

## recall — scored, budget-capped retrieval

`recall` runs the full pipeline: FTS5 search → graph expansion → temporal mask → scoring → budget packing.

```python
from nervapack.memory import recall

text = recall(
    store,
    query="authentication design",
    budget_tokens=300,      # hard limit on output length, default 500
    kinds=None,             # filter to specific kinds, e.g. ["fact", "decision"]
    as_of=None,             # ISO-8601 for point-in-time recall
    hops=1,                 # graph expansion depth (0–2)
    min_confidence=0.0,     # exclude nodes below this threshold
)
print(text)
```

**Return value:** always a Markdown string, always `≤ budget_tokens`. Safe to inject directly into any prompt.

**Scoring formula:**

```
score = relevance × recency × frequency × connectivity

relevance   = normalised BM25 rank (0–1)
recency     = exp(−ln2 × age_days / 30)   ← 30-day half-life
frequency   = 1 + 0.1 × ln(1 + access_count)
connectivity= 1 + 0.1 × ln(1 + node_degree)
```

After packing, `access_count` and `last_accessed` are incremented on every returned node.

### recall_timeline

Chronological trace of all nodes matching a topic, including superseded versions:

```python
from nervapack.memory import recall_timeline

text = recall_timeline(
    store,
    topic="auth_service",
    since=None,             # ISO-8601 lower bound on recorded_at
    budget_tokens=1000,
)
print(text)
```

**Output:**

```
## Memory timeline: 'auth_service'

- [d_0019f1...] 2026-01-01 · conf 1.00 [superseded by d_0019f2...] — Chose session cookies for auth_service
- [d_0019f2...] 2026-07-03 · conf 0.90 — Chose JWT over session cookies for auth_service
```

---

## Entity resolution helper

Entity names are normalised so `AuthService`, `auth_service`, and `auth-service` resolve to the same node. Use `resolve_entities` when building your own store pipeline:

```python
from nervapack.memory import resolve_entities

linked_ids, created_ids = resolve_entities(store, ["AuthService", "payment_service"])
for entity_id in linked_ids:
    store.add_edge(node_id, entity_id, "ABOUT")
```

---

## Complete example — chatbot memory

```python
from nervapack.memory import MemoryStore, recall

class ChatMemory:
    def __init__(self, user_id: str):
        self.store = MemoryStore(namespace=f"user_{user_id}")

    def remember(self, content: str, kind: str = "fact") -> str:
        return self.store.add_node(kind, content)

    def context(self, topic: str, tokens: int = 300) -> str:
        return recall(self.store, topic, budget_tokens=tokens)


mem = ChatMemory("alice")
mem.remember("User prefers concise answers under 3 sentences", kind="preference")
mem.remember("User is building a FastAPI app with PostgreSQL", kind="fact")
mem.remember("User wants to avoid ORMs — prefers raw asyncpg", kind="preference")

# At the start of the next conversation turn:
context = mem.context("what the user is building")
print(context)
# → "## Memory recall … User is building a FastAPI app …"
```

See the full chatbot guide for a multi-turn conversation example: [Chatbot memory](use-cases/chatbot.md).

---

## See Also

- [Chatbot use case](use-cases/chatbot.md) — full multi-turn chatbot with message history and preference recall
- [Concepts & data model](concepts.md) — bi-temporal schema, FTS5, edge kinds
- [MCP Tools](mcp-tools.md) — use the same store from Claude Code / Cursor without writing Python
- [CLI](cli.md) — inspect, export, and manage the store from the command line
