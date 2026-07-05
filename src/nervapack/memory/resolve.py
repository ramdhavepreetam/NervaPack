"""Entity resolution: exact match → alias (case-insensitive) → create new entity node."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .store import MemoryStore

if TYPE_CHECKING:
    pass  # graph type is NetworkX DiGraph, avoid import at runtime


def _to_snake(name: str) -> str:
    """CamelCase / PascalCase → snake_case. 'AuthService' → 'auth_service'."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def resolve_entities(
    store: MemoryStore,
    entity_names: list[str],
    session_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """
    Resolve entity strings to node ids.

    For each name: try exact content match on entity nodes, then alias lookup,
    then create a new entity node. Phase 2 will add embedding-tier disambiguation here.

    Returns (linked_entity_ids, created_entity_ids).
    """
    linked: list[str] = []
    created: list[str] = []

    for name in entity_names:
        eid = _find_entity(store, name)
        if eid:
            linked.append(eid)
        else:
            eid = store.add_node(
                kind="entity",
                content=name.strip(),
                data={"entity_type": "unknown"},
                session_id=session_id,
            )
            # Register four alias forms for case-insensitive and cross-convention lookup
            store.add_alias(eid, name.strip())              # original
            store.add_alias(eid, name.strip().lower().replace(" ", "_"))  # basic slug
            store.add_alias(eid, _to_snake(name.strip()))  # CamelCase → snake_case
            store.add_alias(eid, _normalise(name))          # no-separator normalised
            created.append(eid)
            linked.append(eid)

    return linked, created


def _normalise(name: str) -> str:
    """Normalise to lowercase, strip underscores/spaces for fuzzy alias matching."""
    return name.strip().lower().replace("_", "").replace(" ", "").replace("-", "")


def _find_entity(store: MemoryStore, name: str) -> str | None:
    """Exact alias match (case-insensitive), normalised form, then FTS on entity content."""
    clean = name.strip()
    # 1. Direct alias lookup (COLLATE NOCASE: auth_service == AUTH_SERVICE)
    eid = store.find_entity_by_alias(clean)
    if eid:
        return eid

    # 2. CamelCase → snake_case alias lookup
    eid = store.find_entity_by_alias(_to_snake(clean))
    if eid:
        return eid

    # 3. Normalised alias lookup (AuthService → authservice == auth_service normalised)
    norm = _normalise(clean)
    eid = store.find_entity_by_alias_normalised(norm)
    if eid:
        return eid

    # 4. FTS match restricted to entity kind
    results = store.fts_search(name, limit=3, kinds=["entity"])
    for r in results:
        content = (r.get("content") or "").lower()
        if clean.lower() in content or content in clean.lower():
            return r["id"]

    return None


def match_code_entity(graph: "Any", entity_name: str) -> "dict | None":
    """
    Search a NetworkX code graph for a node whose name matches entity_name.

    Tries: exact name match, snake_case, and normalised form.
    Returns {graph_node_id, file_path, start_line, end_line} or None.
    """
    if graph is None:
        return None
    needle_snake = _to_snake(entity_name.strip())
    needle_norm = _normalise(entity_name.strip())
    for node_id, attrs in graph.nodes(data=True):
        raw_name = attrs.get("name", "")
        if not raw_name:
            continue
        if (
            raw_name.lower() == entity_name.strip().lower()
            or _to_snake(raw_name) == needle_snake
            or _normalise(raw_name) == needle_norm
        ):
            return {
                "graph_node_id": node_id,
                "file_path": attrs.get("file_path", ""),
                "start_line": attrs.get("start_line"),
                "end_line": attrs.get("end_line"),
                "code_type": attrs.get("type", ""),
            }
    return None


# Placeholder for future embedding-tier entity resolution
class EmbeddingResolver:
    """Placeholder. Future versions will use sentence-transformers + sqlite-vec here."""

    def resolve(self, name: str) -> str | None:  # pragma: no cover
        raise NotImplementedError("EmbeddingResolver is a future feature")
