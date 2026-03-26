"""Session 134 tests for UNNUMBERED-254 concurrency limits documentation."""

from __future__ import annotations

from pathlib import Path
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
    _route_after_risk_links_traceability,
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
    risk_links_traceability_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult


def test_prd_documents_concurrency_limits_for_three_to_five_users() -> None:
    prd_path = Path("docs/PRD/PRD_v2605.md")
    content = prd_path.read_text(encoding="utf-8")

    assert "Concurrency limits documented for 3-5 users" in content
    assert "hard upper bound: 5 active sessions per node" in content
    assert "Maximum supported active sessions per node: 5." in content
    assert "If active sessions exceed 5" in content
    assert "PRAGMA journal_mode=WAL" in content
    assert "6th-session overload probe" in content


def test_required_sections_and_lists_are_exposed() -> None:
    assert get_required_outputs_section() == REQUIRED_OUTPUTS_SECTION
    assert get_critical_path_features_section() == CRITICAL_PATH_FEATURES_SECTION
    assert get_camera_ready_scope_boundaries() == CAMERA_READY_SCOPE_BOUNDARIES
    assert "input_writer_node" in CRITICAL_PATH_FEATURES_SECTION
    assert "radon_cc_gate_node" in CAMERA_READY_SCOPE_BOUNDARIES


def test_route_helpers_cover_success_and_failure_branches() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"

    assert _route_after_sweep_detection({"sweep_id": "sweep-1"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({}) == "architect_node"

    assert _route_after_required_outputs({"required_outputs_valid": True}) == "camera_ready_scope_boundary_node"
    assert _route_after_required_outputs({"required_outputs_valid": False}) == "clarification_handler"

    assert (
        _route_after_camera_ready_scope_boundaries({"camera_ready_scope_boundaries_valid": True})
        == "intent_extraction_node"
    )
    assert (
        _route_after_camera_ready_scope_boundaries({"camera_ready_scope_boundaries_valid": False})
        == "clarification_handler"
    )

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

    assert _route_after_radon_cc_gate({"radon_cc_valid": True}) == "risk_links_traceability_node"
    assert _route_after_radon_cc_gate({"radon_cc_valid": False}) == "clarification_handler"

    assert _route_after_risk_links_traceability({"risk_links_valid": True}) == "input_writer_node"
    assert _route_after_risk_links_traceability({"risk_links_valid": False}) == "clarification_handler"


def test_latest_architect_and_required_outputs_validation_paths() -> None:
    assert _latest_architect_details({}) is None
    assert _latest_architect_details({"workflow_history": "bad"}) is None
    assert _latest_architect_details({"workflow_history": [{"node": "architect"}]}) is None

    details = _latest_architect_details(
        {
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "old", "modifications": []}},
                {"node": "architect", "details": {"selected_case": "new", "modifications": ["m1"]}},
            ]
        }
    )
    assert details == {"selected_case": "new", "modifications": ["m1"]}

    valid = required_outputs_section_node({"selected_case": "case", "modifications": []})
    assert valid["required_outputs_valid"] is True
    assert valid["required_outputs_error"] is None

    missing = required_outputs_section_node({})
    assert missing["required_outputs_valid"] is False
    assert missing["required_outputs_missing"] == ["selected_case", "modifications"]
    assert "missing required outputs" in missing["required_outputs_error"]

    bad_mods = required_outputs_section_node({"selected_case": "case", "modifications": "bad"})
    assert bad_mods["required_outputs_valid"] is False
    assert "modifications must be a list" in bad_mods["required_outputs_error"]

    mismatch = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": ["m1"],
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "case-b", "modifications": ["m2"]}}
            ],
        }
    )
    assert mismatch["required_outputs_valid"] is False
    assert "selected_case mismatch" in mismatch["required_outputs_error"]
    assert "modifications mismatch" in mismatch["required_outputs_error"]


