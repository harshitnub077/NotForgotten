"""
Pytest configuration and shared fixtures.
Sets DB_PATH and GRAPH_PATH to tmp dirs so tests never touch real data.
"""
from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """
    Redirect all file-based storage to a per-test temp directory.
    This prevents tests from polluting the real data/ directory or
    interfering with each other.
    """
    db = str(tmp_path / "test_memory.db")
    graph = str(tmp_path / "test_graph.json")

    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.setenv("GRAPH_PATH", graph)

    # Also patch the module-level _DB_PATH that was already imported
    try:
        import memory.schema as schema_mod
        monkeypatch.setattr(schema_mod, "_DB_PATH", db)
    except ImportError:
        pass

    try:
        import knowledge_graph.concept_graph as kg_mod
        monkeypatch.setattr(kg_mod, "_GRAPH_PATH", graph)
        # Reset singleton so each test gets a fresh graph
        monkeypatch.setattr(kg_mod, "_graph_instance", None)
    except ImportError:
        pass
