"""Dashboard route: GET /dashboard"""
from __future__ import annotations
from api.models import ConceptMemoryRecord, DashboardResponse
from fastapi import APIRouter
from knowledge_graph.concept_graph import get_concept_graph
from memory.schema import get_conn, init_db

router = APIRouter(tags=["dashboard"])

@router.get("/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    """
    Return the complete memory state for frontend visualisation.
    Includes:
     - All concept_memory rows
     - Knowledge graph nodes/edges/stats
     - Total session count
     - Aggregate stats
    """
    init_db()

    with get_conn() as conn:
        memory_rows = conn.execute("SELECT * FROM concept_memory").fetchall()
        total_sessions = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM session_log"
        ).fetchone()[0] or 0

    memory: list[ConceptMemoryRecord] = [
        ConceptMemoryRecord(
            concept_id=r["concept_id"],
            easiness_factor=r["easiness_factor"],
            interval_days=r["interval_days"],
            repetitions=r["repetitions"],
            last_review=r["last_review"],
            next_review=r["next_review"],
            retention_prob=r["retention_prob"],
            urgency_score=1.0 - (r["retention_prob"] or 1.0),
        )
        for r in memory_rows
    ]

    kg = get_concept_graph()
    kg_dict = kg.to_dict()

    # Aggregate stats
    avg_ease = (
        sum(m.easiness_factor for m in memory) / len(memory) if memory else 2.5
    )
    avg_interval = (
        sum(m.interval_days for m in memory) / len(memory) if memory else 1.0
    )
    avg_retention = (
        sum(m.retention_prob for m in memory) / len(memory) if memory else 1.0
    )

    stats = {
        "total_concepts": len(memory),
        "avg_easiness_factor": round(avg_ease, 3),
        "avg_interval_days": round(avg_interval, 1),
        "avg_retention_prob": round(avg_retention, 3),
        "total_sessions": total_sessions,
        "knowledge_graph": kg_dict.get("stats", {}),
    }

    return DashboardResponse(
        memory=memory,
        knowledge_graph=kg_dict,
        total_sessions=total_sessions,
        stats=stats,
    )
