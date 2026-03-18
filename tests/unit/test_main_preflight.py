from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.main import _run_startup_preflight


def test_run_startup_preflight_forwards_config_erf_repo_path() -> None:
    config = SimpleNamespace(
        amrex_agent_root=Path("/tmp/amrex-agent-root"),
        erf_repo_path=Path("/tmp/custom-erf-path"),
    )

    with patch("src.main._is_tty_session", return_value=False):
        with patch("src.main.run_startup_readiness_checks") as readiness_mock:
            readiness_mock.return_value = {"exit_code": 0, "issues": []}
            _run_startup_preflight(config)

    readiness_mock.assert_called_once()
    kwargs = readiness_mock.call_args.kwargs
    assert kwargs["repo_root"] == Path("/tmp/amrex-agent-root")
    assert kwargs["is_tty"] is False
    assert kwargs["allow_clone_missing"] is False
    assert kwargs["erf_repo_path"] == Path("/tmp/custom-erf-path")
