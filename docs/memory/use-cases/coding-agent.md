# AI Coding Agent Memory

Use NervaPack memory with Claude Code or Cursor to persist project decisions, conventions, and facts across sessions. The agent recalls everything it has learned about your codebase at the start of every conversation — no copy-paste, no context re-injection, no lost knowledge.

---

## The problem it solves

Every time you start a new chat with an AI coding agent, it forgets everything:

- The decision to use JWT instead of session cookies, and why
- The convention that all services must expose `/health` and `/metrics`
- The fact that the payments module has a known race condition under high load
- The procedure for rolling a deployment without downtime

With NervaPack memory, the agent starts each session with a full briefing. 30 days of decisions and conventions load in under 200 tokens.

---

## Setup (5 minutes)

**1. Install and initialise**

```bash
pip install "nervapack[memory]"
cd your-project/
nervapack-memory init
# ✓ Memory store initialised at .nervapack/memory.db
```

**2. Add to `.mcp.json`**

```json
{
  "mcpServers": {
    "nervapack-memory": {
      "command": "nervapack-memory-mcp",
      "description": "Project memory — recall decisions, facts, and conventions across sessions"
    }
  }
}
```

**3. Add `CLAUDE.md` to your project root**

```markdown
## Memory — always use at session start

1. Call `memory_start_session("<task name>")` to open a named session
2. Call `memory_recall("project context", budget_tokens=400)` to load prior context
3. Call `memory_recall("<specific topic>", budget_tokens=200)` for the task at hand

## Memory — always store during the session

- Any architectural decision → `memory_store(..., kind="decision", rationale="...")`
- Any fact discovered → `memory_store(..., kind="fact")`  
- Any team convention → `memory_store(..., kind="preference")`
- Any outcome from an action → `memory_store(..., kind="outcome")`

## Memory — always close the session

Call `memory_end_session("<what was accomplished>")` before ending.
```

Reload your editor. Done.

---

## Session protocol

Every session follows this pattern:

```
┌─ Session start ─────────────────────────────────────────────────┐
│                                                                   │
│  memory_start_session("Refactor auth middleware")                 │
│  memory_recall("project context", budget_tokens=400)              │
│     → loads: architecture decisions, conventions, known issues    │
│  memory_recall("auth middleware", budget_tokens=200)              │
│     → loads: auth-specific decisions and facts                    │
│                                                                   │
└─── agent works ─────────────────────────────────────────────────┘
        │  makes decisions  →  memory_store(..., kind="decision")
        │  finds facts      →  memory_store(..., kind="fact")
        │  confirms prior   →  memory_verify(node_id, "confirm")
        │  refutes prior    →  memory_verify(node_id, "refute")
└─ Session end ────────────────────────────────────────────────────┐
│  memory_end_session("Replaced JWT middleware with Paseto v4;     │
│                      updated all token validation call sites")    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Seeding from existing notes

Don't start from scratch. Seed memory from your existing architecture docs:

```bash
cat > arch_decisions.json << 'EOF'
[
  {
    "content": "Chose JWT for stateless auth — enables horizontal scaling without shared session store",
    "kind": "decision",
    "entities": ["auth_service"],
    "confidence": 1.0,
    "rationale": "Stateless tokens allow any server instance to validate without DB lookup",
    "alternatives_rejected": ["server-side sessions", "opaque tokens"]
  },
  {
    "content": "All services must expose /health and /metrics endpoints",
    "kind": "preference"
  },
  {
    "content": "PostgreSQL for all transactional data — ACID required for payment flows",
    "kind": "decision",
    "entities": ["payments_service", "postgres"],
    "rationale": "Payment flows require ACID guarantees — NoSQL was rejected"
  },
  {
    "content": "Deploy procedure: blue-green via Kubernetes — never rolling deploy for stateful services",
    "kind": "procedure"
  }
]
EOF

nervapack-memory import arch_decisions.json
```

Now at the start of the next session:

```
memory_recall("project context", budget_tokens=400)
```

Returns:

```
## Memory recall: "project context" (as of 2026-07-05 · 4 items · 312/400 tokens)

### Decisions
- [d_0019f2...] 2026-07-05 · conf 1.00 — Chose JWT for stateless auth …
- [d_0019f3...] 2026-07-05 · conf 1.00 — PostgreSQL for all transactional data …

### Preferences
- [pr_0019f4...] 2026-07-05 · conf 1.00 — All services must expose /health and /metrics endpoints

### Procedures
- [p_0019f5...] 2026-07-05 · conf 1.00 — Deploy procedure: blue-green via Kubernetes …
```

---

## TOUCHES bridge — memory linked to code

When you store a memory with an entity that matches a function or class in your code graph, NervaPack creates a `TOUCHES` edge automatically. This links the memory directly to the source location.

**Prerequisites:** build the code graph first.

```bash
nervapack ingest .
```

**Then store a memory:**

```
memory_store(
    "verify_token must validate token expiry before checking signature",
    kind="fact",
    entities=["verify_token"]
)
```

If `verify_token` exists as a function in the graph, a TOUCHES edge is created automatically.

**Then navigate:**

```
# What memories are about this file?
memory_for_code("src/auth/jwt.py")

# Where in code is this memory about?
memory_to_code("f_0019f2...")
# → {"file_path": "src/auth/jwt.py", "start_line": 42, "end_line": 61}

# Are any of my memories stale (file changed since memory was stored)?
memory_verify_staleness()
# → {"stale": 2, "missing": 0, "stale_nodes": [...]}
```

---

## Understanding decisions over time

Ask `memory_why` to get the full rationale for any decision:

```
memory_why("JWT auth")
```

```
## Decision: d_0019f2...
**Chose JWT for stateless auth**
Date: 2026-07-05T10:00:00+00:00  ·  Confidence: 1.00

**Rationale:** Stateless tokens allow any server instance to validate without DB lookup.
**Rejected alternatives:** server-side sessions, opaque tokens
```

Ask `memory_timeline` to see how a decision evolved:

```
memory_timeline("auth_service")
```

```
## Memory timeline: 'auth_service'

- [d_0019f1...] 2026-01-01 [superseded by d_0019f2...] — Chose session cookies
- [d_0019f2...] 2026-07-05 — Chose JWT for stateless auth
```

---

## Multi-project on one machine

Use namespaces to keep projects isolated in one database file:

```
memory_switch_namespace("project_b")
memory_recall("project context")   # reads project_b's memory only

memory_switch_namespace("default")
memory_recall("project context")   # reads default namespace
```

---

## Tool reference at a glance

| Tool | When to call |
|------|-------------|
| `memory_start_session` | First thing — name the session for the task |
| `memory_recall` | At session start — load project context and topic context |
| `memory_store` | Any decision, fact, convention, or outcome worth keeping |
| `memory_import` | One-time seeding from existing notes or ADRs |
| `memory_about` | "What do we know about `auth_service`?" |
| `memory_why` | "Why did we choose X?" |
| `memory_timeline` | "How has this decision evolved?" |
| `memory_for_code` | "What memories are about this file?" |
| `memory_to_code` | "Where in code is this memory anchored?" |
| `memory_verify_staleness` | "Are any code-linked memories stale?" |
| `memory_verify` | Confirm a prior fact holds, or refute it |
| `memory_forget` | Explicitly forget something |
| `memory_end_session` | Always — before ending the session |

---

## See Also

- [MCP Tools reference](../mcp-tools.md) — all 17 tools with parameter tables and examples
- [Decision log / ADR store](adr-store.md) — import existing ADRs and manage the decision history
- [Multi-agent guide](multi-agent.md) — namespace isolation for multi-agent pipelines
- [Concepts](../concepts.md) — bi-temporal schema, scoring formula, entity resolution
