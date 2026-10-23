"""Concepts: list, detail, knowledge graph, Feynman mode, card generation."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import analytics, settings
from core.auth import uid
from core.util import iso, jdumps, jloads, new_id, utcnow
from memory.schema import get_conn

router = APIRouter(tags=["concepts"])


@router.get("/concepts")
def list_concepts() -> List[dict]:
    return analytics.concept_list()


@router.get("/concepts/{concept_id}")
def concept(concept_id: str) -> dict:
    detail = analytics.concept_detail(concept_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return detail


@router.get("/graph")
def knowledge_graph(days: float = 0.0) -> dict:
    return analytics.graph(max(-365.0, min(days, 365.0)))


def _concept_material(concept_id: str):
    with get_conn() as conn:
        c = conn.execute("SELECT * FROM concepts WHERE id = ? AND user_id = ?", (concept_id, uid())).fetchone()
        if c is None:
            raise HTTPException(status_code=404, detail="Concept not found")
        chunks = conn.execute(
            "SELECT id, text FROM chunks WHERE concept_id = ? AND user_id = ? ORDER BY idx", (concept_id, uid())
        ).fetchall()
    return c, chunks


class FeynmanIn(BaseModel):
    explanation: str = Field(..., min_length=10, max_length=8000)


@router.post("/concepts/{concept_id}/feynman")
def feynman(concept_id: str, body: FeynmanIn) -> dict:
    from ingestion.embedder import embed_texts
    from nlp.grader import feynman_heuristic, feynman_with_llm

    c, chunks = _concept_material(concept_id)
    reference = c["summary"] + "\n" + "\n".join(ch["text"] for ch in chunks[:6])
    result = None
    if settings.get("use_llm"):
        result = feynman_with_llm(c["name"], reference, body.explanation)
    if result is None:
        result = feynman_heuristic(jloads(c["keywords"], [])[:8], reference, body.explanation, embed_texts)
    payload = result.__dict__
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO feynman_attempts (id, user_id, concept_id, explanation, score, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id("fey"), uid(), concept_id, body.explanation, result.score, jdumps(payload), iso(utcnow())),
        )
    return payload


class GenerateIn(BaseModel):
    n: int = Field(default=3, ge=1, le=8)


@router.post("/concepts/{concept_id}/generate")
def generate_more(concept_id: str, body: GenerateIn) -> dict:
    from nlp.cards import generate_cards

    c, chunks = _concept_material(concept_id)
    with get_conn() as conn:
        existing = {
            r["prompt"]
            for r in conn.execute(
                "SELECT prompt FROM cards WHERE concept_id = ? AND user_id = ?", (concept_id, uid())
            ).fetchall()
        }
    # Rotate through passages so new cards cover material the old ones didn't.
    offset = len(existing) % max(len(chunks), 1)
    window = (list(chunks[offset:]) + list(chunks[:offset]))[:4]
    drafts = generate_cards(
        c["name"],
        c["summary"],
        jloads(c["keywords"], []),
        [ch["text"] for ch in window],
        n_cards=body.n + 2,
        use_llm=bool(settings.get("use_llm")),
    )
    fresh = [d for d in drafts if d.prompt not in existing][: body.n]
    now = iso(utcnow())
    rows = [
        (
            new_id("card"),
            uid(),
            concept_id,
            c["document_id"],
            d.kind,
            d.prompt,
            d.answer,
            d.explanation,
            window[d.source_index]["id"] if d.source_index is not None and d.source_index < len(window) else None,
            "generated",
            now,
        )
        for d in fresh
    ]
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO cards (id, user_id, concept_id, document_id, kind, prompt, answer, explanation,
                   source_chunk_id, origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            "UPDATE documents SET card_count = (SELECT COUNT(*) FROM cards WHERE document_id = ?) WHERE id = ?",
            (c["document_id"], c["document_id"]),
        )
    return {"created": len(rows)}
