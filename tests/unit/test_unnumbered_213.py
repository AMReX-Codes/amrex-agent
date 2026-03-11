"""Session 117: UNNUMBERED-213 cache hit-rate benchmark observability tests."""

from __future__ import annotations

from src.graph import (
    BENCHMARK_CACHE_HIT_RATE_MARKER,
    CLAIMS_RESULTS_ARTIFACTS_MARKER,
    CROSS_REFERENCE_FEATURE_IDS_MARKER,
    PHASE1_FEATURE_TRACE_MARKER,
    REQUIRED_BEHAVIOR_MARKER,
    _compute_benchmark_cache_hit_rate,
    _has_benchmark_cache_hit_rate,
    _has_claims_results_artifacts,
    _has_cross_reference_feature_ids,
    _has_phase1_feature_trace,
    _has_required_behavior_item,
    _is_results_artifact_path,
    _paper_validator_enabled,
    _route_after_benchmark_cache_hit_rate,
    _route_after_claims_results_artifacts,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_cross_reference_feature_ids,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_post_incident_risk_matrix_feedback,
    _route_after_postgresql_migration_evidence,
    _route_after_required_behavior_item,
    _route_after_sweep_detection,
    benchmark_cache_hit_rate_handler_node,
    claims_results_artifacts_handler_node,
    clarification_handler_node,
    complexity_evidence_handler_node,
    complexity_evidence_node,
    create_graph,
    cross_reference_feature_ids_handler_node,
    paper_validator_node,
    phase1_traceability_handler_node,
    post_incident_risk_matrix_feedback_handler_node,
    postgresql_migration_handler_node,
    required_behavior_handler_node,
    session_dependency_handler_node,
    sweep_execution_handler_node,
)
from src.services.workflow_store import POSTGRESQL_MIGRATION_EVIDENCE_MARKER
from src.session_manager import B1_SESSION_COMPLETION_MARKER
from src.utils.metrics import POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER


def test_unnumbered_213_cache_hit_rate_helpers_and_routes(monkeypatch):
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _compute_benchmark_cache_hit_rate({BENCHMARK_CACHE_HIT_RATE_MARKER: 0.5}) == 0.5
    assert _compute_benchmark_cache_hit_rate({BENCHMARK_CACHE_HIT_RATE_MARKER: "0.25"}) == 0.25
    assert _compute_benchmark_cache_hit_rate({BENCHMARK_CACHE_HIT_RATE_MARKER: 1.2}) is None
    assert _compute_benchmark_cache_hit_rate({"cache_hit_rate": 0.4}) == 0.4
    assert _compute_benchmark_cache_hit_rate({"embedding_cache_hit_rate": 0.7}) == 0.7

    assert _compute_benchmark_cache_hit_rate({"benchmark_cache_stats": {"hits": 8, "misses": 2}}) == 0.8
    assert _compute_benchmark_cache_hit_rate({"embedding_cache_stats": {"cache_hits": 3, "total": 10}}) == 0.3
    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": 5, "requests": 20}}) == 0.25
    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": 5, "lookups": 25}}) == 0.2
    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": 5, "cache_misses": 5}}) == 0.5

    history_state = {
        "workflow_history": [
            "not-a-dict",
            {"node": "architect", "details": "not-a-dict"},
            {"node": "architect", "details": {"cache_stats": {"hits": 9, "misses": 1}}}
        ]
    }
    assert _compute_benchmark_cache_hit_rate(history_state) == 0.9

    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": -1, "misses": 1}}) is None
    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": 3, "total": 0}}) is None
    assert _compute_benchmark_cache_hit_rate({"cache_stats": {"hits": 8, "total": 4}}) is None
    assert _has_benchmark_cache_hit_rate({"cache_stats": {"hits": 4, "misses": 1}}) is True
    assert _has_benchmark_cache_hit_rate({}) is False

    assert _route_after_benchmark_cache_hit_rate({}) == "end"
    assert _route_after_benchmark_cache_hit_rate({"enforce_benchmark_cache_hit_rate": True}) == "benchmark_cache_hit_rate_handler"
    assert (
        _route_after_benchmark_cache_hit_rate(
            {
                "enforce_benchmark_cache_hit_rate": True,
                "cache_stats": {"hits": 7, "misses": 3},
            }
        )
        == "end"
    )

    assert _route_after_required_behavior_item({}) == "end"
    assert (
        _route_after_required_behavior_item({"enforce_benchmark_cache_hit_rate": True})
        == "benchmark_cache_hit_rate_handler"
    )
    assert (
        _route_after_required_behavior_item(
            {
                "enforce_required_behavior_item": True,
                REQUIRED_BEHAVIOR_MARKER: "must include evidence",
                "enforce_benchmark_cache_hit_rate": True,
                "benchmark_cache_stats": {"hits": 2, "misses": 2},
            }
        )
        == "end"
    )

    unchanged = complexity_evidence_node({"enforce_radon_complexity_evidence": False})
    assert BENCHMARK_CACHE_HIT_RATE_MARKER not in unchanged

    with_cache = complexity_evidence_node(
        {
            "enforce_radon_complexity_evidence": False,
            "benchmark_cache_stats": {"hits": 6, "misses": 2},
        }
    )
    assert with_cache[BENCHMARK_CACHE_HIT_RATE_MARKER] == 0.75

    with_cache_and_radon = complexity_evidence_node(
        {
            "enforce_radon_complexity_evidence": True,
            "benchmark_cache_stats": {"hits": 3, "misses": 1},
        }
    )
    assert with_cache_and_radon[BENCHMARK_CACHE_HIT_RATE_MARKER] == 0.75
    assert with_cache_and_radon["radon_complexity_evidence"]["radon_available"] is False
    assert (
        complexity_evidence_node(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
                "benchmark_cache_stats": {"hits": 1, "misses": 1},
            }
        )["radon_complexity_evidence"]["radon_available"]
        is True
    )

    handler = benchmark_cache_hit_rate_handler_node({})
    assert handler["required_marker"] == BENCHMARK_CACHE_HIT_RATE_MARKER
    assert "cache hit rate" in handler["dependency_error"]


