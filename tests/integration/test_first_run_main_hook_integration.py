from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.main import main


def _mock_config() -> SimpleNamespace:
    return SimpleNamespace(
        output_dir=Path("/tmp/amrex-agent-test-output"),
        dry_run=False,
        run_mode="full",
        environment="local",
        preconfirm_gate=False,
        llm_gate_strategy="off",
        indexing_strategy="simple",
        inputs_file_strategy="newest",
        inputs_file_override=None,
        remap_strategy=None,
        baseline_override=None,
        baseline_switch_after_retries=3,
        use_mpi=True,
        mpi_ranks=1,
        amrex_agent_root=Path("."),
        non_interactive=False,
        disabled_validators=[],
    )


def test_main_non_tty_preflight_blocks_before_agent_run() -> None:
    config = _mock_config()
    with patch("src.main.load_config", return_value=config):
        with patch("src.main.run_agent") as run_agent_mock:
            with patch("src.main.run_startup_readiness_checks") as preflight_mock:
                with patch("src.main.apply_interactive_fixes") as apply_mock:
                    with patch("sys.stdin.isatty", return_value=False):
                        with patch("sys.stdout.isatty", return_value=False):
                            preflight_mock.return_value = {
                                "mode": "noninteractive",
                                "issues": [
                                    {
                                        "code": "ERF_REPO_MISSING",
                                        "severity": "error",
                                        "suggested_action": "Set ERF_REPO_PATH or clone sibling ERF.",
                                    }
                                ],
                                "unresolved": [
                                    {
                                        "code": "ERF_REPO_MISSING",
                                        "severity": "error",
                                        "suggested_action": "Set ERF_REPO_PATH or clone sibling ERF.",
                                    }
                                ],
                                "exit_code": 1,
                            }
                            with pytest.raises(SystemExit) as exc:
                                main(args=["--prompt", "run test"])

    assert exc.value.code == 1
    run_agent_mock.assert_not_called()
    apply_mock.assert_not_called()
    preflight_mock.assert_called_once()


def test_main_tty_preflight_uses_interactive_fix_path_then_runs_agent() -> None:
    config = _mock_config()
    with patch("src.main.load_config", return_value=config):
        with patch("src.main.run_agent") as run_agent_mock:
            with patch("src.main.run_startup_readiness_checks") as preflight_mock:
                with patch("src.main.apply_interactive_fixes") as apply_mock:
                    with patch("sys.stdin.isatty", return_value=True):
                        with patch("sys.stdout.isatty", return_value=True):
                            preflight_issue = {
                                "code": "ERF_REPO_MISSING",
                                "severity": "error",
                                "suggested_action": "Choose clone/custom path",
                            }
                            preflight_mock.return_value = {
                                "mode": "interactive",
                                "issues": [preflight_issue],
                                "unresolved": [preflight_issue],
                                "exit_code": 0,
                            }
                            apply_mock.return_value = {
                                "mode": "interactive",
                                "attempted_actions": ["clone_missing:erf"],
                                "resolved": [preflight_issue],
                                "unresolved": [],
                                "exit_code": 0,
                            }
                            run_agent_mock.return_value = {
                                "job_status": "completed",
                                "job_id": "test",
                            }

                            main(args=["--prompt", "run test"])

    preflight_mock.assert_called_once()
    apply_mock.assert_called_once()
    run_agent_mock.assert_called_once()
