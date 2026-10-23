"""
Memory-aware AI tutor (Server-Sent Events stream).

The tutor sees two things a normal chatbot doesn't: passages retrieved with
forgetting-weighted ranking, and the learner's memory state. It weaves
quick recall checks for slipping concepts into its answers, so every
conversation also does review work.
"""
from __future__ import annotations

import json
from typing import Dict, Iterator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import analytics, settings
from core.auth import uid
from core.util import iso, new_id, utcnow
from llm.client import LLMUnavailable, get_llm
from memory.schema import get_conn

router = APIRouter(tags=["tutor"])

MODES = {
    "explain": (
        "Explain clearly and concretely, building from what the student already knows. Use a "
        "short example or analogy. End with ONE quick recall question about the most important idea."
    ),
    "socratic": (
        "Teach Socratically: do not hand over the full answer. Ask one guiding question at a time, "
        "give a hint when the student is stuck, and confirm when they reach the insight."
    ),
    "quiz": (
        "Quiz the student. Ask one question at a time, prioritising concepts listed as fading. "
        "After each answer, say whether it's right, correct misconceptions briefly, then ask the next."
    ),
}


class Turn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=12000)


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[Turn] = Field(default_factory=list)
    mode: str = Field(default="explain", pattern="^(explain|socratic|quiz)$")
    document_ids: Optional[List[str]] = None


def _sse(payload: Dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _system_prompt(mode: str, sources: List[Dict], fading: List[Dict]) -> str:
    ctx = "\n\n".join(
        f"[{i + 1}] ({s['document_title']} · {s['concept_name']} · p.{s['page'] + 1})\n{s['text']}"
        for i, s in enumerate(sources)
    ) or "(The student's library is empty.)"
    fading_txt = "\n".join(
        f"- {c['name']} (recall probability {round((c['retention'] or 0) * 100)}%)" for c in fading
    ) or "- none"
    return f"""You are NotForgotten, a warm, rigorous tutor who knows the student's memory state.

TEACHING MODE: {MODES[mode]}

GROUNDING: Base answers on the numbered library passages and cite them inline like [1] or [2].
If the passages don't cover the question, say so briefly, then answer from general knowledge and
mark that part "(general knowledge)". Never invent citations.

MEMORY STATE — concepts the student is forgetting:
{fading_txt}
When a fading concept is relevant, weave in a one-line "Quick recall:" check about it.

STYLE: Markdown. Short paragraphs, bold key terms, LaTeX with $...$ for maths. Under 300 words
unless the student asks for depth.

LIBRARY PASSAGES:
{ctx}"""


def _offline_answer(message: str, sources: List[Dict], fading: List[Dict]) -> Iterator[str]:
    if not sources:
        yield (
            "Your library is empty, so I have nothing to ground an answer in yet. Add a PDF, notes "
            "or a web page from the **Library** and ask again."
        )
        return
    yield "_Offline mode — showing the most relevant passages from your library._\n\n"
    for i, s in enumerate(sources[:3]):
        excerpt = s["text"].strip().replace("\n", " ")
        if len(excerpt) > 420:
            excerpt = excerpt[:420].rsplit(" ", 1)[0] + "…"
        yield f"**{s['concept_name'] or s['document_title']}** [{i + 1}]\n> {excerpt}\n\n"
    if fading:
        yield f"**Quick recall:** without looking — what do you remember about *{fading[0]['name']}*?"


@router.post("/tutor/chat")
def chat(body: ChatIn) -> StreamingResponse:
    from retrieval.hybrid import retrieve

    concepts = {c["id"]: c for c in analytics.concept_list()}
    try:
        ranked = retrieve(body.message, top_k=5, document_ids=body.document_ids)
    except Exception:  # noqa: BLE001 — empty store or model still loading
        ranked = []
    sources = [
        {
            **r.to_dict(),
            "concept_name": concepts.get(r.concept_id, {}).get("name", ""),
            "document_title": concepts.get(r.concept_id, {}).get("document_title", ""),
        }
        for r in ranked
    ]
    touched = {s["concept_id"] for s in sources}
    learned = [c for c in concepts.values() if c.get("retention") is not None]
    fading = sorted(
        [c for c in learned if c["retention"] < 0.8],
        key=lambda c: (c["id"] not in touched, c["retention"]),
    )[:4]

    use_llm = bool(settings.get("use_llm"))  # read now: the generator runs outside the request context

    def stream() -> Iterator[str]:
        yield _sse(
            {
                "type": "meta",
                "sources": [
                    {k: s[k] for k in ("chunk_id", "concept_id", "concept_name", "document_title", "page", "text", "semantic", "urgency", "score")}
                    for s in sources
                ],
                "fading": [{"id": c["id"], "name": c["name"], "retention": c["retention"]} for c in fading],
            }
        )
        llm = get_llm()
        produced = False
        if use_llm and llm.available:
            msgs = [{"role": t.role, "content": t.content} for t in body.history[-10:]]
            msgs.append({"role": "user", "content": body.message})
            try:
                for tok in llm.stream(_system_prompt(body.mode, sources, fading), msgs):
                    produced = True
                    yield _sse({"type": "token", "text": tok})
            except LLMUnavailable as exc:
                if produced:
                    yield _sse({"type": "error", "message": str(exc)})
        if not produced:
            for piece in _offline_answer(body.message, sources, fading):
                yield _sse({"type": "token", "text": piece})
        yield _sse({"type": "done", "llm": llm.status()})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class CardsFromChatIn(BaseModel):
    text: str = Field(..., min_length=20, max_length=12000)
    concept_id: Optional[str] = None
    n: int = Field(default=3, ge=1, le=6)


@router.post("/tutor/cards")
def cards_from_chat(body: CardsFromChatIn) -> dict:
    """Turn a tutor explanation into review cards ("Remember this")."""
    from nlp.cards import generate_cards
    from nlp.text import keyphrases

    concept_id = body.concept_id
    with get_conn() as conn:
        if concept_id is None:
            raise HTTPException(status_code=400, detail="concept_id is required")
        c = conn.execute("SELECT * FROM concepts WHERE id = ? AND user_id = ?", (concept_id, uid())).fetchone()
        if c is None:
            raise HTTPException(status_code=404, detail="Concept not found")
    kws = (keyphrases([body.text]) or [[]])[0]
    drafts = generate_cards(c["name"], c["summary"], kws, [body.text], n_cards=body.n, use_llm=bool(settings.get("use_llm")))
    now = iso(utcnow())
    rows = [
        (new_id("card"), uid(), concept_id, c["document_id"], d.kind, d.prompt, d.answer, d.explanation, "tutor", now)
        for d in drafts
    ]
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO cards (id, user_id, concept_id, document_id, kind, prompt, answer, explanation, origin, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    return {"created": len(rows), "cards": [{"prompt": d.prompt, "answer": d.answer, "kind": d.kind} for d in drafts]}
