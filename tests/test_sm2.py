"""Unit tests for the SM-2 algorithm."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from memory.sm2 import DEFAULT_EASE, MINIMUM_EASE, SM2Result, sm2

NOW = datetime(2024, 6, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


class TestSM2BasicCorrectness:
    def test_perfect_rating_first_rep(self):
        result = sm2(rating=5, easiness_factor=2.5, interval_days=1, repetitions=0, now=NOW)
        assert result.repetitions == 1
        assert result.interval_days == 1  # first rep always 1
        assert result.easiness_factor > 2.5  # ease increases on perfect rating

    def test_second_rep_interval_is_6(self):
        result = sm2(rating=5, easiness_factor=2.5, interval_days=1, repetitions=1, now=NOW)
        assert result.repetitions == 2
        assert result.interval_days == 6

    def test_third_rep_uses_ease_factor(self):
        result = sm2(rating=5, easiness_factor=2.5, interval_days=6, repetitions=2, now=NOW)
        assert result.repetitions == 3
        expected_interval = 16
        assert result.interval_days == expected_interval

    def test_failed_recall_resets_reps(self):
        result = sm2(rating=1, easiness_factor=2.5, interval_days=30, repetitions=10, now=NOW)
        assert result.repetitions == 0
        assert result.interval_days == 1

    def test_failed_recall_rating_2_resets(self):
        result = sm2(rating=2, easiness_factor=2.5, interval_days=10, repetitions=5, now=NOW)
        assert result.repetitions == 0
        assert result.interval_days == 1

    def test_rating_3_is_passing(self):
        result = sm2(rating=3, easiness_factor=2.5, interval_days=1, repetitions=0, now=NOW)
        assert result.repetitions == 1  # counted as success


# ---------------------------------------------------------------------------
# Ease factor bounds
# ---------------------------------------------------------------------------


class TestEaseFactor:
    def test_ease_never_below_minimum(self):
        # Worst possible rating, many times over
        ease = DEFAULT_EASE
        result = None
        for _ in range(20):
            result = sm2(rating=0, easiness_factor=ease, interval_days=1, repetitions=0, now=NOW)
            ease = result.easiness_factor
        assert ease >= MINIMUM_EASE

    def test_ease_increases_on_perfect(self):
        result = sm2(rating=5, easiness_factor=2.5, interval_days=1, repetitions=1, now=NOW)
        assert result.easiness_factor > 2.5

    def test_ease_decreases_on_low_rating(self):
        result = sm2(rating=3, easiness_factor=2.5, interval_days=1, repetitions=1, now=NOW)
        assert result.easiness_factor < 2.5

    def test_ease_stable_on_rating_4(self):
        # rating=4 → Δease ≈ 0 (slight positive)
        result = sm2(rating=4, easiness_factor=2.5, interval_days=1, repetitions=1, now=NOW)
        # Should be close to 2.5 (slight increase)
        assert abs(result.easiness_factor - 2.5) < 0.2


# ---------------------------------------------------------------------------
# Next review date
# ---------------------------------------------------------------------------


class TestNextReview:
    def test_next_review_offset_by_interval(self):
        result = sm2(rating=5, easiness_factor=2.5, interval_days=1, repetitions=1, now=NOW)
        # Second rep → interval = 6 days
        expected_days = (result.next_review - NOW).days
        assert expected_days == result.interval_days

    def test_next_review_type(self):
        result = sm2(rating=4, now=NOW)
        assert isinstance(result, SM2Result)
        assert isinstance(result.next_review, datetime)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_rating_out_of_range_raises(self):
        with pytest.raises(ValueError):
            sm2(rating=6)

    def test_rating_negative_raises(self):
        with pytest.raises(ValueError):
            sm2(rating=-1)


# ---------------------------------------------------------------------------
# Long-run simulation — convergence
# ---------------------------------------------------------------------------


class TestLongRun:
    def test_high_rater_gets_long_intervals(self):
        ease = DEFAULT_EASE
        interval = 1
        reps = 0
        for _ in range(10):
            r = sm2(rating=5, easiness_factor=ease, interval_days=interval, repetitions=reps, now=NOW)
            ease, interval, reps = r.easiness_factor, r.interval_days, r.repetitions
        assert interval > 100  # should be well over 100 days after 10 perfect reviews

    def test_low_rater_stays_short(self):
        ease = DEFAULT_EASE
        interval = 1
        reps = 0
        for _ in range(10):
            r = sm2(rating=2, easiness_factor=ease, interval_days=interval, repetitions=reps, now=NOW)
            ease, interval, reps = r.easiness_factor, r.interval_days, r.repetitions
        assert interval == 1  # always resets on failure
