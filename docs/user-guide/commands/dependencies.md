# `nervapack dependencies`

Analyze file-level import dependencies, detect circular dependencies, and visualize the dependency graph.

---

## Synopsis

```bash
nervapack dependencies [FILE] [OPTIONS]
```

---

## Description

`dependencies` reads the import edges already stored in your NervaPack graph to build a file-level dependency map. It detects circular import chains, ranks files by how heavily they're depended on, and produces an interactive HTML visualization with the same physics engine used by `nervapack visualize`.

No re-parsing or LLM calls are required — it operates entirely on the existing graph.

---

## Arguments and Options

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `FILE` | *(none)* | Analyze a single file instead of the whole project |
| `--cycles` / `--no-cycles` | cycles on | Include circular dependency detection |
| `--layers` / `--no-layers` | layers on | Include topological layer analysis |
| `--output PATH` | `.nervapack/dependencies.html` | Where to save the visualization |
| `--no-browser` | off | Generate without opening the browser |

---

## Examples

### Full project analysis
```bash
nervapack dependencies
```

### Single file — who does it import, who imports it?
```bash
nervapack dependencies src/graph/builder.py
```

### Skip cycle detection (faster on very large graphs)
```bash
nervapack dependencies --no-cycles
```

---

## Output — Project Analysis

```
╭──────────  Dependency Metrics  ──────────╮
│ Total Files              │  127          │
│ Total Dependencies       │  456          │
│ Max Dependency Depth     │  8            │
│ Orphan Files             │  3            │
╰──────────────────────────────────────────╯

⚠  Circular Dependencies Detected: 2 cycle(s)

Cycle 1:
  auth.py
  → user.py
  → session.py
  → auth.py  (back to start)

Cycle 2:
  config.py
  → settings.py
  → config.py  (back to start)

Most Depended-On Files (top 10):
  1. src/utils/common.py          (42 dependents)
  2. src/models/base.py           (38 dependents)
  3. src/config.py                (31 dependents)
  ...

Files With Most Dependencies (top 10):
  1. src/cli.py                   (18 imports)
  2. src/graph/builder.py         (14 imports)
  ...

Visualization saved to .nervapack/dependencies.html
```

---

## Output — Single File

```
Dependencies for: src/graph/builder.py

Imports (what this file depends on):
  - src/graph/vector_store.py
  - src/parser/ast_parser.py
  - src/graph/token_meter.py

Imported by (what depends on this file):
  - src/nervapack/cli.py
  - src/nervapack/mcp_server.py
```

---

## Visualization

Node colours in the HTML dependency graph:

| Colour | Meaning |
|--------|---------|
| Red | Part of a circular dependency |
| Cyan | Heavily depended on (> 5 dependents) |
| Yellow | Many dependencies (> 5 imports) |
| Green | Normal file |
| Gray | Orphan (no imports, not imported) |

Node size scales with total degree. Layout uses topological sort (DAG) or spring-force (cyclic graphs). A search box lets you filter by filename.

---

## Relationship to the code graph

`dependencies` uses the `DEFINES` and `REFERENCES` edges that `nervapack ingest` writes. For the most accurate results, run `nervapack sync .` first if you've changed files since the last ingest.

---

## See Also

- [`ingest`](ingest.md) — build the graph that `dependencies` reads
- [`sync`](sync.md) — keep the graph up to date
- [`hotspots`](hotspots.md) — which files change most in git history
- [`explore`](explore.md) — focused subgraph around a single entity
- [`serve`](serve.md) — interactive dashboard with dependency analysis tab
