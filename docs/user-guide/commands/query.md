# `nervapack query`

Search the knowledge graph using natural language.

---

## Synopsis

```bash
nervapack query "<prompt>"
```

---

## Description

The `query` command retrieves focused, token-efficient context from the knowledge graph for a given prompt. It uses a **query router** that selects the best retrieval strategy automatically:

1. **Impact intent** — if the prompt starts with `"what breaks if I change ..."` or contains `"impact of"`, triggers reverse dependency traversal to find callers and dependents.
2. **Exact symbol match** — if the prompt exactly matches a node name in the graph, seeds the BFS from that node directly, bypassing vector search.
3. **Semantic (vector) search** — default fallback; embeds the prompt and finds the nearest nodes in ChromaDB, then expands with K-Hop BFS.

After retrieving a subgraph, `query` also injects any memory nodes that TOUCH the retrieved source files, so you see relevant past decisions alongside live code context.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `PROMPT` | Natural language question or symbol name |

---

## Examples

### Standard semantic query
```bash
nervapack query "How does the token counting work?"
```

### Exact symbol lookup
```bash
nervapack query "GraphRetriever"
```

### Impact analysis
```bash
nervapack query "what breaks if I change VectorStore"
nervapack query "impact of GraphBuilder"
```

---

## Output

```
Query Router: Intent: semantic, Direction: both
Vector Search: Found 3 seed nodes

┌─┬──────────┬──────────────────────────────┐
│#│ Node Type│ Name/File                    │
├─┼──────────┼──────────────────────────────┤
│1│ function │ count_tokens                 │
│2│ function │ render_savings_panel         │
│3│ import   │ tiktoken                     │
└─┴──────────┴──────────────────────────────┘

Graph Traversal: Expanding with max_hops=1, direction=both

📁 token_meter.py (2 entities)
  ⚙ count_tokens [seed]
  ⚙ render_savings_panel [seed]
    ← EXPLAINS: Token Efficiency

────────────────────────────────────────────────────────────
Retrieved Context (Markdown)
────────────────────────────────────────────────────────────
...

╭──────────────  NervaPack Token Efficiency  ──────────────╮
│  Naive RAG    12,340   ████████████  100% (base)         │
│  NervaPack       893   █░░░░░░░░░░░    7.2%              │
│  Tokens saved: 11,447   Reduction: 92.8%                 │
╰───────────────────────────────────────────────────────────╯
```

---

## See Also

- [`ingest`](ingest.md) — build the graph first
- [`enrich`](enrich.md) — add semantic doc-code edges without re-ingesting
- [MCP `query` tool](../../integrations/mcp-server.md) — use from Claude Code / Cursor
