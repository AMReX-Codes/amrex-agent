"""
PeleLMeX-specific configuration.

Extends BaseAMReXConfig with low-Mach combustion-specific metadata:
- Chemistry mechanisms and fuels (shared with PeleC)
- Low-Mach solver parameters
- Turbulence models

Pattern: Similar to PeleCConfig but customized for low-Mach flows.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
from pathlib import Path
from typing import Any, ClassVar

from src.services.rules.base import RuleViolation

from .base_amrex_config import BaseAMReXConfig
from .pelec_config import (
    COMBUSTION_FLAME_CONFIGS,
    COMBUSTION_PHYSICS_PROBLEMS,
    MECHANISM_TO_FUEL,
)

logger = logging.getLogger(__name__)

class PeleLMeXConfig(BaseAMReXConfig):
    """
    PeleLMeX (low-Mach reacting flow) configuration.

    Extends base AMReX config with low-Mach combustion knowledge:
    - Chemistry mechanisms (shared with PeleC)
    - Fuel types
    - Low-Mach specific solver parameters
    - Turbulence models
    """

    code_name = "PeleLMeX"
    schema_pattern = "pelelmex_complete_*.json"  # Use composed schema

    # === Input Writer: Schema Scraper: Extended Source Directories ===
    # PeleC-specific: adds generated parameters directory
    schema_source_patterns: ClassVar[list[str]] = [
        # Core source
        "Source",

        # Generated parameters (CRITICAL - scanned last for precedence)
        "_cpp_parameters",

        # Examples/tests that may define parameters
        "Exec/Production",
        "Exec/RegTests",
        "Exec/Regression",

        # Support
        "Support",
    ]

    manual_schema_params: ClassVar[dict[str, dict[str, Any]]] = {}

    # === Amendment D.2: PeleC Critical Parameters ===
    tier1_params: ClassVar[set[str]] = {
        "amr.n_cell",
        "peleLM.do_react",  # Critical: reactions on/off
        "peleLM.les_model",
        "peleLM.do_turbulent_forcing",
    }

    tier2_params: ClassVar[set[str]] = {
        "peleLM.chem_integrator",
        "peleLM.use_typ_vals_chem",
        "peleLM.plot_react",
        "peleLM.chem_load_balancing_method",
        "peleLM.chem_load_balancing_cost_estimate",
        "peleLM.max_grid_size_chem",
        "turbforce.urms",
        "turbforce.nmodes",
        "turbforce.spectrum_type",
        "turb_file",
        "turb_scale_vel",
        "peleLM.les_cs_smag",
        "peleLM.les_cm_wale",
        "peleLM.les_cs_sigma",
        "peleLM.les_c_chi",
        "peleLM.plot_les",
        "peleLM.les_v",
    }

    # Build flag requirements (Amendment D.3)
    # For parameters without #ifdef guards in source code
    build_requirements: ClassVar[dict[str, list[str]]] = {
        # Embedded Boundary parameters
        'eb_refine_type': ['AMREX_USE_EB'],
    }

    # === Registry Metadata ===
    github_org = "AMReX-Combustion"
    github_repo = "PeleLMeX"
    description = "Low Mach combustion with detailed transport"
    inputs_quality = "excellent"
    default_baseline_dir = "Exec/RegTests/FlameSheet"
    default_inputs_path = "Exec/RegTests/FlameSheet/inputs"
    default_exec_repo_path = "Exec/RegTests/FlameSheet"
    default_exec_pattern = "PeleLMeX*ex"

    selection_guidance = ["Combustion/flames -> PeleC or PeleLMeX"]
    github_search_paths = ["Exec/RegTests", "Exec/Production"]
    case_path_markers = {"pelelmex", "pelelm"}
    is_pele_family = True
    is_low_mach_solver = True
    chemistry_param_keys = ["pelelmex.chem_file"]
    reaction_flag_keys = ["pelelmex.do_react"]
    parameter_section_order = [
        "prob",
        "geometry",
        "amr",
        "pelelmex",
        "cvode",
        "ode",
        "other",
    ]
    ode_tolerance_plan = {
        "section": "ode",
        "param": "atol",
        "old_value": "1e-10",
        "new_value": "1e-12",
        "prompt": "What {section}.atol and {section}.rtol should I use for PeleLMeX with a QSSA mechanism?",
    }

    prompt_templates: ClassVar[dict[str, Any]] = {
        "misc": {
            "schema_scan": """Identify requested concepts from the case description that do not map to known baseline or schema parameters.

