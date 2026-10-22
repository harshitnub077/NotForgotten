"""
Personal forgetting-curve fitting.

FSRS ships with population-average parameters. Once a learner has enough
history we fit the parameters that matter most for *them* by maximum
likelihood: replay every card's review log, predict R before each review,
and minimise binary cross-entropy against whether they actually recalled it.

    L(w) = − Σ_i [ y_i · log R_i(w) + (1 − y_i) · log(1 − R_i(w)) ]

Only reviews at least a day apart are prediction targets (same-day repeats
measure short-term memory, which FSRS models separately). Optimisation is
bounded L-BFGS-B over a subset of the 21 weights: initial stabilities
(w0–w3), recall-stability growth (w8–w10), lapse stability (w11) and the
curve's decay exponent (w20).

With a few hundred reviews an unconstrained fit overfits, so this is a MAP
estimate: a Gaussian prior centred on the population defaults, in relative
units, whose weight fades as evidence accumulates:

    J(w) = L(w) + (k / n) · Σ_i ((w_i − w0_i) / w0_i)²

A fit is only accepted if it lowers log-loss *and* doesn't worsen
calibration (binned RMSE) by more than 10%.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from memory.fsrs import DEFAULT_PARAMETERS, FSRS, MemoryState

FREE_PARAMS: Tuple[int, ...] = (0, 1, 2, 3, 8, 9, 10, 11, 20)
BOUNDS: Dict[int, Tuple[float, float]] = {
    0: (0.001, 100.0),
    1: (0.001, 100.0),
    2: (0.001, 100.0),
    3: (0.001, 100.0),
    8: (0.0, 4.5),
    9: (0.0, 0.8),
    10: (0.001, 3.5),
    11: (0.001, 5.0),
    20: (0.1, 0.6),
}
MIN_REVIEWS = 30
PRIOR_STRENGTH = 6.0  # pseudo-observations pulling each weight toward the population default
_EPS = 1e-6

ReviewLog = Sequence[Tuple[datetime, int]]  # (timestamp, rating 1-4) per card


@dataclass
class FitResult:
    parameters: List[float]
    loss_before: float
    loss_after: float
    n_predictions: int
    rmse_bins_before: float
    rmse_bins_after: float
    improved: bool


def _predictions(fsrs: FSRS, logs: Sequence[ReviewLog]) -> List[Tuple[float, int]]:
    preds: List[Tuple[float, int]] = []
    for log in logs:
        state: Optional[MemoryState] = None
        last: Optional[datetime] = None
        for ts, rating in log:
            elapsed = 0.0 if last is None else (ts - last).total_seconds() / 86_400.0
            if state is not None and elapsed >= 1.0:
                preds.append((fsrs.retrievability(elapsed, state.stability), int(rating > 1)))
            state = fsrs.next_state(state, elapsed, rating)
            last = ts
    return preds


def log_loss(preds: Sequence[Tuple[float, int]]) -> float:
    if not preds:
        return float("nan")
    total = 0.0
    for p, y in preds:
        p = min(max(p, _EPS), 1 - _EPS)
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(preds)


def rmse_bins(preds: Sequence[Tuple[float, int]], n_bins: int = 10) -> float:
    """RMSE between predicted R and observed recall rate, binned by R."""
    if not preds:
        return float("nan")
    buckets: Dict[int, List[Tuple[float, int]]] = {}
    for p, y in preds:
        buckets.setdefault(min(int(p * n_bins), n_bins - 1), []).append((p, y))
    sq, n = 0.0, len(preds)
    for members in buckets.values():
        k = len(members)
        mp = sum(p for p, _ in members) / k
        my = sum(y for _, y in members) / k
        sq += k * (mp - my) ** 2
    return math.sqrt(sq / n)


def evaluate(parameters: Sequence[float], logs: Sequence[ReviewLog]) -> Tuple[float, float, int]:
    preds = _predictions(FSRS(parameters), logs)
    return log_loss(preds), rmse_bins(preds), len(preds)


def fit(
    logs: Sequence[ReviewLog],
    initial: Optional[Sequence[float]] = None,
    max_iter: int = 60,
) -> FitResult:
    """Fit personal parameters. Falls back to *initial* when data is thin."""
    from scipy.optimize import minimize  # local import: optional heavy dep

    base = list(initial if initial is not None else DEFAULT_PARAMETERS)
    loss0, rmse0, n = evaluate(base, logs)
    if n < MIN_REVIEWS or math.isnan(loss0):
        return FitResult(base, loss0, loss0, n, rmse0, rmse0, False)

    x0 = [base[i] for i in FREE_PARAMS]
    bounds = [BOUNDS[i] for i in FREE_PARAMS]

    prior = list(DEFAULT_PARAMETERS)

    def objective(x: Sequence[float]) -> float:
        w = list(base)
        for idx, val in zip(FREE_PARAMS, x):
            w[idx] = float(val)
        # Initial stabilities must stay ordered Again ≤ Hard ≤ Good ≤ Easy.
        for i in (1, 2, 3):
            w[i] = max(w[i], w[i - 1])
        loss, _, _ = evaluate(w, logs)
        penalty = sum(((w[i] - prior[i]) / max(abs(prior[i]), 0.05)) ** 2 for i in FREE_PARAMS)
        return loss + PRIOR_STRENGTH / n * penalty

    res = minimize(objective, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": max_iter})
    fitted = list(base)
    for idx, val in zip(FREE_PARAMS, res.x):
        fitted[idx] = round(float(val), 4)
    for i in (1, 2, 3):
        fitted[i] = max(fitted[i], fitted[i - 1])

    loss1, rmse1, _ = evaluate(fitted, logs)
    improved = loss1 < loss0 - 1e-3 and rmse1 <= rmse0 * 1.1 + 1e-3
    return FitResult(
        parameters=fitted if improved else base,
        loss_before=round(loss0, 5),
        loss_after=round(loss1 if improved else loss0, 5),
        n_predictions=n,
        rmse_bins_before=round(rmse0, 5),
        rmse_bins_after=round(rmse1 if improved else rmse0, 5),
        improved=improved,
    )
