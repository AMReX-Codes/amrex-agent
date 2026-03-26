"""Integration checks for startup-readiness git alignment logic.

This file intentionally uses real git commands in tmp_path-backed repos.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.first_run import check_dependency_commit_alignment
from src.first_run import resolve_readiness_issues_noninteractive


def _run(cmd: list[str], cwd: Path) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def _extract_issues(result: dict) -> list[dict]:
    for key in ("issues", "readiness_issues", "blocking_issues"):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def test_dependency_commit_alignment_detects_real_git_head_mismatch(tmp_path: Path) -> None:
    source_repo = tmp_path / "ERF_source"
    source_repo.mkdir(parents=True)
    _run(["git", "init", "-q"], cwd=source_repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=source_repo)
    _run(["git", "config", "user.name", "Test User"], cwd=source_repo)

    (source_repo / "README.txt").write_text("integration fixture\n", encoding="utf-8")
    _run(["git", "add", "README.txt"], cwd=source_repo)
    _run(["git", "commit", "-q", "-m", "fixture commit"], cwd=source_repo)

    erf_repo = tmp_path / "ERF"
    _run(["git", "clone", "-q", str(source_repo), str(erf_repo)], cwd=tmp_path)

    actual_head = _run(["git", "rev-parse", "HEAD"], cwd=erf_repo)
    expected_sha = "0" * 40
    assert actual_head != expected_sha

    result = check_dependency_commit_alignment(
        repo_root=tmp_path,
        erf_repo_path=erf_repo,
        expected_dependencies={"repos": {"erf": {"commit": expected_sha}}},
    )

    issues = _extract_issues(result)
    mismatch = None
    for issue in issues:
        if (issue.get("code") or issue.get("issue_code")) == "ERF_COMMIT_MISMATCH":
            mismatch = issue
            break

    assert mismatch is not None
    assert (mismatch.get("severity") or "")
    assert (mismatch.get("suggested_action") or mismatch.get("action") or "")


def test_noninteractive_clone_missing_uses_real_local_git_clone(tmp_path: Path) -> None:
    """Exercise clone-missing style behavior using real local git clone in /tmp."""
    source_repo = tmp_path / "ERF_source"
    source_repo.mkdir(parents=True)
    _run(["git", "init", "-q"], cwd=source_repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=source_repo)
    _run(["git", "config", "user.name", "Test User"], cwd=source_repo)
    (source_repo / "README.txt").write_text("clone-missing fixture\n", encoding="utf-8")
    _run(["git", "add", "README.txt"], cwd=source_repo)
    _run(["git", "commit", "-q", "-m", "fixture commit"], cwd=source_repo)
    expected_sha = _run(["git", "rev-parse", "HEAD"], cwd=source_repo)

    missing_target = tmp_path / "ERF"
    assert not missing_target.exists()

    issues = [
        {
            "code": "ERF_REPO_MISSING",
            "severity": "error",
            "suggested_action": "clone missing ERF repo",
            "repo_name": "erf",
            "target_path": str(missing_target),
        }
    ]

    result = resolve_readiness_issues_noninteractive(
        repo_root=tmp_path,
        issues=issues,
        allow_clone_missing=True,
        expected_dependencies={
            "repos": {
                "erf": {
                    "url": str(source_repo),
                    "branch": "master",
                    "commit": expected_sha,
                }
            }
        },
    )

    assert missing_target.exists()
    cloned_head = _run(["git", "rev-parse", "HEAD"], cwd=missing_target)
    assert cloned_head == expected_sha
    unresolved = result.get("unresolved", [])
    assert unresolved == []