Case Description:
{case_description}

Baseline Parameters (from inputs file):
{baseline_params}

Available Schema Parameters (truncated, {schema_param_count} total):
{schema_params}

TASK - work through step-by-step:

1. **Extract all physics/simulation concepts** from the case description:
   - Physical phenomena: turbulent, reacting, multiphase, compressible, radiative, etc.
   - Geometry features: channel, pipe, cavity, jet, inlet geometry, specific shapes
   - Boundary conditions: wall types, inlet/outlet characteristics, thermal conditions
   - Flow characteristics: velocity profiles (uniform, parabolic, turbulent), temperature distributions
   - Material properties: composition details, species, equation of state
   - Initial conditions: initialization methods, perturbations, fluctuations
   - Numerical methods: time integration, spatial schemes, turbulence models
   - Special features: particles, lagrangian tracers, adaptive mesh refinement levels
   
2. **For EACH concept, check if it has parameter coverage:**
   a. Look for EXACT or CLOSE parameter matches in baseline parameters
   b. Look for EXACT or CLOSE parameter matches in schema parameters
   c. Consider common parameter naming patterns:
      - Physics toggles: do_*, use_*, enable_*
      - Models: *_model, *_type, *_scheme
      - Properties: *_velocity, *_temp, *_composition, *_profile
      - Numerics: *_integrator, *_solver, *_order
   
3. **Flag as "unresolved" ONLY if:**
   - The concept is EXPLICITLY stated in the case description (not just implied)
   - It represents a specific value, model choice, or configuration requirement
   - NO matching parameter exists in baseline OR schema parameters
   - It's NOT a generic restatement of existing parameters
   
4. **DO NOT flag as unresolved if:**
   - The concept is already captured by existing baseline parameters
   - It's a general physics description that maps to multiple existing parameters
   - It's a derived quantity or output (not an input)
   - It's describing the problem context rather than a configuration requirement
   
5. **Format unresolved concepts as short, specific noun phrases:**
   - Include key details: "turbulent fluctuations 5%", "parabolic velocity profile"
   - Avoid vague terms: instead of "special inlet", use "inlet with 5% turbulence intensity"
   - Reference specific values when stated: "spalart-allmaras turbulence model"

EXAMPLES:

**Should be flagged:**
- "turbulent fluctuations 5%" - if no parameter like inflow_turbulence_intensity exists
- "Spalart-Allmaras turbulence model" - if only schema has Smagorinsky or no turbulence.model param
- "parabolic velocity profile" - if only uniform profiles available via velocity_profile parameter
- "radiation heat transfer" - if no do_radiation or radiation.model parameter exists

**Should NOT be flagged:**
- "channel flow" - this is geometry (covered by domain bounds + BCs)
- "atmospheric pressure" - covered by existing prob.P_mean parameter
- "jet diameter 3mm" - covered by existing prob.jet_rad parameter
- "mixture composition 70% H2" - covered by prob.composition parameters
- "DNS simulation" - this describes the approach, not a specific parameter requirement

CRITICAL RULES:
- Be conservative: only flag truly missing capabilities
- Prioritize actionable, specific concepts over general descriptions
- If a concept might be achievable through parameter combinations, don't flag it
- Focus on what's explicitly requested, not what might be implied

Return JSON:
{{
  "unresolved_concepts": [
    "turbulent inflow fluctuations 5%",
    "Spalart-Allmaras turbulence model",
    "parabolic inlet velocity profile"
  ],
  "notes": "Brief explanation of why these were flagged or any ambiguities"
}}"""
        },
        "architect": {
            "modification_extraction": """Extract parameter modifications needed for this simulation case.

Case Description:
{case_description}

Baseline Input File:
```
{inputs_content}
```

{param_guidance}

