"""
Analysis node - Post-execution log analysis and metrics extraction.

Purpose: Parse AMReX log files, detect issues, extract performance metrics
Runs: ALWAYS after simulation completion (based on user decision)

Workflow integration: After runner node
"""

# Removed: add_history_entry (no longer using in-place modifications)
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.services.analysis import AnalysisService
from src.utils.gate import run_preconfirm_gate

logger = logging.getLogger(__name__)


def get_run_directory(state: GraphState) -> str | None:
    """
    Resolve the run directory from workflow history or state.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing workflow history and run metadata.

    Returns
    -------
    str or None
        Run directory path if found; otherwise ``None``.
    """
    # Prefer runner entry if available (post-staging)
    try:
        runner_entry = next(
            e for e in reversed(state.get('workflow_history', []))
            if e.get('node') == 'runner'
        )
        run_dir = runner_entry.get('details', {}).get('run_directory')
        if run_dir:
            logger.debug("Run directory loaded from runner workflow_history entry")
            return run_dir
    except StopIteration:
        pass

    # Try canonical path next (source of truth)
    try:
        input_writer_entry = next(
            e for e in reversed(state.get('workflow_history', []))
            if e.get('node') == 'input_writer'
        )
        run_dir = input_writer_entry.get('details', {}).get('run_directory')
        if run_dir:
            logger.debug("Run directory loaded from workflow_history (canonical path)")
            return run_dir
    except StopIteration:
        logger.debug("Input writer entry not in workflow_history, falling back to state")

    # Fallback to pragmatic path (convenience copy in state)
    run_dir = state.get("run_directory")
    if run_dir:
        logger.debug("Run directory loaded from state (pragmatic path - convenience copy)")
        return run_dir

    logger.warning("Run directory not found in workflow_history or state")
    return None

