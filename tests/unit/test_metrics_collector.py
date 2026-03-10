import importlib

from src.utils.metrics import metrics_collector, metrics_context

reviewer_node_module = importlib.import_module("src.nodes.reviewer_node")


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


def test_metrics_collector_preserves_validation_latency_and_outcomes() -> None:
    metrics_collector.reset()
    with metrics_context("reviewer", node="reviewer", iteration=2):
        metrics_collector.record_event(
            "validation_metrics",
            {
                "validator_latency_ms": 12.5,
                "validator_outcome": "retry",
                "review_outcome": "rejected",
                "transition_mode": "retry",
                "error_count": 1,
            },
        )

    summary = metrics_collector.summarize_stage("reviewer", iteration=2)
    validation = summary["validation"]
    assert validation["validator_latency_ms"] == 12.5
    assert validation["validator_outcome"] == "retry"
    assert validation["review_outcome"] == "rejected"
    assert validation["transition_mode"] == "retry"


class _DummyConfig:
    preconfirm_gate = False
    preconfirm_gate_auto_approve = False
    retry_guidance_use_llm = False
    baseline_switch_after_retries = 3
    repositories = {}
    amrex_agent_root = None


class _FakeValidationResult:
    mode = "proceed"
    violations = []
    summary = "ok"
    available_schema_params = []


class _FakeReviewerOrchestrator:
    def __init__(self, _config) -> None:
        pass

    def validate_plan(self, _plan):
        return _FakeValidationResult()


def test_reviewer_node_logs_validator_latency_and_outcomes(monkeypatch) -> None:
    metrics_collector.reset()
    monkeypatch.setattr(reviewer_node_module, "ReviewerOrchestrator", _FakeReviewerOrchestrator)

    state = {
        "config": _DummyConfig(),
        "iteration": 0,
        "retry_count": 0,
        "max_retries": 3,
        "workflow_history": [
            {
                "node": "architect",
                "details": {
                    "selected_case": "demo/case",
                    "modifications": [],
                    "baseline": {"code_name": "PeleC"},
                },
            }
        ],
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
    }

    updates = reviewer_node_module.reviewer_node(state)
    metrics = updates["workflow_history"][-1]["details"]["metrics"]["validation"]

    assert metrics["validator_latency_ms"] >= 0.0
    assert metrics["validator_outcome"] == "proceed"
    assert metrics["review_outcome"] == "approved"
    assert metrics["transition_mode"] == "proceed"
