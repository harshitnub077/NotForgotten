"""
networkx concept knowledge graph with JSON persistence.

Nodes = concept tags (str)
Edges = prerequisite relationships (A → B means "A is a prerequisite of B")

Node attributes:
    mastery_level : float  — 0.0 (not mastered) to 1.0 (fully mastered)
    last_visited  : str    — ISO-8601 datetime of last session
    review_count  : int    — total review sessions
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import networkx as nx
from dotenv import load_dotenv

load_dotenv()

_GRAPH_PATH = os.getenv("GRAPH_PATH", "./data/concept_graph.json")
_MASTERY_THRESHOLD = 0.6   # below this → concept is considered a gap


# ---------------------------------------------------------------------------
# ConceptGraph
# ---------------------------------------------------------------------------


class ConceptGraph:
    """
    In-memory networkx DiGraph backed by a JSON file.

    The graph is automatically loaded from disk on init (if file exists)
    and saved via ``save()``.
    """

    def __init__(self, path: str = _GRAPH_PATH) -> None:
        self._path = path
        self.G: nx.DiGraph = nx.DiGraph()
        self._load()

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_concept(self, concept: str) -> None:
        """Add a concept node with default attributes if not present."""
        if concept not in self.G:
            self.G.add_node(
                concept,
                mastery_level=0.0,
                last_visited=None,
                review_count=0,
            )

    def get_concept(self, concept: str) -> Optional[dict[str, Any]]:
        if concept not in self.G:
            return None
        return dict(self.G.nodes[concept])

    # ------------------------------------------------------------------
    # Edge / prerequisite management
    # ------------------------------------------------------------------

    def add_prerequisite(self, source: str, target: str) -> None:
        """
        Add a prerequisite edge: source → target.
        Meaning: you should understand *source* before *target*.
        """
        self.add_concept(source)
        self.add_concept(target)
        self.G.add_edge(source, target, relation="prerequisite")

    def get_prerequisites(self, concept: str) -> list[str]:
        """Return all direct prerequisites of *concept*."""
        return list(self.G.predecessors(concept))

    def get_dependents(self, concept: str) -> list[str]:
        """Return concepts that depend on *concept* as a prerequisite."""
        return list(self.G.successors(concept))

    # ------------------------------------------------------------------
    # Mastery tracking
    # ------------------------------------------------------------------

    def update_mastery(self, concept: str, rating: int) -> None:
        """
        Update mastery_level using an exponential moving average.
        rating 1-5 is normalised to [0, 1].

        EMA: new_mastery = 0.7 * old + 0.3 * normalised_rating
        """
        self.add_concept(concept)
        normalised = (rating - 1) / 4.0   # maps 1→0, 5→1
        old = self.G.nodes[concept]["mastery_level"]
        new_mastery = round(0.7 * old + 0.3 * normalised, 4)
        now_str = datetime.now(tz=timezone.utc).isoformat()

        self.G.nodes[concept]["mastery_level"] = new_mastery
        self.G.nodes[concept]["last_visited"] = now_str
        self.G.nodes[concept]["review_count"] = (
            self.G.nodes[concept]["review_count"] + 1
        )

    def mastery_level(self, concept: str) -> float:
        if concept not in self.G:
            return 0.0
        return self.G.nodes[concept]["mastery_level"]

    # ------------------------------------------------------------------
    # Gap detection
    # ------------------------------------------------------------------

    def find_gaps(
        self,
        concept: str,
        threshold: float = _MASTERY_THRESHOLD,
    ) -> list[str]:
        """
        Return prerequisite concepts whose mastery_level is below *threshold*.
        Recurses up the prerequisite chain.

        Usage: if user struggles with B, find_gaps("B") might return ["A"]
        meaning they should revisit A first.
        """
        gaps: list[str] = []
        visited: set[str] = set()

        def _dfs(node: str) -> None:
            for prereq in self.get_prerequisites(node):
                if prereq in visited:
                    continue
                visited.add(prereq)
                if self.mastery_level(prereq) < threshold:
                    gaps.append(prereq)
                _dfs(prereq)

        _dfs(concept)
        return gaps

    def weakest_concepts(self, n: int = 5) -> list[tuple[str, float]]:
        """Return the n concepts with the lowest mastery_level."""
        nodes = [
            (concept, data["mastery_level"])
            for concept, data in self.G.nodes(data=True)
        ]
        nodes.sort(key=lambda x: x[1])
        return nodes[:n]

    def stats(self) -> dict[str, Any]:
        return {
            "total_concepts": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "avg_mastery": (
                sum(d["mastery_level"] for _, d in self.G.nodes(data=True))
                / max(1, self.G.number_of_nodes())
            ),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        path = Path(self._path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.G)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        path = Path(self._path)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            self.G = nx.node_link_graph(data, directed=True)
        else:
            self.G = nx.DiGraph()

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-friendly dict for API responses."""
        return {
            "nodes": [
                {"id": n, **dict(d)}
                for n, d in self.G.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **dict(d)}
                for u, v, d in self.G.edges(data=True)
            ],
            "stats": self.stats(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_graph_instance: Optional[ConceptGraph] = None


def get_concept_graph() -> ConceptGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = ConceptGraph()
    return _graph_instance