TASK - reference-case adaptation:
1. Identify the physical configuration in a few words.
2. Identify key physical differences vs the baseline (flow regime, fuel/oxidizer, confinement).
3. Modify boundary conditions first to match the new flow regime/configuration.
4. Check the baseline prob.* composition/mixture flags and keep the chemical specification consistent (e.g., prob.cf_composition/jet_composition vs prob.X_* or prob.Y_*).
5. Update chemistry/transport if the user requests a reacting case; do this even if fuel/oxidizer species stay the same.
6. Assess grid/AMR only if the physics scale or resolution requirements change.
7. Apply remaining numeric value updates.
8. Only include parameters that DIFFER from baseline or must be ADDED.

CRITICAL RULES:
- Use parameter names EXACTLY as shown in the valid parameters list (including prefix like "prob.")
- If you cannot find an exact match, SKIP that modification
- Never invent, modify, or abbreviate parameter names
- For grid resolution requests ("grid cells", "grid size", "resolution"), prefer amr.n_cell (domain cell counts).
- amr.max_grid_size is for domain decomposition / refinement control; use it only when explicitly requested.
- When the request implies a significant difference from baseline inputs or choosing a different physics scale, consider a group of parameter modifications in addition to setting the important flag.

Return JSON with your working and results:
{{
  "working": "Step-by-step analysis: 1) Identified configuration ... 2) Found pressure=1atm -> prob.P_mean ...",
  "modifications": [
    {{"parameter": "prob.P_mean", "value": "101325"}}
  ]
}}""",
        },
        "knowledge": {
            "question_generator": (
                "You are a PeleLMeX simulation expert. Given this simulation request:\n\n"
                "\"{user_prompt}\"\n\n"
                "Generate 3-5 specific questions to ask a knowledge base about:\n"
                "1. Physics/transport parameters (mechanism, CFL, timesteps)\n"
                "2. Grid/AMR settings\n"
                "3. Boundary conditions\n"
                "4. Runtime considerations\n\n"
                "Return ONLY a JSON list of questions, no explanation:\n"
                "[\"question 1\", \"question 2\", ...]"
            ),
        },
    }

    @classmethod
    def analysis_error_patterns(cls) -> list[dict[str, str]]:
        """
        Extend stderr error patterns with PeleLMeX-specific cases.

        Call context: Used by stderr analysis to diagnose solver failures.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[dict[str, str]]
            Pattern entries with ``pattern`` and ``message`` keys.
        """
        patterns = super().analysis_error_patterns()
        patterns.append({
            "pattern": r"PMF file must have NUM_SPECIES\+4 variables",
            "message": "PMF file mismatch: PMF must have NUM_SPECIES+4 variables (check mechanism/PMF pairing)",
        })
        return patterns


    faiss_indices = [
        'pelelmex_case_structure',
        'pelelmex_case_details',
        'pelelmex_input_templates',
    ]

    # Priority cases for PeleLMeX (from existing cases.py)
    priority_cases = [
        "Exec/RegTests/FlameSheet",
        "Exec/RegTests/TaylorGreen",
        "Exec/Production/CounterFlow",
        "Exec/Production/JetInCrossflow",
    ]

    # Override with combustion-specific keywords (Indexing Engine: Physics-Agnostic Keywords & Scoring)
    # Adapted from PeleC for low Mach combustion
    level2_index_keywords = {
        'physics_parameters': [
            'pelelmex', 'combustion', 'flame', 'diffusion', 'soret', 'gravity',
            'low_mach', 'incompressible', 'variable_density',
        ],
        'domain_models': [
            'chem', 'species', 'fuel', 'reaction', 'kinetics', 'ignition',
            'premixed', 'diffusion_flame', 'spray',
        ],
        'grid_specifications': [
            'amr', 'geometry', 'grid', 'n_cell', 'refinement', 'eb',
        ],
        'path_hierarchy': [],
        'git_metrics': [],
        'performance_estimates': [],
    }

    # Override with PeleLMeX-specific documentation
    documentation_map = {
        'solver_readme': ['README.md', 'README.rst'],
        'problem_catalogs': ['database/reports/report2.txt', 'database/reports/report4.txt'],
        'parameter_guides': ['database/reports/report5.txt'],
    }

    @classmethod
    def get_knowledge_tools(cls) -> dict[str, Any] | None:
        """
        Return PeleLMeX knowledge tools when available.

        Call context: Used when wiring knowledge-base query helpers.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any] or None
            Tool references for querying and loading knowledge.
        """
        return cls._load_knowledge_tools(
            module_name="utils.pele_tools",
            ask_name="ask_pele_question",
            load_name="load_pele_knowledge",
        )

    @classmethod
    def validate_physics(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Run PeleLMeX-specific physics checks.

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

        pelelmex = config_dict.get("pelelmex", {})
        if pelelmex.get("use_reactions") == "1":
            chem_file = pelelmex.get("chem_file")
            pmf_datafile = config_dict.get("pmf", {}).get("datafile")
            if not (chem_file or pmf_datafile):
                violations.append(
                    RuleViolation(
                        rule_name="ChemistryInputs",
                        severity="warning",
                        parameter="pelelmex.chem_file",
                        message="Chemistry enabled but no chem_file or pmf.datafile found",
                    )
                )

        return violations

    # Override inputs patterns - PeleC uses legacy .inp and input* patterns
    inputs_file_patterns: ClassVar[list[str]] = [
        'inputs',      # Standard
        'inputs*',     # inputs.2d, inputs.3d
        'input*',      # input.2d, input.3d (legacy)
        '*.inp',       # Legacy .inp extension
    ]

    # Remap Hints
    parameter_format_hints: ClassVar[dict[str, str]] = {
        'composition': 'Space-separated "SPECIES:fraction" format. Example: "H2:0.7 N2:0.18 He:0.12"',
        'geometry': 'prob_lo/prob_hi define domain bounds in meters',
        'velocity': 'Scalar float in m/s',
    }

    parameter_transforms: ClassVar[dict[str, str]] = {
        'diameter_to_radius': 'divide_by_2',
        'mm_to_m': 'divide_by_1000',
        'celsius_to_kelvin': 'add_273.15',
    }

    @classmethod
    def get_domain_data(cls) -> dict[str, Any]:
        """
        Get PeleLMeX-specific domain data.

        Returns low-Mach combustion knowledge:
        - mechanisms: Chemistry mechanism to fuel mappings (shared with PeleC)
        - flame_configs: Flame configuration scoring weights
        - physics_problems: Physics problem scoring weights
        - physics: Physics types
        - default_solver: Default solver name

        Call context: Used by domain knowledge selection and ranking logic.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any]
            PeleLMeX domain data dictionary.
        """
        return {
            'mechanisms': MECHANISM_TO_FUEL,  # Same as PeleC
            'flame_configs': COMBUSTION_FLAME_CONFIGS,
            'physics_problems': COMBUSTION_PHYSICS_PROBLEMS,
            'physics': ['combustion', 'reacting_flow', 'low_mach', 'incompressible'],
            'default_solver': 'LMeX',
        }

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract PeleLMeX-specific metadata from case directory.

        Extends base AMReX extraction with:
        - Chemistry mechanism
        - Fuel type
        - Low-Mach solver parameters
        - Turbulence model info

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to PeleLMeX case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX params + PeleLMeX-specific fields.
        """
        # Get common AMReX metadata from base class
        metadata = super().extract_metadata(case_path, repo_root=repo_root)

        # Parse inputs file
        inputs_file = cls._find_inputs_file(case_path)
        params = {}
        if inputs_file:
            params = cls._parse_inputs_file(inputs_file)

        # Extract chemistry mechanism (same approach as PeleC)
        mechanism = cls._extract_mechanism(case_path, params)
        metadata['mechanism'] = mechanism

        # Extract fuel from mechanism
        metadata['fuel'] = cls._extract_fuel_from_mechanism(mechanism)

        # Extract PeleLMeX-specific params
        metadata.update({
            'solver': 'LMeX',
            'use_reactions': cls._parse_bool(params.get('pelelmex.do_react')),
            'use_soret': cls._parse_bool(params.get('pelelmex.use_soret')),
            'use_wbar': cls._parse_bool(params.get('pelelmex.use_wbar')),
            'chemistry_file': params.get('pelelmex.chem_file'),
            'turbulence_model': cls._extract_turbulence_model(params),
        })

        return metadata

    @classmethod
    def _extract_mechanism(cls, case_path: Path, params: dict[str, str]) -> str | None:
        """
        Extract chemistry mechanism from case.

        Similar to PeleCConfig but checks PeleLMeX-specific parameter names.

        Args:
            case_path: Path to case directory
            params: Parsed parameters from inputs file

        Returns
        -------
            Mechanism name, or None
        """
        import re

        # Check for PeleLMeX chemistry file parameter
        chem_file = params.get('pelelmex.chem_file') or params.get('chem.chem_file')
        if chem_file:
            match = re.search(
                r'(drm\d+|gri\d+|mech_[\w]+|sandiego|dodecane|hydrogen|methane)',
                chem_file.lower()
            )
            if match:
                return match.group(1)

        # Check case path for mechanism keywords
        path_str = str(case_path).lower()
        domain_data = cls.get_domain_data()
        mechanisms = domain_data.get('mechanisms', {})

        for mech in mechanisms:
            if mech.lower() in path_str:
                return mech

        # Look for mechanism files
        for mech_file in case_path.glob('**/*'):
            if mech_file.is_file():
                filename = mech_file.name.lower()
                match = re.search(
                    r'(drm\d+|gri\d+|mech_[\w]+|sandiego|dodecane)',
                    filename
                )
                if match:
                    return match.group(1)

        return None

    @classmethod
    def _extract_fuel_from_mechanism(cls, mechanism: str | None) -> str | None:
        """
        Get fuel type from mechanism (same as PeleC).

        Args:
            mechanism: Mechanism name

        Returns
        -------
            Primary fuel name, or None
        """
        if mechanism is None:
            return None

        domain_data = cls.get_domain_data()
        mechanisms = domain_data.get('mechanisms', {})

        if mechanism in mechanisms:
            fuels = mechanisms[mechanism]
            return fuels[0] if fuels else None

        return None

    @classmethod
    def _extract_turbulence_model(cls, params: dict[str, str]) -> str | None:
        """
        Extract turbulence model information.

        Args:
            params: Parsed parameters

        Returns
        -------
            Turbulence model name, or None
        """
        # Check for turbulence-related parameters
        turb_params = [
            'pelelmex.les_model',
            'pelelmex.turb_model',
            'turbulence.model',
        ]

        for param in turb_params:
            if param in params:
                return params[param]

        # Check for LES-related flags
        if cls._parse_bool(params.get('pelelmex.do_les')):
            return 'LES'

        return None

    @classmethod
    def get_priority_cases(cls) -> list[str]:
        """
        Get priority case paths for PeleLMeX.

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

    # === File Generation Overrides ===
    @classmethod
    def _resource_bytes_per_cell(cls, config: dict[str, Any]) -> int:
        do_react = config.get("pelelmex", {}).get("do_react")
        if isinstance(do_react, str):
            enabled = do_react.strip().lower() in ["1", "true", "t", "yes", "y"]
        else:
            enabled = bool(do_react)
        return 500 if enabled else 200

    @classmethod
    def get_readme_solver_lines(cls, config: dict[str, Any]) -> list[str]:
        """
        Build solver-specific README lines for PeleLMeX.

        Call context: Used by README generation for solver details.

        Parameters
        ----------
        cls : type
            Config class.
        config : dict[str, Any]
            Parsed configuration dictionary.

        Returns
        -------
        list[str]
            Solver-specific README lines.
        """
        pelelmex = config.get("pelelmex", {})
        do_react = pelelmex.get("do_react", "0")
        if isinstance(do_react, str):
            enabled = do_react.strip().lower() in ["1", "true", "t", "yes", "y"]
        else:
            enabled = bool(do_react)
        return [f"Chemistry: {'Enabled' if enabled else 'Disabled'}"]

    @classmethod
    def extract_key_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        """
        Extract key PeleLMeX parameters for summaries.

        Call context: Used by reporting and README generators.

        Parameters
        ----------
        cls : type
            Config class.
        params : dict[str, Any]
            Parsed parameters grouped by prefix.

        Returns
        -------
        dict[str, Any]
            Flattened key parameter mapping.
        """
        key_params = super().extract_key_params(params)

        if "pelelmex" in params:
            for key in ["do_react", "do_les", "use_soret", "use_wbar"]:
                if key in params["pelelmex"]:
                    key_params[f"pelelmex.{key}"] = params["pelelmex"][key]

        return key_params
