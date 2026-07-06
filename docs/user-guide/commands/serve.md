# `nervapack serve`

Launch an interactive web dashboard for your knowledge graph — graph health,
query analytics, code hotspots, and graph evolution, all in one place.

---

## Synopsis

```bash
nervapack serve [OPTIONS]
```

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port N` / `-p N` | `8501` | Port to run the dashboard on |
| `--no-browser` | off | Don't open the browser automatically |

---

## Requirements

The dashboard requires optional dependencies:

```bash
pip install "nervapack[dashboard]"
# or:
pip install streamlit plotly pandas
```

---

## Examples

```bash
# Launch on default port, open browser
nervapack serve

# Custom port
nervapack serve --port 8080

# Headless (server environments, CI)
nervapack serve --no-browser
```

---

## Dashboard Tabs

### Overview
- Health score (0–100) with colour indicator
- Total nodes, edges, doc coverage cards
- Language distribution bar chart
- Most connected files table

### Analytics
- Node type and edge type pie charts
- Degree distribution histogram

### Query History
- Aggregate token savings and cost metrics
- Top queried keywords
- Recent query log (requires prior `nervapack query` runs)

### Graph Explorer
- Node search (by name, type, or file path)
- Graph density and orphaned node count

### Hotspots *(v0.5.3+)*
- Files ranked by commit frequency or total churn
- Time-window filter (All time / 1 year / 6 months / 3 months / 1 month)
- Interactive Plotly bar chart + table

### Graph Evolution *(v0.5.3+)*
- Node and edge count over time (recorded per `ingest` / `sync`)
- Health score and documentation coverage trends
- Sync log table (newest first)

!!! note "Evolution tab"
    The Graph Evolution timeline is empty on first launch. Snapshots are
    recorded automatically every time you run `nervapack ingest` or
    `nervapack sync`. The chart fills in as you use NervaPack.

---

## Related commands

- [`nervapack hotspots`](hotspots.md) — CLI view of code hotspots
- [`nervapack history`](history.md) — CLI view of query history
