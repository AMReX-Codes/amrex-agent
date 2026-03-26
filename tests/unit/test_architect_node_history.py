import importlib
from types import MethodType, SimpleNamespace

import pytest

from src.services.plan import SimulationPlan


architect_node_module = importlib.import_module("src.nodes.architect_node")
embedding_factory_module = importlib.import_module("src.services.embedding_service_factory")
architect_service_module = importlib.import_module("src.services.architect")


class DummyConfig:
    def __init__(self, repositories=None):
        self.repositories = repositories or {}


class DummyEmbeddingService:
    def __init__(self):
        self.embeddings = object()

    def get_embedding_call_counts(self):
        return {"total": 0, "embed_documents": 0, "embed_query": 0}


def _plan(selected_case="PeleC/Exec/RegTests/PMF", selected_solver="PeleC"):
    return SimulationPlan(
        selected_solver=selected_solver,
        selected_case=selected_case,
        modifications=[("amr.n_cell", "64 64 64"), ("pelec.cfl", "0.5")],
        reasoning="Reasoning text",
        requirements={
            "solver_source": "level0_faiss",
            "solver_confidence": 0.92,
            "solver_citations": [
                {
                    "index": "physics_regimes",
                    "code": selected_solver,
                    "score": 0.92,
                    "source": "config",
                }
            ],
        },
        baseline_confidence=0.92,
        level0_latency_per_query_ms=6.0,
        level1_latency_per_query_ms=14.5,
        level2_latency_per_query_ms=11.25,
        indexing_strategy="simple",
        case_candidates=[],
    )


def test_appends_history_entry(monkeypatch, tmp_path):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            call_state["called"] = True
            return _plan()

    repo_root = tmp_path / "pelec"
    repo_root.mkdir()
    config = DummyConfig(repositories={"PeleC": str(repo_root)})

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node({"config": config, "prompt": "test", "workflow_history": []})

    entry = updates["workflow_history"][-1]
    assert entry["node"] == "architect"
    assert entry["action"] == "plan_created"
    assert "timestamp" in entry
    assert entry["details"]["selected_case"] == "PeleC/Exec/RegTests/PMF"
    assert entry["details"]["modifications"]
    assert entry["details"]["baseline"]["local_path"] == str(repo_root / "PeleC/Exec/RegTests/PMF")


def test_history_grows_across_calls(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {"config": DummyConfig(), "prompt": "test", "workflow_history": []}
    updates_1 = architect_node_module.architect_node(state)
    updates_2 = architect_node_module.architect_node({**state, **updates_1})

    assert len(updates_2["workflow_history"]) == 2


def test_retry_action_label(monkeypatch):
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
        "errors_active": ["Bad input"],
        "selected_case": "Bad/Case",
        "workflow_history": [],
    }
    updates = architect_node_module.architect_node(state)

    entry = updates["workflow_history"][-1]
    assert entry["action"] == "plan_created_retry"


def test_indexing_calls_are_cumulative(monkeypatch):
    class CountingEmbeddingService:
        def __init__(self):
            self.embeddings = object()
            self._counts = [
                {"total": 2, "embed_documents": 1, "embed_query": 1},
                {"total": 5, "embed_documents": 3, "embed_query": 2},
            ]

        def get_embedding_call_counts(self):
            return self._counts.pop(0)

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: CountingEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {"config": DummyConfig(), "prompt": "test", "workflow_history": []}
    updates = architect_node_module.architect_node(state)

    details = updates["workflow_history"][-1]["details"]
    assert details["indexing_calls_count"] == 3
    assert details["indexing_calls_total"] == 5
    assert details["indexing_calls_detail"]["embed_documents"] == 2
    assert details["indexing_calls_detail"]["embed_query"] == 1


def test_history_includes_level0_and_level2_override_trace(monkeypatch):
    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return SimulationPlan(
                selected_solver="ERF",
                selected_case="Exec/DryRegTests/TaylorGreenVortex",
                modifications=[("amr.n_cell", "128 128 128")],
                reasoning="Override based on case-name match",
                requirements={
                    "solver_source": "level0_faiss",
                    "solver_confidence": 0.1,
                    "solver_citations": [
                        {
                            "index": "physics_regimes",
                            "code": "PeleC",
                            "score": 0.1,
                            "source": "config",
                        }
                    ],
                },
                baseline_confidence=0.91,
                indexing_strategy="hierarchical",
                case_candidates=[],
                level0_solver="PeleC",
                level0_confidence=0.1,
                level2_override_applied=True,
                level2_override_solver="ERF",
                level2_override_case="Exec/DryRegTests/TaylorGreenVortex",
                level2_override_confidence=0.9,
            )

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node({"config": DummyConfig(), "prompt": "test", "workflow_history": []})
    details = updates["workflow_history"][-1]["details"]

    assert details["level0_solver"] == "PeleC"
    assert details["level0_confidence"] == 0.1
    assert details["level2_override_applied"] is True
    assert details["level2_override_solver"] == "ERF"
    assert details["level2_override_case"] == "Exec/DryRegTests/TaylorGreenVortex"
    assert details["level2_override_confidence"] == 0.9
    assert updates["plan"]["requirements"]["solver_confidence"] == 0.1
    assert updates["plan"]["requirements"]["solver_citations"][0]["index"] == "physics_regimes"
