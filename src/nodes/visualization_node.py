"""
Visualization node - AMReX plotfile visualization with multi-backend support.

Purpose: Generate visualizations from simulation plotfiles
Backend: Multi-backend (Phase 5 - AMReX tools → yt fallback)

Workflow integration: After analysis node (if simulation succeeded)

Phase 5 enhancements:
- Backend selection logging
- Enhanced error handling
- Visualization status tracking
- Container mode support
- Analysis-driven customization
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.services.visualization import VisualizationService
from src.utils.gate import run_preconfirm_gate

logger = logging.getLogger(__name__)


def get_run_directory_and_analysis(state: GraphState) -> tuple:
    """
    Resolve run directory and analysis report from state or history.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing workflow history and analysis data.

    Returns
    -------
    tuple
        Tuple of (run_directory, analysis_report).
    """
    # Try canonical path for run_directory
    run_dir = None
    try:
        input_writer_entry = next(
            e for e in state.get('workflow_history', [])
            if e.get('node') == 'input_writer'
        )
        run_dir = input_writer_entry.get('details', {}).get('run_directory')
    except StopIteration:
        pass

    # Fallback to state
    if not run_dir:
        run_dir = state.get("run_directory")

    # Get analysis report (can be in state or as fallback from workflow_history)
    analysis_report = state.get("analysis_report", {})

    return run_dir, analysis_report


def visualization_node(state: GraphState) -> dict[str, Any]:
    """
    Generate visualization artifacts from simulation plotfiles.

    Call context: LangGraph node entry point.

    Parameters
    ----------
    state : GraphState
        Current workflow state containing run directory and analysis data.

    Returns
    -------
    dict
        State updates with visualization metadata and artifacts.
    """
    logger.info("=" * 80)
    logger.info("Starting Visualization node")
    logger.info("=" * 80)

    config = state["config"]
    iteration = state.get("iteration", 0)
    workflow_history = state.get("workflow_history", [])
    error_logs = state.get("error_logs", [])

    run_dir, analysis_report = get_run_directory_and_analysis(state)
    analysis_status = analysis_report.get("status", "unknown") if isinstance(analysis_report, dict) else "unknown"
    plan = state.get("plan", {}) or {}
    selected_case = plan.get("selected_case", "unknown")

    auto_approve = getattr(config, "preconfirm_gate_auto_approve", False) is True
    gate_result = run_preconfirm_gate(
        node_name="visualization",
        summary_lines=[
            "This step generates plots or images from simulation output.",
            f"Selected case: {selected_case}",
            f"Run directory: {run_dir or 'unknown'}",
            f"Analysis status: {analysis_status}",
        ],
        options=[{"label": "Proceed with visualization", "value": "proceed"}],
        enabled=getattr(config, "preconfirm_gate", False) is True,
        allow_cancel=True,
        auto_approve=auto_approve,
    )
    gate_entry = gate_result.get("history_entry")
    if gate_entry:
        gate_entry["iteration"] = iteration
        workflow_history = workflow_history + [gate_entry]
    if gate_result["action"] == "cancel":
        return {
            "mode": "terminal",
            "job_status": "skipped",
            "visualization_status": "skipped",
            "workflow_history": workflow_history,
        }

    # Get run_directory and analysis_report from canonical/pragmatic paths
    run_dir, analysis_report = get_run_directory_and_analysis(state)
    plan = state.get("plan", {})

    # Initialize default visualization values (will be populated if successful)
    viz_status = "pending"
    viz_backend = "none"
    viz_images = []
    viz_metadata = {}

    # Validation: Check run_dir exists
    if not run_dir:
        logger.warning("[WARN] No run directory provided (skipping visualization)")
        viz_status = "skipped"
        viz_metadata = {"reason": "no_run_directory"}

        history_entry = {
            "node": "visualization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "skipped",
            "iteration": iteration,
            "details": {"status": "skipped", "reason": "no_run_directory"}
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "visualization_status": viz_status,
            "visualization_backend": viz_backend,
            "visualization_images": viz_images,
            "visualization_metadata": viz_metadata,
            "error_logs": error_logs
        }

    run_dir_path = Path(run_dir)
    if not run_dir_path.exists():
        logger.warning(f"[WARN] Run directory does not exist: {run_dir}")
        viz_status = "skipped"
        viz_metadata = {"reason": "run_dir_missing"}

        history_entry = {
            "node": "visualization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "skipped",
            "iteration": iteration,
            "details": {"status": "skipped", "reason": "run_dir_missing"}
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "visualization_status": viz_status,
            "visualization_backend": viz_backend,
            "visualization_images": viz_images,
            "visualization_metadata": viz_metadata,
            "error_logs": error_logs
        }

    # Validation: Check if simulation succeeded
    if analysis_report.get('status') == 'failed':
        logger.info("Simulation failed - skipping visualization")
        viz_status = "skipped"
        viz_metadata = {"reason": "simulation_failed"}

        history_entry = {
            "node": "visualization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "skipped",
            "iteration": iteration,
            "details": {"status": "skipped", "reason": "simulation_failed"}
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "visualization_status": viz_status,
            "visualization_backend": viz_backend,
            "visualization_images": viz_images,
            "visualization_metadata": viz_metadata,
            "error_logs": error_logs
        }

    # Pre-check: Verify plotfiles exist
    logger.debug("\n[Step 1/4] Checking for plotfiles...")
    plotfiles = sorted(run_dir_path.glob('plt*'))
    plotfiles = [p for p in plotfiles if p.is_dir()]

    if not plotfiles:
        logger.warning("[WARN] No plotfiles found in run directory")
        logger.debug(f"  Searched: {run_dir}")
        viz_status = "skipped"
        viz_metadata = {
            "plotfile_count": 0,
            "skip_reason": "no_plotfiles"
        }

        history_entry = {
            "node": "visualization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "skipped",
            "iteration": iteration,
            "details": {"status": "skipped", "reason": "no_plotfiles", "plotfile_count": 0}
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "visualization_status": viz_status,
            "visualization_backend": viz_backend,
            "visualization_images": viz_images,
            "visualization_metadata": viz_metadata,
            "error_logs": error_logs
        }

    logger.debug(f"  Found {len(plotfiles)} plotfile(s)")
    logger.debug(f"  Latest: {plotfiles[-1].name}")

    # Initialize visualization service
    logger.debug("\n[Step 2/4] Initializing visualization service...")
    backend_name = "none"
    viz = None

    try:
        viz = VisualizationService(config)
        backend_name = viz.backend.__class__.__name__
        logger.debug(f"  Selected backend: {backend_name}")
        viz_backend = backend_name

    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize visualization service: {e}")
        viz_status = "failed"
        viz_metadata = {"reason": "init_error", "error": str(e)[:200]}
        error_logs = error_logs + [f"Visualization init error: {str(e)}"]

        history_entry = {
            "node": "visualization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "failed",
            "iteration": iteration,
            "details": {"status": "failed", "reason": "init_error", "error": str(e)[:200]}
        }
        new_history = workflow_history + [history_entry]

        return {
            "mode": "proceed",
            "iteration": iteration,
            "workflow_history": new_history,
            "visualization_status": viz_status,
            "visualization_backend": viz_backend,
            "visualization_images": viz_images,
            "visualization_metadata": viz_metadata,
            "error_logs": error_logs
        }

    # Build visualization config
    logger.debug("\n[Step 3/4] Building visualization configuration...")
    solver_name = (
        state.get("selected_solver")
        or plan.get("selected_solver")
        or (plan.get("baseline") or {}).get("code_name")
        or ""
    )
    inputs_file_path = (
        state.get("inputs_file_path")
        or state.get("inputs_file")
        or plan.get("inputs_file_path")
        or plan.get("baseline_inputs_path")
    )
    vis_config = _build_vis_config(
        plan=plan,
        analysis_report=analysis_report,
        plotfiles=plotfiles,
        viz_service=viz,
        prompt=state.get("prompt", ""),
        solver_name=solver_name,
        inputs_file_path=inputs_file_path,
        requested_plot_vars=state.get("requested_plot_vars", []) or [],
    )

    logger.debug(f"  Will generate {len(vis_config.get('plots', []))} plot(s):")
    for plot_cfg in vis_config.get('plots', []):
        logger.debug(f"    - {plot_cfg['field']} ({plot_cfg['type']} along {plot_cfg['axis']})")

    # Check container mode
    container_mode = getattr(config, 'container_mode', False)
    if container_mode:
        logger.debug("  Container mode: ENABLED (two-stage extraction)")
    else:
        logger.debug("  Container mode: DISABLED (direct rendering)")

    # Generate visualizations
    logger.debug("\n[Step 4/4] Generating visualizations...")
    try:
        images = viz.create_standard_plots(
            run_dir=run_dir_path,
            vis_config=vis_config
        )

        # Success - set local variables
        if not images:
            viz_status = "skipped"
        else:
            viz_status = "success"
        viz_backend = backend_name
        viz_images = [str(img) for img in images]
        viz_metadata = {
            "plotfile_count": len(plotfiles),
            "latest_plotfile": plotfiles[-1].name,
            "fields_plotted": [p['field'] for p in vis_config.get('plots', [])],
            "backend_used": backend_name,
            "image_count": len(images),
            "reason": "no_images" if not images else "ok",
            "container_mode": container_mode
        }

        logger.debug(f"\n[PASS] Generated {len(images)} visualization(s)")
        for img in images[:5]:
            logger.debug(f"   - {Path(img).name}")
        if len(images) > 5:
            logger.debug(f"   ... and {len(images) - 5} more")

    except FileNotFoundError as e:
        logger.debug(f"\n[WARN] Plotfile access error: {e}")
        viz_status = "failed"
        viz_metadata = {
            "plotfile_count": len(plotfiles),
            "error": "plotfile_not_found",
            "error_detail": str(e)[:200]
        }
        error_logs = error_logs + [f"Visualization error: {str(e)}"]

    except Exception as e:
        logger.debug(f"\n[ERROR] Visualization failed: {e}")
        import traceback
        traceback.print_exc()

        viz_status = "failed"
        viz_metadata = {
            "plotfile_count": len(plotfiles),
            "error": "generation_failed",
            "error_detail": str(e)[:200]
        }
        error_logs = error_logs + [f"Visualization error: {str(e)}"]

    # ========================================
    # WORKFLOW HISTORY ENTRY (CANONICAL PATH)
    # ========================================

    history_entry = {
        "node": "visualization",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "success" if viz_status == "success" else "failed" if viz_status == "failed" else "skipped",
        "iteration": iteration,
        "details": {
            "status": viz_status,
            "backend": viz_backend,
            "image_count": len(viz_images),
            "metadata": viz_metadata,
            "container_mode": container_mode
        }
    }

    new_history = workflow_history + [history_entry]

    # ========================================
    # RETURN STATE UPDATES (LangGraph PATTERN)
    # ========================================

    logger.info(f"Visualization complete: {viz_status}")
    logger.info("-" * 80)
    logger.info("Visualization node complete")
    logger.info("-" * 80)
    return {
        "mode": "proceed",
        "iteration": iteration,
        "workflow_history": new_history,
        "visualization_status": viz_status,
        "visualization_backend": viz_backend,
        "visualization_images": viz_images,
        "visualization_metadata": viz_metadata,
        "error_logs": error_logs
    }


def _build_vis_config(
    plan: dict[str, Any],
    analysis_report: dict[str, Any],
    plotfiles: list[Path],
    viz_service: VisualizationService,
    prompt: str = "",
    solver_name: str = "",
    inputs_file_path: str | None = None,
    requested_plot_vars: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build visualization configuration from plan and analysis signals.

    Parameters
    ----------
    plan : dict
        Plan data from the architect node.
    analysis_report : dict
        Analysis report from the analysis node.
    plotfiles : list[pathlib.Path]
        Plotfile paths to inspect for available fields.
    viz_service : VisualizationService
        Visualization service used to query available fields.

    Returns
    -------
    dict
        Visualization configuration with a ``plots`` list.
    """
    preferred_axis = _infer_preferred_slice_axis(
        prompt=prompt,
        solver_name=solver_name,
        n_cell=_parse_inputs_n_cell(inputs_file_path),
    )

    # Start with plan config if provided
    vis_config = plan.get('visualization') or {'plots': []}
    if not isinstance(vis_config, dict):
        vis_config = {'plots': []}
    if not isinstance(vis_config.get("plots"), list):
        vis_config["plots"] = []

    # Normalize plan-provided entries so defaults are deterministic.
    plan_plots: list[dict[str, Any]] = []
    for plot_cfg in vis_config.get("plots", []):
        if not isinstance(plot_cfg, dict):
            continue
        if plot_cfg.get("type", "slice") != "slice":
            continue
        field = plot_cfg.get("field")
        if not field:
            continue
        axis = plot_cfg.get("axis") or preferred_axis
        plan_plots.append({
            "type": "slice",
            "field": field,
            "axis": axis,
            **({k: v for k, v in plot_cfg.items() if k not in {"type", "field", "axis"}}),
        })

    fields: list[str] = []
    try:
        fields = viz_service.backend.get_field_list(plotfiles[-1]) if plotfiles else []
    except Exception as exc:
        logger.debug(f"  [WARN] Field detection failed: {exc}")

    requested = list(requested_plot_vars or [])
    requested_fields = _resolve_requested_fields(requested, fields) if fields else []

    merged_plots: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def _add_plot(plot_cfg: dict[str, Any]) -> None:
        field = str(plot_cfg.get("field", "")).strip()
        ptype = str(plot_cfg.get("type", "slice")).strip() or "slice"
        axis = str(plot_cfg.get("axis", preferred_axis)).strip() or preferred_axis
        if not field or ptype != "slice":
            return
        key = (ptype, field, axis)
        if key in seen_keys:
            return
        seen_keys.add(key)
        merged_plots.append({"type": ptype, "field": field, "axis": axis})

    # 1) Requested plot vars are primary source of truth.
    for field in requested_fields:
        _add_plot({"type": "slice", "field": field, "axis": preferred_axis})

    if requested and not fields:
        # If we cannot inspect fields, still honor requested vars as plot intents.
        for token in requested:
            _add_plot({"type": "slice", "field": token, "axis": preferred_axis})

    # 2) Plan plots are optional add-ons (never replace requested).
    if plan_plots:
        missing_plan_fields: list[str] = []
        for plot_cfg in plan_plots:
            field = str(plot_cfg.get("field", ""))
            if fields and field not in fields:
                missing_plan_fields.append(field)
                continue
            _add_plot(plot_cfg)
        if missing_plan_fields:
            logger.info(
                "Requested visualization fields not available: %s; keeping requested plot vars and skipping unavailable plan fields.",
                ", ".join([m for m in missing_plan_fields if m]),
            )

    if merged_plots:
        vis_config["plots"] = merged_plots
        return vis_config

    # If still empty, build defaults.
    if not vis_config.get("plots"):
        vis_config["plots"] = []

        try:
            if not fields:
                fields = viz_service.backend.get_field_list(plotfiles[-1])

            # Always plot Temp and density if available
            # Temperature
            if 'Temp' in fields or 'temperature' in fields:
                field_name = 'Temp' if 'Temp' in fields else 'temperature'
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': field_name,
                    'axis': preferred_axis
                })

            # Density
            if 'density' in fields:
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': 'density',
                    'axis': preferred_axis
                })

            # Velocity (if analysis detected high velocities)
            max_velocity = analysis_report.get('max_velocity', 0)
            if max_velocity > 1e5 and 'x_velocity' in fields:  # High velocity threshold
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': 'x_velocity',
                    'axis': preferred_axis
                })

            # Chemistry species (detect Y(...) fields)
            species = [f for f in fields if f.startswith('Y(') and f.endswith(')')]
            if species:
                # Plot first 3 species
                for sp in species[:3]:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': sp,
                        'axis': preferred_axis
                    })

            # If still no plots, fall back to density or components
            if not vis_config['plots']:
                if 'density' in fields:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': 'density',
                        'axis': preferred_axis
                    })
                elif len(fields) < 10:
                    for field in fields:
                        vis_config['plots'].append({
                            'type': 'slice',
                            'field': field,
                            'axis': preferred_axis
                        })
                elif fields:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': fields[0],
                        'axis': preferred_axis
                    })

        except Exception as e:
            # Field detection failed - use minimal default
            logger.debug(f"  [WARN] Field detection failed: {e}")
            vis_config['plots'] = [
                {'type': 'slice', 'field': 'Temp', 'axis': preferred_axis},
                {'type': 'slice', 'field': 'density', 'axis': preferred_axis}
            ]

    return vis_config


