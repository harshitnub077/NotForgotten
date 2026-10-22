"""
FSRS-6 — Free Spaced Repetition Scheduler (DSR memory model).

Each memory is described by three variables:

    D  difficulty      ∈ [1, 10]   how hard the item is for *this* learner
    S  stability       > 0 (days)  time for R to fall from 100% to 90%
    R  retrievability  ∈ [0, 1]    probability of recall right now

Forgetting curve (power law, trainable decay w20):

    R(t, S) = (1 + F · t / S) ^ (−w20),     F = 0.9 ^ (−1 / w20) − 1

so that R(S, S) = 0.9 by construction. A power law fits real review logs
better than Ebbinghaus' exponential because a population of memories with
heterogeneous decay rates averages to a power law.

Reference: open-spaced-repetition/awesome-fsrs wiki, "The Algorithm" (FSRS-6),
and py-fsrs. Default parameters are the FSRS-6 population defaults.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PARAMETERS: Tuple[float, ...] = (
    0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001,
    1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014,
    1.8729, 0.5425, 0.0912, 0.0658, 0.1542,
)

STABILITY_MIN = 0.001
DIFFICULTY_MIN = 1.0
DIFFICULTY_MAX = 10.0
DEFAULT_DESIRED_RETENTION = 0.9
MAX_INTERVAL_DAYS = 36_500
RELEARN_MINUTES = 10  # an "Again" brings the card back within the session


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


@dataclass(frozen=True)
class MemoryState:
    stability: float
    difficulty: float


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class FSRS:
    """Pure, side-effect-free FSRS-6 model. Thread-safe; cheap to construct."""

    def __init__(
        self,
        parameters: Optional[Sequence[float]] = None,
        desired_retention: float = DEFAULT_DESIRED_RETENTION,
        max_interval: int = MAX_INTERVAL_DAYS,
    ) -> None:
        w = tuple(parameters) if parameters is not None else DEFAULT_PARAMETERS
        if len(w) != 21:
            raise ValueError(f"FSRS-6 needs 21 parameters, got {len(w)}")
        if not 0.5 <= desired_retention < 1.0:
            raise ValueError("desired_retention must be in [0.5, 1.0)")
        self.w = w
        self.desired_retention = desired_retention
        self.max_interval = max_interval
        self.decay = -w[20]
        self.factor = 0.9 ** (1.0 / self.decay) - 1.0

    # ── Forgetting curve ────────────────────────────────────────────────

    def retrievability(self, elapsed_days: float, stability: float) -> float:
        if stability <= 0:
            return 0.0
        t = max(0.0, elapsed_days)
        return (1.0 + self.factor * t / stability) ** self.decay

    def interval_for(self, stability: float, retention: Optional[float] = None) -> float:
        """Unrounded days until R falls to *retention* (inverse of the curve)."""
        r = self.desired_retention if retention is None else retention
        return stability / self.factor * (r ** (1.0 / self.decay) - 1.0)

    def next_interval(self, stability: float, retention: Optional[float] = None) -> int:
        days = round(self.interval_for(stability, retention))
        return int(min(max(days, 1), self.max_interval))

    def half_life(self, stability: float) -> float:
        """Days until R drops to 50% — an intuitive 'memory half-life'."""
        return self.interval_for(stability, 0.5)

    def retention_area(self, stability: float, t0: float, t1: float) -> float:
        """
        ∫_{t0}^{t1} R(t, S) dt  in closed form ("retention-days").

        With u = 1 + F·t/S and exponent −d:
            ∫ u^(−d) dt = S / (F·(1−d)) · u^(1−d)
        """
        if stability <= 0 or t1 <= t0:
            return 0.0
        d = -self.decay
        f, s = self.factor, stability
        u0 = 1.0 + f * max(t0, 0.0) / s
        u1 = 1.0 + f * t1 / s
        if abs(1.0 - d) < 1e-9:
            return s / f * (math.log(u1) - math.log(u0))
        return s / (f * (1.0 - d)) * (u1 ** (1.0 - d) - u0 ** (1.0 - d))

    # ── Initial state ───────────────────────────────────────────────────

    def init_stability(self, rating: int) -> float:
        return max(self.w[rating - 1], STABILITY_MIN)

    def init_difficulty(self, rating: int, clamp: bool = True) -> float:
        d = self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1.0
        return _clamp(d, DIFFICULTY_MIN, DIFFICULTY_MAX) if clamp else d

    # ── Transitions ─────────────────────────────────────────────────────

    def next_difficulty(self, difficulty: float, rating: int) -> float:
        delta = -self.w[6] * (rating - 3)
        damped = difficulty + (10.0 - difficulty) * delta / 9.0  # linear damping
        target = self.init_difficulty(Rating.EASY, clamp=False)
        reverted = self.w[7] * target + (1.0 - self.w[7]) * damped  # mean reversion
        return _clamp(reverted, DIFFICULTY_MIN, DIFFICULTY_MAX)

    def next_recall_stability(self, d: float, s: float, r: float, rating: int) -> float:
        hard_penalty = self.w[15] if rating == Rating.HARD else 1.0
        easy_bonus = self.w[16] if rating == Rating.EASY else 1.0
        growth = (
            math.exp(self.w[8])
            * (11.0 - d)
            * s ** (-self.w[9])
            * (math.exp((1.0 - r) * self.w[10]) - 1.0)
            * hard_penalty
            * easy_bonus
        )
        return max(s * (1.0 + growth), STABILITY_MIN)

    def next_forget_stability(self, d: float, s: float, r: float) -> float:
        long_term = (
            self.w[11]
            * d ** (-self.w[12])
            * ((s + 1.0) ** self.w[13] - 1.0)
            * math.exp((1.0 - r) * self.w[14])
        )
        short_term = s / math.exp(self.w[17] * self.w[18])
        return max(min(long_term, short_term), STABILITY_MIN)

    def short_term_stability(self, s: float, rating: int) -> float:
        inc = math.exp(self.w[17] * (rating - 3 + self.w[18])) * s ** (-self.w[19])
        if rating >= Rating.HARD:
            inc = max(inc, 1.0)
        return max(s * inc, STABILITY_MIN)

    def next_state(
        self,
        state: Optional[MemoryState],
        elapsed_days: float,
        rating: int,
    ) -> MemoryState:
        """Memory state after answering with *rating* after *elapsed_days*."""
        if rating not in (1, 2, 3, 4):
            raise ValueError(f"rating must be 1-4, got {rating}")

        if state is None:
            return MemoryState(self.init_stability(rating), self.init_difficulty(rating))

        s, d = state.stability, state.difficulty
        if elapsed_days < 1.0:
            new_s = self.short_term_stability(s, rating)
        else:
            r = self.retrievability(elapsed_days, s)
            if rating == Rating.AGAIN:
                new_s = self.next_forget_stability(d, s, r)
            else:
                new_s = self.next_recall_stability(d, s, r, rating)
        return MemoryState(new_s, self.next_difficulty(d, rating))

    def schedule_days(self, new_state: MemoryState, rating: int) -> float:
        """Days until the next review (fractional for in-session relearning)."""
        if rating == Rating.AGAIN:
            return RELEARN_MINUTES / 1440.0
        return float(self.next_interval(new_state.stability))

    def preview(
        self, state: Optional[MemoryState], elapsed_days: float
    ) -> Dict[int, Tuple[MemoryState, float]]:
        """Outcome of every rating, used for the 'next review in…' buttons."""
        out: Dict[int, Tuple[MemoryState, float]] = {}
        for rating in Rating:
            ns = self.next_state(state, elapsed_days, rating)
            out[int(rating)] = (ns, self.schedule_days(ns, rating))
        return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)
