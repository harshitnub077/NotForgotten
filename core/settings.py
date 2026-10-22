"""User settings persisted in SQLite (scheduler parameters, limits, goals)."""
from __future__ import annotations

from typing import Any, Dict

from memory.fsrs import DEFAULT_DESIRED_RETENTION, DEFAULT_PARAMETERS, FSRS
from memory.schema import get_conn, init_db
from core.util import jdumps, jloads

DEFAULTS: Dict[str, Any] = {
    "desired_retention": DEFAULT_DESIRED_RETENTION,
    "fsrs_parameters": list(DEFAULT_PARAMETERS),
    "parameters_personalized": False,
    "last_fit": None,
    "daily_new_limit": 20,
    "daily_goal_minutes": 15,
    "use_llm": True,
}


def get_all() -> Dict[str, Any]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    out = dict(DEFAULTS)
    for r in rows:
        out[r["key"]] = jloads(r["value"], DEFAULTS.get(r["key"]))
    return out


def get(key: str) -> Any:
    return get_all().get(key, DEFAULTS.get(key))


def update(values: Dict[str, Any]) -> Dict[str, Any]:
    init_db()
    with get_conn() as conn:
        for key, value in values.items():
            if key not in DEFAULTS:
                raise KeyError(key)
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, jdumps(value)),
            )
    return get_all()


def get_fsrs() -> FSRS:
    s = get_all()
    params = s["fsrs_parameters"]
    if not isinstance(params, list) or len(params) != 21:
        params = list(DEFAULT_PARAMETERS)
    return FSRS(params, desired_retention=float(s["desired_retention"]))
