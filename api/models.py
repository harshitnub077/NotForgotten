"""Pydantic request/response models for the FastAPI layer."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class SessionStartRequest(BaseModel):
    top_n: int = Field(default=10, ge=1, le=50, description="Number of urgent concepts to return.")


class UrgentConcept(BaseModel):
    concept_id: str
    urgency_score: float
    next_review: Optional[str] = None
    mastery_level: Optional[float] = None


class SessionStartResponse(BaseModel):
    urgent_concepts: list[UrgentConcept]
    total_concepts: int


# ---------------------------------------------------------------------------
# Query models
# ---------------------------------------------------------------------------


class SessionQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Optional pre-supplied rating (skips interactive assess).",
    )
    alpha: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override semantic weight for this request.",
    )


class ChunkSource(BaseModel):
    concept_tag: str
    source_file: str
    page_num: int
    semantic_score: float
    urgency_score: float
    final_score: float


class SessionQueryResponse(BaseModel):
    session_id: str
    answer: str
    chunks: list[ChunkSource]
    reteach_count: int = 0
    schedule_message: Optional[str] = None
    next_review_info: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Rate models
# ---------------------------------------------------------------------------


class SessionRateRequest(BaseModel):
    session_id: Optional[str] = None
    concept_id: str
    rating: int = Field(..., ge=1, le=5)


class SessionRateResponse(BaseModel):
    concept_id: str
    new_interval_days: int
    new_easiness_factor: float
    next_review: str
    message: str


# ---------------------------------------------------------------------------
# Dashboard models
# ---------------------------------------------------------------------------


class ConceptMemoryRecord(BaseModel):
    concept_id: str
    easiness_factor: float
    interval_days: int
    repetitions: int
    last_review: Optional[str]
    next_review: Optional[str]
    retention_prob: float
    urgency_score: float


class AtRiskConcept(BaseModel):
    concept_id: str
    retention_prob: float
    urgency_score: float


class WeeklyReview(BaseModel):
    day: str
    count: int


class RecentSource(BaseModel):
    filename: str
    upload_date: str
    concept_count: int


class DashboardResponse(BaseModel):
    memory: list[ConceptMemoryRecord]
    knowledge_graph: dict[str, Any]
    total_sessions: int
    stats: dict[str, Any]
