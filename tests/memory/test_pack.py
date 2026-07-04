"""Tests for TokenCounter and pack() budget enforcement."""
from __future__ import annotations

import pytest

from nervapack.memory.pack import (
    CharTokenCounter,
    get_token_counter,
    pack,
    pack_timeline,
)


def _make_node(kind="fact", content="test content", nid="f_abc", conf=1.0, session_id=None):
    return {
        "id": nid,
        "kind": kind,
        "content": content,
        "confidence": conf,
        "valid_from": "2026-06-01T00:00:00",
        "recorded_at": "2026-06-01T00:00:00",
        "session_id": session_id,
        "access_count": 0,
    }


def test_char_token_counter_basic():
    tc = CharTokenCounter()
    assert tc.count("hello") == 2  # ceil(5/4) = 2
    assert tc.count("") == 1  # min 1
    assert tc.count("a" * 100) == 25


def test_get_token_counter_returns_counter():
    tc = get_token_counter()
    assert hasattr(tc, "count")
    result = tc.count("test string")
    assert isinstance(result, int)
    assert result >= 1


@pytest.mark.parametrize("budget", [50, 100, 200, 500])
def test_pack_budget_invariant(budget):
    """pack() must never exceed budget_tokens regardless of input size."""
    tc = CharTokenCounter()
    nodes = [
        _make_node(
            nid=f"f_{i:03d}",
            content=f"Fact {i}: " + "x" * 100,
        )
        for i in range(20)
    ]
    result = pack(nodes, "test query", budget, None, counter=tc)
    actual = tc.count(result)
    assert actual <= budget, f"Budget {budget} exceeded with {actual} tokens\n---\n{result}"


def test_pack_empty_nodes():
    tc = CharTokenCounter()
    result = pack([], "empty query", 500, None, counter=tc)
    assert isinstance(result, str)
    assert tc.count(result) <= 500


def test_pack_includes_header():
    tc = CharTokenCounter()
    nodes = [_make_node()]
    result = pack(nodes, "my query", 500, None, counter=tc)
    assert "Memory recall" in result
    assert "my query" in result


def test_pack_groups_by_kind():
    tc = CharTokenCounter()
    nodes = [
        _make_node(kind="decision", content="chose JWT", nid="d_001"),
        _make_node(kind="fact", content="JWT is stateless", nid="f_001"),
    ]
    result = pack(nodes, "auth", 500, None, counter=tc)
    assert "Decisions" in result
    assert "Facts" in result


def test_pack_provenance():
    tc = CharTokenCounter()
    nodes = [_make_node(session_id="s_123", nid="f_abc", content="prov fact")]
    result = pack(nodes, "prov", 500, None, counter=tc)
    if "f_abc" in result:
        assert "Provenance" in result or "s_123" in result


def test_pack_adversarial_budget_50():
    """At budget=50, must still not exceed even with 20 large nodes."""
    tc = CharTokenCounter()
    nodes = [
        _make_node(nid=f"f_{i:04d}", content="A" * 200)
        for i in range(20)
    ]
    result = pack(nodes, "adversarial query that is quite long indeed", 50, None, counter=tc)
    actual = tc.count(result)
    assert actual <= 50, f"50-token budget exceeded: {actual}\n---\n{result}"


def test_pack_timeline():
    tc = CharTokenCounter()
    nodes = [
        {**_make_node(nid="f_001", content="old version"), "_superseded_by": "f_002"},
        {**_make_node(nid="f_002", content="new version"), "_superseded_by": None},
    ]
    result = pack_timeline(nodes, "timeline topic", counter=tc)
    assert "old version" in result
    assert "new version" in result
    assert "superseded" in result
    assert "f_002" in result
