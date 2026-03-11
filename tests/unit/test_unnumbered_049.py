"""Session 79 tests for UNNUMBERED-049 camera-ready scope boundaries."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.graph import (
    CAMERA_READY_SCOPE_BOUNDARIES,
    CRITICAL_PATH_FEATURES_SECTION,
    REQUIRED_OUTPUTS_SECTION,
    _is_paper_validator_enabled,
    _latest_architect_details,
    _route_after_camera_ready_scope_boundaries,
    _route_after_clarification,
    _route_after_manifest_validation,
    _route_after_radon_cc_gate,
    _route_after_required_outputs,
    _route_after_sweep_detection,
    camera_ready_scope_boundary_node,
    clarification_handler_node,
    create_graph,
    critical_path_features_section_node,
    get_camera_ready_scope_boundaries,
    get_critical_path_features_section,
    get_required_outputs_section,
    paper_manifest_gate_node,
    radon_cc_gate_node,
    required_outputs_section_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult
from src.services.plan import evaluate_radon_cc_threshold


def test_get_camera_ready_scope_boundaries_returns_expected_nodes() -> None:
    assert get_camera_ready_scope_boundaries() == CAMERA_READY_SCOPE_BOUNDARIES
    assert "input_writer_node" in CAMERA_READY_SCOPE_BOUNDARIES
    assert "paper_manifest_gate_node" in CAMERA_READY_SCOPE_BOUNDARIES


def test_camera_ready_scope_boundary_node_defaults_to_valid() -> None:
    result = camera_ready_scope_boundary_node({})
    assert result["camera_ready_scope_boundaries_valid"] is True
    assert result["camera_ready_scope_boundaries_missing"] == []
    assert result["camera_ready_scope_boundaries_error"] is None


def test_camera_ready_scope_boundary_node_accepts_sequence_and_mapping() -> None:
    by_list = camera_ready_scope_boundary_node(
        {"camera_ready_scope_boundaries": list(CAMERA_READY_SCOPE_BOUNDARIES)}
    )
    assert by_list["camera_ready_scope_boundaries_valid"] is True
    assert by_list["camera_ready_scope_boundaries_missing"] == []

    by_map = camera_ready_scope_boundary_node(
        {"camera_ready_scope_boundaries": {name: True for name in CAMERA_READY_SCOPE_BOUNDARIES}}
    )
    assert by_map["camera_ready_scope_boundaries_valid"] is True
    assert by_map["camera_ready_scope_boundaries_error"] is None


def test_camera_ready_scope_boundary_node_reports_missing_and_invalid_payload() -> None:
    missing = camera_ready_scope_boundary_node(
        {
            "camera_ready_scope_boundaries": [
                name for name in CAMERA_READY_SCOPE_BOUNDARIES if name != "input_writer_node"
            ]
        }
    )
    assert missing["camera_ready_scope_boundaries_valid"] is False
    assert missing["camera_ready_scope_boundaries_missing"] == ["input_writer_node"]
    assert "missing camera-ready scope boundaries" in missing["camera_ready_scope_boundaries_error"]

    invalid = camera_ready_scope_boundary_node({"camera_ready_scope_boundaries": "bad"})
    assert invalid["camera_ready_scope_boundaries_valid"] is False
    assert len(invalid["camera_ready_scope_boundaries_missing"]) == len(CAMERA_READY_SCOPE_BOUNDARIES)
    assert "must be list, tuple, set, or dict" in invalid["camera_ready_scope_boundaries_error"]


def test_route_after_camera_ready_scope_boundaries() -> None:
    assert (
        _route_after_camera_ready_scope_boundaries(
            {"camera_ready_scope_boundaries_valid": True}
        )
        == "intent_extraction_node"
    )
    assert (
        _route_after_camera_ready_scope_boundaries(
            {"camera_ready_scope_boundaries_valid": False}
        )
        == "clarification_handler"
    )
    assert _route_after_camera_ready_scope_boundaries({}) == "clarification_handler"


def test_required_outputs_helpers_and_routes() -> None:
    assert get_required_outputs_section() == REQUIRED_OUTPUTS_SECTION
    assert _route_after_required_outputs({"required_outputs_valid": True}) == "camera_ready_scope_boundary_node"
    assert _route_after_required_outputs({"required_outputs_valid": False}) == "clarification_handler"

    assert _latest_architect_details({}) is None
    assert _latest_architect_details({"workflow_history": "bad"}) is None
    assert _latest_architect_details({"workflow_history": [{"node": "architect"}]}) is None
    assert _latest_architect_details(
        {
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "old", "modifications": []}},
                {"node": "architect", "details": {"selected_case": "new", "modifications": ["m1"]}},
            ]
        }
    ) == {"selected_case": "new", "modifications": ["m1"]}

    ok = required_outputs_section_node({"selected_case": "Exec/Flame", "modifications": []})
    assert ok["required_outputs_valid"] is True
    assert ok["required_outputs_error"] is None

    missing = required_outputs_section_node({})
    assert missing["required_outputs_valid"] is False
    assert missing["required_outputs_missing"] == ["selected_case", "modifications"]
    assert "missing required outputs" in missing["required_outputs_error"]

    bad_mods = required_outputs_section_node(
        {"selected_case": "Exec/Flame", "modifications": "not-list"}
    )
    assert bad_mods["required_outputs_valid"] is False
    assert "modifications must be a list" in bad_mods["required_outputs_error"]

    mismatch = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": ["m1"],
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {"selected_case": "case-b", "modifications": ["m2"]},
                }
            ],
        }
    )
    assert mismatch["required_outputs_valid"] is False
    assert "selected_case mismatch" in mismatch["required_outputs_error"]
    assert "modifications mismatch" in mismatch["required_outputs_error"]


def test_route_helpers_and_placeholder_nodes(capsys: pytest.CaptureFixture[str]) -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
    assert _route_after_sweep_detection({}) == "architect_node"
    assert _route_after_radon_cc_gate({"radon_cc_valid": True}) == "input_writer_node"
    assert _route_after_radon_cc_gate({"radon_cc_valid": False}) == "clarification_handler"
    assert _route_after_radon_cc_gate({}) == "clarification_handler"

    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"
    assert _route_after_manifest_validation({"paper_manifest_valid": True}) == "radon_cc_gate_node"
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

    clarification_state = {"clarification_questions": ["Need CFL?"]}
    sweep_state = {"sweep_id": "s1", "sweep_parameter": "amr.n_cell"}
    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state
    out = capsys.readouterr().out
    assert "Clarification needed" in out
    assert "Sweep detected" in out


def test_critical_path_features_section_node_paths() -> None:
    assert get_critical_path_features_section() == CRITICAL_PATH_FEATURES_SECTION

    default_result = critical_path_features_section_node({})
    assert default_result["critical_path_features_valid"] is True
    assert default_result["critical_path_features_missing"] == []

    map_result = critical_path_features_section_node(
        {"critical_path_features": {name: True for name in CRITICAL_PATH_FEATURES_SECTION}}
    )
    assert map_result["critical_path_features_valid"] is True

    missing_result = critical_path_features_section_node(
        {
            "critical_path_features": [
                name for name in CRITICAL_PATH_FEATURES_SECTION if name != "architect_node"
            ]
        }
    )
    assert missing_result["critical_path_features_valid"] is False
    assert missing_result["critical_path_features_missing"] == ["architect_node"]

    invalid_result = critical_path_features_section_node({"critical_path_features": "bad"})
    assert invalid_result["critical_path_features_valid"] is False
    assert "must be list, tuple, set, or dict" in invalid_result["critical_path_features_error"]


def test_manifest_and_radon_gate_paths() -> None:
    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert _is_paper_validator_enabled({"config": object()}) is False
    assert _is_paper_validator_enabled({}) is False

    bypass = paper_manifest_gate_node({})
    assert bypass["paper_manifest_valid"] is True
    assert bypass["paper_manifest_error"] is None

    missing_manifest = paper_manifest_gate_node({"paper_validator_enabled": True})
    assert missing_manifest["paper_manifest_valid"] is False
    assert "required" in missing_manifest["paper_manifest_error"]

    invalid_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {"document_id": 123, "checks": "bad"},
        }
    )
    assert invalid_manifest["paper_manifest_valid"] is False
    assert invalid_manifest["paper_manifest_error"]

    blocking_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-049",
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
    assert blocking_manifest["paper_manifest_valid"] is False
    assert "blocking failures" in blocking_manifest["paper_manifest_error"]

    manifest = PaperValidationManifest(
        document_id="paper-049-model",
        checks=[ValidationCheckResult(check_id="c1", title="ok", status="pass")],
    )
    accepted_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": manifest,
        }
    )
    assert accepted_manifest["paper_manifest_valid"] is True
    assert accepted_manifest["paper_manifest_error"] is None
    assert accepted_manifest["paper_validation_manifest"]["document_id"] == "paper-049-model"

    assert evaluate_radon_cc_threshold(radon_available=False, flagged_functions=[]) == {
        "valid": False,
        "error": "radon is not installed",
        "offenders": [],
    }
    assert (
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions={"bad": "type"},  # type: ignore[arg-type]
        )["error"]
        == "radon_cc_functions must be a list of mappings"
    )
    assert (
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions=[123],  # type: ignore[list-item]
        )["error"]
        == "radon_cc_functions entries must be mappings"
    )

    passing_eval = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[
            {"name": "f", "complexity": "10"},
            {"name": "f2", "complexity": 10.0},
            {"name": "skip-bool", "complexity": True},
            {"name": "skip-float", "complexity": 10.2},
            {"name": "skip-text", "complexity": "not-a-number"},
        ],
    )
    assert passing_eval["valid"] is True
    assert passing_eval["offenders"] == []

    failing_eval = evaluate_radon_cc_threshold(
        radon_available=True,
        flagged_functions=[{"name": "hard_fn", "complexity": 11}],
    )
    assert failing_eval["valid"] is False
    assert failing_eval["error"] == "functions exceed complexity threshold"
    assert failing_eval["offenders"] == [{"name": "hard_fn", "complexity": 11}]

    with pytest.raises(ValueError, match="non-negative"):
        evaluate_radon_cc_threshold(
            radon_available=True,
            flagged_functions=[],
            max_complexity=-1,
        )

    bypass_radon = radon_cc_gate_node({})
    assert bypass_radon["radon_cc_valid"] is True
    assert bypass_radon["radon_cc_offenders"] == []

    enforced_radon_ok = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "fn_ok", "complexity": 7}],
        }
    )
    assert enforced_radon_ok["radon_cc_valid"] is True
    assert enforced_radon_ok["radon_cc_error"] is None

    enforced_radon_bad = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "fn_bad", "complexity": 12}],
        }
    )
    assert enforced_radon_bad["radon_cc_valid"] is False
    assert enforced_radon_bad["radon_cc_offenders"] == [{"name": "fn_bad", "complexity": 12}]


def test_create_graph_compiles_with_camera_ready_scope_gate() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()

    nodes = set(graph_def.nodes.keys())
    assert "required_outputs_section_node" in nodes
    assert "camera_ready_scope_boundary_node" in nodes
    assert "paper_manifest_gate_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("required_outputs_section_node", "camera_ready_scope_boundary_node") in edges
    assert ("required_outputs_section_node", "clarification_handler") in edges
    assert ("camera_ready_scope_boundary_node", "intent_extraction_node") in edges
    assert ("camera_ready_scope_boundary_node", "clarification_handler") in edges
    assert ("clarification_node", "paper_manifest_gate_node") in edges
