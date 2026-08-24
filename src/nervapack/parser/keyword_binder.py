"""
Free, instant doc-to-code binding via keyword overlap — no LLM required.

Used as the fallback (or default, with --no-bind) binding strategy during
ingest/enrich. Building a word -> node_ids inverted index once and reusing
it per markdown chunk avoids re-tokenizing every AST node for every chunk
(O(chunks) instead of O(chunks x nodes)).
"""
import re
from collections import defaultdict
from typing import Dict, List, Set

_WORD_RE = re.compile(r"[a-zA-Z_]{4,}")


def _tokenise(text: str) -> Set[str]:
    return set(w for w in _WORD_RE.findall(text.lower()))


def build_keyword_index(ast_docs: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Build a word -> [node_id, ...] inverted index from AST doc node_ids."""
    index: Dict[str, List[str]] = defaultdict(list)
    for doc in ast_docs:
        for word in _tokenise(doc["node_id"]):
            index[word].append(doc["node_id"])
    return index


def keyword_search(doc_text: str, index: Dict[str, List[str]], top_k: int = 5) -> List[str]:
    """Return the top_k node_ids whose node_id shares the most words with doc_text."""
    doc_words = _tokenise(doc_text)
    if not doc_words:
        return []

    overlap_counts: Dict[str, int] = defaultdict(int)
    for word in doc_words:
        for node_id in index.get(word, ()):
            overlap_counts[node_id] += 1

    scored = [(count, node_id) for node_id, count in overlap_counts.items() if count >= 2]
    scored.sort(key=lambda x: -x[0])
    return [node_id for _, node_id in scored[:top_k]]
