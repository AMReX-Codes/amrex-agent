"""
PeleC-specific configuration.

Extends BaseAMReXConfig with combustion-specific metadata:
- Chemistry mechanisms and fuels
- Boundary condition types
- Combustion physics parameters

Pattern: Similar to yt's CastroDataset extending BoxlibDataset.
Stores combustion domain mappings for reuse across solver configs.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

from src.services.rules.base import RuleViolation

from .base_amrex_config import BaseAMReXConfig

# Import Pele-specific metadata utilities
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from pele_metadata_utils import (
    catalog_pele_auxiliary_files,
    extract_pele_build_config,
    infer_combustion_regime,
)

logger = logging.getLogger(__name__)

# Combustion domain mappings used by scoring/metadata.
MECHANISM_TO_FUEL = {
    # Methane mechanisms
    'drm19': ['methane', 'ch4', 'natural_gas'],
    'drm22': ['methane', 'ch4', 'natural_gas'],
    'gri30': ['methane', 'ch4'],
    'grimech30': ['methane', 'ch4'],
    'grimech12': ['methane', 'ch4'],
    'grimech30-noarn': ['methane', 'ch4'],
    'alzeta': ['methane', 'ch4'],
    'kolla': ['methane', 'ch4'],

    # Hydrogen mechanisms
    'lidryer': ['hydrogen', 'h2'],
    'burkedryer': ['hydrogen', 'h2'],
    'sandiego': ['hydrogen', 'h2'],
    'chem-h': ['hydrogen', 'h2'],
    'h2-co-co2-3spec': ['hydrogen', 'h2', 'syngas'],

    # Dodecane
    'dodecane_lu': ['dodecane', 'c12h26', 'diesel'],
    'dodecane_lu_qss': ['dodecane', 'c12h26', 'diesel'],

    # Decane
    'decane_3sp': ['decane', 'c10h22'],

    # Heptane
    'heptane_3sp': ['heptane', 'c7h16'],
    'heptane_fc': ['heptane', 'c7h16'],

    # Ethylene
    'luethylene': ['ethylene', 'c2h4'],
    'ethylene_af': ['ethylene', 'c2h4'],

    # Propane
    'propane_fc': ['propane', 'c3h8'],

    # Soot
    'sootreaction': ['soot', 'pah', 'polycyclic'],

    # Ions/Plasma
    'methaneions_direnzo': ['methane', 'ch4', 'plasma'],
    'ionizedair': ['air', 'plasma'],

    # Air/Null
    'air': ['air', 'nitrogen', 'oxygen'],
    'null': ['inert', 'air', 'non_reacting'],
}

COMBUSTION_FLAME_CONFIGS = {
    'pmf': 0.35,              # Premixed flame (common baseline)
    'counterflow': 0.30,
    'bunsen': 0.30,
    'tripleflame': 0.28,
    'flamesheet': 0.28,
    'jetflame': 0.25,
    'enclosedflame': 0.25,
    'sphericalflame': 0.25,
    'backwardstepflame': 0.25,
    'cavityflame': 0.22,
    'flame': 0.15,            # Generic flame
}

COMBUSTION_PHYSICS_PROBLEMS = {
    'ignitiondelay': 0.20,
    'tgreact': 0.18,          # Reacting Taylor-Green
    'soot': 0.15,
    'reacteval': 0.12,
    'detonation': 0.18,
    'ignition': 0.15,
}

class PeleCConfig(BaseAMReXConfig):
    """
    PeleC (compressible reacting flow) configuration.

    Extends base AMReX config with combustion-specific knowledge:
    - Chemistry mechanisms
    - Fuel types
    - Boundary conditions
    - Combustion physics
    """

    # Input Writer: Rule Factory: Extend base validation rules
    validation_rules = BaseAMReXConfig.validation_rules + [
        "CFLStabilityRule",  # PeleC uses explicit time integration
        # Future: PeleC-specific rules
        # "ChemistryConsistency",
        # "EquationOfStateRule",
    ]

    code_name = "PeleC"
    schema_pattern = "pelec_complete_*.json"  # Use composed schema

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

    # === Amendment D.2: PeleC Critical Parameters ===
    tier1_params: ClassVar[set[str]] = {
        "amr.n_cell",
        "pelec.do_react",  # Critical: reactions on/off
        "pelec.cfl",
    }

    # Build flag requirements (Amendment D.3)
    # For parameters without #ifdef guards in source code
    build_requirements: ClassVar[dict[str, list[str]]] = {
        # Embedded Boundary parameters
        'eb_refine_type': ['AMREX_USE_EB'],
        'eb_detag_factor': ['AMREX_USE_EB'],
        'eb_boundary_T': ['AMREX_USE_EB'],
        'eb_isothermal': ['AMREX_USE_EB'],
        'eb_noslip': ['AMREX_USE_EB'],
        'eb_clean_massfrac': ['AMREX_USE_EB'],
        'eb_clean_massfrac_threshold': ['AMREX_USE_EB'],
        'eb_srd_max_order': ['AMREX_USE_EB'],
        'eb_weights_type': ['AMREX_USE_EB'],
        'eb_zero_body_state': ['AMREX_USE_EB'],
        'eb_problem_state': ['AMREX_USE_EB'],
        'max_eb_refine_lev': ['AMREX_USE_EB'],
        'min_eb_refine_lev': ['AMREX_USE_EB'],
    }


    # === Registry Metadata (migrated from cases.py PRIORITY_CODES) ===
    github_org = "AMReX-Combustion"
    github_repo = "PeleC"
    description = "Compressible reacting flow with detailed chemistry"
    inputs_quality = "excellent"
    default_baseline_dir = "Exec/RegTests/PMF"
    default_inputs_path = "Exec/RegTests/PMF/pmf-lidryer-rk64.inp"
    default_exec_repo_path = "Exec/RegTests/PMF"
    default_exec_pattern = "PeleC*ex"

    selection_keywords = ["flame", "combustion", "methane"]
    selection_guidance = ["Combustion/flames -> PeleC or PeleLMeX"]
    github_search_paths = ["Exec/RegTests", "Exec/Production"]
    case_path_markers = {"pelec"}
    is_pele_family = True
    match_exclusions = ["pelelm"]
    cfl_param_name = "pelec.cfl"
    explicit_cfl = True
    chemistry_param_keys = ["pelec.chem_file"]
    reaction_flag_keys = ["pelec.do_react"]
    parameter_section_order = [
        "prob",
        "geometry",
        "amr",
        "pelec",
        "ode",
        "other",
    ]
    prompt_templates: ClassVar[dict[str, Any]] = {
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
4. Update chemistry/transport only if the fuel or oxidizer changes.
5. Assess grid/AMR only if the physics scale or resolution requirements change.
6. Apply remaining numeric value updates.
7. Only include parameters that DIFFER from baseline or must be ADDED.

CRITICAL RULES:
- Use parameter names EXACTLY as shown in the baseline input file or valid parameters list (including prefix like "prob."). The list is a priority aid, not exhaustive.
- If you cannot find an exact match in either place, SKIP that modification
- Never invent, modify, or abbreviate parameter names
- For grid resolution requests ("grid cells", "grid size", "resolution"), prefer amr.n_cell (domain cell counts).
- amr.max_grid_size is for domain decomposition / refinement control; use it only when explicitly requested.

Return JSON with your working and results:
{{
  "working": "Step-by-step analysis: 1) Identified configuration ... 2) Found pressure=1atm -> prob.P_mean ...",
  "modifications": [
    {{"parameter": "prob.P_mean", "value": "101325"}}
  ]
}}""",
        },
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
        "knowledge": {
            "question_generator": (
                "You are a PeleC simulation expert. Given this simulation request:\n\n"
                "\"{user_prompt}\"\n\n"
                "Generate 3-5 specific questions to ask a knowledge base about:\n"
                "1. Physics/chemistry parameters (mechanism, CFL, timesteps)\n"
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
        Extend stderr error patterns with PeleC-specific cases.

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
        'pelec_case_structure',
        'pelec_case_details',
        'pelec_case_names',
        'pelec_input_templates',
        'pelec_chemistry',
    ]

    # Priority cases for PeleC (from existing cases.py)
    priority_cases = [
        "Exec/RegTests/PMF",
        "Exec/RegTests/Sedov",
        "Exec/RegTests/TG",
        "Exec/Production/JetFlame",
    ]

    example_catalog: ClassVar[dict[str, str]] = {
        'sedov-1': 'Exec/RegTests/Sedov/sedov-1.inp',
        'sedov-example': 'Exec/RegTests/Sedov/example.inp',
        'tg-1': 'Exec/RegTests/TG/tg-1.inp',
        'tg-2': 'Exec/RegTests/TG/tg-2.inp',
        'tgreact': 'Exec/RegTests/TGReact/tgreact.inp',
        'pmf-lidryer': 'Exec/RegTests/PMF/pmf-lidryer-rk64.inp',
        'pmf-dodecane': 'Exec/RegTests/PMF/pmf-dodecane.inp',
    }

    # Override with PeleC-specific documentation
    documentation_map = {
        'solver_readme': ['README.rst'],
        'problem_catalogs': ['database/reports/report2.txt', 'database/reports/report4.txt'],
        'parameter_guides': ['database/reports/report5.txt'],
        'build_instructions': ['Docs/sphinx/BuildingSource.rst'],
    }

    # Override inputs patterns - PeleC uses legacy .inp and input* patterns
    inputs_file_patterns: ClassVar[list[str]] = [
        'inputs',      # Standard
        'inputs*',     # inputs.2d, inputs.3d
        'input*',      # input.2d, input.3d (legacy)
        '*.inp',       # Legacy .inp extension
    ]

    @classmethod
    def get_knowledge_tools(cls) -> dict[str, Any] | None:
        """
        Return PeleC knowledge tools when available.

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

    # Override with PeleC-specific auxiliary files
    auxiliary_patterns = [
        '*.dat',
        'probin*',
        'GNUmakefile',
        'chem_*.txt',      # Chemistry files
        'dodecane.dat',    # Fuel data
        'drm19.dat',       # Chemistry mechanism
    ]

    # Override with combustion-specific keywords (Indexing Engine: Physics-Agnostic Keywords & Scoring)
    level2_index_keywords = {
        'physics_parameters': [
            'pelec', 'combustion', 'flame', 'diffusion', 'soret', 'gravity',
        ],
        'domain_models': [
            'chem', 'species', 'fuel', 'reaction', 'kinetics', 'ignition',
        ],
        'grid_specifications': [
            'amr', 'geometry', 'grid', 'n_cell', 'refinement', 'eb',
        ],
        'path_hierarchy': [],
        'git_metrics': [],
        'performance_estimates': [],
    }





    @classmethod
    @classmethod
    def get_domain_data(cls) -> dict[str, Any]:
        """
        Get PeleC-specific domain data.

        Returns combustion-specific knowledge:
        - mechanisms: Chemistry mechanism to fuel mappings
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
            PeleC domain data dictionary.
        """
        return {
            'mechanisms': MECHANISM_TO_FUEL,
            'flame_configs': COMBUSTION_FLAME_CONFIGS,
            'physics_problems': COMBUSTION_PHYSICS_PROBLEMS,
            'physics': ['combustion', 'reacting_flow', 'compressible', 'cns'],
            'default_solver': 'CNS',
        }

    @classmethod
    def validate_physics(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Run PeleC-specific physics checks.

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

        pelec = config_dict.get("pelec", {})
        cfl = cls._parse_float(pelec.get("cfl"))
        if cfl is not None:
            if cfl >= 1.0:
                violations.append(
                    RuleViolation(
                        rule_name="CFLStability",
                        severity="error",
                        parameter="pelec.cfl",
                        message=f"CFL {cfl} >= 1.0 will be unstable",
                    )
                )
            elif cfl > 0.8:
                violations.append(
                    RuleViolation(
                        rule_name="CFLStability",
                        severity="warning",
                        parameter="pelec.cfl",
                        message=f"CFL {cfl} is aggressive, consider < 0.7",
                    )
                )

        if pelec.get("use_reactions") == "1":
            chem_file = pelec.get("chem_file")
            pmf_datafile = config_dict.get("pmf", {}).get("datafile")
            if not (chem_file or pmf_datafile):
                violations.append(
                    RuleViolation(
                        rule_name="ChemistryInputs",
                        severity="warning",
                        parameter="pelec.chem_file",
                        message="Chemistry enabled but no chem_file or pmf.datafile found",
                    )
                )

        return violations

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract PeleC-specific metadata from case directory.

        Extends base AMReX extraction with:
        - Chemistry mechanism
        - Fuel type
        - Boundary condition types
        - Combustion-specific parameters

        PHASE 2 UPDATE: Now includes complete path information:
        - case_path: Portable repo-relative (Exec/RegTests/PMF)
        - local_path: Full absolute path where case currently exists
        - repo_path: Repository root path
        - github_*: For remote fetching if needed

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to PeleC case directory.
        repo_root : pathlib.Path or None, optional
            Repository root for portable paths.

        Returns
        -------
        dict[str, Any]
            Metadata including base AMReX params + PeleC-specific fields.
        """
        # Get common AMReX metadata from base class (includes generic build config)
        metadata = super().extract_metadata(case_path, repo_root=repo_root)

        # GitHub info for remote fetching
        metadata.update({
            'github_org': 'AMReX-Combustion',
            'github_repo': 'PeleC',
            'github_url': 'https://github.com/AMReX-Combustion/PeleC',
        })

        # Get inputs file params for PeleC-specific extraction
        inputs_file = cls._find_inputs_file(case_path)
        params = {}
        if inputs_file:
            params = cls._parse_inputs_file(inputs_file)

        # Extract chemistry mechanism
        mechanism = cls._extract_mechanism(case_path, params)
        metadata['mechanism'] = mechanism

        # Extract fuel from mechanism
        metadata['fuel'] = cls._extract_fuel_from_mechanism(mechanism)

        # Extract boundary conditions
        metadata['bc_types'] = cls._extract_boundary_conditions(params)

        # Extract PeleC-specific params from inputs file
        metadata.update({
            'solver': params.get('pelec.pele_solver', 'CNS'),
            'use_reactions': cls._parse_bool(params.get('pelec.do_react')),
            'use_diffusion': cls._parse_bool(params.get('pelec.diffuse_temp')),
            'chemistry_file': params.get('pelec.chem_file'),
        })

        # Enhanced Pele-specific metadata from new utilities
        # Extract Pele build config (Chemistry_Model, Eos_dir, Transport_dir from GNUmakefile)
        pele_build = extract_pele_build_config(case_path)
        metadata.update(pele_build)

        # Override generic auxiliary files with Pele-specific interpretation
        # (chemistry files get better descriptions)
        pele_aux = catalog_pele_auxiliary_files(case_path)
        if pele_aux:  # Only override if we found Pele-specific files
            metadata['auxiliary_files'] = [f['file'] for f in pele_aux]
            metadata['auxiliary_file_details'] = pele_aux

        # Infer combustion regime from case characteristics
        metadata['combustion_regime'] = infer_combustion_regime(case_path, metadata)

        return metadata

    @classmethod
    def _extract_mechanism(cls, case_path: Path, params: dict[str, str]) -> str | None:
        """
        Extract chemistry mechanism from case.

        Tries multiple strategies:
        1. Check inputs file for chem_file parameter
        2. Check case path for mechanism keywords
        3. Check for mechanism files in directory

        Args:
            case_path: Path to case directory
            params: Parsed parameters from inputs file

        Returns
        -------
            Mechanism name (e.g., 'drm19', 'gri30'), or None
        """
        # Strategy 1: Check chem_file parameter
        chem_file = params.get('pelec.chem_file') or params.get('chem.chem_file')
        if chem_file:
            # Extract mechanism name from file path
            # Examples: "drm19.yaml", "mech_h2.xml", "gri30.dat"
            match = re.search(
                r'(drm\d+|gri\d+|mech_[\w]+|sandiego|dodecane|hydrogen|methane)',
                chem_file.lower()
            )
            if match:
                return match.group(1)

        # Strategy 2: Check case path for mechanism keywords
        path_str = str(case_path).lower()

        # Get known mechanisms from domain data
        domain_data = cls.get_domain_data()
        mechanisms = domain_data.get('mechanisms', {})

        for mech in mechanisms:
            if mech.lower() in path_str:
                return mech

        # Strategy 3: Look for mechanism files in directory
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
        Get fuel type from mechanism using existing MECHANISM_TO_FUEL dict.

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
    def _extract_boundary_conditions(cls, params: dict[str, str]) -> dict[str, Any] | None:
        """
        Extract boundary condition types from parameters.

        PeleC boundary conditions:
        - 0 = Interior
        - 1 = Inflow
        - 2 = Outflow
        - 3 = Symmetry
        - 4 = SlipWall
        - 5 = NoSlipWall

        Args:
            params: Parsed parameters

        Returns
        -------
            Dictionary with lo/hi boundary conditions, or None
        """
        bc_data = {}

        # Check for PeleC-style BC parameters
        for direction in ['lo', 'hi']:
            bc_param = f'pelec.{direction}_bc'
            if bc_param in params:
                bc_data[direction] = params[bc_param]

        # Also check cns.* prefix (older style)
        if not bc_data:
            for direction in ['lo', 'hi']:
                bc_param = f'cns.{direction}_bc'
                if bc_param in params:
                    bc_data[direction] = params[bc_param]

        return bc_data if bc_data else None

    @classmethod
    def get_priority_cases(cls) -> list[str]:
        """
        Get priority case paths for PeleC.

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
    def resolve_executable_path(cls, app_config: Any | None) -> str | None:
        """
        Resolve a PeleC executable path override.

        Call context: Used when assembling run commands or job scripts.

        Parameters
        ----------
        cls : type
            Config class.
        app_config : Any or None
            Application config object with executable overrides.

        Returns
        -------
        str or None
            Resolved executable path, or None if unavailable.
        """
        if not app_config:
            return None
        path = getattr(app_config, "pelec_executable", None)
        if path:
            return str(path)
        return super().resolve_executable_path(app_config)

    @classmethod
    def _resource_bytes_per_cell(cls, config: dict[str, Any]) -> int:
        do_react = config.get("pelec", {}).get("do_react")
        if isinstance(do_react, str):
            enabled = do_react.strip().lower() in ["1", "true", "t", "yes", "y"]
        else:
            enabled = bool(do_react)
        return 500 if enabled else 200

    @classmethod
    def get_readme_solver_lines(cls, config: dict[str, Any]) -> list[str]:
        """
        Build solver-specific README lines for PeleC.

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
        pelec = config.get("pelec", {})
        do_react = pelec.get("do_react", "0")
        if isinstance(do_react, str):
            enabled = do_react.strip().lower() in ["1", "true", "t", "yes", "y"]
        else:
            enabled = bool(do_react)
        cfl = pelec.get("cfl", "0.5")
        return [
            f"Chemistry: {'Enabled' if enabled else 'Disabled'}",
            f"CFL: {cfl}",
        ]

    @classmethod
    def extract_key_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        """
        Extract key PeleC parameters for summaries.

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

        if "pelec" in params:
            for key in ["cfl", "v", "do_react", "do_hydro"]:
                if key in params["pelec"]:
                    key_params[f"pelec.{key}"] = params["pelec"][key]

        return key_params
