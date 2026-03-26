"""Unit tests for schema staleness detection and mismatch policy handling."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import AMReXAgentConfig, _default_repo_root
from src.services.schema_staleness import (
    PolicyResult,
    RepoMismatch,
    SchemaStalenessError,
    StalenessReport,
    apply_mismatch_policy,
    check_schema_staleness,
)


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_git_repo(repo_path: Path) -> str:
    repo_path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], repo_path)
    _run(["git", "config", "user.email", "tests@example.com"], repo_path)
    _run(["git", "config", "user.name", "tests"], repo_path)

    (repo_path / "README.md").write_text("init\n", encoding="utf-8")
    _run(["git", "add", "README.md"], repo_path)
    _run(["git", "commit", "-m", "init"], repo_path)
    return _run(["git", "rev-parse", "HEAD"], repo_path)


def _advance_git_repo(repo_path: Path) -> str:
    with (repo_path / "README.md").open("a", encoding="utf-8") as f:
        f.write("next\n")
    _run(["git", "add", "README.md"], repo_path)
    _run(["git", "commit", "-m", "advance"], repo_path)
    return _run(["git", "rev-parse", "HEAD"], repo_path)


def _write_schema(schema_path: Path, repo_commits: dict[str, str] | None) -> None:
    payload: dict[str, object] = {"metadata": {"solver": "PeleLMeX"}}
    if repo_commits is not None:
        payload["repo_commits"] = repo_commits
    schema_path.write_text(json.dumps(payload), encoding="utf-8")


class TestStalenessDetection:
    def test_matching_commits_no_staleness(self, tmp_path: Path):
        """Returns clean report when schema SHAs match sibling repo HEADs."""
        erf_repo = tmp_path / "ERF"
        erf_sha = _init_git_repo(erf_repo)

        schema_path = tmp_path / "schema.json"
        _write_schema(schema_path, {"erf": erf_sha})

        report = check_schema_staleness(schema_path, {"erf": erf_repo})

        assert report.is_stale is False
        assert report.mismatched_repos == []

    def test_single_repo_mismatch_detected(self, tmp_path: Path):
        """Detects mismatch and records expected/actual SHA values."""
        erf_repo = tmp_path / "ERF"
        old_sha = _init_git_repo(erf_repo)
        new_sha = _advance_git_repo(erf_repo)

        schema_path = tmp_path / "schema.json"
        _write_schema(schema_path, {"erf": old_sha})

        report = check_schema_staleness(schema_path, {"erf": erf_repo})

        assert report.is_stale is True
        assert [m.repo_name for m in report.mismatched_repos] == ["erf"]
        assert report.mismatched_repos[0].expected_sha == old_sha
        assert report.mismatched_repos[0].actual_sha == new_sha

    def test_multiple_repo_mismatches(self, tmp_path: Path):
        """Detects multiple mismatched sibling repositories."""
        amrex_repo = tmp_path / "amrex"
        pelec_repo = tmp_path / "PeleC"
        amrex_old = _init_git_repo(amrex_repo)
        pelec_old = _init_git_repo(pelec_repo)
        _advance_git_repo(amrex_repo)
        _advance_git_repo(pelec_repo)

        schema_path = tmp_path / "schema.json"
        _write_schema(schema_path, {"amrex": amrex_old, "pelec": pelec_old})

        report = check_schema_staleness(
            schema_path,
            {"amrex": amrex_repo, "pelec": pelec_repo},
        )

        assert report.is_stale is True
        assert {m.repo_name for m in report.mismatched_repos} == {"amrex", "pelec"}

    def test_missing_sibling_repo_counted(self, tmp_path: Path):
        """Marks missing sibling repo path with actual_sha='MISSING'."""
        schema_path = tmp_path / "schema.json"
        _write_schema(schema_path, {"remora": "abc123"})

        report = check_schema_staleness(schema_path, {"remora": tmp_path / "REMORA"})

        assert report.is_stale is True
        assert [m.repo_name for m in report.mismatched_repos] == ["remora"]
        assert report.mismatched_repos[0].actual_sha == "MISSING"

    def test_schema_without_repo_commits_ok(self, tmp_path: Path):
        """Legacy schema (no repo_commits) should return non-stale legacy report."""
        schema_path = tmp_path / "schema.json"
        _write_schema(schema_path, None)

        report = check_schema_staleness(schema_path, {"erf": tmp_path / "ERF"})

        assert report.is_stale is False
        assert report.legacy is True
        assert report.mismatched_repos == []


class TestMismatchPolicy:
    def test_warn_continue_logs_and_continues(self, caplog):
        """Warn policy logs mismatch details and returns proceed=True."""
        report = StalenessReport(
            is_stale=True,
            mismatched_repos=[
                RepoMismatch(repo_name="erf", expected_sha="abc", actual_sha="def")
            ],
        )

        with caplog.at_level("WARNING"):
            result = apply_mismatch_policy(
                report=report,
                policy="warn_continue",
                solver="PeleLMeX",
                solver_path=Path("/repos/PeleLMeX"),
            )

        assert isinstance(result, PolicyResult)
        assert result.proceed is True
        assert "erf" in caplog.text
        assert "build_schema.py" in caplog.text

    def test_fail_policy_raises(self):
        """Fail policy raises with exact rebuild command when stale."""
        report = StalenessReport(
            is_stale=True,
            mismatched_repos=[
                RepoMismatch(repo_name="erf", expected_sha="abc", actual_sha="def")
            ],
        )

        with pytest.raises(SchemaStalenessError) as exc_info:
            apply_mismatch_policy(
                report=report,
                policy="fail",
                solver="PeleLMeX",
                solver_path=Path("/repos/PeleLMeX"),
            )

        message = str(exc_info.value)
        assert "python database/scripts/build_schema.py" in message
        assert "--output database/schemas" in message
        assert "--solver PeleLMeX --auto-compose" in message

    def test_fail_policy_clean_state_ok(self):
        """Fail policy proceeds if staleness report is clean."""
        report = StalenessReport(is_stale=False)

        result = apply_mismatch_policy(
            report=report,
            policy="fail",
            solver="PeleLMeX",
            solver_path=Path("/repos/PeleLMeX"),
        )

        assert result == PolicyResult(proceed=True)

    def test_warn_continue_clean_state_ok(self, caplog):
        """Warn policy should not log warnings when state is clean."""
        report = StalenessReport(is_stale=False)

        with caplog.at_level("WARNING"):
            result = apply_mismatch_policy(
                report=report,
                policy="warn_continue",
                solver="PeleLMeX",
                solver_path=Path("/repos/PeleLMeX"),
            )

        assert result == PolicyResult(proceed=True)
        assert "build_schema.py" not in caplog.text

    def test_auto_rebuild_stale_emits_command(self, caplog):
        """Auto rebuild logs command and marks rebuild_triggered=True."""
        report = StalenessReport(
            is_stale=True,
            mismatched_repos=[
                RepoMismatch(repo_name="erf", expected_sha="abc", actual_sha="def")
            ],
        )

        with patch("src.services.schema_staleness.subprocess.run") as mock_run:
            with caplog.at_level("INFO"):
                result = apply_mismatch_policy(
                    report=report,
                    policy="auto_rebuild",
                    solver="PeleLMeX",
                    solver_path=Path("/repos/PeleLMeX"),
                )

        assert result == PolicyResult(proceed=True, rebuild_triggered=True)
        assert mock_run.called
        assert mock_run.call_args.kwargs["cwd"] == _default_repo_root()
        assert "build_schema.py" in caplog.text

    def test_unknown_policy_raises_valueerror(self):
        """Unknown policy strings should raise ValueError."""
        report = StalenessReport(is_stale=False)

        with pytest.raises(ValueError, match="Unknown database mismatch policy"):
            apply_mismatch_policy(
                report=report,
                policy="invalid_value",
                solver="PeleLMeX",
                solver_path=Path("/repos/PeleLMeX"),
            )


class TestConfigIntegration:
    def test_default_policy_is_warn_continue(self):
        """Config default policy should be warn_continue."""
        config = AMReXAgentConfig()
        assert config.database_mismatch_policy == "warn_continue"

    def test_policy_values_are_validated(self):
        """Invalid config policy values should fail validation."""
        with pytest.raises(ValidationError):
            AMReXAgentConfig(database_mismatch_policy="invalid_value")
