"""
LangGraph node functions.

State shape (TypedDict):
    session_id      : str
    query           : str
    chunks          : list[RetrievedChunk]
    context         : str          — formatted context string for LLM
    answer          : str
    rating          : int | None   — user self-rating 1-5
    concept_ids     : list[str]    — concept_tags seen this turn
    sm2_results     : list[dict]   — updated memory records
    next_review_info: dict[str, str]
    reteach_count   : int          — how many re-teach loops have run
    messages        : list[dict]   — raw LLM message history
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from agent.prompts import (
    ASSESS_PROMPT,
    GENERATE_PROMPT,
    RETEACH_PROMPT,
    SCHEDULE_PROMPT,
    SYSTEM_PROMPT,
)
from memory.schema import get_conn, init_db
from memory.sm2 import sm2
from retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk

load_dotenv(override=True)

def _get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0.3)
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=0.3)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0.3)


# ---------------------------------------------------------------------------
# Helper — format retrieved chunks into a context block
# ---------------------------------------------------------------------------


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[{i}] (source: {c.source_file} p.{c.page_num + 1} | "
            f"concept: {c.concept_tag} | urgency: {c.urgency_score:.2f})\n"
            f"{c.text}"
        )
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def retrieve_node(state: dict) -> dict:
    """
    Embed the query, run HybridRetriever, store chunks + context in state.
    Also ensures all retrieved concept_tags exist in concept_memory.
    """
    init_db()
    query = state.get("query", "")
    retriever = HybridRetriever()

    chunks = retriever.retrieve(query)

    # Ensure concept memory rows exist for every seen concept
    for chunk in chunks:
        retriever.ensure_concept_exists(chunk.concept_tag)

    context = _format_context(chunks)
    concept_ids = list({c.concept_tag for c in chunks})

    return {
        **state,
        "chunks": [c.__dict__ for c in chunks],
        "context": context,
        "concept_ids": concept_ids,
    }


def generate_node(state: dict) -> dict:
    """
    Call the LLM with system prompt + retrieved context + user query.
    Appends to message history.
    """
    llm = _get_llm()
    context = state.get("context", "")
    query = state.get("query", "")
    reteach_count = state.get("reteach_count") or 0

    if reteach_count > 0:
        user_content = RETEACH_PROMPT.format(context=context)
    else:
        user_content = GENERATE_PROMPT.format(context=context, query=query)

    from langchain_core.messages import HumanMessage, SystemMessage
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    answer = response.content

    history = state.get("messages", [])
    history.append({"role": "assistant", "content": answer})

    return {
        **state,
        "answer": answer,
        "messages": history,
    }


def assess_node(state: dict) -> dict:
    """
    In API mode, the rating is optional in the initial query.
    If missing, we skip interactive prompting to avoid blocking the server.
    """
    rating = state.get("rating")
    return {**state, "rating": rating}


def update_memory_node(state: dict) -> dict:
    """
    Run SM-2 on every concept seen this turn and persist results to SQLite.
    Also writes to session_log.
    """
    rating = state.get("rating")
    if rating is None:
        rating = 3
    else:
        rating = int(rating)
    concept_ids: list[str] = state.get("concept_ids", [])
    session_id = state.get("session_id") or str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    now_str = now.isoformat()

    sm2_results: list[dict] = []

    with get_conn() as conn:
        for concept_id in concept_ids:
            row = conn.execute(
                "SELECT * FROM concept_memory WHERE concept_id = ?",
                (concept_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT OR IGNORE INTO concept_memory (concept_id) VALUES (?)",
                    (concept_id,),
                )
                row = conn.execute(
                    "SELECT * FROM concept_memory WHERE concept_id = ?",
                    (concept_id,),
                ).fetchone()

            result = sm2(
                rating=rating,
                easiness_factor=row["easiness_factor"],
                interval_days=row["interval_days"],
                repetitions=row["repetitions"],
                now=now,
            )

            next_review_str = result.next_review.isoformat()

            conn.execute(
                """
                UPDATE concept_memory
                SET easiness_factor = ?,
                    interval_days   = ?,
                    repetitions     = ?,
                    last_review     = ?,
                    next_review     = ?
                WHERE concept_id = ?
                """,
                (
                    result.easiness_factor,
                    result.interval_days,
                    result.repetitions,
                    now_str,
                    next_review_str,
                    concept_id,
                ),
            )

            conn.execute(
                """
                INSERT INTO session_log (session_id, concept_id, user_rating, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, concept_id, rating, now_str),
            )

            sm2_results.append(
                {
                    "concept_id": concept_id,
                    "easiness_factor": result.easiness_factor,
                    "interval_days": result.interval_days,
                    "repetitions": result.repetitions,
                    "next_review": next_review_str,
                }
            )

    return {**state, "sm2_results": sm2_results, "session_id": session_id}


def schedule_node(state: dict) -> dict:
    """
    Summarise the updated review schedule and attach it to state.
    """
    sm2_results: list[dict] = state.get("sm2_results", [])

    lines: list[str] = []
    for r in sm2_results:
        lines.append(
            f"  • {r['concept_id']} → next review in {r['interval_days']} day(s) "
            f"(ease: {r['easiness_factor']:.2f})"
        )

    schedule_summary = "\n".join(lines) if lines else "No concepts updated."
    schedule_message = SCHEDULE_PROMPT.format(schedule_summary=schedule_summary)

    next_review_info = {r["concept_id"]: r["next_review"] for r in sm2_results}

    return {
        **state,
        "next_review_info": next_review_info,
        "schedule_message": schedule_message,
    }
