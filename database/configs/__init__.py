"""
Configuration modules for different AMReX codes.

Pattern inspired by yt-project's AMReX frontend:
- BaseAMReXConfig: Common AMReX parameters (geometry, AMR, grid, time stepping)
- Code-specific configs: Domain knowledge (PeleC combustion, ERF physics, etc.)

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

from .amrex_config import AMReXConfig
from .base_amrex_config import BaseAMReXConfig
from .erf_config import ERFConfig
from .incflo_config import IncfloConfig
from .pelec_config import PeleCConfig
from .pelelmex_config import PeleLMeXConfig
from .remora_config import REMORAConfig
from .warpx_config import WarpXConfig
from typing import Type

__all__ = [
    'get_config_for_path',
    "BaseAMReXConfig",
    "AMReXConfig",
    "PeleCConfig",
    "PeleLMeXConfig",
    "IncfloConfig",
    "WarpXConfig",
    "ERFConfig",
    "REMORAConfig",
]


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
    return [
        AMReXConfig,
        PeleCConfig,
        PeleLMeXConfig,
        IncfloConfig,  # Non-combustion test case (validates architecture flexibility)
        WarpXConfig,
        ERFConfig,
        REMORAConfig,
    ]


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