def _resolve_requested_fields(requested: list[str], available_fields: list[str]) -> list[str]:
    """
    Map semantic requested plot vars to available plotfile field names.
    """
    if not requested or not available_fields:
        return []

    available_lower = {f.lower(): f for f in available_fields}

    semantic_candidates: dict[str, list[str]] = {
        "temperature": ["temp", "temperature"],
        "velocity": ["magvel", "mag_vel", "x_velocity"],
        "vertical_velocity": ["z_velocity", "w_velocity", "w"],
        "pressure": ["pressure", "pres"],
        "density": ["density", "rho"],
        "vorticity": ["vorticity", "magvort", "mag_vort", "vorticity_z", "VortZ"],
        "cloud_water": ["qc", "cloud water", "cloud_water", "liquid water"],
    }

    resolved: list[str] = []
    for token in requested:
        token_lower = str(token).strip().lower()
        candidates = semantic_candidates.get(token_lower, [token_lower])
        selected = None
        for candidate in candidates:
            key = candidate.lower()
            if key in available_lower:
                selected = available_lower[key]
                break
        if selected and selected not in resolved:
            resolved.append(selected)
    return resolved


def _parse_inputs_n_cell(inputs_file_path: str | None) -> list[int] | None:
    """
    Parse amr.n_cell from an inputs file, if available.
    """
    if not inputs_file_path:
        return None
    path = Path(inputs_file_path)
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    pattern = re.compile(r"^\s*amr\.n_cell\s*=\s*(.*?)\s*$")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        values = [token for token in match.group(1).split() if token]
        parsed: list[int] = []
        for token in values:
            try:
                parsed.append(int(float(token)))
            except ValueError:
                return None
        return parsed or None

    return None


