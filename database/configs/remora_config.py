"""
REMORA-specific configuration.

Extends BaseAMReXConfig for ocean and coastal circulation simulations.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo, REMORA.
"""

import logging
import re
from pathlib import Path
from typing import Any

from src.services.rules.base import RuleViolation

from .base_amrex_config import BaseAMReXConfig

logger = logging.getLogger(__name__)

class REMORAConfig(BaseAMReXConfig):
    """REMORA (Regional Ocean Modeling with AMReX) configuration."""

    code_name = "REMORA"

    @classmethod
    def get_default_slice_axis(cls) -> str | None:
        """
        Prefer x-z style cross-sections (normal=y) so z is vertical on plots.
        """
        return "y"

    # === Registry Metadata ===
    github_org = "AMReX-Codes"
    github_repo = "REMORA"
    description = "Ocean modeling and coastal circulation simulation"
    inputs_quality = "good"
    default_baseline_dir = "Exec/Seamount"
    default_inputs_path = "Exec/Seamount/inputs"
    default_exec_repo_path = "Exec/Seamount"
    default_exec_pattern = "REMORA*ex"

    selection_keywords = [
        "ocean",
        "coastal",
        "circulation",
        "seamount",
        "upwelling",
        "baroclinic flow",
        "coastal ocean",
        "topography",
        "ocean circulation",
    ]
    selection_guidance = ["Ocean/coastal modeling -> REMORA"]
    level0_physics_regimes = [
        {
            "family": "Ocean Modeling",
            "description": "Ocean circulation, coastal dynamics, and upwelling physics",
            "aliases": ["ocean", "coastal", "upwelling", "channel circulation"],
        }
    ]
    level0_capabilities = [
        "regional ocean circulation modeling",
        "ocean circulation",
        "wind-driven upwelling configurations",
        "periodic channel and coastal flow setups",
        "baroclinic flow over coastal ocean topography",
        "seamount and bathymetry-driven circulation dynamics",
    ]
    level0_lineage = {
        "related": ["ERF"],
        "description": "REMORA shares setup patterns with ERF and specializes them for ocean/coastal circulation.",
    }
    level0_cross_cutting_guidance = [
        "Use REMORA for ocean/coastal circulation and upwelling-style workflows.",
    ]
    github_search_paths = ["Exec/Seamount", "Exec/Upwelling", "Exec/DoubleGyre"]

    priority_cases = [
        "Exec/Seamount",
        "Exec/Upwelling",
        "Exec/DoubleGyre",
        "Exec/Channel_Test",
        "Exec/DoublyPeriodic",
    ]

    faiss_indices = [
        'remora_case_structure',
        'remora_case_details',
    ]

    documentation_map = {
        'solver_readme': ['README.md', 'README.rst'],
    }

    @classmethod
    def get_viz_variable_catalog(cls, repo_root: Path | None = None) -> list[dict[str, Any]]:
        """
        Build REMORA visualization variable catalog from live source files.
        """
        if repo_root:
            root = Path(repo_root)
        else:
            root = Path(__file__).resolve().parents[2].parent / "REMORA"

        header = root / "Source" / "REMORA.H"
        if not header.exists():
            return []

        try:
            header_text = header.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        names: list[str] = []
        for _, body in re.findall(
            r'const\s+amrex::Vector<std::string>\s+(cons_names|derived_names)\s*\{(.*?)\};',
            header_text,
            flags=re.DOTALL,
        ):
            names.extend(re.findall(r'"([^"]+)"', body))
        names.extend(["x_velocity", "y_velocity", "z_velocity"])

        long_name_map: dict[str, str] = {}
        units_map: dict[str, str] = {}
        ncplot = root / "Source" / "IO" / "REMORA_NCPlotFile.cpp"
        if ncplot.exists():
            try:
                nc_text = ncplot.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                nc_text = ""
            for var, desc in re.findall(
                r'ncf\.var\("([^"]+)"\)\.put_attr\("long_name","([^"]*)"\);',
                nc_text,
            ):
                long_name_map[var] = desc
            for var, unit in re.findall(
                r'ncf\.var\("([^"]+)"\)\.put_attr\("units","([^"]*)"\);',
                nc_text,
            ):
                units_map[var] = unit

        aliases = {
            "temp": ["temperature"],
            "salt": ["salinity"],
            "vorticity": ["vort"],
            "x_velocity": ["x velocity", "u velocity"],
            "y_velocity": ["y velocity", "v velocity"],
            "z_velocity": ["z velocity", "vertical velocity", "w velocity"],
        }

        catalog: list[dict[str, Any]] = []
        seen: set[str] = set()
        source_ref = str(header)
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            catalog.append(
                {
                    "name": name,
                    "aliases": aliases.get(name, []),
                    "units": units_map.get(name),
                    "description": long_name_map.get(name),
                    "source": source_ref,
                }
            )
        return catalog

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract REMORA-specific metadata.

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to REMORA case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX + REMORA-specific fields.
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
        Get priority case paths for REMORA.

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
        Run REMORA-specific physics checks.

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

        def check_salinity(value: Any, parameter: str) -> None:
            """
            Validate that a salinity value is within physical range.

            Parameters
            ----------
            value : Any
                Salinity value to validate (PSU).
            parameter : str
                Parameter name for reporting violations.

            Returns
            -------
            None
                This helper only records violations.
            """
            try:
                salinity = float(value)
            except (TypeError, ValueError):
                return
            if salinity < 0.0 or salinity > 50.0:
                violations.append(
                    RuleViolation(
                        rule_name="SalinityRange",
                        severity="warning",
                        parameter=parameter,
                        message=f"Salinity {salinity} PSU outside typical range [0, 50]",
                    )
                )

        def check_temperature(value: Any, parameter: str) -> None:
            """
            Validate that a temperature value is within physical range for ocean.

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
            if temperature < -2.0 or temperature > 40.0:
                violations.append(
                    RuleViolation(
                        rule_name="TemperatureRange",
                        severity="warning",
                        parameter=parameter,
                        message=f"Temperature {temperature}°C outside typical ocean range [-2, 40]",
                    )
                )

        # Check REMORA-specific parameters
        remora = config_dict.get("remora", {})
        if isinstance(remora, dict):
            for key in ["salinity", "s0"]:
                if key in remora:
                    check_salinity(remora[key], f"remora.{key}")
            for key in ["temperature", "t0"]:
                if key in remora:
                    check_temperature(remora[key], f"remora.{key}")

        prob = config_dict.get("prob", {})
        if isinstance(prob, dict):
            for key in ["salinity", "S_0"]:
                if key in prob:
                    check_salinity(prob[key], f"prob.{key}")
            for key in ["temperature", "T_0"]:
                if key in prob:
                    check_temperature(prob[key], f"prob.{key}")

        return violations
