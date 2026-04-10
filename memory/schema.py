"""SQLite schema bootstrap for memory tables."""
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
CREATE TABLE IF NOT EXISTS concept_memory (
    concept_id       TEXT PRIMARY KEY,
    easiness_factor  REAL    NOT NULL DEFAULT 2.5,
    interval_days    INTEGER NOT NULL DEFAULT 1,
    repetitions      INTEGER NOT NULL DEFAULT 0,
    last_review      TEXT,                        -- ISO-8601 datetime string
    next_review      TEXT,                        -- ISO-8601 datetime string
    retention_prob   REAL    NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS session_log (
    session_id  TEXT    NOT NULL,
    concept_id  TEXT    NOT NULL,
    user_rating INTEGER NOT NULL,                 -- 0-5 (SM-2 scale)
    timestamp   TEXT    NOT NULL                  -- ISO-8601
);

CREATE INDEX IF NOT EXISTS idx_session_log_concept
    ON session_log (concept_id);

CREATE INDEX IF NOT EXISTS idx_concept_memory_next_review
    ON concept_memory (next_review);
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
    """Context-managed SQLite connection with WAL mode."""
    conn = sqlite3.connect(get_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
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


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript(_DDL)
    print(f"[DB] Initialized at {get_db_path()}")


if __name__ == "__main__":
    init_db()
