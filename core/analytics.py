"""Read models for the dashboard, insights, knowledge graph and concept pages."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import settings
from core.memory import card_view, concept_stats, fetch_cards, to_memory
from core.util import jloads, parse_dt, utcnow
from knowledge_graph.propagation import effective_retention, weakest_foundations
from memory.calibration import calibration_report
from memory.fsrs import FSRS
from memory.planner import build_queue, forecast
from memory.schema import get_conn, init_db


def _local_day(dt: datetime, tz_offset_min: int) -> str:
    return (dt + timedelta(minutes=tz_offset_min)).date().isoformat()


def _concepts() -> Dict[str, Dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.summary, c.keywords, c.document_id, c.position, d.title AS document_title
               FROM concepts c JOIN documents d ON d.id = c.document_id WHERE d.status = 'ready'"""
        ).fetchall()
    return {
        r["id"]: {
            "id": r["id"],
            "name": r["name"],
            "summary": r["summary"],
            "keywords": jloads(r["keywords"], []),
            "document_id": r["document_id"],
            "document_title": r["document_title"],
            "position": r["position"],
        }
        for r in rows
    }


def _edges() -> List[tuple]:
    with get_conn() as conn:
        return [
            (r["source"], r["target"], r["weight"], r["kind"])
            for r in conn.execute("SELECT source, target, weight, kind FROM concept_links").fetchall()
        ]


def streak_info(tz_offset_min: int = 0, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or utcnow()
    with get_conn() as conn:
        rows = conn.execute("SELECT reviewed_at FROM reviews").fetchall()
    days = {_local_day(parse_dt(r["reviewed_at"]), tz_offset_min) for r in rows}  # type: ignore[arg-type]
    today = _local_day(now, tz_offset_min)
    cursor = datetime.fromisoformat(today).date()
    if today not in days:
        cursor -= timedelta(days=1)  # streak survives until today ends
    current = 0
    while cursor.isoformat() in days:
        current += 1
        cursor -= timedelta(days=1)
    longest, run, prev = 0, 0, None
    for d in sorted(days):
        day = datetime.fromisoformat(d).date()
        run = run + 1 if prev is not None and (day - prev).days == 1 else 1
        longest = max(longest, run)
        prev = day
    return {"current": current, "longest": longest, "reviewed_today": today in days}


def _avg_seconds() -> Dict[str, float]:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT AVG(CASE WHEN stability_before IS NOT NULL THEN duration_ms END) AS rev,
                      AVG(CASE WHEN stability_before IS NULL THEN duration_ms END) AS new
               FROM (SELECT * FROM reviews WHERE duration_ms BETWEEN 1000 AND 300000
                     ORDER BY reviewed_at DESC LIMIT 500)"""
        ).fetchone()
    return {
        "review": (row["rev"] or 20_000) / 1000.0,
        "new": (row["new"] or 45_000) / 1000.0,
    }


# ---------------------------------------------------------------------------
# Today
# ---------------------------------------------------------------------------


def today(tz_offset_min: int = 0) -> Dict[str, Any]:
    fsrs = settings.get_fsrs()
    s = settings.get_all()
    now = utcnow()
    rows = fetch_cards()
    mems = [to_memory(r) for r in rows]
    secs = _avg_seconds()

    with get_conn() as conn:
        new_today = conn.execute(
            "SELECT COUNT(DISTINCT card_id) FROM reviews WHERE stability_before IS NULL AND reviewed_at >= ?",
            ((now - timedelta(hours=24)).isoformat(),),
        ).fetchone()[0]
        reviewed_today = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE reviewed_at >= ?",
            ((now - timedelta(hours=24)).isoformat(),),
        ).fetchone()[0]
        docs = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'ready'").fetchone()[0]

    new_left = max(0, int(s["daily_new_limit"]) - new_today)
    queue = build_queue(fsrs, mems, now, max_new=new_left, review_seconds=secs["review"], new_seconds=secs["new"])
    due = sum(1 for q in queue if not q.is_new)
    new = sum(1 for q in queue if q.is_new)
    learned = [m for m in mems if not m.is_new]
    rs = [fsrs.retrievability(m.elapsed_days(now), float(m.stability)) for m in learned]

    stats = concept_stats(fsrs, now, rows)
    concepts = _concepts()
    at_risk = []
    for cid, st in stats.items():
        if st["retention"] is None or cid not in concepts:
            continue
        at_risk.append({**concepts[cid], **st})
    at_risk.sort(key=lambda c: c["retention"])

    fc = forecast(fsrs, mems, days=7, now=now)
    next_due = min((m.due for m in learned if m.due and m.due > now), default=None)

    exams = upcoming_exams()
    return {
        "due": due,
        "new": new,
        "estimated_minutes": round((due * secs["review"] + new * secs["new"]) / 60.0, 1),
        "reviewed_today": reviewed_today,
        "goal_minutes": s["daily_goal_minutes"],
        "retention_now": round(sum(rs) / len(rs), 4) if rs else None,
        "desired_retention": fsrs.desired_retention,
        "cards_total": len(mems),
        "cards_learned": len(learned),
        "concepts_total": len(concepts),
        "documents_total": docs,
        "streak": streak_info(tz_offset_min, now),
        "at_risk": at_risk[:6],
        "forecast": fc,
        "next_due": next_due.isoformat() if next_due else None,
        "exams": exams[:3],
    }


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


def insights(tz_offset_min: int = 0) -> Dict[str, Any]:
    fsrs = settings.get_fsrs()
    s = settings.get_all()
    now = utcnow()
    rows = fetch_cards()
    mems = [to_memory(r) for r in rows]

    with get_conn() as conn:
        reviews = conn.execute(
            "SELECT rating, confidence, elapsed_days, retrievability, duration_ms, reviewed_at, stability_before, score "
            "FROM reviews ORDER BY reviewed_at"
        ).fetchall()

    per_day: Counter = Counter()
    minutes_per_day: Dict[str, float] = defaultdict(float)
    for r in reviews:
        day = _local_day(parse_dt(r["reviewed_at"]), tz_offset_min)  # type: ignore[arg-type]
        per_day[day] += 1
        minutes_per_day[day] += (r["duration_ms"] or 0) / 60_000.0
    start = (now - timedelta(days=364)).date()
    heatmap = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "count": per_day.get((start + timedelta(days=i)).isoformat(), 0),
            "minutes": round(minutes_per_day.get((start + timedelta(days=i)).isoformat(), 0.0), 1),
        }
        for i in range(365)
    ]

    # True retention: recall rate on reviews that were genuinely spaced (≥1 day).
    spaced = [r for r in reviews if r["stability_before"] is not None and r["elapsed_days"] >= 1]
    month_ago = (now - timedelta(days=30)).isoformat()
    recent = [r for r in spaced if r["reviewed_at"] >= month_ago]

    def recall_rate(rs):
        return round(sum(1 for r in rs if r["rating"] > 1) / len(rs), 4) if rs else None

    # Predicted vs actual — how well the memory model fits this learner.
    pred_pairs = [(r["retrievability"], int(r["rating"] > 1)) for r in spaced if r["retrievability"] is not None]
    predicted = round(sum(p for p, _ in pred_pairs) / len(pred_pairs), 4) if pred_pairs else None

    calib = calibration_report(
        [(float(r["confidence"]), int(r["rating"] > 2)) for r in reviews if r["confidence"] is not None]
    )

    learned = [m for m in mems if not m.is_new]
    stab_bins = [0, 1, 3, 7, 14, 30, 90, 180, 365, math.inf]
    stab_labels = ["<1d", "1-3d", "3-7d", "1-2w", "2-4w", "1-3mo", "3-6mo", "6-12mo", "1y+"]
    stab_hist = [0] * len(stab_labels)
    for m in learned:
        for i in range(len(stab_labels)):
            if stab_bins[i] <= float(m.stability) < stab_bins[i + 1]:
                stab_hist[i] += 1
                break
    diff_hist = [0] * 9
    for m in learned:
        diff_hist[min(8, max(0, int(float(m.difficulty or 5) - 1)))] += 1

    # Total retention-days banked over the next year: an honest "knowledge asset" number.
    knowledge_days = sum(
        fsrs.retention_area(float(m.stability), m.elapsed_days(now), m.elapsed_days(now) + 365) for m in learned
    )

    ratings = Counter(r["rating"] for r in reviews)
    return {
        "reviews_total": len(reviews),
        "minutes_total": round(sum((r["duration_ms"] or 0) for r in reviews) / 60_000.0, 1),
        "days_studied": len(per_day),
        "streak": streak_info(tz_offset_min, now),
        "heatmap": heatmap,
        "true_retention": {"all_time": recall_rate(spaced), "last_30d": recall_rate(recent), "n": len(spaced)},
        "model_fit": {"predicted": predicted, "actual": recall_rate([r for r in spaced if r["retrievability"] is not None])},
        "calibration": calib,
        "forecast": forecast(fsrs, mems, days=30, now=now),
        "stability_histogram": [{"label": l, "count": c} for l, c in zip(stab_labels, stab_hist)],
        "difficulty_histogram": [{"label": str(i + 1), "count": c} for i, c in enumerate(diff_hist)],
        "ratings": {str(k): ratings.get(k, 0) for k in (1, 2, 3, 4)},
        "knowledge_days": round(knowledge_days, 1),
        "cards_learned": len(learned),
        "model": {
            "desired_retention": fsrs.desired_retention,
            "parameters": list(fsrs.w),
            "personalized": bool(s["parameters_personalized"]),
            "last_fit": s["last_fit"],
            "decay": round(-fsrs.decay, 4),
        },
    }


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------


def graph(days_ahead: float = 0.0) -> Dict[str, Any]:
    fsrs = settings.get_fsrs()
    at = utcnow() + timedelta(days=days_ahead)
    rows = fetch_cards()
    stats = concept_stats(fsrs, at, rows)
    concepts = _concepts()
    edges = [e for e in _edges() if e[0] in concepts and e[1] in concepts]
    own = {cid: (stats.get(cid) or {}).get("retention") for cid in concepts}
    eff = effective_retention(own, edges)

    nodes = []
    for cid, c in concepts.items():
        st = stats.get(cid, {"cards": 0, "learned": 0, "due": 0, "stability": None, "mastery": 0.0})
        nodes.append(
            {
                "id": cid,
                "name": c["name"],
                "document_id": c["document_id"],
                "document_title": c["document_title"],
                "retention": own[cid],
                "effective_retention": None if eff.get(cid) is None else round(eff[cid], 4),  # type: ignore[arg-type]
                "cards": st["cards"],
                "learned": st["learned"],
                "due": st["due"],
                "stability": st.get("stability"),
                "mastery": st.get("mastery", 0.0),
            }
        )
    return {
        "at": at.isoformat(),
        "days_ahead": days_ahead,
        "nodes": nodes,
        "edges": [{"source": s_, "target": t, "weight": w, "kind": k} for s_, t, w, k in edges],
    }


# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------


def concept_list() -> List[Dict[str, Any]]:
    fsrs = settings.get_fsrs()
    stats = concept_stats(fsrs)
    out = []
    for cid, c in _concepts().items():
        st = stats.get(cid, {"cards": 0, "learned": 0, "due": 0, "retention": None, "stability": None, "mastery": 0.0, "difficulty": None})
        out.append({**c, **st})
    out.sort(key=lambda c: (c["document_title"], c["position"]))
    return out


def concept_detail(concept_id: str) -> Optional[Dict[str, Any]]:
    fsrs = settings.get_fsrs()
    now = utcnow()
    concepts = _concepts()
    if concept_id not in concepts:
        return None
    c = dict(concepts[concept_id])
    rows = fetch_cards("concept_id = ?", (concept_id,))
    with get_conn() as conn:
        all_rows = conn.execute(
            "SELECT * FROM cards WHERE concept_id = ? ORDER BY created_at", (concept_id,)
        ).fetchall()
    cards = [{**card_view(r, fsrs, now, with_preview=False), "suspended": bool(r["suspended"])} for r in all_rows]
    stats = concept_stats(fsrs, now)
    c.update(stats.get(concept_id, {"cards": 0, "learned": 0, "due": 0, "retention": None, "stability": None, "mastery": 0.0}))

    edges = _edges()
    own = {cid: (stats.get(cid) or {}).get("retention") for cid in concepts}
    eff = effective_retention(own, edges)
    c["effective_retention"] = eff.get(concept_id)

    def link(cid):
        return {"id": cid, "name": concepts[cid]["name"], "retention": own.get(cid)} if cid in concepts else None

    c["prerequisites"] = [link(s_) for s_, t, _, k in edges if t == concept_id and k == "prerequisite" and s_ in concepts]
    c["dependents"] = [link(t) for s_, t, _, k in edges if s_ == concept_id and k == "prerequisite" and t in concepts]
    c["related"] = [
        link(t if s_ == concept_id else s_)
        for s_, t, _, k in edges
        if k == "related" and concept_id in (s_, t)
    ]
    c["weak_foundations"] = [link(a) for a in weakest_foundations(concept_id, eff, edges)]

    # Concept-level forgetting curve: mean of card curves going forward.
    learned = [to_memory(r) for r in rows if r["stability"] is not None]
    curve = []
    for t in range(0, 91, 3):
        when = now + timedelta(days=t)
        rs = [fsrs.retrievability(m.elapsed_days(when), float(m.stability)) for m in learned]
        curve.append({"t": t, "r": round(sum(rs) / len(rs), 4) if rs else None})
    c["curve"] = curve
    c["cards_detail"] = cards

    with get_conn() as conn:
        chunks = conn.execute(
            "SELECT id, page, text FROM chunks WHERE concept_id = ? ORDER BY idx LIMIT 12", (concept_id,)
        ).fetchall()
        attempts = conn.execute(
            "SELECT id, score, result, created_at FROM feynman_attempts WHERE concept_id = ? ORDER BY created_at DESC LIMIT 5",
            (concept_id,),
        ).fetchall()
    c["passages"] = [dict(r) for r in chunks]
    c["feynman"] = [{**dict(a), "result": jloads(a["result"], {})} for a in attempts]
    return c


# ---------------------------------------------------------------------------
# Exams
# ---------------------------------------------------------------------------


def upcoming_exams() -> List[Dict[str, Any]]:
    init_db()
    now = utcnow()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM exams ORDER BY exam_date").fetchall()
    out = []
    for r in rows:
        when = parse_dt(r["exam_date"])
        if when is None or when < now - timedelta(days=1):
            continue
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "exam_date": r["exam_date"],
                "target": r["target"],
                "document_ids": jloads(r["document_ids"], []),
                "days_left": max(0, math.ceil((when - now).total_seconds() / 86_400.0)),
            }
        )
    return out


def exam_cards(document_ids: List[str]):
    if document_ids:
        marks = ",".join("?" * len(document_ids))
        return fetch_cards(f"document_id IN ({marks})", document_ids)
    return fetch_cards()


def exam_plan(exam_id: str) -> Optional[Dict[str, Any]]:
    from memory.planner import plan_exam

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if row is None:
        return None
    fsrs = settings.get_fsrs()
    secs = _avg_seconds()
    doc_ids = jloads(row["document_ids"], [])
    mems = [to_memory(r) for r in exam_cards(doc_ids)]
    when = parse_dt(row["exam_date"])
    assert when is not None
    plan = plan_exam(fsrs, mems, when, target=row["target"], review_seconds=secs["review"], new_seconds=secs["new"])

    now = utcnow()
    at_exam = [
        fsrs.retrievability(m.elapsed_days(when), float(m.stability)) for m in mems if not m.is_new
    ]
    return {
        "id": row["id"],
        "name": row["name"],
        "exam_date": row["exam_date"],
        "target": row["target"],
        "document_ids": doc_ids,
        "days_left": plan.days_left,
        "total_cards": plan.total_cards,
        "new_cards": sum(1 for m in mems if m.is_new),
        "daily": plan.daily,
        "projected_retention": plan.projected_retention,
        "projected_retention_no_plan": plan.projected_retention_no_plan,
        "cards_below_target": plan.cards_below_target,
        "current_retention_at_exam": round(sum(at_exam) / len(mems), 4) if mems else None,
        "today_minutes": plan.daily[0]["minutes"] if plan.daily else 0,
        "generated_at": now.isoformat(),
    }
