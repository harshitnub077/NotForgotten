"""Card CRUD."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import settings
from core.memory import card_view
from core.util import iso, new_id, utcnow
from memory.schema import get_conn, init_db

router = APIRouter(tags=["cards"])


@router.get("/cards")
def list_cards(concept_id: Optional[str] = None, document_id: Optional[str] = None, include_suspended: bool = True) -> List[dict]:
    init_db()
    clauses, params = [], []
    if concept_id:
        clauses.append("concept_id = ?")
        params.append(concept_id)
    if document_id:
        clauses.append("document_id = ?")
        params.append(document_id)
    if not include_suspended:
        clauses.append("suspended = 0")
    sql = "SELECT * FROM cards" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY created_at"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    fsrs, now = settings.get_fsrs(), utcnow()
    return [{**card_view(r, fsrs, now, with_preview=False), "suspended": bool(r["suspended"])} for r in rows]


class CardIn(BaseModel):
    concept_id: str
    kind: str = Field(default="qa", pattern="^(qa|cloze|explain)$")
    prompt: str = Field(..., min_length=3, max_length=1000)
    answer: str = Field(..., min_length=1, max_length=1000)
    explanation: str = Field(default="", max_length=1000)


@router.post("/cards")
def create_card(body: CardIn) -> dict:
    with get_conn() as conn:
        c = conn.execute("SELECT document_id FROM concepts WHERE id = ?", (body.concept_id,)).fetchone()
        if c is None:
            raise HTTPException(status_code=404, detail="Concept not found")
        cid = new_id("card")
        conn.execute(
            """INSERT INTO cards (id, concept_id, document_id, kind, prompt, answer, explanation, origin, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)""",
            (cid, body.concept_id, c["document_id"], body.kind, body.prompt, body.answer, body.explanation, iso(utcnow())),
        )
    return {"id": cid}


class CardPatch(BaseModel):
    prompt: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    answer: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    explanation: Optional[str] = Field(default=None, max_length=1000)
    suspended: Optional[bool] = None


@router.patch("/cards/{card_id}")
def update_card(card_id: str, patch: CardPatch) -> dict:
    values = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not values:
        return {"updated": 0}
    if "suspended" in values:
        values["suspended"] = int(values["suspended"])
    sets = ", ".join(f"{k} = ?" for k in values)
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE cards SET {sets} WHERE id = ?", (*values.values(), card_id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"updated": cur.rowcount}


@router.delete("/cards/{card_id}")
def delete_card(card_id: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"deleted": card_id}
