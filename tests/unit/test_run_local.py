from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.run_local import LocalRunner


def test_setup_job_uses_run_dir_and_copies_files(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()

    monkeypatch.setattr(
        "src.services.run_local.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )
    monkeypatch.setattr(
        "src.services.run_local.copy_to_rundir",
        SimpleNamespace(invoke=lambda payload: {"inputs": str(run_dir / "inputs")}),
    )

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    result = runner.setup_job(
        case_dir=tmp_path,
        executable_path=str(tmp_path / "solver.ex"),
    )

    assert Path(result["run_dir"]) == run_dir
    assert result["inputs"] == str(run_dir / "inputs")
    assert "files" in result


def test_submit_dry_run_writes_script(tmp_path):
    run_dir = tmp_path / "run_local"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.ex"
    exe.write_text("binary")

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    result = runner.submit(run_dir, nodes=2, dry_run=True)

    script_path = Path(result["script_path"])
    assert result["method"] == "dry_run"
    assert script_path.exists()
    assert "mpirun -np 2" in script_path.read_text()


def test_submit_missing_executable_raises(tmp_path):
    run_dir = tmp_path / "run_missing"
    run_dir.mkdir()

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    with pytest.raises(FileNotFoundError):
        runner.submit(run_dir, dry_run=True)


def test_erf_finds_executable_from_config_path_before_compile(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    config_exe = tmp_path / "central" / "ERF3d.gnu.TEST.MPI.ex"
    config_exe.parent.mkdir(parents=True)
    config_exe.write_text("binary")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=config_exe,
        erf_repo_path=repo_root,
    )
    runner = LocalRunner(config)

    exe_path = runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=False)
    assert Path(exe_path) == config_exe


def test_erf_finds_executable_in_derived_central_build_dir(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    central_exe = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.ex"
    central_exe.write_text("binary")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=None,
        erf_repo_path=repo_root,
    )
    runner = LocalRunner(config)

    exe_path = runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=False)
    assert Path(exe_path) == central_exe


def test_non_erf_compiles_when_case_has_no_executable(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    compiled_exe = case_dir / "solver.MPI.ex"
    compiled_exe.write_text("binary")

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    calls = {"count": 0}

    def fake_find(_case_dir, require_mpi=True, require_cuda=True):
        calls["count"] += 1
        return None if calls["count"] == 1 else compiled_exe

    monkeypatch.setattr(runner, "_find_exe_in_dir", fake_find)
    monkeypatch.setattr("src.services.run_local.compile_solver", lambda **kwargs: True)

    exe_path = runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=False)
    assert Path(exe_path) == compiled_exe


