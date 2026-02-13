import sys
from pathlib import Path
from types import SimpleNamespace

from src.services.run_superfacility_tools import (
    create_nersc_session,
    generate_slurm_script,
    monitor_job,
    resolve_remote_output_dir,
    submit_job,
    submit_via_sfapi,
)


def test_generate_slurm_script_includes_params(tmp_path):
    params = {
        "nodes": 2,
        "walltime": "00:10:00",
        "account": "acct",
        "qos": "regular",
        "constraint": "gpu",
        "executable": "solver.ex",
    }
    script = generate_slurm_script(params=params, run_dir=str(tmp_path))

    assert "#SBATCH --nodes=2" in script
    assert "#SBATCH --account=acct" in script
    assert "srun -n 8 ./solver.ex inputs" in script


def test_create_nersc_session_uses_token():
    session = create_nersc_session({"token": "abc"})

    assert session["type"] == "token"
    assert session["token"] == "abc"


def test_submit_via_sfapi_success(tmp_path, monkeypatch):
    script_path = tmp_path / "submit.sh"
    script_path.write_text("#!/bin/bash\necho test\n")

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"jobid": "123"}

    def fake_post(url, headers=None, json=None):
        return DummyResponse()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    result = submit_via_sfapi(
        script_path=str(script_path),
        nersc_session={"type": "token", "token": "abc"},
    )

    assert result["job_id"] == "123"
    assert result["method"] == "api"


def test_submit_job_falls_back_to_sbatch(monkeypatch):
    monkeypatch.setattr(
        "src.services.run_superfacility_tools._load_sfapi_key_file",
        lambda: None,
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.submit_via_sfapi_client",
        lambda *args, **kwargs: {"error": "skipped"},
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.find_nersc_clients",
        lambda: {},
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.submit_via_sbatch",
        lambda script_path, config=None: {"job_id": "456", "method": "sbatch"},
    )

    job_id, method = submit_job(script_path="submit.sh")

    assert job_id == "456"
    assert method == "sbatch"


def test_monitor_job_sbatch_completes(monkeypatch):
    calls = {"count": 0}

    def fake_run(cmd, capture_output=True, text=True):
        calls["count"] += 1
        stdout = "RUNNING" if calls["count"] == 1 else ""
        return SimpleNamespace(stdout=stdout)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _: None)

    state = monitor_job(job_id="123", method="sbatch", poll_interval=0, max_polls=2)

    assert state == "COMPLETED"


def test_resolve_remote_output_dir_prefers_shared_then_fallback(monkeypatch):
    checks = []

    def fake_list_remote_entries(remote_dir, **_kwargs):
        checks.append(remote_dir)
        if remote_dir.endswith("/acct/superfacility/output"):
            raise RuntimeError("shared missing")
        return [{"name": "ok"}]

    def fake_ensure_remote_directory_rest(remote_run_dir, **_kwargs):
        checks.append(f"ensure:{remote_run_dir}")

    monkeypatch.setattr(
        "src.services.run_superfacility_tools.list_remote_entries",
        fake_list_remote_entries,
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.ensure_remote_directory_rest",
        fake_ensure_remote_directory_rest,
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.find_nersc_clients",
        lambda: {"token": "abc"},
    )

    result = resolve_remote_output_dir(
        preferred_output_dir="/global/cfs/cdirs/acct/superfacility/output",
        account="acct",
        user="jdoe",
    )

    assert result == Path("/global/cfs/cdirs/acct/jdoe/superfacility/output")
    assert f"ensure:{result}" in checks


def test_resolve_remote_output_dir_returns_local_path(monkeypatch):
    def fail_call(*_args, **_kwargs):
        raise AssertionError("unexpected remote check")

    monkeypatch.setattr(
        "src.services.run_superfacility_tools.list_remote_entries",
        fail_call,
    )
    monkeypatch.setattr(
        "src.services.run_superfacility_tools.ensure_remote_directory_rest",
        fail_call,
    )

    result = resolve_remote_output_dir(
        preferred_output_dir="/tmp/amrex_agent_runs",
        account="acct",
        user="jdoe",
    )

    assert result == Path("/tmp/amrex_agent_runs")
