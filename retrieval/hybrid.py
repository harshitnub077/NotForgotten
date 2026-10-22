"""
Memory-aware retrieval.

    score = α · semantic_similarity + (1 − α) · urgency(concept)
    urgency = 1 − R_concept           (0.5 for concepts not yet studied)

Among passages that answer the question about equally well, the ones
from concepts you're forgetting are surfaced first, so every tutor answer
doubles as a review of what is slipping.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence

from retrieval.vector_store import VectorHit

DEFAULT_ALPHA = 0.75
UNSTUDIED_URGENCY = 0.5


@dataclass
class RankedChunk:
    chunk_id: str
    document_id: str
    concept_id: str
    page: int
    text: str
    semantic: float
    urgency: float
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


def rerank(
    hits: Sequence[VectorHit],
    concept_retention: Dict[str, Optional[float]],
    alpha: float = DEFAULT_ALPHA,
    top_k: int = 6,
) -> List[RankedChunk]:
    ranked: List[RankedChunk] = []
    for h in hits:
        r = concept_retention.get(h.concept_id)
        urgency = UNSTUDIED_URGENCY if r is None else 1.0 - r
        ranked.append(
            RankedChunk(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                concept_id=h.concept_id,
                page=h.page,
                text=h.text,
                semantic=round(h.similarity, 4),
                urgency=round(urgency, 4),
                score=round(alpha * h.similarity + (1 - alpha) * urgency, 4),
            )
        )
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked[:top_k]


def retrieve(
    query: str,
    top_k: int = 6,
    alpha: float = DEFAULT_ALPHA,
    document_ids: Optional[Sequence[str]] = None,
) -> List[RankedChunk]:
    from core.memory import concept_stats
    from ingestion.embedder import get_embedder
    from retrieval.vector_store import get_store

    vec = get_embedder().embed(query)
    hits = get_store().query(vec, k=top_k * 3, document_ids=document_ids)
    stats = concept_stats()
    retention = {cid: s["retention"] for cid, s in stats.items()}
    return rerank(hits, retention, alpha, top_k)
