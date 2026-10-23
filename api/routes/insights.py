"""Learning analytics and personal memory-model optimisation."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from core import analytics, settings
from core.auth import uid
from core.util import iso, parse_dt, utcnow
from memory.optimizer import fit
from memory.schema import get_conn

router = APIRouter(tags=["insights"])


@router.get("/insights")
def insights(tz_offset: int = 0) -> dict:
    return analytics.insights(tz_offset)


@router.post("/insights/optimize")
def optimize() -> dict:
    """Fit FSRS parameters to this learner's own review history."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT card_id, rating, reviewed_at FROM reviews WHERE user_id = ? ORDER BY card_id, reviewed_at",
            (uid(),),
        ).fetchall()
    logs = defaultdict(list)
    for r in rows:
        logs[r["card_id"]].append((parse_dt(r["reviewed_at"]), int(r["rating"])))
    current = settings.get_fsrs()
    result = fit(list(logs.values()), initial=list(current.w))
    summary = {
        "improved": result.improved,
        "n_predictions": result.n_predictions,
        "loss_before": result.loss_before,
        "loss_after": result.loss_after,
        "rmse_before": result.rmse_bins_before,
        "rmse_after": result.rmse_bins_after,
        "fitted_at": iso(utcnow()),
    }
    if result.improved:
        settings.update(
            {
                "fsrs_parameters": result.parameters,
                "parameters_personalized": True,
                "last_fit": summary,
            }
        )
    else:
        settings.update({"last_fit": summary})
    return {**summary, "parameters": result.parameters}
