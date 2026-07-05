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

from nervapack import __version__
from nervapack._update_check import start as _start_update_check
from .store import MemoryStore

app = typer.Typer(name="nervapack-memory", help="NervaPack agent memory CLI.", no_args_is_help=True)
console = Console()


@app.callback(invoke_without_command=True)
def _callback(ctx: typer.Context) -> None:
    """Run the update checker in the background on every CLI invocation."""
    _start_update_check(__version__)


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


@app.command("sessions")
def cmd_sessions(
    limit: int = typer.Option(50, "--limit", "-l", help="Max sessions to show"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """List all sessions, newest first."""
    store = MemoryStore(db_path=db)
    sessions = store.list_sessions(limit=limit)

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    from rich.table import Table
    table = Table(title=f"Sessions ({len(sessions)})")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Content", style="white")
    table.add_column("Recorded", style="cyan", width=19)
    table.add_column("Nodes", justify="right", style="green")
    table.add_column("Status", style="yellow")

    for s in sessions:
        status = "tombstoned" if s["tombstoned"] else ("closed" if s["valid_until"] else "open")
        table.add_row(
            s["id"],
            s["content"] or "",
            (s["recorded_at"] or "")[:19],
            str(s["node_count"]),
            status,
        )
    console.print(table)


@app.command("delete-session")
def cmd_delete_session(
    session_id: str = typer.Argument(..., help="Session ID to delete (s_...)"),
    purge: bool = typer.Option(False, "--purge", help="Hard-delete instead of tombstone (irreversible)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Delete a session and all its nodes (tombstone by default, --purge for hard delete)."""
    store = MemoryStore(db_path=db)

    # Show what will be deleted
    sessions = [s for s in store.list_sessions(limit=200) if s["id"] == session_id]
    if not sessions:
        console.print(f"[red]Session {session_id!r} not found.[/red]")
        raise typer.Exit(1)

    s = sessions[0]
    console.print(f"Session: [cyan]{s['id']}[/cyan]")
    console.print(f"Content: {s['content']}")
    console.print(f"Recorded: {(s['recorded_at'] or '')[:19]}  ·  Nodes: {s['node_count']}")

    if not yes:
        action = "hard-delete (irreversible)" if purge else "tombstone"
        confirmed = typer.confirm(f"\n{action} this session and all {s['node_count']} of its nodes?")
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    result = store.delete_session(session_id, purge=purge)
    if purge:
        console.print(f"[red]Hard-deleted {result['count']} node(s).[/red]")
    else:
        console.print(f"[yellow]Tombstoned {result['count']} node(s).[/yellow]")


@app.command("start-session")
def cmd_start_session(
    name: str = typer.Argument(..., help="Human-readable session name"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Open a named session and print its ID."""
    from .store import _now_iso
    store = MemoryStore(db_path=db)
    sid = store.add_node(
        kind="session",
        content=name.strip(),
        data={"started_at": _now_iso(), "agent_id": "cli"},
    )
    console.print(f"[green]Session opened:[/green] {sid}")
    console.print(f"  Pass to memory_store with --session-id {sid}")


@app.command("show")
def cmd_show(
    node_id: str = typer.Argument(..., help="Node ID to inspect"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Print a single node as JSON."""
    store = MemoryStore(db_path=db)
    node = store.get_node(node_id)
    if node is None:
        console.print(f"[red]Node {node_id!r} not found.[/red]")
        raise typer.Exit(1)
    print(json.dumps(dict(node), indent=2, default=str))


@app.command("search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query (FTS5)"),
    kind: Optional[str] = typer.Option(None, "--kind", "-k", help="Filter by node kind"),
    limit: int = typer.Option(10, "--limit", "-l"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Run a full-text search and print results as a table."""
    store = MemoryStore(db_path=db)
    kinds = [kind] if kind else None
    results = store.fts_search(query, limit=limit, kinds=kinds)
    if not results:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(title=f'Search: "{query}"')
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Kind", style="cyan")
    table.add_column("Conf", justify="right")
    table.add_column("Date", width=10)
    table.add_column("Content", style="white")
    for r in results:
        table.add_row(
            r.get("id", ""),
            r.get("kind", ""),
            f"{r.get('confidence', 1.0):.2f}",
            (r.get("valid_from") or r.get("recorded_at") or "")[:10],
            (r.get("content") or "")[:80],
        )
    console.print(table)


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


@app.command("consolidate")
def cmd_consolidate(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be tombstoned without doing it"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Process pending consolidation jobs: deduplicate near-identical facts."""
    from .consolidate import RuleBasedConsolidator
    store = MemoryStore(db_path=db)
    consolidator = RuleBasedConsolidator(store)
    result = consolidator.process_pending(dry_run=dry_run)
    prefix = "[yellow](dry run)[/yellow] " if dry_run else ""
    console.print(
        f"{prefix}Processed [cyan]{result['jobs']}[/cyan] job(s), "
        f"tombstoned [red]{result['tombstoned']}[/red] duplicate(s)."
    )


@app.command("import")
def cmd_import(
    file: str = typer.Argument(..., help="JSON file to import (.json array or export format)"),
    db: Optional[str] = typer.Option(None, "--db"),
) -> None:
    """Import memory nodes from a JSON file."""
    from .resolve import resolve_entities
    path = Path(file)
    if not path.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    raw = json.loads(path.read_text())
    # Accept both plain list and export format {"nodes": [...], "edges": [...]}
    nodes: list[dict] = raw if isinstance(raw, list) else raw.get("nodes", [])

    if not nodes:
        console.print("[yellow]No nodes found in file.[/yellow]")
        return

    store = MemoryStore(db_path=db)
    valid_kinds = {"session", "fact", "decision", "action", "outcome", "entity", "procedure", "preference"}

    table = Table(title=f"Importing from {path.name}")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Kind", style="cyan")
    table.add_column("Content", style="white")

    imported = 0
    errors = 0
    for i, spec in enumerate(nodes):
        content = spec.get("content", "")
        kind = spec.get("kind", "fact")
        if not content or kind not in valid_kinds:
            console.print(f"[red]Skip [{i}]: bad content/kind ({kind!r})[/red]")
            errors += 1
            continue

        data: dict = {}
        if spec.get("rationale"):
            data["rationale"] = spec["rationale"]
        if spec.get("alternatives_rejected"):
            data["alternatives_rejected"] = spec["alternatives_rejected"]

        nid = store.add_node(
            kind=kind,
            content=content,
            confidence=float(spec.get("confidence", 1.0)),
            valid_from=spec.get("valid_from"),
            session_id=spec.get("session_id"),
            data=data if data else None,
        )
        entity_names: list[str] = spec.get("entities") or []
        linked, _ = resolve_entities(store, entity_names)
        for eid in linked:
            store.add_edge(nid, eid, "ABOUT")

        table.add_row(nid, kind, content[:70])
        imported += 1

    console.print(table)
    console.print(f"[green]✓[/green] Imported {imported} node(s)." + (f"  [red]{errors} skipped.[/red]" if errors else ""))


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
