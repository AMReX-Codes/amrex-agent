import json
from types import SimpleNamespace

import pytest

from src.benchmark_runner import (
    _build_command,
    _derive_reproducibility_oracle_fields,
    _write_jsonl,
    run_model_benchmark,
)
from src.utils import metrics as metrics_mod


def test_run_model_benchmark_writes_manifest_and_metrics(tmp_path, monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"job_status": "ok"}),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    config = {
        "prompts": [{"id": "p1", "prompt": "Hello"}],
        "models": [{"id": "m1", "overrides": {"llm_provider": "cborg", "llm_model": "x"}}],
        "run_args": {"dry_run": True},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config))

    result = run_model_benchmark(config_path, tmp_path, run_name="bench_test")
    run_dir = tmp_path / "bench_test"

    assert result["run_dir"] == str(run_dir)
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "benchmark_runs.jsonl").exists()
    assert (run_dir / "configs" / "m1.json").exists()

    prompt_context = run_dir / "runs" / "m1" / "p1" / "benchmark_context.json"
    assert prompt_context.exists()

    record = json.loads((run_dir / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert record["model_id"] == "m1"
    assert record["prompt_id"] == "p1"
    assert record["run_directory"] is None


def test_reproducibility_oracle_preserves_numeric_zero_seed() -> None:
    result = _derive_reproducibility_oracle_fields(
        {
            "reproducibility_oracle_enabled": True,
            "seed": 0,
            "analysis_status": "success",
        },
        {},
    )
    assert result["reproducibility_oracle_seed"] == "0"
    assert result["reproducibility_oracle_valid"] is True
    assert result["reproducibility_oracle_reason"] is None


def test_run_model_benchmark_sanitizes_replay_manifest_command_in_privacy_mode(
    tmp_path, monkeypatch
) -> None:
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"job_status": "ok"}),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    config = {
        "prompts": [{"id": "p1", "prompt": "TOP_SECRET_PROMPT"}],
        "models": [{"id": "m1", "overrides": {"llm_provider": "cborg", "llm_model": "x"}}],
        "run_args": {"dry_run": True, "privacy_mode": "strict"},
    }
    config_path = tmp_path / "bench_privacy.json"
    config_path.write_text(json.dumps(config))

    run_model_benchmark(config_path, tmp_path, run_name="bench_privacy")
    replay_manifest = json.loads((tmp_path / "bench_privacy" / "replay_manifest.json").read_text())

    assert replay_manifest["runs"]
    assert replay_manifest["runs"][0]["command"] == "[REDACTED]"
    assert "TOP_SECRET_PROMPT" not in json.dumps(replay_manifest)


def test_build_command_maps_optional_and_boolean_run_args(tmp_path):
    config_path = tmp_path / "config.json"
    context_path = tmp_path / "context.json"
    cmd = _build_command(
        config_path=config_path,
        prompt_entry={"id": "p1", "prompt": "solve this"},
        output_dir=tmp_path,
        run_args={
            "run_mode": "batch",
            "environment": "ci",
            "run_ntasks": 4,
            "dry_run": True,
            "verbose": True,
            "extra_args": ["--foo", 7],
        },
        benchmark_context=context_path,
    )

    assert "--config" in cmd and str(config_path) in cmd
    assert "--prompt" in cmd and "solve this" in cmd
    assert "--output-dir" in cmd and str(tmp_path) in cmd
    assert "--benchmark-context" in cmd and str(context_path) in cmd
    assert "--run-mode" in cmd and "batch" in cmd
    assert "--environment" in cmd and "ci" in cmd
    assert "--run-ntasks" in cmd and "4" in cmd
    assert "--dry-run" in cmd
    assert "--verbose" in cmd
    assert cmd[-2:] == ["--foo", "7"]


