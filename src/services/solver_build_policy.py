"""Build/executable discovery policy resolution from solver config classes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from database.configs.registry import get_config_class


def _runtime_override(runtime_config: Any, key: str, default: Any) -> Any:
    if runtime_config is None:
        return default
    return getattr(runtime_config, key, default)


def get_solver_build_policy(solver_code: str, runtime_config: Any = None) -> dict[str, Any]:
    """Resolve build/executable policy for a solver with optional runtime overrides."""
    solver = str(solver_code).strip().upper()
    solver_config = get_config_class(solver)

    preference = str(
        _runtime_override(
            runtime_config,
            f"{solver.lower()}_build_system_preference",
            solver_config.get_build_system_preference(),
        )
    ).strip().lower()
    if preference not in {"cmake", "gnumake"}:
        preference = "gnumake"

    templates = _runtime_override(
        runtime_config,
        f"{solver.lower()}_executable_search_path_templates",
        solver_config.get_executable_search_path_templates(),
    )

    cmake_names = _runtime_override(
        runtime_config,
        f"{solver.lower()}_cmake_executable_names",
        solver_config.get_cmake_executable_names(),
    )
    cmake_ignore_suffix = bool(
        _runtime_override(
            runtime_config,
            f"{solver.lower()}_cmake_executable_ignores_accel_suffix",
            solver_config.cmake_ignores_accel_suffix(),
        )
    )
    gnumake_globs = _runtime_override(
        runtime_config,
        f"{solver.lower()}_gnumake_executable_globs",
        solver_config.get_gnumake_executable_globs(),
    )

    return {
        "solver_config": solver_config,
        "build_system_preference": preference,
        "executable_search_path_templates": [str(item) for item in (templates or [])],
        "cmake_executable_names": [str(item) for item in (cmake_names or [])],
        "cmake_executable_ignores_accel_suffix": cmake_ignore_suffix,
        "gnumake_executable_globs": [str(item) for item in (gnumake_globs or ["*.ex"])],
    }


def derive_central_build_dir(case_dir: Path, repo_root: Path | None) -> Path | None:
    """Derive central build directory as ``Exec/<group>`` from a case path."""
    case_path = Path(case_dir).resolve()
    repo_path = Path(repo_root).resolve() if repo_root else None

    relative_case = None
    if repo_path:
        try:
            relative_case = case_path.relative_to(repo_path)
        except ValueError:
            relative_case = None

    if relative_case is None:
        return None
    if not relative_case.parts or relative_case.parts[0] != "Exec":
        return None
    if len(relative_case.parts) < 2:
        return None
    return repo_path / "Exec" / relative_case.parts[1]


def central_build_candidates(
    case_dir: Path,
    repo_root: Path | None,
    configured_central_build_dir: str | Path | None = None,
) -> list[Path]:
    """Return ordered unique central-build candidates."""
    candidates: list[Path] = []
    derived = derive_central_build_dir(case_dir, repo_root)
    if derived:
        candidates.append(derived)

    if configured_central_build_dir:
        configured = Path(os.path.expandvars(str(configured_central_build_dir))).expanduser()
        candidates.append(configured)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def expand_local_candidate_dirs(
    *,
    policy: dict[str, Any],
    case_dir: Path,
    repo_root: Path | None,
    central_build_dirs: list[Path],
) -> list[Path]:
    """Expand local template directories from policy tokens."""
    templates = list(policy.get("executable_search_path_templates", []))
    candidates: list[Path] = []

    for template in templates:
        template_text = str(template)
        for central_dir in (central_build_dirs or [None]):
            text = template_text.replace("{case_dir}", str(case_dir))
            text = text.replace("{repo_root}", str(repo_root) if repo_root is not None else "")
            text = text.replace("{central_build_dir}", str(central_dir) if central_dir is not None else "")
            if not text.strip():
                continue
            candidates.append(Path(text).expanduser())

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _matches_requirements(
    exe_name: str,
    *,
    require_mpi: bool,
    require_cuda: bool,
    ignore_accel_suffix: bool,
) -> bool:
    if ignore_accel_suffix:
        return True

    name = exe_name.lower()
    has_mpi = "mpi" in name
    has_cuda = "cuda" in name
    if require_mpi and not has_mpi:
        return False
    if require_cuda and not has_cuda:
        return False
    return True


def _branch_order(preference: str) -> list[str]:
    pref = str(preference).strip().lower()
    return ["cmake", "gnumake"] if pref == "cmake" else ["gnumake", "cmake"]


def resolve_local_executable_fallback(
    *,
    solver_code: str,
    runtime_config: Any,
    case_dir: Path,
    repo_root: Path | None,
    configured_executable_path: str | Path | None,
    central_build_dirs: list[Path],
    require_mpi: bool,
    require_cuda: bool,
    find_default_executable: Callable[[Path, bool, bool], Path | None],
) -> dict[str, Any]:
    """Resolve solver executable fallback using shared policy semantics.

    Returns dict keys:
    - executable_path: Path | None
    - checked_paths: list[Path]
    - effective_policy: dict[str, Any]
    - candidate_dirs: list[Path]
    - branch_order: list[str]
    - selected_branch: str | None
    - matching_rules: dict[str, Any]
    """
    policy = get_solver_build_policy(solver_code, runtime_config=runtime_config)
    checked_paths: list[Path] = [Path(case_dir)]

    if configured_executable_path:
        configured = Path(os.path.expandvars(str(configured_executable_path))).expanduser()
        checked_paths.append(configured)
        if configured.is_file():
            return {
                "executable_path": configured,
                "checked_paths": checked_paths,
                "effective_policy": policy,
                "candidate_dirs": [],
                "branch_order": ["configured"],
                "selected_branch": "configured",
                "matching_rules": {
                    "cmake_executable_names": policy.get("cmake_executable_names", []),
                    "cmake_executable_ignores_accel_suffix": policy.get(
                        "cmake_executable_ignores_accel_suffix", False
                    ),
                    "gnumake_executable_globs": policy.get("gnumake_executable_globs", []),
                },
            }

    candidate_dirs = expand_local_candidate_dirs(
        policy=policy,
        case_dir=Path(case_dir),
        repo_root=repo_root,
        central_build_dirs=central_build_dirs,
    )

    branch_order = _branch_order(str(policy.get("build_system_preference", "gnumake")))
    for branch in branch_order:
        for search_dir in candidate_dirs:
            if search_dir not in checked_paths:
                checked_paths.append(search_dir)
            if not search_dir.exists():
                continue

            if branch == "cmake":
                names = list(policy.get("cmake_executable_names") or [])
                ignore_suffix = bool(policy.get("cmake_executable_ignores_accel_suffix", False))
                for name in names:
                    candidate = search_dir / name
                    if candidate.is_file() and _matches_requirements(
                        candidate.name,
                        require_mpi=require_mpi,
                        require_cuda=require_cuda,
                        ignore_accel_suffix=ignore_suffix,
                    ):
                        return {
                            "executable_path": candidate,
                            "checked_paths": checked_paths,
                            "effective_policy": policy,
                            "candidate_dirs": candidate_dirs,
                            "branch_order": branch_order,
                            "selected_branch": "cmake",
                            "matching_rules": {
                                "cmake_executable_names": names,
                                "cmake_executable_ignores_accel_suffix": ignore_suffix,
                                "gnumake_executable_globs": policy.get("gnumake_executable_globs", []),
                            },
                        }
            else:
                globs = list(policy.get("gnumake_executable_globs") or ["*.ex"])
                for pattern in globs:
                    for candidate in sorted(search_dir.glob(pattern)):
                        if not candidate.is_file():
                            continue
                        if _matches_requirements(
                            candidate.name,
                            require_mpi=require_mpi,
                            require_cuda=require_cuda,
                            ignore_accel_suffix=False,
                        ):
                            return {
                                "executable_path": candidate,
                                "checked_paths": checked_paths,
                                "effective_policy": policy,
                                "candidate_dirs": candidate_dirs,
                                "branch_order": branch_order,
                                "selected_branch": "gnumake",
                                "matching_rules": {
                                    "cmake_executable_names": policy.get("cmake_executable_names", []),
                                    "cmake_executable_ignores_accel_suffix": policy.get(
                                        "cmake_executable_ignores_accel_suffix", False
                                    ),
                                    "gnumake_executable_globs": globs,
                                },
                            }

                fallback = find_default_executable(search_dir, require_mpi, require_cuda)
                if fallback:
                    return {
                        "executable_path": fallback,
                        "checked_paths": checked_paths,
                        "effective_policy": policy,
                        "candidate_dirs": candidate_dirs,
                        "branch_order": branch_order,
                        "selected_branch": "gnumake",
                        "matching_rules": {
                            "cmake_executable_names": policy.get("cmake_executable_names", []),
                            "cmake_executable_ignores_accel_suffix": policy.get(
                                "cmake_executable_ignores_accel_suffix", False
                            ),
                            "gnumake_executable_globs": policy.get("gnumake_executable_globs", []),
                        },
                    }

    return {
        "executable_path": None,
        "checked_paths": checked_paths,
        "effective_policy": policy,
        "candidate_dirs": candidate_dirs,
        "branch_order": branch_order,
        "selected_branch": None,
        "matching_rules": {
            "cmake_executable_names": policy.get("cmake_executable_names", []),
            "cmake_executable_ignores_accel_suffix": policy.get(
                "cmake_executable_ignores_accel_suffix", False
            ),
            "gnumake_executable_globs": policy.get("gnumake_executable_globs", []),
        },
    }
