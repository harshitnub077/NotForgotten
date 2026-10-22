"""
Card generation following the minimum-information principle: each card
tests one atomic fact, avoids yes/no prompts, and keeps answers short.

Card kinds
    qa       question → short answer                      (retrieval practice)
    cloze    sentence with a key term blanked              (cued recall)
    explain  "why/how" prompt graded on key ideas          (elaborative interrogation)

With an LLM we ask for a mix of all three; offline we mine definitional
sentences and blank out the most characteristic keyphrase.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from nlp.text import STOPWORDS, sentences

CLOZE_BLANK = "_____"
_DEF_RE = re.compile(
    r"^(?:The |An? )?(?P<term>[A-Za-z][\w\-\s()]{2,60}?)\s+"
    r"(?P<verb>is|are|refers to|means|describes|represents|is defined as|denotes)\s+"
    r"(?P<body>.{15,240})$"
)


@dataclass
class CardDraft:
    kind: str
    prompt: str
    answer: str
    explanation: str = ""
    source_index: Optional[int] = None   # index into the excerpts given


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You write excellent spaced-repetition flashcards. Rules: one atomic fact per card; "
    "questions must be answerable from the excerpts alone; never yes/no questions; answers "
    "under 25 words; prefer 'why' and 'how' over trivia; no references to 'the text' or "
    "'the passage'."
)


def generate_with_llm(
    concept_name: str,
    summary: str,
    excerpts: Sequence[str],
    n_cards: int = 5,
) -> Optional[List[CardDraft]]:
    from llm.client import LLMUnavailable, get_llm

    llm = get_llm()
    if not llm.available:
        return None
    numbered = "\n\n".join(f"[{i}] {e[:900]}" for i, e in enumerate(excerpts[:4]))
    prompt = (
        f"Concept: {concept_name}\nSummary: {summary}\n\nExcerpts:\n{numbered}\n\n"
        f"Write {n_cards} cards mixing kinds: 'qa' (question/answer), 'cloze' (a sentence "
        f"with the key term replaced by {CLOZE_BLANK}; answer is the missing term), and "
        "'explain' (a why/how question whose answer lists the key idea). Return a JSON array "
        'of objects: {"kind": "qa|cloze|explain", "prompt": "...", "answer": "...", '
        '"explanation": "one sentence of context shown after answering", "source": <excerpt '
        "index>}."
    )
    try:
        data = llm.complete_json(_SYSTEM, prompt, max_tokens=1800, temperature=0.4)
    except (LLMUnavailable, ValueError):
        return None
    if not isinstance(data, list):
        return None
    cards: List[CardDraft] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "qa")).lower()
        prompt_text = str(item.get("prompt", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if kind not in ("qa", "cloze", "explain") or not prompt_text or not answer:
            continue
        if kind == "cloze" and CLOZE_BLANK not in prompt_text:
            prompt_text = re.sub(r"_{2,}|\[\.\.\.\]|\{\{.*?\}\}", CLOZE_BLANK, prompt_text)
            if CLOZE_BLANK not in prompt_text:
                kind = "qa"
        src = item.get("source")
        cards.append(
            CardDraft(
                kind=kind,
                prompt=prompt_text[:500],
                answer=answer[:400],
                explanation=str(item.get("explanation", "")).strip()[:400],
                source_index=src if isinstance(src, int) and 0 <= src < len(excerpts) else None,
            )
        )
    return cards or None


# ---------------------------------------------------------------------------
# Offline heuristics
# ---------------------------------------------------------------------------


def generate_heuristic(
    keywords: Sequence[str],
    excerpts: Sequence[str],
    n_cards: int = 4,
) -> List[CardDraft]:
    cards: List[CardDraft] = []
    seen_prompts = set()
    kw = [k for k in keywords if k and k.lower() not in STOPWORDS]

    candidates = []
    for src_idx, excerpt in enumerate(excerpts):
        for s in sentences(excerpt):
            if 50 <= len(s) <= 260 and not s.endswith("?"):
                candidates.append((src_idx, s))

    # 1. Definitions → Q/A
    for src_idx, s in candidates:
        m = _DEF_RE.match(s.rstrip("."))
        if not m:
            continue
        term = m.group("term").strip()
        if len(term.split()) > 6 or term.lower() in STOPWORDS:
            continue
        verb = m.group("verb")
        question = f"What {'are' if verb == 'are' else 'is'} {term[0].lower() + term[1:]}?"
        base_verb = {"refers to": "refer to", "means": "mean", "denotes": "denote"}
        if verb in base_verb:
            question = f"What does “{term}” {base_verb[verb]}?"
        if question in seen_prompts:
            continue
        seen_prompts.add(question)
        cards.append(CardDraft("qa", question, m.group("body").strip().rstrip("."), s, src_idx))
        if len(cards) >= max(1, n_cards // 2):
            break

    # 2. Keyphrase cloze on the most keyword-dense sentences
    scored = []
    for src_idx, s in candidates:
        low = s.lower()
        hits = [k for k in kw if re.search(rf"\b{re.escape(k)}\b", low)]
        if hits:
            scored.append((len(hits), -abs(len(s) - 140), src_idx, s, hits))
    scored.sort(reverse=True)
    used_terms = set()
    for _, _, src_idx, s, hits in scored:
        if len(cards) >= n_cards:
            break
        term = next((h for h in sorted(hits, key=len, reverse=True) if h not in used_terms), None)
        if term is None:
            continue
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        match = pattern.search(s)
        if not match:
            continue
        prompt = pattern.sub(CLOZE_BLANK, s, count=1)
        if prompt in seen_prompts:
            continue
        seen_prompts.add(prompt)
        used_terms.add(term)
        cards.append(CardDraft("cloze", prompt, match.group(0), s, src_idx))

    return cards[:n_cards]


def generate_cards(
    concept_name: str,
    summary: str,
    keywords: Sequence[str],
    excerpts: Sequence[str],
    n_cards: int = 5,
    use_llm: bool = True,
) -> List[CardDraft]:
    if use_llm:
        cards = generate_with_llm(concept_name, summary, excerpts, n_cards)
        if cards:
            return cards
    cards = generate_heuristic(keywords, excerpts, n_cards)
    if not cards and summary:
        cards = [CardDraft("explain", f"Explain the key idea of “{concept_name}”.", summary, summary, 0)]
    return cards