def test_unnumbered_213_graph_gate_and_routes(monkeypatch):
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _is_results_artifact_path("results/run_001/summary.json") is True
    assert _is_results_artifact_path("benchmark_results/20260310/metrics.jsonl") is True
    assert _is_results_artifact_path("./results/sub/path.csv") is True
    assert _is_results_artifact_path("output/benchmarks/results.json") is False

    assert _has_claims_results_artifacts({}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"": "results/a.json"}}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": []}}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": ["results/a.json", 7]}}) is False
    assert (
        _has_claims_results_artifacts(
            {CLAIMS_RESULTS_ARTIFACTS_MARKER: {"claim_1": ["results/a.json", "benchmark_results/b.json"]}}
        )
        is True
    )

    assert _paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _paper_validator_enabled({"paper_source": "2401.12345"}) is True
    assert _paper_validator_enabled({}) is False

    assert _route_after_paper_validator({}) == "input_writer_node"
    assert _route_after_paper_validator({"paper_validator_enabled": True}) == "paper_validator_node"
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({}) == "input_writer_node"

    assert _route_after_sweep_detection({}) == "architect_node"
    assert _route_after_sweep_detection({"sweep_id": "sweep"}) == "session_dependency_handler"
    assert _route_after_sweep_detection(
        {"sweep_id": "sweep", "session_markers": {B1_SESSION_COMPLETION_MARKER: True}}
    ) == "sweep_execution_handler"

    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": "F1.1"}}) is True
    assert _has_phase1_feature_trace({}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"BAD": ["F1.1"]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": 1}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False

    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "must be true"}) is True
    assert _has_required_behavior_item({}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ""}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: []}) is False

    assert _has_cross_reference_feature_ids({CROSS_REFERENCE_FEATURE_IDS_MARKER: {"SEC-1": "F2A"}}) is True
    assert _has_cross_reference_feature_ids({}) is False
    assert _has_cross_reference_feature_ids({CROSS_REFERENCE_FEATURE_IDS_MARKER: {"": "F2A"}}) is False

    assert _route_after_post_incident_risk_matrix_feedback({}) == "end"
    assert (
        _route_after_post_incident_risk_matrix_feedback({"enforce_post_incident_risk_matrix_feedback": True})
        == "post_incident_risk_matrix_feedback_handler"
    )
    assert (
        _route_after_post_incident_risk_matrix_feedback(
            {
                "enforce_post_incident_risk_matrix_feedback": True,
                POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER: [
                    {
                        "incident_id": "INC-1",
                        "risk_id": "R-1",
                        "owner": "team",
                        "update_summary": "updated matrix",
                        "mitigation_evidence_ref": "results/inc-1.md",
                        "reviewed_at": "2026-03-10",
                    }
                ],
            }
        )
        == "end"
    )

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
                    "migration_runbook_ref": "docs/postgresql_migration.md",
                    "index_growth_proof_ref": "artifacts/index_growth.json",
                },
            }
        )
        == "end"
    )

    assert _route_after_cross_reference_feature_ids({}) == "end"
    assert (
        _route_after_cross_reference_feature_ids({"enforce_cross_reference_feature_ids": True})
        == "cross_reference_feature_ids_handler"
    )

    assert _route_after_claims_results_artifacts({}) == "end"
    assert (
        _route_after_claims_results_artifacts({"enforce_claims_results_artifacts": True})
        == "claims_results_artifacts_handler"
    )

    assert _route_after_phase1_traceability({}) == "end"
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )

    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
            }
        )
        == "end"
    )
    assert (
        _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True})
        == "complexity_evidence_handler"
    )

    assert session_dependency_handler_node({})["required_marker"] == B1_SESSION_COMPLETION_MARKER

    complexity_handler = complexity_evidence_handler_node({})
    assert complexity_handler["required_marker"] == "radon_complexity_evidence"

    phase1_handler = phase1_traceability_handler_node({})
    assert phase1_handler["required_marker"] == PHASE1_FEATURE_TRACE_MARKER

    required_handler = required_behavior_handler_node({})
    assert required_handler["required_marker"] == REQUIRED_BEHAVIOR_MARKER

    claims_handler = claims_results_artifacts_handler_node({})
    assert claims_handler["required_marker"] == CLAIMS_RESULTS_ARTIFACTS_MARKER

    cross_ref_handler = cross_reference_feature_ids_handler_node({})
    assert cross_ref_handler["required_marker"] == CROSS_REFERENCE_FEATURE_IDS_MARKER

    postgres_handler = postgresql_migration_handler_node({})
    assert postgres_handler["required_marker"] == POSTGRESQL_MIGRATION_EVIDENCE_MARKER

    post_incident_handler = post_incident_risk_matrix_feedback_handler_node({})
    assert post_incident_handler["required_marker"] == POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {
        "clarification_questions": ["q1"]
    }
    assert sweep_execution_handler_node({"sweep_id": "swp", "sweep_parameter": "amr.n_cell"}) == {
        "sweep_id": "swp",
        "sweep_parameter": "amr.n_cell",
    }
    assert paper_validator_node({"paper_source": "x"}) == {"paper_source": "x"}

    graph = create_graph()
    compiled = graph.compile()
    assert compiled is not None
