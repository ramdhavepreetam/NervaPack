import networkx as nx
import re
from collections import defaultdict
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
            self.graph.add_edge(file_node_id, entity_node_id, relation="DEFINES", source="ast", confidence=1.0)

        # Heuristic cross-file name resolution
        # Group entities by their names (filtering out short names to avoid excessive false positives)
        entity_nodes_by_name = defaultdict(list)
        for entity in entities:
            if entity.name and len(entity.name) >= 4:
                entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
                entity_nodes_by_name[entity.name].append(entity_node_id)
                
        # For each entity, tokenize its content and find overlaps
        for entity in entities:
            if not entity.content:
                continue
                
            entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
            # Extract alphanumeric/underscore word tokens
            words = set(re.findall(r'[a-zA-Z_]\w*', entity.content))
            for word in words:
                if word in entity_nodes_by_name and word != entity.name:
                    for target_id in entity_nodes_by_name[word]:
                        if target_id != entity_node_id:
                            self.graph.add_edge(
                                entity_node_id, 
                                target_id, 
                                relation="REFERENCES", 
                                source="heuristic", 
                                confidence=0.7
                            )

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
