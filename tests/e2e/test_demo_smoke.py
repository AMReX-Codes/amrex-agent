import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "demo"
PELELMEX_PROMPT_PATH = DEMO_DIR / "pelelmex" / "user_requirements_test_DNS.txt"
ERF_PROMPT_PATH = DEMO_DIR / "erf" / "user_requirements_abl.txt"


def _run_cli(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_repo_path(env_var: str, repo_name: str) -> Path | None:
    env_path = os.getenv(env_var)
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
        return None
    candidate = REPO_ROOT.parent / repo_name
    if candidate.exists():
        return candidate
    candidate = REPO_ROOT / repo_name
    if candidate.exists():
        return candidate
    return None


def _resolve_pelelmex_repo() -> Path | None:
    return _resolve_repo_path("PELELMEX_REPO_PATH", "PeleLMeX")


def _resolve_pelec_repo() -> Path | None:
    return _resolve_repo_path("PELEC_REPO_PATH", "PeleC")


def _resolve_erf_repo() -> Path | None:
    return _resolve_repo_path("ERF_REPO_PATH", "ERF")


def _resolve_amrex_repo() -> Path | None:
    return _resolve_repo_path("AMREX_REPO_PATH", "amrex")


def _resolve_remora_repo() -> Path | None:
    return _resolve_repo_path("REMORA_REPO_PATH", "REMORA")

def _find_run_directory(output_dir: Path, stdout: str, stderr: str) -> Path | None:
    run_dirs = sorted(output_dir.glob("run_*"))
    if run_dirs:
        return run_dirs[-1]

    output_text = "\n".join([stdout, stderr])
    patterns = [
        r"Files written to:\s*(\S+)",
        r"Created simulation in\s*(\S+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output_text)
        if match:
            candidate = Path(match.group(1))
            if candidate.exists():
                return candidate
    return None


@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.use_real_services
@pytest.mark.indexing_hierarchical
@pytest.mark.requires_solver("PeleLMeX")
@pytest.mark.requires_repos("PeleLMeX")
@pytest.mark.requires_schema("PeleLMeX")
@pytest.mark.requires_indices("level0", "level1", "level2")
def test_demo_prompt_file_pelelmex_hierarchical(tmp_path: Path) -> None:
    if not PELELMEX_PROMPT_PATH.exists():
        pytest.skip("Demo prompt file missing")
    repo_path = _resolve_pelelmex_repo()
    if not repo_path:
        pytest.skip("PeleLMeX repo not available")
    baseline_dir = repo_path / "Exec" / "RegTests" / "JetInCrossFlow"
    if not baseline_dir.exists():
        pytest.skip("PeleLMeX JetInCrossFlow baseline not available")
    baseline_override = "PeleLMeX/Exec/RegTests/JetInCrossFlow"

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt-path",
        str(PELELMEX_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "hierarchical",
        "--baseline-override",
        baseline_override,
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["PELELMEX_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "Demo smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir, result.stdout, result.stderr)
    assert run_dir, (
        "No run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    inputs_files = list(run_dir.rglob("inputs"))
    assert inputs_files, "No inputs file created"


@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.use_real_services
@pytest.mark.indexing_simple
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_demo_prompt_file_erf(tmp_path: Path) -> None:
    if not ERF_PROMPT_PATH.exists():
        pytest.skip("ERF demo prompt file missing")
    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")
    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")
    baseline_override = "ERF/Exec/ABL"

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt-path",
        str(ERF_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        baseline_override,
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "ERF smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir, result.stdout, result.stderr)
    assert run_dir, (
        "No ERF run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    inputs_files = list(run_dir.rglob("inputs"))
    assert inputs_files, "No ERF inputs file created"


@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.use_real_services
@pytest.mark.indexing_simple
@pytest.mark.requires_solver("REMORA")
@pytest.mark.requires_repos("REMORA")
@pytest.mark.requires_schema("REMORA")
@pytest.mark.requires_indices("faiss")
def test_demo_inline_prompt_remora(tmp_path: Path) -> None:
    repo_path = _resolve_remora_repo()
    if not repo_path:
        pytest.skip("REMORA repo not available")
    baseline_dir = repo_path / "Exec" / "Channel_Test"
    if not baseline_dir.exists():
        pytest.skip("REMORA Channel_Test baseline not available")
    baseline_override = "REMORA/Exec/Channel_Test"

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt",
        (
            "Run a REMORA ocean channel simulation with 20x60x50 cells, "
            "periodic boundaries in x-direction, and GLS vertical mixing for 100 steps"
        ),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        baseline_override,
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["REMORA_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "REMORA smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir, result.stdout, result.stderr)
    assert run_dir, (
        "No REMORA run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    inputs_files = list(run_dir.rglob("inputs"))
    assert inputs_files, "No REMORA inputs file created"


@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.use_real_services
@pytest.mark.indexing_simple
@pytest.mark.requires_solver("PeleC")
@pytest.mark.requires_repos("PeleC")
@pytest.mark.requires_schema("PeleC")
@pytest.mark.requires_indices("faiss")
def test_demo_inline_prompt_pelec(tmp_path: Path) -> None:
    repo_path = _resolve_pelec_repo()
    if not repo_path:
        pytest.skip("PeleC repo not available")
    baseline_dir = repo_path / "Exec" / "RegTests" / "PMF"
    if not baseline_dir.exists():
        pytest.skip("PeleC PMF baseline not available")
    baseline_override = "PeleC/Exec/RegTests/PMF"

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt",
        "PeleC premixed methane flame simulation with a 64x64 grid",
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        baseline_override,
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["PELEC_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "Inline prompt smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir, result.stdout, result.stderr)
    assert run_dir, (
        "No inline prompt run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    inputs_files = list(run_dir.rglob("inputs"))
    assert inputs_files, "No inline prompt inputs file created"


@pytest.mark.e2e
@pytest.mark.demo
@pytest.mark.use_real_services
@pytest.mark.indexing_simple
@pytest.mark.requires_solver("AMReX")
@pytest.mark.requires_repos("AMReX")
@pytest.mark.requires_schema("AMReX")
@pytest.mark.requires_indices("faiss")
def test_demo_amrex_baseline_override(tmp_path: Path) -> None:
    repo_path = _resolve_amrex_repo()
    if not repo_path:
        pytest.skip("AMReX repo not available")
    baseline_dir = repo_path / "Tests" / "Amr" / "Advection_AmrCore" / "Exec"
    if not baseline_dir.exists():
        pytest.skip("AMReX Advection_AmrCore baseline not available")
    baseline_override = "AMReX/Tests/Amr/Advection_AmrCore/Exec"

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt",
        "AMReX Advection_AmrCore baseline with a 64x64 grid",
        "--baseline-override",
        baseline_override,
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["AMREX_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "AMReX smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir, result.stdout, result.stderr)
    assert run_dir, (
        "No AMReX run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    inputs_files = list(run_dir.rglob("inputs"))
    assert inputs_files, "No AMReX inputs file created"
