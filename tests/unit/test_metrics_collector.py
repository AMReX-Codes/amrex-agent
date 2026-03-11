import json
from types import SimpleNamespace

import src.utils.metrics as metrics_module
from src.utils.metrics import MetricsCollector, _latency_ms, metrics_collector, metrics_context, metrics_extra


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _FakeResponse:
    def __init__(self, model: str, usage: _FakeUsage) -> None:
        self.model = model
        self.usage = usage


def test_metrics_collector_aggregates_llm_tokens() -> None:
    metrics_collector.reset()
    response = _FakeResponse("test-model", _FakeUsage(12, 8))

    with metrics_context("architect", node="architect", iteration=1):
        metrics_collector.record_llm_usage(response, model="test-model", provider="test")

    summary = metrics_collector.summarize_stage("architect", iteration=1)
    assert summary["llm"]["total_calls"] == 1
    assert summary["llm"]["total_tokens"] == 20
    assert summary["llm"]["prompt_tokens"] == 12
    assert summary["llm"]["completion_tokens"] == 8
    assert summary["llm"]["by_model"]["test-model"]["calls"] == 1


def test_record_event_persists_stage_tag_and_node_latency_jsonl(monkeypatch, tmp_path) -> None:
    collector = MetricsCollector()
    perf_values = iter([100.0, 100.015])
    monkeypatch.setattr(metrics_module.time, "perf_counter", lambda: next(perf_values))

    with metrics_context("architect", node="architect", iteration=3):
        event = collector.record_event("custom_metric", {"ok": True})

    assert event["stage"] == "architect"
    assert event["node"] == "architect"
    assert event["node_latency_ms"] == 15.0
    assert event["stage_latency_ms"] == 15.0

    metrics_path = tmp_path / "metrics.jsonl"
    collector.write_jsonl(str(metrics_path))
    payload = json.loads(metrics_path.read_text(encoding="utf-8").strip())
    assert payload["stage"] == "architect"
    assert payload["node"] == "architect"
    assert payload["node_latency_ms"] == 15.0


def test_record_event_without_context_has_unknown_tags() -> None:
    collector = MetricsCollector()
    event = collector.record_event("freeform", {"ok": True})

    assert event["stage"] == "unknown"
    assert event["node"] == "unknown"
    assert "node_latency_ms" not in event
    assert "stage_latency_ms" not in event


def test_metrics_extra_adds_context_and_resets() -> None:
    collector = MetricsCollector()

    with metrics_context("analysis", node="analysis", iteration=4):
        with metrics_extra({"run_id": "abc123"}):
            event_with_context = collector.record_event("annotated", {"a": 1})
        event_without_context = collector.record_event("plain", {"a": 2})

    assert event_with_context["context"] == {"run_id": "abc123"}
    assert "context" not in event_without_context


def test_record_llm_usage_handles_usage_dict_and_model_fallback() -> None:
    collector = MetricsCollector()
    response = SimpleNamespace(
        usage={"input_tokens": 3, "output_tokens": 2},
        _raw_response=SimpleNamespace(model="fallback-model"),
    )

    event = collector.record_llm_usage(response, provider="cborg")
    assert event is not None
    assert event["data"]["prompt_tokens"] == 3
    assert event["data"]["completion_tokens"] == 2
    assert event["data"]["total_tokens"] == 5
    assert event["data"]["model"] == "fallback-model"
    assert event["data"]["provider"] == "cborg"


def test_record_llm_usage_handles_nested_response_usage() -> None:
    collector = MetricsCollector()
    response = SimpleNamespace(
        model="nested-model",
        response=SimpleNamespace(usage=SimpleNamespace(input_tokens=4, output_tokens=6)),
    )

    event = collector.record_llm_usage(response, provider="nested")
    assert event is not None
    assert event["data"]["prompt_tokens"] == 4
    assert event["data"]["completion_tokens"] == 6
    assert event["data"]["total_tokens"] == 10


def test_record_llm_usage_returns_none_when_usage_missing() -> None:
    collector = MetricsCollector()
    assert collector.record_llm_usage(SimpleNamespace(model="none")) is None


def test_summarize_stage_includes_retrieval_and_validation_iteration_filtering() -> None:
    collector = MetricsCollector()
    collector.record_event("retrieval_strategy", {"strategy": "l2"}, stage="reviewer", node="reviewer", iteration=2)
    collector.record_event(
        "validation_metrics",
        {"error_count": 1, "warning_count": 2},
        stage="reviewer",
        node="reviewer",
        iteration=2,
    )
    collector.record_event("retrieval_strategy", {"strategy": "l1"}, stage="reviewer", node="reviewer", iteration=1)

    summary = collector.summarize_stage("reviewer", iteration=2)
    assert summary["retrieval"]["strategies"] == {"l2": 1}
    assert summary["retrieval"]["last"]["strategy"] == "l2"
    assert summary["validation"] == {"error_count": 1, "warning_count": 2}


def test_build_workflow_summary_aggregates_tokens_models_and_providers() -> None:
    collector = MetricsCollector()
    first = _FakeResponse("model-a", _FakeUsage(5, 7))
    second = _FakeResponse("model-b", _FakeUsage(2, 3))

    with metrics_context("architect", node="architect", iteration=1):
        collector.record_llm_usage(first, provider="p1")
    with metrics_context("reviewer", node="reviewer", iteration=1):
        collector.record_llm_usage(second, provider="p2")

    summary = collector.build_workflow_summary()
    assert summary["tokens_total_input"] == 7
    assert summary["tokens_total_output"] == 10
    assert summary["tokens_total"] == 17
    assert summary["tokens_by_stage"]["architect"]["total"] == 12
    assert summary["tokens_by_stage"]["reviewer"]["total"] == 5
    assert summary["models"] == ["model-a", "model-b"]
    assert summary["providers"] == ["p1", "p2"]
    assert "stages" in summary


def test_build_workflow_summary_returns_empty_without_events() -> None:
    assert MetricsCollector().build_workflow_summary() == {}


def test_write_jsonl_with_config_uses_sanitizer(monkeypatch, tmp_path) -> None:
    collector = MetricsCollector()
    collector.record_event("custom", {"secret": "x"}, stage="workflow", node="main")

    def _sanitize(payload, config):
        return {"sanitized": True, "type": payload.get("type")}

    import src.utils.privacy as privacy

    monkeypatch.setattr(privacy, "sanitize_payload", _sanitize)
    metrics_path = tmp_path / "metrics.jsonl"
    collector.write_jsonl(str(metrics_path), config=SimpleNamespace())
    payload = json.loads(metrics_path.read_text(encoding="utf-8").strip())
    assert payload == {"sanitized": True, "type": "custom"}


def test_events_returns_copy_and_reset_clears_state() -> None:
    collector = MetricsCollector()
    collector.record_event("sample", {"v": 1}, stage="workflow", node="main")
    events = collector.events()
    events.append({"type": "tampered"})

    assert len(collector.events()) == 1
    collector.reset()
    assert collector.events() == []


def test_latency_helper_handles_none_and_negative() -> None:
    assert _latency_ms(None) is None
    assert _latency_ms(2.0, 1.0) == 0.0
