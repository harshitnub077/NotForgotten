"""
LangGraph agent graph.

Flow:
    retrieve → generate → assess → update_memory → schedule
                              ↓ (rating ≤ 2, reteach_count < MAX_RETEACH)
                           retrieve  (re-teach loop)

The conditional edge from assess_node checks the rating. If ≤ 2 and the
user hasn't been re-taught too many times, we loop back to retrieve_node
so fresh context can be fetched and explained differently.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    assess_node,
    generate_node,
    retrieve_node,
    schedule_node,
    update_memory_node,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETEACH = 2  # maximum re-teach loops before forcing exit

# ---------------------------------------------------------------------------
# State type
# ---------------------------------------------------------------------------

from typing import TypedDict, Any, Optional


class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    chunks: list[dict]
    context: str
    answer: str
    rating: Optional[int]
    concept_ids: list[str]
    sm2_results: list[dict]
    next_review_info: dict[str, str]
    schedule_message: str
    reteach_count: int
    messages: list[dict]


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


def _should_reteach(state: AgentState) -> Literal["retrieve", "update_memory"]:
    """
    After assess_node:
    - rating ≤ 2  AND  reteach_count < MAX_RETEACH  → re-teach (loop to retrieve)
    - otherwise → continue to update_memory
    """
    # Use 'or' to handle None values correctly
    rating = state.get("rating")
    if rating is None:
        rating = 3
    
    reteach_count = state.get("reteach_count") or 0

    if rating <= 2 and reteach_count < MAX_RETEACH:
        return "retrieve"
    return "update_memory"


# ---------------------------------------------------------------------------
# Wrap retrieve_node to increment reteach counter
# ---------------------------------------------------------------------------


def _retrieve_with_counter(state: AgentState) -> AgentState:
    count = state.get("reteach_count", 0)
    new_state = retrieve_node(state)
    new_state["reteach_count"] = count + 1 if count > 0 else 0
    return new_state  # type: ignore[return-value]


def _retrieve_reteach(state: AgentState) -> AgentState:
    """Same as retrieve but bumps reteach_count."""
    count = state.get("reteach_count", 0)
    new_state = retrieve_node(state)
    new_state["reteach_count"] = count + 1
    return new_state  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_node("assess", assess_node)
    builder.add_node("update_memory", update_memory_node)
    builder.add_node("schedule", schedule_node)
    builder.add_node("reteach_retrieve", _retrieve_reteach)

    # Linear edges
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "assess")

    # Conditional edge: re-teach loop or continue
    builder.add_conditional_edges(
        "assess",
        _should_reteach,
        {
            "retrieve": "reteach_retrieve",
            "update_memory": "update_memory",
        },
    )

    # Re-teach loops back into generate (fresh context already in state)
    builder.add_edge("reteach_retrieve", "generate")

    # Final linear path
    builder.add_edge("update_memory", "schedule")
    builder.add_edge("schedule", END)

    return builder


def compile_graph():
    """Compile and return the runnable LangGraph app."""
    return build_graph().compile()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph
