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
    # Unwrap TextContent
    contents = result.content
    if contents and hasattr(contents[0], "text"):
        text = contents[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
    return contents


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
