"""Session 112: UNNUMBERED-189 post-incident risk matrix feedback tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import src.utils.metrics as metrics_mod
from src.graph import (
    CLAIMS_RESULTS_ARTIFACTS_MARKER,
    CROSS_REFERENCE_FEATURE_IDS_MARKER,
    PHASE1_FEATURE_TRACE_MARKER,
    REQUIRED_BEHAVIOR_MARKER,
    _has_claims_results_artifacts,
    _has_cross_reference_feature_ids,
    _has_phase1_feature_trace,
    _has_required_behavior_item,
    _is_results_artifact_path,
    _paper_validator_enabled,
    _route_after_claims_results_artifacts,
    _route_after_clarification,
    _route_after_complexity_evidence,
    _route_after_paper_validator,
    _route_after_phase1_traceability,
    _route_after_cross_reference_feature_ids,
    _route_after_post_incident_risk_matrix_feedback,
    _route_after_postgresql_migration_evidence,
    _route_after_required_behavior_item,
    _route_after_sweep_detection,
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
from src.utils.metrics import (
    POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER,
    collect_post_incident_risk_matrix_feedback,
    has_post_incident_risk_matrix_feedback,
    metrics_extra,
    metrics_context,
    normalize_unnumbered_143,
    normalize_unnumbered_189,
)


def test_unnumbered_189_metrics_feedback_pipeline() -> None:
    assert normalize_unnumbered_189(None) == []
    assert normalize_unnumbered_189("bad") == []
    assert normalize_unnumbered_189([1, "x"]) == []

    single = normalize_unnumbered_189(
        {
            "incident_id": " INC-1 ",
            "risk_id": " R-7 ",
            "owner": " team-a ",
            "update_summary": " tightened timeout policy ",
            "mitigation_evidence_ref": "results/inc-1.md",
            "reviewed_at": "2026-03-10",
            "ignored": "x",
        }
    )
    assert single == [
        {
            "incident_id": "INC-1",
            "risk_id": "R-7",
            "owner": "team-a",
            "update_summary": "tightened timeout policy",
            "mitigation_evidence_ref": "results/inc-1.md",
            "reviewed_at": "2026-03-10",
        }
    ]

    mixed = [
        {"incident_id": "INC-2", "risk_id": "R-8"},
        {
            "incident_id": "INC-3",
            "risk_id": "R-9",
            "owner": "team-b",
            "update_summary": "added retry budget",
            "mitigation_evidence_ref": "benchmark_results/inc-3.json",
            "reviewed_at": "2026-03-10T12:30:00Z",
        },
    ]
    assert has_post_incident_risk_matrix_feedback(mixed) is True
    assert has_post_incident_risk_matrix_feedback([{"incident_id": "INC-4"}]) is False

    collected = collect_post_incident_risk_matrix_feedback(
        {POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER: mixed}
    )
    assert collected["feedback_complete"] is True
    assert len(collected["feedback_records"]) == 2

    fallback = collect_post_incident_risk_matrix_feedback({"risk_matrix_feedback": mixed})
    assert fallback["feedback_complete"] is True

    empty = collect_post_incident_risk_matrix_feedback({})
    assert empty == {"feedback_records": [], "feedback_complete": False}

    assert normalize_unnumbered_143({"type": "evt"}, workflow_id="wf-1")["workflow_id"] == "wf-1"
    assert normalize_unnumbered_143({"workflow_id": "wf-existing"})["workflow_id"] == "wf-existing"


def test_unnumbered_189_metrics_collector_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    collector = metrics_mod.MetricsCollector()
    response = SimpleNamespace(model="m1", usage={"input_tokens": 4, "output_tokens": 5})

    with metrics_context("architect", node="planner", iteration=3, extra={"run": "r1"}):
        recorded = collector.record_llm_usage(response, provider="test")
        collector.record_event("retrieval_strategy", {"strategy": "hybrid"})
        collector.record_event("validation_metrics", {"schema_valid": True})
        collector.record_event("perf", {"latency_ms": 120, "concurrency": 2})
        collector.record_event(
            "perf",
            {"duration_ms": 620, "active_requests": 6, "p95_target_ms": 500, "max_concurrency": 4},
        )
    with metrics_extra({"batch": "b-1"}):
        collector.record_event("generic", {"ok": True}, stage="architect", node="planner", iteration=3)
    with metrics_extra(None):
        collector.record_event("generic", {}, stage="architect", node="planner", iteration=3)
    assert recorded is not None
    assert recorded["context"] == {"run": "r1"}
    assert recorded["data"]["total_tokens"] == 9

    summary = collector.summarize_stage("architect", iteration=3)
    assert summary["llm"]["total_calls"] == 1
    assert summary["retrieval"]["strategies"]["hybrid"] == 1
    assert summary["validation"]["schema_valid"] is True
    assert summary["performance"]["p95_latency_ms"] == 620
    assert summary["performance"]["p95_latency_ok"] is False
    assert summary["performance"]["concurrency_ok"] is False

    workflow_summary = collector.build_workflow_summary()
    assert workflow_summary["tokens_total"] == 9
    assert workflow_summary["models"] == ["m1"]
    assert workflow_summary["providers"] == ["test"]

    assert metrics_mod._extract_usage(SimpleNamespace()) == {}
    assert metrics_mod._extract_usage(
        SimpleNamespace(
            _raw_response=SimpleNamespace(usage={"prompt_tokens": 2, "completion_tokens": 1})
        )
    )["total_tokens"] == 3
    assert metrics_mod._extract_usage(
        SimpleNamespace(response=SimpleNamespace(usage=SimpleNamespace(input_tokens=4, output_tokens=6)))
    )["total_tokens"] == 10
    assert metrics_mod._extract_model(SimpleNamespace(_raw_response=SimpleNamespace(model="m-raw"))) == "m-raw"
    assert metrics_mod._extract_model(SimpleNamespace()) is None
    assert metrics_mod._percentile([], 95) is None
    assert metrics_mod._percentile([3.0, 1.0, 2.0], 0) == 1.0
    assert metrics_mod._percentile([1.0, 2.0, 3.0], 100) == 3.0
    assert metrics_mod._extract_latency_ms({"elapsed_ms": "12.5"}) == 12.5
    assert metrics_mod._extract_concurrency({"parallelism": "4"}) == 4
    assert metrics_mod._to_float("bad") is None
    assert metrics_mod._to_int("bad") is None
    assert metrics_mod._aggregate_llm_usage([]) == {}
    assert metrics_mod._aggregate_retrieval([]) == {}
    assert metrics_mod._aggregate_validation([]) == {}
    assert metrics_mod._aggregate_models(
        [
            {"type": "llm_usage", "data": {"model": "m1", "provider": "p1"}},
            {"type": "llm_usage", "data": {"model": "m1", "provider": "p1"}},
            {"type": "llm_usage", "data": {"model": "m2", "provider": "p2"}},
        ]
    ) == (["m1", "m2"], ["p1", "p2"])
    assert metrics_mod._aggregate_performance([{"type": "perf", "node": "x", "data": None}]) == {}

    metrics_path = tmp_path / "metrics.jsonl"
    collector.write_jsonl(str(metrics_path))
    rows = [json.loads(line) for line in metrics_path.read_text().splitlines()]
    assert rows[-1]["workflow_id"] == "unknown"

    warnings: list[str] = []
    monkeypatch.setattr(metrics_mod.logger, "warning", lambda message, *_args: warnings.append(message))
    monkeypatch.setattr(
        metrics_mod,
        "_append_jsonl_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    collector.write_jsonl(str(metrics_path))
    assert warnings
    assert metrics_mod.MetricsCollector().build_workflow_summary() == {}
    empty_collector = metrics_mod.MetricsCollector()
    empty_collector.write_jsonl(str(metrics_path))
    collector.reset()
    assert collector.events() == []


def test_unnumbered_189_graph_gate_and_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.graph.collect_radon_complexity_evidence",
        lambda: {"radon_available": False, "passed": False},
    )

    assert _is_results_artifact_path("results/run_001/summary.json") is True
    assert _is_results_artifact_path("benchmark_results/20260310/metrics.jsonl") is True
    assert _is_results_artifact_path("other/results.json") is False

    assert _has_claims_results_artifacts({}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"": "results/a.json"}}) is False
    assert _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": []}}) is False
    assert (
        _has_claims_results_artifacts({CLAIMS_RESULTS_ARTIFACTS_MARKER: {"C1": ["results/a.json", 7]}})
        is False
    )
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
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": []}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": [1]}}) is False
    assert _has_phase1_feature_trace({PHASE1_FEATURE_TRACE_MARKER: {"UC1": ["X1"]}}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: "must be true"}) is True
    assert _has_required_behavior_item({}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ""}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: 1}) is False
    assert _has_required_behavior_item({REQUIRED_BEHAVIOR_MARKER: ["ok", ""]}) is False

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
                    "migration_runbook_ref": "docs/runbook.md",
                    "index_growth_proof_ref": "artifacts/proof.json",
                },
                "enforce_post_incident_risk_matrix_feedback": True,
            }
        )
        == "post_incident_risk_matrix_feedback_handler"
    )
    assert _route_after_cross_reference_feature_ids({}) == "end"
    assert (
        _route_after_cross_reference_feature_ids({"enforce_cross_reference_feature_ids": True})
        == "cross_reference_feature_ids_handler"
    )
    assert (
        _route_after_cross_reference_feature_ids(
            {
                "enforce_cross_reference_feature_ids": True,
                CROSS_REFERENCE_FEATURE_IDS_MARKER: {"ref-1": ["F1.1", "F2B"]},
                "enforce_post_incident_risk_matrix_feedback": True,
            }
        )
        == "post_incident_risk_matrix_feedback_handler"
    )
    assert _has_cross_reference_feature_ids({}) is False
    assert _has_cross_reference_feature_ids({CROSS_REFERENCE_FEATURE_IDS_MARKER: []}) is False
    assert _has_cross_reference_feature_ids({CROSS_REFERENCE_FEATURE_IDS_MARKER: {"": "F1.1"}}) is False
    assert (
        _has_cross_reference_feature_ids({CROSS_REFERENCE_FEATURE_IDS_MARKER: {"ref-1": ["bad", "F1.1"]}})
        is False
    )
    assert _has_cross_reference_feature_ids(
        {CROSS_REFERENCE_FEATURE_IDS_MARKER: {"ref-1": ["F1.1", "F2B"]}}
    )

    assert _route_after_claims_results_artifacts({}) == "end"
    assert (
        _route_after_claims_results_artifacts({"enforce_claims_results_artifacts": True})
        == "claims_results_artifacts_handler"
    )
    assert (
        _route_after_required_behavior_item({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_phase1_traceability({"enforce_phase1_feature_trace": True})
        == "phase1_traceability_handler"
    )
    assert (
        _route_after_phase1_traceability({"enforce_required_behavior_item": True})
        == "required_behavior_handler"
    )
    assert (
        _route_after_complexity_evidence({"enforce_radon_complexity_evidence": True})
        == "complexity_evidence_handler"
    )
    assert _route_after_complexity_evidence({}) == "end"
    assert (
        _route_after_complexity_evidence(
            {
                "enforce_radon_complexity_evidence": True,
                "radon_complexity_evidence": {"radon_available": True},
                "enforce_post_incident_risk_matrix_feedback": True,
            }
        )
        == "post_incident_risk_matrix_feedback_handler"
    )

    assert session_dependency_handler_node({})["required_marker"] == B1_SESSION_COMPLETION_MARKER
    assert complexity_evidence_node({"enforce_radon_complexity_evidence": False}) == {
        "enforce_radon_complexity_evidence": False
    }
    enforced = complexity_evidence_node({"enforce_radon_complexity_evidence": True})
    assert enforced["radon_complexity_evidence"]["radon_available"] is False
    existing = complexity_evidence_node(
        {
            "enforce_radon_complexity_evidence": True,
            "radon_complexity_evidence": {"radon_available": True},
        }
    )
    assert existing["radon_complexity_evidence"]["radon_available"] is True
    assert complexity_evidence_handler_node({})["required_marker"] == "radon_complexity_evidence"
    assert (
        complexity_evidence_handler_node({"radon_complexity_evidence": {"radon_available": True}})[
            "radon_complexity_evidence"
        ]["radon_available"]
        is True
    )
    assert phase1_traceability_handler_node({})["required_marker"] == PHASE1_FEATURE_TRACE_MARKER
    assert required_behavior_handler_node({})["required_marker"] == REQUIRED_BEHAVIOR_MARKER
    assert claims_results_artifacts_handler_node({})["required_marker"] == CLAIMS_RESULTS_ARTIFACTS_MARKER
    assert cross_reference_feature_ids_handler_node({})["required_marker"] == CROSS_REFERENCE_FEATURE_IDS_MARKER
    assert postgresql_migration_handler_node({})["required_marker"] == POSTGRESQL_MIGRATION_EVIDENCE_MARKER

    unmet = post_incident_risk_matrix_feedback_handler_node({})
    assert unmet["required_marker"] == POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER
    assert POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER in unmet
    assert "Post-incident updates must feed back into the risk matrix" in unmet["dependency_error"]

    preserved = post_incident_risk_matrix_feedback_handler_node(
        {
            "required_marker": "existing_marker",
            "dependency_error": "existing",
            POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER: {
                "feedback_records": [{"incident_id": "INC-1"}],
                "feedback_complete": False,
            },
        }
    )
    assert preserved["required_marker"] == "existing_marker"
    assert preserved["dependency_error"] == "existing"

    assert clarification_handler_node({"clarification_questions": ["q1"]}) == {
        "clarification_questions": ["q1"]
    }
    assert sweep_execution_handler_node({"sweep_id": "id", "sweep_parameter": "p"})["sweep_id"] == "id"
    state = {"x": 1}
    assert paper_validator_node(state) is state

    app = create_graph().compile()
    graph_def = app.get_graph()
    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("complexity_evidence_node", "post_incident_risk_matrix_feedback_handler") in edges
    assert ("complexity_evidence_node", "cross_reference_feature_ids_handler") in edges
    assert ("post_incident_risk_matrix_feedback_handler", "__end__") in edges
