from pathlib import Path
from types import SimpleNamespace

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
