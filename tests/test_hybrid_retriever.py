"""
Unit tests for HybridRetriever score blending.

Weaviate is mocked so these tests run without Docker.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk, _RawChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_raw(concept_tag: str, semantic_score: float) -> _RawChunk:
    return _RawChunk(
        text=f"Text for {concept_tag}",
        concept_tag=concept_tag,
        source_file="test.pdf",
        page_num=0,
        semantic_score=semantic_score,
        chroma_id="mock-uuid",
    )


# ---------------------------------------------------------------------------
# Score blending
# ---------------------------------------------------------------------------


class TestScoreBlending:
    """Validate the α·semantic + (1-α)·urgency formula."""

    def _retriever_with_mocks(
        self,
        alpha: float,
        raw_chunks: list[_RawChunk],
        urgency_map: dict[str, float],
    ) -> list[RetrievedChunk]:
        retriever = HybridRetriever(alpha=alpha, top_k=10)

        with (
            patch.object(retriever, "_semantic_search", return_value=raw_chunks),
            patch.object(retriever, "_get_client", return_value=MagicMock()),
            patch("retrieval.hybrid_retriever.ForgettingScorer") as MockScorer,
            patch("retrieval.hybrid_retriever.get_embedder") as MockEmb,
        ):
            MockScorer.return_value.score_all.return_value = urgency_map
            MockEmb.return_value.embed.return_value = [0.0] * 384

            results = retriever.retrieve("test query")

        return results

    def test_alpha_1_pure_semantic(self):
        """With alpha=1.0 urgency has no effect — rank by semantic only."""
        chunks = [
            _make_raw("concept_a", semantic_score=0.9),
            _make_raw("concept_b", semantic_score=0.5),
        ]
        urgency = {"concept_a": 0.0, "concept_b": 1.0}

        results = self._retriever_with_mocks(alpha=1.0, raw_chunks=chunks, urgency_map=urgency)

        assert results[0].concept_tag == "concept_a"
        assert results[1].concept_tag == "concept_b"

    def test_alpha_0_pure_urgency(self):
        """With alpha=0.0 semantic is ignored — rank by urgency only."""
        chunks = [
            _make_raw("forgotten_concept", semantic_score=0.1),
            _make_raw("fresh_concept", semantic_score=0.9),
        ]
        urgency = {"forgotten_concept": 0.95, "fresh_concept": 0.05}

        results = self._retriever_with_mocks(alpha=0.0, raw_chunks=chunks, urgency_map=urgency)

        assert results[0].concept_tag == "forgotten_concept"
        assert results[1].concept_tag == "fresh_concept"

    def test_hybrid_blending(self):
        """α=0.6: forgotten concept with moderate semantic boost should beat fresh concept."""
        chunks = [
            _make_raw("forgotten", semantic_score=0.6),
            _make_raw("remembered", semantic_score=0.9),
        ]
        urgency = {"forgotten": 1.0, "remembered": 0.0}

        results = self._retriever_with_mocks(alpha=0.6, raw_chunks=chunks, urgency_map=urgency)

        # forgotten: 0.6*0.6 + 0.4*1.0 = 0.36 + 0.40 = 0.76
        # remembered: 0.6*0.9 + 0.4*0.0 = 0.54
        assert results[0].concept_tag == "forgotten"

    def test_final_score_formula_correct(self):
        alpha = 0.6
        sem = 0.8
        urg = 0.7
        expected = alpha * sem + (1 - alpha) * urg

        chunks = [_make_raw("c1", semantic_score=sem)]
        urgency = {"c1": urg}

        results = self._retriever_with_mocks(alpha=alpha, raw_chunks=chunks, urgency_map=urgency)

        assert results[0].final_score == pytest.approx(expected, rel=1e-4)

    def test_missing_urgency_defaults_zero(self):
        """If concept has no urgency record, default to 0."""
        chunks = [_make_raw("unknown_concept", semantic_score=0.7)]
        urgency: dict[str, float] = {}  # no record

        results = self._retriever_with_mocks(alpha=0.6, raw_chunks=chunks, urgency_map=urgency)

        assert results[0].urgency_score == 0.0
        assert results[0].final_score == pytest.approx(0.6 * 0.7)


# ---------------------------------------------------------------------------
# Top-k limiting
# ---------------------------------------------------------------------------


class TestTopK:
    def test_top_k_limits_results(self):
        chunks = [_make_raw(f"concept_{i}", semantic_score=float(i) / 10) for i in range(20)]
        urgency = {f"concept_{i}": 0.5 for i in range(20)}

        retriever = HybridRetriever(alpha=0.6, top_k=5)
        with (
            patch.object(retriever, "_semantic_search", return_value=chunks),
            patch.object(retriever, "_get_client", return_value=MagicMock()),
            patch("retrieval.hybrid_retriever.ForgettingScorer") as MockScorer,
            patch("retrieval.hybrid_retriever.get_embedder") as MockEmb,
        ):
            MockScorer.return_value.score_all.return_value = urgency
            MockEmb.return_value.embed.return_value = [0.0] * 384
            results = retriever.retrieve("test")

        assert len(results) == 5

    def test_empty_weaviate_returns_empty(self):
        retriever = HybridRetriever(alpha=0.6, top_k=5)
        with (
            patch.object(retriever, "_semantic_search", return_value=[]),
            patch.object(retriever, "_get_client", return_value=MagicMock()),
            patch("retrieval.hybrid_retriever.ForgettingScorer") as MockScorer,
            patch("retrieval.hybrid_retriever.get_embedder") as MockEmb,
        ):
            MockScorer.return_value.score_all.return_value = {}
            MockEmb.return_value.embed.return_value = [0.0] * 384
            results = retriever.retrieve("test")

        assert results == []
