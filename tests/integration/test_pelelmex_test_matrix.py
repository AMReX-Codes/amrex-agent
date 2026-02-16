from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "demo" / "pelelmex"
CONFIG_PATH = DEMO_DIR / "config_JICF.yaml"

PROMPT_FILES = [
    DEMO_DIR / "user_requirements_test_DNS.txt",
    DEMO_DIR / "user_requirements_test_DNS_mod.txt",
    DEMO_DIR / "user_requirements_DNS_channel.txt",
    DEMO_DIR / "user_requirements_DNS_isothermal.txt",
    DEMO_DIR / "user_requirements_DNS_isothermal_reacting.txt",
    DEMO_DIR / "user_requirements_DNS_turb5.txt",
    DEMO_DIR / "user_requirements_DNS_turb5_reacting.txt",
]

EXECUTION_TARGETS = (
    "local",
    "local_to_perlmutter",
    "perlmutter_local",
    "perlmutter_to_perlmutter",
    "alcf_to_perlmutter",
)

pytestmark = [
    pytest.mark.integration_full,
    pytest.mark.demo,
    pytest.mark.e2e,
    pytest.mark.use_real_services,
    pytest.mark.requires_repos("PeleLMeX"),
    pytest.mark.requires_schema("PeleLMeX"),
]


@dataclass(frozen=True)
class MatrixCase:
    prompt_path: Path
    execution_target: str


CASES = [
    MatrixCase(prompt_path=prompt_path, execution_target=target)
    for prompt_path in PROMPT_FILES
    for target in EXECUTION_TARGETS
]


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


def _remote_tests_enabled(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("pelelmex_remote"))


def _on_perlmutter() -> bool:
    return os.getenv("NERSC_HOST") in {"perlmutter", "alvarez", "muller"}


def _build_config_override(
    tmp_path: Path,
    provider: str | None,
    model: str | None,
    alcf_cluster: str | None,
    alcf_base_url: str | None,
) -> Path:
    config_data = {}
    if CONFIG_PATH.exists():
        config_data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    if provider:
        config_data["llm_provider"] = provider
    if model:
        config_data["llm_model"] = model
    if alcf_cluster:
        config_data["alcf_cluster"] = alcf_cluster
    if alcf_base_url:
        config_data["alcf_base_url"] = alcf_base_url

    override_path = tmp_path / "pelelmex_config_override.yaml"
    override_path.write_text(
        yaml.safe_dump(config_data, sort_keys=False)
    )
    return override_path


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=lambda case: f"{case.prompt_path.stem}:{case.execution_target}",
)
def test_pelelmex_test_matrix_case(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    case: MatrixCase,
) -> None:
    if not CONFIG_PATH.exists():
        pytest.skip("PeleLMeX JICF config missing")
    if not case.prompt_path.exists():
        pytest.skip("PeleLMeX prompt file missing")

    repo_path = _resolve_pelelmex_repo()
    if not repo_path:
        pytest.skip("PeleLMeX repo not available")
    baseline_dir = repo_path / "Exec" / "Production" / "JetInCrossflow"
    if not baseline_dir.exists():
        pytest.skip("PeleLMeX JetInCrossflow baseline not available")

    if case.execution_target != "local":
        if not _remote_tests_enabled(request):
            pytest.skip(
                f"{case.execution_target} requires remote setup; "
                "enable with --pelelmex-remote"
            )
        if case.execution_target in {"perlmutter_local", "perlmutter_to_perlmutter"} and not _on_perlmutter():
            pytest.skip("Perlmutter-only test case")
        if case.execution_target == "alcf_to_perlmutter" and not os.getenv("ALCF_API_KEY"):
            pytest.skip("ALCF credentials not available")

    provider = request.config.getoption("llm_provider")
    model = request.config.getoption("llm_model")
    alcf_cluster = request.config.getoption("alcf_cluster")
    alcf_base_url = request.config.getoption("alcf_base_url")
    if provider and provider.strip().lower() == "alcf" and not os.getenv("ALCF_API_KEY"):
        pytest.skip("ALCF credentials not available")

    output_dir = tmp_path / f"{case.prompt_path.stem}-{case.execution_target}"
    config_path = _build_config_override(tmp_path, provider, model, alcf_cluster, alcf_base_url)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--config",
        str(config_path),
        "--prompt-path",
        str(case.prompt_path),
        "--output-dir",
        str(output_dir),
        "--run-mode",
        "dry",
        "--save-workflow",
    ]
    if case.execution_target != "local":
        cmd.extend(["--environment", "perlmutter"])

    env = os.environ.copy()
    env["PELELMEX_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    assert result.returncode == 0, (
        "PeleLMeX test matrix run failed.\n"
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
    workflow_file = run_dir / "workflow_history.json"
    assert workflow_file.exists(), "workflow_history.json missing"
