import json

from src.utils.metrics import metrics_collector, metrics_context


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


def test_metrics_workflow_summary_tracks_stage_totals() -> None:
    metrics_collector.reset()
    architect = _FakeResponse("a-model", _FakeUsage(5, 7))
    reviewer = _FakeResponse("r-model", _FakeUsage(3, 2))

    with metrics_context("architect", node="architect", iteration=1):
        metrics_collector.record_llm_usage(architect, model="a-model", provider="test")
    with metrics_context("reviewer", node="reviewer", iteration=1):
        metrics_collector.record_llm_usage(reviewer, model="r-model", provider="test")

    summary = metrics_collector.build_workflow_summary()

    assert summary["tokens_total_input"] == 8
    assert summary["tokens_total_output"] == 9
    assert summary["tokens_total"] == 17
    assert summary["tokens_by_stage"]["architect"]["total"] == 12
    assert summary["tokens_by_stage"]["reviewer"]["total"] == 5
    assert "a-model" in summary["models"]
    assert "r-model" in summary["models"]


def test_metrics_write_jsonl_outputs_events(tmp_path) -> None:
    metrics_collector.reset()
    metrics_collector.record_event("custom", {"alpha": 1}, stage="test", node="node")

    path = tmp_path / "metrics.jsonl"
    metrics_collector.write_jsonl(str(path))

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["type"] == "custom"
    assert payload["data"]["alpha"] == 1
