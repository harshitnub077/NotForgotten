"""
GET /graph — Knowledge graph data for frontend visualisation.

Returns all tracked concepts as nodes (with retention/urgency)
and any prerequisite edges stored in the database.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["graph"])


class GraphNode(BaseModel):
    id: str
    retention: float
    urgency: float
    file: str | None = None
    repetitions: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("/graph", response_model=GraphResponse)
def knowledge_graph() -> GraphResponse:
    """
    Return all concept nodes with their memory state and any known edges.
    Edges represent prerequisite relationships; currently sourced from
    the concept_memory table (future: semantic edge extraction).
    """
    from memory.schema import get_conn, init_db
    from memory.forgetting_scorer import ForgettingScorer

    init_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, retention_prob, repetitions,
                   COALESCE(source_file, '') AS source_file
            FROM concept_memory
            """
        ).fetchall()

    # Compute urgency via forgetting scorer
    try:
        scorer = ForgettingScorer()
        urgency_map = scorer.score_all()
    except Exception:
        urgency_map = {}

    nodes: list[GraphNode] = []
    for row in rows:
        cid = row["concept_id"]
        nodes.append(
            GraphNode(
                id=cid,
                retention=round(float(row["retention_prob"]), 4),
                urgency=round(urgency_map.get(cid, 1.0 - float(row["retention_prob"])), 4),
                file=row["source_file"] or None,
                repetitions=int(row["repetitions"]),
            )
        )

    # Edges: currently empty unless concept_edges table exists
    edges: list[GraphEdge] = []
    try:
        with get_conn() as conn:
            edge_rows = conn.execute(
                "SELECT source_concept, target_concept FROM concept_edges"
            ).fetchall()
            edges = [GraphEdge(source=r["source_concept"], target=r["target_concept"]) for r in edge_rows]
    except Exception:
        pass  # Table doesn't exist yet — that's fine

    return GraphResponse(nodes=nodes, edges=edges)
