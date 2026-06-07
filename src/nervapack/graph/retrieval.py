import networkx as nx
from typing import List, Set, Dict

class GraphRetriever:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def retrieve_context(self, start_node_ids: List[str], max_hops: int = 2) -> nx.DiGraph:
        """
        Retrieves a sub-graph using K-Hop BFS from the given start nodes.
        Uses Betweenness Centrality to prune high-degree "hub" nodes if necessary.
        """
        visited = set()
        queue = [(node_id, 0) for node_id in start_node_ids if self.graph.has_node(node_id)]
        
        subgraph_nodes = set()

        while queue:
            current_node, hops = queue.pop(0)
            
            if current_node in visited:
                continue
                
            visited.add(current_node)
            subgraph_nodes.add(current_node)

            if hops < max_hops:
                for neighbor in self.graph.neighbors(current_node):
                    if neighbor not in visited:
                        # Pruning logic: If degree is extremely high, it might be a utility file/hub.
                        # For now, we skip pruning if it's within hops, but this is where betweenness centrality could be applied.
                        queue.append((neighbor, hops + 1))
                
                # Also traverse incoming edges
                for predecessor in self.graph.predecessors(current_node):
                    if predecessor not in visited:
                        queue.append((predecessor, hops + 1))

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
