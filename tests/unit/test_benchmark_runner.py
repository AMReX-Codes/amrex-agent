import json
from types import SimpleNamespace

import pytest

from src.benchmark_runner import _write_jsonl, run_model_benchmark


def test_run_model_benchmark_writes_manifest_and_metrics(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_run(*_args, **_kwargs):
        calls.append({"args": _args, "kwargs": _kwargs})
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
    assert (run_dir / "replay_manifest.json").exists()

    prompt_context = run_dir / "runs" / "m1" / "p1" / "benchmark_context.json"
    assert prompt_context.exists()
    context_payload = json.loads(prompt_context.read_text())
    assert context_payload["deterministic_seed"] == 1729
    assert isinstance(context_payload["replay_fingerprint"], str)
    assert context_payload["replay_fingerprint"]

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["determinism"]["seed"] == 1729
    assert manifest["determinism"]["enforce_replay"] is True
    assert isinstance(manifest["determinism"]["replay_fingerprint"], str)

    replay_manifest = json.loads((run_dir / "replay_manifest.json").read_text())
    assert replay_manifest["seed"] == 1729
    assert replay_manifest["enforce_replay"] is True
    assert len(replay_manifest["planned_runs"]) == 1

    record = json.loads((run_dir / "benchmark_runs.jsonl").read_text().splitlines()[0])
    assert record["model_id"] == "m1"
    assert record["prompt_id"] == "p1"
    assert record["run_directory"] is None
    assert record["deterministic_seed"] == 1729
    assert record["replay_fingerprint"] == manifest["determinism"]["replay_fingerprint"]

    env = calls[0]["kwargs"]["env"]
    assert env["PYTHONHASHSEED"] == "1729"
    assert env["AMREX_AGENT_BENCHMARK_SEED"] == "1729"
    assert env["AMREX_AGENT_DETERMINISTIC_REPLAY"] == "1"
    assert env["AMREX_AGENT_REPLAY_FINGERPRINT"] == manifest["determinism"]["replay_fingerprint"]


def test_run_model_benchmark_rejects_non_deterministic_replay_setting(tmp_path):
    config = {
        "prompts": [{"id": "p1", "prompt": "Hello"}],
        "models": [{"id": "m1", "overrides": {"llm_provider": "cborg", "llm_model": "x"}}],
        "run_args": {"dry_run": True, "enforce_replay": False},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config))

    with pytest.raises(ValueError, match="enforce_replay"):
        run_model_benchmark(config_path, tmp_path, run_name="bench_test")


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
