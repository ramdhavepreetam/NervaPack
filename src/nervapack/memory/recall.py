"""Recall pipeline: FTS5 entry search → graph expansion → temporal mask → score → budget pack."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .pack import TokenCounter, get_token_counter, pack, pack_timeline
from .store import MemoryStore


def _age_days(node: dict[str, Any]) -> float:
    """Days since valid_from (or recorded_at if no valid_from)."""
    ts = node.get("valid_from") or node.get("recorded_at")
    if not ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400)
    except Exception:
        return 0.0


def _score(
    node: dict[str, Any],
    relevance: float,
    half_life_days: float = 30.0,
) -> float:
    age = _age_days(node)
    recency = math.exp(-math.log(2) * age / half_life_days)
    freq = 1 + 0.1 * math.log(1 + (node.get("access_count") or 0))
    # degree: count edges via store is expensive here; use a precomputed field if present
    degree = node.get("_degree", 0)
    connectivity = 1 + 0.1 * math.log(1 + degree)
    return relevance * recency * freq * connectivity


def recall(
    store: MemoryStore,
    query: str,
    budget_tokens: int = 500,
    kinds: list[str] | None = None,
    as_of: str | None = None,
    hops: int = 1,
    min_confidence: float = 0.0,
    counter: TokenCounter | None = None,
) -> str:
    """Run the full recall pipeline and return a packed markdown block."""
    tc = counter or get_token_counter()
    hops = min(max(hops, 0), 2)

    # 1. Entry search — FTS5 + alias, top K=12
    entries = store.fts_search(query, limit=12, kinds=kinds, as_of=as_of)

    # Build relevance scores from FTS rank (BM25 — lower is better in SQLite FTS5)
    # Normalise to [0, 1] where 1 = most relevant
    raw_ranks = [e.get("rank", 0.0) or 0.0 for e in entries]
    if raw_ranks:
        min_r, max_r = min(raw_ranks), max(raw_ranks)
        span = max_r - min_r if max_r != min_r else 1.0
        # FTS5 rank is negative BM25: more negative = better match
        relevances = [(max_r - r) / span for r in raw_ranks]
    else:
        relevances = []

    entry_map: dict[str, float] = {}
    for node, rel in zip(entries, relevances):
        entry_map[node["id"]] = rel

    # 2. Expand hops (inherit 0.6× relevance per hop)
    candidates: dict[str, tuple[dict[str, Any], float]] = {}
    for node, rel in zip(entries, relevances):
        # Pre-stamp _degree=0; expansion loop overwrites with real value for frontier nodes
        node.setdefault("_degree", 0)
        candidates[node["id"]] = (node, rel)

    frontier = list(zip(entries, relevances))
    for _ in range(hops):
        next_frontier = []
        for node, rel in frontier:
            neighbors = store.neighbors(node["id"])
            # Stamp _degree onto the node so scoring can use connectivity factor
            node["_degree"] = len(neighbors)
            child_rel = rel * 0.6
            for neighbor in neighbors:
                nid = neighbor["id"]
                if nid not in candidates or candidates[nid][1] < child_rel:
                    candidates[nid] = (neighbor, child_rel)
                    next_frontier.append((neighbor, child_rel))
        frontier = next_frontier

    # 3. Temporal mask — filter to currently valid (or as_of)
    if as_of:
        # Filter nodes valid at as_of
        valid_ids: set[str] = set()
        for nid, (node, _) in candidates.items():
            vf = node.get("valid_from") or ""
            vu = node.get("valid_until")
            if (not vf or vf <= as_of) and (vu is None or vu > as_of):
                if not node.get("tombstoned"):
                    valid_ids.add(nid)
    else:
        # Currently valid = tombstoned=0, valid_until IS NULL, not superseded
        current = store.currently_valid(list(candidates.keys()))
        valid_ids = {n["id"] for n in current}

    filtered = {
        nid: (node, rel)
        for nid, (node, rel) in candidates.items()
        if nid in valid_ids
        and (node.get("confidence") or 1.0) >= min_confidence
    }

    # 4. Score and sort
    def score_node(nid: str) -> float:
        node, rel = filtered[nid]
        return _score(node, rel)

    sorted_ids = sorted(filtered.keys(), key=score_node, reverse=True)
    scored_nodes = [filtered[nid][0] for nid in sorted_ids]

    # 5. Pack into budget (pack.py handles budget enforcement)
    result = pack(scored_nodes, query, budget_tokens, as_of, counter=tc)

    # Increment access counts for nodes that made it into the output
    # Parse which node ids appear in the result
    returned_ids = [nid for nid in sorted_ids if f"[{nid}]" in result]
    store.touch_nodes(returned_ids)

    return result


def recall_timeline(
    store: MemoryStore,
    topic: str,
    since: str | None = None,
    counter: TokenCounter | None = None,
) -> str:
    """Chronological trace including superseded nodes."""
    tc = counter or get_token_counter()
    nodes = store.timeline(topic, since=since)
    return pack_timeline(nodes, topic, counter=tc)
