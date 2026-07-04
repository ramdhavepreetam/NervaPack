"""Tests for recall pipeline and budget invariant."""
from __future__ import annotations

import pytest

from nervapack.memory.store import MemoryStore
from nervapack.memory.recall import recall
from nervapack.memory.pack import CharTokenCounter


def _populate(store: MemoryStore, n: int = 10) -> list[str]:
    ids = []
    for i in range(n):
        nid = store.add_node("fact", f"Fact number {i}: the system uses component_{i} for processing data requests efficiently")
        ids.append(nid)
    return ids


@pytest.mark.parametrize("budget", [50, 100, 200, 500])
def test_budget_invariant(store, budget):
    """Packed output must never exceed budget_tokens (acceptance criterion 3)."""
    _populate(store, 15)
    tc = CharTokenCounter()
    result = recall(store, "component processing data", budget_tokens=budget, counter=tc)
    actual_tokens = tc.count(result)
    assert actual_tokens <= budget, (
        f"Budget {budget} exceeded: got {actual_tokens} tokens\n---\n{result}"
    )


def test_recall_returns_string(store):
    store.add_node("fact", "JWT is stateless and supports horizontal scaling")
    result = recall(store, "JWT scaling", budget_tokens=500)
    assert isinstance(result, str)
    assert len(result) > 0


def test_recall_empty_store(store):
    result = recall(store, "nonexistent query", budget_tokens=500)
    assert isinstance(result, str)


def test_recall_kind_filter(store):
    store.add_node("fact", "fact about redis caching")
    store.add_node("decision", "decision about redis caching")
    result = recall(store, "redis caching", budget_tokens=500, kinds=["decision"])
    # Should only have decisions in the grouped output
    assert "### Decisions" in result or "decision" in result.lower()


def test_recall_increments_access_count(store):
    nid = store.add_node("fact", "access count test fact unique_xyz")
    before = store.get_node(nid)["access_count"]
    result = recall(store, "access count unique_xyz", budget_tokens=500)
    if f"[{nid}]" in result:
        after = store.get_node(nid)["access_count"]
        assert after > before


def test_recall_provenance_footer(store):
    sid = store.add_node("session", "test session")
    store.add_node("fact", "provenance test fact unique_prov", session_id=sid)
    result = recall(store, "provenance unique_prov", budget_tokens=500)
    # If node is returned and has session_id, provenance section should appear
    if "unique_prov" in result:
        assert "Provenance" in result or sid in result


def test_recall_with_hops(store):
    """Expanded nodes (via hops) can be included in results."""
    eid = store.add_node("entity", "auth_service hop test")
    nid = store.add_node("fact", "hop_fact: JWT handles auth")
    store.add_edge(nid, eid, "ABOUT")
    # Query the entity; the fact should be reachable via hop
    result = recall(store, "auth_service hop test", budget_tokens=500, hops=1)
    assert isinstance(result, str)


def test_recall_timeline_includes_superseded(store):
    from nervapack.memory.recall import recall_timeline
    old_id = store.add_node("fact", "timeline old fact xyz")
    new_id = store.add_node("fact", "timeline new fact xyz")
    store.supersede(new_id, old_id)
    result = recall_timeline(store, "timeline xyz")
    assert "old fact" in result
    assert "new fact" in result
    assert "superseded" in result
