# Token Efficiency

NervaPack reduces token usage by **80–95%** compared to naive RAG. Here's how — and how to measure it in your own project.

---

## The Token Problem

LLMs have limited context windows (GPT-4o: 128K tokens, Claude Sonnet: 200K tokens), and every token costs money. Traditional RAG sends entire files to the LLM — most of that content is irrelevant to the query.

**Naive RAG:**

```
Query: "How does the sync command decide which files to re-ingest?"

1. Vector search finds 3 relevant files
2. Send all three files in full
3. Total: ~12,840 tokens (95% irrelevant boilerplate)
```

---

## NervaPack Approach

NervaPack performs a **K-Hop BFS** on the AST knowledge graph, collecting only the classes, functions, and imports actually needed to answer the query — then formats them as a compact Markdown context block.

```
Query: "How does the sync command decide which files to re-ingest?"

1. Vector search finds 3 seed nodes (function signatures)
2. BFS traversal (1 hop) collects related callers and callees
3. Format only the relevant code as Markdown
4. Total: ~1,180 tokens (90.8% reduction)
```

---

## Verified Results

Measured on the NervaPack codebase itself (1,246 nodes, 417 edges) using five representative queries:

| Query | NP Tokens | Naive Tokens | Savings |
|-------|----------:|-------------:|--------:|
| how does ingest work | 225 | 3,830 | **94.1%** |
| memory store and recall flow | 307 | 2,046 | **85.0%** |
| vector search and similarity | 321 | 4,507 | **92.9%** |
| MCP server tools and query | 286 | 5,943 | **95.2%** |
| graph builder nodes and edges | 1,126 | 5,618 | **80.0%** |
| **Average** | **453** | **4,389** | **89.4%** |

Full benchmark methodology: [METHODOLOGY.md](../../METHODOLOGY.md).

---

## Per-Query Savings Panel

Every `nervapack query` run shows a live comparison panel:

```
╭──────────────────────  NervaPack Token Efficiency  ──────────────────────╮
│                                                                          │
│   Strategy              Tokens   Visual                       Relative   │
│  ──────────────────────────────────────────────────────────────────────  │
│   Naive RAG (2 files)    3,830   ████████████████████      100% (base)  │
│   NervaPack                225   █░░░░░░░░░░░░░░░░░░░             5.9%  │
│                                                                          │
│ ──────────────────────────────────────────────────────────────────────── │
│   Tokens saved: 3,605   Reduction: 94.1%                                 │
│   Cost saved (GPT-4o  $2.50/1M): $0.0090 per query                       │
│   Cost saved (Claude Sonnet $3/1M): $0.0108 per query                    │
╰──────────────────────────────────────────────────────────────────────────╯
```

When using NervaPack through MCP (Claude Code, Copilot, Cursor), each `query` call appends a bold savings footer to the response:

```
**NervaPack:** 225 tokens  (naive RAG: 3,830 — **94.1% saved**, ~$0.0090 GPT-4o cost per query)
```

---

## Cumulative Savings Tracking

NervaPack records every query in `.nervapack/query_history.jsonl` — including MCP calls from Copilot and Cursor. To see your running total:

```bash
nervapack savings
```

Or from inside Claude Code / Copilot, ask:

> "Show me my NervaPack token savings."

The `show_savings` MCP tool returns a Markdown table with total queries, average reduction, total tokens saved, and cost impact — rendered directly in the chat response.

---

## Why This Matters

| Benefit | Impact |
|---------|--------|
| **Lower API costs** | 89% fewer tokens = 89% less spend on context |
| **Faster responses** | Smaller prompts → lower latency |
| **Better answer quality** | LLM sees only relevant code, no noise |
| **More context budget** | Fit more queries and tool calls in the same context window |
| **Works offline** | No cloud embedding service — all token counting is local (tiktoken) |

---

## Token Counting

NervaPack counts tokens using **tiktoken** (`cl100k_base` encoding, compatible with GPT-4 and Claude) when it is installed:

```bash
pip install "nervapack[metrics]"
```

Without tiktoken, counts are estimated as `len(text) // 4` and marked with a `~` prefix. Install tiktoken for exact numbers.

---

## See Also

- [`nervapack savings`](../commands/savings.md) — cumulative savings summary command
- [`nervapack history`](../commands/history.md) — per-query history with `--verbose` token columns
- [Verified Benchmarks](../../BENCHMARKS.md) — third-party reproducible results
