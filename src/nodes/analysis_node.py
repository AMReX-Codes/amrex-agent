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


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).strip())
    except Exception:
        return None


def _format_numeric_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.8g}"


def _derive_postexec_repair_hints(state: GraphState, report: dict[str, Any]) -> dict[str, Any] | None:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    suggestions = report.get("suggestions") if isinstance(report.get("suggestions"), list) else []
    stderr_excerpt = report.get("stderr_excerpt", "")
    evidence_text = " ".join([str(x) for x in [*issues, *suggestions, stderr_excerpt] if x]).lower()
    instability_tokens = [
        "floating point",
        "arithmetic operation",
        "nan",
        "diverg",
        "cfl",
        "unstable",
        "timestep",
        "dt",
        "abort",
        "runner_execution_failed",
    ]
    if not any(token in evidence_text for token in instability_tokens):
        return None

    modification_map: dict[str, Any] = {}
    for item in state.get("modifications", []) or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            modification_map[str(item[0])] = item[1]

    candidate_keys = list(modification_map.keys())
    if not candidate_keys:
        return None

    def _key_tokens(key: str) -> list[str]:
        text = str(key).strip().lower().replace("-", "_")
        return [tok for tok in text.replace(".", "_").split("_") if tok]

    def _dt_score(key: str) -> int:
        text = str(key).strip().lower().replace("-", "_")
        score = 0
        if "fixed_dt" in text:
            score += 50
        if text.endswith(".dt") or text.endswith("_dt") or text == "dt":
            score += 40
        if "time_step" in text or "timestep" in text:
            score += 25
        if "dt" in text:
            score += 15
        return score

    def _cfl_score(key: str) -> int:
        text = str(key).strip().lower().replace("-", "_")
        score = 0
        if text.endswith(".cfl") or text.endswith("_cfl") or text == "cfl":
            score += 50
        if "courant" in text:
            score += 35
        if "cfl" in text:
            score += 20
        return score

    def _is_temporal_key(key: str) -> bool:
        text = str(key).strip().lower().replace("-", "_")
        tokens = _key_tokens(text)
        return any(t in {"dt", "timestep", "time_step", "stop_time", "max_step", "fixed_dt"} for t in tokens)

    def _is_spatial_key(key: str) -> bool:
        text = str(key).strip().lower().replace("-", "_")
        tokens = _key_tokens(text)
        return any(
            t in {"ncell", "n_cell", "max_level", "ref_ratio", "blocking_factor", "grid", "cell", "level"}
            for t in tokens
        )

    temporal_keys = [k for k in candidate_keys if _is_temporal_key(k)]
    spatial_keys = [k for k in candidate_keys if _is_spatial_key(k)]
    cfl_keys = [k for k in candidate_keys if _cfl_score(k) > 0]

    severity_scale = 0.25 if any(t in evidence_text for t in ["floating point", "nan", "diverg", "abort"]) else 0.5
    required_assignments: dict[str, Any] = {}
    required_meta: dict[str, Any] = {}
    unresolved: list[tuple[str, Any]] = []
    suggested_params: dict[str, Any] = {}
    remap_mapping: dict[str, str] = {}

    cfl_key = sorted(cfl_keys, key=_cfl_score, reverse=True)[0] if cfl_keys else None
    if cfl_key:
        cfl_value = _coerce_float(modification_map.get(cfl_key))
        if cfl_value is not None and cfl_value > 0:
            lowered_cfl = max(min(cfl_value * (0.7 if temporal_keys or spatial_keys else 0.8), 0.9), 0.05)
            if lowered_cfl < cfl_value:
                required_assignments[cfl_key] = _format_numeric_value(lowered_cfl)
                required_meta[cfl_key] = {
                    "schema_verified": False,
                    "source": "analysis_node",
                    "match_method": "stability_consistency",
                }
                unresolved.append(("stability_consistency_cfl", _format_numeric_value(cfl_value)))
                suggested_params["cfl"] = cfl_key
                remap_mapping["cfl"] = cfl_key

    # Fallback only when no explicit CFL control is available in the current plan.
    if not required_assignments:
        dt_candidates = sorted(candidate_keys, key=_dt_score, reverse=True)
        dt_key = dt_candidates[0] if dt_candidates and _dt_score(dt_candidates[0]) > 0 else None
        if dt_key:
            current_dt = _coerce_float(modification_map.get(dt_key))
            if current_dt is not None and current_dt > 0:
                proposed_dt = max(current_dt * severity_scale, 1e-8)
                if proposed_dt >= current_dt:
                    proposed_dt = max(current_dt * 0.5, 1e-8)
                required_assignments[dt_key] = _format_numeric_value(proposed_dt)
                required_meta[dt_key] = {
                    "schema_verified": False,
                    "source": "analysis_node",
                    "match_method": "stability_consistency_fallback",
                }
                unresolved.append(("stability_consistency_dt", _format_numeric_value(current_dt)))
                suggested_params["dt"] = dt_key
                remap_mapping["dt"] = dt_key

    if not required_assignments:
        return None

    return {
        "unresolved_parameters": unresolved or [("stability_consistency", "required")],
        "required_assignments": required_assignments,
        "required_assignments_meta": required_meta,
        "resolution_guidance": (
            "Post-execution stability consistency check failed. "
            "Apply coupled temporal/CFL adjustments and rerun."
        ),
        "suggested_params": suggested_params,
        "remap_mapping": remap_mapping,
        "reason_code": "postexec_stability_consistency",
        "consistency_flags": {
            "temporal_keys_present": bool(temporal_keys),
            "spatial_keys_present": bool(spatial_keys),
            "cfl_keys_present": bool(cfl_keys),
        },
    }

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
    runner_failed = (
        str(state.get("job_status", "")).lower() in {"failed", "timeout", "cancelled"}
        or int(state.get("exit_code") or 0) != 0
        or str(state.get("run_status", "")).lower() == "failed"
    )
    if runner_failed and status == "success":
        # Preserve reflexion contract: failed execution must trigger post-exec reviewer diagnosis.
        report["status"] = "failed"
        report_issues = report.get("issues", [])
        if not isinstance(report_issues, list):
            report_issues = [str(report_issues)]
        if "runner_execution_failed" not in report_issues:
            report_issues.append("runner_execution_failed")
        report["issues"] = report_issues
        status = "failed"

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
    postexec_repair_hints = None
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
        postexec_repair_hints = _derive_postexec_repair_hints(state, report)

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
            "postexec_repair_hints": postexec_repair_hints,
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

    next_mode = "retry" if status in {"failed", "unstable"} else "proceed"
    review_context = "post_execution" if status in {"failed", "unstable"} else None
    review_origin = "analysis_diagnosis" if status in {"failed", "unstable"} else None

    updates = {
        # === UTILITY FLAGS ===
        "mode": next_mode,
        "iteration": iteration,

        # === AUDIT TRAIL ===
        "workflow_history": new_history,

        # === PRAGMATIC CONVENIENCE COPIES ===
        # For performance/visualization (optional, matches workflow_history.details)
        "analysis_report": report,
        "error_logs": error_logs if error_logs else state.get('error_logs', []),
        "retry_guidance": retry_guidance,
        "postexec_repair_hints": postexec_repair_hints,
    }
    if review_context:
        updates["review_context"] = review_context
    if review_origin:
        updates["review_origin"] = review_origin
    if mapped_status:
        updates["job_status"] = mapped_status

    logger.info(f"Analysis complete: {status}")
    logger.info("-" * 80)
    logger.info("Analysis node complete")
    logger.info("-" * 80)
    return updates


# Export for LangGraph
__all__ = ['analysis_node']
