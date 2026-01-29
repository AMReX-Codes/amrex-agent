"""
WarpX-specific configuration.

Extends BaseAMReXConfig for particle-in-cell simulations.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
from pathlib import Path
from typing import Any

from .base_amrex_config import BaseAMReXConfig

logger = logging.getLogger(__name__)

class WarpXConfig(BaseAMReXConfig):
    """WarpX (particle-in-cell plasma simulation) configuration."""

    code_name = "WarpX"

    # === Registry Metadata ===
    github_org = "ECP-WarpX"
    github_repo = "WarpX"
    description = "Advanced electromagnetic particle-in-cell code"
    inputs_quality = "excellent"
    default_baseline_dir = "Examples/Physics_applications/laser_acceleration"
    default_inputs_path = "Examples/Physics_applications/laser_acceleration/inputs"
    default_exec_repo_path = "Examples/Physics_applications/laser_acceleration"
    default_exec_pattern = "WarpX*ex"

    selection_keywords = ["plasma", "laser", "accelerator"]
    selection_guidance = ["Laser/plasma -> WarpX"]
    github_search_paths = ["Examples/Physics_applications", "Examples/Tests"]


    # Override search patterns (WarpX uses Examples/ not Exec/)
    search_patterns = [
        '**/Examples/**',    # WarpX standard location
        '**/Benchmarks/**',  # Performance tests
        '**/Tests/**',       # Regression tests
    ]

    priority_cases = [
        "Examples/Physics_applications/laser_acceleration",
        "Examples/Physics_applications/plasma_acceleration",
        "Examples/Tests/gaussian_beam",
    ]

    faiss_indices = [
        'warpx_case_structure',
        'warpx_case_details',
    ]

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract WarpX-specific metadata.

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to WarpX case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX + WarpX-specific fields.
        """
        metadata = super().extract_metadata(case_path, repo_root=repo_root)

        metadata.update({
            'github_org': cls.github_org,
            'github_repo': cls.github_repo,
        })

        return metadata

    @classmethod
    def get_priority_cases(cls) -> list[str]:
        """
        Get priority case paths for WarpX.

        Call context: Used by example selection and baselines.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[str]
            Priority case relative paths.
        """
        return cls.priority_cases
