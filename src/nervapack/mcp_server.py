"""
NervaPack MCP Server

Exposes NervaPack's knowledge graph as MCP tools so any MCP-compatible
LLM tool (Claude Code, Cursor, etc.) can query the graph natively.

Run via:  nervapack-mcp
Or add to .mcp.json:
  { "mcpServers": { "nervapack": { "command": "nervapack-mcp" } } }
"""
from __future__ import annotations

import json
import os
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP SDK is not installed. Run: pip install nervapack[mcp]"
    )


mcp = FastMCP(
    "nervapack",
    instructions=(
        "NervaPack provides a precise, token-efficient knowledge graph of the "
        "current codebase. Always call query_codebase before answering any "
        "question about how this codebase works, what a function does, or where "
        "something is defined. Use graph_status to check if the graph is up to date. "
        "Use list_entities to browse all known classes, functions, or imports."
    ),
)


def _load_graph():
    from nervapack.graph.builder import GraphBuilder
    builder = GraphBuilder()
    return builder.load_graph()


def _load_vstore():
    from nervapack.graph.vector_store import VectorStore
    return VectorStore()


# ── Tool 1: query_codebase ────────────────────────────────────────────────────

@mcp.tool()
def query(prompt: str, max_hops: int = 1) -> str:
    """
    Query the NervaPack knowledge graph for relevant code context.

    Performs a vector similarity search to find seed nodes, then runs a
    K-Hop BFS through the AST graph to collect related classes, functions,
    imports, and any documentation linked via EXPLAINS edges.

    Returns a compact Markdown block ready to use as LLM context.
    Use this before answering any question about the codebase.

    Args:
        prompt:   Natural-language description of what you're looking for.
        max_hops: How many hops to traverse from seed nodes (default 1).
                  Increase to 2 for broader context on complex queries.
    """
    try:
        graph = _load_graph()
    except Exception as e:
        return (
            f"Graph not found: {e}\n"
            "Run `nervapack ingest .` in the project root to build the graph first."
        )

    try:
        vstore = _load_vstore()
        results = vstore.search(prompt, n_results=5)
    except Exception as e:
        return f"Vector store error: {e}\nRun `nervapack ingest .` to rebuild."

    start_nodes = results.get("ids", [[]])[0] if results else []
    if not start_nodes:
        return "No relevant nodes found for this query. Try rephrasing or run `nervapack sync .`."

    from nervapack.graph.retrieval import GraphRetriever
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=max_hops)
    context = retriever.format_as_markdown(subgraph)

    # Append a compact token summary
    try:
        from nervapack.graph.token_meter import count_tokens, naive_rag_text
        np_tokens, exact = count_tokens(context)
        source_files = retriever.get_source_files(subgraph)
        naive_tokens, _ = count_tokens(naive_rag_text(source_files))
        prefix = "" if exact else "~"
        saved_pct = round((1 - np_tokens / max(naive_tokens, 1)) * 100, 1)
        context += (
            f"\n\n---\n*NervaPack: {prefix}{np_tokens:,} tokens "
            f"(vs {prefix}{naive_tokens:,} naive — {saved_pct}% saved)*"
        )
    except Exception:
        pass

    return context


# ── Tool 2: graph_status ──────────────────────────────────────────────────────

@mcp.tool()
def graph_status() -> str:
    """
    Return the current state of the NervaPack knowledge graph.

    Shows total node and edge counts broken down by type, which languages
    are present, and whether any files have been modified since the last
    ingest (i.e., whether `nervapack sync .` needs to be run).

    Use this to check if the graph is stale before relying on query results.
    """
    try:
        graph = _load_graph()
    except Exception as e:
        return (
            f"No graph found ({e}).\n"
            "Run `nervapack ingest .` to build it."
        )

    # Count by node type
    type_counts: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        t = data.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Count edge relations
    rel_counts: dict[str, int] = {}
    for _, _, data in graph.edges(data=True):
        r = data.get("relation", "unknown")
        rel_counts[r] = rel_counts.get(r, 0) + 1

    # Language breakdown from file extensions
    ext_counts: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        fp = data.get("file_path") or data.get("path", "")
        if fp:
            ext = os.path.splitext(fp)[1]
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    lines = [
        f"## NervaPack Graph Status\n",
        f"**Nodes:** {graph.number_of_nodes():,}  |  **Edges:** {graph.number_of_edges():,}\n",
        "### Node breakdown",
    ]
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {t}: {count:,}")

    lines.append("\n### Edge breakdown")
    for r, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {r}: {count:,}")

    if ext_counts:
        lines.append("\n### File extensions in graph")
        for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- `{ext}`: {count:,} nodes")

    # Check for unsynced files
    try:
        from nervapack.git.tracker import GitTracker
        tracker = GitTracker(".")
        if tracker.repo:
            changed = tracker.get_changed_files()
            if changed:
                lines.append(f"\n⚠️  **{len(changed)} file(s) modified since last ingest** — run `nervapack sync .`")
                for f in changed[:5]:
                    lines.append(f"   - {f}")
                if len(changed) > 5:
                    lines.append(f"   - … and {len(changed) - 5} more")
            else:
                lines.append("\n✅ Graph is up to date with the working tree.")
    except Exception:
        pass

    return "\n".join(lines)


