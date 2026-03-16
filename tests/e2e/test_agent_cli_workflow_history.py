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

    runner_indices = [i for i, e in enumerate(workflow_history) if e.get("node") == "runner"]
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

    # Require explicit two-phase repair behavior in the same run:
    # 1) pre-exec intent coverage enforces dt=20
    # 2) post-exec repair changes that assignment before rerun
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
    intent_dt_values = []
    for idx in intent_retry_indices:
        if idx >= first_runner_idx:
            continue
        required = workflow_history[idx].get("details", {}).get("required_assignments", {}) or {}
        if "erf.fixed_dt" in required:
            intent_dt_values.append(str(required["erf.fixed_dt"]))
    assert intent_dt_values, (
        "Expected intent coverage to require erf.fixed_dt prior to first runner attempt.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_retry_indices={intent_retry_indices}\n"
    )
    intent_dt_value = intent_dt_values[-1]

    postexec_dt_values = []
    for idx in postexec_reviewer_indices:
        details = workflow_history[idx].get("details", {}) or {}
        repair_feedback = details.get("postexec_repair_feedback", {}) or {}
        required = repair_feedback.get("required_assignments", {}) or {}
        if "erf.fixed_dt" in required:
            postexec_dt_values.append(str(required["erf.fixed_dt"]))
    assert postexec_dt_values, (
        "Expected post-exec reviewer feedback to provide erf.fixed_dt repair assignment.\n"
        f"workflow_path={workflow_path}\n"
    )
    postexec_dt_value = postexec_dt_values[-1]
    assert postexec_dt_value != intent_dt_value, (
        "Expected post-exec repair assignment to differ from pre-exec intent assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_dt_value={intent_dt_value}\n"
        f"postexec_dt_value={postexec_dt_value}\n"
    )

    architect_entries = [
        (i, e)
        for i, e in enumerate(workflow_history)
        if e.get("node") == "architect"
    ]
    assert architect_entries, f"No architect entries found. workflow_path={workflow_path}"

    has_architect_intent_dt_before_first_run = False
    has_architect_postexec_dt_after_postexec = False
    for idx, entry in architect_entries:
        mods = entry.get("details", {}).get("modifications", []) or []
        dt_values = [
            str(item[1])
            for item in mods
            if isinstance(item, (list, tuple)) and len(item) >= 2 and str(item[0]) == "erf.fixed_dt"
        ]
        if not dt_values:
            continue
        if idx < first_runner_idx and intent_dt_value in dt_values:
            has_architect_intent_dt_before_first_run = True
        if any(post_idx < idx for post_idx in postexec_reviewer_indices) and postexec_dt_value in dt_values:
            has_architect_postexec_dt_after_postexec = True

    assert has_architect_intent_dt_before_first_run, (
        "Expected architect plan before first run to contain intent-enforced erf.fixed_dt assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"intent_dt_value={intent_dt_value}\n"
    )
    assert has_architect_postexec_dt_after_postexec, (
        "Expected architect plan after post-exec review to contain repaired erf.fixed_dt assignment.\n"
        f"workflow_path={workflow_path}\n"
        f"postexec_dt_value={postexec_dt_value}\n"
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
