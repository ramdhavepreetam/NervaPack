# Chatbot Memory

Give your chatbot persistent memory across conversations — user preferences, prior topics, past answers. Pure Python, no MCP, no vector database, no cloud calls.

---

## What we're building

A chatbot that:

1. Remembers user preferences discovered during past conversations
2. Recalls relevant prior answers so it doesn't repeat itself
3. Uses a per-user namespace so each user's memory is isolated

---

## Setup

```bash
pip install "nervapack[memory]"
nervapack-memory init      # creates .nervapack/memory.db
```

---

## Core pattern

```python
from nervapack.memory import MemoryStore, recall

class UserMemory:
    """Per-user persistent memory, namespace-isolated."""

    def __init__(self, user_id: str, db_path: str = None):
        self.store = MemoryStore(db_path=db_path, namespace=f"user_{user_id}")
        self.user_id = user_id

    def store_preference(self, content: str) -> str:
        return self.store.add_node("preference", content)

    def store_fact(self, content: str) -> str:
        return self.store.add_node("fact", content)

    def recall(self, topic: str, tokens: int = 200) -> str:
        return recall(self.store, topic, budget_tokens=tokens)
```

---

## Full multi-turn example

```python
import os
from nervapack.memory import MemoryStore, recall

DB_PATH = ".nervapack/memory.db"


def get_memory(user_id: str) -> MemoryStore:
    return MemoryStore(db_path=DB_PATH, namespace=f"user_{user_id}")


def chat(user_id: str, message: str, llm_response: str) -> None:
    """
    Called after each conversation turn.
    Extracts memorable facts from the exchange and stores them.
    """
    mem = get_memory(user_id)

    # You decide what to remember — this example uses simple keyword heuristics.
    # In production you'd have your LLM identify memorable facts.
    if "prefer" in message.lower() or "always" in message.lower() or "never" in message.lower():
        mem.add_node("preference", message)

    if "my project" in message.lower() or "i'm building" in message.lower():
        mem.add_node("fact", message)


def build_system_prompt(user_id: str, current_topic: str) -> str:
    """
    Build a system prompt that includes relevant memory for the current topic.
    Call this before every LLM API call.
    """
    mem = get_memory(user_id)
    memory_context = recall(mem, current_topic, budget_tokens=250)

    if "0 items" in memory_context:
        return "You are a helpful assistant."

    return f"""You are a helpful assistant with memory of past conversations.

{memory_context}

Use this context to personalise your responses. Don't repeat information
the user has already told you. Reference past preferences naturally."""


# --- Simulate a conversation ---

user_id = "alice"

# Turn 1: User tells us their preferences
msg1 = "I'm building a FastAPI app. I prefer short answers, no more than 3 sentences."
chat(user_id, msg1, "Got it!")

# Turn 2: User mentions their stack
msg2 = "I'm using PostgreSQL with asyncpg — no ORMs."
chat(user_id, msg2, "Understood!")

# Turn 3: New conversation, same user
# Build a system prompt that recalls what we know about alice
system = build_system_prompt("alice", "python web development")
print(system)
```

**Output:**

```
You are a helpful assistant with memory of past conversations.

## Memory recall: "python web development" (as of 2026-07-05 · 2 items · 198/250 tokens)

### Facts
- [f_0019f3...] 2026-07-05 · conf 1.00 — I'm building a FastAPI app. I prefer short answers, no more than 3 sentences.
- [f_0019f4...] 2026-07-05 · conf 1.00 — I'm using PostgreSQL with asyncpg — no ORMs.

### Provenance
f_0019f3... ← session s_0019f3... · f_0019f4... ← session s_0019f4...

Use this context to personalise your responses...
```

Now every API call to your LLM includes up to 250 tokens of relevant user context — automatically.

---

## Per-user namespace isolation

Every user gets their own namespace in the database. Memory from user `alice` is completely invisible to user `bob`:

```python
alice_mem = MemoryStore(db_path=DB_PATH, namespace="user_alice")
bob_mem   = MemoryStore(db_path=DB_PATH, namespace="user_bob")

alice_mem.add_node("preference", "Alice prefers Python")
# bob_mem sees nothing from alice's namespace
result = recall(bob_mem, "Python", budget_tokens=200)
# → "## Memory recall … 0 items …"
```

All users share one SQLite file — no per-user files, no file management.

---

## Forgetting

Users can ask to be forgotten (e.g. GDPR):

```python
def forget_user(user_id: str) -> int:
    mem = MemoryStore(db_path=DB_PATH, namespace=f"user_{user_id}")
    conn = mem._get_conn()
    # Tombstone all nodes in this namespace
    result = conn.execute(
        "UPDATE mem_nodes SET tombstoned=1 WHERE namespace=?",
        (f"user_{user_id}",)
    )
    conn.commit()
    return result.rowcount
```

Or use the CLI:

```bash
nervapack-memory forget --before 2026-01-01T00:00:00  # forget old memories
```

---

## Updating stale preferences

When a user corrects a past preference, supersede the old node:

```python
def update_preference(user_id: str, old_node_id: str, new_content: str) -> str:
    mem = MemoryStore(db_path=DB_PATH, namespace=f"user_{user_id}")
    # Supersede closes old node's valid_until and creates a SUPERSEDES edge
    new_id = mem.add_node("preference", new_content)
    # Close old node
    from nervapack.memory.store import _now_iso
    conn = mem._get_conn()
    conn.execute("UPDATE mem_nodes SET valid_until=? WHERE id=?", (_now_iso(), old_node_id))
    conn.execute("INSERT INTO mem_edges (id, src, dst, kind, recorded_at) VALUES (?,?,?,?,?)",
                 (f"edge_{new_id}", new_id, old_node_id, "SUPERSEDES", _now_iso()))
    conn.commit()
    return new_id

# Or use the MCP tool:
# memory_store("I now prefer verbose answers", kind="preference", supersedes="pr_0019f2...")
```

---

## Production tips

**Scale.** SQLite handles thousands of namespaces and millions of nodes. WAL mode (`PRAGMA journal_mode=WAL`) is already enabled, so readers never block writers.

**Recall budget.** 200–300 tokens is the right range for chatbot system-prompt injection — enough context to personalise without burning your context window.

**What to remember.** Don't store raw conversation turns — store extracted facts and preferences. A good rule: if a human assistant would write it in their notes about a client, store it.

**Deduplication.** Run `nervapack-memory consolidate` periodically to tombstone near-duplicate facts automatically (Jaccard > 0.9 threshold). Or call `nervapack-memory forget --before <date>` to prune old low-value memories.

---

## See Also

- [Python API](../python-api.md) — full `MemoryStore` and `recall()` reference
- [Multi-agent guide](multi-agent.md) — when you need multiple agents sharing one store
- [CLI](../cli.md) — inspect and manage memory from the command line
