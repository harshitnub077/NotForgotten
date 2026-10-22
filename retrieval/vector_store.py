"""ChromaDB-backed vector store for chunk embeddings."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Sequence

from dotenv import load_dotenv

load_dotenv()

COLLECTION = "chunks_v2"


@dataclass
class VectorHit:
    chunk_id: str
    document_id: str
    concept_id: str
    page: int
    text: str
    similarity: float


class VectorStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.getenv("CHROMA_DB_DIR", "./data/chroma")
        self._client = None
        self._lock = threading.Lock()

    def _collection(self):
        with self._lock:
            if self._client is None:
                import chromadb

                os.makedirs(self._path, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self._path)
            return self._client.get_or_create_collection(
                name=COLLECTION, metadata={"hnsw:space": "cosine"}
            )

    def add(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        texts: Sequence[str],
        metadatas: Sequence[dict],
        batch: int = 256,
    ) -> None:
        col = self._collection()
        for i in range(0, len(ids), batch):
            col.upsert(
                ids=list(ids[i : i + batch]),
                embeddings=[list(map(float, e)) for e in embeddings[i : i + batch]],
                documents=list(texts[i : i + batch]),
                metadatas=list(metadatas[i : i + batch]),
            )

    def update_concepts(self, ids: Sequence[str], concept_ids: Sequence[str]) -> None:
        col = self._collection()
        got = col.get(ids=list(ids), include=["metadatas"])
        metas = []
        lookup = dict(zip(ids, concept_ids))
        for cid, meta in zip(got["ids"], got["metadatas"]):
            meta = dict(meta or {})
            meta["concept_id"] = lookup[cid]
            metas.append(meta)
        if got["ids"]:
            col.update(ids=got["ids"], metadatas=metas)

    def query(
        self,
        embedding: Sequence[float],
        k: int = 8,
        document_ids: Optional[Sequence[str]] = None,
    ) -> List[VectorHit]:
        col = self._collection()
        if col.count() == 0:
            return []
        where = None
        if document_ids:
            where = {"document_id": {"$in": list(document_ids)}}
        res = col.query(
            query_embeddings=[list(map(float, embedding))],
            n_results=min(k, col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: List[VectorHit] = []
        for cid, doc, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            meta = meta or {}
            hits.append(
                VectorHit(
                    chunk_id=cid,
                    document_id=str(meta.get("document_id", "")),
                    concept_id=str(meta.get("concept_id", "")),
                    page=int(meta.get("page", 0)),
                    text=doc or "",
                    similarity=max(0.0, 1.0 - float(dist)),  # cosine distance → similarity
                )
            )
        return hits

    def delete_document(self, document_id: str) -> None:
        col = self._collection()
        col.delete(where={"document_id": document_id})


_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
