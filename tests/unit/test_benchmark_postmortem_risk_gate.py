"""Tests for benchmark/postmortem risk feedback criterion wiring."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tests.unit import test_impl_test_sync_gate as impl_sync_suite

from src.graph import (
    _route_after_input_writer,
    benchmark_postmortem_risk_feedback_handler_node,
    create_graph,
)
from src.utils import metrics as metrics_mod
from src.utils.metrics import (
    MetricsCollector,
    _aggregate_llm_usage,
    _aggregate_models,
    _aggregate_retrieval,
    _aggregate_validation,
    _calculate_cost_usd,
    _extract_model,
    _extract_update_risk_ids,
    _extract_usage,
    _extract_review_risk_ids,
    _find_pricing_model,
    _load_pricing_table,
    _normalized_risk_id,
    _state_list_entries,
    benchmark_postmortem_risk_feedback_failure_reason,
    benchmark_postmortem_risk_feedback_passed,
    metrics_context,
    metrics_extra,
)


class _UsageObj:
    def __init__(self, prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _ResponseObj:
    def __init__(self, *, model: str | None = None, usage: object | None = None, raw: object | None = None) -> None:
        self.model = model
        self.usage = usage
        self._raw_response = raw


def test_existing_graph_regression_suite_for_coverage_stability() -> None:
    impl_sync_suite.test_impl_test_sync_report_gate_reason_and_route()
    impl_sync_suite.test_latency_taxonomy_uc_and_depth_gates_still_functional()
    impl_sync_suite.test_routes_handlers_and_graph_wiring_cover_all_gate_nodes()
    impl_sync_suite.test_graph_regression_suite_still_passes()
    impl_sync_suite.test_plan_and_graph_fallback_branches_for_coverage_guardrails()
    impl_sync_suite.test_regression_uc_row_traceability_helpers_and_pass_fail_logic()
    impl_sync_suite.test_regression_plan_generation_and_taxonomy_and_depth_routes()


def test_benchmark_postmortem_criterion_wiring_pass_fail_and_handler() -> None:
    baseline_state = {
        "benchmark_reviews": [{"risk_id": "R-1"}, {"risk": "R-2"}],
        "postmortem_reviews": [{"id": "R-3"}],
        "risk_register_updates": [{"risks": ["r-1", "r-2", "r-3"]}],
    }
    assert benchmark_postmortem_risk_feedback_passed(baseline_state) is True
    assert (
        benchmark_postmortem_risk_feedback_failure_reason(baseline_state)
        == "benchmark_postmortem_risk_feedback_satisfied"
    )

    assert benchmark_postmortem_risk_feedback_passed({}) is False
    assert benchmark_postmortem_risk_feedback_failure_reason({}) == "benchmark_reviews_missing"
    assert (
        benchmark_postmortem_risk_feedback_failure_reason({"benchmark_reviews": [{"risk_id": "R-1"}]})
        == "postmortem_reviews_missing"
    )
    assert (
        benchmark_postmortem_risk_feedback_failure_reason(
            {
                "benchmark_reviews": [{"note": "missing risk id"}],
                "postmortem_reviews": [{"note": "missing risk id"}],
            }
        )
        == "review_risks_missing"
    )
    assert (
        benchmark_postmortem_risk_feedback_failure_reason(
            {
                "benchmark_reviews": [{"risk_id": "R-1"}],
                "postmortem_reviews": [{"risk_id": "R-2"}],
            }
        )
        == "risk_updates_missing"
    )
    assert (
        benchmark_postmortem_risk_feedback_failure_reason(
            {
                "benchmark_reviews": [{"risk_id": "R-1"}],
                "postmortem_reviews": [{"risk_id": "R-2"}],
                "risk_register_updates": [{"risk_id": "R-1"}],
            }
        )
        == "risk_updates_incomplete"
    )

    approved = {
        "gate_approvals": [
            {
                "decision": "approved",
                "details": {"criterion": "UNNUMBERED-185"},
            }
        ]
    }
    assert benchmark_postmortem_risk_feedback_passed(approved) is True

    assert (
        _route_after_input_writer(
            {
                "enforce_benchmark_postmortem_risk_feedback": True,
                "benchmark_reviews": [{"risk_id": "R-1"}],
                "postmortem_reviews": [{"risk_id": "R-2"}],
                "risk_register_updates": [{"risk_id": "R-1"}],
            }
        )
        == "benchmark_postmortem_risk_feedback_handler"
    )
    assert (
        _route_after_input_writer(
            {
                "enforce_benchmark_postmortem_risk_feedback": True,
                "benchmark_reviews": [{"risk_id": "R-1"}],
                "postmortem_reviews": [{"risk_id": "R-2"}],
                "risk_register_updates": [{"risks": ["R-1", "R-2"]}],
            }
        )
        == "end"
    )

    updates = benchmark_postmortem_risk_feedback_handler_node(
        {"gate_approvals": "invalid", "errors_active": "invalid", "benchmark_reviews": []}
    )
    assert updates["reviewer_failure_category"] == "benchmark_postmortem_risk_feedback_gate"
    assert updates["mode"] == "terminal"
    assert updates["errors_active"] == ["benchmark_reviews_missing"]
    assert updates["gate_approvals"][-1]["details"]["criterion"] == "UNNUMBERED-185"

    graph = create_graph().compile().get_graph()
    nodes = set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert "benchmark_postmortem_risk_feedback_handler" in nodes
    assert ("input_writer_node", "benchmark_postmortem_risk_feedback_handler") in edges
    assert ("benchmark_postmortem_risk_feedback_handler", "__end__") in edges


def test_metrics_helpers_cover_private_fallback_paths() -> None:
    assert _state_list_entries({"benchmark_reviews": [{"risk_id": "r1"}, "bad"]}, ("benchmark_reviews",)) == [
        {"risk_id": "r1"}
    ]
    assert _state_list_entries({"other": []}, ("benchmark_reviews",)) == []

    assert _normalized_risk_id(" R-123 ") == "r-123"
    assert _normalized_risk_id(None) == ""

    assert _extract_review_risk_ids([{"risk_id": "R-1"}, {"risk": "R-2"}, {"id": "R-3"}]) == {
        "r-1",
        "r-2",
        "r-3",
    }
    assert _extract_update_risk_ids([{"risk_id": "R-1"}, {"risks": ["R-2", 3]}]) == {"r-1", "r-2"}
    assert _state_list_entries(
        {
            "benchmark_reviews": [],
            "benchmark_findings": [{"risk_id": "R-10"}],
        },
        ("benchmark_reviews", "benchmark_findings"),
    ) == [{"risk_id": "R-10"}]


def test_metrics_usage_extraction_model_and_pricing_branches(monkeypatch) -> None:
    assert _extract_usage(_ResponseObj(usage=None)) == {}

    usage_dict = {"input_tokens": 11, "output_tokens": 7}
    assert _extract_usage(_ResponseObj(usage=usage_dict)) == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }

    usage_obj = _UsageObj(prompt_tokens=3, completion_tokens=2, total_tokens=None)
    assert _extract_usage(_ResponseObj(usage=usage_obj)) == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }

    raw_response = SimpleNamespace(usage={"prompt_tokens": 4, "completion_tokens": 1}, model="from-raw")
    response = _ResponseObj(model=None, usage=None, raw=raw_response)
    assert _extract_usage(response) == {
        "prompt_tokens": 4,
        "completion_tokens": 1,
        "total_tokens": 5,
    }
    assert _extract_model(_ResponseObj(model="direct-model")) == "direct-model"
    assert _extract_model(response) == "from-raw"

    pricing = {
        "model-a": {
            "provider": "provider-a",
            "input_cost_per_1k": 0.002,
            "output_cost_per_1k": 0.004,
            "currency": "USD",
        },
        "model-eur": {
            "provider": "provider-eur",
            "input_cost_per_1k": 0.001,
            "output_cost_per_1k": 0.002,
            "currency": "EUR",
        },
        "model-no-rates": {"provider": "provider-b", "currency": "USD"},
    }

    assert _find_pricing_model("model-a", None, pricing) == "model-a"
    assert _find_pricing_model(None, "provider-a", pricing) == "model-a"
    assert _find_pricing_model(None, "missing", pricing) is None

    assert _calculate_cost_usd(
        {"model": "model-a", "provider": "provider-a", "prompt_tokens": 1000, "completion_tokens": 500},
        pricing_table=pricing,
    ) == (0.004, "model-a")
    assert _calculate_cost_usd(
        {"model": "model-eur", "prompt_tokens": 1000, "completion_tokens": 500},
        pricing_table=pricing,
    ) == (None, "model-eur")
    assert _calculate_cost_usd(
        {"model": "model-no-rates", "prompt_tokens": 1000, "completion_tokens": 500},
        pricing_table=pricing,
    ) == (None, "model-no-rates")
    assert _calculate_cost_usd(
        {"model": "missing", "provider": "unknown", "prompt_tokens": 1000, "completion_tokens": 500},
        pricing_table=pricing,
    ) == (None, None)

    missing_path = Path("/tmp/does-not-exist-pricing.yaml")
    monkeypatch.setattr(metrics_mod, "_PRICING_PATH", missing_path)
    table = _load_pricing_table()
    assert "gpt-4-turbo" in table


def test_metrics_load_pricing_table_with_yaml_and_error_paths(tmp_path: Path, monkeypatch) -> None:
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(
        "models:\n  new-model:\n    provider: custom\n    input_cost_per_1k: 0.1\n    output_cost_per_1k: 0.2\n    currency: USD\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(metrics_mod, "_PRICING_PATH", pricing_path)
    table = _load_pricing_table()
    assert table["new-model"]["provider"] == "custom"

    class _BadYaml:
        @staticmethod
        def safe_load(_content: str) -> dict[str, object]:
            raise ValueError("bad yaml")

    monkeypatch.setitem(__import__("sys").modules, "yaml", _BadYaml)
    table_on_error = _load_pricing_table()
    assert "claude-3-5-sonnet-20250514" in table_on_error


def test_metrics_collector_aggregation_context_and_write_jsonl(tmp_path: Path, monkeypatch) -> None:
    collector = MetricsCollector()

    with metrics_context("architect", node="architect", iteration=2, extra={"trace": "t1"}):
        collector.record_event("retrieval_strategy", {"strategy": "rag"})
        collector.record_event("validation_metrics", {"passed": True})
        collector.record_llm_usage(
            _ResponseObj(model="claude-3-5-sonnet-20250514", usage={"prompt_tokens": 1000, "completion_tokens": 2000}),
            provider="anthropic",
        )

    with metrics_extra({"trace": "t2"}):
        collector.record_event("llm_usage", {"model": "unknown", "prompt_tokens": 1, "completion_tokens": 1})
    with metrics_extra(None):
        collector.record_event("noop", {"ok": True}, stage="misc")

    stage_summary = collector.summarize_stage("architect", iteration=2)
    assert stage_summary["retrieval"]["strategies"]["rag"] == 1
    assert stage_summary["validation"]["passed"] is True
    assert stage_summary["llm"]["total_calls"] == 1
    assert stage_summary["llm"]["cost_usd"] == 0.033

    assert collector.summarize_stage("missing") == {}

    workflow_summary = collector.build_workflow_summary(stages=["architect", "misc"])
    assert workflow_summary["tokens_total"] >= 3000
    assert "architect" in workflow_summary["tokens_by_stage"]
    assert "stages" in workflow_summary

    auto_stage_summary = collector.build_workflow_summary()
    assert "models" in auto_stage_summary
    assert "providers" in auto_stage_summary

    events = collector.events()
    assert any(event.get("context", {}).get("trace") == "t1" for event in events)

    llm_summary = _aggregate_llm_usage(events)
    assert llm_summary["total_calls"] >= 2
    assert _aggregate_retrieval(events)["last"]["strategy"] == "rag"
    assert _aggregate_validation(events)["passed"] is True
    models, providers = _aggregate_models(events)
    assert "claude-3-5-sonnet-20250514" in models
    assert "anthropic" in providers
    assert _aggregate_llm_usage([]) == {}
    assert _aggregate_retrieval([]) == {}
    assert _aggregate_validation([]) == {}

    out_path = tmp_path / "events.jsonl"
    collector.write_jsonl(str(out_path))
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(events)

    def fake_sanitize(payload: dict[str, object], *, config: object) -> dict[str, object]:
        return {"sanitized": True, "type": payload.get("type"), "cfg": getattr(config, "mode", "unknown")}

    monkeypatch.setattr("src.utils.privacy.sanitize_payload", fake_sanitize)
    sanitized_path = tmp_path / "sanitized.jsonl"
    collector.write_jsonl(str(sanitized_path), config=SimpleNamespace(mode="strict"))
    first_payload = json.loads(sanitized_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_payload["sanitized"] is True

    collector.write_jsonl(str(tmp_path))

    collector.reset()
    assert collector.events() == []
    assert collector.build_workflow_summary() == {}
