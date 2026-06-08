import typer
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

    console.print(f"[bold magenta]Running query:[/bold magenta] {prompt}")

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

    console.print(f"Found {len(start_nodes)} seed nodes. Traversing graph...")
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=1)

    markdown_context = retriever.format_as_markdown(subgraph)

    console.print("\n[bold cyan]--- Retrieved Context ---[/bold cyan]\n")
    console.print(markdown_context)
    console.print("\n[bold cyan]--- End Context ---[/bold cyan]\n")

    # Token efficiency dashboard
    source_files = retriever.get_source_files(subgraph)
    np_tokens, exact = count_tokens(markdown_context)
    naive_text = naive_rag_text(source_files)
    naive_tokens, _ = count_tokens(naive_text)
    console.print(render_savings_panel(np_tokens, naive_tokens, exact, file_count=len(source_files)))

    console.print("Query complete.")


@app.command()
def visualize(
    output: str = typer.Option(".nervapack/graph.html", help="Output HTML file path"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
):
    """
    Render the knowledge graph as an interactive HTML visualization.
    """
    import webbrowser
    import os
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.visualizer import export_html

    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
    except Exception as e:
        console.print(f"[bold red]No graph found:[/bold red] {e}. Run 'nervapack ingest' first.")
        raise typer.Exit(1)

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    console.print(f"[bold blue]Rendering graph[/bold blue] ({node_count} nodes, {edge_count} edges)...")

    export_html(graph, output)
    abs_path = os.path.abspath(output)
    console.print(f"[bold green]Visualization saved:[/bold green] {abs_path}")

    if not no_browser:
        webbrowser.open(f"file://{abs_path}")
        console.print("[dim]Opened in browser.[/dim]")

@app.command()
def status():
    """
    Show the status of the local NervaPack graph.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.git.tracker import GitTracker
    
    console.print("[bold cyan]NervaPack Status:[/bold cyan]")
    
    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
        console.print(f"- Graph loaded: [green]Yes[/green]")
        console.print(f"- Nodes: [cyan]{graph.number_of_nodes()}[/cyan]")
        console.print(f"- Edges: [cyan]{graph.number_of_edges()}[/cyan]")
    except Exception:
        console.print("- Graph loaded: [red]No (Run 'nervapack ingest')[/red]")

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
        
    console.print("Status: OK")

if __name__ == "__main__":
    app()
