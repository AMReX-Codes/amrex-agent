"""Schema staleness checks against sibling repository HEAD commits."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import subprocess

from src.config import _default_repo_root


logger = logging.getLogger(__name__)


@dataclass
class RepoMismatch:
    repo_name: str
    expected_sha: str
    actual_sha: str


@dataclass
class StalenessReport:
    is_stale: bool
    mismatched_repos: list[RepoMismatch] = field(default_factory=list)
    legacy: bool = False


@dataclass
class PolicyResult:
    proceed: bool
    rebuild_triggered: bool = False


class SchemaStalenessError(RuntimeError):
    """Raised when mismatch policy is set to fail on stale schema."""


def check_schema_staleness(
    schema_path: Path,
    repo_paths: dict[str, Path],
) -> StalenessReport:
    """Compare schema repo commit provenance with local sibling repo HEAD SHAs."""
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    repo_commits = _extract_repo_commits(schema_data)
    if repo_commits is None:
        return StalenessReport(is_stale=False, mismatched_repos=[], legacy=True)

    mismatches: list[RepoMismatch] = []
    for repo_name, expected_sha in repo_commits.items():
        repo_path = repo_paths.get(repo_name)
        actual_sha = _get_repo_head(repo_path) if repo_path is not None else "MISSING"
        if actual_sha != expected_sha:
            mismatches.append(
                RepoMismatch(
                    repo_name=repo_name,
                    expected_sha=expected_sha,
                    actual_sha=actual_sha,
                )
            )

    return StalenessReport(
        is_stale=bool(mismatches),
        mismatched_repos=mismatches,
        legacy=False,
    )


def apply_mismatch_policy(
    report: StalenessReport,
    policy: str,
    solver: str,
    solver_path: Path,
) -> PolicyResult:
    """Apply configured policy for schema staleness mismatches."""
    valid_policies = {"warn_continue", "fail", "auto_rebuild"}
    if policy not in valid_policies:
        raise ValueError(f"Unknown database mismatch policy: {policy}")

    if not report.is_stale:
        return PolicyResult(proceed=True)

    mismatch_names = ", ".join(m.repo_name for m in report.mismatched_repos)
    mismatch_details = ", ".join(
        f"{m.repo_name}(expected={m.expected_sha}, actual={m.actual_sha})"
        for m in report.mismatched_repos
    )
    rebuild_cmd = _rebuild_command(solver=solver, solver_path=solver_path)

    if policy == "warn_continue":
        logger.warning(
            "Schema staleness detected for repos [%s]: %s. Rebuild with: %s",
            mismatch_names,
            mismatch_details,
            rebuild_cmd,
        )
        return PolicyResult(proceed=True)

    if policy == "fail":
        raise SchemaStalenessError(
            "Schema staleness detected for repos "
            f"[{mismatch_names}]: {mismatch_details}. "
            f"Rebuild command: {rebuild_cmd}"
        )

    logger.info(
        "Schema staleness detected for repos [%s]. Triggering rebuild command: %s",
        mismatch_names,
        rebuild_cmd,
    )
    result = subprocess.run(
        _rebuild_command_args(solver=solver, solver_path=solver_path),
        capture_output=True,
        text=True,
        check=False,
        cwd=_default_repo_root(),
    )
    if result.returncode != 0:
        logger.warning(
            "Schema rebuild command exited non-zero (%s): %s",
            result.returncode,
            (result.stderr or "").strip(),
        )
    return PolicyResult(proceed=True, rebuild_triggered=True)


def _get_repo_head(repo_path: Path) -> str:
    """Return repository HEAD SHA or 'MISSING' if unavailable."""
    if not repo_path.exists():
        return "MISSING"

    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "MISSING"

    head_sha = result.stdout.strip()
    return head_sha if head_sha else "MISSING"


def _rebuild_command(
    solver: str,
    solver_path: Path,
) -> str:
    """Return CLI command for rebuilding the schema."""
    return (
        "python database/scripts/build_schema.py "
        f"{solver_path} --output database/schemas --solver {solver} --auto-compose"
    )


def _rebuild_command_args(solver: str, solver_path: Path) -> list[str]:
    return [
        "python",
        "database/scripts/build_schema.py",
        str(solver_path),
        "--output",
        "database/schemas",
        "--solver",
        solver,
        "--auto-compose",
    ]


def _extract_repo_commits(schema_data: dict) -> dict[str, str] | None:
    top_level = schema_data.get("repo_commits")
    if isinstance(top_level, dict):
        return {str(k): str(v) for k, v in top_level.items()}

    metadata = schema_data.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("repo_commits"), dict):
        return {str(k): str(v) for k, v in metadata["repo_commits"].items()}

    return None
