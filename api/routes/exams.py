"""Exam planner."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import analytics
from core.auth import uid
from core.util import iso, jdumps, new_id, utcnow
from memory.schema import get_conn

router = APIRouter(tags=["exams"])


@router.get("/exams")
def list_exams() -> List[dict]:
    return analytics.upcoming_exams()


class ExamIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    exam_date: str = Field(..., description="ISO date or datetime")
    target: float = Field(default=0.9, ge=0.6, le=0.99)
    document_ids: List[str] = Field(default_factory=list)


@router.post("/exams")
def create_exam(body: ExamIn) -> dict:
    try:
        when = datetime.fromisoformat(body.exam_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="exam_date must be ISO formatted") from exc
    if when.tzinfo is None:
        when = when.replace(hour=9, tzinfo=timezone.utc) if len(body.exam_date) <= 10 else when.replace(tzinfo=timezone.utc)
    if when <= utcnow():
        raise HTTPException(status_code=400, detail="The exam date must be in the future.")
    exam_id = new_id("exam")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO exams (id, user_id, name, exam_date, target, document_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (exam_id, uid(), body.name, iso(when), body.target, jdumps(body.document_ids), iso(utcnow())),
        )
    return analytics.exam_plan(exam_id) or {}


@router.get("/exams/{exam_id}")
def get_plan(exam_id: str) -> dict:
    plan = analytics.exam_plan(exam_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return plan


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM exams WHERE id = ? AND user_id = ?", (exam_id, uid()))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Exam not found")
    return {"deleted": exam_id}
