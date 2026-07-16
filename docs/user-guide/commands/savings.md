# `nervapack savings`

Show a one-screen summary of cumulative token savings across all queries.

---

## Synopsis

```bash
nervapack savings [OPTIONS]
```

---

## Description

The `savings` command reads your project's `.nervapack/query_history.jsonl` and presents a formatted summary of how much NervaPack has saved versus sending full files as context (naive RAG). It covers every query made from the CLI (`nervapack query`) and from MCP-connected tools (Claude Code, Copilot, Cursor).

This is the fastest way to demonstrate NervaPack's value — you can share the output directly or export machine-readable JSON for CI badges or README shields.

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | off | Output machine-readable JSON instead of the panel |

---

## Examples

### One-screen summary
```bash
nervapack savings
```

### Machine-readable output (for CI, badges, scripts)
```bash
nervapack savings --json
```

---

## Output

```
╭─────────────────────  NervaPack Token Savings Summary  ──────────────────────╮
│                                                                              │
│    Total queries run                                                      5  │
│    Average token reduction                                            89.4%  │
│    Total tokens saved                                                19,679  │
│                                                                              │
│    Naive RAG would have used                                  21,944 tokens  │
│    NervaPack used                            2,265 tokens  (10.3% of naive)  │
│                                                                              │
│    Cost saved  GPT-4o   ($2.50/1M)                                  $0.0492  │
│    Cost saved  Sonnet   ($3.00/1M)                                  $0.0590  │
│                                                                              │
│    Top query topics                           graph, builder, nodes, server  │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## JSON output

Use `--json` when you want to integrate savings data into a script, README badge, or CI pipeline:

```bash
nervapack savings --json
```

```json
{
  "total_queries": 5,
  "avg_token_reduction_pct": 89.4,
  "total_tokens_saved": 19679,
  "total_nervapack_tokens": 2265,
  "total_naive_tokens": 21944,
  "cost_saved_gpt4_usd": 0.0492,
  "cost_saved_sonnet_usd": 0.0590,
  "top_topics": ["graph", "builder", "nodes", "server", "edges"]
}
```

### Example: README badge via shell substitution

```bash
PCT=$(nervapack savings --json | python3 -c "import sys,json; print(round(json.load(sys.stdin)['avg_token_reduction_pct']))")
echo "Average reduction: ${PCT}%"
```

---

## How savings are computed

For every query, NervaPack records:

- **NervaPack tokens** — exact token count of the focused context it returned (using tiktoken `cl100k_base` if available, otherwise estimated as `len / 4`)
- **Naive tokens** — token count of all source files that were touched by the query, concatenated in full (what a traditional RAG would send)

`savings` aggregates these across all records and computes:

| Metric | Formula |
|--------|---------|
| Tokens saved | `naive_tokens − nervapack_tokens` per query, summed |
| Avg reduction | Mean of `(naive − np) / naive × 100` per query |
| Cost saved | `tokens_saved × rate_per_million` (GPT-4o: $2.50, Sonnet: $3.00) |

History is stored in `.nervapack/query_history.jsonl`. Every `nervapack query` and every MCP `query` call (from Claude Code, Copilot, Cursor) appends a record automatically — no extra configuration needed.

---

## `show_savings` in Claude Code / Copilot

If you are using NervaPack via MCP, you can get the same summary directly inside your AI tool's chat without switching to the terminal. Ask Claude or Copilot to call the `show_savings` tool:

> "Show me my NervaPack token savings."

The tool returns a Markdown table rendered in the chat response:

```
## NervaPack Token Savings

| Metric | Value |
|--------|-------|
| Total queries | 5 |
| Average token reduction | **89.4%** |
| Total tokens saved | **19,679** |
| Naive RAG total | 21,944 tokens |
| NervaPack total | 2,265 tokens (10.3% of naive) |
| Cost saved — GPT-4o ($2.50/1M) | **$0.0492** |
| Cost saved — Sonnet ($3.00/1M) | **$0.0590** |
| Top query topics | graph, builder, nodes, server |
```

Savings from MCP queries (Copilot, Cursor) and CLI queries (`nervapack query`) all accumulate in the same `.nervapack/query_history.jsonl` file, so both the CLI and the MCP tool always show the full picture.

---

## Related commands

- [`nervapack history`](history.md) — per-query breakdown with `--verbose` token counts
- [`nervapack query`](query.md) — run a query (every query adds a savings record)
- [`nervapack serve`](serve.md) — interactive dashboard with query history charts
