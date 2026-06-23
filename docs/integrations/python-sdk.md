# Python SDK

Build custom tools with NervaPack's Python API.

---

## Basic Usage

```python
from nervapack.graph.builder import GraphBuilder
from nervapack.graph.vector_store import VectorStore
from nervapack.graph.retrieval import GraphRetriever

# Load graph
graph = GraphBuilder().load_graph()

# Query
vstore = VectorStore()
results = vstore.search("authentication", n_results=3)
start_nodes = results["ids"][0]

# Retrieve context
retriever = GraphRetriever(graph)
subgraph = retriever.retrieve_context(start_nodes, max_hops=1)
context = retriever.format_as_markdown(subgraph)

print(context)
```

---

## API Documentation

See [API Reference](../api/graph.md) for detailed module docs.
