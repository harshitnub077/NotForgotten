"""
Forgetting propagation through prerequisite edges.

Knowing a concept is only as reliable as the foundations it rests on. For a
prerequisite edge u → v with weight w (centroid similarity), a decayed
prerequisite discounts the dependent concept's *effective* retention:

    R_eff(v) = R(v) · Π_{u → v} (1 − λ · w · (1 − R_eff(u)))

evaluated in topological order, so weakness compounds down a chain. The
gap between R(v) and R_eff(v) is "structural risk": you may still recall v
today, but your grasp of it is fragile because what it builds on is fading.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx

LAMBDA = 0.6

Edge = Tuple[str, str, float, str]


def effective_retention(
    retention: Dict[str, Optional[float]],
    edges: Sequence[Edge],
    lam: float = LAMBDA,
) -> Dict[str, Optional[float]]:
    g = nx.DiGraph()
    g.add_nodes_from(retention)
    for src, tgt, w, kind in edges:
        if kind == "prerequisite" and src in retention and tgt in retention:
            g.add_edge(src, tgt, weight=w)

    try:
        order: List[str] = list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible:
        # Cycles shouldn't occur (edges point forward in reading order) but
        # cross-document merges could create one; drop back to raw values.
        return dict(retention)

    eff: Dict[str, Optional[float]] = {}
    for node in order:
        own = retention.get(node)
        if own is None:
            eff[node] = None
            continue
        value = own
        for pred in g.predecessors(node):
            pr = eff.get(pred)
            if pr is None:
                continue  # unlearned prerequisite: unknown, not penalised
            value *= 1.0 - lam * g[pred][node]["weight"] * (1.0 - pr)
        eff[node] = max(0.0, min(1.0, value))
    return eff


def weakest_foundations(
    concept_id: str,
    eff: Dict[str, Optional[float]],
    edges: Sequence[Edge],
    limit: int = 3,
) -> List[str]:
    """Ancestors of *concept_id* ordered by how decayed they are."""
    g = nx.DiGraph()
    for src, tgt, _, kind in edges:
        if kind == "prerequisite":
            g.add_edge(src, tgt)
    if concept_id not in g:
        return []
    ancestors = [a for a in nx.ancestors(g, concept_id) if eff.get(a) is not None]
    ancestors.sort(key=lambda a: eff[a])  # type: ignore[index]
    return ancestors[:limit]
