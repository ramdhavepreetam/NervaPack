# Knowledge Graphs

Understanding knowledge graphs is key to using NervaPack effectively.

---

## What is a Knowledge Graph?

A **knowledge graph** is a network of interconnected entities (nodes) and their relationships (edges). Unlike traditional databases that store data in tables, knowledge graphs represent information as a web of connections.

**Example:**
```
[File: auth.py] ──DEFINES──> [Class: AuthMiddleware]
                                    ↑
                                    │
                            EXPLAINS
                                    │
                            [Doc: Authentication Guide]
```

---

## Why Knowledge Graphs for Code?

Traditional approaches to code understanding:

❌ **Text search** — Finds keywords, not concepts  
❌ **Full-file retrieval** — Includes irrelevant code  
❌ **Chunking** — Breaks semantic boundaries

✅ **Knowledge graphs** — Preserve structural relationships

---

## NervaPack's Graph Model

### Node Types
- **file** — Source files
- **class** — Class definitions
- **function** — Function/method definitions
- **import** — Import statements
- **markdown** — Documentation chunks

### Edge Types
- **DEFINES** — File defines a class/function/import
- **EXPLAINS** — Documentation explains code entity

---

## Graph vs Vector RAG

| Approach | Retrieval Method | Context Quality |
|----------|------------------|-----------------|
| **Vector RAG** | Cosine similarity on chunks | Often includes irrelevant text |
| **Graph RAG** | Structural traversal (BFS) | Precise, semantically connected |

---

## Learn More

- [Architecture](architecture.md) — How NervaPack builds the graph
- [Token Efficiency](token-efficiency.md) — Why graphs save tokens