# ── Tool 3: list_entities ─────────────────────────────────────────────────────

@mcp.tool()
def explore(entity_type: str = "", file_path: str = "") -> str:
    """
    List entities (classes, functions, imports) in the knowledge graph.

    Useful for exploring what NervaPack has indexed — e.g. all classes,
    all functions in a specific file, or all markdown docs.

    Args:
        entity_type: Filter by type — "class", "function", "import",
                     "markdown", or "file". Leave empty to list all.
        file_path:   Filter to a specific file (partial match, e.g. "cli.py").
                     Leave empty to list across all files.
    """
    try:
        graph = _load_graph()
    except Exception as e:
        return f"Graph not found: {e}\nRun `nervapack ingest .` first."

    rows = []
    for node_id, data in graph.nodes(data=True):
        t = data.get("type", "")
        fp = data.get("file_path") or data.get("path", "")

        if entity_type and t != entity_type.lower():
            continue
        if file_path and file_path.lower() not in (fp or "").lower():
            continue
        if t == "file":
            continue

        name = data.get("name") or data.get("header", "")
        start = data.get("start_line", "")
        end = data.get("end_line", "")
        loc = f"L{start}-L{end}" if start else ""
        short_path = os.path.basename(fp) if fp else "?"
        rows.append((t, name, short_path, loc))

    if not rows:
        qualifier = f" of type '{entity_type}'" if entity_type else ""
        qualifier += f" in '{file_path}'" if file_path else ""
        return f"No entities found{qualifier}."

    rows.sort(key=lambda r: (r[0], r[2], r[1]))

    lines = [f"## Entities ({len(rows)} found)\n"]
    lines.append(f"{'Type':<12} {'Name':<35} {'File':<25} Location")
    lines.append("-" * 85)
    for t, name, fp, loc in rows[:200]:
        lines.append(f"{t:<12} {name[:34]:<35} {fp[:24]:<25} {loc}")
    if len(rows) > 200:
        lines.append(f"\n… {len(rows) - 200} more. Narrow with entity_type or file_path.")

    return "\n".join(lines)


# ── Tool 4: impact ────────────────────────────────────────────────────────────

@mcp.tool()
def impact(target: str, max_hops: int = 1) -> str:
    """
    Perform impact analysis (reverse dependency search).
    
    Finds what depends on a given entity (e.g. who calls a function, who
    imports a file or class) by traversing the graph backwards.
    
    Args:
        target:   Name of the entity (e.g. "my_function", "UserAuth", "auth.py").
        max_hops: How many hops backwards to traverse (default 1).
    """
    try:
        graph = _load_graph()
    except Exception as e:
        return f"Graph not found: {e}\nRun `nervapack ingest .` first."
        
    start_nodes = []
    target_lower = target.lower()
    for node_id, data in graph.nodes(data=True):
        name = (data.get("name") or "").lower()
        fp = (data.get("file_path") or data.get("path") or "").lower()
        if target_lower in name or target_lower in fp:
            start_nodes.append(node_id)
            
    if not start_nodes:
        return f"Could not find any entity matching '{target}'."
        
    from nervapack.graph.retrieval import GraphRetriever
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=max_hops, direction="reverse")
    
    # We only want to show the inbound edges to the user
    # A simple markdown output of the dependents
    lines = [f"## Impact Analysis for '{target}' (hops={max_hops})"]
    found_any = False
    
    for u, v, data in subgraph.edges(data=True):
        if v in start_nodes or subgraph.nodes[v].get("name", "").lower() == target_lower:
            rel = data.get("relation", "DEPENDS_ON")
            caller_name = subgraph.nodes[u].get("name", u)
            caller_fp = subgraph.nodes[u].get("file_path", "?")
            callee_name = subgraph.nodes[v].get("name", v)
            lines.append(f"- **{caller_name}** (`{caller_fp}`) {rel} **{callee_name}**")
            found_any = True
            
    if not found_any:
        return f"No inbound dependencies found for '{target}'."
        
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
