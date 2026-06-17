"""
Dependency Graph Analyzer - Analyze import dependencies and detect circular dependencies.
"""

import networkx as nx
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
from collections import defaultdict


class DependencyAnalyzer:
    """Analyze import dependencies in the codebase."""

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the dependency analyzer.

        Args:
            graph: The full NervaPack knowledge graph
        """
        self.graph = graph
        self.dependency_graph: Optional[nx.DiGraph] = None

    def build_dependency_graph(self) -> nx.DiGraph:
        """
        Build a file-level dependency graph from import edges.

        Returns:
            A directed graph where nodes are files and edges represent imports
        """
        dep_graph = nx.DiGraph()

        # Collect all files first
        files = set()
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == "file":
                file_path = data.get("path") or data.get("file_path")
                if file_path:
                    files.add(file_path)
            elif data.get("file_path"):
                files.add(data["file_path"])

        # Add all files as nodes
        for file_path in files:
            dep_graph.add_node(file_path, label=Path(file_path).name)

        # Build edges from import relationships
        # Strategy: Look for import nodes and trace back to their source files
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == "import":
                source_file = data.get("file_path")

                # The import node's content might contain the target module/file
                # For now, we look at edges to find what this import connects to
                for successor in self.graph.successors(node_id):
                    succ_data = self.graph.nodes.get(successor, {})
                    target_file = succ_data.get("file_path")

                    if source_file and target_file and source_file != target_file:
                        # Add dependency edge: source_file depends on target_file
                        if not dep_graph.has_edge(source_file, target_file):
                            dep_graph.add_edge(source_file, target_file)

                # Also check predecessors (in case the graph is structured differently)
                for predecessor in self.graph.predecessors(node_id):
                    pred_data = self.graph.nodes.get(predecessor, {})

                    # If predecessor is a file node, it depends on the import's target
                    if pred_data.get("type") == "file":
                        source_file = pred_data.get("path") or pred_data.get("file_path")

                        # Find what the import points to
                        for succ in self.graph.successors(node_id):
                            succ_data = self.graph.nodes.get(succ, {})
                            target_file = succ_data.get("file_path")

                            if source_file and target_file and source_file != target_file:
                                if not dep_graph.has_edge(source_file, target_file):
                                    dep_graph.add_edge(source_file, target_file)

        self.dependency_graph = dep_graph
        return dep_graph

    def detect_circular_dependencies(self) -> List[List[str]]:
        """
        Detect circular dependencies in the codebase.

        Returns:
            List of cycles, where each cycle is a list of file paths
        """
        if self.dependency_graph is None:
            self.build_dependency_graph()

        try:
            cycles = list(nx.simple_cycles(self.dependency_graph))
            return cycles
        except Exception:
            return []

    def get_dependency_metrics(self) -> Dict:
        """
        Calculate dependency metrics.

        Returns:
            Dictionary containing:
                - total_files: Total number of files
                - total_dependencies: Total number of dependency edges
                - max_depth: Maximum dependency chain length
                - orphan_files: Files with no dependencies
                - most_depended_on: Top 10 files that are most depended on
                - most_dependencies: Top 10 files with most dependencies (imports)
        """
        if self.dependency_graph is None:
            self.build_dependency_graph()

        g = self.dependency_graph

        # Basic counts
        total_files = g.number_of_nodes()
        total_dependencies = g.number_of_edges()

        # Find orphan files (no incoming or outgoing edges)
        orphan_files = [
            node for node in g.nodes()
            if g.in_degree(node) == 0 and g.out_degree(node) == 0
        ]

        # Most depended on (highest in-degree)
        in_degrees = [(node, g.in_degree(node)) for node in g.nodes()]
        most_depended_on = sorted(in_degrees, key=lambda x: x[1], reverse=True)[:10]

        # Most dependencies (highest out-degree)
        out_degrees = [(node, g.out_degree(node)) for node in g.nodes()]
        most_dependencies = sorted(out_degrees, key=lambda x: x[1], reverse=True)[:10]

        # Calculate max depth (longest path)
        max_depth = 0
        if nx.is_directed_acyclic_graph(g):
            try:
                # For DAGs, we can compute longest path
                for node in g.nodes():
                    try:
                        lengths = nx.single_source_shortest_path_length(g, node)
                        if lengths:
                            max_depth = max(max_depth, max(lengths.values()))
                    except Exception:
                        pass
            except Exception:
                max_depth = 0
        else:
            # If there are cycles, approximate with average path length
            try:
                # Use diameter or radius
                if nx.is_weakly_connected(g):
                    # Get largest weakly connected component
                    largest_cc = max(nx.weakly_connected_components(g), key=len)
                    subgraph = g.subgraph(largest_cc)
                    # Try to get longest shortest path
                    max_depth = nx.diameter(subgraph.to_undirected())
            except Exception:
                max_depth = 0

        return {
            "total_files": total_files,
            "total_dependencies": total_dependencies,
            "max_depth": max_depth,
            "orphan_files": orphan_files,
            "most_depended_on": most_depended_on,
            "most_dependencies": most_dependencies,
        }

    def get_file_dependencies(self, file_path: str) -> Tuple[List[str], List[str]]:
        """
        Get dependencies for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (imports, imported_by) lists
        """
        if self.dependency_graph is None:
            self.build_dependency_graph()

        g = self.dependency_graph

        # Files this file imports
        imports = list(g.successors(file_path)) if g.has_node(file_path) else []

        # Files that import this file
        imported_by = list(g.predecessors(file_path)) if g.has_node(file_path) else []

        return imports, imported_by

    def export_dependency_graph_html(
        self,
        output_path: str,
        enable_layers: bool = True,
        highlight_cycles: bool = True,
    ) -> None:
        """
        Export dependency graph as interactive HTML visualization.

        Args:
            output_path: Path to save HTML file
            enable_layers: Use hierarchical layout based on dependency depth
            highlight_cycles: Highlight nodes involved in circular dependencies
        """
        if self.dependency_graph is None:
            self.build_dependency_graph()

        from pyvis.network import Network

        g = self.dependency_graph

        # Detect cycles if needed
        cycles = []
        nodes_in_cycles = set()
        if highlight_cycles:
            cycles = self.detect_circular_dependencies()
            for cycle in cycles:
                nodes_in_cycles.update(cycle)

        # Create pyvis network
        net = Network(
            height="800px",
            width="100%",
            directed=True,
            bgcolor="#1a1a1a",
            font_color="white",
        )

        # Configure physics
        net.set_options("""
        {
            "physics": {
                "enabled": true,
                "hierarchicalRepulsion": {
                    "centralGravity": 0.0,
                    "springLength": 200,
                    "springConstant": 0.01,
                    "nodeDistance": 250,
                    "damping": 0.09
                },
                "solver": "hierarchicalRepulsion"
            },
            "layout": {
                "hierarchical": {
                    "enabled": %s,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "levelSeparation": 200,
                    "nodeSpacing": 150
                }
            },
            "edges": {
                "arrows": {
                    "to": {
                        "enabled": true,
                        "scaleFactor": 0.5
                    }
                },
                "smooth": {
                    "enabled": true,
                    "type": "cubicBezier"
                }
            }
        }
        """ % ("true" if enable_layers else "false"))

        # Add nodes
        for node in g.nodes():
            file_name = Path(node).name
            in_deg = g.in_degree(node)
            out_deg = g.out_degree(node)

            # Determine color
            if node in nodes_in_cycles:
                color = "#FF6B6B"  # Red for cycles
                border_color = "#FF0000"
            elif in_deg > 5:
                color = "#4ECDC4"  # Cyan for heavily depended on
                border_color = "#3DBDB4"
            elif out_deg > 5:
                color = "#FFD93D"  # Yellow for files with many dependencies
                border_color = "#FFC93D"
            elif in_deg == 0 and out_deg == 0:
                color = "#6C757D"  # Gray for orphans
                border_color = "#5C656D"
            else:
                color = "#95E1D3"  # Light green for normal
                border_color = "#85D1C3"

            # Size based on degree
            total_degree = in_deg + out_deg
            size = 20 + min(total_degree * 3, 40)

            title = f"<b>{file_name}</b><br>"
            title += f"Full path: {node}<br>"
            title += f"Imported by: {in_deg} file(s)<br>"
            title += f"Imports: {out_deg} file(s)"

            if node in nodes_in_cycles:
                title += "<br><b style='color: #FF6B6B'>⚠ Part of circular dependency</b>"

            net.add_node(
                node,
                label=file_name,
                title=title,
                color={"background": color, "border": border_color},
                size=size,
            )

        # Add edges
        for source, target in g.edges():
            # Check if this edge is part of a cycle
            is_cycle_edge = False
            if highlight_cycles:
                for cycle in cycles:
                    if source in cycle and target in cycle:
                        # Check if this specific edge is in the cycle
                        cycle_idx_source = cycle.index(source)
                        cycle_idx_target = (cycle_idx_source + 1) % len(cycle)
                        if cycle[cycle_idx_target] == target:
                            is_cycle_edge = True
                            break

            edge_color = "#FF6B6B" if is_cycle_edge else "#666666"
            edge_width = 3 if is_cycle_edge else 1

            net.add_edge(
                source,
                target,
                color=edge_color,
                width=edge_width,
            )

        # Build custom UI
        html = net.generate_html()

        # Add custom CSS and controls
        custom_ui = """
        <style>
            #np-dep-controls {
                position: absolute;
                top: 10px;
                left: 10px;
                background: rgba(26, 26, 26, 0.95);
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #4ECDC4;
                font-family: 'Monaco', 'Courier New', monospace;
                color: white;
                max-width: 300px;
                z-index: 1000;
            }
            #np-dep-controls h3 {
                margin: 0 0 10px 0;
                color: #4ECDC4;
                font-size: 14px;
            }
            #np-dep-controls .metric {
                margin: 5px 0;
                font-size: 12px;
            }
            #np-dep-controls .metric-label {
                color: #95E1D3;
                font-weight: bold;
            }
            #np-dep-controls .metric-value {
                color: white;
                float: right;
            }
            #np-dep-controls .legend {
                margin-top: 15px;
                padding-top: 10px;
                border-top: 1px solid #444;
            }
            #np-dep-controls .legend-item {
                display: flex;
                align-items: center;
                margin: 5px 0;
                font-size: 11px;
            }
            #np-dep-controls .legend-color {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            #np-search-box {
                width: 100%;
                padding: 6px;
                margin-top: 10px;
                background: #2a2a2a;
                border: 1px solid #4ECDC4;
                border-radius: 4px;
                color: white;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 11px;
            }
            #np-search-box::placeholder {
                color: #888;
            }
        </style>

        <div id="np-dep-controls">
            <h3>📦 Dependency Graph</h3>
            <div class="metric">
                <span class="metric-label">Files:</span>
                <span class="metric-value" id="total-files">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Dependencies:</span>
                <span class="metric-value" id="total-deps">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Circular Deps:</span>
                <span class="metric-value" id="cycle-count">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Max Depth:</span>
                <span class="metric-value" id="max-depth">0</span>
            </div>

            <input type="text" id="np-search-box" placeholder="Search files..." onkeyup="searchDependencies()">

            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #FF6B6B;"></div>
                    <span>Circular dependency</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4ECDC4;"></div>
                    <span>Heavily depended on</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #FFD93D;"></div>
                    <span>Many dependencies</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #95E1D3;"></div>
                    <span>Normal file</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #6C757D;"></div>
                    <span>Orphan (isolated)</span>
                </div>
            </div>
        </div>

        <script type="text/javascript">
            // Update metrics
            document.getElementById('total-files').textContent = nodes.length;
            document.getElementById('total-deps').textContent = edges.length;

            // Count cycles
            const cycleNodes = nodes.filter(n => n.color.background === '#FF6B6B').length;
            document.getElementById('cycle-count').textContent = cycleNodes > 0 ? 'Yes (' + cycleNodes + ' files)' : 'None';

            // Search functionality
            function searchDependencies() {
                const searchTerm = document.getElementById('np-search-box').value.toLowerCase();

                if (searchTerm === '') {
                    // Reset all nodes
                    nodes.forEach(node => {
                        network.body.data.nodes.update({
                            id: node.id,
                            opacity: 1.0,
                            font: {size: 14}
                        });
                    });
                    return;
                }

                // Dim non-matching nodes
                nodes.forEach(node => {
                    const label = node.label.toLowerCase();
                    const id = node.id.toLowerCase();
                    const matches = label.includes(searchTerm) || id.includes(searchTerm);

                    network.body.data.nodes.update({
                        id: node.id,
                        opacity: matches ? 1.0 : 0.2,
                        font: {size: matches ? 16 : 14}
                    });
                });
            }
        </script>
        """

        # Insert custom UI before closing body tag
        html = html.replace("</body>", custom_ui + "</body>")

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
