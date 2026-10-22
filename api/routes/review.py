"""Review sessions: build a queue, grade typed answers, record ratings."""
from __future__ import annotations

import random
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import analytics, settings
from core.memory import card_view, concept_stats, fetch_cards, submit_review, to_memory
from core.util import jloads, new_id, parse_dt, utcnow
from memory.planner import build_queue
from memory.schema import get_conn

router = APIRouter(tags=["review"])


@router.get("/review/queue")
def queue(
    mode: str = "due",
    minutes: Optional[float] = None,
    concept_id: Optional[str] = None,
    document_id: Optional[str] = None,
    exam_id: Optional[str] = None,
    limit: int = 200,
) -> dict:
    """
    Modes
      due    every due card + today's new-card allowance, most valuable first
      smart  time-boxed: the best reviews for *minutes* (may include not-yet-due)
      cram   lowest predicted recall first, regardless of schedule
      exam   cards for an exam, ordered by predicted recall on exam day
    Due/smart queues interleave concepts — mixing topics strengthens
    discrimination between them (the interleaving effect).
    """
    fsrs = settings.get_fsrs()
    now = utcnow()
    where, params = [], []
    exam = None
    if concept_id:
        where.append("concept_id = ?")
        params.append(concept_id)
    if document_id:
        where.append("document_id = ?")
        params.append(document_id)
    if exam_id:
        with get_conn() as conn:
            exam = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
        if exam is None:
            raise HTTPException(status_code=404, detail="Exam not found")
        docs = jloads(exam["document_ids"], [])
        if docs:
            where.append(f"document_id IN ({','.join('?' * len(docs))})")
            params.extend(docs)
    rows = fetch_cards(" AND ".join(where), params)
    by_id = {r["id"]: r for r in rows}
    mems = [to_memory(r) for r in rows]

    if mode == "cram":
        learned = [m for m in mems if not m.is_new]
        learned.sort(key=lambda m: fsrs.retrievability(m.elapsed_days(now), float(m.stability)))
        ordered = [m.card_id for m in learned] + [m.card_id for m in mems if m.is_new]
        reasons = {cid: "cram" for cid in ordered}
    elif mode == "exam" and exam is not None:
        when = parse_dt(exam["exam_date"])
        target = float(exam["target"])
        scored = []
        for m in mems:
            r_exam = 0.0 if m.is_new else fsrs.retrievability(m.elapsed_days(when), float(m.stability))
            if r_exam < target or (m.due and m.due <= now):
                scored.append((r_exam, m.card_id))
        scored.sort()
        ordered = [cid for _, cid in scored]
        reasons = {cid: "exam" for cid in ordered}
    else:
        focused = bool(concept_id or document_id)
        max_new = 50 if focused else max(0, int(settings.get("daily_new_limit")) - _new_today())
        items = build_queue(
            fsrs,
            mems,
            now,
            minutes=minutes if mode == "smart" else None,
            max_new=max_new,
        )
        ordered = _interleave([it.card_id for it in items], by_id)
        reasons = {it.card_id: it.reason for it in items}

    concept_names = {c["id"]: c["name"] for c in analytics.concept_list()}
    cards = []
    for cid in ordered[: max(1, min(limit, 500))]:
        view = card_view(by_id[cid], fsrs, now)
        view["reason"] = reasons.get(cid, "due")
        view["concept_name"] = concept_names.get(view["concept_id"], "")
        cards.append(view)
    return {"session_id": new_id("ses"), "mode": mode, "cards": cards}


def _new_today() -> int:
    from datetime import timedelta

    since = (utcnow() - timedelta(hours=24)).isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(DISTINCT card_id) FROM reviews WHERE stability_before IS NULL AND reviewed_at >= ?",
            (since,),
        ).fetchone()[0]


def _interleave(card_ids: List[str], rows) -> List[str]:
    """Avoid consecutive cards from the same concept while roughly keeping priority order."""
    pending = list(card_ids)
    out: List[str] = []
    last = None
    while pending:
        pick = next((i for i, cid in enumerate(pending[:6]) if rows[cid]["concept_id"] != last), 0)
        cid = pending.pop(pick)
        out.append(cid)
        last = rows[cid]["concept_id"]
    return out


class GradeIn(BaseModel):
    card_id: str
    response: str = Field(default="", max_length=4000)


@router.post("/review/grade")
def grade(body: GradeIn) -> dict:
    from ingestion.embedder import embed_texts
    from nlp.grader import grade as grade_answer

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (body.card_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Card not found")
    result = grade_answer(
        row["kind"],
        row["prompt"],
        row["answer"],
        body.response,
        embed=embed_texts,
        use_llm=bool(settings.get("use_llm")),
    )
    return result.__dict__


class AnswerIn(BaseModel):
    card_id: str
    rating: int = Field(..., ge=1, le=4)
    response: Optional[str] = Field(default=None, max_length=4000)
    score: Optional[float] = Field(default=None, ge=0, le=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=3_600_000)
    session_id: Optional[str] = None


@router.post("/review/answer")
def answer(body: AnswerIn) -> dict:
    fsrs = settings.get_fsrs()
    try:
        result = submit_review(
            body.card_id,
            body.rating,
            response=body.response,
            score=body.score,
            confidence=body.confidence,
            duration_ms=body.duration_ms,
            session_id=body.session_id,
            fsrs=fsrs,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Card not found") from exc
    with get_conn() as conn:
        concept_id = conn.execute("SELECT concept_id FROM cards WHERE id = ?", (body.card_id,)).fetchone()[0]
    stats = concept_stats(fsrs, rows=fetch_cards("concept_id = ?", (concept_id,)))
    result["concept_retention"] = (stats.get(concept_id) or {}).get("retention")
    return result


@router.get("/review/session/{session_id}")
def session_summary(session_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT r.*, c.prompt, c.concept_id FROM reviews r JOIN cards c ON c.id = r.card_id
               WHERE r.session_id = ? ORDER BY r.reviewed_at""",
            (session_id,),
        ).fetchall()
    if not rows:
        return {"session_id": session_id, "reviews": 0}
    gained = sum((r["stability_after"] or 0) - (r["stability_before"] or 0) for r in rows)
    with_conf = [r for r in rows if r["confidence"] is not None]
    return {
        "session_id": session_id,
        "reviews": len(rows),
        "correct": sum(1 for r in rows if r["rating"] > 1),
        "ratings": {str(k): sum(1 for r in rows if r["rating"] == k) for k in (1, 2, 3, 4)},
        "minutes": round(sum(r["duration_ms"] or 0 for r in rows) / 60_000.0, 1),
        "stability_gained_days": round(gained, 1),
        "mean_confidence": round(sum(r["confidence"] for r in with_conf) / len(with_conf), 3) if with_conf else None,
        "concepts": len({r["concept_id"] for r in rows}),
    }


@router.get("/review/peek")
def peek(n: int = 3) -> List[dict]:
    """A few random learned cards — used for the 'quick recall' warm-up on Today."""
    fsrs, now = settings.get_fsrs(), utcnow()
    rows = [r for r in fetch_cards() if r["stability"] is not None]
    random.shuffle(rows)
    return [card_view(r, fsrs, now, with_preview=False) for r in rows[: max(1, min(n, 10))]]
