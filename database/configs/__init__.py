"""
Configuration modules for different AMReX codes.

Pattern inspired by yt-project's AMReX frontend:
- BaseAMReXConfig: Common AMReX parameters (geometry, AMR, grid, time stepping)
- Code-specific configs: Domain knowledge (PeleC combustion, ERF physics, etc.)

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from .amrex_config import AMReXConfig
from .base_amrex_config import BaseAMReXConfig
from .erf_config import ERFConfig
from .incflo_config import IncfloConfig
from .pelec_config import PeleCConfig
from .pelelmex_config import PeleLMeXConfig
from .remora_config import REMORAConfig
from .warpx_config import WarpXConfig
from typing import Type

MAX_NEW_INTEGRATION_LOC = 300
LEGACY_LOC_BUDGET_EXEMPT_CODES = {
    "AMReX",
    "PeleC",
    "PeleLMeX",
    "Incflo",
    "WarpX",
    "ERF",
    "REMORA",
}

__all__ = [
    'get_config_for_path',
    'validate_new_code_integration',
    "BaseAMReXConfig",
    "AMReXConfig",
    "PeleCConfig",
    "PeleLMeXConfig",
    "IncfloConfig",
    "WarpXConfig",
    "ERFConfig",
    "REMORAConfig",
]


def _count_non_comment_loc(source_path: Path) -> int:
    """Count logical LOC (non-empty, non-comment) for compliance checks."""
    loc = 0
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                loc += 1
    return loc


def validate_new_code_integration(
    config_cls: Type[BaseAMReXConfig],
    loc_limit: int = MAX_NEW_INTEGRATION_LOC,
) -> None:
    """
    Enforce F5.3 guardrails for newly integrated solver configs.

    Existing legacy solver configs are exempt from LOC cap enforcement.
    """
    code_name = getattr(config_cls, "code_name", "")
    if not isinstance(code_name, str) or not code_name.strip():
        raise ValueError("Solver config must define a non-empty code_name")
    if code_name in LEGACY_LOC_BUDGET_EXEMPT_CODES:
        return

    source_file = inspect.getsourcefile(config_cls)
    if not source_file:
        raise ValueError(f"Unable to resolve source file for solver config {code_name}")

    source_path = Path(source_file)
    loc_count = _count_non_comment_loc(source_path)
    if loc_count >= loc_limit:
        raise ValueError(
            f"New solver config {code_name} exceeds LOC budget: "
            f"{loc_count} lines (limit is < {loc_limit})"
        )


def discover_code_configs() -> list[Type[BaseAMReXConfig]]:
    """
    Auto-discover all registered code configurations.

    Returns
    -------
    list[type]
        Code configuration classes.

    Examples
    --------
    >>> configs = discover_code_configs()
    >>> for config in configs:
    ...     print(config.code_name, config.get_faiss_indices())
    """
    configs = [
        AMReXConfig,
        PeleCConfig,
        PeleLMeXConfig,
        IncfloConfig,  # Non-combustion test case (validates architecture flexibility)
        WarpXConfig,
        ERFConfig,
        REMORAConfig,
    ]
    for config in configs:
        validate_new_code_integration(config)
    return configs


def get_config_for_path(path_text: str) -> Type[BaseAMReXConfig]:
    """
    Detect config class from path string.

    Parameters
    ----------
    path_text : str
        Path text to inspect for solver identifiers.

    Returns
    -------
    type
        Matching config class (falls back to BaseAMReXConfig).
    """
    path_lower = path_text.lower()
    if 'pelec' in path_lower:
        return PeleCConfig
    elif 'pelelmex' in path_lower or 'pelelm' in path_lower:
        return PeleLMeXConfig
    elif 'erf' in path_lower:
        return ERFConfig
    elif 'remora' in path_lower:
        return REMORAConfig
    elif 'amrex' in path_lower:
        return AMReXConfig
    elif 'incflo' in path_lower:
        return IncfloConfig
    elif 'warpx' in path_lower:
        return WarpXConfig
    return BaseAMReXConfig  # Conservative fallback
