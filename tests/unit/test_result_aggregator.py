import json
import importlib.util
from pathlib import Path

from src.models.sweep_schemas import (
    ChildJobStatus,
    ChildWorkflowState,
    ParentSweepState,
    SweepSpec,
    SweepType,
)
from src.services.result_aggregator import aggregate_results


def _build_parent(children: list[ChildWorkflowState]) -> ParentSweepState:
    completed_count = sum(1 for child in children if child.status == ChildJobStatus.completed)
    failed_count = sum(1 for child in children if child.status == ChildJobStatus.failed)
    spec = SweepSpec(
        sweep_type=SweepType.physics,
        parameter_name="alpha",
        parameter_values=[child.parameter_value for child in children],
        sweep_id="sweep-123",
    )
    return ParentSweepState(
        sweep_id="sweep-123",
        sweep_spec=spec,
        children=children,
        total_count=len(children),
        completed_count=completed_count,
        failed_count=failed_count,
    )


def _child(
    idx: int,
    status: ChildJobStatus,
    value: float,
    failure_reason: str | None = None,
    metrics: dict | None = None,
) -> ChildWorkflowState:
    result_summary = None
    if metrics is not None:
        result_summary = {"result_metrics": metrics}

    return ChildWorkflowState(
        sweep_id="sweep-123",
        sweep_child_id=f"sweep-123-child-{idx}",
        parameter_name="alpha",
        parameter_value=value,
        status=status,
        failure_reason=failure_reason,
        result_summary=result_summary,
    )


class TestSweepSummarySchema:
    def test_summary_json_has_required_keys(self, tmp_path):
        children = [
            _child(0, ChildJobStatus.completed, 1),
            _child(1, ChildJobStatus.completed, 2),
            _child(2, ChildJobStatus.completed, 4),
        ]
        parent = _build_parent(children)

        summary = aggregate_results(parent, tmp_path)

        summary_path = tmp_path / "sweep_summary.json"
        assert summary_path.exists()
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        expected_keys = {
            "sweep_id",
            "sweep_type",
            "parameter",
            "total_count",
            "completed_count",
            "failed_count",
            "status",
            "children",
        }
        assert expected_keys.issubset(loaded.keys())
        assert expected_keys.issubset(summary.keys())

    def test_summary_children_list_correct(self, tmp_path):
        children = [
            _child(0, ChildJobStatus.completed, 1),
            _child(1, ChildJobStatus.completed, 2),
            _child(2, ChildJobStatus.completed, 4),
        ]
        parent = _build_parent(children)

        summary = aggregate_results(parent, tmp_path)

        assert len(summary["children"]) == 3
        for entry in summary["children"]:
            assert {"child_id", "parameter_value", "status", "failure_reason"}.issubset(entry.keys())

    def test_summary_status_completed(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.completed, 1),
                _child(1, ChildJobStatus.completed, 2),
                _child(2, ChildJobStatus.completed, 4),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        assert summary["status"] == "completed"


class TestPartialFailure:
    def test_partial_failure_preserves_failed(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.completed, 1),
                _child(1, ChildJobStatus.completed, 2),
                _child(2, ChildJobStatus.failed, 4, failure_reason="bad input"),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        assert summary["status"] == "partial"
        failed_entries = [entry for entry in summary["children"] if entry["status"] == "failed"]
        assert len(failed_entries) == 1
        assert failed_entries[0]["failure_reason"] == "bad input"

    def test_all_failed_status(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.failed, 1, failure_reason="e1"),
                _child(1, ChildJobStatus.failed, 2, failure_reason="e2"),
                _child(2, ChildJobStatus.failed, 4, failure_reason="e3"),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        assert summary["status"] == "failed"
        assert summary["completed_count"] == 0

    def test_failed_child_has_failure_reason(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.completed, 1),
                _child(1, ChildJobStatus.failed, 2, failure_reason="SFAPI timeout"),
                _child(2, ChildJobStatus.completed, 4),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        failed_entry = next(entry for entry in summary["children"] if entry["child_id"] == "sweep-123-child-1")
        assert failed_entry["failure_reason"] == "SFAPI timeout"


class TestAggregatedMetrics:
    def test_successful_children_aggregated(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.completed, 1, metrics={"wall_time": 10.0}),
                _child(1, ChildJobStatus.completed, 2, metrics={"wall_time": 20.0}),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        assert "aggregated_metrics" in summary
        assert "wall_time" in summary["aggregated_metrics"]
        assert summary["aggregated_metrics"]["wall_time"]["mean"] == 15.0

    def test_failed_children_excluded_from_metrics(self, tmp_path):
        parent = _build_parent(
            [
                _child(0, ChildJobStatus.completed, 1, metrics={"wall_time": 10.0}),
                _child(1, ChildJobStatus.failed, 2, failure_reason="boom", metrics={"wall_time": 999.0}),
            ]
        )

        summary = aggregate_results(parent, tmp_path)

        wall_time = summary["aggregated_metrics"]["wall_time"]
        assert wall_time["mean"] == 10.0
        assert wall_time["min"] == 10.0
        assert wall_time["max"] == 10.0


def _load_aggregate_metrics_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "aggregate_metrics.py"
    spec = importlib.util.spec_from_file_location("aggregate_metrics", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load aggregate_metrics module.")
    spec.loader.exec_module(module)
    return module


class TestSweepSavingsVsNaive:
    def test_by_strategy_includes_naive_savings_delta(self):
        module = _load_aggregate_metrics_module()
        records = [
            {
                "retrieval_strategy": "naive",
                "job_status": "completed",
                "tokens_total": 100,
                "tokens_total_input": 70,
                "tokens_total_output": 30,
            },
            {
                "retrieval_strategy": "sweep",
                "job_status": "completed",
                "tokens_total": 80,
                "tokens_total_input": 55,
                "tokens_total_output": 25,
            },
        ]

        rows = module._group_summary(records, "retrieval_strategy", "retrieval_strategy")
        sweep_row = next(row for row in rows if row["retrieval_strategy"] == "sweep")
        naive_row = next(row for row in rows if row["retrieval_strategy"] == "naive")

        assert naive_row["savings_tokens_total_vs_naive"] == 0.0
        assert naive_row["savings_tokens_total_pct_vs_naive"] == 0.0
        assert sweep_row["naive_avg_tokens_total"] == 100.0
        assert sweep_row["savings_tokens_total_vs_naive"] == 20.0
        assert sweep_row["savings_tokens_total_pct_vs_naive"] == 20.0
        assert sweep_row["savings_tokens_input_vs_naive"] == 15.0
        assert sweep_row["savings_tokens_output_vs_naive"] == 5.0

    def test_by_strategy_without_naive_sets_savings_fields_none(self):
        module = _load_aggregate_metrics_module()
        records = [
            {
                "retrieval_strategy": "sweep",
                "job_status": "completed",
                "tokens_total": 80,
                "tokens_total_input": 55,
                "tokens_total_output": 25,
            }
        ]

        rows = module._group_summary(records, "retrieval_strategy", "retrieval_strategy")
        row = rows[0]

        assert row["retrieval_strategy"] == "sweep"
        assert row["naive_avg_tokens_total"] is None
        assert row["savings_tokens_total_vs_naive"] is None
        assert row["savings_tokens_total_pct_vs_naive"] is None
