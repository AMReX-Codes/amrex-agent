from types import SimpleNamespace

from src.services.build_tools import compile_solver


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_compile_solver_erf_prefers_cmake(tmp_path, monkeypatch):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Case"
    case_dir.mkdir(parents=True)

    calls = []

    def _run(cmd, cwd, capture_output, text, timeout):  # noqa: ARG001
        calls.append(cmd)
        return _Result(returncode=0)

    monkeypatch.setattr("src.services.build_tools.subprocess.run", _run)

    config = SimpleNamespace(erf_repo_path=repo_root)
    assert compile_solver(case_dir=case_dir, solver_code="ERF", runtime_config=config, use_cuda=False)
    assert calls[0][:3] == ["cmake", "-S", str(repo_root)]
    assert calls[1][:2] == ["cmake", "--build"]
    assert all(cmd[0] != "make" and cmd[0] != "nice" for cmd in calls)


def test_compile_solver_erf_falls_back_to_gnumake_when_cmake_fails(tmp_path, monkeypatch):
    repo_root = tmp_path / "ERF"
    case_dir = repo_root / "Exec" / "ABL" / "Case"
    case_dir.mkdir(parents=True)
    (case_dir / "GNUmakefile").write_text("all:\n\t@echo ok\n")

    calls = []

    def _run(cmd, cwd, capture_output, text, timeout):  # noqa: ARG001
        calls.append(cmd)
        if cmd[0] == "cmake":
            return _Result(returncode=1, stderr="cmake failed")
        return _Result(returncode=0)

    monkeypatch.setattr("src.services.build_tools.subprocess.run", _run)

    config = SimpleNamespace(erf_repo_path=repo_root)
    assert compile_solver(case_dir=case_dir, solver_code="ERF", runtime_config=config, use_cuda=False)
    assert calls[0][0] == "cmake"
    assert any(cmd[0] in {"make", "nice"} for cmd in calls)


def test_compile_solver_non_erf_uses_gnumake_first(tmp_path, monkeypatch):
    case_dir = tmp_path / "PeleC" / "Exec" / "RegTests" / "Case"
    case_dir.mkdir(parents=True)
    (case_dir / "GNUmakefile").write_text("all:\n\t@echo ok\n")

    calls = []

    def _run(cmd, cwd, capture_output, text, timeout):  # noqa: ARG001
        calls.append(cmd)
        return _Result(returncode=0)

    monkeypatch.setattr("src.services.build_tools.subprocess.run", _run)

    assert compile_solver(case_dir=case_dir, solver_code="PeleC", runtime_config=SimpleNamespace(), use_cuda=False)
    assert calls[0][0] in {"make", "nice"}
