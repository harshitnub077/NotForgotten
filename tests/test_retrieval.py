"""Tests for memory-aware reranking and forgetting propagation."""
from __future__ import annotations

import pytest

from knowledge_graph.propagation import effective_retention, weakest_foundations
from retrieval.hybrid import UNSTUDIED_URGENCY, rerank
from retrieval.vector_store import VectorHit


def _hit(cid: str, concept: str, sim: float) -> VectorHit:
    return VectorHit(cid, "doc", concept, 0, f"text {cid}", sim)


class TestRerank:
    def test_alpha_one_is_pure_semantic(self):
        hits = [_hit("a", "c1", 0.9), _hit("b", "c2", 0.5)]
        ranked = rerank(hits, {"c1": 0.99, "c2": 0.1}, alpha=1.0)
        assert [r.chunk_id for r in ranked] == ["a", "b"]

    def test_forgotten_concept_boosted(self):
        hits = [_hit("a", "c1", 0.70), _hit("b", "c2", 0.65)]
        ranked = rerank(hits, {"c1": 0.98, "c2": 0.30}, alpha=0.75)
        assert ranked[0].chunk_id == "b"

    def test_formula(self):
        ranked = rerank([_hit("a", "c1", 0.8)], {"c1": 0.6}, alpha=0.7)
        assert ranked[0].score == pytest.approx(0.7 * 0.8 + 0.3 * 0.4)

    def test_unstudied_neutral(self):
        ranked = rerank([_hit("a", "new", 0.8)], {}, alpha=0.5)
        assert ranked[0].urgency == UNSTUDIED_URGENCY

    def test_top_k(self):
        hits = [_hit(str(i), "c", i / 10) for i in range(10)]
        assert len(rerank(hits, {}, top_k=3)) == 3


class TestPropagation:
    EDGES = [("a", "b", 1.0, "prerequisite"), ("b", "c", 1.0, "prerequisite"), ("a", "x", 0.9, "related")]

    def test_strong_foundation_no_penalty(self):
        eff = effective_retention({"a": 1.0, "b": 0.9, "c": 0.9, "x": 0.9}, self.EDGES)
        assert eff["b"] == pytest.approx(0.9)
        assert eff["x"] == pytest.approx(0.9)  # related edges don't propagate

    def test_weak_foundation_compounds(self):
        eff = effective_retention({"a": 0.3, "b": 0.9, "c": 0.9, "x": 0.9}, self.EDGES)
        assert eff["b"] < 0.9
        assert eff["c"] < 0.9
        assert eff["a"] == pytest.approx(0.3)

    def test_unlearned_not_penalised(self):
        eff = effective_retention({"a": None, "b": 0.8, "c": 0.8, "x": None}, self.EDGES)
        assert eff["a"] is None and eff["b"] == pytest.approx(0.8)

    def test_cycle_falls_back(self):
        edges = [("a", "b", 1.0, "prerequisite"), ("b", "a", 1.0, "prerequisite")]
        assert effective_retention({"a": 0.5, "b": 0.5}, edges) == {"a": 0.5, "b": 0.5}

    def test_weakest_foundations(self):
        eff = {"a": 0.2, "b": 0.7, "c": 0.9}
        assert weakest_foundations("c", eff, self.EDGES) == ["a", "b"]
