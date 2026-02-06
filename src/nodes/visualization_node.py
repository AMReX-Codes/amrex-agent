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
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import GraphState
from src.services.visualization import VisualizationService

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
    logger.debug("\n" + "="*80)
    logger.debug("VISUALIZATION NODE - Multi-Backend Plotfile Visualization")
    logger.debug("="*80)

    config = state["config"]
    iteration = state.get("iteration", 0)
    workflow_history = state.get("workflow_history", [])
    error_logs = state.get("error_logs", [])

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
    vis_config = _build_vis_config(
        plan=plan,
        analysis_report=analysis_report,
        plotfiles=plotfiles,
        viz_service=viz
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
    viz_service: VisualizationService
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
    # Start with plan config if provided
    vis_config = plan.get('visualization') or {'plots': []}
    if not isinstance(vis_config, dict):
        vis_config = {'plots': []}

    # Validate requested plots against available fields when possible
    if vis_config.get('plots'):
        try:
            fields = viz_service.backend.get_field_list(plotfiles[-1]) if plotfiles else []
        except Exception as exc:
            fields = []
            logger.debug(f"  [WARN] Field detection failed: {exc}")
        if fields:
            requested = vis_config.get('plots', [])
            filtered = [p for p in requested if p.get('field') in fields]
            if len(filtered) != len(requested):
                missing = [p.get('field') for p in requested if p.get('field') not in fields]
                logger.info(
                    "Requested visualization fields not available: %s; falling back to available fields.",
                    ", ".join([m for m in missing if m])
                )
                vis_config['plots'] = filtered

    # If no plots specified (or all were filtered out), build default set
    if not vis_config.get('plots'):
        vis_config['plots'] = []

        # Always plot Temp and density if available
        try:
            fields = viz_service.backend.get_field_list(plotfiles[-1])

            # Temperature
            if 'Temp' in fields or 'temperature' in fields:
                field_name = 'Temp' if 'Temp' in fields else 'temperature'
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': field_name,
                    'axis': 'z'
                })

            # Density
            if 'density' in fields:
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': 'density',
                    'axis': 'z'
                })

            # Velocity (if analysis detected high velocities)
            max_velocity = analysis_report.get('max_velocity', 0)
            if max_velocity > 1e5 and 'x_velocity' in fields:  # High velocity threshold
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': 'x_velocity',
                    'axis': 'z'
                })

            # Chemistry species (detect Y(...) fields)
            species = [f for f in fields if f.startswith('Y(') and f.endswith(')')]
            if species:
                # Plot first 3 species
                for sp in species[:3]:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': sp,
                        'axis': 'z'
                    })

            # If still no plots, fall back to density or components
            if not vis_config['plots']:
                if 'density' in fields:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': 'density',
                        'axis': 'z'
                    })
                elif len(fields) < 10:
                    for field in fields:
                        vis_config['plots'].append({
                            'type': 'slice',
                            'field': field,
                            'axis': 'z'
                        })
                elif fields:
                    vis_config['plots'].append({
                        'type': 'slice',
                        'field': fields[0],
                        'axis': 'z'
                    })

        except Exception as e:
            # Field detection failed - use minimal default
            logger.debug(f"  [WARN] Field detection failed: {e}")
            vis_config['plots'] = [
                {'type': 'slice', 'field': 'Temp', 'axis': 'z'},
                {'type': 'slice', 'field': 'density', 'axis': 'z'}
            ]

    return vis_config


# Export for LangGraph
__all__ = ['visualization_node']
