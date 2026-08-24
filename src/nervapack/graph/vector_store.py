import os
import chromadb
from typing import List, Dict, Optional

# Caps how much raw code text gets embedded per AST entity. Large classes/
# functions otherwise produce very long embedding inputs that slow down
# ONNX tokenization/inference for no retrieval benefit beyond a few hundred
# tokens worth of context.
MAX_ENTITY_SUMMARY_CHARS = 2000


def build_entity_summary(entity_type: str, name: str, file_path: str, content: str) -> str:
    """Build the text embedded for an AST entity, truncating oversized code bodies."""
    if len(content) > MAX_ENTITY_SUMMARY_CHARS:
        content = content[:MAX_ENTITY_SUMMARY_CHARS] + "\n...(truncated)"
    return f"This is a {entity_type} named {name} in {file_path}. Code:\n{content}"


def _onnx_thread_count() -> int:
    """Thread count for ONNX intra-op parallelism.

    onnxruntime's default under-subscribes this workload: measured over 1144
    markdown chunks on a 15-core machine, the default runs at 94 docs/s while
    pinning intra_op to the full core count reaches 149 docs/s (1.6x). Since
    embedding is ~99% of ingest wall time, that is the single biggest lever.

    Override with NERVAPACK_ONNX_THREADS; set it to 0 to restore the ORT default.
    """
    env = os.environ.get("NERVAPACK_ONNX_THREADS")
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return os.cpu_count() or 0


def _tuned_onnx_class():
    """Chroma's ONNX embedder subclassed to set `intra_op_num_threads`.

    Chroma builds its InferenceSession without that option, leaving most cores
    idle. Everything else about the session is deliberately reproduced as-is —
    notably the CoreML exclusion, which is correct here: CoreML measured 5x
    *slower* than CPU for all-MiniLM-L6-v2 on Apple silicon.

    Returns None if chromadb's ONNX extra is unavailable, so callers fall back
    to Chroma's default embedding function.
    """
    try:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )
    except ImportError:
        return None

    from functools import cached_property

    class _TunedONNXMiniLM(ONNXMiniLM_L6_V2):  # type: ignore[misc]
        @cached_property
        def model(self):  # type: ignore[override]
            threads = _onnx_thread_count()
            if not threads:
                return ONNXMiniLM_L6_V2.model.func(self)

            providers = self._preferred_providers or self.ort.get_available_providers()
            # CoreML is measurably slower for this model; Chroma drops it too.
            providers = [p for p in providers if p != "CoreMLExecutionProvider"]
            self._preferred_providers = providers

            so = self.ort.SessionOptions()
            so.log_severity_level = 3
            so.graph_optimization_level = self.ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            so.intra_op_num_threads = threads

            return self.ort.InferenceSession(
                os.path.join(
                    self.DOWNLOAD_PATH, self.EXTRACTED_FOLDER_NAME, "model.onnx"
                ),
                so,
                providers=providers,
            )

    return _TunedONNXMiniLM


def _make_embedding_function(model_path: Optional[str] = None):
    """
    Build a ChromaDB embedding function, respecting the NERVAPACK_ONNX_MODEL
    environment variable (or an explicit model_path) to avoid network downloads
    in corporate / air-gapped environments.

    Priority order:
      1. explicit model_path argument
      2. NERVAPACK_ONNX_MODEL env var pointing to the local model directory
      3. None → ChromaDB's DefaultEmbeddingFunction (downloads on first use)

    The model directory must contain the extracted onnx/ subfolder produced by
    running nervapack on a machine that has internet access, then copying
    ~/.cache/chroma/onnx_models/all-MiniLM-L6-v2 to the target machine.
    Set NERVAPACK_ONNX_MODEL to that directory path.
    """
    base = _tuned_onnx_class()
    if base is None:
        return None

    resolved = model_path or os.environ.get("NERVAPACK_ONNX_MODEL")
    if resolved:
        from pathlib import Path

        model_dir = Path(resolved).expanduser().resolve()

        # Subclass to redirect DOWNLOAD_PATH without mutating the global class
        class _LocalONNX(base):  # type: ignore[valid-type,misc]
            DOWNLOAD_PATH = model_dir
            EXTRACTED_FOLDER_NAME = "onnx"

        return _LocalONNX()

    # Default (auto-downloaded) model, with the tuned ORT session.
    return base()


