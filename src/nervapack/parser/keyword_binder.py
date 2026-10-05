"""
Free, instant doc-to-code binding — no LLM required (``--mode fast``).

A markdown chunk is linked to a code entity only when the chunk names that
entity *as code*: in a backtick span, as a call (``name(``), or as a compound
identifier (``build_keyword_index``, ``VectorStore``) that is unlikely to be
an ordinary English word.

The previous version scored overlap between prose words and the entity's
node_id, which embeds the file path and entity type. Path words like
"nervapack" or "documents" and type words like "function" matched almost
every chunk, and import nodes (``json``, ``re``) collected most edges. So:

* only the entity's own name is matched — never its path or type;
* ``import`` and ``file`` nodes are never targets;
* names match case-sensitively, like code — ``nervapack`` in a shell
  command is not the Homebrew formula's ``class Nervapack``;
* a name defined in many places only matches when the chunk also mentions
  the defining file, so ``__init__`` or a common ``query`` doesn't fan out.
"""
import os
import re
from collections import defaultdict
from typing import Dict, List, Set

# Entity types a doc never "explains" — they would only add noise edges.
_NON_TARGET_TYPES = {"import", "file", "markdown"}

# A name defined by more entities than this needs the file named too.
MAX_AMBIGUOUS_DEFS = 3

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_CALL_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
# CLI flags (`--model`) and keyword arguments (`budget_tokens=400`) name
# parameters, not entities — strip them from code spans before matching.
_PARAM_RE = re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*|\b[A-Za-z_]\w*\s*=(?!=)")
_CAMEL_SPLIT_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _name_parts(name: str) -> List[str]:
    """Split ``build_keyword_index`` / ``VectorStore`` into lowercase words."""
    return [p.lower() for chunk in name.split("_") for p in _CAMEL_SPLIT_RE.findall(chunk)]


def _is_compound(name: str) -> bool:
    """True for identifiers that read as code rather than an English word."""
    return len(_name_parts(name)) >= 2


def _parse_node_id(node_id: str):
    """Recover (type, file_path, name) from ``type:file_path:name:line``."""
    entity_type, _, rest = node_id.partition(":")
    rest = rest.rsplit(":", 1)[0]          # drop :line
    file_path, _, name = rest.rpartition(":")
    return entity_type, file_path, name


def _file_stem(file_path: str) -> str:
    return os.path.splitext(os.path.basename(file_path))[0].lower()


class KeywordIndex:
    """Entity names (case-sensitive) -> node_ids, plus each node's file stem."""

    def __init__(self) -> None:
        self.by_name: Dict[str, List[str]] = defaultdict(list)
        self.stem_of: Dict[str, str] = {}
        self.compound: Dict[str, bool] = {}

    def get(self, name: str, default=()):
        return self.by_name.get(name, default)


def build_keyword_index(ast_docs: List[Dict[str, str]]) -> KeywordIndex:
    """Index bindable entities by their own name."""
    index = KeywordIndex()
    for doc in ast_docs:
        node_id = doc["node_id"]
        parsed_type, parsed_path, parsed_name = _parse_node_id(node_id)
        entity_type = doc.get("type") or parsed_type
        name = doc.get("name") or parsed_name
        if entity_type in _NON_TARGET_TYPES or not name:
            continue
        # Dunder methods are named the same in every class — never specific.
        if name.startswith("__") and name.endswith("__"):
            continue
        index.by_name[name].append(node_id)
        index.stem_of[node_id] = _file_stem(doc.get("file_path") or parsed_path)
        index.compound[name] = _is_compound(name)
    return index


def _code_mentions(doc_text: str) -> Set[str]:
    """Identifiers the chunk writes as code: backticked or called."""
    names: Set[str] = set()
    for span in _CODE_SPAN_RE.findall(doc_text):
        names.update(_IDENT_RE.findall(_PARAM_RE.sub(" ", span)))
    names.update(_CALL_RE.findall(doc_text))
    return names


def keyword_search(doc_text: str, index: KeywordIndex, top_k: int = 5) -> List[str]:
    """Return up to ``top_k`` node_ids the chunk explicitly refers to.

    Scores: 2 for a name written as code (backticks / call), 1 for a compound
    identifier appearing verbatim in prose. A single-word name in plain prose
    ("query", "status") is not evidence and scores nothing.
    """
    if not doc_text:
        return []

    code_names = _code_mentions(doc_text)
    mentioned = code_names | set(_IDENT_RE.findall(doc_text))
    # File stems the chunk mentions, e.g. "vector_store" or "vector_store.py".
    mentioned_lower = {m.lower() for m in mentioned}

    scored: Dict[str, int] = {}
    for name in mentioned:
        node_ids = index.by_name.get(name)
        if not node_ids:
            continue
        if name in code_names:
            score = 2
        elif index.compound.get(name):
            score = 1
        else:
            continue

        if len(node_ids) > MAX_AMBIGUOUS_DEFS:
            node_ids = [n for n in node_ids if index.stem_of.get(n) in mentioned_lower]
        for node_id in node_ids:
            scored[node_id] = max(scored.get(node_id, 0), score)

    ranked = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    return [node_id for node_id, _ in ranked[:top_k]]
