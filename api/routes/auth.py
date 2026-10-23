"""Accounts: sign up, log in, log out, profile, password, export, delete."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core import auth
from core.auth import AuthError, set_current_user
from core.util import iso, jloads, utcnow
from memory.schema import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE = "nf_session"


def _secure_cookies() -> bool:
    return os.getenv("COOKIE_SECURE", "0") == "1"


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 86_400,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        path="/",
    )


def _token(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE)
    if token:
        return token
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else None


async def require_user(request: Request) -> Dict[str, Any]:
    """Dependency for every data route. Async, so the context variable it sets
    is inherited by the (threadpool) endpoint that runs after it."""
    user = await run_in_threadpool(auth.user_for_token, _token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    set_current_user(user["id"])
    request.state.user = user
    return user


def _fail(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


class SignupIn(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)
    name: str = Field(default="", max_length=80)
    invite_code: str = Field(default="", max_length=64)


class LoginIn(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)


@router.get("/config")
def config() -> dict:
    return {"invite_required": bool(auth.invite_codes())}


@router.post("/signup")
def signup(body: SignupIn, request: Request, response: Response) -> dict:
    try:
        user = auth.signup(body.email, body.password, body.name, body.invite_code)
    except AuthError as exc:
        raise _fail(exc) from exc
    _set_cookie(response, auth.create_session(user["id"], request.headers.get("user-agent", "")))
    return {"user": user}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    ip = request.client.host if request.client else ""
    try:
        user = auth.login(body.email, body.password, ip)
    except AuthError as exc:
        raise _fail(exc) from exc
    _set_cookie(response, auth.create_session(user["id"], request.headers.get("user-agent", "")))
    return {"user": user}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    auth.end_session(_token(request))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: Dict[str, Any] = Depends(require_user)) -> dict:
    return {"user": user}


class ProfileIn(BaseModel):
    name: str = Field(..., max_length=80)


@router.patch("/me")
def update_profile(body: ProfileIn, user: Dict[str, Any] = Depends(require_user)) -> dict:
    with get_conn() as conn:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (body.name.strip(), user["id"]))
    return {"user": {**user, "name": body.name.strip()}}


class PasswordIn(BaseModel):
    current_password: str = Field(..., max_length=256)
    new_password: str = Field(..., max_length=256)


@router.post("/password")
def change_password(
    body: PasswordIn, request: Request, response: Response, user: Dict[str, Any] = Depends(require_user)
) -> dict:
    try:
        auth.change_password(user["id"], body.current_password, body.new_password)
    except AuthError as exc:
        raise _fail(exc) from exc
    # All sessions were revoked; keep this browser signed in with a fresh one.
    _set_cookie(response, auth.create_session(user["id"], request.headers.get("user-agent", "")))
    return {"ok": True}


class DeleteIn(BaseModel):
    password: str = Field(..., max_length=256)


@router.post("/delete")
def delete_account(body: DeleteIn, response: Response, user: Dict[str, Any] = Depends(require_user)) -> dict:
    try:
        auth.delete_account(user["id"], body.password)
    except AuthError as exc:
        raise _fail(exc) from exc
    from retrieval.vector_store import get_store

    get_store().invalidate(user["id"])
    response.delete_cookie(COOKIE, path="/")
    return {"deleted": True}


@router.get("/export")
def export(user: Dict[str, Any] = Depends(require_user)) -> dict:
    """Everything stored about this user, as JSON (data portability)."""
    out: Dict[str, Any] = {"exported_at": iso(utcnow()), "user": user}
    tables = {
        "documents": "SELECT id, title, filename, kind, source_url, status, created_at FROM documents",
        "concepts": "SELECT id, document_id, name, summary, keywords, created_at FROM concepts",
        "cards": "SELECT id, concept_id, kind, prompt, answer, explanation, stability, difficulty, due, "
        "last_review, reps, lapses, suspended, created_at FROM cards",
        "reviews": "SELECT card_id, rating, score, confidence, response, elapsed_days, duration_ms, reviewed_at FROM reviews",
        "exams": "SELECT id, name, exam_date, target, document_ids, created_at FROM exams",
        "settings": "SELECT key, value FROM user_settings",
    }
    with get_conn() as conn:
        for name, sql in tables.items():
            rows = conn.execute(f"{sql} WHERE user_id = ?", (user["id"],)).fetchall()
            out[name] = [dict(r) for r in rows]
    for c in out["concepts"]:
        c["keywords"] = jloads(c["keywords"], [])
    for s in out["settings"]:
        s["value"] = jloads(s["value"], s["value"])
    return out
