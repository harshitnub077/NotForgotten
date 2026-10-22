"""
Answer grading — turns a typed answer into an FSRS rating suggestion.

Typing (generating) an answer instead of flipping a card is what makes
retrieval practice work; the grader removes the honesty problem of
self-rating. Score ∈ [0, 1] maps to ratings:

    < 0.40 Again   < 0.62 Hard   < 0.86 Good   otherwise Easy

LLM grading uses a rubric (accuracy, completeness, key points missed).
Offline grading blends semantic similarity of sentence embeddings with
lexical recall of the reference's content words:

    score = 0.55 · clip((cos − 0.25) / 0.55) + 0.45 · recall
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

import numpy as np

from nlp.text import content_tokens

EmbedFn = Callable[[List[str]], np.ndarray]

_IDK = re.compile(r"^\s*(i\s*(don'?t|do not)\s*know|idk|no idea|not sure|\?+|pass|skip)\s*\.?\s*$", re.I)


@dataclass
class GradeResult:
    score: float
    rating: int
    verdict: str                     # correct | partial | incorrect
    feedback: str
    missing: List[str] = field(default_factory=list)
    method: str = "heuristic"


def score_to_rating(score: float) -> int:
    if score < 0.40:
        return 1
    if score < 0.62:
        return 2
    if score < 0.86:
        return 3
    return 4


def _verdict(score: float) -> str:
    return "correct" if score >= 0.62 else "partial" if score >= 0.40 else "incorrect"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _stem(t: str) -> str:
    return t[:5] if len(t) > 5 else t


def lexical_recall(reference: str, response: str) -> tuple:
    ref = list(dict.fromkeys(content_tokens(reference)))
    if not ref:
        return 1.0, []
    got = {_stem(t) for t in content_tokens(response)}
    missing = [t for t in ref if _stem(t) not in got]
    return 1.0 - len(missing) / len(ref), missing


def grade_heuristic(
    kind: str,
    reference: str,
    response: str,
    embed: Optional[EmbedFn] = None,
) -> GradeResult:
    if not response.strip() or _IDK.match(response):
        return GradeResult(0.0, 1, "incorrect", "No answer given — here is the answer to study.", [])

    if kind == "cloze" or len(reference.split()) <= 3:
        ratio = difflib.SequenceMatcher(None, _norm(reference), _norm(response)).ratio()
        contained = _norm(reference) in _norm(response) and len(_norm(response)) <= len(_norm(reference)) * 3
        score = 1.0 if contained else ratio
        if score >= 0.86:
            fb = "Exactly right."
        elif score >= 0.62:
            fb = "Close — check the exact wording."
        else:
            fb = "Not quite."
        return GradeResult(round(score, 3), score_to_rating(score), _verdict(score), fb, [])

    recall, missing = lexical_recall(reference, response)
    semantic = recall
    if embed is not None:
        vecs = embed([reference, response])
        cos = float(np.dot(vecs[0], vecs[1]) / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[1]) + 1e-9))
        semantic = min(max((cos - 0.25) / 0.55, 0.0), 1.0)
    score = 0.55 * semantic + 0.45 * recall
    if score >= 0.86:
        fb = "Excellent — you captured the key idea."
    elif score >= 0.62:
        fb = "Good recall. Compare with the reference for any nuance you skipped."
    elif score >= 0.40:
        fb = "Partially there — some key ideas are missing."
    else:
        fb = "This doesn't match the reference yet."
    return GradeResult(round(score, 3), score_to_rating(score), _verdict(score), fb, missing[:6])


_GRADER_SYSTEM = (
    "You are a fair, encouraging examiner grading a student's recall from memory. Judge "
    "meaning, not wording. Accept synonyms and paraphrase. Penalise factual errors."
)


def grade_with_llm(prompt: str, reference: str, response: str) -> Optional[GradeResult]:
    from llm.client import LLMUnavailable, get_llm

    llm = get_llm()
    if not llm.available:
        return None
    task = (
        f"Question: {prompt}\nReference answer: {reference}\nStudent answer: {response}\n\n"
        'Return JSON: {"score": 0.0-1.0, "feedback": "one or two sentences addressed to the '
        'student", "missing": ["key point missed", ...]}'
    )
    try:
        data = llm.complete_json(_GRADER_SYSTEM, task, max_tokens=300, temperature=0.0)
        score = float(data["score"])
    except (LLMUnavailable, ValueError, KeyError, TypeError):
        return None
    score = min(max(score, 0.0), 1.0)
    missing = [str(m) for m in data.get("missing", []) if m][:5] if isinstance(data, dict) else []
    return GradeResult(
        round(score, 3),
        score_to_rating(score),
        _verdict(score),
        str(data.get("feedback", "")).strip()[:400],
        missing,
        method="llm",
    )


def grade(
    kind: str,
    prompt: str,
    reference: str,
    response: str,
    embed: Optional[EmbedFn] = None,
    use_llm: bool = True,
) -> GradeResult:
    quick = grade_heuristic(kind, reference, response, embed)
    # Blank or exact answers don't need a model call.
    if quick.score in (0.0, 1.0) or kind == "cloze" or not use_llm:
        return quick
    return grade_with_llm(prompt, reference, response) or quick


# ---------------------------------------------------------------------------
# Feynman technique — explain a whole concept in your own words
# ---------------------------------------------------------------------------


@dataclass
class FeynmanResult:
    score: float
    coverage: float
    clarity: float
    covered: List[str]
    missing: List[str]
    feedback: str
    follow_up: str
    method: str = "heuristic"


def feynman_heuristic(
    keywords: Sequence[str],
    reference: str,
    explanation: str,
    embed: Optional[EmbedFn] = None,
) -> FeynmanResult:
    low = explanation.lower()
    covered = [k for k in keywords if all(_stem(w) in low for w in k.lower().split())]
    missing = [k for k in keywords if k not in covered]
    coverage = len(covered) / max(len(keywords), 1)
    semantic = coverage
    if embed is not None and explanation.strip():
        v = embed([reference, explanation])
        cos = float(np.dot(v[0], v[1]) / (np.linalg.norm(v[0]) * np.linalg.norm(v[1]) + 1e-9))
        semantic = min(max((cos - 0.2) / 0.6, 0.0), 1.0)
    words = explanation.split()
    avg_sentence = len(words) / max(1, explanation.count(".") + explanation.count("!") + explanation.count("?"))
    clarity = 1.0 if 8 <= avg_sentence <= 24 else 0.7 if avg_sentence < 35 else 0.4
    if len(words) < 25:
        clarity *= 0.6
    score = round(0.45 * semantic + 0.4 * coverage + 0.15 * clarity, 3)
    follow = f"How would you explain “{missing[0]}” to a 12-year-old?" if missing else (
        "What is a real-world example that shows this idea?"
    )
    return FeynmanResult(
        score,
        round(coverage, 3),
        round(clarity, 3),
        covered,
        missing[:6],
        "Strong explanation." if score >= 0.75 else "Good start — fill the gaps below and try again."
        if score >= 0.45 else "Re-read the source, then explain it again in simple words.",
        follow,
    )


def feynman_with_llm(concept: str, reference: str, explanation: str) -> Optional[FeynmanResult]:
    from llm.client import LLMUnavailable, get_llm

    llm = get_llm()
    if not llm.available:
        return None
    task = (
        f"Concept: {concept}\nSource material: {reference[:2500]}\n\nStudent's explanation "
        f"(Feynman technique, in their own words):\n{explanation}\n\nEvaluate it. Return JSON: "
        '{"score": 0-1, "coverage": 0-1, "clarity": 0-1, "covered": ["idea", ...], '
        '"missing": ["important idea not explained", ...], "misconceptions": ["...", ...], '
        '"feedback": "2-3 sentences", "follow_up": "one probing question that exposes the '
        'biggest gap"}'
    )
    try:
        d = llm.complete_json(_GRADER_SYSTEM, task, max_tokens=700, temperature=0.1)
        score = float(d["score"])
    except (LLMUnavailable, ValueError, KeyError, TypeError):
        return None
    misconceptions = [f"Misconception: {m}" for m in d.get("misconceptions", []) if m]
    return FeynmanResult(
        round(min(max(score, 0.0), 1.0), 3),
        round(float(d.get("coverage", score)), 3),
        round(float(d.get("clarity", score)), 3),
        [str(c) for c in d.get("covered", [])][:8],
        ([str(m) for m in d.get("missing", [])] + misconceptions)[:8],
        str(d.get("feedback", ""))[:600],
        str(d.get("follow_up", ""))[:300],
        method="llm",
    )
