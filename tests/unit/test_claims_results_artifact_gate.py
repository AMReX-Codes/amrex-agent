"""Claims-to-results-artifacts gate tests."""

from __future__ import annotations

from src.graph import (
    CLAIMS_RESULTS_ARTIFACTS_MARKER,
    PHASE1_FEATURE_TRACE_MARKER,
    REQUIRED_BEHAVIOR_MARKER,
    _has_claims_results_artifacts,
    _has_phase1_feature_trace,
    _has_required_behavior_item,
    _is_results_artifact_path,
    _paper_validator_enabled,
    _route_after_claims_results_artifacts,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_postgresql_migration_evidence,
    _route_after_required_behavior_item,
    _route_after_sweep_detection,
    claims_results_artifacts_handler_node,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    paper_validator_node,
    phase1_traceability_handler_node,
    postgresql_migration_handler_node,
    required_behavior_handler_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.services.workflow_store import POSTGRESQL_MIGRATION_EVIDENCE_MARKER
from src.session_manager import SESSION_DEPENDENCY_COMPLETION_MARKER


def test_claims_results_artifacts_gate_and_graph_routes(monkeypatch):
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _is_results_artifact_path("results/run_001/summary.json") is True
    assert _is_results_artifact_path("benchmark_results/20260310/metrics.jsonl") is True
    assert _is_results_artifact_path("./results/sub/path.csv") is True
    assert _is_results_artifact_path("output/benchmarks/results.json") is False
    assert _is_results_artifact_path("benchmark/runs/metrics.jsonl") is False

    assert _has_claims_results_artifacts({}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: []}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {}}) is False
    assert (
        _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"": "results/a.json"}})
        is False
    )
    assert (
        _has_claims_results_artifacts(
            {CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": "benchmark/runs/a.json"}}
        )
        is False
    )
    assert (
        _has_claims_results_artifacts(
            {CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": ["results/a.json", 7]}}
        )
        is False
    )
    assert (
        _has_claims_results_artifacts(
            {CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": ["results/a.json", "benchmark_results/b.json"]}}
        )
        is True
    )

    assert _paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_enabled({"paper_source": "2401.12345"}) is True
    assert _paper_validator_enabled({}) is False

    assert _route_after_paper_validator({"paper_validator_enabled": True}) == "paper_validator_node"
    assert _route_after_paper_validator({}) == "input_writer_node"

    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"paper_source": "paper"}) == "paper_validator_node"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({}) == "architect_node"
    assert _route_after_sweep_detection({"sweep_id": "sweep"}) == "session_dependency_handler"
    assert _route_after_sweep_detection(
        {"sweep_id": "sweep", "session_markers": {SESSION_DEPENDENCY_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _has_phase1_feature_trace({}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: "invalid"}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"BAD": ["F1.1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": [1]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"}}) is True
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC2": ["F2B", "F6.2"]}}) is True

    assert _has_required_behavior_item({}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ""}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "   "}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: 1}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: []}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["ok", ""]}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "must be true"}) is True
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["must", "be true"]}) is True

    assert _route_after_postgresql_migration_evidence({}) == "end"
    assert (
        _route_after_postgresql_migration_evidence({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_postgresql_migration_evidence(
            {
                "enforce_postgresql_migration_evidence": True,
                POSTGRESQL_MIGRATION_EVIDENCE_MARKER: {
                    "migration_runbook_ref": "docs/runbook.md",
                    "index_growth_proof_ref": "artifacts/index-growth.json",
                },
            }
        )
        == "end"
    )

    assert _route_after_claims_results_artifacts({}) == "end"
    assert (
        _route_after_claims_results_artifacts({"enforce_claims_results_artifacts": True})
        == "claims_results_artifacts_handler"
    )
    assert (
        _route_after_claims_results_artifacts(
            {
                "enforce_claims_results_artifacts": True,
                CLAIMS_RESULTS_ARTIFACTS_MARKER: {
                    "claim_1": ["results/run_001/summary.json"],
                },
                "enforce_postgresql_migration_evidence": True,
            }
        )
        == "postgresql_migration_handler"
    )

    assert _route_after_required_behavior_item({}) == "end"
    assert (
        _route_after_required_behavior_item({"enforce_claims_results_artifacts": True})
        == "claims_results_artifacts_handler"
    )
    assert (
        _route_after_required_behavior_item({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_required_behavior_item({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_required_behavior_item(
            {
                "enforce_required_behavior_item": True,
                REQUIRED_BEHAVIOR_MARKER: "must be true",
                "enforce_claims_results_artifacts": True,
                CLAIMS_RESULTS_ARTIFACTS_MARKER: {
                    "claim_1": ["benchmark_results/20260310/table.csv"]
                },
            }
        )
        == "end"
    )

    assert _route_after_phase1_traceability({}) == "end"
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_phase1_traceability(
            {
                "enforce_phase1_feature_trace": True,
                PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"},
                "enforce_claims_results_artifacts": True,
            }
        )
        == "claims_results_artifacts_handler"
    )

    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence({"enforce_postgresql_migration_evidence": True})
        == "postgresql_migration_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_claims_results_artifacts": True})
        == "claims_results_artifacts_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True})
        == "complexity_evidence_handler"
    )
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
                "enforce_claims_results_artifacts": True,
                CLAIMS_RESULTS_ARTIFACTS_MARKER: {
                    "claim_1": ["results/run_001/summary.json"]
                },
            }
        )
        == "end"
    )

    assert session_dependency_handler_node({})["required_marker"] == SESSION_DEPENDENCY_COMPLETION_MARKER

    enforced = complexity_evidence_node({"enforce_radon_complexity_evidence": True})
    assert enforced["radon_complexity_evidence"]["radon_available"] is False

    unchanged = complexity_evidence_node({"enforce_radon_complexity_evidence": False})
    assert "radon_complexity_evidence" not in unchanged

    existing = complexity_evidence_node(
        {
            "enforce_radon_complexity_evidence": True,
            "radon_complexity_evidence": {"radon_available": True},
        }
    )
    assert existing["radon_complexity_evidence"]["radon_available"] is True

    complexity_handler = complexity_evidence_handler_node({})
    assert complexity_handler["required_marker"] == "radon_complexity_evidence"
    assert "Radon complexity evidence" in complexity_handler["dependency_error"]

    phase1_handler = phase1_traceability_handler_node({})
    assert phase1_handler["required_marker"] == PHASE1_FEATURE_TRACE_MARKER
    assert "traceability is required" in phase1_handler["dependency_error"]

    required_handler = required_behavior_handler_node({})
    assert required_handler["required_marker"] == REQUIRED_BEHAVIOR_MARKER
    assert "required behavior item is required" in required_handler["dependency_error"]

    claims_handler = claims_results_artifacts_handler_node({})
    assert claims_handler["required_marker"] == CLAIMS_RESULTS_ARTIFACTS_MARKER
    assert "Claims must map to results artifacts" in claims_handler["dependency_error"]

    claims_existing = claims_results_artifacts_handler_node(
        {"required_marker": "existing_marker", "dependency_error": "existing"}
    )
    assert claims_existing["required_marker"] == "existing_marker"
    assert claims_existing["dependency_error"] == "existing"

    postgres_handler = postgresql_migration_handler_node({})
    assert postgres_handler["required_marker"] == POSTGRESQL_MIGRATION_EVIDENCE_MARKER
    assert "PostgreSQL migration runbook and index growth proof" in postgres_handler["dependency_error"]
    assert postgres_handler[POSTGRESQL_MIGRATION_EVIDENCE_MARKER]["proof_complete"] is False

    existing_postgres = postgresql_migration_handler_node(
        {
            "dependency_error": "existing",
            "required_marker": "existing_marker",
            POSTGRESQL_MIGRATION_EVIDENCE_MARKER: {
                "migration_runbook_ref": "docs/migration.md",
                "index_growth_proof_ref": "artifacts/proof.json",
                "proof_complete": True,
            },
        }
    )
    assert existing_postgres["dependency_error"] == "existing"
    assert existing_postgres["required_marker"] == "existing_marker"
    assert existing_postgres[POSTGRESQL_MIGRATION_EVIDENCE_MARKER]["proof_complete"] is True

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {
        "clarification_questions": ["q1"]
    }
    assert sweep_execution_handler_node({"sweep_id": "id", "sweep_parameter": "p"})["sweep_id"] == "id"
    state = {"x": 1}
    assert paper_validator_node(state) is state

    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}

    assert ("complexity_evidence_node", "claims_results_artifacts_handler") in edges
    assert ("claims_results_artifacts_handler", "__end__") in edges
    assert ("complexity_evidence_node", "postgresql_migration_handler") in edges
    assert ("postgresql_migration_handler", "__end__") in edges
