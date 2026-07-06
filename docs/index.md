# NervaPack

<div class="hero" markdown>

**Privacy-first, offline knowledge graph for developers**

Build token-efficient context for your LLMs without sending code to the cloud.

[Get Started](getting-started/installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/ramdhavepreetam/NervaPack){ .md-button }

</div>

---

## Why NervaPack?

**NervaPack** solves two fundamental problems with standard Vector RAG:

- **Token waste** — chunk-based RAG retrieves blobs of text that may only tangentially relate to your query, bloating your context window.
- **Privacy risk** — sending code to cloud embedding APIs leaks your proprietary logic.

NervaPack runs 100% on your machine. It uses `tree-sitter` to parse your codebase into a deterministic Abstract Syntax Tree graph, then uses a local Ollama model to draw hard semantic edges between your documentation and your code. Queries traverse this graph with a K-Hop BFS, returning a hyper-targeted, token-efficient context window — no cloud required.

---

## Key Features

<div class="grid cards" markdown>

-   :material-shield-lock: **100% Private**

    ---

    All processing happens locally. Your code never leaves your machine. Uses ChromaDB + Ollama for complete privacy.

    [:octicons-arrow-right-24: Learn more](user-guide/concepts/architecture.md)

-   :material-speedometer: **91% Token Savings**

    ---

    Graph-based retrieval reduces tokens by 91% vs naive RAG. Verified through real-world testing. Save on API costs and context window limits.

    [:octicons-arrow-right-24: Verified benchmarks](BENCHMARKS.md) · [:octicons-arrow-right-24: Token efficiency](user-guide/concepts/token-efficiency.md)

-   :material-offline: **Offline First**

    ---

    Works completely offline with local Ollama models. Optional cloud providers (Claude, OpenAI) available.

    [:octicons-arrow-right-24: LLM providers](getting-started/llm-providers.md)

-   :material-graph: **AST-Based Precision**

    ---

    Deterministic parsing with tree-sitter. No arbitrary text chunks — only real code entities.

    [:octicons-arrow-right-24: How it works](user-guide/concepts/knowledge-graphs.md)

-   :material-source-branch: **Incremental Sync**

    ---

    GitPython-powered surgical updates. Only changed files are re-indexed.

    [:octicons-arrow-right-24: Sync command](user-guide/commands/sync.md)

-   :material-chart-timeline: **Rich Visualizations**

    ---

    Interactive HTML graphs with community detection, search, and dependency analysis.

    [:octicons-arrow-right-24: Visualization guide](user-guide/commands/visualize.md)

-   :material-brain: **Persistent Memory Layer**

    ---

    Give any LLM app persistent memory — chatbots, coding agents, multi-agent pipelines, decision logs. `memory_recall("project context")` loads 30 days of decisions in under 200 tokens. Bi-temporal, namespace-isolated, 100% offline.

    [:octicons-arrow-right-24: Memory overview](memory/index.md) · [:octicons-arrow-right-24: Use cases](memory/use-cases/chatbot.md)

</div>

---

## Quick Example

```bash
# Install (30 seconds)
brew install nervapack
# or: pipx install nervapack

# Build graph (2 minutes)
cd your-project/
nervapack ingest .

# Query (instant results)
nervapack query "How does authentication work?"

# Visualize
nervapack visualize --enhanced --communities
```

**Output:** Precise, token-efficient context with savings dashboard:

```
╭──────────────  NervaPack Token Efficiency  ──────────────╮
│  Strategy              Tokens   Visual            Relative │
│  Naive RAG (3 files)   12,840   ████████████████  100%    │
│  NervaPack              1,180   █░░░░░░░░░░░░░░░    9.2%  │
│ ──────────────────────────────────────────────────────────│
│  Tokens saved: 11,660   Reduction: 90.8%                  │
│  Cost saved (GPT-4o  $2.50/1M): $0.0292 per query         │
│  Cost saved (Claude Sonnet $3/1M): $0.0350 per query      │
╰───────────────────────────────────────────────────────────╯
```

!!! success "Verified Performance"
    The 91% token reduction is verified through real-world testing on NervaPack's own codebase.
    See [detailed benchmarks](BENCHMARKS.md) for test methodology and results.

---

## NervaPack vs Standard Vector RAG

| | Standard Vector RAG | NervaPack |
|---|---|---|
| **Parsing** | Arbitrary text chunks | Deterministic AST nodes (class, function, import) |
| **Retrieval** | Nearest-neighbor blob | K-Hop BFS on structural graph |
| **Doc ↔ Code links** | None | Hard `EXPLAINS` edges drawn by local LLM |
| **Privacy** | Cloud embeddings | 100% local (ChromaDB + Ollama) |
| **Incremental sync** | Re-index everything | Surgical per-file update via GitPython diff |
| **Token savings** | No measurement | Built-in dashboard shows exact reduction per query |
| **Graph visibility** | Black box | Interactive HTML visualization of every node and edge |

---

## Supported Languages

**Bundled** (no extra install):
- Python, JavaScript, JSX, TypeScript, TSX

**Optional extras**:
```bash
pip install "nervapack[go]"           # Go
pip install "nervapack[rust]"         # Rust
pip install "nervapack[java]"         # Java
pip install "nervapack[c]"            # C / C headers
pip install "nervapack[cpp]"          # C++
pip install "nervapack[ruby]"         # Ruby
pip install "nervapack[csharp]"       # C#
pip install "nervapack[all-languages]" # Everything
```

---

## Use Cases

- **Chatbot memory** — Persistent user preferences and conversation history; per-user namespace isolation; pure Python, no vector DB → [guide](memory/use-cases/chatbot.md)
- **AI coding agent** — Claude Code / Cursor recalls all project decisions and conventions at session start → [guide](memory/use-cases/coding-agent.md)
- **Multi-agent pipelines** — Agents share memory via namespaces; writer publishes facts, reader recalls them → [guide](memory/use-cases/multi-agent.md)
- **Decision log / ADRs** — Import architecture decisions, query why choices were made, detect when code drifts from decisions → [guide](memory/use-cases/adr-store.md)
- **Code onboarding** — Understand new codebases 10x faster with graph-precise retrieval
- **LLM context optimisation** — 91% smaller prompts via graph traversal vs. naive RAG
- **Refactoring analysis** — See full dependency impact before touching a file

---

## What's Next?

<div class="grid" markdown>

[**Installation Guide**](getting-started/installation.md){ .md-button }
Walk through setup for macOS, Linux, and Windows

[**Quick Start Tutorial**](getting-started/quick-start.md){ .md-button }
Build your first knowledge graph in 5 minutes

[**Command Reference**](user-guide/commands/ingest.md){ .md-button }
Detailed documentation for all 10 CLI commands

</div>

---

## Community & Support

- **GitHub Issues:** [Report bugs & request features](https://github.com/ramdhavepreetam/NervaPack/issues)
- **PyPI Package:** [nervapack on PyPI](https://pypi.org/project/nervapack/)
- **License:** MIT (free for commercial use)

---

**NervaPack** is actively developed and maintained. We welcome contributions!

[Contributing Guide](contributing.md){ .md-button }
