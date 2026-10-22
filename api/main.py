"""FastAPI application entry point."""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import cards, concepts, documents, exams, insights, review, system, tutor
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
    version="2.0.0",
    lifespan=lifespan,
)

_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (system, documents, concepts, cards, review, insights, tutor, exams):
    app.include_router(module.router, prefix="/api")

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
