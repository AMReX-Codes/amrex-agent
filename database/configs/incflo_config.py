"""
incflo-specific configuration.

Extends BaseAMReXConfig for incompressible flow simulations.

Key differences from combustion codes (PeleC/PeleLMeX):
- NO chemistry mechanisms or fuels
- NO combustion physics parameters
- Focus on fluid dynamics (viscosity, density, Godunov methods)

Pattern: Tests architecture flexibility for non-combustion AMReX codes.
Similar to yt's BoxlibDataset pattern - extends base without domain-specific extras.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
from pathlib import Path
from typing import Any

from .base_amrex_config import BaseAMReXConfig

logger = logging.getLogger(__name__)

class IncfloConfig(BaseAMReXConfig):
    """
    incflo (incompressible flow) configuration.

    Domain: Incompressible Navier-Stokes
    Physics: Fluid dynamics, turbulence, NO reactions
    Differentiators: Simpler than combustion codes, tests architecture flexibility

    This config validates that the agent architecture works for non-combustion
    physics domains, proving it's not combustion-specific.
    """

    code_name = "incflo"

    # === Registry Metadata ===
    github_org = "AMReX-Codes"
    github_repo = "incflo"
    description = "Incompressible flow solver"
    inputs_quality = "good"
    default_baseline_dir = "benchmark_Godunov"
    default_inputs_path = "benchmark_Godunov/inputs"
    default_exec_repo_path = "benchmark_Godunov"
    default_exec_pattern = "incflo*ex"

    selection_keywords = ["incompressible", "flow"]
    selection_guidance = ["Incompressible flow -> incflo"]
    level0_physics_regimes = [
        {
            "family": "Low Mach Flow",
            "description": "Incompressible and weakly compressible fluid flow",
            "aliases": ["incompressible", "navier-stokes", "low speed flow"],
        }
    ]
    level0_capabilities = [
        "incompressible navier-stokes solver",
        "godunov-based fluid dynamics",
        "benchmark turbulent and channel-flow configurations",
    ]
    level0_lineage = {
        "description": "incflo is an AMReX incompressible flow application.",
    }
    level0_cross_cutting_guidance = [
        "Use incflo for non-reacting incompressible flow and canonical CFD benchmarks.",
    ]



    faiss_indices = [
        'incflo_case_structure',
        'incflo_case_details',
        'incflo_input_templates',
        # NO chemistry index (incflo has no reactions)
    ]

    # Priority cases for incflo (classic fluid dynamics benchmarks)
    priority_cases = [
        "benchmark_Godunov",
        "double_shear_layer",
        "lid_driven_cavity",
        "taylor_green_vortex",
        "channel_flow",
        "vortex_patch",
    ]

    # Incompressible flow specific parameters (no chemistry!)
    INCFLO_PARAMS = [
        'incflo.physics',           # Physics type (MultiPhase, Godunov, etc.)
        'incflo.viscosity',         # Fluid viscosity
        'incflo.density',           # Fluid density
        'incflo.advection_type',    # Advection scheme
        'incflo.use_godunov',       # Godunov method
        'incflo.godunov_type',      # Godunov variant
        'incflo.diffusion_type',    # Diffusion scheme
        'incflo.velocity',          # Velocity BCs
    ]

    @classmethod
    def get_domain_data(cls) -> dict[str, Any]:
        """
        Get incflo-specific domain data.

        Returns fluid dynamics knowledge:
        - physics: Physics types (incompressible, turbulence, etc.)
        - default_solver: Default solver name
        - NO mechanisms (incflo has no chemistry)

        Note: Deliberately empty mechanisms dict to test non-combustion path.

        Call context: Used by domain knowledge selection and ranking logic.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any]
            incflo domain data dictionary.
        """
        return {
            'mechanisms': {},  # NO chemistry for incompressible flow
            'physics': ['incompressible', 'fluid_dynamics', 'turbulence', 'multiphase'],
            'default_solver': 'Godunov',
        }

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract incflo-specific metadata from case directory.

        Extends base AMReX extraction with:
        - Physics type (incompressible, multiphase, etc.)
        - Fluid properties (viscosity, density)
        - Advection/diffusion schemes

        NO combustion-specific fields (mechanism, fuel, chemistry).
        This tests that metadata extraction doesn't assume combustion.

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX + incflo-specific fields.
        """
        # Get common AMReX metadata from base class
        metadata = super().extract_metadata(case_path, repo_root=repo_root)

        # Parse inputs file
        inputs_file = cls._find_inputs_file(case_path)
        if not inputs_file:
            return metadata

        params = cls._parse_inputs_file(inputs_file)

        # Extract incflo-specific fields (NO combustion!)
        metadata.update({
            # Fluid dynamics parameters
            'physics': params.get('incflo.physics', 'unknown'),
            'viscosity': params.get('incflo.viscosity'),
            'density': params.get('incflo.density'),
            'advection_type': params.get('incflo.advection_type'),
            'diffusion_type': params.get('incflo.diffusion_type'),
            'use_godunov': params.get('incflo.use_godunov', '0') == '1',

            # NO chemistry fields (validates non-combustion path)
            'mechanism': None,
            'fuel': None,
            'use_reactions': False,
        })

        return metadata

    @classmethod
    def get_priority_cases(cls) -> list[str]:
        """
        Get priority test cases for incflo.

        Call context: Used by example selection and baselines.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[str]
            Classic fluid dynamics benchmark cases.
        """
        return cls.priority_cases

    @classmethod
    def get_faiss_indices(cls) -> list[str]:
        """
        Get FAISS index names for incflo.

        Call context: Used by vector index builders and search services.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[str]
            FAISS index names (no chemistry indices).
        """
        return cls.faiss_indices

    @classmethod
    def is_valid_case(cls, case_path: Path) -> bool:
        """
        Check if a case directory is valid for incflo.

        Call context: Used by case discovery to validate candidates.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to case directory.

        Returns
        -------
        bool
            True if valid incflo case, False otherwise.
        """
        # Use base class validation (check for inputs file, GNUmakefile, etc.)
        if not super().is_valid_case(case_path):
            return False

        # Additional incflo-specific checks
        inputs_file = cls._find_inputs_file(case_path)
        if not inputs_file:
            return False

        # Check for incflo-specific parameters
        try:
            content = inputs_file.read_text()
            has_incflo_params = any(param in content for param in ['incflo.physics', 'incflo.viscosity'])
            return has_incflo_params
        except Exception:
            return False