def test_build_command_accepts_prompt_path(tmp_path):
    cmd = _build_command(
        config_path=None,
        prompt_entry={"id": "p1", "prompt_path": "prompts/p1.txt"},
        output_dir=tmp_path,
        run_args={},
        benchmark_context=None,
    )
    assert "--prompt-path" in cmd
    assert "prompts/p1.txt" in cmd
    assert "--prompt" not in cmd


def test_build_command_requires_prompt_or_prompt_path(tmp_path):
    with pytest.raises(ValueError, match="Prompt entry missing prompt text/path"):
        _build_command(
            config_path=None,
            prompt_entry={"id": "p1"},
            output_dir=tmp_path,
            run_args={},
            benchmark_context=None,
        )


def _read_first_jsonl(path):
    return json.loads(path.read_text().splitlines()[0])


def test_jsonl_contains_schema_valid_field(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "schema_valid" in record
    assert isinstance(record["schema_valid"], bool)


def test_jsonl_contains_physics_valid_field(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "physics_valid" in record
    assert isinstance(record["physics_valid"], bool)


def test_jsonl_contains_resource_valid_field(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "resource_valid" in record
    assert isinstance(record["resource_valid"], bool)


def test_jsonl_schema_errors_empty_when_valid(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1", "schema_valid": True})
    record = _read_first_jsonl(path)
    assert record["schema_errors"] == []


def test_jsonl_schema_errors_populated_when_invalid(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "schema_valid": False,
            "review_analysis": {
                "violations": [
                    {"rule_name": "SchemaExistence", "message": "invalid parameter"},
                ]
            },
        },
    )
    record = _read_first_jsonl(path)
    assert record["schema_errors"]
    assert all(isinstance(item, str) for item in record["schema_errors"])


def test_jsonl_physics_warnings_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "physics_warnings" in record
    assert isinstance(record["physics_warnings"], list)


def test_jsonl_iteration_count_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1", "iteration": 2})
    record = _read_first_jsonl(path)
    assert "iteration_count" in record
    assert isinstance(record["iteration_count"], int)


def test_jsonl_reviewer_retry_count_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1", "retry_count": 1})
    record = _read_first_jsonl(path)
    assert "reviewer_retry_count" in record
    assert isinstance(record["reviewer_retry_count"], int)


def test_jsonl_converged_field_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "converged" in record
    assert isinstance(record["converged"], bool)


def test_jsonl_wall_time_seconds_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1", "duration_seconds": 1.25})
    record = _read_first_jsonl(path)
    assert "wall_time_seconds" in record
    assert isinstance(record["wall_time_seconds"], float)


def test_jsonl_architect_time_seconds_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "architect_time_seconds" in record
    assert isinstance(record["architect_time_seconds"], float)


def test_jsonl_llm_call_count_present(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert "llm_call_count" in record
    assert isinstance(record["llm_call_count"], int)


def test_jsonl_field_null_with_reason_when_unavailable(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert record["iteration_count"] is None
    assert isinstance(record["iteration_count_unavailable_reason"], str)
    assert record["reviewer_retry_count"] is None
    assert isinstance(record["reviewer_retry_count_unavailable_reason"], str)


def test_jsonl_no_new_required_field_breaks_existing(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1"})
    record = _read_first_jsonl(path)
    assert record["schema_valid"] is False
    assert record["physics_valid"] is False
    assert record["resource_valid"] is False
    assert record["schema_errors"] == []
    assert record["physics_warnings"] == []
    assert record["converged"] is False


def test_gate_approvals_written_to_jsonl(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "__graph_state": {
                "gate_approvals": [
                    {"interface_path": "cli", "decision": "approved"},
                    {"interface_path": "api", "decision": "rejected"},
                ]
            },
        },
    )
    record = _read_first_jsonl(path)
    assert record["gate_approval_count"] == 2
    assert isinstance(record["gate_approvals"], list)
    assert all(isinstance(item, dict) for item in record["gate_approvals"])


def test_gate_approvals_empty_writes_zero_count(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "__graph_state": {"gate_approvals": []},
        },
    )
    record = _read_first_jsonl(path)
    assert record["gate_approval_count"] == 0
    assert record["gate_approvals"] == []


def test_gate_approval_interface_path_preserved(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "__graph_state": {
                "gate_approvals": [{"interface_path": "cli", "decision": "approved"}]
            },
        },
    )
    record = _read_first_jsonl(path)
    assert record["gate_approvals"][0]["interface_path"] == "cli"


def test_gate_approval_decision_preserved(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(
        path,
        {
            "model_id": "m1",
            "prompt_id": "p1",
            "__graph_state": {
                "gate_approvals": [{"interface_path": "cli", "decision": "approved"}]
            },
        },
    )
    record = _read_first_jsonl(path)
    assert record["gate_approvals"][0]["decision"] == "approved"


def test_gate_approvals_missing_from_state_safe(tmp_path):
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"model_id": "m1", "prompt_id": "p1", "__graph_state": {}})
    record = _read_first_jsonl(path)
    assert record["gate_approval_count"] == 0


def test_normalize_unnumbered_143_sets_default_workflow_id():
    normalized = metrics_mod.normalize_unnumbered_143({"event": "x"})
    assert normalized["workflow_id"] == "unknown"


def test_normalize_unnumbered_143_uses_provided_workflow_id():
    normalized = metrics_mod.normalize_unnumbered_143({"event": "x"}, workflow_id="wf-1")
    assert normalized["workflow_id"] == "wf-1"


def test_metrics_context_and_extra_are_applied_to_recorded_event():
    collector = metrics_mod.MetricsCollector()
    with metrics_mod.metrics_context("architect", node="planner", iteration=2, extra={"run": "r1"}):
        event = collector.record_event("validation_metrics", {"ok": True})
    assert event["stage"] == "architect"
    assert event["node"] == "planner"
    assert event["iteration"] == 2
    assert event["context"] == {"run": "r1"}


def test_metrics_extra_none_is_noop():
    collector = metrics_mod.MetricsCollector()
    with metrics_mod.metrics_extra(None):
        event = collector.record_event("generic", {})
    assert event["stage"] == "unknown"


def test_record_llm_usage_supports_dict_and_object_usage_shapes():
    collector = metrics_mod.MetricsCollector()
    dict_response = SimpleNamespace(usage={"input_tokens": 3, "output_tokens": 4}, model="m1")
    object_response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2), model="m2")

    first = collector.record_llm_usage(dict_response, provider="p1")
    second = collector.record_llm_usage(object_response)

    assert first is not None
    assert second is not None
    assert first["data"]["total_tokens"] == 7
    assert second["data"]["model"] == "m2"


