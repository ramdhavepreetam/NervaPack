# Multi-Agent Memory

Multiple agents sharing one memory database — with complete namespace isolation so agents can collaborate without stepping on each other's memory.

---

## When you need this

- A **planner agent** writes a task plan; an **executor agent** reads it and stores results
- A **research agent** writes facts; a **writer agent** recalls them to compose a report
- Multiple instances of the same agent running for different users or projects
- An agent pipeline where each stage stores its output for the next stage to recall

---

## Namespace isolation

Every agent gets its own namespace. Nodes written in namespace `agent_a` are completely invisible to queries in `agent_b`. All agents share one SQLite file — no coordination required.

```python
from nervapack.memory import MemoryStore, recall

# Agent A — the planner
planner = MemoryStore(namespace="planner")
planner.add_node("decision", "Break the auth refactor into 3 tasks: model, routes, tests",
                 data={"tasks": ["update_user_model", "update_auth_routes", "update_tests"]})

# Agent B — the executor
executor = MemoryStore(namespace="executor")

# Executor cannot see planner's memory by default
result = recall(executor, "auth refactor tasks", budget_tokens=200)
# → "## Memory recall … 0 items …"

# To share: planner explicitly writes a handoff to a shared namespace
shared = MemoryStore(namespace="shared")
shared.add_node("fact", "Auth refactor tasks: update_user_model, update_auth_routes, update_tests",
                confidence=1.0)

# Now executor reads from the shared namespace
executor.namespace = "shared"
result = recall(executor, "auth refactor tasks", budget_tokens=200)
# → "## Memory recall … Auth refactor tasks: update_user_model …"
```

---

## Pattern 1: Writer → Reader

One agent writes facts; another reads them. Use a shared namespace as the communication channel.

```python
from nervapack.memory import MemoryStore, recall

DB = ".nervapack/memory.db"


class ResearchAgent:
    def __init__(self):
        self.store = MemoryStore(db_path=DB, namespace="research")
        self.shared = MemoryStore(db_path=DB, namespace="shared")

    def research(self, topic: str) -> list[str]:
        # ... do research ...
        findings = [
            "Competitor A uses gRPC for internal services",
            "Competitor B uses REST with OpenAPI — slower but easier to onboard",
            "Industry standard latency for internal services is <10ms p99",
        ]
        node_ids = []
        for finding in findings:
            # Store in private namespace for own use
            self.store.add_node("fact", finding)
            # Publish to shared namespace for other agents
            nid = self.shared.add_node("fact", finding, confidence=0.85)
            node_ids.append(nid)
        return node_ids


class WriterAgent:
    def __init__(self):
        self.store = MemoryStore(db_path=DB, namespace="shared")

    def draft_section(self, topic: str) -> str:
        context = recall(self.store, topic, budget_tokens=500)
        # Feed context to your LLM here
        return f"[LLM prompt would include]\n{context}"


researcher = ResearchAgent()
researcher.research("API design patterns")

writer = WriterAgent()
draft = writer.draft_section("gRPC vs REST tradeoffs")
print(draft)
```

---

## Pattern 2: Pipeline stages

Each stage in a pipeline stores its output for the next stage to recall.

```python
from nervapack.memory import MemoryStore, recall

DB = ".nervapack/memory.db"
PIPELINE_NS = "pipeline_run_20260705"


def stage_1_extract(raw_text: str) -> None:
    """Extract key facts from raw text."""
    store = MemoryStore(db_path=DB, namespace=PIPELINE_NS)
    sid = store.add_node("session", "stage_1_extract")

    # In production you'd use an LLM to extract these
    facts = [
        "The API handles 50,000 requests per second at peak",
        "Latency p99 is 8ms under normal load",
        "The bottleneck is the database connection pool (max 100 connections)",
    ]
    for fact in facts:
        store.add_node("fact", fact, session_id=sid)
    store.close_session(sid)


def stage_2_analyse(focus: str) -> str:
    """Analyse facts extracted in stage 1."""
    store = MemoryStore(db_path=DB, namespace=PIPELINE_NS)
    context = recall(store, focus, budget_tokens=400)

    # Add analysis result back to shared memory
    store.add_node("decision",
                   f"Root cause of latency: connection pool saturation at {focus}",
                   confidence=0.8)
    return context


def stage_3_report() -> str:
    """Compose a report from all stored findings."""
    store = MemoryStore(db_path=DB, namespace=PIPELINE_NS)
    return recall(store, "performance findings and recommendations", budget_tokens=800)


# Run pipeline
stage_1_extract("... raw monitoring data ...")
stage_2_analyse("database performance")
report = stage_3_report()
print(report)
```

---

## Pattern 3: Parallel agents with isolated memory

Multiple agent instances running in parallel — each with its own namespace, no cross-contamination.

```python
import threading
from nervapack.memory import MemoryStore, recall

DB = ".nervapack/memory.db"


def agent_worker(agent_id: str, task: str) -> None:
    # Each agent writes to its own isolated namespace
    store = MemoryStore(db_path=DB, namespace=f"agent_{agent_id}")
    store.add_node("action", f"Working on: {task}")
    store.add_node("fact", f"Task {task} assigned to agent {agent_id}")
    # ... do work ...
    store.add_node("outcome", f"Task {task} completed successfully")


threads = [
    threading.Thread(target=agent_worker, args=("a1", "auth_module")),
    threading.Thread(target=agent_worker, args=("a2", "payment_module")),
    threading.Thread(target=agent_worker, args=("a3", "notification_module")),
]
for t in threads:
    t.start()
for t in threads:
    t.join()

# Coordinator reads from all namespaces
for agent_id in ["a1", "a2", "a3"]:
    store = MemoryStore(db_path=DB, namespace=f"agent_{agent_id}")
    result = recall(store, "task outcome", budget_tokens=100)
    print(f"Agent {agent_id}:", result[:80])
```

SQLite WAL mode is already enabled — concurrent readers and writers work without blocking.

---

## Via MCP (Claude Code / Cursor)

Use `memory_switch_namespace` to route an agent to a specific namespace mid-session:

```
# Planner agent stores its plan
memory_switch_namespace("planner")
memory_store("Break auth refactor into: model, routes, tests", kind="decision")

# Switch to shared channel to publish
memory_switch_namespace("shared")
memory_store("Auth refactor plan ready — 3 tasks queued", kind="fact")

# Executor agent reads the shared channel
memory_recall("auth refactor plan", budget_tokens=200)
```

---

## Seeing all namespaces

```python
store = MemoryStore(db_path=DB)
stats = store.stats()
print(stats["namespaces"])
# → ["default", "planner", "executor", "shared", "pipeline_run_20260705",
#    "agent_a1", "agent_a2", "agent_a3"]
```

Or via CLI:

```bash
nervapack-memory stats
# DB size: 128.0 KB  |  Namespaces: default, planner, executor, shared, …
```

---

## Cleanup

Delete a pipeline run's namespace when done:

```python
from nervapack.memory.store import _now_iso

store = MemoryStore(db_path=DB, namespace="pipeline_run_20260705")
conn = store._get_conn()
conn.execute("UPDATE mem_nodes SET tombstoned=1 WHERE namespace=?", ("pipeline_run_20260705",))
conn.commit()
```

---

## See Also

- [Python API](../python-api.md) — `MemoryStore` namespace parameter, `stats()`
- [Chatbot guide](chatbot.md) — per-user isolation (same pattern, different use case)
- [Coding agent guide](coding-agent.md) — single-agent MCP workflow
- [Concepts](../concepts.md) — namespace isolation design, WAL mode
