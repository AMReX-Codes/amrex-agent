"""
Baseline Loader - Shared utility for loading and merging baseline configurations.

Used by:
- Reviewer: To validate plan before execution
- Input Writer: To generate final inputs

This ensures both services see the same merged configuration.
"""

import copy
import logging
from pathlib import Path

from amrex_tools import parse_pele_inputs

logger = logging.getLogger(__name__)

def load_and_merge_baseline(
    baseline: dict,
    modifications: list[dict],
    prefer_2d: bool | None = None
) -> dict:
    """
    Load baseline inputs from case directory and apply modifications.

    Call context: Shared utility for Input Writer and Reviewer services.

    Parameters
    ----------
    baseline : dict
        Baseline metadata with 'path', 'code', and 'name'.
    modifications : list of dict
        List of parameter modifications.
    prefer_2d : bool or None, optional
        If True, prefer 2D inputs files. If None, auto-detect.

    Returns
    -------
    dict
        Merged configuration dict with all sections.
    """
    # Step 1: Load baseline inputs from path
    repo_path = baseline.get('repo_path')
    case_path = baseline.get('path')

    if repo_path and case_path:
        baseline_path = Path(repo_path) / case_path

    if not baseline_path:
        logger.warning("[WARN] No baseline path provided in baseline dict")
        return {}

    case_dir = Path(baseline_path)

    if not case_dir.exists():
        logger.warning(f"[WARN] Baseline path does not exist: {case_dir}")
        return {}

    # Step 2: Find inputs file(s) in case directory
    # Use config-based patterns
    from database.configs import get_config_for_path
    config_cls = get_config_for_path(str(case_dir))
    inputs_files = config_cls.find_inputs_files(case_dir)

    if not inputs_files:
        logger.warning(f"[WARN] No inputs file found in {case_dir}")
        return {}

    # Step 3: Choose best inputs file
    inputs_file = _select_inputs_file(inputs_files, prefer_2d)

    # Step 4: Parse baseline inputs
    try:
        baseline_config = parse_pele_inputs(str(inputs_file))
    except Exception as e:
        logger.warning(f"[WARN] Could not parse baseline inputs {inputs_file.name}: {e}")
        return {}

    # Step 5: Extract sections (remove metadata)
    config = {}
    for section, params in baseline_config.items():
        if section != '_metadata' and isinstance(params, dict):
            config[section] = copy.deepcopy(params)

    # Step 6: Apply modifications
    for mod in modifications:
        parameter = mod.get('parameter')
        new_value = mod.get('new_value') or mod.get('value')

        if not parameter or new_value is None:
            continue

        # Parse parameter: "geometry.prob_lo" → section="geometry", param="prob_lo"
        if '.' in parameter:
            section, param_name = parameter.split('.', 1)
        else:
            # No section prefix - use solver from baseline
            solver_code = baseline.get('code') or baseline.get('code_name')
            if not solver_code:
                raise ValueError("Baseline missing 'code' field for parameter overrides")
            solver_code = solver_code.lower()
            section = solver_code
            param_name = parameter

        # Apply modification
        if section not in config:
            config[section] = {}

        config[section][param_name] = new_value

    return config


def _select_inputs_file(inputs_files: list[Path], prefer_2d: bool | None = None) -> Path:
    """
    Select best inputs file from available options.

    Args:
        inputs_files: List of inputs file paths
        prefer_2d: If True, prefer 2D files. If False, prefer 3D. If None, auto.

    Returns
    -------
        Selected inputs file path
    """
    if len(inputs_files) == 1:
        return inputs_files[0]

    # Sort for consistency
    inputs_files = sorted(inputs_files)

    # If preference specified, try to honor it
    if prefer_2d is not None:
        target = '2d' if prefer_2d else '3d'

        for f in inputs_files:
            if target in f.name.lower():
                return f

    # Default: prefer 2D over 3D (2D is usually simpler/faster)
    for f in inputs_files:
        if '2d' in f.name.lower():
            return f

    # Fallback: first file
    return inputs_files[0]


def get_baseline_info(baseline: dict) -> dict:
    """
    Get information about baseline without fully parsing.

    Call context: Used by reviewer or UI to inspect baseline availability.

    Parameters
    ----------
    baseline : dict
        Baseline metadata.

    Returns
    -------
    dict
        Info dict with available_inputs, selected_input, etc.
    """
    baseline_path = baseline.get('path')

    if not baseline_path:
        return {'error': 'No baseline path'}

    case_dir = Path(baseline_path)

    if not case_dir.exists():
        return {'error': f'Path does not exist: {case_dir}'}

    # Find inputs files using config patterns
    from database.configs import get_config_for_path
    config_cls = get_config_for_path(str(case_dir))
    inputs_files = config_cls.find_inputs_files(case_dir)

    return {
        'case_dir': str(case_dir),
        'available_inputs': [f.name for f in inputs_files],
        'count': len(inputs_files)
    }


# Export
__all__ = [
    'load_and_merge_baseline',
    'get_baseline_info'
]
