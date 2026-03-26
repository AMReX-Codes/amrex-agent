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


def test_unnumbered_090_generates_latex_tables_from_metrics(tmp_path, monkeypatch) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    events = [
        {
            "type": "workflow_summary",
            "context": {
                "model_id": "model_alpha",
                "solver": "AMReX",
                "difficulty_tier": "medium",
                "novelty_tier": "known",
                "strategy": "hierarchical",
            },
            "data": {
                "job_status": "completed",
                "iteration": 0,
                "tokens_total": 100,
                "tokens_total_input": 60,
                "tokens_total_output": 40,
            },
        },
        {
            "type": "workflow_summary",
            "context": {
                "model_id": "model_alpha",
                "solver": "AMReX",
                "difficulty_tier": "hard",
                "novelty_tier": "novel",
            },
            "data": {
                "job_status": "failed",
                "iteration": 2,
                "tokens_total": 140,
                "tokens_total_input": 80,
                "tokens_total_output": 60,
                "strategy": "hybrid",
            },
        },
        {
            "type": "workflow_summary",
            "context": {
                "model_id": "model_beta",
                "solver": "WarpX",
                "difficulty_tier": "medium",
                "novelty_tier": "known",
            },
            "data": {
                "job_status": "completed",
                "iteration": 1,
                "tokens_total": 70,
                "tokens_total_input": 30,
                "tokens_total_output": 40,
                "strategy": "simple",
            },
        },
    ]
    metrics_path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    output_path = tmp_path / "reports" / "raw_metrics.jsonl"
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

    table_dir = tmp_path / "reports" / "tables"
    expected_tables = [
        "model_comparison.tex",
        "strategy_performance.tex",
        "validation_effectiveness.tex",
        "cost_analysis.tex",
        "iteration_convergence.tex",
    ]

    for table_name in expected_tables:
        path = table_dir / table_name
        assert path.exists(), f"Expected generated table: {table_name}"
        content = path.read_text(encoding="utf-8")
        assert "\\begin{table}" in content
        assert "\\begin{tabular}" in content

    model_table = (table_dir / "model_comparison.tex").read_text(encoding="utf-8")
    assert "model\\_alpha" in model_table
    assert "model\\_beta" in model_table

    iteration_table = (table_dir / "iteration_convergence.tex").read_text(encoding="utf-8")
    assert "At Iter 0" in iteration_table
    assert "At Iter 1" in iteration_table
    assert "At Iter 2" in iteration_table
