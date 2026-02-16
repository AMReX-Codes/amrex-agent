import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "demo"
PELELMEX_PROMPT_PATH = DEMO_DIR / "pelelmex" / "user_requirements_test_DNS.txt"
EXPECTED_JICF_CASE = "Exec/Production/JetInCrossflow"


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


@pytest.mark.integration_full
@pytest.mark.use_real_services
@pytest.mark.requires_solver("PeleLMeX")
@pytest.mark.requires_repos("PeleLMeX")
@pytest.mark.requires_schema("PeleLMeX")
@pytest.mark.parametrize(
    "indexing_strategy, expected_min_calls, expect_zero_calls",
    [
        pytest.param(
            "simple",
            0,
            False,
            marks=(
                pytest.mark.indexing_simple,
                pytest.mark.requires_indices("faiss"),
            ),
            id="simple",
        ),
        pytest.param(
            "hierarchical",
            1,
            False,
            marks=(
                pytest.mark.indexing_hierarchical,
                pytest.mark.requires_indices("level0", "level1", "level2"),
            ),
            id="hierarchical",
        ),
        pytest.param(
            "override_static",
            0,
            True,
            marks=pytest.mark.indexing_override_static,
            id="override_static",
        ),
    ],
)
def test_jicf_prompt_across_indexing_strategies(
    tmp_path: Path,
    indexing_strategy: str,
    expected_min_calls: int,
    expect_zero_calls: bool,
) -> None:
    if not PELELMEX_PROMPT_PATH.exists():
        pytest.skip("Demo prompt file missing")
    repo_path = _resolve_pelelmex_repo()
    if not repo_path:
        pytest.skip("PeleLMeX repo not available")
    baseline_override = f"PeleLMeX/{EXPECTED_JICF_CASE}"
    if indexing_strategy == "override_static":
        baseline_dir = repo_path / "Exec" / "Production" / "JetInCrossflow"
        if not baseline_dir.exists():
            pytest.skip("PeleLMeX JetInCrossflow baseline not available")

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "amrex_agent.py"),
        "--prompt-path",
        str(PELELMEX_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        indexing_strategy,
        "--dry-run",
        "--run-mode",
        "dry",
        "--save-workflow",
        "--save-log",
    ]
    if indexing_strategy == "override_static":
        cmd.extend(["--baseline-override", baseline_override])

    env = os.environ.copy()
    env["PELELMEX_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    if "Connection error" in result.stderr:
        pytest.skip("Embedding/LLM connection error")
    assert result.returncode == 0, (
        "JICF run failed.\n"
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

    workflow_path = run_dir / "workflow_history.json"
    assert workflow_path.exists(), "workflow_history.json not saved"
    workflow_history = workflow_path.read_text()
    history = json.loads(workflow_history)
    architect_entries = [entry for entry in history if entry.get("node") == "architect"]
    assert architect_entries, "No architect entry found in workflow history"
    details = architect_entries[-1].get("details", {})
    assert details.get("indexing_strategy") == indexing_strategy
    assert details.get("selected_case") == EXPECTED_JICF_CASE
    indexing_calls = details.get("indexing_calls_count")
    assert isinstance(indexing_calls, int)
    if expect_zero_calls:
        assert indexing_calls == 0
    else:
        assert indexing_calls >= expected_min_calls