def test_critical_path_and_camera_ready_nodes_validate_inputs() -> None:
    default_critical = critical_path_features_section_node({})
    assert default_critical["critical_path_features_valid"] is True

    partial_critical = critical_path_features_section_node(
        {"critical_path_features": ["architect_node", "input_writer_node"]}
    )
    assert partial_critical["critical_path_features_valid"] is False
    assert "sweep_detection_node" in partial_critical["critical_path_features_missing"]

    bad_critical = critical_path_features_section_node({"critical_path_features": "bad"})
    assert bad_critical["critical_path_features_valid"] is False
    assert "must be list" in bad_critical["critical_path_features_error"]

    default_scope = camera_ready_scope_boundary_node({})
    assert default_scope["camera_ready_scope_boundaries_valid"] is True

    partial_scope = camera_ready_scope_boundary_node(
        {"camera_ready_scope_boundaries": ["architect_node", "input_writer_node"]}
    )
    assert partial_scope["camera_ready_scope_boundaries_valid"] is False
    assert "intent_extraction_node" in partial_scope["camera_ready_scope_boundaries_missing"]

    bad_scope = camera_ready_scope_boundary_node({"camera_ready_scope_boundaries": "bad"})
    assert bad_scope["camera_ready_scope_boundaries_valid"] is False
    assert "must be list" in bad_scope["camera_ready_scope_boundaries_error"]


def test_manifest_and_radon_gates_cover_enabled_and_disabled_paths() -> None:
    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert _is_paper_validator_enabled({"config": object()}) is False

    bypass_manifest = paper_manifest_gate_node({})
    assert bypass_manifest["paper_manifest_valid"] is True
    assert bypass_manifest["paper_manifest_error"] is None

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

    blocking_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-254",
                "checks": [
                    {"check_id": "c1", "title": "critical", "status": "fail", "blocking": True}
                ],
            },
        }
    )
    assert blocking_manifest["paper_manifest_valid"] is False
    assert "blocking failures" in blocking_manifest["paper_manifest_error"]

    accepted_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": PaperValidationManifest(
                document_id="paper-254-model",
                checks=[ValidationCheckResult(check_id="c1", title="ok", status="pass")],
            ),
        }
    )
    assert accepted_manifest["paper_manifest_valid"] is True
    assert accepted_manifest["paper_validation_manifest"]["document_id"] == "paper-254-model"

    bypass_radon = radon_cc_gate_node({})
    assert bypass_radon["radon_cc_valid"] is True
    assert bypass_radon["radon_cc_offenders"] == []

    fail_radon = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "f", "complexity": 12}],
        }
    )
    assert fail_radon["radon_cc_valid"] is False

    pass_radon = radon_cc_gate_node(
        {
            "radon_cc_gate_enabled": True,
            "radon_available": True,
            "radon_cc_functions": [{"name": "f", "complexity": 5}],
        }
    )
    assert pass_radon["radon_cc_valid"] is True


def test_traceability_and_placeholder_handlers(capsys: pytest.CaptureFixture[str]) -> None:
    valid_trace = risk_links_traceability_node(
        {"risk_links": [{"risk_id": "R-1", "mitigation": "x", "validation_artifact": "ci:test"}]}
    )
    assert valid_trace["risk_links_valid"] is True

    invalid_trace = risk_links_traceability_node({"risk_register": [{"risk_id": "R-2"}]})
    assert invalid_trace["risk_links_valid"] is False

    clarification_state = {"clarification_questions": ["Need Reynolds number?"]}
    sweep_state = {"sweep_id": "sweep-1", "sweep_parameter": "amr.n_cell"}
    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state

    captured = capsys.readouterr()
    assert "Clarification needed" in captured.out
    assert "Sweep detected" in captured.out


def test_create_graph_compiles_with_expected_edges() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()

    nodes = set(graph_def.nodes.keys())
    assert "required_outputs_section_node" in nodes
    assert "camera_ready_scope_boundary_node" in nodes
    assert "paper_manifest_gate_node" in nodes
    assert "radon_cc_gate_node" in nodes
    assert "risk_links_traceability_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("architect_node", "required_outputs_section_node") in edges
    assert ("required_outputs_section_node", "camera_ready_scope_boundary_node") in edges
    assert ("required_outputs_section_node", "clarification_handler") in edges
    assert ("camera_ready_scope_boundary_node", "intent_extraction_node") in edges
    assert ("camera_ready_scope_boundary_node", "clarification_handler") in edges
    assert ("clarification_node", "paper_manifest_gate_node") in edges
    assert ("paper_manifest_gate_node", "radon_cc_gate_node") in edges
    assert ("paper_manifest_gate_node", "clarification_handler") in edges
    assert ("radon_cc_gate_node", "risk_links_traceability_node") in edges
    assert ("radon_cc_gate_node", "clarification_handler") in edges
    assert ("risk_links_traceability_node", "input_writer_node") in edges
    assert ("risk_links_traceability_node", "clarification_handler") in edges
