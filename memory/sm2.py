"""
SM-2 spaced repetition algorithm — pure function implementation.

Reference: https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MINIMUM_EASE = 1.3
DEFAULT_EASE = 2.5


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SM2Result:
    easiness_factor: float
    interval_days: int
    repetitions: int
    next_review: datetime


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def sm2(
    rating: int,
    easiness_factor: float = DEFAULT_EASE,
    interval_days: int = 1,
    repetitions: int = 0,
    now: Optional[datetime] = None,
) -> SM2Result:
    """
    Compute the next review schedule using the SM-2 algorithm.

    Parameters
    ----------
    rating          : int   — User self-rating 0-5 (SM-2 scale)
                              0/1 = complete blackout
                              2   = incorrect, but remembered on seeing answer
                              3   = correct with serious difficulty
                              4   = correct after a hesitation
                              5   = perfect response
    easiness_factor : float — Current ease factor (default 2.5)
    interval_days   : int   — Current review interval in days
    repetitions     : int   — Number of successful repetitions so far
    now             : datetime — Reference "today" (UTC); defaults to utcnow

    Returns
    -------
    SM2Result with updated ease, interval, repetitions, and next_review date.
    """
    if not (0 <= rating <= 5):
        raise ValueError(f"rating must be 0-5, got {rating}")

    if now is None:
        now = datetime.now(tz=timezone.utc)

    # ── Update ease factor ────────────────────────────────────────────────
    # Δease = 0.1 − (5−rating)·(0.08 + (5−rating)·0.02)
    delta_ease = 0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02)
    new_ease = max(MINIMUM_EASE, easiness_factor + delta_ease)

    # ── Compute new interval ──────────────────────────────────────────────
    if rating < 3:
        # Failed recall — reset but keep ease update
        new_reps = 0
        new_interval = 1
    else:
        new_reps = repetitions + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = min(36500, max(1, round(interval_days * new_ease)))

    next_review = now + timedelta(days=new_interval)

    return SM2Result(
        easiness_factor=round(new_ease, 4),
        interval_days=new_interval,
        repetitions=new_reps,
        next_review=next_review,
    )


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------


def batch_sm2(
    records: list[dict],
    rating: int,
    now: Optional[datetime] = None,
) -> list[SM2Result]:
    """
    Apply SM-2 to a list of concept memory dicts from SQLite.
    Each dict must have: easiness_factor, interval_days, repetitions.
    """
    return [
        sm2(
            rating=rating,
            easiness_factor=rec["easiness_factor"],
            interval_days=rec["interval_days"],
            repetitions=rec["repetitions"],
            now=now,
        )
        for rec in records
    ]
