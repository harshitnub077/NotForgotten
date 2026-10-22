"""Tests for text utilities, concept discovery, card generation and grading."""
from __future__ import annotations

import numpy as np
import pytest

from llm.client import parse_json
from nlp.cards import CLOZE_BLANK, generate_cards, generate_heuristic
from nlp.concepts import ConceptNode, build_edges, cluster_chunks, discover_concepts
from nlp.grader import feynman_heuristic, grade, grade_heuristic, score_to_rating
from nlp.text import clean_text, keyphrases, sentences

PHOTO = (
    "Photosynthesis is the process by which green plants convert light energy into chemical "
    "energy stored in glucose. Chlorophyll absorbs mostly blue and red light in the chloroplast. "
    "The light-dependent reactions occur in the thylakoid membranes and produce ATP and NADPH."
)
MITO = (
    "Mitochondria are organelles that produce ATP through cellular respiration. The Krebs cycle "
    "takes place in the mitochondrial matrix and releases carbon dioxide. Oxidative "
    "phosphorylation uses the electron transport chain to pump protons across the inner membrane."
)


class TestText:
    def test_clean_dehyphenates(self):
        assert clean_text("photo-\nsynthesis  is   neat") == "photosynthesis is neat"

    def test_sentences(self):
        assert len(sentences(PHOTO)) == 3

    def test_keyphrases_are_distinctive(self):
        kp = keyphrases([PHOTO, MITO])
        assert any("chloro" in p or "photo" in p or "light" in p for p in kp[0])
        assert any("mitochondri" in p or "krebs" in p or "atp" in p for p in kp[1])


def _blobs(n_per=8, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    centers = np.eye(dim)[:3] * 3
    pts = np.vstack([c + rng.normal(0, 0.2, size=(n_per, dim)) for c in centers])
    return pts / np.linalg.norm(pts, axis=1, keepdims=True)


class TestConcepts:
    def test_reading_order_labels(self):
        assert cluster_chunks(_blobs())[0] == 0

    def test_sections_pull_passages_together(self):
        labels = cluster_chunks(_blobs(), sections=[i // 8 for i in range(24)])
        for topic in range(3):
            block = set(labels[topic * 8 : (topic + 1) * 8])
            rest = set(labels[: topic * 8] + labels[(topic + 1) * 8 :])
            assert block.isdisjoint(rest)

    def test_headed_sections_become_concepts(self):
        from nlp.concepts import section_labels

        sections = [0, 0, 1, 2, 2, 2] + [3] * 9
        rng = np.random.default_rng(1)
        emb = rng.normal(size=(15, 8))
        labels = section_labels(emb, sections)
        assert labels[:6] == [0, 0, 1, 2, 2, 2]
        assert len(set(labels[6:])) >= 2  # the oversized section was split

    def test_granularity_prior(self):
        labels = cluster_chunks(_blobs())
        assert 3 <= len(set(labels)) <= 16

    def test_tiny_input_single_concept(self):
        assert cluster_chunks(np.ones((2, 4))) == [0, 0]

    def test_discover_names_and_summaries(self):
        texts = [PHOTO] * 8 + [MITO] * 8 + [PHOTO + " " + MITO] * 8
        drafts = discover_concepts(texts, _blobs(), sections=[i // 8 for i in range(24)])
        assert len(drafts) >= 3
        assert all(d.name and d.summary for d in drafts)
        assert len({d.name for d in drafts}) == len(drafts)

    def test_edges_direction_and_kinds(self):
        a = np.array([1.0, 0.1, 0])
        nodes = [
            ConceptNode("late", "doc1", 10.0, a),
            ConceptNode("early", "doc1", 1.0, a + 0.05),
            ConceptNode("other", "doc2", 3.0, a),
        ]
        edges = build_edges(nodes)
        prereq = [e for e in edges if e[3] == "prerequisite"]
        assert ("early", "late") in [(e[0], e[1]) for e in prereq]
        assert any(e[3] == "related" for e in edges)


class TestCards:
    def test_heuristic_definition_and_cloze(self):
        cards = generate_heuristic(["chlorophyll", "thylakoid membranes", "photosynthesis"], [PHOTO], 4)
        kinds = {c.kind for c in cards}
        assert "qa" in kinds and "cloze" in kinds
        for c in cards:
            if c.kind == "cloze":
                assert CLOZE_BLANK in c.prompt
                assert c.answer.lower() not in c.prompt.lower()

    def test_generate_cards_offline(self, monkeypatch):
        monkeypatch.setenv("NOTFORGOTTEN_OFFLINE", "1")
        cards = generate_cards("Photosynthesis", "summary", ["chlorophyll"], [PHOTO])
        assert cards

    def test_fallback_explain_card(self, monkeypatch):
        monkeypatch.setenv("NOTFORGOTTEN_OFFLINE", "1")
        cards = generate_cards("Zen", "Zen is about presence.", [], ["short."])
        assert cards[0].kind == "explain"


class TestGrader:
    @pytest.mark.parametrize("score,rating", [(0.1, 1), (0.5, 2), (0.7, 3), (0.95, 4)])
    def test_score_to_rating(self, score, rating):
        assert score_to_rating(score) == rating

    def test_blank_and_idk(self):
        assert grade_heuristic("qa", "ATP", "").rating == 1
        assert grade_heuristic("qa", "ATP and NADPH", "I don't know").rating == 1

    def test_cloze_fuzzy(self):
        assert grade_heuristic("cloze", "chlorophyll", "Chlorophyll").rating == 4
        assert grade_heuristic("cloze", "chlorophyll", "chlorophyl").rating >= 3
        assert grade_heuristic("cloze", "chlorophyll", "mitochondria").rating == 1

    def test_lexical_partial_credit(self):
        ref = "They produce ATP through cellular respiration in the matrix"
        full = grade_heuristic("qa", ref, "Mitochondria produce ATP by cellular respiration in the matrix")
        part = grade_heuristic("qa", ref, "they make energy")
        assert full.score > part.score
        assert part.missing

    def test_grade_offline_uses_heuristic(self, monkeypatch):
        monkeypatch.setenv("NOTFORGOTTEN_OFFLINE", "1")
        assert grade("qa", "q", "light energy to chemical energy", "light energy into chemical energy").method == "heuristic"

    def test_feynman(self):
        good = feynman_heuristic(
            ["chlorophyll", "light energy", "glucose"],
            PHOTO,
            "Plants use chlorophyll to capture light energy. They turn it into chemical energy and "
            "store it as glucose, which the plant can later burn for fuel when it needs it.",
        )
        bad = feynman_heuristic(["chlorophyll", "light energy", "glucose"], PHOTO, "Plants are green.")
        assert good.score > bad.score
        assert "glucose" in good.covered
        assert bad.missing


class TestJSON:
    def test_parse_fenced(self):
        assert parse_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]

    def test_parse_with_chatter(self):
        assert parse_json('Sure! {"score": 0.5} hope it helps') == {"score": 0.5}

    def test_parse_failure(self):
        with pytest.raises(ValueError):
            parse_json("nothing here")
