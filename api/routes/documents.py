"""Library: documents, ingestion jobs and semantic search."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.auth import uid
from ingestion import pipeline
from memory.schema import get_conn, init_db

router = APIRouter(tags=["documents"])

MAX_UPLOAD_BYTES = 60 * 1024 * 1024
TEXT_EXTS = {".txt": "text", ".md": "markdown", ".markdown": "markdown"}


@router.get("/documents")
def list_documents() -> List[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT d.*,
                      (SELECT COUNT(*) FROM reviews r JOIN cards c ON c.id = r.card_id
                        WHERE c.document_id = d.id) AS review_count
               FROM documents d WHERE d.user_id = ? ORDER BY d.created_at DESC""",
            (uid(),),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/documents/{doc_id}")
def get_document(doc_id: str) -> dict:
    from core.analytics import concept_list

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, uid())).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = dict(row)
    doc["concepts"] = [c for c in concept_list() if c["document_id"] == doc_id]
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict:
    if not pipeline.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}


@router.post("/documents/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    name = file.filename or "upload"
    ext = os.path.splitext(name)[1].lower()
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            path = tmp.name
        if os.path.getsize(path) > MAX_UPLOAD_BYTES:
            os.remove(path)
            raise HTTPException(status_code=413, detail="File is larger than 60 MB.")
        return pipeline.submit({"kind": "pdf", "path": path, "filename": name, "cleanup": True})
    if ext in TEXT_EXTS:
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File is larger than 60 MB.")
        text = raw.decode("utf-8", errors="replace")
        return pipeline.submit(
            {"kind": TEXT_EXTS[ext], "text": text, "title": os.path.splitext(name)[0], "filename": name}
        )
    raise HTTPException(status_code=400, detail="Supported formats: PDF, TXT, Markdown.")


class TextIn(BaseModel):
    title: str = Field(default="My notes", max_length=200)
    text: str = Field(..., min_length=40, max_length=2_000_000)


@router.post("/documents/text")
def add_text(body: TextIn) -> dict:
    return pipeline.submit({"kind": "markdown", "text": body.text, "title": body.title})


class UrlIn(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)


@router.post("/documents/url")
def add_url(body: UrlIn) -> dict:
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    return pipeline.submit({"kind": "url", "url": body.url, "title": body.url})


@router.get("/jobs")
def active_jobs() -> List[dict]:
    return pipeline.list_active_jobs()


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict:
    j = pipeline.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return j


@router.get("/search")
def search(q: str, k: int = 8, document_id: Optional[str] = None) -> List[dict]:
    from retrieval.hybrid import retrieve

    if not q.strip():
        return []
    ranked = retrieve(q, top_k=min(max(k, 1), 25), document_ids=[document_id] if document_id else None)
    names = {}
    with get_conn() as conn:
        for r in conn.execute(
            "SELECT c.id, c.name, d.title FROM concepts c JOIN documents d ON d.id = c.document_id WHERE c.user_id = ?",
            (uid(),),
        ).fetchall():
            names[r["id"]] = (r["name"], r["title"])
    return [
        {
            **c.to_dict(),
            "concept_name": names.get(c.concept_id, ("", ""))[0],
            "document_title": names.get(c.concept_id, ("", ""))[1],
        }
        for c in ranked
    ]
