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
        baseline_confidence=0.92,
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


def _make_router_service(
    strategy: str = "hierarchical",
    baseline_override: str | None = None,
    fallback_to_simple_on_error: bool = True,
):
    service = object.__new__(architect_service_module.ArchitectService)
    service.config = SimpleNamespace(
        indexing_strategy=strategy,
        baseline_override=baseline_override,
        fallback_to_simple_on_error=fallback_to_simple_on_error,
    )
    return service


def test_execute_planning_attaches_hierarchical_router_mapping(caplog):
    service = _make_router_service(strategy="hierarchical")

    def _fake_create_plan_rag(self, **_kwargs):
        return _plan()

    service.create_plan_rag = MethodType(_fake_create_plan_rag, service)

    with caplog.at_level("INFO"):
        plan = service.execute_planning(user_prompt="test")

    mapping = plan.analysis["router_mapping"]
    assert mapping["router_branch"] == "hierarchical"
    assert mapping["diagram_nodes"]["router"] == "strategy_router"
    assert mapping["diagram_nodes"]["branch"] == "hierarchical_strategy"
    assert "strategy_router -> hierarchical_strategy" in caplog.text


def test_execute_planning_attaches_override_router_mapping(caplog):
    service = _make_router_service(
        strategy="simple",
        baseline_override="PeleC/Exec/RegTests/PMF",
    )

    def _fake_execute_planning_with_override(self, **_kwargs):
        return _plan()

    service._execute_planning_with_override = MethodType(_fake_execute_planning_with_override, service)

    with caplog.at_level("INFO"):
        plan = service.execute_planning(user_prompt="test")

    mapping = plan.analysis["router_mapping"]
    assert mapping["router_branch"] == "baseline_override"
    assert mapping["diagram_nodes"]["router"] == "strategy_router"
    assert mapping["diagram_nodes"]["branch"] == "static_strategy"
    assert "baseline_override=true" in caplog.text


def test_execute_planning_attaches_fallback_router_mapping(caplog):
    service = _make_router_service(strategy="hierarchical", fallback_to_simple_on_error=True)

    def _failing_create_plan_rag(self, **_kwargs):
        raise RuntimeError("boom")

    def _fake_create_plan(self, **_kwargs):
        return _plan()

    service.create_plan_rag = MethodType(_failing_create_plan_rag, service)
    service.create_plan = MethodType(_fake_create_plan, service)

    with caplog.at_level("INFO"):
        plan = service.execute_planning(user_prompt="test")

    mapping = plan.analysis["router_mapping"]
    assert mapping["router_branch"] == "hierarchical_fallback_to_simple"
    assert mapping["diagram_nodes"]["router"] == "strategy_router"
    assert mapping["diagram_nodes"]["branch"] == "simple_strategy"
    assert "fallback=hierarchical_error" in caplog.text
