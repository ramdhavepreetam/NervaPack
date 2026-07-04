"""Tests for bi-temporal supersede semantics."""
from __future__ import annotations

import time
from datetime import datetime

from nervapack.memory.recall import recall


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def test_supersede_closes_old_valid_until(store):
    old_id = store.add_node("fact", "v1: uses session cookies")
    time.sleep(0.01)
    new_id = store.add_node("fact", "v2: uses JWT")
    store.supersede(new_id, old_id)

    old = store.get_node(old_id)
    assert old["valid_until"] is not None, "Superseded node must have valid_until set"

    new = store.get_node(new_id)
    assert new["valid_until"] is None, "New node must be currently valid"


def test_supersede_edge_created(store):
    old_id = store.add_node("fact", "old fact")
    new_id = store.add_node("fact", "new fact")
    store.supersede(new_id, old_id)
    edges = store.get_edges(src=new_id, kind="SUPERSEDES")
    assert len(edges) == 1
    assert edges[0]["dst"] == old_id


def test_recall_returns_only_new_version(store):
    """memory_recall must not surface the superseded fact."""
    old_id = store.add_node(
        "fact",
        "supersede_test auth uses session cookies",
        valid_from="2026-01-01T00:00:00",
    )
    new_id = store.add_node(
        "fact",
        "supersede_test auth uses JWT tokens",
        valid_from="2026-06-01T00:00:00",
    )
    store.supersede(new_id, old_id)

    result = recall(store, "supersede_test auth", budget_tokens=500)
    assert "JWT tokens" in result
    assert "session cookies" not in result


def test_recall_as_of_returns_old_version(store):
    """memory_recall with as_of before supersession must return old version."""
    t1 = "2026-01-01T00:00:00"
    t2 = "2026-06-01T00:00:00"
    t_between = "2026-03-15T00:00:00"

    old_id = store.add_node("fact", "TEMPORAL auth session cookies approach", valid_from=t1)
    new_id = store.add_node("fact", "TEMPORAL auth JWT tokens approach", valid_from=t2)

    # Manually set old node valid_until to t2 and add SUPERSEDES edge
    store._get_conn().execute(
        "UPDATE mem_nodes SET valid_until = ? WHERE id = ?", (t2, old_id)
    )
    store._get_conn().commit()
    store.add_edge(new_id, old_id, "SUPERSEDES")

    result = recall(store, "TEMPORAL auth", budget_tokens=500, as_of=t_between)
    assert "session cookies approach" in result
    assert "JWT tokens approach" not in result


def test_timeline_shows_both_versions(store):
    """memory_timeline must show both old and new, old marked superseded."""
    old_id = store.add_node("fact", "timeline_v1 session cookies")
    new_id = store.add_node("fact", "timeline_v2 JWT tokens")
    store.supersede(new_id, old_id)

    from nervapack.memory.recall import recall_timeline
    result = recall_timeline(store, "timeline_v")
    assert "timeline_v1" in result
    assert "timeline_v2" in result
    assert "superseded" in result


def test_currently_valid_excludes_superseded(store):
    old_id = store.add_node("fact", "old superseded fact")
    new_id = store.add_node("fact", "new valid fact")
    store.supersede(new_id, old_id)

    valid = store.currently_valid([old_id, new_id])
    valid_ids = {n["id"] for n in valid}
    assert new_id in valid_ids
    assert old_id not in valid_ids