def _infer_preferred_slice_axis(
    prompt: str,
    solver_name: str,
    n_cell: list[int] | None,
) -> str:
    """
    Choose a deterministic default slice normal axis.

    Rules:
    1. ERF/REMORA default to 'y' so z stays vertical on x-z plots.
    2. Honor explicit prompt cues (x-z => y, y-z => x, x-y => z).
    3. If grid suggests a collapsed dimension (n_cell == 1), use it.
    4. Otherwise choose shortest-axis normal for 3D grids.
    5. Fallback to z.
    """
    text = (prompt or "").lower()
    solver = (solver_name or "").strip().upper()

    if "x-z" in text or "xz " in text or " xz" in text or "vertical slice" in text:
        return "y"
    if "y-z" in text or "yz " in text or " yz" in text:
        return "x"
    if "x-y" in text or "xy " in text or " xy" in text or "plan view" in text:
        return "z"

    if n_cell and len(n_cell) >= 3:
        axis_labels = ["x", "y", "z"]
        for idx, val in enumerate(n_cell[:3]):
            if val == 1:
                return axis_labels[idx]

    config_default = _get_config_default_slice_axis(solver)
    if config_default in {"x", "y", "z"}:
        return config_default

    if n_cell and len(n_cell) >= 3:
        axis_labels = ["x", "y", "z"]
        min_idx = min(range(3), key=lambda i: n_cell[i])
        return axis_labels[min_idx]

    return "z"


def _get_config_default_slice_axis(solver_name: str) -> str | None:
    if not solver_name:
        return None
    try:
        from database.configs.registry import get_config_class

        config_cls = get_config_class(solver_name)
        getter = getattr(config_cls, "get_default_slice_axis", None)
        if getter is None:
            return None
        axis = getter()
        if isinstance(axis, str):
            axis = axis.strip().lower()
            return axis or None
    except Exception:
        return None
    return None


# Export for LangGraph
__all__ = ['visualization_node']
