"""FastAPI application entry point."""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import auth, cards, concepts, documents, exams, insights, review, system, tutor
from api.routes.auth import require_user
from memory.schema import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    def warm() -> None:
        from ingestion.embedder import get_embedder

        get_embedder()

    # Load the embedding model in the background so the API answers immediately.
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(
    title="NotForgotten",
    description=(
        "Memory-aware learning engine: FSRS-6 scheduling, concept knowledge graphs, "
        "typed-recall grading and an AI tutor that knows what you're forgetting."
    ),
    version="2.1.0",
    lifespan=lifespan,
)

_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class OriginGuard:
    """
    Reject cross-site state-changing requests (CSRF defence in depth on top of
    SameSite=Lax cookies): a POST/PATCH/DELETE whose Origin header names a
    site other than this one or an allowed CORS origin is refused.
    """

    SAFE = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, app, allowed):
        self.app = app
        self.allowed = set(allowed)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] not in self.SAFE:
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            origin = headers.get("origin")
            host = headers.get("host", "")
            if origin and origin not in self.allowed and origin.split("://", 1)[-1] != host:
                body = b'{"detail":"Cross-site request blocked."}'
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


app.add_middleware(OriginGuard, allowed=_origins)

app.include_router(system.public, prefix="/api")
app.include_router(auth.router, prefix="/api")
for module in (system, documents, concepts, cards, review, insights, tutor, exams):
    app.include_router(module.router, prefix="/api", dependencies=[Depends(require_user)])

# Serve the built frontend (npm run build) from the same origin in production.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = _DIST / path
        if path and target.is_file() and _DIST in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")
