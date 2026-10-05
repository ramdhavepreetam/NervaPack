"""Fast-mode doc-to-code binding precision.

The regression: matching prose words against node_ids meant path words
("nervapack", "documents") and type words ("function") matched nearly every
chunk, and 65% of EXPLAINS edges on the NervaPack repo pointed at import
nodes like ``json``.
"""

from nervapack.parser.keyword_binder import (
    MAX_AMBIGUOUS_DEFS,
    build_keyword_index,
    keyword_search,
)

ROOT = "/Users/someone/Documents/nervapack/src/nervapack"


def _doc(type_, name, path, line=1):
    fp = f"{ROOT}/{path}"
    return {"node_id": f"{type_}:{fp}:{name}:{line}", "file_path": fp}


DOCS = [
    _doc("function", "build_keyword_index", "parser/keyword_binder.py", 20),
    _doc("class", "VectorStore", "graph/vector_store.py", 140),
    _doc("function", "query", "cli.py", 400),
    _doc("function", "model", "graph/vector_store.py", 60),
    _doc("import", "json", "memory/store.py", 4),
    _doc("function", "__init__", "graph/builder.py", 10),
]
INDEX = build_keyword_index(DOCS)


def _names(ids):
    return {i.rsplit(":", 2)[-2] for i in ids}


def test_path_and_type_words_do_not_match():
    text = "NervaPack documents every function and class in your nervapack source."
    assert keyword_search(text, INDEX) == []


def test_imports_are_never_targets():
    assert keyword_search("Memories are serialised with `json` and `json.dumps()`.", INDEX) == []


def test_backticked_name_matches():
    assert _names(keyword_search("Run `query` to search the graph.", INDEX)) == {"query"}


def test_call_syntax_matches():
    assert _names(keyword_search("Call VectorStore() with a custom path.", INDEX)) == {"VectorStore"}


def test_compound_identifier_in_prose_matches():
    text = "The build_keyword_index helper is built once per ingest."
    assert _names(keyword_search(text, INDEX)) == {"build_keyword_index"}


def test_single_word_in_prose_does_not_match():
    assert keyword_search("You can query the model for anything.", INDEX) == []


def test_case_sensitive():
    """`nervapack ingest .` must not bind to a `class Nervapack` formula."""
    index = build_keyword_index([_doc("class", "Nervapack", "Formula/nervapack.rb")])
    assert keyword_search("Run `nervapack ingest .` first.", index) == []


def test_cli_flags_and_kwargs_are_not_entities():
    text = "Pass `--model qwen2.5:7b`, or call it with `run(model=1)`."
    assert "model" not in _names(keyword_search(text, INDEX))


def test_dunder_names_never_match():
    assert keyword_search("Override `__init__` to customise.", INDEX) == []


def test_ambiguous_name_needs_its_file_mentioned():
    many = [_doc("function", "load", f"mod{i}.py") for i in range(MAX_AMBIGUOUS_DEFS + 1)]
    index = build_keyword_index(many)
    assert keyword_search("Call `load()` to read it.", index) == []
    hits = keyword_search("Call `load()` in `mod2.py` to read it.", index)
    assert hits == [many[2]["node_id"]]


def test_backticked_ranks_above_prose_and_top_k_applies():
    text = "`query` uses VectorStore() and build_keyword_index internally."
    hits = keyword_search(text, INDEX, top_k=2)
    assert len(hits) == 2
    assert _names(hits) == {"query", "VectorStore"}
