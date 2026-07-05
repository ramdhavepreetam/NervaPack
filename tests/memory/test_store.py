"""Tests for MemoryStore CRUD, FTS sync, alias, and tombstone/purge."""
from __future__ import annotations

import json

import pytest



def test_add_and_get_node(store):
    nid = store.add_node("fact", "The sky is blue")
    node = store.get_node(nid)
    assert node is not None
    assert node["content"] == "The sky is blue"
    assert node["kind"] == "fact"
    assert node["tombstoned"] == 0


def test_id_prefix(store):
    nid = store.add_node("decision", "Use JWT")
    assert nid.startswith("d_")
    nid2 = store.add_node("fact", "x")
    assert nid2.startswith("f_")
    nid3 = store.add_node("session", "s")
    assert nid3.startswith("s_")


def test_add_edge(store):
    n1 = store.add_node("fact", "fact node")
    n2 = store.add_node("entity", "auth_service")
    store.add_edge(n1, n2, "ABOUT")
    edges = store.get_edges(src=n1, kind="ABOUT")
    assert len(edges) == 1
    assert edges[0]["dst"] == n2


def test_invalid_edge_kind(store):
    n1 = store.add_node("fact", "f")
    n2 = store.add_node("entity", "e")
    with pytest.raises(ValueError):
        store.add_edge(n1, n2, "INVALID_KIND")


def test_fts_search_finds_node(store):
    store.add_node("fact", "JWT is used for stateless authentication")
    results = store.fts_search("JWT authentication")
    assert any("JWT" in r["content"] for r in results)


def test_fts_search_kinds_filter(store):
    store.add_node("fact", "fact about auth")
    store.add_node("decision", "decision about auth")
    results = store.fts_search("auth", kinds=["fact"])
    assert all(r["kind"] == "fact" for r in results)


def test_alias_lookup(store):
    eid = store.add_node("entity", "auth_service")
    store.add_alias(eid, "AuthService")
    store.add_alias(eid, "auth_service")

    found = store.find_entity_by_alias("authservice")
    assert found == eid

    found2 = store.find_entity_by_alias("AuthService")
    assert found2 == eid


def test_tombstone_excludes_from_valid(store):
    nid = store.add_node("fact", "to be tombstoned")
    store.tombstone([nid])
    valid = store.currently_valid([nid])
    assert not any(n["id"] == nid for n in valid)


def test_tombstone_does_not_delete_row(store):
    nid = store.add_node("fact", "persisted")
    store.tombstone([nid])
    node = store.get_node(nid)
    assert node is not None
    assert node["tombstoned"] == 1


def test_purge_removes_row(store):
    nid = store.add_node("fact", "ephemeral")
    store.purge([nid])
    node = store.get_node(nid)
    assert node is None


def test_fts_after_tombstone_excluded_by_validity(store):
    """FTS still finds node after tombstone, but currently_valid excludes it."""
    nid = store.add_node("fact", "unique_tombstone_test_xyz")
    store.tombstone([nid])
    # FTS raw search may still find it, but currently_valid must exclude it
    valid = store.currently_valid([nid])
    assert not any(n["id"] == nid for n in valid)


def test_fts_after_purge_not_found(store):
    """After purge, FTS should not return the node (DELETE trigger ran)."""
    nid = store.add_node("fact", "unique_purge_test_abc")
    store.purge([nid])
    results = store.fts_search("unique_purge_test_abc")
    assert not any(r["id"] == nid for r in results)


def test_touch_nodes_increments_access_count(store):
    nid = store.add_node("fact", "access test")
    store.touch_nodes([nid])
    node = store.get_node(nid)
    assert node["access_count"] == 1
    store.touch_nodes([nid])
    node = store.get_node(nid)
    assert node["access_count"] == 2


def test_data_roundtrip(store):
    data = {"rationale": "faster", "alternatives_rejected": ["REST", "GraphQL"]}
    nid = store.add_node("decision", "Use gRPC", data=data)
    node = store.get_node(nid)
    loaded = json.loads(node["data"])
    assert loaded["rationale"] == "faster"
    assert "REST" in loaded["alternatives_rejected"]


def test_stats(store):
    store.add_node("fact", "f1")
    store.add_node("decision", "d1")
    s = store.stats()
    assert s["kind_counts"].get("fact", 0) >= 1
    assert s["kind_counts"].get("decision", 0) >= 1
    assert s["db_size_bytes"] > 0


def test_list_sessions(store):
    sid = store.add_node("session", "Test session A")
    store.add_node("fact", "A fact in session A", session_id=sid)
    sessions = store.list_sessions()
    assert any(s["id"] == sid for s in sessions)
    found = next(s for s in sessions if s["id"] == sid)
    assert found["node_count"] == 1
    assert found["content"] == "Test session A"


def test_delete_session_tombstone(store):
    sid = store.add_node("session", "To be deleted")
    nid = store.add_node("fact", "child of session", session_id=sid)
    result = store.delete_session(sid, purge=False)
    assert result["count"] >= 2  # session + child
    assert result["mode"] == "tombstone"
    # Both should be tombstoned
    assert store.get_node(sid)["tombstoned"] == 1
    assert store.get_node(nid)["tombstoned"] == 1


def test_delete_session_purge(store):
    sid = store.add_node("session", "Purge target")
    nid = store.add_node("fact", "purge child", session_id=sid)
    store.delete_session(sid, purge=True)
    assert store.get_node(sid) is None
    assert store.get_node(nid) is None
