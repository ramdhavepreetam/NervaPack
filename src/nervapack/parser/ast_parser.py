import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set

from tree_sitter import Language, Parser, Node

from nervapack.parser.language_registry import LANGUAGE_REGISTRY, LanguageConfig


# ---------------------------------------------------------------------------
# Intelligent vendor detection helpers
# ---------------------------------------------------------------------------

def _build_installed_package_names() -> Set[str]:
    """
    Return the union of all top-level import names and dist-info directory
    names from the current Python environment.  Used to auto-skip directories
    whose name matches a known installed package (Option 2).
    """
    names: Set[str] = set()
    try:
        import importlib.metadata as meta
        for dist in meta.distributions():
            # Canonical name: lowercase, dashes → underscores
            raw = dist.metadata.get("Name", "")
            if raw:
                norm = raw.lower().replace("-", "_")
                names.add(norm)
                names.add(raw.lower())
            # top_level.txt lists the actual importable package dirs
            tl = dist.read_text("top_level.txt")
            if tl:
                for line in tl.splitlines():
                    t = line.strip().lower()
                    if t:
                        names.add(t)
    except Exception:
        pass
    return names


# Lazy singleton — computed once per process.
_INSTALLED_PACKAGE_NAMES: Set[str] | None = None


def _is_installed_package_dir(name: str) -> bool:
    global _INSTALLED_PACKAGE_NAMES
    if _INSTALLED_PACKAGE_NAMES is None:
        _INSTALLED_PACKAGE_NAMES = _build_installed_package_names()
    norm = name.lower().replace("-", "_")
    return norm in _INSTALLED_PACKAGE_NAMES or name.lower() in _INSTALLED_PACKAGE_NAMES


# Nested-package manifests — presence in a *non-root* dir signals a bundled library.
_EMBEDDED_PACKAGE_SIGNALS = {"package.json", "pyproject.toml", "setup.py", "setup.cfg"}

# Minification signals: if a directory's JS/TS files are almost all on a single
# (very long) line, it is almost certainly a vendored minified bundle.
_MINIFIED_EXTENSIONS = {".js", ".ts", ".cjs", ".mjs"}
_MINIFIED_LINE_RATIO = 0.95   # 95% of lines are very long (>500 chars)
_MINIFIED_LONG_LINE  = 500    # chars
_MINIFIED_MIN_FILES  = 3      # only check dirs with at least this many JS/TS files


def _has_embedded_manifest(dir_path: str) -> bool:
    """True if dir_path contains a manifest file indicating it is its own package."""
    for signal in _EMBEDDED_PACKAGE_SIGNALS:
        if os.path.isfile(os.path.join(dir_path, signal)):
            return True
    return False


def _looks_minified(dir_path: str) -> bool:
    """
    True if the directory appears to be a minified JS/TS bundle.
    Samples the first 10 JS/TS files and counts how many have a suspiciously
    high ratio of very-long lines.
    """
    js_files = []
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file() and Path(entry.name).suffix in _MINIFIED_EXTENSIONS:
                js_files.append(entry.path)
                if len(js_files) >= 10:
                    break
    except OSError:
        return False

    if len(js_files) < _MINIFIED_MIN_FILES:
        return False

    long_line_files = 0
    for fp in js_files:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
            if not lines:
                continue
            long = sum(1 for l in lines if len(l) > _MINIFIED_LONG_LINE)
            if long / len(lines) >= _MINIFIED_LINE_RATIO:
                long_line_files += 1
        except OSError:
            pass

    return long_line_files / len(js_files) >= _MINIFIED_LINE_RATIO


# Cache to avoid re-checking the same absolute dir path multiple times.
_vendor_cache: Dict[str, bool] = {}


def _is_vendor_dir(dir_path: str, name: str) -> bool:
    """
    Returns True if dir_path should be treated as vendor/third-party code.
    Combines:
      - pip cross-reference (Option 2): dir name matches an installed package
      - embedded manifest check (Option 3a): contains package.json / pyproject.toml
      - minification heuristic (Option 3b): nearly all JS/TS files are minified

    This is always called on a *subdirectory* of the scan root, never the
    root itself, so every signal is safe to apply without a root-exclusion guard.
    """
    if dir_path in _vendor_cache:
        return _vendor_cache[dir_path]

    result = (
        _is_installed_package_dir(name)
        or _has_embedded_manifest(dir_path)
        or _looks_minified(dir_path)
    )

    _vendor_cache[dir_path] = result
    return result


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
_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".nervapack",
    # build outputs
    "dist", "build", "site", "target", "out", "output",
    # Python tooling
    ".eggs", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    # coverage / test artefacts
    "htmlcov", "coverage",
    # JS/TS frameworks
    ".next", ".nuxt", ".svelte-kit", ".turbo",
    # JVM
    "bin", ".gradle",
    # IDEs
    ".idea", ".vscode",
    # vendored / bundled third-party code (never user source)
    "vendor", "vendors", "third_party", "extern", "_vendor",
    "lib", "libs",
    # pip-installed packages that land inside the project tree
    "rusted-host", "site-packages",
}

# File suffixes that are never worth parsing (minified bundles, lock files)
_SKIP_SUFFIXES = {".min.js", ".min.ts", ".min.cjs", ".bundle.js", ".bundle.ts"}


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


_shared_parser: ASTParser | None = None


def scan_directory(directory: str, parser: ASTParser | None = None) -> List[ParsedEntity]:
    global _shared_parser
    if parser is None:
        if _shared_parser is None:
            _shared_parser = ASTParser()
        parser = _shared_parser
    all_entities: List[ParsedEntity] = []
    ignore_patterns = _load_ignore_patterns(directory)
    abs_root = str(Path(directory).resolve())

    for root, dirs, files in os.walk(directory):
        # Skip hardcoded dirs and .nervapackignore dir patterns;
        # also skip auto-detected vendor/pip directories.
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_DIRS
            and not d.endswith((".egg-info", ".dist-info"))
            and not _is_ignored(os.path.join(root, d), abs_root, ignore_patterns)
            and not _is_vendor_dir(os.path.join(root, d), d)
        ]
        for file in files:
            # Skip unsupported extensions and minified bundles
            p = Path(file)
            if p.suffix not in _SUPPORTED_EXTENSIONS:
                continue
            if any(file.endswith(s) for s in _SKIP_SUFFIXES):
                continue
            file_path = os.path.join(root, file)
            if _is_ignored(file_path, abs_root, ignore_patterns):
                continue
            try:
                file_entities = parser.parse_file(file_path)
                # Guard against minified files that slip through (e.g. renamed
                # without .min suffix): cap at 500 entities per file.
                if len(file_entities) > 500:
                    continue
                all_entities.extend(file_entities)
            except ImportError:
                pass
    return all_entities
