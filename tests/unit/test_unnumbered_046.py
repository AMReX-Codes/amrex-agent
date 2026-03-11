"""Session 24 tests for UNNUMBERED-046 critical path features section."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.graph import (
    CRITICAL_PATH_FEATURES_SECTION,
    _is_paper_validator_enabled,
    _route_after_clarification,
    _route_after_critical_path_features,
    _route_after_manifest_validation,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    critical_path_features_section_node,
    get_critical_path_features_section,
    paper_manifest_gate_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult


def test_get_critical_path_features_section_returns_expected_nodes() -> None:
    assert get_critical_path_features_section() == CRITICAL_PATH_FEATURES_SECTION
    assert "input_writer_node" in CRITICAL_PATH_FEATURES_SECTION


def test_critical_path_features_section_node_defaults_to_valid() -> None:
    result = critical_path_features_section_node({})
    assert result["critical_path_features_valid"] is True
    assert result["critical_path_features_missing"] == []
    assert result["critical_path_features_error"] is None


def test_critical_path_features_section_node_accepts_sequence() -> None:
    result = critical_path_features_section_node(
        {"critical_path_features": list(CRITICAL_PATH_FEATURES_SECTION)}
    )
    assert result["critical_path_features_valid"] is True
    assert result["critical_path_features_missing"] == []


def test_critical_path_features_section_node_accepts_mapping_flags() -> None:
    feature_map = {name: True for name in CRITICAL_PATH_FEATURES_SECTION}
    result = critical_path_features_section_node({"critical_path_features": feature_map})
    assert result["critical_path_features_valid"] is True
    assert result["critical_path_features_error"] is None


def test_critical_path_features_section_node_reports_missing_features() -> None:
    declared = [name for name in CRITICAL_PATH_FEATURES_SECTION if name != "clarification_node"]
    result = critical_path_features_section_node({"critical_path_features": declared})
    assert result["critical_path_features_valid"] is False
    assert result["critical_path_features_missing"] == ["clarification_node"]
    assert "missing critical path features" in result["critical_path_features_error"]


def test_critical_path_features_section_node_rejects_invalid_payload_type() -> None:
    result = critical_path_features_section_node({"critical_path_features": "invalid"})
    assert result["critical_path_features_valid"] is False
    assert len(result["critical_path_features_missing"]) == len(CRITICAL_PATH_FEATURES_SECTION)
    assert "must be list, tuple, set, or dict" in result["critical_path_features_error"]


def test_route_after_critical_path_features() -> None:
    assert _route_after_critical_path_features({"critical_path_features_valid": True}) == "input_writer_node"
    assert _route_after_critical_path_features({"critical_path_features_valid": False}) == "clarification_handler"
    assert _route_after_critical_path_features({}) == "clarification_handler"


def test_route_after_clarification() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"


def test_route_after_sweep_detection() -> None:
    assert _route_after_sweep_detection({"sweep_id": "sweep-01"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({}) == "architect_node"


def test_route_after_manifest_validation() -> None:
    assert _route_after_manifest_validation({"paper_manifest_valid": True}) == "input_writer_node"
    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"
    assert _route_after_manifest_validation({}) == "clarification_handler"


def test_is_paper_validator_enabled_by_state_and_config() -> None:
    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert (
        _is_paper_validator_enabled(
            {"config": SimpleNamespace(paper_validator_enabled=True)}
        )
        is True
    )
    assert _is_paper_validator_enabled({"config": object()}) is False
    assert _is_paper_validator_enabled({}) is False


def test_placeholder_handler_nodes_return_state(capsys: pytest.CaptureFixture[str]) -> None:
    clarification_state = {"clarification_questions": ["Need Reynolds number?"]}
    sweep_state = {"sweep_id": "s1", "sweep_parameter": "amr.n_cell"}

    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state

    captured = capsys.readouterr()
    assert "Clarification needed" in captured.out
    assert "Sweep detected" in captured.out


def test_paper_manifest_gate_bypasses_when_feature_disabled() -> None:
    result = paper_manifest_gate_node({})
    assert result["paper_manifest_valid"] is True
    assert result["paper_manifest_error"] is None


def test_paper_manifest_gate_rejects_when_enabled_and_manifest_missing() -> None:
    result = paper_manifest_gate_node({"paper_validator_enabled": True})
    assert result["paper_manifest_valid"] is False
    assert "required" in result["paper_manifest_error"]


def test_paper_manifest_gate_rejects_invalid_manifest_payload() -> None:
    result = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {"document_id": 123, "checks": "invalid"},
        }
    )
    assert result["paper_manifest_valid"] is False
    assert result["paper_manifest_error"]


def test_paper_manifest_gate_rejects_blocking_failures() -> None:
    result = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-046",
                "checks": [
                    {
                        "check_id": "c1",
                        "title": "critical",
                        "status": "fail",
                        "blocking": True,
                    }
                ],
            },
        }
    )
    assert result["paper_manifest_valid"] is False
    assert "blocking failures" in result["paper_manifest_error"]


def test_paper_manifest_gate_accepts_manifest_model_instance() -> None:
    manifest = PaperValidationManifest(
        document_id="paper-046-model",
        checks=[ValidationCheckResult(check_id="c1", title="ok", status="pass")],
    )
    result = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": manifest,
        }
    )
    assert result["paper_manifest_valid"] is True
    assert result["paper_manifest_error"] is None
    assert result["paper_validation_manifest"]["document_id"] == "paper-046-model"


def test_create_graph_compiles_with_critical_path_artifacts() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    assert "paper_manifest_gate_node" in nodes
    assert "input_writer_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("clarification_node", "paper_manifest_gate_node") in edges
    assert ("paper_manifest_gate_node", "input_writer_node") in edges
    assert ("paper_manifest_gate_node", "clarification_handler") in edges

