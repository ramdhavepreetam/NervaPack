import networkx as nx
from typing import List
from nervapack.parser.ast_parser import ParsedEntity

class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_from_entities(self, entities: List[ParsedEntity]) -> nx.DiGraph:
        """
        Takes a list of ParsedEntity and constructs a directed graph.
        Files are nodes, entities are nodes. Contains/Defines edges connect them.
        """
        for entity in entities:
            # File Node
            file_node_id = f"file:{entity.file_path}"
            if not self.graph.has_node(file_node_id):
                self.graph.add_node(file_node_id, type="file", path=entity.file_path)

            # Entity Node
            # Unique ID for the entity
            entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
            self.graph.add_node(
                entity_node_id, 
                type=entity.type, 
                name=entity.name, 
                file_path=entity.file_path,
                start_line=entity.start_line,
                end_line=entity.end_line,
                content=entity.content
            )

            # Edge from File -> Entity
            self.graph.add_edge(file_node_id, entity_node_id, relation="DEFINES")

        return self.graph

    def save_graph(self, path: str = ".nervapack/graph.graphml"):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        nx.write_graphml(self.graph, path)

    def load_graph(self, path: str = ".nervapack/graph.graphml"):
        self.graph = nx.read_graphml(path)
        return self.graph

    def remove_nodes_for_file(self, file_path: str):
        """Removes the file node and all entities associated with it."""
        nodes_to_remove = []
        file_node_id = f"file:{file_path}"
        if self.graph.has_node(file_node_id):
            nodes_to_remove.append(file_node_id)
        
        for node, data in self.graph.nodes(data=True):
            if data.get("file_path") == file_path:
                nodes_to_remove.append(node)
                
        self.graph.remove_nodes_from(nodes_to_remove)
