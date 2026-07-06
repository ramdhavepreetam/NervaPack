# Decision Log & ADR Store

Use NervaPack memory as an Architecture Decision Record (ADR) store — import existing decisions, query why choices were made, trace supersession history, and get notified when code changes make a recorded decision potentially stale.

---

## What it does better than a docs folder

| Docs folder (Markdown ADRs) | NervaPack memory |
|---|---|
| Full-text search only | FTS5 + graph expansion (finds related decisions) |
| No temporal model | Bi-temporal: point-in-time recall, supersession chain |
| Static — no link to code | TOUCHES bridge: decisions link to the exact functions they describe |
| Manual staleness check | `memory_verify_staleness()` — flags decisions where code changed |
| Paste into every chat | `memory_recall("project context")` — loads everything in <200 tokens |

---

## Setup

```bash
pip install "nervapack[memory]"
nervapack-memory init
```

---

## Import existing ADRs

If you have ADRs in Markdown files or a database, export them as JSON and import:

```bash
cat > decisions.json << 'EOF'
[
  {
    "content": "Chose PostgreSQL over MongoDB for transactional data",
    "kind": "decision",
    "entities": ["database", "postgres"],
    "confidence": 1.0,
    "rationale": "ACID compliance is required for payment flows. MongoDB's eventual consistency model created reconciliation complexity we could not accept.",
    "alternatives_rejected": ["MongoDB", "CockroachDB", "MySQL"]
  },
  {
    "content": "Chose gRPC for all internal service communication",
    "kind": "decision",
    "entities": ["api_gateway", "auth_service", "payments_service"],
    "confidence": 1.0,
    "rationale": "Strong typing via protobuf eliminates a class of runtime errors. Bi-directional streaming needed for the notification service.",
    "alternatives_rejected": ["REST/JSON", "GraphQL", "NATS"]
  },
  {
    "content": "All services use structured logging (JSON) — no printf-style logs",
    "kind": "preference",
    "entities": ["logging"]
  },
  {
    "content": "Feature flags use LaunchDarkly — no custom flag system",
    "kind": "decision",
    "entities": ["feature_flags"],
    "rationale": "Custom flag systems consistently become maintenance burden. LD handles targeting, gradual rollout, and kill switches.",
    "alternatives_rejected": ["custom Redis-backed flags", "environment variables"]
  },
  {
    "content": "Blue-green deployment via Kubernetes — no rolling deploys for stateful services",
    "kind": "procedure",
    "entities": ["deployment"]
  }
]
EOF

nervapack-memory import decisions.json
```

---

## Query decisions

**Ask why a decision was made:**

```bash
# Via CLI
nervapack-memory search "database choice"
```

```
# Via MCP (in Claude Code)
memory_why("PostgreSQL decision")
```

**Output:**

```
## Decision: d_0019f2...
**Chose PostgreSQL over MongoDB for transactional data**
Date: 2026-07-05T10:00:00+00:00  ·  Confidence: 1.00

**Rationale:** ACID compliance is required for payment flows. MongoDB's eventual
consistency model created reconciliation complexity we could not accept.

**Rejected alternatives:** MongoDB, CockroachDB, MySQL
```

**Find all decisions about a service:**

```
memory_about("payments_service")
```

**Find what changed over time:**

```
memory_timeline("database")
```

---

## Superseding old decisions

When a decision changes, create a new node that supersedes the old one. The full history is preserved.

```python
from nervapack.memory import MemoryStore
from nervapack.memory.store import _now_iso

store = MemoryStore()

# Original decision (already stored as d_0019f2...)
old_id = "d_0019f2..."

# New decision supersedes it
new_id = store.add_node(
    "decision",
    "Switched auth_service from JWT to Paseto v4 — stronger type safety, no algorithm confusion",
    confidence=0.95,
    data={
        "rationale": "CVE-2022-21449 (Psychic Signatures) highlighted JWT's algorithm agility as a risk. Paseto has no algorithm field — the version is the algorithm.",
        "alternatives_rejected": ["JWT with algorithm whitelist", "opaque tokens"],
    }
)

# Close old node
conn = store._get_conn()
conn.execute("UPDATE mem_nodes SET valid_until=? WHERE id=?", (_now_iso(), old_id))
conn.execute(
    "INSERT INTO mem_edges (id, src, dst, kind, recorded_at) VALUES (?,?,?,?,?)",
    (f"edge_{new_id}", new_id, old_id, "SUPERSEDES", _now_iso()),
)
conn.commit()
```

