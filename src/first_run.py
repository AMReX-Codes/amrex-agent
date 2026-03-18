"""Startup readiness checks for first-run preflight."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

from src.services.faiss_artifacts import faiss_indices_present
from src.services.schema_staleness import check_schema_staleness


ISSUE_ERF_REPO_MISSING = "ERF_REPO_MISSING"
ISSUE_ERF_COMMIT_MISMATCH = "ERF_COMMIT_MISMATCH"
ISSUE_FAISS_INDEX_MISSING = "FAISS_INDEX_MISSING"
ISSUE_FAISS_MANIFEST_MISMATCH = "FAISS_MANIFEST_MISMATCH"
ISSUE_SCHEMA_STALE = "SCHEMA_STALE"
ISSUE_BUILD_POLICY = "ERF_BUILD_POLICY"


def _issue(code: str, severity: str, suggested_action: str, **extra: Any) -> dict[str, Any]:
    issue = {
        "code": code,
        "severity": severity,
        "suggested_action": suggested_action,
    }
    issue.update(extra)
    return issue


def _read_dependencies(repo_root: Path) -> dict[str, Any]:
    deps_path = repo_root / ".dependencies.json"
    if not deps_path.exists():
        return {}
    try:
        return json.loads(deps_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _as_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value)


def _erf_path(repo_root: Path, erf_repo_path: Any = None) -> Path:
    path = _as_path(erf_repo_path)
    if path is not None:
        return path
    return repo_root.parent / "ERF"


def _get_git_head_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _detect_schema_staleness(**kwargs: Any) -> bool:
    schema_root = Path(kwargs.get("schema_root") or "")
    repo_root = Path(kwargs.get("repo_root") or ".")
    repo_paths = kwargs.get("repo_paths") or {"erf": _erf_path(repo_root, kwargs.get("erf_repo_path"))}
    solver = str(kwargs.get("solver") or "erf").lower()
    if not schema_root.exists():
        return False
    candidates = sorted(schema_root.glob(f"{solver}_schema_*.json"))
    if not candidates:
        return False
    report = check_schema_staleness(candidates[-1], repo_paths=repo_paths)
    return bool(report.is_stale)


def _cmake_available() -> bool:
    return which("cmake") is not None


def _manifest_path(faiss_root: Path, provider: str) -> Path:
    return faiss_root / provider / "build_session_manifest.json"


def _clone_missing_repo(**kwargs: Any) -> dict[str, Any]:
    repo_name = str(kwargs.get("repo_name") or "erf").lower()
    repo_root = Path(kwargs.get("repo_root") or ".")
    target_path = Path(kwargs.get("target_path") or _erf_path(repo_root))
    expected = kwargs.get("expected_dependencies") or {}
    repo_meta = (expected.get("repos") or {}).get(repo_name, {})
    repo_url = repo_meta.get("url")
    branch = repo_meta.get("branch")
    commit = repo_meta.get("commit")

    if not repo_url:
        return {"ok": False, "error": "Missing repository URL in dependencies metadata"}

    clone = subprocess.run(
        ["git", "clone", "--recursive", str(repo_url), str(target_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if clone.returncode != 0:
        return {"ok": False, "error": (clone.stderr or "git clone failed").strip()}

    if commit:
        subprocess.run(
            ["git", "-C", str(target_path), "checkout", str(commit)],
            capture_output=True,
            text=True,
            check=False,
        )
    elif branch:
        subprocess.run(
            ["git", "-C", str(target_path), "checkout", str(branch)],
            capture_output=True,
            text=True,
            check=False,
        )

    subprocess.run(
        ["git", "-C", str(target_path), "submodule", "update", "--init", "--recursive"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {"ok": True, "path": str(target_path)}


def check_repo_readiness(**kwargs: Any) -> dict[str, Any]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    erf_repo_path = _erf_path(repo_root, kwargs.get("erf_repo_path"))
    issues: list[dict[str, Any]] = []
    if not erf_repo_path.exists() or not (erf_repo_path / ".git").exists():
        issues.append(
            _issue(
                ISSUE_ERF_REPO_MISSING,
                "error",
                "Add a local ERF repository path or clone ERF into a sibling directory.",
                repo_name="erf",
                target_path=str(erf_repo_path),
            )
        )
    return {"issues": issues}


def check_dependency_commit_alignment(**kwargs: Any) -> dict[str, Any]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    erf_repo_path = _erf_path(repo_root, kwargs.get("erf_repo_path"))
    expected_dependencies = kwargs.get("expected_dependencies") or _read_dependencies(repo_root)
    expected_sha = ((expected_dependencies.get("repos") or {}).get("erf") or {}).get("commit")
    issues: list[dict[str, Any]] = []

    if expected_sha and erf_repo_path.exists():
        actual_sha = _get_git_head_sha(erf_repo_path)
        has_git_metadata = (erf_repo_path / ".git").exists()
        if not actual_sha and not has_git_metadata:
            return {"issues": issues}
        if actual_sha and actual_sha != expected_sha:
            rebuild_cmds = (
                f"ERF_PATH={erf_repo_path} && "
                "python -u database/scripts/build_schema.py \"$ERF_PATH\" --output database/schemas --auto-compose && "
                "python -u scripts/rename_schema_after_build.py --repo-root . --schemas-dir database/schemas --singleton-rename && "
                "python -u database/scripts/build_all_indices.py --level 1 --repo \"$ERF_PATH\" --output database/faiss --provider cborg && "
                "python -u database/scripts/build_all_indices.py --level 2 --repo \"$ERF_PATH\" --output database/faiss --provider cborg && "
                "python -u database/scripts/build_index.py --config erf --type case_structure --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg && "
                "python -u database/scripts/build_index.py --config erf --type case_details --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg && "
                "python -u database/scripts/build_index.py --config erf --type input_templates --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg && "
                "python -u database/scripts/build_all_indices.py --check --output database/faiss --provider cborg"
            )
            issues.append(
                _issue(
                    ISSUE_ERF_COMMIT_MISMATCH,
                    "error",
                    (
                        "Check out the ERF commit pinned in .dependencies.json, or rebuild ERF schema/indices. "
                        f"Suggested rebuild sequence: {rebuild_cmds}"
                    ),
                    expected_commit=expected_sha,
                    actual_commit=actual_sha,
                )
            )
    return {"issues": issues}


def check_faiss_readiness(**kwargs: Any) -> dict[str, Any]:
    faiss_root = Path(kwargs.get("faiss_root") or "database/faiss")
    provider = str(kwargs.get("provider") or "cborg")
    embedding_model = str(kwargs.get("embedding_model") or "")
    provider_root = faiss_root / provider if (faiss_root / provider).exists() else faiss_root
    issues: list[dict[str, Any]] = []
    if not faiss_indices_present(provider_root):
        issues.append(
            _issue(
                ISSUE_FAISS_INDEX_MISSING,
                "error",
                "Run demo/setup_demo_database.sh to build FAISS indices for your embedding provider.",
                provider=provider,
                embedding_model=embedding_model,
            )
        )
    return {"issues": issues}


def check_manifest_compatibility(**kwargs: Any) -> dict[str, Any]:
    manifest = kwargs.get("manifest") or {}
    configured_provider = kwargs.get("configured_provider")
    configured_model = kwargs.get("configured_embedding_model")
    manifest_provider = manifest.get("provider") or manifest.get("embedding_provider")
    manifest_model = manifest.get("embedding_model")

    mismatch = (
        (configured_provider and manifest_provider and str(configured_provider) != str(manifest_provider))
        or (configured_model and manifest_model and str(configured_model) != str(manifest_model))
    )
    if not mismatch:
        return {"issues": []}

    return {
        "issues": [
            _issue(
                ISSUE_FAISS_MANIFEST_MISMATCH,
                "error",
                "Rebuild FAISS indices so provider and embedding model match your current config.",
                configured_provider=configured_provider,
                configured_embedding_model=configured_model,
                manifest_provider=manifest_provider,
                manifest_embedding_model=manifest_model,
            )
        ]
    }


def check_schema_staleness_readiness(**kwargs: Any) -> dict[str, Any]:
    stale = _detect_schema_staleness(**kwargs)
    if not stale:
        return {"issues": []}
    return {
        "issues": [
            _issue(
                ISSUE_SCHEMA_STALE,
                "error",
                "Rebuild schemas and indices because repository commits changed.",
            )
        ]
    }


def check_erf_build_readiness(**kwargs: Any) -> dict[str, Any]:
    erf_repo_path = _as_path(kwargs.get("erf_repo_path"))
    if erf_repo_path is None or not erf_repo_path.exists():
        return {"issues": []}
    if _cmake_available():
        return {"issues": []}
    return {
        "issues": [
            _issue(
                ISSUE_BUILD_POLICY,
                "warning",
                "CMake is unavailable; use the GNUmakefile build fallback for ERF.",
                fallback="GNUmakefile fallback when CMake is unavailable",
            )
        ]
    }


def _load_manifest_for_provider(faiss_root: Path, provider: str) -> dict[str, Any]:
    path = _manifest_path(faiss_root, provider)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _collect_readiness_issues(**kwargs: Any) -> list[dict[str, Any]]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    config = kwargs.get("config")
    provider = kwargs.get("provider") or getattr(config, "embedding_provider", "cborg")
    embedding_model = kwargs.get("embedding_model") or getattr(config, "embedding_model", None)
    faiss_root = Path(kwargs.get("faiss_root") or repo_root / "database" / "faiss")

    checks = [
        check_repo_readiness(repo_root=repo_root, erf_repo_path=kwargs.get("erf_repo_path")),
        check_dependency_commit_alignment(
            repo_root=repo_root,
            erf_repo_path=kwargs.get("erf_repo_path"),
            expected_dependencies=kwargs.get("expected_dependencies"),
        ),
        check_faiss_readiness(
            faiss_root=faiss_root,
            provider=str(provider),
            embedding_model=str(embedding_model or ""),
        ),
        check_manifest_compatibility(
            manifest=kwargs.get("manifest") or _load_manifest_for_provider(faiss_root, str(provider)),
            configured_provider=provider,
            configured_embedding_model=embedding_model,
        ),
        check_schema_staleness_readiness(
            schema_root=Path(kwargs.get("schema_root") or repo_root / "database" / "schemas"),
            repo_root=repo_root,
            erf_repo_path=kwargs.get("erf_repo_path"),
            solver=kwargs.get("solver") or "erf",
        ),
        check_erf_build_readiness(erf_repo_path=kwargs.get("erf_repo_path") or _erf_path(repo_root)),
    ]

    issues: list[dict[str, Any]] = []
    for result in checks:
        issues.extend(result.get("issues", []))
    return issues


def _has_blocking(issues: list[dict[str, Any]]) -> bool:
    return any(str(issue.get("severity", "")).lower() == "error" for issue in issues)


def _config_repo_path(config: Any, repo_name: str) -> Path | None:
    if config is None:
        return None
    normalized = str(repo_name or "").strip().lower()
    attr_map = {
        "erf": "erf_repo_path",
        "pelec": "pelec_repo_path",
        "pelelmex": "pelelmex_repo_path",
        "amrex": "amrex_repo_path",
        "remora": "remora_repo_path",
        "warpx": "warpx_repo_path",
        "incflo": "incflo_repo_path",
        "amrex-tutorials": "amrex_tutorials_repo_path",
    }
    attr_name = attr_map.get(normalized)
    if attr_name:
        direct = _as_path(getattr(config, attr_name, None))
        if direct is not None:
            return direct

    repositories = getattr(config, "repositories", None)
    if isinstance(repositories, dict):
        for key, value in repositories.items():
            if str(key).strip().lower() == normalized:
                resolved = _as_path(value)
                if resolved is not None:
                    return resolved
    return None


def _is_git_repo(path: Path | None) -> bool:
    return path is not None and path.exists() and (path / ".git").exists()


def _interactive_missing_repo_prompt(repo_name: str, custom_path: Path | None) -> str:
    upper = repo_name.upper()
    if custom_path is not None and not _is_git_repo(custom_path):
        return input(
            f"Configured {upper} path is not usable. Type 'custom' to enter a new path, "
            f"'clone' to clone {upper}, or 'skip' to continue: "
        ).strip().lower()
    return input(
        f"{upper} repository is missing. Type 'clone' to clone automatically, "
        "'custom' to provide a path, or 'skip' to continue: "
    ).strip().lower()


def _try_interactive_resolution(
    *,
    response: str,
    repo_name: str,
    repo_root: Path,
    target_path: Path,
    expected_dependencies: dict[str, Any],
) -> tuple[str, bool]:
    if response == "clone":
        result = _clone_missing_repo(
            repo_root=repo_root,
            repo_name=repo_name,
            target_path=str(target_path),
            expected_dependencies=expected_dependencies,
        )
        return (f"clone_missing:{repo_name}", bool(result.get("ok")))
    if response == "custom":
        custom_text = input(f"Enter the full path to your {repo_name.upper()} repository: ").strip()
        custom_path = Path(custom_text) if custom_text else None
        return (f"use_custom_path:{repo_name}", _is_git_repo(custom_path))
    return ("", False)


def resolve_readiness_issues_noninteractive(**kwargs: Any) -> dict[str, Any]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    issues = list(kwargs.get("issues") or [])
    expected_dependencies = kwargs.get("expected_dependencies") or _read_dependencies(repo_root)
    custom_repo_paths = kwargs.get("custom_repo_paths") or {}
    config = kwargs.get("config")
    allow_clone_missing = bool(kwargs.get("allow_clone_missing", False))

    attempted_actions: list[str] = []
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for issue in issues:
        if issue.get("code") != ISSUE_ERF_REPO_MISSING:
            unresolved.append(issue)
            continue

        repo_name = str(issue.get("repo_name") or "erf").lower()
        custom_path = _as_path(custom_repo_paths.get(repo_name)) or _config_repo_path(config, repo_name)
        if _is_git_repo(custom_path):
            attempted_actions.append(f"use_custom_path:{repo_name}")
            resolved.append(issue)
            continue

        sibling_path = Path(issue.get("target_path") or _erf_path(repo_root))
        if _is_git_repo(sibling_path):
            attempted_actions.append(f"use_sibling_repo:{repo_name}")
            resolved.append(issue)
            continue

        if allow_clone_missing:
            clone_result = _clone_missing_repo(
                repo_root=repo_root,
                repo_name=repo_name,
                target_path=str(sibling_path),
                expected_dependencies=expected_dependencies,
            )
            attempted_actions.append(f"clone_missing:{repo_name}")
            if clone_result.get("ok"):
                resolved.append(issue)
                continue

        unresolved.append(issue)

    exit_code = 1 if _has_blocking(unresolved) else 0
    return {
        "mode": "noninteractive",
        "attempted_actions": attempted_actions,
        "resolved": resolved,
        "unresolved": unresolved,
        "exit_code": exit_code,
    }


def resolve_readiness_issues_interactive(**kwargs: Any) -> dict[str, Any]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    issues = list(kwargs.get("issues") or [])
    expected_dependencies = kwargs.get("expected_dependencies") or _read_dependencies(repo_root)
    custom_repo_paths = kwargs.get("custom_repo_paths") or {}
    config = kwargs.get("config")

    attempted_actions: list[str] = []
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for issue in issues:
        if issue.get("code") != ISSUE_ERF_REPO_MISSING:
            unresolved.append(issue)
            continue

        repo_name = str(issue.get("repo_name") or "erf").lower()
        custom_path = _as_path(custom_repo_paths.get(repo_name)) or _config_repo_path(config, repo_name)
        if _is_git_repo(custom_path):
            attempted_actions.append(f"use_custom_path:{repo_name}")
            resolved.append(issue)
            continue

        target_path = Path(issue.get("target_path") or _erf_path(repo_root))
        if _is_git_repo(target_path):
            attempted_actions.append(f"use_sibling_repo:{repo_name}")
            resolved.append(issue)
            continue

        response = _interactive_missing_repo_prompt(repo_name, custom_path)
        action, ok = _try_interactive_resolution(
            response=response,
            repo_name=repo_name,
            repo_root=repo_root,
            target_path=target_path,
            expected_dependencies=expected_dependencies,
        )
        if action:
            attempted_actions.append(action)
        if ok:
            resolved.append(issue)
            continue

        unresolved.append(issue)

    return {
        "mode": "interactive",
        "attempted_actions": attempted_actions,
        "resolved": resolved,
        "unresolved": unresolved,
        "exit_code": 0,
    }


def apply_interactive_fixes(**kwargs: Any) -> dict[str, Any]:
    return resolve_readiness_issues_interactive(**kwargs)


def run_startup_readiness_checks(**kwargs: Any) -> dict[str, Any]:
    repo_root = Path(kwargs.get("repo_root") or ".")
    config = kwargs.get("config")
    is_tty = bool(kwargs.get("is_tty", False))
    non_interactive = bool(getattr(config, "non_interactive", False))

    issues = _collect_readiness_issues(**kwargs)
    if not issues:
        return {"exit_code": 0, "issues": []}

    if non_interactive or not is_tty:
        result = resolve_readiness_issues_noninteractive(
            repo_root=repo_root,
            issues=issues,
            allow_clone_missing=bool(kwargs.get("allow_clone_missing", False)),
            expected_dependencies=kwargs.get("expected_dependencies") or _read_dependencies(repo_root),
            custom_repo_paths=kwargs.get("custom_repo_paths"),
            config=config,
        )
        result.setdefault("issues", issues)
        return result

    return {
        "mode": "interactive",
        "issues": issues,
        "resolved": [],
        "unresolved": issues,
        "exit_code": 0,
    }
