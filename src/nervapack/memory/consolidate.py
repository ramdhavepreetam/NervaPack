"""Consolidation workers: rule-based deduplication of memory nodes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .store import MemoryStore


@runtime_checkable
class Consolidator(Protocol):
    """Extract structured memory nodes from unstructured session transcripts."""

    def consolidate(self, session_id: str, transcript: str) -> list[str]:
        """Return list of created node ids. Future LLM implementation goes here."""
        ...


class NoopConsolidator:
    """Phase 1 placeholder. Logs a message; performs no work."""

    def consolidate(self, session_id: str, transcript: str) -> list[str]:
        print(
            f"[nervapack.memory] consolidation queued (Phase 2) for session {session_id}"
        )
        return []


class RuleBasedConsolidator:
    """
    Rule-based consolidator: queues a review job and deduplicates near-identical facts.

    On session close: writes to mem_review_queue so the `consolidate` CLI command
    can process them later. Does not call an LLM.
    """

    def __init__(self, store: "MemoryStore") -> None:
        self._store = store

    def consolidate(self, session_id: str, transcript: str) -> list[str]:
        """Queue a consolidation job; return [] (no nodes created at queue time)."""
        self._store.queue_consolidation(session_id, transcript)
        return []

    def process_pending(self, dry_run: bool = False) -> dict[str, int]:
        """
        Process all pending queue jobs.

        For each job, deduplicate facts within the session by Jaccard word-overlap
        (threshold > 0.9). Tombstones the older duplicate. Marks job resolved.

        Returns {"jobs": N, "tombstoned": M}.
        """
        jobs = self._store.get_pending_jobs()
        tombstoned = 0
        for job in jobs:
            import json
            payload = json.loads(job["payload"])
            session_id = payload.get("session_id", "")
            facts = self._store.get_session_facts(session_id)
            tombstoned += self._deduplicate(facts, dry_run=dry_run)
            if not dry_run:
                self._store.resolve_job(job["id"])
        return {"jobs": len(jobs), "tombstoned": tombstoned}

    def _deduplicate(self, facts: list[dict], dry_run: bool = False) -> int:
        """Tombstone near-duplicate facts (Jaccard > 0.9). Returns count tombstoned."""
        count = 0
        tombstoned_ids: set[str] = set()
        for i, a in enumerate(facts):
            if a["id"] in tombstoned_ids:
                continue
            for b in facts[i + 1:]:
                if b["id"] in tombstoned_ids:
                    continue
                if self._jaccard(a["content"], b["content"]) > 0.9:
                    # Keep the newer node (higher recorded_at), tombstone the older
                    older = a if (a["recorded_at"] or "") < (b["recorded_at"] or "") else b
                    tombstoned_ids.add(older["id"])
                    if not dry_run:
                        self._store.tombstone([older["id"]])
                    count += 1
        return count

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)
