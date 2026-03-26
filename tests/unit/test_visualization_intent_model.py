from src.models.visualization_intent import VisualizationIntent
from src.nodes.visualization_intent_node import (
    build_visualization_intent,
    resolve_visualization_intent,
    visualization_intent_node,
)
from src.services.viz_param_extractor import VizMappingCatalogUnavailableError
from unittest.mock import patch


def test_visualization_intent_model_defaults():
    model = VisualizationIntent()
    assert model.requested_fields == []
    assert model.cadence_prompt_seconds is None
    assert model.cadence_solver_time is None
    assert model.timestep_scope == "latest"
    assert model.plots == []
    assert model.source == "default"
    assert model.adjustments == []


def test_build_visualization_intent_from_prompt_cadence():
    class _MockConfig:
        @classmethod
        def get_viz_tier1_intents(cls):
            return {"cloud_water": {"aliases": ["cloud water", "cloud_water"]}}

        @classmethod
        def build_viz_tier2_candidates(cls, repo_root=None):
            del cls, repo_root
            return {
                "cloud_water": [
                    {"name": "qc", "aliases": ["cloud_water", "cloud water"]},
                ]
            }

    with patch(
        "database.configs.registry.get_config_class",
        lambda code_name: _MockConfig,
    ):
        model = build_visualization_intent(
            prompt="show cloud water every 2 minutes",
            solver_name="ERF",
        )
    assert "qc" in model.requested_fields
    assert model.cadence_prompt_seconds == 120
    assert model.cadence_solver_time == 120.0
    assert model.timestep_scope == "all"
    assert model.source == "prompt"


def test_build_visualization_intent_hard_fails_when_solver_catalog_unavailable(monkeypatch):
    class _MockConfig:
        @classmethod
        def get_viz_tier1_intents(cls):
            return {"cloud_water": {"aliases": ["cloud water"]}}

        @classmethod
        def build_viz_tier2_candidates(cls, repo_root=None):
            del cls, repo_root
            return {}

    monkeypatch.setattr(
        "database.configs.registry.get_config_class",
        lambda code_name: _MockConfig,
    )

    try:
        build_visualization_intent(
            prompt="show cloud water",
            solver_name="ERF",
        )
    except VizMappingCatalogUnavailableError:
        return
    assert False, "expected hard failure when solver catalog is unavailable"


def test_resolve_visualization_intent_uses_existing_typed_payload():
    resolved = resolve_visualization_intent(
        {
                "visualization_intent": {
                    "requested_fields": ["temperature"],
                    "cadence_prompt_seconds": 10,
                    "cadence_solver_time": 10.0,
                    "timestep_scope": "all",
                "plots": [],
                "solver_name": "PeleC",
                "source": "clarification",
                "adjustments": ["remote_latest_only"],
                "visualization_config": {"timesteps": "all"},
            }
        }
    )
    assert resolved["requested_fields"] == ["temperature"]
    assert resolved["source"] == "clarification"
    assert resolved["timestep_scope"] == "all"


def test_visualization_intent_node_populates_state_and_legacy_mirror():
    updates = visualization_intent_node(
        {
            "prompt": "plot temperature every 5 seconds",
            "requested_plot_vars": [],
            "visualization_config": {},
        }
    )
    assert "visualization_intent" in updates
    assert updates["visualization_intent"]["requested_fields"] == ["temperature"]
    assert updates["visualization_intent"]["cadence_prompt_seconds"] == 5
    assert updates["visualization_intent"]["cadence_solver_time"] is None
    assert updates["visualization_intent"]["visualization_config"]["cadence_solver_steps"] == 5
    assert updates["requested_plot_vars"] == ["temperature"]
    assert updates["visualization_config"]["plot_interval_seconds"] == 5


def test_visualization_intent_node_routes_ambiguous_mapping_to_clarification(monkeypatch):
    monkeypatch.setattr(
        "src.nodes.visualization_intent_node.extract_viz_params_from_prompt",
        lambda prompt, code_name=None, repo_root=None: (["velocity"], {}),
    )

    class _MockConfig:
        @classmethod
        def get_viz_tier1_intents(cls):
            return {"velocity": {"aliases": ["velocity"]}}

        @classmethod
        def build_viz_tier2_candidates(cls, repo_root=None):
            del cls, repo_root
            return {
                "velocity": [
                    {"name": "x_velocity", "aliases": ["velocity"]},
                    {"name": "y_velocity", "aliases": ["velocity"]},
                ]
            }

    monkeypatch.setattr(
        "database.configs.registry.get_config_class",
        lambda code_name: _MockConfig,
    )

    updates = visualization_intent_node(
        {
            "prompt": "plot velocity",
            "selected_solver": "ERF",
            "requested_plot_vars": [],
            "visualization_config": {},
        }
    )
    assert updates["requested_plot_vars"] == []
    assert updates["visualization_intent"]["requested_fields"] == []
    assert updates["visualization_mapping_candidates"]["velocity"][0]["name"] == "x_velocity"
    assert updates["visualization_mapping_unresolved"] == []


def test_build_visualization_intent_falls_back_to_step_cadence_for_unknown_solver():
    model = build_visualization_intent(
        prompt="plot temperature every 7 seconds",
        solver_name="UnknownSolver",
    )
    assert model.cadence_prompt_seconds == 7
    assert model.cadence_solver_time is None
    assert "cadence_fallback_to_steps_unknown_time_units" in model.adjustments
    assert model.visualization_config["cadence_solver_steps"] == 7
