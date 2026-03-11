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


def test_table_updated_from_summary_and_by_strategy(tmp_path, monkeypatch) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    events = [
        {
            "type": "workflow_summary",
            "context": {"model_id": "m1", "strategy": "hierarchical"},
            "data": {
                "job_status": "completed",
                "tokens_total": 100,
                "tokens_total_input": 40,
                "tokens_total_output": 60,
            },
        },
        {
            "type": "workflow_summary",
            "context": {"model_id": "m1", "strategy": "simple"},
            "data": {
                "job_status": "failed",
                "tokens_total": 80,
                "tokens_total_input": 30,
                "tokens_total_output": 50,
            },
        },
    ]
    metrics_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    output_path = tmp_path / "raw_metrics.jsonl"
    module = _load_aggregate_metrics_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "aggregate_metrics.py",
            "--input",
            str(metrics_path),
            "--output",
            str(output_path),
        ],
    )
    module.main()

    table_path = tmp_path / "strategy_comparison_table.md"
    assert table_path.exists()
    table_text = table_path.read_text(encoding="utf-8")

    assert "Overall runs: 2" in table_text
    assert "Overall success rate: 50.00%" in table_text
    assert "| hierarchical | 100.00% | 1/1 | 40.0/60.0/100.0 |" in table_text
    assert "| simple | 0.00% | 0/1 | 30.0/50.0/80.0 |" in table_text
    assert "Generated from `summary.csv` and `by_strategy.csv`." in table_text
