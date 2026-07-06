"""
Graph evolution history — records a snapshot of graph stats on every ingest/sync.

Snapshots are appended to .nervapack/graph_history.jsonl (same pattern as
query_history.py). The timeline fills in from the moment of first use.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GraphSnapshot:
    """Stats recorded after one ingest or sync operation."""
    timestamp: str
    trigger: str          # "ingest" | "sync"
    total_nodes: int
    total_edges: int
    health_score: int
    node_counts: Dict[str, int]
    edge_counts: Dict[str, int]
    doc_coverage_pct: float
    orphaned_count: int
    files_changed: int    # number of files processed in this run


class GraphHistory:
    """Appends and reads graph snapshots from a JSONL file."""

    DEFAULT_FILE = os.path.join(".nervapack", "graph_history.jsonl")

    def __init__(self, history_file: Optional[str] = None):
        self.history_file = Path(history_file or self.DEFAULT_FILE)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.touch()

    def record(
        self,
        trigger: str,
        total_nodes: int,
        total_edges: int,
        health_score: int,
        node_counts: Dict[str, int],
        edge_counts: Dict[str, int],
        doc_coverage_pct: float,
        orphaned_count: int,
        files_changed: int = 0,
    ) -> None:
        """Append one snapshot to the history file."""
        snap = GraphSnapshot(
            timestamp=datetime.now().isoformat(),
            trigger=trigger,
            total_nodes=total_nodes,
            total_edges=total_edges,
            health_score=health_score,
            node_counts=node_counts,
            edge_counts=edge_counts,
            doc_coverage_pct=doc_coverage_pct,
            orphaned_count=orphaned_count,
            files_changed=files_changed,
        )
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(snap)) + "\n")

    def record_from_analytics(self, analytics: Any, trigger: str, files_changed: int = 0) -> None:
        """Convenience: build snapshot from a GraphAnalytics instance."""
        stats = analytics.get_summary_stats()
        doc_cov = stats.get("documentation_coverage", {})
        self.record(
            trigger=trigger,
            total_nodes=stats["total_nodes"],
            total_edges=stats["total_edges"],
            health_score=stats["health_score"],
            node_counts=stats["node_counts"],
            edge_counts=stats["edge_counts"],
            doc_coverage_pct=doc_cov.get("percentage", 0.0),
            orphaned_count=stats.get("orphaned_count", 0),
            files_changed=files_changed,
        )

    def get_all(self) -> List[GraphSnapshot]:
        """Return all snapshots oldest-first."""
        snapshots: List[GraphSnapshot] = []
        if not self.history_file.exists():
            return snapshots
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    snapshots.append(GraphSnapshot(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        return snapshots

    def get_recent(self, limit: int = 50) -> List[GraphSnapshot]:
        all_snaps = self.get_all()
        return all_snaps[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        snaps = self.get_all()
        if not snaps:
            return {
                "total_snapshots": 0,
                "first_snapshot": None,
                "latest_snapshot": None,
                "node_growth": 0,
                "edge_growth": 0,
                "ingest_count": 0,
                "sync_count": 0,
            }

        first = snaps[0]
        latest = snaps[-1]

        return {
            "total_snapshots": len(snaps),
            "first_snapshot": first.timestamp,
            "latest_snapshot": latest.timestamp,
            "node_growth": latest.total_nodes - first.total_nodes,
            "edge_growth": latest.total_edges - first.total_edges,
            "ingest_count": sum(1 for s in snaps if s.trigger == "ingest"),
            "sync_count": sum(1 for s in snaps if s.trigger == "sync"),
        }