def analysis_node(state: GraphState) -> dict[str, Any]:
    """
    Analyze simulation output logs and performance metrics.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing run directory metadata.

    Returns
    -------
    dict
        State updates containing analysis results.
    """
    logger.info("=" * 80)
    logger.info("Starting Analysis node")
    logger.info("=" * 80)

    config = state["config"]
    iteration = state.get("iteration", 0)

    run_mode = getattr(config, "run_mode", None)
    if run_mode is None or run_mode == "full":
        if getattr(config, "dry_run", False):
            run_mode = "dry"
        else:
            run_mode = run_mode or "full"

    if run_mode in {"dry", "stage", "submit"}:
        logger.info("[INFO] Run mode %s - skipping analysis", run_mode)
        workflow_history = state.get("workflow_history", [])
        history_entry = {
            "node": "analysis",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "analysis_skipped",
            "iteration": iteration,
            "details": {
                "status": "skipped",
                "reason": run_mode
            }
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "job_status": state.get("job_status", "completed"),
            "analysis_report": {
                "status": "skipped",
                "message": "Dry-run: analysis skipped"
            }
        }

    gate_entry = None
    run_dir = get_run_directory(state)
    auto_approve = getattr(config, "preconfirm_gate_auto_approve", False) is True
    gate_result = run_preconfirm_gate(
        node_name="analysis",
        summary_lines=[
            "This step analyzes simulation output for errors and metrics.",
            f"Run directory: {run_dir or 'unknown'}",
            f"Job status: {state.get('job_status', 'unknown')}",
            f"Run mode: {run_mode}",
        ],
        options=[{"label": "Proceed with analysis", "value": "proceed"}],
        enabled=getattr(config, "preconfirm_gate", False) is True,
        allow_cancel=True,
        auto_approve=auto_approve,
    )
    gate_entry = gate_result.get("history_entry")
    if gate_entry:
        gate_entry["iteration"] = iteration
    if gate_result["action"] == "cancel":
        return {
            "mode": "terminal",
            "job_status": "skipped",
            "analysis_report": {
                "status": "skipped",
                "message": "User canceled analysis at pre-confirm gate.",
            },
            "workflow_history": state.get("workflow_history", []) + ([gate_entry] if gate_entry else []),
        }

    # Get run_directory from canonical path (workflow_history) with fallback to state
    run_dir = get_run_directory(state)

    if not run_dir:
        logger.warning("[WARN] No run directory provided (skipping analysis)")

        # ========================================
        # WORKFLOW HISTORY ENTRY (SKIPPED)
        # ========================================

        workflow_history = state.get("workflow_history", [])
        history_entry = {
            "node": "analysis",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "analysis_skipped",
            "iteration": iteration,
            "details": {
                "status": "skipped",
                "reason": "No run directory provided"
            }
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "job_status": state.get("job_status", "completed"),
            "analysis_report": {
                "status": "skipped",
                "message": "No run directory"
            }
        }

    # Create analysis service
    analyzer = AnalysisService(config)
    logger.debug(f"AnalysisService created for: {run_dir}")

    # Analyze simulation
    # Note: Visual diagnostics deferred to Phase 5
    baseline = state.get("baseline", {}) or {}
    case_dir = baseline.get("local_path")
    repo_root = baseline.get("repo_path")
    executable_path = state.get("executable_path")

    try:
        import inspect

        kwargs = {
            "run_dir": Path(run_dir),
            "include_visual": False,  # Phase 5 feature
        }
        optional_args = {
            "solver_name": state.get("selected_solver"),
            "case_dir": Path(case_dir) if case_dir else None,
            "repo_root": Path(repo_root) if repo_root else None,
            "executable_path": executable_path,
        }

        sig = inspect.signature(analyzer.analyze_simulation)
        for key, value in optional_args.items():
            if key in sig.parameters:
                kwargs[key] = value

        report = analyzer.analyze_simulation(**kwargs)
        logger.debug("Analysis completed successfully")
    except Exception as e:
        # Catch any service errors and return graceful failure
        logger.error(f"[ERROR] Analysis service crashed: {e}")
        report = {
            "status": "failed",
            "issues": [f"Analysis service error: {str(e)}"],
            "warnings": [],
            "metrics": {}
        }

    # ========================================
    # WORKFLOW HISTORY ENTRY (CANONICAL PATH)
    # ========================================
    # Store complete analysis results in workflow_history.details

    workflow_history = state.get("workflow_history", [])
    if gate_entry:
        workflow_history = workflow_history + [gate_entry]
    status = report.get('status', 'unknown')

    # Determine action based on status
    if status == 'success':
        action = "analysis_success"
        logger.info("[PASS] Simulation completed successfully")
    elif status == 'unstable':
        action = "analysis_unstable"
        logger.warning("[WARN] Simulation UNSTABLE")
    elif status == 'failed':
        action = "analysis_failed"
        logger.error("[ERROR] Simulation FAILED")
    else:
        action = "analysis_unknown"
        logger.warning("[QUERY] Status: %s", status)

    # Retry guidance for inputs/baseline adjustments
    retry_guidance = None
    if status in {"failed", "unstable"}:
        issues = report.get("issues", []) or []
        issue_text = " ".join(str(i).lower() for i in issues)
        inputs_action = "keep"
        baseline_action = "keep"
        inputs_reason = None
        baseline_reason = None

        if any(token in issue_text for token in ["input", "inputs", "initial", "setup", "configuration"]):
            inputs_action = "switch"
            inputs_reason = "analysis_indicates_setup_issue"

        if any(token in issue_text for token in ["baseline", "case", "directory", "repo"]):
            baseline_action = "switch"
            baseline_reason = "analysis_indicates_case_issue"

        retry_guidance = {
            "inputs_base_action": inputs_action,
            "inputs_reason": inputs_reason,
            "baseline_base_action": baseline_action,
            "baseline_reason": baseline_reason,
        }

        if (
            inputs_action == "keep"
            and baseline_action == "keep"
            and getattr(config, "retry_guidance_use_llm", False)
        ):
            try:
                from src.utils.metrics import metrics_context

                from database.configs.base_amrex_config import BaseAMReXConfig

                from src.config import get_llm_client
                llm_client = get_llm_client(config)
                prompt = BaseAMReXConfig.get_prompt_templates().get("misc", {}).get("retry_guidance")
                if prompt:
                    filled = prompt.format(
                        solver=state.get("selected_solver") or "unknown",
                        baseline_case=state.get("selected_case") or "unknown",
                        inputs_file=state.get("used_inputs_file") or "unknown",
                        errors_current="none",
                        errors_all_found="\n".join(state.get("errors_found", []) or []) or "none",
                        errors_all_fixed="\n".join(state.get("errors_fixed", []) or []) or "none",
                        analysis_issues="\n".join(issues) if issues else "none",
                    )
                    try:
                        import json
                        from pydantic import BaseModel, Field
                        from src.utils.llm_calls import LLMCallSpec, call_llm

                        class RetryGuidance(BaseModel):
                            inputs_base_action: str = Field(description="keep or switch")
                            baseline_base_action: str = Field(description="keep or switch")
                            rationale: str | None = None

                        spec = LLMCallSpec(
                            model=config.llm_model,
                            response_model=RetryGuidance,
                            messages=[{"role": "user", "content": filled}],
                            temperature=0.0,
                            max_retries=2,
                            purpose="retry_guidance",
                            template_name="retry_guidance",
                            template_source="base_config.misc",
                        )
                        with metrics_context("analysis", node="analysis", iteration=iteration):
                            result = call_llm(llm_client, spec, config=config)
                        if hasattr(result, "inputs_base_action"):
                            retry_guidance.update({
                                "inputs_base_action": result.inputs_base_action or "keep",
                                "baseline_base_action": result.baseline_base_action or "keep",
                                "inputs_reason": result.rationale,
                                "baseline_reason": result.rationale,
                            })
                        else:
                            content = result.choices[0].message.content.strip()
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                retry_guidance.update({
                                    "inputs_base_action": parsed.get("inputs_base_action", "keep"),
                                    "baseline_base_action": parsed.get("baseline_base_action", "keep"),
                                    "inputs_reason": parsed.get("rationale"),
                                    "baseline_reason": parsed.get("rationale"),
                                })
                    except Exception as exc:
                        logger.debug(f"Retry guidance LLM unavailable: {exc}")
            except Exception as exc:
                logger.debug(f"Retry guidance LLM unavailable: {exc}")

    try:
        from src.utils.metrics import metrics_collector

        metrics_summary = metrics_collector.summarize_stage("analysis", iteration=iteration)
    except Exception:
        metrics_summary = {}

    history_entry = {
        "node": "analysis",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "iteration": iteration,
        "details": {
            # Full computation output (canonical path - source of truth)
            "status": status,
            "report": report,  # Complete analysis report
            # Summary metrics for quick access
            "issues_count": len(report.get('issues', [])),
            "warnings_count": len(report.get('warnings', [])),
            "has_suggestions": bool(report.get('suggestions')),
            # Performance metrics
            "performance": report.get('performance', {}),
            "retry_guidance": retry_guidance,
        }
    }
    if metrics_summary:
        history_entry["details"]["metrics"] = metrics_summary

    new_history = workflow_history + [history_entry]

    # ========================================
    # STATE UPDATES (LangGraph PATTERN)
    # ========================================

    # Prepare error logs if needed
    error_logs = state.get('error_logs', [])
    if status == 'failed':
        issues = report.get('issues', [])
        error_logs = error_logs + issues
        logger.debug(f"   Critical issues: {len(issues)}")

        # Log suggestions if available
        suggestions = report.get('suggestions', [])
        if suggestions:
            logger.debug("\n[TIP] Retry suggestions:")
            for i, suggestion in enumerate(suggestions[:3], 1):
                logger.debug(f"   {i}. {suggestion}")

    elif status == 'unstable':
        issues = report.get('issues', [])
        logger.debug(f"   Issues detected: {len(issues)}")

    elif status == 'success':
        # Print performance summary
        performance = report.get('performance', {})
        if performance.get('avg_cells_per_sec'):
            logger.debug(f"   Performance: {performance['avg_cells_per_sec']:,.0f} cells/s (avg)")

    # Return state updates dict
    status_map = {
        "success": "completed",
        "failed": "failed",
        "unstable": "failed",
    }
    mapped_status = status_map.get(status)

    updates = {
        # === UTILITY FLAGS ===
        "mode": "proceed",
        "iteration": iteration,

        # === AUDIT TRAIL ===
        "workflow_history": new_history,

        # === PRAGMATIC CONVENIENCE COPIES ===
        # For performance/visualization (optional, matches workflow_history.details)
        "analysis_report": report,
        "error_logs": error_logs if error_logs else state.get('error_logs', []),
        "retry_guidance": retry_guidance,
    }
    if mapped_status:
        updates["job_status"] = mapped_status

    logger.info(f"Analysis complete: {status}")
    logger.info("-" * 80)
    logger.info("Analysis node complete")
    logger.info("-" * 80)
    return updates


# Export for LangGraph
__all__ = ['analysis_node']
