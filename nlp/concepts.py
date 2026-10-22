"""
Concept discovery: turn a document's chunks into a small set of concepts.

1. Each chunk embedding (unit-norm MiniLM vector) is augmented with a scaled
   position coordinate, so clusters prefer contiguous passages — documents
   are written in order, and a concept usually spans neighbouring pages.
2. Ward agglomerative clustering for a range of k; the k with the best
   silhouette score wins (bounded so a 300-page book doesn't become 3 blobs
   or 150 shards).
3. Concepts are named by class-based TF-IDF keyphrases, optionally refined
   by an LLM into a human title + one-line summary.
4. Edges come from centroid cosine similarity. Within a document, the
   earlier concept is treated as a prerequisite of the later one; across
   documents, similar concepts are linked as "related".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from nlp.text import keyphrases, sentences, title_case

POSITION_WEIGHT = 0.6
PREREQ_THRESHOLD = 0.35
SEQUENTIAL_THRESHOLD = 0.25
RELATED_THRESHOLD = 0.5
MAX_NEIGHBOURS = 3


@dataclass
class ConceptDraft:
    chunk_indices: List[int]
    centroid: np.ndarray
    position: float
    keywords: List[str] = field(default_factory=list)
    name: str = ""
    summary: str = ""


def _candidate_ks(n: int, max_concepts: int) -> List[int]:
    lo = max(2, math.ceil(n / 14))
    hi = min(max_concepts, max(2, n // 3))
    if hi <= lo:
        return [min(lo, n)]
    step = max(1, (hi - lo) // 10)
    return list(range(lo, hi + 1, step))


def cluster_chunks(embeddings: np.ndarray, max_concepts: int = 40) -> List[int]:
    """Return a concept label per chunk (labels ordered by first appearance)."""
    n = len(embeddings)
    if n <= 3:
        return [0] * n

    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    emb = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True).clip(1e-9)
    pos = (np.arange(n) / max(n - 1, 1))[:, None] * POSITION_WEIGHT
    features = np.hstack([emb, pos])

    best_labels: Optional[np.ndarray] = None
    best_score = -2.0
    for k in _candidate_ks(n, max_concepts):
        labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(features)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(features, labels)
        if score > best_score:
            best_score, best_labels = score, labels
    if best_labels is None:
        return [0] * n

    # Relabel in reading order so concept #0 is the first one encountered.
    order: Dict[int, int] = {}
    for lab in best_labels:
        order.setdefault(int(lab), len(order))
    return [order[int(lab)] for lab in best_labels]


def discover_concepts(
    texts: Sequence[str],
    embeddings: np.ndarray,
    max_concepts: int = 40,
) -> List[ConceptDraft]:
    labels = cluster_chunks(np.asarray(embeddings, dtype=np.float32), max_concepts)
    groups: Dict[int, List[int]] = {}
    for idx, lab in enumerate(labels):
        groups.setdefault(lab, []).append(idx)

    drafts: List[ConceptDraft] = []
    for lab in sorted(groups):
        idxs = groups[lab]
        centroid = np.mean([embeddings[i] for i in idxs], axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-9)
        drafts.append(ConceptDraft(idxs, centroid, float(np.mean(idxs))))

    phrases = keyphrases([" ".join(texts[i] for i in d.chunk_indices) for d in drafts])
    used_names: Dict[str, int] = {}
    for d, kws in zip(drafts, phrases):
        d.keywords = kws
        name = title_case(kws[0]) if kws else f"Section {len(used_names) + 1}"
        if name in used_names:
            used_names[name] += 1
            alt = next((title_case(k) for k in kws[1:] if title_case(k) not in used_names), None)
            name = alt or f"{name} ({used_names[name]})"
        used_names.setdefault(name, 1)
        d.name = name
        d.summary = _central_sentence(texts, embeddings, d)
    return drafts


def _central_sentence(texts: Sequence[str], embeddings: np.ndarray, d: ConceptDraft) -> str:
    sims = [float(np.dot(embeddings[i], d.centroid)) for i in d.chunk_indices]
    best_chunk = texts[d.chunk_indices[int(np.argmax(sims))]]
    for s in sentences(best_chunk):
        if 40 <= len(s) <= 260:
            return s
    return best_chunk[:220].strip()


def refine_with_llm(drafts: List[ConceptDraft], texts: Sequence[str]) -> bool:
    """Ask the LLM for crisp names and summaries. Returns False when offline."""
    from llm.client import LLMUnavailable, get_llm

    llm = get_llm()
    if not llm.available or not drafts:
        return False
    items = []
    for i, d in enumerate(drafts):
        sample = " ".join(texts[j] for j in d.chunk_indices[:2])[:700]
        items.append(f'{i}. keywords: {", ".join(d.keywords[:5])}\n   excerpt: {sample}')
    prompt = (
        "Below are concept clusters extracted from a study document. For each, give a short "
        "specific concept name (2-5 words, Title Case) and a one-sentence summary a student "
        "could learn from.\n\n" + "\n".join(items) + '\n\nReturn a JSON array: [{"i": 0, '
        '"name": "...", "summary": "..."}, ...] with one entry per cluster.'
    )
    try:
        data = llm.complete_json("You are an expert curriculum designer.", prompt, max_tokens=2500)
    except (LLMUnavailable, ValueError):
        return False
    if not isinstance(data, list):
        return False
    for entry in data:
        try:
            d = drafts[int(entry["i"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if isinstance(entry.get("name"), str) and entry["name"].strip():
            d.name = entry["name"].strip()[:80]
        if isinstance(entry.get("summary"), str) and entry["summary"].strip():
            d.summary = entry["summary"].strip()[:400]
    return True


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


@dataclass
class ConceptNode:
    id: str
    document_id: str
    position: float
    centroid: np.ndarray


def build_edges(nodes: Sequence[ConceptNode]) -> List[Tuple[str, str, float, str]]:
    """Return (source, target, weight, kind) edges; kind ∈ {prerequisite, related}."""
    if len(nodes) < 2:
        return []
    mat = np.stack([n.centroid for n in nodes])
    mat = mat / np.linalg.norm(mat, axis=1, keepdims=True).clip(1e-9)
    sims = mat @ mat.T

    candidates: List[Tuple[float, int, int, str]] = []
    by_doc: Dict[str, List[int]] = {}
    for i, n in enumerate(nodes):
        by_doc.setdefault(n.document_id, []).append(i)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b, s = nodes[i], nodes[j], float(sims[i, j])
            if a.document_id == b.document_id:
                if s >= PREREQ_THRESHOLD:
                    candidates.append((s, i, j, "prerequisite"))
            elif s >= RELATED_THRESHOLD:
                candidates.append((s, i, j, "related"))

    # Sequential "builds on" links keep each document's storyline connected.
    for idxs in by_doc.values():
        ordered = sorted(idxs, key=lambda k: nodes[k].position)
        for i, j in zip(ordered, ordered[1:]):
            s = float(sims[i, j])
            if SEQUENTIAL_THRESHOLD <= s < PREREQ_THRESHOLD:
                candidates.append((s, i, j, "prerequisite"))

    candidates.sort(reverse=True)
    degree = [0] * len(nodes)
    edges: List[Tuple[str, str, float, str]] = []
    for s, i, j, kind in candidates:
        if degree[i] >= MAX_NEIGHBOURS and degree[j] >= MAX_NEIGHBOURS:
            continue
        degree[i] += 1
        degree[j] += 1
        src, tgt = (i, j) if nodes[i].position <= nodes[j].position else (j, i)
        if kind == "related":
            src, tgt = i, j
        edges.append((nodes[src].id, nodes[tgt].id, round(s, 4), kind))
    return edges
