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


def test_metrics_collector_tracks_usd_cost_for_known_model() -> None:
    metrics_collector.reset()
    response = _FakeResponse("claude-3-5-sonnet-20250514", _FakeUsage(1000, 2000))

    with metrics_context("architect", node="architect", iteration=1):
        metrics_collector.record_llm_usage(response, provider="anthropic")

    summary = metrics_collector.summarize_stage("architect", iteration=1)
    assert summary["llm"]["cost_usd"] == 0.033
    assert summary["llm"]["by_model"]["claude-3-5-sonnet-20250514"]["cost_usd"] == 0.033


def test_metrics_collector_includes_workflow_cost_breakdown() -> None:
    metrics_collector.reset()
    stage_a_response = _FakeResponse("claude-3-5-sonnet-20250514", _FakeUsage(500, 500))
    stage_b_response = _FakeResponse("gpt-4-turbo", _FakeUsage(2000, 1000))

    with metrics_context("architect", node="architect", iteration=1):
        metrics_collector.record_llm_usage(stage_a_response, provider="anthropic")
    with metrics_context("review", node="reviewer", iteration=1):
        metrics_collector.record_llm_usage(stage_b_response, provider="openai")

    summary = metrics_collector.build_workflow_summary(stages=["architect", "review"])
    assert summary["cost_total_usd"] == 0.059
    assert summary["cost_by_stage_usd"]["architect"] == 0.009
    assert summary["cost_by_stage_usd"]["review"] == 0.05
