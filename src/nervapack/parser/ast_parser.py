import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from tree_sitter import Language, Parser, Node

from nervapack.parser.language_registry import LANGUAGE_REGISTRY, LanguageConfig


@dataclass
class ParsedEntity:
    name: str
    type: str  # 'class', 'function', 'import'
    file_path: str
    start_line: int
    end_line: int
    content: str
    metadata: Dict[str, Any]


class ASTParser:
    def __init__(self):
        self._parsers: Dict[str, Parser] = {}       # ext -> Parser (lazy)
        self._languages: Dict[str, Language] = {}   # ext -> Language (lazy)

    def _get_parser(self, ext: str) -> Optional[Parser]:
        if ext in self._parsers:
            return self._parsers[ext]
        if ext not in LANGUAGE_REGISTRY:
            return None
        config = LANGUAGE_REGISTRY[ext]
        try:
            lang = config.grammar_loader()
            parser = Parser(lang)
            self._languages[ext] = lang
            self._parsers[ext] = parser
            return parser
        except ImportError:
            extra = config.extra_name
            hint = f"pip install nervapack[{extra}]" if extra else f"pip install {config.package_name}"
            raise ImportError(
                f"{config.package_name} is not installed. "
                f"To parse {ext} files, run: {hint}"
            )

    def _extract_name(self, node: Node, config: LanguageConfig) -> Optional[str]:
        if config.name_extractor is not None:
            result = config.name_extractor(node)
            return result if result else None
        name_node = node.child_by_field_name(config.name_field)
        if name_node:
            return name_node.text.decode("utf-8", errors="replace")
        return None

    def parse_file(self, file_path: str) -> List[ParsedEntity]:
        ext = Path(file_path).suffix
        parser = self._get_parser(ext)
        if parser is None:
            return []

        with open(file_path, "rb") as f:
            content_bytes = f.read()

        tree = parser.parse(content_bytes)
        config = LANGUAGE_REGISTRY[ext]
        entities: List[ParsedEntity] = []
        self._traverse_tree(tree.root_node, content_bytes, file_path, ext, config, entities)
        return entities

    def _traverse_tree(
        self,
        node: Node,
        content_bytes: bytes,
        file_path: str,
        ext: str,
        config: LanguageConfig,
        entities: List[ParsedEntity],
    ):
        for entity_kind, node_type_list in config.node_types.items():
            if node.type in node_type_list:
                name = self._extract_name(node, config)
                if name:
                    entities.append(
                        self._create_entity(name, entity_kind, node, content_bytes, file_path)
                    )
                break

        for child in node.children:
            self._traverse_tree(child, content_bytes, file_path, ext, config, entities)

    def _create_entity(
        self, name: str, entity_type: str, node: Node, content_bytes: bytes, file_path: str
    ) -> ParsedEntity:
        return ParsedEntity(
            name=name,
            type=entity_type,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=node.text.decode("utf-8", errors="replace"),
            metadata={},
        )


_SUPPORTED_EXTENSIONS = set(LANGUAGE_REGISTRY.keys())
_SKIP_DIRS = {".git", "node_modules", "venv", "__pycache__", ".nervapack"}


def scan_directory(directory: str) -> List[ParsedEntity]:
    parser = ASTParser()
    all_entities: List[ParsedEntity] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for file in files:
            if Path(file).suffix not in _SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(root, file)
            try:
                all_entities.extend(parser.parse_file(file_path))
            except ImportError as exc:
                # Optional language package not installed — skip silently
                # (the user will see this only once if they explicitly try to parse that ext)
                pass
    return all_entities
