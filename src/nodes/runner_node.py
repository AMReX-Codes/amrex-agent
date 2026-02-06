"""
Runner Node: Runner Node.

Executes simulations using SuperfacilityRunner service.
"""
import inspect
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.services.run_superfacility import SuperfacilityRunner
from src.services.run_superfacility_tools import stage_out_outputs
from src.utils.gate import run_preconfirm_gate

logger = logging.getLogger(__name__)


def runner_node(state: GraphState) -> dict[str, Any]:
    """
    Execute the simulation job for the prepared run directory.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing configuration and run metadata.

    Returns
    -------
    dict
        State updates containing job execution results.
    """
    logger.info("=" * 80)
    logger.info("Starting Runner node")
    logger.info("=" * 80)

    # ========================================
    # COMPONENT 11a: STATE VALIDATION
    # ========================================

    # Check 1: Config exists
    config = state.get("config")
    if not config:
        logger.error("Missing required 'config' in state")
        return {
            "mode": "fail",
            "error": "Runner Node requires 'config' in state"
        }

    # Check 2: Input Writer completed successfully
    ready_to_run = state.get("ready_to_run")
    if not ready_to_run:
        logger.error("Input Writer did not complete successfully")
        return {
            "mode": "fail",
            "error": "Input Writer did not complete successfully (ready_to_run=False)"
        }

    # Check 3: Run directory exists
    run_directory = state.get("run_directory")
    if not run_directory:
        logger.error("Missing 'run_directory' in state")
        return {
            "mode": "fail",
            "error": "Runner Node requires 'run_directory' in state"
        }

    run_dir_path = Path(run_directory)
    if not run_dir_path.exists():
        logger.error(f"Run directory not found: {run_directory}")
        return {
            "mode": "fail",
            "error": f"Run directory not found: {run_directory}"
        }

    # Check 4: Inputs file exists
    inputs_file_path = state.get("inputs_file_path")
    if not inputs_file_path:
        logger.error("Missing 'inputs_file_path' in state")
        return {
            "mode": "fail",
            "error": "Runner Node requires 'inputs_file_path' in state"
        }

    inputs_path = Path(inputs_file_path)
    if not inputs_path.exists():
        logger.error(f"Inputs file not found: {inputs_file_path}")
        return {
            "mode": "fail",
            "error": f"Inputs file not found: {inputs_file_path}"
        }

    logger.info(f"Validation passed: {run_dir_path.name}")

    # ========================================
    # COMPONENT 11b: SERVICE ORCHESTRATION
    # ========================================

    # Extract baseline path for executable discovery
    plan = state.get("plan", {})
    baseline = state.get("baseline", {})

    # Validate baseline path exists (needed for executable discovery)
    if not plan and not baseline.get("local_path"):
        logger.error("Missing baseline path for executable discovery")
        return {
            "mode": "fail",
            "error": "Missing baseline path (plan or baseline.local_path required)"
        }

    compile_gate_entry = None
    run_gate_entry = None
    try:
        run_mode = getattr(config, "run_mode", None)
        if run_mode is None or run_mode == "full":
            if getattr(config, "dry_run", False):
                run_mode = "dry"
            else:
                run_mode = run_mode or "full"
        compile_gate = run_preconfirm_gate(
            node_name="runner_compile",
            summary_lines=[
                "This step compiles/links the executable and prepares the run directory.",
                f"Run directory: {run_directory}",
                f"Inputs file: {inputs_file_path}",
            ],
            options=[
                {"label": "Compile and run", "value": "compile_and_run"},
                {"label": "Compile only (skip run)", "value": "compile_only"},
            ],
            enabled=getattr(config, "preconfirm_gate", False) is True,
            allow_cancel=True,
        )
        compile_gate_entry = compile_gate.get("history_entry")
        if compile_gate_entry:
            compile_gate_entry["iteration"] = state.get("iteration", 0)
        if compile_gate["action"] == "cancel":
            return {
                "mode": "terminal",
                "error": "User canceled at pre-confirm gate.",
                "job_status": "skipped",
                "workflow_history": state.get("workflow_history", []) + ([compile_gate_entry] if compile_gate_entry else []),
            }

        run_after_compile = True
        compile_selection = compile_gate.get("selection") or {}
        if compile_selection.get("value") == "compile_only":
            run_after_compile = False

        # Select runner based on environment
        if config.environment == "local":
            from src.services.run_local import LocalRunner
            runner = LocalRunner(config)
            logger.info("Using LocalRunner for local execution")
        else:
            runner = SuperfacilityRunner(config)
            logger.info(f"Using SuperfacilityRunner for {config.environment}")

        # Setup job (Runner Node: Executable Resolution: Executable Discovery & Linking)
        # Service handles:
        # - Finding .ex file in baseline directory
        # - Filtering by config.use_mpi / use_cuda
        # - Symlinking to run_directory
        # Extract baseline directory for executable search
        baseline = state.get("baseline", {})
        case_dir = baseline.get("local_path")

        setup_kwargs = {
            "output_dir": str(run_dir_path),
            "case_dir": case_dir,
        }
        try:
            if "inputs_path" in inspect.signature(runner.setup_job).parameters:
                setup_kwargs["inputs_path"] = str(inputs_path)
        except (TypeError, ValueError):
            pass

        setup_result = runner.setup_job(**setup_kwargs)

        # Extract actual run directory from setup (may be nested)
        actual_run_dir = setup_result.get('run_dir')
        logger.info(f"Job setup complete: {setup_result.get('executable')}")
        logger.debug(f"   Using run directory: {actual_run_dir}")

        if not run_after_compile:
            history_entry = {
                "node": "runner",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "compile_only",
                "iteration": state.get("iteration", 0),
                "details": {
                    "run_dir": actual_run_dir,
                    "executable": setup_result.get("executable"),
                },
            }
            workflow_history = state.get("workflow_history", [])
            if compile_gate_entry:
                workflow_history = workflow_history + [compile_gate_entry]
            return {
                "mode": "terminal",
                "job_status": "skipped",
                "executable_path": setup_result.get("executable"),
                "workflow_history": workflow_history + [history_entry],
            }

        # Submit job (Runner Node: Script Generation)
        # Use the ACTUAL run directory returned by setup, not the parent
        run_gate = run_preconfirm_gate(
            node_name="runner_submit",
            summary_lines=[
                "This step submits the job to run.",
                f"Run directory: {actual_run_dir}",
            ],
            options=[{"label": "Submit run", "value": "run_now"}],
            enabled=getattr(config, "preconfirm_gate", False) is True,
            allow_cancel=True,
        )
        run_gate_entry = run_gate.get("history_entry")
        if run_gate_entry:
            run_gate_entry["iteration"] = state.get("iteration", 0)
        if run_gate["action"] == "cancel":
            workflow_history = state.get("workflow_history", [])
            if compile_gate_entry:
                workflow_history = workflow_history + [compile_gate_entry]
            if run_gate_entry:
                workflow_history = workflow_history + [run_gate_entry]
            return {
                "mode": "terminal",
                "error": "User canceled at pre-confirm gate.",
                "job_status": "skipped",
                "workflow_history": workflow_history,
            }
        submit_kwargs = {"run_directory": actual_run_dir}
        submit_sig = None
        try:
            submit_sig = inspect.signature(runner.submit)
        except (TypeError, ValueError):
            submit_sig = None

        if submit_sig:
            params = submit_sig.parameters
            if "nodes" in params:
                submit_kwargs["nodes"] = getattr(config, "mpi_ranks", 1)
            if "run_mode" in params:
                submit_kwargs["run_mode"] = run_mode
            if "dry_run" in params:
                submit_kwargs["dry_run"] = getattr(config, "dry_run", False)
            if "case_dir" in params:
                submit_kwargs["case_dir"] = case_dir

        submit_result = runner.submit(**submit_kwargs)

        if config.environment != "local":
            monitor_enabled = getattr(config, "monitor_job", True)
            job_status = submit_result.get("job_status")
            monitor_states = {None, "queued", "pending", "running", "submitted"}
            if (
                not getattr(config, "dry_run", False)
                and monitor_enabled
                and submit_result.get("job_id")
                and job_status in monitor_states
                and hasattr(runner, "monitor")
            ):
                final_state = runner.monitor(
                    job_id=submit_result["job_id"],
                    method=submit_result.get("method", "sbatch"),
                )
                submit_result["job_status"] = final_state
                submit_result["final_state"] = final_state
                if (
                    getattr(config, "stage_out_outputs", True)
                    and submit_result.get("remote_run_dir")
                ):
                    stage_out_result = stage_out_outputs(
                        remote_run_dir=submit_result["remote_run_dir"],
                        local_run_dir=actual_run_dir,
                        system=getattr(config, "environment", "perlmutter"),
                    )
                    submit_result["stage_out"] = stage_out_result
                    if stage_out_result.get("errors"):
                        logger.warning(
                            "Stage-out completed with errors: %s",
                            stage_out_result["errors"],
                        )

        final_state = None
        method = submit_result.get("method")
        if final_state is None and run_mode == "full" and method not in {"dry_run", "stage_only"}:
            job_id = submit_result.get("job_id")
            job_status = submit_result.get("job_status")
            monitor_states = {None, "queued", "pending", "running", "submitted"}
            if job_id and hasattr(runner, "monitor") and job_status in monitor_states:
                final_state = runner.monitor(job_id, method=method or "sbatch")

        # ========================================
        # COMPONENT 11e: OUTPUT MAPPING (Complete)
        # ========================================
        # Handle dry run case (no real job ID)
        job_id = submit_result.get("job_id") or "dry_run_placeholder"

        # Create structured history entry (Fix 11 - canonical format)
        action = "job_submitted"
        if run_mode == "dry":
            action = "job_dry_run"
        elif run_mode == "stage":
            action = "job_staged"
        history_entry = {
            "node": "runner",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "iteration": state.get("iteration", 0),
            "details": {
                "job_id": job_id,
                "script_path": submit_result.get("script_path"),
                "run_directory": str(actual_run_dir),
            }
        }

        # Get actual job status from submit result
        actual_status = submit_result.get("job_status", "completed")
        if final_state:
            state_str = str(final_state).upper()
            failed_states = {
                "FAILED",
                "CANCELLED",
                "TIMEOUT",
                "NODE_FAIL",
                "OUT_OF_MEMORY",
                "BOOT_FAIL",
                "DEADLINE",
                "PREEMPTED",
            }
            completed_states = {"COMPLETED", "COMPLETING", "DONE", "SUCCESS"}
            running_states = {"RUNNING", "PENDING", "CONFIGURING"}
            if state_str in failed_states:
                actual_status = "failed"
            elif state_str in completed_states:
                actual_status = "completed"
            elif state_str in running_states:
                actual_status = "running"
            else:
                actual_status = state_str.lower()
        exit_code = submit_result.get("exit_code", 0)

        workflow_history = state.get("workflow_history", [])
        if compile_gate_entry:
            workflow_history = workflow_history + [compile_gate_entry]
        if run_gate_entry:
            workflow_history = workflow_history + [run_gate_entry]

        logger.info("-" * 80)
        logger.info(f"Runner node complete ({actual_status})")
        logger.info("-" * 80)
        return {
            "mode": "proceed",
            "executable_path": setup_result.get("executable"),  # Propagate discovered executable (Fix 4)
            "job_id": job_id,
            "script_path": submit_result.get("script_path"),
            "job_submission_time": datetime.utcnow().isoformat() + "Z",  # Track submission time
            "job_status": actual_status,  # Use actual status from submit (completed or failed)
            "exit_code": exit_code,
            "workflow_history": workflow_history + [history_entry]
        }

    except (FileNotFoundError, PermissionError) as e:
        # Executable discovery failures
        logger.error(f"Executable resolution failed: {e}")
        history_entry = {
            "node": "runner",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "write_failed",
            "iteration": state.get("iteration", 0),
            "details": {
                "error": str(e)
            }
        }

        workflow_history = state.get("workflow_history", [])
        if compile_gate_entry:
            workflow_history = workflow_history + [compile_gate_entry]
        if run_gate_entry:
            workflow_history = workflow_history + [run_gate_entry]
        return {
            "mode": "fail",
            "error": f"Executable resolution failed: {str(e)}",
            "workflow_history": workflow_history + [history_entry]
        }
    except Exception as e:
        logger.exception("Runner execution failed")

        # Check if this is a compilation failure (terminal condition)
        error_str = str(e)
        is_compilation_error = "Compilation failed" in error_str or "compilation error" in error_str.lower()

        if is_compilation_error:
            logger.error("Compilation failure detected - this is terminal")

        history_entry = {
            "node": "runner",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "compilation_failed" if is_compilation_error else "execution_failed",
            "iteration": state.get("iteration", 0),
            "details": {
                "error": error_str,
                "compilation_failed": is_compilation_error
            }
        }

        workflow_history = state.get("workflow_history", [])
        if compile_gate_entry:
            workflow_history = workflow_history + [compile_gate_entry]
        if run_gate_entry:
            workflow_history = workflow_history + [run_gate_entry]
        return {
            "mode": "terminal" if is_compilation_error else "analysis",
            "error": f"Runner execution failed: {error_str}",
            "compilation_failed": is_compilation_error,
            "run_status": "failed",
            "workflow_history": workflow_history + [history_entry]
        }
