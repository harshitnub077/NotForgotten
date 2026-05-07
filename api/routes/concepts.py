"""Concepts route: GET /concepts"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from memory.schema import get_conn
import datetime

router = APIRouter(tags=["concepts"])

class ConceptSchema(BaseModel):
    concept_id: str
    source_file: Optional[str]
    retention_prob: float
    urgency_score: float
    interval_days: int
    repetitions: int
    last_review: Optional[str]
    next_review: Optional[str]
    status: str

@router.get("/concepts", response_model=List[ConceptSchema])
def get_concepts() -> List[ConceptSchema]:
    """
    Return all tracked concepts with their current memory status.
    """
    now = datetime.datetime.utcnow()
    
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM concept_memory").fetchall()
    
    concepts = []
    for r in rows:
        # Calculate urgency and status
        retention = r["retention_prob"] if r["retention_prob"] is not None else 1.0
        next_rev_str = r["next_review"]
        
        status = "strong"
        if retention < 0.55:
            status = "urgent"
        elif next_rev_str:
            try:
                next_rev = datetime.datetime.fromisoformat(next_rev_str)
                if next_rev <= now:
                    status = "urgent"
                elif (next_rev - now).days <= 2:
                    status = "due_soon"
            except (ValueError, TypeError):
                pass
        elif retention >= 0.9: # New concepts start at strong
            status = "strong"
        
        concepts.append(ConceptSchema(
            concept_id=r["concept_id"],
            source_file=r["source_file"],
            retention_prob=retention,
            urgency_score=1.0 - retention,
            interval_days=r["interval_days"],
            repetitions=r["repetitions"],
            last_review=r["last_review"],
            next_review=r["next_review"],
            status=status
        ))
        
    return concepts
