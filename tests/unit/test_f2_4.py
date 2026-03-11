import csv
import importlib.util
import json
from pathlib import Path


def _load_aggregate_metrics_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "aggregate_metrics.py"
    spec = importlib.util.spec_from_file_location("aggregate_metrics", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load aggregate_metrics module.")
    spec.loader.exec_module(module)
    return module


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_aggregate_metrics_generates_raw_and_grouped_tables(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    nested_dir = run_dir / "nested"
    nested_dir.mkdir(parents=True)

    events = [
        {
            "type": "workflow_summary",
            "context": {
                "model_id": "model-alpha",
                "provider": "provider-a",
                "case_id": "case-1",
                "solver": "AMReX",
                "difficulty_tier": "medium",
                "novelty_tier": "known",
            },
            "data": {
                "job_status": "completed",
                "tokens_total": 120,
                "tokens_total_input": 80,
                "tokens_total_output": 40,
                "iteration": 1,
            },
        },
        {
            "type": "workflow_summary",
            "context": {
                "case_id": "case-2",
                "solver": "WarpX",
                "difficulty_tier": "hard",
                "novelty_tier": "novel",
            },
            "data": {
                "models": ["model-beta"],
                "providers": ["provider-b"],
                "job_status": "failed",
                "tokens_total": 60,
                "tokens_total_input": 20,
                "tokens_total_output": 40,
                "stages": {
                    "retrieval": {
                        "retrieval": {
                            "last": {"strategy": "hybrid"},
                        }
                    }
                },
            },
        },
        {
            "type": "node_event",
            "context": {"model_id": "ignored"},
            "data": {"job_status": "completed"},
        },
    ]

    metrics_path = nested_dir / "metrics_sample.jsonl"
    metrics_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    output_path = run_dir / "reports" / "raw_metrics.jsonl"
    module = _load_aggregate_metrics_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "aggregate_metrics.py",
            "--input",
            str(run_dir),
            "--output",
            str(output_path),
        ],
    )

    module.main()

    assert output_path.exists()
    records = _read_jsonl(output_path)
    assert len(records) == 2

    first = next(record for record in records if record["case_id"] == "case-1")
    assert first["model_id"] == "model-alpha"
    assert first["provider"] == "provider-a"

    second = next(record for record in records if record["case_id"] == "case-2")
    assert second["model_id"] == "model-beta"
    assert second["provider"] == "provider-b"
    assert second["retrieval_strategy"] == "hybrid"

    summary_rows = _read_csv_rows(run_dir / "reports" / "summary.csv")
    assert summary_rows[0]["total_runs"] == "2"
    assert summary_rows[0]["success_runs"] == "1"
    assert summary_rows[0]["success_rate"] == "0.5"

    by_model_rows = _read_csv_rows(run_dir / "reports" / "by_model.csv")
    assert {row["model_id"] for row in by_model_rows} == {"model-alpha", "model-beta"}

    by_solver_rows = _read_csv_rows(run_dir / "reports" / "by_solver.csv")
    assert {row["solver"] for row in by_solver_rows} == {"AMReX", "WarpX"}

    by_strategy_rows = _read_csv_rows(run_dir / "reports" / "by_strategy.csv")
    assert {row["retrieval_strategy"] for row in by_strategy_rows} == {"hybrid", "unknown"}


def test_aggregate_metrics_writes_default_outputs_for_file_input(tmp_path, monkeypatch):
    metrics_path = tmp_path / "metrics_run.jsonl"
    metrics_path.write_text(
        json.dumps(
            {
                "type": "workflow_summary",
                "context": {"case_id": "case-3"},
                "data": {
                    "models": ["model-gamma"],
                    "providers": ["provider-c"],
                    "job_status": "completed",
                    "tokens_total": 10,
                },
            }
        ),
        encoding="utf-8",
    )

    module = _load_aggregate_metrics_module()
    monkeypatch.setattr("sys.argv", ["aggregate_metrics.py", "--input", str(metrics_path)])

    module.main()

    raw_path = tmp_path / "raw_metrics.jsonl"
    assert raw_path.exists()
    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "by_model.csv").exists()
    assert (tmp_path / "by_solver.csv").exists()
    assert (tmp_path / "by_strategy.csv").exists()
    assert (tmp_path / "by_difficulty.csv").exists()
    assert (tmp_path / "by_novelty.csv").exists()

    rows = _read_jsonl(raw_path)
    assert rows[0]["case_id"] == "case-3"
    assert rows[0]["model_id"] == "model-gamma"
    assert rows[0]["provider"] == "provider-c"
