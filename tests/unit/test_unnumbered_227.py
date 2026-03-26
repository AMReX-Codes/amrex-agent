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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_strategy_comparison_populates_from_benchmark_metrics(tmp_path, monkeypatch) -> None:
    benchmark_metrics_path = tmp_path / "benchmark_runs.jsonl"
    benchmark_metrics_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "model_id": "model-a",
                        "prompt_id": "prompt-1",
                        "job_status": "completed",
                        "retrieval_strategy": "hierarchical",
                        "tokens_total_input": 40,
                        "tokens_total_output": 60,
                        "tokens_total": 100,
                    }
                ),
                json.dumps(
                    {
                        "model_id": "model-b",
                        "prompt_id": "prompt-2",
                        "job_status": "failed",
                        "retrieval_strategy": "simple",
                        "tokens_total_input": 30,
                        "tokens_total_output": 50,
                        "tokens_total": 80,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "raw_metrics.jsonl"
    module = _load_aggregate_metrics_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "aggregate_metrics.py",
            "--input",
            str(benchmark_metrics_path),
            "--output",
            str(output_path),
        ],
    )

    module.main()

    by_strategy = _read_csv_rows(tmp_path / "by_strategy.csv")
    assert {row["retrieval_strategy"] for row in by_strategy} == {"hierarchical", "simple"}

    table_path = tmp_path / "strategy_comparison_table.md"
    assert table_path.exists()
    table = table_path.read_text(encoding="utf-8")
    assert "Overall runs: 2" in table
    assert "| hierarchical | 100.00% | 1/1 | 40.0/60.0/100.0 |" in table
    assert "| simple | 0.00% | 0/1 | 30.0/50.0/80.0 |" in table
