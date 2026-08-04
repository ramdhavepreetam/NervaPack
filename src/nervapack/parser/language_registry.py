from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from nervapack.parser.regex_extractors import (
    extract_cl,
    extract_cobol,
    extract_rpg,
)


@dataclass
class LanguageConfig:
    grammar_loader: Optional[Callable]  # () -> tree_sitter.Language; None for regex-only languages
    node_types: Dict[str, List[str]]  # "class"|"function"|"import" -> list of tree-sitter node type strings
    package_name: str               # e.g. "tree-sitter-go", used in error messages
    extra_name: str                 # pip extras key, e.g. "go" (empty string = bundled)
    name_field: str = "name"        # tree-sitter field used for default name extraction
    name_extractor: Optional[Callable] = None  # overrides name_field when node structure is non-standard
    regex_extractor: Optional[Callable] = None  # (content, file_path) -> List[ParsedEntity]; set for
                                                # languages with no tree-sitter grammar (RPG/CL/COBOL).
                                                # Mutually exclusive with grammar_loader.


def _loader(module: str, attr: str) -> Callable:
    """Return a lazy grammar loader that imports `module` and calls `module.attr()`."""
    def load():
        try:
            mod = importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(str(exc)) from exc
        from tree_sitter import Language
        return Language(getattr(mod, attr)())
    return load


# ── Per-language name extractors ────────────────────────────────────────────

def _go_name(node) -> Optional[str]:
    """Go: type_declaration wraps type_spec which holds the name field.
    import_declaration has no name — use a line-based key."""
    if node.type == "type_declaration":
        for child in node.children:
            if child.type == "type_spec":
                name_node = child.child_by_field_name("name")
                if name_node:
                    return name_node.text.decode("utf-8", errors="replace")
        return None
    if node.type == "import_declaration":
        return f"import_{node.start_point[0]}"
    name_node = node.child_by_field_name("name")
    return name_node.text.decode("utf-8", errors="replace") if name_node else None


def _c_name(node) -> Optional[str]:
    """C: function_definition name lives two levels deep in the declarator chain.
    preproc_include uses the path field, not name."""
    if node.type == "function_definition":
        # function_definition.declarator → function_declarator.declarator → identifier
        decl = node.child_by_field_name("declarator")
        if decl:
            inner = decl.child_by_field_name("declarator")
            if inner:
                return inner.text.decode("utf-8", errors="replace")
        return None
    if node.type == "preproc_include":
        path_node = node.child_by_field_name("path")
        if path_node:
            return path_node.text.decode("utf-8", errors="replace").strip('"<>')
        return f"include_{node.start_point[0]}"
    name_node = node.child_by_field_name("name")
    return name_node.text.decode("utf-8", errors="replace") if name_node else None


def _cpp_name(node) -> Optional[str]:
    """C++: same as C for function_definition and preproc_include;
    class_specifier and struct_specifier both have a direct name field."""
    return _c_name(node)


def _java_name(node) -> Optional[str]:
    """Java: import_declaration wraps a scoped_identifier — use its full text
    as the import name. All other entity types have a direct name field."""
    if node.type == "import_declaration":
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                return child.text.decode("utf-8", errors="replace")
        return f"import_{node.start_point[0]}"
    name_node = node.child_by_field_name("name")
    return name_node.text.decode("utf-8", errors="replace") if name_node else None


# ── Registry ─────────────────────────────────────────────────────────────────

