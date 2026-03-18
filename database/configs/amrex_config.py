"""
AMReX core configuration.

Provides a minimal config wrapper for the AMReX repository so baseline overrides
can target AMReX test cases (e.g., Advection_AmrCore).
"""

from .base_amrex_config import BaseAMReXConfig


class AMReXConfig(BaseAMReXConfig):
    """Base AMReX configuration (no solver-specific metadata)."""

    code_name = "AMReX"
    description = "AMReX framework reference and core AMR tutorials"
    selection_keywords = [
        "amrex",
        "amrex tutorial",
        "amrex amrcore",
        "advection tutorial",
        "amr advection",
        "passive scalar",
        "nested grid advection",
        "advection_amrcore",
    ]
    selection_guidance = ["Framework/core AMR tutorial workflows -> AMReX"]
    level0_physics_regimes = [
        {
            "family": "Framework Infrastructure",
            "description": "Core AMReX AMR and framework-level reference workflows",
            "aliases": ["framework", "core amr", "tutorial"],
        }
    ]
    level0_capabilities = [
        "amrex framework tutorials",
        "advection tutorial and nested grid advection examples",
        "amrcore reference advection tests",
        "AMR advection and passive scalar transport workflows",
    ]
    level0_lineage = {
        "description": "AMReX is the base framework supporting solver applications.",
    }
    level0_cross_cutting_guidance = [
        "Use AMReX for framework-centric AMR/tutorial requests without domain-specific physics requirements.",
    ]
    github_org = "AMReX-Codes"
    github_repo = "amrex"
    default_baseline_dir = "Tests/Amr/Advection_AmrCore"
    default_inputs_path = "Tests/Amr/Advection_AmrCore/inputs"
    default_exec_repo_path = "Tests/Amr/Advection_AmrCore"
    default_exec_pattern = "*.ex"
    priority_cases = [
        "Tests/Amr/Advection_AmrCore",
    ]

    @classmethod
    def get_plotfile_period_param(cls) -> str | None:
        return "amr.plot_per"

    @classmethod
    def get_plotfile_step_interval_param(cls) -> str | None:
        return "amr.plot_int"
