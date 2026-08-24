"""Regression tests for the three ingest-path performance/correctness fixes.

1. Chunk IDs are scoped per file, so editing one file does not invalidate the
   whole corpus and force a full re-embed.
2. The vendor heuristic is root-scoped, so a project's own source is never
   mistaken for a third-party dependency.
3. REFERENCES resolution is import-scoped and fan-out capped, so a common name
   does not link to every same-named definition in the repo.
"""

import os

import pytest

from nervapack.graph.builder import GraphBuilder, MAX_NAME_FANOUT
from nervapack.graph.vector_store import (
    _make_chunk_ids,
    _make_embedding_function,
    _onnx_thread_count,
)
from nervapack.parser.ast_parser import ParsedEntity, _is_vendor_dir


def _entity(name, file_path, type_="function", content="", start_line=1):
    return ParsedEntity(
        name=name, type=type_, file_path=file_path,
        start_line=start_line, end_line=start_line + 1,
        content=content, metadata={},
    )


# ── 1. chunk IDs ───────────────────────────────────────────────────────────

def test_chunk_ids_are_scoped_per_file():
    chunks = [{"file_path": "a.md"}, {"file_path": "a.md"}, {"file_path": "b.md"}]
    assert _make_chunk_ids(chunks) == ["md_a.md_0", "md_a.md_1", "md_b.md_0"]


def test_inserting_a_chunk_does_not_shift_other_files():
    """The bug: a global enumerate shifted every downstream ID, so every
    chunk after the edit missed the content check and got re-embedded."""
    before = [{"file_path": "a.md"}, {"file_path": "b.md"}, {"file_path": "c.md"}]
    after = [{"file_path": "a.md"}, {"file_path": "a.md"},
             {"file_path": "b.md"}, {"file_path": "c.md"}]

    untouched_before = [i for i in _make_chunk_ids(before) if not i.startswith("md_a")]
    untouched_after = [i for i in _make_chunk_ids(after) if not i.startswith("md_a")]
    assert untouched_before == untouched_after


# ── 2. vendor heuristic ────────────────────────────────────────────────────

def test_own_source_with_manifest_is_not_vendor(tmp_path):
    """A monorepo package carries its own package.json — that must not make
    it look like a vendored dependency."""
    pkg = tmp_path / "packages" / "api"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text('{"name":"api"}')

    assert _is_vendor_dir(str(pkg), "api", str(tmp_path)) is False


def test_real_vendor_dir_still_skipped(tmp_path):
    dep = tmp_path / "node_modules" / "lodash"
    dep.mkdir(parents=True)
    (dep / "package.json").write_text('{"name":"lodash"}')

    assert _is_vendor_dir(str(dep), "lodash", str(tmp_path)) is True


def test_src_dir_matching_installed_package_is_not_vendor(tmp_path):
    """An editable install makes the source dir share a name with a real
    dist; scoping to the source root is what keeps it in the graph."""
    src = tmp_path / "src" / "os"   # "os" always resolves as a known name
    src.mkdir(parents=True)
    (src / "mod.py").write_text("def f(): pass")

    assert _is_vendor_dir(str(src), "os", str(tmp_path)) is False


# ── 3. REFERENCES scoping ──────────────────────────────────────────────────

def test_same_file_reference_resolves():
    entities = [
        _entity("helper", "a.py", start_line=1),
        _entity("caller", "a.py", content="helper()", start_line=10),
    ]
    g = GraphBuilder().build_from_entities(entities)
    assert g.has_edge("function:a.py:caller:10", "function:a.py:helper:1")


def test_reference_follows_imports_not_every_same_name():
    """`caller` imports only `mod_a`, so it must link there and nowhere else."""
    entities = [
        _entity("target", "mod_a.py"),
        _entity("target", "mod_b.py"),
        _entity("target", "mod_c.py"),
        _entity("mod_a", "caller.py", type_="import"),
        _entity("caller", "caller.py", content="target()", start_line=5),
    ]
    g = GraphBuilder().build_from_entities(entities)
    src = "function:caller.py:caller:5"
    assert g.has_edge(src, "function:mod_a.py:target:1")
    assert not g.has_edge(src, "function:mod_b.py:target:1")
    assert not g.has_edge(src, "function:mod_c.py:target:1")


def test_high_fanout_name_yields_no_unresolved_edges():
    """A name defined in many files, with nothing to disambiguate it, links
    to none of them — a wrong edge is worse than a missing one."""
    n = MAX_NAME_FANOUT + 3
    entities = [_entity("process", f"m{i}.py") for i in range(n)]
    entities.append(_entity("caller", "unrelated.py", content="process()", start_line=7))

    g = GraphBuilder().build_from_entities(entities)
    src = "function:unrelated.py:caller:7"
    assert [v for _, v in g.out_edges(src)] == []


def test_polymorphic_interface_survives_fanout_cap():
    """Widely-implemented interface methods stay connected when an import
    resolves them — the cap must not pre-empt real resolution."""
    n = MAX_NAME_FANOUT + 3
    entities = [_entity("chat", f"provider_{i}.py") for i in range(n)]
    entities.append(_entity("provider_2", "client.py", type_="import"))
    entities.append(_entity("run", "client.py", content="chat()", start_line=3))

    g = GraphBuilder().build_from_entities(entities)
    assert g.has_edge("function:client.py:run:3", "function:provider_2.py:chat:1")


# ── 4. ONNX session tuning ─────────────────────────────────────────────────

def test_onnx_thread_count_defaults_to_cpu_count(monkeypatch):
    monkeypatch.delenv("NERVAPACK_ONNX_THREADS", raising=False)
    assert _onnx_thread_count() == (os.cpu_count() or 0)


def test_onnx_thread_count_respects_override(monkeypatch):
    monkeypatch.setenv("NERVAPACK_ONNX_THREADS", "4")
    assert _onnx_thread_count() == 4


def test_onnx_thread_count_zero_restores_ort_default(monkeypatch):
    """0 is the documented escape hatch back to onnxruntime's own default."""
    monkeypatch.setenv("NERVAPACK_ONNX_THREADS", "0")
    assert _onnx_thread_count() == 0


def test_onnx_thread_count_ignores_garbage(monkeypatch):
    monkeypatch.setenv("NERVAPACK_ONNX_THREADS", "not-a-number")
    assert _onnx_thread_count() == (os.cpu_count() or 0)


def test_tuned_session_excludes_coreml(monkeypatch):
    """CoreML measured ~5x slower than CPU for all-MiniLM-L6-v2."""
    ef = _make_embedding_function()
    if ef is None:
        pytest.skip("chromadb onnx extra unavailable")
    assert "CoreMLExecutionProvider" not in ef.model.get_providers()
