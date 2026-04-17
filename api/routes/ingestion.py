"""Routes for PDF ingestion."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ingestion.importer import ingest_pdf

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestResponse(BaseModel):
    filename: str
    chunks_imported: int
    concepts_detected: int
    concept_tags: list[str]
    message: str


@router.post("", response_model=IngestResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file, chunk it, and store in the vector database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Create a temporary file to store the upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        try:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        finally:
            file.file.close()

    try:
        # Run the ingestion pipeline
        count, tags = ingest_pdf(tmp_path, original_filename=file.filename)
        
        return IngestResponse(
            filename=file.filename,
            chunks_imported=count,
            concepts_detected=len(tags),
            concept_tags=tags,
            message=f"Successfully ingested '{file.filename}' into vector memory."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/sources")
def get_sources():
    """Return history of uploaded PDF files."""
    from memory.schema import get_conn
    with get_conn() as conn:
        rows = conn.execute("SELECT filename, upload_date, size_bytes, chunk_count, concept_count FROM source_files ORDER BY upload_date DESC").fetchall()
    return [
        {
            "filename": r[0],
            "upload_date": r[1],
            "size_bytes": r[2],
            "chunk_count": r[3],
            "concept_count": r[4]
        }
        for r in rows
    ]
