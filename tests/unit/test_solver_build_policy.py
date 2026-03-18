from pathlib import Path
from types import SimpleNamespace

from src.services.solver_build_policy import get_solver_build_policy, resolve_local_executable_fallback


def _find_default_executable(search_dir: Path, require_mpi: bool, require_cuda: bool):
    exes = sorted(search_dir.glob("*.ex"))
    return exes[0] if exes else None


def test_erf_policy_uses_cmake_override_from_config_class():
    policy = get_solver_build_policy("ERF")
    assert policy["build_system_preference"] == "cmake"
    assert policy["cmake_executable_names"] == ["erf_exec"]
    assert policy["cmake_executable_ignores_accel_suffix"] is True
    assert policy["gnumake_executable_globs"] == ["ERF*ex"]


def test_runtime_override_wins_over_solver_default():
    runtime = SimpleNamespace(erf_build_system_preference="gnumake")
    policy = get_solver_build_policy("ERF", runtime_config=runtime)
    assert policy["build_system_preference"] == "gnumake"


def test_resolver_prefers_cmake_when_both_artifacts_exist(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)

    cmake = repo_root / "build" / "Exec" / "erf_exec"
    cmake.parent.mkdir(parents=True)
    cmake.write_text("binary")

    gnumake = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.ex"
    gnumake.parent.mkdir(parents=True, exist_ok=True)
    gnumake.write_text("binary")

    result = resolve_local_executable_fallback(
        solver_code="ERF",
        runtime_config=SimpleNamespace(),
        case_dir=case_dir,
        repo_root=repo_root,
        configured_executable_path=None,
        central_build_dirs=[repo_root / "Exec" / "ABL"],
        require_mpi=True,
        require_cuda=True,
        find_default_executable=_find_default_executable,
    )

    assert result["selected_branch"] == "cmake"
    assert result["executable_path"] == cmake


def test_resolver_falls_back_to_gnumake_when_cmake_missing(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)

    gnumake = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.CUDA.ex"
    gnumake.parent.mkdir(parents=True, exist_ok=True)
    gnumake.write_text("binary")

    result = resolve_local_executable_fallback(
        solver_code="ERF",
        runtime_config=SimpleNamespace(),
        case_dir=case_dir,
        repo_root=repo_root,
        configured_executable_path=None,
        central_build_dirs=[repo_root / "Exec" / "ABL"],
        require_mpi=True,
        require_cuda=True,
        find_default_executable=_find_default_executable,
    )

    assert result["selected_branch"] == "gnumake"
    assert result["executable_path"] == gnumake
