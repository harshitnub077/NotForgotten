"""
Study planning on top of the FSRS memory model.

Three ideas, all expressed in "retention-days" — the area under a card's
forgetting curve, i.e. how many days' worth of recall probability it holds:

1. Value of review (time-budgeted queue)
       gain = E[area | review now] − area | no review     (horizon H)
       E[area | review] = R·A(S_recall) + (1−R)·A(S_forget)
   Dividing gain by the expected seconds a review costs gives retention-days
   per second, so a greedy knapsack picks the best reviews for "I have 10
   minutes" instead of a blind due-date list.

2. Forecasts — expected retention and review workload for the next N days
   if the learner keeps to the schedule.

3. Exam planning — simulate the schedule up to an exam date, adding
   just-in-time final reviews so predicted recall *on exam day* clears a
   target, and report the daily workload that requires.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from memory.fsrs import FSRS, MemoryState, Rating

DEFAULT_HORIZON_DAYS = 30.0
DEFAULT_REVIEW_SECONDS = 20.0
DEFAULT_NEW_SECONDS = 45.0


@dataclass
class CardMemory:
    card_id: str
    stability: Optional[float] = None
    difficulty: Optional[float] = None
    last_review: Optional[datetime] = None
    due: Optional[datetime] = None
    concept_id: Optional[str] = None

    @property
    def is_new(self) -> bool:
        return self.stability is None or self.last_review is None

    def state(self) -> Optional[MemoryState]:
        if self.is_new:
            return None
        return MemoryState(float(self.stability), float(self.difficulty or 5.0))

    def elapsed_days(self, now: datetime) -> float:
        if self.last_review is None:
            return 0.0
        return max(0.0, (now - self.last_review).total_seconds() / 86_400.0)


@dataclass
class QueueItem:
    card_id: str
    retrievability: Optional[float]
    gain: float               # retention-days gained by reviewing now
    cost_seconds: float
    priority: float           # gain per second
    is_new: bool
    is_due: bool
    reason: str


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Value of review
# ---------------------------------------------------------------------------


def review_gain(
    fsrs: FSRS,
    card: CardMemory,
    now: datetime,
    horizon: float = DEFAULT_HORIZON_DAYS,
) -> float:
    """Expected retention-days gained over *horizon* by reviewing now."""
    if card.is_new:
        # Learning creates a memory where there was none (area 0 before).
        good = fsrs.next_state(None, 0.0, Rating.GOOD)
        return fsrs.retention_area(good.stability, 0.0, horizon)

    state = card.state()
    assert state is not None
    t = card.elapsed_days(now)
    r = fsrs.retrievability(t, state.stability)

    without = fsrs.retention_area(state.stability, t, t + horizon)
    recall = fsrs.next_state(state, t, Rating.GOOD)
    forget = fsrs.next_state(state, t, Rating.AGAIN)
    # A failed recall is followed by relearning, which restores R≈1 with the
    # (smaller) post-lapse stability.
    with_review = r * fsrs.retention_area(recall.stability, 0.0, horizon) + (
        1.0 - r
    ) * fsrs.retention_area(forget.stability, 0.0, horizon)
    return with_review - without


def build_queue(
    fsrs: FSRS,
    cards: List[CardMemory],
    now: Optional[datetime] = None,
    minutes: Optional[float] = None,
    max_new: int = 15,
    review_seconds: float = DEFAULT_REVIEW_SECONDS,
    new_seconds: float = DEFAULT_NEW_SECONDS,
    include_not_due: bool = False,
) -> List[QueueItem]:
    """
    Rank cards by retention-days gained per second.

    Without a time budget: every due card (plus up to *max_new* new cards),
    ordered by priority. With *minutes*: a greedy knapsack that may also pull
    in not-yet-due cards when they are the best use of the remaining time.
    """
    now = now or utcnow()
    items: List[QueueItem] = []
    new_count = 0

    for card in cards:
        is_due = card.is_new or (card.due is not None and card.due <= now)
        if card.is_new:
            if new_count >= max_new:
                continue
            new_count += 1
        elif not is_due and not include_not_due and minutes is None:
            continue

        gain = review_gain(fsrs, card, now)
        cost = new_seconds if card.is_new else review_seconds
        r = None if card.is_new else fsrs.retrievability(card.elapsed_days(now), card.stability or 0)
        if card.is_new:
            reason = "new"
        elif is_due:
            reason = "due"
        else:
            reason = "boost"
        items.append(
            QueueItem(
                card_id=card.card_id,
                retrievability=None if r is None else round(r, 4),
                gain=round(gain, 4),
                cost_seconds=cost,
                priority=gain / cost,
                is_new=card.is_new,
                is_due=is_due,
                reason=reason,
            )
        )

    # Due reviews before new material (forgetting is the expensive failure),
    # each group ordered by marginal value.
    items.sort(key=lambda it: (not (it.is_due and not it.is_new), -it.priority))

    if minutes is None:
        return [it for it in items if it.is_due]

    budget = minutes * 60.0
    chosen: List[QueueItem] = []
    for it in sorted(items, key=lambda it: -it.priority):
        if it.gain <= 0:
            continue
        if it.cost_seconds <= budget:
            chosen.append(it)
            budget -= it.cost_seconds
    chosen.sort(key=lambda it: (not (it.is_due and not it.is_new), -it.priority))
    return chosen


# ---------------------------------------------------------------------------
# 2. Forecasts
# ---------------------------------------------------------------------------


def retention_at(fsrs: FSRS, card: CardMemory, when: datetime) -> Optional[float]:
    if card.is_new:
        return None
    return fsrs.retrievability(card.elapsed_days(when), float(card.stability))


def forecast(
    fsrs: FSRS,
    cards: List[CardMemory],
    days: int = 30,
    now: Optional[datetime] = None,
) -> List[Dict[str, float]]:
    """
    Per-day projection: due workload if you keep up, and the average
    retention of learned cards if you stop reviewing entirely (the decay
    you are protecting against).
    """
    now = now or utcnow()
    learned = [c for c in cards if not c.is_new]
    out: List[Dict[str, float]] = []

    # Simulate keeping up (assume Good) to estimate workload per day.
    sim = {c.card_id: (c.state(), c.last_review, c.due) for c in learned}
    for day in range(days + 1):
        day_start = now + timedelta(days=day)
        day_end = day_start + timedelta(days=1)
        due_today = 0
        for cid, (state, last, due) in list(sim.items()):
            if due is not None and due < day_end and state is not None and last is not None:
                due_today += 1
                t = (max(due, day_start) - last).total_seconds() / 86_400.0
                ns = fsrs.next_state(state, t, Rating.GOOD)
                reviewed_at = max(due, day_start)
                sim[cid] = (
                    ns,
                    reviewed_at,
                    reviewed_at + timedelta(days=fsrs.next_interval(ns.stability)),
                )

        if learned:
            idle = [retention_at(fsrs, c, day_start) or 0.0 for c in learned]
            kept = [
                fsrs.retrievability((day_end - last).total_seconds() / 86_400.0, st.stability)
                for st, last, _ in sim.values()
                if st is not None and last is not None
            ]
            avg_idle = sum(idle) / len(idle)
            avg_kept = sum(kept) / len(kept) if kept else 0.0
        else:
            avg_idle = avg_kept = 0.0
        out.append(
            {
                "day": day,
                "date": day_start.date().isoformat(),
                "due": due_today,
                "retention_if_idle": round(avg_idle, 4),
                "retention_if_kept": round(avg_kept, 4),
            }
        )
    return out


# ---------------------------------------------------------------------------
# 3. Exam planner
# ---------------------------------------------------------------------------


@dataclass
class ExamPlan:
    exam_date: str
    days_left: int
    target: float
    daily: List[Dict[str, float]] = field(default_factory=list)
    projected_retention: float = 0.0
    projected_retention_no_plan: float = 0.0
    cards_below_target: int = 0
    total_cards: int = 0


def plan_exam(
    fsrs: FSRS,
    cards: List[CardMemory],
    exam_date: datetime,
    target: float = 0.9,
    now: Optional[datetime] = None,
    review_seconds: float = DEFAULT_REVIEW_SECONDS,
    new_seconds: float = DEFAULT_NEW_SECONDS,
) -> ExamPlan:
    """
    Simulate daily study until *exam_date* assuming successful recall.

    A learned card is reviewed on day d when either
      • R(d) has fallen below the scheduler's desired retention, or
      • R on exam day would miss *target* and a review today (Good) would
        carry it past the exam — the just-in-time final review.
    New cards are introduced evenly across the first ~60% of the window so
    every card gets several spaced repetitions before the exam.
    """
    now = now or utcnow()
    days_left = max(1, math.ceil((exam_date - now).total_seconds() / 86_400.0))
    plan = ExamPlan(
        exam_date=exam_date.date().isoformat(),
        days_left=days_left,
        target=target,
        total_cards=len(cards),
    )
    if not cards:
        return plan

    new_cards = [c for c in cards if c.is_new]
    learn_window = max(1, int(days_left * 0.6))
    per_day_new = math.ceil(len(new_cards) / learn_window) if new_cards else 0

    # card_id -> (state, last_review_day_offset)
    sim: Dict[str, tuple] = {}
    for c in cards:
        if not c.is_new:
            sim[c.card_id] = (c.state(), -c.elapsed_days(now))

    no_plan = [
        fsrs.retrievability(days_left - st[1], st[0].stability) for st in sim.values()
    ]
    plan.projected_retention_no_plan = round(sum(no_plan) / len(cards), 4)

    new_iter = iter(new_cards)
    for day in range(days_left):
        reviews = 0
        learned_today = 0
        for cid, (state, last) in list(sim.items()):
            elapsed = day - last
            r_now = fsrs.retrievability(elapsed, state.stability)
            r_exam = fsrs.retrievability(days_left - last, state.stability)
            due = r_now <= fsrs.desired_retention
            if not due and r_exam < target:
                after = fsrs.next_state(state, elapsed, Rating.GOOD)
                due = fsrs.retrievability(days_left - day, after.stability) >= target or (
                    days_left - day <= 1
                )
            if due and elapsed >= 1.0:
                sim[cid] = (fsrs.next_state(state, elapsed, Rating.GOOD), day)
                reviews += 1
        for _ in range(per_day_new):
            card = next(new_iter, None)
            if card is None:
                break
            sim[card.card_id] = (fsrs.next_state(None, 0.0, Rating.GOOD), day)
            learned_today += 1
        plan.daily.append(
            {
                "day": day,
                "date": (now + timedelta(days=day)).date().isoformat(),
                "reviews": reviews,
                "new": learned_today,
                "minutes": round((reviews * review_seconds + learned_today * new_seconds) / 60.0, 1),
            }
        )

    final = [fsrs.retrievability(days_left - last, st.stability) for st, last in sim.values()]
    final += [0.0] * (len(cards) - len(final))
    plan.projected_retention = round(sum(final) / len(cards), 4)
    plan.cards_below_target = sum(1 for r in final if r < target)
    return plan
