"""Session routes: /session/start, /session/query, /session/rate"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from agent.graph import get_graph
from api.models import (
    ChunkSource,
    SessionQueryRequest,
    SessionQueryResponse,
    SessionRateRequest,
    SessionRateResponse,
    SessionStartRequest,
    SessionStartResponse,
    UrgentConcept,
)
from knowledge_graph.concept_graph import get_concept_graph
from memory.forgetting_scorer import ForgettingScorer
from memory.schema import get_conn, init_db
from memory.sm2 import sm2
from retrieval.hybrid_retriever import HybridRetriever

router = APIRouter(prefix="/session", tags=["session"])


# ---------------------------------------------------------------------------
# POST /session/start
# ---------------------------------------------------------------------------


@router.post("/start", response_model=SessionStartResponse)
def session_start(req: SessionStartRequest = SessionStartRequest()) -> SessionStartResponse:
    """
    Return today's highest-urgency concepts so the user knows what to study.
    """
    init_db()
    scorer = ForgettingScorer()
    top = scorer.top_urgent(n=req.top_n)

    graph = get_concept_graph()

    # Fetch next_review dates from SQLite
    with get_conn() as conn:
        rows = {
            r["concept_id"]: r
            for r in conn.execute("SELECT * FROM concept_memory").fetchall()
        }

    urgent_concepts: list[UrgentConcept] = []
    for concept_id, urgency in top:
        row = rows.get(concept_id)
        mastery = graph.mastery_level(concept_id)
        urgent_concepts.append(
            UrgentConcept(
                concept_id=concept_id,
                urgency_score=round(urgency, 4),
                next_review=row["next_review"] if row else None,
                mastery_level=round(mastery, 4),
            )
        )

    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM concept_memory").fetchone()[0]

    return SessionStartResponse(
        urgent_concepts=urgent_concepts,
        total_concepts=total,
    )


# ---------------------------------------------------------------------------
# POST /session/query
# ---------------------------------------------------------------------------


@router.post("/query", response_model=SessionQueryResponse)
def session_query(req: SessionQueryRequest) -> SessionQueryResponse:
    """
    Run the full LangGraph pipeline for a user query.
    Returns the answer, sources, and updated review schedule.
    """
    init_db()
    session_id = req.session_id or str(uuid.uuid4())

    initial_state = {
        "session_id": session_id,
        "query": req.query,
        "rating": req.rating,  # None → assess_node will wait for /session/rate
        "reteach_count": 0,
        "messages": [],
    }

    # Override alpha if provided
    if req.alpha is not None:
        # Temporarily patch env — in production use a proper DI approach
        import os
        os.environ["HYBRID_ALPHA"] = str(req.alpha)

    try:
        graph = get_graph()
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Build source list
    chunks_raw: list[dict] = final_state.get("chunks", [])
    sources = [
        ChunkSource(
            concept_tag=c.get("concept_tag", ""),
            source_file=c.get("source_file", ""),
            page_num=c.get("page_num", 0),
            semantic_score=c.get("semantic_score", 0.0),
            urgency_score=c.get("urgency_score", 0.0),
            final_score=c.get("final_score", 0.0),
        )
        for c in chunks_raw
    ]

    # Update knowledge graph mastery if rating is available
    rating = final_state.get("rating")
    if rating:
        kg = get_concept_graph()
        for concept_id in final_state.get("concept_ids", []):
            kg.update_mastery(concept_id, rating)
        kg.save()

    return SessionQueryResponse(
        session_id=session_id,
        answer=final_state.get("answer", ""),
        sources=sources,
        reteach_count=final_state.get("reteach_count", 0),
        schedule_message=final_state.get("schedule_message"),
        next_review_info=final_state.get("next_review_info", {}),
    )


# ---------------------------------------------------------------------------
# POST /session/rate
# ---------------------------------------------------------------------------


@router.post("/rate", response_model=SessionRateResponse)
def session_rate(req: SessionRateRequest) -> SessionRateResponse:
    """
    Accept a user self-rating for a concept and update SM-2 memory.
    Use this when the client handles the assess step separately from query.
    """
    init_db()
    now = datetime.now(tz=timezone.utc)
    now_str = now.isoformat()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM concept_memory WHERE concept_id = ?",
            (req.concept_id,),
        ).fetchone()

        if row is None:
            # Auto-create on first rating
            conn.execute(
                "INSERT OR IGNORE INTO concept_memory (concept_id) VALUES (?)",
                (req.concept_id,),
            )
            row = conn.execute(
                "SELECT * FROM concept_memory WHERE concept_id = ?",
                (req.concept_id,),
            ).fetchone()

        result = sm2(
            rating=req.rating,
            easiness_factor=row["easiness_factor"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            now=now,
        )

        next_str = result.next_review.isoformat()

        conn.execute(
            """
            UPDATE concept_memory
            SET easiness_factor = ?,
                interval_days   = ?,
                repetitions     = ?,
                last_review     = ?,
                next_review     = ?
            WHERE concept_id = ?
            """,
            (
                result.easiness_factor,
                result.interval_days,
                result.repetitions,
                now_str,
                next_str,
                req.concept_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO session_log (session_id, concept_id, user_rating, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (req.session_id, req.concept_id, req.rating, now_str),
        )

    # Update knowledge graph
    kg = get_concept_graph()
    kg.update_mastery(req.concept_id, req.rating)
    kg.save()

    return SessionRateResponse(
        concept_id=req.concept_id,
        new_interval_days=result.interval_days,
        new_easiness_factor=result.easiness_factor,
        next_review=next_str,
        message=(
            f"Memory updated. Next review in {result.interval_days} day(s). "
            f"Ease factor: {result.easiness_factor:.2f}."
        ),
    )
