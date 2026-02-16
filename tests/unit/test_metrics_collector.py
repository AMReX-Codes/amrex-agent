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
