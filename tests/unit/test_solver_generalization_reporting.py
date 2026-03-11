import csv
import importlib.util
import json
from pathlib import Path

import pytest


def _load_compare_models_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "compare_models.py"
    spec = importlib.util.spec_from_file_location("compare_models", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load compare_models module.")
    spec.loader.exec_module(module)
    return module


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def benchmark_records() -> list[dict[str, object]]:
    return [
        {
            "model_id": "model_a",
            "prompt_id": "erf_bubble",
            "solver": "ERF",
            "job_status": "completed",
            "analysis_status": "success",
            "duration_seconds": 10.0,
            "selected_case": "Exec/RegTests/Bubble",
        },
        {
            "model_id": "model_b",
            "prompt_id": "laser_case",
            "job_status": "failed",
            "analysis_status": "failed",
            "duration_seconds": 12.0,
            "selected_case": "warpx_laser_acceleration",
        },
        {
            "model_id": "model_a",
            "prompt_id": "amrex_advection",
            "job_status": "completed",
            "analysis_status": "success",
            "duration_seconds": 8.0,
            "selected_case": "Tests/Amr/Advection_AmrCore",
        },
        {
            "model_id": "model_c",
            "prompt_id": "generic_prompt",
            "job_status": "failed",
            "analysis_status": "failed",
            "duration_seconds": 9.0,
            "selected_case": "unknown_case_path",
        },
        {
            "model_id": "model_d",
            "prompt_id": "combustion_case",
            "solver": "PeleC",
            "job_status": "completed",
            "analysis_status": "success",
            "duration_seconds": 11.0,
            "selected_case": "Exec/RegTests/PMF",
        },
    ]


@pytest.fixture
def generated_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, benchmark_records: list[dict[str, object]]) -> Path:
    input_path = tmp_path / "benchmark_runs.jsonl"
    input_path.write_text("\n".join(json.dumps(record) for record in benchmark_records), encoding="utf-8")

    output_dir = tmp_path / "out"
    module = _load_compare_models_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "compare_models.py",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    module.main()
    return output_dir


@pytest.mark.parametrize(
    ("solver", "total_runs", "completed_runs"),
    [
        ("ERF", "1", "1"),
        ("WarpX", "1", "0"),
        ("AMReX", "1", "1"),
        ("PeleC", "1", "1"),
        ("unknown", "1", "0"),
    ],
)
def test_generalization_by_solver_table_contract(
    generated_tables: Path,
    solver: str,
    total_runs: str,
    completed_runs: str,
) -> None:
    rows = _read_csv_rows(generated_tables / "generalization_by_solver.csv")
    row = next((item for item in rows if item["solver"] == solver), None)
    assert row is not None
    assert row["total_runs"] == total_runs
    assert row["completed_runs"] == completed_runs


def test_summary_includes_generalization_metrics(generated_tables: Path) -> None:
    summary = _read_csv_rows(generated_tables / "summary.csv")[0]
    assert summary["generalization_solver_count"] == "4"
    assert summary["generalization_unknown_runs"] == "1"
    assert float(summary["generalization_cross_solver_success_rate"]) == pytest.approx(0.75)


def test_solver_inference_uses_token_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_compare_models_module()
    monkeypatch.setattr(module, "SOLVER_ALIASES", {"ERF": ("erf",)})

    assert module._infer_solver({"prompt_excerpt": "performance tuning only"}) == "unknown"
    assert module._infer_solver({"prompt_excerpt": "erf bubble case"}) == "ERF"
