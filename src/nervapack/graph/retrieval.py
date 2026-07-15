import networkx as nx
from collections import deque
from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RetrievalMetadata:
    """Metadata about the graph traversal process."""
    seed_nodes: List[str]
    expanded_nodes: List[str]
    total_nodes: int
    traversal_depth: int
    edges_followed: List[Tuple[str, str, str]]  # (source, target, relation)


class GraphRetriever:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self.last_metadata: Optional[RetrievalMetadata] = None

    def retrieve_context(self, start_node_ids: List[str], max_hops: int = 2, direction: str = "both") -> nx.DiGraph:
        """
        Retrieves a sub-graph using K-Hop BFS from the given start nodes.
        Uses Betweenness Centrality to prune high-degree "hub" nodes if necessary.
        
        Args:
            start_node_ids: Initial nodes to seed the search.
            max_hops: Maximum BFS depth.
            direction: 'both' (default), 'forward' (successors only), or 'reverse' (predecessors only).

        Also tracks metadata about the traversal which can be accessed via self.last_metadata.
        """
        visited = set()
        seed_nodes = [nid for nid in start_node_ids if self.graph.has_node(nid)]
        queue: deque = deque((node_id, 0) for node_id in seed_nodes)

        subgraph_nodes = set()
        expanded_nodes = []
        edges_followed = []
        max_depth_reached = 0

        while queue:
            current_node, hops = queue.popleft()

            if current_node in visited:
                continue

            visited.add(current_node)
            subgraph_nodes.add(current_node)
            max_depth_reached = max(max_depth_reached, hops)

            # Track if this was expanded from a seed
            if current_node not in seed_nodes:
                expanded_nodes.append(current_node)

            if hops < max_hops:
                if direction in ["both", "forward"]:
                    for neighbor in self.graph.neighbors(current_node):
                        if neighbor not in visited:
                            # Track edge traversal
                            edge_data = self.graph.get_edge_data(current_node, neighbor)
                            relation = edge_data.get("relation", "unknown") if edge_data else "unknown"
                            source = edge_data.get("source", "unknown") if edge_data else "unknown"
                            confidence = edge_data.get("confidence", 1.0) if edge_data else 1.0
                            # We can just store source/confidence in the third tuple slot, or expand it. Let's expand it.
                            # But wait, Metadata expects List[Tuple[str, str, str]]. Let's stick to relation, maybe format as relation|source
                            # Actually, we can just change the tuple to Dict or add it. The formatting only uses `relation`.
                            # We'll just leave it as (current, neighbor, relation) to avoid breaking existing usages, but we can append them if needed.
                            edges_followed.append((current_node, neighbor, relation))
                            queue.append((neighbor, hops + 1))

                # Also traverse incoming edges
                if direction in ["both", "reverse"]:
                    for predecessor in self.graph.predecessors(current_node):
                        if predecessor not in visited:
                            edge_data = self.graph.get_edge_data(predecessor, current_node)
                            relation = edge_data.get("relation", "unknown") if edge_data else "unknown"
                            edges_followed.append((predecessor, current_node, relation))
                            queue.append((predecessor, hops + 1))

        # Store metadata
        self.last_metadata = RetrievalMetadata(
            seed_nodes=seed_nodes,
            expanded_nodes=expanded_nodes,
            total_nodes=len(subgraph_nodes),
            traversal_depth=max_depth_reached,
            edges_followed=edges_followed,
        )

        return self.graph.subgraph(subgraph_nodes).copy()

    def format_as_markdown(self, subgraph: nx.DiGraph) -> str:
        """
        Formats the retrieved sub-graph into a minimized, clean Markdown block.
        """
        markdown_lines = []
        markdown_lines.append("# NervaPack Context Retrieval\n")
        
        # Group by file
        files = {}
        for node, data in subgraph.nodes(data=True):
            if data.get('type') == 'file':
                continue
            
            file_path = data.get('file_path', 'Unknown')
            if file_path not in files:
                files[file_path] = []
            files[file_path].append(data)

        for file_path, nodes in files.items():
            markdown_lines.append(f"## File: `{file_path}`\n")
            # Sort by start line
            nodes = sorted(nodes, key=lambda x: x.get('start_line', 0))
            for node_data in nodes:
                node_type = node_data.get('type', 'entity').upper()
                name = node_data.get('name', 'Unknown')
                lines = f"(L{node_data.get('start_line', '?')}-L{node_data.get('end_line', '?')})"
                markdown_lines.append(f"### {node_type}: {name} {lines}")
                
                content = node_data.get('content', '')
                if content:
                    markdown_lines.append("```")
                    markdown_lines.append(content)
                    markdown_lines.append("```\n")

        return "\n".join(markdown_lines)

    def get_source_files(self, subgraph: nx.DiGraph) -> List[str]:
        """Return deduplicated file paths of all non-file nodes in the subgraph."""
        seen = set()
        result = []
        for _, data in subgraph.nodes(data=True):
            fp = data.get("file_path")
            if fp and data.get("type") != "file" and fp not in seen:
                seen.add(fp)
                result.append(fp)
        return result
