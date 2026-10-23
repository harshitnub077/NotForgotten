"""
Pytest configuration and shared fixtures.

Every test gets its own database: a temp SQLite file by default, or a freshly
reset schema when DATABASE_URL points at Postgres (as in CI).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    db = str(tmp_path / "test_memory.db")
    monkeypatch.setenv("DB_PATH", db)
    # Never hit a real LLM provider from the test suite.
    monkeypatch.setenv("NOTFORGOTTEN_OFFLINE", "1")
    monkeypatch.delenv("BETA_INVITE_CODES", raising=False)

    import memory.schema as schema_mod

    monkeypatch.setattr(schema_mod, "_DB_PATH", db)
    schema_mod.reset_init_cache()
    if schema_mod.is_postgres():
        with schema_mod.get_conn() as conn:
            conn.executescript("DROP SCHEMA public CASCADE; CREATE SCHEMA public")

    from core.auth import clear_rate_limits
    from retrieval.vector_store import get_store

    clear_rate_limits()
    get_store().invalidate()
    yield
