"""
Accounts and sessions.

Passwords: scrypt (stdlib, memory-hard), per-user random salt, constant-time
comparison. Sessions: a random 256-bit token is sent to the browser in an
HttpOnly cookie; only its SHA-256 is stored, so a leaked database can't be
replayed as live sessions. The signed-in user travels through a request in a
context variable, so data-access code scopes every query with `uid()`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from contextvars import ContextVar
from datetime import timedelta
from typing import Any, Dict, Optional

from core.util import iso, new_id, parse_dt, utcnow
from memory.schema import USER_TABLES, get_conn, init_db

SESSION_DAYS = 30
MIN_PASSWORD = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

_current_user: ContextVar[Optional[str]] = ContextVar("current_user", default=None)


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------


def set_current_user(user_id: Optional[str]) -> Any:
    return _current_user.set(user_id)


def reset_current_user(token: Any) -> None:
    _current_user.reset(token)


def uid() -> str:
    """The signed-in user's id; data access without one is a programming error."""
    user_id = _current_user.get()
    if not user_id:
        raise RuntimeError("No signed-in user in this context")
    return user_id


def bump_library_version(user_id: Optional[str] = None) -> None:
    """Invalidate per-user caches (vector index) after the library changes."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET library_version = library_version + 1 WHERE id = ?", (user_id or uid(),))


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt${n}${r}${p}${salt}${hash}".format(
        n=_SCRYPT["n"],
        r=_SCRYPT["r"],
        p=_SCRYPT["p"],
        salt=base64.b64encode(salt).decode(),
        hash=base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        candidate = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Rate limiting (per email + per IP, in-process; enough for a beta)
# ---------------------------------------------------------------------------

_attempts: Dict[str, list] = {}
_attempt_lock = threading.Lock()
WINDOW_S = 15 * 60
MAX_ATTEMPTS = 8


def _check_rate(key: str) -> None:
    now = time.time()
    with _attempt_lock:
        hits = [t for t in _attempts.get(key, []) if now - t < WINDOW_S]
        _attempts[key] = hits
        if len(hits) >= MAX_ATTEMPTS:
            raise AuthError("Too many attempts. Try again in a few minutes.", 429)


def _record_failure(key: str) -> None:
    with _attempt_lock:
        _attempts.setdefault(key, []).append(time.time())


def clear_rate_limits() -> None:
    with _attempt_lock:
        _attempts.clear()


# ---------------------------------------------------------------------------
# Users & sessions
# ---------------------------------------------------------------------------


def invite_codes() -> set:
    raw = os.getenv("BETA_INVITE_CODES", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


def public_user(row: Any) -> Dict[str, Any]:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "created_at": row["created_at"]}


def signup(email: str, password: str, name: str = "", invite_code: str = "") -> Dict[str, Any]:
    init_db()
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise AuthError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for your password.")
    codes = invite_codes()
    if codes and invite_code.strip() not in codes:
        raise AuthError("That invite code isn't valid.", 403)

    user_id = new_id("usr")
    now = iso(utcnow())
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise AuthError("An account with this email already exists. Log in instead.", 409)
        first_user = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0
        conn.execute(
            "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, name.strip()[:80], hash_password(password), now),
        )
        if first_user:
            _claim_unowned(conn, user_id)
    return {"id": user_id, "email": email, "name": name.strip()[:80], "created_at": now}


def _claim_unowned(conn: Any, user_id: str) -> None:
    """The first account inherits a library created before accounts existed."""
    for table in USER_TABLES:
        conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (user_id,))
    legacy = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    ).fetchone() if not _is_pg() else None
    if legacy:
        for row in conn.execute("SELECT key, value FROM settings").fetchall():
            conn.execute(
                "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) ON CONFLICT (user_id, key) DO NOTHING",
                (user_id, row["key"], row["value"]),
            )


def _is_pg() -> bool:
    from memory.schema import is_postgres

    return is_postgres()


def login(email: str, password: str, ip: str = "") -> Dict[str, Any]:
    init_db()
    email = email.strip().lower()
    for key in (f"email:{email}", f"ip:{ip}"):
        _check_rate(key)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        _record_failure(f"email:{email}")
        _record_failure(f"ip:{ip}")
        raise AuthError("Email or password is incorrect.", 401)
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (iso(utcnow()), row["id"]))
    return public_user(row)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str, user_agent: str = "") -> str:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, user_agent) VALUES (?, ?, ?, ?, ?)",
            (_token_hash(token), user_id, iso(now), iso(now + timedelta(days=SESSION_DAYS)), user_agent[:200]),
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(now),))
    return token


def user_for_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ?""",
            (_token_hash(token),),
        ).fetchone()
    if row is None:
        return None
    expires = parse_dt(row["expires_at"])
    if expires is None or expires < utcnow():
        return None
    return public_user(row)


def end_session(token: Optional[str]) -> None:
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def change_password(user_id: str, current: str, new: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not verify_password(current, row["password_hash"]):
        raise AuthError("Your current password is incorrect.", 401)
    if len(new) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for your password.")
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def delete_account(user_id: str, password: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise AuthError("Password is incorrect.", 401)
    with get_conn() as conn:
        # Explicit deletes in child-to-parent order keep this correct even on
        # databases migrated from before foreign keys carried user ownership.
        for table in ("reviews", "feynman_attempts", "concept_links", "cards", "chunks", "concepts",
                      "jobs", "exams", "documents", "user_settings", "sessions"):
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
