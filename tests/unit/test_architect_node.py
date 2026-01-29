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


def _plan(selected_case="PeleC/Exec/RegTests/PMF", selected_solver="PeleC"):
    return SimulationPlan(
        selected_solver=selected_solver,
        selected_case=selected_case,
        modifications=[("amr.n_cell", "64 64 64")],
        reasoning="Standard PMF case",
        baseline_confidence=0.95,
        indexing_strategy="simple",
        case_candidates=[],
    )


def test_requires_config():
    with pytest.raises(ValueError, match="requires 'config'"):
        architect_node_module.architect_node({"prompt": "test"})


def test_requires_prompt_or_user_requirement():
    with pytest.raises(ValueError, match="requires 'prompt'"):
        architect_node_module.architect_node({"config": DummyConfig()})


def test_uses_user_requirement_fallback(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            call_state["embedding"] = embedding_service
            self.level0_searcher = object()

        def execute_planning(self, **kwargs):
            call_state["kwargs"] = kwargs
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    state = {"config": DummyConfig(), "user_requirement": "legacy prompt"}
    updates = architect_node_module.architect_node(state)

    assert updates["mode"] == "proceed"
    assert call_state["kwargs"]["user_prompt"] == "legacy prompt"


def test_success_maps_plan_and_baseline(tmp_path, monkeypatch):
    repo_root = tmp_path / "pelec"
    repo_root.mkdir()
    config = DummyConfig(repositories={"PeleC": str(repo_root)})

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **_kwargs):
            return _plan()

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node({"config": config, "prompt": "test"})

    assert updates["mode"] == "proceed"
    assert updates["selected_case"] == "PeleC/Exec/RegTests/PMF"
    assert updates["baseline"]["local_path"] == str(repo_root / "PeleC/Exec/RegTests/PMF")
    assert updates["plan"]["baseline"]["local_path"] == str(repo_root / "PeleC/Exec/RegTests/PMF")
