import importlib

import pytest

from src.services.plan import SimulationPlan


architect_node_module = importlib.import_module("src.nodes.architect_node")
embedding_factory_module = importlib.import_module("src.services.embedding_service_factory")


class DummyConfig:
    def __init__(self):
        self.repositories = {}


class DummyEmbeddingService:
    def __init__(self):
        self.embeddings = object()

    def get_embedding_call_counts(self):
        return {"total": 0, "embed_documents": 0, "embed_query": 0}


def _plan(selected_case="Test/Case", selected_solver="PeleC"):
    return SimulationPlan(
        selected_solver=selected_solver,
        selected_case=selected_case,
        modifications=[],
        reasoning="Test reasoning",
        baseline_confidence=0.8,
        indexing_strategy="simple",
        case_candidates=[],
    )


def test_increments_iteration_and_retry_count(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {"config": DummyConfig(), "prompt": "test", "iteration": 5, "mode": "initial"}
    updates = architect_node_module.architect_node(state)

    assert updates["iteration"] == 6
    assert updates["retry_count"] == 0


def test_retry_increments_counter(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {
        "config": DummyConfig(),
        "prompt": "test",
        "mode": "retry",
        "retry_count": 1,
        "errors_active": ["Some error"],
    }
    updates = architect_node_module.architect_node(state)

    assert updates["retry_count"] == 2
    assert updates["mode"] == "proceed"


def test_enforces_max_retries(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            call_state["init"] = True
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            call_state["called"] = True
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {
        "config": DummyConfig(),
        "prompt": "test",
        "mode": "retry",
        "retry_count": 3,
        "max_retries": 3,
    }
    updates = architect_node_module.architect_node(state)

    assert updates["mode"] == "fail"
    assert updates["retry_count"] == 4
    assert "Max retries" in updates["error"]
    assert "called" not in call_state


def test_iteration_increments_on_failure(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            raise RuntimeError("Planning failed")

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {"config": DummyConfig(), "prompt": "test", "iteration": 5}
    updates = architect_node_module.architect_node(state)

    assert updates["mode"] == "fail"
    assert updates["iteration"] == 6
