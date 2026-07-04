"""Phase 2 stub: consolidation worker interface (LLM extraction from transcripts)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Consolidator(Protocol):
    """Extract structured memory nodes from unstructured session transcripts."""

    def consolidate(self, session_id: str, transcript: str) -> list[str]:
        """Return list of created node ids. Phase 2 implementation calls LiteLLM."""
        ...


class NoopConsolidator:
    """Phase 1 placeholder. Logs a message; performs no LLM extraction."""

    def consolidate(self, session_id: str, transcript: str) -> list[str]:
        print(
            f"[nervapack.memory] consolidation queued (Phase 2) for session {session_id}"
        )
        return []
