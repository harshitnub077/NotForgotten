"""
Metacognition metrics — does the learner know what they know?

Before revealing an answer the learner states a confidence c ∈ [0, 1]; the
outcome o ∈ {0, 1} is whether they actually recalled it. We report:

    Brier score          mean (c − o)²                 lower is better
    ECE                  Σ_b (n_b / N) · |conf_b − acc_b|   expected calibration error
    Overconfidence       mean(c) − mean(o)             > 0 ⇒ illusion of competence
    Resolution           how well confidence separates right from wrong

Overconfidence is the classic "illusion of fluency" from re-reading: it is
the single most useful number to show a student, because it tells them
when to stop trusting the feeling of familiarity.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

BIN_EDGES: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001)


def calibration_report(pairs: Sequence[Tuple[float, int]]) -> Dict[str, object]:
    """*pairs* = [(confidence ∈ [0,1], outcome ∈ {0,1}), …]."""
    n = len(pairs)
    if n == 0:
        return {
            "n": 0,
            "brier": None,
            "ece": None,
            "overconfidence": None,
            "resolution": None,
            "bins": [],
        }

    mean_c = sum(c for c, _ in pairs) / n
    base_rate = sum(o for _, o in pairs) / n
    brier = sum((c - o) ** 2 for c, o in pairs) / n

    bins: List[Dict[str, float]] = []
    ece = 0.0
    resolution = 0.0
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        members = [(c, o) for c, o in pairs if lo <= c < hi]
        if not members:
            continue
        k = len(members)
        conf = sum(c for c, _ in members) / k
        acc = sum(o for _, o in members) / k
        ece += k / n * abs(conf - acc)
        resolution += k / n * (acc - base_rate) ** 2
        bins.append(
            {
                "lo": lo,
                "hi": min(hi, 1.0),
                "confidence": round(conf, 4),
                "accuracy": round(acc, 4),
                "count": k,
            }
        )

    return {
        "n": n,
        "brier": round(brier, 4),
        "ece": round(ece, 4),
        "overconfidence": round(mean_c - base_rate, 4),
        "resolution": round(resolution, 4),
        "mean_confidence": round(mean_c, 4),
        "accuracy": round(base_rate, 4),
        "bins": bins,
    }
