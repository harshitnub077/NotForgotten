"""PDF → text chunks with metadata."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def _slugify(text: str) -> str:
    """Convert text to a safe concept-tag slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:64]


def _derive_concept_tag(source_file: str, start_page: int, end_page: int) -> str:
    """Auto-derive concept tag from filename + page range."""
    stem = _slugify(Path(source_file).stem)
    return f"{stem}_p{start_page + 1}-{end_page}"


# ---------------------------------------------------------------------------
# Main chunker
# ---------------------------------------------------------------------------

class PDFChunker:
    """
    Reads a PDF, extracts text, and splits into ~300-token chunks
    with 50-token overlap using LangChain's RecursiveCharacterTextSplitter.
    """

    def __init__(
        self,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=_token_len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_pdf(self, pdf_path: str) -> list[dict[str, Any]]:
        """
        Returns a list of chunk dicts:
        {
            "text": str,
            "concept_tag": str,
            "source_file": str,
            "page_num": int,          # start page (0-indexed)
        }
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        reader = PdfReader(str(path))
        page_texts: list[tuple[int, str]] = []

        for page_num, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            cleaned = self._clean(raw)
            if cleaned:
                page_texts.append((page_num, cleaned))

        if not page_texts:
            raise ValueError(f"No extractable text found in {pdf_path}")

        chunks: list[dict[str, Any]] = []
        source = path.name

        # Group pages into sliding windows before splitting so that
        # chunk-page attribution is meaningful.
        for page_num, page_text in page_texts:
            sub_chunks = self._splitter.split_text(page_text)
            tag = _derive_concept_tag(source, page_num, page_num + 1)
            for chunk_text in sub_chunks:
                if chunk_text.strip():
                    chunks.append(
                        {
                            "text": chunk_text.strip(),
                            "concept_tag": tag,
                            "source_file": source,
                            "page_num": page_num,
                        }
                    )

        return chunks

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """Basic cleanup: collapse excessive whitespace, remove null bytes."""
        text = text.replace("\x00", "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()


# ---------------------------------------------------------------------------
# CLI entry-point helper
# ---------------------------------------------------------------------------

def chunk_pdf(pdf_path: str, **kwargs) -> list[dict[str, Any]]:
    """Convenience wrapper."""
    return PDFChunker(**kwargs).chunk_pdf(pdf_path)
