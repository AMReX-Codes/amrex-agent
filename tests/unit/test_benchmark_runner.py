import csv
import json
import sys
from types import SimpleNamespace

from scripts import aggregate_metrics
from src.benchmark_runner import _write_jsonl, run_model_benchmark


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


def _read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_aggregate_metrics_emits_accuracy_latency_cost_strategy_vectors(tmp_path, monkeypatch):
    metrics_path = tmp_path / "metrics_sample.jsonl"
    events = [
        {
            "type": "workflow_summary",
            "stage_latency_ms": 3300,
            "context": {"strategy": "simple", "model_id": "m1"},
            "data": {
                "job_status": "completed",
                "accuracy": 0.75,
                "cost_usd": 0.60,
                "tokens_total": 120,
            },
        },
        {
            "type": "workflow_summary",
            "context": {"strategy": "simple", "model_id": "m1"},
            "data": {
                "job_status": "failed",
                "duration_seconds": 9.0,
                "total_cost_usd": 0.20,
                "tokens_total": 80,
            },
        },
        {
            "type": "workflow_summary",
            "node_latency_ms": 1800,
            "context": {"strategy": "hierarchical", "model_id": "m2"},
            "data": {
                "job_status": "completed",
                "accuracy_score": 0.9,
                "cost_breakdown": {"total_usd": 1.40},
                "tokens_total": 300,
            },
        },
    ]
    metrics_path.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["aggregate_metrics.py", "--input", str(metrics_path)])
    aggregate_metrics.main()

    by_strategy = _read_csv_rows(tmp_path / "by_strategy.csv")
    by_key = {row["retrieval_strategy"]: row for row in by_strategy}

    assert "simple" in by_key
    simple = by_key["simple"]
    assert simple["avg_accuracy"] == "0.75"
    assert simple["accuracy_sample_count"] == "1"
    assert simple["avg_latency_seconds"] == "6.15"
    assert simple["latency_sample_count"] == "2"
    assert simple["avg_cost_usd"] == "0.4"
    assert simple["cost_sample_count"] == "2"

    assert "hierarchical" in by_key
    hierarchical = by_key["hierarchical"]
    assert hierarchical["avg_accuracy"] == "0.9"
    assert hierarchical["avg_latency_seconds"] == "1.8"
    assert hierarchical["avg_cost_usd"] == "1.4"


def test_aggregate_metrics_falls_back_to_success_rate_when_accuracy_missing(tmp_path, monkeypatch):
    metrics_path = tmp_path / "metrics_sample.jsonl"
    events = [
        {
            "type": "workflow_summary",
            "context": {"strategy": "fallback"},
            "data": {"job_status": "completed"},
        },
        {
            "type": "workflow_summary",
            "context": {"strategy": "fallback"},
            "data": {"job_status": "failed"},
        },
    ]
    metrics_path.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["aggregate_metrics.py", "--input", str(metrics_path)])
    aggregate_metrics.main()

    row = _read_csv_rows(tmp_path / "by_strategy.csv")[0]
    assert row["retrieval_strategy"] == "fallback"
    assert row["success_rate"] == "0.5"
    assert row["avg_accuracy"] == "0.5"
    assert row["accuracy_sample_count"] == "2"
