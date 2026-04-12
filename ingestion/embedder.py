"""Sentence-transformers embedder using all-MiniLM-L6-v2."""
from __future__ import annotations

from typing import List, Optional

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_BATCH = 64


class Embedder:
    """
    Thin wrapper around sentence-transformers that encodes text into
    384-dimensional float vectors.
    """

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        print(f"[Embedder] Loading model: {model_name} …")
        self._model = SentenceTransformer(model_name)
        print("[Embedder] Model ready.")

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()  # type: ignore[return-value]

    def embed(self, text: str) -> List[float]:
        """Embed a single string."""
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = _DEFAULT_BATCH,
        show_progress: bool = True,
    ) -> List[List[float]]:
        """
        Embed a list of strings. Returns parallel list of vectors.
        """
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
        )
        return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
