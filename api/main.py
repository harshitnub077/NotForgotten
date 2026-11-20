"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.dashboard import router as dashboard_router
from api.routes.ingestion import router as ingestion_router
from api.routes.session import router as session_router
from api.routes.chat import router as chat_router
from api.routes.graph import router as graph_router
from api.routes.concepts import router as concepts_router
from memory.schema import init_db


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap DB and warm up embedder on startup."""
    print("[Startup] Initialising SQLite schema …")
    init_db()

    print("[Startup] Pre-loading embedding model …")
    from ingestion.embedder import get_embedder
    get_embedder()

    print("[Startup] Ready. 🧠")
    yield
    print("[Shutdown] NotForgotten shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="NotForgotten",
    description=(
        "AI-powered spaced repetition learning system. "
        "Combines semantic search with the Ebbinghaus forgetting curve "
        "to surface what you're about to forget, before you forget it."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for local dev (tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(session_router)
app.include_router(dashboard_router)
app.include_router(ingestion_router)
app.include_router(chat_router)
app.include_router(graph_router)
app.include_router(concepts_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "NotForgotten"}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "message": "NotForgotten API",
        "docs": "/docs",
        "endpoints": [
            "POST /session/start",
            "POST /session/query",
            "POST /session/rate",
            "POST /ingest",
            "GET  /dashboard",
            "POST /chat",
            "GET  /graph",
        ],
    }
