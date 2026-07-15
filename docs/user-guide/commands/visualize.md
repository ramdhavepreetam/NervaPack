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
| `--enhanced` | off | Enable real-time search + path finder |
| `--communities` | off | Enable Louvain community detection + colour coding |
| `--no-browser` | off | Generate without auto-opening the browser |

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

For graphs with > 5,000 nodes, the browser layout can be slow to settle. In that case:
- Use `nervapack explore <target>` to generate a focused subgraph visualization instead.
- Or use `--no-browser` to generate the file and open it manually after the physics have settled.

---

## See Also

- [`explore`](explore.md) — focused subgraph for a specific file or class
- [`serve`](serve.md) — full web dashboard with embedded graph explorer
- [`ingest`](ingest.md) — build the graph that `visualize` reads
