import importlib

import pytest

from src.services.plan import SimulationPlan


architect_node_module = importlib.import_module("src.nodes.architect_node")
embedding_factory_module = importlib.import_module("src.services.embedding_service_factory")


class DummyConfig:
    def __init__(self, repositories=None):
        self.repositories = repositories or {}


class DummyEmbeddingService:
    def __init__(self):
        self.embeddings = object()


def _plan(selected_case="New/Case", selected_solver="PeleC"):
    return SimulationPlan(
        selected_solver=selected_solver,
        selected_case=selected_case,
        modifications=[("amr.n_cell", "128 128 128")],
        reasoning="Adjusted based on feedback",
        baseline_confidence=0.85,
        indexing_strategy="simple",
        case_candidates=[],
    )


def _retry_state():
    return {
        "config": DummyConfig(),
        "prompt": "simulate turbulent flame",
        "mode": "retry",
        "errors_active": [
            "Missing parameter: pelec.cfl",
            "Invalid grid: amr.n_cell not divisible by blocking_factor",
        ],
        "selected_case": "Old/Bad/Case",
        "retry_count": 1,
    }


def test_retry_excludes_rejected_case(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **kwargs):
            call_state["kwargs"] = kwargs
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node(_retry_state())

    assert updates["mode"] == "proceed"
    assert "Old/Bad/Case" in updates["excluded_cases"]
    assert "Old/Bad/Case" in call_state["kwargs"]["excluded_cases"]


def test_clears_errors_after_success(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node(_retry_state())
    assert updates["errors_active"] == []


def test_parameter_resolution_feedback_passed(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **kwargs):
            call_state["kwargs"] = kwargs
            return _plan()

    workflow_history = [
        {
            "node": "input_writer",
            "details": {
                "requires_parameter_resolution": True,
                "unresolved_parameters": [("amr.max_level", "2")],
                "resolution_guidance": "Provide amr.max_level",
                "available_schema_params": ["amr.max_level", "amr.n_cell"],
                "suggested_params": {"amr.max_level": ["amr.max_level"]},
            },
        }
    ]

    state = {
        "config": DummyConfig(),
        "prompt": "test",
        "mode": "retry",
        "retry_count": 1,
        "workflow_history": workflow_history,
        "errors_active": [],
    }

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    architect_node_module.architect_node(state)

    feedback = call_state["kwargs"]["parameter_resolution_feedback"]
    assert feedback is not None
    assert feedback["unresolved_parameters"] == [("amr.max_level", "2")]
