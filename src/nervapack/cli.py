import typer
from typing import List, Optional
from rich.console import Console

from nervapack import __version__
from nervapack._update_check import start as _start_update_check

app = typer.Typer(
    help="NervaPack: Privacy-first, offline knowledge graph for developers.",
    no_args_is_help=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def _callback(ctx: typer.Context) -> None:
    """Run the update checker in the background on every CLI invocation."""
    _start_update_check(__version__)


@app.command()
def init():
    """
    Initialize a NervaPack graph in the current directory.
    """
    console.print("[bold green]Initializing NervaPack graph...[/bold green]")
    # TODO: Implement initialization logic
    console.print("Initialization complete.")

@app.command()
def ingest(
    path: str = typer.Argument(".", help="Path to the repository to ingest"),
    llm: str = typer.Option(None, help="LLM provider (ollama, claude, openai, mcp). Auto-detects if not specified."),
    model: str = typer.Option(None, help="Model name (provider-specific)"),
    api_key: str = typer.Option(None, help="API key for cloud providers"),
    embeddings: str = typer.Option(None, help="Embedding backend (onnx, ollama). Defaults to ONNX."),
    no_bind: bool = typer.Option(False, "--no-bind", help="Skip LLM doc-to-code binding (fast keyword binding only). Useful for quick re-ingests."),
):
    """
    Ingest a repository, building the AST and Vector graph.

    LLM Providers:
      ollama     - Local Ollama (privacy-first, free)
      claude     - Claude API (requires ANTHROPIC_API_KEY)
      openai     - OpenAI API (requires OPENAI_API_KEY)
      mcp        - MCP delegation (auto-used in Claude Code/Cursor)

    Examples:
      nervapack ingest .                           # Auto-detect provider
      nervapack ingest . --llm ollama              # Force Ollama
      nervapack ingest . --llm claude              # Use Claude API
      nervapack ingest . --llm openai --model gpt-4o-mini
    """
    from nervapack.parser.ast_parser import scan_directory
    from nervapack.graph.builder import GraphBuilder
    from nervapack.llm.factory import get_llm_provider
    from rich.prompt import Confirm
    import time
    import os

    start_time = time.time()
    console.print(f"[bold blue]Ingesting repository at {path}...[/bold blue]")

    console.print("Scanning directory for code entities...")
    entities = scan_directory(path)
    console.print(f"Found {len(entities)} AST entities.")

    console.print("Building deterministic Structural Graph...")
    builder = GraphBuilder()
    graph = builder.build_from_entities(entities)
    console.print(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    console.print("Ingesting AST nodes into Vector Store...")
    try:
        from nervapack.graph.vector_store import VectorStore
        
        embed_backend = embeddings or os.getenv("NERVAPACK_EMBEDDINGS", "onnx")
        embed_fn = None
        if embed_backend.lower() == "ollama":
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
            embed_fn = OllamaEmbeddingFunction(
                url="http://localhost:11434/api/embeddings",
                model_name="all-minilm"
            )

        vstore = VectorStore(embedding_function=embed_fn)

        # We'll just ingest them with basic code text for now (in production, LLMSummarizer would summarize them first)
        ast_docs = []
        for e in entities:
            # We construct a mock 'summary' that just describes the node to avoid calling local Ollama during tests
            node_id = f"{e.type}:{e.file_path}:{e.name}:{e.start_line}"
            ast_docs.append({
                "node_id": node_id,
                "summary": f"This is a {e.type} named {e.name} in {e.file_path}. Code:\n{e.content}",
                "file_path": e.file_path
            })

        vstore.ingest_ast_entities(ast_docs)
        console.print("AST Vector ingestion complete.")

        from nervapack.parser.md_chunker import scan_markdown_directory
        console.print("Scanning directory for Markdown docs...")
        md_chunks = scan_markdown_directory(path)
        console.print(f"Found {len(md_chunks)} Markdown chunks.")

        if md_chunks:
            # Ingest to vector store
            vstore.ingest_chunks(md_chunks)

            # Get LLM provider (skip if --no-bind)
            provider = None
            if no_bind:
                console.print("[dim]--no-bind set: skipping LLM binding, using keyword matching only.[/dim]")
            else:
                console.print("\n[bold cyan]Setting up LLM provider...[/bold cyan]")
                try:
                    provider = get_llm_provider(
                        provider=llm,
                        model=model,
                        api_key=api_key
                    )
                    provider_name = provider.get_provider_name()

                    # Validate configuration
                    if not provider.validate_config():
                        raise ValueError(f"Provider {provider_name} configuration invalid")

                    console.print(f"Using LLM provider: [green]{provider_name}[/green]")

                    # Show cost estimate for cloud providers
                    estimated_cost = provider.estimate_cost(len(md_chunks))
                    if estimated_cost is not None and estimated_cost > 0:
                        console.print(f"\n[bold yellow]💰 Cost Estimate[/bold yellow]")
                        console.print(f"Provider: {provider_name}")
                        console.print(f"Markdown chunks to bind: {len(md_chunks)}")
                        console.print(f"Estimated cost: [yellow]${estimated_cost:.2f}[/yellow]")
                        console.print(f"(Actual cost may vary based on content length)\n")

                        # Ask for confirmation
                        if not Confirm.ask("Proceed with cloud LLM binding?"):
                            console.print("[yellow]Binding cancelled. Graph created but docs not linked.[/yellow]")
                            provider = None

                except Exception as e:
                    console.print(f"[bold yellow]Notice: Install/Start Ollama to unlock semantic doc-code binding. Building structural graph only. ({e})[/bold yellow]")
                    provider = None

            console.print("Binding documentation to AST (this may take a while)...")
            import re as _re
            def _kw_bind(doc_text, nodes, top_k=5):
                """Keyword-overlap binding — free, instant, no API calls."""
                doc_words = set(w for w in _re.findall(r"[a-zA-Z_]{4,}", doc_text.lower()))
                if not doc_words:
                    return []
                scored = []
                for n in nodes:
                    node_words = set(w for w in _re.findall(r"[a-zA-Z_]{4,}", n["node_id"].lower()))
                    overlap = len(doc_words & node_words)
                    if overlap >= 2:
                        scored.append((overlap, n["node_id"]))
                scored.sort(key=lambda x: -x[0])
                return [nid for _, nid in scored[:top_k]]

            for i, chunk in enumerate(md_chunks):
                md_node_id = f"md_{chunk['file_path']}_{i}"
                if not graph.has_node(md_node_id):
                    graph.add_node(md_node_id, type="markdown", header=chunk['header'], content=chunk['content'], file_path=chunk['file_path'])

                if provider:
                    matched_ids = provider.bind_docs_to_ast(chunk['content'], ast_docs)
                    source = "semantic-llm"
                    confidence = 0.9
                else:
                    matched_ids = _kw_bind(chunk['content'], ast_docs)
                    source = "keyword"
                    confidence = 0.5

                for matched_id in matched_ids:
                    if graph.has_node(matched_id):
                        graph.add_edge(md_node_id, matched_id, relation="EXPLAINS", source=source, confidence=confidence)

            console.print("Semantic binding complete.")

    except Exception as e:
        console.print(f"[bold red]Error during ingestion:[/bold red] {e}")

    # Single graph save — done once after all work (structural + doc binding)
    builder.save_graph()
    console.print(f"Graph saved with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    # Record graph snapshot for temporal tracking (reuse in-memory graph, no disk reload)
    try:
        from nervapack.graph.analytics import GraphAnalytics
        from nervapack.graph.graph_history import GraphHistory
        GraphHistory().record_from_analytics(GraphAnalytics(graph), trigger="ingest")
    except Exception:
        pass

    elapsed_time = time.time() - start_time
    console.print(f"[bold green]Ingestion complete in {elapsed_time:.2f} seconds.[/bold green]")

@app.command()
def sync(path: str = typer.Argument(".", help="Path to the repository to sync")):
    """
    Sync graph with modified git files.
    """
    from nervapack.git.tracker import GitTracker
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.vector_store import VectorStore
    from nervapack.parser.ast_parser import ASTParser
    from nervapack.parser.md_chunker import MarkdownChunker
    from nervapack.parser.language_registry import LANGUAGE_REGISTRY
    import os

    _CODE_EXTS = tuple(LANGUAGE_REGISTRY.keys())

    console.print("[bold blue]Syncing changed files with NervaPack graph...[/bold blue]")
    
    tracker = GitTracker(path)
    if not tracker.repo:
        console.print("[bold red]Not a git repository. Cannot sync.[/bold red]")
        raise typer.Exit(1)
        
    changed_files = tracker.get_changed_files()
    if not changed_files:
        console.print("[bold green]No files changed. Graph is up to date.[/bold green]")
        raise typer.Exit(0)
        
    console.print(f"Found {len(changed_files)} changed files.")
    
    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
        vstore = VectorStore()
    except Exception as e:
        console.print(f"[bold red]Failed to load graph or vector store. Run 'nervapack ingest' first.[/bold red]")
        raise typer.Exit(1)

    ast_parser = ASTParser()
    md_chunker = MarkdownChunker()
    
    # ast_docs accumulates summaries from all changed code files for doc binding
    ast_docs: list = []

    for f in changed_files:
        file_path = os.path.join(path, f)

        # 1. Prune old nodes and vectors
        builder.remove_nodes_for_file(file_path)
        vstore.delete_by_file(file_path)

        if not os.path.exists(file_path):
            console.print(f"Removed [red]{f}[/red]")
            continue

        # 2. Re-parse and insert
        if file_path.endswith(_CODE_EXTS):
            entities = ast_parser.parse_file(file_path)

            # Add to graph
            file_node_id = f"file:{file_path}"
            if not graph.has_node(file_node_id):
                graph.add_node(file_node_id, type="file", path=file_path)

            new_summaries = []
            for entity in entities:
                entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
                graph.add_node(
                    entity_node_id,
                    type=entity.type,
                    name=entity.name,
                    file_path=entity.file_path,
                    start_line=entity.start_line,
                    end_line=entity.end_line,
                    content=entity.content
                )
                graph.add_edge(file_node_id, entity_node_id, relation="DEFINES")
                new_summaries.append({
                    "node_id": entity_node_id,
                    "summary": f"This is a {entity.type} named {entity.name} in {entity.file_path}. Code:\n{entity.content}",
                    "file_path": entity.file_path,
                })

            # Single batched write — avoids one ChromaDB transaction per entity
            if new_summaries:
                vstore.ingest_ast_entities(new_summaries)

            # Accumulate for doc binding across all changed files
            ast_docs.extend(new_summaries)

            console.print(f"Updated AST for [green]{f}[/green]")
            
        elif file_path.endswith('.md'):
            chunks = md_chunker.chunk_file(file_path)
            if chunks:
                vstore.ingest_chunks(chunks)
                
                from nervapack.llm.summarizer import LLMSummarizer
                llm = LLMSummarizer()
                for i, chunk in enumerate(chunks):
                    md_node_id = f"md_{chunk['file_path']}_{i}"
                    graph.add_node(md_node_id, type="markdown", header=chunk['header'], content=chunk['content'], file_path=chunk['file_path'])
                    matched_ids = llm.bind_docs_to_ast(chunk['content'], ast_docs)
                    for matched_id in matched_ids:
                        if graph.has_node(matched_id):
                            graph.add_edge(md_node_id, matched_id, relation="EXPLAINS", source="semantic-llm", confidence=0.9)
                            
            console.print(f"Updated Markdown for [cyan]{f}[/cyan]")
            
    builder.save_graph()

    # Record graph snapshot for temporal tracking
    try:
        from nervapack.graph.analytics import GraphAnalytics
        from nervapack.graph.graph_history import GraphHistory
        GraphHistory().record_from_analytics(
            GraphAnalytics(graph), trigger="sync", files_changed=len(changed_files)
        )
    except Exception:
        pass

    console.print("[bold green]Sync complete.[/bold green]")

@app.command()
def query(prompt: str = typer.Argument(..., help="Query to run against the knowledge graph")):
    """
    Query the knowledge graph for context.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.vector_store import VectorStore
    from nervapack.graph.retrieval import GraphRetriever
    from nervapack.graph.token_meter import count_tokens, naive_rag_text, render_savings_panel
    from nervapack.graph.query_history import QueryHistory
    from rich.tree import Tree
    from rich.table import Table
    from rich import box
    from pathlib import Path
    from collections import defaultdict
    import time

    # Start timing
    start_time = time.time()

    console.print(f"[bold magenta]Query:[/bold magenta] \"{prompt}\"\n")

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]Failed to load graph:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

    intent = "semantic"
    direction = "both"
    start_nodes = []

    # Build a single name→[node_id] index in one pass (avoids two O(N) scans)
    name_index: dict = {}
    for n, d in graph.nodes(data=True):
        nm = d.get("name")
        if nm:
            name_index.setdefault(nm, []).append(n)

    # 1. Check for impact intent
    prompt_lower = prompt.lower()
    if prompt_lower.startswith("what breaks if i change ") or "impact of" in prompt_lower:
        intent = "impact"
        direction = "reverse"
        target = prompt.split()[-1].strip("?")
        matching_nodes = name_index.get(target, [])
        if matching_nodes:
            start_nodes = matching_nodes

    # 2. Check for exact symbol match
    if not start_nodes and intent != "impact":
        matching_nodes = name_index.get(prompt, [])
        if matching_nodes:
            intent = "exact"
            start_nodes = matching_nodes
            
    # 3. Fallback to vector search
    if not start_nodes:
        try:
            vstore = VectorStore()
            results = vstore.search(prompt, n_results=3)
            if results and results['ids'] and len(results['ids']) > 0:
                start_nodes = results['ids'][0]
        except Exception as e:
            console.print(f"[bold red]Failed to query vector store:[/bold red] {e}")
            raise typer.Exit(1)

    if not start_nodes:
        console.print("No relevant nodes found in graph or vector search.")
        raise typer.Exit(0)

    console.print(f"[bold cyan]Query Router:[/bold cyan] Intent: [yellow]{intent}[/yellow], Direction: [yellow]{direction}[/yellow]")
    if intent in ["exact", "impact"] and start_nodes == matching_nodes:
        console.print(f"[bold cyan]Exact Match:[/bold cyan] Found {len(start_nodes)} seed nodes bypassing vector search\n")
    else:
        console.print(f"[bold cyan]Vector Search:[/bold cyan] Found {len(start_nodes)} seed nodes\n")

    # Display seed nodes in a table
    seed_table = Table(box=box.MINIMAL, show_header=True, header_style="bold cyan")
    seed_table.add_column("#", style="dim", width=3)
    seed_table.add_column("Node Type", style="cyan")
    seed_table.add_column("Name/File", style="white")

    from rich.markup import escape
    for i, node_id in enumerate(start_nodes[:5], 1):  # Show max 5
        node_data = graph.nodes.get(node_id, {})
        node_type = node_data.get("type", "unknown")
        name = node_data.get("name") or Path(node_data.get("file_path", node_id)).name
        seed_table.add_row(str(i), node_type, escape(name))

    if len(start_nodes) > 5:
        seed_table.add_row("...", "...", f"and {len(start_nodes) - 5} more")

    console.print(seed_table)
    console.print()

    # Perform graph traversal
    console.print(f"[bold cyan]Graph Traversal:[/bold cyan] Expanding with max_hops=1, direction={direction}\n")
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=1, direction=direction)

    # Get traversal metadata
    metadata = retriever.last_metadata
    if metadata:
        console.print(f"  [dim]Seed nodes:[/dim] {len(metadata.seed_nodes)}")
        console.print(f"  [dim]Expanded nodes:[/dim] {len(metadata.expanded_nodes)}")
        console.print(f"  [dim]Total retrieved:[/dim] {metadata.total_nodes}")
        console.print(f"  [dim]Edges followed:[/dim] {len(metadata.edges_followed)}")
        console.print(f"  [dim]Traversal depth:[/dim] {metadata.traversal_depth}\n")

        # Visualize the retrieved subgraph structure
        console.print("[bold cyan]Retrieved Subgraph Structure:[/bold cyan]\n")

        # Group by file
        file_groups = defaultdict(list)
        for node_id in subgraph.nodes():
            node_data = graph.nodes.get(node_id, {})
            if node_data.get("type") == "file":
                continue
            file_path = node_data.get("file_path", "unknown")
            file_groups[file_path].append((node_id, node_data))

        # Build tree visualization
        tree = Tree("📦 Retrieved Context", style="bold cyan")

        for file_path in sorted(file_groups.keys()):
            nodes = file_groups[file_path]
            file_name = Path(file_path).name
            file_branch = tree.add(f"📄 [cyan]{file_name}[/cyan] ({len(nodes)} entities)")

            from rich.markup import escape
            for node_id, node_data in nodes:
                node_type = node_data.get("type", "unknown")
                name = escape(node_data.get("name", "?"))
                is_seed = node_id in metadata.seed_nodes

                # Icon and color based on type
                icon = {"function": "⚡", "class": "🔷", "import": "📦", "markdown": "📝"}.get(node_type, "•")
                color = "yellow" if is_seed else "white"
                label = f"{icon} {name}"
                if is_seed:
                    label += " [yellow]\\[seed\\][/yellow]"

                entity_branch = file_branch.add(f"[{color}]{label}[/{color}]")

                # Show connected EXPLAINS edges
                for source, target, relation in metadata.edges_followed:
                    if target == node_id and relation == "EXPLAINS":
                        source_data = graph.nodes.get(source, {})
                        if source_data.get("type") == "markdown":
                            header = escape(source_data.get("header", "doc"))
                            entity_branch.add(f"[lavender]← EXPLAINS: {header}[/lavender]")

        console.print(tree)
        console.print()

    markdown_context = retriever.format_as_markdown(subgraph)

    try:
        from nervapack.memory.store import MemoryStore
        store = MemoryStore()
        memory_lines = ["\n# Relevant Memories\n"]
        memories_added = False
        source_files = retriever.get_source_files(subgraph)
        for file_path in source_files:
            touches = store.get_touches_for_file(file_path)
            if touches:
                memories_added = True
                memory_lines.append(f"## Memories touching `{file_path}`")
                for n in touches:
                    kind = n.get("kind", "node")
                    content = n.get("content", "")
                    conf = n.get("confidence", 1.0)
                    memory_lines.append(f"- [{kind}] ({conf:.0%}) {content}")
        
        if memories_added:
            markdown_context += "\n" + "\n".join(memory_lines) + "\n"
    except Exception:
        pass
    console.print("[bold cyan]" + "─" * 60 + "[/bold cyan]")
    console.print("[bold cyan]Retrieved Context (Markdown)[/bold cyan]")
    console.print("[bold cyan]" + "─" * 60 + "[/bold cyan]\n")
    console.print(markdown_context, markup=False)
    console.print("\n[bold cyan]" + "─" * 60 + "[/bold cyan]\n")

    # Token efficiency dashboard
    source_files = retriever.get_source_files(subgraph)
    np_tokens, exact = count_tokens(markdown_context)
    naive_text = naive_rag_text(source_files)
    naive_tokens, _ = count_tokens(naive_text)
    console.print(render_savings_panel(np_tokens, naive_tokens, exact, file_count=len(source_files)))

    # Calculate execution time
    execution_time_ms = (time.time() - start_time) * 1000

    # Save query to history
    try:
        history = QueryHistory()
        history.add_query(
            query=prompt,
            seed_nodes_count=len(metadata.seed_nodes) if metadata else len(start_nodes),
            expanded_nodes_count=len(metadata.expanded_nodes) if metadata else 0,
            total_nodes_retrieved=metadata.total_nodes if metadata else subgraph.number_of_nodes(),
            edges_followed=len(metadata.edges_followed) if metadata else 0,
            traversal_depth=metadata.traversal_depth if metadata else 1,
            nervapack_tokens=np_tokens,
            naive_tokens=naive_tokens,
            source_files_count=len(source_files),
            execution_time_ms=execution_time_ms,
        )
    except Exception as e:
        # Don't fail the query if history saving fails
        console.print(f"[dim yellow]Note: Failed to save query history: {e}[/dim yellow]")

    console.print("\n[dim]Query complete.[/dim]")


@app.command()
def visualize(
    output: str = typer.Option(".nervapack/graph.html", help="Output HTML file path"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
    enhanced: bool = typer.Option(False, "--enhanced", help="Enable enhanced features (search, community detection)"),
    communities: bool = typer.Option(False, "--communities", help="Enable community detection and color coding"),
    scope: str = typer.Option(None, "--scope", help="Only visualize the neighborhood around this file/name/node (e.g. a program name)"),
    hops: int = typer.Option(2, "--hops", help="Neighborhood depth when --scope is given (callers + callees)"),
):
    """
    Render the knowledge graph as an interactive HTML visualization.

    Use --scope to focus on one program and its N-hop neighborhood — the right
    way to navigate a large estate:

        nervapack visualize --scope PAYROLL --hops 2
    """
    import webbrowser
    import os
    from nervapack.graph.builder import GraphBuilder, scoped_subgraph

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]No graph found:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

    # Scope down to a program's neighborhood if requested.
    if scope:
        subgraph, seeds = scoped_subgraph(graph, scope, hops)
        if not seeds:
            console.print(f"[yellow]No nodes match '[cyan]{scope}[/cyan]'.[/yellow] "
                          "Try a program/copybook name, a file path, or part of a node ID.")
            raise typer.Exit(1)
        graph = subgraph
        console.print(
            f"[cyan]Scope:[/cyan] '{scope}' — {len(seeds)} seed(s), "
            f"{hops}-hop neighborhood (callers + callees)."
        )
        # Default the output name to the scope so scoped views don't clobber the full graph.
        if output == ".nervapack/graph.html":
            safe = "".join(c if c.isalnum() else "_" for c in scope)[:50]
            output = f".nervapack/scope_{safe}.html"

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    console.print(f"[bold blue]Rendering graph[/bold blue] ({node_count} nodes, {edge_count} edges)...")

    # Use enhanced visualizer if requested
    if enhanced or communities:
        from nervapack.graph.visualizer_v2 import export_html_enhanced
        console.print("[cyan]Using enhanced visualization with:[/cyan]")
        if enhanced:
            console.print("  ✓ Search functionality")
        if communities:
            console.print("  ✓ Community detection")

        export_html_enhanced(
            graph,
            output,
            enable_search=enhanced,
            enable_community_detection=communities,
            enable_minimap=False,
        )
    else:
        from nervapack.graph.visualizer import export_html
        cap_info = export_html(graph, output)
        if cap_info:
            console.print(
                f"[yellow]Large graph:[/yellow] showing the "
                f"{cap_info['shown_nodes']} most-connected nodes / "
                f"{cap_info['shown_edges']} edges "
                f"(of {cap_info['total_nodes']} nodes, {cap_info['total_edges']} edges). "
                f"Physics is disabled for speed."
            )
            console.print(
                "[dim]Tip: the full graph is still in .nervapack/graph.graphml. "
                "Use 'nervapack explore'/'query' to navigate the whole graph.[/dim]"
            )

    abs_path = os.path.abspath(output)
    console.print(f"[bold green]Visualization saved:[/bold green] {abs_path}")

    if not no_browser:
        webbrowser.open(f"file://{abs_path}")
        console.print("[dim]Opened in browser.[/dim]")

@app.command()
def explore(
    target: str = typer.Argument(..., help="File path, node name, or node type to explore"),
    hops: int = typer.Option(2, "--hops", "-h", help="Number of hops for neighborhood exploration"),
    output: str = typer.Option(None, help="Output HTML file path (default: .nervapack/explore_{target}.html)"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
):
    """
    Explore a focused subgraph around a specific file or node.

    Examples:
        nervapack explore src/graph/builder.py
        nervapack explore GraphBuilder --hops 2
        nervapack explore --type function --hops 1
    """
    import webbrowser
    import os
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.visualizer_v2 import export_html_enhanced
    from pathlib import Path

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]No graph found:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

    # Find matching nodes
    matching_nodes = []
    for node_id, data in graph.nodes(data=True):
        # Match by file path
        file_path = data.get("file_path") or data.get("path", "")
        if target in file_path:
            matching_nodes.append(node_id)
            continue

        # Match by node name
        name = data.get("name", "")
        if target.lower() in name.lower():
            matching_nodes.append(node_id)
            continue

        # Match by node ID
        if target in node_id:
            matching_nodes.append(node_id)

    if not matching_nodes:
        console.print(f"[yellow]No nodes found matching '[cyan]{target}[/cyan]'[/yellow]")
        console.print("\n[dim]Try:[/dim]")
        console.print("  [dim]- A file path: [cyan]src/graph/builder.py[/cyan][/dim]")
        console.print("  [dim]- A class/function name: [cyan]GraphBuilder[/cyan][/dim]")
        console.print("  [dim]- Part of a node ID[/dim]")
        raise typer.Exit(1)

    console.print(f"[cyan]Found {len(matching_nodes)} matching node(s)[/cyan]")

    # Show matches if multiple
    if len(matching_nodes) > 1:
        console.print("\n[bold]Matching nodes:[/bold]")
        for i, node_id in enumerate(matching_nodes[:10], 1):
            node_data = graph.nodes[node_id]
            node_type = node_data.get("type", "unknown")
            name = node_data.get("name") or Path(node_data.get("file_path", node_id)).name
            console.print(f"  {i}. [{node_type}] {name}")
        if len(matching_nodes) > 10:
            console.print(f"  ... and {len(matching_nodes) - 10} more")

    # Extract ego network (N-hop neighborhood)
    console.print(f"\n[cyan]Extracting {hops}-hop neighborhood...[/cyan]")

    from collections import deque as _deque
    all_neighbors = set(matching_nodes)
    for seed_node in matching_nodes:
        visited: set = set()
        bfs_queue: _deque = _deque([(seed_node, 0)])

        while bfs_queue:
            current, depth = bfs_queue.popleft()
            if current in visited or depth > hops:
                continue

            visited.add(current)
            all_neighbors.add(current)

            if depth < hops:
                for neighbor in graph.successors(current):
                    if neighbor not in visited:
                        bfs_queue.append((neighbor, depth + 1))
                for neighbor in graph.predecessors(current):
                    if neighbor not in visited:
                        bfs_queue.append((neighbor, depth + 1))

    # Create subgraph
    subgraph = graph.subgraph(all_neighbors).copy()

    console.print(f"[green]Subgraph extracted:[/green] {subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges")

    # Determine output path
    if output is None:
        safe_target = target.replace("/", "_").replace("\\", "_").replace(".", "_")[:50]
        output = f".nervapack/explore_{safe_target}.html"

    # Export with enhanced features
    console.print(f"[bold blue]Rendering subgraph...[/bold blue]")
    export_html_enhanced(
        subgraph,
        output,
        enable_search=True,
        enable_community_detection=False,  # Usually not needed for small subgraphs
        enable_minimap=False,
    )

    abs_path = os.path.abspath(output)
    console.print(f"[bold green]Visualization saved:[/bold green] {abs_path}")

    if not no_browser:
        webbrowser.open(f"file://{abs_path}")
        console.print("[dim]Opened in browser.[/dim]")

@app.command()
def status(detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed analytics")):
    """
    Show the status of the local NervaPack graph.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.git.tracker import GitTracker
    from nervapack.graph.analytics import GraphAnalytics, format_percentage_bar, format_number
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.text import Text

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
        analytics = GraphAnalytics(graph)
    except Exception:
        console.print("[bold red]No graph found.[/bold red] Run [cyan]nervapack ingest[/cyan] first.")
        raise typer.Exit(1)

    if not detailed:
        # Simple status output (original behavior)
        console.print("[bold cyan]NervaPack Status:[/bold cyan]")
        console.print(f"- Graph loaded: [green]Yes[/green]")
        console.print(f"- Nodes: [cyan]{graph.number_of_nodes()}[/cyan]")
        console.print(f"- Edges: [cyan]{graph.number_of_edges()}[/cyan]")

        gitsync = GitTracker()
        if gitsync.repo:
            changed = gitsync.get_changed_files()
            console.print(f"- Git repo detected: [green]Yes[/green]")
            if changed:
                console.print(f"- Unsynced changes: [yellow]{len(changed)} file(s)[/yellow]")
                for f in changed[:5]:
                    console.print(f"  - {f}")
                if len(changed) > 5:
                    console.print("  - ...")
            else:
                console.print("- Unsynced changes: [green]None[/green]")
        else:
            console.print("- Git repo detected: [yellow]No[/yellow]")

        console.print("\n[dim]Use --detailed for comprehensive analytics[/dim]")
        return

    # Detailed status with rich formatting
    stats = analytics.get_summary_stats()
    health_score = stats["health_score"]

    # Health score visualization
    health_dots = "●" * (health_score // 10) + "○" * (10 - health_score // 10)
    health_color = "green" if health_score >= 70 else "yellow" if health_score >= 50 else "red"

    # Overview panel
    overview_table = Table(box=None, show_header=False, padding=(0, 2))
    overview_table.add_column("Metric", style="dim")
    overview_table.add_column("Value", style="bold cyan")

    node_counts = stats["node_counts"]
    overview_table.add_row("Nodes:", format_number(stats["total_nodes"]))
    overview_table.add_row("Edges:", format_number(stats["total_edges"]))
    overview_table.add_row("Files:", format_number(node_counts.get("file", 0)))
    overview_table.add_row("Functions:", format_number(node_counts.get("function", 0)))
    overview_table.add_row("Classes:", format_number(node_counts.get("class", 0)))
    overview_table.add_row("Imports:", format_number(node_counts.get("import", 0)))

    edge_counts = stats["edge_counts"]
    overview_table.add_row("", "")  # Spacer
    overview_table.add_row("DEFINES edges:", format_number(edge_counts.get("DEFINES", 0)))
    overview_table.add_row("EXPLAINS edges:", format_number(edge_counts.get("EXPLAINS", 0)))

    # Language distribution
    lang_dist = stats["languages"]
    total_files = sum(lang_dist.values()) or 1
    lang_lines = []
    for lang, count in sorted(lang_dist.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_files * 100
        bar = format_percentage_bar(pct, width=16)
        lang_lines.append(f"  [cyan]{lang:12s}[/cyan] [{health_color}]{bar}[/{health_color}] {pct:5.1f}%  ({count} files)")

    # Documentation coverage
    doc_cov = stats["documentation_coverage"]
    doc_pct = doc_cov["percentage"]
    doc_bar = format_percentage_bar(doc_pct, width=16)
    doc_color = "green" if doc_pct >= 60 else "yellow" if doc_pct >= 30 else "red"

    # Most connected files
    most_connected = stats["most_connected"]
    conn_lines = []
    for i, (node_id, degree) in enumerate(most_connected, 1):
        display_name = analytics.get_file_display_name(node_id)
        conn_lines.append(f"  {i}. [cyan]{display_name:40s}[/cyan] ({degree} edges)")

    # Git sync status
    gitsync = GitTracker()
    git_status_line = ""
    if gitsync.repo:
        changed = gitsync.get_changed_files()
        if changed:
            git_status_line = f"[yellow]✗ {len(changed)} unsynced file(s)[/yellow]"
        else:
            git_status_line = "[green]✓ Graph is in sync[/green]"
    else:
        git_status_line = "[yellow]⚠ Not a git repository[/yellow]"

    # Build the main panel content
    content_lines = [
        f"[bold {health_color}]Graph Health Score: {health_score}/100[/bold {health_color}] {health_dots}\n",
        "[bold]📊 Overview[/bold]",
        overview_table,
        "",
        "[bold]📚 Language Distribution[/bold]",
        *lang_lines,
        "",
        f"[bold]📖 Documentation Coverage[/bold]",
        f"  [{doc_color}]{doc_bar}[/{doc_color}] {doc_pct:.1f}% ({doc_cov['documented']}/{doc_cov['total']} entities)",
        "",
        "[bold]🔗 Most Connected Files[/bold]",
        *conn_lines,
        "",
        f"[bold]🔄 Git Sync Status[/bold]",
        f"  {git_status_line}",
    ]

    from rich.console import Group
    panel = Panel(
        Group(*content_lines),
        title="[bold cyan] NervaPack Status [/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)

    # Show warnings if any
    if stats["orphaned_count"] > 0:
        console.print(f"\n[yellow]⚠ Warning: {stats['orphaned_count']} orphaned nodes detected (no connections)[/yellow]")

    if doc_pct < 30:
        console.print(f"\n[yellow]💡 Tip: Add more documentation to improve coverage ({doc_cov['total'] - doc_cov['documented']} entities undocumented)[/yellow]")

    if gitsync.repo and changed and len(changed) > 0:
        console.print(f"\n[yellow]💡 Tip: Run [cyan]nervapack sync[/cyan] to update the graph with {len(changed)} changed files[/yellow]")

@app.command()
def serve(
    port: int = typer.Option(8501, "--port", "-p", help="Port to run the dashboard on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
):
    """
    Launch the interactive web dashboard.
    """
    import subprocess
    import sys
    from pathlib import Path

    # Check if streamlit is installed
    try:
        import streamlit
    except ImportError:
        console.print("[bold red]Streamlit not installed.[/bold red]")
        console.print("\nInstall with: [cyan]pip install \"nervapack[dashboard]\"[/cyan]")
        console.print("Or: [cyan]pip install streamlit plotly[/cyan]")
        raise typer.Exit(1)

    # Get dashboard app path
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"

    if not dashboard_path.exists():
        console.print(f"[bold red]Dashboard app not found:[/bold red] {dashboard_path}")
        raise typer.Exit(1)

    console.print(f"[bold cyan]🚀 Launching NervaPack Dashboard...[/bold cyan]")
    console.print(f"[dim]Port: {port}[/dim]")
    console.print(f"[dim]URL: http://localhost:{port}[/dim]\n")

    # Build streamlit command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.port", str(port),
        "--server.headless", "true",
    ]

    if no_browser:
        cmd.append("--server.runOnSave")
        cmd.append("false")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Failed to start dashboard:[/bold red] {e}")
        raise typer.Exit(1)

@app.command()
def dependencies(
    file_path: Optional[str] = typer.Argument(None, help="Specific file to analyze (optional)"),
    output: str = typer.Option(".nervapack/dependencies.html", "--output", "-o", help="Output HTML file path"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
    show_cycles: bool = typer.Option(True, "--cycles", help="Highlight circular dependencies"),
    layers: bool = typer.Option(True, "--layers", help="Use hierarchical layout"),
):
    """
    Analyze and visualize import dependencies in the codebase.

    Detects circular dependencies and shows dependency metrics.
    """
    import webbrowser
    import os
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.dependency_analyzer import DependencyAnalyzer
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from pathlib import Path

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]No graph found:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

    console.print("[bold blue]Analyzing dependencies...[/bold blue]\n")

    analyzer = DependencyAnalyzer(graph)
    dep_graph = analyzer.build_dependency_graph()

    # If specific file requested, show its dependencies
    if file_path:
        if not dep_graph.has_node(file_path):
            console.print(f"[yellow]File not found in dependency graph:[/yellow] {file_path}")
            console.print("[dim]Available files:[/dim]")
            for node in list(dep_graph.nodes())[:10]:
                console.print(f"  - {node}")
            if dep_graph.number_of_nodes() > 10:
                console.print(f"  ... and {dep_graph.number_of_nodes() - 10} more")
            raise typer.Exit(1)

        imports, imported_by = analyzer.get_file_dependencies(file_path)

        console.print(f"[bold cyan]Dependencies for:[/bold cyan] {Path(file_path).name}\n")

        # Show imports
        if imports:
            console.print(f"[bold green]Imports ({len(imports)} files):[/bold green]")
            for imp in imports:
                console.print(f"  → {Path(imp).name}")
        else:
            console.print("[dim]No imports found[/dim]")

        console.print()

        # Show imported by
        if imported_by:
            console.print(f"[bold yellow]Imported by ({len(imported_by)} files):[/bold yellow]")
            for imp_by in imported_by:
                console.print(f"  ← {Path(imp_by).name}")
        else:
            console.print("[dim]Not imported by any files[/dim]")

        return

    # Show overall metrics
    metrics = analyzer.get_dependency_metrics()

    # Create metrics table
    metrics_table = Table(box=box.MINIMAL, show_header=False, padding=(0, 2))
    metrics_table.add_column("Metric", style="cyan", width=25)
    metrics_table.add_column("Value", style="bold white")

    metrics_table.add_row("Total Files", str(metrics["total_files"]))
    metrics_table.add_row("Total Dependencies", str(metrics["total_dependencies"]))
    metrics_table.add_row("Max Dependency Depth", str(metrics["max_depth"]))
    metrics_table.add_row("Orphan Files", str(len(metrics["orphan_files"])))

    panel = Panel(
        metrics_table,
        title="[bold cyan] Dependency Metrics [/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)

    # Detect circular dependencies
    cycles = analyzer.detect_circular_dependencies()

    if cycles:
        console.print(f"\n[bold red]⚠ Circular Dependencies Detected:[/bold red] {len(cycles)} cycle(s)\n")

        for i, cycle in enumerate(cycles[:5], 1):
            console.print(f"[yellow]Cycle {i}:[/yellow]")
            for j, file_path in enumerate(cycle):
                file_name = Path(file_path).name
                arrow = "  → " if j > 0 else "  "
                console.print(f"{arrow}[cyan]{file_name}[/cyan]")
            # Show the cycle completion
            console.print(f"  → [cyan]{Path(cycle[0]).name}[/cyan] (back to start)\n")

        if len(cycles) > 5:
            console.print(f"[dim]... and {len(cycles) - 5} more cycles (see visualization)[/dim]\n")
    else:
        console.print("\n[bold green]✓ No circular dependencies detected[/bold green]\n")

    # Show most depended on files
    if metrics["most_depended_on"]:
        console.print("[bold cyan]Most Depended On Files:[/bold cyan]")
        dep_table = Table(box=box.MINIMAL, show_header=True, header_style="bold cyan")
        dep_table.add_column("#", style="dim", width=3)
        dep_table.add_column("File", style="white")
        dep_table.add_column("Depended By", justify="right", style="green")

        for i, (file_path, count) in enumerate(metrics["most_depended_on"][:10], 1):
            if count > 0:  # Only show files with dependencies
                file_name = Path(file_path).name
                dep_table.add_row(str(i), file_name, str(count))

        console.print(dep_table)
        console.print()

    # Show files with most dependencies
    if metrics["most_dependencies"]:
        console.print("[bold cyan]Files with Most Dependencies:[/bold cyan]")
        imp_table = Table(box=box.MINIMAL, show_header=True, header_style="bold cyan")
        imp_table.add_column("#", style="dim", width=3)
        imp_table.add_column("File", style="white")
        imp_table.add_column("Imports", justify="right", style="yellow")

        for i, (file_path, count) in enumerate(metrics["most_dependencies"][:10], 1):
            if count > 0:  # Only show files with dependencies
                file_name = Path(file_path).name
                imp_table.add_row(str(i), file_name, str(count))

        console.print(imp_table)
        console.print()

    # Generate visualization
    console.print(f"[bold blue]Generating dependency visualization...[/bold blue]")

    # Update metrics with actual cycle count
    analyzer.export_dependency_graph_html(
        output,
        enable_layers=layers,
        highlight_cycles=show_cycles,
    )

    abs_path = os.path.abspath(output)
    console.print(f"[bold green]Visualization saved:[/bold green] {abs_path}")

    if not no_browser:
        webbrowser.open(f"file://{abs_path}")
        console.print("[dim]Opened in browser.[/dim]")

    # Tips
    console.print()
    console.print("[dim]💡 Tips:[/dim]")
    console.print("[dim]  - Use [cyan]nervapack dependencies <file>[/cyan] to see specific file dependencies[/dim]")
    if cycles:
        console.print("[dim]  - Circular dependencies can make code harder to maintain and test[/dim]")
    if metrics["orphan_files"]:
        console.print(f"[dim]  - {len(metrics['orphan_files'])} orphan file(s) have no dependencies (check if intended)[/dim]")

@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent queries to show"),
    stats: bool = typer.Option(False, "--stats", help="Show aggregate statistics"),
    clear: bool = typer.Option(False, "--clear", help="Clear all query history"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show NervaPack and naive token counts per query"),
):
    """
    View query history and analytics.
    """
    from nervapack.graph.query_history import QueryHistory
    from nervapack.graph.analytics import format_number
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from datetime import datetime

    history_manager = QueryHistory()

    # Handle clear command
    if clear:
        confirm = typer.confirm("Are you sure you want to clear all query history?")
        if confirm:
            history_manager.clear_history()
            console.print("[green]Query history cleared.[/green]")
        else:
            console.print("[yellow]Clear cancelled.[/yellow]")
        return

    # Show statistics
    if stats:
        console.print("[bold cyan]Query History Statistics[/bold cyan]\n")

        stats_data = history_manager.get_statistics()

        if stats_data["total_queries"] == 0:
            console.print("[yellow]No query history available yet.[/yellow]")
            console.print("[dim]Run some queries with [cyan]nervapack query[/cyan] to build history.[/dim]")
            return

        # Create stats table
        stats_table = Table(box=box.MINIMAL, show_header=False, padding=(0, 2))
        stats_table.add_column("Metric", style="cyan", width=30)
        stats_table.add_column("Value", style="bold white")

        stats_table.add_row("Total Queries", format_number(stats_data["total_queries"]))
        stats_table.add_row("Avg Token Savings", f"{stats_data['avg_token_savings_pct']:.1f}%")
        stats_table.add_row("Total Tokens Saved", format_number(stats_data["total_tokens_saved"]))
        stats_table.add_row("Avg Execution Time", f"{stats_data['avg_execution_time_ms']:.0f}ms")
        stats_table.add_row("Avg Nodes Retrieved", f"{stats_data['avg_nodes_retrieved']:.1f}")
        stats_table.add_row("", "")  # Spacer
        stats_table.add_row("Total Cost Saved (GPT-4o)", f"${stats_data['total_cost_saved_gpt4']:.4f}")
        stats_table.add_row("Total Cost Saved (Claude Sonnet)", f"${stats_data['total_cost_saved_sonnet']:.4f}")

        panel = Panel(
            stats_table,
            title="[bold cyan] Query Analytics [/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)

        # Show most common query topics
        if stats_data["most_common_words"]:
            console.print("\n[bold cyan]Most Queried Topics:[/bold cyan]")
            topic_table = Table(box=box.MINIMAL, show_header=True, header_style="bold cyan")
            topic_table.add_column("Word", style="white")
            topic_table.add_column("Count", justify="right", style="cyan")

            for word, count in stats_data["most_common_words"][:10]:
                topic_table.add_row(word, str(count))

            console.print(topic_table)

        return

    # Show recent queries
    queries = history_manager.get_recent_queries(limit=limit)

    if not queries:
        console.print("[yellow]No query history available yet.[/yellow]")
        console.print("[dim]Run queries with [cyan]nervapack query \"your question\"[/cyan] to build history.[/dim]")
        console.print("[dim]Use [cyan]nervapack history --stats[/cyan] to see aggregate statistics.[/dim]")
        return

    console.print(f"[bold cyan]Recent Queries[/bold cyan] (showing last {len(queries)})\n")

    # Create history table
    history_table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=True, header_style="bold cyan")
    history_table.add_column("#", style="dim", width=3)
    history_table.add_column("Time", style="dim", width=16, no_wrap=True)
    history_table.add_column("Query", style="white", width=22 if verbose else None, max_width=22 if verbose else 50, no_wrap=verbose)
    history_table.add_column("Nodes", justify="right", style="cyan", width=6)
    history_table.add_column("Savings", justify="right", style="green", width=8)
    history_table.add_column("Elapsed", justify="right", style="yellow", width=8)
    if verbose:
        history_table.add_column("NP Tokens", justify="right", style="green", width=10)
        history_table.add_column("Naive Tokens", justify="right", style="red", width=13)

    for i, query in enumerate(queries, 1):
        # Format timestamp
        try:
            dt = datetime.fromisoformat(query.timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = query.timestamp[:16]

        # Truncate long queries
        query_text = query.query
        if len(query_text) > 47:
            query_text = query_text[:44] + "..."

        # Format savings percentage
        savings_str = f"{query.token_savings_pct:.1f}%"

        # Format execution time
        if query.execution_time_ms < 1000:
            time_str_exec = f"{query.execution_time_ms:.0f}ms"
        else:
            time_str_exec = f"{query.execution_time_ms/1000:.1f}s"

        row = [
            str(i),
            time_str,
            query_text,
            str(query.total_nodes_retrieved),
            savings_str,
            time_str_exec,
        ]
        if verbose:
            row.append(f"{query.nervapack_tokens:,}")
            row.append(f"{query.naive_tokens:,}")
        history_table.add_row(*row)

    console.print(history_table)

    # Summary stats
    total_savings = sum(q.naive_tokens - q.nervapack_tokens for q in queries)
    avg_savings_pct = sum(q.token_savings_pct for q in queries) / len(queries)

    console.print(f"\n[dim]Showing {len(queries)} most recent queries[/dim]")
    console.print(f"Average token savings: [green]{avg_savings_pct:.1f}%[/green]")
    console.print(f"Total tokens saved: [green]{format_number(total_savings)}[/green]")
    console.print(f"\n[dim]Use [cyan]--limit N[/cyan] to show more queries or [cyan]--stats[/cyan] for detailed analytics.[/dim]")

@app.command()
def savings(
    json_out: bool = typer.Option(False, "--json", help="Output as JSON (for badges, scripts, READMEs)"),
):
    """
    Show a one-screen summary of cumulative token savings across all queries.

    Compares NervaPack's focused context against naive RAG (full file dump)
    and shows total tokens saved, average reduction %, and cost impact.
    """
    import json as _json
    from nervapack.graph.query_history import QueryHistory
    from nervapack.graph.analytics import format_number
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.text import Text
    from rich.console import Group
    from rich.rule import Rule

    history_manager = QueryHistory()
    stats = history_manager.get_statistics()

    if stats["total_queries"] == 0:
        console.print("[yellow]No query history yet.[/yellow]")
        console.print("[dim]Run [cyan]nervapack query \"your question\"[/cyan] first to start tracking savings.[/dim]")
        return

    if json_out:
        total_np = sum(
            q.nervapack_tokens for q in history_manager.get_all_queries()
        )
        total_naive = sum(
            q.naive_tokens for q in history_manager.get_all_queries()
        )
        out = {
            "total_queries": stats["total_queries"],
            "avg_token_reduction_pct": round(stats["avg_token_savings_pct"], 1),
            "total_tokens_saved": stats["total_tokens_saved"],
            "total_nervapack_tokens": total_np,
            "total_naive_tokens": total_naive,
            "cost_saved_gpt4_usd": round(stats["total_cost_saved_gpt4"], 4),
            "cost_saved_sonnet_usd": round(stats["total_cost_saved_sonnet"], 4),
            "top_topics": [w for w, _ in stats["most_common_words"][:5]],
        }
        console.print(_json.dumps(out, indent=2))
        return

    # Compute totals for display
    all_queries = history_manager.get_all_queries()
    total_np = sum(q.nervapack_tokens for q in all_queries)
    total_naive = sum(q.naive_tokens for q in all_queries)
    pct_of_naive = (total_np / max(total_naive, 1)) * 100
    topics = ", ".join(w for w, _ in stats["most_common_words"][:5]) or "—"

    # Build metrics table
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="cyan", min_width=34)
    table.add_column("Value", style="bold white", justify="right")

    table.add_row("Total queries run", format_number(stats["total_queries"]))
    table.add_row("Average token reduction", f"[green]{stats['avg_token_savings_pct']:.1f}%[/green]")
    table.add_row("Total tokens saved", f"[green]{format_number(stats['total_tokens_saved'])}[/green]")
    table.add_row("", "")
    table.add_row("Naive RAG would have used", f"[red]{format_number(total_naive)}[/red] tokens")
    table.add_row(
        "NervaPack used",
        f"[green]{format_number(total_np)}[/green] tokens  [dim]({pct_of_naive:.1f}% of naive)[/dim]",
    )
    table.add_row("", "")
    table.add_row(
        "Cost saved  GPT-4o   ($2.50/1M)",
        f"[yellow]${stats['total_cost_saved_gpt4']:.4f}[/yellow]",
    )
    table.add_row(
        "Cost saved  Sonnet   ($3.00/1M)",
        f"[yellow]${stats['total_cost_saved_sonnet']:.4f}[/yellow]",
    )
    table.add_row("", "")
    table.add_row("Top query topics", f"[dim]{topics}[/dim]")

    footer = Text.from_markup(
        f"\n  [dim]Run [cyan]nervapack history --stats[/cyan] for per-query breakdown  "
        f"·  [cyan]nervapack savings --json[/cyan] for machine-readable output[/dim]"
    )

    content = Group(table, Rule(style="dim"), footer)
    console.print(Panel(
        content,
        title="[bold cyan] NervaPack Token Savings Summary [/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    ))


@app.command()
def hotspots(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of files to show"),
    since: str = typer.Option(None, "--since", help="Limit to commits since this date/expression (e.g. '6 months ago', '2024-01-01')"),
    ext: List[str] = typer.Option(None, "--ext", help="Filter to file extension(s), e.g. --ext .py --ext .ts"),
    churn: bool = typer.Option(False, "--churn", help="Sort by total lines changed instead of commit count"),
):
    """
    Show code hotspots — files changed most frequently in git history.
    """
    from nervapack.graph.hotspots import HotspotAnalyzer
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    analyzer = HotspotAnalyzer()

    if not analyzer.is_git_repo():
        console.print("[bold red]Not a git repository.[/bold red]")
        raise typer.Exit(1)

    extensions = list(ext) if ext else None
    hotspot_list = analyzer.get_hotspots(limit=limit, since=since, extensions=extensions)

    if not hotspot_list:
        console.print("[yellow]No git history found (or no files match the filter).[/yellow]")
        return

    if churn:
        hotspot_list.sort(key=lambda h: h.churn_score, reverse=True)

    # Header
    since_label = f" since [cyan]{since}[/cyan]" if since else ""
    ext_label = f" · extensions: [cyan]{', '.join(extensions)}[/cyan]" if extensions else ""
    console.print(f"\n[bold cyan]Code Hotspots[/bold cyan]{since_label}{ext_label}\n")

    table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="white", min_width=30)
    table.add_column("Changes", justify="right", style="bold red", width=9)
    table.add_column("+Lines", justify="right", style="green", width=8)
    table.add_column("-Lines", justify="right", style="red", width=8)
    table.add_column("Churn", justify="right", style="yellow", width=8)
    table.add_column("Heat", style="magenta", width=12)

    max_changes = hotspot_list[0].change_count if hotspot_list else 1

    for i, h in enumerate(hotspot_list, 1):
        heat_ratio = h.change_count / max_changes
        heat_bars = int(heat_ratio * 8)
        heat_str = "█" * heat_bars + "░" * (8 - heat_bars)

        table.add_row(
            str(i),
            h.file_path,
            str(h.change_count),
            f"+{h.insertions:,}",
            f"-{h.deletions:,}",
            f"{h.churn_score:,.0f}",
            heat_str,
        )

    console.print(table)

    total_changes = sum(h.change_count for h in hotspot_list)
    console.print(f"\n[dim]Top {len(hotspot_list)} files · {total_changes:,} total commits touching these files")
    if not since:
        console.print("[dim]Tip: use [cyan]--since '6 months ago'[/cyan] to focus on recent activity[/dim]")

@app.command()
def enrich(
    path: str = typer.Argument(".", help="Path to the repository to enrich"),
    llm: str = typer.Option(None, help="LLM provider (ollama, claude, openai, mcp). Auto-detects if not specified."),
    model: str = typer.Option(None, help="Model name (provider-specific)"),
    api_key: str = typer.Option(None, help="API key for cloud providers"),
):
    """
    Add semantic doc-to-code edges to an existing NervaPack graph.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.llm.factory import get_llm_provider
    from rich.prompt import Confirm
    import os

    console.print(f"[bold blue]Enriching repository at {path}...[/bold blue]")

    builder = GraphBuilder()
    try:
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]Failed to load graph. Did you run 'nervapack ingest' first?[/bold red]")
        raise typer.Exit(1)

    # Reconstruct AST docs and Markdown chunks from the graph
    ast_docs = []
    md_chunks = []

    for node_id, data in graph.nodes(data=True):
        if data.get("type") == "markdown":
            md_chunks.append({
                "node_id": node_id,
                "header": data.get("header", ""),
                "content": data.get("content", ""),
                "file_path": data.get("file_path", "")
            })
        elif data.get("type") in ["class", "function", "import"]:
            ast_docs.append({
                "node_id": node_id,
                "summary": f"This is a {data.get('type')} named {data.get('name')} in {data.get('file_path')}. Code:\n{data.get('content')}"
            })

    if not md_chunks:
        console.print("[bold green]No markdown documentation found in the graph. Nothing to enrich.[/bold green]")
        raise typer.Exit(0)

    if not ast_docs:
        console.print("[bold green]No code entities found in the graph. Nothing to enrich.[/bold green]")
        raise typer.Exit(0)

    console.print("\n[bold cyan]Setting up LLM provider...[/bold cyan]")
    provider = None
    try:
        provider = get_llm_provider(provider=llm, model=model, api_key=api_key)
        provider_name = provider.get_provider_name()
        
        if not provider.validate_config():
            raise ValueError(f"Provider {provider_name} configuration invalid")
        
        console.print(f"Using LLM provider: [green]{provider_name}[/green]")

        estimated_cost = provider.estimate_cost(len(md_chunks))
        if estimated_cost is not None and estimated_cost > 0:
            console.print(f"\n[bold yellow]💰 Cost Estimate[/bold yellow]")
            console.print(f"Provider: {provider_name}")
            console.print(f"Markdown chunks to bind: {len(md_chunks)}")
            console.print(f"Estimated cost: [yellow]${estimated_cost:.2f}[/yellow]")
            if not Confirm.ask("Proceed with cloud LLM binding?"):
                console.print("[yellow]Enrichment cancelled.[/yellow]")
                raise typer.Exit(0)

    except Exception as e:
        console.print(f"[bold red]LLM provider error:[/bold red] {e}")
        console.print("[bold yellow]Please ensure your LLM (e.g., Ollama) is running to use 'enrich'.[/bold yellow]")
        raise typer.Exit(1)

    console.print(f"Adding semantic edges for {len(md_chunks)} markdown chunks...")
    added_edges = 0
    for chunk in md_chunks:
        matched_ids = provider.bind_docs_to_ast(chunk['content'], ast_docs)
        for matched_id in matched_ids:
            if graph.has_node(matched_id) and not graph.has_edge(chunk["node_id"], matched_id):
                graph.add_edge(chunk["node_id"], matched_id, relation="EXPLAINS")
                added_edges += 1

    builder.save_graph()
    console.print(f"[bold green]Enrichment complete. Added {added_edges} semantic edges.[/bold green]")

@app.command()
def doctor():
    """
    Check system configuration and NervaPack dependencies.
    """
    import sys
    import importlib
    import os
    
    console.print("[bold blue]NervaPack System Check[/bold blue]\n")
    
    issues = []
    
    # 1. Check Python version
    py_version = sys.version_info
    py_ver_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    if py_version >= (3, 9):
        console.print(f"[green]✓ Python version:[/green] {py_ver_str}")
    else:
        console.print(f"[red]✗ Python version:[/red] {py_ver_str} (Requires >= 3.9)")
        issues.append("Upgrade Python to 3.9 or higher.")
        
    # 2. Check core Tree-sitter grammars
    grammars = ["tree_sitter_python", "tree_sitter_javascript", "tree_sitter_typescript"]
    missing_grammars = []
    for g in grammars:
        try:
            importlib.import_module(g)
        except ImportError:
            missing_grammars.append(g)
            
    if not missing_grammars:
        console.print("[green]✓ Tree-sitter grammars:[/green] All core grammars installed")
    else:
        pkg_names = [g.replace('_', '-') for g in missing_grammars]
        console.print(f"[red]✗ Tree-sitter grammars missing:[/red] {', '.join(pkg_names)}")
        issues.append(f"Run: pip install {' '.join(pkg_names)}")
        
    # 3. Check embedding backend / Ollama
    embed_backend = os.getenv("NERVAPACK_EMBEDDINGS", "onnx").lower()
    console.print(f"[green]✓ Embedding backend configured as:[/green] {embed_backend}")
    if embed_backend == "ollama":
        import requests
        try:
            r = requests.get("http://localhost:11434/")
            if r.status_code == 200:
                console.print("[green]✓ Ollama instance:[/green] Reachable on localhost:11434")
            else:
                console.print("[yellow]⚠ Ollama instance:[/yellow] Returned non-200 status")
        except Exception:
            console.print("[yellow]⚠ Ollama instance:[/yellow] Cannot connect to http://localhost:11434/")
            issues.append("Start your Ollama server by running: ollama serve")
            
    # 4. Check MCP config
    mcp_paths = [
        os.path.join(os.getcwd(), ".mcp.json"),
        os.path.expanduser("~/.claude_code/mcp.json")
    ]
    mcp_found = any(os.path.exists(p) for p in mcp_paths)
    if mcp_found:
        console.print("[green]✓ MCP config:[/green] Found")
    else:
        console.print("[yellow]⚠ MCP config:[/yellow] Not found (Optional)")
        issues.append("If using Claude Code, configure MCP by running: claude mcp add nervapack python -m nervapack mcp")
        
    if issues:
        console.print("\n[bold yellow]Recommended Fixes:[/bold yellow]")
        for i, issue in enumerate(issues, 1):
            console.print(f"  {i}. {issue}")
    else:
        console.print("\n[bold green]All systems go! NervaPack is ready.[/bold green]")


@app.command()
def clean(
    vectors: bool = typer.Option(False, "--vectors", help="Wipe the ChromaDB vector store only"),
    graph: bool = typer.Option(False, "--graph", help="Delete the GraphML file only"),
    history: bool = typer.Option(False, "--history", help="Clear query history only"),
    all_data: bool = typer.Option(False, "--all", help="Wipe everything: vectors + graph + history (keeps memory.db)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    path: str = typer.Option(".", help="Project root (where .nervapack/ lives)"),
):
    """
    Remove ingested graph data so you can start fresh.

    Use this when you have duplicate vectors, a corrupt graph, or wrong data ingested.

    Examples:
      nervapack clean --vectors          # Clear duplicate ChromaDB embeddings only
      nervapack clean --graph            # Delete graph.graphml only
      nervapack clean --all              # Full wipe (vectors + graph + history)
      nervapack clean --all --yes        # Same, skip confirmation
    """
    import os
    import shutil
    from rich.prompt import Confirm
    from rich.table import Table
    from rich import box

    nervapack_dir = os.path.join(path, ".nervapack")

    chroma_path   = os.path.join(nervapack_dir, "chroma_db")
    graphml_path  = os.path.join(nervapack_dir, "graph.graphml")
    history_path  = os.path.join(nervapack_dir, "query_history.jsonl")
    gh_path       = os.path.join(nervapack_dir, "graph_history.jsonl")

    if not any([vectors, graph, history, all_data]):
        console.print("[bold yellow]Nothing selected.[/bold yellow] Specify what to clean:\n")
        console.print("  [cyan]--vectors[/cyan]   Wipe ChromaDB vector store (fixes duplicate embeddings)")
        console.print("  [cyan]--graph[/cyan]     Delete graph.graphml (fixes corrupt/wrong graph)")
        console.print("  [cyan]--history[/cyan]   Clear query + graph history logs")
        console.print("  [cyan]--all[/cyan]       Everything above (full reset, keeps memory.db)\n")
        console.print("Add [cyan]--yes[/cyan] to skip the confirmation prompt.")
        raise typer.Exit(0)

    # Determine what will actually be touched
    targets: list[tuple[str, str, str]] = []

    if vectors or all_data:
        if os.path.isdir(chroma_path):
            size = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, files in os.walk(chroma_path)
                for f in files
            )
            targets.append(("ChromaDB vector store", chroma_path, f"{size / 1_048_576:.1f} MB"))
        else:
            console.print("[dim]ChromaDB directory not found — already clean.[/dim]")

    if graph or all_data:
        if os.path.exists(graphml_path):
            size = os.path.getsize(graphml_path)
            targets.append(("Graph (graph.graphml)", graphml_path, f"{size / 1_048_576:.1f} MB"))
        else:
            console.print("[dim]graph.graphml not found — already clean.[/dim]")

    if history or all_data:
        for hpath, label in [(history_path, "Query history"), (gh_path, "Graph history")]:
            if os.path.exists(hpath):
                size = os.path.getsize(hpath)
                targets.append((label, hpath, f"{size / 1024:.1f} KB"))

    if not targets:
        console.print("[bold green]Nothing to clean — everything is already empty.[/bold green]")
        raise typer.Exit(0)

    # Show what will be deleted
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold red")
    table.add_column("What", style="white")
    table.add_column("Path", style="dim")
    table.add_column("Size", justify="right", style="yellow")
    for label, tpath, size_str in targets:
        table.add_row(label, tpath, size_str)

    console.print("\n[bold red]The following will be permanently deleted:[/bold red]")
    console.print(table)
    console.print("[dim]Note: memory.db (agent memory) is never touched by clean.[/dim]\n")

    if not yes:
        confirmed = Confirm.ask("[bold red]Proceed?[/bold red]")
        if not confirmed:
            console.print("[yellow]Aborted. Nothing deleted.[/yellow]")
            raise typer.Exit(0)

    # Execute deletions
    for label, tpath, _ in targets:
        try:
            if os.path.isdir(tpath):
                shutil.rmtree(tpath)
            else:
                os.remove(tpath)
            console.print(f"[green]✓ Deleted:[/green] {label}")
        except Exception as e:
            console.print(f"[red]✗ Failed to delete {label}:[/red] {e}")

    console.print("\n[bold green]Clean complete.[/bold green] Run [cyan]nervapack ingest .[/cyan] to rebuild.")


if __name__ == "__main__":
    app()
