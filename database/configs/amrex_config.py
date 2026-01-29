"""
AMReX core configuration.

Provides a minimal config wrapper for the AMReX repository so baseline overrides
can target AMReX test cases (e.g., Advection_AmrCore).
"""

from .base_amrex_config import BaseAMReXConfig


class AMReXConfig(BaseAMReXConfig):
    """Base AMReX configuration (no solver-specific metadata)."""

    code_name = "AMReX"
    github_org = "AMReX-Codes"
    github_repo = "amrex"
    default_baseline_dir = "Tests/Amr/Advection_AmrCore"
    default_inputs_path = "Tests/Amr/Advection_AmrCore/inputs"
    default_exec_repo_path = "Tests/Amr/Advection_AmrCore"
    default_exec_pattern = "*.ex"
    priority_cases = [
        "Tests/Amr/Advection_AmrCore",
    ]
