import typer
from typing import Optional
from rich.console import Console

app = typer.Typer(help="NervaPack: Privacy-first, offline knowledge graph for developers.")
console = Console()

@app.command()
def init():
    """
    Initialize a NervaPack graph in the current directory.
    """
    console.print("[bold green]Initializing NervaPack graph...[/bold green]")
    # TODO: Implement initialization logic
    console.print("Initialization complete.")

@app.command()
def ingest(path: str = typer.Argument(".", help="Path to the repository to ingest")):
    """
    Ingest a repository, building the AST and Vector graph.
    """
    from nervapack.parser.ast_parser import scan_directory
    from nervapack.graph.builder import GraphBuilder

    console.print(f"[bold blue]Ingesting repository at {path}...[/bold blue]")
    
    console.print("Scanning directory for code entities...")
    entities = scan_directory(path)
    console.print(f"Found {len(entities)} AST entities.")

    console.print("Building deterministic Structural Graph...")
    builder = GraphBuilder()
    graph = builder.build_from_entities(entities)
    builder.save_graph()
    console.print(f"Graph saved with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    
    console.print("Ingesting AST nodes into Vector Store...")
    try:
        from nervapack.graph.vector_store import VectorStore
        vstore = VectorStore()
        
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
            
            # Add to graph and Bind with LLM
            from nervapack.llm.summarizer import LLMSummarizer
            llm = LLMSummarizer()
            
            console.print("Binding documentation to AST (this may take a while)...")
            for i, chunk in enumerate(md_chunks):
                md_node_id = f"md_{chunk['file_path']}_{i}"
                if not graph.has_node(md_node_id):
                    graph.add_node(md_node_id, type="markdown", header=chunk['header'], content=chunk['content'], file_path=chunk['file_path'])
                
                # Try to bind
                matched_ids = llm.bind_docs_to_ast(chunk['content'], ast_docs)
                for matched_id in matched_ids:
                    if graph.has_node(matched_id):
                        graph.add_edge(md_node_id, matched_id, relation="EXPLAINS")
            
            builder.save_graph()
            console.print("Semantic binding complete.")

    except Exception as e:
        console.print(f"[bold red]Error during ingestion:[/bold red] {e}")

    console.print("[bold green]Ingestion complete.[/bold green]")

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
    
    ast_docs = []
    
    # Pre-gather all existing ast_docs for LLM binding
    # We reconstruct a simple mock summary for existing nodes just for binding if needed.
    # In a real app, we'd pull these from the graph directly.
    for node, data in graph.nodes(data=True):
        if data.get("type") in ["class", "function", "import"]:
            ast_docs.append({
                "node_id": node,
                "summary": f"This is a {data.get('type')} named {data.get('name')} in {data.get('file_path')}. Code:\n{data.get('content')}"
            })

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
                
                # Add to vector store
                node_summary = {"node_id": entity_node_id, "summary": f"This is a {entity.type} named {entity.name} in {entity.file_path}. Code:\n{entity.content}", "file_path": entity.file_path}
                vstore.ingest_ast_entities([node_summary])
                ast_docs.append(node_summary)
                
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
                            graph.add_edge(md_node_id, matched_id, relation="EXPLAINS")
                            
            console.print(f"Updated Markdown for [cyan]{f}[/cyan]")
            
    builder.save_graph()
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

    try:
        vstore = VectorStore()
        results = vstore.search(prompt, n_results=3)
    except Exception as e:
        console.print(f"[bold red]Failed to query vector store:[/bold red] {e}")
        raise typer.Exit(1)

    start_nodes = []
    if results and results['ids'] and len(results['ids']) > 0:
        start_nodes = results['ids'][0]

    if not start_nodes:
        console.print("No relevant nodes found in vector search.")
        raise typer.Exit(0)

    console.print(f"[bold cyan]Vector Search:[/bold cyan] Found {len(start_nodes)} seed nodes\n")

    # Display seed nodes in a table
    seed_table = Table(box=box.MINIMAL, show_header=True, header_style="bold cyan")
    seed_table.add_column("#", style="dim", width=3)
    seed_table.add_column("Node Type", style="cyan")
    seed_table.add_column("Name/File", style="white")

    for i, node_id in enumerate(start_nodes[:5], 1):  # Show max 5
        node_data = graph.nodes.get(node_id, {})
        node_type = node_data.get("type", "unknown")
        name = node_data.get("name") or Path(node_data.get("file_path", node_id)).name
        seed_table.add_row(str(i), node_type, name)

    if len(start_nodes) > 5:
        seed_table.add_row("...", "...", f"and {len(start_nodes) - 5} more")

    console.print(seed_table)
    console.print()

    # Perform graph traversal
    console.print(f"[bold cyan]Graph Traversal:[/bold cyan] Expanding with max_hops=1\n")
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=1)

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

            for node_id, node_data in nodes:
                node_type = node_data.get("type", "unknown")
                name = node_data.get("name", "?")
                is_seed = node_id in metadata.seed_nodes

                # Icon and color based on type
                icon = {"function": "⚡", "class": "🔷", "import": "📦", "markdown": "📝"}.get(node_type, "•")
                color = "yellow" if is_seed else "white"
                label = f"{icon} {name}"
                if is_seed:
                    label += " [yellow][seed][/yellow]"

                entity_branch = file_branch.add(f"[{color}]{label}[/{color}]")

                # Show connected EXPLAINS edges
                for source, target, relation in metadata.edges_followed:
                    if target == node_id and relation == "EXPLAINS":
                        source_data = graph.nodes.get(source, {})
                        if source_data.get("type") == "markdown":
                            header = source_data.get("header", "doc")
                            entity_branch.add(f"[lavender]← EXPLAINS: {header}[/lavender]")

        console.print(tree)
        console.print()

    markdown_context = retriever.format_as_markdown(subgraph)

    console.print("[bold cyan]" + "─" * 60 + "[/bold cyan]")
    console.print("[bold cyan]Retrieved Context (Markdown)[/bold cyan]")
    console.print("[bold cyan]" + "─" * 60 + "[/bold cyan]\n")
    console.print(markdown_context)
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
):
    """
    Render the knowledge graph as an interactive HTML visualization.
    """
    import webbrowser
    import os
    from nervapack.graph.builder import GraphBuilder

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]No graph found:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

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
        export_html(graph, output)

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

    all_neighbors = set(matching_nodes)
    for seed_node in matching_nodes:
        # Use BFS to get N-hop neighborhood
        visited = set()
        queue = [(seed_node, 0)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > hops:
                continue

            visited.add(current)
            all_neighbors.add(current)

            if depth < hops:
                # Add successors and predecessors
                for neighbor in graph.successors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
                for neighbor in graph.predecessors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

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
    show_cycles: bool = typer.Option(True, "--cycles/--no-cycles", help="Highlight circular dependencies"),
    layers: bool = typer.Option(True, "--layers/--no-layers", help="Use hierarchical layout"),
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
    history_table.add_column("Time", style="dim", width=16)
    history_table.add_column("Query", style="white", max_width=50)
    history_table.add_column("Nodes", justify="right", style="cyan", width=6)
    history_table.add_column("Savings", justify="right", style="green", width=8)
    history_table.add_column("Time", justify="right", style="yellow", width=8)

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

        history_table.add_row(
            str(i),
            time_str,
            query_text,
            str(query.total_nodes_retrieved),
            savings_str,
            time_str_exec,
        )

    console.print(history_table)

    # Summary stats
    total_savings = sum(q.naive_tokens - q.nervapack_tokens for q in queries)
    avg_savings_pct = sum(q.token_savings_pct for q in queries) / len(queries)

    console.print(f"\n[dim]Showing {len(queries)} most recent queries")
    console.print(f"Average token savings: [green]{avg_savings_pct:.1f}%[/green]")
    console.print(f"Total tokens saved: [green]{format_number(total_savings)}[/green]")
    console.print(f"\nUse [cyan]--limit N[/cyan] to show more queries or [cyan]--stats[/cyan] for detailed analytics.[/dim]")

if __name__ == "__main__":
    app()
