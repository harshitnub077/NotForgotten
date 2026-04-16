"""
30-day synthetic study session simulation harness.

Verifies three properties:
  (a) Concepts with low ratings get shorter intervals
  (b) High-rated concepts get longer intervals
  (c) HybridRetriever ranks forgotten concepts differently than pure semantic search

Run:
    python tests/simulation_harness.py
"""
from __future__ import annotations

import os
import random
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Ensure project root is on sys.path ──────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from memory.sm2 import sm2, DEFAULT_EASE
from memory.forgetting_scorer import ForgettingScorer, urgency_score
from retrieval.hybrid_retriever import HybridRetriever, _RawChunk

# ---------------------------------------------------------------------------
# ANSI colours for terminal output
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")
    sys.exit(1)


def _header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")


# ---------------------------------------------------------------------------
# (a) + (b)  SM-2 interval convergence over 30 days
# ---------------------------------------------------------------------------


def simulate_study_sessions(
    days: int = 30,
    rating_fn=None,
    seed: int = 42,
) -> dict:
    """
    Simulate *days* consecutive review sessions.
    rating_fn(day) → int rating (1-5)
    Returns final memory state dict.
    """
    rng = random.Random(seed)
    if rating_fn is None:
        rating_fn = lambda d: rng.randint(1, 5)

    ease = DEFAULT_EASE
    interval = 1
    reps = 0
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    history = []
    for day in range(days):
        now = base + timedelta(days=day)
        rating = rating_fn(day)
        result = sm2(rating=rating, easiness_factor=ease, interval_days=interval, repetitions=reps, now=now)
        ease, interval, reps = result.easiness_factor, result.interval_days, result.repetitions
        history.append(
            {
                "day": day,
                "rating": rating,
                "interval": interval,
                "ease": ease,
                "reps": reps,
            }
        )

    return {
        "final_interval": interval,
        "final_ease": ease,
        "final_reps": reps,
        "history": history,
    }


def test_low_ratings_produce_short_intervals():
    _header("(a)  Low ratings → short intervals")

    # Always fail (rating=1)
    always_fail = simulate_study_sessions(days=30, rating_fn=lambda d: 1)
    print(f"  Always-fail  → final interval: {always_fail['final_interval']} days, reps: {always_fail['final_reps']}")
    assert always_fail["final_interval"] == 1, "Expected interval=1 on consistent failures"
    _ok("Consistent failures keep interval at 1 day")

    # Mostly fail (rating=2)
    mostly_fail = simulate_study_sessions(days=30, rating_fn=lambda d: 2)
    print(f"  Mostly-fail  → final interval: {mostly_fail['final_interval']} days")
    assert mostly_fail["final_interval"] <= 3, f"Expected short interval, got {mostly_fail['final_interval']}"
    _ok("Mostly-fail keeps interval short (≤ 3 days)")


def test_high_ratings_produce_long_intervals():
    _header("(b)  High ratings → long intervals")

    # Always perfect (rating=5)
    always_pass = simulate_study_sessions(days=10, rating_fn=lambda d: 5)
    print(f"  Always-pass  → final interval: {always_pass['final_interval']} days, ease: {always_pass['final_ease']:.2f}")
    assert always_pass["final_interval"] > 15, f"Expected interval > 15 days, got {always_pass['final_interval']}"
    _ok(f"Consistent 5-ratings yield interval > 15 days ({always_pass['final_interval']} days)")

    # Moderate success (rating=4)
    moderate = simulate_study_sessions(days=10, rating_fn=lambda d: 4)
    print(f"  Moderate     → final interval: {moderate['final_interval']} days")
    assert moderate["final_interval"] > 5
    _ok(f"Moderate ratings (4) yield interval > 5 days ({moderate['final_interval']} days)")

    # Verify ordering: 5-rated > 4-rated > 3-rated
    r3 = simulate_study_sessions(days=10, rating_fn=lambda d: 3)["final_interval"]
    r4 = simulate_study_sessions(days=10, rating_fn=lambda d: 4)["final_interval"]
    r5 = simulate_study_sessions(days=10, rating_fn=lambda d: 5)["final_interval"]
    assert r5 > r4 > r3, f"Ordering broken: r5={r5}, r4={r4}, r3={r3}"
    _ok(f"Interval ordering correct: rating-5 ({r5}d) > rating-4 ({r4}d) > rating-3 ({r3}d)")


