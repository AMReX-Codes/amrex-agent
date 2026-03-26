"""Session 109 tests for UNNUMBERED-183 risk link traceability checker."""

from __future__ import annotations

import json
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
    paper_manifest_gate_node,
    radon_cc_gate_node,
    required_outputs_section_node,
    risk_links_traceability_node,
    sweep_execution_handler_node,
)
from src.models.paper_validation_manifest import PaperValidationManifest, ValidationCheckResult
from src.utils import metrics as metrics_mod
from src.utils.metrics import RISK_LINK_VALIDATION_ARTIFACT, MetricsCollector, validate_risk_links


def test_validate_risk_links_paths() -> None:
    missing_payload = validate_risk_links(None)
    assert missing_payload["risk_links_valid"] is True
    assert missing_payload["risk_links_missing"] == []
    assert missing_payload["risk_links_validation_artifact"] == RISK_LINK_VALIDATION_ARTIFACT

    invalid_payload = validate_risk_links("bad")  # type: ignore[arg-type]
    assert invalid_payload["risk_links_valid"] is False
    assert "must be a list" in invalid_payload["risk_links_error"]

    valid_payload = validate_risk_links(
        [
            {
                "risk_id": "R-1",
                "mitigation": "Add check",
                "validation_artifact": "tests/unit/test_unnumbered_183.py",
            }
        ]
    )
    assert valid_payload["risk_links_valid"] is True

    mixed_payload = validate_risk_links(
        [
            "bad-item",
            {"risk_id": "R-2", "mitigation": "", "validation_artifact": "  "},
            {"risk_id": " ", "mitigation": "Use gate", "validation_artifact": "artifact"},
        ]  # type: ignore[list-item]
    )
    assert mixed_payload["risk_links_valid"] is False
    assert len(mixed_payload["risk_links_missing"]) == 3
    assert mixed_payload["risk_links_error"] == "risk link traceability check failed"


def test_graph_risk_links_node_and_routes() -> None:
    assert _route_after_risk_links_traceability({"risk_links_valid": True}) == "input_writer_node"
    assert _route_after_risk_links_traceability({"risk_links_valid": False}) == "clarification_handler"
    assert _route_after_risk_links_traceability({}) == "clarification_handler"

    result = risk_links_traceability_node(
        {
            "risk_links": [
                {
                    "risk_id": "R-3",
                    "mitigation": "Enforce linkage checker",
                    "validation_artifact": "ci:test_unnumbered_183",
                }
            ]
        }
    )
    assert result["risk_links_valid"] is True

    via_register = risk_links_traceability_node(
        {"risk_register": [{"risk_id": "R-4", "mitigation": "x", "validation_artifact": ""}]}
    )
    assert via_register["risk_links_valid"] is False


def test_graph_routes_and_gate_nodes() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_sweep_detection({"sweep_id": "s1"}) == "sweep_execution_handler"
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

    assert _is_paper_validator_enabled({"paper_validator_enabled": True}) is True
    assert _is_paper_validator_enabled({"paper_validator_enabled": False}) is False
    assert _is_paper_validator_enabled({"config": SimpleNamespace(paper_validator_enabled=True)}) is True
    assert _is_paper_validator_enabled({"config": object()}) is False

    default_manifest = paper_manifest_gate_node({})
    assert default_manifest["paper_manifest_valid"] is True

    missing_manifest = paper_manifest_gate_node({"paper_validator_enabled": True})
    assert missing_manifest["paper_manifest_valid"] is False

    invalid_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {"document_id": 1, "checks": "bad"},
        }
    )
    assert invalid_manifest["paper_manifest_valid"] is False

    blocking_manifest = paper_manifest_gate_node(
        {
            "paper_validator_enabled": True,
            "paper_validation_manifest": {
                "document_id": "paper-183",
                "checks": [
                    {"check_id": "c1", "title": "critical", "status": "fail", "blocking": True}
                ],
            },
        }
    )
    assert blocking_manifest["paper_manifest_valid"] is False

    manifest = PaperValidationManifest(
        document_id="paper-183-model",
        checks=[ValidationCheckResult(check_id="c1", title="ok", status="pass")],
    )
    accepted_manifest = paper_manifest_gate_node(
        {"paper_validator_enabled": True, "paper_validation_manifest": manifest}
    )
    assert accepted_manifest["paper_manifest_valid"] is True

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


