# `nervapack status`

Show the health and current state of the local NervaPack graph.

---

## Synopsis

```bash
nervapack status [--detailed]
```

---

## Description

`status` gives you a quick read on whether your graph is up to date and how healthy it is.

Without `--detailed` it prints a one-screen summary: node/edge counts, git sync status, and a list of unsynced files. With `--detailed` it adds a full analytics panel: health score, language distribution, documentation coverage, and the most connected files.

---

## Options

| Option | Description |
|--------|-------------|
| `--detailed` / `-d` | Show comprehensive analytics (health score, language breakdown, coverage) |

---

## Examples

```bash
# Quick check
nervapack status

# Full analytics panel
nervapack status --detailed
```

---

## Output — Quick Mode

```
NervaPack Status:
- Graph loaded: Yes
- Nodes: 1,322
- Edges: 21,833
- Git repo detected: Yes
- Unsynced changes: 2 file(s)
  - src/graph/builder.py
  - src/graph/retrieval.py

Use --detailed for comprehensive analytics
```

---

## Output — Detailed Mode

```
╭──────────────  NervaPack Status  ──────────────╮
│ Graph Health Score: 85/100 ●●●●●●●●○○          │
│                                                │
│ 📊 Overview                                    │
│   Nodes:        1,322                          │
│   Edges:       21,833                          │
│   Files:           78                          │
│   Functions:      551                          │
│   Classes:         65                          │
│   Imports:        628                          │
│                                                │
│ 📚 Language Distribution                       │
│   Python      ████████████████  100.0%  (78)  │
│                                                │
│ 📖 Documentation Coverage                      │
│   ████████░░░░░░░░  67.8% (416/616 entities)   │
│                                                │
│ 🔗 Most Connected Files                        │
│   1. cli.py                    (75 edges)      │
│   2. builder.py                (48 edges)      │
│   3. retrieval.py              (31 edges)      │
│                                                │
│ 🔄 Git Sync Status                             │
│   ✓ Graph is in sync                           │
╰────────────────────────────────────────────────╯
```

---

## Health Score

The health score (0–100) is computed from four factors:

| Factor | Weight | What it measures |
|--------|--------|------------------|
| Documentation coverage | 40 pts | % of functions/classes with an `EXPLAINS` edge from a doc chunk |
| Node connectivity | 30 pts | Inverse fraction of orphaned nodes (no edges at all) |
| Graph density | 20 pts | Edge/node ratio, scaled to a sweet spot |
| Edge diversity | 10 pts | Both `DEFINES` and `EXPLAINS` edges present |

A newly ingested structural-only graph (no LLM binding) typically scores 30–40. After `nervapack enrich .` the score rises to 70–90 depending on your documentation coverage.

---

## See Also

- [`ingest`](ingest.md) — build the graph
- [`sync`](sync.md) — update after code changes
- [`enrich`](enrich.md) — improve health score by adding semantic edges
- [`clean`](clean.md) — wipe and restart if the graph is wrong
