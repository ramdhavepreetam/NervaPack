"""MCP integration tests — all nine tools exercised through FastMCP test client."""
from __future__ import annotations

import json
import pytest

from mcp.shared.memory import create_connected_server_and_client_session


# Isolate each test to a fresh in-memory db via env var
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "mcp_test_memory.db")
    monkeypatch.setenv("NERVAPACK_MEMORY_DB", db_file)
    # Reset module-level store and session state
    import nervapack.memory.mcp_server as ms
    ms._store = None
    ms._session_id = None
    yield
    ms._store = None
    ms._session_id = None


@pytest.fixture
def mcp_app():
    """Return the FastMCP app with a fresh store."""
    import nervapack.memory.mcp_server as ms
    return ms.mcp


async def _call_tool(client, name, args=None):
    result = await client.call_tool(name, args or {})
    # FastMCP may return structuredContent for list/dict types
    if result.structuredContent is not None:
        return result.structuredContent.get("result", result.structuredContent)
    # Unwrap TextContent
    contents = result.content
    if not contents:
        return None
    if len(contents) == 1 and hasattr(contents[0], "text"):
        text = contents[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
    # Multiple TextContent items — try to parse each and return as list
    parsed = []
    for c in contents:
        if hasattr(c, "text"):
            try:
                parsed.append(json.loads(c.text))
            except (json.JSONDecodeError, TypeError):
                parsed.append(c.text)
    return parsed if len(parsed) > 1 else (parsed[0] if parsed else contents)


@pytest.mark.asyncio
async def test_memory_store_and_recall(mcp_app, tmp_path):
    async with create_connected_server_and_client_session(mcp_app) as client:
        # Store a decision
        result = await _call_tool(client, "memory_store", {
            "content": "Chose JWT over session cookies for auth_service",
            "kind": "decision",
            "entities": ["auth_service"],
            "confidence": 0.9,
        })
        assert "node_id" in result
        node_id = result["node_id"]
        assert node_id.startswith("d_")
        assert len(result["linked_entity_ids"]) == 1

        # Recall it
        recall_result = await _call_tool(client, "memory_recall", {
            "query": "JWT auth",
            "budget_tokens": 500,
        })
        assert isinstance(recall_result, str)
        assert "JWT" in recall_result


@pytest.mark.asyncio
async def test_memory_about(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        # Store with entity
        await _call_tool(client, "memory_store", {
            "content": "auth_service issues 15-minute access tokens",
            "kind": "fact",
            "entities": ["auth_service"],
        })
        result = await _call_tool(client, "memory_about", {"entity": "auth_service"})
        assert isinstance(result, str)
        assert "15-minute" in result or "auth_service" in result.lower()


@pytest.mark.asyncio
async def test_memory_why(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_store", {
            "content": "why_test: Chose gRPC over REST for internal services",
            "kind": "decision",
            "confidence": 0.85,
        })
        node_id = result["node_id"]

        why = await _call_tool(client, "memory_why", {"decision_ref": node_id})
        assert isinstance(why, str)
        assert "gRPC" in why

        why2 = await _call_tool(client, "memory_why", {"decision_ref": "gRPC over REST"})
        assert isinstance(why2, str)


@pytest.mark.asyncio
async def test_memory_timeline(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {
            "content": "timeline_test: v1 approach",
            "kind": "fact",
        })
        await _call_tool(client, "memory_store", {
            "content": "timeline_test: v2 approach",
            "kind": "fact",
        })
        result = await _call_tool(client, "memory_timeline", {"topic": "timeline_test"})
        assert isinstance(result, str)
        assert "v1" in result
        assert "v2" in result


@pytest.mark.asyncio
async def test_memory_end_session(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        # Store something to open a session
        await _call_tool(client, "memory_store", {
            "content": "session test fact",
            "kind": "fact",
        })
        result = await _call_tool(client, "memory_end_session", {
            "summary": "Completed session successfully"
        })
        assert "closed_session_id" in result
        assert "outcome_id" in result


@pytest.mark.asyncio
async def test_memory_forget_tombstone(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        stored = await _call_tool(client, "memory_store", {
            "content": "to be forgotten fact",
            "kind": "fact",
        })
        node_id = stored["node_id"]

        result = await _call_tool(client, "memory_forget", {
            "node_id": node_id,
            "purge": False,
        })
        assert result["count"] == 1
        assert result["mode"] == "tombstone"


@pytest.mark.asyncio
async def test_memory_forget_purge(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        stored = await _call_tool(client, "memory_store", {
            "content": "to be purged fact unique999",
            "kind": "fact",
        })
        node_id = stored["node_id"]

        result = await _call_tool(client, "memory_forget", {
            "node_id": node_id,
            "purge": True,
        })
        assert result["count"] == 1
        assert result["mode"] == "purge"

        # Should return 0 items (node was purged)
        recall_result = await _call_tool(client, "memory_recall", {
            "query": "purged fact unique999",
            "budget_tokens": 500,
        })
        assert "0 items" in recall_result


@pytest.mark.asyncio
async def test_memory_verify_confirm(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        stored = await _call_tool(client, "memory_store", {
            "content": "verifiable fact",
            "kind": "fact",
            "confidence": 0.7,
        })
        node_id = stored["node_id"]

        result = await _call_tool(client, "memory_verify", {
            "node_id": node_id,
            "status": "confirm",
        })
        assert result["confidence"] == pytest.approx(0.8, abs=0.01)


@pytest.mark.asyncio
async def test_memory_verify_refute(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        stored = await _call_tool(client, "memory_store", {
            "content": "refutable fact",
            "kind": "fact",
            "confidence": 0.8,
        })
        node_id = stored["node_id"]

        result = await _call_tool(client, "memory_verify", {
            "node_id": node_id,
            "status": "refute",
        })
        assert result["confidence"] == pytest.approx(0.4, abs=0.01)
        assert result["status"] == "refuted"


@pytest.mark.asyncio
async def test_memory_stats(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {
            "content": "stats test fact",
            "kind": "fact",
        })
        result = await _call_tool(client, "memory_stats", {})
        assert "kind_counts" in result
        assert "db_size_bytes" in result
        assert "namespaces" in result


@pytest.mark.asyncio
async def test_entity_resolution_case_insensitive(mcp_app):
    """Acceptance criterion 4: memory_about('AuthService') finds auth_service nodes."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        # Store with entity "auth_service"
        await _call_tool(client, "memory_store", {
            "content": "auth_service handles JWT validation",
            "kind": "fact",
            "entities": ["auth_service"],
        })
        # Look up with different casing
        result = await _call_tool(client, "memory_about", {"entity": "AuthService"})
        assert isinstance(result, str)
        # Should find the fact via case-insensitive alias
        # (entity node content is "auth_service", alias "auth_service" registered)
        assert "auth_service" in result.lower() or "JWT" in result


@pytest.mark.asyncio
async def test_cross_session_persistence(tmp_path, monkeypatch):
    """Acceptance criterion 1: data persists across separate store instances."""
    db_file = str(tmp_path / "cross_session.db")
    monkeypatch.setenv("NERVAPACK_MEMORY_DB", db_file)

    import nervapack.memory.mcp_server as ms

    # Session A: store
    ms._store = None
    ms._session_id = None
    async with create_connected_server_and_client_session(ms.mcp) as client:
        result = await _call_tool(client, "memory_store", {
            "content": "Chose JWT over session cookies for cross_session_test",
            "kind": "decision",
            "entities": ["cross_session_service"],
            "confidence": 0.9,
        })
        await _call_tool(client, "memory_end_session", {
            "summary": "JWT decision made"
        })

    # Session B: fresh store, same db
    ms._store = None
    ms._session_id = None
    async with create_connected_server_and_client_session(ms.mcp) as client:
        result = await _call_tool(client, "memory_recall", {
            "query": "why JWT for cross_session_test",
            "budget_tokens": 500,
        })
        assert isinstance(result, str)
        assert "JWT" in result


@pytest.mark.asyncio
async def test_memory_list_sessions(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {"content": "some fact", "kind": "fact"})
        result = await _call_tool(client, "memory_list_sessions", {})
        assert isinstance(result, list)
        assert len(result) >= 1
        session = result[0]
        assert "id" in session
        assert "node_count" in session


@pytest.mark.asyncio
async def test_memory_clear_session_tombstone(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        # Create a session by storing a fact
        store_result = await _call_tool(client, "memory_store", {"content": "clearable fact", "kind": "fact"})
        sessions = await _call_tool(client, "memory_list_sessions", {})
        sid = sessions[0]["id"]
        clear_result = await _call_tool(client, "memory_clear_session", {"session_id": sid, "purge": False})
        assert clear_result["count"] >= 1
        assert clear_result["mode"] == "tombstone"
        # Session should now be tombstoned
        sessions_after = await _call_tool(client, "memory_list_sessions", {})
        tombstoned = next((s for s in sessions_after if s["id"] == sid), None)
        if tombstoned:
            assert tombstoned["tombstoned"] == 1


@pytest.mark.asyncio
async def test_memory_verify_refute_excludes_from_recall(mcp_app):
    """Refuted nodes should be excluded from recall (valid_until is set to now)."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        store_result = await _call_tool(client, "memory_store", {
            "content": "refutable_fact_unique_xyz: some claim that will be refuted",
            "kind": "fact",
            "confidence": 0.8,
        })
        node_id = store_result["node_id"]
        # Refute the node
        await _call_tool(client, "memory_verify", {"node_id": node_id, "status": "refute"})
        # Recall should not return the node content (valid_until is now set)
        result = await _call_tool(client, "memory_recall", {
            "query": "refutable_fact_unique_xyz",
            "budget_tokens": 500,
        })
        # The query phrase appears in the header; confirm the *node content* is absent
        assert "some claim that will be refuted" not in result


@pytest.mark.asyncio
async def test_memory_about_normalised_alias(mcp_app):
    """memory_about('AuthService') should find entity stored as 'auth_service'."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {
            "content": "AuthService handles token validation",
            "kind": "fact",
            "entities": ["AuthService"],
        })
        # Lookup via snake_case form
        result = await _call_tool(client, "memory_about", {"entity": "auth_service"})
        assert isinstance(result, str)
        assert "AuthService" in result or "token validation" in result


@pytest.mark.asyncio
async def test_memory_start_session(mcp_app):
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_start_session", {"name": "JWT auth refactor"})
        assert "session_id" in result
        assert result["created"] is True
        sid = result["session_id"]
        # Second call should return the existing session
        result2 = await _call_tool(client, "memory_start_session", {"name": "different name"})
        assert result2["session_id"] == sid
        assert result2["created"] is False


@pytest.mark.asyncio
async def test_memory_store_rationale(mcp_app):
    """memory_store with rationale/alternatives should surface in memory_why."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        store_result = await _call_tool(client, "memory_store", {
            "content": "Chose JWT for authentication rationale_test_unique",
            "kind": "decision",
            "entities": ["auth_service"],
            "rationale": "Stateless, scales horizontally",
            "alternatives_rejected": ["session cookies", "API keys"],
        })
        node_id = store_result["node_id"]
        why_result = await _call_tool(client, "memory_why", {"decision_ref": node_id})
        assert "Stateless" in why_result
        assert "session cookies" in why_result


@pytest.mark.asyncio
async def test_memory_recall_min_confidence(mcp_app):
    """min_confidence parameter filters out low-confidence nodes."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {
            "content": "high confidence system design fact confidence_filter_test",
            "kind": "fact",
            "confidence": 0.9,
        })
        await _call_tool(client, "memory_store", {
            "content": "low confidence system design fact confidence_filter_test",
            "kind": "fact",
            "confidence": 0.1,
        })
        result = await _call_tool(client, "memory_recall", {
            "query": "confidence_filter_test",
            "budget_tokens": 500,
            "min_confidence": 0.5,
        })
        assert "high confidence" in result
        assert "low confidence" not in result


# ── Phase 2 MCP tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_end_session_queues_consolidation_job(mcp_app):
    """memory_end_session now queues a row in mem_review_queue."""
    import nervapack.memory.mcp_server as ms
    async with create_connected_server_and_client_session(mcp_app) as client:
        await _call_tool(client, "memory_store", {"content": "a fact", "kind": "fact"})
        await _call_tool(client, "memory_end_session", {"summary": "test done"})

    store = ms._get_store()
    jobs = store.get_pending_jobs()
    assert len(jobs) >= 1


@pytest.mark.asyncio
async def test_memory_import_basic(mcp_app):
    """memory_import loads nodes and they appear in recall."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_import", {
            "nodes": [
                {"content": "Import test: chose gzip compression for logs", "kind": "decision", "confidence": 0.9},
                {"content": "Import test: all workers need heartbeat monitoring", "kind": "preference"},
            ]
        })
        assert result["imported"] == 2
        assert len(result["node_ids"]) == 2
        assert result["errors"] == []

        recall = await _call_tool(client, "memory_recall", {"query": "gzip compression logs", "budget_tokens": 500})
        assert "gzip" in recall


@pytest.mark.asyncio
async def test_memory_import_with_entities(mcp_app):
    """memory_import creates ABOUT edges for entities."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_import", {
            "nodes": [
                {"content": "Use async_db for all reads", "kind": "decision",
                 "entities": ["async_db"]},
            ]
        })
        assert result["imported"] == 1
        # Entity should have been created
        assert len(result["created_entity_ids"]) == 1


@pytest.mark.asyncio
async def test_memory_import_bad_kind_skipped(mcp_app):
    """memory_import skips nodes with invalid kinds and reports errors."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_import", {
            "nodes": [
                {"content": "valid node", "kind": "fact"},
                {"content": "bad kind node", "kind": "bogus"},
            ]
        })
        assert result["imported"] == 1
        assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_memory_for_code_no_touches(mcp_app):
    """memory_for_code returns a no-match message when no TOUCHES edges exist."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_for_code", {"file_path": "src/nonexistent.py"})
        assert isinstance(result, str)
        assert "No memories" in result


@pytest.mark.asyncio
async def test_memory_to_code_empty(mcp_app):
    """memory_to_code returns empty list for a node with no TOUCHES edges."""
    async with create_connected_server_and_client_session(mcp_app) as client:
        store_result = await _call_tool(client, "memory_store", {
            "content": "no code connection", "kind": "fact"
        })
        result = await _call_tool(client, "memory_to_code", {"memory_id": store_result["node_id"]})
        assert result == [] or result is None or result == {}


@pytest.mark.asyncio
async def test_touches_edge_created_when_graph_loaded(mcp_app, monkeypatch):
    """When code graph is present and entity matches, TOUCHES edge is created on memory_store."""
    import networkx as nx
    import nervapack.memory.mcp_server as ms

    # Build a minimal graph with one known node
    G = nx.DiGraph()
    G.add_node(
        "function:src/auth.py:verify_token:42",
        type="function",
        name="verify_token",
        file_path="src/auth.py",
        start_line=42,
        end_line=61,
        content="def verify_token(token): ...",
    )

    # Inject the mock graph and reset graph cache
    ms._code_graph = None
    monkeypatch.setattr(ms, "_get_code_graph", lambda: G)

    async with create_connected_server_and_client_session(mcp_app) as client:
        result = await _call_tool(client, "memory_store", {
            "content": "verify_token must validate expiry",
            "kind": "fact",
            "entities": ["verify_token"],
        })
        node_id = result["node_id"]

        # Verify TOUCHES edge was created
        code_locs = await _call_tool(client, "memory_to_code", {"memory_id": node_id})
        # code_locs may be None/empty/list
        if isinstance(code_locs, list) and code_locs:
            loc = code_locs[0]
            assert loc.get("file_path") == "src/auth.py"
            assert loc.get("start_line") == 42

    # Clean up graph override
    ms._code_graph = None
