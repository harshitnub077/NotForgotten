"""Sentence-transformers embedder (all-MiniLM-L6-v2, 384-d, unit-normalised)."""
from __future__ import annotations

import threading
from typing import List, Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()  # HF_HOME / SENTENCE_TRANSFORMERS_HOME must be set before import

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_BATCH = 64


class Embedder:
    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        from sentence_transformers import SentenceTransformer

        print(f"[Embedder] Loading model: {model_name} …")
        self._model = SentenceTransformer(model_name)
        self._lock = threading.Lock()
        print("[Embedder] Model ready.")

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()  # type: ignore[return-value]

    def embed(self, text: str) -> List[float]:
        return self.embed_many([text])[0].tolist()

    def embed_many(self, texts: List[str], batch_size: int = _DEFAULT_BATCH) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        with self._lock:
            return self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

    def embed_batch(self, texts: List[str], batch_size: int = _DEFAULT_BATCH) -> List[List[float]]:
        return [v.tolist() for v in self.embed_many(texts, batch_size)]


_embedder: Optional[Embedder] = None
_init_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder()
    return _embedder


def embed_texts(texts: List[str]) -> np.ndarray:
    return get_embedder().embed_many(list(texts))
