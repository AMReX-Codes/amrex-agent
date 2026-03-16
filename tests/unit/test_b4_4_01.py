"""Session 9 tests for B4.4 validation manifest schema and graph wiring."""

from __future__ import annotations

import pytest

from src.graph import (
    _is_paper_validator_enabled,
    _route_after_clarification,
    _route_after_manifest_validation,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    paper_manifest_gate_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import (
    ManifestSummary,
    PaperValidationManifest,
    ValidationCheckResult,
)


def test_manifest_auto_summary_builds_from_checks() -> None:
    manifest = PaperValidationManifest(
        document_id="paper-001",
        checks=[
            ValidationCheckResult(check_id="c1", title="format", status="pass"),
            ValidationCheckResult(check_id="c2", title="range", status="warn"),
            ValidationCheckResult(
                check_id="c3",
                title="critical",
                status="fail",
                blocking=True,
            ),
        ],
    )

    assert manifest.summary is not None
    assert manifest.summary.total_checks == 3
    assert manifest.summary.pass_count == 1
    assert manifest.summary.warn_count == 1
    assert manifest.summary.fail_count == 1
    assert manifest.summary.blocking_failures == 1
    assert manifest.has_blocking_failures() is True


def test_manifest_rejects_summary_mismatch() -> None:
    with pytest.raises(ValueError, match="summary does not match"):
        PaperValidationManifest(
            document_id="paper-002",
            checks=[ValidationCheckResult(check_id="c1", title="format", status="pass")],
            summary=ManifestSummary(
                total_checks=1,
                pass_count=0,
                warn_count=0,
                fail_count=1,
                blocking_failures=0,
            ),
        )


def test_manifest_rejects_non_failed_blocking_check() -> None:
    with pytest.raises(ValueError, match="blocking can only be true"):
        ValidationCheckResult(
            check_id="c-bad",
            title="invalid",
            status="pass",
            blocking=True,
        )


def test_manifest_has_no_blocking_failures_when_only_warning() -> None:
    manifest = PaperValidationManifest(
        document_id="paper-003",
        checks=[ValidationCheckResult(check_id="c1", title="warn-only", status="warn")],
    )
    assert manifest.has_blocking_failures() is False


def test_route_after_existing_clarification_gate() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"


def test_route_after_existing_sweep_gate() -> None:
    assert _route_after_sweep_detection({"sweep_id": "sweep-01"}) == "sweep_execution_handler"
    assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"


def test_is_paper_validator_enabled_by_state_and_config() -> None:
    class ConfigEnabled:
        paper_validator_enabled = True

    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"paper_input_type": "arxiv"}) is True
    assert _is_paper_validator_enabled({"config": ConfigEnabled()}) is True
    assert _is_paper_validator_enabled({}) is False


def test_route_after_manifest_validation() -> None:
    assert _route_after_manifest_validation({"paper_manifest_valid": True}) == "input_writer_node"
    assert _route_after_manifest_validation({"paper_manifest_valid": False}) == "clarification_handler"


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
            "paper_validation_manifest": {"document_id": 12, "checks": "invalid"},
        }
    )
    assert result["paper_manifest_valid"] is False
    assert result["paper_manifest_error"]


def test_paper_manifest_gate_rejects_blocking_failures() -> None:
    result = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-004",
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


def test_paper_manifest_gate_accepts_model_instance() -> None:
    manifest = PaperValidationManifest(
        document_id="paper-005",
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
    assert result["paper_validation_manifest"]["document_id"] == "paper-005"


def test_placeholder_handler_nodes_return_state(capsys: pytest.CaptureFixture[str]) -> None:
    clarification_state = {"clarification_questions": ["Need Reynolds number?"]}
    sweep_state = {"sweep_id": "s1", "sweep_parameter": "amr.n_cell"}

    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state
    captured = capsys.readouterr()
    assert "Clarification needed" in captured.out
    assert "Sweep detected" in captured.out


def test_create_graph_compiles_with_manifest_gate_node() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()

    nodes = set(graph_def.nodes.keys())
    assert "paper_manifest_gate_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("clarification_node", "paper_manifest_gate_node") in edges
    assert ("paper_manifest_gate_node", "input_writer_node") in edges
    assert ("paper_manifest_gate_node", "clarification_handler") in edges
