from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.run_superfacility import SuperfacilityRunner


def test_setup_job_uses_stubbed_tools(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_456"
    run_dir.mkdir()

    monkeypatch.setattr(
        "src.services.run_superfacility.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )
    monkeypatch.setattr(
        "src.services.run_superfacility.copy_to_rundir",
        SimpleNamespace(invoke=lambda payload: {"inputs": str(run_dir / "inputs")}),
    )
    monkeypatch.setattr(
        SuperfacilityRunner,
        "find_or_compile_executable",
        lambda self, case_dir, require_mpi=True, require_cuda=True: str(tmp_path / "solver.MPI.CUDA.ex"),
    )

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    result = runner.setup_job(case_dir=tmp_path)

    assert Path(result["run_dir"]) == run_dir
    assert result["inputs"] == str(run_dir / "inputs")
    assert result["executable"].endswith("solver.MPI.CUDA.ex")


def test_submit_dry_run_writes_script(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_sf"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr(
        "src.services.run_superfacility.generate_slurm_script",
        lambda params, run_dir, config=None: "#!/bin/bash\necho test\n",
    )

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    result = runner.submit(run_dir, nodes=2, walltime="00:05:00", dry_run=True)

    script_path = Path(result["script_path"])
    assert result["method"] == "dry_run"
    assert result["job_status"] == "completed"
    assert script_path.exists()
    assert "echo test" in script_path.read_text()


def test_submit_stage_only_stages_without_submitting(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_sf"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr(
        "src.services.run_superfacility.generate_slurm_script",
        lambda params, run_dir, config=None: "#!/bin/bash\necho stage\n",
    )

    staged = {"called": False}

    def fake_stage_run_directory(**kwargs):
        staged["called"] = True

    monkeypatch.setattr("src.services.run_superfacility.stage_run_directory", fake_stage_run_directory)
    monkeypatch.setattr(
        "src.services.run_superfacility.submit_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("submit_job should not be called")),
    )
    monkeypatch.setattr("src.config.detect_environment", lambda: "local")

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="perlmutter",
    )
    runner = SuperfacilityRunner(config)

    result = runner.submit(run_dir, nodes=1, run_mode="stage")

    assert staged["called"] is True
    assert result["method"] == "stage_only"
    assert result["job_status"] == "completed"


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
        superfacility_account="acct",
        erf_executable_path=config_exe,
        erf_repo_path=repo_root,
    )
    runner = SuperfacilityRunner(config)

    exe_path = runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=True)
    assert Path(exe_path) == config_exe


def test_erf_finds_executable_in_derived_central_build_dir(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    central_exe = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.CUDA.ex"
    central_exe.write_text("binary")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        superfacility_account="acct",
        erf_executable_path=None,
        erf_repo_path=repo_root,
    )
    runner = SuperfacilityRunner(config)

    exe_path = runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=True)
    assert Path(exe_path) == central_exe


def test_erf_fallback_prefers_case_group_over_configured_regtests(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)

    regtests_dir = repo_root / "Exec" / "RegTests"
    regtests_dir.mkdir(parents=True)
    regtests_exe = regtests_dir / "ERF3d.gnu.TEST.MPI.CUDA.ex"
    regtests_exe.write_text("regtests")

    abl_dir = repo_root / "Exec" / "ABL"
    abl_dir.mkdir(parents=True, exist_ok=True)
    abl_exe = abl_dir / "ERF3d.gnu.TEST.MPI.CUDA.ex"
    abl_exe.write_text("abl")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        superfacility_account="acct",
        erf_executable_path=None,
        erf_repo_path=repo_root,
        erf_central_build_dir=regtests_dir,
    )
    runner = SuperfacilityRunner(config)

    exe, checked = runner._resolve_erf_executable_fallbacks(case_dir=case_dir, require_mpi=True, require_cuda=True)
    assert exe == abl_exe
    assert abl_dir in checked


