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
Recent Queries (showing last 10)

  #  │ Time              │ Query                           │ Nodes │ Savings │ Time
 ════╪═══════════════════╪═════════════════════════════════╪═══════╪═════════╪══════
  1  │ 2026-07-05 21:00  │ How does memory_store work?     │    12 │  84.3%  │ 230ms
  2  │ 2026-07-05 20:45  │ What is the recall pipeline?    │     9 │  81.1%  │ 198ms
  ...

Average token savings: 83.2%
Total tokens saved: 42,800
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
Use `--clear` to delete it.

---

## Dashboard

The same data appears in the **Query History** tab of `nervapack serve`.

---

## Related commands

- [`nervapack query`](query.md) — run a query (populates history)
- [`nervapack serve`](serve.md) — interactive dashboard
