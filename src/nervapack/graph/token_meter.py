from __future__ import annotations

import os
from typing import List, Tuple

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


def count_tokens(text: str) -> Tuple[int, bool]:
    """Return (token_count, is_exact). is_exact=False when tiktoken isn't available."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), True
    except ImportError:
        return max(1, len(text) // 4), False


def naive_rag_text(file_paths: List[str]) -> str:
    """Concatenate full contents of all given files — what a naive RAG would send."""
    parts = []
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                parts.append(f"# File: {path}\n{f.read()}")
        except OSError:
            pass
    return "\n\n".join(parts)


def _bar(filled: int, total: int = 20) -> str:
    n = round(filled * total / max(total, 1))
    return "█" * n + "░" * (total - n)


def render_savings_panel(
    nervapack_tokens: int,
    naive_tokens: int,
    exact: bool,
    file_count: int = 0,
) -> Panel:
    prefix = "" if exact else "~"
    token_label = "tokens" + ("" if exact else " (est.)")

    saved = max(0, naive_tokens - nervapack_tokens)
    pct_nervapack = (nervapack_tokens / naive_tokens * 100) if naive_tokens > 0 else 0
    pct_saved = 100 - pct_nervapack

    # Cost rates per million input tokens (as of mid-2025)
    GPT4_RATE = 2.50 / 1_000_000   # GPT-4o input
    SONNET_RATE = 3.00 / 1_000_000  # Claude Sonnet 4 input
    cost_gpt4 = saved * GPT4_RATE
    cost_sonnet = saved * SONNET_RATE

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("Strategy", style="white", min_width=20)
    table.add_column(token_label.title(), justify="right", style="white", min_width=10)
    table.add_column("Visual", min_width=22)
    table.add_column("Relative", justify="right", min_width=12)

    naive_bar = _bar(20)
    np_bar = _bar(round(pct_nervapack / 5))  # scale to 20-char bar

    table.add_row(
        f"[red]Naive RAG[/red] ({file_count} file{'s' if file_count != 1 else ''})",
        f"[red]{prefix}{naive_tokens:,}[/red]",
        f"[red]{naive_bar}[/red]",
        "[red]100% (base)[/red]",
    )
    table.add_row(
        "[green]NervaPack[/green]",
        f"[green]{prefix}{nervapack_tokens:,}[/green]",
        f"[green]{_bar(round(pct_nervapack / 5))}[/green]",
        f"[green]{pct_nervapack:.1f}%[/green]",
    )

    summary_lines = [
        f"  [bold white]Tokens saved:[/bold white] [bold green]{prefix}{saved:,}[/bold green]   "
        f"[bold white]Reduction:[/bold white] [bold green]{pct_saved:.1f}%[/bold green]",
        f"  [dim]Cost saved (GPT-4o  $2.50/1M): [bold yellow]${cost_gpt4:.4f}[/bold yellow] per query[/dim]",
        f"  [dim]Cost saved (Claude Sonnet $3/1M): [bold yellow]${cost_sonnet:.4f}[/bold yellow] per query[/dim]",
    ]
    if not exact:
        summary_lines.append(
            "  [dim italic]Install tiktoken for exact counts: pip install nervapack[metrics][/dim italic]"
        )

    body = Text.from_markup("\n".join(summary_lines))

    from rich.console import Group
    from rich.rule import Rule
    content = Group(table, Rule(style="dim"), body)

    return Panel(
        content,
        title="[bold cyan] NervaPack Token Efficiency [/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )
