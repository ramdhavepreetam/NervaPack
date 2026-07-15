# `nervapack explore`

Extract and visualize the N-hop neighbourhood of a specific file, class, or function.

---

## Synopsis

```bash
nervapack explore TARGET [OPTIONS]
```

---

## Description

`explore` is `visualize` scoped to a single entity. You give it a file path, class name, or function name and it:

1. Finds all graph nodes that match the target string (by file path, node name, or node ID).
2. Runs a multi-source BFS to N hops from those seed nodes.
3. Generates an enhanced HTML visualization of just that subgraph — with search and path finder enabled.

Use `explore` when you want to understand one module's relationships without the noise of the full graph.

---

## Arguments and Options

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `TARGET` | *(required)* | File path, class name, function name, or partial string to match |
| `--hops N` / `-h N` | `2` | Number of BFS hops from the matched nodes |
| `--output PATH` | `.nervapack/explore_{target}.html` | Where to save the HTML file |
| `--no-browser` | off | Generate without opening the browser |

---

## Examples

### Explore a class by name
```bash
nervapack explore GraphBuilder --hops 2
```

### Explore a file
```bash
nervapack explore src/graph/builder.py --hops 1
```

### Partial name match (all nodes containing "store")
```bash
nervapack explore store --hops 1
```

### Save to a custom path
```bash
nervapack explore AuthMiddleware --output ~/graphs/auth.html
```

---

## Output

```
Exploring neighborhood of 'GraphBuilder' (hops=2)...
Found 3 matching nodes:
  - class:src/nervapack/graph/builder.py:GraphBuilder
  - function:src/nervapack/graph/builder.py:build_from_entities
  - function:src/nervapack/graph/builder.py:save_graph

Extracting 2-hop neighborhood...
Subgraph: 47 nodes, 83 edges

Visualization saved: .nervapack/explore_GraphBuilder.html
Opened in browser.
```

---

## Use cases

| Goal | Command |
|------|---------|
| Understand a class before refactoring | `nervapack explore MyClass --hops 2` |
| Check who calls a function | `nervapack explore my_function --hops 1` |
| See what a file imports and exports | `nervapack explore src/foo.py --hops 1` |
| Onboard to a module quickly | `nervapack explore src/auth/ --hops 2` |
| Pre-review impact check | `nervapack explore ChangedClass --hops 2` |

---

## Difference from `visualize`

| | `visualize` | `explore` |
|--|-------------|-----------|
| Scope | Full graph | Subgraph around one entity |
| Speed | Slow on large graphs | Fast (small subgraph) |
| Good for | Big-picture view | Focused investigation |
| Search | `--enhanced` flag | Always enabled |

---

## See Also

- [`visualize`](visualize.md) — full graph visualization
- [`query`](query.md) — text-based context retrieval
- [`dependencies`](dependencies.md) — file-level import dependency analysis
