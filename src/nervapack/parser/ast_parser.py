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


def _load_ignore_patterns(directory: str) -> List[str]:
    """Read .nervapackignore and return patterns as a list of strings."""
    ignore_file = Path(directory) / ".nervapackignore"
    if not ignore_file.exists():
        return []
    patterns = []
    for line in ignore_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _is_ignored(path: str, root: str, patterns: List[str]) -> bool:
    """Return True if path matches any ignore pattern (gitignore-style, simple)."""
    import fnmatch
    # Make path relative to root for matching
    try:
        rel = Path(path).relative_to(root).as_posix()
    except ValueError:
        rel = path

    for pattern in patterns:
        # Strip trailing slash — used for dirs but match against both
        pat = pattern.rstrip("/")
        # Match against filename, relative path, or any path component
        name = Path(path).name
        if (fnmatch.fnmatch(name, pat)
                or fnmatch.fnmatch(rel, pat)
                or any(fnmatch.fnmatch(part, pat) for part in Path(rel).parts)):
            return True
    return False


def scan_directory(directory: str) -> List[ParsedEntity]:
    parser = ASTParser()
    all_entities: List[ParsedEntity] = []
    ignore_patterns = _load_ignore_patterns(directory)
    abs_root = str(Path(directory).resolve())

    for root, dirs, files in os.walk(directory):
        # Skip hardcoded dirs and .nervapackignore dir patterns
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_DIRS
            and not _is_ignored(os.path.join(root, d), abs_root, ignore_patterns)
        ]
        for file in files:
            if Path(file).suffix not in _SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(root, file)
            if _is_ignored(file_path, abs_root, ignore_patterns):
                continue
            try:
                all_entities.extend(parser.parse_file(file_path))
            except ImportError:
                pass
    return all_entities