def test_graph_section_nodes_and_placeholders(capsys: pytest.CaptureFixture[str]) -> None:
    assert REQUIRED_OUTPUTS_SECTION == ("selected_case", "modifications")
    assert "architect_node" in CRITICAL_PATH_FEATURES_SECTION
    assert "input_writer_node" in CAMERA_READY_SCOPE_BOUNDARIES

    assert _latest_architect_details({}) is None
    assert _latest_architect_details({"workflow_history": "bad"}) is None
    assert _latest_architect_details({"workflow_history": [{"node": "architect"}]}) is None

    latest = _latest_architect_details(
        {
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "old", "modifications": []}},
                {"node": "architect", "details": {"selected_case": "new", "modifications": ["m1"]}},
            ]
        }
    )
    assert latest == {"selected_case": "new", "modifications": ["m1"]}

    req_ok = required_outputs_section_node({"selected_case": "case", "modifications": []})
    assert req_ok["required_outputs_valid"] is True

    req_missing = required_outputs_section_node({})
    assert req_missing["required_outputs_valid"] is False
    assert req_missing["required_outputs_missing"] == ["selected_case", "modifications"]

    req_bad_mods = required_outputs_section_node({"selected_case": "case", "modifications": "bad"})
    assert req_bad_mods["required_outputs_valid"] is False

    req_mismatch = required_outputs_section_node(
        {
            "selected_case": "case-a",
            "modifications": ["m1"],
            "workflow_history": [
                {"node": "architect", "details": {"selected_case": "case-b", "modifications": ["m2"]}}
            ],
        }
    )
    assert req_mismatch["required_outputs_valid"] is False

    critical_default = critical_path_features_section_node({})
    assert critical_default["critical_path_features_valid"] is True

    critical_map = critical_path_features_section_node(
        {"critical_path_features": {name: True for name in CRITICAL_PATH_FEATURES_SECTION}}
    )
    assert critical_map["critical_path_features_valid"] is True

    critical_missing = critical_path_features_section_node(
        {
            "critical_path_features": [
                name for name in CRITICAL_PATH_FEATURES_SECTION if name != "architect_node"
            ]
        }
    )
    assert critical_missing["critical_path_features_valid"] is False

    critical_invalid = critical_path_features_section_node({"critical_path_features": "bad"})
    assert critical_invalid["critical_path_features_valid"] is False

    boundary_default = camera_ready_scope_boundary_node({})
    assert boundary_default["camera_ready_scope_boundaries_valid"] is True

    boundary_map = camera_ready_scope_boundary_node(
        {"camera_ready_scope_boundaries": {name: True for name in CAMERA_READY_SCOPE_BOUNDARIES}}
    )
    assert boundary_map["camera_ready_scope_boundaries_valid"] is True

    boundary_missing = camera_ready_scope_boundary_node(
        {
            "camera_ready_scope_boundaries": [
                name for name in CAMERA_READY_SCOPE_BOUNDARIES if name != "input_writer_node"
            ]
        }
    )
    assert boundary_missing["camera_ready_scope_boundaries_valid"] is False

    boundary_invalid = camera_ready_scope_boundary_node({"camera_ready_scope_boundaries": "bad"})
    assert boundary_invalid["camera_ready_scope_boundaries_valid"] is False

    clarification_state = {"clarification_questions": ["Need CFL?"]}
    sweep_state = {"sweep_id": "s1", "sweep_parameter": "amr.n_cell"}
    assert clarification_handler_node(clarification_state) == clarification_state
    assert sweep_execution_handler_node(sweep_state) == sweep_state
    out = capsys.readouterr().out
    assert "Clarification needed" in out
    assert "Sweep detected" in out


def test_graph_compilation_contains_session_109_nodes_and_edges() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    nodes = set(graph_def.nodes.keys())
    assert "radon_cc_gate_node" in nodes
    assert "risk_links_traceability_node" in nodes
    assert "input_writer_node" in nodes

    edges = {(edge.source, edge.target) for edge in graph_def.edges}
    assert ("radon_cc_gate_node", "risk_links_traceability_node") in edges
    assert ("radon_cc_gate_node", "clarification_handler") in edges
    assert ("risk_links_traceability_node", "input_writer_node") in edges
    assert ("risk_links_traceability_node", "clarification_handler") in edges


