"""
Base configuration for all AMReX codes.

Handles common AMReX parameters from inputs files:
- geometry.*: domain bounds, periodicity
- amr.*: grid hierarchy, refinement
- Time stepping: max_step, stop_time, CFL
- I/O: plot files, checkpoint files

Pattern inspired by yt-project's BoxlibDataset base class.
Code-specific configs (PeleC, ERF, etc.) inherit and extend this.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import copy
import hashlib
import json
import logging
import math
import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Any, ClassVar

from src.services.rules.base import RuleViolation

# Import generic AMReX metadata utilities
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


logger = logging.getLogger(__name__)

class BaseAMReXConfig:
    """
    Base configuration for all AMReX codes.

    Provides common AMReX parameter parsing and metadata extraction.
    Subclasses override for code-specific domain knowledge.
    """

    # Input Writer: Rule Factory: Validation Rules (Config-Driven)
    # Generic AMReX rules inherited by all solver configs
    # Following DRY pattern from Metadata Schema/5
    validation_rules = [
        "SchemaExistence",      # Amendment D.3: Source Code Truth validation
        "BuildFlagDependency",  # Schema-driven dependency checking
        "GridConsistency",      # AMReX grid constraints
        "TimestepBounds",       # Detect implausible max_dt for timesteps
    ]

    code_name: str = "amrex_base"
    """Code identifier (e.g., 'PeleC', 'ERF', 'WarpX')"""

    # === Input Writer: Schema Scraper: Schema Source Directories ===
    # Directory paths to scan recursively (based on common AMReX/Pele structure)
    schema_source_patterns: ClassVar[list[str]] = [
        # Core source directories
        "Source",
        "Src",
        "Src/Base",
        "Src/AmrCore",
        "Src/Amr",
        "Src/Boundary",

        # Example/test directories (may have parameters)
        "Exec/Production",
        "Exec/Regression",
        "Exec/RegTests",
        "Exec/Tests",
        "Exec/Benchmark",

        # Support utilities
        "Support",
        "Utils",
    ]

    # Optional manual schema additions for parameters missing from source scans.
    # Keys are parameter names, values define schema fields.
    manual_schema_params: ClassVar[dict[str, dict[str, Any]]] = {}

    # === Amendment D.2: Parameter Priority Tiers ===
    tier1_params: ClassVar[set[str]] = {
        "amr.n_cell",
        "geometry.is_periodic",
        "amr.max_step",
        "max_step",
        "stop_time",
    }

    tier2_params: ClassVar[set[str]] = {
        "amr.max_level",
        "amr.blocking_factor",
    }

    # === Registry Metadata (Cases Service: Config-Driven Discovery: Config-Driven Discovery) ===
    github_org: str = ""
    """GitHub organization (e.g., 'AMReX-Combustion')"""

    github_repo: str = ""
    """GitHub repository name (defaults to code_name)"""

    description: str = ""
    """Human-readable description of the code's purpose"""

    inputs_quality: str = "basic"
    """Documentation quality: 'excellent', 'good', or 'basic'"""

    priority_cases: list[str] = []
    """List of example case paths (e.g., ['Exec/RegTests/PMF'])"""

    case_selection_prompt: ClassVar[str] = """You are an expert in AMReX-based simulation codes. Given this request:

"{user_prompt}"

Select the BEST AMReX code and example case as a starting point.

Available codes:{options}

#######################
# Domain-specific: physics keyword -> solver mapping guidance
#######################
Guidelines:
{guidance_block}
#######################

Prefer codes with "excellent" documentation quality.

Return EXACTLY two lines:
CODE: <name>
CASE: <path>"""
    """Template for selecting a code and case based on the user request."""

    misc_prompts: ClassVar[dict[str, str]] = {
        "llm_connectivity_test": "Say 'OK' and nothing else.",
        "inputs_select": (
            "You are selecting the best inputs file for an AMReX case.\n"
            "Case directory: {case_name}\n\n"
            "Choose the file that most closely matches the case based on file name and header.\n"
            "Prefer case-named .inp files over generic inputs.* when both are available.\n"
            "Return ONLY the filename from the list below.\n\n"
            "{candidates}\n"
        ),
        "retry_guidance": (
            "You are deciding whether to switch the baseline case or inputs file on retry.\n"
            "Return ONLY JSON with keys: inputs_base_action, baseline_base_action, rationale.\n"
            "Valid values: 'keep' or 'switch'.\n\n"
            "SOLVER: {solver}\n"
            "BASELINE CASE: {baseline_case}\n"
            "INPUTS FILE: {inputs_file}\n\n"
            "CURRENT ERRORS:\n{errors_current}\n\n"
            "ERRORS ALL FOUND:\n{errors_all_found}\n\n"
            "ERRORS ALL FIXED:\n{errors_all_fixed}\n\n"
            "ANALYSIS ISSUES:\n{analysis_issues}\n"
        ),
    }
    """Miscellaneous prompt strings used outside solver-specific flows."""

    example_catalog: ClassVar[dict[str, str]] = {}
    """Map of example keys to repo-relative inputs paths."""

    # === Default Paths (Repo-Relative) ===
    default_baseline_dir: ClassVar[str | None] = None
    """Repo-relative default case directory (e.g., 'Exec/RegTests/PMF')."""

    default_inputs_path: ClassVar[str | None] = None
    """Repo-relative default inputs file path (e.g., 'Exec/RegTests/PMF/inputs')."""

    default_exec_repo_path: ClassVar[str | None] = None
    """Repo-relative path to directory or file containing default executable."""

    default_exec_pattern: ClassVar[str | None] = None
    """Glob pattern for default executable within default_exec_repo_path."""

    # === Solver Heuristics (Config-Driven) ===
    selection_keywords: ClassVar[list[str]] = []
    """Keyword hints for solver selection (e.g., ["combustion", "flame"])."""

    selection_guidance: ClassVar[list[str]] = [
        "Learning AMReX -> amrex-tutorials",
    ]
    """Guidance lines used in solver-selection prompts."""

    # === Level 0 Metadata (Indexing Engine: Level 0) ===
    level0_physics_regimes: ClassVar[list[dict[str, Any]]] = []
    """
    Structured physics regime entries for Level 0 `physics_regimes`.

    Entry shape:
        {
            "family": "Low Mach Flow",
            "description": "Low speed incompressible/weakly compressible flow",
            "aliases": ["incompressible", "low mach"]
        }
    """

    level0_capabilities: ClassVar[list[str]] = []
    """Solver-specific capability phrases for Level 0 `solver_capabilities`."""

    level0_lineage: ClassVar[dict[str, Any]] = {}
    """
    Optional solver lineage metadata for Level 0 `code_lineage`.

    Expected keys include: `description`, `evolved_from`, `related`.
    """

    level0_cross_cutting_guidance: ClassVar[list[str]] = []
    """
    Optional per-solver decision guidance lines for Level 0
    `cross_cutting_guidance`.
    """

    github_search_paths: ClassVar[list[str]] = ["Exec", "Examples"]
    """Repo paths used for GitHub case discovery."""

    case_path_markers: ClassVar[set[str]] = set()
    """Lowercase markers used for heuristic path matching."""

    is_pele_family: ClassVar[bool] = False
    """True if solver is part of the Pele code family."""

    match_exclusions: ClassVar[list[str]] = []
    """Substrings to exclude when matching solver names in text."""

    is_low_mach_solver: ClassVar[bool] = False
    """True if solver targets low-Mach/incompressible regimes."""

    cfl_param_name: ClassVar[str] = "amr.cfl"
    """Parameter name for CFL setting (dot-notation)."""

    explicit_cfl: ClassVar[bool] = False
    """True if solver uses explicit CFL stability constraints."""

    chemistry_param_keys: ClassVar[list[str]] = []
    """Parameter keys that reference chemistry mechanism files."""

    reaction_flag_keys: ClassVar[list[str]] = []
    """Parameter keys that enable or disable reaction mechanisms."""

    parameter_section_order: ClassVar[list[str]] = [
        "prob",
        "geometry",
        "amr",
        "ode",
        "other",
    ]
    """Preferred ordering when grouping parameters by prefix."""

    ode_tolerance_plan: ClassVar[dict[str, str] | None] = None
    """Optional ODE tolerance adjustment plan for solver-specific workflows."""

    cfl_model_aliases: ClassVar[list[str]] = ["pelec_cfl", "cfl"]
    """Model attribute aliases for CFL in validation."""

    feedback_physics_prefixes: ClassVar[list[str]] = [
        "pelec.",
        "pelelmex.",
        "pelemp.",
        "cfl",
        "diffusion",
        "chem",
        "gravity",
    ]
    """Prefixes used to categorize physics-related feedback."""

    # === Analysis Error Detection ===
    @classmethod
    def analysis_error_patterns(cls) -> list[dict[str, str]]:
        """
        Regex patterns for stderr issue detection.

        Call context: Used by stderr analysis to map errors to messages.

        Subclasses can extend for solver-specific errors. Each entry includes
        a regex pattern and human-readable message.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[dict[str, str]]
            Pattern entries with ``pattern`` and ``message`` keys.
        """
        return [
            {
                "pattern": r"AMReX::Abort|MPI_ABORT|Abort",
                "message": "Simulation aborted (see stderr.log for details)",
            },
        ]

    @classmethod
    def makefile_search_globs(cls) -> list[str]:
        """
        Get makefile glob patterns for token extraction.

        Call context: Used during stderr diagnostics to scan build files.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[str]
            Glob patterns used to locate makefiles.
        """
        return ["GNUmakefile", "Make.*"]

    @classmethod
    def find_makefile_tokens(
        cls,
        case_dir: Path | None,
        repo_root: Path | None,
        max_files: int = 50,
    ) -> set[str]:
        """
        Extract build/config tokens from makefiles.

        Call context: Used by stderr heuristics to enrich diagnostics.

        Parameters
        ----------
        cls : type
            Config class.
        case_dir : pathlib.Path or None
            Case directory that may contain a GNUmakefile.
        repo_root : pathlib.Path or None
            Repository root to scan for Make.* files.
        max_files : int, optional
            Maximum number of Make.* files to scan.

        Returns
        -------
        set[str]
            Unique build tokens extracted from makefiles.
        """
        tokens: set[str] = set()

        if case_dir:
            makefile = Path(case_dir) / "GNUmakefile"
            if makefile.is_file():
                try:
                    content = makefile.read_text(errors="ignore")
                    tokens.update(
                        re.findall(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*[?:]?=", content, flags=re.M)
                    )
                    tokens.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", content))
                except Exception:
                    pass

        if repo_root:
            repo_root = Path(repo_root)
            files_scanned = 0
            for makefile in repo_root.rglob("Make.*"):
                if not makefile.is_file():
                    continue
                try:
                    content = makefile.read_text(errors="ignore")
                except Exception:
                    continue
                tokens.update(
                    re.findall(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*[?:]?=", content, flags=re.M)
                )
                tokens.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", content))
                files_scanned += 1
                if files_scanned >= max_files:
                    break

        # Keep the set reasonably small for downstream matching
        if len(tokens) > 500:
            tokens = set(list(tokens)[:500])
        return tokens

    # === Case Discovery (Cases Service: Config-Driven Scanner: Config-Driven Scanner) ===
    search_patterns: list[str] = [
        '**/Exec/**',       # Standard AMReX location (PeleC, incflo, etc.)
        '**/RegTests/**',   # Test cases
        '**/Tests/**',      # Alternative test location
        '**/Production/**', # Production cases
    ]
    """Glob patterns for finding case directories (override in subclasses)"""


    # Options: "newest" (default), "exact" (git hash), "tag" (version)
    schema_strategy: str = "newest"

    # === Knowledge Service Prompts ===
    knowledge_prompt_templates: ClassVar[dict[str, Any]] = {
        "question_generator": (
            "You are an AMReX simulation expert. Given this simulation request:\n\n"
            "\"{user_prompt}\"\n\n"
            "Generate 3-5 specific questions to ask a knowledge base about:\n"
            "1. Physics parameters (timestep, stability, models)\n"
            "2. Grid/AMR settings\n"
            "3. Boundary conditions\n"
            "4. Runtime considerations\n\n"
            "Return ONLY a JSON list of questions, no explanation:\n"
            "[\"question 1\", \"question 2\", ...]"
        ),
        "fallback_questions": [
            "What are recommended simulation parameters?",
            "What grid settings should I use?",
            "What boundary conditions are common?",
        ],
    }

    @classmethod
    def get_knowledge_prompt_templates(cls) -> dict[str, Any]:
        """
        Return knowledge-service prompt templates with solver overrides.

        Call context: Used when preparing knowledge-base queries.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any]
            Knowledge prompt templates for this solver.
        """
        return cls.get_prompt_templates().get("knowledge", {})

    @staticmethod
    def _load_knowledge_tools(
        module_name: str,
        ask_name: str,
        load_name: str,
    ) -> dict[str, Any] | None:
        try:
            module = import_module(module_name)
        except Exception:
            return None

        ask_tool = getattr(module, ask_name, None)
        load_tool = getattr(module, load_name, None)
        if not ask_tool or not load_tool:
            return None
        return {"ask": ask_tool, "load": load_tool, "module": module_name}

    @classmethod
    def get_knowledge_tools(cls) -> dict[str, Any] | None:
        """
        Return knowledge tools if available for this solver.

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
        return None

    # Schema pattern for AMReX core defaults (optional)
    schema_pattern: str = "amrex_schema_*.json"

    # Schema tag (used when schema_strategy="tag")
    schema_tag: str = ""
    # Schema metadata version (used in composed schema naming/selection)
    schema_version: int = 1

    # === Documentation Sources (Indexing Engine: Level 1 (Documentation): Level 1 Index) ===
    documentation_map: dict[str, list[str]] = {
        'solver_readme': ['README.rst', 'README.md'],
        'build_instructions': ['INSTALL.md', 'Docs/sphinx/BuildingSource.rst'],
    }
    """
    Extensible documentation source map (yt-project pattern).

    Keys: Logical index names (e.g., 'parameter_guides', 'problem_catalogs')
    Values: File paths/patterns relative to repo root or database/reports/

    Override in subclasses to add code-specific documentation:

    Example:
        class PeleCConfig(BaseAMReXConfig):
            documentation_map = {
                'solver_readme': ['README.rst'],
                'problem_catalogs': ['database/reports/report2.txt'],
                'parameter_guides': ['database/reports/report5.txt'],
                'sphinx_docs': ['Docs/sphinx/*.rst'],
            }

    The Level1Builder iterates these keys to create indices generically.
    No hardcoded index names in builder code.
    """

    # === Auxiliary Files (Indexing Engine: Build Metadata Extensions: Level 2 Extensions) ===
    auxiliary_patterns: list[str] = [
        '*.dat',           # Data files
        '*.txt',           # Text inputs
        'probin*',         # Fortran namelists
        'GNUmakefile',     # Build configuration
        'CMakeLists.txt',  # CMake build
        '*.cmake',         # CMake modules
    ]
    """
    Extensible auxiliary file patterns (yt-project pattern).

    Patterns are globs relative to case directory.
    Subclasses can override to add solver-specific files.

    Example:
        class PeleCConfig(BaseAMReXConfig):
            auxiliary_patterns = [
                '*.dat',
                'probin*',
                'GNUmakefile',
                'dodecane.dat',      # Pele-specific
                'chem_*.txt',        # Chemistry files
            ]

    Used by extract_metadata to discover auxiliary files.
    """

    # Inputs file search patterns (ordered by priority)
    # Base AMReX: conservative - just standard inputs files
    inputs_file_patterns: ClassVar[list[str]] = [
        'inputs',      # Exact match first
        'inputs*',     # inputs.2d, inputs.3d, inputs-pmf, etc.
    ]

    # === Prompt Templates ===
    remap_prompt_template: ClassVar[str] = """Map semantic parameter names to schema field aliases.

Failed parameters needing remapping:
{failed_list}

Available schema fields (alias + type + description):
{schema_list}

Format hints:
{format_hints}

TASK (for each failed parameter):
1) Identify the intent in the phrase/value (e.g., timesteps, grid cells, AMR levels).
2) Scan the schema list and choose the single closest match by meaning.
3) If no clear match exists, set "to": null.

