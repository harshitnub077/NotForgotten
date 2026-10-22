"""
Demo library: three sample texts plus a simulated two-month study history.

The simulated learner forgets a little faster than the FSRS population
default and is mildly overconfident, so every analytic (calibration,
personal-curve fitting, at-risk concepts) has something real to show.
All demo documents are flagged is_demo and can be removed in one call.
"""
from __future__ import annotations

import random
import threading
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

from core import settings
from core.memory import submit_review
from core.util import iso, new_id, parse_dt, utcnow
from ingestion import pipeline
from memory.fsrs import DEFAULT_PARAMETERS, FSRS
from memory.schema import get_conn, init_db

DEMO_DIR = Path(__file__).resolve().parent.parent / "assets" / "demo"
HISTORY_DAYS = 60
_lock = threading.Lock()


def _learner() -> FSRS:
    w = list(DEFAULT_PARAMETERS)
    w[2] = 1.4   # first-day memories a bit weaker than average
    w[8] = 1.65  # slightly slower stability growth
    return FSRS(w)


def load_demo() -> Dict[str, str]:
    if not _lock.acquire(blocking=False):
        raise RuntimeError("The demo library is already being prepared.")
    init_db()
    with get_conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM documents WHERE is_demo = 1").fetchone()[0]:
            _lock.release()
            raise RuntimeError("Demo library is already loaded.")
        job_id = new_id("job")
        now = iso(utcnow())
        conn.execute(
            "INSERT INTO jobs (id, document_id, status, stage, progress, message, created_at, updated_at) "
            "VALUES (?, NULL, 'running', 'queued', 0, 'Preparing the demo library…', ?, ?)",
            (job_id, now, now),
        )
    threading.Thread(target=_build, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}


def _build(job_id: str) -> None:
    try:
        files = sorted(DEMO_DIR.glob("*.md"))
        doc_ids: List[str] = []
        for i, path in enumerate(files):
            pipeline._job_update(job_id, "ingesting", 0.05 + 0.75 * i / len(files), f"Reading “{path.stem.replace('-', ' ')}”…")
            res = pipeline.submit(
                {"kind": "markdown", "text": path.read_text(), "title": path.stem.replace("-", " ").title()},
                sync=True,
                is_demo=True,
            )
            doc_ids.append(res["document_id"])
        pipeline._job_update(job_id, "simulating", 0.85, "Simulating two months of study history…")
        n = simulate_history(doc_ids)
        pipeline._job_update(job_id, "done", 1.0, f"Demo ready — {n} simulated reviews.", status="done")
    except Exception as exc:  # noqa: BLE001
        pipeline._job_update(job_id, "failed", 1.0, str(exc)[:300], status="failed")
    finally:
        _lock.release()


def simulate_history(doc_ids: List[str], seed: int = 42) -> int:
    rng = random.Random(seed)
    truth = _learner()
    app_fsrs = settings.get_fsrs()
    now = utcnow()
    marks = ",".join("?" * len(doc_ids))
    with get_conn() as conn:
        cards = conn.execute(
            f"SELECT id, document_id FROM cards WHERE document_id IN ({marks}) ORDER BY created_at",
            doc_ids,
        ).fetchall()

    # Documents were "started" at different times; a few cards stay new.
    doc_start = {d: HISTORY_DAYS - i * 14 for i, d in enumerate(doc_ids)}
    skipped_days = {d for d in range(HISTORY_DAYS) if rng.random() < 0.18}
    total = 0
    session = new_id("ses")
    for card in cards:
        if rng.random() < 0.15:
            continue
        start = doc_start.get(card["document_id"], 30) - rng.uniform(0, 6)
        t = now - timedelta(days=max(start, 1.0))
        state, last = None, None
        while t < now - timedelta(hours=2):
            day_idx = (now - t).days
            if day_idx in skipped_days:
                t += timedelta(days=1)
                continue
            elapsed = 0.0 if last is None else (t - last).total_seconds() / 86_400.0
            if state is None:
                rating = rng.choice([3, 3, 3, 2, 4])
                p = 0.6
            else:
                p = truth.retrievability(elapsed, state.stability)
                if rng.random() < p:
                    rating = 4 if p > 0.93 and rng.random() < 0.35 else (2 if p < 0.75 and rng.random() < 0.5 else 3)
                else:
                    rating = 1
            confidence = min(1.0, max(0.05, p + 0.1 + rng.gauss(0, 0.15)))
            state = truth.next_state(state, elapsed, rating)
            res = submit_review(
                card["id"],
                rating,
                confidence=round(confidence, 2),
                score=None,
                duration_ms=int(rng.uniform(7, 38) * 1000),
                session_id=session,
                now=t,
                fsrs=app_fsrs,
            )
            total += 1
            last = t
            due = parse_dt(res["due"])
            assert due is not None
            # Real learners are late more often than early.
            jitter = rng.choice([0, 0, 0, 1, 2, -0.3]) if res["interval_days"] >= 1 else 0
            t = due + timedelta(days=jitter, hours=rng.uniform(-3, 3))
    return total


def clear_demo() -> int:
    init_db()
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM documents WHERE is_demo = 1")]
    for doc_id in ids:
        pipeline.delete_document(doc_id)
    return len(ids)
