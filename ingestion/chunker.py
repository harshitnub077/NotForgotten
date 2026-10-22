"""Token-aware chunking that preserves page attribution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.extract import is_citation_block

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

CHUNK_TOKENS = 220
OVERLAP_TOKENS = 40
MIN_CHUNK_CHARS = 60


@dataclass
class Chunk:
    idx: int
    page: int
    text: str
    section: int = 0


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def chunk_pages(
    pages: Sequence[Tuple[int, str]],
    sections: Optional[Sequence[int]] = None,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap: int = OVERLAP_TOKENS,
) -> List[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_tokens,
        chunk_overlap=overlap,
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
    )
    chunks: List[Chunk] = []
    carry = ""
    carry_page = 0
    sections = list(sections) if sections is not None else list(range(len(pages)))
    for (page, text), section in zip(pages, sections):
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if is_citation_block(piece):
                continue
            if len(piece) < MIN_CHUNK_CHARS:
                # Tiny tails merge into the next chunk instead of becoming noise.
                carry, carry_page = (carry + " " + piece).strip(), page
                continue
            if carry:
                piece = f"{carry} {piece}"
                carry = ""
            chunks.append(Chunk(len(chunks), page, piece, section))
    if carry:
        if chunks:
            chunks[-1].text += " " + carry
        else:
            chunks.append(Chunk(0, carry_page, carry, 0))
    return chunks
