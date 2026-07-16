import os
import chromadb
from typing import List, Dict, Optional


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
    resolved = model_path or os.environ.get("NERVAPACK_ONNX_MODEL")
    if resolved:
        from pathlib import Path
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

        model_dir = Path(resolved).expanduser().resolve()

        # Subclass to redirect DOWNLOAD_PATH without mutating the global class
        class _LocalONNX(ONNXMiniLM_L6_V2):
            DOWNLOAD_PATH = model_dir
            EXTRACTED_FOLDER_NAME = "onnx"

        return _LocalONNX()
    return None  # use ChromaDB's default (downloads on first use if not cached)


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
        ids = [f"md_{c['file_path']}_{i}" for i, c in enumerate(chunks)]

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

    def delete_by_file(self, file_path: str):
        """Delete all vectors associated with a specific file."""
        self.collection.delete(where={"file_path": file_path})
