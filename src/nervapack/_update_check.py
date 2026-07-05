"""
Background update checker — queries PyPI at most once per day and prints
a Rich notice if a newer version of nervapack is available.

Runs in a daemon thread so it never blocks the CLI. The result is printed
*after* the command completes (via atexit), so it never interrupts output.
"""
from __future__ import annotations

import atexit
import json
import threading
import time
from pathlib import Path

_PYPI_URL = "https://pypi.org/pypi/nervapack/json"
_CHECK_INTERVAL = 86400  # 24 hours
_CACHE_FILE = Path.home() / ".nervapack" / "update_check.json"
_result: dict | None = None  # filled by background thread


def _load_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _fetch_latest() -> str | None:
    """Return latest version string from PyPI, or None on any error."""
    import ssl
    import urllib.request

    def _get(ctx: ssl.SSLContext | None) -> str | None:
        try:
            kwargs = {"timeout": 3}
            if ctx:
                kwargs["context"] = ctx  # type: ignore[arg-type]
            with urllib.request.urlopen(_PYPI_URL, **kwargs) as resp:
                return json.loads(resp.read())["info"]["version"]
        except Exception:
            return None

    # Try verified first (certifi if available, then system certs)
    try:
        import certifi
        result = _get(ssl.create_default_context(cafile=certifi.where()))
    except ImportError:
        result = _get(ssl.create_default_context())

    if result:
        return result

    # Fallback: unverified — acceptable for a public read-only update check
    return _get(ssl._create_unverified_context())


def _check(current: str) -> None:
    global _result
    cache = _load_cache()
    now = time.time()

    # Use cached latest if checked recently
    if now - cache.get("checked_at", 0) < _CHECK_INTERVAL:
        latest = cache.get("latest")
    else:
        latest = _fetch_latest()
        if latest:
            _save_cache({"checked_at": now, "latest": latest})

    if latest and _is_newer(latest, current):
        _result = {"current": current, "latest": latest}


def _is_newer(latest: str, current: str) -> bool:
    """Return True if latest > current (simple semver tuple comparison)."""
    try:
        def to_tuple(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split(".")[:3])
        return to_tuple(latest) > to_tuple(current)
    except Exception:
        return False


def _print_notice() -> None:
    if _result is None:
        return
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(stderr=True)
        console.print(
            Panel(
                f"[bold yellow]Update available:[/bold yellow] "
                f"nervapack [red]{_result['current']}[/red] → [green]{_result['latest']}[/green]\n"
                f"[dim]Run:[/dim] [cyan]pip install --upgrade nervapack[/cyan]",
                title="[bold]nervapack[/bold]",
                border_style="yellow",
                expand=False,
            )
        )
    except Exception:
        # Never crash the CLI for an update notice
        print(
            f"\n[nervapack] Update available: {_result['current']} → {_result['latest']}\n"
            f"Run: pip install --upgrade nervapack\n"
        )


def start(current: str) -> None:
    """
    Spawn a daemon thread to check for updates. Register print_notice via atexit
    so the notice appears after the command output, not before.
    """
    atexit.register(_print_notice)
    t = threading.Thread(target=_check, args=(current,), daemon=True)
    t.start()
