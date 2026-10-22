"""Tests for planning, calibration and the personal-curve optimizer."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from memory.calibration import calibration_report
from memory.fsrs import FSRS, DEFAULT_PARAMETERS, Rating
from memory.optimizer import evaluate, fit
from memory.planner import CardMemory, build_queue, forecast, plan_exam, review_gain

NOW = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
fsrs = FSRS()


def _learned(cid: str, stability: float, days_ago: float) -> CardMemory:
    last = NOW - timedelta(days=days_ago)
    due = last + timedelta(days=fsrs.next_interval(stability))
    return CardMemory(cid, stability=stability, difficulty=5.0, last_review=last, due=due)


class TestValueOfReview:
    def test_overdue_card_gains_more_than_fresh_one(self):
        fresh = _learned("fresh", 10.0, 0.5)
        overdue = _learned("overdue", 10.0, 25.0)
        assert review_gain(fsrs, overdue, NOW) > review_gain(fsrs, fresh, NOW)

    def test_new_card_gain_positive(self):
        assert review_gain(fsrs, CardMemory("n"), NOW) > 0

    def test_queue_only_due_without_budget(self):
        cards = [_learned("due", 3.0, 10.0), _learned("notdue", 50.0, 1.0)]
        ids = [q.card_id for q in build_queue(fsrs, cards, NOW)]
        assert ids == ["due"]

    def test_budget_respected(self):
        cards = [_learned(f"c{i}", 3.0, 10.0 + i) for i in range(50)]
        queue = build_queue(fsrs, cards, NOW, minutes=2, review_seconds=20)
        assert len(queue) == 6
        assert sum(q.cost_seconds for q in queue) <= 120

    def test_max_new_limit(self):
        cards = [CardMemory(f"n{i}") for i in range(40)]
        queue = build_queue(fsrs, cards, NOW, max_new=10)
        assert len(queue) == 10 and all(q.is_new for q in queue)

    def test_due_reviews_come_before_new(self):
        cards = [CardMemory("new"), _learned("due", 3.0, 10.0)]
        queue = build_queue(fsrs, cards, NOW)
        assert queue[0].card_id == "due"


class TestForecastAndExam:
    def test_forecast_shapes(self):
        cards = [_learned(f"c{i}", 2.0 + i, i) for i in range(10)]
        fc = forecast(fsrs, cards, days=14, now=NOW)
        assert len(fc) == 15
        idle = [d["retention_if_idle"] for d in fc]
        assert idle == sorted(idle, reverse=True)
        assert fc[-1]["retention_if_kept"] > fc[-1]["retention_if_idle"]

    def test_exam_plan_beats_no_plan(self):
        cards = [_learned(f"c{i}", 4.0, 3.0) for i in range(20)] + [
            CardMemory(f"n{i}") for i in range(20)
        ]
        plan = plan_exam(fsrs, cards, NOW + timedelta(days=21), target=0.9, now=NOW)
        assert plan.days_left == 21
        assert len(plan.daily) == 21
        assert plan.projected_retention > plan.projected_retention_no_plan
        assert plan.projected_retention >= 0.85
        assert sum(d["new"] for d in plan.daily) == 20

    def test_exam_plan_empty(self):
        plan = plan_exam(fsrs, [], NOW + timedelta(days=5), now=NOW)
        assert plan.total_cards == 0


class TestCalibration:
    def test_perfect_calibration(self):
        pairs = [(1.0, 1)] * 10 + [(0.0, 0)] * 10
        rep = calibration_report(pairs)
        assert rep["brier"] == 0
        assert rep["ece"] == 0
        assert rep["overconfidence"] == 0

    def test_overconfident_learner(self):
        pairs = [(0.9, 1)] * 5 + [(0.9, 0)] * 5
        rep = calibration_report(pairs)
        assert rep["overconfidence"] == pytest.approx(0.4)
        assert rep["ece"] == pytest.approx(0.4)

    def test_empty(self):
        assert calibration_report([])["brier"] is None


def _simulate_learner(true_params, n_cards=60, seed=7):
    """Generate review logs from a learner whose memory follows *true_params*."""
    rng = random.Random(seed)
    truth = FSRS(true_params)
    logs = []
    for _ in range(n_cards):
        t = NOW - timedelta(days=200)
        state, last, log = None, None, []
        for _ in range(8):
            if state is None:
                rating = 3
            else:
                elapsed = (t - last).total_seconds() / 86_400.0
                recalled = rng.random() < truth.retrievability(elapsed, state.stability)
                rating = rng.choice([2, 3, 3, 4]) if recalled else 1
            elapsed = 0.0 if last is None else (t - last).total_seconds() / 86_400.0
            state = truth.next_state(state, elapsed, rating)
            log.append((t, rating))
            last = t
            # learner reviews a bit irregularly around the scheduled date
            gap = max(1, truth.next_interval(state.stability) * rng.uniform(0.6, 2.2))
            t = t + timedelta(days=gap)
        logs.append(log)
    return logs


class TestOptimizer:
    def test_fit_improves_on_mismatched_learner(self):
        true = list(DEFAULT_PARAMETERS)
        true[2] = 0.6     # forgets new material much faster than average
        true[8] = 1.2     # slower stability growth
        logs = _simulate_learner(true)
        result = fit(logs)
        assert result.n_predictions > 100
        assert result.loss_after <= result.loss_before
        assert result.improved
        assert result.parameters[2] < DEFAULT_PARAMETERS[2]

    def test_too_little_data_keeps_defaults(self):
        logs = _simulate_learner(DEFAULT_PARAMETERS, n_cards=2)
        result = fit(logs)
        assert not result.improved
        assert result.parameters == list(DEFAULT_PARAMETERS)

    def test_evaluate_returns_finite(self):
        loss, rmse, n = evaluate(DEFAULT_PARAMETERS, _simulate_learner(DEFAULT_PARAMETERS, 10))
        assert n > 0 and loss > 0 and rmse >= 0
