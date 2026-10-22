"""Card memory state: loading, presenting, reviewing, and concept roll-ups."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from core import settings
from core.util import iso, parse_dt, utcnow
from memory.fsrs import FSRS, MemoryState
from memory.planner import CardMemory
from memory.schema import get_conn, init_db

RATING_LABELS = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


def fmt_interval(days: float) -> str:
    if days < 1 / 24:
        return f"{max(1, round(days * 1440))}m"
    if days < 1:
        return f"{round(days * 24)}h"
    if days < 30:
        return f"{round(days)}d"
    if days < 365:
        return f"{days / 30.4:.1f}mo"
    return f"{days / 365:.1f}y"


def to_memory(row: sqlite3.Row) -> CardMemory:
    return CardMemory(
        card_id=row["id"],
        stability=row["stability"],
        difficulty=row["difficulty"],
        last_review=parse_dt(row["last_review"]),
        due=parse_dt(row["due"]),
        concept_id=row["concept_id"],
    )


def fetch_cards(where: str = "", params: Iterable[Any] = ()) -> List[sqlite3.Row]:
    init_db()
    sql = "SELECT * FROM cards WHERE suspended = 0"
    if where:
        sql += f" AND ({where})"
    with get_conn() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def card_view(row: sqlite3.Row, fsrs: FSRS, now: datetime, with_preview: bool = True) -> Dict[str, Any]:
    mem = to_memory(row)
    elapsed = mem.elapsed_days(now)
    r = None if mem.is_new else fsrs.retrievability(elapsed, float(mem.stability))
    view: Dict[str, Any] = {
        "id": row["id"],
        "concept_id": row["concept_id"],
        "document_id": row["document_id"],
        "kind": row["kind"],
        "prompt": row["prompt"],
        "answer": row["answer"],
        "explanation": row["explanation"],
        "origin": row["origin"],
        "is_new": mem.is_new,
        "stability": row["stability"],
        "difficulty": row["difficulty"],
        "due": row["due"],
        "last_review": row["last_review"],
        "reps": row["reps"],
        "lapses": row["lapses"],
        "retrievability": None if r is None else round(r, 4),
        "half_life_days": None if mem.is_new else round(fsrs.half_life(float(mem.stability)), 1),
    }
    if with_preview:
        preview = fsrs.preview(mem.state(), elapsed)
        view["preview"] = {
            str(rating): {
                "label": RATING_LABELS[rating],
                "interval_days": round(days, 4),
                "interval": fmt_interval(days),
                "stability": round(state.stability, 3),
            }
            for rating, (state, days) in preview.items()
        }
    return view


def submit_review(
    card_id: str,
    rating: int,
    response: Optional[str] = None,
    score: Optional[float] = None,
    confidence: Optional[float] = None,
    duration_ms: Optional[int] = None,
    session_id: Optional[str] = None,
    now: Optional[datetime] = None,
    fsrs: Optional[FSRS] = None,
) -> Dict[str, Any]:
    if rating not in (1, 2, 3, 4):
        raise ValueError("rating must be 1-4")
    init_db()
    now = now or utcnow()
    fsrs = fsrs or settings.get_fsrs()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if row is None:
            raise KeyError(card_id)
        mem = to_memory(row)
        elapsed = mem.elapsed_days(now)
        prev = mem.state()
        r_before = None if prev is None else fsrs.retrievability(elapsed, prev.stability)
        new_state = fsrs.next_state(prev, elapsed, rating)
        days = fsrs.schedule_days(new_state, rating)
        due = now + timedelta(days=days)
        conn.execute(
            """UPDATE cards SET stability = ?, difficulty = ?, due = ?, last_review = ?,
                   reps = reps + 1, lapses = lapses + ? WHERE id = ?""",
            (
                new_state.stability,
                new_state.difficulty,
                iso(due),
                iso(now),
                1 if (rating == 1 and prev is not None) else 0,
                card_id,
            ),
        )
        conn.execute(
            """INSERT INTO reviews (card_id, rating, score, confidence, response, elapsed_days,
                   scheduled_days, retrievability, stability_before, stability_after,
                   difficulty_after, duration_ms, session_id, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card_id,
                rating,
                score,
                confidence,
                response,
                round(elapsed, 5),
                round(days, 5),
                r_before,
                None if prev is None else prev.stability,
                new_state.stability,
                new_state.difficulty,
                duration_ms,
                session_id,
                iso(now),
            ),
        )
    return {
        "card_id": card_id,
        "rating": rating,
        "retrievability_before": None if r_before is None else round(r_before, 4),
        "stability_before": None if prev is None else round(prev.stability, 3),
        "stability_after": round(new_state.stability, 3),
        "difficulty_after": round(new_state.difficulty, 3),
        "interval_days": round(days, 4),
        "interval": fmt_interval(days),
        "due": iso(due),
        "half_life_days": round(fsrs.half_life(new_state.stability), 1),
    }


def concept_stats(
    fsrs: Optional[FSRS] = None,
    at: Optional[datetime] = None,
    rows: Optional[List[sqlite3.Row]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Per-concept roll-up of card memory, evaluated at time *at*."""
    fsrs = fsrs or settings.get_fsrs()
    at = at or utcnow()
    rows = rows if rows is not None else fetch_cards()
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = row["concept_id"]
        if cid is None:
            continue
        agg = out.setdefault(
            cid,
            {"cards": 0, "learned": 0, "due": 0, "_r": [], "_s": [], "_d": []},
        )
        agg["cards"] += 1
        mem = to_memory(row)
        if mem.is_new:
            continue
        agg["learned"] += 1
        agg["_r"].append(fsrs.retrievability(mem.elapsed_days(at), float(mem.stability)))
        agg["_s"].append(float(mem.stability))
        agg["_d"].append(float(mem.difficulty or 5.0))
        if mem.due is not None and mem.due <= at:
            agg["due"] += 1
    for agg in out.values():
        r, s, d = agg.pop("_r"), agg.pop("_s"), agg.pop("_d")
        agg["retention"] = round(sum(r) / len(r), 4) if r else None
        agg["stability"] = round(sum(s) / len(s), 2) if s else None
        agg["difficulty"] = round(sum(d) / len(d), 2) if d else None
        # Mastery blends how much is learned with how well it's held.
        agg["mastery"] = round((agg["learned"] / agg["cards"]) * (agg["retention"] or 0.0), 4)
    return out


def memory_curve(state: Optional[MemoryState], last_review: Optional[datetime], fsrs: FSRS, days: int = 60) -> List[Dict[str, float]]:
    """Points of a card/concept forgetting curve from its last review onwards."""
    if state is None or last_review is None:
        return []
    return [
        {"t": t, "r": round(fsrs.retrievability(t, state.stability), 4)}
        for t in range(0, days + 1)
    ]
