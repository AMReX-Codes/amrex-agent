import csv
import importlib.util
import json
from pathlib import Path


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


def test_compare_models_generates_tables(tmp_path, monkeypatch):
    input_path = tmp_path / "benchmark_runs.jsonl"
    records = [
        {
            "model_id": "model_a",
            "prompt_id": "prompt_001",
            "job_status": "completed",
            "analysis_status": "success",
            "duration_seconds": 12.0,
            "analysis_performance": {"avg_cells_per_sec": 1000.0},
            "run_directory": "/tmp/run_a",
            "prompt_excerpt": "demo prompt a",
        },
        {
            "model_id": "model_b",
            "prompt_id": "prompt_002",
            "job_status": "failed",
            "analysis_status": "failed",
            "duration_seconds": 8.0,
            "analysis_performance": {"avg_cells_per_sec": 2000.0},
            "run_directory": "/tmp/run_b",
            "prompt_excerpt": "demo prompt b",
        },
    ]
    input_path.write_text("\n".join(json.dumps(r) for r in records))

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

    by_model_path = output_dir / "by_model.csv"
    by_prompt_path = output_dir / "by_prompt.csv"
    summary_path = output_dir / "summary.csv"

    assert by_model_path.exists()
    assert by_prompt_path.exists()
    assert summary_path.exists()

    by_model_rows = _read_csv_rows(by_model_path)
    assert {row["model_id"] for row in by_model_rows} == {"model_a", "model_b"}

    model_a = next(row for row in by_model_rows if row["model_id"] == "model_a")
    assert model_a["total_runs"] == "1"
    assert model_a["completed_runs"] == "1"
    assert model_a["analysis_success_runs"] == "1"

    summary_rows = _read_csv_rows(summary_path)
    assert summary_rows[0]["total_runs"] == "2"
