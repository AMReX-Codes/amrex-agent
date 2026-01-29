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
