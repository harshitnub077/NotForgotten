"""Lightweight text utilities: cleaning, sentences, tokens, keyphrases."""
from __future__ import annotations

import re
from typing import Dict, List, Sequence

STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each either else
    etc even ever every few for from further get gets got had has have having he her here hers
    herself him himself his how however i if in into is it its itself just least less let like
    made make makes many may me might more most much must my myself no nor not now of off often
    on once one only or other others our ours ourselves out over own per perhaps rather really
    same see seen several shall she should since so some such than that the their theirs them
    themselves then there therefore these they this those though through thus to too toward
    under until up upon us use used uses using very via was we well were what whatever when
    where whether which while who whom whose why will with within without would yet you your
    yours yourself yourselves fig figure table chapter section page pp et al eg ie
    """.split()
)

_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-']+")


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # de-hyphenate line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentences(text: str) -> List[str]:
    flat = re.sub(r"\s*\n\s*", " ", text)
    return [s.strip() for s in _SENT_RE.split(flat) if len(s.strip()) > 1]


def tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def content_tokens(text: str) -> List[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 2]


def keyphrases(
    docs: Sequence[str],
    top_k: int = 6,
    ngram_range: tuple = (1, 3),
) -> List[List[str]]:
    """
    Class-based TF-IDF (as in BERTopic): treat each document as one class and
    score n-grams by how characteristic they are of it relative to the rest.
    Returns top_k phrases per input document.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = [d if d.strip() else "empty" for d in docs]
    if len(docs) == 1:
        docs_fit = list(docs) + [""]
    else:
        docs_fit = list(docs)
    vec = TfidfVectorizer(
        ngram_range=ngram_range,
        stop_words=list(STOPWORDS),
        token_pattern=r"(?u)\b[A-Za-z][A-Za-z0-9\-]{2,}\b",
        sublinear_tf=True,
        min_df=1,
        max_df=0.95 if len(docs_fit) > 2 else 1.0,
    )
    try:
        matrix = vec.fit_transform(docs_fit)
    except ValueError:
        return [[] for _ in docs]
    vocab = vec.get_feature_names_out()
    out: List[List[str]] = []
    for row in range(len(docs)):
        scores = matrix.getrow(row).toarray().ravel()
        # Prefer multi-word phrases slightly: they read better as concept names.
        boosted = [(s * (1.0 + 0.15 * (vocab[i].count(" "))), vocab[i]) for i, s in enumerate(scores) if s > 0]
        boosted.sort(reverse=True)
        picked: List[str] = []
        for _, phrase in boosted:
            if any(phrase in p or p in phrase for p in picked):
                continue
            picked.append(phrase)
            if len(picked) >= top_k:
                break
        out.append(picked)
    return out


def title_case(phrase: str) -> str:
    small = {"of", "and", "the", "in", "on", "for", "to", "a", "an", "vs"}
    return " ".join(
        w if (i and w in small) else w[:1].upper() + w[1:]
        for i, w in enumerate(phrase.split())
    )


def term_frequencies(text: str) -> Dict[str, int]:
    freq: Dict[str, int] = {}
    for t in content_tokens(text):
        freq[t] = freq.get(t, 0) + 1
    return freq
