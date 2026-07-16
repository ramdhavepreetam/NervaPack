# `nervapack history`

View your query history and aggregate token-savings analytics.

---

## Synopsis

```bash
nervapack history [OPTIONS]
```

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit N` / `-n N` | `10` | Number of recent queries to show |
| `--verbose` / `-v` | off | Add `NP Tokens` and `Naive Tokens` columns to the table |
| `--stats` | off | Show aggregate statistics instead of the query list |
| `--clear` | off | Clear all query history (prompts for confirmation) |

---

## Examples

### Show last 10 queries
```bash
nervapack history
```

### Show last 25 queries
```bash
nervapack history --limit 25
```

### Show per-query token counts
```bash
nervapack history --verbose
```

### Show aggregate statistics
```bash
nervapack history --stats
```

### Clear history
```bash
nervapack history --clear
```

---

## Output — query list

```
Recent Queries (showing last 5)

  #  │ Time              │ Query                           │ Nodes │ Savings │ Elapsed
 ════╪═══════════════════╪═════════════════════════════════╪═══════╪═════════╪════════
  1  │ 2026-07-16 13:20  │ graph builder nodes and edges   │     5 │  80.0%  │ 267ms
  2  │ 2026-07-16 13:19  │ MCP server tools and query      │     3 │  95.2%  │ 267ms
  3  │ 2026-07-16 13:18  │ vector search and similarity    │     3 │  92.9%  │ 263ms
  4  │ 2026-07-16 13:17  │ memory store and recall flow    │     2 │  85.0%  │ 266ms
  5  │ 2026-07-16 13:16  │ how does ingest work            │     3 │  94.1%  │ 342ms

Average token savings: 89.4%
Total tokens saved: 19,679
```

---

## Output — `--verbose`

Adds `NP Tokens` and `Naive Tokens` columns to show the raw token counts per query alongside the percentage:

```
  #  │ Time     │ Query                │ N… │ Sav…  │ Elapsed │ NP Tokens │ Naive Tokens
 ════╪══════════╪══════════════════════╪════╪═══════╪═════════╪═══════════╪═════════════
  1  │ 13:20    │ graph builder nod…   │  5 │ 80.0% │ 267ms   │     1,126 │       5,618
  2  │ 13:19    │ MCP server tools …   │  3 │ 95.2% │ 267ms   │       286 │       5,943
  3  │ 13:18    │ vector search and…   │  3 │ 92.9% │ 263ms   │       321 │       4,507
```

---

## Output — `--stats`

```
Query Analytics

  Total Queries                 47
  Avg Token Savings             83.2%
  Total Tokens Saved            42,800
  Avg Execution Time            215ms
  Avg Nodes Retrieved           10.4

  Total Cost Saved (GPT-4o)     $0.1070
  Total Cost Saved (Claude)     $0.1284

Most Queried Topics:
  memory    12
  recall     8
  ingest     5
  ...
```

---

## How history is stored

Every `nervapack query` run appends a JSON record to
`.nervapack/query_history.jsonl`. The file is append-only and human-readable.

Use `--clear` to delete history via the CLI. Alternatively, `nervapack clean --history` deletes both `query_history.jsonl` and `graph_history.jsonl` as part of a broader data-cleanup workflow.

Reads are tail-based (O(limit) not O(file size)) — querying the last 10 records from a large history file reads only the final few KB, never the full file.

---

## Dashboard

The same data appears in the **Query History** tab of `nervapack serve`.

---

## Related commands

- [`nervapack query`](query.md) — run a query (populates history)
- [`nervapack savings`](savings.md) — one-screen cumulative savings summary
- [`nervapack serve`](serve.md) — interactive dashboard
