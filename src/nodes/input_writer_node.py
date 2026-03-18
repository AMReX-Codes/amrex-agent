"""
Input Writer Node: Input Writer Node.

LangGraph node wrapper for InputWriterService.
Architecture: Node = Path logic, Service = I/O operations
"""
import logging
import inspect
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.nodes.visualization_intent_node import resolve_visualization_intent
from src.services.input_writer import InputWriterService
from src.utils.gate import run_preconfirm_gate

logger = logging.getLogger(__name__)


def input_writer_node(state: GraphState) -> dict[str, Any]:
    """
    Write inputs and prepare the run directory for execution.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing configuration and architect plan data.

    Returns
    -------
    dict
        State updates including run directory and input file metadata.
    """
    logger.info("=" * 80)
    logger.info("Starting Input Writer node")
    logger.info("=" * 80)

    # ========================================
    # COMPONENT 10a: STATE VALIDATION & PLAN EXTRACTION FROM WORKFLOW_HISTORY
    # ========================================

    config = state.get("config")
    if not config:
        logger.error("Missing required 'config' in state")
        raise ValueError("Input Writer Node requires 'config' in state")

    workflow_history = state.get("workflow_history", [])
    architect_entry = next(
        (entry for entry in reversed(workflow_history) if entry.get("node") == "architect"),
        None,
    )
    plan_details = architect_entry.get("details", {}) if architect_entry else {}
    selected_case = plan_details.get("selected_case", "unknown")
    modifications = plan_details.get("modifications", []) or []
    baseline = plan_details.get("baseline", {}) or {}
    baseline_path = baseline.get("local_path", "unknown")

    auto_approve = getattr(config, "preconfirm_gate_auto_approve", False) is True
    gate_result = run_preconfirm_gate(
        node_name="input_writer",
        summary_lines=[
            "This step writes inputs and prepares the run directory.",
            f"Selected case: {selected_case}",
            f"Baseline path: {baseline_path}",
            f"Planned modifications: {len(modifications)}",
        ],
        options=[{"label": "Proceed with input writing", "value": "proceed"}],
        enabled=getattr(config, "preconfirm_gate", False) is True,
        allow_cancel=True,
        auto_approve=auto_approve,
    )
    gate_entry = gate_result.get("history_entry")
    if gate_entry:
        gate_entry["iteration"] = state.get("iteration", 0)
    if gate_result["action"] == "cancel":
        return {
            "mode": "terminal",
            "error": "User canceled at pre-confirm gate.",
            "workflow_history": state.get("workflow_history", []) + ([gate_entry] if gate_entry else []),
        }

    # === CRITICAL: Read plan from workflow_history, NOT top-level state ===
    # Per contract line 12-18: Extract plan by searching workflow_history
    # for architect entry, then read from details (canonical location)
    workflow_history = state.get("workflow_history", [])
    if gate_entry:
        workflow_history = workflow_history + [gate_entry]

    architect_entry = None
    try:
        # Search in reverse to find most recent architect entry
        architect_entry = next(
            (entry for entry in reversed(workflow_history)
             if entry.get("node") == "architect"),
            None
        )
    except StopIteration:
        architect_entry = None

    if not architect_entry:
        logger.error("No architect entry found in workflow_history")
        return {
            "mode": "fail",
            "error": "Missing architect plan in workflow_history",
            "workflow_history": workflow_history
        }

    # Extract all plan data from canonical location (workflow_history)
    plan_details = architect_entry.get("details", {})
    selected_case = plan_details.get("selected_case")
    modifications = plan_details.get("modifications", [])
    baseline = plan_details.get("baseline")
    reasoning = plan_details.get("reasoning", "")
    vis_intent = resolve_visualization_intent(state)
    requested_plot_vars = vis_intent.get("requested_fields", []) or []
    visualization_config = vis_intent.get("visualization_config", {}) or {}

    logger.debug(f"[InputWriter] Plan extracted from workflow_history: {selected_case}")
    logger.debug(f"[InputWriter] Extracted {len(modifications)} modifications: {modifications[:3]}...")
    logger.debug(f"[InputWriter] Baseline: {baseline}")

    def _should_prefer_strategy_on_retry(state: GraphState) -> bool:
        if state.get("retry_count", 0) <= 0:
            return False
        guidance = state.get("retry_guidance", {}) or {}
        if guidance.get("inputs_base_action") == "switch":
            return True
        review = state.get("review", {}) or {}
        if review.get("status") == "rejected":
            if review.get("rejected_inputs_file"):
                return True
            errors = review.get("errors", []) or []
            if any("input" in str(e).lower() for e in errors):
                return True
        analysis_report = state.get("analysis_report", {}) or {}
        if analysis_report.get("status") == "failed":
            issues = analysis_report.get("issues", []) or []
            if any("input" in str(i).lower() or "initial" in str(i).lower() for i in issues):
                return True
        return False

    # Validate baseline structure (contract line 127-130)
    if not baseline:
        logger.error("Baseline is missing from plan")
        return {
            "mode": "fail",
            "error": "Baseline metadata missing from architect plan",
            "workflow_history": workflow_history
        }

    if not baseline.get("local_path"):
        logger.error(f"Baseline missing local_path: {baseline}")
        return {
            "mode": "fail",
            "error": "Incomplete baseline metadata (missing local_path)",
            "workflow_history": workflow_history
        }

    # Validate selected_case
    if not selected_case:
        logger.error("selected_case is empty from plan")
        return {
            "mode": "fail",
            "error": "No case selected in architect plan",
            "workflow_history": workflow_history
        }

    # ========================================
    # COMPONENT 10b: SERVICE ORCHESTRATION
    # ========================================

    # 1. Determine run directory path under configured output root.
    # Keep generated directories nested under config.output_dir (e.g., benchmark strategy root).
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_base = Path(config.output_dir)
    run_dir = output_base / f"run_{timestamp}"

    logger.debug(f"Target directory: {run_dir}")

    try:
        from src.services.cases import AMReXCasesService
        cases_service = AMReXCasesService(config)
        baseline_override = getattr(config, "baseline_override", None)
        if baseline_override:
            config.inputs_default_precedence = "strategy_first"
            logger.info(
                "[InputWriter] Baseline override detected; using strategy_first precedence "
                "for inputs selection"
            )
        elif _should_prefer_strategy_on_retry(state):
            config.inputs_default_precedence = "strategy_first"
            logger.info("[InputWriter] Retry context suggests varying inputs base; "
                        "using strategy_first precedence for inputs selection")
        else:
            config.inputs_default_precedence = "strategy_first"
        service = InputWriterService(config)
        # Ensure cases_service is available
        if not hasattr(service, 'cases_svc') or not service.cases_svc:
            service.cases_svc = cases_service
        logger.debug("InputWriterService instantiated with cases service")
    except Exception as e:
        logger.exception("Failed to instantiate InputWriterService")
        return {
            "error": f"Service instantiation failed: {str(e)}",
            "mode": "fail",
            "workflow_history": workflow_history + [{
                "node": "input_writer",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "init_failed",
                "iteration": state.get("iteration", 0),
                "details": {
                    "error": str(e)
                }
            }]
        }

    try:
        from src.utils.metrics import metrics_context

        # 2. Call service with individual parameters (per contract)
        # apply_plan() signature: selected_case, modifications, baseline, reasoning, output_dir
        with metrics_context("input_writer", node="input_writer", iteration=state.get("iteration", 0)):
            apply_kwargs = {
                "selected_case": selected_case,
                "modifications": modifications,
                "baseline": baseline,
                "reasoning": reasoning,
                "user_prompt": (state.get("prompt") or state.get("user_prompt") or ""),
                "output_dir": str(run_dir),  # Service physically creates this
                "requested_plot_vars": requested_plot_vars,
                "visualization_config": visualization_config,
            }
            signature = inspect.signature(service.apply_plan)
            params = signature.parameters
            accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
            if not accepts_var_kw:
                apply_kwargs = {key: value for key, value in apply_kwargs.items() if key in params}

            result = service.apply_plan(**apply_kwargs)

        logger.info(f"Files written to: {result.get('run_dir', 'unknown')}")

    except Exception as e:
        logger.exception("Input writing failed")
        error_entry = {
            "node": "input_writer",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "write_failed",
            "iteration": state.get("iteration", 0),
            "details": {
                "error": str(e),
                "selected_case": selected_case,
                "baseline_code": baseline.get("code_name") if baseline else None
            }
        }
        return {
            "error": f"Writing failed: {str(e)}",
            "mode": "fail",
            "ready_to_run": False,  # Prevent Runner from attempting execution
            "workflow_history": workflow_history + [error_entry]
        }

    # ========================================
    # COMPONENT 10c: PARAMETER RESOLUTION CHECK
    # ========================================

    # Check if service flagged unresolved parameters
    logger.debug("[DATA TRANSFER] Checking InputWriterService result")
    logger.debug(f"[DATA TRANSFER] Service result keys: {list(result.keys())}")
    if result.get("requires_parameter_resolution"):
        logger.debug("[DATA TRANSFER] Service flagged parameter resolution required")
        unresolved = result.get("unresolved_parameters", [])
        guidance = result.get("resolution_guidance", "")
        available = result.get("available_schema_params", [])
        suggested = result.get("suggested_params", {})

        logger.debug(f"[DATA TRANSFER] Extracted unresolved_parameters: {len(unresolved)} items")
        logger.debug(f"[DATA TRANSFER] Extracted available_schema_params: {len(available)} items")
        logger.debug(f"[DATA TRANSFER] Extracted suggested_params: {len(suggested)} mappings")

        logger.warning(
            f"[InputWriter] {len(unresolved)} unresolved parameters - "
            f"returning to architect for re-planning"
        )

        # Create history entry for failed resolution
        resolution_entry = {
            "node": "input_writer",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "parameter_resolution_failed",
            "iteration": state.get("iteration", 0),
            "details": {
                "unresolved_parameters": unresolved,
                "resolution_guidance": guidance,
                "available_schema_params": available[:100],  # Cap for state size
                "suggested_params": suggested,
                "selected_case": selected_case,
                "inputs_path": result.get("inputs_path"),  # File was still written
                "run_dir": result.get("run_dir"),
                "inputs_file_selected": result.get("inputs_file_selected"),
                "inputs_file_strategy": result.get("inputs_file_strategy"),
                "inputs_file_override": result.get("inputs_file_override"),
                "inputs_candidates": result.get("inputs_candidates", []),
            }
        }

        return {
            # Control flow - route to reviewer which will send to architect
            "mode": "review",
            "requires_parameter_resolution": True,  # Flag for reviewer routing
            "iteration": state.get("iteration", 0),

            # File was written (possibly incomplete) - track for exclusion on retry
            "inputs_file_path": result.get("inputs_path"),
            "used_inputs_file": result.get("inputs_file_selected"),
            "run_directory": result.get("run_dir"),

            # Audit trail - resolution details stored in workflow_history[-1]['details']
            "workflow_history": workflow_history + [resolution_entry]
        }

    # ========================================
    # COMPONENT 10d: SERVICE ERROR HANDLING
    # ========================================

    # Check for service-level errors
    if result.get("status") == "error":
        # Handle both singular 'error' and plural 'errors' from service
        errors = result.get("errors") or [result.get("error", "Unknown error")]
        logger.error(f"Service returned errors: {errors}")

        # Validation errors are retryable (Architect can fix)
        error_entry = {
            "node": "input_writer",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "validation_failed",
            "iteration": state.get("iteration", 0),
            "details": {
                "errors": errors,
                "selected_case": selected_case,
                "baseline_code": baseline.get("code_name") if baseline else None,
                "inputs_file_selected": result.get("inputs_file_selected"),
                "inputs_file_strategy": result.get("inputs_file_strategy"),
                "inputs_file_override": result.get("inputs_file_override"),
                "inputs_candidates": result.get("inputs_candidates", []),
            }
        }
        return {
            "mode": "retry",  # Allow Architect to fix validation issues
            "error": f"Validation failed: {errors[0] if errors else 'Unknown'}",
            "errors_active": errors,
            "ready_to_run": False,  # Don't attempt execution
            "workflow_history": workflow_history + [error_entry]
        }

    # ========================================
    # COMPONENT 10e: SUCCESS LOGGING & WORKFLOW HISTORY ENTRY
    # ========================================

    # Create history entry (per contract line 62-89)
    # Store full computation output in details (canonical path)
    try:
        from src.utils.metrics import metrics_collector

        metrics_summary = metrics_collector.summarize_stage("input_writer", iteration=state.get("iteration", 0))
    except Exception:
        metrics_summary = {}

    history_entry = {
        "node": "input_writer",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "inputs_generated",
        "iteration": state.get("iteration", 0),
        "details": {
            # Full computation output (canonical path - source of truth)
            "run_directory": result.get("run_dir"),
            "inputs_file_path": result.get("inputs_path"),
            "status": result.get("status", "success"),
            "modifications_applied": len(modifications),  # Count of mods applied
            "file_size_bytes": len(result.get("inputs_path", "")) or 0,
            "applied_modifications": modifications,  # Full list for audit
            # Resolution status (consistent with failure path)
            "requires_parameter_resolution": False,
            # Traceability
            "selected_case": selected_case,
            "baseline_code": baseline.get("code_name") if baseline else None,
            "inputs_file_selected": result.get("inputs_file_selected"),
            "inputs_file_strategy": result.get("inputs_file_strategy"),
            "inputs_file_override": result.get("inputs_file_override"),
            "inputs_candidates": result.get("inputs_candidates", []),
        }
    }
    if metrics_summary:
        history_entry["details"]["metrics"] = metrics_summary

    new_history = workflow_history + [history_entry]

    # ========================================
    # COMPONENT 10f: OUTPUT MAPPING (DUAL-PATH MODEL)
    # ========================================
    # CANONICAL PATH (PRIMARY): workflow_history[-1]['details'] has source of truth
    # PRAGMATIC PATH (OPTIONAL): top-level state has convenience copies
    #
    # Per contract line 24-42: Return only control flow + audit trail
    # Optional pragmatic copies for runner convenience

    updated_plan = None
    if state.get("plan"):
        updated_plan = dict(state["plan"])
        updated_plan["baseline_inputs_path"] = result.get("inputs_file_selected")
        updated_plan["inputs_file_strategy"] = result.get("inputs_file_strategy")
        updated_plan["inputs_file_override"] = result.get("inputs_file_override")
        updated_plan["inputs_candidates"] = result.get("inputs_candidates", [])

    updates = {
        # === UTILITY FLAGS (REQUIRED FOR CONTROL FLOW) ===
        "mode": "proceed",              # Control flow (Router will decide next step)
        "ready_to_run": True,           # Signal for Runner node
        "iteration": state.get("iteration", 0),
        "requires_parameter_resolution": False,  # Explicit success signal

        # === AUDIT TRAIL (REQUIRED) ===
        # workflow_history[-1]['details'] contains canonical computation output
        "workflow_history": new_history,

        # === PRAGMATIC CONVENIENCE COPIES (OPTIONAL) ===
        # For runner to find executable without searching workflow_history
        # Must match workflow_history[-1]['details']
        "run_directory": result.get("run_dir"),
        "inputs_file_path": result.get("inputs_path"),  # PRD schema name
        "inputs_file": result.get("inputs_path"),       # Legacy key for backward compatibility
        "used_inputs_file": result.get("inputs_file_selected"),
    }
    if updated_plan is not None:
        updates["plan"] = updated_plan

    logger.info(f"Input Writer complete: {Path(result['run_dir']).name}")
    logger.info(
        f"  Inputs selected: {result.get('inputs_file_selected')} "
        f"(strategy: {result.get('inputs_file_strategy')}, override: {result.get('inputs_file_override')})"
    )
    logger.debug(f"  Inputs written: {result.get('inputs_path')}")
    logger.debug(f"  Run directory: {result.get('run_dir')}")
    logger.info("-" * 80)
    logger.info("Input Writer node complete")
    logger.info("-" * 80)

    return updates
