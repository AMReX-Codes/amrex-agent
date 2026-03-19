"""Startup readiness checks for first-run preflight."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from shutil import which
from string import hexdigits
from typing import Any

from src.services.faiss_artifacts import faiss_indices_present
from src.services.schema_staleness import check_schema_staleness

logger = logging.getLogger(__name__)


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


def _checkout_repo_commit(repo_path: Path, commit: str) -> bool:
    if not commit:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_path), "checkout", str(commit)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _short_sha(sha: str) -> str:
    return sha[:10] if sha else "unknown"


def _is_commit_like(value: str) -> bool:
    text = value.strip()
    if len(text) < 7:
        return False
    return all(ch in hexdigits for ch in text)


def _collect_indexed_commits(repo_root: Path, repo_name: str) -> set[str]:
    commits: set[str] = set()
    faiss_root = repo_root / "database" / "faiss"
    if not faiss_root.exists():
        return commits
    for manifest_path in faiss_root.glob("*/build_session_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            solver = str(entry.get("solver") or "").strip().lower()
            if solver != repo_name:
                continue
            for key in ("repo_commit", "dependencies_commit"):
                commit = str(entry.get(key) or "").strip()
                if _is_commit_like(commit):
                    commits.add(commit.lower())
    return commits


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


def _github_https_to_ssh(url: str) -> str:
    text = str(url).strip()
    prefix = "https://github.com/"
    if not text.startswith(prefix):
        return text
    repo_path = text[len(prefix):].strip("/")
    if not repo_path:
        return text
    return f"git@github.com:{repo_path}.git" if not repo_path.endswith(".git") else f"git@github.com:{repo_path}"


def _preferred_clone_urls(repo_url: str) -> list[str]:
    primary = str(repo_url).strip()
    ssh = _github_https_to_ssh(primary)
    if ssh == primary:
        return [primary]
    return [ssh, primary]


def _run_git_streaming(cmd: list[str], *, timeout: int) -> tuple[int, str]:
    """Run a git command with line-by-line streamed output and captured tail."""
    tail_lines: list[str] = []
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if process.stdout is not None:
            for line in process.stdout:
                logger.info("%s", line.rstrip("\n"))
                tail_lines.append(line.rstrip("\n"))
                if len(tail_lines) > 80:
                    tail_lines.pop(0)
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return 124, f"git command timed out after {timeout}s: {' '.join(cmd)}"
    finally:
        if process.stdout is not None:
            process.stdout.close()

    tail = "\n".join(tail_lines).strip()
    return process.returncode, tail[-500:]


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

    clone_timeout = int(kwargs.get("clone_timeout_seconds") or 300)
    clone_error = ""
    selected_url = None
    logger.info(
        "Preflight clone start: repo=%s target=%s timeout=%ss",
        repo_name.upper(),
        target_path,
        clone_timeout,
    )
    for candidate_url in _preferred_clone_urls(str(repo_url)):
        selected_url = candidate_url
        logger.info("Preflight clone attempt: %s", candidate_url)
        if target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)

        clone_rc, clone_tail = _run_git_streaming(
            ["git", "clone", "--recursive", str(candidate_url), str(target_path)],
            timeout=clone_timeout,
        )
        if clone_rc == 124:
            clone_error = clone_tail
            logger.warning("Preflight clone timed out for %s", candidate_url)
            continue
        if clone_rc == 0:
            logger.info("Preflight clone succeeded via %s", candidate_url)
            break
        clone_error = clone_tail or "git clone failed"
        logger.warning("Preflight clone failed for %s", candidate_url)
    else:
        return {"ok": False, "error": clone_error or "git clone failed"}

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

    submodule_rc, submodule_tail = _run_git_streaming(
        ["git", "-C", str(target_path), "submodule", "update", "--init", "--recursive"],
        timeout=clone_timeout,
    )
    if submodule_rc != 0:
        return {"ok": False, "error": submodule_tail or "git submodule update failed"}
    logger.info("Preflight submodule update complete")
    return {"ok": True, "path": str(target_path), "url": selected_url}


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
            rebuild_steps = [
                "python -u database/scripts/build_schema.py \"$ERF_PATH\" --output database/schemas --auto-compose",
                "python -u scripts/rename_schema_after_build.py --repo-root . --schemas-dir database/schemas --singleton-rename",
                "python -u database/scripts/build_all_indices.py --level 1 --repo \"$ERF_PATH\" --output database/faiss --provider cborg",
                "python -u database/scripts/build_all_indices.py --level 2 --repo \"$ERF_PATH\" --output database/faiss --provider cborg",
                "python -u database/scripts/build_index.py --config erf --type case_structure --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg",
                "python -u database/scripts/build_index.py --config erf --type case_details --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg",
                "python -u database/scripts/build_index.py --config erf --type input_templates --source \"$ERF_PATH\" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg",
                "python -u database/scripts/build_all_indices.py --check --output database/faiss --provider cborg",
            ]
            rebuild_cmds = " && \\\n  ".join(rebuild_steps)
            issues.append(
                _issue(
                    ISSUE_ERF_COMMIT_MISMATCH,
                    "error",
                    (
                        "Check out the ERF commit pinned in .dependencies.json, or rebuild ERF schema/indices.\n"
                        "Rebuild sequence:\n"
                        f"  ERF_PATH={erf_repo_path} && \\\n"
                        f"  {rebuild_cmds}"
                    ),
                    expected_commit=expected_sha,
                    actual_commit=actual_sha,
                    repo_name="erf",
                    repo_path=str(erf_repo_path),
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
        print(f"\n{upper} repository path is configured but unusable: {custom_path}")
    else:
        print(f"\n{upper} repository is missing.")
    print("Choose an action:")
    print("  1) Clone pinned repository")
    print("  2) Enter custom local path")
    print("  3) Select from discovered local repositories")
    print("  4) Skip for now")

    while True:
        response = input("Selection [1/2/3/4, default 4]: ").strip().lower()
        if response in {"1", "clone"}:
            return "clone"
        if response in {"2", "custom"}:
            return "custom"
        if response in {"3", "select"}:
            return "select"
        if response in {"", "4", "skip"}:
            return "skip"
        print("Invalid selection. Enter 1, 2, 3, or 4.")


def _interactive_commit_mismatch_prompt(
    repo_name: str,
    expected_commit: str,
    actual_commit: str,
) -> str:
    upper = repo_name.upper()
    print(f"\n{upper} commit mismatch detected.")
    print(f"  expected: {_short_sha(expected_commit)} ({expected_commit})")
    print(f"  actual  : {_short_sha(actual_commit)} ({actual_commit})")
    print("Choose an action:")
    print(f"  1) Checkout pinned commit {_short_sha(expected_commit)}")
    print(f"  2) Continue with current commit {_short_sha(actual_commit)}")
    print("  3) Abort preflight (safe default)")

    while True:
        response = input("Selection [1/2/3, default 3]: ").strip().lower()
        if response in {"1", "checkout"}:
            return "checkout"
        if response in {"2", "continue"}:
            return "continue"
        if response in {"", "3", "abort"}:
            return "abort"
        print("Invalid selection. Enter 1, 2, or 3.")


def _interactive_checkout_failure_prompt(repo_name: str, expected_commit: str) -> str:
    print(f"Checkout to {_short_sha(expected_commit)} failed for {repo_name.upper()}.")
    print("Choose next step:")
    print("  1) Retry checkout")
    print("  2) Continue with current commit")
    print("  3) Abort preflight")
    while True:
        response = input("Selection [1/2/3, default 3]: ").strip().lower()
        if response in {"1", "retry"}:
            return "retry"
        if response in {"2", "continue"}:
            return "continue"
        if response in {"", "3", "abort"}:
            return "abort"
        print("Invalid selection. Enter 1, 2, or 3.")


def _discover_local_repo_candidates(repo_root: Path, repo_name: str) -> list[Path]:
    repo_token = str(repo_name or "").lower()
    candidates: dict[str, Path] = {}

    for base in (repo_root.parent, repo_root):
        if not base.exists():
            continue
        for child in base.iterdir():
            if not child.is_dir():
                continue
            if repo_token not in child.name.lower():
                continue
            if not _is_git_repo(child):
                continue
            candidates[str(child.resolve())] = child

    return [candidates[key] for key in sorted(candidates)]


def _candidate_index_status(head_commit: str, indexed_commits: set[str]) -> str:
    if not head_commit:
        return "unknown"
    return "yes" if head_commit.lower() in indexed_commits else "no"


def _try_interactive_resolution(
    *,
    response: str,
    repo_name: str,
    repo_root: Path,
    target_path: Path,
    expected_dependencies: dict[str, Any],
    discovered_candidates: list[Path] | None = None,
    indexed_commits: set[str] | None = None,
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
    if response == "select":
        candidates = list(discovered_candidates or [])
        if not candidates:
            print("No discovered repositories are available for selection.")
            return (f"select_discovered_repo:{repo_name}", False)
        for idx, candidate in enumerate(candidates, start=1):
            candidate_sha = _get_git_head_sha(candidate)
            status = _candidate_index_status(candidate_sha, indexed_commits or set())
            print(f"[{idx}] {candidate}")
            print(f"    head={_short_sha(candidate_sha)} indexed_match={status}")
        selected = input("Select candidate number: ").strip()
        if not selected.isdigit():
            return (f"select_discovered_repo:{repo_name}", False)
        selected_idx = int(selected)
        if selected_idx < 1 or selected_idx > len(candidates):
            return (f"select_discovered_repo:{repo_name}", False)
        return (f"use_discovered_repo:{repo_name}", _is_git_repo(candidates[selected_idx - 1]))
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
        code = issue.get("code")
        if code == ISSUE_ERF_COMMIT_MISMATCH:
            repo_name = str(issue.get("repo_name") or "erf").lower()
            repo_path = (
                _as_path(issue.get("repo_path"))
                or _as_path(custom_repo_paths.get(repo_name))
                or _config_repo_path(config, repo_name)
                or _erf_path(repo_root)
            )
            expected_commit = str(issue.get("expected_commit") or "")
            actual_commit = str(issue.get("actual_commit") or "")
            response = _interactive_commit_mismatch_prompt(repo_name, expected_commit, actual_commit)
            if response == "checkout":
                attempted_actions.append(f"checkout_pinned_commit:{repo_name}")
                while True:
                    if _is_git_repo(repo_path) and _checkout_repo_commit(repo_path, expected_commit):
                        resolved.append(issue)
                        break
                    next_step = _interactive_checkout_failure_prompt(repo_name, expected_commit)
                    if next_step == "retry":
                        attempted_actions.append(f"retry_checkout_pinned_commit:{repo_name}")
                        continue
                    if next_step == "continue":
                        attempted_actions.append(f"continue_with_current_commit:{repo_name}")
                        resolved.append(issue)
                        break
                    attempted_actions.append(f"abort_commit_mismatch:{repo_name}")
                    unresolved.append(issue)
                    break
                if issue in resolved or issue in unresolved:
                    continue
                unresolved.append(issue)
                continue
            if response == "continue":
                attempted_actions.append(f"continue_with_current_commit:{repo_name}")
                resolved.append(issue)
                continue
            attempted_actions.append(f"abort_commit_mismatch:{repo_name}")
            unresolved.append(issue)
            continue

        if code != ISSUE_ERF_REPO_MISSING:
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

        discovered_candidates = _discover_local_repo_candidates(repo_root, repo_name)
        indexed_commits = _collect_indexed_commits(repo_root, repo_name)
        response = _interactive_missing_repo_prompt(repo_name, custom_path)
        action, ok = _try_interactive_resolution(
            response=response,
            repo_name=repo_name,
            repo_root=repo_root,
            target_path=target_path,
            expected_dependencies=expected_dependencies,
            discovered_candidates=discovered_candidates,
            indexed_commits=indexed_commits,
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
