import networkx as nx
import re
from collections import defaultdict
from typing import List, Dict, Set
from nervapack.parser.ast_parser import ParsedEntity

_WORD_RE = re.compile(r'[a-zA-Z_]\w*')

class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._file_index: Dict[str, Set[str]] = defaultdict(set)

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
            self._file_index[entity.file_path].add(entity_node_id)

            # Edge from File -> Entity
            self.graph.add_edge(file_node_id, entity_node_id, relation="DEFINES", source="ast", confidence=1.0)

        # Heuristic cross-file name resolution
        # Group entities by their names (filtering out short names to avoid excessive false positives)
        entity_nodes_by_name: Dict[str, List[str]] = defaultdict(list)
        for entity in entities:
            if entity.name and len(entity.name) >= 4:
                entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
                entity_nodes_by_name[entity.name].append(entity_node_id)

        name_set: Set[str] = set(entity_nodes_by_name.keys())

        # For each entity, tokenize its content and find overlaps.
        # Intersect words with name_set first — reduces inner iterations by ~95%.
        for entity in entities:
            if not entity.content:
                continue

            entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
            words = set(_WORD_RE.findall(entity.content)) & name_set
            for word in words:
                if word == entity.name:
                    continue
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
        nodes_to_remove = list(self._file_index.pop(file_path, set()))
        file_node_id = f"file:{file_path}"
        if self.graph.has_node(file_node_id):
            nodes_to_remove.append(file_node_id)
        self.graph.remove_nodes_from(nodes_to_remove)