# ---------------------------------------------------------------------------
# (c)  HybridRetriever vs pure semantic — forgotten chunks get boosted
# ---------------------------------------------------------------------------


def test_hybrid_vs_semantic_ranking():
    _header("(c)  Hybrid retriever boosts forgotten concepts")

    # Three mock chunks
    # chunk_A: moderate semantic, HIGH urgency (forgotten)
    # chunk_B: high semantic, LOW urgency (well remembered)
    # chunk_C: low semantic, zero urgency
    chunks = [
        _RawChunk("Deep content about backpropagation", "backprop",    "ml.pdf", 1, semantic_score=0.65, chroma_id="a"),
        _RawChunk("Intro to gradient descent",          "grad_descent", "ml.pdf", 2, semantic_score=0.90, chroma_id="b"),
        _RawChunk("Basic algebra refresher",            "algebra",      "ml.pdf", 3, semantic_score=0.30, chroma_id="c"),
    ]

    urgency_map = {
        "backprop":    0.95,   # mostly forgotten
        "grad_descent": 0.05,  # just reviewed
        "algebra":     0.10,
    }

    def _run(alpha: float) -> list[str]:
        retriever = HybridRetriever(alpha=alpha, top_k=3)
        with (
            patch.object(retriever, "_semantic_search", return_value=chunks),
            patch.object(retriever, "_get_client", return_value=MagicMock()),
            patch("retrieval.hybrid_retriever.ForgettingScorer") as MockScorer,
            patch("retrieval.hybrid_retriever.get_embedder") as MockEmb,
        ):
            MockScorer.return_value.score_all.return_value = urgency_map
            MockEmb.return_value.embed.return_value = [0.0] * 384
            results = retriever.retrieve("explain neural network training")
        return [r.concept_tag for r in results]

    # Pure semantic (alpha=1) → grad_descent (0.90) tops
    semantic_order = _run(alpha=1.0)
    print(f"  Pure semantic order:  {semantic_order}")
    assert semantic_order[0] == "grad_descent", f"Expected grad_descent first, got {semantic_order[0]}"
    _ok("Pure semantic: grad_descent (highest cosine) ranks #1")

    # Hybrid (alpha=0.6) → backprop should jump to #1
    # backprop:    0.6*0.65 + 0.4*0.95 = 0.39 + 0.38 = 0.77
    # grad_descent: 0.6*0.90 + 0.4*0.05 = 0.54 + 0.02 = 0.56
    hybrid_order = _run(alpha=0.6)
    print(f"  Hybrid order (α=0.6): {hybrid_order}")
    assert hybrid_order[0] == "backprop", f"Expected backprop first (forgotten), got {hybrid_order[0]}"
    _ok("Hybrid: backprop (forgotten, urgency=0.95) promoted to #1 despite lower semantic")

    assert semantic_order != hybrid_order
    _ok("Hybrid ranking differs from pure semantic — forgotten concepts boosted ✓")


# ---------------------------------------------------------------------------
# Forgetting curve decay validation
# ---------------------------------------------------------------------------


def test_forgetting_curve_decay():
    _header("Forgetting curve — retention decays over time")

    stability = 7.0  # 7-day stability

    prev_urgency = 0.0
    for t in [0, 1, 3, 7, 14, 21]:
        u = urgency_score(t_days=t, stability=stability)
        print(f"  t={t:>2}d  urgency={u:.4f}")
        assert u >= prev_urgency, f"Urgency should increase over time (t={t})"
        prev_urgency = u

    _ok("Urgency monotonically increases as time since review grows")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  NotForgotten — 30-Day Simulation Harness{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    test_low_ratings_produce_short_intervals()
    test_high_ratings_produce_long_intervals()
    test_hybrid_vs_semantic_ranking()
    test_forgetting_curve_decay()

    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}  ✓  All simulation checks passed!{RESET}")
    print(f"{BOLD}{GREEN}{'='*60}{RESET}\n")


if __name__ == "__main__":
    main()
