# Agent Memory as a Conversation Context Extender

The single most practical use of `nervapack.memory` is one that the standard "agent memory" framing undersells: **it eliminates the need to re-paste project context into every new chat.**

Instead of spending 1,000–3,000 tokens at the start of each conversation explaining your architecture, tech choices, team conventions, and recent decisions, an agent calls `memory_recall("project context")` and gets back a scored, deduplicated, budget-capped briefing — built up automatically over weeks of prior sessions.

---

## The Problem With Today's Workflows

Every developer using an AI assistant in an ongoing project hits the same friction:

**Session 1 (Monday):** You explain the architecture, the decision to use JWT, the deployment pipeline.

**Session 2 (Wednesday):** You re-explain the same architecture. The agent doesn't remember Wednesday's refactor discussion. You paste the same background again.

**Session 3 (Friday):** Another new tab. Another blank slate.

Over a month of daily sessions, you spend more tokens re-establishing context than doing real work. Standard RAG retrieves text *chunks* — but your context isn't a chunk, it's an accumulation of decisions, discoveries, and team conventions spread across weeks.

---

## How Memory Fixes It

`nervapack.memory` stores **atomic facts** — not transcript blobs. Each stored item is 8–30 tokens. A month of project history fits in 500 tokens of recall output.

The system accumulates context across sessions automatically:

```
Session 1: "Chose JWT for auth — stateless scaling"             → d_aaa (8 tokens stored)
Session 2: "auth_service issues 15-min tokens"                  → f_bbb (7 tokens stored)
Session 3: "Switched from Postgres to CockroachDB for geo-dist" → d_ccc (9 tokens stored)
Session 4: "Deploy via GitHub Actions → staging → manual prod"  → p_ddd (8 tokens stored)
           ...12 sessions later...

memory_recall("project context", budget_tokens=500)
→ 3 items · 171/500 tokens          ← complete briefing in 171 tokens
```

The bi-temporal model ensures you always get **current truth**: a decision superseded three sessions ago doesn't surface as if it's still active. Old context doesn't pollute fresh work.

---

## The Recommended Claude Prompt Template

Add this system prompt (or CLAUDE.md instruction) to any project where you use NervaPack memory:

```markdown
## Session Protocol

At the start of every session:
1. Call `memory_start_session` with the task name (e.g. "Debugging payment flow").
2. Call `memory_recall("project context", budget_tokens=400)` — paste the result into your working context.
3. Call `memory_recall` again for any specific topic before diving in (e.g. "auth_service decisions").

During the session, call `memory_store` for:
- Any decision made (use `kind="decision"` with `rationale` and `alternatives_rejected`)
- Any fact discovered about system behaviour (`kind="fact"`)
- Any procedure or convention established (`kind="procedure"`)
- Any outcome from an action (`kind="outcome"`)

At session end, call `memory_end_session` with a one-paragraph summary.
```

With this in place, every new Claude tab starts informed — no copy-paste, no re-explanation.

---

## Concrete Example: 30 Days of Project Context in 171 Tokens

**What was stored across sessions (cumulative):**

```
Session 1  d_0019f2  "Chose JWT for auth_service — stateless horizontal scaling"
Session 1  f_0019f3  "auth_service issues 15-min access tokens with rotating refresh"
Session 2  d_0019f4  "CockroachDB replaces Postgres for geo-distributed writes"
Session 3  p_0019f5  "Deploy: GitHub Actions → staging auto → prod manual approval"
Session 3  pr_0019f6 "All new services must expose /health and /metrics endpoints"
Session 4  f_0019f7  "payment_service processes ~8k transactions/day at p99 < 200ms"
```

**Session 5 starts — first thing the agent calls:**

```python
memory_recall("project context", budget_tokens=500)
```

**Output (171 tokens):**

```markdown
## Memory recall: "project context" (as of 2026-07-05 · 6 items · 171/500 tokens)

### Decisions
- [d_0019f2] 2026-06-05 · conf 0.90 — Chose JWT for auth_service — stateless horizontal scaling
- [d_0019f4] 2026-06-12 · conf 0.95 — CockroachDB replaces Postgres for geo-distributed writes

### Facts
- [f_0019f3] 2026-06-05 · conf 1.00 — auth_service issues 15-min access tokens with rotating refresh
- [f_0019f7] 2026-06-19 · conf 1.00 — payment_service processes ~8k transactions/day at p99 < 200ms

### Procedures
- [p_0019f5] 2026-06-12 · conf 1.00 — Deploy: GitHub Actions → staging auto → prod manual approval

### Preferences
- [pr_0019f6] 2026-06-12 · conf 1.00 — All new services must expose /health and /metrics endpoints

### Provenance
d_0019f2 ← session s_0019f1 · d_0019f4 ← session s_0019f2 · ...
```

