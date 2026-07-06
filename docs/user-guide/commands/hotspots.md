# `nervapack hotspots`

Show the files changed most frequently in git history — high-churn areas
often indicate bug-prone or rapidly-evolving parts of the codebase.

---

## Synopsis

```bash
nervapack hotspots [OPTIONS]
```

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit N` / `-n N` | `20` | Number of files to show |
| `--since DATE` | all time | Only count commits since this date/expression |
| `--ext EXT` | all | Filter to a file extension (repeatable) |
| `--churn` | off | Sort by total lines changed instead of commit count |

---

## Examples

### Top 20 hotspots across all history
```bash
nervapack hotspots
```

### Limit to the last 6 months
```bash
nervapack hotspots --since "6 months ago"
```

### Last 3 months, Python files only, sorted by churn
```bash
nervapack hotspots --since "3 months ago" --ext .py --churn
```

### Focus on multiple extensions
```bash
nervapack hotspots --ext .py --ext .ts --limit 10
```

---

## Output

```
Code Hotspots  since 6 months ago

  #  │ File                          │ Changes │ +Lines │ -Lines │ Churn │ Heat
 ════╪═══════════════════════════════╪═════════╪════════╪════════╪═══════╪══════════
  1  │ src/nervapack/cli.py          │       8 │ +1,250 │    -47 │ 1,297 │ ████████
  2  │ README.md                     │      12 │ +1,049 │   -139 │ 1,188 │ ███████░
  3  │ pyproject.toml                │      23 │   +126 │    -27 │   153 │ ██░░░░░░
  ...
```

- **Changes** — number of commits that touched this file
- **+Lines / -Lines** — cumulative insertions and deletions
- **Churn** — insertions + deletions (total lines touched)
- **Heat** — visual bar proportional to commit count

---

## How it works

`hotspots` calls `git log --numstat` under the hood — no extra tools
required, no network access, no new dependencies beyond GitPython (already
a core dependency). Binary files are automatically skipped.

---

## Dashboard

The same data appears in the **Hotspots** tab of `nervapack serve`:

- Time-window dropdown (All time / 1 year / 6 months / 3 months / 1 month)
- Sort toggle (commit count vs churn)
- Interactive Plotly bar chart + filterable table

---

## Related commands

- [`nervapack dependencies`](dependencies.md) — static import dependency graph
- [`nervapack serve`](serve.md) — interactive dashboard with Hotspots tab
