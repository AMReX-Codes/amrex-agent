"""Unit tests for Paper Validator Mode 2."""

from __future__ import annotations

from types import SimpleNamespace

from src.graph import (
    _paper_validator_mode2_enabled,
    _route_after_clarification,
    _route_after_input_writer,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    feature_a_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.nodes import paper_validator_node as mode2_module
from src.session_manager import FEATURE_A_DEPENDENCY_ID


def test_mode2_enabled_from_state_flag():
    assert _paper_validator_mode2_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_mode2_enabled({"paper_validator_enabled": False}) is False


def test_mode2_enabled_from_config_dict_or_object():
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": True}}) is True
    assert (
        _paper_validator_mode2_enabled(
            {"config": SimpleNamespace(paper_validator_enabled=True)}
        )
        is True
    )
    assert _paper_validator_mode2_enabled({"config": {"paper_validator_enabled": "yes"}}) is False


def test_route_after_input_writer_mode2_gate():
    assert _route_after_input_writer({}) == "end"
    assert (
        _route_after_input_writer(
            {"paper_validator_enabled": True, "validation_manifest": {"figures": []}}
        )
        == "paper_validator_node"
    )
    assert (
        _route_after_input_writer(
            {"paper_validator_enabled": True, "validation_manifest": "invalid"}
        )
        == "end"
    )


def test_existing_graph_routes_still_behave():
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": None}) == "architect_node"
    assert (
        _route_after_sweep_detection({"feature_a_verified": True, "sweep_id": "sweep_1"})
        == "sweep_execution_handler"
    )
    assert _route_after_sweep_detection({}) == "architect_node"


def test_existing_handler_nodes_and_dependency_gate():
    updates = feature_a_dependency_handler_node(
        {"gate_approvals": "bad", "errors_active": "bad", "feature_a_verified": False}
    )
    assert updates["mode"] == "terminal"
    assert updates["reviewer_failure_category"] == "dependency_gate"
    assert updates["gate_approvals"][-1]["details"]["criterion"] == FEATURE_A_DEPENDENCY_ID
    assert "feature_a_dependency_unverified" in updates["errors_active"]

    deduped = feature_a_dependency_handler_node(
        {"feature_a_verified": False, "gate_approvals": [], "errors_active": ["feature_a_dependency_unverified"]}
    )
    assert deduped["errors_active"].count("feature_a_dependency_unverified") == 1


def test_existing_printing_handlers(capsys):
    clarification_state = {"clarification_questions": ["q1"]}
    assert clarification_handler_node(clarification_state) is clarification_state
    assert "Clarification needed:" in capsys.readouterr().out

    sweep_state = {"sweep_id": "s-1", "sweep_parameter": "run_ntasks"}
    assert sweep_execution_handler_node(sweep_state) is sweep_state
    assert "Sweep detected:" in capsys.readouterr().out


def test_create_graph_wires_mode2_node():
    app = create_graph().compile()
    edges = {(edge.source, edge.target) for edge in app.get_graph().edges}
    assert ("input_writer_node", "paper_validator_node") in edges
    assert ("input_writer_node", "__end__") in edges
    assert ("paper_validator_node", "__end__") in edges


def test_mode2_node_returns_not_complete_without_manifest():
    updates = mode2_module.paper_validator_node({})
    assert updates.get("paper_validator_mode2_complete", False) is False


def test_mode2_node_aggregates_report_and_skips(monkeypatch):
    def fake_ssim(reference_path: str, generated_path: str):
        if "temperature" in generated_path:
            return 0.91, None
        if "pressure" in generated_path:
            return 0.62, None
        return None, "ssim_computation_failed:RuntimeError"

    monkeypatch.setattr(mode2_module, "compute_ssim_score", fake_ssim)

    state = {
        "config": {"ssim_pass_threshold": 0.85},
        "validation_manifest": {
            "paper_source": "arxiv:2401.12345",
            "figures": [
                {
                    "figure_id": "fig_temp",
                    "reference_image_path": "/tmp/ref_temp.png",
                    "quantity_of_interest": "temperature",
                    "plot_type": "slice",
                },
                {
                    "figure_id": "fig_pressure",
                    "reference_image_path": "/tmp/ref_pressure.png",
                    "quantity_of_interest": "pressure",
                    "plot_type": "slice",
                },
                {
                    "figure_id": "fig_skipped",
                    "reference_image_path": "/tmp/ref_density.png",
                    "quantity_of_interest": "density",
                    "plot_type": "contour",
                },
            ],
        },
        "visualization_output_paths": [
            "/tmp/generated_temperature_slice.png",
            "/tmp/generated_pressure_slice.png",
        ],
    }

    updates = mode2_module.paper_validator_node(state)

    assert updates["paper_validator_mode2_complete"] is True
    report = updates["validation_report"]
    assert report["paper_source"] == "arxiv:2401.12345"
    assert report["n_figures_compared"] == 2
    assert report["n_figures_skipped"] == 1
    assert len(report["figures"]) == 3
    assert set(report["failed_figures"]) == {"fig_pressure", "fig_skipped"}
    assert report["overall_passed"] is False
    assert report["overall_ssim_mean"] == (0.91 + 0.62) / 2
    assert updates["reproduction_confidence"] == report["overall_ssim_mean"]


def test_mode2_node_handles_invalid_threshold_and_non_list_figures(monkeypatch):
    monkeypatch.setattr(mode2_module, "compute_ssim_score", lambda _a, _b: (0.9, None))

    updates = mode2_module.paper_validator_node(
        {
            "config": SimpleNamespace(ssim_pass_threshold="not-a-number"),
            "validation_manifest": {"paper_source": "x", "figures": "invalid"},
            "visualization_images": ["/tmp/generated_any.png"],
        }
    )
    report = updates["validation_report"]
    assert report["n_figures_compared"] == 0
    assert report["n_figures_skipped"] == 0
    assert report["overall_ssim_mean"] is None
    assert report["reproduction_confidence"] is None
    assert report["overall_passed"] is False
