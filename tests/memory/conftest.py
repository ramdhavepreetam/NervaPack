"""Shared fixtures for memory tests."""
from __future__ import annotations

import pytest

from nervapack.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """Fresh in-memory store backed by a temp file."""
    s = MemoryStore(db_path=str(tmp_path / "test_memory.db"))
    yield s
    s.close()