Or via MCP:

```
memory_store(
    "Switched auth_service from JWT to Paseto v4",
    kind="decision",
    entities=["auth_service"],
    supersedes="d_0019f2...",
    rationale="CVE-2022-21449 highlighted JWT algorithm agility risk",
)
```

Now `memory_recall("auth mechanism")` returns only the Paseto decision.
`memory_timeline("auth_service")` shows both, with the JWT decision marked `[superseded]`.
`memory_why("Paseto")` shows the full rationale.

---

## Staleness detection — did the code drift from the decision?

When you build the code graph (`nervapack ingest .`) and store decisions with entity names that match code entities, TOUCHES edges are created. Then `memory_verify_staleness()` checks whether the code files have changed since the decision was recorded.

```bash
nervapack ingest .   # build the code graph
```

```
# Store a decision linked to a function
memory_store(
    "verify_token must check expiry before signature to prevent timing attacks",
    kind="decision",
    entities=["verify_token"]
)

# Later — check if the code changed since this decision was stored
memory_verify_staleness()
```

**Output if verify_token was modified:**

```json
{
  "checked": 5,
  "stale": 1,
  "stale_nodes": [
    {
      "node_id": "d_0019f2...",
      "file_path": "src/auth/jwt.py",
      "memory_date": "2026-06-01T10:00:00+00:00",
      "file_mtime": "2026-07-04T14:22:00+00:00"
    }
  ],
  "queued": true
}
```

The stale decision is queued in `mem_review_queue` for review. You decide whether to update it, supersede it, or confirm it still holds (`memory_verify(node_id, "confirm")`).

---

## Full Python pipeline

```python
from nervapack.memory import MemoryStore, recall
from nervapack.memory.store import _now_iso
import json, pathlib

store = MemoryStore()


def import_adr_file(path: str) -> list[str]:
    """Import a JSON file of ADRs. Returns list of created node IDs."""
    nodes = json.loads(pathlib.Path(path).read_text())
    ids = []
    for spec in nodes:
        nid = store.add_node(
            spec["kind"],
            spec["content"],
            confidence=spec.get("confidence", 1.0),
            data={
                k: spec[k]
                for k in ("rationale", "alternatives_rejected")
                if k in spec
            } or None,
        )
        ids.append(nid)
    return ids


def query_decision(topic: str, tokens: int = 400) -> str:
    return recall(store, topic, budget_tokens=tokens)


def supersede(old_id: str, new_content: str, rationale: str) -> str:
    new_id = store.add_node("decision", new_content,
                             data={"rationale": rationale})
    conn = store._get_conn()
    conn.execute("UPDATE mem_nodes SET valid_until=? WHERE id=?", (_now_iso(), old_id))
    conn.execute(
        "INSERT INTO mem_edges (id, src, dst, kind, recorded_at) VALUES (?,?,?,?,?)",
        (f"edge_{new_id}", new_id, old_id, "SUPERSEDES", _now_iso()),
    )
    conn.commit()
    return new_id


# Usage
import_adr_file("decisions.json")
print(query_decision("database choice"))
```

---

## Generating decision reports

Export all decisions as JSON and feed to a report generator:

```bash
nervapack-memory export --out decisions_dump.json
```

Or search for decisions specifically:

```bash
nervapack-memory search "PostgreSQL" --kind decision
```

---

## Best practices

**One node per decision.** Don't put multiple decisions in one node — the graph expansion and entity resolution work best on atomic claims.

**Always record rationale.** The `data.rationale` field is what `memory_why` surfaces. Without it, the decision log is just a list of outcomes with no explanation.

**Record rejected alternatives.** Future team members (and future you) will ask "why didn't we use X?" — `alternatives_rejected` answers it.

**Supersede, never edit.** When a decision changes, supersede the old node rather than editing it. The full history is preserved in `memory_timeline`, which is invaluable during post-mortems and onboarding.

**Tag entities.** Decisions tagged with `entities=["auth_service"]` are retrieved by `memory_about("auth_service")`. Without entity links, decisions are only reachable via FTS.

---

## See Also

- [MCP Tools reference](../mcp-tools.md) — `memory_why`, `memory_timeline`, `memory_about`, `memory_verify_staleness`
- [Coding agent guide](coding-agent.md) — seeding from existing docs as part of the agent workflow
- [Python API](../python-api.md) — `MemoryStore.add_node()`, `recall_timeline()`
- [Concepts](../concepts.md) — bi-temporal model, supersession chain, TOUCHES bridge