def _make_chunk_ids(chunks: List[Dict[str, str]]) -> List[str]:
    """Build stable, per-file chunk IDs.

    The index is scoped to the chunk's own file, not to the position of the
    chunk in the whole corpus. A global ``enumerate`` shifts every downstream
    ID as soon as one chunk is added or removed in an earlier file, which makes
    the content-equality check in :meth:`VectorStore._filter_new` miss and
    forces a full re-embed of the corpus on every ingest.
    """
    per_file: Dict[str, int] = {}
    ids: List[str] = []
    for c in chunks:
        fp = c["file_path"]
        i = per_file.get(fp, 0)
        per_file[fp] = i + 1
        ids.append(f"md_{fp}_{i}")
    return ids


class VectorStore:
    def __init__(self, db_path: str = ".nervapack/chroma_db", embedding_function=None,
                 model_path: Optional[str] = None):
        self.client = chromadb.PersistentClient(path=db_path)
        ef = embedding_function or _make_embedding_function(model_path)
        # We use a single collection for both AST node summaries and Markdown chunks
        self.collection = self.client.get_or_create_collection(
            name="nervapack_nodes",
            embedding_function=ef
        )

    def _filter_new(self, ids: List[str], documents: List[str], metadatas: List[dict]) -> tuple:
        """Return only ids/documents/metadatas not already in the collection with identical content."""
        if not ids:
            return [], [], []
        # First-time ingest into an empty collection: nothing to dedup against,
        # so skip the round-trip fetch entirely and embed everything directly.
        if self.collection.count() == 0:
            return ids, documents, metadatas
        # Fetch existing documents for these IDs in one query
        existing = self.collection.get(ids=ids, include=["documents"])
        existing_map = dict(zip(existing["ids"], existing["documents"]))
        new_ids, new_docs, new_metas = [], [], []
        for id_, doc, meta in zip(ids, documents, metadatas):
            if existing_map.get(id_) != doc:
                new_ids.append(id_)
                new_docs.append(doc)
                new_metas.append(meta)
        return new_ids, new_docs, new_metas

    def ingest_chunks(self, chunks: List[Dict[str, str]]):
        """Ingest Markdown chunks — skips chunks already in the store with identical content."""
        if not chunks:
            return

        documents = [c["content"] for c in chunks]
        metadatas = [{"header": c["header"], "file_path": c["file_path"], "type": "markdown"} for c in chunks]
        ids = _make_chunk_ids(chunks)

        new_ids, new_docs, new_metas = self._filter_new(ids, documents, metadatas)
        if new_ids:
            self.collection.upsert(documents=new_docs, metadatas=new_metas, ids=new_ids)

    def ingest_ast_entities(self, entities: List[Dict[str, str]]):
        """Ingest AST entities — skips entities already in the store with identical content."""
        if not entities:
            return

        documents = [e["summary"] for e in entities]
        metadatas = [{"node_id": e["node_id"], "type": "ast", "file_path": e.get("file_path", "")} for e in entities]
        ids = [e["node_id"] for e in entities]

        new_ids, new_docs, new_metas = self._filter_new(ids, documents, metadatas)
        if new_ids:
            self.collection.upsert(documents=new_docs, metadatas=new_metas, ids=new_ids)

    def search(self, query: str, n_results: int = 5):
        return self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

    def search_ast_candidates(self, query: str, n_results: int = 15) -> List[str]:
        """Return the node_ids of the nearest AST entities for a query.

        Used during doc-to-code binding to pre-filter the candidate set sent
        to the LLM, so each binding call ships only the most relevant nodes
        instead of the entire graph.
        """
        res = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"type": "ast"},
        )
        metas = (res.get("metadatas") or [[]])[0]
        return [m["node_id"] for m in metas if m and m.get("node_id")]

    def delete_by_file(self, file_path: str):
        """Delete all vectors associated with a specific file."""
        self.collection.delete(where={"file_path": file_path})