def test_record_llm_usage_returns_none_when_usage_missing():
    collector = metrics_mod.MetricsCollector()
    response = SimpleNamespace(model="m1")
    assert collector.record_llm_usage(response) is None


def test_summarize_stage_combines_llm_retrieval_and_validation():
    collector = metrics_mod.MetricsCollector()
    with metrics_mod.metrics_context("architect", iteration=1):
        collector.record_event("llm_usage", {"model": "m1", "prompt_tokens": 2, "completion_tokens": 3})
        collector.record_event("retrieval_strategy", {"strategy": "hybrid"})
        collector.record_event("validation_metrics", {"schema_valid": True})
    summary = collector.summarize_stage("architect", iteration=1)
    assert summary["llm"]["total_calls"] == 1
    assert summary["retrieval"]["strategies"]["hybrid"] == 1
    assert summary["validation"]["schema_valid"] is True


def test_build_workflow_summary_and_reset():
    collector = metrics_mod.MetricsCollector()
    collector.record_event(
        "llm_usage",
        {"model": "m1", "provider": "p1", "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        stage="architect",
    )
    summary = collector.build_workflow_summary()
    assert summary["tokens_total"] == 3
    assert summary["models"] == ["m1"]
    assert summary["providers"] == ["p1"]
    assert summary["tokens_by_stage"]["architect"]["total"] == 3
    collector.reset()
    assert collector.events() == []


def test_build_workflow_summary_empty_returns_empty_dict():
    collector = metrics_mod.MetricsCollector()
    assert collector.build_workflow_summary() == {}


def test_metrics_write_jsonl_appends_and_handles_workflow_id(tmp_path):
    path = tmp_path / "metrics.jsonl"
    collector = metrics_mod.MetricsCollector()
    collector.record_event("x", {"y": 1}, stage="s1")
    collector.record_event("x", {"y": 2}, stage="s2")
    collector.write_jsonl(str(path))

    line1, line2 = path.read_text().splitlines()
    first = json.loads(line1)
    second = json.loads(line2)
    assert first["workflow_id"] == "unknown"
    assert second["workflow_id"] == "unknown"

    collector = metrics_mod.MetricsCollector()
    collector._events = [  # pylint: disable=protected-access
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "x",
            "stage": "s3",
            "node": "s3",
            "iteration": None,
            "data": {"y": 3},
            "workflow_id": "wf-existing",
        }
    ]
    collector.write_jsonl(str(path))
    last = json.loads(path.read_text().splitlines()[-1])
    assert last["workflow_id"] == "wf-existing"


