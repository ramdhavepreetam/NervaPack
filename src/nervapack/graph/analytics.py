"""
Graph analytics and statistics module for NervaPack.

Provides helper functions for analyzing the knowledge graph structure,
computing metrics, and generating insights.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import networkx as nx


class GraphAnalytics:
    """Analyzes graph structure and computes various metrics."""

    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def get_node_counts_by_type(self) -> Dict[str, int]:
        """Return count of nodes by type (file, function, class, import, markdown)."""
        counts = Counter()
        for _, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            counts[node_type] += 1
        return dict(counts)

    def get_edge_counts_by_relation(self) -> Dict[str, int]:
        """Return count of edges by relation type (DEFINES, EXPLAINS)."""
        counts = Counter()
        for _, _, data in self.graph.edges(data=True):
            relation = data.get("relation", "unknown")
            counts[relation] += 1
        return dict(counts)

    def get_language_distribution(self) -> Dict[str, int]:
        """
        Return count of files by programming language based on file extensions.

        Returns:
            Dict mapping language name to file count
        """
        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".c": "C",
            ".h": "C",
            ".cpp": "C++",
            ".hpp": "C++",
            ".rb": "Ruby",
            ".cs": "C#",
            ".md": "Markdown",
        }

        counts = Counter()
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == "file":
                path = data.get("path", "")
                ext = Path(path).suffix.lower()
                lang = language_map.get(ext, f"Other{ext}")
                counts[lang] += 1

        return dict(counts)

    def get_most_connected_nodes(self, n: int = 10, node_type: Optional[str] = None) -> List[Tuple[str, int]]:
        """
        Return top N most connected nodes by degree.

        Args:
            n: Number of top nodes to return
            node_type: Optional filter by node type (e.g., "file", "function")

        Returns:
            List of (node_id, degree) tuples sorted by degree descending
        """
        all_degrees = dict(self.graph.degree())
        if node_type:
            degrees = [
                (nid, deg) for nid, deg in all_degrees.items()
                if self.graph.nodes[nid].get("type") == node_type
            ]
        else:
            degrees = list(all_degrees.items())
        degrees.sort(key=lambda x: x[1], reverse=True)
        return degrees[:n]

    def get_documentation_coverage(self) -> Dict[str, Any]:
        """
        Calculate documentation coverage - what percentage of code entities have EXPLAINS edges.

        Returns:
            Dict with 'documented', 'total', 'percentage', 'undocumented_nodes'
        """
        code_node_types = {"function", "class"}
        code_nodes = set()
        documented_nodes = set()

        # Find all code nodes
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") in code_node_types:
                code_nodes.add(node_id)

        # Find which code nodes have incoming EXPLAINS edges
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation") == "EXPLAINS":
                if v in code_nodes:
                    documented_nodes.add(v)

        total = len(code_nodes)
        documented = len(documented_nodes)
        percentage = (documented / total * 100) if total > 0 else 0
        undocumented = code_nodes - documented_nodes

        return {
            "documented": documented,
            "total": total,
            "percentage": percentage,
            "undocumented_nodes": list(undocumented),
        }

    def get_orphaned_nodes(self) -> List[str]:
        """
        Find orphaned nodes (nodes with no edges).

        Returns:
            List of node IDs that have no incoming or outgoing edges
        """
        return [nid for nid, deg in self.graph.degree() if deg == 0]

    def get_health_score(self) -> int:
        """
        Calculate overall graph health score (0-100).

        Factors:
        - Documentation coverage (40 points)
        - Node connectivity (30 points) - fewer orphaned nodes is better
        - Graph density (20 points)
        - Has both DEFINES and EXPLAINS edges (10 points)

        Returns:
            Integer score from 0 to 100
        """
        score = 0

        # Documentation coverage (40 points max)
        doc_coverage = self.get_documentation_coverage()
        score += int(doc_coverage["percentage"] * 0.4)

        # Node connectivity (30 points max)
        orphaned = self.get_orphaned_nodes()
        total_nodes = self.graph.number_of_nodes()
        if total_nodes > 0:
            connected_ratio = 1 - (len(orphaned) / total_nodes)
            score += int(connected_ratio * 30)

        # Graph density (20 points max)
        # Density = actual_edges / possible_edges
        n = total_nodes
        if n > 1:
            possible_edges = n * (n - 1)  # Directed graph
            actual_edges = self.graph.number_of_edges()
            density = min(actual_edges / possible_edges, 1.0)
            # We want some density but not too much (sweet spot around 0.01-0.1)
            # Scale appropriately
            normalized_density = min(density * 100, 1.0)  # Normalize to 0-1
            score += int(normalized_density * 20)

        # Has both edge types (10 points)
        edge_types = self.get_edge_counts_by_relation()
        if "DEFINES" in edge_types and "EXPLAINS" in edge_types:
            score += 10

        return min(score, 100)

    def get_file_display_name(self, node_id: str) -> str:
        """
        Get display name for a file node.

        Args:
            node_id: Node ID (usually file:<path>)

        Returns:
            Display name (file basename or shortened path)
        """
        node_data = self.graph.nodes.get(node_id, {})
        path = node_data.get("path") or node_data.get("file_path", node_id)
        return Path(path).name if path else node_id

    def get_degree_distribution(self) -> Dict[str, Any]:
        """
        Calculate degree distribution statistics.

        Returns:
            Dict with 'min', 'max', 'mean', 'median', 'histogram'
        """
        degrees = [self.graph.degree(node) for node in self.graph.nodes()]

        if not degrees:
            return {
                "min": 0,
                "max": 0,
                "mean": 0,
                "median": 0,
                "histogram": {},
            }

        degrees.sort()
        n = len(degrees)

        # Create histogram buckets
        histogram = Counter()
        for deg in degrees:
            # Bucket by powers of 2 for better visualization
            if deg == 0:
                bucket = "0"
            elif deg <= 2:
                bucket = "1-2"
            elif deg <= 5:
                bucket = "3-5"
            elif deg <= 10:
                bucket = "6-10"
            elif deg <= 20:
                bucket = "11-20"
            elif deg <= 50:
                bucket = "21-50"
            else:
                bucket = "50+"
            histogram[bucket] += 1

        return {
            "min": degrees[0],
            "max": degrees[-1],
            "mean": sum(degrees) / n,
            "median": degrees[n // 2],
            "histogram": dict(histogram),
        }

    def get_directory_stats(self) -> Dict[str, int]:
        """
        Get node counts by top-level directory.

        Returns:
            Dict mapping directory name to node count
        """
        dir_counts = Counter()

        for node_id, data in self.graph.nodes(data=True):
            path = data.get("path") or data.get("file_path", "")
            if path:
                # Get first directory component
                parts = Path(path).parts
                if len(parts) > 1:
                    top_dir = parts[0]
                    dir_counts[top_dir] += 1
                else:
                    dir_counts["<root>"] += 1

        return dict(dir_counts)

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive summary statistics for the graph.

        Returns:
            Dict containing all major statistics
        """
        return {
            "health_score": self.get_health_score(),
            "node_counts": self.get_node_counts_by_type(),
            "edge_counts": self.get_edge_counts_by_relation(),
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "languages": self.get_language_distribution(),
            "documentation_coverage": self.get_documentation_coverage(),
            "most_connected": self.get_most_connected_nodes(n=5),
            "orphaned_count": len(self.get_orphaned_nodes()),
            "degree_distribution": self.get_degree_distribution(),
        }


def format_percentage_bar(percentage: float, width: int = 20, filled_char: str = "█", empty_char: str = "░") -> str:
    """
    Format a percentage as a visual progress bar.

    Args:
        percentage: Percentage value (0-100)
        width: Total width of the bar in characters
        filled_char: Character for filled portion
        empty_char: Character for empty portion

    Returns:
        Formatted bar string
    """
    filled = int(percentage / 100 * width)
    empty = width - filled
    return filled_char * filled + empty_char * empty


def format_number(num: int) -> str:
    """Format large numbers with comma separators."""
    return f"{num:,}"
