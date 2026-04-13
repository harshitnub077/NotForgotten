"""
Hybrid Retriever — blends semantic similarity with forgetting urgency.

Final score = α × semantic_similarity + (1−α) × urgency_score
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import chromadb
from dotenv import load_dotenv

from ingestion.embedder import get_embedder
from memory.forgetting_scorer import ForgettingScorer
from memory.schema import get_conn, init_db

load_dotenv()

DB_DIR = os.getenv("CHROMA_DB_DIR", "./data/chroma")
_DEFAULT_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.6"))
_DEFAULT_TOP_K = int(os.getenv("TOP_K", "5"))
COLLECTION_NAME = "chunks"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RetrievedChunk:
    text: str
    concept_tag: str
    source_file: str
    page_num: int
    semantic_score: float
    urgency_score: float
    final_score: float
    chroma_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------


class HybridRetriever:
    """
    Parallel semantic + urgency retrieval with configurable blending.
    """

    def __init__(
        self,
        alpha: float = _DEFAULT_ALPHA,
        top_k: int = _DEFAULT_TOP_K,
    ) -> None:
        self.alpha = alpha
        self.top_k = top_k
        self._client: chromadb.ClientAPI | None = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """
        Retrieve and re-rank chunks for *query*.
        """
        embedder = get_embedder()
        query_vector = embedder.embed(query)

        # ── Semantic candidates ──────────────────────────────────────────
        candidates = self._semantic_search(query_vector, limit=self.top_k * 3)

        if not candidates:
            return []

        # ── Urgency lookup ───────────────────────────────────────────────
        scorer = ForgettingScorer()
        urgency_map = scorer.score_all()

        # ── Score & rank ─────────────────────────────────────────────────
        scored: list[RetrievedChunk] = []
        for chunk in candidates:
            u = urgency_map.get(chunk.concept_tag, 0.0)
            final = self.alpha * chunk.semantic_score + (1 - self.alpha) * u
            scored.append(
                RetrievedChunk(
                    text=chunk.text,
                    concept_tag=chunk.concept_tag,
                    source_file=chunk.source_file,
                    page_num=chunk.page_num,
                    semantic_score=chunk.semantic_score,
                    urgency_score=u,
                    final_score=round(final, 6),
                    chroma_id=chunk.chroma_id,
                )
            )

        scored.sort(key=lambda c: c.final_score, reverse=True)
        return scored[: self.top_k]

    def ensure_concept_exists(self, concept_id: str) -> None:
        """Insert concept_id into concept_memory if not already present."""
        init_db()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO concept_memory (concept_id)
                VALUES (?)
                """,
                (concept_id,),
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _semantic_search(
        self,
        vector: list[float],
        limit: int,
    ) -> list["_RawChunk"]:
        client = self._get_client()
        try:
            collection = client.get_collection(name=COLLECTION_NAME)
        except Exception:
            return [] # collection doesn't exist yet

        response = collection.query(
            query_embeddings=[vector],
            n_results=limit,
            include=["documents", "metadatas", "distances"] # type: ignore
        )

        results: list[_RawChunk] = []
        if not response['ids'] or len(response['ids']) == 0:
            return results

        # Chroma returns distance, we want to map it to a similarity score [0, 1]
        # Cosine distance to similarity: similarity = 1 - (distance / 2)
        # Using a simple conversion if the embedder uses cosine.
        distances = response['distances'][0] if response['distances'] else [] # type: ignore
        metadatas = response['metadatas'][0] if response['metadatas'] else [] # type: ignore
        documents = response['documents'][0] if response['documents'] else [] # type: ignore
        ids = response['ids'][0]

        for i in range(len(ids)):
            distance = distances[i] if i < len(distances) else 1.0 # type: ignore
            # convert distance roughly to a 0-1 similarity score
            certainty = max(0.0, 1.0 - (float(distance) / 2.0))
            meta = metadatas[i] if i < len(metadatas) else {} # type: ignore
            
            results.append(
                _RawChunk(
                    text=str(documents[i]),
                    concept_tag=str(meta.get("concept_tag", "")),
                    source_file=str(meta.get("source_file", "")),
                    page_num=int(meta.get("page_num", 0)),
                    semantic_score=float(certainty),
                    chroma_id=str(ids[i]),
                )
            )
        return results

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            os.makedirs(DB_DIR, exist_ok=True)
            self._client = chromadb.PersistentClient(path=DB_DIR)
        return self._client

    def close(self) -> None:
        if self._client:
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# Internal dataclass (not exported)
# ---------------------------------------------------------------------------


@dataclass
class _RawChunk:
    text: str
    concept_tag: str
    source_file: str
    page_num: int
    semantic_score: float
    chroma_id: str
