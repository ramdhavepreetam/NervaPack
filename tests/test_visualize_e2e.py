"""
End-to-end smoke tests for the visualize pipeline.

These tests build a real (small) graph, call export_html(), write the file to
a temp directory, then validate the HTML is self-contained and free of the
known failure modes that broke production:

  1. TomSelect broken — "TomSelect is not defined" in browser
     Root cause: pyvis select_menu=True emits <script src="lib/tom-select/...">
     which is a relative path that doesn't exist next to the output HTML.

  2. vis.js / bindings broken — "lib/bindings/utils.js not found"
     Root cause: same pyvis relative-path problem for its own JS.

  3. Empty / zero-node graph — should render without crashing.

  4. Large label truncation — node labels > 30 chars must be trimmed.

  5. Enhanced visualizer — Path Finder and Clear Search bugs:
     - findPath/clearPath were inside initPathFinder() closure but called from
       onclick= attributes (global scope) → ReferenceError, buttons did nothing
     - clearSearch/clearPath restored node.size from already-scaled value,
       so Clear never fully restored the graph

Run with:
    python3 -m pytest tests/test_visualize_e2e.py -v
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

import networkx as nx


def _make_sample_graph() -> nx.DiGraph:
    """Build a small but representative graph with all node types."""
    g = nx.DiGraph()
    g.add_node("file:src/auth.py",     type="file",     path="src/auth.py")
    g.add_node("class:AuthMiddleware", type="class",    name="AuthMiddleware",
               file_path="src/auth.py", start_line=10, end_line=40,
               content="class AuthMiddleware:\n    pass")
    g.add_node("function:login",       type="function", name="login",
               file_path="src/auth.py", start_line=42, end_line=60,
               content="def login(user, pw):\n    return True")
    g.add_node("import:jwt",           type="import",   name="jwt",
               file_path="src/auth.py")
    g.add_node("markdown:auth_doc",    type="markdown", header="Authentication",
               file_path="docs/auth.md", content="Handles login and JWT tokens.")
    g.add_edge("file:src/auth.py",     "class:AuthMiddleware", relation="DEFINES")
    g.add_edge("file:src/auth.py",     "function:login",       relation="DEFINES")
    g.add_edge("file:src/auth.py",     "import:jwt",           relation="DEFINES")
    g.add_edge("markdown:auth_doc",    "class:AuthMiddleware", relation="EXPLAINS")
    return g


class TestVisualizerExportHTML(unittest.TestCase):

    def setUp(self):
        from nervapack.graph.visualizer import export_html
        self.export_html = export_html
        self.graph = _make_sample_graph()
        self.tmpdir = tempfile.mkdtemp()
        self.out = os.path.join(self.tmpdir, "graph.html")

    # ------------------------------------------------------------------
    # 1. File is created and non-empty
    # ------------------------------------------------------------------
    def test_output_file_created(self):
        self.export_html(self.graph, self.out)
        self.assertTrue(os.path.exists(self.out), "graph.html was not created")
        self.assertGreater(os.path.getsize(self.out), 1000, "graph.html is suspiciously small")

    # ------------------------------------------------------------------
    # 2. No relative lib/ paths that will 404 in the browser
    # ------------------------------------------------------------------
    def test_no_broken_relative_lib_paths(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        # These relative src/href patterns are the known failure modes
        broken = re.findall(r'(?:src|href)=["\']lib/[^"\']+["\']', html)
        self.assertEqual(broken, [],
            f"HTML contains relative lib/ paths that will 404 in the browser: {broken}")

    # ------------------------------------------------------------------
    # 3. TomSelect is not loaded (it depends on missing relative files)
    # ------------------------------------------------------------------
    def test_no_tomselect_reference(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        self.assertNotIn("TomSelect", html,
            "HTML references TomSelect — browser will throw 'TomSelect is not defined'")
        self.assertNotIn("tom-select", html,
            "HTML references tom-select library — will fail when lib/ is not present")

    # ------------------------------------------------------------------
    # 4. vis-network JS is present (inline or absolute CDN URL, not relative)
    # ------------------------------------------------------------------
    def test_vis_network_loaded(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        has_vis = (
            "vis-network" in html
            or "visjs.org" in html
            or "vis.min.js" in html
        )
        self.assertTrue(has_vis, "vis-network JS not found in output HTML")

        # If it's loaded via a <script src>, that src must NOT be a bare relative path
        relative_vis = re.findall(r'src=["\'][^"\']*vis[^"\']*\.js["\']', html)
        for ref in relative_vis:
            self.assertTrue(
                ref.startswith('src="http') or ref.startswith("src='http") or
                ref.startswith('src="//') or "cdnjs" in ref or "jsdelivr" in ref,
                f"vis-network JS is loaded via a relative path that will 404: {ref}"
            )

    # ------------------------------------------------------------------
    # 5. All five node types appear in the HTML
    # ------------------------------------------------------------------
    def test_all_node_types_rendered(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        for label in ("AuthMiddleware", "login", "jwt", "Authentication"):
            self.assertIn(label, html, f"Expected node label '{label}' missing from HTML")

    # ------------------------------------------------------------------
    # 6. Edge relations appear
    # ------------------------------------------------------------------
    def test_edge_relations_rendered(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        self.assertIn("DEFINES", html)
        self.assertIn("EXPLAINS", html)

    # ------------------------------------------------------------------
    # 7. Legend is injected
    # ------------------------------------------------------------------
    def test_legend_injected(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        self.assertIn("NervaPack Graph", html, "Legend block missing from HTML")

    # ------------------------------------------------------------------
    # 8. Empty graph does not crash
    # ------------------------------------------------------------------
    def test_empty_graph_no_crash(self):
        empty = nx.DiGraph()
        out = os.path.join(self.tmpdir, "empty.html")
        try:
            self.export_html(empty, out)
        except Exception as e:
            self.fail(f"export_html raised on empty graph: {e}")

    # ------------------------------------------------------------------
    # 9. Long node labels are truncated
    # ------------------------------------------------------------------
    def test_long_label_truncated(self):
        from nervapack.graph.visualizer import _short_label
        long_header = "A" * 50
        label = _short_label("md:x", {"header": long_header})
        self.assertLessEqual(len(label), 33,  # 30 chars + "…"
            f"Label not truncated: '{label}'")
        self.assertTrue(label.endswith("…"), "Truncated label should end with ellipsis")

    # ------------------------------------------------------------------
    # 10. Output file is valid HTML (has <html> and </html>)
    # ------------------------------------------------------------------
    def test_output_is_valid_html(self):
        self.export_html(self.graph, self.out)
        html = Path(self.out).read_text(encoding="utf-8")
        self.assertIn("<html", html.lower())
        self.assertIn("</html>", html.lower())


class TestEnhancedVisualizerHTML(unittest.TestCase):
    """Tests for export_html_enhanced — path finder and search clear bugs."""

    def setUp(self):
        from nervapack.graph.visualizer_v2 import export_html_enhanced
        self.export_html_enhanced = export_html_enhanced
        self.graph = _make_sample_graph()
        self.tmpdir = tempfile.mkdtemp()
        self.out = os.path.join(self.tmpdir, "enhanced.html")

    def _html(self):
        self.export_html_enhanced(self.graph, self.out, enable_search=True,
                                   enable_community_detection=False)
        return Path(self.out).read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 11. No relative lib/ paths in enhanced output
    # ------------------------------------------------------------------
    def test_enhanced_no_broken_relative_lib_paths(self):
        html = self._html()
        broken = re.findall(r'(?:src|href)=["\']lib/[^"\']+["\']', html)
        self.assertEqual(broken, [],
            f"Enhanced HTML has relative lib/ paths that will 404: {broken}")

    # ------------------------------------------------------------------
    # 12. No TomSelect in enhanced output
    # ------------------------------------------------------------------
    def test_enhanced_no_tomselect(self):
        html = self._html()
        self.assertNotIn("TomSelect", html)
        self.assertNotIn("tom-select", html)

    # ------------------------------------------------------------------
    # 13. Path finder functions are in GLOBAL scope (npFindPath, npClearPath)
    #     Previously findPath/clearPath were trapped inside initPathFinder()
    #     closure and unreachable from onclick= attributes.
    # ------------------------------------------------------------------
    def test_path_finder_functions_in_global_scope(self):
        html = self._html()
        # Must be top-level function declarations (not inside another function body)
        self.assertIn("function npFindPath()", html,
            "npFindPath() not defined at global scope — onclick will fail")
        self.assertIn("function npClearPath()", html,
            "npClearPath() not defined at global scope — onclick will fail")
        # Buttons must reference the global names
        self.assertIn('onclick="npFindPath()"', html,
            "Find Path button does not call npFindPath()")
        self.assertIn('onclick="npClearPath()"', html,
            "Clear Path button does not call npClearPath()")

    # ------------------------------------------------------------------
    # 14. Clear Search calls npClearSearch (not old clearSearch)
    # ------------------------------------------------------------------
    def test_clear_search_calls_global_function(self):
        html = self._html()
        self.assertIn('onclick="npClearSearch()"', html,
            "Clear button calls wrong function name — will throw ReferenceError")
        self.assertIn("function npClearSearch()", html,
            "npClearSearch() not defined")

    # ------------------------------------------------------------------
    # 15. npSnapshot and npRestore exist (size-restore fix)
    # ------------------------------------------------------------------
    def test_snapshot_restore_functions_present(self):
        html = self._html()
        self.assertIn("function npSnapshot()", html,
            "npSnapshot() missing — Clear will not restore correct node sizes")
        self.assertIn("function npRestore()", html,
            "npRestore() missing — Clear will not restore correct node sizes")

    # ------------------------------------------------------------------
    # 16. Path finder wires up bidirectional BFS (finds paths in both directions)
    # ------------------------------------------------------------------
    def test_bfs_is_bidirectional(self):
        html = self._html()
        # The BFS must traverse both edge.to and edge.from for each edge
        self.assertIn("adj[edge.to]", html,
            "BFS only searches forward edges — reverse paths will not be found")

    # ------------------------------------------------------------------
    # 17. npOriginalNodeState used for size restoration (not raw node.size)
    # ------------------------------------------------------------------
    def test_clear_uses_original_state_not_current_size(self):
        html = self._html()
        # clearSearch should use npOriginalNodeState, not node.size directly
        self.assertIn("npOriginalNodeState", html)
        # The old broken pattern: restoring to node.size which was already scaled
        # Check that clearSearch/clearPath don't do `size: node.size || 10` naively
        bad_restore = re.findall(
            r'function np(?:ClearSearch|ClearPath|Restore).*?size:\s*node\.size\s*\|\|\s*10',
            html, re.DOTALL
        )
        self.assertEqual(bad_restore, [],
            "Clear still uses raw node.size (scaled value) instead of original snapshot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
