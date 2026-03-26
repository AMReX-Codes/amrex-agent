"""
ERF-specific configuration.

Extends BaseAMReXConfig for atmospheric simulations.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
from pathlib import Path
from typing import Any

from src.services.rules.base import RuleViolation

from .base_amrex_config import BaseAMReXConfig

logger = logging.getLogger(__name__)

class ERFConfig(BaseAMReXConfig):
    """ERF (Energy Research and Forecasting) configuration."""

    code_name = "ERF"

    # === Registry Metadata ===
    github_org = "erf-model"
    github_repo = "ERF"
    description = "Atmospheric modeling and weather simulation"
    inputs_quality = "good"
    default_baseline_dir = "Exec/RegTests/Bubble"
    default_inputs_path = "Exec/RegTests/Bubble/inputs"
    default_exec_repo_path = "Exec/RegTests/Bubble"
    default_exec_pattern = "ERF*ex"

    selection_keywords = [
        "atmospheric",
        "weather",
        "wind",
        "thermal bubble",
        "dry convection",
        "squall line",
        "squall-line",
        "moist convection",
        "atmospheric boundary",
        "density current",
        "cold air outflow",
        "stratified atmosphere",
    ]
    selection_guidance = ["Atmospheric/weather -> ERF"]
    level0_physics_regimes = [
        {
            "family": "Atmospheric Modeling",
            "description": "Atmospheric boundary layer, weather, and mesoscale dynamics",
            "aliases": ["atmospheric", "boundary layer", "weather", "wind"],
        }
    ]
    level0_capabilities = [
        "atmospheric boundary layer modeling",
        "atmospheric boundary and stratified atmosphere studies",
        "terrain-influenced weather dynamics",
        "thermal bubble and dry convection benchmarks",
        "buoyancy-driven and density-current flows",
        "density current and cold air outflow dynamics",
        "moist convection and squall-line simulations",
        "squall line and squall-line convection workflows",
        "hurricane and tropical-cyclone test workflows",
        "radiation and land-surface coupling tests",
        "wind-farm parameterization workflows",
        "data-assimilation and initialization from netcdf",
    ]
    level0_lineage = {
        "description": "ERF is an AMReX atmospheric and weather modeling solver.",
    }
    level0_cross_cutting_guidance = [
        "Use ERF for atmospheric, ABL, and weather-oriented simulations.",
    ]
    github_search_paths = ["Exec/RegTests", "Exec/ABL"]
    schema_pattern = "erf_complete_*.json"

    priority_cases = [
        "Exec/MoistRegTests/SquallLine_2D",
        "Exec/RegTests/Bubble",
        "Exec/RegTests/DensityCurrent",
        "Exec/ABL",
    ]

    faiss_indices = [
        'erf_case_structure',
        'erf_case_details',
    ]

    documentation_map = {
        'solver_readme': ['README.md', 'README.rst'],
    }

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract ERF-specific metadata.

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to ERF case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX + ERF-specific fields.
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
        Get priority case paths for ERF.

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

    @classmethod
    def validate_physics(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Run ERF-specific physics checks.

        Call context: Used by config validation to enforce solver rules.

        Parameters
        ----------
        cls : type
            Config class.
        config_dict : dict[str, Any]
            Parsed configuration dictionary.

        Returns
        -------
        list[RuleViolation]
            Validation rule violations.
        """
        violations: list[RuleViolation] = []

        def check_temperature(value: Any, parameter: str) -> None:
            """
            Validate that a temperature value is non-negative.

            Parameters
            ----------
            value : Any
                Temperature value to validate.
            parameter : str
                Parameter name for reporting violations.

            Returns
            -------
            None
                This helper only records violations.
            """
            try:
                temperature = float(value)
            except (TypeError, ValueError):
                return
            if temperature < 0.0:
                violations.append(
                    RuleViolation(
                        rule_name="TemperatureRange",
                        severity="error",
                        parameter=parameter,
                        message=f"Temperature {temperature} K must be non-negative",
                    )
                )

        data = config_dict.get("erf", {})
        if isinstance(data, dict):
            for key in ["most.surf_temp", "if_init_surf_temp"]:
                if key in data:
                    check_temperature(data[key], f"erf.{key}")

        prob = config_dict.get("prob", {})
        if isinstance(prob, dict):
            for key in ["T_0", "T_inf", "T_tr", "T_0_Pert_Mag"]:
                if key in prob:
                    check_temperature(prob[key], f"prob.{key}")

        return violations
