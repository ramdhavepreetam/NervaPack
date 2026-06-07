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
                "summary": f"This is a {e.type} named {e.name} in {e.file_path}. Code:\n{e.content}"
            })
        
        vstore.ingest_ast_entities(ast_docs)
        console.print("Vector Store ingestion complete.")
    except Exception as e:
        console.print(f"[bold yellow]Warning:[/bold yellow] Failed to ingest into Vector Store: {e}")

    console.print("[bold green]Ingestion complete.[/bold green]")

@app.command()
def query(prompt: str = typer.Argument(..., help="Query to run against the knowledge graph")):
    """
    Query the knowledge graph for context.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.vector_store import VectorStore
    from nervapack.graph.retrieval import GraphRetriever

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
    console.print("Query complete.")

@app.command()
def status():
    """
    Show the status of the local NervaPack graph.
    """
    from nervapack.graph.builder import GraphBuilder
    from nervapack.graph.sync import GitSync
    
    console.print("[bold cyan]NervaPack Status:[/bold cyan]")
    
    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
        console.print(f"- Graph loaded: [green]Yes[/green]")
        console.print(f"- Nodes: [cyan]{graph.number_of_nodes()}[/cyan]")
        console.print(f"- Edges: [cyan]{graph.number_of_edges()}[/cyan]")
    except Exception:
        console.print("- Graph loaded: [red]No (Run 'nervapack ingest')[/red]")

    gitsync = GitSync()
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
