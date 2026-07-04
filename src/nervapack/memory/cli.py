"""CLI for nervapack.memory: init, stats, forget, export."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ImportError:
    raise ImportError("Run: pip install nervapack[memory]")

from .store import MemoryStore

app = typer.Typer(name="nervapack-memory", help="NervaPack agent memory CLI.")
console = Console()


@app.command("init")
def cmd_init(
    db: Optional[str] = typer.Option(None, "--db", help="Path to memory.db"),
) -> None:
    """Initialize the memory database (create schema if not exists)."""
    store = MemoryStore(db_path=db)
    store._get_conn()  # triggers schema application
    console.print(f"[green]✓[/green] Memory store initialised at {store.db_path}")


@app.command("stats")
def cmd_stats(
    db: Optional[str] = typer.Option(None, "--db", help="Path to memory.db"),
) -> None:
    """Show memory store statistics."""
    store = MemoryStore(db_path=db)
    s = store.stats()

    table = Table(title="Memory Stats")
    table.add_column("Kind", style="cyan")
    table.add_column("Count", justify="right")
    for kind, count in s["kind_counts"].items():
        table.add_row(kind, str(count))
    console.print(table)

    size_kb = s["db_size_bytes"] / 1024
    console.print(f"\nDB size: {size_kb:.1f} KB  |  Namespaces: {', '.join(s['namespaces'])}")

    if s["top_entities"]:
        console.print("\n[bold]Top entities by degree:[/bold]")
        for e in s["top_entities"][:5]:
            console.print(f"  [{e['id']}] {e['content']} (degree {e.get('degree', 0)})")


@app.command("forget")
def cmd_forget(
    node_id: Optional[str] = typer.Option(None, "--node-id", "-n"),
    entity: Optional[str] = typer.Option(None, "--entity", "-e"),
    before: Optional[str] = typer.Option(None, "--before", "-b", help="ISO-8601 timestamp"),
    purge: bool = typer.Option(False, "--purge", help="Hard-delete (irreversible)"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Tombstone or purge memory nodes."""
    store = MemoryStore(db_path=db)
    ids: list[str] = []

    if node_id:
        ids.append(node_id)
    if entity:
        from .resolve import _find_entity
        eid = _find_entity(store, entity)
        if eid:
            ids.extend(r["id"] for r in store.find_nodes(entity_id=eid))
    if before:
        ids.extend(r["id"] for r in store.find_nodes(before=before))

    ids = list(set(ids))
    if not ids:
        console.print("[yellow]No matching nodes found.[/yellow]")
        return

    if purge:
        count = store.purge(ids)
        console.print(f"[red]Hard-deleted {count} node(s).[/red]")
    else:
        count = store.tombstone(ids)
        console.print(f"[yellow]Tombstoned {count} node(s).[/yellow]")


@app.command("export")
def cmd_export(
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Output file (default stdout)"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Export all non-tombstoned nodes and edges as JSON."""
    store = MemoryStore(db_path=db)
    conn = store._get_conn()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM mem_nodes WHERE tombstoned = 0").fetchall()]
    edges = [dict(r) for r in conn.execute("SELECT * FROM mem_edges").fetchall()]
    dump = json.dumps({"nodes": nodes, "edges": edges}, indent=2)
    if out:
        Path(out).write_text(dump)
        console.print(f"[green]Exported to {out}[/green]")
    else:
        print(dump)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
