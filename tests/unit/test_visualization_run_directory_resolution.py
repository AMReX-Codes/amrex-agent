"""Unit tests for visualization run-directory resolution."""

from src.nodes.visualization_node import get_run_directory_and_analysis


def test_prefers_latest_runner_run_directory_over_input_writer():
    state = {
        "workflow_history": [
            {"node": "input_writer", "details": {"run_directory": "output/run_old"}},
            {"node": "runner", "details": {"run_directory": "output/run_new"}},
        ],
        "run_directory": "output/run_state",
        "analysis_report": {"status": "success"},
    }

    run_dir, analysis = get_run_directory_and_analysis(state)  # type: ignore[arg-type]
    assert run_dir == "output/run_new"
    assert analysis.get("status") == "success"


def test_falls_back_to_latest_input_writer_then_state():
    state_with_input_writer = {
        "workflow_history": [
            {"node": "input_writer", "details": {"run_directory": "output/run_iw_old"}},
            {"node": "input_writer", "details": {"run_directory": "output/run_iw_new"}},
        ],
        "run_directory": "output/run_state",
        "analysis_report": {},
    }
    run_dir, _ = get_run_directory_and_analysis(state_with_input_writer)  # type: ignore[arg-type]
    assert run_dir == "output/run_iw_new"

    state_with_state_only = {
        "workflow_history": [],
        "run_directory": "output/run_state_only",
        "analysis_report": {},
    }
    run_dir, _ = get_run_directory_and_analysis(state_with_state_only)  # type: ignore[arg-type]
    assert run_dir == "output/run_state_only"


def test_loads_analysis_report_from_history_when_state_missing():
    state = {
        "workflow_history": [
            {
                "node": "analysis",
                "details": {"report": {"status": "success", "issues": []}},
            }
        ],
        "run_directory": "output/run_state",
        "analysis_report": {},
    }

    _, analysis = get_run_directory_and_analysis(state)  # type: ignore[arg-type]
    assert analysis.get("status") == "success"
