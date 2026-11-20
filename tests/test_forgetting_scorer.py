"""Unit tests for ForgettingScorer."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from memory.forgetting_scorer import ForgettingScorer, retention, urgency_score


NOW = datetime(2024, 6, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Retention math
# ---------------------------------------------------------------------------


class TestRetentionMath:
    def test_zero_elapsed_time(self):
        # t=0 → R = e^0 = 1.0 (perfect recall)
        assert retention(t_days=0, stability=10) == pytest.approx(1.0)

    def test_full_forgetting(self):
        # very large t relative to S → R ≈ 0
        r = retention(t_days=1000, stability=1)
        assert r < 0.01

    def test_retention_at_stability(self):
        # t == S → R = e^(-1) ≈ 0.368
        r = retention(t_days=10, stability=10)
        assert r == pytest.approx(math.exp(-1), rel=1e-6)

    def test_stability_zero_returns_zero(self):
        assert retention(t_days=1, stability=0) == 0.0

    def test_urgency_is_complement(self):
        r = retention(t_days=5, stability=10)
        u = urgency_score(t_days=5, stability=10)
        assert r + u == pytest.approx(1.0)

    def test_urgency_increases_with_time(self):
        u1 = urgency_score(t_days=1, stability=10)
        u2 = urgency_score(t_days=5, stability=10)
        assert u2 > u1

    def test_urgency_range(self):
        for t in range(0, 30):
            u = urgency_score(t_days=t, stability=10)
            assert 0.0 <= u <= 1.0


# ---------------------------------------------------------------------------
# ForgettingScorer with SQLite
# ---------------------------------------------------------------------------


class TestForgettingScorer:
    """Tests that require a real (temp) SQLite DB."""

    def _seed_db(self, concept_id: str, days_since_review: int, interval: int = 7, ease: float = 2.5):
        """Insert a row into concept_memory."""
        from memory.schema import init_db, get_conn

        init_db()
        last_review = (NOW - timedelta(days=days_since_review)).isoformat()
        next_review = (NOW + timedelta(days=interval - days_since_review)).isoformat()

        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO concept_memory
                (concept_id, easiness_factor, interval_days, repetitions, last_review, next_review, retention_prob)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (concept_id, ease, interval, 3, last_review, next_review, 1.0),
            )

    def test_no_review_gets_max_urgency(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        from memory import schema
        schema._DB_PATH = str(tmp_path / "test.db")
        from importlib import reload
        reload(schema)

        from memory.schema import init_db, get_conn
        init_db()

        # Insert concept with no last_review
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO concept_memory (concept_id) VALUES (?)",
                ("new_concept",),
            )

        scorer = ForgettingScorer(now=NOW)
        scores = scorer.score_all()
        assert scores.get("new_concept") == 1.0

    def test_recently_reviewed_has_low_urgency(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        from memory import schema
        schema._DB_PATH = str(tmp_path / "test.db")
        from importlib import reload
        reload(schema)

        self._seed_db("fresh_concept", days_since_review=0, interval=7, ease=2.5)

        scorer = ForgettingScorer(now=NOW)
        scores = scorer.score_all()
        # Just reviewed (t=0) → urgency very close to 0
        assert scores.get("fresh_concept", 1.0) < 0.1

    def test_old_concept_has_high_urgency(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        from memory import schema
        schema._DB_PATH = str(tmp_path / "test.db")
        from importlib import reload
        reload(schema)

        # Reviewed 30 days ago with interval 7 → very overdue
        self._seed_db("old_concept", days_since_review=30, interval=7, ease=2.5)

        scorer = ForgettingScorer(now=NOW)
        scores = scorer.score_all()
        assert scores.get("old_concept", 0.0) > 0.8

    def test_top_urgent_ordering(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
        from memory import schema
        schema._DB_PATH = str(tmp_path / "test.db")
        from importlib import reload
        reload(schema)

        self._seed_db("urgent", days_since_review=25, interval=7, ease=2.5)
        self._seed_db("fresh", days_since_review=0, interval=7, ease=2.5)

        scorer = ForgettingScorer(now=NOW)
        top = scorer.top_urgent(n=2)
        assert top[0][0] == "urgent"
        assert top[1][0] == "fresh"
