"""
Ebbinghaus forgetting curve scorer.

Retention:  R = e^(−t / S)
Urgency:    urgency = 1 − R   (∈ [0, 1], higher = more forgotten)

Stability S is approximated as:
    S = interval_days * easiness_factor
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from memory.schema import get_conn

# ---------------------------------------------------------------------------
# Retention math
# ---------------------------------------------------------------------------


def retention(t_days: float, stability: float) -> float:
    """
    Compute Ebbinghaus retention probability.

    Parameters
    ----------
    t_days    : float — Days elapsed since last review
    stability : float — Memory stability (interval * ease)

    Returns
    -------
    float in [0, 1] — probability of recall
    """
    if stability <= 0:
        return 0.0
    return math.exp(-t_days / stability)


def urgency_score(t_days: float, stability: float) -> float:
    """1 − retention; higher means more urgently needs review."""
    return 1.0 - retention(t_days, stability)


# ---------------------------------------------------------------------------
# ForgettingScorer
# ---------------------------------------------------------------------------


class ForgettingScorer:
    """
    Reads all concept_memory rows from SQLite and returns urgency scores.

    Usage::

        scorer = ForgettingScorer()
        scores = scorer.score_all()
        # scores = {"gradient_descent_p1-4": 0.87, "attention_p5-8": 0.12, ...}
    """

    def __init__(self, now: Optional[datetime] = None) -> None:
        self._now = now or datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def score_all(self) -> dict[str, float]:
        """
        Returns ``{concept_id: urgency_score}`` for every concept in memory.
        Concepts with no last_review get urgency = 1.0 (treat as fully forgotten).
        New concepts (never reviewed) also get urgency = 1.0.
        """
        rows = self._fetch_all()
        result: dict[str, float] = {}

        for row in rows:
            concept_id = row["concept_id"]
            last_review_str = row["last_review"]

            if not last_review_str:
                # Never reviewed → treat as fully forgotten
                result[concept_id] = 1.0
                continue

            last_review = datetime.fromisoformat(last_review_str)
            if last_review.tzinfo is None:
                last_review = last_review.replace(tzinfo=timezone.utc)

            t_days = (self._now - last_review).total_seconds() / 86_400.0
            stability = row["interval_days"] * row["easiness_factor"]
            result[concept_id] = round(urgency_score(t_days, stability), 6)

        return result

    def top_urgent(self, n: int = 10) -> list[tuple[str, float]]:
        """Return top-n concepts sorted by urgency descending."""
        scores = self.score_all()
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]

    def update_retention_probs(self) -> None:
        """Write current retention probabilities back to concept_memory."""
        rows = self._fetch_all()
        updates: list[tuple[float, str]] = []

        for row in rows:
            concept_id = row["concept_id"]
            last_review_str = row["last_review"]

            if not last_review_str:
                ret = 0.0
            else:
                last_review = datetime.fromisoformat(last_review_str)
                if last_review.tzinfo is None:
                    last_review = last_review.replace(tzinfo=timezone.utc)
                t_days = (self._now - last_review).total_seconds() / 86_400.0
                stability = row["interval_days"] * row["easiness_factor"]
                ret = round(retention(t_days, stability), 6)

            updates.append((ret, concept_id))

        with get_conn() as conn:
            conn.executemany(
                "UPDATE concept_memory SET retention_prob = ? WHERE concept_id = ?",
                updates,
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_all() -> list:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT concept_id, easiness_factor, interval_days,
                       repetitions, last_review, next_review, retention_prob
                FROM concept_memory
                """
            ).fetchall()
        return rows
