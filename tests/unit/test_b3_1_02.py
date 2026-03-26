"""Session 44 tests for [B3.1-02] Required Unit Test Entry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.graph import (
    CRITICAL_PATH_FEATURES_SECTION,
    REQUIRED_OUTPUTS_SECTION,
    _is_paper_validator_enabled,
    _latest_architect_details,
    _route_after_clarification,
    _route_after_critical_path_features,
    _route_after_manifest_validation,
    _route_after_required_outputs,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    critical_path_features_section_node,
    get_critical_path_features_section,
    get_required_outputs_section,
    paper_manifest_gate_node,
    required_outputs_section_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult


def test_required_unit_test_entry_exists_and_targets_required_outputs() -> None:
    assert get_required_outputs_section() == REQUIRED_OUTPUTS_SECTION
    assert REQUIRED_OUTPUTS_SECTION == ("selected_case", "modifications")


def test_latest_architect_details_handles_missing_or_invalid_history() -> None:
    assert _latest_architect_details({}) is None
    assert _latest_architect_details({"workflow_history": "bad"}) is None
    assert _latest_architect_details({"workflow_history": ["bad", {"node": "architect"}]}) is None
    assert (
        _latest_architect_details(
            {"workflow_history": [{"node": "clarification", "details": {"selected_case": "x"}}]}
        )
        is None
    )


def test_latest_architect_details_returns_most_recent_architect_details() -> None:
    state = {
        "workflow_history": [
            {"node": "architect", "details": {"selected_case": "A"}},
            {"node": "input_writer", "details": {"selected_case": "B"}},
            {
                "node": "architect",
                "details": {"selected_case": "C", "modifications": ["m1"]},
            },
        ]
    }
    assert _latest_architect_details(state) == {
        "selected_case": "C",
        "modifications": ["m1"],
    }


def test_required_outputs_section_node_accepts_valid_top_level_only() -> None:
    result = required_outputs_section_node(
        {"selected_case": "flame_sheet", "modifications": []}
    )
    assert result["required_outputs_valid"] is True
    assert result["required_outputs_missing"] == []
    assert result["required_outputs_error"] is None


def test_required_outputs_section_node_rejects_missing_required_fields() -> None:
    result = required_outputs_section_node({})
    assert result["required_outputs_valid"] is False
    assert result["required_outputs_missing"] == ["selected_case", "modifications"]
    assert "missing required outputs" in result["required_outputs_error"]


def test_required_outputs_section_node_rejects_blank_selected_case() -> None:
    result = required_outputs_section_node({"selected_case": "  ", "modifications": []})
    assert result["required_outputs_valid"] is False
    assert result["required_outputs_missing"] == ["selected_case"]


def test_required_outputs_section_node_rejects_non_list_modifications() -> None:
    result = required_outputs_section_node(
        {"selected_case": "flame_sheet", "modifications": "not-a-list"}
    )
    assert result["required_outputs_valid"] is False
    assert result["required_outputs_missing"] == []
    assert "modifications must be a list" in result["required_outputs_error"]


def test_required_outputs_section_node_rejects_canonical_mismatch() -> None:
    result = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": [{"param": "x", "value": 1}],
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "case-b",
                        "modifications": [{"param": "x", "value": 2}],
                    },
                }
            ],
        }
    )
    assert result["required_outputs_valid"] is False
    assert "selected_case mismatch" in result["required_outputs_error"]
    assert "modifications mismatch" in result["required_outputs_error"]


def test_required_outputs_section_node_allows_history_without_comparable_shapes() -> None:
    result = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": [],
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": 123, "modifications": "bad"}}
            ],
        }
    )
    assert result["required_outputs_valid"] is True
    assert result["required_outputs_error"] is None


def test_route_after_required_outputs() -> None:
    assert _route_after_required_outputs({"required_outputs_valid": True}) == "intent_extraction_node"
    assert _route_after_required_outputs({"required_outputs_valid": False}) == "clarification_handler"
    assert _route_after_required_outputs({}) == "clarification_handler"


def test_route_helpers() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-01"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"

    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"
    assert _route_after_manifest_validation({"paper_manifest_valid": True}) == "input_writer_node"
    assert (
        _route_after_manifest_validation(
            {
                "paper_manifest_valid": True,
                "reproducibility_oracle_enabled": True,
                "reproducibility_oracle_valid": False,
            }
        )
        == "clarification_handler"
    )


def test_critical_path_feature_helpers() -> None:
    assert get_critical_path_features_section() == CRITICAL_PATH_FEATURES_SECTION
    assert _route_after_critical_path_features({"critical_path_features_valid": True}) == "input_writer_node"
    assert _route_after_critical_path_features({"critical_path_features_valid": False}) == "clarification_handler"
    assert _route_after_critical_path_features({}) == "clarification_handler"


def test_critical_path_features_section_node_paths() -> None:
    result_default = critical_path_features_section_node({})
    assert result_default["critical_path_features_valid"] is True
    assert result_default["critical_path_features_missing"] == []

    result_map = critical_path_features_section_node(
        {"critical_path_features": {name: True for name in CRITICAL_PATH_FEATURES_SECTION}}
    )
    assert result_map["critical_path_features_valid"] is True

    result_missing = critical_path_features_section_node(
        {
            "critical_path_features": [
                name for name in CRITICAL_PATH_FEATURES_SECTION if name != "architect_node"
            ]
        }
    )
    assert result_missing["critical_path_features_valid"] is False
    assert result_missing["critical_path_features_missing"] == ["architect_node"]

    result_bad = critical_path_features_section_node({"critical_path_features": "invalid"})
    assert result_bad["critical_path_features_valid"] is False
    assert "must be list, tuple, set, or dict" in result_bad["critical_path_features_error"]


def test_is_paper_validator_enabled_by_state_and_config() -> None:
    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
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


def test_paper_manifest_gate_paths() -> None:
    bypass = paper_manifest_gate_node({})
    assert bypass["paper_manifest_valid"] is True
    assert bypass["paper_manifest_error"] is None

    missing = paper_manifest_gate_node({"paper_validator_enabled": True})
    assert missing["paper_manifest_valid"] is False
    assert "required" in missing["paper_manifest_error"]

    invalid = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {"document_id": 123, "checks": "invalid"},
        }
    )
    assert invalid["paper_manifest_valid"] is False
    assert invalid["paper_manifest_error"]

    blocking = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-b3-1-02",
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
    assert blocking["paper_manifest_valid"] is False
    assert "blocking failures" in blocking["paper_manifest_error"]

    manifest = PaperValidationManifest(
        document_id="paper-b3-1-02-model",
        checks=[ValidationCheckResult(check_id="c1", title="ok", status="pass")],
    )
    accepted = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": manifest,
        }
    )
    assert accepted["paper_manifest_valid"] is True
    assert accepted["paper_manifest_error"] is None
    assert accepted["paper_validation_manifest"]["document_id"] == "paper-b3-1-02-model"


def test_create_graph_compiles_with_required_outputs_gate() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()

    nodes = set(graph_def.nodes.keys())
    assert "required_outputs_section_node" in nodes
    assert "paper_manifest_gate_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("architect_node", "required_outputs_section_node") in edges
    assert ("required_outputs_section_node", "intent_extraction_node") in edges
    assert ("required_outputs_section_node", "clarification_handler") in edges
