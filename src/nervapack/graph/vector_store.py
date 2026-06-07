import chromadb
from typing import List, Dict

class VectorStore:
    def __init__(self, db_path: str = ".nervapack/chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        # We use a single collection for both AST node summaries and Markdown chunks
        self.collection = self.client.get_or_create_collection(name="nervapack_nodes")

    def ingest_chunks(self, chunks: List[Dict[str, str]]):
        """
        Ingest a list of Markdown chunks into the vector store.
        """
        if not chunks:
            return

        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            documents.append(chunk["content"])
            metadatas.append({"header": chunk["header"], "file_path": chunk["file_path"], "type": "markdown"})
            ids.append(f"md_{chunk['file_path']}_{i}")

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def ingest_ast_entities(self, entities: List[Dict[str, str]]):
        """
        Ingest AST summaries into the vector store.
        """
        if not entities:
            return

        documents = []
        metadatas = []
        ids = []

        for entity in entities:
            documents.append(entity["summary"])
            metadatas.append({"node_id": entity["node_id"], "type": "ast"})
            ids.append(entity["node_id"])

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query: str, n_results: int = 5):
        return self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