def test_erf_fallback_prefers_cmake_build_exec_when_present(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Scaling" / "Perlmutter"
    case_dir.mkdir(parents=True)
    cmake_exe = repo_root / "build" / "Exec" / "erf_exec"
    cmake_exe.parent.mkdir(parents=True)
    cmake_exe.write_text("binary")

    gnumake_exe = repo_root / "Exec" / "ABL" / "ERF3d.gnu.TEST.MPI.CUDA.ex"
    gnumake_exe.parent.mkdir(parents=True, exist_ok=True)
    gnumake_exe.write_text("binary")

    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        superfacility_account="acct",
        erf_executable_path=None,
        erf_repo_path=repo_root,
        erf_central_build_dir=repo_root / "Exec" / "ABL",
    )
    runner = SuperfacilityRunner(config)

    exe, _ = runner._resolve_erf_executable_fallbacks(case_dir=case_dir, require_mpi=True, require_cuda=True)
    assert exe == cmake_exe


def test_active_solver_prefers_case_repo_path_over_default_solver(tmp_path):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "CanonicalTests" / "SquallLine_2D"
    case_dir.mkdir(parents=True)

    config = SimpleNamespace(
        default_solver="AMREX",
        output_dir=tmp_path,
        superfacility_account="acct",
        erf_repo_path=repo_root,
    )
    runner = SuperfacilityRunner(config)

    assert runner._active_solver_code(case_dir) == "ERF"


