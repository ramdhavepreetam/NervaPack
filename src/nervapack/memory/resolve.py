"""Entity resolution: exact match → alias (case-insensitive) → create new entity node."""
from __future__ import annotations

from .store import MemoryStore


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
            # Create new entity node
            slug = name.strip().lower().replace(" ", "_")
            eid = store.add_node(
                kind="entity",
                content=name.strip(),
                data={"entity_type": "unknown"},
                session_id=session_id,
            )
            # Register multiple alias forms for case-insensitive lookup
            store.add_alias(eid, name.strip())         # original
            store.add_alias(eid, slug)                  # snake_case
            store.add_alias(eid, _normalise(name))      # normalised (no separators)
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

    # 2. Normalised alias lookup (AuthService → authservice == auth_service normalised)
    norm = _normalise(clean)
    eid = store.find_entity_by_alias_normalised(norm)
    if eid:
        return eid

    # 3. FTS match restricted to entity kind
    results = store.fts_search(name, limit=3, kinds=["entity"])
    for r in results:
        content = (r.get("content") or "").lower()
        if clean.lower() in content or content in clean.lower():
            return r["id"]

    return None


# Phase 2 stub: embedding-tier entity resolution
class EmbeddingResolver:
    """Placeholder. Phase 2 will use sentence-transformers + sqlite-vec here."""

    def resolve(self, name: str) -> str | None:  # pragma: no cover
        raise NotImplementedError("EmbeddingResolver is a Phase 2 feature")
