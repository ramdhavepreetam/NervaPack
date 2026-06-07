# NervaPack

**NervaPack** is a privacy-first, offline knowledge graph designed to solve "token waste" and privacy risks inherent in standard Vector RAG. It runs entirely on your local machine (optimized for Apple Silicon). 

By explicitly binding human-readable documentation to deterministic Abstract Syntax Tree (AST) code structures via a local LLM, NervaPack allows you to query your entire codebase locally and retrieve hyper-targeted context windows.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**
- **Ollama**: You must have [Ollama](https://ollama.com/) installed and running locally. 
  - Pull a local model before running (e.g., `ollama run llama3` or `phi3`). The default model NervaPack uses is `llama3`.
- **Git**: Ensure your project is a Git repository (`git init`).

### 2. Installation
To install NervaPack in your project environment, clone this repository and install it via `pip`:

```bash
git clone https://github.com/ramdhavepreetam/NervaPack.git
cd NervaPack
pip install -e .
```

*Note: The first time you run this, `chromadb` will download `onnxruntime` models to your cache, and `tree-sitter` bindings will be built.*

---

## 🛠️ How to Use NervaPack in Your Projects

Once installed, NervaPack provides a CLI called `nervapack` that you can run at the root of any Git repository.

### Step 1: Ingest Your Codebase
To build your initial Knowledge Graph, run:
```bash
nervapack ingest .
```
**What happens behind the scenes?**
1. **Structural Parsing:** `tree-sitter` scans all `.py`, `.js`, and `.ts` files to identify Classes, Functions, and Imports exactly, avoiding arbitrary text chunks.
2. **Semantic Docs:** It scans all `.md` files and chunks them by headers.
3. **LLM Binding:** It feeds the Markdown prose to your local Ollama model. If Ollama determines the prose explains a specific code entity, NervaPack draws a hard `EXPLAINS` edge in the graph.
4. **Vector Storage:** Summaries and code snippets are embedded into a local `ChromaDB` instance (`.nervapack/chroma_db`).

*(Note: Depending on the size of your codebase and your local machine's speed, the initial LLM Binding step may take several minutes).*

### Step 2: Query for Context
When you need context for a feature, bug, or general question, simply query the graph:
```bash
nervapack query "How does the CLI work?"
```
**What happens behind the scenes?**
1. NervaPack converts your prompt into an embedding and queries ChromaDB to find the most relevant nodes.
2. It uses those nodes as "seeds" and performs a **K-Hop Breadth-First Search (BFS)** through the NetworkX graph.
3. It crawls adjacent dependencies (e.g., finding the Markdown documentation that explains the matched function) and returns a highly compressed, token-efficient Markdown snippet directly to your terminal.

### Step 3: Fast Incremental Syncs
As you code, you don't want to re-parse the entire repository. When you modify files, simply run:
```bash
nervapack sync .
```
**What happens behind the scenes?**
NervaPack hooks into `GitPython` to check your working tree diffs. It prunes the old vectors and graph nodes associated *only* with the files you modified or deleted, and selectively re-ingests the new code. This turns a 10-minute full ingestion into a 2-second surgical update.

### Step 4: Check Status
To view the health of your graph, total nodes, edges, and see what files are currently out of sync:
```bash
nervapack status
```

---

## 📁 Architecture Overview

- **Storage Layers:**
  - `Vector Store (ChromaDB)`: Handles semantic similarity searches.
  - `Structural Graph (NetworkX)`: Maps exact deterministic relationships (`DEFINES`, `EXPLAINS`, `IMPLEMENTS`).
- **Core Modules:**
  - `nervapack.parser.ast_parser`: Deterministic Tree-Sitter parsing.
  - `nervapack.parser.md_chunker`: Hierarchical prose chunking.
  - `nervapack.git.tracker`: Temporal diffing for surgical updates.
  - `nervapack.llm.summarizer`: Local LLM interface for drawing edges.
  - `nervapack.graph.retrieval`: BFS context crawler.

## 🔒 Privacy
NervaPack is 100% offline. No code or documentation ever leaves your machine. Vector embeddings are stored locally in the `.nervapack` directory, and LLM queries are routed exclusively to your local `localhost:11434` Ollama instance.
