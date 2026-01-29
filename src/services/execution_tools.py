"""Execution validation and resource estimation helpers."""

import json
from typing import Any


def validate_executable_for_job(
    executable_path: str,
    nodes: int = 1,
    ntasks_per_node: int = 1,
    constraint: str = "",
) -> dict[str, Any]:
    """
    Validate executable meets job requirements.

    Call context: Used by execution planning to sanity-check runner inputs.

    Parameters
    ----------
    executable_path : str
        Path to the executable to validate.
    nodes : int, optional
        Number of nodes requested for the job.
    ntasks_per_node : int, optional
        MPI ranks per node.
    constraint : str, optional
        Scheduler constraint string (e.g., GPU partition).

    Returns
    -------
    dict
        Validation results, including warnings and derived executable traits.
    """
    from pathlib import Path

    exe_path = Path(executable_path)
    exe_name = exe_path.name if exe_path.exists() else executable_path

    has_mpi = ".MPI." in exe_name
    has_cuda = ".CUDA." in exe_name or ".HIP." in exe_name

    warnings = []
    valid = True

    total_ranks = nodes * ntasks_per_node

    if total_ranks > 1 and not has_mpi:
        warnings.append(
            f"\u26a0\ufe0f  Multi-rank job (nodes={nodes} \u00d7 ntasks_per_node={ntasks_per_node} = {total_ranks} ranks)"
        )
        warnings.append("   but executable is not MPI-enabled")
        warnings.append(f"   Executable: {exe_name}")
        warnings.append("   Need: *.MPI.* in filename")
        valid = False

    if "gpu" in constraint.lower() and not has_cuda:
        warnings.append(
            f"\u26a0\ufe0f  GPU job (constraint={constraint}) but executable is not GPU-enabled"
        )
        warnings.append(f"   Executable: {exe_name}")
        warnings.append("   Need: *.CUDA.* or *.HIP.* in filename")
        valid = False

    if has_mpi and has_cuda:
        exe_type = "MPI+CUDA"
    elif has_mpi:
        exe_type = "MPI"
    elif has_cuda:
        exe_type = "CUDA (single-rank)"
    else:
        exe_type = "serial"

    return {
        "valid": valid,
        "warnings": warnings,
        "executable_type": exe_type,
        "has_mpi": has_mpi,
        "has_cuda": has_cuda,
        "total_ranks": total_ranks,
    }


def estimate_resources(
    config_json: str,
    system: str = "perlmutter",
    selected_solver: str | None = None,
) -> str:
    """
    Estimate computational resources needed.

    Call context: Used by planning or UI to size a requested run.

    Parameters
    ----------
    config_json : str
        JSON-encoded simulation configuration.
    system : str, optional
        Target system name for resource estimation.
    selected_solver : str or None, optional
        Solver override to select the config class.

    Returns
    -------
    str
        JSON-encoded resource estimate.
    """
    config = json.loads(config_json)

    config_cls = _resolve_config_class(config, selected_solver=selected_solver)
    resources = config_cls.estimate_resources(config, system=system)
    return json.dumps(resources, indent=2)


def _resolve_config_class(config: dict[str, Any], selected_solver: str | None = None):
    from database.configs import BaseAMReXConfig, discover_code_configs

    registry = {c.code_name: c for c in discover_code_configs()}
    if selected_solver:
        return registry.get(selected_solver, BaseAMReXConfig)

    metadata = config.get("_metadata", {}) if isinstance(config, dict) else {}
    for key in ("selected_solver", "solver", "code", "code_name"):
        if key in metadata:
            return registry.get(metadata[key], BaseAMReXConfig)
        if key in config:
            return registry.get(config[key], BaseAMReXConfig)

    lower_registry = {name.lower(): name for name in registry}
    for section in config:
        name = lower_registry.get(str(section).lower())
        if name:
            return registry[name]

    return BaseAMReXConfig
