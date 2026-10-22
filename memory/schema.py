"""
Database access: SQLite locally, PostgreSQL in the cloud.

Set DATABASE_URL (postgres://…) to use a hosted Postgres such as Neon,
Supabase or Render; otherwise a local SQLite file at DB_PATH is used. Code
everywhere writes one SQL dialect (qmark `?` placeholders, portable DDL and
upserts); the Postgres adapter translates placeholders on the way through.
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from dotenv import load_dotenv

load_dotenv()

_DB_PATH = os.getenv("DB_PATH", "./data/memory.db")


def database_url() -> Optional[str]:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def is_postgres() -> bool:
    url = database_url()
    return bool(url and url.startswith(("postgres://", "postgresql://")))


# ---------------------------------------------------------------------------
# DDL (portable; {PK_AUTO}, {BLOB}, {FLOAT} filled per dialect)
# ---------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id               TEXT PRIMARY KEY,
    email            TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL DEFAULT '',
    password_hash    TEXT NOT NULL,
    library_version  INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_login       TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    user_agent  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);

CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    user_id        TEXT REFERENCES users(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    filename       TEXT,
    kind           TEXT NOT NULL,
    source_url     TEXT,
    size_bytes     INTEGER NOT NULL DEFAULT 0,
    chunk_count    INTEGER NOT NULL DEFAULT 0,
    concept_count  INTEGER NOT NULL DEFAULT 0,
    card_count     INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'processing',
    error          TEXT,
    is_demo        INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx          INTEGER NOT NULL,
    page         INTEGER NOT NULL DEFAULT 0,
    text         TEXT NOT NULL,
    concept_id   TEXT,
    embedding    {BLOB}
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (document_id, idx);
CREATE INDEX IF NOT EXISTS idx_chunks_concept ON chunks (concept_id);

CREATE TABLE IF NOT EXISTS concepts (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    keywords     TEXT NOT NULL DEFAULT '[]',
    centroid     TEXT NOT NULL DEFAULT '[]',
    position     {FLOAT} NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_concepts_doc ON concepts (document_id);

CREATE TABLE IF NOT EXISTS concept_links (
    source   TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    target   TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    user_id  TEXT REFERENCES users(id) ON DELETE CASCADE,
    weight   {FLOAT} NOT NULL,
    kind     TEXT NOT NULL,
    PRIMARY KEY (source, target)
);

CREATE TABLE IF NOT EXISTS cards (
    id               TEXT PRIMARY KEY,
    user_id          TEXT REFERENCES users(id) ON DELETE CASCADE,
    concept_id       TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    document_id      TEXT REFERENCES documents(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,
    prompt           TEXT NOT NULL,
    answer           TEXT NOT NULL,
    explanation      TEXT NOT NULL DEFAULT '',
    source_chunk_id  TEXT,
    origin           TEXT NOT NULL DEFAULT 'generated',
    stability        {FLOAT},
    difficulty       {FLOAT},
    due              TEXT,
    last_review      TEXT,
    reps             INTEGER NOT NULL DEFAULT 0,
    lapses           INTEGER NOT NULL DEFAULT 0,
    suspended        INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_concept ON cards (concept_id);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards (due);

CREATE TABLE IF NOT EXISTS reviews (
    id               {PK_AUTO},
    user_id          TEXT REFERENCES users(id) ON DELETE CASCADE,
    card_id          TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    rating           INTEGER NOT NULL,
    score            {FLOAT},
    confidence       {FLOAT},
    response         TEXT,
    elapsed_days     {FLOAT} NOT NULL DEFAULT 0,
    scheduled_days   {FLOAT} NOT NULL DEFAULT 0,
    retrievability   {FLOAT},
    stability_before {FLOAT},
    stability_after  {FLOAT} NOT NULL,
    difficulty_after {FLOAT} NOT NULL,
    duration_ms      INTEGER,
    session_id       TEXT,
    reviewed_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews (card_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_reviews_time ON reviews (reviewed_at);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
    document_id  TEXT,
    status       TEXT NOT NULL,
    stage        TEXT NOT NULL,
    progress     {FLOAT} NOT NULL DEFAULT 0,
    message      TEXT NOT NULL DEFAULT '',
    log          TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS feynman_attempts (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
    concept_id   TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    explanation  TEXT NOT NULL,
    score        {FLOAT} NOT NULL,
    result       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exams (
    id            TEXT PRIMARY KEY,
    user_id       TEXT REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    exam_date     TEXT NOT NULL,
    target        {FLOAT} NOT NULL DEFAULT 0.9,
    document_ids  TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL
);
"""

