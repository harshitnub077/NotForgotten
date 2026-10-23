"""
Per-user vector search over chunk embeddings stored in the main database.

A student's library is thousands of passages, not millions, so exact cosine
search with one matrix product beats running a separate vector database:
nothing extra to host, no consistency to manage, and per-user isolation is a
WHERE clause. Each user's matrix is cached in memory and invalidated by their
`library_version`, which the ingestion pipeline bumps on every change.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from memory.schema import get_conn

_DTYPE = np.float32
_CACHE_USERS = 64


@dataclass
class VectorHit:
    chunk_id: str
    document_id: str
    concept_id: str
    page: int
    text: str
    similarity: float


def to_blob(vec: Sequence[float]) -> bytes:
    return np.asarray(vec, dtype=_DTYPE).tobytes()


def from_blob(blob: Optional[bytes]) -> Optional[np.ndarray]:
    if blob is None:
        return None
    return np.frombuffer(bytes(blob), dtype=_DTYPE)


@dataclass
class _Index:
    version: int
    ids: List[str]
    meta: List[Tuple[str, str, int, str]]  # document_id, concept_id, page, text
    matrix: np.ndarray                      # (n, d), unit-normalised


class VectorStore:
    def __init__(self) -> None:
        self._cache: "OrderedDict[str, _Index]" = OrderedDict()
        self._lock = threading.Lock()

    def _version(self, user_id: str) -> int:
        with get_conn() as conn:
            row = conn.execute("SELECT library_version FROM users WHERE id = ?", (user_id,)).fetchone()
        return int(row["library_version"]) if row else -1

    def _backfill(self, user_id: str) -> None:
        """Embed passages imported before embeddings lived in the database."""
        with get_conn() as conn:
            missing = conn.execute(
                "SELECT id, text FROM chunks WHERE user_id = ? AND embedding IS NULL", (user_id,)
            ).fetchall()
        if not missing:
            return
        from ingestion.embedder import embed_texts

        vectors = embed_texts([r["text"] for r in missing])
        with get_conn() as conn:
            conn.executemany(
                "UPDATE chunks SET embedding = ? WHERE id = ?",
                [(to_blob(v), r["id"]) for r, v in zip(missing, vectors)],
            )

    def _index(self, user_id: str) -> _Index:
        version = self._version(user_id)
        with self._lock:
            cached = self._cache.get(user_id)
            if cached is not None and cached.version == version:
                self._cache.move_to_end(user_id)
                return cached
        self._backfill(user_id)
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT id, document_id, COALESCE(concept_id, '') AS concept_id, page, text, embedding
                   FROM chunks WHERE user_id = ? AND embedding IS NOT NULL ORDER BY document_id, idx""",
                (user_id,),
            ).fetchall()
        vecs = [from_blob(r["embedding"]) for r in rows]
        matrix = np.vstack(vecs).astype(_DTYPE) if vecs else np.zeros((0, 1), dtype=_DTYPE)
        if len(matrix):
            matrix /= np.linalg.norm(matrix, axis=1, keepdims=True).clip(1e-9)
        index = _Index(
            version=version,
            ids=[r["id"] for r in rows],
            meta=[(r["document_id"], r["concept_id"], int(r["page"]), r["text"]) for r in rows],
            matrix=matrix,
        )
        with self._lock:
            self._cache[user_id] = index
            self._cache.move_to_end(user_id)
            while len(self._cache) > _CACHE_USERS:
                self._cache.popitem(last=False)
        return index

    def query(
        self,
        embedding: Sequence[float],
        k: int = 8,
        document_ids: Optional[Sequence[str]] = None,
        user_id: Optional[str] = None,
    ) -> List[VectorHit]:
        from core.auth import uid

        index = self._index(user_id or uid())
        if not index.ids:
            return []
        q = np.asarray(embedding, dtype=_DTYPE)
        q = q / max(float(np.linalg.norm(q)), 1e-9)
        sims = index.matrix @ q
        if document_ids:
            allowed = set(document_ids)
            mask = np.array([m[0] in allowed for m in index.meta])
            sims = np.where(mask, sims, -np.inf)
        k = min(k, len(index.ids))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        hits: List[VectorHit] = []
        for i in top:
            if not np.isfinite(sims[i]):
                continue
            doc_id, concept_id, page, text = index.meta[i]
            hits.append(VectorHit(index.ids[i], doc_id, concept_id, page, text, max(0.0, float(sims[i]))))
        return hits

    def invalidate(self, user_id: Optional[str] = None) -> None:
        with self._lock:
            if user_id is None:
                self._cache.clear()
            else:
                self._cache.pop(user_id, None)


_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def cache_stats() -> Dict[str, int]:
    return {"users_cached": len(get_store()._cache)}
