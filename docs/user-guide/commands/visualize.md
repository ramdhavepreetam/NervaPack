# `nervapack visualize`

Render the knowledge graph as an interactive, standalone HTML file.

---

## Synopsis

```bash
nervapack visualize [OPTIONS]
```

---

## Description

`visualize` reads the graph from `.nervapack/graph.graphml` and generates a self-contained HTML file with no external dependencies — drag, zoom, search, and share it without any server.

Two rendering modes are available:

- **Basic** (default) — spring-force physics layout, hover tooltips, node colours by type.
- **Enhanced** (`--enhanced`, `--communities`) — adds real-time search, shortest-path finder, and Louvain community detection.

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output PATH` | `.nervapack/graph.html` | Where to save the HTML file |
| `--scope TARGET` | (none) | Only render the neighborhood around a file/name/node (e.g. a program name). Physics stays on for these small, readable views. |
| `--hops N` | `2` | Neighborhood depth when `--scope` is given — follows both callers and callees |
| `--enhanced` | off | Enable real-time search + path finder |
| `--communities` | off | Enable Louvain community detection + colour coding |
| `--no-browser` | off | Generate without auto-opening the browser |

### Scoping large estates

For a big graph (thousands of nodes), rendering the whole thing is rarely
readable — `--scope` is the way to navigate it. It extracts the N-hop
neighborhood around the matched node(s), following **both directions** so you
see what a program calls *and* who calls it:

```bash
# PAYROLL, its callers, and its callees (2 hops)
nervapack visualize --scope PAYROLL --hops 2

# Just the immediate neighbors of a copybook
nervapack visualize --scope EMPREC --hops 1
```

Scoped output defaults to `.nervapack/scope_<TARGET>.html` so it never clobbers
the full-graph file. Because scoped views are small, physics stays enabled for a
proper interactive layout.

---

## Examples

```bash
# Basic visualization
nervapack visualize

# Enhanced — search + path finder
nervapack visualize --enhanced

# Enhanced + community detection (recommended)
nervapack visualize --enhanced --communities

# Custom output path
nervapack visualize --enhanced --output ~/graphs/myproject.html

# Generate without opening browser (server/CI)
nervapack visualize --no-browser
```

---

## What you see

### Node colours (basic mode)

| Colour | Node type |
|--------|-----------|
| Blue | File |
| Green | Function |
| Amber | Class |
| Gray | Import |
| Lavender | Markdown doc |

In `--communities` mode, nodes are coloured by detected community (module cluster) instead.

### Node shapes

| Shape | Meaning |
|-------|---------|
| Diamond | File node |
| Circle | All other entities |

Node size scales with degree (more connections = larger node).

### Edge styles

| Style | Edge type |
|-------|-----------|
| Solid line | `DEFINES` (AST structural edge) |
| Dashed line | `EXPLAINS` (doc-to-code semantic edge) |

### Interactions

- **Hover** — tooltip with type, name, file, line range, and a code/content preview
- **Drag** — reposition nodes; spring-force physics settle them
- **Scroll/pinch** — zoom in/out
- **Click** — select a node and highlight its direct connections

### Enhanced mode only

- **Search box** — type to filter nodes in real time; matched nodes are enlarged and non-matched nodes are dimmed
- **Path finder** — click two nodes in sequence to highlight the shortest path between them
- **Community colours** — Louvain algorithm groups strongly connected nodes into communities, each coloured distinctly

---

## Output

```
Rendering graph (1,322 nodes, 21,833 edges)...
Using enhanced visualization with:
  ✓ Search functionality
  ✓ Community detection
Visualization saved: /path/to/.nervapack/graph.html
Opened in browser.
```

---

## Performance notes

Interactive force-directed physics only stays responsive for a couple of
thousand nodes. NervaPack handles large graphs automatically:

- **Above ~2,000 nodes, physics is disabled** — the browser renders a static
  layout immediately instead of running an unbounded force simulation that
  never settles and pins the CPU.
- **Very large graphs are capped** to the most-connected core (by default the
  top ~3,000 nodes / ~8,000 edges). Selecting highest-degree nodes keeps the
  structurally important hubs — heavily-called programs, shared copybooks — and
  the command prints exactly how many of the total were shown.

The full graph is always preserved in `.nervapack/graph.graphml`; capping only
affects the HTML view. To navigate the whole graph at scale:

- Use `nervapack explore <target>` for a focused subgraph around one entity.
- Use `nervapack query` / the MCP tools to traverse programmatically.

This is expected for large mainframe estates — a 20k-node / 400k-edge graph is
not meant to be read as a single hairball; scoped views are how you navigate it.

---

## See Also

- [`explore`](explore.md) — focused subgraph for a specific file or class
- [`serve`](serve.md) — full web dashboard with embedded graph explorer
- [`ingest`](ingest.md) — build the graph that `visualize` reads