def test_metrics_extractors_and_aggregators_cover_paths() -> None:
    class UsageObj:
        def __init__(self) -> None:
            self.prompt_tokens = 2
            self.completion_tokens = 3
            self.total_tokens = None

    class ResponseObj:
        def __init__(self) -> None:
            self.usage = UsageObj()
            self.model = "model-a"

    response = ResponseObj()
    usage = metrics_mod._extract_usage(response)
    assert usage == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
    assert metrics_mod._extract_model(response) == "model-a"

    raw_model_response = SimpleNamespace(_raw_response=SimpleNamespace(model="raw-model"))
    assert metrics_mod._extract_model(raw_model_response) == "raw-model"

    dict_usage_response = SimpleNamespace(
        usage={"input_tokens": 4, "output_tokens": 1, "total_tokens": None}
    )
    dict_usage = metrics_mod._extract_usage(dict_usage_response)
    assert dict_usage["prompt_tokens"] == 4
    assert dict_usage["completion_tokens"] == 1
    assert dict_usage["total_tokens"] == 5

    nested_usage_response = SimpleNamespace(response=SimpleNamespace(usage={"total_tokens": 9}))
    nested_usage = metrics_mod._extract_usage(nested_usage_response)
    assert nested_usage["total_tokens"] == 9

    no_usage = metrics_mod._extract_usage(SimpleNamespace())
    assert no_usage == {}

    events = [
        {"type": "llm_usage", "data": {"model": "m1", "provider": "p1", "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
        {"type": "llm_usage", "data": {"model": "m1", "provider": "p1", "prompt_tokens": 4, "completion_tokens": 5}},
        {"type": "retrieval_strategy", "data": {"strategy": "bm25", "k": 5}},
        {"type": "retrieval_strategy", "data": {"strategy": "bm25", "k": 8}},
        {"type": "validation_metrics", "data": {"checks": 7}},
    ]
    llm_summary = metrics_mod._aggregate_llm_usage(events)
    assert llm_summary["total_calls"] == 2
    assert llm_summary["prompt_tokens"] == 5
    assert llm_summary["completion_tokens"] == 7
    assert llm_summary["total_tokens"] == 12
    assert llm_summary["by_model"]["m1"]["calls"] == 2

    retrieval_summary = metrics_mod._aggregate_retrieval(events)
    assert retrieval_summary["strategies"]["bm25"] == 2
    assert retrieval_summary["last"]["k"] == 8

    validation_summary = metrics_mod._aggregate_validation(events)
    assert validation_summary == {"checks": 7}

    models, providers = metrics_mod._aggregate_models(events)
    assert models == ["m1"]
    assert providers == ["p1"]

    assert metrics_mod._aggregate_llm_usage([]) == {}
    assert metrics_mod._aggregate_retrieval([]) == {}
    assert metrics_mod._aggregate_validation([]) == {}
    assert metrics_mod._aggregate_models([]) == ([], [])


def test_metrics_collector_end_to_end_and_write_jsonl(tmp_path, monkeypatch) -> None:
    collector = MetricsCollector()

    with metrics_mod.metrics_context("architect", node="architect_node", iteration=1, extra={"s": "x"}):
        event = collector.record_event("retrieval_strategy", {"strategy": "hybrid"})
        assert event["stage"] == "architect"
        assert event["node"] == "architect_node"
        assert event["iteration"] == 1
        assert event["context"] == {"s": "x"}

        with metrics_mod.metrics_extra({"risk": "R-1"}):
            nested = collector.record_event("validation_metrics", {"checks": 3})
            assert nested["context"] == {"risk": "R-1"}

        llm_recorded = collector.record_llm_usage(
            SimpleNamespace(usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}),
            model="m-ctx",
            provider="provider-x",
        )
        assert llm_recorded is not None

    assert collector.record_llm_usage(SimpleNamespace(), model="none") is None

    summary = collector.summarize_stage("architect", iteration=1)
    assert summary["llm"]["total_calls"] == 1
    assert summary["retrieval"]["strategies"]["hybrid"] == 1
    assert summary["validation"] == {"checks": 3}

    assert collector.summarize_stage("missing") == {}

    workflow_summary = collector.build_workflow_summary()
    assert workflow_summary["tokens_total"] == 5
    assert workflow_summary["tokens_by_stage"]["architect"]["total"] == 5
    assert workflow_summary["models"] == ["m-ctx"]
    assert workflow_summary["providers"] == ["provider-x"]
    assert "stages" in workflow_summary

    staged_summary = collector.build_workflow_summary(stages=["architect", "missing"])
    assert "architect" in staged_summary["tokens_by_stage"]

    out_path = tmp_path / "metrics.jsonl"
    collector.write_jsonl(str(out_path))
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["type"] == "retrieval_strategy"

    sanitized_path = tmp_path / "sanitized.jsonl"
    sanitizer_calls = {"count": 0}

    def _sanitize(payload, config):
        sanitizer_calls["count"] += 1
        return {"sanitized": payload["type"], "cfg": config["mode"]}

    monkeypatch.setattr("src.utils.privacy.sanitize_payload", _sanitize)
    collector.write_jsonl(str(sanitized_path), config={"mode": "safe"})
    sanitized = [json.loads(line) for line in sanitized_path.read_text(encoding="utf-8").splitlines()]
    assert sanitizer_calls["count"] == 3
    assert sanitized[0]["cfg"] == "safe"

    empty_collector = MetricsCollector()
    empty_target = tmp_path / "empty.jsonl"
    empty_collector.write_jsonl(str(empty_target))
    assert not empty_target.exists()

    def _raise_open(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", _raise_open)
    collector.write_jsonl(str(tmp_path / "will_fail.jsonl"))

    assert len(collector.events()) == 3
    collector.reset()
    assert collector.events() == []
    assert collector.build_workflow_summary() == {}
