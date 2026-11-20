"""Bulk-import PDF chunks (with embeddings) into local ChromaDB."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import chromadb
from dotenv import load_dotenv

from ingestion.pdf_chunker import PDFChunker
from memory.schema import get_conn
import datetime
import os

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_NAME = "chunks"
DB_DIR = os.getenv("CHROMA_DB_DIR", "./data/chroma")
BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_chunks(
    chunks: list[dict[str, Any]],
    client: chromadb.ClientAPI,
) -> int:
    """
    Embed chunks and bulk-import them into ChromaDB.
    Returns the number of objects inserted.
    """
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    embedder = get_embedder()
    texts = [c["text"] for c in chunks]

    print(f"[ChromaDB] Embedding {len(texts)} chunks …")
    vectors = embedder.embed_batch(texts)

    ids = [f'{chunk["concept_tag"]}_p{chunk["page_num"]}_{i}' for i, chunk in enumerate(chunks)]
    metadatas = [
        {
            "concept_tag": chunk["concept_tag"],
            "source_file": chunk["source_file"],
            "page_num": chunk["page_num"],
        }
        for chunk in chunks
    ]

    print(f"[ChromaDB] Inserting into collection '{COLLECTION_NAME}'...")
    
    # Batch insertion
    for i in range(0, len(ids), BATCH_SIZE):
        collection.add(
            ids=ids[i:i + BATCH_SIZE],
            embeddings=vectors[i:i + BATCH_SIZE],
            metadatas=metadatas[i:i + BATCH_SIZE], # type: ignore
            documents=texts[i:i + BATCH_SIZE],
        )

    print(f"[ChromaDB] Imported {len(chunks)} chunks successfully.")
    return len(chunks)


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: str, original_filename: str = "unknown.pdf") -> tuple[int, list[str]]:
    """Full pipeline: PDF → chunks → embed → ChromaDB + Memory SQLite."""
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)

    try:
        chunker = PDFChunker()
        chunks = chunker.chunk_pdf(pdf_path)
        print(f"[PDFChunker] Extracted {len(chunks)} chunks from '{pdf_path}'.")
        
        # Override the source_file in chunks with the original filename instead of the temp path
        for chunk in chunks:
            chunk["source_file"] = original_filename

        count = import_chunks(chunks, client)
        
        # Extract unique concept tags
        concept_tags = list({c["concept_tag"] for c in chunks if c.get("concept_tag")})
        
        # Insert metadata into SQLite
        size_bytes = os.path.getsize(pdf_path)
        now_str = datetime.datetime.utcnow().isoformat()
        
        with get_conn() as conn:
            # 1. Register the source file
            conn.execute(
                """
                INSERT OR REPLACE INTO source_files (filename, upload_date, size_bytes, chunk_count, concept_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (original_filename, now_str, size_bytes, count, len(concept_tags))
            )
            
            # 2. Initialize memory rows for new concepts
            for tag in concept_tags:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO concept_memory (concept_id, source_file, easiness_factor, interval_days, repetitions, retention_prob)
                    VALUES (?, ?, 2.5, 1, 0, 1.0)
                    """,
                    (tag, original_filename)
                )

        return count, concept_tags
    finally:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into ChromaDB.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file.")
    args = parser.parse_args()
    n = ingest_pdf(args.pdf)
    print(f"\n✅  Done — {n} chunks imported.")


if __name__ == "__main__":
    _cli()