def test_non_erf_compile_failure_raises(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr(runner, "_find_exe_in_dir", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.compile_solver", lambda **kwargs: False)

    with pytest.raises(RuntimeError, match="Compilation failed"):
        runner.find_or_compile_executable(case_dir=case_dir)


def test_non_erf_compiled_but_missing_executable_raises(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr(runner, "_find_exe_in_dir", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.compile_solver", lambda **kwargs: True)

    with pytest.raises(RuntimeError, match="Compiled but no executable found"):
        runner.find_or_compile_executable(case_dir=case_dir)


def test_erf_missing_all_fallbacks_raises_with_checked_paths(tmp_path):
    case_dir = tmp_path / "case_without_erf"
    case_dir.mkdir()
    config = SimpleNamespace(
        default_solver="ERF",
        output_dir=tmp_path,
        superfacility_account="acct",
        erf_executable_path=None,
        erf_repo_path=None,
    )
    runner = SuperfacilityRunner(config)

    with pytest.raises(RuntimeError, match="No ERF executable found. Checked paths:"):
        runner.find_or_compile_executable(case_dir=case_dir, require_mpi=True, require_cuda=True)


def test_resolve_remote_executable_template_returns_explicit_ex_path(tmp_path):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/path/to/prebuilt.ex",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)
    result = runner._resolve_remote_executable(case_dir=case_dir)
    assert str(result) == "/path/to/prebuilt.ex"


def test_resolve_remote_executable_template_missing_key_raises(tmp_path):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/x/{unknown}/y",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)
    with pytest.raises(ValueError, match="remote_executable_template missing key"):
        runner._resolve_remote_executable(case_dir=case_dir)


def test_resolve_remote_executable_template_dir_find_success(tmp_path, monkeypatch):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/remote/{case_dir}",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr("src.services.run_superfacility.list_remote_entries", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "src.services.run_superfacility.find_remote_executable",
        lambda remote_case_dir, system=None: f"{remote_case_dir}/ERF3d.gnu.TEST.MPI.CUDA.ex",
    )
    result = runner._resolve_remote_executable(case_dir=case_dir)
    assert str(result).endswith(".ex")


def test_resolve_remote_executable_template_dir_list_error_has_hint(tmp_path, monkeypatch):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/remote/{case_dir}",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)

    def _boom(*args, **kwargs):
        raise RuntimeError("No NERSC session")

    monkeypatch.setattr("src.services.run_superfacility.list_remote_entries", _boom)
    with pytest.raises(RuntimeError, match="SFAPI auth missing"):
        runner._resolve_remote_executable(case_dir=case_dir)


def test_resolve_remote_executable_disabled_returns_none(tmp_path):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(repositories={"code": tmp_path / "repo"}, remote_executable_find=False)
    runner = SuperfacilityRunner(config)
    assert runner._resolve_remote_executable(case_dir=case_dir) is None


def test_setup_job_remote_resolution_enabled_skips_local_compile(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    copied_payload = {}

    monkeypatch.setattr(
        "src.services.run_superfacility.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )
    monkeypatch.setattr(
        "src.services.run_superfacility.copy_to_rundir",
        SimpleNamespace(
            invoke=lambda payload: copied_payload.setdefault("payload", payload) or {"inputs": str(run_dir / "inputs")}
        ),
    )

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="perlmutter",
        remote_executable_path=Path("/remote/solver.ex"),
    )
    runner = SuperfacilityRunner(config)

    result = runner.setup_job(case_dir=tmp_path / "case")
    assert result["executable"] is None
    assert copied_payload["payload"]["executable_path"] == ""


def test_setup_job_uses_existing_run_dir_when_inputs_present(tmp_path, monkeypatch):
    existing = tmp_path / "existing_run"
    existing.mkdir()
    (existing / "inputs").write_text("inputs")

    monkeypatch.setattr(
        "src.services.run_superfacility.copy_to_rundir",
        SimpleNamespace(invoke=lambda payload: {"inputs": str(existing / "inputs")}),
    )

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    result = runner.setup_job(case_dir=tmp_path, executable_path=str(tmp_path / "solver.ex"), output_dir=existing)
    assert Path(result["run_dir"]) == existing


def test_submit_raises_when_no_local_or_remote_executable(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_empty"
    run_dir.mkdir()
    monkeypatch.setattr(
        "src.services.run_superfacility.generate_slurm_script",
        lambda params, run_dir, config=None: "#!/bin/bash\n",
    )
    monkeypatch.setattr(SuperfacilityRunner, "_resolve_remote_executable", lambda self, case_dir, system="perlmutter": None)

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct", remote_executable_find=True)
    runner = SuperfacilityRunner(config)

    with pytest.raises(FileNotFoundError, match="No executable found"):
        runner.submit(run_dir, dry_run=True, case_dir=tmp_path / "case")


def test_submit_full_calls_submit_job(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_submit"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\necho run\n")
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("12345", "api"))
    monkeypatch.setattr("src.config.detect_environment", lambda: "local")

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct", environment="local")
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["job_id"] == "12345"
    assert result["method"] == "api"
    assert result["job_status"] == "queued"


def test_monitor_proxies_to_monitor_job(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.services.run_superfacility.monitor_job",
        lambda **kwargs: "COMPLETED",
    )
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    assert runner.monitor("job123", method="api") == "COMPLETED"


def test_monitor_scales_max_polls_from_walltime(tmp_path, monkeypatch):
    captured = {}

    def _fake_monitor_job(**kwargs):
        captured.update(kwargs)
        return "COMPLETED"

    monkeypatch.setattr("src.services.run_superfacility.monitor_job", _fake_monitor_job)
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    assert runner.monitor("job123", method="api", poll_interval=10, max_polls=30, walltime="01:00:00") == "COMPLETED"
    assert captured["max_polls"] > 30


def test_find_or_compile_returns_existing_exe_without_compile(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    existing = case_dir / "solver.MPI.CUDA.ex"
    existing.write_text("binary")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    assert Path(runner.find_or_compile_executable(case_dir=case_dir)) == existing


def test_find_or_compile_compiles_and_returns_exe(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    compiled = case_dir / "solver.MPI.CUDA.ex"
    compiled.write_text("binary")

    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    calls = {"count": 0}

    def _find(*args, **kwargs):
        calls["count"] += 1
        return None if calls["count"] == 1 else compiled

    monkeypatch.setattr(runner, "_find_exe_in_dir", _find)
    monkeypatch.setattr("src.services.run_superfacility.compile_solver", lambda **kwargs: True)
    assert Path(runner.find_or_compile_executable(case_dir=case_dir)) == compiled


def test_find_exe_returns_none_when_case_dir_missing(tmp_path):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    assert runner._find_exe_in_dir(tmp_path / "missing") is None


def test_find_exe_falls_back_to_first_when_filter_misses(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    first = case_dir / "solver.ex"
    first.write_text("binary")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    assert runner._find_exe_in_dir(case_dir, require_mpi=True, require_cuda=True) == first


def test_resolve_remote_executable_skips_none_repo_entries(tmp_path):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": None},
        remote_executable_find=False,
    )
    runner = SuperfacilityRunner(config)
    assert runner._resolve_remote_executable(case_dir=case_dir) is None


def test_resolve_remote_executable_fallback_without_repo_match_returns_none(tmp_path):
    case_dir = tmp_path / "other" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_find=False,
    )
    runner = SuperfacilityRunner(config)
    assert runner._resolve_remote_executable(case_dir=case_dir) is None


def test_resolve_remote_executable_env_derived_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    case_dir = repo_root / "Exec" / "RegTests" / "Bubble"
    case_dir.mkdir(parents=True)
    monkeypatch.setenv("SBATCH_ACCOUNT", "acct")
    monkeypatch.setenv("USER", "jdoe")

    captured = {}

    def _list_remote(path, system=None):
        captured["path"] = path
        return []

    monkeypatch.setattr("src.services.run_superfacility.list_remote_entries", _list_remote)
    monkeypatch.setattr(
        "src.services.run_superfacility.find_remote_executable",
        lambda remote_case_dir, system=None: f"{remote_case_dir}/solver.ex",
    )

    config = SimpleNamespace(
        repositories={"ERF": repo_root},
        remote_executable_find=True,
        remote_executable_template=None,
    )
    runner = SuperfacilityRunner(config)
    resolved = runner._resolve_remote_executable(case_dir=case_dir)
    assert str(resolved).endswith("solver.ex")
    assert "/global/cfs/cdirs/acct/jdoe/repo/Exec/RegTests/Bubble" in captured["path"]


def test_submit_uses_explicit_remote_executable_path(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_remote"
    run_dir.mkdir()
    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("999", "api"))
    monkeypatch.setattr("src.config.detect_environment", lambda: "local")

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="local",
        remote_executable_path=Path("/remote/solver.ex"),
        remote_executable_template=None,
        remote_executable_find=False,
    )
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["params"]["executable"] == "/remote/solver.ex"


def test_submit_remote_staging_with_fixed_remote_run_dir(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_stage_fixed"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.resolve_remote_output_dir", lambda **kwargs: Path("/remote/out"))
    monkeypatch.setattr("src.services.run_superfacility.ensure_remote_directory_rest", lambda **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.stage_run_directory", lambda **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("111", "api"))

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="perlmutter",
        remote_output_dir=None,
        remote_run_dir=Path("/fixed/run"),
        remote_staging_method="auto",
        remote_executable_path=Path("/fixed/solver.ex"),
    )
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["remote_run_dir"] == "/fixed/run"


def test_submit_remote_staging_recovers_credentials_from_key_file(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_stage_creds"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.resolve_remote_output_dir", lambda **kwargs: Path("/remote/out"))
    monkeypatch.setattr("src.services.run_superfacility.stage_run_directory", lambda **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("222", "api"))
    monkeypatch.setattr("src.services.run_superfacility._load_sfapi_key_file", lambda: ("cid", "secret"))

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="perlmutter",
        remote_output_dir=Path("/remote/out"),
        remote_run_dir=None,
        remote_staging_method="auto",
        remote_executable_path=None,
    )
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["job_id"] == "222"


def test_submit_should_stage_run_exception_falls_back_to_false(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_stage_exception"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")
    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("333", "api"))

    class _Cfg(SimpleNamespace):
        def should_stage_run(self):
            raise RuntimeError("boom")

    config = _Cfg(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["method"] == "api"


def test_run_simulation_combines_setup_submit_and_monitor(tmp_path, monkeypatch):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr(
        runner,
        "setup_job",
        lambda **kwargs: {"run_dir": str(tmp_path / "run"), "files": {}, "inputs": "inputs", "executable": "x.ex"},
    )
    monkeypatch.setattr(
        runner,
        "submit",
        lambda **kwargs: {"job_id": "42", "method": "api", "job_status": "queued"},
    )
    monkeypatch.setattr(runner, "monitor", lambda **kwargs: "COMPLETED")

    result = runner.run_simulation(case_dir=tmp_path / "case", monitor_job_flag=True)
    assert result["job_id"] == "42"
    assert result["final_state"] == "COMPLETED"


def test_run_simulation_passes_walltime_to_monitor(tmp_path, monkeypatch):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    monitor_calls = []

    monkeypatch.setattr(
        runner,
        "setup_job",
        lambda **kwargs: {"run_dir": str(tmp_path / "run"), "files": {}, "inputs": "inputs", "executable": "x.ex"},
    )
    monkeypatch.setattr(
        runner,
        "submit",
        lambda **kwargs: {"job_id": "42", "method": "api", "job_status": "queued"},
    )
    monkeypatch.setattr(
        runner,
        "monitor",
        lambda **kwargs: monitor_calls.append(kwargs) or "COMPLETED",
    )

    result = runner.run_simulation(case_dir=tmp_path / "case", monitor_job_flag=True, walltime="00:42:00")
    assert result["final_state"] == "COMPLETED"
    assert monitor_calls and monitor_calls[0]["walltime"] == "00:42:00"


def test_run_simulation_requires_default_solver_when_base_name_missing(tmp_path):
    config = SimpleNamespace(default_solver=None, output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    with pytest.raises(ValueError, match="No default solver configured"):
        runner.run_simulation(case_dir=tmp_path / "case", monitor_job_flag=False)


def test_find_exe_skips_non_cuda_when_cuda_required(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "solver.MPI.ex").write_text("binary")
    cuda_exe = case_dir / "solver.MPI.CUDA.ex"
    cuda_exe.write_text("binary")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    assert runner._find_exe_in_dir(case_dir, require_mpi=True, require_cuda=True) == cuda_exe


def test_find_or_compile_force_recompile_path(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    exe = case_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    monkeypatch.setattr("src.services.run_superfacility.compile_solver", lambda **kwargs: True)
    monkeypatch.setattr(runner, "_find_exe_in_dir", lambda *args, **kwargs: exe)
    assert Path(runner.find_or_compile_executable(case_dir=case_dir, force_recompile=True)) == exe


def test_resolve_remote_executable_template_dir_without_find_returns_none(tmp_path):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/remote/{case_dir}",
        remote_executable_find=False,
    )
    runner = SuperfacilityRunner(config)
    assert runner._resolve_remote_executable(case_dir=case_dir) is None


def test_resolve_remote_executable_template_dir_error_without_auth_hint(tmp_path, monkeypatch):
    case_dir = tmp_path / "repo" / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    config = SimpleNamespace(
        repositories={"code": tmp_path / "repo"},
        remote_executable_template="/remote/{case_dir}",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr(
        "src.services.run_superfacility.list_remote_entries",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("directory unavailable")),
    )
    with pytest.raises(RuntimeError, match="Remote case directory not available"):
        runner._resolve_remote_executable(case_dir=case_dir)


def test_resolve_remote_executable_returns_none_when_env_missing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    case_dir = repo_root / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    monkeypatch.delenv("SBATCH_ACCOUNT", raising=False)
    monkeypatch.delenv("USER", raising=False)
    config = SimpleNamespace(repositories={"ERF": repo_root}, remote_executable_find=True, remote_executable_template=None)
    runner = SuperfacilityRunner(config)
    assert runner._resolve_remote_executable(case_dir=case_dir) is None


def test_resolve_remote_executable_env_list_error_includes_auth_hint(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    case_dir = repo_root / "Exec" / "Case"
    case_dir.mkdir(parents=True)
    monkeypatch.setenv("SBATCH_ACCOUNT", "acct")
    monkeypatch.setenv("USER", "jdoe")
    config = SimpleNamespace(repositories={"ERF": repo_root}, remote_executable_find=True, remote_executable_template=None)
    runner = SuperfacilityRunner(config)

    monkeypatch.setattr(
        "src.services.run_superfacility.list_remote_entries",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("No NERSC session")),
    )
    with pytest.raises(RuntimeError, match="SFAPI auth missing"):
        runner._resolve_remote_executable(case_dir=case_dir)


def test_setup_job_requires_case_or_executable(tmp_path):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    with pytest.raises(ValueError, match="Must provide either executable_path or case_dir"):
        runner.setup_job(case_dir=None, executable_path=None)


def test_setup_job_requires_inputs_or_case_dir_for_copy(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_inputs_missing"
    run_dir.mkdir()
    monkeypatch.setattr(
        "src.services.run_superfacility.setup_run_directory",
        SimpleNamespace(invoke=lambda payload: str(run_dir)),
    )
    monkeypatch.setattr(
        "src.services.run_superfacility.copy_to_rundir",
        SimpleNamespace(invoke=lambda payload: {"inputs": "x"}),
    )
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    with pytest.raises(ValueError, match="Must provide either inputs_path or case_dir"):
        runner.setup_job(case_dir=None, inputs_path=None, executable_path=str(tmp_path / "solver.ex"))


def test_setup_job_raises_when_default_solver_missing(tmp_path):
    config = SimpleNamespace(default_solver=None, output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    with pytest.raises(ValueError, match="No default solver configured"):
        runner.setup_job(case_dir=tmp_path, executable_path=str(tmp_path / "solver.ex"))


def test_submit_uses_default_account_when_none(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_account"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")
    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("777", "api"))
    monkeypatch.setattr("src.config.detect_environment", lambda: "local")
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct", environment="local")
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, account=None, dry_run=False, case_dir=tmp_path / "case")
    assert result["params"]["account"] == "acct"


def test_submit_uses_resolved_remote_executable_when_template_enabled(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_remote_template"
    run_dir.mkdir()
    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("888", "api"))
    monkeypatch.setattr("src.config.detect_environment", lambda: "local")
    monkeypatch.setattr(SuperfacilityRunner, "_resolve_remote_executable", lambda self, case_dir, system="perlmutter": Path("/remote/tmpl.ex"))

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="local",
        remote_executable_path=None,
        remote_executable_template="/remote/{case_dir}",
        remote_executable_find=True,
    )
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["params"]["executable"] == "/remote/tmpl.ex"


def test_submit_stage_load_sfapi_key_file_none(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_stage_none"
    run_dir.mkdir()
    exe = run_dir / "solver.MPI.CUDA.ex"
    exe.write_text("binary")

    monkeypatch.setattr("src.services.run_superfacility.generate_slurm_script", lambda **kwargs: "#!/bin/bash\n")
    monkeypatch.setattr("src.services.run_superfacility.resolve_remote_output_dir", lambda **kwargs: Path("/remote/out"))
    monkeypatch.setattr("src.services.run_superfacility.stage_run_directory", lambda **kwargs: None)
    monkeypatch.setattr("src.services.run_superfacility.submit_job", lambda **kwargs: ("999", "api"))
    monkeypatch.setattr("src.services.run_superfacility._load_sfapi_key_file", lambda: None)

    config = SimpleNamespace(
        default_solver="PeleC",
        output_dir=tmp_path,
        superfacility_account="acct",
        environment="perlmutter",
        remote_output_dir=Path("/remote/out"),
        remote_run_dir=None,
        remote_staging_method="auto",
        remote_executable_path=None,
    )
    runner = SuperfacilityRunner(config)
    result = runner.submit(run_dir, dry_run=False, case_dir=tmp_path / "case")
    assert result["job_id"] == "999"


def test_run_simulation_without_monitor_skips_final_state(tmp_path, monkeypatch):
    config = SimpleNamespace(default_solver="PeleC", output_dir=tmp_path, superfacility_account="acct")
    runner = SuperfacilityRunner(config)
    monkeypatch.setattr(runner, "setup_job", lambda **kwargs: {"run_dir": str(tmp_path / "run"), "files": {}})
    monkeypatch.setattr(runner, "submit", lambda **kwargs: {"job_id": "1", "method": "api"})
    result = runner.run_simulation(case_dir=tmp_path / "case", monitor_job_flag=False)
    assert "final_state" not in result
