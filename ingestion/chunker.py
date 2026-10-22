"""Token-aware chunking that preserves page attribution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

CHUNK_TOKENS = 220
OVERLAP_TOKENS = 40
MIN_CHUNK_CHARS = 60


@dataclass
class Chunk:
    idx: int
    page: int
    text: str


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def chunk_pages(
    pages: Sequence[Tuple[int, str]],
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
    for page, text in pages:
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if len(piece) < MIN_CHUNK_CHARS:
                # Tiny tails merge into the next chunk instead of becoming noise.
                carry, carry_page = (carry + " " + piece).strip(), page
                continue
            if carry:
                piece = f"{carry} {piece}"
                carry = ""
            chunks.append(Chunk(len(chunks), page, piece))
    if carry:
        if chunks:
            chunks[-1].text += " " + carry
        else:
            chunks.append(Chunk(0, carry_page, carry))
    return chunks
