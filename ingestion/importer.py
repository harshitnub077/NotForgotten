"""Bulk-import PDF chunks (with embeddings) into local ChromaDB."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import chromadb
from dotenv import load_dotenv

from ingestion.embedder import get_embedder
from ingestion.pdf_chunker import PDFChunker

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

def ingest_pdf(pdf_path: str) -> int:
    """Full pipeline: PDF → chunks → embed → ChromaDB."""
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)

    try:
        chunker = PDFChunker()
        chunks = chunker.chunk_pdf(pdf_path)
        print(f"[PDFChunker] Extracted {len(chunks)} chunks from '{pdf_path}'.")
        count = import_chunks(chunks, client)
        return count
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
