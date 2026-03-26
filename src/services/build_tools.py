"""Build helpers for AMReX-based codes."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from database.configs.registry import is_pele_case_path

from src.services.solver_build_policy import get_solver_build_policy

logger = logging.getLogger(__name__)


def _run_build_command(cmd: list[str], *, cwd: Path, timeout: int = 600) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, Exception) as exc:
        return False, str(exc)

    if result.returncode == 0:
        return True, ""

    tail = (result.stderr or result.stdout or "").strip()[-500:]
    return False, tail


def _contains_flag(args: list[str], key: str) -> bool:
    prefix = f"{key}="
    return any(str(item).startswith(prefix) for item in args)


def _contains_cmake_define(args: list[str], key: str) -> bool:
    prefix = f"-D{key}="
    return any(str(item).startswith(prefix) for item in args)


def _compile_with_cmake(
    case_dir: Path,
    compile_policy: dict[str, Any],
    *,
    jobs: int,
) -> bool:
    source_dir = compile_policy.get("cmake_source_dir")
    build_dir = compile_policy.get("cmake_build_dir")
    if not source_dir or not build_dir:
        return False

    source_path = Path(source_dir).expanduser()
    build_path = Path(build_dir).expanduser()
    if not source_path.exists():
        return False

    configure_args = list(compile_policy.get("cmake_configure_args") or [])
    build_args = list(compile_policy.get("cmake_build_args") or [])
    install_args = list(compile_policy.get("cmake_install_args") or [])
    install_prefix = compile_policy.get("cmake_install_prefix")

    if install_prefix and not _contains_cmake_define(configure_args, "CMAKE_INSTALL_PREFIX"):
        configure_args.append(f"-DCMAKE_INSTALL_PREFIX={install_prefix}")

    commands: list[tuple[list[str], Path]] = [
        (["cmake", "-S", str(source_path), "-B", str(build_path)] + configure_args, case_dir),
        (["cmake", "--build", str(build_path), "--parallel", str(jobs)] + build_args, case_dir),
    ]
    if install_prefix or install_args:
        commands.append((["cmake", "--install", str(build_path)] + install_args, case_dir))

    for cmd, cwd in commands:
        success, details = _run_build_command(cmd, cwd=cwd)
        if not success:
            logger.error("CMake compilation failed: %s", " ".join(cmd))
            if details:
                logger.error("Build output: %s", details)
            return False
    return True


def _compile_with_gnumake(
    case_dir: Path,
    compile_policy: dict[str, Any],
    *,
    use_cuda: bool,
    jobs: int,
) -> bool:
    if not (case_dir / "GNUmakefile").exists():
        return False

    make_flags = list(compile_policy.get("gnumake_build_args") or [])
    if use_cuda and not _contains_flag(make_flags, "USE_CUDA"):
        make_flags.append("USE_CUDA=TRUE")

    clean_targets = list(compile_policy.get("gnumake_clean_targets") or ["realclean"])
    commands: list[list[str]] = []
    is_pele_code = is_pele_case_path(case_dir)
    if is_pele_code:
        commands.append(["make", "TPLrealclean"] + make_flags)
    for target in clean_targets:
        commands.append(["make", str(target)])
    if is_pele_code:
        commands.append(["make", "TPL", f"-j{jobs}"] + make_flags)
    commands.append(["nice", "make", f"-j{jobs}"] + make_flags)

    for cmd in commands:
        success, details = _run_build_command(cmd, cwd=case_dir)
        if not success:
            logger.error("GNUmake compilation failed: %s", " ".join(cmd))
            if details:
                logger.error("Build output: %s", details)
            return False
    return True


def _solver_repo_path(runtime_config: Any, solver_code: str) -> Path | None:
    attr = f"{solver_code.lower()}_repo_path"
    value = getattr(runtime_config, attr, None)
    return Path(value).expanduser() if value else None


def compile_solver(
    case_dir: str | Path,
    solver_code: str,
    runtime_config: Any = None,
    use_cuda: bool = True,
    jobs: int = 12,
) -> bool:
    """Compile a solver with policy-driven branch ordering."""
    case_path = Path(case_dir).expanduser()
    if not case_path.exists():
        return False

    solver = str(solver_code).strip().upper()
    policy = get_solver_build_policy(
        solver,
        runtime_config=runtime_config,
        case_dir=case_path,
        repo_root=_solver_repo_path(runtime_config, solver),
    )
    preference = str(policy.get("build_system_preference", "gnumake")).strip().lower()
    branch_order = ["cmake", "gnumake"] if preference == "cmake" else ["gnumake", "cmake"]
    compile_policy = dict(policy.get("compile_policy") or {})

    for branch in branch_order:
        if branch == "cmake":
            if _compile_with_cmake(case_path, compile_policy, jobs=jobs):
                return True
            continue
        if _compile_with_gnumake(case_path, compile_policy, use_cuda=use_cuda, jobs=jobs):
            return True
    return False


def compile_amrex(
    case_dir: str,
    use_cuda: bool = True,
    jobs: int = 12,
    config: Any = None,
) -> bool:
    """Backward-compatible wrapper around policy-driven compile."""
    solver = str(getattr(config, "default_solver", "AMREX")).strip().upper() or "AMREX"
    return compile_solver(
        case_dir=case_dir,
        solver_code=solver,
        runtime_config=config,
        use_cuda=use_cuda,
        jobs=jobs,
    )