def test_metrics_write_jsonl_logs_warning_on_write_failure(monkeypatch):
    collector = metrics_mod.MetricsCollector()
    collector.record_event("x", {"y": 1}, stage="s1")
    warnings: list[str] = []

    def fake_warning(message, *_args):
        warnings.append(message)

    monkeypatch.setattr(metrics_mod.logger, "warning", fake_warning)
    monkeypatch.setattr(
        metrics_mod,
        "_append_jsonl_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    collector.write_jsonl("/tmp/does_not_matter.jsonl")
    assert warnings


def test_extract_usage_model_and_aggregates_cover_fallback_paths():
    usage_from_raw = metrics_mod._extract_usage(
        SimpleNamespace(_raw_response=SimpleNamespace(usage={"prompt_tokens": 2, "completion_tokens": 1}))
    )
    assert usage_from_raw["total_tokens"] == 3

    usage_from_response = metrics_mod._extract_usage(
        SimpleNamespace(response=SimpleNamespace(usage=SimpleNamespace(input_tokens=4, output_tokens=6)))
    )
    assert usage_from_response["total_tokens"] == 10

    model = metrics_mod._extract_model(SimpleNamespace(_raw_response=SimpleNamespace(model="m-raw")))
    assert model == "m-raw"

    llm_summary = metrics_mod._aggregate_llm_usage(
        [
            {"type": "llm_usage", "data": {"model": "m1", "prompt_tokens": 2, "completion_tokens": 3}},
            {"type": "llm_usage", "data": {"model": "m1", "prompt_tokens": 1, "completion_tokens": 0}},
        ]
    )
    assert llm_summary["total_calls"] == 2
    assert llm_summary["by_model"]["m1"]["total_tokens"] == 6

    retrieval = metrics_mod._aggregate_retrieval(
        [{"type": "retrieval_strategy", "data": {"strategy": "dense"}}]
    )
    assert retrieval["strategies"]["dense"] == 1

    validation = metrics_mod._aggregate_validation(
        [{"type": "validation_metrics", "data": {"ok": True}}]
    )
    assert validation["ok"] is True

    models, providers = metrics_mod._aggregate_models(
        [
            {"type": "llm_usage", "data": {"model": "m1", "provider": "p1"}},
            {"type": "llm_usage", "data": {"model": "m1", "provider": "p1"}},
            {"type": "llm_usage", "data": {"model": "m2", "provider": "p2"}},
        ]
    )
    assert models == ["m1", "m2"]
    assert providers == ["p1", "p2"]
