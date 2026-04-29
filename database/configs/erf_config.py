"""
ERF-specific configuration.

Extends BaseAMReXConfig for atmospheric simulations.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
import re
from pathlib import Path
from typing import Any, ClassVar

from src.services.rules.base import RuleViolation

from .base_amrex_config import BaseAMReXConfig

logger = logging.getLogger(__name__)

class ERFConfig(BaseAMReXConfig):
    """ERF (Energy Research and Forecasting) configuration."""

    code_name = "ERF"

    @classmethod
    def get_default_slice_axis(cls) -> str | None:
        """
        Prefer x-z style cross-sections (normal=y) so z is vertical on plots.
        """
        return "y"

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
        "abl",
        "atmospheric",
        "boundary layer",
        "weather",
        "wind",
        "thermal bubble",
        "dry convection",
        "2d squall line",
        "squallline",
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
    github_search_paths = ["Exec/RegTests", "Exec/ABL", "Exec/CanonicalFlows"]
    schema_pattern = "erf_complete_*.json"

    priority_cases = [
        "Exec/CanonicalFlows/SquallLine_2D",
        "Exec/MoistRegTests/SquallLine_2D",
        "Exec/RegTests/Bubble",
        "Exec/RegTests/DensityCurrent",
        "Exec/ABL",
    ]

    faiss_indices = [
        'erf_case_structure',
        'erf_case_details',
        'erf_case_names',
    ]

    documentation_map = {
        'solver_readme': ['README.md', 'README.rst'],
    }

    prompt_templates: ClassVar[dict[str, Any]] = {
        "misc": {
            "inputs_select": (
                "You are selecting the best inputs file for an ERF atmospheric case.\n"
                "ERF atmospheric case directory: {case_name}\n\n"
                "Requested simulation prompt:\n"
                "{user_prompt}\n\n"
                "Choose the file that best matches the benchmark intent from filename and header.\n"
                "Prefer files that preserve the intended atmospheric setup (e.g., terrain, ABL, "
                "moist/dry convection, forcing) without assuming case-specific IDs.\n"
                "Strongly prioritize explicit matches to requested boundary conditions, moisture model, "
                "and timestep style when present in the prompt.\n"
                "Return ONLY one filename from the candidate list.\n\n"
                "{candidates}\n"
            ),
        },
        "architect": {
            "modification_extraction": (
                "Extract parameter modifications needed for this ERF simulation case.\n\n"
                "Case Description:\n"
                "{case_description}\n\n"
                "Baseline Input File:\n"
                "```\n"
                "{inputs_content}\n"
                "```\n\n"
                "{param_guidance}\n\n"
                "TASK - work through step-by-step:\n"
                "1. Identify each requested atmospheric behavior or value in the case description.\n"
                "2. For EACH requested change:\n"
                "   a. Find the exact corresponding parameter name in baseline or schema list.\n"
                "   b. Preserve atmospheric consistency: stratification, forcing, terrain/ABL setup, "
                "boundary conditions, and initialization assumptions.\n"
                "   c. Determine whether value differs from baseline.\n"
                "3. Include only parameters that differ from baseline or must be added.\n"
                "4. Keep modifications generic and transferable across ERF cases.\n\n"
                "CRITICAL RULES:\n"
                "- Never invent parameter names.\n"
                "- Use exact keys as present in baseline inputs or valid schema list.\n"
                "- Keep updates generic; do not hardcode benchmark IDs or case names.\n\n"
                "Return JSON:\n"
                "{{\n"
                '  "working": "brief step-by-step notes",\n'
                '  "modifications": [{{"parameter": "name", "value": "value"}}]\n'
                "}}\n"
            ),
        },
    }

    @classmethod
    def get_viz_variable_catalog(cls, repo_root: Path | None = None) -> list[dict[str, Any]]:
        """
        Build ERF visualization variable catalog from live ERF source files.
        """
        if repo_root:
            root = Path(repo_root)
        else:
            root = Path(__file__).resolve().parents[2].parent / "ERF"

        header = root / "Source" / "ERF.H"
        if not header.exists():
            return []

        try:
            text = header.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        vector_pattern = re.compile(
            r'const\s+amrex::Vector<std::string>\s+(cons_names|derived_names|derived_names_2d)\s*\{(.*?)\};',
            re.DOTALL,
        )
        names: list[str] = []
        for _, body in vector_pattern.findall(text):
            names.extend(re.findall(r'"([^"]+)"', body))

        units = {
            "density": "kg/m^3",
            "temp": "K",
            "pressure": "Pa",
            "qv": "kg/kg",
            "qc": "kg/kg",
            "qi": "kg/kg",
            "qrain": "kg/kg",
            "qsnow": "kg/kg",
            "qgraup": "kg/kg",
            "qt": "kg/kg",
        }
        aliases = {
            "temp": ["temperature"],
            "magvel": ["velocity", "speed"],
            "vorticity_z": ["vorticity", "vertical vorticity"],
            "qc": ["cloud water", "cloud_water", "liquid water", "cloud liquid"],
            "qv": ["water vapor", "vapor mixing ratio", "humidity"],
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
                    "units": units.get(name),
                    "description": None,
                    "source": source_ref,
                }
            )
        return catalog

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