def test_non_erf_compile_failure_raises(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    monkeypatch.setattr(runner, "_find_exe_in_dir", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.services.run_local.compile_solver", lambda **kwargs: False)

    with pytest.raises(RuntimeError, match="Compilation failed"):
        runner.find_or_compile_executable(case_dir=case_dir)


def test_non_erf_compiled_but_missing_executable_raises(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)

    monkeypatch.setattr(runner, "_find_exe_in_dir", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.services.run_local.compile_solver", lambda **kwargs: True)

    with pytest.raises(RuntimeError, match="Compiled but no executable found"):
        runner.find_or_compile_executable(case_dir=case_dir)


def test_erf_missing_all_fallbacks_raises_with_checked_paths(tmp_path):
    case_dir = tmp_path / "case_without_erf"
    case_dir.mkdir()
    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=None,
        erf_repo_path=None,
    )
    runner = LocalRunner(config)

    with pytest.raises(RuntimeError, match="No ERF executable found. Checked paths:"):
        runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=False)


def test_derive_erf_central_build_dir_returns_none_for_non_erf_paths(tmp_path):
    config = SimpleNamespace(default_solver="ERF", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    assert runner._derive_erf_central_build_dir(tmp_path / "not_erf" / "Exec" / "ABL") is None


def test_resolve_erf_executable_path_expands_env_var(tmp_path, monkeypatch):
    case_dir = tmp_path / "ERF" / "Exec" / "ABL" / "Case"
    case_dir.mkdir(parents=True)
    env_exe = tmp_path / "central" / "ERF3d.gnu.TEST.MPI.ex"
    env_exe.parent.mkdir(parents=True)
    env_exe.write_text("binary")
    monkeypatch.setenv("ERF_EXE_PATH", str(env_exe))

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path="$ERF_EXE_PATH",
        erf_repo_path=tmp_path / "ERF",
    )
    runner = LocalRunner(config)

    exe, checked = runner._resolve_erf_executable_fallbacks(case_dir)
    assert exe == env_exe
    assert env_exe in checked


def test_submit_non_mpi_executes_and_marks_completed(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_local_exec"
    run_dir.mkdir()
    exe = run_dir / "solver.ex"
    exe.write_text("binary")

    class _Proc:
        pid = 123

        @staticmethod
        def wait():
            return 0

    monkeypatch.setattr("src.services.run_local.subprocess.Popen", lambda *args, **kwargs: _Proc())
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=False)
    runner = LocalRunner(config)

    result = runner.submit(run_dir, nodes=1, dry_run=False)
    assert result["method"] == "local_subprocess"
    assert result["job_status"] == "completed"
    assert result["exit_code"] == 0


def test_submit_execution_failure_marks_failed(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_local_exec_fail"
    run_dir.mkdir()
    exe = run_dir / "solver.ex"
    exe.write_text("binary")

    class _Proc:
        pid = 456

        @staticmethod
        def wait():
            return 2

    monkeypatch.setattr("src.services.run_local.subprocess.Popen", lambda *args, **kwargs: _Proc())
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=False)
    runner = LocalRunner(config)

    result = runner.submit(run_dir, nodes=1, dry_run=False)
    assert result["job_status"] == "failed"
    assert result["exit_code"] == 2


def test_find_or_compile_returns_existing_executable_without_compile(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    existing = case_dir / "solver.MPI.ex"
    existing.write_text("binary")

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    assert Path(runner.find_or_compile_executable(case_dir=case_dir)) == existing


def test_find_exe_falls_back_to_first_ex_when_no_name_match(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    first = case_dir / "solver_plain.ex"
    first.write_text("binary")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    assert runner._find_exe_in_dir(case_dir, require_mpi=True, require_cuda=False) == first


def test_resolve_erf_fallback_returns_none_when_central_has_no_exe(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    (repo_root / "Exec" / "ABL").mkdir(parents=True, exist_ok=True)

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=None,
        erf_repo_path=repo_root,
    )
    runner = LocalRunner(config)
    exe, _ = runner._resolve_erf_executable_fallbacks(case_dir=case_dir)
    assert exe is None


def test_setup_job_requires_case_dir_or_executable(tmp_path):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    with pytest.raises(ValueError, match="Must provide either executable_path or case_dir"):
        runner.setup_job(case_dir=None, executable_path=None)


def test_setup_job_inputs_path_branch_and_base_name_override(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_777"
    run_dir.mkdir()
    captured = {}

    monkeypatch.setattr(
        "src.services.run_local.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )

    def _copy(payload):
        captured["payload"] = payload
        return {"inputs": str(run_dir / "inputs")}

    monkeypatch.setattr("src.services.run_local.copy_to_rundir", SimpleNamespace(invoke=_copy))

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    result = runner.setup_job(
        inputs_path=tmp_path / "inputs.test",
        case_dir=tmp_path,
        executable_path=str(tmp_path / "solver.ex"),
        base_name="custom",
    )
    assert result["inputs"].endswith("inputs")
    assert "inputs_path" in captured["payload"]


def test_setup_job_requires_inputs_or_case_dir_for_copy(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_778"
    run_dir.mkdir()
    monkeypatch.setattr(
        "src.services.run_local.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )
    monkeypatch.setattr("src.services.run_local.copy_to_rundir", SimpleNamespace(invoke=lambda payload: {"inputs": "x"}))

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    with pytest.raises(ValueError, match="Must provide either inputs_path or case_dir"):
        runner.setup_job(case_dir=None, inputs_path=None, executable_path=str(tmp_path / "solver.ex"))


def test_setup_job_raises_when_default_solver_missing(tmp_path):
    config = SimpleNamespace(default_solver=None, output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    with pytest.raises(ValueError, match="No default solver configured"):
        runner.setup_job(case_dir=tmp_path, executable_path=str(tmp_path / "solver.ex"))


def test_setup_job_uses_existing_timestamped_run_dir(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_abc"
    run_dir.mkdir()
    monkeypatch.setattr("src.services.run_local.copy_to_rundir", SimpleNamespace(invoke=lambda payload: {"inputs": "x"}))
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, use_mpi=True)
    runner = LocalRunner(config)
    result = runner.setup_job(case_dir=tmp_path, executable_path=str(tmp_path / "solver.ex"), output_dir=run_dir)
    assert result["run_dir"] == str(run_dir)


def test_derive_erf_central_dir_from_erf_path_without_repo_root(tmp_path):
    erf_case = tmp_path / "foo" / "ERF" / "Exec" / "ABL" / "Case"
    erf_case.mkdir(parents=True)
    config = SimpleNamespace(default_solver="ERF", output_dir=tmp_path, use_mpi=True, erf_repo_path=None)
    runner = LocalRunner(config)
    derived = runner._derive_erf_central_build_dir(erf_case)
    assert str(derived).endswith("/ERF/Exec/ABL")


def test_resolve_erf_fallback_prefers_case_group_over_configured_regtests(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)

    regtests_dir = repo_root / "Exec" / "RegTests"
    regtests_dir.mkdir(parents=True)
    regtests_exe = regtests_dir / "ERF3d.gnu.TEST.MPI.ex"
    regtests_exe.write_text("regtests")

    abl_dir = repo_root / "Exec" / "ABL"
    abl_dir.mkdir(parents=True, exist_ok=True)
    abl_exe = abl_dir / "ERF3d.gnu.TEST.MPI.ex"
    abl_exe.write_text("abl")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=None,
        erf_repo_path=repo_root,
        erf_central_build_dir=regtests_dir,
    )
    runner = LocalRunner(config)

    exe, checked = runner._resolve_erf_executable_fallbacks(case_dir=case_dir)
    assert exe == abl_exe
    assert abl_dir in checked


def test_erf_fallback_prefers_cmake_build_exec_when_present(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    cmake_exe = repo_root / "build" / "Exec" / "erf_exec"
    cmake_exe.parent.mkdir(parents=True)
    cmake_exe.write_text("binary")

    gnumake_exe = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.ex"
    gnumake_exe.parent.mkdir(parents=True, exist_ok=True)
    gnumake_exe.write_text("binary")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        use_mpi=True,
        erf_executable_path=None,
        erf_repo_path=repo_root,
        erf_central_build_dir=repo_root / "Exec" / "ABL",
    )
    runner = LocalRunner(config)

    exe, _ = runner._resolve_erf_executable_fallbacks(case_dir=case_dir)
    assert exe == cmake_exe


def test_active_solver_prefers_case_repo_path_over_default_solver(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "CanonicalTests" / "SquallLine_2D"
    case_dir.mkdir(parents=True)

    config = SimpleNamespace(
        default_solver="AMREX",
        output_dir=tmp_path,
        use_mpi=True,
        erf_repo_path=repo_root,
    )
    runner = LocalRunner(config)

    assert runner._active_solver_code(case_dir) == "ERF"
