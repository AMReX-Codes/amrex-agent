import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.benchmark_runner import _write_jsonl, run_model_benchmark
from src.config import AMReXAgentConfig, resolve_benchmark_lockfile_path
from src.services import plan as plan_service


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


def test_benchmark_environment_contract_defaults_to_containerized_lockfile() -> None:
    config = AMReXAgentConfig()
    contract = config.get_benchmark_environment_contract()
    assert contract["isolation_mode"] == "container"
    assert contract["reproducible_by_default"] is True
    assert contract["lockfile_exists"] is True
    assert contract["lockfile_path"].endswith("utils/environment-frozen.yaml")


def test_resolve_benchmark_lockfile_path_handles_relative_and_absolute(tmp_path) -> None:
    relative = resolve_benchmark_lockfile_path("locks/bench.lock", repo_root=tmp_path)
    assert relative == tmp_path / "locks" / "bench.lock"

    absolute = tmp_path / "absolute.lock"
    assert resolve_benchmark_lockfile_path(absolute, repo_root=Path("/unused")) == absolute


def test_benchmark_environment_requires_existing_lockfile(tmp_path) -> None:
    missing_lockfile = tmp_path / "missing-environment.lock"
    with pytest.raises(ValueError, match="benchmark_environment_lockfile_missing"):
        AMReXAgentConfig(benchmark_environment_lockfile=missing_lockfile)


def test_benchmark_environment_can_allow_missing_lockfile(tmp_path) -> None:
    missing_lockfile = tmp_path / "missing-environment.lock"
    config = AMReXAgentConfig(
        benchmark_environment_lockfile=missing_lockfile,
        benchmark_require_lockfile=False,
    )
    contract = config.get_benchmark_environment_contract()
    assert contract["lockfile_exists"] is False
    assert contract["reproducible_by_default"] is True


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


def test_normalize_camera_ready_phase_mappings_canonicalizes_phase_shapes():
    normalized = plan_service.normalize_camera_ready_phase_mappings(
        {
            "pipeline_phases": [
                {
                    "phase_id": "benchmark_execution",
                    "implementation_locations": ["src/benchmark_runner.py", ""],
                    "tests": ["tests/unit/test_benchmark_runner.py", 7],
                },
                {
                    "phase": "aggregation",
                    "implementation": "scripts/aggregate_metrics.py",
                    "test_files": "tests/integration/test_oracle_benchmarks.py",
                },
                {
                    "id": "table_generation",
                    "impl_locations": ["scripts/generate_paper_tables.py", None],
                    "coverage": ["tests/unit/test_generate_paper_tables.py", ""],
                },
                {
                    "phase_id": "   ",
                    "implementation_locations": ["scripts/run_benchmark.py"],
                    "tests": ["tests/unit/test_benchmark_runner.py"],
                },
            ]
        }
    )

    assert normalized == [
        {
            "phase_id": "benchmark_execution",
            "implementation_locations": ["src/benchmark_runner.py"],
            "tests": ["tests/unit/test_benchmark_runner.py"],
        },
        {
            "phase_id": "aggregation",
            "implementation_locations": ["scripts/aggregate_metrics.py"],
            "tests": ["tests/integration/test_oracle_benchmarks.py"],
        },
        {
            "phase_id": "table_generation",
            "implementation_locations": ["scripts/generate_paper_tables.py"],
            "tests": ["tests/unit/test_generate_paper_tables.py"],
        },
    ]


def test_camera_ready_phase_report_and_state_helpers_share_logic():
    report_entries = plan_service._camera_ready_phase_entries_from_report(
        {
            "camera_ready_pipeline": [
                {
                    "phase": "benchmark_execution",
                    "implementation": "src/benchmark_runner.py",
                    "tests": "tests/unit/test_benchmark_runner.py",
                }
            ]
        }
    )
    state_entries = plan_service._camera_ready_phase_entries_from_state(
        {
            "benchmark_pipeline": [
                {
                    "id": "benchmark_execution",
                    "locations": ["src/benchmark_runner.py"],
                    "test_locations": ["tests/unit/test_benchmark_runner.py"],
                }
            ]
        }
    )

    assert report_entries == [
        {
            "phase_id": "benchmark_execution",
            "implementation_locations": ["src/benchmark_runner.py"],
            "tests": ["tests/unit/test_benchmark_runner.py"],
        }
    ]
    assert state_entries == report_entries
