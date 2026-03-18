"""Startup readiness preflight stubs.

Phase 4 requires failing tests before implementation. This module provides
importable placeholders only; behavior is intentionally incomplete.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _get_git_head_sha(_repo_path: Path) -> str:
    return ""


def _detect_schema_staleness(**_kwargs: Any) -> bool:
    return False


def _cmake_available() -> bool:
    return True


def _collect_readiness_issues(**_kwargs: Any) -> list[dict[str, Any]]:
    return []


def check_repo_readiness(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def check_dependency_commit_alignment(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def check_faiss_readiness(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def check_manifest_compatibility(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def check_schema_staleness_readiness(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def check_erf_build_readiness(**_kwargs: Any) -> dict[str, Any]:
    return {"issues": []}


def run_startup_readiness_checks(**_kwargs: Any) -> dict[str, Any]:
    # Intentionally wrong placeholder to keep tests red in Phase 4.
    return {"exit_code": 1, "issues": []}


def resolve_readiness_issues_noninteractive(**_kwargs: Any) -> dict[str, Any]:
    # Intentionally incomplete placeholder for Phase 4.
    return {"resolved": [], "unresolved": _kwargs.get("issues", [])}


def resolve_readiness_issues_interactive(**_kwargs: Any) -> dict[str, Any]:
    # Intentionally incomplete placeholder for Phase 4.
    return {"resolved": [], "unresolved": _kwargs.get("issues", [])}
