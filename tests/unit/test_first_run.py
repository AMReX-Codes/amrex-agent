"""Red-phase contract tests for startup readiness checks.

These tests intentionally define the expected behavior of ``src.first_run``
before implementation exists.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


EXPECTED_ISSUE_CODES = {
    "missing_erf_repo": "ERF_REPO_MISSING",
    "erf_commit_mismatch": "ERF_COMMIT_MISMATCH",
    "faiss_missing": "FAISS_INDEX_MISSING",
    "manifest_mismatch": "FAISS_MANIFEST_MISMATCH",
    "schema_stale": "SCHEMA_STALE",
    "noninteractive_blocking": "NONINTERACTIVE_BLOCKING",
    "build_policy": "ERF_BUILD_POLICY",
}


def _extract_issues(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if not isinstance(result, dict):
        return []
    for key in ("issues", "readiness_issues", "blocking_issues"):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _find_issue(issues: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    for issue in issues:
        issue_code = issue.get("code") or issue.get("issue_code")
        if issue_code == code:
            return issue
    return None


def _assert_issue_contract(issue: dict[str, Any], code: str) -> None:
    issue_code = issue.get("code") or issue.get("issue_code")
    severity = issue.get("severity")
    suggested_action = issue.get("suggested_action") or issue.get("action")

    assert issue_code == code
    assert isinstance(severity, str) and severity
    assert isinstance(suggested_action, str) and suggested_action


@pytest.fixture
def first_run_module() -> Any:
    return importlib.import_module("src.first_run")


@pytest.fixture
def no_real_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Real subprocess execution is forbidden in first_run tests")

    monkeypatch.setattr(subprocess, "run", _fail)
    monkeypatch.setattr(subprocess, "Popen", _fail)


def test_missing_erf_repo_path_reports_blocking_issue(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    result = first_run_module.check_repo_readiness(
        repo_root=tmp_path,
        erf_repo_path=tmp_path / "ERF",
    )
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["missing_erf_repo"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["missing_erf_repo"])


def test_repo_exists_but_commit_mismatch_reports_issue(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    erf_repo = tmp_path / "ERF"
    erf_repo.mkdir(parents=True)

    monkeypatch.setattr(first_run_module, "_get_git_head_sha", lambda _p: "actual-sha")

    result = first_run_module.check_dependency_commit_alignment(
        repo_root=tmp_path,
        erf_repo_path=erf_repo,
        expected_dependencies={"repos": {"erf": {"commit": "expected-sha"}}},
    )
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["erf_commit_mismatch"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["erf_commit_mismatch"])


def test_missing_faiss_indices_for_provider_model_reports_issue(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    faiss_root = tmp_path / "database" / "faiss"
    faiss_root.mkdir(parents=True)

    result = first_run_module.check_faiss_readiness(
        faiss_root=faiss_root,
        provider="cborg",
        embedding_model="nomic-embed-text-v1",
    )
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["faiss_missing"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["faiss_missing"])


def test_manifest_endpoint_model_mismatch_reports_issue(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    manifest = {
        "provider": "openai",
        "embedding_model": "text-embedding-3-large",
    }

    result = first_run_module.check_manifest_compatibility(
        manifest=manifest,
        configured_provider="cborg",
        configured_embedding_model="nomic-embed-text-v1",
    )
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["manifest_mismatch"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["manifest_mismatch"])


def test_schema_staleness_detected_reports_issue(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    monkeypatch.setattr(first_run_module, "_detect_schema_staleness", lambda **_kwargs: True)

    result = first_run_module.check_schema_staleness_readiness(
        schema_root=tmp_path / "database" / "schemas",
        repo_root=tmp_path,
    )
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["schema_stale"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["schema_stale"])


def test_tty_interactive_vs_non_tty_fail_fast_behavior(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    blocking_issue = {
        "code": EXPECTED_ISSUE_CODES["noninteractive_blocking"],
        "severity": "error",
        "suggested_action": "Set ERF_REPO_PATH or clone sibling ERF repo",
    }
    monkeypatch.setattr(first_run_module, "_collect_readiness_issues", lambda **_kwargs: [blocking_issue])

    non_tty_result = first_run_module.run_startup_readiness_checks(
        config=SimpleNamespace(non_interactive=True),
        repo_root=tmp_path,
        is_tty=False,
    )
    interactive_result = first_run_module.run_startup_readiness_checks(
        config=SimpleNamespace(non_interactive=False),
        repo_root=tmp_path,
        is_tty=True,
    )

    non_tty_exit = non_tty_result.get("exit_code") if isinstance(non_tty_result, dict) else None
    interactive_exit = interactive_result.get("exit_code") if isinstance(interactive_result, dict) else None
    assert non_tty_exit not in (None, 0)
    assert interactive_exit in (None, 0)


def test_clean_environment_passes_without_prompts(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    monkeypatch.setattr(first_run_module, "_collect_readiness_issues", lambda **_kwargs: [])

    def _prompt_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("No prompts expected for clean environment")

    monkeypatch.setattr("builtins.input", _prompt_called)

    result = first_run_module.run_startup_readiness_checks(
        config=SimpleNamespace(non_interactive=True),
        repo_root=tmp_path,
        is_tty=False,
    )
    assert isinstance(result, dict)
    assert result.get("exit_code", 0) == 0
    assert result.get("issues") in ([], None)


def test_erf_build_readiness_prefers_cmake_with_explicit_fallback(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    erf_repo = tmp_path / "ERF"
    erf_repo.mkdir(parents=True)

    monkeypatch.setattr(first_run_module, "_cmake_available", lambda: False)

    result = first_run_module.check_erf_build_readiness(erf_repo_path=erf_repo)
    issues = _extract_issues(result)
    issue = _find_issue(issues, EXPECTED_ISSUE_CODES["build_policy"])
    assert issue is not None
    _assert_issue_contract(issue, EXPECTED_ISSUE_CODES["build_policy"])

    fallback = issue.get("fallback") or issue.get("fallback_policy")
    assert isinstance(fallback, str) and "gnu" in fallback.lower()


def test_noninteractive_resolver_fail_fast_when_clone_disabled(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    issues = [
        {
            "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
            "severity": "error",
            "suggested_action": "Clone ERF into sibling path",
            "repo_name": "erf",
            "target_path": str(tmp_path / "ERF"),
        }
    ]
    result = first_run_module.resolve_readiness_issues_noninteractive(
        repo_root=tmp_path,
        issues=issues,
        allow_clone_missing=False,
    )
    assert isinstance(result, dict)
    # Require explicit, actionable fail-fast contract (not implicit truthy fallback).
    assert result.get("mode") == "noninteractive"
    assert result.get("attempted_actions") == []
    assert result.get("exit_code") == 1
    unresolved = result.get("unresolved", [])
    assert isinstance(unresolved, list) and unresolved
    unresolved_codes = {item.get("code") or item.get("issue_code") for item in unresolved}
    assert EXPECTED_ISSUE_CODES["missing_erf_repo"] in unresolved_codes


def test_noninteractive_resolver_clone_missing_attempt_marks_issue_resolved(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    target = tmp_path / "ERF"
    issues = [
        {
            "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
            "severity": "error",
            "suggested_action": "Clone ERF into sibling path",
            "repo_name": "erf",
            "target_path": str(target),
        }
    ]

    monkeypatch.setattr(
        first_run_module,
        "_clone_missing_repo",
        lambda **_kwargs: {"ok": True, "path": str(target)},
        raising=False,
    )

    result = first_run_module.resolve_readiness_issues_noninteractive(
        repo_root=tmp_path,
        issues=issues,
        allow_clone_missing=True,
        expected_dependencies={"repos": {"erf": {"url": "file:///tmp/ERF_source"}}},
    )
    assert isinstance(result, dict)
    resolved = result.get("resolved", [])
    assert isinstance(resolved, list) and resolved
    assert result.get("unresolved", []) == []


def test_noninteractive_resolver_accepts_valid_custom_path(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    custom_repo = tmp_path / "custom_erf"
    custom_repo.mkdir(parents=True)
    (custom_repo / ".git").mkdir()

    issues = [
        {
            "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
            "severity": "error",
            "suggested_action": "Provide custom ERF path",
            "repo_name": "erf",
        }
    ]

    result = first_run_module.resolve_readiness_issues_noninteractive(
        repo_root=tmp_path,
        issues=issues,
        allow_clone_missing=False,
        custom_repo_paths={"erf": str(custom_repo)},
    )
    assert isinstance(result, dict)
    assert result.get("unresolved", []) == []
    resolved = result.get("resolved", [])
    assert isinstance(resolved, list) and resolved


def test_interactive_resolver_can_resolve_via_prompted_action(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    issues = [
        {
            "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
            "severity": "error",
            "suggested_action": "Choose clone/custom path",
            "repo_name": "erf",
        }
    ]

    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "clone")
    monkeypatch.setattr(
        first_run_module,
        "_clone_missing_repo",
        lambda **_kwargs: {"ok": True, "path": str(tmp_path / "ERF")},
        raising=False,
    )

    result = first_run_module.resolve_readiness_issues_interactive(
        repo_root=tmp_path,
        issues=issues,
        expected_dependencies={"repos": {"erf": {"url": "file:///tmp/ERF_source"}}},
    )
    assert isinstance(result, dict)
    assert result.get("unresolved", []) == []
    resolved = result.get("resolved", [])
    assert isinstance(resolved, list) and resolved


def test_run_startup_readiness_checks_orchestrates_resolution_usefully(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    """Verify full startup-readiness orchestration performs meaningful work."""
    issue = {
        "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
        "severity": "error",
        "suggested_action": "Clone ERF into sibling path",
    }
    calls: dict[str, Any] = {"collect_called": False, "resolve_called_with": None}

    def _collect(**_kwargs: Any) -> list[dict[str, Any]]:
        calls["collect_called"] = True
        return [issue]

    def _resolve_noninteractive(**kwargs: Any) -> dict[str, Any]:
        calls["resolve_called_with"] = kwargs
        return {
            "mode": "noninteractive",
            "attempted_actions": ["clone_missing:erf"],
            "resolved": [issue],
            "unresolved": [],
            "exit_code": 0,
        }

    monkeypatch.setattr(first_run_module, "_collect_readiness_issues", _collect)
    monkeypatch.setattr(
        first_run_module,
        "resolve_readiness_issues_noninteractive",
        _resolve_noninteractive,
    )

    result = first_run_module.run_startup_readiness_checks(
        repo_root=tmp_path,
        config=SimpleNamespace(non_interactive=True),
        is_tty=False,
    )

    assert calls["collect_called"] is True
    assert isinstance(calls["resolve_called_with"], dict)
    assert calls["resolve_called_with"].get("issues") == [issue]
    assert isinstance(result, dict)
    assert result.get("mode") == "noninteractive"
    assert result.get("attempted_actions") == ["clone_missing:erf"]
    assert result.get("resolved") == [issue]
    assert result.get("unresolved") == []
    assert result.get("exit_code") == 0


def test_interactive_commit_mismatch_checkout_resolves_issue(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    erf_repo = tmp_path / "ERF"
    erf_repo.mkdir(parents=True)
    (erf_repo / ".git").mkdir()
    issue = {
        "code": EXPECTED_ISSUE_CODES["erf_commit_mismatch"],
        "severity": "error",
        "suggested_action": "Checkout pinned commit or rebuild",
        "repo_name": "erf",
        "repo_path": str(erf_repo),
        "expected_commit": "expected-sha",
        "actual_commit": "actual-sha",
    }

    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "checkout")
    monkeypatch.setattr(first_run_module, "_checkout_repo_commit", lambda *_args, **_kwargs: True)

    result = first_run_module.resolve_readiness_issues_interactive(
        repo_root=tmp_path,
        issues=[issue],
    )
    assert isinstance(result, dict)
    assert result.get("resolved") == [issue]
    assert result.get("unresolved") == []
    assert "checkout_pinned_commit:erf" in (result.get("attempted_actions") or [])


def test_interactive_commit_mismatch_continue_marks_resolved(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    issue = {
        "code": EXPECTED_ISSUE_CODES["erf_commit_mismatch"],
        "severity": "error",
        "suggested_action": "Checkout pinned commit or rebuild",
        "repo_name": "erf",
        "expected_commit": "expected-sha",
        "actual_commit": "actual-sha",
    }

    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "continue")

    result = first_run_module.resolve_readiness_issues_interactive(
        repo_root=tmp_path,
        issues=[issue],
    )
    assert isinstance(result, dict)
    assert result.get("resolved") == [issue]
    assert result.get("unresolved") == []
    assert "continue_with_current_commit:erf" in (result.get("attempted_actions") or [])


def test_interactive_commit_mismatch_abort_leaves_issue_unresolved(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    issue = {
        "code": EXPECTED_ISSUE_CODES["erf_commit_mismatch"],
        "severity": "error",
        "suggested_action": "Checkout pinned commit or rebuild",
        "repo_name": "erf",
        "expected_commit": "expected-sha",
        "actual_commit": "actual-sha",
    }

    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "abort")

    result = first_run_module.resolve_readiness_issues_interactive(
        repo_root=tmp_path,
        issues=[issue],
    )
    assert isinstance(result, dict)
    assert result.get("resolved") == []
    assert result.get("unresolved") == [issue]
    assert "abort_commit_mismatch:erf" in (result.get("attempted_actions") or [])


def test_discover_local_repo_candidates_finds_sibling_and_child_erf_git_repos(
    first_run_module: Any,
    tmp_path: Path,
    no_real_subprocess: None,
) -> None:
    sibling_repo = tmp_path.parent / "ERF_sibling"
    sibling_repo.mkdir(parents=True)
    (sibling_repo / ".git").mkdir()

    child_repo = tmp_path / "my_erf_repo"
    child_repo.mkdir(parents=True)
    (child_repo / ".git").mkdir()

    not_git = tmp_path / "ERF_not_git"
    not_git.mkdir(parents=True)

    candidates = first_run_module._discover_local_repo_candidates(tmp_path, "erf")
    as_paths = {str(path) for path in candidates}

    assert str(sibling_repo) in as_paths
    assert str(child_repo) in as_paths
    assert str(not_git) not in as_paths


def test_interactive_missing_repo_select_uses_discovered_candidate(
    first_run_module: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_real_subprocess: None,
) -> None:
    selected_repo = tmp_path.parent / "ERF_selected"
    selected_repo.mkdir(parents=True)
    (selected_repo / ".git").mkdir()

    issue = {
        "code": EXPECTED_ISSUE_CODES["missing_erf_repo"],
        "severity": "error",
        "suggested_action": "Choose clone/custom/select path",
        "repo_name": "erf",
    }
    inputs = iter(["select", "1"])
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: next(inputs))
    monkeypatch.setattr(
        first_run_module,
        "_discover_local_repo_candidates",
        lambda *_args, **_kwargs: [selected_repo],
    )
    monkeypatch.setattr(
        first_run_module,
        "_get_git_head_sha",
        lambda *_args, **_kwargs: "5613ec3943a33d5f0b4f954e34c4e3ff5559a945",
    )

    result = first_run_module.resolve_readiness_issues_interactive(
        repo_root=tmp_path,
        issues=[issue],
    )
    assert isinstance(result, dict)
    assert result.get("resolved") == [issue]
    assert result.get("unresolved") == []
    assert "use_discovered_repo:erf" in (result.get("attempted_actions") or [])
