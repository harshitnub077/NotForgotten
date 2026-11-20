"""
POST /chat — Memory-aware AI Tutor endpoint.

Retrieves relevant chunks from ChromaDB, injects the user's current
memory state (weak concepts + due reviews), builds a system prompt,
and calls the LLM for a grounded, pedagogically aware response.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    memory_context: dict[str, Any]
    boosted_concepts: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_memory_context() -> dict[str, Any]:
    """Fetch weak concepts and due reviews from SQLite."""
    from memory.schema import get_conn, init_db

    init_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT concept_id, retention_prob, next_review FROM concept_memory"
        ).fetchall()

    memory = [dict(r) for r in rows]
    weak = [m for m in memory if m["retention_prob"] < 0.6]
    due = [m for m in memory if m.get("next_review") and m["next_review"] <= now_iso]

    return {
        "weak_concepts": [m["concept_id"] for m in sorted(weak, key=lambda x: x["retention_prob"])[:5]],
        "due_reviews": [m["concept_id"] for m in due[:5]],
        "avg_retention": round(
            sum(m["retention_prob"] for m in memory) / max(len(memory), 1), 3
        ),
    }


def _build_system_prompt(memory_ctx: dict, retrieved_chunks: list) -> str:
    weak_str = ", ".join(memory_ctx["weak_concepts"]) or "none"
    due_str = ", ".join(memory_ctx["due_reviews"]) or "none"
    avg = round(memory_ctx["avg_retention"] * 100, 1)

    ctx_text = "\n\n".join(
        f"[Source: {c.get('source_file', '?')} | Concept: {c.get('concept_tag', '?')}]\n{c['text']}"
        for c in retrieved_chunks[:4]
    ) if retrieved_chunks else "No documents uploaded yet."

    return f"""You are ForgetLess AI — a memory-aware personalized study tutor.

=== USER'S MEMORY STATE ===
Average retention: {avg}%
Weak concepts (retention < 60%): {weak_str}
Due for review today: {due_str}

=== YOUR BEHAVIOR ===
1. Answer the user's question clearly, concisely, and with depth.
2. Proactively reinforce weak concepts whenever relevant.
3. Occasionally (not always) inject a "you might be forgetting..." reminder for high-urgency concepts.
4. Use the Socratic method: pose follow-up questions that prompt active recall.
5. If a concept is in the weak list, explain it more carefully even if not directly asked.
6. Be encouraging but honest about forgetting risks.

=== KNOWLEDGE BASE CONTEXT ===
{ctx_text}

Respond in a clear, educational tone. Use markdown formatting (bold, code blocks, bullet lists) where helpful."""


def _call_llm(system_prompt: str, history: list[ChatMessage], user_message: str) -> str:
    """Attempt real LLM call. Falls back to a rule-based mock."""

    # Try Groq (existing integration)
    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
        msgs = [{"role": "system", "content": system_prompt}]
        for h in history[-6:]:
            msgs.append({"role": h.role, "content": h.content})
        msgs.append({"role": "user", "content": user_message})

        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama3-8b-8192"),
            messages=msgs,  # type: ignore
            max_tokens=900,
            temperature=0.7,
        )
        return completion.choices[0].message.content or "..."
    except Exception:
        pass

    # Try Anthropic Claude
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msgs = []
        for h in history[-6:]:
            msgs.append({"role": h.role, "content": h.content})
        msgs.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=900,
            system=system_prompt,
            messages=msgs,  # type: ignore
        )
        return response.content[0].text  # type: ignore
    except Exception:
        pass

    # Deterministic mock fallback
    return (
        f"Great question! Based on your knowledge base and memory state, here's what I know:\n\n"
        f"The topic you're asking about connects several important concepts you've been studying. "
        f"I can see that your retention is currently solid in some areas, but there are concepts "
        f"worth reinforcing.\n\n"
        f"> **You might be forgetting:** Check your Dashboard for concepts due for review today.\n\n"
        f"Would you like me to quiz you, or dive deeper into a specific concept?"
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Memory-aware tutor chat endpoint.
    """
    # 1. Fetch memory state
    try:
        memory_ctx = _get_memory_context()
    except Exception:
        memory_ctx = {"weak_concepts": [], "due_reviews": [], "avg_retention": 0.0}

    # 2. Hybrid retrieval for relevant chunks
    retrieved: list[dict] = []
    boosted_concepts: list[str] = []
    try:
        from retrieval.hybrid_retriever import HybridRetriever

        with HybridRetriever() as retriever:
            chunks = retriever.retrieve(req.message)
            retrieved = [
                {
                    "text": c.text,
                    "concept_tag": c.concept_tag,
                    "source_file": c.source_file,
                    "final_score": c.final_score,
                }
                for c in chunks
            ]
            # Identify boosted concepts (high urgency score)
            boosted_concepts = [
                c.concept_tag
                for c in chunks
                if c.urgency_score > 0.4 and c.concept_tag
            ]
    except Exception:
        pass

    # 3. Build system prompt
    system_prompt = _build_system_prompt(memory_ctx, retrieved)

    # 4. Call LLM
    reply = _call_llm(system_prompt, req.history, req.message)

    return ChatResponse(
        reply=reply,
        memory_context=memory_ctx,
        boosted_concepts=list(set(boosted_concepts))[:3],
    )
