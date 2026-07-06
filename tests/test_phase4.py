"""Tests for Phase 4 analytics: hotspots and graph evolution history."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestHotspotAnalyzer(unittest.TestCase):

    def _make_numstat_output(self):
        # Simulate `git log --numstat --pretty=format:` output
        return "\n".join([
            "10\t2\tsrc/main.py",
            "5\t1\tsrc/main.py",
            "3\t0\tsrc/utils.py",
            "",
            "20\t5\tsrc/main.py",
            "-\t-\tbinary.bin",   # binary — must be skipped
            "1\t1\tsrc/utils.py",
        ])

    def test_get_hotspots_ranking(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=self._make_numstat_output()):
            with patch.object(analyzer, "is_git_repo", return_value=True):
                hotspots = analyzer.get_hotspots(limit=10)

        self.assertEqual(len(hotspots), 2)
        # main.py should rank first with 3 changes
        self.assertEqual(hotspots[0].file_path, "src/main.py")
        self.assertEqual(hotspots[0].change_count, 3)
        self.assertEqual(hotspots[1].file_path, "src/utils.py")
        self.assertEqual(hotspots[1].change_count, 2)

    def test_get_hotspots_churn_values(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=self._make_numstat_output()):
            hotspots = analyzer.get_hotspots(limit=10)

        main_py = next(h for h in hotspots if h.file_path == "src/main.py")
        # insertions: 10+5+20=35, deletions: 2+1+5=8
        self.assertEqual(main_py.insertions, 35)
        self.assertEqual(main_py.deletions, 8)
        self.assertEqual(main_py.churn_score, 43.0)

    def test_binary_files_skipped(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=self._make_numstat_output()):
            hotspots = analyzer.get_hotspots(limit=10)

        paths = [h.file_path for h in hotspots]
        self.assertNotIn("binary.bin", paths)

    def test_extension_filter(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        output = "\n".join([
            "5\t1\tsrc/app.py",
            "3\t0\tsrc/style.css",
            "2\t1\tsrc/app.py",
        ])
        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=output):
            hotspots = analyzer.get_hotspots(limit=10, extensions=[".py"])

        paths = [h.file_path for h in hotspots]
        self.assertIn("src/app.py", paths)
        self.assertNotIn("src/style.css", paths)

    def test_limit_respected(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        lines = "\n".join(f"1\t0\tsrc/file{i}.py" for i in range(50))
        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=lines):
            hotspots = analyzer.get_hotspots(limit=5)

        self.assertEqual(len(hotspots), 5)

    def test_empty_output(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=""):
            hotspots = analyzer.get_hotspots()

        self.assertEqual(hotspots, [])

    def test_get_hotspot_summary_structure(self):
        from nervapack.graph.hotspots import HotspotAnalyzer

        analyzer = HotspotAnalyzer()
        with patch.object(analyzer, "_run_git", return_value=self._make_numstat_output()):
            summary = analyzer.get_hotspot_summary(limit=10, since="6 months ago")

        self.assertIn("hotspots", summary)
        self.assertIn("total_files_analyzed", summary)
        self.assertEqual(summary["since"], "6 months ago")
        for entry in summary["hotspots"]:
            self.assertIn("file_path", entry)
            self.assertIn("change_count", entry)
            self.assertIn("churn_score", entry)


class TestGraphHistory(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.tmpdir, "graph_history.jsonl")

    def _make_history(self):
        from nervapack.graph.graph_history import GraphHistory
        return GraphHistory(history_file=self.history_file)

    def test_record_and_retrieve(self):
        gh = self._make_history()
        gh.record(
            trigger="ingest",
            total_nodes=100,
            total_edges=80,
            health_score=75,
            node_counts={"file": 10, "function": 90},
            edge_counts={"DEFINES": 80},
            doc_coverage_pct=45.0,
            orphaned_count=3,
            files_changed=0,
        )
        snaps = gh.get_all()
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].total_nodes, 100)
        self.assertEqual(snaps[0].trigger, "ingest")
        self.assertEqual(snaps[0].health_score, 75)

    def test_multiple_records_ordered(self):
        gh = self._make_history()
        for i in range(3):
            gh.record(
                trigger="sync",
                total_nodes=100 + i * 10,
                total_edges=80,
                health_score=70,
                node_counts={},
                edge_counts={},
                doc_coverage_pct=50.0,
                orphaned_count=0,
                files_changed=i + 1,
            )
        snaps = gh.get_all()
        self.assertEqual(len(snaps), 3)
        # Oldest first
        self.assertEqual(snaps[0].total_nodes, 100)
        self.assertEqual(snaps[2].total_nodes, 120)

    def test_get_recent_limit(self):
        gh = self._make_history()
        for i in range(10):
            gh.record(
                trigger="ingest",
                total_nodes=i,
                total_edges=0,
                health_score=50,
                node_counts={},
                edge_counts={},
                doc_coverage_pct=0.0,
                orphaned_count=0,
            )
        recent = gh.get_recent(limit=3)
        self.assertEqual(len(recent), 3)
        # get_recent returns last N (newest last)
        self.assertEqual(recent[-1].total_nodes, 9)

    def test_get_statistics_empty(self):
        gh = self._make_history()
        stats = gh.get_statistics()
        self.assertEqual(stats["total_snapshots"], 0)
        self.assertIsNone(stats["first_snapshot"])

    def test_get_statistics_populated(self):
        gh = self._make_history()
        gh.record(
            trigger="ingest",
            total_nodes=50, total_edges=40, health_score=60,
            node_counts={}, edge_counts={}, doc_coverage_pct=30.0, orphaned_count=0,
        )
        gh.record(
            trigger="sync",
            total_nodes=80, total_edges=70, health_score=75,
            node_counts={}, edge_counts={}, doc_coverage_pct=50.0, orphaned_count=0,
        )
        stats = gh.get_statistics()
        self.assertEqual(stats["total_snapshots"], 2)
        self.assertEqual(stats["node_growth"], 30)
        self.assertEqual(stats["edge_growth"], 30)
        self.assertEqual(stats["ingest_count"], 1)
        self.assertEqual(stats["sync_count"], 1)

    def test_record_from_analytics(self):
        from nervapack.graph.graph_history import GraphHistory

        mock_analytics = MagicMock()
        mock_analytics.get_summary_stats.return_value = {
            "total_nodes": 200,
            "total_edges": 150,
            "health_score": 82,
            "node_counts": {"file": 20},
            "edge_counts": {"DEFINES": 150},
            "documentation_coverage": {"percentage": 60.0},
            "orphaned_count": 5,
        }

        gh = GraphHistory(history_file=self.history_file)
        gh.record_from_analytics(mock_analytics, trigger="ingest", files_changed=7)

        snaps = gh.get_all()
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].total_nodes, 200)
        self.assertEqual(snaps[0].doc_coverage_pct, 60.0)
        self.assertEqual(snaps[0].files_changed, 7)

    def test_malformed_lines_skipped(self):
        gh = self._make_history()
        # Write one valid and one malformed line
        with open(self.history_file, "w") as f:
            f.write('{"not": "a snapshot"}\n')
            f.write('not json at all\n')
        snaps = gh.get_all()
        self.assertEqual(len(snaps), 0)


if __name__ == "__main__":
    unittest.main()