Mapping guidance:
- "grid size", "grid cells", or "resolution" → prefer amr.n_cell (domain cell counts).
- amr.max_grid_size is for domain decomposition / mesh refinement control; use it only when explicitly asked.
- "timesteps" → amr.max_step (not max_dt).
- "AMR levels" → amr.max_level.

Return JSON: {{"mappings": [
  {{"from": "jet_diameter", "to": "prob.jet_rad", "transform": "divide_by_2", "formatted_value": null}},
  {{"from": "jet_composition", "to": "prob.jet_Y", "transform": null, "formatted_value": "H2:0.7 N2:0.18 He:0.12"}}
]}}

Supported transforms: null, "divide_by_2", "multiply_by_2"
If no match exists, set "to": null."""

    # Option D (two-stage remap) draft prompt — kept for future experimentation:
    # remap_prompt_template = """Map semantic parameter names to schema field aliases.
    #
    # Failed parameters needing remapping:
    # {failed_list}
    #
    # Available schema fields (alias + type + description):
    # {schema_list}
    #
    # Format hints:
    # {format_hints}
    #
    # TASK (two stages for each failed parameter):
    # Stage 1: Propose the 3 best candidate schema fields by name/meaning.
    # Stage 2: Choose the single best match and justify it using the schema description.
    # If no clear match exists, set "to": null.
    #
    # DOMAIN RULES:
    # - "grid size", "grid cells", "resolution" → prefer amr.n_cell (domain cell counts).
    # - amr.max_grid_size is for domain decomposition / refinement control; use only when explicitly asked.
    # - "timesteps" → amr.max_step (not max_dt).
    # - "AMR levels" → amr.max_level.
    #
    # Return JSON:
    # {
    #   "mappings": [
    #     {"from": "timesteps", "to": "amr.max_step", "transform": null, "formatted_value": null}
    #   ]
    # }
    #
    # Supported transforms: null, "divide_by_2", "multiply_by_2"
    # If no match exists, set "to": null."""

    # === Level 2 Index Keywords (Indexing Engine: Physics-Agnostic Keywords & Scoring: Physics-Agnostic) ===
    level2_index_keywords: dict[str, list[str]] = {
        'physics_parameters': [
            # Generic solver-agnostic terms
            'solver', 'algorithm', 'physics', 'model', 'simulation',
        ],
        'domain_models': [
            # Generic compile-time/feature terms (override per solver)
            'feature', 'module', 'compile', 'build',
        ],
        'grid_specifications': [
            'amr', 'geometry', 'grid', 'n_cell', 'refinement', 'domain',
        ],
        'path_hierarchy': [],  # Logic-based, not keyword-based
        'git_metrics': [],      # Metadata-based, not keyword-based
        'performance_estimates': [],  # Future: derived from logs
    }
    """
    Keyword filters for Level 2 sub-indices (yt-project pattern).

    Each sub-index uses keywords to filter inputs_content from Metadata Schema.
    Subclasses override with domain-specific terms.

    Example - Combustion (PeleC):
        level2_index_keywords = {
            'domain_models': ['chem', 'species', 'fuel', 'reaction'],
            'physics_parameters': ['pelec', 'combustion', 'flame', 'diffusion'],
        }

    Example - Plasma (WarpX):
        level2_index_keywords = {
            'domain_models': ['USE_MPI', 'USE_CUDA', 'algo'],  # Build features
            'physics_parameters': ['plasma', 'beams', 'laser', 'particles'],
        }

    Empty list [] means index uses non-keyword logic (e.g., path parsing).
    """

    # === Additional Indices (Indexing Engine: Physics-Agnostic Keywords & Scoring: Extensibility) ===
    additional_level2_indices: dict[str, dict[str, Any]] = {}
    """
    Domain-specific indices beyond the base 6 (PRD 5.4).

    Example:
        additional_level2_indices = {
            'diagnostic_outputs': {
                'weight': 0.05,
                'keywords': ['diag', 'output', 'plot'],
            }
        }

    Builder creates base 6 + additional indices.
    """

    # === Path Hierarchy Weights (Indexing Engine: Path Hierarchy Weights: Quality Scoring) ===
    path_weights: dict[str, float] = {
        'Production': 1.0,      # Production-ready cases
        'Exec': 0.9,            # Executable examples
        'Examples': 0.8,        # Tutorial examples
        'Tutorials': 0.8,       # Educational cases
        'RegTests': 0.5,        # Regression tests
        'Tests': 0.4,           # Unit tests
    }
    """
    Path quality weights (yt-project pattern).

    Defines what makes a "good" baseline case based on directory structure.
    Subclasses override to reflect code-specific conventions.

    Example - PeleC:
        path_weights = {
            'Production': 1.0,
            'Exec': 0.9,
            'Examples': 0.6,
        }

    Example - WarpX:
        path_weights = {
            'Examples': 1.0,           # WarpX prefers Examples
            'Physics_applications': 0.9,
            'Exec': 0.7,
        }
    """

    llm_prompt_templates: ClassVar[dict[str, str]] = {
        "schema_scan": """Identify requested concepts from the case description that do not map to known baseline or schema parameters.

Case Description:
{case_description}

Baseline Parameters (from inputs file):
{baseline_params}

Available Schema Parameters (truncated, {schema_param_count} total):
{schema_params}

TASK:
1. Extract all physics/simulation concepts from the case description:
   - Physical phenomena: turbulent, reacting, multiphase, compressible, radiative, etc.
   - Geometry features: channel, pipe, cavity, jet, inlet geometry, specific shapes
   - Boundary conditions: wall types, inlet/outlet characteristics, thermal conditions
   - Flow characteristics: velocity profiles (uniform, parabolic, turbulent), temperature distributions
   - Material properties: composition details, species, equation of state
   - Initial conditions: initialization methods, perturbations, fluctuations
   - Numerical methods: time integration, spatial schemes, turbulence models
   - Special features: particles, lagrangian tracers, adaptive mesh refinement levels
2. For EACH concept, check if it has parameter coverage:
   a. Look for EXACT or CLOSE parameter matches in baseline parameters
   b. Look for EXACT or CLOSE parameter matches in schema parameters
   c. Consider common parameter naming patterns:
      - Physics toggles: do_*, use_*, enable_*
      - Models: *_model, *_type, *_scheme
      - Properties: *_velocity, *_temp, *_composition, *_profile
      - Numerics: *_integrator, *_solver, *_order
3. Flag as "unresolved" ONLY if:
   - The concept is EXPLICITLY stated in the case description (not just implied)
   - It represents a specific value, model choice, or configuration requirement
   - NO matching parameter exists in baseline OR schema parameters
   - It is NOT a generic restatement of existing parameters
4. DO NOT flag as unresolved if:
   - The concept is already captured by existing baseline parameters
   - It is a general physics description that maps to multiple existing parameters
   - It is a derived quantity or output (not an input)
   - It is describing the problem context rather than a configuration requirement
5. Format unresolved concepts as short, specific noun phrases:
   - Include key details: "turbulent fluctuations 5%", "parabolic velocity profile"
   - Avoid vague terms: instead of "special inlet", use "inlet with 5% turbulence intensity"
   - Reference specific values when stated: "turbulence intensity 5%", "parabolic profile"

EXAMPLES:

Should be flagged:
- "turbulent fluctuations 5%" - if no parameter like inflow_turbulence_intensity exists
- "specific turbulence model" - if no turbulence model parameter exists
- "parabolic velocity profile" - if only uniform profiles are supported
- "radiation heat transfer" - if no radiation toggle/model parameter exists

Should NOT be flagged:
- "channel flow" - this is geometry (covered by domain bounds + BCs)
- "atmospheric pressure" - covered by existing pressure parameter
- "jet diameter 3mm" - covered by existing geometry parameter
- "inlet temperature 300 K" - covered by existing temperature parameter
- "DNS simulation" - this describes the approach, not a specific parameter requirement

CRITICAL RULES:
- Be conservative: only flag truly missing capabilities
- Prioritize actionable, specific concepts over general descriptions
- If a concept might be achievable through parameter combinations, do not flag it
- Focus on what is explicitly requested, not what might be implied

Return JSON:
{{
  "unresolved_concepts": [
    "turbulent fluctuations 5%"
  ],
  "notes": "Optional brief note"
}}""",
        "modification_extraction": """Extract parameter modifications needed for this simulation case.

Case Description:
{case_description}

Baseline Input File:
```
{inputs_content}
```

{param_guidance}

TASK - work through step-by-step:
1. Identify each physics value in the case description (pressure, velocities, temperatures, compositions, dimensions)
2. For EACH value:
   a. Find the EXACT corresponding parameter name in the baseline file OR valid parameters list
   b. Convert units if needed - show your work:
      - atm -> Pa: multiply by 101325
      - mm -> m: divide by 1000
      - cm -> m: divide by 100
      - diameter -> radius: divide by 2
      - percentage -> fraction: divide by 100
   c. Determine if value differs from baseline
3. Only include parameters that DIFFER from baseline or must be ADDED

4. PHYSICS CONSISTENCY CHECK (brief):
   - Identify the physical configuration in a few words (e.g., channel, jet, cavity).
   - Verify BCs/geometry/periodicity align with that type.
   - If mismatched, adjust parameters only when a clear input mapping exists.

CRITICAL RULES:
- Use parameter names EXACTLY as shown in the baseline input file or valid parameters list (including prefix like "prob."). The list is a priority aid, not exhaustive.
- If you cannot find an exact match in either place, SKIP that modification
- Never invent, modify, or abbreviate parameter names
- For grid resolution requests ("grid cells", "grid size", "resolution"), prefer amr.n_cell (domain cell counts).
- amr.max_grid_size is for domain decomposition / refinement control; use it only when explicitly requested.

Return JSON with your working and results:
{{
  "working": "Step-by-step analysis: 1) Found pressure=1atm -> prob.P_mean, 1*101325=101325Pa. 2) Found jet_velocity=42.2m/s -> prob.jet_velocity (matches baseline, skip). 3) ...",
  "modifications": [
    {{"parameter": "prob.P_mean", "value": "101325"}}
  ]
}}""",
            "kb_relevance_rating": """Rate each example case for this simulation request.

USER WANTS: {user_prompt}

Problem characteristics:
- Type: {problem_type}
- Dimensionality: {dimensionality}
- Physics: {physics}
- Solver: {code_name}

CASES TO RATE:
{cases_list}

RATING SCALE (0-10):
- 9-10: Excellent match (same problem type, physics, dimensionality)
- 7-8:  Good match (similar physics, minor differences)
- 5-6:  Moderate (same domain, different problem)
- 3-4:  Poor match (different physics or regime)
- 0-2:  Unrelated

RETURN ONLY a JSON object with case names and numeric scores:
{{"FlameSheet": 8, "TaylorGreen": 3, "NormalJet": 5, ...}}

No explanation, just the JSON.""",
            "structured_fallback_planning": """Complete this simulation plan by proposing parameter modifications.

USER REQUEST:
{query}

BASELINE CASE: {baseline_case}
SOLVER: {solver_name}

BASELINE PARAMETERS:
{baseline_summary}

TASK:
Generate a SimulationPlan with:
- modifications: List of (parameter_name, new_value) tuples to apply
- reasoning: Technical justification for your modifications
- cbr_confidence: Your confidence in these modifications (0.0-1.0)

Use actual parameter names from baseline with namespace prefixes (e.g., 'amr.n_cell', 'geometry.prob_extent').
Set solver_confidence=1.0 and baseline_confidence=1.0 (already determined).
""",
    }

    prompt_templates: ClassVar[dict[str, Any]] = {
        "knowledge": knowledge_prompt_templates,
        "cases": {"selection_prompt": case_selection_prompt},
        "misc": misc_prompts,
        "remap": {"template": remap_prompt_template},
        "architect": llm_prompt_templates,
    }

    @classmethod
    def _deep_merge_prompt_templates(
        cls, base: dict[str, Any], overrides: dict[str, Any]
    ) -> dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in overrides.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = cls._deep_merge_prompt_templates(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    @classmethod
    def get_prompt_templates(cls) -> dict[str, Any]:
        """
        Return normalized prompt templates.

        Call context: Used by LLM prompt assembly pipelines.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any]
            Merged prompt templates for this solver.
        """
        return cls._deep_merge_prompt_templates(
            BaseAMReXConfig.prompt_templates,
            getattr(cls, "prompt_templates", {}),
        )

    @classmethod
    def get_llm_prompt_templates(cls) -> dict[str, str]:
        """
        Return LLM prompt templates (ASCII-only).

        Call context: Used by LLM prompt generation for workflows.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, str]
            LLM prompt templates for this solver.
        """
        return cls.get_prompt_templates().get("architect", {})


    @classmethod
    def find_inputs_files(cls, case_dir: Path) -> list[Path]:
        """
        Find inputs files in case directory using solver-specific patterns.

        Call context: Used during case discovery and metadata extraction.

        Parameters
        ----------
        cls : type
            Config class.
        case_dir : pathlib.Path
            Path to the case directory.

        Returns
        -------
        list[pathlib.Path]
            Inputs file paths in priority order.
        """
        files = []
        for pattern in cls.inputs_file_patterns:
            if '*' in pattern:
                files.extend(case_dir.glob(pattern))
            else:
                exact = case_dir / pattern
                if exact.exists():
                    files.append(exact)
        return files

    @classmethod
    def score_path(cls, case_path: str) -> float:
        """
        Return quality score (0-1) based on path segments.

        Call context: Used to rank candidate cases in selection flows.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : str
            Relative path to a case (e.g., "Exec/Production/PMF").

        Returns
        -------
        float
            Quality score between 0.0 and 1.0.

        Examples
        --------
        >>> PeleCConfig.score_path('Exec/Production/PMF')
        1.0
        >>> PeleCConfig.score_path('Exec/RegTests/Test')
        0.5
        """
        for key, score in cls.path_weights.items():
            if key in case_path:
                return score
        return 0.3  # Default for unknown paths





    @classmethod
    def is_valid_case(cls, directory: Path) -> bool:
        """
        Check if directory contains a valid AMReX case.

        Call context: Used by case discovery to validate candidates.

        Parameters
        ----------
        cls : type
            Config class.
        directory : pathlib.Path
            Path to check.

        Returns
        -------
        bool
            True if the directory contains inputs files.
        """
        if not directory.is_dir():
            return False

        patterns = list(getattr(cls, "inputs_file_patterns", [])) or [
            'inputs*',
            '*.inp',
            '*.inputs',
        ]
        has_inputs = any(any(directory.glob(pattern)) for pattern in patterns)

        return has_inputs

    @classmethod
    def scan_for_cases(cls, source_dir: Path) -> list[Path]:
        """
        Find all case directories using this config's search patterns.

        This is the polymorphic scanning method that replaces hardcoded
        if/elif logic in utils.py and services/cases.py.

        Call context: Used by discovery services to enumerate cases.

        Parameters
        ----------
        cls : type
            Config class.
        source_dir : pathlib.Path
            Root directory to scan (e.g., "/path/to/PeleC").

        Returns
        -------
        list[pathlib.Path]
            Sorted list of case directories.

        Examples
        --------
        >>> pelec_cases = PeleCConfig.scan_for_cases(Path("/codes/PeleC"))
        >>> print(pelec_cases[0])
        /codes/PeleC/Exec/RegTests/PMF
        """
        if not source_dir.exists():
            return []

        case_dirs = set()

        # Use patterns defined by this config class
        for pattern in cls.search_patterns:
            for path in source_dir.glob(pattern):
                # Delegate validation to is_valid_case
                if cls.is_valid_case(path):
                    case_dirs.add(path)

        # Return sorted for deterministic ordering
        return sorted(case_dirs)

    @classmethod
    def examples_catalog(cls) -> dict[str, str]:
        """
        Return example catalog for this solver.

        Call context: Used by example selection and fetch workflows.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, str]
            Mapping of example name to repo-relative inputs path.
        """
        return dict(cls.example_catalog)

    @classmethod
    def fetch_example(cls,
                      example_name: str,
                      save_dir: Path | None = None,
                      force_download: bool = False,
                      version: str = "development",
                      repo_root: Path | None = None) -> dict[str, Any] | None:
        """
        Fetch a solver example inputs file using the config's catalog.

        Returns metadata dict with file info instead of just Path.

        Call context: Used by example-loading helpers and CLI flows.

        Parameters
        ----------
        cls : type
            Config class.
        example_name : str
            Example catalog key to fetch.
        save_dir : pathlib.Path or None, optional
            Directory where the example should be written.
        force_download : bool, optional
            If True, re-download even when cached locally.
        version : str, optional
            Git ref to fetch from GitHub when needed.
        repo_root : pathlib.Path or None, optional
            Repository root used for local file resolution.

        Returns
        -------
        dict[str, Any] or None
            Metadata for the fetched example, or None on failure.
        """
        examples = cls.examples_catalog()
        if example_name not in examples:
            logger.error(f"[ERROR] Unknown example: {example_name}")
            logger.debug(f"Available examples: {list(examples.keys())}")
            return None

        save_dir = Path.cwd() if save_dir is None else Path(save_dir)

        save_path = Path(save_dir) / f"inputs.{example_name}"
        repo_path = Path(examples[example_name])

        if save_path.exists() and not force_download:
            content = save_path.read_text()
            checksum = hashlib.sha256(content.encode()).hexdigest()[:8]
            return {
                'local_path': save_path,
                'example_name': example_name,
                'repo_path': str(repo_path),
                'version': version,
                'source': 'cached',
                'checksum': checksum,
            }

        if repo_root:
            repo_root = Path(repo_root)
            local_source = repo_root / repo_path
            if local_source.exists():
                content = local_source.read_text()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(content)
                checksum = hashlib.sha256(content.encode()).hexdigest()[:8]
                return {
                    'local_path': save_path,
                    'example_name': example_name,
                    'repo_path': str(repo_path),
                    'version': 'local',
                    'source': 'local_repo',
                    'checksum': checksum,
                }

        try:
            from github import Github
        except ImportError:
            logger.error("[ERROR] PyGithub not installed - cannot fetch examples")
            return None

        if not cls.github_org:
            logger.error("[ERROR] GitHub org not configured for example fetch")
            return None

        repo_name = cls.github_repo or cls.code_name
        logger.info(f"Fetching {example_name} from {repo_name}/{repo_path}")

        try:
            g = Github()
            repo = g.get_repo(f"{cls.github_org}/{repo_name}")

            try:
                file_content = repo.get_contents(str(repo_path), ref=version)
                used_version = version
            except Exception:
                logger.warning(f"[WARN] Ref {version} not found, trying development")
                file_content = repo.get_contents(str(repo_path), ref="development")
                used_version = "development"

            content = file_content.decoded_content.decode('utf-8')

            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(content)

            checksum = hashlib.sha256(content.encode()).hexdigest()[:8]

            return {
                'local_path': save_path,
                'example_name': example_name,
                'repo_path': str(repo_path),
                'version': used_version,
                'source': 'github',
                'checksum': checksum,
            }
        except Exception as e:
            logger.error(f"[ERROR] Could not fetch: {e}")
            return None


    faiss_indices: list[str] = []
    """FAISS index names for this code (overridden in subclasses)"""

    # Common AMReX parameters across all codes
    COMMON_PARAMS = [
        # Geometry
        'geometry.prob_lo',
        'geometry.prob_hi',
        'geometry.is_periodic',
        'geometry.coord_sys',
        # AMR hierarchy
        'amr.n_cell',
        'amr.max_level',
        'amr.ref_ratio',
        'amr.regrid_int',
        'amr.blocking_factor',
        'amr.max_grid_size',
        'amr.n_error_buf',
        'amr.grid_eff',
        # Time stepping
        'max_step',
        'stop_time',
        # I/O
        'amr.plot_file',
        'amr.plot_int',
        'amr.check_file',
        'amr.check_int',
        # Verbosity
        'amr.v',
    ]


    @classmethod
    def parse_inputs(cls, inputs_text: str) -> dict[str, str]:
        r"""
        Parse AMReX inputs file into structured dictionary.

        Handles standard ``key = value`` pairs, inline comments, namespaced
        parameters, extra whitespace, and empty lines.

        Call context: Used when parsing inputs files for metadata extraction.

        Parameters
        ----------
        cls : type
            Config class.
        inputs_text : str
            Raw contents of an inputs file.

        Returns
        -------
        dict[str, str]
            Mapping of parameter name to string value.

        Examples
        --------
        >>> text = "amr.n_cell = 64 64 64  # Grid size\nmax_step=100"
        >>> parsed = BaseAMReXConfig.parse_inputs(text)
        >>> print(parsed["amr.n_cell"])
        64 64 64
        >>> print(parsed["max_step"])
        100
        """
        parsed = {}

        # Process line by line
        for line in inputs_text.split('\n'):
            # Strip whitespace
            line = line.strip()

            # Skip empty lines and comment-only lines
            if not line or line.startswith('#'):
                continue

            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0].strip()

            # Look for key = value pattern
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key and value:
                    parsed[key] = value

        return parsed

    @classmethod
    def extract_metadata(cls, case_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
        """
        Extract complete metadata for a case directory.

        Implements Metadata Schema schema:
        - Amendment B: Portable repo_path identifier
        - Amendment C: Full inputs_content parsing
        - Level 2 metadata: Grid, Physics, Path

        Call context: Used by case indexing and metadata services.

        Parameters
        ----------
        cls : type
            Config class.
        case_path : pathlib.Path
            Path to the case directory.
        repo_root : pathlib.Path or None, optional
            Repository root (for portable paths).

        Returns
        -------
        dict[str, Any]
            Complete metadata dictionary for indexing.

        Notes
        -----
        Schema includes portable identifiers, parsed inputs content, and
        auxiliary file metadata.
        """
        metadata = {}

        # 1. Identity and paths
        metadata['case_name'] = case_path.name


        # Portable path (Amendment B)
        if repo_root:
            try:
                relative = case_path.relative_to(repo_root)
                metadata['repo_path'] = str(relative)
                metadata['case_path'] = metadata['repo_path']  # Indexing Engine: Path Standards Enforcement: Relative path
            except ValueError:
                # case_path not under repo_root
                metadata['repo_path'] = f"Exec/{case_path.name}"
        else:
            # Infer from path structure
            parts = case_path.parts
            if 'Exec' in parts:
                exec_idx = parts.index('Exec')
                metadata['repo_path'] = str(Path(*parts[exec_idx:]))
            else:
                metadata['repo_path'] = f"Exec/{case_path.name}"
        metadata['case'] = metadata['repo_path']  # Legacy compatibility - aliased to repo_path (Phase 1)

        # Absolute path (for file operations)
        metadata['local_path'] = str(case_path.absolute())
        metadata['absolute_path'] = str(case_path.absolute())  # Alias

        # 2. Registry metadata (from class attributes - Cases Service: Config-Driven Discovery)
        metadata['code_name'] = cls.code_name
        metadata['code'] = cls.code_name  # Alias

        if hasattr(cls, 'github_org'):
            metadata['github_org'] = cls.github_org
        if hasattr(cls, 'github_repo'):
            metadata['github_repo'] = cls.github_repo
        if hasattr(cls, 'description'):
            metadata['description'] = cls.description

        # 3. Parse inputs file (Amendment C)
        inputs_file = cls._find_inputs_file(case_path)
        if inputs_file and inputs_file.exists():
            try:
                inputs_text = inputs_file.read_text()

                # Parse into structured dict (Amendment C)
                inputs_dict = cls.parse_inputs(inputs_text)
                metadata['inputs_content'] = inputs_dict

                # Extract key parameters for Level 2 indexing
                # Grid configuration
                if 'amr.n_cell' in inputs_dict:
                    metadata['n_cell'] = inputs_dict['amr.n_cell']

                # Common parameters
                for key in ['max_step', 'stop_time', 'amr.max_level', 'geometry.prob_lo', 'geometry.is_periodic']:
                    if key in inputs_dict:
                        # Store both with and without namespace
                        metadata[key] = inputs_dict[key]
                        # Also store short form if namespaced
                        if '.' in key:
                            short_key = key.split('.')[-1]
                            if short_key not in metadata:
                                metadata[short_key] = inputs_dict[key]

                # Code-specific parameters (preserve namespace)
                for key, value in inputs_dict.items():
                    if key.startswith(f'{cls.code_name.lower()}.'):
                        metadata[key] = value

            except Exception as e:
                logger.debug(f"Warning: Could not parse {inputs_file}: {e}")
                metadata['inputs_content'] = {}
        else:
            metadata['inputs_content'] = {}

        # 4. Auxiliary files
        # Discover auxiliary files using class patterns
        metadata['auxiliary_files'] = []
        for pattern in cls.auxiliary_patterns:
            for aux_file in case_path.glob(pattern):
                if aux_file.is_file():
                    metadata['auxiliary_files'].append(aux_file.name)

        metadata['auxiliary_file_details'] = []

        for pattern in ['*.dat', '*.txt', 'probin*']:
            for aux_file in case_path.glob(pattern):
                if aux_file.is_file():
                    metadata['auxiliary_files'].append(aux_file.name)

        return metadata


    @classmethod
    def _parse_inputs_file(cls, inputs_path: Path) -> dict[str, str]:
        """
        Parse AMReX inputs file.

        Format is consistent across all AMReX codes:
            parameter = value  # optional comment

        Args:
            inputs_path: Path to inputs file

        Returns
        -------
            Dictionary mapping parameter names to values (as strings)
        """
        params = {}

        try:
            with open(inputs_path) as f:
                for line in f:
                    # Remove comments
                    line = line.split('#')[0].strip()

                    # Skip empty lines
                    if not line:
                        continue

                    # Parse parameter = value
                    if '=' in line:
                        param, val = line.split('=', 1)
                        params[param.strip()] = val.strip()

        except Exception as e:
            logger.debug(f"Warning: Could not parse {inputs_path}: {e}")

        return params

    @classmethod
    def _find_inputs_file(cls, case_path: Path) -> Path | None:
        """
        Find inputs file in case directory.

        Searches for common patterns:
        - inputs*
        - *.inp
        - probin* (Fortran parameter files)

        Args:
            case_path: Path to case directory

        Returns
        -------
            Path to inputs file, or None if not found
        """
        # Try configured input file patterns
        patterns = list(getattr(cls, "inputs_file_patterns", []))
        if not patterns:
            patterns = ['inputs*']
        for pattern in patterns:
            files = list(case_path.glob(pattern))
            if files:
                # Prefer files named exactly "inputs" or shortest match
                exact_match = [f for f in files if f.name == 'inputs']
                if exact_match:
                    return exact_match[0]
                return sorted(files, key=lambda f: len(f.name))[0]

        # Recursively check subdirectories (common in tutorials)
        for subdir in ['Exec', 'exec', 'run']:
            subpath = case_path / subdir
            if subpath.exists():
                result = cls._find_inputs_file(subpath)
                if result:
                    return result

        return None

    @classmethod
    def _extract_case_type(cls, case_path: Path) -> str:
        """
        Extract case type from directory path.

        Args:
            case_path: Path to case directory

        Returns
        -------
            Case type string: 'regression_test', 'production', 'tutorial', etc.
        """
        parts = case_path.parts

        if 'RegTests' in parts or 'RegTest' in parts:
            return 'regression_test'
        elif 'Production' in parts:
            return 'production'
        elif 'Tests' in parts or 'Test' in parts:
            return 'test'
        elif 'Tutorials' in parts or 'ExampleCodes' in parts:
            return 'tutorial'
        elif 'Exec' in parts:
            return 'executable'
        else:
            return 'unknown'

    @classmethod
    def _extract_cfl(cls, params: dict[str, str]) -> float | None:
        """
        Extract CFL number from parameters.

        Different codes use different parameter names:
        - cns.cfl (PeleC)
        - adv.cfl (advection)
        - pelec.cfl
        - etc.

        Args:
            params: Parsed parameters dict

        Returns
        -------
            CFL number as float, or None if not found
        """
        # Try common CFL parameter names
        cfl_params = [k for k in params if k.endswith('.cfl') or k == 'cfl']

        for param in cfl_params:
            val = params.get(param)
            if val:
                return cls._parse_float(val)

        return None

    @classmethod
    def _extract_geometry(cls, params: dict[str, str]) -> dict[str, Any] | None:
        """
        Extract geometry information from parameters.

        Args:
            params: Parsed parameters dict

        Returns
        -------
            Dictionary with geometry info, or None
        """
        if not any(k.startswith('geometry.') for k in params):
            return None

        return {
            'prob_lo': params.get('geometry.prob_lo'),
            'prob_hi': params.get('geometry.prob_hi'),
            'is_periodic': params.get('geometry.is_periodic'),
            'coord_sys': params.get('geometry.coord_sys'),
        }

    @classmethod
    def get_domain_data(cls) -> dict[str, Any]:
        """
        Get code-specific domain data.

        Override in subclasses for domain-specific dictionaries.

        Call context: Used by domain knowledge selection and ranking logic.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, Any]
            Empty dict for base class; subclasses return domain data.
        """
        return {}

    @classmethod
    def validate_config(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Run AMReX-generic validation checks on a config dict.

        Subclasses can override validate_physics/validate_grid/validate_completeness
        for solver-specific logic.

        Call context: Used by config validation pipelines prior to execution.

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
        violations.extend(cls.validate_completeness(config_dict))
        violations.extend(cls.validate_grid(config_dict))
        violations.extend(cls.validate_physics(config_dict))
        return violations

    @classmethod
    def validate_completeness(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Check for required sections and basic completeness.

        Call context: Used by config validation to detect missing inputs.

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

        for section in ["geometry", "amr"]:
            if section not in config_dict or not config_dict.get(section):
                violations.append(RuleViolation(
                    rule_name="RequiredSection",
                    severity="error",
                    parameter=section,
                    message=f"Missing required section: {section}"
                ))

        geom = config_dict.get("geometry", {})
        if geom:
            if "prob_lo" not in geom:
                violations.append(RuleViolation(
                    rule_name="GeometryBounds",
                    severity="error",
                    parameter="geometry.prob_lo",
                    message="geometry.prob_lo not specified"
                ))
            if "prob_hi" not in geom:
                violations.append(RuleViolation(
                    rule_name="GeometryBounds",
                    severity="error",
                    parameter="geometry.prob_hi",
                    message="geometry.prob_hi not specified"
                ))
            if "is_periodic" not in geom:
                violations.append(RuleViolation(
                    rule_name="BoundaryCondition",
                    severity="warning",
                    parameter="geometry.is_periodic",
                    message="geometry.is_periodic not specified (default may be wrong)"
                ))

        amr = config_dict.get("amr", {})
        if amr and "n_cell" not in amr:
            violations.append(RuleViolation(
                rule_name="GridResolution",
                severity="error",
                parameter="amr.n_cell",
                message="amr.n_cell not specified (grid resolution)"
            ))

        has_max_step = "max_step" in config_dict or "max_step" in amr
        has_stop_time = "stop_time" in config_dict or "stop_time" in amr
        if not has_max_step and not has_stop_time:
            violations.append(RuleViolation(
                rule_name="TimestepBounds",
                severity="warning",
                parameter="max_step",
                message="Neither max_step nor stop_time specified"
            ))

        return violations

    @classmethod
    def validate_grid(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate AMReX grid consistency checks.

        Call context: Used by config validation before execution.

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

        amr = config_dict.get("amr", {})
        if not amr:
            return violations

        def _parse_int_list(value: Any) -> list[int] | None:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                try:
                    return [int(v) for v in value]
                except (TypeError, ValueError):
                    return None
            if isinstance(value, str):
                try:
                    return [int(v) for v in value.split()]
                except ValueError:
                    return None
            return None

        def _parse_float_list(value: Any) -> list[float] | None:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                try:
                    return [float(v) for v in value]
                except (TypeError, ValueError):
                    return None
            if isinstance(value, str):
                try:
                    return [float(v) for v in value.split()]
                except ValueError:
                    return None
            return None

        schema_defaults = cls._load_schema_defaults()
        blocking = (
            cls._parse_int(amr.get("blocking_factor"))
            or cls._parse_int(schema_defaults.get("amr.blocking_factor"))
            or 16
        )
        max_grid = (
            cls._parse_int(amr.get("max_grid_size"))
            or cls._parse_int(schema_defaults.get("amr.max_grid_size"))
            or 32
        )
        if max_grid % blocking != 0:
            violations.append(RuleViolation(
                rule_name="GridConsistency",
                severity="error",
                parameter="amr.max_grid_size",
                message=f"max_grid_size ({max_grid}) must be divisible by blocking_factor ({blocking})"
            ))

        n_cell = _parse_int_list(amr.get("n_cell"))
        if n_cell:
            for idx, cells in enumerate(n_cell):
                if cells % blocking != 0:
                    violations.append(RuleViolation(
                        rule_name="GridConsistency",
                        severity="error",
                        parameter=f"amr.n_cell[{idx}]",
                        message=(
                            f"n_cell[{idx}]={cells} must be divisible by "
                            f"blocking_factor ({blocking})"
                        )
                    ))

        max_level = cls._parse_int(amr.get("max_level")) or 0
        if max_level > 3 and n_cell:
            base_cells = 1
            for n in n_cell:
                base_cells *= n
            dim = len(n_cell) if n_cell else 3
            multiplier = (2 ** dim) ** max_level
            max_cells = base_cells * multiplier
            violations.append(RuleViolation(
                rule_name="GridScale",
                severity="warning",
                parameter="amr.max_level",
                message=f"max_level={max_level} is high. Max cells: {max_cells:,}"
            ))
            if max_cells > 1e10:
                violations.append(RuleViolation(
                    rule_name="GridScale",
                    severity="error",
                    parameter="amr.max_level",
                    message=f"Max cells ({max_cells:,}) exceeds reasonable limit"
                ))

        ref_ratio = _parse_int_list(amr.get("ref_ratio"))
        if ref_ratio and any(r != 2 for r in ref_ratio):
            violations.append(RuleViolation(
                rule_name="RefinementRatio",
                severity="warning",
                parameter="amr.ref_ratio",
                message=f"ref_ratio contains non-2 values: {ref_ratio}"
            ))

        geom = config_dict.get("geometry", {})
        if geom:
            prob_lo = _parse_float_list(geom.get("prob_lo"))
            prob_hi = _parse_float_list(geom.get("prob_hi"))
            if prob_lo and prob_hi and len(prob_lo) == len(prob_hi):
                if any(hi <= lo for hi, lo in zip(prob_hi, prob_lo, strict=True)):
                    violations.append(RuleViolation(
                        rule_name="GeometryBounds",
                        severity="error",
                        parameter="geometry.prob_hi",
                        message="prob_hi must be > prob_lo in all dimensions"
                    ))
            elif prob_lo and prob_hi and len(prob_lo) != len(prob_hi):
                violations.append(RuleViolation(
                    rule_name="GeometryBounds",
                    severity="error",
                    parameter="geometry.prob_hi",
                    message="prob_lo and prob_hi dimensions mismatch"
                ))

        return violations

    @classmethod
    def validate_physics(cls, config_dict: dict[str, Any]) -> list[RuleViolation]:
        """
        Run solver-specific physics checks.

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
        return []

    @classmethod
    def _load_schema_defaults(cls) -> dict[str, Any]:
        """Load defaults from the latest available schema, if present."""
        cache = getattr(cls, "_schema_defaults_cache", None)
        if cache is not None:
            return cache

        schema_dir = Path(__file__).parent.parent / "schemas"
        pattern = getattr(cls, "schema_pattern", None)
        if pattern:
            matches = list(schema_dir.glob(pattern))
        else:
            matches = list(schema_dir.glob(f"{cls.code_name.lower()}_schema_*.json"))

        if not matches:
            cls._schema_defaults_cache = {}
            return {}

        latest = max(matches, key=lambda p: p.stat().st_mtime)
        try:
            with latest.open() as handle:
                schema_data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            cls._schema_defaults_cache = {}
            return {}

        params = schema_data.get("parameters", schema_data)
        defaults = {}
        if isinstance(params, dict):
            for name, spec in params.items():
                if isinstance(spec, dict) and spec.get("default") is not None:
                    defaults[name] = spec["default"]

        cls._schema_defaults_cache = defaults
        return defaults

    @classmethod
    def get_faiss_indices(cls) -> list[str]:
        """
        Get FAISS index names for this code.

        Call context: Used by vector index builders and search services.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        list[str]
            FAISS index names for this solver.
        """
        return cls.faiss_indices

    # Utility parsing methods

    @staticmethod
    def _parse_int(val: str | None) -> int | None:
        """Parse integer value safely."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_float(val: str | None) -> float | None:
        """Parse float value safely."""
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_bool(val: str | None) -> bool | None:
        """Parse boolean value safely."""
        if val is None:
            return None
        val_lower = val.lower().strip()
        if val_lower in ['1', 'true', 't', 'yes', 'y']:
            return True
        elif val_lower in ['0', 'false', 'f', 'no', 'n']:
            return False
        return None

    @classmethod
    def _get_repo_relative_path(cls, case_dir: Path) -> str:
        """
        Get path relative to repo root.

        Converts:
          /global/.../PeleC/Exec/RegTests/PMF → Exec/RegTests/PMF
          ../PeleLMeX/Exec/Production/FlameSheet → Exec/Production/FlameSheet

        Returns portable path that works regardless of where repo is cloned.

        Args:
            case_dir: Full path to case directory

        Returns
        -------
            Repo-relative path (e.g., "Exec/RegTests/PMF")
        """
        path_str = str(case_dir)
        parts = case_dir.parts

        # Find where code name appears in path
        code_name = cls.code_name
        for i, part in enumerate(parts):
            if part == code_name:
                # Return everything after CodeName/
                rel_parts = parts[i+1:]
                if rel_parts:
                    return str(Path(*rel_parts))

        # Fallback: look for Exec/ directory
        if 'Exec/' in path_str:
            idx = path_str.find('Exec/')
            return path_str[idx:]
        elif 'exec/' in path_str.lower():
            idx = path_str.lower().find('exec/')
            return path_str[idx:]

        # Last resort: return name only
        return case_dir.name

    @classmethod
    def _get_repo_root(cls, case_dir: Path) -> str | None:
        """
        Get repository root path.

        Finds the code directory in the path and returns full path to it.

        Args:
            case_dir: Full path to case directory

        Returns
        -------
            Absolute path to repo root (e.g., "/global/.../PeleC")
            or None if not found
        """
        parts = case_dir.parts
        code_name = cls.code_name

        # Find where code name appears
        for i, part in enumerate(parts):
            if part == code_name:
                # Return path up to and including code name
                return str(Path(*parts[:i+1]))

        return None

    # === File Generation Metadata (AMReX-Generic) ===
    @classmethod
    def resolve_executable_path(cls, app_config: Any | None) -> str | None:
        """
        Return default executable path for this solver.

        Call context: Used when assembling run commands or job scripts.

        Parameters
        ----------
        cls : type
            Config class.
        app_config : Any or None
            Application config object with repository mappings.

        Returns
        -------
        str or None
            Resolved executable path, or None if unavailable.
        """
        if not app_config:
            return None
        repo_root = None
        if hasattr(app_config, "repositories"):
            repo_root = app_config.repositories.get(cls.code_name)
        if (
            not repo_root
            and getattr(cls, "default_exec_repo_path", None)
            and Path(cls.default_exec_repo_path).is_absolute()
        ):
            # Allow absolute default_exec_repo_path without repo_root
            repo_root = ""
        if repo_root is None or not getattr(cls, "default_exec_repo_path", None):
            return None

        base_path = Path(repo_root) / cls.default_exec_repo_path if repo_root else Path(cls.default_exec_repo_path)
        if base_path.is_file() and base_path.exists():
            return str(base_path)

        if base_path.is_dir():
            pattern = cls.default_exec_pattern or "*.ex"
            pattern = pattern.format(code=cls.code_name, code_lower=cls.code_name.lower())
            matches = sorted(base_path.glob(pattern))
            if matches:
                return str(matches[0])

        return None

    @classmethod
    def resolve_default_inputs_path(cls, repo_root: Path | None) -> Path | None:
        """
        Resolve default inputs path against repo root.

        Call context: Used when selecting baseline inputs for new runs.

        Parameters
        ----------
        cls : type
            Config class.
        repo_root : pathlib.Path or None
            Repository root for relative resolution.

        Returns
        -------
        pathlib.Path or None
            Resolved inputs path, or None if not configured.
        """
        if cls.default_inputs_path:
            path = Path(cls.default_inputs_path)
            if not path.is_absolute() and repo_root:
                path = Path(repo_root) / path
            return path
        if cls.default_baseline_dir:
            base = Path(cls.default_baseline_dir)
            if not base.is_absolute() and repo_root:
                base = Path(repo_root) / base
            return base / "inputs"
        return None

    @classmethod
    def get_slurm_metadata(cls) -> dict[str, str]:
        """
        Return SLURM metadata defaults for this solver.

        Call context: Used by job-script generators.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        dict[str, str]
            SLURM metadata (job_name, display_name).
        """
        return {
            "job_name": f"{cls.code_name.lower()}_sim",
            "display_name": cls.code_name,
        }

    @classmethod
    def get_readme_title(cls) -> str:
        """
        Return README title for this solver.

        Call context: Used by README generation.

        Parameters
        ----------
        cls : type
            Config class.

        Returns
        -------
        str
            README title string.
        """
        return f"{cls.code_name} Simulation"

    @classmethod
    def get_readme_summary_lines(cls, config: dict[str, Any]) -> list[str]:
        """
        Build README summary lines for a config.

        Call context: Used by README generation.

        Parameters
        ----------
        cls : type
            Config class.
        config : dict[str, Any]
            Parsed configuration dictionary.

        Returns
        -------
        list[str]
            Summary lines describing grid and domain.
        """
        geometry = config.get("geometry", {})
        amr = config.get("amr", {})

        prob_lo = cls._format_vector(geometry.get("prob_lo", "?"))
        prob_hi = cls._format_vector(geometry.get("prob_hi", "?"))
        n_cell = cls._format_vector(amr.get("n_cell", "unknown"))
        max_level = amr.get("max_level", "0")
        dims = cls._infer_dims(prob_lo, n_cell)

        summary = []
        if dims:
            summary.append(f"Dimensions: {dims}D")
        summary.append(f"Grid: {n_cell}")
        summary.append(f"AMR Levels: {max_level}")
        summary.append(f"Domain: {prob_lo} -> {prob_hi}")
        return summary

    @classmethod
    def get_readme_solver_lines(cls, config: dict[str, Any]) -> list[str]:
        """
        Build solver-specific README lines.

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
        return []

    @classmethod
    def estimate_resources(cls, config: dict[str, Any], system: str = "perlmutter") -> dict[str, Any]:
        """
        Estimate resource usage for a configuration.

        Call context: Used by planning tools to size runs.

        Parameters
        ----------
        cls : type
            Config class.
        config : dict[str, Any]
            Parsed configuration dictionary.
        system : str, optional
            System name used to select hardware assumptions.

        Returns
        -------
        dict[str, Any]
            Resource estimates (nodes, memory, walltime, etc.).
        """
        amr = config.get("amr", {})
        n_cell = cls._parse_vector(amr.get("n_cell", "64 64 64"))
        max_level = int(amr.get("max_level", 0) or 0)

        base_cells = int(math.prod(n_cell)) if n_cell else 0
        dims = len(n_cell) if n_cell else 0
        refinement_factor = 2 ** max_level
        max_cells = int(base_cells * (refinement_factor ** dims)) if dims else base_cells

        bytes_per_cell = cls._resource_bytes_per_cell(config)
        memory_gb = (max_cells * bytes_per_cell * 1.2) / 1e9 if max_cells else 0.0

        system_specs = {
            "perlmutter": {"mem_per_node": 512, "cores_per_node": 128, "gpus_per_node": 4},
            "frontier": {"mem_per_node": 512, "cores_per_node": 64, "gpus_per_node": 8},
            "crusher": {"mem_per_node": 512, "cores_per_node": 64, "gpus_per_node": 8},
            "polaris": {"mem_per_node": 512, "cores_per_node": 64, "gpus_per_node": 4},
            "summit": {"mem_per_node": 512, "cores_per_node": 42, "gpus_per_node": 6},
        }

        specs = system_specs.get(system, {"mem_per_node": 256, "cores_per_node": 64, "gpus_per_node": 0})

        nodes_for_mem = int(math.ceil(memory_gb / (specs["mem_per_node"] * 0.8))) if memory_gb else 1
        total_cores = max(1, nodes_for_mem) * specs["cores_per_node"]
        cells_per_core = (max_cells / total_cores) if total_cores else 0

        if cells_per_core and cells_per_core < 10000:
            nodes_for_scaling = int(math.ceil(max_cells / (10000 * specs["cores_per_node"])))
        else:
            nodes_for_scaling = nodes_for_mem

        nodes_needed = max(1, nodes_for_mem, nodes_for_scaling)

        gpus_per_node = specs.get("gpus_per_node", 0)
        gpus_needed = nodes_needed * gpus_per_node if gpus_per_node else nodes_needed
        cells_per_gpu = int(base_cells // gpus_needed) if gpus_needed else base_cells

        max_steps = int(amr.get("max_step", 1000) or 1000)
        cell_updates = base_cells * max_steps
        walltime_hours = (cell_updates / 1e8 / gpus_needed) if gpus_needed else 0.0

        return {
            "base_cells": int(base_cells),
            "max_cells": int(max_cells),
            "memory_gb": float(memory_gb),
            "recommended_nodes": int(nodes_needed),
            "total_cores": int(nodes_needed * specs["cores_per_node"]),
            "cells_per_core": float(cells_per_core),
            "gpus_needed": int(gpus_needed),
            "cells_per_gpu": int(cells_per_gpu) if gpus_needed else int(base_cells),
            "estimated_walltime_hours": float(walltime_hours),
            "cost_node_hours": float(walltime_hours * nodes_needed),
            "max_level": max_level,
            "grid_dims": n_cell,
        }

    @classmethod
    def extract_key_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        """
        Extract key parameters for summaries or highlights.

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
        key_params: dict[str, Any] = {}

        # AMR parameters
        if "amr" in params:
            for key in ["max_level", "n_cell", "blocking_factor", "max_grid_size"]:
                if key in params["amr"]:
                    key_params[f"amr.{key}"] = params["amr"][key]

        # Time stepping (top-level group)
        for key in ["stop_time", "max_step"]:
            if key in params.get("", {}):
                key_params[key] = params[""][key]

        return key_params

    @classmethod
    def _resource_bytes_per_cell(cls, config: dict[str, Any]) -> int:
        return 200

    @staticmethod
    def _parse_vector(value: Any) -> list[int]:
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        if isinstance(value, str):
            parts = value.split()
            return [int(p) for p in parts if p.strip()]
        return []

    @staticmethod
    def _format_vector(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return " ".join(str(v) for v in value)
        return str(value)

    @staticmethod
    def _infer_dims(prob_lo: str, n_cell: str) -> int | None:
        if n_cell and n_cell != "unknown":
            return len(str(n_cell).split())
        if prob_lo:
            return len(str(prob_lo).split())
        return None
