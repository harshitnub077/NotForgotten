"""Unit tests for the FSRS-6 memory model."""
from __future__ import annotations

import math

import pytest

from memory.fsrs import DEFAULT_PARAMETERS, FSRS, MemoryState, Rating

fsrs = FSRS()


class TestForgettingCurve:
    def test_r_is_one_at_zero(self):
        assert fsrs.retrievability(0, 5.0) == pytest.approx(1.0)

    def test_r_is_90pct_at_stability(self):
        for s in (0.5, 3.0, 40.0, 400.0):
            assert fsrs.retrievability(s, s) == pytest.approx(0.9, abs=1e-9)

    def test_r_monotonically_decreases(self):
        rs = [fsrs.retrievability(t, 10.0) for t in range(0, 100, 5)]
        assert all(a > b for a, b in zip(rs, rs[1:]))

    def test_interval_inverts_curve(self):
        for r in (0.7, 0.85, 0.9, 0.95):
            t = fsrs.interval_for(12.0, r)
            assert fsrs.retrievability(t, 12.0) == pytest.approx(r, abs=1e-9)

    def test_half_life(self):
        h = fsrs.half_life(10.0)
        assert fsrs.retrievability(h, 10.0) == pytest.approx(0.5, abs=1e-9)
        assert h > 10.0

    def test_retention_area_matches_numeric_integral(self):
        s, t0, t1 = 7.0, 2.0, 32.0
        n = 20_000
        dt = (t1 - t0) / n
        numeric = sum(fsrs.retrievability(t0 + (i + 0.5) * dt, s) for i in range(n)) * dt
        assert fsrs.retention_area(s, t0, t1) == pytest.approx(numeric, rel=1e-6)

    def test_zero_stability_is_zero(self):
        assert fsrs.retrievability(3, 0) == 0.0
        assert fsrs.retention_area(0, 0, 10) == 0.0


class TestTransitions:
    def test_initial_state_ordering(self):
        states = [fsrs.next_state(None, 0, r) for r in Rating]
        stabilities = [s.stability for s in states]
        difficulties = [s.difficulty for s in states]
        assert stabilities == sorted(stabilities)
        assert difficulties == sorted(difficulties, reverse=True)
        assert stabilities[0] == pytest.approx(DEFAULT_PARAMETERS[0])

    def test_success_grows_stability(self):
        s0 = MemoryState(stability=5.0, difficulty=5.0)
        for rating in (Rating.HARD, Rating.GOOD, Rating.EASY):
            assert fsrs.next_state(s0, 5.0, rating).stability > s0.stability

    def test_easy_beats_good_beats_hard(self):
        s0 = MemoryState(stability=5.0, difficulty=5.0)
        h, g, e = (fsrs.next_state(s0, 5.0, r).stability for r in (2, 3, 4))
        assert h < g < e

    def test_lapse_shrinks_stability(self):
        s0 = MemoryState(stability=30.0, difficulty=5.0)
        assert fsrs.next_state(s0, 30.0, Rating.AGAIN).stability < 30.0

    def test_later_review_gives_bigger_boost(self):
        """Spacing effect: recalling at lower R yields a larger stability gain."""
        s0 = MemoryState(stability=10.0, difficulty=5.0)
        early = fsrs.next_state(s0, 2.0, Rating.GOOD).stability
        late = fsrs.next_state(s0, 20.0, Rating.GOOD).stability
        assert late > early

    def test_difficulty_bounds(self):
        s = MemoryState(stability=1.0, difficulty=9.9)
        for _ in range(30):
            s = fsrs.next_state(s, 1.0, Rating.AGAIN)
        assert 1.0 <= s.difficulty <= 10.0
        s = MemoryState(stability=1.0, difficulty=1.1)
        for _ in range(30):
            s = fsrs.next_state(s, 2.0, Rating.EASY)
        assert 1.0 <= s.difficulty <= 10.0

    def test_same_day_good_does_not_reduce_stability(self):
        s0 = MemoryState(stability=2.0, difficulty=5.0)
        assert fsrs.next_state(s0, 0.01, Rating.GOOD).stability >= 2.0

    def test_invalid_rating(self):
        with pytest.raises(ValueError):
            fsrs.next_state(None, 0, 5)

    def test_wrong_param_count(self):
        with pytest.raises(ValueError):
            FSRS(parameters=[1.0] * 19)


class TestScheduling:
    def test_again_relearns_within_session(self):
        preview = fsrs.preview(MemoryState(10.0, 5.0), 10.0)
        assert preview[1][1] < 1.0

    def test_intervals_increase_with_rating(self):
        preview = fsrs.preview(MemoryState(10.0, 5.0), 10.0)
        days = [preview[r][1] for r in (1, 2, 3, 4)]
        assert days == sorted(days)

    def test_higher_desired_retention_shortens_interval(self):
        relaxed = FSRS(desired_retention=0.8).next_interval(20.0)
        strict = FSRS(desired_retention=0.95).next_interval(20.0)
        assert strict < relaxed

    def test_interval_capped(self):
        assert FSRS(max_interval=100).next_interval(1e6) == 100

    def test_good_streak_grows_exponentially(self):
        state, intervals = None, []
        elapsed = 0.0
        for _ in range(6):
            state = fsrs.next_state(state, elapsed, Rating.GOOD)
            elapsed = float(fsrs.next_interval(state.stability))
            intervals.append(elapsed)
        assert intervals == sorted(intervals)
        assert intervals[-1] > 60
        assert not math.isnan(intervals[-1])