The agent now knows the full project context. No copy-paste. No re-explanation. 171 tokens.

---

## Seeding Memory From Existing Notes

If you have existing architecture docs, decision logs, or conventions, seed them in one command using the import workflow:

**From a decision log (JSON):**

```bash
# decisions.json — one object per decision
cat > decisions.json <<'EOF'
[
  {
    "content": "Chose JWT for auth_service — stateless horizontal scaling",
    "kind": "decision",
    "entities": ["auth_service"],
    "confidence": 0.9,
    "rationale": "Stateless tokens avoid shared session store; can scale auth horizontally.",
    "alternatives_rejected": ["server-side sessions", "PASETO"]
  },
  {
    "content": "CockroachDB replaces Postgres for geo-distributed writes",
    "kind": "decision",
    "entities": ["database"],
    "confidence": 0.95
  },
  {
    "content": "All new services must expose /health and /metrics endpoints",
    "kind": "preference",
    "confidence": 1.0
  }
]
EOF

nervapack-memory import decisions.json
# Imported 3 nodes.
```

**From Markdown notes (manual conversion):**

```python
from nervapack.memory import MemoryStore

store = MemoryStore()

# Seed architecture conventions
conventions = [
    ("Use snake_case for all Python identifiers", "preference"),
    ("All API responses must include request_id for tracing", "preference"),
    ("Feature flags managed via LaunchDarkly — no env-var flags", "procedure"),
    ("On-call rotation: Mon-Thu primary, Fri-Sun secondary", "procedure"),
]

for content, kind in conventions:
    store.add_node(kind=kind, content=content, confidence=1.0)

print(f"Seeded {len(conventions)} conventions into memory.")
```

After seeding, every future session starts with this context available in a `memory_recall`.

---

## Token Efficiency: Memory vs. Paste

Concrete comparison for a medium-sized project after 4 weeks of sessions:

| Approach | Tokens spent per session | After 20 sessions |
|----------|-------------------------|-------------------|
| Manual paste (architecture doc) | 2,400 tokens/session | 48,000 tokens total |
| Manual paste (recent notes) | 800 tokens/session | 16,000 tokens total |
| `memory_recall` (this system) | **171 tokens/session** | **3,420 tokens total** |
| **Savings vs. doc paste** | — | **93% fewer tokens** |

The savings compound: as more sessions accumulate, the memory system gets better (more context, more accurately scored) while the manual-paste approach gets worse (more docs to paste, more to maintain).

---

## Combined With the Code Graph

NervaPack ships two systems. Used together, they cover the full context problem:

```
Code graph (nervapack-mcp)              Agent memory (nervapack-memory-mcp)
─────────────────────────────           ─────────────────────────────────────
"How does auth_service work?"     +     "Why was JWT chosen for auth_service?"
"Which functions call validate()?"      "What did we decide last sprint?"
"What does this class import?"          "What's the deployment procedure?"
↓                                       ↓
AST-precise, 91% token reduction        Decision-precise, budget-capped recall
```

**Recommended combined session start:**

```python
# 1. Load project memory (decisions, facts, conventions)
memory_recall("project context", budget_tokens=400)

# 2. Query code graph for the specific task
query_codebase("How does the payment flow handle refunds?")

# 3. Work — store any decisions made
memory_store(
    "Chose idempotency keys over distributed locks for refund handling",
    kind="decision",
    entities=["payment_service"],
    rationale="Simpler failure model; locks risk deadlock at scale",
    alternatives_rejected=["distributed locks", "saga pattern"],
)
```

This gives the agent both structural precision (code graph) and temporal context (memory) — the two things that are otherwise re-established from scratch in every conversation.

---

## What Gets Stored, and When

Not every conversation detail should be stored. Use this guide:

| Store as `decision` | Store as `fact` | Store as `procedure` | Store as `preference` | Don't store |
|---------------------|-----------------|---------------------|----------------------|-------------|
| Architecture choices | Observed system behaviour | Step-by-step how-tos | Team conventions | Debugging one-liners |
| Tech stack selections | Performance metrics | Deploy sequences | Code style rules | Error messages |
| Design trade-offs made | API contract details | Rollback steps | Tool preferences | Transient state |
| Vendor/library choices | Discovered constraints | Setup sequences | Review norms | Meeting transcripts |

**Rule of thumb:** if you'd put it in a decision log or architecture doc, store it as memory. If it's one-off debugging output, don't.

---

## See Also

- [Memory concept guide](memory.md) — data model, recall pipeline, bi-temporal semantics
- [Memory MCP Server](../../integrations/memory-mcp.md) — all 12 tools with parameters and examples
- [memory CLI](../commands/memory.md) — `init`, `stats`, `search`, `show`, `import`, `export`
- [Architecture](architecture.md) — how memory relates to the code graph
