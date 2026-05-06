import importlib

from src.services.plan import SimulationPlan


architect_node_module = importlib.import_module("src.nodes.architect_node")
embedding_factory_module = importlib.import_module("src.services.embedding_service_factory")


class DummyConfig:
    def __init__(self, repositories=None):
        self.repositories = repositories or {}


class DummyEmbeddingService:
    def __init__(self):
        self.embeddings = object()

    def get_embedding_call_counts(self):
        return {"total": 0, "embed_documents": 0, "embed_query": 0}


def _plan(selected_case: str):
    return SimulationPlan(
        selected_solver="PeleLMeX",
        selected_case=selected_case,
        modifications=[("amr.n_cell", "128 128 128")],
        reasoning="Retry plan",
        baseline_confidence=0.9,
        indexing_strategy="hierarchical",
        case_candidates=[],
    )


def _retry_state(*, allow_case_reselection_fallback: bool):
    locked_case = "Exec/Plasma/FlameSheetIons"
    return {
        "config": DummyConfig(),
        "prompt": "Use PeleLMeX FlameSheetIons with corrected parameters",
        "mode": "retry",
        "retry_count": 1,
        "selected_case": locked_case,
        "selected_solver": "PeleLMeX",
        "iteration1_case": locked_case,
        "iteration1_solver": "PeleLMeX",
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": locked_case,
                    "selected_solver": "PeleLMeX",
                },
            }
        ],
        "errors_active": ["Unresolved parameter: amr.max_level"],
        "parameter_resolution_feedback": {
            "unresolved_parameters": [("amr.max_level", "2")],
            "resolution_guidance": "Use schema-backed names",
            "available_schema_params": ["amr.max_level"],
            "suggested_params": {"amr.max_level": ["amr.max_level"]},
            "locked_case": locked_case,
            "locked_solver": "PeleLMeX",
            "retry_attempt": 1,
            "max_retries": 3,
            "allow_case_reselection_fallback": allow_case_reselection_fallback,
        },
    }


def test_parameter_resolution_retry_is_locked_to_iteration1_case(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **kwargs):
            call_state["kwargs"] = kwargs
            return _plan("Exec/Plasma/FlameSheetIons")

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node(_retry_state(allow_case_reselection_fallback=False))

    assert call_state["kwargs"].get("baseline_override") == "PeleLMeX/Exec/Plasma/FlameSheetIons"
    assert updates["selected_case"] == "Exec/Plasma/FlameSheetIons"
    assert updates["iteration1_case"] == "Exec/Plasma/FlameSheetIons"
    assert updates["case_reselection_fallback"] is False


def test_retry_fallback_allows_open_reselection_after_limit(monkeypatch):
    call_state = {}

    class FakeArchitectService:
        def __init__(self, _config, embedding_service=None):
            self.level0_searcher = object()

        def execute_planning(self, **kwargs):
            call_state["kwargs"] = kwargs
            return _plan("Exec/Plasma/PremBunsen3DKuhl")

    monkeypatch.setattr(embedding_factory_module, "get_embedding_service", lambda _cfg: DummyEmbeddingService())
    monkeypatch.setattr(architect_node_module, "ArchitectService", FakeArchitectService)

    updates = architect_node_module.architect_node(_retry_state(allow_case_reselection_fallback=True))

    assert "baseline_override" not in call_state["kwargs"]
    assert updates["selected_case"] == "Exec/Plasma/PremBunsen3DKuhl"
    assert updates["iteration1_case"] == "Exec/Plasma/FlameSheetIons"
    assert updates["case_reselection_fallback"] is True
