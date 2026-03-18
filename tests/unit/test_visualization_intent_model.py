from src.models.visualization_intent import VisualizationIntent
from src.nodes.visualization_intent_node import (
    build_visualization_intent,
    resolve_visualization_intent,
    visualization_intent_node,
)


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
    model = build_visualization_intent(
        prompt="show cloud water every 2 minutes",
        solver_name="ERF",
    )
    assert "qc" in model.requested_fields
    assert model.cadence_prompt_seconds == 120
    assert model.cadence_solver_time == 120.0
    assert model.timestep_scope == "all"
    assert model.source == "prompt"


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


def test_build_visualization_intent_falls_back_to_step_cadence_for_unknown_solver():
    model = build_visualization_intent(
        prompt="plot temperature every 7 seconds",
        solver_name="UnknownSolver",
    )
    assert model.cadence_prompt_seconds == 7
    assert model.cadence_solver_time is None
    assert "cadence_fallback_to_steps_unknown_time_units" in model.adjustments
    assert model.visualization_config["cadence_solver_steps"] == 7
