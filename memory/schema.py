"""SQLite schema and connection helper."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

_DB_PATH = os.getenv("DB_PATH", "./data/memory.db")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    filename       TEXT,
    kind           TEXT NOT NULL,                 -- pdf | text | markdown | url
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
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx          INTEGER NOT NULL,
    page         INTEGER NOT NULL DEFAULT 0,
    text         TEXT NOT NULL,
    concept_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (document_id, idx);
CREATE INDEX IF NOT EXISTS idx_chunks_concept ON chunks (concept_id);

CREATE TABLE IF NOT EXISTS concepts (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    keywords     TEXT NOT NULL DEFAULT '[]',      -- JSON array
    centroid     TEXT NOT NULL DEFAULT '[]',      -- JSON array of floats
    position     REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_concepts_doc ON concepts (document_id);

CREATE TABLE IF NOT EXISTS concept_links (
    source  TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    target  TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    weight  REAL NOT NULL,
    kind    TEXT NOT NULL,                        -- prerequisite | related
    PRIMARY KEY (source, target)
);

CREATE TABLE IF NOT EXISTS cards (
    id               TEXT PRIMARY KEY,
    concept_id       TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    document_id      TEXT REFERENCES documents(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,               -- qa | cloze | explain
    prompt           TEXT NOT NULL,
    answer           TEXT NOT NULL,
    explanation      TEXT NOT NULL DEFAULT '',
    source_chunk_id  TEXT,
    origin           TEXT NOT NULL DEFAULT 'generated',
    stability        REAL,
    difficulty       REAL,
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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    rating           INTEGER NOT NULL,            -- 1 Again | 2 Hard | 3 Good | 4 Easy
    score            REAL,
    confidence       REAL,
    response         TEXT,
    elapsed_days     REAL NOT NULL DEFAULT 0,
    scheduled_days   REAL NOT NULL DEFAULT 0,
    retrievability   REAL,
    stability_before REAL,
    stability_after  REAL NOT NULL,
    difficulty_after REAL NOT NULL,
    duration_ms      INTEGER,
    session_id       TEXT,
    reviewed_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews (card_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_reviews_time ON reviews (reviewed_at);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    document_id  TEXT,
    status       TEXT NOT NULL,                   -- running | done | failed
    stage        TEXT NOT NULL,
    progress     REAL NOT NULL DEFAULT 0,
    message      TEXT NOT NULL DEFAULT '',
    log          TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL                          -- JSON
);

CREATE TABLE IF NOT EXISTS feynman_attempts (
    id           TEXT PRIMARY KEY,
    concept_id   TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    explanation  TEXT NOT NULL,
    score        REAL NOT NULL,
    result       TEXT NOT NULL,                   -- JSON
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exams (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    exam_date     TEXT NOT NULL,
    target        REAL NOT NULL DEFAULT 0.9,
    document_ids  TEXT NOT NULL DEFAULT '[]',     -- JSON; empty = everything
    created_at    TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


def get_db_path() -> str:
    path = Path(_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Context-managed SQLite connection with WAL mode and FK enforcement."""
    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
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


_initialised_for: set = set()


def init_db() -> None:
    """Create tables if they don't exist (idempotent, cheap after first call)."""
    path = get_db_path()
    if path in _initialised_for and Path(path).exists():
        return
    with get_conn() as conn:
        conn.executescript(_DDL)
    _initialised_for.add(path)


if __name__ == "__main__":
    init_db()
    print(f"[DB] Initialised at {get_db_path()}")
