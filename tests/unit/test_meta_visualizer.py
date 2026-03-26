import json

from src.services.meta_visualizer import generate_meta_plots


def _summary(children: list[dict], status: str = "completed") -> dict:
    completed = sum(1 for child in children if child["status"] == "completed")
    failed = sum(1 for child in children if child["status"] == "failed")
    return {
        "sweep_id": "sweep-123",
        "sweep_type": "physics",
        "parameter": "alpha",
        "total_count": len(children),
        "completed_count": completed,
        "failed_count": failed,
        "status": status,
        "children": children,
    }


class TestMetaPlotsDirectory:
    def test_meta_plots_dir_created(self, tmp_path):
        summary = _summary(
            [
                {
                    "child_id": "sweep-123-child-0",
                    "parameter_value": 1,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 10.0},
                }
            ]
        )

        meta_dir = generate_meta_plots(summary, tmp_path)

        assert meta_dir.exists()
        assert meta_dir.is_dir()

    def test_meta_plots_has_summary_plot(self, tmp_path):
        summary = _summary(
            [
                {
                    "child_id": "sweep-123-child-0",
                    "parameter_value": 1,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 10.0},
                },
                {
                    "child_id": "sweep-123-child-1",
                    "parameter_value": 2,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 20.0},
                },
                {
                    "child_id": "sweep-123-child-2",
                    "parameter_value": 4,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 30.0},
                },
            ]
        )

        meta_dir = generate_meta_plots(summary, tmp_path)

        files = list(meta_dir.iterdir())
        assert files
        assert any("sweep-123" in path.name or "alpha" in path.name for path in files)

    def test_failed_children_excluded_from_plots(self, tmp_path):
        summary = _summary(
            [
                {
                    "child_id": "sweep-123-child-0",
                    "parameter_value": 1,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 10.0},
                },
                {
                    "child_id": "sweep-123-child-1",
                    "parameter_value": 2,
                    "status": "failed",
                    "failure_reason": "timeout",
                    "result_metrics": {"wall_time": 999.0},
                },
                {
                    "child_id": "sweep-123-child-2",
                    "parameter_value": 4,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {"wall_time": 30.0},
                },
            ],
            status="partial",
        )

        meta_dir = generate_meta_plots(summary, tmp_path)

        plot_file = next(meta_dir.glob("*plot*.json"))
        payload = json.loads(plot_file.read_text(encoding="utf-8"))
        assert len(payload["points"]) == 2

    def test_all_failed_no_plot_generated(self, tmp_path):
        summary = _summary(
            [
                {
                    "child_id": "sweep-123-child-0",
                    "parameter_value": 1,
                    "status": "failed",
                    "failure_reason": "timeout",
                    "result_metrics": {"wall_time": 10.0},
                },
                {
                    "child_id": "sweep-123-child-1",
                    "parameter_value": 2,
                    "status": "failed",
                    "failure_reason": "oom",
                    "result_metrics": {"wall_time": 20.0},
                },
            ],
            status="failed",
        )

        meta_dir = generate_meta_plots(summary, tmp_path)

        assert meta_dir.exists()
        artifacts = list(meta_dir.iterdir())
        assert len(artifacts) <= 1

    def test_meta_plots_skipped_when_no_metrics(self, tmp_path):
        summary = _summary(
            [
                {
                    "child_id": "sweep-123-child-0",
                    "parameter_value": 1,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {},
                },
                {
                    "child_id": "sweep-123-child-1",
                    "parameter_value": 2,
                    "status": "completed",
                    "failure_reason": None,
                    "result_metrics": {},
                },
            ]
        )

        meta_dir = generate_meta_plots(summary, tmp_path)

        assert meta_dir.exists()
        artifacts = list(meta_dir.iterdir())
        assert len(artifacts) <= 1