LANGUAGE_REGISTRY: Dict[str, LanguageConfig] = {
    # ── Python ────────────────────────────────────────────────────────────────
    ".py": LanguageConfig(
        grammar_loader=_loader("tree_sitter_python", "language"),
        package_name="tree-sitter-python",
        extra_name="",
        node_types={
            "class":    ["class_definition"],
            "function": ["function_definition"],
            "import":   ["import_statement", "import_from_statement"],
        },
    ),

    # ── JavaScript / JSX ──────────────────────────────────────────────────────
    ".js": LanguageConfig(
        grammar_loader=_loader("tree_sitter_javascript", "language"),
        package_name="tree-sitter-javascript",
        extra_name="",
        node_types={
            "class":    ["class_declaration"],
            "function": ["function_declaration", "method_definition"],
            "import":   ["import_statement"],
        },
    ),
    ".jsx": LanguageConfig(
        grammar_loader=_loader("tree_sitter_javascript", "language"),
        package_name="tree-sitter-javascript",
        extra_name="",
        node_types={
            "class":    ["class_declaration"],
            "function": ["function_declaration", "method_definition"],
            "import":   ["import_statement"],
        },
    ),

    # ── TypeScript / TSX ──────────────────────────────────────────────────────
    ".ts": LanguageConfig(
        grammar_loader=_loader("tree_sitter_typescript", "language_typescript"),
        package_name="tree-sitter-typescript",
        extra_name="",
        node_types={
            "class":    ["class_declaration", "interface_declaration"],
            "function": ["function_declaration", "method_definition"],
            "import":   ["import_statement"],
        },
    ),
    ".tsx": LanguageConfig(
        grammar_loader=_loader("tree_sitter_typescript", "language_tsx"),
        package_name="tree-sitter-typescript",
        extra_name="",
        node_types={
            "class":    ["class_declaration", "interface_declaration"],
            "function": ["function_declaration", "method_definition"],
            "import":   ["import_statement"],
        },
    ),

    # ── Go ────────────────────────────────────────────────────────────────────
    ".go": LanguageConfig(
        grammar_loader=_loader("tree_sitter_go", "language"),
        package_name="tree-sitter-go",
        extra_name="go",
        node_types={
            "class":    ["type_declaration"],
            "function": ["function_declaration", "method_declaration"],
            "import":   ["import_declaration"],
        },
        name_extractor=_go_name,
    ),

    # ── Rust ──────────────────────────────────────────────────────────────────
    ".rs": LanguageConfig(
        grammar_loader=_loader("tree_sitter_rust", "language"),
        package_name="tree-sitter-rust",
        extra_name="rust",
        node_types={
            "class":    ["struct_item", "impl_item", "trait_item", "enum_item"],
            "function": ["function_item"],
            "import":   ["use_declaration"],
        },
    ),

    # ── Java ──────────────────────────────────────────────────────────────────
    ".java": LanguageConfig(
        grammar_loader=_loader("tree_sitter_java", "language"),
        package_name="tree-sitter-java",
        extra_name="java",
        node_types={
            "class":    ["class_declaration", "interface_declaration", "enum_declaration"],
            "function": ["method_declaration", "constructor_declaration"],
            "import":   ["import_declaration"],
        },
        name_extractor=_java_name,
    ),

    # ── C ─────────────────────────────────────────────────────────────────────
    ".c": LanguageConfig(
        grammar_loader=_loader("tree_sitter_c", "language"),
        package_name="tree-sitter-c",
        extra_name="c",
        node_types={
            "class":    ["struct_specifier"],
            "function": ["function_definition"],
            "import":   ["preproc_include"],
        },
        name_extractor=_c_name,
    ),
    ".h": LanguageConfig(
        grammar_loader=_loader("tree_sitter_c", "language"),
        package_name="tree-sitter-c",
        extra_name="c",
        node_types={
            "class":    ["struct_specifier"],
            "function": ["function_definition", "declaration"],
            "import":   ["preproc_include"],
        },
        name_extractor=_c_name,
    ),

    # ── C++ ───────────────────────────────────────────────────────────────────
    ".cpp": LanguageConfig(
        grammar_loader=_loader("tree_sitter_cpp", "language"),
        package_name="tree-sitter-cpp",
        extra_name="cpp",
        node_types={
            "class":    ["class_specifier", "struct_specifier"],
            "function": ["function_definition"],
            "import":   ["preproc_include"],
        },
        name_extractor=_cpp_name,
    ),
    ".cc": LanguageConfig(
        grammar_loader=_loader("tree_sitter_cpp", "language"),
        package_name="tree-sitter-cpp",
        extra_name="cpp",
        node_types={
            "class":    ["class_specifier", "struct_specifier"],
            "function": ["function_definition"],
            "import":   ["preproc_include"],
        },
        name_extractor=_cpp_name,
    ),
    ".cxx": LanguageConfig(
        grammar_loader=_loader("tree_sitter_cpp", "language"),
        package_name="tree-sitter-cpp",
        extra_name="cpp",
        node_types={
            "class":    ["class_specifier", "struct_specifier"],
            "function": ["function_definition"],
            "import":   ["preproc_include"],
        },
        name_extractor=_cpp_name,
    ),
    ".hpp": LanguageConfig(
        grammar_loader=_loader("tree_sitter_cpp", "language"),
        package_name="tree-sitter-cpp",
        extra_name="cpp",
        node_types={
            "class":    ["class_specifier", "struct_specifier"],
            "function": ["function_definition", "declaration"],
            "import":   ["preproc_include"],
        },
        name_extractor=_cpp_name,
    ),

    # ── Ruby ──────────────────────────────────────────────────────────────────
    ".rb": LanguageConfig(
        grammar_loader=_loader("tree_sitter_ruby", "language"),
        package_name="tree-sitter-ruby",
        extra_name="ruby",
        node_types={
            "class":    ["class", "module"],
            "function": ["method", "singleton_method"],
            "import":   [],
        },
    ),

    # ── C# ────────────────────────────────────────────────────────────────────
    ".cs": LanguageConfig(
        grammar_loader=_loader("tree_sitter_c_sharp", "language"),
        package_name="tree-sitter-c-sharp",
        extra_name="csharp",
        node_types={
            "class":    ["class_declaration", "interface_declaration",
                         "struct_declaration", "enum_declaration"],
            "function": ["method_declaration", "constructor_declaration"],
            "import":   ["using_directive"],
        },
    ),

    # ── IBM i / mainframe (regex extractors, no tree-sitter grammar) ──────────
    # These have no usable tree-sitter grammar on PyPI, so they use the
    # pure-Python regex path in `regex_extractors`. Bundled, always on.

    # RPG (free-form RPGLE, fixed-form RPG, embedded-SQL RPG)
    ".rpgle":   LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_rpg),
    ".rpg":     LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_rpg),
    ".sqlrpgle": LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                                extra_name="", regex_extractor=extract_rpg),

    # CL (Control Language programs / procedures)
    ".clle":    LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cl),
    ".clp":     LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cl),
    ".cl":      LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cl),

    # COBOL (fixed- and free-form, plus copybooks)
    ".cbl":     LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cobol),
    ".cob":     LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cobol),
    ".cobol":   LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cobol),
    ".cpy":     LanguageConfig(grammar_loader=None, node_types={}, package_name="",
                               extra_name="", regex_extractor=extract_cobol),
}
