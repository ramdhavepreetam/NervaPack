"""Token counting protocol and markdown packing for recall output."""
from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable

from datetime import datetime


@runtime_checkable
class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class CharTokenCounter:
    """Default: ceil(len / 4). No external deps."""

    def count(self, text: str) -> int:
        return max(1, math.ceil(len(text) / 4))


def _try_tiktoken_counter() -> TokenCounter | None:
    try:
        import tiktoken  # type: ignore[import]

        enc = tiktoken.get_encoding("cl100k_base")

        class _Tiktoken:
            def count(self, text: str) -> int:
                return max(1, len(enc.encode(text)))

        return _Tiktoken()
    except Exception:
        return None


def get_token_counter() -> TokenCounter:
    return _try_tiktoken_counter() or CharTokenCounter()


_KIND_LABELS: dict[str, str] = {
    "decision": "Decisions",
    "fact": "Facts",
    "outcome": "Outcomes",
    "procedure": "Procedures",
    "preference": "Preferences",
    "action": "Actions",
    "entity": "Entities",
    "session": "Sessions",
}

_KIND_ORDER = ["decision", "fact", "outcome", "procedure", "preference", "action", "entity", "session"]


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "unknown"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def _node_line(node: dict[str, Any]) -> str:
    nid = node.get("id", "?")
    date = _fmt_date(node.get("valid_from") or node.get("recorded_at"))
    conf = node.get("confidence", 1.0)
    content = node.get("content", "").strip()
    return f"- [{nid}] {date} · conf {conf:.2f} — {content}"


def pack(
    nodes: list[dict[str, Any]],
    query: str,
    budget_tokens: int,
    as_of: str | None,
    counter: TokenCounter | None = None,
) -> str:
    """
    Render nodes into a budget-capped markdown block.
    Never exceeds budget_tokens. Returns header-only if nothing fits.
    """
    tc = counter or get_token_counter()
    as_of_str = as_of or datetime.utcnow().strftime("%Y-%m-%d")

    header = f'## Memory recall: "{query}" (as of {as_of_str} · {{n}} items · {{used}}/{budget_tokens} tokens)\n'

    # Reserve ~10% for the provenance footer
    footer_budget = max(20, budget_tokens // 10)
    body_budget = budget_tokens - footer_budget

    # Check header itself fits
    header_placeholder = header.format(n=0, used=0)
    header_tokens = tc.count(header_placeholder)
    if header_tokens > body_budget:
        # Budget too small even for header — return minimal
        return header.format(n=0, used=header_tokens)

    # Group nodes by kind
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        k = node.get("kind", "fact")
        by_kind.setdefault(k, []).append(node)

    # Build body lines greedily, highest-scored nodes first (caller pre-sorted)
    body_lines: list[str] = []
    included_nodes: list[dict[str, Any]] = []
    used = header_tokens

    for kind in _KIND_ORDER:
        if kind not in by_kind:
            continue
        label = _KIND_LABELS.get(kind, kind.capitalize() + "s")
        section_header = f"\n### {label}"
        sh_tokens = tc.count(section_header)
        if used + sh_tokens > body_budget:
            break
        section_lines: list[str] = []
        section_nodes: list[dict[str, Any]] = []
        for node in by_kind[kind]:
            line = _node_line(node)
            line_tokens = tc.count(line)
            if used + sh_tokens + tc.count("\n".join(section_lines)) + line_tokens > body_budget:
                break
            section_lines.append(line)
            section_nodes.append(node)
        if section_lines:
            body_lines.append(section_header)
            body_lines.extend(section_lines)
            included_nodes.extend(section_nodes)
            used += sh_tokens + sum(tc.count(line) for line in section_lines)

    # Provenance footer
    prov_parts = [
        f"{n['id']} ← session {n['session_id']}"
        for n in included_nodes
        if n.get("session_id")
    ]
    footer = ""
    if prov_parts:
        footer_text = "\n\n### Provenance\n" + " · ".join(prov_parts)
        if used + tc.count(footer_text) <= budget_tokens:
            footer = footer_text
            used += tc.count(footer_text)

    n_items = len(included_nodes)
    final_header = header.format(n=n_items, used=used)
    body = "\n".join(body_lines)
    result = final_header + body + footer

    # Hard invariant: if total exceeds budget, strip footer then drop items
    if tc.count(result) > budget_tokens:
        result = final_header + body
    if tc.count(result) > budget_tokens:
        # Drop items from end until fits
        while included_nodes and tc.count(result) > budget_tokens:
            included_nodes.pop()
            # Rebuild
            by_kind2: dict[str, list[dict[str, Any]]] = {}
            for node in included_nodes:
                k = node.get("kind", "fact")
                by_kind2.setdefault(k, []).append(node)
            body_lines2: list[str] = []
            for kind in _KIND_ORDER:
                if kind not in by_kind2:
                    continue
                label = _KIND_LABELS.get(kind, kind.capitalize() + "s")
                body_lines2.append(f"\n### {label}")
                for node in by_kind2[kind]:
                    body_lines2.append(_node_line(node))
            body = "\n".join(body_lines2)
            n_items = len(included_nodes)
            final_header = header.format(n=n_items, used=tc.count(final_header + body))
            result = final_header + body

    return result


def pack_timeline(
    nodes: list[dict[str, Any]],
    topic: str,
    counter: TokenCounter | None = None,
) -> str:
    """Render a chronological timeline including superseded nodes."""
    _ = counter or get_token_counter()  # reserved for future budget-cap on timeline
    lines = [f"## Memory timeline: {topic!r}\n"]
    for node in nodes:
        nid = node.get("id", "?")
        date = _fmt_date(node.get("valid_from") or node.get("recorded_at"))
        conf = node.get("confidence", 1.0)
        content = node.get("content", "").strip()
        sup = node.get("_superseded_by")
        marker = f" [superseded by {sup}]" if sup else ""
        lines.append(f"- [{nid}] {date} · conf {conf:.2f}{marker} — {content}")
    return "\n".join(lines)