# Tables that carry user_id (added by migration to pre-accounts databases).
USER_TABLES = (
    "documents",
    "chunks",
    "concepts",
    "concept_links",
    "cards",
    "reviews",
    "jobs",
    "feynman_attempts",
    "exams",
)

_USER_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents (user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user ON chunks (user_id);
CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts (user_id);
CREATE INDEX IF NOT EXISTS idx_links_user ON concept_links (user_id);
CREATE INDEX IF NOT EXISTS idx_cards_user_due ON cards (user_id, due);
CREATE INDEX IF NOT EXISTS idx_reviews_user_time ON reviews (user_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id, status);
CREATE INDEX IF NOT EXISTS idx_exams_user ON exams (user_id);
"""


def _ddl() -> str:
    if is_postgres():
        return _DDL.format(PK_AUTO="BIGSERIAL PRIMARY KEY", BLOB="BYTEA", FLOAT="DOUBLE PRECISION")
    return _DDL.format(PK_AUTO="INTEGER PRIMARY KEY AUTOINCREMENT", BLOB="BLOB", FLOAT="REAL")


# ---------------------------------------------------------------------------
# Rows: support both row["name"] and row[0]
# ---------------------------------------------------------------------------


class Row(dict):
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def keys(self):  # sqlite3.Row compatibility
        return super().keys()


def _sqlite_row(cursor: sqlite3.Cursor, values: tuple) -> Row:
    return Row(zip([c[0] for c in cursor.description], values))


# ---------------------------------------------------------------------------
# Postgres adapter
# ---------------------------------------------------------------------------

_QMARK = re.compile(r"\?")
_pool = None
_pool_lock = threading.Lock()


def _to_pg(sql: str) -> str:
    return _QMARK.sub("%s", sql)


class _PgConn:
    """Gives a psycopg connection the sqlite3 surface this codebase uses."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Iterable[Any] = ()):
        cur = self._conn.cursor()
        cur.execute(_to_pg(sql), tuple(_pg_param(p) for p in params))
        return cur

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]):
        cur = self._conn.cursor()
        rows = [tuple(_pg_param(p) for p in r) for r in seq]
        if rows:
            cur.executemany(_to_pg(sql), rows)
        return cur

    def executescript(self, script: str) -> None:
        cur = self._conn.cursor()
        for stmt in (s.strip() for s in script.split(";")):
            if stmt:
                cur.execute(stmt)


def _pg_param(p: Any) -> Any:
    return bytes(p) if isinstance(p, (bytearray, memoryview)) else p


def _pg_row_factory(cursor: Any):
    names = [c.name for c in cursor.description] if cursor.description else []

    def make(values: tuple) -> Row:
        return Row(zip(names, (bytes(v) if isinstance(v, memoryview) else v for v in values)))

    return make


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool

            url = database_url()
            assert url is not None
            _pool = ConnectionPool(
                url,
                min_size=1,
                max_size=int(os.getenv("DB_POOL_SIZE", "10")),
                kwargs={"row_factory": _pg_row_factory, "autocommit": False},
                open=True,
            )
        return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


def get_db_path() -> str:
    path = Path(_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    """One transaction: commits on success, rolls back on error."""
    if is_postgres():
        with _get_pool().connection() as raw:
            try:
                yield _PgConn(raw)
                raw.commit()
            except Exception:
                raw.rollback()
                raise
        return

    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = _sqlite_row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bootstrap & migrations
# ---------------------------------------------------------------------------

_initialised_for: set = set()


def _columns(conn: Any, table: str) -> set:
    if is_postgres():
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?", (table,)
        ).fetchall()
        return {r["column_name"] for r in rows}
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate(conn: Any) -> None:
    """Bring a pre-accounts (v2.0) database up to the multi-user schema."""
    for table in USER_TABLES:
        if "user_id" not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
    if "embedding" not in _columns(conn, "chunks"):
        conn.execute(f"ALTER TABLE chunks ADD COLUMN embedding {'BYTEA' if is_postgres() else 'BLOB'}")


def init_db() -> None:
    """Create tables and apply migrations (idempotent, cheap after first call)."""
    key = database_url() or get_db_path()
    if key in _initialised_for and (is_postgres() or Path(key).exists()):
        return
    with get_conn() as conn:
        conn.executescript(_ddl())
        _migrate(conn)
        conn.executescript(_USER_INDEXES)
    _initialised_for.add(key)


def reset_init_cache() -> None:
    _initialised_for.clear()


if __name__ == "__main__":
    init_db()
    print(f"[DB] Initialised ({'postgres' if is_postgres() else get_db_path()})")
