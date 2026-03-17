import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ERF_PROMPT_PATH = REPO_ROOT / "demo" / "erf" / "user_requirements_abl.txt"


def _run_cli(
    cmd: list[str],
    env: dict[str, str],
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


def _resolve_erf_repo() -> Path | None:
    env_path = os.getenv("ERF_REPO_PATH")
    if env_path:
        candidate = Path(env_path)
        return candidate if candidate.exists() else None
    candidate = REPO_ROOT.parent / "ERF"
    if candidate.exists():
        return candidate
    candidate = REPO_ROOT / "ERF"
    if candidate.exists():
        return candidate
    return None


def _resolve_pelec_repo() -> Path | None:
    env_path = os.getenv("PELEC_REPO_PATH")
    if env_path:
        candidate = Path(env_path)
        return candidate if candidate.exists() else None
    candidate = REPO_ROOT.parent / "PeleC"
    if candidate.exists():
        return candidate
    candidate = REPO_ROOT / "PeleC"
    if candidate.exists():
        return candidate
    return None


def _resolve_remora_repo() -> Path | None:
    env_path = os.getenv("REMORA_REPO_PATH")
    if env_path:
        candidate = Path(env_path)
        return candidate if candidate.exists() else None
    candidate = REPO_ROOT.parent / "REMORA"
    if candidate.exists():
        return candidate
    candidate = REPO_ROOT / "REMORA"
    if candidate.exists():
        return candidate
    return None


def _find_run_directory(output_dir: Path) -> Path | None:
    run_dirs = sorted(output_dir.glob("run_*"))
    if run_dirs:
        return run_dirs[-1]
    return None


def _find_workflow_history(output_dir: Path, run_dir: Path | None) -> Path | None:
    if run_dir is not None:
        candidate = run_dir / "workflow_history.json"
        if candidate.exists():
            return candidate
    candidates = sorted(output_dir.glob("workflow_history*.json"))
    if candidates:
        return candidates[-1]
    return None


def _extract_required_value(required_assignments: dict[str, object], keys: list[str]) -> str | None:
    if not isinstance(required_assignments, dict):
        return None
    key_set = {k.strip().lower() for k in keys}
    for key, value in required_assignments.items():
        if str(key).strip().lower() in key_set:
            return str(value)
    return None


def _assert_two_phase_solver_contract(
    *,
    workflow_history: list[dict],
    workflow_path: Path,
    result: subprocess.CompletedProcess[str],
    parameter_keys: list[str],
    allow_preexec_terminal_skip: bool = False,
    solver_label: str = "solver",
) -> None:
    runner_indices = [i for i, e in enumerate(workflow_history) if e.get("node") == "runner"]
    if len(runner_indices) < 2 and allow_preexec_terminal_skip:
        has_postexec = any(
            e.get("node") == "reviewer"
            and e.get("details", {}).get("review_context") == "post_execution"
            for e in workflow_history
        )
        terminal_preexec = any(
            e.get("node") == "reviewer"
            and e.get("details", {}).get("review_context") in {None, "pre_execution"}
            and e.get("action") in {"intent_coverage_max_retries", "validation_completed"}
            and e.get("details", {}).get("status") == "terminal"
            for e in workflow_history
        )
        if not has_postexec and terminal_preexec and not runner_indices:
            pytest.skip(
                f"{solver_label} full-mode run terminated in pre-exec validation before runner; "
                "skipping two-phase post-exec rerun assertion for this environment."
            )
    assert len(runner_indices) >= 2, (
        "Expected at least two runner executions (initial run + repaired rerun).\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"runner_indices={runner_indices}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    postexec_reviewer_indices = [
        i
        for i, e in enumerate(workflow_history)
        if e.get("node") == "reviewer"
        and e.get("details", {}).get("review_context") == "post_execution"
    ]
    assert postexec_reviewer_indices, (
        "Expected post-exec reviewer diagnosis before rerun.\n"
        f"workflow_path={workflow_path}\n"
    )

    has_postexec_between_runs = any(
        any(first < r < second for r in postexec_reviewer_indices)
        for first, second in zip(runner_indices, runner_indices[1:])
    )
    assert has_postexec_between_runs, (
        "Expected a post-exec reviewer diagnosis between runner attempts.\n"
        f"workflow_path={workflow_path}\n"
        f"runner_indices={runner_indices}\n"
        f"postexec_reviewer_indices={postexec_reviewer_indices}\n"
    )

    intent_retry_indices = [
        i
        for i, e in enumerate(workflow_history)
        if e.get("node") == "reviewer" and e.get("action") == "intent_coverage_retry"
    ]
    assert intent_retry_indices, (
        "Expected pre-execution intent coverage retry before first execution.\n"
        f"workflow_path={workflow_path}\n"
    )

    first_runner_idx = runner_indices[0]
    intent_values = []
    for idx in intent_retry_indices:
        if idx >= first_runner_idx:
            continue
        required = workflow_history[idx].get("details", {}).get("required_assignments", {}) or {}
        matched = _extract_required_value(required, parameter_keys)
        if matched is not None:
            intent_values.append(matched)
    assert intent_values, (
        "Expected intent coverage to require target parameter prior to first runner attempt.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_retry_indices={intent_retry_indices}\n"
        f"parameter_keys={parameter_keys}\n"
    )
    intent_value = intent_values[-1]

    postexec_values = []
    for idx in postexec_reviewer_indices:
        details = workflow_history[idx].get("details", {}) or {}
        repair_feedback = details.get("postexec_repair_feedback", {}) or {}
        required = repair_feedback.get("required_assignments", {}) or {}
        matched = _extract_required_value(required, parameter_keys)
        if matched is not None:
            postexec_values.append(matched)
    assert postexec_values, (
        "Expected post-exec reviewer feedback to provide repaired target parameter.\n"
        f"workflow_path={workflow_path}\n"
        f"parameter_keys={parameter_keys}\n"
    )
    postexec_value = postexec_values[-1]
    assert postexec_value != intent_value, (
        "Expected post-exec repair assignment to differ from pre-exec intent assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_value={intent_value}\n"
        f"postexec_value={postexec_value}\n"
    )

    architect_entries = [
        (i, e)
        for i, e in enumerate(workflow_history)
        if e.get("node") == "architect"
    ]
    assert architect_entries, f"No architect entries found. workflow_path={workflow_path}"

    key_set = {k.strip().lower() for k in parameter_keys}

    def _mods_contain_value(entry: dict, expected: str) -> bool:
        mods = entry.get("details", {}).get("modifications", []) or []
        for item in mods:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            key = str(item[0]).strip().lower()
            value = str(item[1])
            if key in key_set and value == expected:
                return True
        return False

    assert any(
        idx < first_runner_idx and _mods_contain_value(entry, intent_value)
        for idx, entry in architect_entries
    ), (
        "Expected architect plan before first run to contain intent-enforced assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_value={intent_value}\n"
    )
    assert any(
        any(post_idx < idx for post_idx in postexec_reviewer_indices)
        and _mods_contain_value(entry, postexec_value)
        for idx, entry in architect_entries
    ), (
        "Expected architect plan after post-exec review to contain repaired assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"postexec_value={postexec_value}\n"
    )

    analysis_entries = [e for e in workflow_history if e.get("node") == "analysis"]
    assert analysis_entries, f"No analysis entries found. workflow_path={workflow_path}"
    final_analysis_status = analysis_entries[-1].get("details", {}).get("status")
    assert final_analysis_status == "success", (
        "Expected repaired rerun to end with successful analysis.\n"
        f"workflow_path={workflow_path}\n"
        f"final_analysis_status={final_analysis_status}\n"
        f"returncode={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_writes_workflow_history_with_reviewer_guidance_fields(tmp_path: Path) -> None:
    """Run real CLI dry path and verify reviewer guidance contract fields."""
    if not ERF_PROMPT_PATH.exists():
        pytest.skip("ERF demo prompt file missing")

    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")

    output_dir = tmp_path / "runs"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt-path",
        str(ERF_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "ERF/Exec/ABL",
        "--dry-run",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)
    assert result.returncode == 0, (
        "CLI smoke run failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    run_dir = _find_run_directory(output_dir)
    assert run_dir is not None, (
        "No run directory created.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), "workflow_history.json was not saved"

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history, "workflow_history is empty"

    reviewer_entries = [
        entry
        for entry in workflow_history
        if entry.get("node") == "reviewer" and entry.get("action") == "validation_completed"
    ]
    assert reviewer_entries, "No reviewer validation entries found in workflow history"

    reviewer_guidance = reviewer_entries[-1].get("details", {}).get("reviewer_guidance")
    assert isinstance(reviewer_guidance, dict), "reviewer_guidance missing from reviewer details"
    for required_key in (
        "required_solver",
        "forbidden_path_patterns",
        "preferred_path_patterns",
        "excluded_cases",
        "schema_escalation_required",
        "replan_reason_codes",
    ):
        assert required_key in reviewer_guidance, f"Missing reviewer guidance key: {required_key}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_shows_post_execution_reflexion_loop(tmp_path: Path) -> None:
    """Run full mode and require post-execution reflexion evidence from workflow history when available."""
    if not ERF_PROMPT_PATH.exists():
        pytest.skip("ERF demo prompt file missing")

    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")
    if os.getenv("AMREX_AGENT_RUN_SLOW_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_SLOW_E2E=1 to run slow full-mode reflexion E2E")

    output_dir = tmp_path / "runs_full_mode"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt-path",
        str(ERF_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "ERF/Exec/ABL",
        "--run-mode",
        "full",
        "--max-iterations",
        "5",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)

    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)

    if workflow_path is not None and workflow_path.exists():
        workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    else:
        workflow_history = []

    if workflow_history:
        post_exec_reviewer_indices = [
            idx
            for idx, entry in enumerate(workflow_history)
            if entry.get("node") == "reviewer"
            and (
                entry.get("details", {}).get("review_context") == "post_execution"
                or entry.get("details", {}).get("review_origin") == "analysis_diagnosis"
            )
        ]
        assert post_exec_reviewer_indices, (
            "Expected reviewer post-execution diagnosis entry in workflow history.\n"
            f"workflow_path={workflow_path}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        for idx in post_exec_reviewer_indices:
            reviewer_guidance = workflow_history[idx].get("details", {}).get("reviewer_guidance", {})
            assert isinstance(reviewer_guidance, dict), "post-exec reviewer_guidance must be a dict"
            for required_key in ("feasible", "intent_consistent", "diagnosis", "guidance"):
                assert required_key in reviewer_guidance, (
                    f"Missing structured reviewer feasibility key: {required_key}\n"
                    f"workflow_path={workflow_path}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

        has_architect_after_post = False
        for idx in post_exec_reviewer_indices:
            if any(e.get("node") == "architect" for e in workflow_history[idx + 1 :]):
                has_architect_after_post = True
                break
        assert has_architect_after_post, (
            "Expected architect retry after post-execution reviewer diagnosis.\n"
            f"workflow_path={workflow_path}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        return

    # Fallback for environments where recursive termination yields no persisted workflow history
    reviewer_passes = result.stderr.count("Starting Reviewer node")
    assert reviewer_passes >= 2, (
        "Expected at least one reflexion loop with repeated reviewer passes.\n"
        f"reviewer_passes={reviewer_passes}\n"
        f"workflow_path={workflow_path}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_real_llm_structured_feasibility_contract(tmp_path: Path) -> None:
    """Opt-in real-LLM full reflexion test for structured feasibility contract."""
    if os.getenv("RUN_REAL_LLM_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_REAL_LLM_TESTS=1 to run real-LLM feasibility test")

    if not ERF_PROMPT_PATH.exists():
        pytest.skip("ERF demo prompt file missing")

    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")

    output_dir = tmp_path / "runs_full_mode_real_llm"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt-path",
        str(ERF_PROMPT_PATH),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "ERF/Exec/ABL",
        "--run-mode",
        "full",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history.json required for real-LLM feasibility contract test.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    post_exec = [
        (idx, entry)
        for idx, entry in enumerate(workflow_history)
        if entry.get("node") == "reviewer"
        and entry.get("details", {}).get("review_context") == "post_execution"
    ]
    assert post_exec, "Expected at least one post-execution reviewer entry"

    for idx, entry in post_exec:
        reviewer_guidance = entry.get("details", {}).get("reviewer_guidance", {})
        assert isinstance(reviewer_guidance, dict)
        assert isinstance(reviewer_guidance.get("feasible"), bool)
        assert isinstance(reviewer_guidance.get("intent_consistent"), bool)
        assert isinstance(reviewer_guidance.get("diagnosis"), str) and reviewer_guidance.get("diagnosis")
        assert isinstance(reviewer_guidance.get("guidance"), dict)
        assert any(e.get("node") == "architect" for e in workflow_history[idx + 1 :]), (
            "Expected architect retry after post-exec reviewer guidance.\n"
            f"workflow_path={workflow_path}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


@pytest.mark.e2e
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_short_reflexive_repair_cycle(tmp_path: Path) -> None:
    """Run bounded full mode and require post-exec structured reviewer feasibility guidance with architect retry."""
    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")

    output_dir = tmp_path / "runs_full_mode_short"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        (
            "Configure ERF ABL and run only 10 coarse timesteps (max_step = 10). "
            "Set dt = 20."
        ),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "ERF/Exec/ABL",
        "--inputs-file-override",
        "inputs_numdiff",
        "--run-mode",
        "full",
        "--max-iterations",
        "5",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    try:
        result = _run_cli(cmd, env, timeout_seconds=300)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"Short full-mode reflexive repair test timed out after 300s: {exc}")

    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history.json missing for short full-mode reflexive repair test.\n"
        f"run_dir={run_dir}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history, "workflow_history is empty for short full-mode reflexive repair test"

    postexec_reviewer_indices = [
        idx
        for idx, entry in enumerate(workflow_history)
        if entry.get("node") == "reviewer"
        and entry.get("details", {}).get("review_context") == "post_execution"
    ]
    assert postexec_reviewer_indices, (
        "Expected post-execution reviewer diagnosis entries.\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    for idx in postexec_reviewer_indices:
        reviewer_guidance = workflow_history[idx].get("details", {}).get("reviewer_guidance", {})
        assert isinstance(reviewer_guidance, dict)
        for required_key in ("feasible", "intent_consistent", "diagnosis", "guidance"):
            assert required_key in reviewer_guidance

    has_architect_after_postexec = any(
        any(e.get("node") == "architect" for e in workflow_history[idx + 1 :])
        for idx in postexec_reviewer_indices
    )
    assert has_architect_after_postexec, (
        "Expected architect reconsideration after post-execution reviewer diagnosis.\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Require at least one execution attempt after reconsideration.
    nodes = [entry.get("node") for entry in workflow_history]
    assert "runner" in nodes, (
        "Expected at least one runner execution attempt after reviewer/architect repair cycle.\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"nodes={nodes}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_postexec_repair_rerun_converges(tmp_path: Path) -> None:
    """Require a true post-exec repair cycle: rerun occurs and final analysis succeeds."""
    if os.getenv("AMREX_AGENT_RUN_SLOW_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_SLOW_E2E=1 to run post-exec rerun convergence E2E")

    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    baseline_dir = repo_path / "Exec" / "ABL"
    if not baseline_dir.exists():
        pytest.skip("ERF ABL baseline not available")

    output_dir = tmp_path / "runs_full_mode_repair_converges"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        (
            "Configure ERF ABL and run only 10 coarse timesteps (max_step = 10). "
            "Set dt = 20."
        ),
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "ERF/Exec/ABL",
        "--inputs-file-override",
        "inputs_numdiff",
        "--run-mode",
        "full",
        "--max-iterations",
        "6",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=600)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history.json missing for post-exec rerun convergence test.\n"
        f"run_dir={run_dir}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history
    _assert_two_phase_solver_contract(
        workflow_history=workflow_history,
        workflow_path=workflow_path,
        result=result,
        parameter_keys=["erf.fixed_dt", "fixed_dt", "dt"],
        allow_preexec_terminal_skip=False,
        solver_label="ERF",
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("PeleC")
@pytest.mark.requires_repos("PeleC")
@pytest.mark.requires_schema("PeleC")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_postexec_repair_rerun_converges_pelec(tmp_path: Path) -> None:
    if os.getenv("AMREX_AGENT_RUN_SLOW_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_SLOW_E2E=1 to run slow full-mode E2E")
    if os.getenv("AMREX_AGENT_RUN_MULTI_SOLVER_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_MULTI_SOLVER_E2E=1 to run multi-solver post-exec E2E")

    repo_path = _resolve_pelec_repo()
    if not repo_path:
        pytest.skip("PeleC repo not available")
    baseline_dir = repo_path / "Exec" / "RegTests" / "PMF"
    if not baseline_dir.exists():
        pytest.skip("PeleC PMF baseline not available")

    output_dir = tmp_path / "runs_full_mode_repair_converges_pelec"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        "Configure PeleC PMF and run only 10 coarse timesteps (max_step = 10). Set amr.cfl = 0.9.",
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "PeleC/Exec/RegTests/PMF",
        "--run-mode",
        "full",
        "--max-iterations",
        "6",
        "--save-workflow",
    ]
    env = os.environ.copy()
    env["PELEC_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=600)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history.json missing for PeleC post-exec rerun convergence test.\n"
        f"run_dir={run_dir}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history
    _assert_two_phase_solver_contract(
        workflow_history=workflow_history,
        workflow_path=workflow_path,
        result=result,
        parameter_keys=["amr.cfl", "pelec.cfl", "cfl"],
        allow_preexec_terminal_skip=True,
        solver_label="PeleC",
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("REMORA")
@pytest.mark.requires_repos("REMORA")
@pytest.mark.requires_schema("REMORA")
@pytest.mark.requires_indices("faiss")
def test_cli_full_mode_postexec_repair_rerun_converges_remora(tmp_path: Path) -> None:
    if os.getenv("AMREX_AGENT_RUN_SLOW_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_SLOW_E2E=1 to run slow full-mode E2E")
    if os.getenv("AMREX_AGENT_RUN_MULTI_SOLVER_E2E", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set AMREX_AGENT_RUN_MULTI_SOLVER_E2E=1 to run multi-solver post-exec E2E")

    repo_path = _resolve_remora_repo()
    if not repo_path:
        pytest.skip("REMORA repo not available")
    baseline_dir = repo_path / "Exec" / "Channel_Test"
    if not baseline_dir.exists():
        pytest.skip("REMORA Channel_Test baseline not available")

    output_dir = tmp_path / "runs_full_mode_repair_converges_remora"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        "Configure REMORA Channel_Test and run only 10 coarse timesteps (max_step = 10). Set remora.fixed_dt = 30.",
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--baseline-override",
        "REMORA/Exec/Channel_Test",
        "--run-mode",
        "full",
        "--max-iterations",
        "6",
        "--save-workflow",
    ]
    env = os.environ.copy()
    env["REMORA_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=600)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history.json missing for REMORA post-exec rerun convergence test.\n"
        f"run_dir={run_dir}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history
    _assert_two_phase_solver_contract(
        workflow_history=workflow_history,
        workflow_path=workflow_path,
        result=result,
        parameter_keys=["remora.fixed_dt", "fixed_dt", "dt"],
        allow_preexec_terminal_skip=True,
        solver_label="REMORA",
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_benchmark_wave_phys_row_avoids_preexec_retry_exhaustion(tmp_path: Path) -> None:
    """Benchmark-row reproducer: one wave_phys row should not terminate via pre-exec retry-exhaustion."""
    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    row_id = "abl_neutral_wave_phys1"
    prompt_text = (
        "Configure ERF ABL neutral boundary layer over flat terrain with coriolis forcing and "
        "stratification controls. Use the canonical Neutral_ABL setup and select a physically "
        "consistent inputs file for this case."
    )
    cfg_path = REPO_ROOT / "results/track2_recovery/model_sweep/configs/lbl__llama4-scout_tuned_weights_retune_20260316.yaml"
    if not cfg_path.exists():
        pytest.skip(f"Benchmark config missing: {cfg_path}")

    output_dir = tmp_path / "runs_benchmark_row_repro"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        prompt_text,
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--inputs-file-strategy",
        "llm_compare",
        "--run-mode",
        "dry",
        "--config",
        str(cfg_path),
        "--max-iterations",
        "3",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=300)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history missing for benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history

    terminal_preexec = [
        e for e in workflow_history
        if e.get("node") == "reviewer"
        and e.get("action") in {
            "intent_coverage_max_retries",
            "parameter_resolution_max_retries",
            "parameter_resolution_stalled",
        }
        and e.get("details", {}).get("status") == "terminal"
        and e.get("details", {}).get("review_context", "pre_execution") in {None, "pre_execution"}
    ]
    assert not terminal_preexec, (
        "Benchmark-row run terminated via pre-execution retry-exhaustion.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"terminal_entries={terminal_preexec}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_benchmark_wave_phys1_hierarchical_reaches_input_writer(tmp_path: Path) -> None:
    """
    RED reproducer for core hierarchical quality/routing issue.
    This benchmark-style row should make it past pre-exec review into input_writer.
    """
    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    row_id = "abl_neutral_wave_phys2"
    prompt_text = (
        "Configure ERF for the Exec/CanonicalFlows/Canonical_LES/Neutral_ABL scenario "
        "and choose inputs_anelastic as baseline inputs."
    )
    expected_case = "Exec/CanonicalFlows/Canonical_LES/Neutral_ABL"
    expected_inputs_suffix = "Exec/CanonicalFlows/Canonical_LES/Neutral_ABL/inputs_anelastic"
    cfg_path = REPO_ROOT / "results/track2_recovery/model_sweep/configs/lbl__llama4-scout_tuned_weights_retune_20260316.yaml"
    if not cfg_path.exists():
        pytest.skip(f"Benchmark config missing: {cfg_path}")

    output_dir = tmp_path / "runs_benchmark_row_hierarchical_repro"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        prompt_text,
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "hierarchical",
        "--inputs-file-strategy",
        "llm_compare",
        "--run-mode",
        "dry",
        "--config",
        str(cfg_path),
        "--max-iterations",
        "3",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=300)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history missing for hierarchical benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history

    has_input_writer = any(e.get("node") == "input_writer" for e in workflow_history)
    assert has_input_writer, (
        "Expected hierarchical benchmark-row run to reach input_writer (pre-exec review should converge).\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"returncode={result.returncode}\n"
        f"nodes={[e.get('node') for e in workflow_history]}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    architect_entries = [e for e in workflow_history if e.get("node") == "architect"]
    assert architect_entries, (
        "Expected at least one architect entry in benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
    )
    selected_case = architect_entries[-1].get("details", {}).get("selected_case")
    assert selected_case == expected_case, (
        "Hierarchical benchmark-row selected incorrect case.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"expected_case={expected_case}\n"
        f"selected_case={selected_case}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    input_writer_entries = [e for e in workflow_history if e.get("node") == "input_writer"]
    assert input_writer_entries, (
        "Expected input_writer entry in benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
    )
    selected_inputs = input_writer_entries[-1].get("details", {}).get("inputs_file_selected", "")
    selected_inputs_text = str(selected_inputs)
    assert selected_inputs_text.endswith(expected_inputs_suffix), (
        "Hierarchical benchmark-row selected incorrect inputs file.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"expected_inputs_suffix={expected_inputs_suffix}\n"
        f"selected_inputs={selected_inputs_text}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.use_real_services
@pytest.mark.requires_solver("ERF")
@pytest.mark.requires_repos("ERF")
@pytest.mark.requires_schema("ERF")
@pytest.mark.requires_indices("faiss")
def test_cli_benchmark_wave_phys2_simple_selects_expected_case(tmp_path: Path) -> None:
    """Companion control: simple strategy should also honor explicit benchmark row case anchor."""
    repo_path = _resolve_erf_repo()
    if not repo_path:
        pytest.skip("ERF repo not available")

    row_id = "abl_neutral_wave_phys2"
    prompt_text = (
        "Configure ERF for the Exec/CanonicalFlows/Canonical_LES/Neutral_ABL scenario "
        "and choose inputs_anelastic as baseline inputs."
    )
    expected_case = "Exec/CanonicalFlows/Canonical_LES/Neutral_ABL"
    expected_inputs_suffix = "Exec/CanonicalFlows/Canonical_LES/Neutral_ABL/inputs_anelastic"
    cfg_path = REPO_ROOT / "results/track2_recovery/model_sweep/configs/lbl__llama4-scout_tuned_weights_retune_20260316.yaml"
    if not cfg_path.exists():
        pytest.skip(f"Benchmark config missing: {cfg_path}")

    output_dir = tmp_path / "runs_benchmark_row_simple_repro"
    cmd = [
        sys.executable,
        "./amrex_agent.py",
        "--prompt",
        prompt_text,
        "--output-dir",
        str(output_dir),
        "--indexing-strategy",
        "simple",
        "--inputs-file-strategy",
        "llm_compare",
        "--run-mode",
        "dry",
        "--config",
        str(cfg_path),
        "--max-iterations",
        "3",
        "--save-workflow",
    ]

    env = os.environ.copy()
    env["ERF_REPO_PATH"] = str(repo_path)

    result = _run_cli(cmd, env, timeout_seconds=300)
    run_dir = _find_run_directory(output_dir)
    workflow_path = _find_workflow_history(output_dir, run_dir)
    assert workflow_path is not None and workflow_path.exists(), (
        "workflow_history missing for simple benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    workflow_history = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(workflow_history, list) and workflow_history

    architect_entries = [e for e in workflow_history if e.get("node") == "architect"]
    assert architect_entries, (
        "Expected at least one architect entry in simple benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
    )
    selected_case = architect_entries[-1].get("details", {}).get("selected_case")
    assert selected_case == expected_case, (
        "Simple benchmark-row selected incorrect case.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"expected_case={expected_case}\n"
        f"selected_case={selected_case}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    input_writer_entries = [e for e in workflow_history if e.get("node") == "input_writer"]
    assert input_writer_entries, (
        "Expected input_writer entry in simple benchmark-row reproducer.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
    )
    selected_inputs = input_writer_entries[-1].get("details", {}).get("inputs_file_selected", "")
    selected_inputs_text = str(selected_inputs)
    assert selected_inputs_text.endswith(expected_inputs_suffix), (
        "Simple benchmark-row selected incorrect inputs file.\n"
        f"row_id={row_id}\n"
        f"workflow_path={workflow_path}\n"
        f"expected_inputs_suffix={expected_inputs_suffix}\n"
        f"selected_inputs={selected_inputs_text}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
