import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser, Node

@dataclass
class ParsedEntity:
    name: str
    type: str  # 'class', 'function', 'import', 'export'
    file_path: str
    start_line: int
    end_line: int
    content: str
    metadata: Dict[str, Any]

class ASTParser:
    def __init__(self):
        self.languages = {
            ".py": Language(tree_sitter_python.language()),
            ".js": Language(tree_sitter_javascript.language()),
            ".jsx": Language(tree_sitter_javascript.language()),
            ".ts": Language(tree_sitter_typescript.language_typescript()),
            ".tsx": Language(tree_sitter_typescript.language_tsx())
        }
        self.parsers = {}
        for ext, lang in self.languages.items():
            parser = Parser(lang)
            self.parsers[ext] = parser

    def parse_file(self, file_path: str) -> List[ParsedEntity]:
        ext = Path(file_path).suffix
        if ext not in self.parsers:
            return []

        with open(file_path, "rb") as f:
            content_bytes = f.read()

        tree = self.parsers[ext].parse(content_bytes)
        entities = []
        self._traverse_tree(tree.root_node, content_bytes, file_path, ext, entities)
        return entities

    def _traverse_tree(self, node: Node, content_bytes: bytes, file_path: str, ext: str, entities: List[ParsedEntity]):
        # Simple extraction logic for Python and JS/TS
        if node.type in ["class_definition", "class_declaration"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf8")
                entities.append(self._create_entity(name, "class", node, content_bytes, file_path))
        
        elif node.type in ["function_definition", "function_declaration", "method_definition"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode("utf8")
                entities.append(self._create_entity(name, "function", node, content_bytes, file_path))
        
        elif node.type in ["import_statement", "import_from_statement", "import_declaration"]:
            # For simplicity, extract the entire import block as an entity for the graph
            name = f"import_{node.start_point[0]}"
            entities.append(self._create_entity(name, "import", node, content_bytes, file_path))

        for child in node.children:
            self._traverse_tree(child, content_bytes, file_path, ext, entities)

    def _create_entity(self, name: str, entity_type: str, node: Node, content_bytes: bytes, file_path: str) -> ParsedEntity:
        return ParsedEntity(
            name=name,
            type=entity_type,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=node.text.decode("utf8"),
            metadata={}
        )

def scan_directory(directory: str) -> List[ParsedEntity]:
    parser = ASTParser()
    all_entities = []
    for root, _, files in os.walk(directory):
        # Ignore common bad directories
        if any(ignored in root for ignored in [".git", "node_modules", "venv", "__pycache__"]):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            all_entities.extend(parser.parse_file(file_path))
    return all_entities
